"""Optional headless Chrome acceptance check (requires websocket-client)."""
import base64,json,subprocess,tempfile,time,sys
from pathlib import Path
from threading import Thread
from http.server import ThreadingHTTPServer
from urllib.request import urlopen
import websocket
from spy_predictor_quant.investment_research.workspace import Workspace, QUESTION, handler
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"python/tests"))
from test_investment_research_live import live_fixture
from spy_predictor_quant.investment_research.store import Store
root=Path(__file__).resolve().parents[1]
temporary=Path(tempfile.mkdtemp(prefix='research-ui-check-'))
calls=[]
workspace=Workspace(temporary/'workspace',temporary/'ledger',launch=lambda *args:calls.append(args))
identity=str(uuid.uuid4())
workspace.start(identity,QUESTION)
fixture, _ = live_fixture(workspace.directory(identity))
assert fixture.run()['status'] == 'DRAFT'
job=workspace.job(identity);job['scope']=[r['symbol'] for r in fixture.store.load()['mandate']['watchlist']];job['horizon_sessions']=fixture.store.load()['mandate']['horizon_sessions'];job['operation']=None;workspace.save_job(job);workspace.active=None
server=ThreadingHTTPServer(('127.0.0.1',0),handler(workspace))
thread=Thread(target=server.serve_forever,daemon=True);thread.start()
profile=Path(tempfile.mkdtemp(prefix='m3-chrome-'))
process=subprocess.Popen(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome','--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--user-data-dir='+str(profile),'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
ws=None
try:
 for _ in range(150):
  if (profile/'DevToolsActivePort').exists():break
  time.sleep(.1)
 port=(profile/'DevToolsActivePort').read_text().splitlines()[0]
 pages=json.load(urlopen(f'http://127.0.0.1:{port}/json/list',timeout=5))
 page=next(p for p in pages if p['type']=='page' and p.get('url')=='about:blank')
 ws=websocket.create_connection(page['webSocketDebuggerUrl'],suppress_origin=True,timeout=10)
 serial=0;exceptions=[]
 def call(method,params=None):
  global serial
  serial+=1;ws.send(json.dumps({'id':serial,'method':method,'params':params or {}}))
  while True:
   item=json.loads(ws.recv())
   if item.get('method')=='Runtime.exceptionThrown':exceptions.append(item['params'])
   if item.get('id')==serial:
    if 'error' in item:raise RuntimeError(item['error'])
    return item.get('result',{})
 def evaluate(expression):
  r=call('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
  if r.get('exceptionDetails'):raise RuntimeError(r['exceptionDetails'])
  return r.get('result',{}).get('value')
 call('Runtime.enable');call('Page.enable')
 call('Emulation.setDeviceMetricsOverride',{'width':1500,'height':1000,'deviceScaleFactor':1,'mobile':False})
 call('Page.navigate',{'url':f'http://127.0.0.1:{server.server_port}/'})
 def until(expression):
  for _ in range(150):
   if evaluate(expression):return
   time.sleep(.1)
  raise AssertionError(expression)
 until("!document.getElementById('entry').hidden")
 assert evaluate("document.getElementById('question').value") == QUESTION
 assert evaluate("document.getElementById('budget').textContent.includes(String(workspace.budgets.model_calls)+' calls')")
 assert evaluate("document.getElementById('symbols').value==='NVDA, MU' && document.querySelectorAll('[name=horizon]').length===3")
 shot=call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
 Path('/tmp/research-entry.png').write_bytes(base64.b64decode(shot['data']))
 call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
 assert evaluate("document.documentElement.scrollWidth<=innerWidth")
 call('Emulation.setDeviceMetricsOverride',{'width':1500,'height':1000,'deviceScaleFactor':1,'mobile':False})
 call('Page.navigate',{'url':f'http://127.0.0.1:{server.server_port}/reports?run={identity}'})
 until("document.querySelectorAll('.instrument').length===5")
 assert evaluate("document.getElementById('conclusion').textContent.includes('Draft conclusions')")
 assert evaluate("document.getElementById('instruments').textContent.includes('What would change this assessment')")
 assert evaluate("document.querySelectorAll('.instrument table tbody tr').length")==12
 assert evaluate("document.getElementById('instruments').textContent.includes('ETF exposure')")
 assert evaluate("document.getElementById('instruments').textContent.includes('Synthetic margin/growth sensitivity')")
 assert evaluate("document.querySelectorAll('.instrument .dimension').length")==25
 assert evaluate("document.querySelector('.instrument').textContent.includes('Relative assessment')")
 assert evaluate("document.querySelector('.dimension').textContent.includes('supported')")
 assert evaluate("Array.from(document.querySelectorAll('.dimension')).some(n=>n.textContent.includes('policy exposure')&&n.textContent.includes('insufficient evidence'))")
 assert evaluate("document.getElementById('supporting').textContent.includes('Source readiness')")
 assert evaluate("document.getElementById('instruments').textContent.includes('Global forces that matter') && document.getElementById('instruments').textContent.includes('What I recommend considering')")
 assert evaluate("document.querySelectorAll('#agentReports .agent-choice').length===7")
 evaluate("document.querySelector('[data-view=agents]').click()")
 assert evaluate("!document.getElementById('agentsView').hidden && document.getElementById('overviewView').hidden")
 evaluate("document.querySelector('#agentReports [data-role=company]').click()")
 assert evaluate("document.querySelector('#agentReports .agent-detail').textContent.includes('Final short summary') && document.querySelector('#agentReports .agent-detail').textContent.includes('What it did')")
 assert evaluate("document.querySelector('#agentReports .chart-browser')!==null")
 evaluate("document.querySelector('#agentReports .chart-browser').open=true")
 until("document.querySelector('#agentReports .research-chart svg')!==null")
 assert evaluate("document.querySelector('#agentReports .research-chart').textContent.includes('Completed close $100.00')")
 evaluate("document.querySelector('#agentReports .research-chart').scrollIntoView({block:'center'})")
 shot=call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
 Path('/tmp/research-agent-valuation.png').write_bytes(base64.b64decode(shot['data']))
 shot=call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
 Path('/tmp/research-agents.png').write_bytes(base64.b64decode(shot['data']))
 evaluate("document.querySelector('[data-view=overview]').click()")
 shot=call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
 Path('/tmp/research-conclusions.png').write_bytes(base64.b64decode(shot['data']))
 evaluate("for(const d of document.querySelectorAll('.instrument details'))d.open=true;document.querySelector('.instrument table').scrollIntoView({block:'center'})")
 shot=call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
 Path('/tmp/research-scenarios.png').write_bytes(base64.b64decode(shot['data']))
 call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
 assert evaluate("document.documentElement.scrollWidth<=innerWidth")
 call('Emulation.setDeviceMetricsOverride',{'width':1500,'height':1000,'deviceScaleFactor':1,'mobile':False})
 call('Page.navigate',{'url':f'http://127.0.0.1:{server.server_port}/monitor?run={identity}'})
 until("document.getElementById('runStateTitle').textContent==='Finished — draft ready'")
 assert evaluate("document.getElementById('runStateDetail').textContent.includes('No research is running')")
 assert evaluate("document.getElementById('researchQuestion').textContent")==QUESTION
 assert evaluate("document.getElementById('researchScope').textContent.includes('trading sessions')")
 evaluate("document.getElementById('follow').checked=false")
 for status,title in [('RUNNING','Research running'),('FAILED','Stopped — saved replay'),('INTERRUPTED','Stopped — saved replay'),('PUBLISHED','Finished — report published')]:
  evaluate("stateBanner({...snapshot,status:"+json.dumps(status)+",stale:false})")
  assert evaluate("document.getElementById('runStateTitle').textContent") == title
 evaluate("stateBanner({...snapshot,status:'RUNNING',stale:true})")
 assert evaluate("document.getElementById('runStateTitle').textContent.includes('uncertain')")
 evaluate("stateBanner(snapshot)")
 assert evaluate("document.getElementById('conclusionsLink').href.includes('/reports?run=')")
 assert evaluate("document.querySelectorAll('#table tr').length")>0
 assert evaluate("document.querySelectorAll('#agentReports .agent-choice').length===7 && !document.getElementById('executionDetails').open")
 evaluate("document.querySelector('#agentReports [data-role=technical]').click()")
 assert evaluate("document.querySelector('#agentReports .agent-detail').textContent.includes('Final short summary')")
 call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
 assert evaluate("document.documentElement.scrollWidth<=innerWidth")
 call('Emulation.setDeviceMetricsOverride',{'width':1500,'height':1000,'deviceScaleFactor':1,'mobile':False})
 shot=call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
 Path('/tmp/research-monitor-status.png').write_bytes(base64.b64decode(shot['data']))
 # Real form submission against a fake launcher verifies the same-origin write path.
 call('Page.navigate',{'url':f'http://127.0.0.1:{server.server_port}/'})
 until("!document.getElementById('entry').hidden")
 evaluate("document.getElementById('researchForm').requestSubmit()")
 until("location.pathname==='/reports'")
 assert len(calls)==2,calls
 assert not exceptions,exceptions
 result={'status':'PASS','question_entry':True,'form_launch':True,'draft_conclusions':True,'scenario_rows':12,'distinct_conclusions':25,'source_readiness':True,'assumptions_and_etf_exposure':True,'exact_research_question_heading':True,'monitor_statuses':['running','draft','published','failed','interrupted','uncertain'],'responsive_entry':True,'browser_exceptions':exceptions,'paid_calls':0,'seven_agent_reports':True,'live_global_contract':True,'explicit_stocks_and_horizons':True,'progressive_disclosure':True,'agent_valuation_chart':True}
 Path('/tmp/research-workspace-browser-check.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2))
finally:
 if ws:ws.close()
 process.terminate();process.wait(timeout=20)
 server.shutdown();server.server_close();thread.join()
