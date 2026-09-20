import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const modules = {
  sources: 'meta_research_sources',
  panel: 'meta_research_panel',
  collection: 'meta_research_collection',
  'prompt-eval': 'meta_prompt_eval',
};
const [command, ...args] = process.argv.slice(2);
if (!(command in modules)) throw new Error('Choose sources, panel, collection, or prompt-eval');
const root = fileURLToPath(new URL('../', import.meta.url));
const result = spawnSync(`${root}python/.venv/bin/python`, ['-m', `spy_predictor_quant.${modules[command]}`, ...args],
  { cwd: root, stdio: 'inherit', env: process.env });
if (result.error) console.error(result.error.message);
process.exit(result.status ?? 1);
