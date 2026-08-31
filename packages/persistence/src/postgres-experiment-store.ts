import type { Pool as PoolType, PoolClient } from "pg";
import pg from "pg";
import type {
  ExperimentManifest,
  ExperimentState,
  FoundationObservation
} from "@spy-predictor/domain";
import { contentHash } from "@spy-predictor/domain";
import type { ExperimentStore } from "./experiment-store";
import { reusableManifestIdentity } from "./experiment-store";
import { FileExperimentStore } from "./file-experiment-store";

const { Pool } = pg;

export class PostgresExperimentStore implements ExperimentStore {
  private readonly pool: PoolType;
  private readonly files: FileExperimentStore;

  constructor(root: string, readonly experimentId: string, databaseUrl: string) {
    this.pool = new Pool({ connectionString: databaseUrl });
    this.files = new FileExperimentStore(root, experimentId);
  }

  get directory(): string { return this.files.directory; }

  private async transaction<T>(work: (client: PoolClient) => Promise<T>): Promise<T> {
    const client = await this.pool.connect();
    try {
      await client.query("BEGIN");
      const result = await work(client);
      await client.query("COMMIT");
      return result;
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    } finally {
      client.release();
    }
  }

  async initialize(manifest: ExperimentManifest, totalDates: number): Promise<ExperimentState> {
    const localState = await this.files.initialize(manifest, totalDates);
    const state = await this.transaction(async (client) => {
      const existing = await client.query<{ manifest: ExperimentManifest }>(
        "SELECT manifest FROM experiments WHERE id = $1 FOR UPDATE",
        [this.experimentId]
      );
      if (existing.rowCount) {
        const persisted = existing.rows[0]!.manifest;
        if (reusableManifestIdentity(persisted) !== reusableManifestIdentity(manifest)) {
          throw new Error(`Experiment ${this.experimentId} has an incompatible PostgreSQL manifest`);
        }
      } else {
        await client.query(
          `INSERT INTO experiments (
             id, research_definition_id, experiment_type, config, code_commit,
             code_identity_hash, source_tree_hash, dirty_tree, dataset_version,
             seed, status, manifest, created_at
           ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)`,
          [
            manifest.experimentId,
            manifest.researchDefinitionId,
            "foundation",
            JSON.stringify(manifest.configuration),
            manifest.codeCommit,
            manifest.codeIdentity.identityHash,
            manifest.codeIdentity.sourceTreeHash,
            manifest.codeIdentity.dirty,
            manifest.datasetVersion,
            manifest.randomSeed,
            localState.status,
            JSON.stringify(manifest),
            manifest.createdAt
          ]
        );
      }
      const checkpoint = await client.query<{ state: ExperimentState }>(
        "SELECT state FROM experiment_checkpoints WHERE experiment_id = $1",
        [this.experimentId]
      );
      if (checkpoint.rowCount) return checkpoint.rows[0]!.state;
      await client.query(
        `INSERT INTO experiment_checkpoints (
           experiment_id, checkpoint_version, completed_items, state, updated_at
         ) VALUES ($1,$2,$3,$4,$5)`,
        [
          this.experimentId,
          localState.checkpointVersion,
          JSON.stringify(localState.completedDates),
          JSON.stringify(localState),
          localState.updatedAt
        ]
      );
      return localState;
    });
    await this.files.saveState(state);
    return state;
  }

