"""Copy a completed development case for read-only workspace presentation."""
import json, shutil, sys, uuid
from pathlib import Path
from spy_predictor_quant.investment_research.workspace import Workspace, QUESTION
source=Path(sys.argv[1]);state=json.loads((source/'state.json').read_text())
if state['status']!='DRAFT':raise ValueError('Completed draft required')
w=Workspace();identity=str(uuid.uuid4());destination=w.directory(identity);destination.mkdir()
shutil.copytree(source,destination/'run')
(destination/'mandate.json').write_text(json.dumps(state['mandate'],indent=2)+'\n')
job={'id':identity,'question':QUESTION,'created_at':state['started_at'],'status':'DRAFT','operation':None,'scope':[r['symbol'] for r in state['mandate']['watchlist']],'horizon_sessions':state['mandate']['horizon_sessions'],'budgets':state['mandate']['budgets'],'model':state['mandate']['runtime']['model'],'mode':'live','saved_evaluation':True,'publication_attempted':False,'source_evaluation':str(source),'qualification':'Saved development evaluation; original run preserved. Publication unavailable from this copy.'}
w.save_job(job)
record={'id':identity,'url':'http://127.0.0.1:8766/reports?run='+identity,'source_run':str(source),'qualification':job['qualification']}
(source.parent/(source.name+'-workspace-report.json')).write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
