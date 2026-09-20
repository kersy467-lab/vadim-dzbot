// Module: EGE_CORE
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

  let currentSubject = "russian";
  let currentTask = 4; // 4 (Ударения) или 5 (Паронимы)
  let currentSubTab = "quiz"; // 'quiz' or 'dict'

  function initEge() {
    const container = document.getElementById("pane-ege");
    if (!container) return;
    renderEge();
  }

  function renderEge() {
    const container = document.getElementById("pane-ege");
    if (!container) return;

    container.innerHTML = `
      <!-- Subject Header & Selector -->
      <div class="space-y-3">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-base font-black text-slate-900 dark:text-white tracking-tight flex items-center gap-1.5">
              <span>🎓</span> Тренажер ЕГЭ
            </h2>
            <p class="text-xs text-slate-400 font-medium">Подготовка по официальным банкам ФИПИ</p>
          </div>
          <span class="text-[11px] font-bold px-2 py-0.5 rounded-lg bg-indigo-50 dark:bg-slate-800 text-indigo-600 dark:text-indigo-400 border border-indigo-100 dark:border-slate-700">ФИПИ 2026</span>
        </div>

        <!-- Subjects Carousel/Pills -->
        <div class="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar text-xs">
          ${(EGE_DATA.subjects || []).map(s => `
            <button onclick="window.EGE.selectSubject('${s.id}')" class="px-3 py-1.5 rounded-xl font-bold whitespace-nowrap transition-all flex items-center gap-1.5 ${
              currentSubject === s.id
                ? 'bg-blue-600 text-white shadow-sm shadow-blue-500/25'
                : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200/80 dark:border-slate-700'
            }">
              <span>${s.icon}</span>
              <span>${s.name}</span>
            </button>
          `).join('')}
        </div>
      </div>

      <!-- Content Area for Selected Subject -->
      <div id="ege-subject-content" class="space-y-4">
        ${renderSubjectContent()}
      </div>
    `;
  }

  function renderSubjectContent() {
    const subj = (EGE_DATA.subjects || []).find(s => s.id === currentSubject);
    const availableTasks = (subj?.tasks || []).filter(t => t.available !== false);

    if (!subj || availableTasks.length === 0) {
      return `
        <div class="theme-card rounded-2xl p-8 text-center bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 space-y-2">
          <span class="text-3xl">${subj?.icon || '📚'}</span>
          <h3 class="font-bold text-slate-800 dark:text-slate-100 text-sm">Заданий пока нет</h3>
          <p class="text-xs text-slate-400 max-w-xs mx-auto">Для предмета «${subj?.name || ''}» пока нет добавленных заданий.</p>
        </div>
      `;
    }

    // Task Selection Cards
    return `
      <!-- Tasks list -->
      <div class="theme-card rounded-2xl p-3 bg-white dark:bg-slate-800 border border-slate-200/70 dark:border-slate-700 space-y-2">
        <div class="flex items-center justify-between px-1">
          <span class="text-[11px] font-bold uppercase tracking-wider text-slate-400">Задания ЕГЭ</span>
          <span class="text-[11px] text-blue-600 dark:text-blue-400 font-bold">${availableTasks.length} доступно</span>
        </div>
        <div class="grid grid-cols-1 gap-1.5">
          ${availableTasks.map(t => {
            const isActive = currentTask === t.number;
            const cardStyle = isActive
              ? "border-blue-500 bg-blue-50/70 dark:bg-blue-950/40 ring-1 ring-blue-500 shadow-sm"
              : "border-slate-200/80 dark:border-slate-700 bg-white dark:bg-slate-800 hover:border-blue-300 cursor-pointer";

            return `
              <div onclick="window.EGE.selectTask(${t.number})"
                   class="p-2.5 rounded-xl border transition-all ${cardStyle}">
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2">
                    <span class="w-6 h-6 rounded-lg ${isActive ? 'bg-blue-600 text-white shadow-sm' : 'bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-200'} font-black text-xs flex items-center justify-center">${t.number}</span>
                    <div>
                      <h4 class="text-xs font-bold text-slate-800 dark:text-slate-100">${t.title}</h4>
                      <p class="text-[11px] text-slate-400">${t.desc}</p>
                    </div>
                  </div>
                  <span class="text-[10px] font-bold px-2 py-0.5 rounded-md ${isActive ? 'bg-blue-600 text-white' : 'bg-emerald-100 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400'}">${isActive ? 'Выбрано' : 'Открыть'}</span>
                </div>
              </div>
            `;
          }).join('')}
        </div>
      </div>

      <!-- Active Task Container -->
      <div class="space-y-3">
        ${currentSubject === "math" && currentTask === 18
          ? (window.EGE_MATH18 ? window.EGE_MATH18.renderMathTask18() : '')
          : `
            <!-- Sub-tabs: Quiz vs Dictionary -->
            <div class="flex items-center p-1 rounded-2xl bg-slate-200/70 dark:bg-slate-800/90 text-xs font-bold">
              <button id="ege-subtab-btn-quiz" onclick="window.EGE.setSubTab('quiz')" class="flex-1 py-2 rounded-xl transition-all flex items-center justify-center gap-1.5 ${
                currentSubTab === 'quiz'
                  ? 'bg-white dark:bg-slate-700 text-blue-600 dark:text-blue-400 shadow-sm'
                  : 'text-slate-500 dark:text-slate-400 hover:text-slate-700'
              }">
                <span>🎯</span>
                <span>Тренажёр</span>
              </button>
              <button id="ege-subtab-btn-dict" onclick="window.EGE.setSubTab('dict')" class="flex-1 py-2 rounded-xl transition-all flex items-center justify-center gap-1.5 ${
                currentSubTab === 'dict'
                  ? 'bg-white dark:bg-slate-700 text-blue-600 dark:text-blue-400 shadow-sm'
                  : 'text-slate-500 dark:text-slate-400 hover:text-slate-700'
              }">
                <span>📖</span>
                <span>${currentTask === 5 ? 'Словарь паронимов' : 'Словарь ФИПИ'}</span>
              </button>
            </div>

            <!-- Tab Body -->
            <div id="ege-subtab-container">
              ${currentTask === 5 
                ? (currentSubTab === 'quiz' ? (window.EGE_PARONYMS ? window.EGE_PARONYMS.renderParonymsQuizTab() : '') : (window.EGE_PARONYMS ? window.EGE_PARONYMS.renderParonymsDictTab() : ''))
                : (currentSubTab === 'quiz' ? (window.EGE_STRESS ? window.EGE_STRESS.renderQuizTab() : '') : (window.EGE_STRESS ? window.EGE_STRESS.renderDictTab() : ''))
              }
            </div>
          `
        }
      </div>
    `;
  }

  function selectSubject(subjectId) {
    currentSubject = subjectId;
    if (subjectId === "math") {
      currentTask = 18;
      if (window.EGE_MATH18 && typeof window.EGE_MATH18.resetSolution === "function") {
        window.EGE_MATH18.resetSolution();
      }
    } else if (subjectId === "russian") {
      if (currentTask !== 4 && currentTask !== 5) currentTask = 4;
    }
    if (window.Telegram?.WebApp?.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.selectionChanged();
    }
    renderEge();
  }

  function selectTask(taskNumber) {
    if (currentTask === taskNumber) return;
    currentTask = taskNumber;
    currentSubTab = "quiz";
    if (window.Telegram?.WebApp?.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.selectionChanged();
    }
    renderEge();
  }

  function updateSubTabNavDOM() {
    const btnQuiz = document.getElementById("ege-subtab-btn-quiz");
    const btnDict = document.getElementById("ege-subtab-btn-dict");
    if (!btnQuiz || !btnDict) return;

    const activeClasses = ["bg-white", "dark:bg-slate-700", "text-blue-600", "dark:text-blue-400", "shadow-sm"];
    const inactiveClasses = ["text-slate-500", "dark:text-slate-400", "hover:text-slate-700"];

    if (currentSubTab === "quiz") {
      btnQuiz.classList.add(...activeClasses);
      btnQuiz.classList.remove(...inactiveClasses);
      btnDict.classList.remove(...activeClasses);
      btnDict.classList.add(...inactiveClasses);
    } else {
      btnDict.classList.add(...activeClasses);
      btnDict.classList.remove(...inactiveClasses);
      btnQuiz.classList.remove(...activeClasses);
      btnQuiz.classList.add(...inactiveClasses);
    }
  }

  function setSubTab(tab) {
    currentSubTab = tab;
    if (window.Telegram?.WebApp?.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.selectionChanged();
    }
    const subContainer = document.getElementById("ege-subtab-container");
    if (!subContainer) {
      renderEge();
      return;
    }
    updateSubTabNavDOM();
    if (currentTask === 5) {
      subContainer.innerHTML = currentSubTab === "quiz" ? (window.EGE_PARONYMS ? window.EGE_PARONYMS.renderParonymsQuizTab() : '') : (window.EGE_PARONYMS ? window.EGE_PARONYMS.renderParonymsDictTab() : '');
    } else {
      subContainer.innerHTML = currentSubTab === "quiz" ? (window.EGE_STRESS ? window.EGE_STRESS.renderQuizTab() : '') : (window.EGE_STRESS ? window.EGE_STRESS.renderDictTab() : '');
    }
  }

  // ==============================================================================

  window.EGE_CORE = {
    initEge: initEge,
    renderEge: renderEge,
    selectSubject: selectSubject,
    selectTask: selectTask,
    setSubTab: setSubTab
  };
})();
