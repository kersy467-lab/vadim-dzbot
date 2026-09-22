(function () {
  'use strict';
  let words = [], index = 0, total = 10, correct = 0, mistakes = [], answered = false, selected = '';
  const vowels = 'аеёиоуыэюя';
  const shuffle = (list) => [...list].sort(() => Math.random() - 0.5);
  const escape = (value) => String(value || '').replace(/[&<>"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[char]));
  function question(word) {
    const options = [...new Set([...word].filter(letter => vowels.includes(letter.toLowerCase())))] || ['а'];
    const position = [...word].map((letter, i) => vowels.includes(letter.toLowerCase()) ? i : -1).filter(i => i >= 0);
    const hiddenAt = position[Math.floor(Math.random() * position.length)];
    return { word, hiddenAt, answer: word[hiddenAt], options: shuffle([...new Set([word[hiddenAt], ...'аеёиоуыэюя'.split('').sort(() => Math.random() - .5).slice(0, 3)])]) };
  }
  function renderQuizTab() {
    if (!words.length) return renderSetup();
    if (index >= words.length) return renderResult();
    return renderQuestion();
  }
  function renderSetup() {
    const count = (window.EGE_VOCAB_DATA || []).length;
    return `<div class="theme-card rounded-3xl p-5 bg-white dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700 shadow-sm space-y-4 text-center">
      <div class="text-3xl">📝</div><h3 class="text-sm font-black text-slate-900 dark:text-white">Словарные слова · задание 9</h3>
      <p class="text-xs text-slate-500">Вставьте пропущенную безударную гласную в слове из списка ФИПИ 2026.</p>
      <div class="grid grid-cols-4 gap-2">${[10,25,50,count].map(value => `<button onclick="window.EGE.vocabSetTotal(${value})" class="py-2 rounded-xl text-xs font-bold ${total === value ? 'bg-blue-600 text-white' : 'bg-slate-100 dark:bg-slate-700'}">${value === count ? 'Все' : value}</button>`).join('')}</div>
      <button onclick="window.EGE.vocabStart()" class="w-full py-3 rounded-2xl bg-blue-600 text-white font-bold">Начать тренировку</button></div>`;
  }
  function renderQuestion() {
    const item = words[index]; const q = item.q;
    const masked = q.word.split('').map((letter, i) => i === q.hiddenAt ? '<span class="inline-flex w-9 h-10 items-center justify-center rounded-xl bg-blue-100 text-blue-800 font-black">_</span>' : `<span>${escape(letter)}</span>`).join('');
    return `<div class="theme-card rounded-3xl p-5 bg-white dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700 shadow-sm space-y-5 text-center">
      <div class="flex justify-between text-xs font-bold text-slate-500"><span>${index + 1} / ${words.length}</span><span class="text-emerald-600">✓ ${correct}</span></div>
      <div class="h-2 rounded-full bg-slate-100 overflow-hidden"><div class="h-full bg-blue-600" style="width:${(index / words.length) * 100}%"></div></div>
      <p class="text-xs uppercase tracking-wide text-slate-400">Вставьте букву</p><div class="text-3xl font-black tracking-wider text-slate-900 dark:text-white">${masked}</div>
      <div class="grid grid-cols-4 gap-2">${q.options.map(letter => `<button ${answered ? 'disabled' : ''} onclick="window.EGE.vocabAnswer('${letter}')" class="py-3 rounded-2xl font-black text-lg ${answered && letter === q.answer ? 'bg-emerald-500 text-white' : answered && letter === selected ? 'bg-rose-500 text-white' : 'bg-slate-100 dark:bg-slate-700 text-slate-800 dark:text-white'}">${letter}</button>`).join('')}</div>
      ${answered ? `<div class="text-xs ${selected === q.answer ? 'text-emerald-600' : 'text-rose-500'} font-bold">${selected === q.answer ? 'Верно!' : `Ошибка. Правильно: ${q.word}`}</div><button onclick="window.EGE.vocabNext()" class="w-full py-3 rounded-2xl bg-blue-600 text-white font-bold">Дальше</button>` : ''}</div>`;
  }
  function renderResult() { return `<div class="theme-card rounded-3xl p-6 text-center space-y-3"><div class="text-4xl">${correct === words.length ? '🏆' : '📚'}</div><h3 class="font-black">Тренировка завершена</h3><p class="text-sm">${correct} из ${words.length} верно</p>${mistakes.length ? `<p class="text-xs text-rose-500">Ошибки: ${mistakes.map(escape).join(', ')}</p>` : ''}<button onclick="window.EGE.vocabReset()" class="w-full py-3 rounded-2xl bg-blue-600 text-white font-bold">Новая тренировка</button></div>`; }
  function renderDictTab() { const all = window.EGE_VOCAB_DATA || []; return `<div class="theme-card rounded-2xl p-3"><p class="text-xs text-slate-500 mb-2">Словарные слова ФИПИ: ${all.length}</p><div class="grid grid-cols-2 gap-1.5 max-h-[55vh] overflow-y-auto">${all.map(word => `<div class="rounded-xl bg-slate-50 dark:bg-slate-800 p-2 text-xs font-bold">${escape(word)}</div>`).join('')}</div></div>`; }
  function rerender() { const root = document.getElementById('ege-subtab-container'); if (root) root.innerHTML = renderQuizTab(); }
  function start() { words = shuffle(window.EGE_VOCAB_DATA || []).slice(0, total).map(word => ({ q: question(word) })); index = correct = 0; mistakes = []; answered = false; rerender(); }
  function answer(letter) { if (answered) return; answered = true; selected = letter; const item = words[index]; if (letter === item.q.answer) correct++; else mistakes.push(item.q.word); rerender(); }
  window.EGE_VOCAB = { renderQuizTab, renderDictTab, vocabSetTotal: value => { total = value; rerender(); }, vocabStart: start, vocabAnswer: answer, vocabNext: () => { index++; answered = false; rerender(); }, vocabReset: () => { words = []; rerender(); } };
})();
