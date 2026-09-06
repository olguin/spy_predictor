import { spawn } from "node:child_process";

const child = spawn(
  "uv",
  [
    "run",
    "--project",
    "python",
    "python",
    "-m",
    "spy_predictor_quant.phase1",
    "--config",
    "config/phase1.json",
    "--repo-root",
    ".",
    ...process.argv.slice(2)
  ],
  {
    env: { ...process.env, UV_CACHE_DIR: ".uv-cache" },
    stdio: "inherit"
  }
);

const exitCode = await new Promise<number>((resolve, reject) => {
  child.once("error", reject);
  child.once("exit", (code, signal) => {
    if (signal) {
      reject(new Error(`Phase 1 terminated by signal ${signal}`));
      return;
    }
    resolve(code ?? 1);
  });
});

if (exitCode !== 0) process.exitCode = exitCode;
