export type Instant = string;
export type DirectionLabel = "DOWN" | "NEUTRAL" | "UP";

export interface SourceMetadata {
  source: string;
  sourceTimestamp: Instant;
  firstSeenAt: Instant;
  effectiveTimestamp: Instant;
  ingestionTimestamp: Instant;
  version: string;
  hash: string;
}

export interface MarketBar extends SourceMetadata {
  symbol: string;
  eventTime: Instant;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface InstrumentSnapshot {
  symbol: string;
  asOf: Instant;
  latestPrice: number;
  previousClose: number;
  overnightReturn: number;
}

export interface SourceManifestEntry {
  source: string;
  datasetVersion: string;
  recordCount: number;
  earliestFirstSeenAt: Instant;
  latestFirstSeenAt: Instant;
  contentHash: string;
}

export interface DataQualityReport {
  marketDataComplete: boolean;
  newsAvailable: boolean;
  macroAvailable: boolean;
  optionsAvailable: boolean;
  staleSources: string[];
  qualityScore: number;
}

export interface MarketSnapshot {
  id: string;
  schemaVersion: string;
  predictionTime: Instant;
  dataCutoff: Instant;
  instruments: InstrumentSnapshot[];
  technicalFeatures: Record<string, number | null>;
  sourceManifest: SourceManifestEntry[];
  dataQuality: DataQualityReport;
  hash: string;
}

export interface TargetDefinition {
  id: string;
  instrument: string;
  predictionTime: string;
  targetStart: string;
  targetEnd: string;
  timezone: "America/New_York";
  neutralThreshold: number;
}

export interface MarketTarget {
  snapshotId: string;
  targetDefinitionId: string;
  startTime: Instant;
  endTime: Instant;
  startPrice: number;
  endPrice: number;
  return: number;
  directionLabel: DirectionLabel;
  realizedVolatility: number;
  absoluteReturn: number;
  highLowRange: number;
}

export interface ExperimentManifest {
  manifestVersion: "experiment-manifest-v2";
  researchDefinitionId: string;
  experimentId: string;
  codeCommit: string;
  codeIdentity: CodeIdentity;
  datasetVersion: string;
  snapshotSchemaVersion: string;
  targetDefinition: TargetDefinition;
  featureVersion: string;
  agentVersions: string[];
  models: string[];
  randomSeed: number;
  configHash: string;
  configuration: unknown;
  createdAt: Instant;
}

export interface CodeIdentity {
  commit: string | null;
  sourceTreeHash: string;
  dirty: boolean;
  identityHash: string;
}

export interface ExperimentState {
  experimentId: string;
  status: "running" | "paused" | "completed" | "failed";
  completedDates: string[];
  totalDates: number;
  checkpointVersion: number;
  updatedAt: Instant;
}

export interface FoundationObservation {
  date: string;
  snapshot: MarketSnapshot;
  target: MarketTarget;
}
