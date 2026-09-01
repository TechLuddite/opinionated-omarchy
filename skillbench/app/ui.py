"""The web UI: one page, plain controls, tables and charts.

Deliberately unclever. Dropdowns, checkboxes and buttons drive it; results are tables
and bar charts. The 8-bit character comes from geometry -- hard corners everywhere,
3px edges, offset shadows, segmented meters, uppercase letter-spaced labels -- and not
from a downloaded font or a canvas effect, so it renders identically offline.

Charts follow the house data-visualisation rules: horizontal bars (long model names),
thin marks with a 2px surface gap, direct value labels, a legend whenever two or more
variants are shown, recessive axes, hover tooltips, and every chart backed by the same
numbers in a table immediately beneath it.
"""

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);
  font-family:"CaskaydiaMono Nerd Font","JetBrainsMono Nerd Font",ui-monospace,
    SFMono-Regular,Menlo,Consolas,monospace;
  font-size:13px;line-height:1.5;padding:16px;image-rendering:pixelated}
h1,h2,h3{font-weight:700;letter-spacing:.14em;text-transform:uppercase}
h1{font-size:16px}h2{font-size:13px;margin-bottom:8px}h3{font-size:12px;margin:14px 0 6px}
a{color:var(--accent)}
.wrap{max-width:1180px;margin:0 auto}
.panel{background:var(--panel);border:3px solid var(--edge);
  box-shadow:4px 4px 0 var(--edge);padding:14px;margin-bottom:18px}
.head{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:16px}
.head h1{flex:1}
.pip{display:inline-block;width:10px;height:10px;background:var(--accent);
  box-shadow:0 -10px 0 var(--series-1),10px 0 0 var(--series-2),10px -10px 0 var(--series-3);
  margin:10px 12px 0 2px}
label{display:block;font-size:10px;letter-spacing:.14em;text-transform:uppercase;
  color:var(--ink-dim);margin-bottom:4px}
select,input{background:var(--bg);color:var(--ink);border:2px solid var(--edge);
  padding:5px 7px;font:inherit;font-size:12px;width:100%}
select:focus,input:focus{outline:2px solid var(--accent);outline-offset:1px}
button{background:var(--panel);color:var(--ink);border:3px solid var(--edge);
  box-shadow:3px 3px 0 var(--edge);padding:7px 14px;font:inherit;font-size:11px;
  font-weight:700;letter-spacing:.14em;text-transform:uppercase;cursor:pointer}
button:hover:not(:disabled){background:var(--sel);border-color:var(--accent)}
button:active:not(:disabled){transform:translate(3px,3px);box-shadow:none}
button:disabled{opacity:.4;cursor:not-allowed}
button.go{border-color:var(--accent);color:var(--accent)}
.row{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end;margin-bottom:12px}
.col{flex:1;min-width:170px}
.chips{display:flex;flex-wrap:wrap;gap:5px;max-height:112px;overflow-y:auto;
  border:2px solid var(--edge);padding:6px;background:var(--bg)}
.chip{border:2px solid var(--edge);padding:3px 7px;font-size:11px;cursor:pointer;
  user-select:none;white-space:nowrap}
.chip:hover{border-color:var(--accent)}
.chip.on{background:var(--accent);color:var(--bg);border-color:var(--accent);font-weight:700}
.chip .ord{font-size:9px;vertical-align:super;margin-left:3px}
table{border-collapse:collapse;width:100%;font-size:12px}
caption{caption-side:top;text-align:left;font-size:10px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--ink-dim);padding-bottom:6px}
th,td{border:2px solid var(--edge);padding:4px 7px;text-align:right;white-space:nowrap}
th{background:var(--sel);font-size:10px;letter-spacing:.1em;text-transform:uppercase}
th:first-child,td:first-child,td.l,th.l{text-align:left}
tbody tr:hover{background:var(--sel)}
tbody tr.sel{outline:2px solid var(--accent);outline-offset:-2px}
.scroll{overflow-x:auto;margin-bottom:6px}
.tiles{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:14px}
.tile{border:3px solid var(--edge);box-shadow:3px 3px 0 var(--edge);padding:10px 14px;
  min-width:132px;background:var(--bg)}
