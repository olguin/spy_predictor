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
from test_investment_research_m3 import draft
from spy_predictor_quant.investment_research.store import Store
root=Path(__file__).resolve().parents[1]
temporary=Path(tempfile.mkdtemp(prefix='research-ui-check-'))
calls=[]
workspace=Workspace(temporary/'workspace',temporary/'ledger',launch=lambda *args:calls.append(args))
identity=str(uuid.uuid4())
workspace.start(identity,QUESTION)
draft(workspace.directory(identity)/'run')
job=workspace.job(identity);job['operation']=None;workspace.save_job(job);workspace.active=None
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
 assert evaluate("document.getElementById('budget').textContent.includes('40 calls')")
 shot=call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
 Path('/tmp/research-entry.png').write_bytes(base64.b64decode(shot['data']))
 call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
 assert evaluate("document.documentElement.scrollWidth<=innerWidth")
 call('Emulation.setDeviceMetricsOverride',{'width':1500,'height':1000,'deviceScaleFactor':1,'mobile':False})
 call('Page.navigate',{'url':f'http://127.0.0.1:{server.server_port}/reports?run={identity}'})
 until("document.querySelectorAll('.instrument').length===5")
 assert evaluate("document.getElementById('conclusion').textContent.includes('Draft conclusions')")
 assert evaluate("document.getElementById('instruments').textContent.includes('What would change this assessment')")
 shot=call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
 Path('/tmp/research-conclusions.png').write_bytes(base64.b64decode(shot['data']))
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
 shot=call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
 Path('/tmp/research-monitor-status.png').write_bytes(base64.b64decode(shot['data']))
 # Real form submission against a fake launcher verifies the same-origin write path.
 call('Page.navigate',{'url':f'http://127.0.0.1:{server.server_port}/'})
 until("!document.getElementById('entry').hidden")
 evaluate("document.getElementById('researchForm').requestSubmit()")
 until("location.pathname==='/reports'")
 assert len(calls)==2,calls
 assert not exceptions,exceptions
 result={'status':'PASS','question_entry':True,'form_launch':True,'draft_conclusions':True,'exact_research_question_heading':True,'monitor_statuses':['running','draft','published','failed','interrupted','uncertain'],'responsive_entry':True,'browser_exceptions':exceptions,'paid_calls':0}
 Path('/tmp/research-workspace-browser-check.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2))
finally:
 if ws:ws.close()
 process.terminate();process.wait(timeout=20)
 server.shutdown();server.server_close();thread.join()