  async saveObservation(observation: FoundationObservation): Promise<void> {
    await this.transaction(async (client) => {
      const snapshot = observation.snapshot;
      const target = observation.target;
      await client.query(
        `INSERT INTO snapshots (
           id, prediction_time, data_cutoff, schema_version, source_manifest,
           snapshot_json, hash
         ) VALUES ($1,$2,$3,$4,$5,$6,$7)
         ON CONFLICT (id) DO NOTHING`,
        [
          snapshot.id,
          snapshot.predictionTime,
          snapshot.dataCutoff,
          snapshot.schemaVersion,
          JSON.stringify(snapshot.sourceManifest),
          JSON.stringify(snapshot),
          snapshot.hash
        ]
      );
      const persistedSnapshot = await client.query<{ hash: string }>(
        "SELECT hash FROM snapshots WHERE id = $1",
        [snapshot.id]
      );
      if (persistedSnapshot.rows[0]?.hash !== snapshot.hash) {
        throw new Error(`Snapshot ${snapshot.id} is immutable and has different content`);
      }
      await client.query(
        `INSERT INTO targets (
           snapshot_id, target_definition, start_time, end_time, start_price,
           end_price, return, direction_label, realized_volatility,
           absolute_return, high_low_range, target_json
         ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
         ON CONFLICT (snapshot_id, target_definition) DO NOTHING`,
        [
          target.snapshotId,
          target.targetDefinitionId,
          target.startTime,
          target.endTime,
          target.startPrice,
          target.endPrice,
          target.return,
          target.directionLabel,
          target.realizedVolatility,
          target.absoluteReturn,
          target.highLowRange,
          JSON.stringify(target)
        ]
      );
      const persistedTarget = await client.query<{ target_json: FoundationObservation["target"] }>(
        `SELECT target_json FROM targets
         WHERE snapshot_id = $1 AND target_definition = $2`,
        [snapshot.id, target.targetDefinitionId]
      );
      if (
        !persistedTarget.rows[0] ||
        contentHash(persistedTarget.rows[0].target_json) !== contentHash(target)
      ) {
        throw new Error(
          `Target ${snapshot.id}/${target.targetDefinitionId} is immutable and has different content`
        );
      }
      await client.query(
        `INSERT INTO experiment_observations (
           experiment_id, observation_date, snapshot_id, target_definition
         ) VALUES ($1,$2,$3,$4)
         ON CONFLICT (experiment_id, observation_date) DO NOTHING`,
        [this.experimentId, observation.date, snapshot.id, target.targetDefinitionId]
      );
      const mapping = await client.query<{ snapshot_id: string; target_definition: string }>(
        `SELECT snapshot_id, target_definition FROM experiment_observations
         WHERE experiment_id = $1 AND observation_date = $2`,
        [this.experimentId, observation.date]
      );
      if (
        mapping.rows[0]?.snapshot_id !== snapshot.id ||
        mapping.rows[0]?.target_definition !== target.targetDefinitionId
      ) {
        throw new Error(`Experiment observation ${observation.date} is immutable`);
      }
    });
    await this.files.saveObservation(observation);
  }

  async loadObservation(date: string): Promise<FoundationObservation | undefined> {
    const result = await this.pool.query<{
      observation_date: string;
      snapshot_json: FoundationObservation["snapshot"];
      target_json: FoundationObservation["target"];
    }>(
      `SELECT eo.observation_date::text, s.snapshot_json, t.target_json
       FROM experiment_observations eo
       JOIN snapshots s ON s.id = eo.snapshot_id
       JOIN targets t ON t.snapshot_id = eo.snapshot_id
                     AND t.target_definition = eo.target_definition
       WHERE eo.experiment_id = $1 AND eo.observation_date = $2`,
      [this.experimentId, date]
    );
    if (!result.rowCount) return undefined;
    const row = result.rows[0]!;
    return { date: row.observation_date, snapshot: row.snapshot_json, target: row.target_json };
  }

  async saveState(state: ExperimentState): Promise<void> {
    await this.pool.query(
      `INSERT INTO experiment_checkpoints (
         experiment_id, checkpoint_version, completed_items, state, updated_at
       ) VALUES ($1,$2,$3,$4,$5)
       ON CONFLICT (experiment_id) DO UPDATE
       SET checkpoint_version = EXCLUDED.checkpoint_version,
           completed_items = EXCLUDED.completed_items,
           state = EXCLUDED.state,
           updated_at = EXCLUDED.updated_at`,
      [
        state.experimentId,
        state.checkpointVersion,
        JSON.stringify(state.completedDates),
        JSON.stringify(state),
        state.updatedAt
      ]
    );
    await this.pool.query(
      `UPDATE experiments SET status = $2,
       completed_at = CASE WHEN $2 = 'completed' THEN $3::timestamptz ELSE NULL END
       WHERE id = $1`,
      [state.experimentId, state.status, state.updatedAt]
    );
    await this.files.saveState(state);
  }

  saveArtifact(name: string, value: unknown): Promise<void> {
    return this.files.saveArtifact(name, value);
  }

  async close(): Promise<void> { await this.pool.end(); }
}
