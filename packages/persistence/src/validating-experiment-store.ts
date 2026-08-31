import type { ExperimentManifest, ExperimentState, FoundationObservation } from "@spy-predictor/domain";
import type { ExperimentStore } from "./experiment-store";
import type { ArtifactSchemaValidator } from "./schema-validator";

export class ValidatingExperimentStore implements ExperimentStore {
  constructor(
    private readonly delegate: ExperimentStore,
    private readonly validator: ArtifactSchemaValidator
  ) {}

  get directory(): string { return this.delegate.directory; }
  get experimentId(): string { return this.delegate.experimentId; }

  initialize(manifest: ExperimentManifest, totalDates: number) {
    this.validator.manifest(manifest);
    return this.delegate.initialize(manifest, totalDates);
  }

  async saveObservation(observation: FoundationObservation): Promise<void> {
    this.validator.snapshot(observation.snapshot);
    this.validator.target(observation.target);
    await this.delegate.saveObservation(observation);
  }

  loadObservation(date: string) { return this.delegate.loadObservation(date); }

  async saveState(state: ExperimentState): Promise<void> {
    this.validator.state(state);
    await this.delegate.saveState(state);
  }

  saveArtifact(name: string, value: unknown) {
    return this.delegate.saveArtifact(name, value);
  }

  async close(): Promise<void> { await this.delegate.close?.(); }
}
