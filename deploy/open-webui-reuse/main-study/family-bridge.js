/* Same-origin book/chapter selection bridge for the deployed family workbench.
 * Only book/chapter IDs and a timestamp are shared, scoped by the workbench's
 * authenticated account + learner + revision. Never reads answers or tokens.
 * Server authorization remains mandatory in the main study client.
 */
(() => {
  'use strict';
  if (location.pathname !== '/learning/ui' || window.__ddFamilyBridgeLoaded) return;
  window.__ddFamilyBridgeLoaded = true;
  let queued = false, lastKey = '', lastValue = '', handledLink = '';
  const prefix = 'dd-study-family-scope-v1:';
  function pulse() { localStorage.setItem('dd-study-family-pulse-v1', String(Date.now()) + Math.random()); }
  function update() {
    queued = false;
    // The existing workbench exposes these lexical functions after its inline
    // script initializes. Fail closed if a future version changes the contract.
    if (typeof contextNamespace !== 'function' || typeof contextVersion === 'undefined') return;
    const main = document.querySelector('main'), learner = document.getElementById('learner');
    const book = document.getElementById('textbookBook'), chapter = document.getElementById('textbookChapter');
    if (!main || main.inert || !learner?.value || !book?.value) {
      if (lastKey) { try { localStorage.removeItem(lastKey); pulse(); } catch (_) {} lastKey = ''; lastValue = ''; }
      return;
    }
    if (book.disabled || chapter.disabled) return;
    const key = prefix + contextNamespace();
    const value = JSON.stringify({bookId: book.value, chapterId: chapter.value});
    if (key !== lastKey || value !== lastValue) {
      try {
        if (lastKey && key !== lastKey) localStorage.removeItem(lastKey);
        localStorage.setItem(key, JSON.stringify({...JSON.parse(value), updatedAt: Date.now()}));
        if (key !== lastKey) pulse();
      } catch (_) {} // Storage-disabled browsers retain independent reading.
      lastKey = key; lastValue = value;
    }
    const params = new URLSearchParams(location.hash.slice(1));
    const linkKey = location.hash + '|' + contextNamespace();
    if (handledLink === linkKey) return;
    handledLink = linkKey;
    document.getElementById('dd-family-continue')?.remove();
    if (!params.has('studyBook')) return;
    const targetBook = params.get('studyBook'), targetChapter = params.get('studyChapter') || '';
    const targetQuestion = params.get('studyQuestion') || '';
    const targetEvidence = params.get('studyEvidence') || '';
    if (targetEvidence && (!/^dd-excerpt-[a-f0-9]{64}$/.test(targetEvidence) || targetQuestion)) return;
    const targetPage = params.has('studyPage') ? Number(params.get('studyPage')) : null;
    const revision = params.get('studyRevision');
    const namespace = contextNamespace();
    if (!/^[a-z0-9-]{1,80}$/.test(targetBook) || !/^[a-z0-9_-]{0,80}$/.test(targetChapter) || !/^[A-Za-z0-9_-]{0,128}$/.test(targetQuestion)) return;
    const banner = document.createElement('div'); banner.id = 'dd-family-continue';
    banner.style.cssText = 'grid-column:1/-1;margin:12px 0;padding:14px;border:1px solid #86bda8;border-radius:12px;background:#f2fbf7;color:#164532';
    const text = document.createElement('p');
    if (revision !== String(contextVersion)) {
      text.textContent = '家庭档案已变化，请返回学科伴学同步后，再打开对应课本。'; banner.append(text);
    } else if (targetQuestion) {
      // Only public, installed practice metadata from this profile's existing
      // catalogue can resolve a link. Hash values never supply content/answers.
      const findChoice = () => typeof gameCatalog !== 'undefined' ? gameCatalog.find(c => c.question_version_id === targetQuestion &&
        c.practice && c.textbook_scope?.book_id === targetBook && c.textbook_scope.chapter_id === targetChapter) : null;
      const choice = findChoice();
      if (!choice) {
        text.textContent = '这道题不在当前档案的所选教材章节中，请返回学科伴学重新选择。'; banner.append(text);
      } else {
        text.textContent = '从知识路线继续：' + choice.practice.title + ' · ' + (typeof difficultyNames !== 'undefined' ? difficultyNames[choice.practice.difficulty] : '关联练习');
        const button = document.createElement('button'); button.type = 'button'; button.textContent = '开始这道关联题';
        const valid = () => revision === String(contextVersion) && namespace === contextNamespace() && !main.inert;
        button.onclick = async () => {
          if (!valid() || typeof selectLearningScope !== 'function' || typeof launchGameChoice !== 'function' || !findChoice()) {
            text.textContent = '档案已变化，请返回学科伴学同步。'; button.disabled = true; return;
          }
          button.disabled = true;
          try {
            await selectLearningScope(targetBook, targetChapter);
            // A cancelled scope change must never start the linked question.
            if (!valid() || gameBook !== targetBook || gameChapter !== targetChapter) return;
            await launchGameChoice(findChoice());
          } finally { button.disabled = !valid(); }
        };
        banner.append(text, button);
      }
    } else if (targetPage !== null) {
      const target = typeof textbookBooks !== 'undefined' ? textbookBooks.find(b => b.id === targetBook) : null;
      const chapters = target?.chapters.filter(c => !targetChapter || c.id === targetChapter) || [];
      const validPage = Number.isInteger(targetPage) && chapters.some(c => targetPage >= c.printed_page && targetPage <= c.printed_page + c.page_end - c.page_start);
      if (!validPage) {
        text.textContent = '这条原页引用不在当前档案的课本范围内，请重新检索。'; banner.append(text);
      } else {
        text.textContent = '聊天原页核对：' + target.title + ' · 第 ' + targetPage + ' 页';
        const button = document.createElement('button'); button.type = 'button'; button.textContent = '查看引用的第 ' + targetPage + ' 页';
        const valid = () => revision === String(contextVersion) && namespace === contextNamespace() && !main.inert;
        button.onclick = async () => {
          if (!valid()) { button.disabled = true; text.textContent = '档案已变化，请返回聊天重新查询。'; return; }
          button.disabled = true;
          try {
            await selectLearningScope(targetBook, targetChapter);
            if (!valid() || gameBook !== targetBook || gameChapter !== targetChapter) return;
            setGameView('home'); document.getElementById('textbookReader').open = true;
            document.getElementById('textbookQuery').value = '';
            if (targetEvidence) {
              if (typeof openReaderEvidence !== 'function') { text.textContent = '当前工作台不支持核验这条片段，请重新查询。'; return; }
              await openReaderEvidence(targetBook, targetChapter, targetEvidence, targetPage);
            } else await loadTextbookResults(targetPage - readerRange().start);
            document.getElementById('textbookReader').scrollIntoView({block: 'start'});
          } finally { button.disabled = !valid(); }
        };
        banner.append(text, button);
      }
    } else {
      text.textContent = '从学科伴学继续：可以打开刚才选择的教材范围。';
      const button = document.createElement('button'); button.type = 'button'; button.textContent = '打开伴学所选章节';
      button.onclick = async () => {
        if (revision !== String(contextVersion) || namespace !== contextNamespace() || main.inert || typeof selectLearningScope !== 'function') {
          text.textContent = '档案已变化，请先返回学科伴学同步。'; button.disabled = true; return;
        }
        // The original handler validates available books and asks before skipping
        // any unfinished exercise. Never bypass or force that confirmation.
        await selectLearningScope(targetBook, targetChapter, true);
      };
      banner.append(text, button);
    }
    // Keep the invitation visible even when a saved exercise opens Practice.
    main.prepend(banner);
  }
  function schedule() { if (!queued) { queued = true; setTimeout(update, 120); } }
  function start() {
    new MutationObserver(schedule).observe(document.body, {childList: true, subtree: true, attributes: true, attributeFilter: ['disabled', 'inert']});
    document.addEventListener('change', schedule); window.addEventListener('pageshow', schedule);
    window.addEventListener('hashchange', schedule);
    document.addEventListener('visibilitychange', schedule); schedule();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true}); else start();
})();
