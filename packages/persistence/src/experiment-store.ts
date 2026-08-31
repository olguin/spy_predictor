import { contentHash, type ExperimentManifest, type ExperimentState, type FoundationObservation } from "@spy-predictor/domain";

export interface ExperimentStore {
  readonly directory: string;
  readonly experimentId: string;
  initialize(manifest: ExperimentManifest, totalDates: number): Promise<ExperimentState>;
  saveObservation(observation: FoundationObservation): Promise<void>;
  loadObservation(date: string): Promise<FoundationObservation | undefined>;
  saveState(state: ExperimentState): Promise<void>;
  saveArtifact(name: string, value: unknown): Promise<void>;
  close?(): Promise<void>;
}

export function reusableManifestIdentity(manifest: ExperimentManifest): string {
  return contentHash({
    manifestVersion: manifest.manifestVersion,
    researchDefinitionId: manifest.researchDefinitionId,
    experimentId: manifest.experimentId,
    codeIdentity: manifest.codeIdentity,
    datasetVersion: manifest.datasetVersion,
    snapshotSchemaVersion: manifest.snapshotSchemaVersion,
    targetDefinition: manifest.targetDefinition,
    featureVersion: manifest.featureVersion,
    agentVersions: manifest.agentVersions,
    models: manifest.models,
    randomSeed: manifest.randomSeed,
    configHash: manifest.configHash,
    configuration: manifest.configuration
  });
}
