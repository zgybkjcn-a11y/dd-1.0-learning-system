"""Trusted workbench fragments for read-only, scope-bound study support."""

STYLE = r'''
    .study-support { margin-top: 16px; padding: 14px; border: 1px solid #dce4d6; border-radius: 14px; background: #f8faf5; }
    .study-support > summary { cursor: pointer; padding: 7px; font-weight: 700; }
    .study-cards { display: grid; grid-template-columns: repeat(auto-fit,minmax(min(100%,230px),1fr)); gap: 12px; margin-top: 12px; }
    .study-card { min-width: 0; background: white; border: 1px solid #dfe7da; border-radius: 12px; padding: 16px; overflow-wrap: anywhere; }
    .study-card h4 { margin: 0 0 10px; font-size: 16px; }
    .study-card p { line-height: 1.65; margin: 8px 0; }
    #studySupportStatus { min-height: 1.5em; }
    #studyDemo { margin: 18px 0; }
    #studyDemoControls label { flex: 1; min-width: 150px; }
    #studyDemoControls input { width: 100%; }
    #studyCalculation { display: block; font-size: 18px; font-weight: 700; line-height: 1.7; margin: 16px 0; overflow-wrap: anywhere; }
    #studyVisual { display: block; width: 100%; height: auto; background: #edf4e6; border-radius: 12px; }
    #studyVisual[hidden] { display: none; }
    .study-support [hidden] { display: none !important; }
    #studyExports { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
'''

PANEL = r'''
        <details id="studySupport" class="study-support">
          <summary>理解工坊 · 阅读方法与数学演示</summary>
          <p class="chapter-note">跟随当前课本和章节，先观察、再解释、回到教材核对。</p>
          <p id="studySupportStatus" class="chapter-note" role="status"></p>
          <button id="studySupportRetry" type="button" class="secondary" hidden>重新读取</button>
          <div id="studySteps" class="study-cards"></div>
          <section id="studyDemo" hidden><h4 id="studyDemoTitle"></h4><p id="studyDemoHint" class="chapter-note"></p>
            <div id="studyDemoControls" class="row"></div><output id="studyCalculation" aria-live="polite"></output>
            <svg id="studyVisual" viewBox="0 0 700 230" role="img" aria-label="数值关系演示"></svg>
            <p class="chapter-note">改变参数看看关系，不计入作答、难度或成绩。</p>
          </section>
          <div id="studyConcepts" class="study-cards"></div>
          <div id="studyExports"><button id="studyDownload" type="button" class="secondary" disabled>下载学习卡</button>
            <button id="studyDiagram" type="button" class="secondary" disabled>下载关系图文本</button></div>
          <details><summary>参考范围与来源</summary><p class="chapter-note">数学知识卡仅覆盖已核对的局部样本；其他学科目前提供阅读问题串。
            参考 faststudy-knowledge 的教材定位、EduLab 的交互课件形式及 Mermaid / Marp 的文本导出。
            本地编写的内容与演示未经过教师签署，不作为标准答案或掌握证明。图谱相关元数据保留 CC BY-NC-SA 4.0，教材版权归出版社。</p></details>
        </details>
'''

