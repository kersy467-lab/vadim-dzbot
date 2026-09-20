// Module: EGE_STRESS
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

  const RUSSIAN_VOWELS = "аеёиоуыэюяАЕЁИОУЫЭЮЯ";
  const EGE_DATA = window.EGE_DATA || {};
  let currentPosFilter = "all";
  let dictSearchQuery = "";
  let quizWords = [];
  let quizIndex = 0;
  let quizAnswered = false;
  let quizCorrectCount = 0;
  let quizMistakes = [];
  let quizTotal = 10;
// РАЗДЕЛ ЗАДАНИЯ 4: ОРФОЭПИЯ / УДАРЕНИЯ (СЛОВАРЬ + ТРЕНАЖЕР)
  // ==============================================================================

  function renderDictTab() {
    const query = dictSearchQuery.toLowerCase().trim();
    const filtered = (EGE_DATA.task4_words || []).filter(item => {
      const matchesPos = currentPosFilter === "all" || item.pos === currentPosFilter;
      const matchesQuery = !query || item.word.toLowerCase().includes(query) || (item.note && item.note.toLowerCase().includes(query));
      return matchesPos && matchesQuery;
    });

    const posFilters = [
      { id: "all", label: "Все" },
      { id: "noun", label: "Сущ." },
      { id: "adjective", label: "Прил." },
      { id: "verb", label: "Глаг." },
      { id: "participle", label: "Прич." },
      { id: "gerund", label: "Деепр." },
      { id: "adverb", label: "Нареч." }
    ];

    return `
      <div class="space-y-3">
        <!-- Search bar -->
        <div class="relative">
          <input
            type="text"
            value="${dictSearchQuery}"
            oninput="window.EGE.onDictSearch(this.value)"
            placeholder="Поиск слова по словарю ФИПИ..."
            class="w-full px-3.5 py-2.5 pl-9 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all shadow-sm"
          />
          <span class="absolute left-3 top-2.5 text-slate-400 text-xs">🔍</span>
          ${dictSearchQuery ? `
            <button onclick="window.EGE.onDictSearch('')" class="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600 text-xs font-bold">✕</button>
          ` : ''}
        </div>

        <!-- Part of speech pills -->
        <div class="flex items-center gap-1 overflow-x-auto pb-1 no-scrollbar text-xs">
          ${posFilters.map(p => `
            <button onclick="window.EGE.setPosFilter('${p.id}')" class="px-2.5 py-1 rounded-xl text-[11px] font-bold whitespace-nowrap transition-all ${
              currentPosFilter === p.id
                ? 'bg-blue-600 text-white shadow-sm shadow-blue-500/20'
                : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200/80 dark:border-slate-700'
            }">
              ${p.label}
            </button>
          `).join('')}
        </div>

        <!-- Words Count and Notice -->
        <div class="flex items-center justify-between text-[11px] text-slate-400 px-1">
          <span>Найдено слов: <b>${filtered.length}</b> из ${(EGE_DATA.task4_words || []).length}</span>
          <span class="text-emerald-600 font-bold">Официальный кодификатор</span>
        </div>

        <!-- Words List Grid -->
        <div class="grid grid-cols-1 gap-1.5 max-h-[55vh] overflow-y-auto pr-1">
          ${filtered.length === 0 ? `
            <div class="text-center py-10 theme-card rounded-2xl p-6 text-slate-400 text-xs space-y-2">
              <span class="text-3xl">🔍</span>
              <p>По запросу «${dictSearchQuery}» ничего не найдено</p>
            </div>
          ` : filtered.map(item => `
            <div class="theme-card rounded-xl p-2.5 bg-white dark:bg-slate-800 border border-slate-200/70 dark:border-slate-700 flex items-center justify-between gap-2 shadow-sm">
              <div>
                <span class="text-sm font-bold text-slate-900 dark:text-white tracking-wide">
                  ${highlightStressedWord(item.word)}
                </span>
                ${item.note ? `<p class="text-[11px] text-slate-400 mt-0.5">${item.note}</p>` : ''}
              </div>
              <span class="text-[10px] px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-300 font-medium whitespace-nowrap">
                ${EGE_DATA.partOfSpeechMap[item.pos] || ''}
              </span>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  function highlightStressedWord(word) {
    return word.split("").map(ch => {
      if (RUSSIAN_VOWELS.includes(ch) && ch === ch.toUpperCase()) {
        return `<span class="text-blue-600 dark:text-blue-400 font-extrabold underline decoration-2 decoration-blue-500">${ch}</span>`;
      }
      return ch;
    }).join("");
  }

  function renderQuizTab() {
    if (quizWords.length === 0) {
      return renderQuizSetup();
    }
    if (quizIndex >= quizWords.length) {
      return renderQuizResults();
    }
    return renderQuizQuestion();
  }

  function renderQuizSetup() {
    const totalWords = (EGE_DATA.task4_words || []).length;
    const storedMistakes = getStoredMistakes();

    return `
      <div class="theme-card rounded-3xl p-5 bg-white dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700 shadow-sm space-y-4">
        <div class="text-center space-y-1.5">
          <div class="w-12 h-12 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-600 text-white text-2xl flex items-center justify-center mx-auto shadow-md shadow-blue-500/25">
            🎯
          </div>
          <h3 class="text-sm font-black text-slate-900 dark:text-white">Тренажер: Ударения (Задание 4)</h3>
          <p class="text-xs text-slate-500 dark:text-slate-400 leading-relaxed max-w-xs mx-auto">
            Нажимайте прямо на правильную ударную гласную букву в слове.
          </p>
        </div>

        <!-- Question count selection -->
        <div class="space-y-2">
          <span class="text-[11px] font-bold uppercase tracking-wider text-slate-400">Количество слов:</span>
          <div class="grid grid-cols-4 gap-1.5">
            ${[10, 25, 50, 'all'].map(cnt => {
              const label = cnt === 'all' ? `Все (${totalWords})` : cnt;
              const isSelected = (quizTotal === cnt || (cnt === 'all' && quizTotal === totalWords));
              return `
                <button onclick="window.EGE.setQuizTotal(${cnt === 'all' ? totalWords : cnt})" class="py-2.5 rounded-xl font-bold text-xs transition-all ${
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
          <button onclick="window.EGE.startQuiz(false)" class="w-full py-3.5 rounded-2xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 active:scale-[0.98] text-white font-extrabold text-sm shadow-lg shadow-blue-500/25 transition-all flex items-center justify-center gap-2">
            <span>🚀 Начать тренировку</span>
          </button>

          ${storedMistakes.length > 0 ? `
            <button onclick="window.EGE.startMistakesQuiz()" class="w-full py-2.5 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 text-amber-700 dark:text-amber-300 font-bold text-xs hover:bg-amber-100 transition-all flex items-center justify-center gap-2">
              <span>⚠️ Повторить ошибки (${storedMistakes.length})</span>
            </button>
          ` : ''}
        </div>
      </div>
    `;
  }

  function renderQuizQuestion() {
    const current = quizWords[quizIndex];
    if (!current) return renderQuizResults();

    const progressPercent = Math.round(((quizIndex + (quizAnswered ? 1 : 0)) / quizWords.length) * 100);
    const letters = current.word.split("");

    return `
      <div class="theme-card rounded-3xl p-5 bg-white dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700 shadow-sm space-y-4">
        <!-- Progress Header -->
        <div class="space-y-1.5">
          <div class="flex items-center justify-between text-xs">
            <span class="font-bold text-slate-500 dark:text-slate-400">Слово ${quizIndex + 1} из ${quizWords.length}</span>
            <div class="flex items-center gap-1.5">
              <span class="text-emerald-600 font-bold">✓ ${quizCorrectCount}</span>
              <span class="text-rose-500 font-bold">✗ ${quizMistakes.length}</span>
              <button onclick="window.EGE.resetQuiz()" class="text-slate-400 hover:text-slate-600 ml-1 text-xs">✕ Выйти</button>
            </div>
          </div>
          <div class="w-full h-2 rounded-full bg-slate-100 dark:bg-slate-700 overflow-hidden">
            <div class="h-full bg-blue-600 rounded-full transition-all duration-300" style="width: ${progressPercent}%"></div>
          </div>
        </div>

        <!-- Question Prompt -->
        <div class="text-center">
          <span class="text-xs font-bold uppercase tracking-wider text-slate-400">Нажмите на ударную гласную:</span>
        </div>

        <!-- Interactive Word Tiles -->
        <div class="flex items-center justify-center flex-wrap gap-1.5 py-4 select-none">
          ${letters.map((ch, idx) => {
            const isVowel = RUSSIAN_VOWELS.includes(ch);
            const isTargetStressed = ch === ch.toUpperCase() && isVowel;
            const lowerCh = ch.toLowerCase();

            if (!isVowel) {
              return `
                <span class="w-9 h-11 flex items-center justify-center text-xl font-bold text-slate-700 dark:text-slate-200">
                  ${lowerCh}
                </span>
              `;
            }

            let tileClass = "bg-slate-100 dark:bg-slate-700/70 text-slate-800 dark:text-slate-100 hover:bg-blue-50 dark:hover:bg-slate-700 border-slate-200 dark:border-slate-600 cursor-pointer active:scale-95";
            if (quizAnswered) {
              if (isTargetStressed) {
                tileClass = "bg-emerald-500 text-white border-emerald-600 font-black shadow-md shadow-emerald-500/25 ring-2 ring-emerald-400";
              } else if (window._lastClickedVowelIdx === idx) {
                tileClass = "bg-rose-500 text-white border-rose-600 font-black ring-2 ring-rose-400 animate-shake";
              } else {
                tileClass = "bg-slate-100 dark:bg-slate-800 text-slate-400 opacity-60 cursor-default";
              }
            }

            return `
              <button
                ${quizAnswered ? 'disabled' : ''}
                onclick="window.EGE.answerQuestion(${idx}, ${isTargetStressed})"
                class="w-10 h-12 rounded-2xl border-2 font-black text-xl flex items-center justify-center transition-all ${tileClass}">
                ${lowerCh}
              </button>
            `;
          }).join('')}
        </div>

        <!-- Feedback -->
        ${quizAnswered ? `
          <div class="p-3.5 rounded-2xl ${window._lastAnswerCorrect ? 'bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-900/40 text-emerald-800 dark:text-emerald-300' : 'bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900/40 text-rose-800 dark:text-rose-300'} text-xs space-y-1 transition-all">
            <div class="flex items-center gap-2 font-bold text-sm">
              <span>${window._lastAnswerCorrect ? '🎉 Правильно!' : '❌ Ошибка!'}</span>
              <span>Правильно: <u>${current.word}</u></span>
            </div>
          </div>

          <button onclick="window.EGE.nextQuestion()" class="w-full py-3 rounded-2xl bg-blue-600 hover:bg-blue-700 active:scale-[0.98] text-white font-extrabold text-sm shadow-md shadow-blue-500/25 transition-all flex items-center justify-center gap-2">
            <span>Дальше ➜</span>
          </button>
        ` : ''}
      </div>
    `;
  }

  function renderQuizResults() {
    const total = quizWords.length;
    const percent = Math.round((quizCorrectCount / total) * 100);
    const hasMistakes = quizMistakes.length > 0;

    saveMistakes(quizMistakes);

    return `
      <div class="theme-card rounded-3xl p-6 bg-white dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700 shadow-sm text-center space-y-5">
        <div class="w-16 h-16 mx-auto rounded-3xl bg-gradient-to-tr ${percent >= 80 ? 'from-emerald-500 to-teal-500 shadow-emerald-500/25' : percent >= 50 ? 'from-amber-500 to-yellow-500 shadow-amber-500/25' : 'from-rose-500 to-orange-500 shadow-rose-500/25'} text-white text-3xl flex items-center justify-center shadow-lg">
          ${percent >= 80 ? '🏆' : percent >= 50 ? '👍' : '💪'}
        </div>

        <div class="space-y-1">
          <h3 class="text-lg font-black text-slate-900 dark:text-white">Тренировка завершена!</h3>
          <p class="text-xs text-slate-400">Результат: ${quizCorrectCount} из ${total} верных (${percent}%)</p>
        </div>

        <!-- Mistakes breakdown if any -->
        ${hasMistakes ? `
          <div class="text-left space-y-2 pt-2 border-t border-slate-100 dark:border-slate-700">
            <span class="text-xs font-bold text-rose-500">Слова с ошибками (${quizMistakes.length}):</span>
            <div class="grid grid-cols-2 gap-1.5 max-h-48 overflow-y-auto pr-1">
              ${quizMistakes.map(m => `
                <div class="p-2 rounded-xl bg-rose-50/70 dark:bg-rose-950/20 border border-rose-100 dark:border-rose-900/40 text-xs font-bold text-rose-700 dark:text-rose-300 truncate">
                  ${m.word}
                </div>
              `).join('')}
            </div>
          </div>
        ` : `
          <div class="p-3 rounded-2xl bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300 text-xs font-bold">
            🌟 Отличный результат! Все слова отвечены правильно!
          </div>
        `}

        <div class="space-y-2 pt-2">
          ${hasMistakes ? `
            <button onclick="window.EGE.startMistakesQuiz()" class="w-full py-3 rounded-2xl bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 active:scale-[0.98] text-white font-extrabold text-xs shadow-md shadow-amber-500/25 transition-all flex items-center justify-center gap-2">
              <span>🔄 Отработать только ошибки (${quizMistakes.length})</span>
            </button>
          ` : ''}

          <button onclick="window.EGE.resetQuiz()" class="w-full py-3 rounded-2xl bg-blue-600 hover:bg-blue-700 active:scale-[0.98] text-white font-extrabold text-xs shadow-md shadow-blue-500/25 transition-all">
            <span>🎯 Начать новую тренировку</span>
          </button>
        </div>
      </div>
    `;
  }

  function setPosFilter(pos) {
    currentPosFilter = pos;
    if (window.Telegram?.WebApp?.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.selectionChanged();
    }
    const subContainer = document.getElementById("ege-subtab-container");
    if (subContainer) subContainer.innerHTML = renderDictTab();
  }

  function onDictSearch(query) {
    dictSearchQuery = query;
    const subContainer = document.getElementById("ege-subtab-container");
    if (subContainer) subContainer.innerHTML = renderDictTab();
  }

  function setQuizTotal(total) {
    quizTotal = total;
    if (window.Telegram?.WebApp?.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.selectionChanged();
    }
    const subContainer = document.getElementById("ege-subtab-container");
    if (subContainer) subContainer.innerHTML = renderQuizTab();
  }

  function startQuiz(isMistakes = false) {
    let pool = EGE_DATA.task4_words || [];
    if (pool.length === 0) return;

    // Shuffle pool using Fisher-Yates
    const shuffled = shuffleArray(pool);

    // Strict deduplication by lowercase word so no word ever repeats in one test
    const seenWords = new Set();
    const uniquePool = [];
    for (const item of shuffled) {
      const key = (item.word || "").toLowerCase();
      if (key && !seenWords.has(key)) {
        seenWords.add(key);
        uniquePool.push(item);
      }
    }

    const count = Math.min(quizTotal, uniquePool.length);
    quizWords = uniquePool.slice(0, count);

    quizIndex = 0;
    quizAnswered = false;
    quizCorrectCount = 0;
    quizMistakes = [];
    window._lastClickedVowelIdx = null;
    window._lastAnswerCorrect = false;

    if (window.Telegram?.WebApp?.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.impactOccurred("medium");
    }

    const subContainer = document.getElementById("ege-subtab-container");
    if (subContainer) subContainer.innerHTML = renderQuizTab();
  }

  function startMistakesQuiz() {
    const mistakes = getStoredMistakes();
    if (!mistakes || mistakes.length === 0) return;

    // Deduplicate mistakes by lowercase word
    const seen = new Set();
    const uniqueMistakes = [];
    for (const m of mistakes) {
      const key = (m && m.word ? m.word : "").toLowerCase();
      if (key && !seen.has(key)) {
        seen.add(key);
        uniqueMistakes.push(m);
      }
    }

    quizWords = shuffleArray(uniqueMistakes);
    quizIndex = 0;
    quizAnswered = false;
    quizCorrectCount = 0;
    quizMistakes = [];
    window._lastClickedVowelIdx = null;
    window._lastAnswerCorrect = false;

    if (window.Telegram?.WebApp?.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.impactOccurred("medium");
    }

    const subContainer = document.getElementById("ege-subtab-container");
    if (subContainer) subContainer.innerHTML = renderQuizTab();
  }

  function answerQuestion(vowelIdx, isCorrect) {
    if (quizAnswered) return;

    const currentWord = quizWords[quizIndex];
    if (!currentWord) return;

    quizAnswered = true;
    window._lastClickedVowelIdx = vowelIdx;
    window._lastAnswerCorrect = isCorrect;

    if (isCorrect) {
      quizCorrectCount++;
      if (window.Telegram?.WebApp?.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.notificationOccurred("success");
      }
    } else {
      if (!quizMistakes.some(m => m.word.toLowerCase() === currentWord.word.toLowerCase())) {
        quizMistakes.push(currentWord);
      }
      if (window.Telegram?.WebApp?.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.notificationOccurred("error");
      }
    }

    const subContainer = document.getElementById("ege-subtab-container");
    if (subContainer) subContainer.innerHTML = renderQuizQuestion();
  }

  function nextQuestion() {
    quizIndex++;
    quizAnswered = false;
    window._lastClickedVowelIdx = null;
    window._lastAnswerCorrect = false;

    const subContainer = document.getElementById("ege-subtab-container");
    if (subContainer) subContainer.innerHTML = renderQuizTab();
  }

  function resetQuiz() {
    quizWords = [];
    quizIndex = 0;
    quizAnswered = false;
    quizCorrectCount = 0;
    quizMistakes = [];
    (window.EGE?.renderEge || window.EGE_CORE?.renderEge || function(){})();
  }

  function saveMistakes(mistakes) {
    try {
      const seen = new Set();
      const unique = [];
      for (const m of (mistakes || [])) {
        if (!m || !m.word) continue;
        const key = m.word.toLowerCase();
        if (!seen.has(key)) {
          seen.add(key);
          unique.push(m);
        }
      }
      localStorage.setItem("ege_task4_mistakes", JSON.stringify(unique));
    } catch (e) {}
  }

  function getStoredMistakes() {
    try {
      const raw = localStorage.getItem("ege_task4_mistakes");
      const list = raw ? JSON.parse(raw) : [];
      const seen = new Set();
      const unique = [];
      for (const m of list) {
        if (!m || !m.word) continue;
        const key = m.word.toLowerCase();
        if (!seen.has(key)) {
          seen.add(key);
          unique.push(m);
        }
      }
      return unique;
    } catch (e) {
      return [];
    }
  }

  

  window.EGE_STRESS = {
    renderDictTab: renderDictTab,
    highlightStressedWord: highlightStressedWord,
    renderQuizTab: renderQuizTab,
    renderQuizSetup: renderQuizSetup,
    renderQuizQuestion: renderQuizQuestion,
    renderQuizResults: renderQuizResults,
    setPosFilter: setPosFilter,
    onDictSearch: onDictSearch,
    setQuizTotal: setQuizTotal,
    startQuiz: startQuiz,
    startMistakesQuiz: startMistakesQuiz,
    answerQuestion: answerQuestion,
    nextQuestion: nextQuestion,
    resetQuiz: resetQuiz,
    saveMistakes: saveMistakes,
    getStoredMistakes: getStoredMistakes
  };
})();
