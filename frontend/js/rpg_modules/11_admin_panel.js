// ============================================================
// 11_admin_panel.js — Админ-Панель управления RPG
// Чит-коды: золото, уровень, предметы из каталога и сброс игроков
// ============================================================

window.RPG = window.RPG || {};
window._adminPlayersList = window._adminPlayersList || null;
window._adminCatalogItems = window._adminCatalogItems || (typeof window._DEFAULT_RPG_CATALOG !== "undefined" ? window._DEFAULT_RPG_CATALOG : []);
window._adminSelectedTarget = window._adminSelectedTarget || "";
window._adminSubTab = window._adminSubTab || "actions"; // "actions" | "slots"
window._fetchingAdminPlayers = false;
window._fetchingAdminCatalog = false;

function showAdminNotice(msg) {
  if (window.Telegram?.WebApp?.showAlert) {
    try { window.Telegram.WebApp.showAlert(msg); return; } catch (_) {}
  }
  alert(msg);
}

function getDefaultAdminPlayers() {
  const p = window.RPG_STATE?.profile;
  const uid = p?.user_id || 1, tg = p?.tg_id || 1053722876, name = p?.user_name || "Я (Администратор)", lvl = p?.level || 1, gold = p?.gold || 0;
  return [
    { user_id: uid, tg_id: tg, name: name, level: lvl, gold: gold, hero_icon: "👑" },
    { user_id: 1, tg_id: 7755842535, name: "Не Вадим", level: 28, gold: 1645000, hero_icon: "🦌" },
    { user_id: 5, tg_id: 1440393642, name: "Михаил Исайкин", level: 43, gold: 373000, hero_icon: "🔮" },
    { user_id: 24, tg_id: 6926859962, name: "Макар", level: 35, gold: 104000, hero_icon: "🔮" },
    { user_id: 17, tg_id: 5181261098, name: "Глеб", level: 21, gold: 146000, hero_icon: "🔮" },
    { user_id: 4, tg_id: 1053722876, name: "notariuspiva", level: 18, gold: 4236000, hero_icon: "🪝" },
  ];
}

function updateAdminModalDOM() {
  const backdrop = document.getElementById("rpg-admin-modal-backdrop");
  if (backdrop && RPG_STATE.adminModalOpen) {
    backdrop.outerHTML = renderAdminModalHTML();
  } else {
    renderRoot();
  }
}

function renderAdminFloatingBadgeHTML() {
  const activeTestSlot = localStorage.getItem("admin_test_tg_uid");
  const currentSlotLabel = activeTestSlot ? `🧪 #${activeTestSlot}` : `👑 Админ`;
  return `<div id="rpg-admin-floating-btn" class="fixed bottom-20 left-2.5 z-40">
    <button onclick="window.RPG.toggleAdminModal(true)" title="Админ-Панель"
      class="px-2.5 py-1.5 rounded-2xl bg-gradient-to-r from-amber-500 via-yellow-400 to-amber-500 text-slate-950 font-black text-[10px] shadow-2xl border-2 border-amber-300 flex items-center gap-1.5 active:scale-95 animate-pulse">
      <span class="text-xs">🛠️</span><span>${currentSlotLabel}</span>
    </button>
  </div>`;
}

