/**
 * app.js — Главный контроллер Mini App 11 «Б».
 * Маршрутизация вкладок, загрузка расписания, ДЗ и звонков.
 * Вынесенные модули:
 * - /static/js/app_calendar.js (календарь, каникулы, выбор даты)
 * - /static/js/app_lightbox.js (галерея фото и зум)
 */

// Application state for 11 "Б"
let currentDate = new Date();
let selectedDateStr = formatDateISO(currentDate);
let activeTab = "schedule";
let isCalendarPicked = false;

// Calendar modal state
let calViewDate = new Date();

function persistTelegramInitDataForChildApps() {
  try {
    const initData = window.Telegram?.WebApp?.initData;
    if (initData && typeof initData === "string" && initData.length > 0) {
      sessionStorage?.setItem("natbirzha_telegram_init_data", initData);
      localStorage?.setItem("natbirzha_telegram_init_data", initData);
      localStorage?.setItem("tg_init_data", initData);
    }
  } catch (_) {}
}

function prepareNatbirzhaNavigation(event) {
  try {
    let initData = window.Telegram?.WebApp?.initData;
    if (!initData) {
      try {
        initData = sessionStorage?.getItem("natbirzha_telegram_init_data") || localStorage?.getItem("natbirzha_telegram_init_data") || localStorage?.getItem("tg_init_data") || "";
      } catch (_) {}
    }
    if (initData) {
      persistTelegramInitDataForChildApps();
      const targetUrl = `/app/natbirzha#tgWebAppData=${encodeURIComponent(initData)}`;
      if (event) {
        event.preventDefault();
        window.location.href = targetUrl;
        return false;
      }
    }
  } catch (_) {}
  return true;
}

window.persistTelegramInitData = persistTelegramInitDataForChildApps;
window.persistTelegramInitDataForChildApps = persistTelegramInitDataForChildApps;
window.prepareNatbirzhaNavigation = prepareNatbirzhaNavigation;

async function initApp() {
  persistTelegramInitDataForChildApps();
  initTabs();
  initCalendarModal();
  initPhotoViewer();
  renderDateSelector();
  await loadUserData();
  loadDutyWidget();
  loadDailyFactWidget();

  const urlParams = new URLSearchParams(window.location.search);
  const roomId = urlParams.get("room");
  const gameType = urlParams.get("game");
  const tabParam = urlParams.get("tab");
  if (roomId) {
    switchTab("games");
    if (window.GAMES && typeof window.GAMES.openOnlineRoom === "function") {
      window.GAMES.openOnlineRoom(roomId, gameType);
    }
  } else if (tabParam === "rpg" || gameType === "rpg" || gameType) {
    switchTab("games");
  } else if (tabParam) {
    switchTab(tabParam);
  } else {
    loadTabContent(activeTab);
  }
}

function switchTab(tab) {
  const btn = document.querySelector(`.tab-btn[data-tab="${tab}"]`);
  if (btn) {
    btn.click();
  } else {
    if (activeTab === "games" && tab !== "games") {
      if (window.GAMES && typeof window.GAMES.cleanup === "function") {
        window.GAMES.cleanup();
      }
    }
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-pane").forEach((p) => p.classList.add("hidden"));
    const targetPane = document.getElementById(`pane-${tab}`);
    if (targetPane) targetPane.classList.remove("hidden");

    const dateWrapper = document.getElementById("date-selector-wrapper");
    const dutyWidget = document.getElementById("duty-widget");
    const factWidget = document.getElementById("daily-fact-widget");
    if (tab === "bells" || tab === "ege" || tab === "games") {
      if (dateWrapper) dateWrapper.classList.add("hidden");
      if (dutyWidget) dutyWidget.classList.add("hidden");
    } else {
      if (dateWrapper) dateWrapper.classList.remove("hidden");
      if (dutyWidget) dutyWidget.classList.remove("hidden");
    }

    if (factWidget) {
      if (tab === "schedule") {
        const content = document.getElementById("fact-content");
        if (content && content.textContent && content.textContent.trim()) {
          factWidget.classList.remove("hidden");
        }
      } else {
        factWidget.classList.add("hidden");
      }
    }

    activeTab = tab;
    loadTabContent(tab);
  }
}
window.switchTab = switchTab;

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initApp);
} else {
  initApp();
}

