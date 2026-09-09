"""Complete-calendar deterministic integration check; never a random power run."""
from datetime import date
import json
import math
from pathlib import Path

from spy_predictor_quant.cycle1_calendar import _xnys
from spy_predictor_quant.cycle1_successor_calendar import month_end
from spy_predictor_quant.cycle1_successor_config import load_successor_config
from spy_predictor_quant.cycle1_successor_equations import MonthInnovations, SessionInnovations, run_equations
from spy_predictor_quant.cycle1_successor_pipeline import evaluate_evidence
from spy_predictor_quant.market_archive import content_hash, file_sha256


def deterministic_evidence(design: dict, config: dict) -> dict:
    start, end = month_end(1990, 1), month_end(2026, 7)
    monthly = tuple(MonthInnovations(
        date(i // 12, i % 12 + 1, 1),
        spy_student=2 * math.sin(i * .73) - (6 if i % 49 == 0 else 0),
        qqq_student=math.cos(i * .43), volatility_normal=math.sin(i * .31),
        macro_normals=tuple(math.sin(i * frequency) for frequency in (.17, .23, .37, .41)),
        baseline_uniform=.01 if i % 17 == 0 else .5,
    ) for i in range(1989 * 12 + 10, 2026 * 12 + 7))
    daily = tuple(SessionInnovations(row.date(), math.sin(i), math.cos(i),
                                     math.sin(i * .7), math.cos(i * .3))
                  for i, row in enumerate(_xnys().sessions_in_range(start.isoformat(), end.isoformat())[1:]))
    return run_equations(start=start, end=end, monthly=monthly, daily=daily,
                         scenario=design['scenarios'][0], config=config, repaired=True)


def main() -> int:
    import argparse
    from spy_predictor_quant.cycle1_power_gate import _publish_once
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=Path('.'))
    args = parser.parse_args()
    root = args.repo_root.resolve()
    design = load_successor_config(root)
    config = json.loads((root / design['preregistrationPath']).read_text())
    evidence = deterministic_evidence(design, config)
    procedure = evaluate_evidence(evidence, config, exercise_branches=True)
    files = sorted((root / 'python/src/spy_predictor_quant').glob('cycle1*.py'))
    report = {
        'schemaVersion': 'cycle1-successor-integration-fixture-v1',
        'status': 'FULL_PIPELINE_FIXTURE_NOT_REGISTERED',
        'designHash': design['designHash'],
        'implementationHashes': {p.name: file_sha256(p) for p in files},
        'procedure': procedure, 'randomDraws': 0, 'powerEstimated': False,
        'realDataApproval': False,
    }
    report['reportHash'] = content_hash(report)
    path = root / 'reports' / ('cycle1-successor-integration-' + report['reportHash'][:16]) / 'report.json'
    _publish_once(path, report)
    print(json.dumps({'status': report['status'], 'reportPath': str(path), 'reportHash': report['reportHash']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