function renderAdminModalHTML() {
  const activeTestSlot = localStorage.getItem("admin_test_tg_uid");
  const currentSlotLabel = activeTestSlot ? `🧪 #${activeTestSlot}` : `👑 Админ`;
  const players = (window._adminPlayersList && window._adminPlayersList.length > 0) ? window._adminPlayersList : getDefaultAdminPlayers();
  const catalog = (window._adminCatalogItems && window._adminCatalogItems.length > 0) ? window._adminCatalogItems : (window._DEFAULT_RPG_CATALOG || []);

  return `<div id="rpg-admin-modal-backdrop" class="fixed inset-0 z-50 bg-slate-950/85 backdrop-blur-md flex items-center justify-center p-3">
    <div class="w-full max-w-md max-h-[92vh] flex flex-col rounded-3xl bg-slate-900 border-2 border-amber-400/90 shadow-2xl text-white animate-scale-up overflow-hidden">
      <div class="p-3.5 border-b border-slate-700/80 flex items-center justify-between bg-slate-800/60 shrink-0">
        <div class="flex items-center gap-2">
          <span class="text-2xl">🛠️</span>
          <div>
            <h3 class="text-xs font-black text-amber-400 uppercase tracking-wider">Админ-Панель natarGRP</h3>
            <span class="text-[9px] text-slate-400">Управление игроками, чит-коды и тестирование</span>
          </div>
        </div>
        <button onclick="window.RPG.toggleAdminModal(false)" class="w-7 h-7 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 flex items-center justify-center font-bold text-xs">✕</button>
      </div>
      <div class="flex border-b border-slate-700/80 bg-slate-950/40 p-1 gap-1 shrink-0">
        <button onclick="window.RPG.setAdminSubTab('actions')" class="flex-1 py-1.5 text-center text-xs font-black rounded-xl transition-all ${window._adminSubTab === 'actions' ? 'bg-amber-500 text-slate-950 shadow-md' : 'text-slate-400 hover:text-white'}">⚡ Чит-Меню & Действия</button>
        <button onclick="window.RPG.setAdminSubTab('slots')" class="flex-1 py-1.5 text-center text-xs font-black rounded-xl transition-all ${window._adminSubTab === 'slots' ? 'bg-amber-500 text-slate-950 shadow-md' : 'text-slate-400 hover:text-white'}">🧪 Тест-Слоты (${currentSlotLabel})</button>
      </div>
      <div class="p-3.5 overflow-y-auto space-y-3 flex-1 text-xs">
        ${window._adminSubTab === "actions" ? renderAdminActionsTabHTML(players, catalog) : renderAdminSlotsTabHTML(activeTestSlot)}
      </div>
    </div>
  </div>`;
}

