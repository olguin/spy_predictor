import type { DirectionLabel, FoundationObservation } from "@spy-predictor/domain";

const LABELS: DirectionLabel[] = ["DOWN", "NEUTRAL", "UP"];

export interface ClassProbabilities {
  pDown: number;
  pNeutral: number;
  pUp: number;
}

export interface ClassificationMetrics {
  observations: number;
  brierScore: number;
  logLoss: number;
  accuracy: number;
}

export interface BaselineEvaluation {
  baseline: "historical-class-frequency";
  fittedProbabilities: ClassProbabilities;
  validation: ClassificationMetrics;
  test: ClassificationMetrics;
}

function probabilityFor(
  probabilities: ClassProbabilities,
  label: DirectionLabel
): number {
  if (label === "DOWN") return probabilities.pDown;
  if (label === "NEUTRAL") return probabilities.pNeutral;
  return probabilities.pUp;
}

export function fitHistoricalClassFrequency(
  observations: readonly FoundationObservation[]
): ClassProbabilities {
  const counts: Record<DirectionLabel, number> = { DOWN: 1, NEUTRAL: 1, UP: 1 };
  for (const observation of observations) {
    counts[observation.target.directionLabel] += 1;
  }
  const total = observations.length + LABELS.length;
  return {
    pDown: counts.DOWN / total,
    pNeutral: counts.NEUTRAL / total,
    pUp: counts.UP / total
  };
}

export function classificationMetrics(
  observations: readonly FoundationObservation[],
  probabilities: ClassProbabilities
): ClassificationMetrics {
  if (observations.length === 0) {
    throw new Error("Cannot evaluate an empty partition");
  }
  const predicted = LABELS.reduce((best, label) =>
    probabilityFor(probabilities, label) > probabilityFor(probabilities, best)
      ? label
      : best
  );
  let brier = 0;
  let logLoss = 0;
  let correct = 0;
  for (const observation of observations) {
    const actual = observation.target.directionLabel;
    for (const label of LABELS) {
      const probability = probabilityFor(probabilities, label);
      const outcome = label === actual ? 1 : 0;
      brier += (probability - outcome) ** 2;
    }
    logLoss -= Math.log(Math.max(probabilityFor(probabilities, actual), 1e-15));
    if (predicted === actual) correct += 1;
  }
  return {
    observations: observations.length,
    brierScore: brier / observations.length,
    logLoss: logLoss / observations.length,
    accuracy: correct / observations.length
  };
}

export function evaluateHistoricalClassFrequency(
  train: readonly FoundationObservation[],
  validation: readonly FoundationObservation[],
  test: readonly FoundationObservation[]
): BaselineEvaluation {
  const fittedProbabilities = fitHistoricalClassFrequency(train);
  return {
    baseline: "historical-class-frequency",
    fittedProbabilities,
    validation: classificationMetrics(validation, fittedProbabilities),
    test: classificationMetrics(test, fittedProbabilities)
  };
}
