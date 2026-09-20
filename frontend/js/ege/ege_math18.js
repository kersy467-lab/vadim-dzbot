// Module: EGE_MATH18
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

// РАЗДЕЛ МАТЕМАТИКИ: ЗАДАНИЕ 18 (ПАРАМЕТРЫ) • 153 ЗАДАЧИ
  // ==============================================================================
  let math18CurrentIdx = 0;
  let math18TopicFilter = "Все";
  let math18SearchQuery = "";
  let math18ShowSolution = false;

  const MATH18_TOPICS = [
    "Все",
    "📊 С графиками",
    "Графический метод",
    "Окружности и прямые",
    "Уголки и модули",
    "Замена переменной",
    "Инвариантность и чётность",
    "Монотонность и оценка",
    "Тригонометрия",
    "Квадратный трёхчлен и Виет"
  ];

  function getFilteredMath18Tasks() {
    const all = window.EGE_MATH18_TASKS || [];
    return all.filter(t => {
      let topicMatch = true;
      if (math18TopicFilter === "📊 С графиками") {
        topicMatch = t.has_graphics === true;
      } else if (math18TopicFilter !== "Все") {
        topicMatch = (t.topic === math18TopicFilter);
      }

      let searchMatch = true;
      if (math18SearchQuery) {
        const q = math18SearchQuery.toLowerCase().trim();
        searchMatch = String(t.num) === q || 
                      t.id.toLowerCase().includes(q) ||
                      (t.topic && t.topic.toLowerCase().includes(q));
      }

      return topicMatch && searchMatch;
    });
  }

  function renderMathTask18() {
    const all = window.EGE_MATH18_TASKS || [];
    const filtered = getFilteredMath18Tasks();
    if (filtered.length > 0 && math18CurrentIdx >= filtered.length) {
      math18CurrentIdx = 0;
    }

    const t = filtered[math18CurrentIdx];

    return `
      <div class="space-y-3">
        <!-- Search & Filter Bar -->
        <div class="theme-card rounded-2xl p-3 bg-white dark:bg-slate-800 border border-slate-200/70 dark:border-slate-700 space-y-2.5">
          <div class="flex items-center gap-2">
            <div class="relative flex-1">
              <input type="text" value="${math18SearchQuery}" 
                     placeholder="Поиск по номеру (напр. 88) или #ID..." 
                     oninput="window.EGE.onMath18Search(this.value)"
                     class="w-full pl-8 pr-3 py-2 text-xs font-semibold rounded-xl bg-slate-50 dark:bg-slate-700/60 border border-slate-200 dark:border-slate-600 text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <span class="absolute left-2.5 top-2.5 text-xs text-slate-400">🔍</span>
            </div>
            <button onclick="window.EGE.randomMath18Task()" class="px-3 py-2 rounded-xl bg-blue-50 dark:bg-slate-700 hover:bg-blue-100 text-xs font-bold text-blue-600 dark:text-blue-400 border border-blue-100 dark:border-slate-600 transition-colors flex items-center gap-1 whitespace-nowrap" title="Случайная задача">
              <span>🎲</span>
            </button>
          </div>

          <!-- Filter Pills -->
          <div class="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar text-xs">
            ${MATH18_TOPICS.map(topic => {
              const isActive = math18TopicFilter === topic;
              return `
                <button onclick="window.EGE.selectMath18Topic('${topic}')" class="px-2.5 py-1 rounded-xl font-bold whitespace-nowrap transition-all text-[11px] ${
                  isActive
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'bg-slate-50 dark:bg-slate-700/70 text-slate-600 dark:text-slate-300 border border-slate-200/80 dark:border-slate-600 hover:border-blue-300'
                }">
                  ${topic}
                </button>
              `;
            }).join('')}
          </div>

          <!-- Carousel / Numbers -->
          <div class="pt-0.5">
            <div class="flex items-center justify-between text-[10px] font-bold text-slate-400 mb-1 px-0.5">
              <span>Каталог заданий</span>
              <span class="text-blue-600 dark:text-blue-400 font-bold">${filtered.length} из ${all.length}</span>
            </div>
            <div class="flex items-center gap-1 overflow-x-auto pb-1 no-scrollbar text-xs" id="math18-carousel">
              ${filtered.map((item, idx) => {
                const isActive = idx === math18CurrentIdx;
                return `
                  <button onclick="window.EGE.selectMath18Task(${idx})"
                          class="px-2.5 py-1 rounded-xl font-black text-xs whitespace-nowrap transition-all flex items-center gap-0.5 ${
                            isActive 
                              ? 'bg-blue-600 text-white shadow-sm scale-105' 
                              : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-200'
                          }">
                    <span>№${item.num}</span>
                    ${item.has_graphics ? '<span class="text-[8px] opacity-75">📊</span>' : ''}
                  </button>
                `;
              }).join('')}
            </div>
          </div>
        </div>

        <!-- Task Content Card -->
        ${!t ? `
          <div class="theme-card rounded-2xl p-6 text-center bg-white dark:bg-slate-800 border border-slate-200/70 dark:border-slate-700 space-y-2">
            <span class="text-3xl">🔍</span>
            <h3 class="font-bold text-sm">Задачи не найдены</h3>
            <p class="text-xs text-slate-400">Попробуйте изменить поисковый запрос или фильтр.</p>
          </div>
        ` : `
          <div class="theme-card rounded-2xl p-3.5 sm:p-4 bg-white dark:bg-slate-800 border border-slate-200/70 dark:border-slate-700 space-y-3.5">
            
            <!-- Top bar -->
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="w-7 h-7 rounded-xl bg-blue-600 text-white font-black text-xs flex items-center justify-center shadow-sm">
                  ${t.num}
                </span>
                <div>
                  <div class="flex items-center gap-1.5">
                    <span class="text-xs font-black text-slate-900 dark:text-white">Задача №${t.num}</span>
                    <span class="text-[11px] font-bold text-blue-600 dark:text-blue-400">#${t.id}</span>
                  </div>
                  <p class="text-[10px] text-slate-400">Параметры • ЕГЭ Профиль</p>
                </div>
              </div>

              <div class="flex items-center gap-1">
                <span class="text-[10px] font-bold px-2 py-0.5 rounded-lg bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300">
                  ${t.topic}
                </span>
                ${t.has_graphics ? `
                  <span class="text-[9px] font-extrabold px-1.5 py-0.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/60 flex items-center gap-0.5">
                    <span>📊</span> График
                  </span>
                ` : ''}
              </div>
            </div>

            <!-- Condition -->
            <div class="p-2.5 sm:p-3 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-100 dark:border-slate-700/60 space-y-1.5">
              <div class="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400">
                <span>Условие задачи:</span>
                <button onclick="window.EGE.viewPhoto(['${t.cond_img}'], 0, 'Задача №${t.num}', 'Условие')" class="text-blue-600 dark:text-blue-400 font-semibold hover:underline">Увеличить 🔍</button>
              </div>
              <div class="bg-white rounded-lg p-1.5 sm:p-2 cursor-zoom-in border border-slate-200/60 shadow-xs" onclick="window.EGE.viewPhoto(['${t.cond_img}'], 0, 'Задача №${t.num}', 'Условие')">
                <img src="${t.cond_img}" alt="Условие №${t.num}" class="w-full h-auto rounded-md mx-auto" loading="lazy" />
              </div>
            </div>

            <!-- Solution Button -->
            <button onclick="window.EGE.toggleMath18Solution()" class="w-full py-2.5 px-3 rounded-xl text-xs font-black transition-all flex items-center justify-center gap-1.5 ${
              math18ShowSolution 
                ? 'bg-blue-600 hover:bg-blue-700 text-white shadow-sm shadow-blue-500/25' 
                : 'bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200'
            }">
              <span>${math18ShowSolution ? '📖 Скрыть решение' : '📝 Открыть полное пошаговое решение'}</span>
            </button>

            <!-- Solution Stream (Chronological order of text, formulas & diagrams) -->
            ${math18ShowSolution ? `
              <div class="space-y-2.5 pt-1 border-t border-slate-100 dark:border-slate-700/60">
                <div class="flex items-center justify-between px-1">
                  <div class="flex items-center gap-1.5">
                    <span class="text-xs">📝</span>
                    <h4 class="text-[11px] font-black uppercase tracking-wider text-slate-700 dark:text-slate-300">
                      Ход решения ${t.has_graphics ? '(с графиками)' : ''}:
                    </h4>
                  </div>
                  <span class="text-[10px] font-bold text-slate-400">${t.sol_imgs.length} стр.</span>
                </div>

                <div class="space-y-2.5">
                  ${t.sol_imgs.map((s_img, s_idx) => `
                    <div class="bg-white dark:bg-slate-900 rounded-xl p-2 border border-slate-200 dark:border-slate-700/80 shadow-xs space-y-1">
                      <div class="flex items-center justify-between px-1 text-[9px] font-bold text-slate-400">
                        <span>Часть ${s_idx + 1} из ${t.sol_imgs.length}</span>
                        <button onclick="window.EGE.viewPhoto(${JSON.stringify(t.sol_imgs).replace(/"/g, '&quot;')}, ${s_idx}, 'Задача №${t.num}', 'Решение (часть ${s_idx+1})')" class="text-blue-600 dark:text-blue-400 hover:underline">
                          Увеличить 🔍
                        </button>
                      </div>
                      <div class="cursor-zoom-in overflow-hidden rounded-lg bg-white p-0.5" onclick="window.EGE.viewPhoto(${JSON.stringify(t.sol_imgs).replace(/"/g, '&quot;')}, ${s_idx}, 'Задача №${t.num}', 'Решение (часть ${s_idx+1})')">
                        <img src="${s_img}" alt="Решение №${t.num} (${s_idx+1})" class="w-full h-auto rounded-md mx-auto" loading="lazy" />
                      </div>
                    </div>
                  `).join('')}
                </div>
              </div>
            ` : ''}

            <!-- Pagination -->
            <div class="flex items-center justify-between pt-2 border-t border-slate-100 dark:border-slate-700/60 text-xs">
              <button onclick="window.EGE.prevMath18Task()" ${math18CurrentIdx === 0 ? 'disabled class="opacity-40 cursor-not-allowed"' : ''} 
                      class="px-3 py-1.5 rounded-xl font-bold bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors flex items-center gap-1">
                <span>←</span> <span>Назад</span>
              </button>
              <span class="text-slate-400 font-bold text-[11px]">${math18CurrentIdx + 1} из ${filtered.length}</span>
              <button onclick="window.EGE.nextMath18Task()" ${math18CurrentIdx === filtered.length - 1 ? 'disabled class="opacity-40 cursor-not-allowed"' : ''} 
                      class="px-3 py-1.5 rounded-xl font-bold bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors flex items-center gap-1">
                <span>Вперёд</span> <span>→</span>
              </button>
            </div>

          </div>
        `}
      </div>
    `;
  }

  function selectMath18Topic(topic) {
    math18TopicFilter = topic;
    math18CurrentIdx = 0;
    math18ShowSolution = false;
    if (window.Telegram?.WebApp?.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.selectionChanged();
    }
    (window.EGE?.renderEge || window.EGE_CORE?.renderEge || function(){})();
  }

  function onMath18Search(query) {
    math18SearchQuery = query;
    math18CurrentIdx = 0;
    math18ShowSolution = false;
    (window.EGE?.renderEge || window.EGE_CORE?.renderEge || function(){})();
  }

  function selectMath18Task(idx) {
    math18CurrentIdx = idx;
    math18ShowSolution = false;
    if (window.Telegram?.WebApp?.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.selectionChanged();
    }
    (window.EGE?.renderEge || window.EGE_CORE?.renderEge || function(){})();
  }

  function nextMath18Task() {
    const filtered = getFilteredMath18Tasks();
    if (math18CurrentIdx < filtered.length - 1) {
      math18CurrentIdx++;
      math18ShowSolution = false;
      if (window.Telegram?.WebApp?.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.selectionChanged();
      }
      (window.EGE?.renderEge || window.EGE_CORE?.renderEge || function(){})();
    }
  }

  function prevMath18Task() {
    if (math18CurrentIdx > 0) {
      math18CurrentIdx--;
      math18ShowSolution = false;
      if (window.Telegram?.WebApp?.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.selectionChanged();
      }
      (window.EGE?.renderEge || window.EGE_CORE?.renderEge || function(){})();
    }
  }

  function randomMath18Task() {
    const filtered = getFilteredMath18Tasks();
    if (filtered.length === 0) return;
    math18CurrentIdx = Math.floor(Math.random() * filtered.length);
    math18ShowSolution = false;
    if (window.Telegram?.WebApp?.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.impactOccurred('medium');
    }
    (window.EGE?.renderEge || window.EGE_CORE?.renderEge || function(){})();
  }

  function toggleMath18Solution() {
    math18ShowSolution = !math18ShowSolution;
    if (window.Telegram?.WebApp?.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.selectionChanged();
    }
    (window.EGE?.renderEge || window.EGE_CORE?.renderEge || function(){})();
  }

  function viewPhoto(photos, idx, title, desc) {
    const arr = Array.isArray(photos) ? photos : [photos];
    const total = arr.length;
    const normPhotos = arr.map((p, i) => {
      const itemDesc = (total > 1) ? `Часть ${i + 1} из ${total}` : (desc || "");
      if (typeof p === "string") {
        return { url: p, title: title || "", desc: itemDesc };
      }
      return { ...p, title: p.title || title || "", desc: p.desc || itemDesc };
    });

    if (typeof window.openPhotoGallery === "function") {
      window.openPhotoGallery(normPhotos, idx || 0, title || "", desc || "");
    }
  }

  // ==============================================================================
  

  window.EGE_MATH18 = {
    renderMathTask18: renderMathTask18,
    selectMath18Topic: selectMath18Topic,
    onMath18Search: onMath18Search,
    selectMath18Task: selectMath18Task,
    nextMath18Task: nextMath18Task,
    prevMath18Task: prevMath18Task,
    randomMath18Task: randomMath18Task,
    toggleMath18Solution: toggleMath18Solution,
    resetSolution: function() { math18ShowSolution = false; },
    viewPhoto: viewPhoto
  };
})();