.tile .k{font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--ink-dim)}
.tile .v{font-size:22px;font-weight:700;letter-spacing:.03em}
.meter{display:inline-flex;gap:2px;vertical-align:middle}
.meter i{width:7px;height:13px;background:var(--sel);display:block}
.meter i.f{background:var(--m,var(--series-1))}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:11px;margin:2px 0 8px}
.legend span{display:flex;align-items:center;gap:5px}
.legend b{width:11px;height:11px;display:block}
.up{color:var(--status-good)}.down{color:var(--status-serious)}
.err{color:var(--status-critical)}.dim{color:var(--ink-dim)}
.badge{font-size:10px;border:2px solid var(--edge);padding:1px 5px;letter-spacing:.1em;
  text-transform:uppercase}
.badge.run{border-color:var(--status-warning);color:var(--status-warning)}
.badge.done{border-color:var(--status-good);color:var(--status-good)}
.badge.abort{border-color:var(--status-serious);color:var(--status-serious)}
.badge.err{border-color:var(--status-critical);color:var(--status-critical)}
.badge.ctl{border-color:var(--ink-dim);color:var(--ink-dim)}
.msg{border:3px solid var(--status-critical);color:var(--status-critical);padding:8px 12px;
  margin-bottom:12px;font-size:12px}
.msg.ok{border-color:var(--status-good);color:var(--status-good)}
svg .grid{stroke:var(--edge);stroke-width:1;opacity:.55}
svg .axis{fill:var(--ink-dim);font-size:10px}
svg .val{fill:var(--ink);font-size:10px;font-weight:700}
svg .bar{shape-rendering:crispEdges;cursor:pointer}
svg .bar:hover{opacity:.8}
.tip{position:fixed;pointer-events:none;background:var(--panel);border:2px solid var(--accent);
  padding:5px 8px;font-size:11px;z-index:40;display:none;box-shadow:3px 3px 0 var(--edge)}
.out{background:var(--bg);border:2px solid var(--edge);padding:8px;font-size:11px;
  white-space:pre-wrap;max-height:270px;overflow:auto}
.chk{font-size:11px;border-left:3px solid var(--status-good);padding:2px 7px;margin:3px 0}
.chk.no{border-left-color:var(--status-critical)}
.hide{display:none}
"""

JS = r"""
const $=id=>document.getElementById(id);
const api=async(u,o)=>{const r=await fetch(u,o);const j=await r.json().catch(()=>({}));
  if(!r.ok)throw new Error(j.detail||r.statusText);return j};
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const pct=v=>v==null?'--':(v*100).toFixed(1)+'%';
const num=v=>v==null?'--':v.toLocaleString();

let BENCHES=[],SKILLS=[],MODELS=[],RUN=null,SELMODELS=new Set(),A=[],B=[],POLL=null,VMS=null;

function meter(v,color){if(v==null)return'<span class="dim">--</span>';
  const n=Math.round(v*12);let s=`<span class="meter" style="--m:${color}">`;
  for(let i=0;i<12;i++)s+=`<i class="${i<n?'f':''}"></i>`;return s+'</span>'}

function variantLabel(list){return list.length?'skill:'+list.join('+'):'none'}
function seriesColor(i){return getComputedStyle(document.body)
  .getPropertyValue('--series-'+((i%4)+1)).trim()}

