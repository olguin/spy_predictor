import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFile, readdir } from "node:fs/promises";
import { join, relative } from "node:path";
import { contentHash, type CodeIdentity } from "@spy-predictor/domain";

const FALLBACK_EXCLUDES = new Set([
  ".git",
  ".uv-cache",
  ".venv",
  "coverage",
  "datasets",
  "dist",
  "experiments",
  "node_modules"
]);

function isGeneratedArtifact(path: string): boolean {
  const topLevel = path.split("/", 1)[0];
  return topLevel === "backups" || topLevel === "datasets" || topLevel === "experiments" || topLevel === "reports";
}

function git(repoRoot: string, args: string[]): string | undefined {
  try {
    return execFileSync("git", args, {
      cwd: repoRoot,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"]
    });
  } catch {
    return undefined;
  }
}

async function fallbackFiles(root: string, directory = root): Promise<string[]> {
  const entries = await readdir(directory, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    if (entry.isDirectory() && FALLBACK_EXCLUDES.has(entry.name)) continue;
    const path = join(directory, entry.name);
    if (entry.isDirectory()) files.push(...(await fallbackFiles(root, path)));
    if (entry.isFile()) files.push(relative(root, path));
  }
  return files;
}

export async function sourceTreeFingerprint(repoRoot: string): Promise<string> {
  const listed = git(repoRoot, [
    "ls-files",
    "--cached",
    "--others",
    "--exclude-standard",
    "-z"
  ]);
  const paths = (
    listed === undefined
      ? await fallbackFiles(repoRoot)
      : listed.split("\0").filter((path) => path.length > 0 && !isGeneratedArtifact(path))
  ).sort();
  if (paths.length === 0) throw new Error("Cannot fingerprint an empty source tree");

  const hash = createHash("sha256");
  for (const path of paths) {
    const bytes = await readFile(join(repoRoot, path));
    hash.update(Buffer.from(`${Buffer.byteLength(path)}:${path}:${bytes.length}:`));
    hash.update(bytes);
  }
  return hash.digest("hex");
}

export async function resolveCodeIdentity(repoRoot: string): Promise<CodeIdentity> {
  const commit = git(repoRoot, ["rev-parse", "HEAD"])?.trim() || null;
  const changeListings = commit
    ? [
        git(repoRoot, ["diff", "--name-only", "-z", "HEAD"]),
        git(repoRoot, ["diff", "--cached", "--name-only", "-z", "HEAD"]),
        git(repoRoot, ["ls-files", "--others", "--exclude-standard", "-z"])
      ]
    : [];
  const dirty =
    commit === null ||
    changeListings.some((listing) => listing === undefined) ||
    changeListings.some((listing) =>
      listing!
        .split("\0")
        .some((path) => path.length > 0 && !isGeneratedArtifact(path))
    );
  const sourceTreeHash = await sourceTreeFingerprint(repoRoot);
  return {
    commit,
    sourceTreeHash,
    dirty,
    identityHash: contentHash({ commit, dirty, sourceTreeHash })
  };
}

export function researchDefinitionId(kind: string, configHash: string): string {
  return `${kind}-definition-${contentHash({ kind, configHash }).slice(0, 16)}`;
}

export function experimentRunId(
  kind: string,
  definitionId: string,
  codeIdentity: CodeIdentity,
  datasetVersion: string
): string {
  return `${kind}-${contentHash({
    definitionId,
    codeIdentityHash: codeIdentity.identityHash,
    datasetVersion
  }).slice(0, 16)}`;
}