async function loadUserData() {
  const userBadge = document.getElementById("user-badge");
  if (!userBadge) return;

  userBadge.textContent = "Загрузка...";

  // Дожидаемся инициализации Telegram WebApp SDK (загружается async)
  if (typeof window.waitForTelegramWebApp === "function") {
    await window.waitForTelegramWebApp();
  }
  try {
    const me = await api.getMe();
    window.currentUser = me;
    if (window.GAMES && typeof window.GAMES.updateTesterStatus === "function") {
      // ADMIN_ID is an effective server-side tester grant even when the
      // legacy users row has not yet been migrated to role="admin".
      window.GAMES.updateTesterStatus(Boolean(me && (me.is_tester || me.role === "admin")));
    }
    if (me && me.full_name) {
      const roleTag = me.role === "admin" ? " • 👑 Админ" : "";
      userBadge.textContent = me.full_name + roleTag;
    } else {
      userBadge.textContent = "Ученик 11 «Б»";
    }
  } catch (e) {
    console.warn("Could not load user data:", e.message);
    userBadge.textContent = "Ученик 11 «Б»";
  }
}





async function loadDutyWidget() {
  const badge = document.getElementById("duty-badge");
  const members = document.getElementById("duty-members");
  if (!badge || !members) return;

  try {
    const data = await api.getDuty();
    badge.textContent = data.name || `Группа ${data.current_group}`;
    members.textContent = data.members || "Состав уточняется";
  } catch (e) {
    console.warn("Could not load duty data:", e.message);
    const widget = document.getElementById("duty-widget");
    if (widget) widget.classList.add("hidden");
  }
}

async function loadDailyFactWidget() {
  const badge = document.getElementById("fact-category");
  const title = document.getElementById("fact-title");
  const content = document.getElementById("fact-content");
  const widget = document.getElementById("daily-fact-widget");
  if (!badge || !title || !content || !widget) return;

  try {
    const data = await api.getDailyFact();
    if (data && data.fact) {
      badge.textContent = data.category || "Факт";
      title.textContent = data.title || "Знаете ли вы?";
      content.textContent = data.fact;
      if (activeTab === "schedule") {
        widget.classList.remove("hidden");
      } else {
        widget.classList.add("hidden");
      }
    } else {
      widget.classList.add("hidden");
    }
  } catch (e) {
    console.warn("Could not load daily fact:", e.message);
    widget.classList.add("hidden");
  }
}



// Tab navigation
function initTabs() {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      if (tab === activeTab) return;

      if (activeTab === "games" && tab !== "games") {
        if (window.GAMES && typeof window.GAMES.cleanup === "function") {
          window.GAMES.cleanup();
        }
      }

      haptic.selection();
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      document.querySelectorAll(".tab-pane").forEach((p) => p.classList.add("hidden"));
      const targetPane = document.getElementById(`pane-${tab}`);
      if (targetPane) targetPane.classList.remove("hidden");

      // Hide date selector and duty widget on bells, ege, and games tabs
      const dateWrapper = document.getElementById("date-selector-wrapper");
      const dutyWidget = document.getElementById("duty-widget");
      if (tab === "bells" || tab === "ege" || tab === "games") {
        if (dateWrapper) dateWrapper.classList.add("hidden");
        if (dutyWidget) dutyWidget.classList.add("hidden");
      } else {
        if (dateWrapper) dateWrapper.classList.remove("hidden");
        if (dutyWidget) dutyWidget.classList.remove("hidden");
      }

      // Interesting fact widget is strictly visible ONLY on the "schedule" (Уроки) tab
      const factWidget = document.getElementById("daily-fact-widget");
      if (factWidget) {
        if (tab === "schedule") {
          const content = document.getElementById("fact-content");
          if (content && content.textContent && content.textContent.trim()) {
            factWidget.classList.remove("hidden");
          }
        } else {
          factWidget.classList.add("hidden");
        }
      }

      activeTab = tab;
      loadTabContent(tab);
    });
  });
}


async function loadTabContent(tab) {
  if (tab === "schedule") await loadSchedule();
  else if (tab === "homework") await loadHomework();
  else if (tab === "bells") await loadBells();
  else if (tab === "ege") {
    if (window.EGE && typeof window.EGE.init === "function") {
      window.EGE.init();
    }
  } else if (tab === "games") {
    if (window.GAMES && typeof window.GAMES.init === "function") {
      window.GAMES.init();
    }
  }
}

