import { spawn } from "node:child_process";
import { delimiter, resolve } from "node:path";

const mode = process.env.IBKR_MODE?.trim();
const readOnly = process.env.IBKR_READ_ONLY?.trim().toLowerCase();

if (mode !== "paper") {
  throw new Error("IBKR_MODE must be paper for contract resolution");
}

if (readOnly !== "true") {
  throw new Error("IBKR_READ_ONLY must be true for contract resolution");
}

const python = resolve(".vendor-local/ibkr-python/bin/python");
const pythonPath = [resolve("python/src"), process.env.PYTHONPATH]
  .filter((entry): entry is string => Boolean(entry))
  .join(delimiter);
const child = spawn(
  python,
  ["-m", "spy_predictor_quant.ibkr_contracts", ...process.argv.slice(2)],
  {
    env: { ...process.env, PYTHONPATH: pythonPath },
    stdio: "inherit"
  }
);

const exitCode = await new Promise<number>((resolveExit, reject) => {
  child.once("error", reject);
  child.once("exit", (code, signal) => {
    if (signal) {
      reject(new Error(`IBKR contract resolver terminated by signal ${signal}`));
      return;
    }
    resolveExit(code ?? 1);
  });
});

if (exitCode !== 0) {
  process.exitCode = exitCode;
}