/* ---------------------------------------------------------------- launch */
function renderChips(el,items,sel,onClick,ordered){
  el.innerHTML=items.map(n=>{const i=sel.indexOf?sel.indexOf(n):-1;
    const on=sel.has?sel.has(n):i>=0;
    return `<span class="chip ${on?'on':''}" data-n="${esc(n)}">${esc(n)}`+
      (ordered&&i>=0?`<span class="ord">${i+1}</span>`:'')+`</span>`}).join('');
  el.querySelectorAll('.chip').forEach(c=>c.onclick=()=>onClick(c.dataset.n));
}
function defaultB(){
  /* Open ready to run: A stays empty (none), B takes the bench's first suggested skill.
     Otherwise the panel loads with A==B and greets you with an error you did not cause. */
  const b=BENCHES.find(x=>x.name===$('bench').value);
  const first=(b&&b.skills||[]).find(s=>SKILLS.some(k=>k.name===s));
  B=first?[first]:[];
}
function drawLaunch(){
  const b=BENCHES.find(x=>x.name===$('bench').value);
  const roster=b?[...b.skills.filter(s=>SKILLS.some(k=>k.name===s)),
    ...SKILLS.map(s=>s.name).filter(s=>!b.skills.includes(s))]:SKILLS.map(s=>s.name);
  renderChips($('models'),MODELS,SELMODELS,n=>{
    SELMODELS.has(n)?SELMODELS.delete(n):SELMODELS.add(n);drawLaunch()});
  renderChips($('va'),roster,A,n=>{const i=A.indexOf(n);i<0?A.push(n):A.splice(i,1);drawLaunch()},1);
  renderChips($('vb'),roster,B,n=>{const i=B.indexOf(n);i<0?B.push(n):B.splice(i,1);drawLaunch()},1);
  const la=variantLabel(A),lb=variantLabel(B);
  $('vaL').textContent=la;$('vbL').textContent=lb;
  const bad=la===lb;
  $('warn').textContent=bad?'variant A and B are identical - change one':'';
  $('go').disabled=bad||!SELMODELS.size;
  if(b){const d=b.defaults||{};$('reps').value=$('reps').value||d.repeats||1;
    $('bsha').textContent=b.spec_sha;
    $('bdesc').textContent=b.description||'';
    $('bctl').className='badge ctl'+(b.control?'':' hide');
    const ag=b.lane==='agentic';
    $('blane').textContent=b.lane||'chat';
    $('blane').className='badge '+(ag?'run':'ctl');
    /* An agentic bench is only runnable if a VM is actually up. Say so before the
       Run button is pressed, not four cases into a wall of ssh errors. */
    let vmWarn='';
    if(ag){
      if(!VMS||!VMS.configured) vmWarn='agentic bench: no VMs configured (SB_VMS)';
      else{const up=VMS.vms.filter(v=>v.ready&&v.tmux).length;
        if(!up) vmWarn='agentic bench: no VM is reachable with a bench tmux session';
        else vmWarn='';}
    }
    $('vmnote').textContent=ag?(vmWarn||
      `${VMS.vms.filter(v=>v.ready&&v.tmux).length}/${VMS.vms.length} VM(s) ready `+
      `- each case runs on a real machine and is graded on its end state`):'';
    $('vmnote').className=vmWarn?'err':'dim';
    if(vmWarn){$('go').disabled=true}
  }
}

/* ---------------------------------------------------------------- charts */
function barChart(el,rows,opts){
  /* rows: [{label, groups:[{name,value,color}]}] -- horizontal grouped bars */
  const W=el.clientWidth||760,padL=opts.padL||150,padR=54,padT=6,rowH=opts.rowH||17,gap=2;
  const gpr=rows[0]?rows[0].groups.length:1;
  const bandH=gpr*rowH+(gpr-1)*gap, band=bandH+14;
  const H=padT+rows.length*band+22;
  const iw=W-padL-padR, max=opts.max||1;
  let s=`<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" role="img">`;
  for(let t=0;t<=4;t++){const x=padL+iw*t/4;
    s+=`<line class="grid" x1="${x}" y1="${padT}" x2="${x}" y2="${padT+rows.length*band}"/>`;
    s+=`<text class="axis" x="${x}" y="${H-6}" text-anchor="middle">${Math.round(max*t/4*100)}%</text>`}
  rows.forEach((r,ri)=>{const y0=padT+ri*band;
    s+=`<text class="axis" x="${padL-8}" y="${y0+bandH/2+4}" text-anchor="end">${esc(r.label)}</text>`;
    r.groups.forEach((g,gi)=>{const y=y0+gi*(rowH+gap);
      const w=g.value==null?0:Math.max(1,iw*(g.value/max));
      s+=`<rect class="bar" x="${padL}" y="${y}" width="${w}" height="${rowH}" fill="${g.color}"`+
         ` data-tip="${esc(g.name)} &middot; ${esc(r.label)} &middot; ${pct(g.value)}"/>`;
      s+=`<text class="val" x="${padL+w+6}" y="${y+rowH-3}">${pct(g.value)}</text>`})});
  el.innerHTML=s+'</svg>';
  el.querySelectorAll('.bar').forEach(b=>{
    b.onmousemove=e=>{const t=$('tip');t.style.display='block';
      t.innerHTML=b.dataset.tip;t.style.left=(e.clientX+14)+'px';t.style.top=(e.clientY+14)+'px'};
    b.onmouseleave=()=>$('tip').style.display='none'})
}
function legend(el,variants){
  el.innerHTML=variants.map((v,i)=>
    `<span><b style="background:${seriesColor(i)}"></b>${esc(v)}</span>`).join('')}

