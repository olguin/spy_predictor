import { describe, expect, it } from "vitest";
import type { FoundationObservation } from "@spy-predictor/domain";
import { chronologicalPartitions } from "./partitions";
import { fitHistoricalClassFrequency } from "./baseline";

describe("research evaluation primitives", () => {
  it("creates ordered, non-overlapping splits with purging and embargo", () => {
    const values = Array.from({ length: 20 }, (_, index) => index);
    const split = chronologicalPartitions(values, {
      trainFraction: 0.6,
      validationFraction: 0.2,
      purgeObservations: 1,
      embargoObservations: 1
    });
    expect(split.train.at(-1)).toBeLessThan(split.validation[0]!);
    expect(split.validation.at(-1)).toBeLessThan(split.test[0]!);
    expect(split.excluded).toEqual([11, 12, 15, 16]);
  });

  it("fits smoothed probabilities that sum to one", () => {
    const labels = ["UP", "UP", "DOWN"] as const;
    const observations = labels.map(
      (directionLabel) =>
        ({ target: { directionLabel } }) as FoundationObservation
    );
    const probabilities = fitHistoricalClassFrequency(observations);
    expect(probabilities.pDown + probabilities.pNeutral + probabilities.pUp).toBeCloseTo(1);
    expect(probabilities.pUp).toBeGreaterThan(probabilities.pDown);
    expect(probabilities.pNeutral).toBeGreaterThan(0);
  });
});
