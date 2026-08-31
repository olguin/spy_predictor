import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { join } from "node:path";
import type {
  ExperimentManifest,
  ExperimentState,
  FoundationObservation
} from "@spy-predictor/domain";
import { contentHash } from "@spy-predictor/domain";
import type { ExperimentStore } from "./experiment-store";
import { reusableManifestIdentity } from "./experiment-store";

async function readJson<T>(path: string): Promise<T | undefined> {
  try {
    return JSON.parse(await readFile(path, "utf8")) as T;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return undefined;
    throw error;
  }
}

async function writeJsonAtomic(path: string, value: unknown): Promise<void> {
  const temporaryPath = `${path}.${process.pid}.tmp`;
  await writeFile(temporaryPath, `${JSON.stringify(value, null, 2)}\n`, "utf8");
  await rename(temporaryPath, path);
}

export class FileExperimentStore implements ExperimentStore {
  readonly directory: string;
  private readonly observationsDirectory: string;

  constructor(root: string, readonly experimentId: string) {
    this.directory = join(root, experimentId);
    this.observationsDirectory = join(this.directory, "observations");
  }

  async initialize(
    manifest: ExperimentManifest,
    totalDates: number
  ): Promise<ExperimentState> {
    await mkdir(this.observationsDirectory, { recursive: true });
    const manifestPath = join(this.directory, "manifest.json");
    const existingManifest = await readJson<ExperimentManifest>(manifestPath);
    if (
      existingManifest &&
      reusableManifestIdentity(existingManifest) !== reusableManifestIdentity(manifest)
    ) {
      throw new Error(
        `Experiment ${this.experimentId} has an incompatible immutable manifest`
      );
    }
    if (!existingManifest) await writeJsonAtomic(manifestPath, manifest);

    const statePath = join(this.directory, "state.json");
    const existingState = await readJson<ExperimentState>(statePath);
    if (existingState) return existingState;
    const state: ExperimentState = {
      experimentId: this.experimentId,
      status: "running",
      completedDates: [],
      totalDates,
      checkpointVersion: 0,
      updatedAt: new Date().toISOString()
    };
    await writeJsonAtomic(statePath, state);
    return state;
  }

  async saveObservation(observation: FoundationObservation): Promise<void> {
    const path = join(this.observationsDirectory, `${observation.date}.json`);
    const existing = await readJson<FoundationObservation>(path);
    if (existing && contentHash(existing) !== contentHash(observation)) {
      throw new Error(
        `Observation ${observation.date} is immutable and already has different content`
      );
    }
    if (!existing) await writeJsonAtomic(path, observation);
  }

  loadObservation(date: string): Promise<FoundationObservation | undefined> {
    return readJson(join(this.observationsDirectory, `${date}.json`));
  }

  async saveState(state: ExperimentState): Promise<void> {
    await writeJsonAtomic(join(this.directory, "state.json"), state);
  }

  async saveArtifact(name: string, value: unknown): Promise<void> {
    await mkdir(join(this.directory, "artifacts"), { recursive: true });
    await writeJsonAtomic(join(this.directory, "artifacts", name), value);
  }
}