/* ---------------------------------------------------------------- run view */
function verdict(v,others){ /* symmetric: better green, worse orange, ties neutral */
  if(v==null||others.length<2)return'';
  const mx=Math.max(...others),mn=Math.min(...others);
  if(mx-mn<1e-9)return'';
  return v===mx?'up':(v===mn?'down':'')}

async function showRun(id){
  const d=await api('/api/runs/'+id);RUN=d;const r=d.run;
  $('runview').classList.remove('hide');
  $('rtitle').textContent=`RUN ${r.id} - ${r.bench}`;
  $('rmeta').innerHTML=
    `<span class="badge ${r.status==='done'?'done':r.status==='running'?'run':
      r.status==='aborted'?'abort':'err'}">${esc(r.status)}</span> `+
    `<span class="dim">sha ${esc(r.spec_sha)} &middot; repeats ${r.repeats} &middot; `+
    `${r.models.length} model(s) &middot; started ${esc(r.started_at)}</span>`+
    (r.error?`<div class="msg">${esc(r.error)}</div>`:'');
  $('stop').disabled=!r.running;$('resume').disabled=r.running||r.status==='done';
  $('regrade').disabled=r.running;

  const vars=r.variants;
  /* stat tiles: overall quality per variant + the delta that is the whole point */
  const q={};vars.forEach(v=>{
    const rs=d.results.filter(x=>x.variant===v);
    const ck=rs.reduce((a,x)=>a+x.checks,0),ps=rs.reduce((a,x)=>a+x.passed,0);
    q[v]=ck?ps/ck:null});
  const ti={};vars.forEach(v=>{const rs=d.results.filter(x=>x.variant===v&&x.tokens_in!=null);
    ti[v]=rs.length?Math.round(rs.reduce((a,x)=>a+x.tokens_in,0)/rs.length):null});
  const ref=vars.includes('none')?'none':vars[0];
  $('tiles').innerHTML=vars.map((v,i)=>{
    const dq=(q[v]!=null&&q[ref]!=null&&v!==ref)?(q[v]-q[ref])*100:null;
    return `<div class="tile"><div class="k">${esc(v)}</div>`+
      `<div class="v" style="color:${seriesColor(i)}">${pct(q[v])}</div>`+
      (dq==null?`<div class="k">reference</div>`:
        `<div class="k ${dq>=0?'up':'down'}">${dq>=0?'+':''}${dq.toFixed(1)} pt vs ${esc(ref)}</div>`)+
      `</div>`}).join('')+
    vars.map((v,i)=>ti[v]==null?'':`<div class="tile"><div class="k">${esc(v)} prompt tokens</div>`+
      `<div class="v">${num(ti[v])}</div><div class="k">mean per case</div></div>`).join('');

  /* An agentic run has a second, harder number: did the MACHINE end up fixed. Shown
     separately because a model can describe the right edit and still not make it. */
  const st={};vars.forEach(v=>{const rs=d.results.filter(x=>x.variant===v);
    const n=rs.reduce((a,x)=>a+(x.post||0),0),p=rs.reduce((a,x)=>a+(x.post_passed||0),0);
    st[v]=n?p/n:null});
  if(vars.some(v=>st[v]!=null)){
    $('tiles').innerHTML+=vars.map((v,i)=>{
      const ds=(st[v]!=null&&st[ref]!=null&&v!==ref)?(st[v]-st[ref])*100:null;
      return `<div class="tile" style="border-color:var(--accent)">`+
        `<div class="k">${esc(v)} &mdash; vm state</div>`+
        `<div class="v" style="color:${seriesColor(i)}">${pct(st[v])}</div>`+
        (ds==null?`<div class="k">reference</div>`:
          `<div class="k ${ds>=0?'up':'down'}">${ds>=0?'+':''}${ds.toFixed(1)} pt vs ${esc(ref)}</div>`)+
        `</div>`}).join('')}

  /* chart 1: quality by model */
  legend($('leg1'),vars);
  barChart($('chart1'),r.models.map(m=>({label:m,groups:vars.map((v,i)=>{
    const row=d.results.find(x=>x.model===m&&x.variant===v);
    return{name:v,value:row?row.quality:null,color:seriesColor(i)}})})),{});

  /* chart 2: quality by task */
  const tasks=[...new Set(d.per_task.map(x=>x.task_id))].sort();
  legend($('leg2'),vars);
  barChart($('chart2'),tasks.map(t=>({label:t,groups:vars.map((v,i)=>{
    const rs=d.per_task.filter(x=>x.task_id===t&&x.variant===v);
    const ck=rs.reduce((a,x)=>a+x.checks,0),ps=rs.reduce((a,x)=>a+x.passed,0);
    return{name:v,value:ck?ps/ck:null,color:seriesColor(i)}})})),{});

  /* results table */
  const hasPost=d.results.some(x=>(x.post||0)>0);
  let h='<caption>Results - the same numbers as the charts above'+
    (hasPost?'. STATE grades the VM after the agent stopped; QUALITY grades what it said'
            :'')+'</caption><thead><tr>'+
    '<th class="l">Model</th><th class="l">Variant</th><th>Quality</th>'+
    (hasPost?'<th>State</th>':'')+'<th>Checks</th>'+
    '<th>Cases</th><th>Errors</th><th>Tok in</th><th>Tok out</th><th>Lat mean</th>'+
    '<th>Lat p95</th></tr></thead><tbody>';
  r.models.forEach(m=>{
    const peer=vars.map(v=>{const x=d.results.find(y=>y.model===m&&y.variant===v);
      return x?x.quality:null}).filter(x=>x!=null);
    const peerState=vars.map(v=>{const x=d.results.find(y=>y.model===m&&y.variant===v);
      return x?x.state:null}).filter(x=>x!=null);
    vars.forEach((v,i)=>{const x=d.results.find(y=>y.model===m&&y.variant===v);if(!x)return;
      h+=`<tr data-m="${esc(m)}" data-v="${esc(v)}"><td class="l">${esc(m)}</td>`+
        `<td class="l"><b style="color:${seriesColor(i)}">&#9632;</b> ${esc(v)}</td>`+
        `<td class="${verdict(x.quality,peer)}">${meter(x.quality,seriesColor(i))} ${pct(x.quality)}</td>`+
        (hasPost?`<td class="${verdict(x.state,peerState)}">`+
          `${meter(x.state,seriesColor(i))} ${pct(x.state)}`+
          `<span class="dim"> ${x.post_passed||0}/${x.post||0}</span></td>`:'')+
        `<td>${x.passed}/${x.checks}</td><td>${x.cases}</td>`+
        `<td class="${x.errors?'err':''}">${x.errors}</td>`+
        `<td>${num(x.tokens_in)}</td><td>${num(x.tokens_out)}</td>`+
        `<td>${x.latency_mean??'--'}s</td><td>${x.latency_p95??'--'}s</td></tr>`})});
  $('results').innerHTML=h+'</tbody>';
  $('results').querySelectorAll('tbody tr').forEach(tr=>tr.onclick=()=>
    loadCases(id,{model:tr.dataset.m,variant:tr.dataset.v}));

  /* per-task table */
  let h2='<caption>Per task - click a row for the raw outputs</caption><thead><tr>'+
    '<th class="l">Task</th>'+vars.map(v=>`<th>${esc(v)}</th>`).join('')+
    '<th>&Delta; pt</th></tr></thead><tbody>';
  tasks.forEach(t=>{
    const qs=vars.map(v=>{const rs=d.per_task.filter(x=>x.task_id===t&&x.variant===v);
      const ck=rs.reduce((a,x)=>a+x.checks,0),ps=rs.reduce((a,x)=>a+x.passed,0);
      return ck?ps/ck:null});
    const rq=qs[vars.indexOf(ref)],dq=qs.map((v,i)=>vars[i]===ref||v==null||rq==null?null:(v-rq)*100)
      .filter(x=>x!=null);
    h2+=`<tr data-t="${esc(t)}"><td class="l">${esc(t)}</td>`+
      qs.map((v,i)=>`<td class="${verdict(v,qs.filter(x=>x!=null))}">`+
        `${meter(v,seriesColor(i))} ${pct(v)}</td>`).join('')+
      `<td class="${dq.length&&dq[0]>=0?'up':dq.length?'down':''}">`+
      `${dq.length?(dq[0]>=0?'+':'')+dq[0].toFixed(1):'--'}</td></tr>`});
  $('pertask').innerHTML=h2+'</tbody>';
  $('pertask').querySelectorAll('tbody tr').forEach(tr=>tr.onclick=()=>
    loadCases(id,{task:tr.dataset.t}));

  if(r.running&&!POLL)POLL=setInterval(()=>showRun(id),4000);
  if(!r.running&&POLL){clearInterval(POLL);POLL=null;loadRuns()}
}

