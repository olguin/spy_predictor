"""Read-only numerical/archive verification; no source or model calls."""
import json, sys, math
from decimal import Decimal, localcontext
from pathlib import Path
from datetime import datetime
from spy_predictor_quant.investment_research.store import Store
from spy_predictor_quant.investment_research.contracts import validate
from spy_predictor_quant.market_archive import content_hash

root=Path(sys.argv[1]);store=Store(root);state=store.load()
assert state['status']=='DRAFT' and not state['usage_unknown']
assert content_hash(state['mandate'])==state['mandate_hash']
product=store.get('products',state['product_id']);validate('product',product)
evidence={i:store.get('evidence',i) for i in state['evidence_ids']}
for e in evidence.values():
 if e.get('document_id'):store.get('documents',e['document_id'])
for a in state['attempts']:
 store.get('requests',a['request_id'])
 if a.get('response_id'):store.get('responses',a['response_id'])
checks=[]
prices={e['data']['symbol']:(i,e) for i,e in evidence.items() if e.get('adapter')=='alpaca_daily'}
for symbol,(identity,e) in prices.items():
 raw=json.loads(store.get('documents',e['document_id'])['text'])
 rows=[b for b in raw['bars'] if b['t'][:10]<=e['data']['price_date']]
 assert rows[-1]['t'][:10]==e['data']['price_date']
 assert Decimal(str(rows[-1]['c']))==Decimal(str(e['data']['latest_close']))
 for h in (5,21,63):
  value=(Decimal(str(rows[-1]['c']))/Decimal(str(rows[-h-1]['c']))-1)*100
  assert abs(value-Decimal(str(e['data'][f'return{h}_pct'])))<Decimal('0.00001')
 checks.append({'kind':'raw_completed_close_and_three_returns','symbol':symbol,'evidence_id':identity})
for identity,e in evidence.items():
 if e.get('kind')=='scenario_grid':
  with localcontext() as ctx:
   ctx.prec=50
   close=Decimal(e['observed_close_decimal'])
   price=evidence[e['price_evidence_id']]['data']
   assert e['price_date']==price['price_date'] and e['share_basis']==price['adjustment']
   for c in e['cases']:
    eps,pe=Decimal(c['earnings_per_share']),Decimal(c['pe_multiple'])
    for actual,wanted in [(c['scenario_price_decimal'],eps*pe),(c['break_even_pe_decimal'],close/eps),(c['break_even_eps_decimal'],close/pe),(c['change_from_close_pct_decimal'],(eps*pe/close-1)*100)]:
     assert abs(Decimal(actual)-wanted)<Decimal('0.000000001')
   bear,bull=[Decimal(next(c for c in e['cases'] if c['case']==name)['change_from_close_pct_decimal']) for name in ['bear','bull']]
   assert abs(Decimal(e['asymmetry']['bull_gain_minus_bear_loss_pp_decimal'])-(max(bull,Decimal(0))-abs(min(bear,Decimal(0)))))<Decimal('0.000000001')
  checks.append({'kind':'three_grid_values_returns_break_even_and_asymmetry','symbol':e['symbol'],'evidence_id':identity})
 if e.get('kind')=='comparison_panel':
  for row in e['data']['relative_strength']:
   a,b=prices[row['symbol']][1]['data'],prices[row['benchmark']][1]['data']
   assert a['price_date']==b['price_date']==row['price_date']
   for h,val in row['excess_price_return_percentage_points'].items():
    expected=Decimal(str(a[f'return{h}_pct']))-Decimal(str(b[f'return{h}_pct']))
    assert abs(expected-Decimal(str(val)))<Decimal('0.000000001')
  checks.append({'kind':'signed_matched_benchmark_comparisons','pairs':len(e['data']['relative_strength']),'evidence_id':identity})
final=product['findings']
for task in state['tasks']:
 if task.get('result'):
  for claim in task['result']['claims']:
   assert set(claim['evidence_ids'])<=set(evidence)
assert len({t['role'] for t in state['tasks'] if t['status']=='COMPLETE'})==7
for instrument in final['instruments']:
 a=instrument['global_analysis'];assert len(a['conditional_outcomes'])==3
 assert {r['case'] for r in a['conditional_outcomes']}=={'bear','base','bull'}
 assert instrument['review_conditions'] and a['recommend_considering']
 assert all(set(r['evidence_ids'])<=set(evidence) for r in a['global_forces']+a['conditional_outcomes'])
objections={o['objection_id']:o for t in state['tasks'] if t.get('result') for o in t['result'].get('objections',[])}
assert {d['objection_id'] for d in final['dispositions']}==set(objections)
unresolved=[{'disposition':d,'objection':objections[d['objection_id']]} for d in final['dispositions'] if d['decision']=='unresolved']
clock=product['as_of_record'];assert datetime.fromisoformat(clock['requested_at'])<=datetime.fromisoformat(clock['assessed_at'])
result={'status':'PASS','run_id':state['run_id'],'product_id':state['product_id'],'checks':checks,'seven_completed_roles':True,'all_requested_sections':True,'unresolved_objections_requiring_scoped_review':unresolved,'archive_identity_verified':True,'qualification':'Deterministic checks supplement prose/primary-source review; not automatic semantic quality or investment performance.'}
(root.parent/(root.name+'-numerical-verification.json')).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':'PASS','run':state['run_id'],'numerical_check_groups':len(checks)}))
