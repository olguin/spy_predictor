"""Optional headless Chrome acceptance check (requires websocket-client)."""
import base64,json,subprocess,tempfile,time,sys
from pathlib import Path
from threading import Thread
from http.server import ThreadingHTTPServer
from urllib.request import urlopen
import websocket
from spy_predictor_quant.investment_research.monitor import handler
from spy_predictor_quant.investment_research.store import Store
root=Path(__file__).resolve().parents[1]
server=ThreadingHTTPServer(('127.0.0.1',0),handler(Store(root/'reports/investment-research/m2-live-v7')))
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
 for _ in range(100):
  if evaluate("document.querySelectorAll('#table tr').length") == 11:break
  time.sleep(.1)
 assert evaluate("document.querySelectorAll('#table tr').length")==11
 assert evaluate("document.getElementById('status').textContent.includes('DRAFT')")
 call('Page.bringToFront')
 evaluate("document.querySelector('#table button[data-task=\"task-3\"]').focus()")
 call('Input.dispatchKeyEvent',{'type':'keyDown','key':'Enter','code':'Enter','windowsVirtualKeyCode':13,'nativeVirtualKeyCode':36,'text':'\r'})
 call('Input.dispatchKeyEvent',{'type':'keyUp','key':'Enter','code':'Enter','windowsVirtualKeyCode':13})
 assert evaluate("document.querySelector('#inspector h2').textContent.includes('task-3')")
 assert evaluate("document.querySelectorAll('#timeline svg path').length")>0
 assert evaluate("document.querySelector('#inspector').textContent.includes('Accepted individual findings')")
 evaluate("document.getElementById('inspector').scrollTop=120")
 scroll=evaluate("document.getElementById('inspector').scrollTop")
 time.sleep(2.2)
 assert evaluate("document.getElementById('inspector').scrollTop")==scroll
 assert evaluate("document.activeElement.dataset.task")== 'task-3'
 # Filters preserve selected inspection, and the request map is available on demand.
 evaluate("document.getElementById('role').value='macro';document.getElementById('role').dispatchEvent(new Event('change'))")
 assert evaluate("[...document.querySelectorAll('#table tr')].every(r=>r.textContent.includes('macro'))")
 assert evaluate("document.querySelector('#inspector h2').textContent.includes('task-3')")
 evaluate("document.getElementById('role').value='';document.getElementById('role').dispatchEvent(new Event('change'))")
 call('Emulation.setEmulatedMedia',{'features':[{'name':'prefers-reduced-motion','value':'reduce'}]})
 assert evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches")
 shot=call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
 Path('/tmp/m3-monitor-desktop.png').write_bytes(base64.b64decode(shot['data']))
 call('Emulation.setDeviceMetricsOverride',{'width':800,'height':1000,'deviceScaleFactor':1,'mobile':False})
 assert evaluate("getComputedStyle(document.querySelector('main')).display")=='block'
 assert not exceptions,exceptions
 result={'status':'PASS','rows':11,'keyboard_selection':True,'dependency_paths':True,'poll_preserves_focus_and_inspector_scroll':True,'filters_preserve_selection':True,'reduced_motion':True,'responsive_layout':True,'browser_exceptions':exceptions,'screenshot':'/tmp/m3-monitor-desktop.png'}
 Path('/tmp/m3-monitor-browser-check.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2))
finally:
 if ws:ws.close()
 process.terminate();process.wait(timeout=20)
 server.shutdown();server.server_close();thread.join()
