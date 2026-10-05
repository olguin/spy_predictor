"""Live scope, temporal integrity and full report contract; all findings synthetic."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import uuid

import pytest
from spy_predictor_quant.market_archive import content_hash
from spy_predictor_quant.investment_research.inputs import live_mandate, selection
from spy_predictor_quant.investment_research.live import normalize_snapshot, as_of_record, validate_report
from spy_predictor_quant.investment_research.reporting import agent_reports
from spy_predictor_quant.investment_research.controller import Controller
from spy_predictor_quant.investment_research.broker import Broker
from spy_predictor_quant.investment_research.workspace import Workspace, QUESTION
from test_investment_research_readiness import DimensionWorker
from test_investment_research_delivery import ready_controller
from test_investment_research_m2 import result, condition
from test_investment_research import response

NOW = datetime(2026, 10, 2, 18, tzinfo=timezone.utc)


def test_idle_sleep_guard_releases_on_failure_and_skips_other_hosts(monkeypatch):
    from spy_predictor_quant.investment_research import awake
    events=[]
    class Process:
        stopped=False
        def poll(self): return 0 if self.stopped else None
        def terminate(self): self.stopped=True; events.append('terminate')
        def wait(self, timeout): events.append(('wait',timeout)); return 0
    def spawn(argv, **kwargs):
        events.append(argv); return Process()
    monkeypatch.setattr(awake.platform,'system',lambda:'Darwin')
    monkeypatch.setattr(awake.subprocess,'Popen',spawn)
    with pytest.raises(ValueError,match='worker failed'):
        with awake.keep_awake():
            assert events[0][:3]==['/usr/bin/caffeinate','-i','-w']
            raise ValueError('worker failed')
    assert events[1:]==['terminate',('wait',5)]
    events.clear()
    monkeypatch.setattr(awake.platform,'system',lambda:'Linux')
    with awake.keep_awake(): pass
    assert not events
    monkeypatch.setattr(awake.platform,'system',lambda:'Darwin')
    with awake.keep_awake(False): pass
    assert not events


def snapshot(symbol='NVDA', stamp=None):
    stamp = stamp or (NOW-timedelta(seconds=10)).isoformat()
    return {'symbol': symbol, 'latestTrade': {'t': stamp, 'p': 101},
            'latestQuote': {'t': stamp, 'bp': 100.9, 'ap': 101.1}}


@pytest.mark.parametrize('symbols,horizons', [([], [63]), (['NVDA']*2,[63]), (['BAD/URL'],[63]),
                                            (['NVDA'],[]), (['NVDA'],[True]), (['NVDA'],[20])])
def test_invalid_explicit_input_refused(symbols,horizons):
    with pytest.raises(ValueError): selection(symbols,horizons)


def test_single_multiple_and_new_primary_issuer_scope():
    query='Assess global forces and conditional outcomes for the selected stock.'
    m=live_mandate(query,['ANET','MU'],[5,63],now=NOW)
    assert [w['symbol'] for w in m['watchlist']]==['ANET','MU']
    assert m['horizon_sessions']==[5,63]
    assert m['schema_version']=='investment-research-mandate-v7'
    assert not any(s['source_id'].startswith('anet-quarterly') for s in m['sources'])
    assert {'EFA','EEM','UUP','GLD','USO'} <= set(m['market_context_symbols'])
    five=live_mandate(query,['ANET','MU','NVDA','META','QQQ'],[5,21,63],now=NOW)
    assert len(five['watchlist'])==5
    primary=lambda url:{'0':{'ticker':'AAPL','cik_str':320193,'title':'Apple Inc.'}}
    new=live_mandate(query,['aapl'],[21],now=NOW,issuer_fetch=primary)
    assert new['analysis_policy']['issuer_resolution'][0]['cik']=='0000320193'
    assert new['watchlist'][0]['sector_benchmark']=='SPY'
    assert any('/CIK0000320193.json' in s['url'] for s in new['sources'])
    with pytest.raises(ValueError,match='resolve'):
        live_mandate(query,['BOGUS'],[63],now=NOW,issuer_fetch=primary)


def test_snapshot_rejects_future_identity_crossed_and_nonfinite():
    source={'symbols':['NVDA'],'feed':'iex'}
    valid=normalize_snapshot(snapshot(),source,now=NOW)
    assert valid['coverage']=='single_venue' and valid['latest_quote']['bid']=='100.9'
    for value in [snapshot('MU'), snapshot(stamp=(NOW+timedelta(seconds=1)).isoformat()),
                  snapshot()|{'latestQuote':{'t':NOW.isoformat(),'bp':102,'ap':100}}]:
        with pytest.raises(ValueError): normalize_snapshot(value,source,now=NOW)
    assert normalize_snapshot(snapshot()|{'latestQuote':{'t':NOW.isoformat(),'bp':0,'ap':0}},source,now=NOW)['latest_quote'] is None
    assert normalize_snapshot(snapshot()|{'latestTrade':{'t':NOW.isoformat(),'p':'NaN'}},source,now=NOW)['latest_trade'] is None


class LiveWorker(DimensionWorker):
    def __call__(self, request, runtime, timeout):
        if request['context']['task']['stage']=='planning':
            r=result(request['task_id']); del r['instruments'];del r['role_coverage'];del r['objections']
            answer=response('submit_findings',r)
        else:
            answer=super().__call__(request,runtime,timeout)
        if answer['action']['tool']!='submit_findings':return answer
        r=answer['action']['arguments'];r['agent_report']={'work_summary':'Analyzed the supplied synthetic research evidence.',
            'main_conclusions':['Synthetic evidence requires conditional interpretation.'],
            'short_summary':'Synthetic conclusions; this fixture is not investment advice.', 'limitations':['Synthetic evidence cannot establish live investment performance.']}
        rows=r.get('instruments',{});rows=rows.values() if isinstance(rows,dict) else rows
        for row in rows:
            identity=next(iter(request['context']['evidence']))
            row['global_analysis']={'overall_assessment':'Synthetic conditional global assessment based on admitted data.',
                'global_forces':[{'force':'Synthetic interest rate environment','mechanism':'Higher rates can affect financing and valuation multiples.',
                    'consequence':'Valuation may decline if rates rise without offsetting earnings growth.','evidence_ids':[identity]}],
                'conditional_outcomes':[{'case':case,'condition':'Synthetic earnings and multiple assumptions occur.',
                    'consequence':'Price sensitivity changes with earnings and the valuation multiple.',
                    'plausibility_basis':'Synthetic scenario only; likelihood is not calibrated.','evidence_ids':[identity]} for case in ['bear','base','bull']],
                'recommend_considering':'Review the assumptions and evidence before taking any investment action.',
                'short_summary':'Synthetic scenario sensitivity, not a calibrated prediction.'}
        if r.get('role_coverage'):
            for row in r['role_coverage']:row.update(status='completed',reason='Synthetic assigned role completed')
        return answer


def live_fixture(path, worker=None):
    # Reuse dated inputs while creating a genuinely v7 controller/task/tool contract.
    seed, state=ready_controller(path/'seed', dimensional=True)
    m=deepcopy(state['mandate']);m['schema_version']='investment-research-mandate-v7'
    m['analysis_policy']={'requested_at':NOW.isoformat(),'quote_feed':'iex','maximum_quote_age_seconds':60,
                          'report_contract':'global-assessment-v1','issuer_resolution':[]}
    c=Controller(path/'run', worker or LiveWorker());s=c.create(m);b=Broker(c.store,s)
    for identity in state['evidence_ids']:
        value=seed.store.get('evidence',identity);record=b.record({k:v for k,v in value.items() if k!='evidence_id'})
        if value.get('source_id'):s['source_cache'][value['source_id']]=record['evidence_id']
    s['seed_complete']=True;c.store.save(s)
    return c,s


def test_all_seven_agents_and_global_output_contract(tmp_path):
    c,_=live_fixture(tmp_path);state=c.run()
    assert state['status']=='DRAFT', state.get('stop_reason')
    product=c.store.get('products',state['product_id'])
    assert product['schema_version']=='investment-research-product-v5'
    assert product['as_of_record']['requested_at']==NOW.isoformat()
    assert state['live_refreshes'][0]['stage']=='before_final'
    assert all(row['global_analysis']['recommend_considering'] for row in product['findings']['instruments'])
    reports=agent_reports(c.store,state)
    assert len(reports)==7 and all(r['status']=='completed' for r in reports)
    assert all(r['narrative']['main_conclusions'] and r['short_summary'] for r in reports)
    assert state['usage']['model_calls']<40
    saved=(c.store.root/'draft.md').read_text()
    assert 'Global forces' in saved and 'What to consider' in saved and 'Agent reports' in saved
    task=next(t for t in state['tasks'] if t['stage']=='final')
    assert next(r for r in reports if r['role']=='company')['integrated_assessment']
    review=next(t for t in state['tasks'] if t['role']=='challenger' and t['stage']=='review')
    review['result']['objections'].append({'objection_id':'test-correction','dimensions':['valuation']})
    task['result']['dispositions'].append({'objection_id':'test-correction','decision':'changed','reason':'Synthetic correction preserved in the final review.'})
    projected=agent_reports(c.store,state)
    assert next(r for r in projected if r['role']=='company')['final_review'][-1]['objection_id']=='test-correction'
    assert not any(d['objection_id']=='test-correction' for d in next(r for r in projected if r['role']=='geopolitics')['final_review'])
    original=next(t for t in state['tasks'] if t['role']=='company')
    followup=deepcopy(original);followup.update(task_id='followup-test',round=1,question='Check a specific corporate action.')
    followup['result']['agent_report']['short_summary']='Specific follow-up answer; original valuation remains available.'
    state['tasks'].append(followup)
    company=next(r for r in agent_reports(c.store,state) if r['role']=='company')
    assert company['short_summary']==original['result']['agent_report']['short_summary']
    assert company['followup_reports'][0]['narrative']['short_summary']==followup['result']['agent_report']['short_summary']
    corrupt=deepcopy(task['result']);corrupt['instruments'][0]['global_analysis']['global_forces'][0]['evidence_ids']=['unknown']
    with pytest.raises(ValueError,match='unknown or unread'):validate_report(state,task,corrupt)
    corrupt=deepcopy(task['result']);corrupt['instruments'][0]['global_analysis']['conditional_outcomes'][1]['case']='bear'
    with pytest.raises(ValueError,match='distinct'):validate_report(state,task,corrupt)


def test_question_routing_is_idempotent_and_offered_only_while_pending(tmp_path):
    from spy_predictor_quant.investment_research.result_transport import tool_schemas
    from spy_predictor_quant.investment_research.contracts import ROOT
    c,state=live_fixture(tmp_path)
    state['followup_round']=1
    state['questions']=[{'question_id':'question-test','status':'PROPOSED','recipient':'company',
                        'question':'Verify the disclosed share basis.','parent_task_id':'task-5','symbols':['NVDA']}]
    triage=c.add_task(state,'director','triage','Prioritize the pending question.')
    base=json.loads((ROOT/'prompts/investment-research/v2.20/tools.json').read_text())
    assert tool_schemas(base,triage,state,5)['route_question']['properties']['question_id']['enum']==['question-test']
    args={'question_id':'question-test','decision':'approve','reason':'Check a material share-basis concern.','answer_task_id':None}
    first=c.prioritize(state,triage,args);count=len(state['tasks'])
    repeated=c.prioritize(state,triage,args|{'reason':'Repeated wording must not create another child.'})
    assert repeated['already_prioritized'] and repeated['answer_task_id']==first['answer_task_id']
    assert len(state['tasks'])==count and first['disposition']==args['reason']
    assert 'route_question' not in tool_schemas(base,triage,state,4)
    with pytest.raises(ValueError,match='cannot be changed'):
        c.prioritize(state,triage,args|{'decision':'decline'})


@pytest.mark.parametrize('field', ['global_forces', 'conditional_outcomes'])
def test_final_citations_cannot_bypass_review_with_already_visible_sources(tmp_path, field):
    c,_=live_fixture(tmp_path);state=c.run()
    final=next(t for t in state['tasks'] if t['stage']=='final')
    # A source can be available to synthesis without having supported its draft.
    identity='visible-ai-cloud-guarantees-not-used-in-draft'
    final['visible_evidence_ids'].append(identity)
    candidate=deepcopy(final['result'])
    candidate['instruments'][0]['global_analysis'][field][0]['evidence_ids']=[identity]
    with pytest.raises(ValueError,match='not covered by the reviewed draft'):
        validate_report(state,final,candidate)


def test_final_citation_corrections_are_scoped_to_reviewed_stock_and_decision(tmp_path):
    c,_=live_fixture(tmp_path);state=c.run()
    final=next(t for t in state['tasks'] if t['stage']=='final')
    review=next(t for t in state['tasks'] if t['stage']=='review')
    identity='reviewed-corrected-earnings-source'
    final['visible_evidence_ids'].append(identity)
    candidate=deepcopy(final['result'])
    symbol=candidate['instruments'][0]['symbol']
    candidate['instruments'][0]['global_analysis']['global_forces'][0]['evidence_ids']=[identity]
    review['result']['claims'].append({'symbols':[symbol], 'evidence_ids':[identity]})
    review['result']['objections'].append({'objection_id':'correction', 'symbols':[symbol]})
    candidate['dispositions'].append({'objection_id':'correction','decision':'changed'})
    validate_report(state,final,candidate)
    candidate['dispositions'][-1]['decision']='held'
    with pytest.raises(ValueError,match='not covered'):
        validate_report(state,final,candidate)
    candidate['dispositions'][-1]['decision']='changed'
    review['result']['objections'][-1]['symbols']=['OTHER']
    with pytest.raises(ValueError,match='not covered'):
        validate_report(state,final,candidate)


def test_final_citations_allow_refresh_of_reviewed_news_but_not_unrelated_news(tmp_path):
    c,_=live_fixture(tmp_path);state=c.run()
    final=next(t for t in state['tasks'] if t['stage']=='final')
    candidate=deepcopy(final['result'])
    item=candidate['instruments'][0]['global_analysis']['global_forces'][0]
    old=item['evidence_ids'][0];fresh='fresh-version-of-reviewed-news'
    final['visible_evidence_ids'].append(fresh)
    item['evidence_ids']=[fresh]
    state['live_news_changes']=[{'evidence_ids':[old,fresh]}]
    validate_report(state,final,candidate)
    state['live_news_changes'][0]['evidence_ids'][0]='unrelated-original'
    with pytest.raises(ValueError,match='not covered'):
        validate_report(state,final,candidate)


def test_multi_company_capacity_preserves_required_grid_turns(tmp_path):
    from spy_predictor_quant.investment_research.result_transport import tool_schemas
    from spy_predictor_quant.investment_research.contracts import ROOT
    m=live_mandate('Assess global forces and conditional outcomes.',['NVDA','MU'],[5,21,63],now=NOW)
    c=Controller(tmp_path);state=c.create(m)
    task=next(t for t in state['tasks'] if t['role']=='company')
    assert task['model_turn_limit']>=10 and state['mandate']['budgets']['model_calls']>=48
    base=json.loads((ROOT/'prompts/investment-research/v2.21/tools.json').read_text())
    available=tool_schemas(base,task,state,3)
    assert set(available)=={'calculate_scenarios'}
    assert available['calculate_scenarios']['properties']['symbol']['enum']==['NVDA','MU']
    task['history']=[{'action':{'tool':'calculate_scenarios','arguments':{'symbol':'NVDA'}},'result':{'status':'OK'}}]
    available=tool_schemas(base,task,state,2)
    assert available['calculate_scenarios']['properties']['symbol']['enum']==['MU']
    assert set(tool_schemas(base,task,state,1))=={'submit_findings'}


def test_quote_coverage_age_closed_market_and_missingness(tmp_path):
    c,state=live_fixture(tmp_path);b=Broker(c.store,state)
    record=b.record({'source_id':'snapshot-NVDA','adapter':'alpaca_snapshot','retrieved_at':NOW.isoformat(),
                     'data':normalize_snapshot(snapshot(),{'symbols':['NVDA'],'feed':'iex'},now=NOW)})
    state['source_cache']['snapshot-NVDA']=record['evidence_id']
    stock=lambda now:next(r for r in as_of_record(c.store,state,now=now)['stocks'] if r['symbol']=='NVDA')
    assert stock(NOW)['quote_status']=='partial_coverage'
    assert stock(NOW+timedelta(minutes=2))['quote_status']=='stale'
    assert stock(NOW+timedelta(days=1))['quote_status']=='market_closed'
    state['source_cache'].pop('snapshot-NVDA')
    assert stock(NOW)['quote_status']=='unavailable'


def test_explicit_scope_idempotency_and_queued_report(tmp_path):
    w=Workspace(tmp_path, tmp_path/'ledger',launch=lambda *_:None)
    identity=str(uuid.uuid4());w.start(identity,QUESTION,symbols=['ANET'],horizon_sessions=[21])
    assert w.report(identity)['product'] is None
    assert w.start(identity,QUESTION,symbols=['ANET'],horizon_sessions=[21])['scope']==['ANET']
    with pytest.raises(ValueError,match='different question'):
        w.start(identity,QUESTION,symbols=['MU'],horizon_sessions=[21])


def test_exported_chart_scale_contains_extreme_returns_without_clipping():
    from xml.etree import ElementTree
    from spy_predictor_quant.investment_research.technical_charts import _relative_chart, _risk_chart
    rows=[{'symbol':'TEST','benchmark':'SPY','excess_price_return_percentage_points':{'5':'-100','21':'130','63':'45'}}]
    tree=ElementTree.fromstring(_relative_chart(rows,'2026-10-02'))
    width=float(tree.attrib['width']);height=float(tree.attrib['height'])
    assert height<400  # A single pair must not inherit a five-stock blank canvas.
    for rect in tree.findall('{http://www.w3.org/2000/svg}rect'):
        if '%' in rect.attrib.get('width',''):continue
        assert float(rect.attrib['x'])>=0
        assert float(rect.attrib['x'])+float(rect.attrib['width'])<=width
    risk=ElementTree.fromstring(_risk_chart({'TEST':{'return63_pct':150,'realized_vol63_pct':120,
       'drawdown_from_window_high_pct':-55,'price_to_sma50':1.5}},'2026-10-02'))
    assert float(risk.attrib['height'])<350
