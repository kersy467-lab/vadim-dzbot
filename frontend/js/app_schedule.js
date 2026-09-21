/**
 * app_schedule.js — Модуль отображения расписания уроков и прикреплённых домашних заданий.
 * Выводит ДЗ непосредственно под каждым уроком, поддерживает чек-лист и просмотр медиа.
 */
(function () {
  'use strict';

  function normalizeSubject(str) {
    return String(str || "")
      .trim()
      .toLowerCase()
      .replace(/ё/g, "е")
      .replace(/[^a-zа-я0-9]/gi, "");
  }

  function isSubjectMatch(hwSubj, lessonSubj) {
    const s1 = normalizeSubject(hwSubj);
    const s2 = normalizeSubject(lessonSubj);
    if (!s1 || !s2) return false;
    if (s1 === s2) return true;
    if (s1.length >= 4 && s2.length >= 4 && (s1.includes(s2) || s2.includes(s1))) {
      return true;
    }
    const aliases = [
      ["алгебра", "матем", "математика"],
      ["общество", "обществознание"],
      ["информатика", "инф"],
      ["литература", "литра"],
      ["физкультура", "физра"],
      ["русский", "русскийязык", "рус"],
      ["английский", "английскийязык", "англ"],
      ["геометрия", "геом"],
      ["биология", "био"],
      ["география", "геогр"],
      ["история", "вис", "всеобщаяистория"]
    ];
    for (const group of aliases) {
      const m1 = group.some(a => s1.includes(normalizeSubject(a)));
      const m2 = group.some(a => s2.includes(normalizeSubject(a)));
      if (m1 && m2) return true;
    }
    return false;
  }

  function renderHomeworkSubcard(hw, isPast, showSubjectName = false) {
    const isDone = !isPast && hw.is_completed;
    const descClass = isDone ? "line-through opacity-60 text-slate-400" : "text-slate-700 dark:text-slate-200";
    const subjBadge = showSubjectName ? `<span class="text-xs font-bold text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-slate-800 px-2 py-0.5 rounded-lg mr-1">${hw.subject_name}</span>` : "";
    const titleStr = hw.title ? `<span class="text-[11px] font-semibold text-slate-400">• ${hw.title}</span>` : "";

    let attHtml = "";
    const photos = (hw.attachments || []).filter(a => a.type === "photo" && a.url);
    const docs = (hw.attachments || []).filter(a => a.type === "document");

    if (photos.length > 0 || docs.length > 0) {
      let photoThumbsHtml = "";
      if (photos.length > 0) {
        const thumbs = photos.map((p, pIdx) => `
          <div class="pv-thumb relative w-16 h-16 sm:w-20 sm:h-20 rounded-xl overflow-hidden shadow-sm border border-slate-200/80 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 cursor-pointer shrink-0 hover:scale-105 active:scale-95 transition-all group" data-hw-id="${hw.id}" data-idx="${pIdx}">
            <img src="${p.url}" alt="Фото задания" loading="lazy" class="w-full h-full object-cover" />
            <div class="absolute inset-0 bg-black/0 group-hover:bg-black/15 transition-colors flex items-end justify-end p-1">
              <span class="text-[9px] bg-black/60 text-white font-bold px-1 rounded shadow">🔍</span>
            </div>
          </div>
        `).join("");

        photoThumbsHtml = `
          <div class="mt-2 flex items-center gap-2 overflow-x-auto pb-1 max-w-full">
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

    return `
      <div class="hw-item-subcard flex items-start justify-between gap-3 bg-slate-50/70 dark:bg-slate-800/40 rounded-xl p-3 border border-slate-100 dark:border-slate-800/80">
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-1.5 mb-1 flex-wrap">
            <span class="text-xs">📝</span>
            ${subjBadge}
            <span class="text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">ДЗ:</span>
            ${titleStr}
          </div>
          <p class="text-sm leading-relaxed whitespace-pre-line ${descClass}">${hw.description}</p>
          ${attHtml}
        </div>
        ${toggleBtnHtml}
      </div>
    `;
  }

  function bindHomeworkEvents(container, homeworks) {
    const hwMap = new Map(homeworks.map(h => [h.id, h]));

    container.querySelectorAll(".pv-thumb").forEach(th => {
      th.addEventListener("click", () => {
        const hwId = parseInt(th.getAttribute("data-hw-id"), 10);
        const idx = parseInt(th.getAttribute("data-idx"), 10) || 0;
        const hw = hwMap.get(hwId);
        if (hw) {
          const photos = (hw.attachments || []).filter(a => a.type === "photo" && a.url);
          if (typeof window.openPhotoGallery === "function") {
            window.openPhotoGallery(photos, idx, hw.subject_name, hw.description);
          }
        }
      });
    });

    container.querySelectorAll(".toggle-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const hwId = parseInt(btn.getAttribute("data-id"), 10);
        if (window.haptic && typeof window.haptic.impact === "function") {
          window.haptic.impact("medium");
        }
        try {
          const res = await window.api.toggleHomework(hwId);
          const hw = hwMap.get(hwId);
          if (hw) {
            hw.is_completed = res.is_completed;
          }
          await loadSchedule();
        } catch (e) {
          alert("Не удалось изменить статус задания");
        }
      });
    });
  }

  async function loadSchedule(targetDate) {
    const list = document.getElementById("schedule-list");
    if (!list) return;

    if (targetDate) {
      window.selectedDateStr = targetDate;
    }
    const todayStr = typeof formatDateISO === "function" ? formatDateISO(new Date()) : new Date().toISOString().split("T")[0];
    const dateStr = targetDate || window.selectedDateStr || todayStr;
    const isPast = dateStr < todayStr;

    list.innerHTML = `<div class="text-center py-8 text-slate-400 text-sm animate-pulse">Загрузка уроков и заданий...</div>`;

    try {
      const [data, hwItems] = await Promise.all([
        window.api.getSchedule(dateStr).catch(() => ({ lessons: [] })),
        window.api.getHomework(dateStr).catch(() => [])
      ]);

      const lessons = data.lessons || [];
      const homeworks = Array.isArray(hwItems) ? hwItems : [];

      if (data.day_status === "vacation") {
        let hwHtml = "";
        if (homeworks.length > 0) {
          hwHtml = `
            <div class="mt-4 pt-3 border-t border-slate-200 dark:border-slate-800 space-y-2.5">
              <h4 class="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Задания на эту дату:</h4>
              ${homeworks.map(hw => renderHomeworkSubcard(hw, isPast, true)).join("")}
            </div>
          `;
        }
        list.innerHTML = `
          <div class="text-center py-10 theme-card rounded-2xl p-6 border-2 border-amber-500/30 bg-amber-50/50 dark:bg-amber-950/20">
            <span class="text-5xl">🌴</span>
            <h3 class="mt-3 text-base font-bold text-amber-600 dark:text-amber-400">🎉 ${data.status_text || "Каникулы"}!</h3>
            <p class="mt-1 text-xs text-slate-500">Каникулы — уроков нет, отдыхаем!</p>
          </div>
          ${hwHtml}
        `;
        bindHomeworkEvents(list, homeworks);
        return;
      }

      if (lessons.length === 0) {
        const isWeekend = data.day_status === "weekend";
        let hwHtml = "";
        if (homeworks.length > 0) {
          hwHtml = `
            <div class="mt-4 pt-3 border-t border-slate-200 dark:border-slate-800 space-y-2.5">
              <h4 class="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Задания на эту дату:</h4>
              ${homeworks.map(hw => renderHomeworkSubcard(hw, isPast, true)).join("")}
            </div>
          `;
        }
        list.innerHTML = `
          <div class="text-center py-10 theme-card rounded-2xl p-6">
            <span class="text-5xl">${isWeekend ? "🏖" : "📅"}</span>
            <h3 class="mt-3 text-sm font-bold text-slate-700 dark:text-slate-200">${isWeekend ? (data.status_text || "Выходной") : "Уроков нет"}</h3>
            <p class="mt-1 text-xs text-slate-500">${isWeekend ? "Выходной день — уроков нет!" : "Расписание на этот день еще не заполнено."}</p>
          </div>
          ${hwHtml}
        `;
        bindHomeworkEvents(list, homeworks);
        return;
      }

      list.innerHTML = "";
      const matchedHwIds = new Set();

      lessons.forEach((l) => {
        const card = document.createElement("div");
        card.className = "theme-card rounded-2xl p-4 shadow-sm transition-all border border-slate-200/50 dark:border-slate-800/80 space-y-3";

        const subjectStyle = l.is_cancelled ? "line-through opacity-50" : "font-semibold";
        const commentText = l.comment ? `<p class="text-xs text-amber-600 dark:text-amber-400 mt-0.5 italic">${l.comment}</p>` : "";

        const matchedHws = homeworks.filter(hw => {
          if (isSubjectMatch(hw.subject_name, l.subject_name)) {
            matchedHwIds.add(hw.id);
            return true;
          }
          return false;
        });

        let hwBadge = "";
        if (matchedHws.length > 0) {
          const allCompleted = matchedHws.every(h => h.is_completed);
          if (allCompleted) {
            hwBadge = `<span class="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800 shrink-0">✓ Сделано</span>`;
          } else {
            hwBadge = `<span class="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-800 shrink-0">📝 ДЗ</span>`;
          }
        }

        let hwListHtml = "";
        if (matchedHws.length > 0) {
          hwListHtml = `
            <div class="space-y-2 pt-2.5 border-t border-slate-100 dark:border-slate-800/80">
              ${matchedHws.map(hw => renderHomeworkSubcard(hw, isPast)).join("")}
            </div>
          `;
        }

        card.innerHTML = `
          <div class="flex items-start justify-between gap-3">
            <div class="flex items-center gap-3">
              <div class="w-8 h-8 rounded-xl bg-blue-50 dark:bg-slate-800 text-blue-600 dark:text-blue-400 font-bold flex items-center justify-center text-sm shrink-0">
                ${l.lesson_number}
              </div>
              <div>
                <div class="flex items-center gap-2">
                  <h3 class="${subjectStyle} text-sm subject-title text-slate-800 dark:text-slate-100">${l.subject_name}</h3>
                </div>
                <p class="text-xs text-slate-400 mt-0.5">${l.start_time} - ${l.end_time}</p>
                ${commentText}
              </div>
            </div>
            ${hwBadge}
          </div>
          ${hwListHtml}
        `;

        list.appendChild(card);
      });

      const unmatchedHws = homeworks.filter(hw => !matchedHwIds.has(hw.id));
      if (unmatchedHws.length > 0) {
        const extraCard = document.createElement("div");
        extraCard.className = "mt-4 pt-2 space-y-2.5";
        extraCard.innerHTML = `
          <div class="flex items-center gap-1.5 px-1">
            <span class="text-xs">📌</span>
            <h4 class="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Дополнительные задания:</h4>
          </div>
          <div class="space-y-2.5">
            ${unmatchedHws.map(hw => {
              return `
                <div class="theme-card rounded-2xl p-4 shadow-sm border border-slate-200/50 dark:border-slate-800/80">
                  <div class="text-xs font-bold text-slate-700 dark:text-slate-200 mb-2">${hw.subject_name}</div>
                  ${renderHomeworkSubcard(hw, isPast)}
                </div>
              `;
            }).join("")}
          </div>
        `;
        list.appendChild(extraCard);
      }

      bindHomeworkEvents(list, homeworks);
    } catch (err) {
      list.innerHTML = `<div class="text-center py-6 text-red-500 text-sm">Ошибка: ${err.message}</div>`;
    }
  }

  window.loadSchedule = loadSchedule;
  window.loadHomework = loadSchedule;
})();
