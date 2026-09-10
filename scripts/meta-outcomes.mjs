// Load existing credentials with: node --env-file=.env scripts/meta-outcomes.mjs …
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const result = spawnSync(`${root}python/.venv/bin/python`,
  ['-m', 'spy_predictor_quant.meta_outcomes', ...process.argv.slice(2)],
  { cwd: root, stdio: 'inherit', env: process.env });
if (result.error) console.error(result.error.message);
process.exit(result.status ?? 1);
