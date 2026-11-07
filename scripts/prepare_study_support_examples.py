#!/usr/bin/env python3
"""Export public study-support examples using a disposable synthetic family DB."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'scripts'))
from prepare_family_math import prepare as prepare_family
from learning_service.db import Database
from learning_service.practice import install
from learning_service.study_support import query_support
from learning_service.textbooks import catalogue


HTML=r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; connect-src 'none'">
<title>学习探险队 · 离线理解工坊</title><style>
:root{font-family:system-ui,"Microsoft YaHei",sans-serif;color:#18392f;background:#f5f7ef}*{box-sizing:border-box}
body{margin:0}main{max-width:1100px;margin:auto;padding:26px 20px}header{background:#174c3c;color:white;border-radius:22px;padding:28px}
h1{margin:0 0 10px;font-size:clamp(25px,4vw,36px)}h2{font-size:22px}p{line-height:1.65}header p{color:#e3f3e4;margin:0}
.tag{font-size:13px;color:#255c49;background:#e2eddc;padding:6px 12px;border-radius:99px;display:inline-block}
.selectors{display:flex;gap:12px;flex-wrap:wrap;background:white;padding:18px;border-radius:16px;margin-top:20px}
label{font-size:14px;font-weight:650;display:flex;flex-direction:column;gap:7px;flex:1;min-width:140px}
select,button,input{font:inherit}select{padding:10px;border:1px solid #bbcec0;border-radius:9px;background:#fafcf9;width:100%}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),1fr));gap:14px}
.card,.panel{background:#fff;border:1px solid #dee8db;border-radius:16px;padding:20px;margin:14px 0}.card h3{margin:0 0 10px}
.card p{margin:6px 0}.muted{color:#587166;font-size:14px}.pages{font-size:13px;color:#3e725a;margin-top:12px}
button{border:0;border-radius:9px;padding:11px 15px;background:#216247;color:white;cursor:pointer;margin:6px 8px 6px 0}
button:focus-visible,select:focus-visible,input:focus-visible{outline:3px solid #e3a81b;outline-offset:3px}
.control-row{display:flex;flex-wrap:wrap;gap:22px}.control-row label{max-width:300px}output{font-size:23px;font-weight:700;display:block;margin:20px 0}
svg{display:block;width:100%;max-height:280px;border-radius:12px;background:#f4f8f0}[hidden]{display:none!important}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f6f8f3;padding:15px;border-radius:10px;font-size:13px}
footer{font-size:13px;color:#63796a;margin:24px 0;line-height:1.7}details{margin-top:15px}.empty{padding:15px;background:#fff5d7;border-radius:12px}
</style></head><body><main>
<header><span class="tag">公开教材 · 离线样例 · 不保存学习记录</span><h1>学习探险队 · 理解工坊</h1>
<p>看清关系，找到依据，用自己的话说明。选择学科，试一试适合这门课的学习方法。</p></header>
<div class="selectors"><label>样例年级<select id="grade"><option value="2">二年级</option><option value="7">七年级</option></select></label>
<label>学科 / 课本<select id="book"></select></label><label>章节（可选）<select id="chapter"></select></label></div>
<p id="scope" class="muted"></p><h2>三个理解步骤</h2><div id="steps" class="cards"></div>
<section id="mathPanel" class="panel" hidden><h2 id="mathTitle"></h2><p id="mathHint" class="muted"></p>
<div id="groupControls" class="control-row"><label>每组数量：<span id="eachLabel"></span><input id="each" type="range" min="1" max="6" value="3"></label>
<label>组数：<span id="groupsLabel"></span><input id="groups" type="range" min="1" max="6" value="4"></label></div>
<div id="lineControls" class="control-row" hidden><label>起点<input id="start" type="range" min="-8" max="8" value="-3"></label>
<label>变化量<input id="change" type="range" min="-8" max="8" value="5"></label><label>运算<select id="operation"><option value="add">加上变化量</option><option value="subtract">减去变化量</option></select></label></div>
<output id="calculation" aria-live="polite"></output><svg id="visual" viewBox="0 0 700 230" role="img" aria-label="数值关系演示"></svg>
<p class="muted">这些参数用于理解数量关系；不会创建题目、作答记录或成绩。数学第五章的等式性质说明见下面的知识卡。</p></section>
<section><h2>本地概念与核对点</h2><p id="mapping" class="muted"></p><div id="concepts" class="cards"></div></section>
<section class="panel"><h2>带走一份学习卡</h2><p class="muted">Markdown 可交给 Marp 排版成讲义；Mermaid 文本可在兼容阅读器中显示为图。导出文件只含本页公开参考资料。</p>
<button id="download">下载学习卡 .md</button><button id="diagram">下载关系图 .mmd</button>
<details><summary>查看导出内容与来源</summary><pre id="export"></pre></details></section>
<footer>请和当前课本一起使用。数学原页位置为局部核对，其他学科目前提供阅读方法。
<details><summary>来源与许可</summary>参考 faststudy-knowledge 的 SCENARIOS 场景，以及 EduLab 的独立交互课件、Mermaid 的文本关系图和 Marp 的讲义格式。
本页使用本地编写的代码、问题串与人教版映射，未接入这些平台的运行服务。图谱相关元数据保留 CC BY-NC-SA 4.0；教材版权归出版社。
数学原页位置仅经过局部核对，整页审核和教师审核均未完成。其他学科提供阅读方法，尚未建立精确知识与答案映射。</details></footer>
</main><script id="public-data" type="application/json">__DATA__</script><script>
const data=JSON.parse(document.getElementById('public-data').textContent),$=id=>document.getElementById(id);let current;
function box(title,text,extra=''){const node=document.createElement('article');node.className='card';const h=document.createElement('h3');h.textContent=title;const p=document.createElement('p');p.textContent=text;node.append(h,p);if(extra){const e=document.createElement('p');e.className='pages';e.textContent=extra;node.append(e)}return node}
function books(){const grade=Number($('grade').value);$('book').replaceChildren();for(const b of data.books.filter(b=>b.grade===grade)){const o=new Option(b.subject_title+' · '+b.semester,b.id);$('book').add(o)}chapters()}
function chapters(){$('chapter').replaceChildren(new Option('整本书',''));const b=data.books.find(b=>b.id===$('book').value);for(const c of b.chapters)$('chapter').add(new Option(c.title,c.id));render()}
function render(){const key=$('book').value+'|'+$('chapter').value;current=data.scopes[key];$('scope').textContent=current.support.scope.title+' / '+current.support.scope.chapter_title+' · '+current.support.scope.edition;
$('steps').replaceChildren(...current.support.study_steps.map((s,i)=>box((i+1)+'. '+s.title,s.prompt)));
$('mapping').textContent=current.math?.mapping_status==='mapped'?'这是已映射题目的小样本；核对点用于回顾，不代表已确认错因。':'本范围提供阅读问题串；暂未建立精确概念/页码映射。';
$('concepts').replaceChildren(...[...(current.math?.concepts||[]),...(current.math?.prerequisites||[])].map(n=>box(n.title,n.explanation+' '+n.checks.join(' '),n.pages.length?'本册原页：'+n.pages.map(p=>p.printed_page).join('、'):'本地综合核对点，无原页声明')));
const math=current.math?.mapping_status==='mapped';const isG2=$('grade').value==='2';const g7Number=math&&current.math.concepts.some(n=>['g7-add','g7-subtract','g7-sign'].includes(n.id));$('mathPanel').hidden=!math||(!isG2&&!g7Number);$('groupControls').hidden=!isG2;$('lineControls').hidden=isG2;
$('mathTitle').textContent=isG2?'把相同的组摆出来':'在数轴上看加减';$('mathHint').textContent=isG2?'改变每组数量和组数，比较乘法与两种除法的含义。':'向右是正方向；减去一个数，相当于加上它的相反数。';$('export').textContent=current.support.lesson_markdown;draw()}
function elem(name,attrs,text){const n=document.createElementNS('http://www.w3.org/2000/svg',name);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;return n}
function draw(){const svg=$('visual');svg.replaceChildren();if($('grade').value==='2'){const each=Number($('each').value),groups=Number($('groups').value),total=each*groups;$('eachLabel').textContent=each;$('groupsLabel').textContent=groups;$('calculation').textContent=`${each} × ${groups} = ${total}`+(current.support.interactive_template==='multiplication_groups_v1'?'':`；${total} ÷ ${groups} = ${each}（每组）；${total} ÷ ${each} = ${groups}（组数）`);
for(let g=0;g<groups;g++){const x=18+g*112;svg.append(elem('rect',{x,y:20,width:100,height:172,rx:12,fill:'#e5efd9',stroke:'#83ac81'}));for(let j=0;j<each;j++)svg.append(elem('circle',{cx:x+28+(j%2)*42,cy:49+Math.floor(j/2)*49,r:14,fill:'#e8ad3e'}));svg.append(elem('text',{x:x+50,y:216,'text-anchor':'middle',fill:'#28533d','font-size':17},`第${g+1}组`))}}
else{const start=Number($('start').value),change=Number($('change').value),subtract=$('operation').value==='subtract',delta=subtract?-change:change,end=start+delta,x=n=>350+n*15;$('calculation').textContent=`${start} ${subtract?'−':'+'} (${change}) = ${end}；从 ${start} ${delta>=0?'向右':'向左'}移动 ${Math.abs(delta)} 格`;
svg.append(elem('line',{x1:40,y1:145,x2:660,y2:145,stroke:'#486455','stroke-width':2}));for(let i=-20;i<=20;i++){svg.append(elem('line',{x1:x(i),y1:139,x2:x(i),y2:151,stroke:'#799380'}));if(i%5===0)svg.append(elem('text',{x:x(i),y:179,'text-anchor':'middle',fill:'#345643'},i))}
svg.append(elem('line',{x1:x(start),y1:90,x2:x(end),y2:90,stroke:'#d99020','stroke-width':5}));svg.append(elem('circle',{cx:x(start),cy:145,r:7,fill:'#287153'}));svg.append(elem('circle',{cx:x(end),cy:90,r:9,fill:'#dc9828'}));svg.append(elem('text',{x:x(end),y:64,'text-anchor':'middle',fill:'#9b610b','font-size':19},`结果 ${end}`))}}
function save(extension,text){const blob=new Blob([text],{type:'text/plain;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=$('book').value+'-'+($('chapter').value||'all')+extension;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
$('grade').onchange=books;$('book').onchange=chapters;$('chapter').onchange=render;for(const id of ['each','groups','start','change','operation'])$(id).oninput=draw;$('download').onclick=()=>save('.md',current.support.lesson_markdown);$('diagram').onclick=()=>save('.mmd',current.support.diagram_mermaid);books();
</script></body></html>'''


def prepare(destination):
    destination=destination.resolve()
    if destination.exists() or not destination.is_relative_to(ROOT):
        raise ValueError('choose a new destination under the project; existing files are preserved')
    payload={'books':[], 'scopes':{}}
    with tempfile.TemporaryDirectory(prefix='dd-study-example-') as scratch:
        family=Path(scratch)/'family';prepare_family(family,'synthetic-parent')
        db=Database(family/'learning.db');install(db)
        for grade in (2,7):
            curriculum=f'math-g{grade}-v1'
            for book in catalogue(curriculum):
                payload['books'].append({k:book[k] for k in ('id','grade','subject','subject_title','semester','chapters')})
                for chapter in ['',*[c['id'] for c in book['chapters']]]:
                    with db.session() as conn:
                        support=query_support(conn,f'family-g{grade}',curriculum,ROOT/'learning_data/textbooks/pep-current-20261105',
                                              book_id=book['id'],chapter_id=chapter)
                        math=None
                        if book['subject']=='math':
                            from learning_service.math_references import query_reference
                            math=query_reference(conn,f'family-g{grade}',curriculum,ROOT/'learning_data/textbooks/pep-current-20261105',
                                                 book_id=book['id'],chapter_id=chapter)
                    payload['scopes'][book['id']+'|'+chapter]={'support':support,'math':math}
    encoded=json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    destination.mkdir(parents=True)
    (destination/'offline-study.html').write_text(HTML.replace('__DATA__',encoded))
    (destination/'public-study-data.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    for name in ('faststudy-LICENSE-DATA.txt','faststudy-NOTICE.txt'):
        (destination/name).write_bytes((ROOT/'learning_service/data'/name).read_bytes())
    exported=destination/'exports';exported.mkdir()
    for key,value in payload['scopes'].items():
        book,chapter=key.split('|');stem=book+'-'+(chapter or 'all')
        (exported/(stem+'.md')).write_text(value['support']['lesson_markdown'])
        (exported/(stem+'.mmd')).write_text(value['support']['diagram_mermaid']+'\n')
    hashes={str(p.relative_to(destination)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(destination.rglob('*')) if p.is_file()}
    manifest={'format':'dd-public-study-support-examples-v1','books':len(payload['books']),'scopes':len(payload['scopes']),
              'student_data_included':False,'model_calls':0,'production_writes':0,'upstream_runtime_installed':False,
              'artifact_sha256':hashes}
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:v for k,v in manifest.items() if k!='artifact_sha256'}))
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--destination',type=Path,required=True)
    prepare(parser.parse_args().destination)
