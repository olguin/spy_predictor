import { describe, expect, it } from "vitest";
import { compareInstants, type TargetDefinition } from "@spy-predictor/domain";
import { createSyntheticMarketProvider } from "@spy-predictor/data-providers";
import { SnapshotBuilder } from "./snapshot-builder";
import { TargetGenerator } from "./target-generator";

const definition: TargetDefinition = {
  id: "spy-open-30m-v1",
  instrument: "SPY",
  predictionTime: "09:29:00",
  targetStart: "09:31:00",
  targetEnd: "10:00:00",
  timezone: "America/New_York",
  neutralThreshold: 0.001
};

describe("snapshot and target generation", () => {
  it("builds identical immutable snapshots from identical inputs", async () => {
    const { provider, dates } = createSyntheticMarketProvider(4);
    const date = dates[1]!;
    const builder = new SnapshotBuilder(provider);
    const first = await builder.build(date, definition);
    const second = await builder.build(date, definition);

    expect(first).toEqual(second);
    expect(first.id).toBe(`snap_${first.hash.slice(0, 20)}`);
    expect(
      first.sourceManifest.every(
        (entry) => compareInstants(entry.latestFirstSeenAt, first.dataCutoff) <= 0
      )
    ).toBe(true);
  });

  it("keeps future outcomes separate from the snapshot", async () => {
    const { provider, dates } = createSyntheticMarketProvider(4);
    const date = dates[2]!;
    const snapshot = await new SnapshotBuilder(provider).build(date, definition);
    const target = await new TargetGenerator(provider).generate(
      date,
      snapshot,
      definition
    );

    expect(compareInstants(snapshot.dataCutoff, target.startTime)).toBeLessThan(0);
    expect(["DOWN", "NEUTRAL", "UP"]).toContain(target.directionLabel);
    expect(target.realizedVolatility).toBeGreaterThanOrEqual(0);
  });
});
