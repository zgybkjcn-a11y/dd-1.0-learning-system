"""No external assets; textbook text is always assigned via textContent/value."""

HTML = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="review-token" content="__TOKEN__">
<title>片段复核工作台</title><link rel="stylesheet" href="/style.css"><script src="/app.js" defer></script></head>
<body><header><p class="eyebrow">教材 · 局部内容复核</p><h1>片段复核工作台</h1>
<p>对照原页，再记录独立推导。每次修订重新核验，所有记录保留。</p>
<p id="operator"></p><p id="state" role="status"></p><button id="refresh">刷新当前版本</button>
<p id="message" role="alert"></p></header>
<main><div class="workspace"><section class="source"><h2>原页对照</h2><p id="location"></p>
<a id="zoom" target="_blank" rel="noopener">打开原图放大</a><img id="original" alt="当前片段所对应的教材完整原页">
<details><summary>原生提取文字（未审核，仅供比对）</summary><pre id="native"></pre></details></section>
<section><h2>转写与上下文</h2><p>范围只限所选片段。教材原文有误时保留原文并登记问题。</p>
<label>片段转写<textarea id="text" rows="4" maxlength="1400"></textarea></label>
<label>上下文与排除范围<textarea id="context" rows="4" maxlength="4000"></textarea></label>
<label>来源 PDF 页码<input id="pdfPage" type="number" min="1"></label>
<label>修订说明<textarea id="revisionReason" rows="2"></textarea></label>
<button id="revise">保存新修订并重审</button>
<h3>原图转写复核</h3><label>逐字、数字与符号的对照依据<textarea id="visualNotes" rows="3"></textarea></label>
<label>片段边界、完整性与上下文依据<textarea id="scopeNotes" rows="3"></textarea></label>
<label>版面、分数与行列的核对依据<textarea id="layoutNotes" rows="3"></textarea></label>
<button id="transcription">记录转写复核</button><p id="visualStatus"></p></section>
<section><h2>独立内容核验</h2><p>记录推导和核算关系；勾选或重复识别不能代替核验。</p>
<label>独立推导<textarea id="derivation" rows="6"></textarea></label>
<label>条件完整性与适用范围<textarea id="conditions" rows="3"></textarea></label>
<label>单位与所求对象<textarea id="units" rows="3"></textarea></label>
<label>图形依赖<select id="diagram"><option value="pending">尚未确认</option><option value="none_for_selected_excerpt">本片段不依赖图形</option><option value="requires_diagram">依赖图形，保持待核</option></select></label>
<label>独立核算（每行：完整等式 | 与片段的关系）<textarea id="checks" rows="5" placeholder="3+2=5 | 说明此核算如何支持所选内容"></textarea></label>
<p class="note">等式采用精确有理数核算；一般论断仍须审核者提供推导依据。</p>
<button id="semantic">记录独立核验</button><p id="semanticStatus"></p></section></div>
<div class="lower"><section><h2>问题与处理依据</h2><label>新增问题<textarea id="issueText" rows="3"></textarea></label>
<button id="addIssue">登记问题并停用</button><div id="issues"></div></section>
<section><h2>本地候选状态</h2><ul id="blockers"></ul><label>启停或撤回说明<textarea id="reason" rows="2"></textarea></label>
<div class="buttons"><button id="enable">启用本地候选</button><button id="disable">停用</button><button id="withdraw" class="danger">撤回并要求重审</button></div>
<p>仅在此复核目录生效。完整页审核、教师签署和题目判分资格均未授予；运行主站另行接入验收。</p>
<button id="export">保存本地审核快照</button><p id="exportStatus"></p></section></div>
<section><h2>版本与审核历史</h2><p>历史证据可回查，不能用于当前片段引用。</p><ol id="history"></ol></section></main>
</body></html>'''

STYLE = '''*{box-sizing:border-box}body{margin:0;background:#f4f5f1;color:#203932;font:16px/1.65 system-ui,sans-serif}
header,main{max-width:1600px;margin:auto;padding:24px}h1{font-size:32px;margin:4px 0}h2{font-size:21px;margin:0 0 14px}h3{margin-top:28px}.eyebrow{color:#527568;letter-spacing:.1em}
.workspace{display:grid;grid-template-columns:1.15fr 1fr 1fr;gap:18px}.lower{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:18px 0}section{background:white;border:1px solid #d7dfd9;border-radius:14px;padding:20px;min-width:0}
label{display:block;margin:14px 0}textarea,input,select{display:block;width:100%;font:inherit;border:1px solid #98afa2;border-radius:7px;padding:10px;background:#fcfdfb;color:#203932}textarea{resize:vertical}button{font:inherit;border:0;border-radius:7px;padding:10px 15px;background:#176953;color:white;cursor:pointer;margin:4px 6px 4px 0}button:disabled{opacity:.45;cursor:default}button:focus-visible,a:focus-visible{outline:3px solid #d39525;outline-offset:3px}.danger{background:#914938}.buttons{display:flex;flex-wrap:wrap}img{display:block;width:100%;height:auto;border:1px solid #dae0db;margin:12px 0}a{color:#116a52}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}.note,section p{color:#526b5e}#state{font-weight:bold}#message{color:#8c2e25;white-space:pre-wrap}#history li{margin:10px 0;overflow-wrap:anywhere}#issues article{border-top:1px solid #ddd;margin:16px 0;padding:14px 0}#exportStatus{overflow-wrap:anywhere}@media(max-width:1050px){.workspace{grid-template-columns:1fr 1fr}.source{grid-column:1/-1}.source img{max-height:650px;width:auto;max-width:100%;object-fit:contain}.lower{grid-template-columns:1fr}}@media(max-width:650px){header,main{padding:16px}.workspace{grid-template-columns:1fr}.source img{max-height:none;width:100%}section{padding:16px}h1{font-size:27px}}
'''

SCRIPT = r''''use strict';
const $=id=>document.getElementById(id), token=document.querySelector('meta[name="review-token"]').content;
let state=null, busy=false, imageUrl=null, dirty=false, generation=0;
const names={import_pending:'导入待核',revise:'新修订',transcription:'转写复核',semantic:'独立核验',issue:'登记问题',resolve:'问题处理',enable:'本地启用',disable:'停用',withdraw:'撤回'};
const roles={assistant:'助手',human:'人工操作者（身份自述）'};
async function api(path, options={}) {
 const response=await fetch(path,{...options,headers:{'X-Review-Token':token,...options.headers}});
 if(!response.ok){let data;try{data=await response.json()}catch{data={error:'复核请求失败'}};throw new Error(data.error || '请求未通过：'+response.status)}
 return response;
}
function lock(on){busy=on;document.querySelectorAll('button').forEach(b=>b.disabled=on);if(!on&&state){$('enable').disabled=state.blockers.length>0||state.available;$('export').disabled=!state.available;if(state.source_unavailable)document.querySelectorAll('button').forEach(b=>b.disabled=!['refresh','disable','withdraw'].includes(b.id))}}
function contentChanged(){return state&&($('text').value!==state.content.text||$('context').value!==state.content.context||Number($('pdfPage').value)!==state.content.source.pdf_page)}
function annotate(node,text){node.textContent=text}
function render(s){
 state=s;dirty=false;
 $('operator').textContent='当前操作者：'+roles[s.operator.type]+' · '+s.operator.label;
 $('state').textContent='内容修订 '+s.revision+' · 审核记录 '+s.seq+' · '+(s.available?'本地候选已启用':s.withdrawn?'已撤回':'待复核 / 已停用')+' · 有效期至 '+s.valid_until;
 $('location').textContent='七上数学 · 第二章 · 书内第 '+s.content.source.printed_page+' 页 / PDF 第 '+s.content.source.pdf_page+' 页';
 $('text').value=s.content.text;$('context').value=s.content.context;$('pdfPage').value=s.content.source.pdf_page;$('native').textContent=s.native_text;
 $('revisionReason').value='';$('reason').value='';$('issueText').value='';
 const v=s.transcription,m=s.semantic;
 $('visualNotes').value=v?.notes||'';$('scopeNotes').value=v?.scope_notes||'';$('layoutNotes').value=v?.layout_notes||'';
 $('derivation').value=m?.derivation||'';$('conditions').value=m?.conditions||'';$('units').value=m?.units||'';$('diagram').value=m?.diagram||'pending';
 $('checks').value=(m?.checks||[]).map(c=>c.claim+' | '+c.purpose).join('\n');
 $('visualStatus').textContent=v?'已记录：'+roles[v.actor.type]+' · '+v.actor.label:'尚无本版本转写复核';
 $('semanticStatus').textContent=m?'已记录：'+roles[m.actor.type]+' · '+m.actor.label:'尚无本版本独立核验';
 $('blockers').replaceChildren();for(const reason of s.blockers){const li=document.createElement('li');li.textContent=reason;$('blockers').append(li)}
 $('issues').replaceChildren();for(const item of s.issues){const card=document.createElement('article'),text=document.createElement('p');text.textContent=item.id+' · '+item.description;card.append(text);
 if(item.resolution){const solved=document.createElement('p');solved.textContent='处理依据：'+item.resolution.notes;card.append(solved)}else{const label=document.createElement('label');label.textContent='解决依据';const input=document.createElement('textarea');input.rows=2;input.dataset.issue=item.id;label.append(input);const button=document.createElement('button');button.textContent='记录解决依据并重审';button.onclick=()=>command('resolve',{issue_id:item.id,resolution:input.value});card.append(label,button)}$('issues').append(card)}
}
async function refresh(force=false){
 if(busy)return;
 if(dirty&&!force&&!window.confirm('刷新会替换尚未提交的表单，请先保存所需文字。继续刷新吗？'))return;
 lock(true);const g=++generation;$('message').textContent='';
 try{
  const s=await(await api('/api/state')).json();const blob=await(await api('/api/image?seq='+s.seq)).blob();
  const current=await(await api('/api/state')).json();if(current.seq!==s.seq)throw new Error('图片加载期间版本已变化，请重新刷新');
  if(g!==generation)return;
  render(s);if(imageUrl)URL.revokeObjectURL(imageUrl);imageUrl=URL.createObjectURL(blob);$('original').src=imageUrl;$('zoom').href=imageUrl;
  const history=await(await api('/api/history')).json();$('history').replaceChildren();for(const entry of history.events.slice().reverse()){
   const li=document.createElement('li'),heading=document.createElement('strong');heading.textContent='#'+entry.seq+' · 修订'+entry.state.revision+' · '+names[entry.action]+' · '+roles[entry.actor.type]+' · '+entry.actor.label;
   const details=document.createElement('details'),summary=document.createElement('summary'),body=document.createElement('pre');summary.textContent='查看当时记录 · '+entry.at;body.textContent=JSON.stringify(entry.state,null,2);details.append(summary,body);li.append(heading,details);$('history').append(li)}
 }catch(e){$('message').textContent=e.message;state=null;$('state').textContent='当前材料不可用，请核对来源或刷新';$('original').removeAttribute('src');$('zoom').removeAttribute('href');$('native').textContent='';
  try{const h=await(await api('/api/history')).json(),last=h.events.at(-1);state={...last.state,seq:last.seq,available:false,blockers:['当前材料不可用'],source_unavailable:true};$('state').textContent='审核记录 '+last.seq+' · 材料不可用 · '+(last.state.withdrawn?'已撤回':'可停用或撤回');}catch{}
 }finally{lock(false);if(!state){$('enable').disabled=true;$('export').disabled=true}}
}
async function command(action,values){
 if(busy||!state)return;
 if(!['revise','disable','withdraw'].includes(action)&&contentChanged()){$('message').textContent='片段或来源有未保存修改，请先保存新修订再复核。';return}
 lock(true);$('message').textContent='';
 try{await api('/api/commands',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_seq:state.seq,action,values})});lock(false);await refresh(true)}
 catch(e){$('message').textContent=e.message+'；未提交表单已保留。';lock(false)}
}
$('refresh').onclick=()=>refresh();
$('revise').onclick=()=>command('revise',{text:$('text').value,context:$('context').value,pdf_page:Number($('pdfPage').value),reason:$('revisionReason').value});
$('transcription').onclick=()=>command('transcription',{notes:$('visualNotes').value,scope_notes:$('scopeNotes').value,layout_notes:$('layoutNotes').value});
$('semantic').onclick=()=>{try{const checks=$('checks').value.split('\n').filter(x=>x.trim()).map(line=>{const at=line.indexOf('|');if(at<0)throw new Error('每行需用 | 分隔算式与核验关系');return{claim:line.slice(0,at).trim(),purpose:line.slice(at+1).trim()}});command('semantic',{derivation:$('derivation').value,conditions:$('conditions').value,units:$('units').value,diagram:$('diagram').value,checks})}catch(e){$('message').textContent=e.message}};
$('addIssue').onclick=()=>command('issue',{description:$('issueText').value});
for(const action of ['enable','disable','withdraw'])$(action).onclick=()=>command(action,{reason:$('reason').value});
$('export').onclick=async()=>{if(busy||!state)return;if(contentChanged()){$('message').textContent='存在未保存修订，请先保存并重审后导出。';return}lock(true);try{const r=await(await api('/api/export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_seq:state.seq,action:'export',values:{}})})).json();$('exportStatus').textContent='已保存历史审核快照：'+r.directory+'。后续停用或修订后请以工作台当前状态为准。'}catch(e){$('message').textContent=e.message}finally{lock(false)}};
document.querySelectorAll('textarea,input,select').forEach(input=>input.addEventListener('input',()=>dirty=true));
refresh();
'''
