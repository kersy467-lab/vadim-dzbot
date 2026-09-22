/**
 * app_calendar.js — Академический календарь учебного года 11 «Б».
 * Расчет каникул, рабочих суббот, модальный календарь и горизонтальная лента дней.
 */
(function () {
  'use strict';

  // Academic Calendar helpers in JS
  const VACATIONS = [
    { start: "2026-10-26", end: "2026-11-03", name: "Осенние каникулы" },
    { start: "2026-12-31", end: "2027-01-10", name: "Зимние каникулы" },
    { start: "2027-03-27", end: "2027-04-04", name: "Весенние каникулы" },
    { start: "2027-05-27", end: "2027-08-31", name: "Летние каникулы" }
  ];

  const WORKING_SATURDAYS = new Set(["2027-02-20"]);

  const MONTHS_RU = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
  ];

  const DAYS_SHORT = ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"];

  function formatDateISO(d) {
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  function getDayType(isoStr, dayOfWeek) {
    for (const v of VACATIONS) {
      if (isoStr >= v.start && isoStr <= v.end) {
        return "vacation";
      }
    }
    if (WORKING_SATURDAYS.has(isoStr)) {
      return "working_sat";
    }
    if (dayOfWeek === 0 || dayOfWeek === 6) {
      return "weekend";
    }
    return "regular";
  }

// --- INTERACTIVE CALENDAR MODAL ---
function initCalendarModal() {
  const openBtn = document.getElementById("open-calendar-btn");
  const closeBtn = document.getElementById("cal-close-btn");
  const modal = document.getElementById("calendar-modal");
  const prevBtn = document.getElementById("cal-prev-month");
  const nextBtn = document.getElementById("cal-next-month");
  const todayBtn = document.getElementById("cal-today-btn");

  if (openBtn) {
    openBtn.addEventListener("click", () => {
      haptic.impact("light");
      const [y, m, d] = selectedDateStr.split("-").map(Number);
      calViewDate = new Date(y, m - 1, 1);
      renderCalendarGrid();
      modal.classList.remove("hidden");
    });
  }

  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      haptic.selection();
      modal.classList.add("hidden");
    });
  }

  if (prevBtn) {
    prevBtn.addEventListener("click", () => {
      haptic.selection();
      calViewDate.setMonth(calViewDate.getMonth() - 1);
      renderCalendarGrid();
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener("click", () => {
      haptic.selection();
      calViewDate.setMonth(calViewDate.getMonth() + 1);
      renderCalendarGrid();
    });
  }

  if (todayBtn) {
    todayBtn.addEventListener("click", () => {
      haptic.impact("medium");
      const today = new Date();
      selectedDateStr = formatDateISO(today);
      isCalendarPicked = false;
      modal.classList.add("hidden");
      renderDateSelector();
      loadTabContent(activeTab);
    });
  }
}

function renderCalendarGrid() {
  const monthTitle = document.getElementById("cal-month-title");
  const daysGrid = document.getElementById("cal-days-grid");
  if (!monthTitle || !daysGrid) return;

  const year = calViewDate.getFullYear();
  const month = calViewDate.getMonth();
  monthTitle.textContent = `${MONTHS_RU[month]} ${year}`;

  daysGrid.innerHTML = "";

  const firstDayOfMonth = new Date(year, month, 1);
  const lastDayOfMonth = new Date(year, month + 1, 0);

  let firstDayIndex = firstDayOfMonth.getDay(); // 0 is Sun
  firstDayIndex = (firstDayIndex === 0 ? 6 : firstDayIndex - 1); // convert to Mon=0

  const totalDays = lastDayOfMonth.getDate();

  // Blank days before first day
  for (let i = 0; i < firstDayIndex; i++) {
    const blank = document.createElement("div");
    blank.className = "py-2";
    daysGrid.appendChild(blank);
  }

  const todayIso = formatDateISO(new Date());

  for (let day = 1; day <= totalDays; day++) {
    const dObj = new Date(year, month, day);
    const iso = formatDateISO(dObj);
    const dayOfWeek = dObj.getDay();
    const dayType = getDayType(iso, dayOfWeek);
    const isSelected = (iso === selectedDateStr);
    const isToday = (iso === todayIso);

    const btn = document.createElement("button");
    btn.className = `py-1.5 px-1 rounded-xl text-xs font-semibold flex flex-col items-center justify-center transition-all ${
      isSelected
        ? "bg-blue-600 text-white shadow-md shadow-blue-500/30 scale-105 font-bold"
        : isToday
        ? "border-2 border-blue-500 text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-slate-800"
        : dayType === "vacation"
        ? "bg-amber-100/70 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 hover:bg-amber-200"
        : "text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
    }`;

    let badge = "";
    if (dayType === "vacation") badge = `<span class="text-[9px] block">🌴</span>`;
    else if (dayType === "working_sat") badge = `<span class="text-[9px] block">💼</span>`;

    btn.innerHTML = `
      <span>${day}</span>
      ${badge}
    `;

    btn.addEventListener("click", () => {
      haptic.impact("light");
      selectedDateStr = iso;
      isCalendarPicked = true;
      document.getElementById("calendar-modal").classList.add("hidden");
      renderDateSelector();
      loadTabContent(activeTab);
    });

    daysGrid.appendChild(btn);
  }
}

// Date selector horizontal strip
function renderDateSelector() {
  const container = document.getElementById("date-selector");
  if (!container) return;

  container.innerHTML = "";
  const [y, m, d] = selectedDateStr.split("-").map(Number);
  const baseDate = new Date(y, m - 1, d);

  const dayOfWeek = baseDate.getDay();
  const diff = baseDate.getDate() - dayOfWeek + (dayOfWeek === 0 ? -6 : 1); // Monday
  const startOfWeek = new Date(baseDate);
  startOfWeek.setDate(diff);

  for (let i = 0; i < 6; i++) {
    const d = new Date(startOfWeek);
    d.setDate(startOfWeek.getDate() + i);
    const iso = formatDateISO(d);
    const isSelected = (iso === selectedDateStr);
    const dayType = getDayType(iso, d.getDay());

    const btn = document.createElement("button");
    btn.className = `flex flex-col items-center justify-center py-2 px-3 rounded-2xl text-xs transition-all ${
      isSelected
        ? "bg-blue-600 text-white font-bold shadow-md shadow-blue-500/20 scale-105"
        : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200"
    }`;

    let icon = "";
    if (dayType === "vacation") icon = " 🌴";

    btn.innerHTML = `
      <span class="text-[10px] uppercase opacity-75">${DAYS_SHORT[d.getDay()]}${icon}</span>
      <span class="text-sm font-semibold">${d.getDate()}</span>
    `;

    btn.addEventListener("click", () => {
      haptic.impact("light");
      selectedDateStr = iso;
      isCalendarPicked = false;
      renderDateSelector();
      if (activeTab === "schedule") loadSchedule();
      if (activeTab === "homework") loadHomework();
    });

    container.appendChild(btn);
  }
}



  // Export to window
  window.formatDateISO = formatDateISO;
  window.getDayType = getDayType;
  window.initCalendarModal = initCalendarModal;
  window.renderCalendarGrid = renderCalendarGrid;
  window.renderDateSelector = renderDateSelector;
  window.VACATIONS = VACATIONS;
  window.WORKING_SATURDAYS = WORKING_SATURDAYS;
  window.MONTHS_RU = MONTHS_RU;
  window.DAYS_SHORT = DAYS_SHORT;
})();