function renderAdminActionsTabHTML(players, catalog) {
  return `
    <div class="p-2.5 rounded-2xl bg-slate-800/80 border border-slate-700 space-y-2">
      <div class="flex items-center justify-between">
        <span class="text-[10px] font-black uppercase text-amber-400 tracking-wider">🎯 Целевой Игрок (${players.length} чел.):</span>
        <button onclick="window.RPG.refreshAdminPlayers()" class="text-[10px] text-sky-400 hover:underline flex items-center gap-1 font-bold"><span>🔄</span> Обновить</button>
      </div>
      <select id="admin-target-select" onchange="window._adminSelectedTarget = this.value; updateAdminModalDOM();" class="w-full bg-slate-950 border border-slate-600 rounded-xl px-2.5 py-1.5 text-xs text-amber-200 font-bold focus:outline-none">
        <option value="" ${!window._adminSelectedTarget ? 'selected' : ''}>👤 Текущий аккаунт (Я)</option>
        ${players.map(p => `<option value="${p.tg_id || p.user_id}" ${window._adminSelectedTarget == (p.tg_id || p.user_id) ? 'selected' : ''}>${p.hero_icon || '👤'} ${p.name} ${p.level > 0 ? `[Ур. ${p.level} | 🪙 ${p.gold >= 1000 ? Math.round(p.gold/1000)+'k' : p.gold}]` : '[Новичок]'} (ID: ${p.tg_id || p.user_id})</option>`).join('')}
      </select>
      <div class="flex items-center gap-2">
        <input type="text" id="admin-custom-target-input" placeholder="Или введите TG ID / User ID / @username" value="${window._adminSelectedTarget || ''}" onchange="window._adminSelectedTarget = this.value.trim()" class="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-2.5 py-1 text-[11px] text-slate-300 placeholder-slate-500">
        <button onclick="window.RPG.applyAdminCustomTarget()" class="px-2.5 py-1 bg-slate-700 hover:bg-slate-600 text-white rounded-xl text-[10px] font-bold">Выбрать</button>
      </div>
    </div>
    <div class="p-2.5 rounded-2xl bg-slate-800/80 border border-slate-700 space-y-2">
      <span class="text-[10px] font-black uppercase text-amber-400 tracking-wider flex items-center gap-1"><span>🪙</span> Выдать Золото</span>
      <div class="grid grid-cols-4 gap-1.5">
        ${[[50000, '+50k'], [250000, '+250k'], [1000000, '+1M'], [10000000, '+10M']].map(([a, l]) => `<button onclick="window.RPG.adminGiveGold(${a})" class="py-1 bg-amber-500/20 border border-amber-500/50 rounded-xl font-black text-amber-300 text-[11px] active:scale-95">${l}</button>`).join('')}
      </div>
      <div class="flex gap-2">
        <input type="number" id="admin-gold-custom-input" placeholder="Своя сумма золота" class="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-2.5 py-1 text-xs text-white">
        <button onclick="window.RPG.adminGiveGoldCustom()" class="px-3 py-1 bg-gradient-to-r from-amber-500 to-yellow-500 text-slate-950 rounded-xl font-black text-xs active:scale-95">Выдать</button>
      </div>
    </div>
    <div class="p-2.5 rounded-2xl bg-slate-800/80 border border-slate-700 space-y-2">
      <span class="text-[10px] font-black uppercase text-emerald-400 tracking-wider flex items-center gap-1"><span>💎</span> Выдать Кристаллы</span>
      <div class="grid grid-cols-4 gap-1.5">
        ${[[50, '+50 💎'], [250, '+250 💎'], [1000, '+1k 💎'], [10000, '+10k 💎']].map(([a, l]) => `<button onclick="window.RPG.adminGiveGems(${a})" class="py-1 bg-emerald-500/20 border border-emerald-500/50 rounded-xl font-black text-emerald-300 text-[11px] active:scale-95">${l}</button>`).join('')}
      </div>
      <div class="flex gap-2">
        <input type="number" id="admin-gems-custom-input" placeholder="Своя сумма кристаллов" class="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-2.5 py-1 text-xs text-white">
        <button onclick="window.RPG.adminGiveGemsCustom()" class="px-3 py-1 bg-gradient-to-r from-emerald-500 to-teal-500 text-slate-950 rounded-xl font-black text-xs active:scale-95">Выдать</button>
      </div>
    </div>
    <div class="p-2.5 rounded-2xl bg-slate-800/80 border border-slate-700 space-y-2">
      <span class="text-[10px] font-black uppercase text-sky-400 tracking-wider flex items-center gap-1"><span>🆙</span> Изменить Уровень Героя (1..50)</span>
      <div class="grid grid-cols-4 gap-1.5">
        ${[[1, 'Ур. 1'], [15, 'Ур. 15'], [30, 'Ур. 30'], [50, 'Ур. 50 (MAX)']].map(([l, lbl]) => `<button onclick="window.RPG.adminSetLevel(${l})" class="py-1 bg-sky-500/20 border border-sky-500/50 rounded-xl font-black text-sky-300 text-[11px] active:scale-95">${lbl}</button>`).join('')}
      </div>
      <div class="flex gap-2">
        <input type="number" id="admin-level-custom-input" min="1" max="50" placeholder="Уровень 1..50" class="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-2.5 py-1 text-xs text-white">
        <button onclick="window.RPG.adminSetLevelCustom()" class="px-3 py-1 bg-gradient-to-r from-sky-500 to-blue-600 text-white rounded-xl font-black text-xs active:scale-95">Установить</button>
      </div>
    </div>
    <div class="p-2.5 rounded-2xl bg-slate-800/80 border border-slate-700 space-y-2">
      <div class="flex items-center justify-between">
        <span class="text-[10px] font-black uppercase text-purple-400 tracking-wider flex items-center gap-1">
          <span>🎁</span> Выдать Предмет из Каталога (${catalog.length} предм.)
        </span>
        <button onclick="window.RPG.fetchAdminCatalog()" class="text-[10px] text-purple-300 hover:underline font-bold">🔄 Обновить</button>
      </div>
      <div>
        <label class="text-[9px] text-slate-400 block mb-0.5">Выберите предмет из игры:</label>
        <select id="admin-catalog-item-select" onchange="window.RPG.onAdminCatalogItemChange(this.value)" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-2 py-1.5 text-xs text-amber-300 font-bold focus:outline-none focus:border-purple-400">
          <option value="">🎲 [Случайный предмет под выбранную редкость]</option>
          ${catalog.map(it => `<option value="${it.name}">${it.icon || '📦'} ${it.name} (${it.rarity || 'common'})</option>`).join('')}
        </select>
      </div>
      <div class="grid grid-cols-2 gap-2">
        <div>
          <label class="text-[9px] text-slate-400 block mb-0.5">Редкость:</label>
          <select id="admin-item-rarity-select" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-2 py-1 text-xs text-purple-300 font-bold">
            <option value="common">⚪ Обычный</option><option value="uncommon">🟢 Необычный</option><option value="rare">🔵 Редкий</option>
            <option value="epic">🟣 Эпический</option><option value="legendary" selected>🟠 Легендарный</option><option value="mythic">🔴 Мифический</option><option value="immortal">💖 Бессмертный</option>
          </select>
        </div>
        <div>
          <label class="text-[9px] text-slate-400 block mb-0.5">Уровень (1..50):</label>
          <input type="number" id="admin-item-level-input" value="10" min="1" max="50" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-2 py-1 text-xs text-white">
        </div>
      </div>
      <button onclick="window.RPG.adminGiveItemSubmit()" class="w-full py-2 bg-gradient-to-r from-purple-600 via-indigo-600 to-purple-700 text-white rounded-xl font-black text-xs shadow-lg shadow-purple-600/30 active:scale-95">✨ Выдать Выбранный Предмет в Инвентарь</button>
    </div>
    <div class="p-2.5 rounded-2xl bg-rose-950/40 border border-rose-600/50 space-y-1.5">
      <span class="text-[10px] font-black uppercase text-rose-400 tracking-wider flex items-center gap-1"><span>⚠️</span> Опасная Зона: Сброс</span>
      <p class="text-[10px] text-rose-300/80 leading-tight">Полностью обнуляет выбранного игрока до 1 уровня, очищает экипировку и инвентарь до стартовых.</p>
      <button onclick="window.RPG.adminResetPlayerSubmit()" class="w-full py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-xl font-black text-xs shadow-lg shadow-rose-600/30 active:scale-95 flex items-center justify-center gap-1">
        <span>🔄</span><span>Обнулить Прогресс Выбранного Игрока</span>
      </button>
    </div>`;
}

