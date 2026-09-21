"""Persist a clearly synthetic five-symbol M3 publication and monitor replay.

This deliberately uses the test worker, never a provider or the frozen M4 cases.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'python/tests'))
from test_investment_research_m3 import m3_mandate
from test_investment_research_m2 import FiveSymbolWorker
from spy_predictor_quant.investment_research.controller import Controller
from spy_predictor_quant.investment_research.monitor import project
from spy_predictor_quant.investment_research.publication import publish, feedback, review, read_publication


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--ledger',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists() or args.ledger.exists():
        raise ValueError('Preserve previous fixtures; use new paths')
    c=Controller(args.output,FiveSymbolWorker())
    mandate=m3_mandate()
    c.create(mandate)
    registration={'kind':'SYNTHETIC_ENGINEERING_FIXTURE','model_calls':'scripted worker, no provider calls',
        'not_evidence_of':['live-model usefulness','M4 acceptance','investment performance'],
        'fixture_source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
            ['scripts/create-investment-research-m3-fixture.py','python/tests/test_investment_research_m3.py','python/tests/test_investment_research_m2.py']}}
    (args.output/'fixture-registration.json').write_text(json.dumps(registration,indent=2)+'\n')
    state=c.run()
    if state['status']!='DRAFT':
        raise ValueError(state.get('stop_reason'))
    record=publish(c.store,args.ledger)
    identity=record['publication_id']
    feedback_record=feedback(args.ledger,identity,{'category':'confusing_explanation','symbol':'QQQ',
        'text':'SYNTHETIC feedback fixture: distinguish dated holdings from current exposure.','engineering_fixture':True})
    review_record=review(args.ledger,identity,{'decision':'needs_research','symbol':'QQQ',
        'reason':'SYNTHETIC manual review fixture: request current sponsor holdings.','engineering_fixture':True})
    snap=project(c.store)
    (args.output/'monitor-snapshot.json').write_text(json.dumps(snap,indent=2)+'\n')
    acceptance={'status':'PASS_SYNTHETIC_PUBLICATION_REPLAY','publication_id':identity,
        'bundle':str(args.ledger/'publications'/identity),'receipts_reconcile':snap['receipts_reconcile'],
        'frozen_bundle_verified':read_publication(args.ledger,identity)==record,
        'feedback_id':feedback_record['feedback_id'],'review_id':review_record['review_id'],
        'm4_release_cases_evaluated':False,'actual_user_usefulness_feedback':False,
        'qualification':registration}
    (args.output/'acceptance.json').write_text(json.dumps(acceptance,indent=2)+'\n')
    print(json.dumps(acceptance,indent=2))


if __name__=='__main__':
    main()