async function loadCases(id,f){
  const qs=new URLSearchParams(f).toString();
  const d=await api(`/api/runs/${id}/cases?`+qs);
  $('cases').classList.remove('hide');
  $('cases').innerHTML='<h3>Cases &middot; '+esc(JSON.stringify(f))+'</h3>'+
    (d.cases.length?'':'<p class="dim">no cases</p>')+
    d.cases.map(c=>{
      const ok=c.checks.filter(x=>x.passed).length;
      return `<div class="panel" style="margin-bottom:10px"><div class="row" style="margin:0 0 6px">
        <div class="col"><b>${esc(c.task_id)}</b> <span class="dim">${esc(c.model)} &middot;
        ${esc(c.variant)} &middot; rep ${c.repeat_idx}</span></div>
        <div><span class="badge ${ok===c.checks.length?'done':'err'}">${ok}/${c.checks.length}</span>
        <span class="dim">${num(c.prompt_tokens)} in &middot; ${num(c.completion_tokens)} out
        &middot; ${c.latency_s??'--'}s</span></div></div>`+
        c.checks.map(k=>`<div class="chk ${k.passed?'':'no'}">${esc(k.criterion)}`+
          (k.note?` <span class="dim">- ${esc(k.note)}</span>`:'')+`</div>`).join('')+
        `<div class="out">${esc(c.error||c.output||'')}</div></div>`}).join('');
  $('cases').scrollIntoView({behavior:'smooth',block:'nearest'});
}

