import { execFileSync } from "node:child_process";
import { mkdir, mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import {
  experimentRunId,
  researchDefinitionId,
  resolveCodeIdentity
} from "./code-identity";

describe("code-aware experiment identity", () => {
  it("is stable for identical source and changes at the cache boundary", async () => {
    const root = await mkdtemp(join(tmpdir(), "spy-identity-"));
    execFileSync("git", ["init", "--quiet"], { cwd: root });
    await writeFile(join(root, "source.ts"), "export const value = 1;\n");
    execFileSync("git", ["add", "source.ts"], { cwd: root });
    execFileSync(
      "git",
      ["-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "--quiet", "-m", "fixture"],
      { cwd: root }
    );
    const first = await resolveCodeIdentity(root);
    const same = await resolveCodeIdentity(root);
    const definition = researchDefinitionId("foundation", "config");
    expect(same).toEqual(first);
    expect(experimentRunId("foundation", definition, same, "dataset")).toBe(
      experimentRunId("foundation", definition, first, "dataset")
    );

    await mkdir(join(root, "reports"));
    await writeFile(join(root, "reports", "generated.json"), "{}\n");
    expect(await resolveCodeIdentity(root)).toEqual(first);

    await writeFile(join(root, "source.ts"), "export const value = 2;\n");
    const changed = await resolveCodeIdentity(root);
    expect(changed.sourceTreeHash).not.toBe(first.sourceTreeHash);
    expect(experimentRunId("foundation", definition, changed, "dataset")).not.toBe(
      experimentRunId("foundation", definition, first, "dataset")
    );
  });
});
