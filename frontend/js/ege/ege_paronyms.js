// Module: EGE_PARONYMS
(function () {
  'use strict';

  function shuffleArray(arr) {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  let paronymLetterFilter = "Все";
  let paronymSearchQuery = "";
  let pQuizTotal = 10;
  let pQuizQuestions = [];
  let pQuizIndex = 0;
  let pQuizAnswered = false;
  let pQuizCorrectCount = 0;
  let pQuizMistakes = [];
  let lastPSelectedWord = null;
  let lastPAnswerCorrect = false;

// РАЗДЕЛ ЗАДАНИЯ 5: ПАРОНИМЫ (СЛОВАРЬ + ТРЕНАЖЕР)
  // ==============================================================================

  function renderParonymsDictTab() {
    const pData = window.PARONYMS_DATA || { groups: [], letters: [] };
    const query = paronymSearchQuery.toLowerCase().trim();

    const filtered = pData.groups.filter(g => {
      if (paronymLetterFilter !== "Все" && g.letter !== paronymLetterFilter) {
        return false;
      }
      if (query) {
        const inTitle = g.title.toLowerCase().includes(query);
        const inWords = g.words.some(w => 
          w.word.toLowerCase().includes(query) || 
          w.meaning.toLowerCase().includes(query) ||
          w.examples.some(ex => ex.toLowerCase().includes(query))
        );
        return inTitle || inWords;
      }
      return true;
    });

    return `
      <div class="space-y-3">
        <!-- Search bar -->
        <div class="relative">
          <input
            type="text"
            value="${paronymSearchQuery}"
            oninput="window.EGE.onParonymSearch(this.value)"
            placeholder="Поиск паронима, толкования или примера..."
            class="w-full px-3.5 py-2.5 pl-9 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all shadow-sm"
          />
          <span class="absolute left-3 top-2.5 text-slate-400 text-xs">🔍</span>
          ${paronymSearchQuery ? `
            <button onclick="window.EGE.onParonymSearch('')" class="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600 text-xs font-bold">✕</button>
          ` : ''}
        </div>

        <!-- Alphabet Pills -->
        <div class="flex items-center gap-1 overflow-x-auto pb-1 no-scrollbar text-[11px] font-bold">
          ${(pData.letters || []).map(l => `
            <button onclick="window.EGE.setPLetterFilter('${l}')" class="px-2.5 py-1 rounded-lg whitespace-nowrap transition-all ${
              paronymLetterFilter === l
                ? 'bg-blue-600 text-white shadow-sm shadow-blue-500/20'
                : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200/80 dark:border-slate-700'
            }">
              ${l}
            </button>
          `).join('')}
        </div>

        <!-- Group Count and Note -->
        <div class="flex items-center justify-between text-[11px] text-slate-400 px-1">
          <span>Найдено групп: <b>${filtered.length}</b> из ${pData.groups.length}</span>
          <span class="text-indigo-600 dark:text-indigo-400 font-bold">ФИПИ 2026</span>
        </div>

        <!-- Groups Cards List -->
        <div class="space-y-2.5 max-h-[60vh] overflow-y-auto pr-1">
          ${filtered.length === 0 ? `
            <div class="text-center py-10 theme-card rounded-2xl p-6 text-slate-400 text-xs space-y-2">
              <span class="text-3xl">🔍</span>
              <p>По запросу «${paronymSearchQuery}» ничего не найдено</p>
            </div>
          ` : filtered.map(g => `
            <div class="theme-card rounded-2xl p-3.5 bg-white dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700 shadow-sm space-y-3">
              <!-- Group Title Header -->
              <div class="flex items-center justify-between border-b border-slate-100 dark:border-slate-700/60 pb-2">
                <h3 class="text-xs font-black text-slate-900 dark:text-white flex items-center gap-1.5">
                  <span class="w-5 h-5 rounded-md bg-blue-100 dark:bg-blue-950 text-blue-600 dark:text-blue-400 text-[10px] font-extrabold flex items-center justify-center">${g.letter}</span>
                  <span>${g.title}</span>
                </h3>
                <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-300">
                  ${g.words.length === 2 ? 'пара' : `${g.words.length} слова`}
                </span>
              </div>

              <!-- Words Meanings & Examples -->
              <div class="space-y-2">
                ${g.words.map(w => `
                  <div class="p-2.5 rounded-xl bg-slate-50/80 dark:bg-slate-700/30 border border-slate-100 dark:border-slate-700/40 space-y-1">
                    <div class="flex items-center gap-2">
                      <span class="text-xs font-black text-blue-600 dark:text-blue-400 capitalize tracking-wide">${w.word}</span>
                    </div>
                    <p class="text-[11px] text-slate-700 dark:text-slate-300 leading-relaxed font-medium">${w.meaning}</p>
                    <div class="pt-1 flex items-center flex-wrap gap-1">
                      <span class="text-[10px] font-bold text-slate-400">Примеры:</span>
                      ${w.examples.map(ex => `
                        <span class="text-[10px] px-2 py-0.5 rounded-md bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200/60 dark:border-slate-700 font-medium italic">
                          ${ex}
                        </span>
                      `).join('')}
                    </div>
                  </div>
                `).join('')}
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  function renderParonymsQuizTab() {
    if (pQuizQuestions.length === 0) {
      return renderPQuizSetup();
    }
    if (pQuizIndex >= pQuizQuestions.length) {
      return renderPQuizResults();
    }
    return renderPQuizQuestion();
  }

  function renderPQuizSetup() {
    const pData = window.PARONYMS_DATA || { questions: [] };
    const storedMistakes = getStoredPMistakes();
    const totalAvailable = pData.questions.length;

    return `
      <div class="theme-card rounded-3xl p-5 bg-white dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700 shadow-sm space-y-4">
        <div class="text-center space-y-1.5">
          <div class="w-12 h-12 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-600 text-white text-2xl flex items-center justify-center mx-auto shadow-md shadow-blue-500/25">
            🎯
          </div>
          <h3 class="text-sm font-black text-slate-900 dark:text-white">Тренажер: Паронимы (Задание 5)</h3>
          <p class="text-xs text-slate-500 dark:text-slate-400 leading-relaxed max-w-xs mx-auto">
            Отрабатывай лексическое значение и сочетаемость паронимов в реальных предложениях формата КИМ ЕГЭ.
          </p>
        </div>

        <!-- Question count selection -->
        <div class="space-y-2">
          <span class="text-[11px] font-bold uppercase tracking-wider text-slate-400">Количество вопросов:</span>
          <div class="grid grid-cols-4 gap-1.5">
            ${[10, 25, 50, 'all'].map(cnt => {
              const label = cnt === 'all' ? `Все (${totalAvailable})` : cnt;
              const isSelected = (pQuizTotal === cnt || (cnt === 'all' && pQuizTotal === totalAvailable));
              return `
                <button onclick="window.EGE.setPQuizTotal(${cnt === 'all' ? totalAvailable : cnt})" class="py-2.5 rounded-xl font-bold text-xs transition-all ${
                  isSelected
                    ? 'bg-blue-600 text-white shadow-sm shadow-blue-500/25 ring-2 ring-blue-400'
                    : 'bg-slate-100 dark:bg-slate-700/60 text-slate-600 dark:text-slate-300 hover:bg-slate-200'
                }">
                  ${label}
                </button>
              `;
            }).join('')}
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="space-y-2 pt-2">
          <button onclick="window.EGE.startPQuiz(false)" class="w-full py-3.5 rounded-2xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 active:scale-[0.98] text-white font-extrabold text-sm shadow-lg shadow-blue-500/25 transition-all flex items-center justify-center gap-2">
            <span>🚀 Начать тренировку</span>
          </button>

          ${storedMistakes.length > 0 ? `
            <button onclick="window.EGE.startPMistakesQuiz()" class="w-full py-2.5 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 text-amber-700 dark:text-amber-300 font-bold text-xs hover:bg-amber-100 transition-all flex items-center justify-center gap-2">
              <span>⚠️ Повторить ошибки (${storedMistakes.length})</span>
            </button>
          ` : ''}
        </div>
      </div>
    `;
  }

  function renderPQuizQuestion() {
    const current = pQuizQuestions[pQuizIndex];
    if (!current) return renderPQuizResults();

    const progressPercent = Math.round(((pQuizIndex + (pQuizAnswered ? 1 : 0)) / pQuizQuestions.length) * 100);

    // Format sentence: replace _____ with a highlighted placeholder
    const formattedSentence = current.sentence.replace(
      "_____",
      `<span class="inline-block px-3 py-0.5 rounded-lg bg-blue-100 dark:bg-blue-900/60 text-blue-700 dark:text-blue-300 font-black border border-blue-200 dark:border-blue-700 mx-1 shadow-sm">[ ? ]</span>`
    );

    return `
      <div class="theme-card rounded-3xl p-5 bg-white dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700 shadow-sm space-y-4">
        <!-- Progress Header -->
        <div class="space-y-1.5">
          <div class="flex items-center justify-between text-xs">
            <span class="font-bold text-slate-500 dark:text-slate-400">Вопрос ${pQuizIndex + 1} из ${pQuizQuestions.length}</span>
            <div class="flex items-center gap-1.5">
              <span class="text-emerald-600 font-bold">✓ ${pQuizCorrectCount}</span>
              <span class="text-rose-500 font-bold">✗ ${pQuizMistakes.length}</span>
              <button onclick="window.EGE.resetPQuiz()" class="text-slate-400 hover:text-slate-600 ml-1 text-xs">✕ Выйти</button>
            </div>
          </div>
          <div class="w-full h-2 rounded-full bg-slate-100 dark:bg-slate-700 overflow-hidden">
            <div class="h-full bg-blue-600 rounded-full transition-all duration-300" style="width: ${progressPercent}%"></div>
          </div>
        </div>

        <!-- Question Prompt -->
        <div class="text-center space-y-1">
          <span class="text-[11px] font-bold uppercase tracking-wider text-slate-400">Вставьте подходящий пароним:</span>
        </div>

        <!-- Sentence Card -->
        <div class="p-4 rounded-2xl bg-slate-50 dark:bg-slate-900/50 border border-slate-200/70 dark:border-slate-700 text-center">
          <p class="text-sm font-medium text-slate-800 dark:text-slate-100 leading-relaxed">
            «${formattedSentence}»
          </p>
        </div>

        <!-- Paronym Options Buttons -->
        <div class="grid grid-cols-1 gap-2 pt-1">
          ${current.options.map(opt => {
            const isCorrect = opt.toLowerCase() === current.correct.toLowerCase();
            const isSelected = lastPSelectedWord && opt.toLowerCase() === lastPSelectedWord.toLowerCase();

            let btnClass = "bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 border-slate-200/90 dark:border-slate-700 hover:border-blue-500 hover:bg-blue-50/40 cursor-pointer active:scale-[0.98]";
            if (pQuizAnswered) {
              if (isCorrect) {
                btnClass = "bg-emerald-500 text-white border-emerald-600 font-black shadow-md shadow-emerald-500/25 ring-2 ring-emerald-400";
              } else if (isSelected) {
                btnClass = "bg-rose-500 text-white border-rose-600 font-black ring-2 ring-rose-400 animate-shake";
              } else {
                btnClass = "bg-slate-100 dark:bg-slate-800/60 text-slate-400 opacity-50 border-slate-200 dark:border-slate-700 cursor-default";
              }
            }

            return `
              <button
                ${pQuizAnswered ? 'disabled' : ''}
                onclick="window.EGE.answerPQuestion('${opt}')"
                class="w-full py-3 px-4 rounded-2xl border-2 text-xs font-bold transition-all flex items-center justify-between ${btnClass}">
                <span class="capitalize text-sm font-extrabold">${opt}</span>
                ${pQuizAnswered && isCorrect ? '<span>✓</span>' : ''}
                ${pQuizAnswered && isSelected && !isCorrect ? '<span>✗</span>' : ''}
              </button>
            `;
          }).join('')}
        </div>

        <!-- Feedback & Explanations -->
        ${pQuizAnswered ? `
          <div class="p-3.5 rounded-2xl ${lastPAnswerCorrect ? 'bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-900/40 text-emerald-800 dark:text-emerald-300' : 'bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900/40 text-rose-800 dark:text-rose-300'} text-xs space-y-1.5 transition-all">
            <div class="flex items-center gap-2 font-bold text-sm">
              <span>${lastPAnswerCorrect ? '🎉 Верно!' : '❌ Ошибка!'}</span>
              <span>Правильно: <u class="capitalize font-black">${current.correct}</u></span>
            </div>
            <p class="text-[11px] opacity-90 leading-relaxed font-medium">${current.explanation}</p>
          </div>

          <button onclick="window.EGE.nextPQuestion()" class="w-full py-3 rounded-2xl bg-blue-600 hover:bg-blue-700 active:scale-[0.98] text-white font-extrabold text-sm shadow-md shadow-blue-500/25 transition-all flex items-center justify-center gap-2">
            <span>Дальше ➜</span>
          </button>
        ` : `
          <div class="text-center text-[11px] text-slate-400">
            Нажмите на верный вариант, чтобы проверить свой ответ
          </div>
        `}
      </div>
    `;
  }

  function renderPQuizResults() {
    const total = pQuizQuestions.length;
    const percent = Math.round((pQuizCorrectCount / total) * 100);
    const hasMistakes = pQuizMistakes.length > 0;

    // Save mistakes to localStorage
    savePMistakes(pQuizMistakes);

    return `
      <div class="theme-card rounded-3xl p-6 bg-white dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700 shadow-sm text-center space-y-5">
        <div class="w-16 h-16 mx-auto rounded-3xl bg-gradient-to-tr ${percent >= 80 ? 'from-emerald-500 to-teal-500 shadow-emerald-500/25' : percent >= 50 ? 'from-amber-500 to-yellow-500 shadow-amber-500/25' : 'from-rose-500 to-orange-500 shadow-rose-500/25'} text-white text-3xl flex items-center justify-center shadow-lg">
          ${percent >= 80 ? '🏆' : percent >= 50 ? '👍' : '💪'}
        </div>

        <div class="space-y-1">
          <h3 class="text-lg font-black text-slate-900 dark:text-white">Тренировка завершена!</h3>
          <p class="text-xs text-slate-400">Результат: ${pQuizCorrectCount} из ${total} верных (${percent}%)</p>
        </div>

        <!-- Mistakes breakdown if any -->
        ${hasMistakes ? `
          <div class="text-left space-y-2 pt-2 border-t border-slate-100 dark:border-slate-700">
            <span class="text-xs font-bold text-rose-500">Вопросы с ошибками (${pQuizMistakes.length}):</span>
            <div class="space-y-2 max-h-48 overflow-y-auto pr-1">
              ${pQuizMistakes.map(m => `
                <div class="p-2.5 rounded-xl bg-rose-50/70 dark:bg-rose-950/20 border border-rose-100 dark:border-rose-900/40 text-xs space-y-1">
                  <p class="text-[11px] text-slate-700 dark:text-slate-300 font-medium">«${m.sentence}»</p>
                  <p class="text-[11px] font-bold text-emerald-600">Верный ответ: ${m.correct}</p>
                </div>
              `).join('')}
            </div>
          </div>
        ` : `
          <div class="p-3 rounded-2xl bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300 text-xs font-bold">
            🌟 Отличный результат! Ни одной ошибки в паронимах!
          </div>
        `}

        <div class="space-y-2 pt-2">
          ${hasMistakes ? `
            <button onclick="window.EGE.startPMistakesQuiz()" class="w-full py-3 rounded-2xl bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 active:scale-[0.98] text-white font-extrabold text-xs shadow-md shadow-amber-500/25 transition-all flex items-center justify-center gap-2">
              <span>🔄 Отработать только ошибки (${pQuizMistakes.length})</span>
            </button>
          ` : ''}

          <button onclick="window.EGE.resetPQuiz()" class="w-full py-3 rounded-2xl bg-blue-600 hover:bg-blue-700 active:scale-[0.98] text-white font-extrabold text-xs shadow-md shadow-blue-500/25 transition-all">
            <span>🎯 Начать новую тренировку</span>
          </button>
        </div>
      </div>
    `;
  }

  function setPLetterFilter(letter) {
    paronymLetterFilter = letter;
    if (window.Telegram?.WebApp?.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.selectionChanged();
    }
    const subContainer = document.getElementById("ege-subtab-container");
    if (subContainer) subContainer.innerHTML = renderParonymsDictTab();
  }

  function onParonymSearch(query) {
    paronymSearchQuery = query;
    const subContainer = document.getElementById("ege-subtab-container");
    if (subContainer) subContainer.innerHTML = renderParonymsDictTab();
  }

  function setPQuizTotal(total) {
    pQuizTotal = total;
    if (window.Telegram?.WebApp?.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.selectionChanged();
    }
    const subContainer = document.getElementById("ege-subtab-container");
    if (subContainer) subContainer.innerHTML = renderParonymsQuizTab();
  }

  function startPQuiz(isMistakes = false) {
    const pData = window.PARONYMS_DATA || { questions: [] };
    const pool = pData.questions;

    if (!pool || pool.length === 0) return;

    // Shuffle pool using Fisher-Yates
    const shuffled = shuffleArray(pool);

    // Deduplicate by question ID or sentence
    const seen = new Set();
    const uniquePool = [];
    for (const q of shuffled) {
      const key = q.id !== undefined ? String(q.id) : (q.sentence || "").trim().toLowerCase();
      if (key && !seen.has(key)) {
        seen.add(key);
        uniquePool.push(q);
      }
    }

    const count = Math.min(pQuizTotal, uniquePool.length);
    pQuizQuestions = uniquePool.slice(0, count);

    pQuizIndex = 0;
    pQuizAnswered = false;
    pQuizCorrectCount = 0;
    pQuizMistakes = [];
    lastPSelectedWord = null;
    lastPAnswerCorrect = false;

    if (window.Telegram?.WebApp?.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.impactOccurred("medium");
    }

    const subContainer = document.getElementById("ege-subtab-container");
    if (subContainer) subContainer.innerHTML = renderParonymsQuizTab();
  }

  function startPMistakesQuiz() {
    const mistakes = getStoredPMistakes();
    if (!mistakes || mistakes.length === 0) return;

    // Deduplicate mistakes by id or sentence
    const seen = new Set();
    const uniqueMistakes = [];
    for (const q of mistakes) {
      const key = q && q.id !== undefined ? String(q.id) : (q && q.sentence ? q.sentence.trim().toLowerCase() : "");
      if (key && !seen.has(key)) {
        seen.add(key);
        uniqueMistakes.push(q);
      }
    }

    pQuizQuestions = shuffleArray(uniqueMistakes);
    pQuizIndex = 0;
    pQuizAnswered = false;
    pQuizCorrectCount = 0;
    pQuizMistakes = [];
    lastPSelectedWord = null;
    lastPAnswerCorrect = false;

    if (window.Telegram?.WebApp?.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.impactOccurred("medium");
    }

    const subContainer = document.getElementById("ege-subtab-container");
    if (subContainer) subContainer.innerHTML = renderParonymsQuizTab();
  }

  function answerPQuestion(selectedWord) {
    if (pQuizAnswered) return;

    const current = pQuizQuestions[pQuizIndex];
    if (!current) return;

    pQuizAnswered = true;
    lastPSelectedWord = selectedWord;
    const isCorrect = selectedWord.toLowerCase() === current.correct.toLowerCase();
    lastPAnswerCorrect = isCorrect;

    if (isCorrect) {
      pQuizCorrectCount++;
      if (window.Telegram?.WebApp?.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.notificationOccurred("success");
      }
    } else {
      const key = current.id !== undefined ? String(current.id) : (current.sentence || "").trim().toLowerCase();
      if (!pQuizMistakes.some(m => (m.id !== undefined ? String(m.id) : (m.sentence || "").trim().toLowerCase()) === key)) {
        pQuizMistakes.push(current);
      }
      if (window.Telegram?.WebApp?.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.notificationOccurred("error");
      }
    }

    const subContainer = document.getElementById("ege-subtab-container");
    if (subContainer) subContainer.innerHTML = renderPQuizQuestion();
  }

  function nextPQuestion() {
    pQuizIndex++;
    pQuizAnswered = false;
    lastPSelectedWord = null;
    lastPAnswerCorrect = false;

    const subContainer = document.getElementById("ege-subtab-container");
    if (subContainer) subContainer.innerHTML = renderParonymsQuizTab();
  }

  function resetPQuiz() {
    pQuizQuestions = [];
    pQuizIndex = 0;
    pQuizAnswered = false;
    pQuizCorrectCount = 0;
    pQuizMistakes = [];
    lastPSelectedWord = null;
    lastPAnswerCorrect = false;
    (window.EGE?.renderEge || window.EGE_CORE?.renderEge || function(){})();
  }

  function savePMistakes(mistakes) {
    try {
      const seen = new Set();
      const unique = [];
      for (const m of (mistakes || [])) {
        const key = m && m.id !== undefined ? String(m.id) : (m && m.sentence ? m.sentence.trim().toLowerCase() : "");
        if (key && !seen.has(key)) {
          seen.add(key);
          unique.push(m);
        }
      }
      localStorage.setItem("ege_task5_mistakes", JSON.stringify(unique));
    } catch (e) {}
  }

  function getStoredPMistakes() {
    try {
      const raw = localStorage.getItem("ege_task5_mistakes");
      const list = raw ? JSON.parse(raw) : [];
      const seen = new Set();
      const unique = [];
      for (const m of list) {
        const key = m && m.id !== undefined ? String(m.id) : (m && m.sentence ? m.sentence.trim().toLowerCase() : "");
        if (key && !seen.has(key)) {
          seen.add(key);
          unique.push(m);
        }
      }
      return unique;
    } catch (e) {
      return [];
    }
  }

  // ==============================================================================
  

  window.EGE_PARONYMS = {
    renderParonymsDictTab: renderParonymsDictTab,
    renderParonymsQuizTab: renderParonymsQuizTab,
    renderPQuizSetup: renderPQuizSetup,
    renderPQuizQuestion: renderPQuizQuestion,
    renderPQuizResults: renderPQuizResults,
    setPLetterFilter: setPLetterFilter,
    onParonymSearch: onParonymSearch,
    setPQuizTotal: setPQuizTotal,
    startPQuiz: startPQuiz,
    startPMistakesQuiz: startPMistakesQuiz,
    answerPQuestion: answerPQuestion,
    nextPQuestion: nextPQuestion,
    resetPQuiz: resetPQuiz,
    savePMistakes: savePMistakes,
    getStoredPMistakes: getStoredPMistakes
  };
})();
