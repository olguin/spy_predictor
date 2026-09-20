// One ordered, fail-visible operator for the GOLDEN GOAL daily workflow.
import { existsSync, readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const python = `${root}python/.venv/bin/python`;
const argv = process.argv.slice(2);
const action = argv[0] ?? 'daily';
const execute = argv.includes('--execute');
const configFlag = argv.indexOf('--config');
const allowed = new Set(['check', 'intraday', 'prospective', 'outcomes', 'daily']);

if (!allowed.has(action)) {
  console.error('Usage: golden-goal-daily.mjs check|intraday|prospective|outcomes|daily [--execute] [--config PATH]');
  process.exit(2);
}
if (configFlag >= 0 && !argv[configFlag + 1]) {
  console.error('--config requires a path');
  process.exit(2);
}
const configPath = path.resolve(root, configFlag >= 0 ? argv[configFlag + 1] : 'config/golden-goal-daily-v1.json');

function readConfig() {
  const value = JSON.parse(readFileSync(configPath, 'utf8'));
  const required = ['symbols', 'etfs', 'runner_config', 'operations_policy', 'forecast_policy',
    'primary_sources', 'intraday_feed', 'holdings_files', 'profile_files'];
  if (value.schema_version !== 'golden-goal-daily-v1' || required.some((key) => value[key] === undefined)) {
    throw new Error('Invalid golden-goal-daily-v1 configuration');
  }
  if (!Array.isArray(value.symbols) || value.symbols.length < 1 || value.symbols.length > 10 ||
      new Set(value.symbols).size !== value.symbols.length) throw new Error('symbols must contain 1–10 unique tickers');
  if (!Array.isArray(value.etfs) || value.etfs.some((symbol) => !value.symbols.includes(symbol))) {
    throw new Error('etfs must be a subset of symbols');
  }
  for (const mapping of [value.holdings_files, value.profile_files]) {
    if (!mapping || Array.isArray(mapping) || typeof mapping !== 'object' ||
        Object.keys(mapping).some((symbol) => !value.etfs.includes(symbol))) {
      throw new Error('manual evidence keys must be configured ETFs');
    }
  }
  return value;
}

const config = readConfig();
const resolve = (value) => path.resolve(root, value);
const manualArgs = () => [
  ...Object.entries(config.holdings_files).flatMap(([symbol, value]) => ['--etf-holdings', `${symbol}=${resolve(value)}`]),
  ...Object.entries(config.profile_files).flatMap(([symbol, value]) => ['--etf-profile', `${symbol}=${resolve(value)}`])
];
const prospectiveArgs = () => [
  'prospective', '--symbols', ...config.symbols, '--etfs', ...config.etfs,
  '--runner-config', resolve(config.runner_config),
  '--operations-policy', resolve(config.operations_policy),
  '--forecast-policy', resolve(config.forecast_policy),
  '--primary-sources', resolve(config.primary_sources), ...manualArgs()
];

function invoke(command, args, label, capture = true) {
  const result = spawnSync(command, args, {
    cwd: root, env: process.env, encoding: 'utf8', stdio: capture ? 'pipe' : 'inherit',
    maxBuffer: 4 * 1024 * 1024
  });
  if (capture && result.stdout) process.stdout.write(result.stdout);
  if (capture && result.stderr) process.stderr.write(result.stderr);
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${label} exited with status ${result.status}`);
  if (!capture) return null;
  try { return JSON.parse(result.stdout); }
  catch { throw new Error(`${label} did not return JSON`); }
}

function readiness() {
  const requiredPaths = [config.runner_config, config.operations_policy, config.forecast_policy,
    config.primary_sources, ...Object.values(config.holdings_files), ...Object.values(config.profile_files)];
  const missingPaths = requiredPaths.filter((value) => !existsSync(resolve(value)));
  const missingHoldings = config.etfs.filter((symbol) => !(symbol in config.holdings_files));
  const missingProfiles = config.etfs.filter((symbol) => !(symbol in config.profile_files));
  const runner = JSON.parse(readFileSync(resolve(config.runner_config), 'utf8'));
  const pi = missingPaths.length ? null : invoke(resolve(runner.argv[0]), ['--preflight'], 'Pi preflight');
  const operations = invoke(python, ['-m', 'spy_predictor_quant.meta_operations', 'doctor',
    '--policy', resolve(config.operations_policy)], 'operations doctor');
  const alpaca = invoke(process.execPath, ['--import', 'tsx', 'apps/cli/src/alpaca-check.ts'], 'Alpaca check');
  let massive = null;
  if (process.env.MASSIVE_API_KEY) {
    try {
      massive = invoke(process.execPath, ['--import', 'tsx', 'apps/cli/src/massive-check.ts'], 'Massive check');
    } catch (error) {
      massive = { status: 'unavailable', indices: { status: 'check_failed',
        requested: ['I:VIX', 'I:VIX3M'], reason: error instanceof Error ? error.message : String(error) } };
    }
  }
  const environment = {
    alpaca_key: Boolean(process.env.APCA_API_KEY_ID),
    alpaca_secret: Boolean(process.env.APCA_API_SECRET_KEY),
    sec_user_agent: Boolean(process.env.SEC_USER_AGENT),
    massive_key: Boolean(process.env.MASSIVE_API_KEY)
  };
  const blocked = missingPaths.length || !environment.alpaca_key || !environment.alpaca_secret ||
    !environment.sec_user_agent || pi?.oauth_configured !== true || operations?.status !== 'OK' ||
    alpaca?.status !== 'ok';
  const status = blocked ? 'BLOCKED' : massive?.indices?.status === 'ok' ? 'READY' : 'DEGRADED';
  const result = { schema_version: 'golden-goal-readiness-v1', status,
    config: configPath, symbols: config.symbols, etfs: config.etfs, environment,
    pi: pi && { runtime: pi.runtime, version: pi.pi_version, oauth_configured: pi.oauth_configured },
    operations: operations?.status, alpaca: alpaca?.status,
    current_volatility: massive?.indices ?? { status: 'missing_key', requested: ['I:VIX', 'I:VIX3M'] },
    manual_evidence: { status: missingHoldings.length || missingProfiles.length ? 'PARTIAL' : 'COMPLETE',
      missing_holdings: missingHoldings, missing_profiles: missingProfiles },
    missing_paths: missingPaths };
  console.log(JSON.stringify(result, null, 2));
  return result;
}

function prospective(doExecute = false) {
  return invoke(python, ['-m', 'spy_predictor_quant.meta_scheduler', ...prospectiveArgs(),
    ...(doExecute ? ['--execute'] : [])], doExecute ? 'prospective execute' : 'prospective dry-run');
}

function outcomes(doExecute = false) {
  return invoke(python, ['-m', 'spy_predictor_quant.meta_scheduler', 'outcomes',
    '--operations-policy', resolve(config.operations_policy), ...(doExecute ? ['--execute'] : [])],
  doExecute ? 'outcomes execute' : 'outcomes dry-run');
}

function intraday() {
  if (!execute) {
    console.log(JSON.stringify({ status: 'DRY_RUN', action: 'intraday', writes: false,
      instruction: 'Append --execute to acquire data and run all agents.' }, null, 2));
    return;
  }
  invoke(python, ['-m', 'spy_predictor_quant.meta_analysis', 'analyze',
    '--symbols', ...config.symbols, '--etfs', ...config.etfs,
    '--runner-config', resolve(config.runner_config), '--operations-policy', resolve(config.operations_policy),
    '--forecast-policy', resolve(config.forecast_policy), '--primary-sources', resolve(config.primary_sources),
    '--market-data-mode', 'intraday', '--intraday-feed', config.intraday_feed, ...manualArgs()],
  'intraday analysis', false);
}

try {
  if (action === 'check') readiness();
  else if (action === 'intraday') intraday();
  else if (action === 'prospective') prospective(execute);
  else if (action === 'outcomes') outcomes(execute);
  else {
    const ready = readiness();
    const closePlan = prospective(false);
    const outcomePlan = outcomes(false);
    if (!execute) {
      console.log(JSON.stringify({ status: 'DRY_RUN_COMPLETE', writes: false,
        readiness: ready.status, prospective_would_execute: closePlan.would_execute,
        outcomes_would_execute: outcomePlan.would_execute }, null, 2));
    } else if (ready.status === 'BLOCKED') {
      throw new Error('Daily execution blocked by readiness checks');
    } else {
      let closeResult = { status: 'ABSTAINED', reason: 'prospective guard is not ready' };
      let closeError = null;
      if (closePlan.would_execute) {
        try { closeResult = prospective(true); }
        catch (error) { closeError = error instanceof Error ? error.message : String(error); }
      }
      let outcomeResult = null;
      let outcomeError = null;
      try { outcomeResult = outcomes(true); }
      catch (error) { outcomeError = error instanceof Error ? error.message : String(error); }
      const status = closeError || outcomeError ? 'DEGRADED' : 'COMPLETE';
      console.log(JSON.stringify({ status, prospective: closeResult, outcomes: outcomeResult,
        errors: { prospective: closeError, outcomes: outcomeError } }, null, 2));
      if (status !== 'COMPLETE') process.exitCode = 1;
    }
  }
} catch (error) {
  console.error(`golden-goal-daily: ${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
}