SCRIPT = r'''
    let studyGeneration = 0, studyScopeKey = '', studyData = null, studyBusy = false, studyPageUrls = [];
    const currentStudyKey = () => contextNamespace() + ':' + gameBook + ':' + gameChapter;
    function resetStudySupport(close = true) {
      studyGeneration += 1; studyBusy = false; studyData = null; studyScopeKey = '';
      studyPageUrls.forEach((url) => URL.revokeObjectURL(url)); studyPageUrls = [];
      for (const id of ['studySteps','studyConcepts','studyDemoControls','studyCalculation','studyVisual']) $(id).replaceChildren();
      $('studyDemo').hidden = true; $('studyDownload').disabled = true; $('studyDiagram').disabled = true;
      $('studySupportStatus').textContent = ''; $('studySupportRetry').hidden = true;
      if (close) $('studySupport').open = false;
    }
    function syncStudySupport() {
      if (studyScopeKey === currentStudyKey()) return;
      resetStudySupport(false); studyScopeKey = currentStudyKey();
      if ($('studySupport').open && selectedBook()) loadStudySupport();
    }
    function studyCard(title, text) {
      const card = document.createElement('article'); card.className = 'study-card';
      const heading = document.createElement('h4'); heading.textContent = title;
      const p = document.createElement('p'); p.textContent = text; card.append(heading, p); return card;
    }
    async function loadStudySupport() {
      if (!selectedBook() || studyBusy) return;
      if (studyData && studyScopeKey === currentStudyKey()) return;
      syncStudySupport();
      // sync may start the same scope's load when it observes an open panel.
      if (studyBusy) return;
      const epoch = contextEpoch, key = currentStudyKey(), generation = ++studyGeneration;
      const current = () => epoch === contextEpoch && key === currentStudyKey() && generation === studyGeneration;
      studyBusy = true; $('studySupportStatus').textContent = '正在准备当前范围的学习参考…'; $('studySupportRetry').hidden = true;
      try {
        const query = new URLSearchParams({book_id:gameBook,chapter_id:gameChapter});
        const data = await call('/api/v1/study-support?' + query);
        if (!current()) return;
        if (data.scope?.book_id !== gameBook || data.scope?.chapter_id !== gameChapter) throw new Error('学习范围已变化，请重新读取。');
        studyData = data;
        $('studySupportStatus').textContent = scopeTitle() + (data.mapping_status === 'mapped' ? ' · 数学知识卡为局部样本，供回顾。' : ' · 阅读问题串；本范围暂未建立精确知识与页码映射。');
        $('studySteps').replaceChildren(...(data.study_steps || []).map((step,i) => studyCard((i+1) + '. ' + step.title, step.prompt)));
        for (const node of [...(data.concepts || []), ...(data.prerequisites || [])]) {
          const card = studyCard((node.depth ? '先修参考 · ' : '') + node.title, node.explanation);
          for (const check of node.checks || []) { const p = document.createElement('p'); p.textContent = check; card.append(p); }
          if (!node.pages?.length) { const p = document.createElement('p'); p.className = 'chapter-note'; p.textContent = '本地综合核对点，无教材原页声明。'; card.append(p); }
          for (const page of node.pages || []) {
            if (page.book_id !== gameBook || !Number.isInteger(page.printed_page)) continue;
            const button = document.createElement('button'); button.type = 'button'; button.className = 'secondary';
            button.textContent = '查看本册第 ' + page.printed_page + ' 页';
            button.onclick = async () => {
              if (!current()) return;
              button.disabled = true;
              try {
                const blob = await fetchScoped('/api/v1/textbooks/' + encodeURIComponent(page.book_id) + '/pages/' + page.printed_page + '/image', {}, true);
                if (!current()) return;
                const url = URL.createObjectURL(blob); studyPageUrls.push(url);
                openTextbookZoom(url, {printed_page:page.printed_page,content_title:node.title});
              } catch (error) { if (current() && !(error instanceof StaleContextError)) $('studySupportStatus').textContent = '原页暂时无法打开，请稍后重试。'; }
              finally { if (current()) button.disabled = false; }
            };
            card.append(button);
          }
          $('studyConcepts').append(card);
        }
        renderStudyDemo(data.interactive_template);
        $('studyDownload').disabled = !data.lesson_markdown; $('studyDiagram').disabled = !data.diagram_mermaid;
      } catch (error) {
        if (current() && !(error instanceof StaleContextError)) { $('studySupportStatus').textContent = '学习参考暂时无法读取，请稍后重试。'; $('studySupportRetry').hidden = false; }
      } finally { if (current()) studyBusy = false; }
    }
    function studySvg(name, attrs, text) {
      const node = document.createElementNS('http://www.w3.org/2000/svg', name);
      for (const [key,value] of Object.entries(attrs)) node.setAttribute(key, value);
      if (text !== undefined) node.textContent = text; return node;
    }
    function renderStudyDemo(template) {
      const groups = ['equal_groups_v1','multiplication_groups_v1'].includes(template), numberLine = template === 'signed_number_line_v1';
      $('studyDemo').hidden = !groups && !numberLine;
      if (!groups && !numberLine) return;
      $('studyDemoTitle').textContent = groups ? '把相同的组摆出来' : '在数轴上看加减';
      $('studyDemoHint').textContent = groups ? '比较每组数量、组数与总数的关系。' : '向右是正方向；减去一个数，相当于加上它的相反数。';
      const controls = $('studyDemoControls'); controls.replaceChildren();
      for (const [id,title,min,max,value] of groups ? [['studyEach','每组数量',1,6,3],['studyGroups','组数',1,6,4]] : [['studyStart','起点',-8,8,-3],['studyChange','变化量',-8,8,5]]) {
        const label = document.createElement('label'), input = document.createElement('input'), number = document.createElement('span');
        input.id = id; input.type = 'range'; input.min = min; input.max = max; input.value = value;
        number.id = id + 'Label'; label.append(document.createTextNode(title + '：'),number,input); controls.append(label);
      }
      if (numberLine) { const label = document.createElement('label'), select = document.createElement('select');
        select.id = 'studyOperation'; select.add(new Option('加上变化量','add')); select.add(new Option('减去变化量','subtract'));
        label.append(document.createTextNode('运算'),select); controls.append(label); }
      const draw = () => {
        const svg = $('studyVisual'); svg.replaceChildren();
        if (groups) {
          const each = Number($('studyEach').value), count = Number($('studyGroups').value), total = each * count;
          $('studyEachLabel').textContent = each; $('studyGroupsLabel').textContent = count;
          $('studyCalculation').textContent = `${each} × ${count} = ${total}` + (template === 'multiplication_groups_v1' ? '' : `；${total} ÷ ${count} = ${each}（每组）；${total} ÷ ${each} = ${count}（组数）`);
          for (let group = 0; group < count; group++) {
            const x = 18 + group * 112; svg.append(studySvg('rect',{x,y:20,width:100,height:172,rx:12,fill:'#e0ecd4',stroke:'#83ac81'}));
            for (let i=0; i<each; i++) svg.append(studySvg('circle',{cx:x+28+(i%2)*42,cy:49+Math.floor(i/2)*49,r:14,fill:'#e8ad3e'}));
            svg.append(studySvg('text',{x:x+50,y:216,'text-anchor':'middle',fill:'#28533d','font-size':17},`第${group+1}组`));
          }
        } else {
          const start = Number($('studyStart').value), change = Number($('studyChange').value), subtract = $('studyOperation').value === 'subtract';
          const delta = subtract ? -change : change, end = start + delta, x = (number) => 350 + number * 15;
          $('studyStartLabel').textContent = start; $('studyChangeLabel').textContent = change;
          $('studyCalculation').textContent = `${start} ${subtract?'−':'+'} (${change}) = ${end}；从 ${start} ${delta>=0?'向右':'向左'}移动 ${Math.abs(delta)} 格`;
          svg.append(studySvg('line',{x1:40,y1:145,x2:660,y2:145,stroke:'#486455','stroke-width':2}));
          for (let i=-20; i<=20; i++) { svg.append(studySvg('line',{x1:x(i),y1:139,x2:x(i),y2:151,stroke:'#799380'}));
            if (i%5===0) svg.append(studySvg('text',{x:x(i),y:179,'text-anchor':'middle',fill:'#345643'},i)); }
          svg.append(studySvg('line',{x1:x(start),y1:90,x2:x(end),y2:90,stroke:'#d99020','stroke-width':5}));
          svg.append(studySvg('circle',{cx:x(start),cy:145,r:7,fill:'#287153'}));
          svg.append(studySvg('circle',{cx:x(end),cy:90,r:9,fill:'#dc9828'}));
          svg.append(studySvg('text',{x:x(end),y:64,'text-anchor':'middle',fill:'#9b610b','font-size':19},`结果 ${end}`));
        }
      };
      controls.querySelectorAll('input,select').forEach((input) => { input.oninput = draw; }); draw();
    }
    function downloadStudyArtifact(field, extension) {
      if (!studyData || studyScopeKey !== currentStudyKey() || typeof studyData[field] !== 'string') return;
      const url = URL.createObjectURL(new Blob([studyData[field]],{type:'text/plain;charset=utf-8'}));
      const link = document.createElement('a'); link.href = url; link.download = gameBook + '-' + (gameChapter || 'all') + extension;
      link.click(); setTimeout(() => URL.revokeObjectURL(url),1000);
    }
    $('studySupport').ontoggle = () => { if ($('studySupport').open && !studyData) loadStudySupport(); };
    $('studySupportOpen').onclick = () => { $('studySupport').open = true; loadStudySupport(); $('studySupport').scrollIntoView({block:'start'}); };
    $('studySupportRetry').onclick = () => { resetStudySupport(false); studyScopeKey = currentStudyKey(); loadStudySupport(); };
    $('studyDownload').onclick = () => downloadStudyArtifact('lesson_markdown','.md');
    $('studyDiagram').onclick = () => downloadStudyArtifact('diagram_mermaid','.mmd');
'''
