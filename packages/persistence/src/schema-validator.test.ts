import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { createSyntheticMarketProvider } from "@spy-predictor/data-providers";
import type { TargetDefinition } from "@spy-predictor/domain";
import { SnapshotBuilder, TargetGenerator } from "@spy-predictor/snapshot-engine";
import { ArtifactSchemaValidator } from "./schema-validator";

const definition: TargetDefinition = {
  id: "schema-target-v1",
  instrument: "SPY",
  predictionTime: "09:29:00",
  targetStart: "09:31:00",
  targetEnd: "10:00:00",
  timezone: "America/New_York",
  neutralThreshold: 0.001
};

describe("language-neutral persisted artifact schemas", () => {
  it("accepts generated artifacts and rejects malformed content", async () => {
    const repoRoot = fileURLToPath(new URL("../../../", import.meta.url));
    const validator = await ArtifactSchemaValidator.fromRepository(repoRoot);
    const { provider, dates } = createSyntheticMarketProvider(3);
    const snapshot = await new SnapshotBuilder(provider).build(dates[1]!, definition);
    const target = await new TargetGenerator(provider).generate(dates[1]!, snapshot, definition);
    expect(() => validator.snapshot(snapshot)).not.toThrow();
    expect(() => validator.target(target)).not.toThrow();
    expect(() => validator.snapshot({ ...snapshot, hash: "invalid" })).toThrow(
      "schema validation failed"
    );
  });
});
