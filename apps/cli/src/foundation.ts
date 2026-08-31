import { execFileSync } from "node:child_process";
import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import {
  contentHash,
  type ExperimentManifest,
  type FoundationObservation,
  type TargetDefinition
} from "@spy-predictor/domain";
import { createSyntheticMarketProvider } from "@spy-predictor/data-providers";
import {
  chronologicalPartitions,
  evaluateHistoricalClassFrequency,
  type ChronologicalPartitionConfig
} from "@spy-predictor/evaluation";
import {
  FileExperimentStore,
  PostgresExperimentStore,
  ArtifactSchemaValidator,
  ValidatingExperimentStore,
  experimentRunId,
  researchDefinitionId,
  resolveCodeIdentity
} from "@spy-predictor/persistence";
import {
  FEATURE_VERSION,
  SNAPSHOT_SCHEMA_VERSION,
  SnapshotBuilder,
  TargetGenerator
} from "@spy-predictor/snapshot-engine";

interface FoundationConfig {
  datasetVersion: string;
  seed: number;
  tradingDays: number;
  target: TargetDefinition;
  partition: ChronologicalPartitionConfig;
}

export interface FoundationRunResult {
  experimentId: string;
  generatedObservations: number;
  reusedObservations: number;
  status: "paused" | "completed";
  experimentDirectory: string;
}

function validateConfig(value: unknown): FoundationConfig {
  const config = value as Partial<FoundationConfig>;
  if (
    typeof config.datasetVersion !== "string" ||
    typeof config.seed !== "number" ||
    typeof config.tradingDays !== "number" ||
    !config.target ||
    !config.partition
  ) {
    throw new Error("Invalid foundation configuration");
  }
  if (config.target.timezone !== "America/New_York") {
    throw new Error("V0.1 market-session timezone must be America/New_York");
  }
  return config as FoundationConfig;
}

export async function runFoundation(
  repoRoot: string,
  stopAfter?: number
): Promise<FoundationRunResult> {
  const configPath = join(repoRoot, "config", "foundation.json");
  const config = validateConfig(JSON.parse(await readFile(configPath, "utf8")));
  const configHash = contentHash(config);
  const { provider, dates } = createSyntheticMarketProvider(config.tradingDays);
  if (provider.datasetVersion !== config.datasetVersion) {
    throw new Error(
      `Provider dataset ${provider.datasetVersion} does not match config ${config.datasetVersion}`
    );
  }
  const codeIdentity = await resolveCodeIdentity(repoRoot);
  const definitionId = researchDefinitionId("foundation", configHash);
  const experimentId = experimentRunId(
    "foundation",
    definitionId,
    codeIdentity,
    provider.datasetVersion
  );
  const evaluationDates = dates.slice(1);
  const metadataStore = process.env.DATABASE_URL
    ? new PostgresExperimentStore(
        join(repoRoot, "experiments"),
        experimentId,
        process.env.DATABASE_URL
      )
    : new FileExperimentStore(join(repoRoot, "experiments"), experimentId);
  const store = new ValidatingExperimentStore(
    metadataStore,
    await ArtifactSchemaValidator.fromRepository(repoRoot)
  );
  const manifest: ExperimentManifest = {
    manifestVersion: "experiment-manifest-v2",
    researchDefinitionId: definitionId,
    experimentId,
    codeCommit: codeIdentity.commit ?? "uncommitted",
    codeIdentity,
    datasetVersion: provider.datasetVersion,
    snapshotSchemaVersion: SNAPSHOT_SCHEMA_VERSION,
    targetDefinition: config.target,
    featureVersion: FEATURE_VERSION,
    agentVersions: ["mock-runtime-interface-v1"],
    models: ["historical-class-frequency"],
    randomSeed: config.seed,
    configHash,
    configuration: config,
    createdAt: new Date().toISOString()
  };
  const state = await store.initialize(manifest, evaluationDates.length);
  state.status = "running";
  await store.saveState(state);

  const builder = new SnapshotBuilder(provider);
  const targetGenerator = new TargetGenerator(provider);
  const observations: FoundationObservation[] = [];
  let generatedObservations = 0;
  let reusedObservations = 0;

  for (const date of evaluationDates) {
    const existing = await store.loadObservation(date);
    if (existing && state.completedDates.includes(date)) {
      observations.push(existing);
      reusedObservations += 1;
      continue;
    }

    const snapshot = await builder.build(date, config.target);
    const target = await targetGenerator.generate(date, snapshot, config.target);
    const observation = { date, snapshot, target };
    await store.saveObservation(observation);
    observations.push(observation);
    if (!state.completedDates.includes(date)) state.completedDates.push(date);
    state.checkpointVersion += 1;
    state.updatedAt = new Date().toISOString();
    await store.saveState(state);
    generatedObservations += 1;

    if (stopAfter !== undefined && generatedObservations >= stopAfter) {
      state.status = "paused";
      state.updatedAt = new Date().toISOString();
      await store.saveState(state);
      await store.close?.();
      return {
        experimentId,
        generatedObservations,
        reusedObservations,
        status: "paused",
        experimentDirectory: store.directory
      };
    }
  }

  observations.sort((left, right) => left.date.localeCompare(right.date));
  const partitions = chronologicalPartitions(observations, config.partition);
  const evaluation = evaluateHistoricalClassFrequency(
    partitions.train,
    partitions.validation,
    partitions.test
  );
  await store.saveArtifact("evaluation.json", {
    experimentId,
    partitionSizes: {
      train: partitions.train.length,
      validation: partitions.validation.length,
      test: partitions.test.length,
      excluded: partitions.excluded.length
    },
    evaluation
  });

  const ndjsonPath = join(store.directory, "artifacts", "observations.ndjson");
  const records = observations.map((observation) =>
    JSON.stringify({
      date: observation.date,
      snapshotId: observation.snapshot.id,
      snapshotHash: observation.snapshot.hash,
      predictionTime: observation.snapshot.predictionTime,
      dataCutoff: observation.snapshot.dataCutoff,
      overnightReturn: observation.snapshot.technicalFeatures.overnightReturn,
      targetStart: observation.target.startTime,
      targetEnd: observation.target.endTime,
      return: observation.target.return,
      directionLabel: observation.target.directionLabel,
      realizedVolatility: observation.target.realizedVolatility,
      absoluteReturn: observation.target.absoluteReturn,
      highLowRange: observation.target.highLowRange
    })
  );
  await writeFile(ndjsonPath, `${records.join("\n")}\n`, "utf8");

  const datasetDirectory = join(repoRoot, "datasets", "foundation", experimentId);
  execFileSync(
    "uv",
    [
      "run",
      "--project",
      join(repoRoot, "python"),
      "python",
      "-m",
      "spy_predictor_quant.materialize",
      "--input",
      ndjsonPath,
      "--parquet",
      join(datasetDirectory, "observations.parquet"),
      "--database",
      join(datasetDirectory, "experiment.duckdb")
    ],
    {
      cwd: repoRoot,
      stdio: "inherit",
      env: { ...process.env, UV_CACHE_DIR: join(repoRoot, ".uv-cache") }
    }
  );

  state.status = "completed";
  state.updatedAt = new Date().toISOString();
  await store.saveState(state);
  await store.close?.();
  return {
    experimentId,
    generatedObservations,
    reusedObservations,
    status: "completed",
    experimentDirectory: store.directory
  };
}
