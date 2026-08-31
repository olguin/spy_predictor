import { fileURLToPath } from "node:url";
import {
  contentHash,
  type ExperimentManifest,
  type TargetDefinition
} from "@spy-predictor/domain";
import { createSyntheticMarketProvider } from "@spy-predictor/data-providers";
import {
  ArtifactSchemaValidator,
  PostgresExperimentStore,
  ValidatingExperimentStore
} from "@spy-predictor/persistence";
import {
  FEATURE_VERSION,
  SNAPSHOT_SCHEMA_VERSION,
  SnapshotBuilder,
  TargetGenerator
} from "@spy-predictor/snapshot-engine";

const repoRoot = fileURLToPath(new URL("../../../", import.meta.url));
const databaseUrl = process.env.DATABASE_URL;
if (!databaseUrl) throw new Error("DATABASE_URL is required for database integration verification");

const experimentId = "foundation-db-integration-v2";
const definition: TargetDefinition = {
  id: "db-integration-target-v1",
  instrument: "SPY",
  predictionTime: "09:29:00",
  targetStart: "09:31:00",
  targetEnd: "10:00:00",
  timezone: "America/New_York",
  neutralThreshold: 0.001
};
const configuration = { fixture: "database-resume-v2", target: definition };
const configHash = contentHash(configuration);
const manifest: ExperimentManifest = {
  manifestVersion: "experiment-manifest-v2",
  researchDefinitionId: "foundation-definition-db-integration-v2",
  experimentId,
  codeCommit: "integration-fixture",
  codeIdentity: {
    commit: null,
    sourceTreeHash: "a".repeat(64),
    dirty: true,
    identityHash: "b".repeat(64)
  },
  datasetVersion: "synthetic-spy-v1",
  snapshotSchemaVersion: SNAPSHOT_SCHEMA_VERSION,
  targetDefinition: definition,
  featureVersion: FEATURE_VERSION,
  agentVersions: [],
  models: ["database-integration"],
  randomSeed: 42,
  configHash,
  configuration,
  createdAt: "2024-01-02T00:00:00Z"
};
const validator = await ArtifactSchemaValidator.fromRepository(repoRoot);
const makeStore = () =>
  new ValidatingExperimentStore(
    new PostgresExperimentStore(`${repoRoot}/experiments`, experimentId, databaseUrl),
    validator
  );

const { provider, dates } = createSyntheticMarketProvider(3);
const date = dates[1]!;
const snapshot = await new SnapshotBuilder(provider).build(date, definition);
const target = await new TargetGenerator(provider).generate(date, snapshot, definition);

const first = makeStore();
const state = await first.initialize(manifest, 1);
if (!state.completedDates.includes(date)) state.completedDates.push(date);
state.status = "paused";
state.checkpointVersion = Math.max(1, state.checkpointVersion);
state.updatedAt = "2024-01-03T00:00:00Z";
await first.saveObservation({ date, snapshot, target });
await first.saveState(state);
await first.close?.();

const resumedStore = makeStore();
const resumed = await resumedStore.initialize(manifest, 1);
const observation = await resumedStore.loadObservation(date);
if (!resumed.completedDates.includes(date) || !observation) {
  throw new Error("PostgreSQL checkpoint/observation resume verification failed");
}
if (observation.snapshot.hash !== snapshot.hash || observation.target.return !== target.return) {
  throw new Error("PostgreSQL persisted artifact does not match source observation");
}
await resumedStore.close?.();
console.log("PostgreSQL experiment resume verified");