function renderAdminSlotsTabHTML(activeTestSlot) {
  return `
    <div class="p-2.5 rounded-xl bg-slate-800/80 border border-slate-700 flex items-center justify-between text-xs">
      <span class="text-slate-400 font-bold text-[11px]">Активный аккаунт:</span>
      <span class="font-black text-amber-300">${activeTestSlot ? `🧪 #${activeTestSlot}` : '👑 Основной Админ'}</span>
    </div>
    <div class="space-y-1.5">
      <span class="text-[10px] font-black uppercase text-slate-400 tracking-wider block">Быстрые слоты:</span>
      ${RPG_STATE.adminTestSlots.map(s => {
        const isCur = (!activeTestSlot && s.id === 'main') || (activeTestSlot === s.tg_id);
        return `<button onclick="window.RPG.switchAdminTestAccount('${s.id}')" class="w-full p-2 rounded-xl text-left text-xs font-black flex items-center justify-between border transition-all ${isCur ? 'bg-amber-500/20 border-amber-400 text-amber-300 shadow-md' : 'bg-slate-800/60 border-slate-700/60 text-slate-300 hover:bg-slate-700'}">
          <span>${s.name}</span>
          <span class="text-[9px] px-1.5 py-0.5 rounded ${isCur ? 'bg-amber-400 text-slate-950 font-extrabold' : 'bg-slate-700 text-slate-400'}">${isCur ? 'АКТИВЕН' : 'Войти →'}</span>
        </button>`;
      }).join('')}
    </div>
    <div class="pt-2 space-y-2">
      <button onclick="window.RPG.createCustomAdminTestAccount()" class="w-full py-2 rounded-xl bg-gradient-to-r from-sky-600 to-cyan-600 text-white font-black text-xs shadow-md active:scale-95 flex items-center justify-center gap-1.5">
        <span>➕</span><span>Создать аккаунт с кастомным ID</span>
      </button>
      ${activeTestSlot ? `<button onclick="window.RPG.switchAdminTestAccount('main')" class="w-full py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-amber-400 font-black text-xs shadow-sm active:scale-95 flex items-center justify-center gap-1.5">
        <span>👑</span><span>Вернуться на Основной Аккаунт</span>
      </button>` : ''}
    </div>`;
}

// === ADMIN ACTIONS CONTROLLER ===
window.RPG = window.RPG || {};
window.RPG.setAdminSubTab = function(tab) {
  window._adminSubTab = tab;
  if (tab === "actions") {
    if (!window._adminPlayersList) window.RPG.refreshAdminPlayers();
    if (!window._adminCatalogItems) window.RPG.fetchAdminCatalog();
  }
  updateAdminModalDOM();
};

window.RPG.applyAdminCustomTarget = function() {
  const inp = document.getElementById("admin-custom-target-input");
  if (inp && inp.value) {
    window._adminSelectedTarget = inp.value.trim();
    alert(`Целевой игрок выбран: ${window._adminSelectedTarget}`);
    updateAdminModalDOM();
  }
};

window.RPG.refreshAdminPlayers = async function() {
  if (window._fetchingAdminPlayers) return;
  window._fetchingAdminPlayers = true;
  try {
    const apiObj = window.api || (typeof api !== "undefined" ? api : null);
    let res = null;
    if (apiObj?.getAdminRpgPlayers) { try { res = await apiObj.getAdminRpgPlayers(); } catch (err) { console.warn(err); } }
    if (!res) { try { res = await fetch("/api/rpg/admin/players").then(r => r.json()); } catch (err) { console.warn(err); } }
    if (res?.players?.length > 0) { window._adminPlayersList = res.players; updateAdminModalDOM(); }
  } catch (e) { console.warn("Failed to fetch admin players:", e); }
  finally { window._fetchingAdminPlayers = false; }
};

window.RPG.fetchAdminCatalog = async function() {
  if (!window._adminCatalogItems || window._adminCatalogItems.length === 0) window._adminCatalogItems = window._DEFAULT_RPG_CATALOG || [];
  if (window._fetchingAdminCatalog) return;
  window._fetchingAdminCatalog = true;
  try {
    const apiObj = window.api || (typeof api !== "undefined" ? api : null);
    let res = null;
    if (apiObj?.getAdminItemsCatalog) { try { res = await apiObj.getAdminItemsCatalog(); } catch (err) { console.warn(err); } }
    if (!res) { try { res = await fetch("/api/rpg/admin/items_catalog").then(r => r.json()); } catch (err) { console.warn(err); } }
    if (res?.items?.length > 0) { window._adminCatalogItems = res.items; updateAdminModalDOM(); }
  } catch (e) { console.warn("Failed to fetch admin items catalog:", e); }
  finally { window._fetchingAdminCatalog = false; }
};

window.RPG.onAdminCatalogItemChange = function(itemName) {
  if (!itemName) return;
  const catalog = window._adminCatalogItems || [];
  const found = catalog.find(it => it.name === itemName);
  if (found && found.rarity) {
    const sel = document.getElementById("admin-item-rarity-select");
    if (sel) sel.value = found.rarity;
  }
};

function applyAdminProfileUpdate(res, target) {
  if (!res || !res.profile) return;
  const p = res.profile;
  const curUid = String(RPG_STATE.profile?.user_id || "");
  const curTg = String(RPG_STATE.profile?.tg_id || localStorage.getItem("admin_test_tg_uid") || localStorage.getItem("cached_tg_uid") || "");
  const tgtStr = target ? String(target).trim() : "";
  const isMe = !tgtStr || tgtStr === curUid || tgtStr === curTg || String(p.user_id) === curUid || (p.tg_id && String(p.tg_id) === curTg);

  if (isMe) {
    RPG_STATE.profile = p;
    if (typeof syncArenaPlayerStats === "function") syncArenaPlayerStats();
    const topNav = document.getElementById("rpg-top-nav");
    if (topNav && typeof renderTopNavBarHTML === "function") topNav.outerHTML = renderTopNavBarHTML();
    const viewContainer = document.getElementById("rpg-view-container");
    if (viewContainer && RPG_STATE.activeTab === "hero" && typeof renderHeroViewHTML === "function") viewContainer.innerHTML = renderHeroViewHTML();
  }
  if (window._adminPlayersList && window._adminPlayersList.length > 0) {
    const pItem = window._adminPlayersList.find(x => String(x.tg_id) === tgtStr || String(x.user_id) === tgtStr || (isMe && (String(x.user_id) === curUid || String(x.tg_id) === curTg)));
    if (pItem) {
      if (p.gold !== undefined) pItem.gold = p.gold;
      if (p.gems !== undefined) pItem.gems = p.gems;
      if (p.level !== undefined) pItem.level = p.level;
    }
  }
}

window.RPG.adminGiveGold = async function(amount) {
  try {
    const target = window._adminSelectedTarget || null;
    const apiObj = window.api || (typeof api !== "undefined" ? api : null);
    const res = await apiObj.adminGiveGold({ target, amount });
    applyAdminProfileUpdate(res, target);
    showAdminNotice(res.message || "Золото успешно выдано!");
    window.RPG.refreshAdminPlayers();
    updateAdminModalDOM();
  } catch (e) {
    showAdminNotice(e.message || "Ошибка выдачи золота");
  }
};

window.RPG.adminGiveGoldCustom = function() {
  const val = parseInt(document.getElementById("admin-gold-custom-input")?.value || 0, 10);
  if (!val) return showAdminNotice("Введите корректную сумму золота");
  window.RPG.adminGiveGold(val);
};

window.RPG.adminGiveGems = async function(amount) {
  try {
    const target = window._adminSelectedTarget || null;
    const apiObj = window.api || (typeof api !== "undefined" ? api : null);
    const res = await apiObj.adminGiveGems({ target, amount });
    applyAdminProfileUpdate(res, target);
    showAdminNotice(res.message || "Кристаллы успешно выданы!");
    window.RPG.refreshAdminPlayers();
    updateAdminModalDOM();
  } catch (e) {
    showAdminNotice(e.message || "Ошибка выдачи кристаллов");
  }
};

window.RPG.adminGiveGemsCustom = function() {
  const val = parseInt(document.getElementById("admin-gems-custom-input")?.value || 0, 10);
  if (!val) return showAdminNotice("Введите корректную сумму кристаллов");
  window.RPG.adminGiveGems(val);
};

window.RPG.adminSetLevel = async function(lvl) {
  try {
    const target = window._adminSelectedTarget || null;
    const apiObj = window.api || (typeof api !== "undefined" ? api : null);
    const res = await apiObj.adminSetLevel({ target, level: lvl });
    applyAdminProfileUpdate(res, target);
    showAdminNotice(res.message || `Уровень успешно изменен на ${lvl}!`);
    window.RPG.refreshAdminPlayers();
    updateAdminModalDOM();
  } catch (e) {
    showAdminNotice(e.message || "Ошибка изменения уровня");
  }
};

window.RPG.adminSetLevelCustom = function() {
  const val = parseInt(document.getElementById("admin-level-custom-input")?.value || 0, 10);
  if (!val || val < 1 || val > 50) return showAdminNotice("Введите уровень от 1 до 50");
  window.RPG.adminSetLevel(val);
};

window.RPG.adminGiveItemSubmit = async function() {
  try {
    const target = window._adminSelectedTarget || null;
    const rarity = document.getElementById("admin-item-rarity-select")?.value || "legendary";
    const lvl = parseInt(document.getElementById("admin-item-level-input")?.value || "10", 10);
    const itemName = document.getElementById("admin-catalog-item-select")?.value || null;
    const apiObj = window.api || (typeof api !== "undefined" ? api : null);
    const res = await apiObj.adminGiveItem({ target, rarity, level: lvl, item_name: itemName });
    applyAdminProfileUpdate(res, target);
    showAdminNotice(res.message || "Предмет успешно выдан в инвентарь!");
    updateAdminModalDOM();
  } catch (e) {
    showAdminNotice(e.message || "Ошибка выдачи предмета");
  }
};

window.RPG.adminResetPlayerSubmit = async function() {
  const targetLabel = window._adminSelectedTarget ? `игрока [${window._adminSelectedTarget}]` : "ТЕКУЩЕГО аккаунта";
  const ok = confirm(`ВНИМАНИЕ! Вы уверены, что хотите ПОЛНОСТЬЮ ОБНУЛИТЬ прогресс ${targetLabel} до 1 уровня?\nЭто действие необратимо!`);
  if (!ok) return;

  try {
    const target = window._adminSelectedTarget || null;
    const apiObj = window.api || (typeof api !== "undefined" ? api : null);
    const res = await apiObj.adminResetPlayer({ target });
    applyAdminProfileUpdate(res, target);
    showAdminNotice(res.message || "Прогресс игрока успешно сброшен!");
    window.RPG.refreshAdminPlayers();
    updateAdminModalDOM();
  } catch (e) {
    showAdminNotice(e.message || "Ошибка сброса игрока");
  }
};

// Immediate pre-fetch in background on script initialization
setTimeout(() => {
  if (window.RPG) {
    if (window.RPG.fetchAdminCatalog) window.RPG.fetchAdminCatalog();
    if (window.RPG.refreshAdminPlayers) window.RPG.refreshAdminPlayers();
  }
}, 300);
