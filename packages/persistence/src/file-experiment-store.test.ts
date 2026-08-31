import { mkdtemp, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import type { ExperimentManifest } from "@spy-predictor/domain";
import { FileExperimentStore } from "./file-experiment-store";

const manifest: ExperimentManifest = {
  manifestVersion: "experiment-manifest-v2",
  researchDefinitionId: "foundation-definition-test",
  experimentId: "foundation-test",
  codeCommit: "test",
  codeIdentity: {
    commit: "test",
    sourceTreeHash: "source",
    dirty: false,
    identityHash: "code"
  },
  datasetVersion: "fixture-v1",
  snapshotSchemaVersion: "v1",
  targetDefinition: {
    id: "t1",
    instrument: "SPY",
    predictionTime: "09:29:00",
    targetStart: "09:31:00",
    targetEnd: "10:00:00",
    timezone: "America/New_York",
    neutralThreshold: 0.001
  },
  featureVersion: "v1",
  agentVersions: [],
  models: [],
  randomSeed: 42,
  configHash: "abc",
  configuration: { fixture: true },
  createdAt: "2024-01-01T00:00:00Z"
};

describe("resumable file experiment store", () => {
  it("loads an existing checkpoint instead of replacing it", async () => {
    const root = await mkdtemp(join(tmpdir(), "spy-predictor-"));
    const store = new FileExperimentStore(root, manifest.experimentId);
    const state = await store.initialize(manifest, 10);
    state.completedDates.push("2024-01-02");
    state.checkpointVersion += 1;
    await store.saveState(state);

    const resumed = await store.initialize(manifest, 10);
    expect(resumed.completedDates).toEqual(["2024-01-02"]);
    expect(resumed.checkpointVersion).toBe(1);
    expect(JSON.parse(await readFile(join(store.directory, "manifest.json"), "utf8"))).toEqual(manifest);
  });

  it("rejects a manifest with a different code identity", async () => {
    const root = await mkdtemp(join(tmpdir(), "spy-predictor-"));
    const store = new FileExperimentStore(root, manifest.experimentId);
    await store.initialize(manifest, 10);
    await expect(
      store.initialize(
        {
          ...manifest,
          codeIdentity: { ...manifest.codeIdentity, identityHash: "changed" }
        },
        10
      )
    ).rejects.toThrow("incompatible immutable manifest");
  });

  it("rejects overwriting an immutable observation", async () => {
    const root = await mkdtemp(join(tmpdir(), "spy-predictor-"));
    const store = new FileExperimentStore(root, manifest.experimentId);
    await store.initialize(manifest, 1);
    const first = { date: "2024-01-02", snapshot: { id: "one" }, target: {} } as never;
    await store.saveObservation(first);
    await expect(
      store.saveObservation({ date: "2024-01-02", snapshot: { id: "two" }, target: {} } as never)
    ).rejects.toThrow("immutable");
  });
});
