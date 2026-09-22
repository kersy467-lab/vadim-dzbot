/**
 * app.js — Главный контроллер Mini App 11 «Б».
 * Маршрутизация вкладок, загрузка расписания, ДЗ и звонков.
 * Вынесенные модули:
 * - /static/js/app_calendar.js (календарь, каникулы, выбор даты)
 * - /static/js/app_lightbox.js (галерея фото и зум)
 */

// Application state for 11 "Б"
let currentDate = new Date();
window.selectedDateStr = window.selectedDateStr || (typeof formatDateISO === "function" ? formatDateISO(currentDate) : currentDate.toISOString().split("T")[0]);
let selectedDateStr = window.selectedDateStr;
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
  if (tab === "homework") tab = "schedule";
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
  if (tab === "schedule" || tab === "homework") {
    const targetDate = window.selectedDateStr || (typeof selectedDateStr !== "undefined" ? selectedDateStr : null);
    if (typeof window.loadSchedule === "function") {
      await window.loadSchedule(targetDate);
    } else if (typeof loadSchedule === "function") {
      await loadSchedule(targetDate);
    }
  } else if (tab === "bells") {
    await loadBells();
  } else if (tab === "ege") {
    if (window.EGE && typeof window.EGE.init === "function") {
      window.EGE.init();
    }
  } else if (tab === "games") {
    if (window.GAMES && typeof window.GAMES.init === "function") {
      window.GAMES.init();
    }
  }
}
window.loadTabContent = loadTabContent;

// --- SCHEDULE & HOMEWORK (Делегировано в app_schedule.js) ---
// window.loadSchedule и window.loadHomework определены в app_schedule.js

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

