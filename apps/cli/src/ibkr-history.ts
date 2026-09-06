import { spawn } from "node:child_process";
import { delimiter, resolve } from "node:path";

if (process.env.IBKR_MODE?.trim() !== "paper") {
  throw new Error("IBKR_MODE must be paper for historical data retrieval");
}
if (process.env.IBKR_READ_ONLY?.trim().toLowerCase() !== "true") {
  throw new Error("IBKR_READ_ONLY must be true for historical data retrieval");
}

const python = resolve(".vendor-local/ibkr-python/bin/python");
const pythonPath = [resolve("python/src"), process.env.PYTHONPATH]
  .filter((entry): entry is string => Boolean(entry))
  .join(delimiter);
const child = spawn(
  python,
  ["-m", "spy_predictor_quant.ibkr_history", ...process.argv.slice(2)],
  {
    env: { ...process.env, PYTHONPATH: pythonPath },
    stdio: "inherit"
  }
);

const exitCode = await new Promise<number>((resolveExit, reject) => {
  child.once("error", reject);
  child.once("exit", (code, signal) => {
    if (signal) {
      reject(new Error(`IBKR history downloader terminated by signal ${signal}`));
      return;
    }
    resolveExit(code ?? 1);
  });
});

if (exitCode !== 0) {
  process.exitCode = exitCode;
}
