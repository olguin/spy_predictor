import json, sys
from pathlib import Path
from datetime import datetime, timezone
from hashlib import sha256
import jsonschema
root=Path(sys.argv[1]); forecast=Path(sys.argv[2]); product=Path(sys.argv[3]); original=Path(sys.argv[4])
load=lambda p:json.loads(p.read_text())
f=load(forecast); p=load(product/'summary.json'); o=load(original)['prior_results']['numerical_forecast']
for obj, schema in [(f,'meta-structured-forecast-v3'),(p,'meta-product-view-v3')]:
 jsonschema.Draft202012Validator(load(Path('schemas')/(schema+'.schema.json')),format_checker=jsonschema.FormatChecker()).validate(obj)
rows=[]
for s in p['symbols']:
 for h in s['horizons']:
  src=next(x for x in f['symbols'][s['symbol']]['horizons'] if x['trading_days']==h['trading_days'])
  old=next(x for x in o['symbols'][s['symbol']]['horizons'] if x['trading_days']==h['trading_days'])
  assert src==old, (s['symbol'],h['trading_days'],'frozen numerical row changed')
  d=src['distribution']; rec=src['recommendation']
  assert h['reference']==src['reference']
  assert h['probability_price_up']==d['probability_price_up'] and h['probabilities']==d['probabilities']
  assert h['price_interval_80']==[d['price_quantiles']['0.1'],d['price_quantiles']['0.9']]
  for field in ['new_position_action','existing_position_action','conditional_trigger','invalidation_trigger','next_review']:
   assert h[field]==rec[field],field
  assert h['action']==rec['action_now']
  g=next(x for x in p['golden_conclusions']['decision_rows'] if x['symbol']==s['symbol'] and x['trading_days']==h['trading_days'])
  assert g['probability_price_up']==d['probability_price_up']
  for field in ['action_now','new_position_action','existing_position_action']: assert g[field]==rec[field]
  rows.append({'symbol':s['symbol'],'trading_days':h['trading_days'],'frozen_numerical_row_exact':True,'product_and_summary_parity':True,'current_entry_action':h['action_overlay']['current_entry_action']})
assert len(rows)==15
for name in ['index.html','report.md']:
 text=(product/name).read_text(); assert 'terminal' in text.lower() and 'invalidation' in text.lower()
receipt={'checked_at':datetime.now(timezone.utc).isoformat(),'status':'PASS','schemas_valid':True,'rows':rows,'artifact_hashes':{str(x):sha256(x.read_bytes()).hexdigest() for x in [forecast,original,product/'summary.json',product/'index.html',product/'report.md']},'notice':'Verifies frozen numerical and displayed structured fields; does not qualify predictive accuracy or current-entry freshness.'}
with (root/'product-parity-verification.json').open('x') as out:json.dump(receipt,out,indent=2);out.write('\n')
print(json.dumps({'status':'PASS','rows':len(rows),'receipt':str(root/'product-parity-verification.json')}))