async function loadRuns(){
  const d=await api('/api/runs');
  $('runs').innerHTML='<caption>Runs &mdash; click a row to open it above</caption>'+
    '<thead><tr><th>#</th><th class="l">Bench</th>'+
    '<th class="l">Variants</th><th>Models</th><th>Cases</th><th class="l">Status</th>'+
    '<th class="l">Started</th></tr></thead><tbody>'+
    d.runs.map(r=>`<tr data-id="${r.id}"><td>${r.id}</td><td class="l">${esc(r.bench)}</td>`+
      `<td class="l">${r.variants.map(esc).join(' vs ')}</td><td>${r.models.length}</td>`+
      `<td>${r.cases}</td><td class="l"><span class="badge ${r.status==='done'?'done':
        r.status==='running'?'run':r.status==='aborted'?'abort':'err'}">${esc(r.status)}</span></td>`+
      `<td class="l dim">${esc(r.started_at)}</td></tr>`).join('')+'</tbody>';
  $('runs').querySelectorAll('tbody tr').forEach(tr=>tr.onclick=()=>{
    $('runs').querySelectorAll('tr').forEach(x=>x.classList.remove('sel'));
    tr.classList.add('sel');location.hash='run-'+tr.dataset.id;showRun(+tr.dataset.id)});
}

function say(m,ok){const e=$('say');e.className='msg'+(ok?' ok':'');e.textContent=m;
  e.classList.toggle('hide',!m)}

async function boot(){
  try{
    const [b,s,m,v]=await Promise.all([api('/api/benches'),api('/api/skills'),
      api('/api/models').catch(e=>{say('Ollama unreachable: '+e.message);return{models:[]}}),
      api('/api/vms').catch(()=>({vms:[],configured:false}))]);
    BENCHES=b.benches;SKILLS=s.skills;MODELS=m.models;VMS=v;
    $('bench').innerHTML=BENCHES.map(x=>`<option value="${esc(x.name)}">${esc(x.name)}`+
      (x.control?' (control)':'')+`</option>`).join('');
    $('bench').onchange=()=>{A=[];B=[];defaultB();drawLaunch()};
    defaultB();drawLaunch();await loadRuns();
    const hm=location.hash.match(/^#run-(\d+)$/);if(hm)showRun(+hm[1]);
  }catch(e){say('startup failed: '+e.message)}
}
$('go').onclick=async()=>{
  say('');
  try{const r=await api('/api/runs',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({bench:$('bench').value,models:[...SELMODELS],
      variants:[variantLabel(A),variantLabel(B)],repeats:+$('reps').value||null})});
    say('launched run '+r.run_id,1);await loadRuns();showRun(r.run_id)}
  catch(e){say(e.message)}};
