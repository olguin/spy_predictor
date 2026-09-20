#!/usr/bin/env node
// Load .env with node --env-file=.env; credentials remain inherited environment.
import { spawn } from "node:child_process";
const child = spawn("python/.venv/bin/python", ["-m", "spy_predictor_quant.investment_research", ...process.argv.slice(2)],
  { stdio: "inherit", env: process.env });
child.on("error", () => { console.error("Investment research Python environment unavailable"); process.exitCode = 1; });
child.on("exit", (code, signal) => { process.exitCode = code ?? (signal ? 1 : 0); });
