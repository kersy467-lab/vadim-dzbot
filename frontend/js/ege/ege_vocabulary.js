(function () {
  'use strict';
  let words = [], index = 0, total = 10, correct = 0, mistakes = [], answered = false, submitted = '';
  const vowels = /[аеёиоуыэюя]/gi;
  function shuffle(arr) {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }
  const escape = value => String(value || '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const normal = value => String(value || '').trim().toLowerCase().replace(/ё/g, 'е').replace(/\s+/g, '');
  const masked = word => word.replace(vowels, '_');

  function renderQuizTab() { return !words.length ? renderSetup() : (index >= words.length ? renderResult() : renderQuestion()); }
  function renderSetup() {
    const count = (window.EGE_VOCAB_DATA || []).length;
    return `<div class="theme-card rounded-3xl p-5 bg-white dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700 shadow-sm space-y-4 text-center">
      <div class="text-3xl">📝</div><h3 class="text-sm font-black text-slate-900 dark:text-white">Словарные слова · задание 9</h3>
      <p class="text-xs text-slate-500">Все гласные скрыты. Впишите слово полностью так, как оно пишется.</p>
      <div class="grid grid-cols-4 gap-2">${[10,25,50,count].map(value => `<button onclick="window.EGE.vocabSetTotal(${value})" class="py-2 rounded-xl text-xs font-bold ${total === value ? 'bg-blue-600 text-white' : 'bg-slate-100 dark:bg-slate-700'}">${value === count ? 'Все' : value}</button>`).join('')}</div>
      <button onclick="window.EGE.vocabStart()" class="w-full py-3 rounded-2xl bg-blue-600 text-white font-bold">Начать тренировку</button></div>`;
  }
  function renderQuestion() {
    const word = words[index]; const right = normal(submitted) === normal(word);
    return `<div class="theme-card rounded-3xl p-5 bg-white dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700 shadow-sm space-y-5 text-center">
      <div class="flex justify-between text-xs font-bold text-slate-500"><span>${index + 1} / ${words.length}</span><span class="text-emerald-600">✓ ${correct}</span></div>
      <div class="h-2 rounded-full bg-slate-100 overflow-hidden"><div class="h-full bg-blue-600" style="width:${(index / words.length) * 100}%"></div></div>
      <p class="text-xs uppercase tracking-wide text-slate-400">Впишите словарное слово полностью</p>
      <div class="text-3xl font-black tracking-[0.18em] text-slate-900 dark:text-white break-all">${escape(masked(word))}</div>
      <input id="ege-vocab-input" ${answered ? 'disabled' : ''} value="${escape(submitted)}" autocomplete="off" autocapitalize="none" onkeydown="if(event.key==='Enter') window.EGE.vocabCheck()" placeholder="Напишите слово" class="w-full px-4 py-3 rounded-2xl border border-slate-200 dark:border-slate-600 bg-slate-50 dark:bg-slate-700 text-center font-bold text-lg text-slate-900 dark:text-white outline-none focus:ring-2 focus:ring-blue-500">
      ${answered ? `<div class="text-xs ${right ? 'text-emerald-600' : 'text-rose-500'} font-bold">${right ? 'Верно!' : `Правильно: ${escape(word)}`}</div><button onclick="window.EGE.vocabNext()" class="w-full py-3 rounded-2xl bg-blue-600 text-white font-bold">Дальше</button>` : '<button onclick="window.EGE.vocabCheck()" class="w-full py-3 rounded-2xl bg-blue-600 text-white font-bold">Проверить</button>'}</div>`;
  }
  function renderResult() { return `<div class="theme-card rounded-3xl p-6 text-center space-y-3"><div class="text-4xl">${correct === words.length ? '🏆' : '📚'}</div><h3 class="font-black">Тренировка завершена</h3><p class="text-sm">${correct} из ${words.length} верно</p>${mistakes.length ? `<p class="text-xs text-rose-500">Ошибки: ${mistakes.map(escape).join(', ')}</p>` : ''}<button onclick="window.EGE.vocabReset()" class="w-full py-3 rounded-2xl bg-blue-600 text-white font-bold">Новая тренировка</button></div>`; }
  function renderDictTab() { const all = window.EGE_VOCAB_DATA || []; return `<div class="theme-card rounded-2xl p-3"><p class="text-xs text-slate-500 mb-2">Словарные слова ФИПИ: ${all.length}</p><div class="grid grid-cols-2 gap-1.5 max-h-[55vh] overflow-y-auto">${all.map(word => `<div class="rounded-xl bg-slate-50 dark:bg-slate-800 p-2 text-xs font-bold">${escape(word)}</div>`).join('')}</div></div>`; }
  function rerender() { const root = document.getElementById('ege-subtab-container'); if (root) root.innerHTML = renderQuizTab(); }
  function start() {
    const seen = new Set();
    const uniquePool = [];
    for (const w of (window.EGE_VOCAB_DATA || [])) {
      const k = normal(w);
      if (k && !seen.has(k)) {
        seen.add(k);
        uniquePool.push(w);
      }
    }
    words = shuffle(uniquePool).slice(0, total);
    index = correct = 0;
    mistakes = [];
    answered = false;
    submitted = '';
    rerender();
  }
  function check() { if (answered) return; submitted = document.getElementById('ege-vocab-input')?.value || ''; answered = true; if (normal(submitted) === normal(words[index])) correct++; else mistakes.push(words[index]); rerender(); }
  function next() { index++; answered = false; submitted = ''; rerender(); }
  function reset() { words = []; rerender(); }
  window.EGE_VOCAB = { renderQuizTab, renderDictTab, vocabSetTotal: value => { total = value; rerender(); }, vocabStart: start, vocabCheck: check, vocabNext: next, vocabReset: reset, maskWord: masked };
})();