// --- SCHEDULE ---
async function loadSchedule() {
  const list = document.getElementById("schedule-list");
  if (!list) return;

  list.innerHTML = `<div class="text-center py-8 text-slate-400 text-sm animate-pulse">Загрузка расписания 11 «Б»...</div>`;

  try {
    const data = await api.getSchedule(selectedDateStr);
    
    if (data.day_status === "vacation") {
      list.innerHTML = `
        <div class="text-center py-12 theme-card rounded-2xl p-6 border-2 border-amber-500/30 bg-amber-50/50 dark:bg-amber-950/20">
          <span class="text-5xl">🌴</span>
          <h3 class="mt-3 text-base font-bold text-amber-600 dark:text-amber-400">🎉 ${data.status_text}!</h3>
          <p class="mt-1 text-xs text-slate-500">Каникулы — уроков нет, отдыхаем!</p>
        </div>
      `;
      return;
    }

    if (!data.lessons || data.lessons.length === 0) {
      const isWeekend = data.day_status === "weekend";
      list.innerHTML = `
        <div class="text-center py-12 theme-card rounded-2xl p-6">
          <span class="text-5xl">${isWeekend ? "🏖" : "📅"}</span>
          <h3 class="mt-3 text-sm font-bold text-slate-700 dark:text-slate-200">${isWeekend ? data.status_text : "Уроков нет"}</h3>
          <p class="mt-1 text-xs text-slate-500">${isWeekend ? "Выходной день — уроков нет!" : "Расписание на этот день еще не заполнено."}</p>
        </div>
      `;
      return;
    }

    list.innerHTML = "";
    data.lessons.forEach((l) => {
      const card = document.createElement("div");
      card.className = "theme-card rounded-2xl p-4 flex items-center justify-between shadow-sm transition-all";

      let statusBadge = "";


      const commentText = l.comment ? `<p class="text-xs text-amber-600 mt-1 italic">${l.comment}</p>` : "";
      const subjectStyle = l.is_cancelled ? "line-through opacity-50" : "font-semibold";

      card.innerHTML = `
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 rounded-xl bg-blue-50 dark:bg-slate-800 text-blue-600 font-bold flex items-center justify-center text-sm shrink-0">
            ${l.lesson_number}
          </div>
          <div>
            <div class="flex items-center gap-2">
              <h3 class="${subjectStyle} text-sm subject-title text-slate-700 dark:text-slate-100">${l.subject_name}</h3>
              ${statusBadge}
            </div>
            <p class="text-xs text-slate-400 mt-0.5">${l.start_time} - ${l.end_time}</p>
            ${commentText}
          </div>
        </div>
      `;

      list.appendChild(card);
    });
  } catch (err) {
    list.innerHTML = `<div class="text-center py-6 text-red-500 text-sm">Ошибка: ${err.message}</div>`;
  }
}

