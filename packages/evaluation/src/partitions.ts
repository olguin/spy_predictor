export interface ChronologicalPartitionConfig {
  trainFraction: number;
  validationFraction: number;
  purgeObservations: number;
  embargoObservations: number;
}

export interface ChronologicalPartitions<T> {
  train: T[];
  validation: T[];
  test: T[];
  excluded: T[];
}

export function chronologicalPartitions<T>(
  observations: readonly T[],
  config: ChronologicalPartitionConfig
): ChronologicalPartitions<T> {
  if (
    config.trainFraction <= 0 ||
    config.validationFraction <= 0 ||
    config.trainFraction + config.validationFraction >= 1
  ) {
    throw new Error("Chronological split fractions must leave non-empty test space");
  }
  if (config.purgeObservations < 0 || config.embargoObservations < 0) {
    throw new Error("Purge and embargo values cannot be negative");
  }

  const trainBoundary = Math.floor(observations.length * config.trainFraction);
  const validationBoundary = Math.floor(
    observations.length * (config.trainFraction + config.validationFraction)
  );
  const trainEnd = Math.max(0, trainBoundary - config.purgeObservations);
  const validationStart = Math.min(
    observations.length,
    trainBoundary + config.embargoObservations
  );
  const validationEnd = Math.max(
    validationStart,
    validationBoundary - config.purgeObservations
  );
  const testStart = Math.min(
    observations.length,
    validationBoundary + config.embargoObservations
  );

  const train = observations.slice(0, trainEnd);
  const validation = observations.slice(validationStart, validationEnd);
  const test = observations.slice(testStart);
  const retained = new Set([...train, ...validation, ...test]);
  const excluded = observations.filter((observation) => !retained.has(observation));
  return { train, validation, test, excluded };
}
