"""Publish deterministic evidence for the repaired laws without releasing draws."""
from dataclasses import replace
from datetime import date
from fractions import Fraction
import json
import math
from pathlib import Path

from spy_predictor_quant.cycle1_calendar import _xnys
from spy_predictor_quant.cycle1_null_law import MarkedKernel, Transition, audit_conditional_law
from spy_predictor_quant.cycle1_power_gate import _publish_once
from spy_predictor_quant.cycle1_redesign import load_proposal
from spy_predictor_quant.cycle1_successor_equations import (
    EQUATION_HASH, MonthInnovations, SessionInnovations, run_equations, derive_successor_targets,
)
from spy_predictor_quant.cycle1_successor_laws import (
    REPAIR_HASH, REPAIR_SPEC, NULL_IDS, validate_repair_scenario, partial_null_mean,
)
from spy_predictor_quant.market_archive import content_hash, file_sha256


def _inputs(start, end):
    first, last = start.year * 12 + start.month - 3, end.year * 12 + end.month - 1
    monthly = tuple(MonthInnovations(date(i // 12, i % 12 + 1, 1)) for i in range(first, last + 1))
    daily = tuple(SessionInnovations(row.date()) for row in _xnys().sessions_in_range(start.isoformat(), end.isoformat())[1:])
    return monthly, daily


def marked_regime_law(scenario: dict) -> dict:
    rho = Fraction(str(scenario['predictorPersistence']))
    stay = (1 + rho) / 2
    groups = {f'{r}:{x}': str(r) for r in (-1, 1) for x in (0, 1)}
    rows = {f'{r}:{extra}': tuple(Transition(f'{nxt}:{x}', r, probability * xp)
              for nxt, probability in ((r, stay), (-r, 1 - stay))
              for x, xp in ((extra, Fraction(99, 100)), (1 - extra, Fraction(1, 100))))
            for r in (-1, 1) for extra in (0, 1)}
    return audit_conditional_law(MarkedKernel(groups, rows))


def repair_review(root: Path) -> dict:
    proposal = load_proposal(root)
    config = json.loads((root / proposal['preregistrationPath']).read_text())
    scenarios = proposal['preserved']['scenarios']
    for scenario in scenarios:
        validate_repair_scenario(scenario)
    start, end = date(2019, 12, 31), date(2020, 12, 31)
    monthly, daily = _inputs(start, end)
    daily = tuple(replace(row, spy_overnight=-2000.) if row.session == date(2020, 3, 2) else row for row in daily)
    positive = run_equations(start=start, end=end, monthly=monthly, daily=daily,
                            scenario=scenarios[0], config=config, repaired=True)
    targets = derive_successor_targets(positive, (start,))
    for row, expected in zip(targets, (.04, .048), strict=True):
        if not math.isclose(row['annualExcessLogReturn'], expected, abs_tol=1e-12):
            raise ValueError('Distribution repair changed the intended annual return')

    start, end = date(1999, 12, 31), date(2008, 12, 31)
    monthly, daily = _inputs(start, end)
    monthly = tuple(replace(row, spy_student=math.sin(i), qqq_student=math.cos(i),
                            baseline_uniform=0. if i % 9 == 0 else .5,
                            macro_normals=(math.sin(i), math.cos(i), .1, -.1))
                    for i, row in enumerate(monthly))
    changed_daily = tuple(replace(row, spy_overnight=(-1.) ** i * 3.) if row.session.year == 2007 else row
                          for i, row in enumerate(daily))
    partial = next(s for s in scenarios if s['id'] == 'partial-null-strong-baseline')
    paths = [run_equations(start=start, end=end, monthly=monthly, daily=d,
                          scenario=partial, config=config, repaired=True) for d in (daily, changed_daily)]
    origin = date(2007, 12, 31)
    states = [next(s for s in p['features']['SPY'] if s['origin'] == origin.isoformat()) for p in paths]
    labels = [derive_successor_targets(p, (origin,))[0]['annualExcessLogReturn'] for p in paths]
    stress = [s['dimensionScores']['stress'] for s in states]
    if stress[0] == stress[1] or not math.isclose(labels[0], labels[1], abs_tol=1e-12):
        raise ValueError('Actual-feature partial-null coupling failed')
    available = [s for s in paths[0]['features']['SPY'] if s['status'] == 'AVAILABLE']
    if {math.copysign(1, s['dimensionScores']['valuation']) for s in available} != {-1., 1.}:
        raise ValueError('Fixture must exercise both observed baseline regimes')
    kernel = marked_regime_law(partial)
    if not kernel['sufficientAllHorizonCondition']:
        raise ValueError('Partial-null marked kernel failed')

    report = {
        'schemaVersion': 'cycle1-successor-repair-review-v1',
        'status': 'SPECIFIC_BLOCKERS_REPAIRED_NOT_REGISTERED',
        'proposalHash': proposal['proposalHash'], 'repairHash': REPAIR_HASH,
        'equationHash': content_hash({'base': EQUATION_HASH, 'repair': REPAIR_HASH}),
        'repairSpecification': REPAIR_SPEC,
        'implementationHashes': {name: file_sha256(Path(__file__).with_name(name)) for name in (
            'cycle1_successor_repair_review.py', 'cycle1_successor_laws.py',
            'cycle1_successor_equations.py', 'cycle1_successor_features.py',
            'cycle1_successor_inputs.py', 'cycle1_successor_calendar.py',
            'cycle1_features.py', 'cycle1_calendar.py', 'cycle1_null_law.py')},
        'requiredNullScenarios': sorted(NULL_IDS),
        'distributionRepair': {'formerFailureShock': -2000., 'allPricesPositive': True,
            'annualTargets': targets, 'paymentKnownBeforeExOpen': True,
            'monthlyReturnLawPreserved': True, 'discardedOrRedrawnPaths': 0},
        'globalNullProof': 'Future monthly excess increments are iid and independent of the origin filtration; their twelve-fold convolution is unchanged after conditioning on any causal feature. Daily persistent bridges and cash cancel from each monthly excess increment.',
        'partialNullProof': 'After deterministic warmup, sign(actual SPY valuation)=R. The joint next-R/excess-return kernel depends only on R, hence the annual law depends only on R by induction. Conditioning additionally on direction or stress cannot alter that law.',
        'partialNullKernel': kernel,
        'partialNullNoise': 'Convolve the exact regime-reward law, scaled by 0.08/12 and shifted by 0.04, with twelve iid standardized-Student times independent-lognormal innovations.',
        'actualFeatureCoupling': {'origin': origin.isoformat(), 'availableOriginsInFixture': len(available),
            'stressScores': stress, 'annualExcessReturns': labels,
            'conditionalAnnualMeans': {str(r): partial_null_mean(r, partial) for r in (-1, 1)}},
        'limits': ['Independent innovation laws still need enforcement in the registered sampler.',
                   'Information-null proofs do not guarantee equal finite-sample fitted-model losses or passing false-qualification bounds.',
                   'Partial-null CPI is a synthetic observability control, not a realistic inflation model or a secondary-workbench data source.',
                   'SPY primary null proof does not qualify QQQ, drawdown, allocation or real investment performance.'],
        'pending': ['final-amended-authority-links-and-atomic-single-redesign-registration',
                    'full-path-evaluator-adapter-and-all-branch-parity',
                    'registered-development-sampler-and-full-procedure-profile',
                    'gated-locked-20000-replication-audit'],
        'randomDraws': 0, 'redesignSlotsConsumed': 0, 'fullProcedureQualified': False,
        'realDataApproval': False,
    }
    report['reportHash'] = content_hash(report)
    return report


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=Path('.'))
    root = parser.parse_args().repo_root.resolve()
    report = repair_review(root)
    path = root / 'reports' / ('cycle1-successor-repair-' + report['reportHash'][:16]) / 'report.json'
    _publish_once(path, report)
    print(json.dumps({'status': report['status'], 'reportPath': str(path), 'reportHash': report['reportHash']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