$('stop').onclick=async()=>{try{await api(`/api/runs/${RUN.run.id}/stop`,{method:'POST'});
  say('stopping - the partial matrix is kept',1)}catch(e){say(e.message)}};
$('resume').onclick=async()=>{try{await api(`/api/runs/${RUN.run.id}/resume`,{method:'POST'});
  say('resumed',1);showRun(RUN.run.id)}catch(e){say(e.message)}};
$('regrade').onclick=async()=>{try{const r=await api(`/api/runs/${RUN.run.id}/regrade`,
  {method:'POST'});say(`regraded ${r.regraded} case(s) - no model calls`,1);
  showRun(RUN.run.id)}catch(e){say(e.message)}};
$('theme').onchange=()=>location.search='?theme='+encodeURIComponent($('theme').value);
boot();
"""


def page(colors, themes):
    from . import theme as T
    opts = "".join(
        f'<option value="{t}"{" selected" if t == colors["name"] else ""}>{t}</option>'
        for t in themes)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Omarchy Skill Bench</title>
<style>{T.css(colors)}{CSS}</style></head><body>
<div class="wrap">

  <div class="head">
    <span class="pip"></span>
    <h1>Omarchy Skill Bench</h1>
    <div style="min-width:170px"><label for="theme">Theme</label>
      <select id="theme">{opts}</select></div>
  </div>

  <div id="say" class="msg hide"></div>

  <div class="panel">
    <h2>Launch</h2>
    <div class="row">
      <div class="col" style="flex:2"><label for="bench">Bench</label>
        <select id="bench"></select></div>
      <div class="col" style="max-width:110px"><label for="reps">Repeats</label>
        <input id="reps" type="number" min="1" max="10" value="1"></div>
      <div class="col"><label>Spec sha</label>
        <div class="dim" id="bsha">--</div>
        <span id="bctl" class="badge ctl hide">control</span>
        <span id="blane" class="badge ctl">chat</span></div>
    </div>
    <p class="dim" id="bdesc" style="margin-bottom:4px"></p>
    <p id="vmnote" class="dim" style="margin-bottom:10px;font-size:11px"></p>
    <div class="row">
      <div class="col" style="flex:2"><label>Models &mdash; local Ollama</label>
        <div class="chips" id="models"></div></div>
    </div>
    <div class="row">
      <div class="col"><label>Variant A &mdash; <span id="vaL">none</span></label>
        <div class="chips" id="va"></div></div>
      <div class="col"><label>Variant B &mdash; <span id="vbL">none</span></label>
        <div class="chips" id="vb"></div></div>
    </div>
    <div class="row">
      <button id="go" class="go">Run</button>
      <span class="err" id="warn"></span>
    </div>
    <p class="dim" style="font-size:11px">Click skills to stack them; order is significant and
      recorded, so <code>a+b</code> and <code>b+a</code> are different variants. An empty side
      is <code>none</code>. Local models only &mdash; every run costs nothing, and the price of
      a skill shows up as prompt tokens.</p>
  </div>


  <div id="runview" class="panel hide">
    <div class="row" style="margin-bottom:6px">
      <div class="col" style="flex:2"><h2 id="rtitle"></h2><div id="rmeta"></div></div>
      <button id="stop">Stop</button>
      <button id="resume">Resume</button>
      <button id="regrade">Regrade</button>
    </div>
    <div class="tiles" id="tiles"></div>

    <h3>Quality by model</h3>
    <div class="legend" id="leg1"></div><div id="chart1"></div>

    <h3>Quality by task</h3>
    <div class="legend" id="leg2"></div><div id="chart2"></div>

    <h3>Results</h3>
    <div class="scroll"><table id="results"></table></div>
    <div class="scroll"><table id="pertask"></table></div>
  </div>

  <div id="cases" class="hide"></div>

  <!-- The run list sits at the BOTTOM. The page reads top-down as the order you work in:
       launch a run, watch the run you just launched, drill into its cases, and only then
       the history you might jump back to. Above the fold it was pushing the thing you
       actually came to look at off the screen. -->
  <div class="panel"><div class="scroll"><table id="runs"></table></div></div>
</div>
<div class="tip" id="tip"></div>
<script>{JS}</script>
</body></html>"""
