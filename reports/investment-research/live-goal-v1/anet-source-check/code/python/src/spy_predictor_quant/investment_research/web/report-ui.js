'use strict';
// Shared read-only reporting components. Model/source strings are always text.
window.ResearchReport = (() => {
 const make=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
 const words=s=>String(s||'not recorded').replaceAll('_',' ');
 const states=new WeakMap();
 const bullets=(parent,items)=>{const ul=make('ul');for(const item of items)ul.append(make('li',item));parent.append(ul);};
 function evidenceLink(parent,id,base,label){const a=make('a',label||`Evidence ${id.slice(0,10)} ↗`);a.href=`${base}/artifact/evidence/${id}`;parent.append(a);}
 function agents(parent,reports,base,onTask){
  if(!states.has(parent))states.set(parent,{role:'director',signature:null});const state=states.get(parent);
  const signature=JSON.stringify(reports);if(state.signature===signature)return;state.signature=signature;
  parent.replaceChildren(make('h2','The research team'),make('p','Choose an agent to read its work, conclusions and short summary.','report-muted'));
  const controls=make('div',undefined,'agent-selector');controls.setAttribute('role','group');controls.setAttribute('aria-label','Choose an agent report');
  const panel=make('article',undefined,'agent-detail');panel.id=parent.id+'-selected';
  const choose=role=>{state.role=role;for(const b of controls.children)b.setAttribute('aria-pressed',String(b.dataset.role===role));const report=reports.find(r=>r.role===role);panel.replaceChildren();if(!report)return;
   panel.append(make('div',words(report.status),'report-status '+report.status),make('h3',report.name),make('p',report.short_summary,'agent-takeaway'));
   const work=make('section');work.append(make('h4','What it did'));
   const activity=Object.entries(report.activity).filter(([tool])=>tool!=='submit_findings').map(([tool,count])=>`${words(tool)} × ${count}`);
   work.append(make('p',activity.length?activity.join(' · '):report.task_ids.length?'No acquisition or calculation tool actions recorded. The agent may have used evidence supplied in its brief.':'This role has no assigned task in this run.'));
   work.append(make('p',`${report.model_calls} model calls · ${report.inspected_evidence_count} evidence records read or inspected via tools · ${report.sources.length} cited · ${report.cost_known?'$'+Number(report.catalog_cost_usd).toFixed(2)+' catalog estimate':'cost total unknown'}`,'report-muted'));
   panel.append(work);
   if(report.narrative?.work_summary)panel.append(make('p',report.narrative.work_summary));
   const findings=make('section');findings.append(make('h4','Main conclusions'));
   if(report.narrative?.main_conclusions?.length)bullets(findings,report.narrative.main_conclusions);
   if(report.instruments.length){for(const row of report.instruments){const d=make('details');d.append(make('summary',`${row.symbol} · ${words(row.assessment)}`),make('p',row.thesis));if(row.counter_thesis)d.append(make('h4','Opposing case'),make('p',row.counter_thesis));if(row.valuation)d.append(make('h4','Valuation'),make('p',row.valuation));findings.append(d);}}
   else findings.append(make('p',report.summary));
   if(report.objections.length)bullets(findings,report.objections.map(o=>o.description||o.reason||o.text||JSON.stringify(o)));
   if(report.main_conclusions.length){const d=make('details');d.append(make('summary',`Claims & supporting evidence (${report.main_conclusions.length})`));for(const claim of report.main_conclusions){d.append(make('p',`${words(claim.classification)}: ${claim.text}`));for(const id of claim.evidence_ids||[])evidenceLink(d,id,base);}findings.append(d);}
   panel.append(findings);
   if(report.narrative?.limitations?.length){const limits=make('details');limits.append(make('summary','Analytical limitations'));bullets(limits,report.narrative.limitations);panel.append(limits);}
   if(report.gaps.length){const d=make('section',undefined,'report-gaps');d.append(make('h4','Limits & unresolved questions'));bullets(d,report.gaps.map(g=>(g.critical?'Critical: ':'')+g.description));panel.append(d);}
   const final=make('section',undefined,'agent-final');final.append(make('h4','Final short summary'),make('p',report.short_summary));panel.append(final,make('p',report.qualification,'report-muted'));
   if(report.latest_task_id&&onTask){const b=make('button','Inspect the saved task','secondary');b.onclick=()=>onTask(report.latest_task_id);panel.append(b);}
   if(report.sources.length){const d=make('details');d.append(make('summary','Cited sources & dates'));for(const source of report.sources){const row=make('div',undefined,'report-source');evidenceLink(row,source.evidence_id,base,source.title||source.evidence_id.slice(0,10));row.append(make('small',`Observed: ${source.observed_at||'unknown'} · Retrieved: ${source.retrieved_at||'unknown'}`));d.append(row);}panel.append(d);}
  };
  for(const report of reports){const b=make('button',undefined,'agent-choice');b.dataset.role=report.role;b.setAttribute('aria-controls',panel.id);b.append(make('strong',report.name),make('small',words(report.status)));b.onclick=()=>choose(report.role);controls.append(b);}
  parent.append(controls,panel);choose(state.role);
 }
 function svgNode(tag,attributes,text){const e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [key,value]of Object.entries(attributes||{}))e.setAttribute(key,String(value));if(text!==undefined)e.textContent=text;return e;}
 function chart(parent,data,base){
  const figure=make('figure',undefined,'research-chart'),caption=make('figcaption');caption.append(make('h3',data.title),make('p',`Observed ${data.as_of}`,'report-muted'));figure.append(caption);
  const svg=svgNode('svg',{viewBox:'0 0 800 330',role:'img','aria-label':data.title});svg.append(svgNode('title',{},data.title));
  const colors=['#23695a','#547ca0','#ab762d'];let table;
  if(data.kind==='price_path'){
   const all=data.series.flatMap(s=>s.values),min=Math.min(...all),max=Math.max(...all),pad=Math.max((max-min)*.1,1),low=min-pad,high=max+pad;
   const x=i=>66+i/(data.dates.length-1)*660,y=v=>270-(v-low)/(high-low)*210;
   for(let i=0;i<5;i++){const v=low+(high-low)*i/4;svg.append(svgNode('line',{x1:66,x2:726,y1:y(v),y2:y(v),stroke:'#dce5e1'}),svgNode('text',{x:55,y:y(v)+4,'text-anchor':'end'},v.toFixed(0)));}
   data.series.forEach((series,index)=>{svg.append(svgNode('polyline',{points:series.values.map((v,i)=>`${x(i)},${y(v)}`).join(' '),fill:'none',stroke:colors[index%3],'stroke-width':index===0?3:2}),svgNode('text',{x:66+index*210,y:28,fill:colors[index%3]},series.name));});
   for(const i of [0,data.dates.length-1])svg.append(svgNode('text',{x:x(i),y:303,'text-anchor':i?'end':'start'},data.dates[i]));
   table=make('table');const head=make('tr');head.append(make('th','Date'),...data.series.map(s=>make('th',s.name+' (index)')));table.append(head);for(let i=0;i<data.dates.length;i++){const tr=make('tr');tr.append(make('td',data.dates[i]),...data.series.map(s=>make('td',s.values[i].toFixed(2))));table.append(tr);}
  }else{
   const rows=data.rows.flatMap(r=>Object.entries(r.excess_price_return_percentage_points).map(([h,v])=>({name:r.benchmark+' / '+h+' sessions',value:Number(v)})));
   const extent=Math.max(1,...rows.map(r=>Math.abs(r.value)))*1.22,zero=462,scale=245/extent;
   svg.setAttribute('viewBox',`0 0 800 ${Math.max(240,rows.length*38+80)}`);svg.append(svgNode('line',{x1:zero,x2:zero,y1:30,y2:rows.length*38+40,stroke:'#869e94'}));
   table=make('table');const head=make('tr');head.append(make('th','Benchmark / horizon'),make('th','Excess return (pp)'));table.append(head);
   rows.forEach((r,i)=>{const y=40+i*38,end=zero+r.value*scale;svg.append(svgNode('text',{x:18,y:y+16},r.name),svgNode('rect',{x:Math.min(zero,end),y,width:Math.max(1,Math.abs(end-zero)),height:22,rx:3,fill:r.value>=0?colors[0]:'#af5b4b'}),svgNode('text',{x:end+(r.value>=0?7:-7),y:y+16,'text-anchor':r.value>=0?'start':'end'},(r.value>=0?'+':'')+r.value.toFixed(2)));const tr=make('tr');tr.append(make('td',r.name),make('td',r.value.toFixed(2)));table.append(tr);});
  }
  figure.append(svg,make('p',data.qualification,'report-muted'));const d=make('details');d.append(make('summary','Chart data & sources'),table);for(const id of data.evidence_ids)evidenceLink(d,id,base);figure.append(d);parent.append(figure);
 }
 function charts(parent,rows,base){if(!rows.length)return;const d=make('details',undefined,'chart-browser');d.append(make('summary',`Explore related charts (${rows.length})`),make('p','One chart at a time. Open its data table for exact values.','report-muted'));const select=make('select');select.setAttribute('aria-label','Choose a related chart');for(const [index,row]of rows.entries()){const option=make('option',row.title);option.value=String(index);select.append(option);}const canvas=make('div');select.onchange=()=>{canvas.replaceChildren();chart(canvas,rows[Number(select.value)],base);};d.append(select,canvas);d.addEventListener('toggle',()=>{if(d.open&&!canvas.children.length)select.onchange();});parent.append(d);}
 return {agents,charts};
})();