// --- HOMEWORK (ЧЕК-ЛИСТ ДЗ) ---
async function loadHomework() {
  const list = document.getElementById("homework-list");
  if (!list) return;

  const todayStr = formatDateISO(new Date());
  const isPast = selectedDateStr < todayStr;

  list.innerHTML = `<div class="text-center py-8 text-slate-400 text-sm animate-pulse">Загрузка заданий...</div>`;

  try {
    const items = await api.getHomework(selectedDateStr);
    if (!items || items.length === 0) {
      list.innerHTML = `
        <div class="text-center py-12 theme-card rounded-2xl p-6">
          <span class="text-4xl">🎉</span>
          <p class="mt-3 text-sm font-medium text-slate-400">На этот день заданий нет! Можно отдыхать.</p>
        </div>
      `;
      return;
    }

    list.innerHTML = "";

    items.forEach((hw) => {
      const card = document.createElement("div");
      const borderClass = isPast
        ? "border-l-slate-400 dark:border-l-slate-600 opacity-80"
        : (hw.is_completed ? "border-l-emerald-500 opacity-60" : "border-l-blue-500");

      card.className = `theme-card rounded-2xl p-4 shadow-sm transition-all border-l-4 ${borderClass}`;

      const titleStr = hw.title ? `<span class="text-xs text-slate-400"> • ${hw.title}</span>` : "";

      let attHtml = "";
      const photos = (hw.attachments || []).filter(a => a.type === "photo" && a.url);
      const docs = (hw.attachments || []).filter(a => a.type === "document");

      if (photos.length > 0 || docs.length > 0) {
        let photoThumbsHtml = "";
        if (photos.length > 0) {
          const thumbs = photos.map((p, pIdx) => `
            <div class="pv-thumb relative w-16 h-16 sm:w-20 sm:h-20 rounded-xl overflow-hidden shadow-sm border border-slate-200/80 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 cursor-pointer shrink-0 hover:scale-105 active:scale-95 transition-all group" data-idx="${pIdx}">
              <img src="${p.url}" alt="Фото задания" loading="lazy" class="w-full h-full object-cover" />
              <div class="absolute inset-0 bg-black/0 group-hover:bg-black/15 transition-colors flex items-end justify-end p-1">
                <span class="text-[9px] bg-black/60 text-white font-bold px-1 rounded shadow">🔍</span>
              </div>
            </div>
          `).join("");

          photoThumbsHtml = `
            <div class="mt-2.5 flex items-center gap-2 overflow-x-auto pb-1 max-w-full">
              ${thumbs}
            </div>
          `;
        }

        let docsHtml = "";
        if (docs.length > 0) {
          const docLinks = docs.map(d => `
            <a href="${d.url || '#'}" download="${d.file_name || 'файл'}" target="_blank" class="inline-flex items-center gap-1.5 text-[11px] font-semibold px-2.5 py-1.5 rounded-xl bg-blue-50 dark:bg-slate-800 text-blue-600 dark:text-blue-400 border border-blue-100 dark:border-slate-700 hover:bg-blue-100 transition-colors">
              <span>📄</span>
              <span class="truncate max-w-[130px]">${d.file_name || 'Документ'}</span>
              <span>⬇️</span>
            </a>
          `).join("");

          docsHtml = `
            <div class="mt-2 flex items-center gap-1.5 flex-wrap">
              ${docLinks}
            </div>
          `;
        }

        attHtml = photoThumbsHtml + docsHtml;
      }

      const toggleBtnHtml = isPast ? "" : `
        <button class="toggle-btn w-7 h-7 rounded-xl border-2 flex items-center justify-center transition-all shrink-0 mt-0.5 ${
          hw.is_completed ? "bg-emerald-500 border-emerald-500 text-white shadow-sm shadow-emerald-500/30" : "border-slate-300 dark:border-slate-600 hover:border-blue-500"
        }" data-id="${hw.id}" title="Отметить выполненным">
          ${hw.is_completed ? "✓" : ""}
        </button>
      `;

      const titleCompletedClass = (!isPast && hw.is_completed) ? "line-through opacity-60" : "";

      card.innerHTML = `
        <div class="flex items-start justify-between gap-3">
          <div class="flex-1">
            <div class="flex items-center gap-2">
              <h3 class="font-bold text-sm subject-title text-slate-700 dark:text-slate-100 ${titleCompletedClass}">${hw.subject_name}</h3>
              ${titleStr}
            </div>
            <p class="text-sm mt-2 leading-relaxed homework-desc text-slate-600 dark:text-slate-200 whitespace-pre-line">${hw.description}</p>
            ${attHtml}
          </div>
          ${toggleBtnHtml}
        </div>
      `;

      // При клике на превью открываем полноэкранный просмотр фото
      if (photos.length > 0) {
        const thumbEls = card.querySelectorAll(".pv-thumb");
        thumbEls.forEach(th => {
          th.addEventListener("click", () => {
            const idx = parseInt(th.getAttribute("data-idx"), 10) || 0;
            openPhotoGallery(photos, idx, hw.subject_name, hw.description);
          });
        });
      }

      // Interactive Toggle handler (только для актуальных ДЗ)
      const toggleBtn = card.querySelector(".toggle-btn");
      if (toggleBtn) {
        toggleBtn.addEventListener("click", async () => {
          haptic.impact("medium");
          try {
            const res = await api.toggleHomework(hw.id);
            hw.is_completed = res.is_completed;
            loadHomework();
          } catch (e) {
            alert("Не удалось изменить статус");
          }
        });
      }

      list.appendChild(card);
    });
  } catch (err) {
    list.innerHTML = `<div class="text-center py-6 text-red-500 text-sm">Ошибка: ${err.message}</div>`;
  }
}

// --- BELLS (ЗВОНКИ) ---
async function loadBells() {
  const list = document.getElementById("bells-list");
  if (!list) return;

  list.innerHTML = `<div class="text-center py-8 text-slate-400 text-sm animate-pulse">Загрузка расписания звонков...</div>`;


  try {
    const bells = await api.getBells();
    list.innerHTML = "";
    bells.forEach((b) => {
      const card = document.createElement("div");
      card.className = "theme-card rounded-2xl p-4 flex items-center justify-between shadow-sm border border-slate-200/40 dark:border-slate-800/80 hover:scale-[1.01] transition-all";
      
      let breakBadge = "";
      if (b.break_duration && b.break_duration > 0) {
        const isLong = b.break_duration >= 15;
        breakBadge = `
          <span class="inline-flex items-center text-[10px] font-bold px-2 py-0.5 rounded-full ${
            isLong 
              ? "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800" 
              : "bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400 border border-amber-200 dark:border-amber-800"
          }">
            ${b.break_duration} мин. перемена
          </span>
        `;
      } else {
        breakBadge = `<span class="text-[10px] font-medium text-slate-400">Конец уроков 🎉</span>`;
      }

      card.innerHTML = `
        <div class="flex items-center gap-3.5">
          <div class="w-9 h-9 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-500 text-white font-black flex items-center justify-center text-sm shadow-md shadow-blue-500/20">
            ${b.lesson_number}
          </div>
          <div>
            <span class="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">${b.lesson_number} урок</span>
            <span class="text-sm font-semibold font-mono text-slate-500 dark:text-slate-400">${b.start_time} – ${b.end_time}</span>
          </div>

        </div>
        <div class="text-right">
          ${breakBadge}
        </div>
      `;
      list.appendChild(card);
    });
  } catch (err) {
    list.innerHTML = `<div class="text-center py-6 text-red-500 text-sm">Ошибка: ${err.message}</div>`;
  }
}

