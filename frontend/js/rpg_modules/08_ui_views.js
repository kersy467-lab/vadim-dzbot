  function renderRoot() {
    const container = document.getElementById("rpg-root");
    if (!container) return;

    if (RPG_STATE.errorMessage) {
      container.innerHTML = `
        <div class="py-16 text-center space-y-3 px-4">
          <div class="text-4xl">вљ пёЏ</div>
          <h3 class="text-base font-bold text-red-500">РљСЂРёС‚РёС‡РµСЃРєР°СЏ РѕС€РёР±РєР°</h3>
          <p class="text-xs font-mono bg-slate-900 text-slate-300 p-3 rounded-xl border border-slate-700 text-left overflow-auto">${RPG_STATE.errorMessage}</p>
        </div>
      `;
      return;
    }

    if (RPG_STATE.loading && !RPG_STATE.profile) {
      container.innerHTML = `
        <div class="py-16 text-center space-y-3">
          <div class="inline-block w-8 h-8 border-4 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
          <p class="text-sm font-bold text-slate-500">Загрузка natarGRP...</p>
        </div>
      `;
      return;
    }

    if (!RPG_STATE.profile || !RPG_STATE.profile.hero_class) {
      container.innerHTML = renderHeroSelectHTML();
      return;
    }

    // Fast-path: If user is actively in the Action Arena and canvas already exists,
    // DO NOT destroy the canvas DOM node! Update header and modals smoothly.
    const existingCanvas = document.getElementById("rpg-action-canvas");
    const viewContainer = document.getElementById("rpg-view-container");

    const isBossFightState = !!(ARENA.isRaidBossBattle || (ARENA.isBossActive && ARENA.topDownMode));
    const bossFightStateChanged = RPG_STATE._lastRenderedBossFight !== isBossFightState;
    RPG_STATE._lastRenderedBossFight = isBossFightState;

    if (!RPG_STATE._forceFullRender && !bossFightStateChanged && existingCanvas && viewContainer && RPG_STATE.activeTab === "farm" && RPG_STATE.farmMode === "arena") {
      const topNav = document.getElementById("rpg-top-nav");
      if (topNav) {
        topNav.outerHTML = renderTopNavBarHTML();
      }
      const toastEl = document.getElementById("rpg-toast-container");
      if (toastEl) {
        toastEl.innerHTML = RPG_STATE.levelUpNotification
          ? `<div class="p-3 rounded-2xl bg-gradient-to-r from-amber-500 to-yellow-400 text-slate-950 font-black text-center text-xs shadow-lg animate-bounce">
              🎉 НОВЫЙ УРОВЕНЬ ${RPG_STATE.levelUpNotification}! Получено +1 очко характеристик!
            </div>`
          : "";
      }
      const modalsEl = document.getElementById("rpg-modals-container");
      if (modalsEl) {
        const existingAdmin = document.getElementById("rpg-admin-modal-backdrop");
        const shouldShowAdmin = isUserAdmin() && RPG_STATE.adminModalOpen;
        if (!shouldShowAdmin && existingAdmin) {
          existingAdmin.remove();
        }
        modalsEl.innerHTML = `
          ${RPG_STATE.inspectedItem ? renderItemModalHTML(RPG_STATE.inspectedItem) : ""}
          ${RPG_STATE.forgeItem ? renderForgeModalHTML(RPG_STATE.forgeItem) : ""}
          ${RPG_STATE.activeChestModal ? renderChestModalHTML(RPG_STATE.activeChestModal) : ""}
          ${RPG_STATE.shopModalOpen ? renderShopModalHTML() : ""}
          ${RPG_STATE.slotFilterModal ? renderSlotFilterModalHTML(RPG_STATE.slotFilterModal) : ""}
          ${(shouldShowAdmin && !existingAdmin) ? renderAdminModalHTML() : ""}
        `;
        if (shouldShowAdmin && existingAdmin && !modalsEl.contains(existingAdmin)) {
          modalsEl.appendChild(existingAdmin);
        }
      }
      if (ARENA.canvas !== existingCanvas || !ARENA.ctx) {
        bindArenaCanvas(existingCanvas);
      }
      if (!ARENA.running) {
        startArenaLoop();
      }
      return;
    }

    // Full render when switching tabs or initial load
    container.innerHTML = `
      <div class="space-y-3.5 pb-8">
        <!-- Level Up Toast Notification Container -->
        <div id="rpg-toast-container">
          ${
            RPG_STATE.levelUpNotification
              ? `
            <div class="p-3 rounded-2xl bg-gradient-to-r from-amber-500 to-yellow-400 text-slate-950 font-black text-center text-xs shadow-lg animate-bounce">
              🎉 НОВЫЙ УРОВЕНЬ ${RPG_STATE.levelUpNotification}! Получено +1 очко характеристик!
            </div>
          `
              : ""
          }
        </div>

        <!-- Top Navigation -->
        ${renderTopNavBarHTML()}

        <!-- Active Subtab View -->
        <div id="rpg-view-container">
          ${renderCurrentViewHTML()}
        </div>
      </div>

      <!-- Modals Container -->
      <div id="rpg-modals-container">
        <!-- Item Inspection Modal -->
        ${RPG_STATE.inspectedItem ? renderItemModalHTML(RPG_STATE.inspectedItem) : ""}

        <!-- Forge Modal -->
        ${RPG_STATE.forgeItem ? renderForgeModalHTML(RPG_STATE.forgeItem) : ""}

        <!-- Chest Opening Modal -->
        ${RPG_STATE.activeChestModal ? renderChestModalHTML(RPG_STATE.activeChestModal) : ""}

        <!-- Shop Modal -->
        ${RPG_STATE.shopModalOpen ? renderShopModalHTML() : ""}

        <!-- Slot Quick Equip Modal -->
        ${RPG_STATE.slotFilterModal ? renderSlotFilterModalHTML(RPG_STATE.slotFilterModal) : ""}

        <!-- Admin Dev Modal -->
        ${(isUserAdmin() && RPG_STATE.adminModalOpen) ? renderAdminModalHTML() : ""}
      </div>

      <!-- Admin Floating Pill Badge (Bottom-left) -->
      ${isUserAdmin() ? renderAdminFloatingBadgeHTML() : ""}
    `;

    if (RPG_STATE.activeTab === "farm" && RPG_STATE.farmMode === "arena") {
      const c = document.getElementById("rpg-action-canvas");
      if (c) {
        bindArenaCanvas(c);
        requestAnimationFrame(() => {
          const freshC = document.getElementById("rpg-action-canvas");
          if (freshC) bindArenaCanvas(freshC);
        });
        if (!ARENA.running) {
          startArenaLoop();
        }
      }
    }
  }

  function renderTopNavBarHTML() {
    const p = RPG_STATE.profile || {};
    const tabs = [
      { id: "farm", name: "Фарм", icon: "⚔️" },
      { id: "hero", name: "Герой", icon: p.class_icon || "🛡️" },
      { id: "talents", name: "Таланты", icon: "🧬" },
      { id: "coop", name: "Боссы", icon: "🐉" }
    ];

    const xp = p.xp !== undefined ? p.xp : (p.experience || 0);
    const xpNeeded = p.xp_needed !== undefined ? p.xp_needed : (p.experience_to_next || 100);
    const xpPct = Math.min(100, Math.max(0, Math.round((xp / xpNeeded) * 100)));

    return `
      <div id="rpg-top-nav" class="space-y-2">
        <!-- Character Summary Card -->
        <div class="p-3.5 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-800 to-amber-950 text-white shadow-md border border-amber-500/30 space-y-2">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2.5">
              <div class="w-10 h-10 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-2xl shadow-inner">
                ${p.class_avatar || p.class_icon || "🛡️"}
              </div>
              <div>
                <div class="flex items-center gap-1.5">
                  <span class="text-xs font-black tracking-wide">${p.class_name || "Герой"}</span>
                  <span class="text-[10px] px-1.5 py-0.2 rounded-md bg-amber-500 text-slate-950 font-black">Ур. ${p.level || 1}</span>
                </div>
                <div class="flex items-center gap-2 text-[11px] text-amber-200/90 font-medium">
                  <span>🪙 <b>${(p.gold || 0).toLocaleString()}</b></span>
                  <span>💎 <b>${p.gems || 0}</b></span>
                  <span>🔥 <b>${p.dungeon_floor || 1}</b> эт.</span>
                  ${(p.stat_points || 0) > 0 ? `<span class="px-1.5 rounded bg-emerald-500 text-white font-extrabold text-[9px] animate-pulse">+${p.stat_points} очк</span>` : ""}
                </div>
              </div>
            </div>

            <div class="text-right flex items-center gap-1.5">
              <button onclick="window.RPG.openShopModal()" class="px-2.5 py-1.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 active:scale-95 text-white font-black text-[11px] shadow-sm flex items-center gap-1">
                <span>🏪</span>
                <span>Лавка</span>
              </button>
              <button onclick="window.RPG.openForge()" class="px-2.5 py-1.5 rounded-xl bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 active:scale-95 text-slate-950 font-black text-[11px] shadow-sm flex items-center gap-1">
                <span>⚒️</span>
                <span>Кузница</span>
              </button>
            </div>
          </div>

          <!-- Mini XP Bar in Header -->
          <div class="w-full h-1.5 rounded-full bg-slate-700/80 overflow-hidden">
            <div class="h-full bg-gradient-to-r from-amber-400 to-yellow-300 transition-all duration-300" style="width: ${xpPct}%"></div>
          </div>
        </div>

        <!-- Navigation Subtabs -->
        <div class="grid grid-cols-4 gap-1 p-1 rounded-2xl bg-slate-200/80 dark:bg-slate-800/90 text-[11px] font-bold">
          ${tabs
            .map(
              (t) => `
            <button onclick="window.RPG.setSubTab('${t.id}')" class="py-2 rounded-xl transition-all flex flex-col items-center justify-center gap-0.5 ${
                RPG_STATE.activeTab === t.id
                  ? "bg-white dark:bg-slate-700 text-amber-600 dark:text-amber-400 shadow-sm"
                  : "text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200"
              }">
              <span class="text-sm">${t.icon}</span>
              <span class="text-[10px] leading-tight">${t.name}</span>
            </button>
          `
            )
            .join("")}
        </div>
      </div>
    `;
  }

  function renderCurrentViewHTML() {
    switch (RPG_STATE.activeTab) {
      case "farm":
        return renderFarmTabHTML();
      case "hero":
        return renderHeroProfileHTML();
      case "talents":
        if (window._talentsTabAutoLoad) setTimeout(_talentsTabAutoLoad, 0);
        return renderTalentsTab();
      case "coop":
        return renderCoopRaidsHTML();
      case "pvp":
        return renderPvPDuelsHTML();
      case "leaderboard":
        return renderLeaderboardHTML();
      default:
        return renderFarmTabHTML();
    }
  }

  // ===========================================================================
  // 1. HERO PROFILE & 3-ATTRIBUTE SYSTEM HTML
  // ===========================================================================

  function renderHeroProfileHTML() {
    const p = RPG_STATE.profile || {};
    const stats = p.stats || {};
    const eq = p.equipment || {};
    const inv = p.inventory || [];
    const points = p.stat_points || 0;

    const baseStr = (p.base_attributes && p.base_attributes.strength) || p.strength || 10;
    const gearStr = (p.gear_attributes && p.gear_attributes.strength) || stats.gear_str || 0;
    const totalStr = (p.total_attributes && p.total_attributes.strength) || (baseStr + gearStr);

    const baseAgi = (p.base_attributes && p.base_attributes.agility) || p.agility || 10;
    const gearAgi = (p.gear_attributes && p.gear_attributes.agility) || stats.gear_agi || 0;
    const totalAgi = (p.total_attributes && p.total_attributes.agility) || (baseAgi + gearAgi);

    const baseInt = (p.base_attributes && p.base_attributes.intelligence) || p.intelligence || 10;
    const gearInt = (p.gear_attributes && p.gear_attributes.intelligence) || stats.gear_int || 0;
    const totalInt = (p.total_attributes && p.total_attributes.intelligence) || (baseInt + gearInt);

    const xp = p.xp !== undefined ? p.xp : (p.experience || 0);
    const xpNeeded = p.xp_needed !== undefined ? p.xp_needed : (p.experience_to_next || 100);
    const xpPct = Math.min(100, Math.max(0, Math.round((xp / xpNeeded) * 100)));
    const primaryAttr = p.primary_attr || stats.primary_attr || "Сила";
    const userGold = p.gold || 0;

    function calcCost(currentVal, count) {
      let total = 0;
      let pts = points;
      let val = currentVal;
      for (let i = 0; i < count; i++) {
        if (pts > 0) {
          pts--;
        } else {
          total += Math.floor(Math.pow(val, 1.35) * 6);
        }
        val++;
      }
      return total;
    }

    function calcMax(currentVal) {
      let count = 0;
      let pts = points;
      let remGold = userGold;
      let val = currentVal;
      while (pts > 0) {
        pts--;
        count++;
        val++;
      }
      while (true) {
        const cost = Math.floor(Math.pow(val, 1.35) * 6);
        if (remGold < cost) break;
        remGold -= cost;
        count++;
        val++;
        if (count >= 10000) break;
      }
      return count;
    }

    function formatShort(num) {
      if (!num || num <= 0) return "0";
      if (num >= 1e9) return (num / 1e9).toFixed(1) + "B";
      if (num >= 1e6) return (num / 1e6).toFixed(1) + "M";
      if (num >= 1e3) return Math.round(num / 1e3) + "k";
      return num.toLocaleString();
    }

    function renderStatUpgradeButtons(statKey, baseVal, themeGradient) {
      const cost1 = calcCost(baseVal, 1);
      const cost10 = calcCost(baseVal, 10);
      const cost100 = calcCost(baseVal, 100);
      const maxCount = calcMax(baseVal);

      const can1 = !isUpgradingStat && (cost1 <= userGold || points > 0);
      const can10 = !isUpgradingStat && (cost10 <= userGold || points >= 10);
      const can100 = !isUpgradingStat && (cost100 <= userGold || points >= 100);
      const canMax = !isUpgradingStat && (maxCount > 0);

      const disabledCls = "bg-slate-100 dark:bg-slate-800/80 text-slate-400 dark:text-slate-500 opacity-50 cursor-not-allowed";
      const btnBase = "py-2 px-1 rounded-xl flex flex-col items-center justify-center transition-all select-none";

      const getSubLabel = (count, cost) => {
        if (points >= count) return `✨ ${count}`;
        return `${formatShort(cost)} 🪙`;
      };

      return `
        <div class="grid grid-cols-4 gap-1.5 pt-2 border-t border-slate-200/50 dark:border-slate-700/50">
          <button ${!can1 ? "disabled" : ""} onclick="window.RPG.upgradeStat('${statKey}', 1)" title="+1 уровень" class="${btnBase} ${can1 ? (points > 0 ? "bg-gradient-to-r from-emerald-600 to-green-500 text-white shadow-sm ring-1 ring-emerald-400/40 active:scale-95" : themeGradient + " active:scale-95") : disabledCls}">
            <span class="text-xs font-black leading-tight">+1</span>
            <span class="text-[9px] font-bold opacity-90 truncate max-w-full">${points > 0 ? "✨ 1" : `${formatShort(cost1)} 🪙`}</span>
          </button>

          <button ${!can10 ? "disabled" : ""} onclick="window.RPG.upgradeStat('${statKey}', 10)" title="+10 уровней" class="${btnBase} ${can10 ? themeGradient + " active:scale-95" : disabledCls}">
            <span class="text-xs font-black leading-tight">+10</span>
            <span class="text-[9px] font-bold opacity-90 truncate max-w-full">${getSubLabel(10, cost10)}</span>
          </button>

          <button ${!can100 ? "disabled" : ""} onclick="window.RPG.upgradeStat('${statKey}', 100)" title="+100 уровней" class="${btnBase} ${can100 ? themeGradient + " active:scale-95" : disabledCls}">
            <span class="text-xs font-black leading-tight">+100</span>
            <span class="text-[9px] font-bold opacity-90 truncate max-w-full">${getSubLabel(100, cost100)}</span>
          </button>

          <button ${!canMax ? "disabled" : ""} onclick="window.RPG.upgradeStat('${statKey}', 'max')" title="+Максимум на сколько хватает монет" class="${btnBase} ${canMax ? "bg-gradient-to-r from-amber-500 to-yellow-500 text-slate-950 font-black shadow-sm ring-1 ring-amber-400/50 active:scale-95" : disabledCls}">
            <span class="text-xs font-black leading-tight">+МАКС</span>
            <span class="text-[9px] font-bold opacity-90 truncate max-w-full">${maxCount > 0 ? `+${maxCount}` : "0"}</span>
          </button>
        </div>
      `;
    }

    return `
      <div class="space-y-4">
        <!-- Level & EXP progress -->
        <div class="theme-card p-3.5 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm space-y-2">
          <div class="flex items-center justify-between text-xs font-bold">
            <span class="text-slate-500 dark:text-slate-400">Прогресс уровня</span>
            <span class="text-amber-600 dark:text-amber-400 font-extrabold">${xp} / ${xpNeeded} XP (${xpPct}%)</span>
          </div>
          <div class="w-full h-2.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
            <div class="h-full bg-gradient-to-r from-amber-500 to-yellow-400 transition-all duration-300" style="width: ${xpPct}%"></div>
          </div>
          <div class="flex items-center justify-between text-xs font-bold mt-2 pt-2 border-t border-slate-200/50 dark:border-slate-700/50">
            <span class="text-slate-500 dark:text-slate-400">Уровень героя:</span>
            <span class="text-amber-600 dark:text-amber-400 font-black text-sm">${p.level || 1} ур.</span>
          </div>
          <div class="flex items-center justify-between text-[11px] pt-1.5 border-t border-purple-500/20">
            <span class="text-slate-400">Доступно очков характеристик:</span>
            <span class="text-amber-400 font-black">${points} очк.</span>
          </div>
          <div class="flex items-center justify-between text-[11px] pt-1.5 border-t border-purple-500/20">
            <span class="text-slate-400">Доступно очков талантов:</span>
            <span class="text-emerald-400 font-black">${p.talent_points || 0} очк.</span>
          </div>
        </div>

        <!-- REBIRTH & TALENTS SUMMARY CARD -->
        <div class="theme-card p-3.5 rounded-2xl bg-gradient-to-r from-purple-950/40 via-slate-900 to-indigo-950/40 border border-purple-500/30 shadow-sm space-y-2.5">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="text-xl">🧬</span>
              <div>
                <div class="text-xs font-black text-purple-300">Перерождение и Таланты</div>
                <div class="text-[10px] text-slate-400">Ранг: <b class="text-white">${p.rebirths || 0}</b> (+${(p.rebirths || 0) * 10}% ко всем статам)</div>
              </div>
            </div>
            <button onclick="window.RPG.setSubTab('talents')" class="px-3 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-500 active:scale-95 text-white font-black text-[11px] shadow-sm flex items-center gap-1">
              <span>Открыть</span>
              <span>⚡</span>
            </button>
          </div>
          <div class="flex items-center justify-between text-[11px] pt-1.5 border-t border-purple-500/20">
            <span class="text-slate-400">Доступно очков талантов:</span>
            <span class="text-emerald-400 font-black">${p.talent_points || 0} очк.</span>
          </div>
        </div>

        <!-- 3 ATTRIBUTES SYSTEM (СИЛА, ЛОВКОСТЬ, ИНТЕЛЛЕКТ) -->
        <div class="theme-card p-3.5 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm space-y-3">
          <div class="flex items-center justify-between">
            <h3 class="text-xs font-black uppercase tracking-wider text-slate-700 dark:text-slate-200 flex items-center gap-1.5">
              <span>📊</span> Характеристики
            </h3>
            ${
              points > 0
                ? `<span class="px-2 py-0.5 rounded-lg bg-emerald-500 text-white font-extrabold text-[10px] animate-pulse">✨ Свободных очков: ${points}</span>`
                : `<span class="text-[10px] text-slate-400 font-medium">Прокачка за золото</span>`
            }
          </div>

          <div class="flex items-center justify-between p-2.5 rounded-xl bg-slate-100 dark:bg-slate-900/60 text-xs font-bold border border-slate-200/60 dark:border-slate-700/60">
            <span class="text-slate-500 dark:text-slate-400">Ваше золото для прокачки:</span>
            <span class="text-amber-500 font-black">🪙 ${(p.gold || 0).toLocaleString()}</span>
          </div>

          <div class="space-y-2">
            <!-- 1. STRENGTH (СИЛА) -->
            <div class="p-3 rounded-2xl bg-slate-50 dark:bg-slate-900/50 border ${primaryAttr === "Сила" ? "border-red-500/50 shadow-sm bg-red-50/20" : "border-slate-200/60 dark:border-slate-700/60"} flex flex-col gap-2">
              <div class="flex items-center justify-between">
                <div class="space-y-0.5">
                  <div class="flex items-center gap-1.5 flex-wrap">
                    <span class="text-xs font-black text-red-500">🥩 Сила: ${baseStr}${gearStr > 0 ? ` <span class="text-amber-500 font-extrabold">(+${gearStr})</span>` : ""}${gearStr > 0 ? ` <span class="text-slate-800 dark:text-slate-100 font-black">= ${totalStr}</span>` : ""}</span>
                    ${primaryAttr === "Сила" ? `<span class="px-1.5 py-0.2 rounded bg-red-500/10 text-red-600 border border-red-500/30 text-[9px] font-black">ОСНОВНОЙ (+1 Урон)</span>` : ""}
                  </div>
                  <span class="block text-[10px] text-slate-400">+22 HP за очко | +0.35 HP/сек регенерация</span>
                </div>
              </div>
              ${renderStatUpgradeButtons('str', baseStr, 'bg-gradient-to-r from-red-600 to-rose-600 text-white hover:from-red-500 hover:to-rose-500 shadow-sm shadow-red-500/20')}
            </div>

            <!-- 2. AGILITY (ЛОВКОСТЬ) -->
            <div class="p-3 rounded-2xl bg-slate-50 dark:bg-slate-900/50 border ${primaryAttr === "Ловкость" ? "border-emerald-500/50 shadow-sm bg-emerald-50/20" : "border-slate-200/60 dark:border-slate-700/60"} flex flex-col gap-2">
              <div class="flex items-center justify-between">
                <div class="space-y-0.5">
                  <div class="flex items-center gap-1.5 flex-wrap">
                    <span class="text-xs font-black text-emerald-500">🗡️ Ловкость: ${baseAgi}${gearAgi > 0 ? ` <span class="text-amber-500 font-extrabold">(+${gearAgi})</span>` : ""}${gearAgi > 0 ? ` <span class="text-slate-800 dark:text-slate-100 font-black">= ${totalAgi}</span>` : ""}</span>
                    ${primaryAttr === "Ловкость" ? `<span class="px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-600 border border-emerald-500/30 text-[9px] font-black">ОСНОВНОЙ (+1 Урон)</span>` : ""}
                  </div>
                  <span class="block text-[10px] text-slate-400">+2.5% Скор. атаки | +0.4 Брони | Крит & Уворот</span>
                </div>
              </div>
              ${renderStatUpgradeButtons('agi', baseAgi, 'bg-gradient-to-r from-emerald-600 to-teal-600 text-white hover:from-emerald-500 hover:to-teal-500 shadow-sm shadow-emerald-500/20')}
            </div>

            <!-- 3. INTELLIGENCE (ИНТЕЛЛЕКТ) -->
            <div class="p-3 rounded-2xl bg-slate-50 dark:bg-slate-900/50 border ${primaryAttr === "Интеллект" ? "border-sky-500/50 shadow-sm bg-sky-50/20" : "border-slate-200/60 dark:border-slate-700/60"} flex flex-col gap-2">
              <div class="flex items-center justify-between">
                <div class="space-y-0.5">
                  <div class="flex items-center gap-1.5 flex-wrap">
                    <span class="text-xs font-black text-sky-500">🧙 Интеллект: ${baseInt}${gearInt > 0 ? ` <span class="text-amber-500 font-extrabold">(+${gearInt})</span>` : ""}${gearInt > 0 ? ` <span class="text-slate-800 dark:text-slate-100 font-black">= ${totalInt}</span>` : ""}</span>
                    ${primaryAttr === "Интеллект" ? `<span class="px-1.5 py-0.2 rounded bg-sky-500/10 text-sky-600 border border-sky-500/30 text-[9px] font-black">ОСНОВНОЙ (+1 Урон)</span>` : ""}
                  </div>
                  <span class="block text-[10px] text-slate-400">+14 Маны за очко | +0.25 MP/сек | +0.4% Сопр. магии</span>
                </div>
              </div>
              ${renderStatUpgradeButtons('int', baseInt, 'bg-gradient-to-r from-sky-600 to-blue-600 text-white hover:from-sky-500 hover:to-blue-500 shadow-sm shadow-sky-500/20')}
            </div>
          </div>

          <!-- Combat Summary Badges -->
          <div class="pt-2 border-t border-slate-100 dark:border-slate-700/80 grid grid-cols-3 gap-1.5 text-center">
            <div class="p-1.5 rounded-lg bg-slate-100 dark:bg-slate-700/40">
              <span class="block text-[9px] font-bold text-slate-400 uppercase">HP</span>
              <span class="text-xs font-black text-emerald-600 dark:text-emerald-400">${stats.hp_max || 180} <span class="text-[9px] text-slate-400">(+${stats.hp_regen || 0}/с)</span></span>
            </div>
            <div class="p-1.5 rounded-lg bg-slate-100 dark:bg-slate-700/40">
              <span class="block text-[9px] font-bold text-slate-400 uppercase">Мана</span>
              <span class="text-xs font-black text-sky-600 dark:text-sky-400">${stats.mp_max || 60} <span class="text-[9px] text-slate-400">(+${stats.mp_regen || 0}/с)</span></span>
            </div>
            <div class="p-1.5 rounded-lg bg-slate-100 dark:bg-slate-700/40">
              <span class="block text-[9px] font-bold text-slate-400 uppercase">Урон</span>
              <span class="text-xs font-black text-red-600 dark:text-red-400">${stats.min_atk || 16}-${stats.max_atk || 24}</span>
            </div>
            <div class="p-1.5 rounded-lg bg-slate-100 dark:bg-slate-700/40">
              <span class="block text-[9px] font-bold text-slate-400 uppercase">Броня</span>
              <span class="text-xs font-black text-sky-600 dark:text-sky-400">${stats.defense || 5}</span>
            </div>
            <div class="p-1.5 rounded-lg bg-slate-100 dark:bg-slate-700/40">
              <span class="block text-[9px] font-bold text-slate-400 uppercase">Скор. атаки</span>
              <span class="text-xs font-black text-amber-600 dark:text-amber-400">${stats.attack_speed || 1.0} уд/с</span>
            </div>
            <div class="p-1.5 rounded-lg bg-slate-100 dark:bg-slate-700/40">
              <span class="block text-[9px] font-bold text-slate-400 uppercase">Сопр. магии</span>
              <span class="text-xs font-black text-purple-600 dark:text-purple-400">${stats.magic_resist || 0}%</span>
            </div>
            <div class="p-1.5 rounded-lg bg-slate-100 dark:bg-slate-700/40">
              <span class="block text-[9px] font-bold text-slate-400 uppercase">Сила Магии ✨</span>
              <span class="text-xs font-black text-amber-500">+${stats.spell_amp || Math.round((stats.mp_max || 60) * 0.2)}%</span>
            </div>
            <div class="p-1.5 rounded-lg bg-slate-100 dark:bg-slate-700/40">
              <span class="block text-[9px] font-bold text-slate-400 uppercase">Крит</span>
              <span class="text-xs font-black text-amber-600 dark:text-amber-400">${stats.crit_chance || 5}%</span>
            </div>
            <div class="p-1.5 rounded-lg bg-slate-100 dark:bg-slate-700/40">
              <span class="block text-[9px] font-bold text-slate-400 uppercase">Уворот</span>
              <span class="text-xs font-black text-violet-600 dark:text-violet-400">${stats.dodge_chance || 5}%</span>
            </div>
            <div class="p-1.5 rounded-lg bg-slate-100 dark:bg-slate-700/40">
              <span class="block text-[9px] font-bold text-slate-400 uppercase">Вампиризм</span>
              <span class="text-xs font-black text-rose-600 dark:text-rose-400">${stats.lifesteal || 0}%</span>
            </div>
            ${stats.ult_boost > 0 ? `
            <div class="p-1.5 rounded-lg bg-purple-500/10 border border-purple-500/30">
              <span class="block text-[9px] font-bold text-purple-400 uppercase">Урон Ульты 💥</span>
              <span class="text-xs font-black text-purple-500">+${stats.ult_boost}%</span>
            </div>
            ` : ""}
            ${stats.ult_cd_reduct > 0 ? `
            <div class="p-1.5 rounded-lg bg-sky-500/10 border border-sky-500/30">
              <span class="block text-[9px] font-bold text-sky-400 uppercase">КД Ульты ⏱️</span>
              <span class="text-xs font-black text-sky-400">-${stats.ult_cd_reduct}%</span>
            </div>
            ` : ""}
          </div>
        </div>

        <!-- Equipped Gear Slots (3 slots) -->
        <div class="theme-card p-3.5 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm space-y-2.5">
          <h3 class="text-xs font-black uppercase tracking-wider text-slate-700 dark:text-slate-200 flex items-center gap-1.5">
            <span>🛡️</span> Экипировка
          </h3>

          <div class="grid grid-cols-3 gap-2">
            ${[1,2,3,4,5,6].map(i => renderEquippedSlotHTML('slot_'+i, 'Слот '+i, '🎒', eq['slot_'+i] || (i===1 ? eq.weapon : i===2 ? eq.armor : i===3 ? eq.relic : null))).join('')}
          </div>
        </div>

        <!-- Inventory Card -->
        <div class="theme-card p-3.5 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm space-y-3">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="text-base">🎒</span>
              <h3 class="text-xs font-black uppercase tracking-wider text-slate-700 dark:text-slate-200">
                Инвентарь
              </h3>
              <span class="text-[10px] font-bold text-slate-400">(${inv.length} / 60)</span>
            </div>

            <!-- Toggle Selection Mode Button -->
            ${inv.length > 0 ? `
              <button onclick="window.RPG.toggleItemSelectionMode()" class="px-2.5 py-1 rounded-xl text-xs font-black transition-all flex items-center gap-1.5 ${
                RPG_STATE.isSelectionMode
                  ? 'bg-rose-500 text-white shadow-md'
                  : 'bg-amber-500/15 text-amber-500 border border-amber-500/40 hover:bg-amber-500/25'
              }">
                <span>${RPG_STATE.isSelectionMode ? "✕ Отмена" : "☑️ Выбрать для продажи"}</span>
              </button>
            ` : ""}
          </div>

          <!-- Quick Bulk Select Filters -->
          ${inv.length > 0 ? `
            <div class="p-2 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200/60 dark:border-slate-700/60 flex items-center justify-between gap-1 flex-wrap text-[10.5px]">
              <span class="text-slate-400 font-bold">Выбрать:</span>
              <div class="flex items-center gap-1 flex-wrap font-extrabold">
                <button onclick="window.RPG.selectAllByRarity('common')" class="px-2 py-0.5 rounded-lg bg-slate-200 dark:bg-slate-700 hover:bg-slate-300 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200">
                  ⬜ Серые
                </button>
                <button onclick="window.RPG.selectAllByRarity('uncommon')" class="px-2 py-0.5 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-500 border border-emerald-500/30">
                  🟩 Зеленые
                </button>
                <button onclick="window.RPG.selectAllByRarity('rare')" class="px-2 py-0.5 rounded-lg bg-sky-500/15 hover:bg-sky-500/25 text-sky-500 border border-sky-500/30">
                  🟦 Синие
                </button>
                <button onclick="window.RPG.selectAllByRarity()" class="px-2 py-0.5 rounded-lg bg-amber-500/15 hover:bg-amber-500/25 text-amber-500 border border-amber-500/30">
                  ✨ Выбрать всё
                </button>
                ${(RPG_STATE.selectedItemUids && RPG_STATE.selectedItemUids.size > 0) ? `
                  <button onclick="window.RPG.clearItemSelection()" class="px-2 py-0.5 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 text-rose-500 border border-rose-500/30">
                    Сброс (${RPG_STATE.selectedItemUids.size})
                  </button>
                ` : ""}
              </div>
            </div>
          ` : ""}

          ${
            inv.length === 0
              ? `
            <div class="py-6 text-center text-slate-400 text-xs">
              Инвентарь пуст. Зачищайте этажи, чтобы получать наградные сундуки!
            </div>
          `
              : `
            <div class="grid grid-cols-3 sm:grid-cols-4 gap-2">
              ${inv.map((item) => renderInventoryItemTileHTML(item)).join("")}
            </div>
          `
          }

          <!-- Floating Bulk Sell Action Bar -->
          ${(RPG_STATE.selectedItemUids && RPG_STATE.selectedItemUids.size > 0) ? `
            <div class="sticky bottom-16 z-30 p-3.5 rounded-2xl bg-gradient-to-r from-amber-500/25 via-yellow-500/20 to-amber-500/25 border-2 border-amber-500 flex items-center justify-between gap-3 shadow-xl backdrop-blur-md animate-scale-up">
              <div>
                <div class="flex items-center gap-1.5">
                  <span class="text-xs font-black text-amber-500 dark:text-amber-400">
                    Выбрано: ${RPG_STATE.selectedItemUids.size} шт.
                  </span>
                </div>
                <span class="text-[11px] font-black text-emerald-600 dark:text-emerald-400 block">
                  Вы получите: +${getSelectedItemsTotalPrice()} 🪙
                </span>
              </div>
              <div class="flex items-center gap-1.5">
                <button onclick="window.RPG.clearItemSelection()" class="px-2.5 py-2 rounded-xl bg-slate-800 text-slate-300 font-bold text-xs hover:bg-slate-700">
                  ✕
                </button>
                <button onclick="window.RPG.sellSelectedItems()" class="px-4 py-2 rounded-xl bg-gradient-to-r from-amber-500 to-yellow-400 hover:from-amber-400 active:scale-95 text-slate-950 font-black text-xs shadow-md flex items-center gap-1">
                  <span>💰</span>
                  <span>Продать за +${getSelectedItemsTotalPrice()} 🪙</span>
                </button>
              </div>
            </div>
          ` : ""}
        </div>

        <!-- Shop Banner in Hero Tab -->
        <div class="p-3 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-800 to-emerald-950 border border-emerald-500/30 text-white flex items-center justify-between shadow-sm">
          <div class="flex items-center gap-2.5">
            <span class="text-2xl">🏪</span>
            <div>
              <span class="text-xs font-black block text-emerald-400">Лавка Снаряжения</span>
              <span class="text-[10px] text-slate-300">Покупка оружия, брони, реликвий и зелий</span>
            </div>
          </div>
          <button onclick="window.RPG.openShopModal()" class="px-3 py-1.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 active:scale-95 text-slate-950 font-black text-xs shadow-md">
            В лавку →
          </button>
        </div>

        <!-- Switch Hero & Hardcore Reset Buttons -->
        <div class="text-center pt-2 space-y-2">
          <button onclick="window.RPG.openHeroPicker()" class="text-xs font-bold text-slate-400 hover:text-amber-500 transition-colors block mx-auto">
            Сменить героя natarGRP 🔄
          </button>
          <button onclick="window.RPG.resetCharacter()" class="text-[11px] font-bold text-rose-500/80 hover:text-rose-400 transition-colors block mx-auto underline">
            Сбросить персонажа (Хардкорный старт с 1 ур.) ⚠️
          </button>
        </div>
      </div>
    `;
  }

  function renderEquippedSlotHTML(slotKey, label, defaultIcon, item) {
    if (!item) {
      return `
        <div onclick="window.RPG.openSlotFilterModal('${slotKey}')" class="cursor-pointer p-2.5 rounded-2xl border-2 border-dashed border-slate-300 dark:border-slate-700 hover:border-amber-500 text-center space-y-1 transition-all active:scale-95">
          <span class="text-2xl opacity-40">${defaultIcon}</span>
          <span class="block text-[10px] font-bold text-slate-400">${label}</span>
          <span class="block text-[9px] text-amber-500 font-bold">+ Надеть</span>
        </div>
      `;
    }

    const rInfo = RARITY_MAP[item.rarity] || RARITY_MAP.common;
    const forgeTag = item.forge_level > 0 ? `+${item.forge_level}` : "";

    return `
      <div onclick="window.RPG.openItemModal('${item.uid}')" class="cursor-pointer p-2.5 rounded-2xl border-2 ${rInfo.color} text-center space-y-1 hover:scale-105 transition-transform relative group">
        <div class="relative inline-block">
          <span class="text-2xl">${item.icon || defaultIcon}</span>
          ${
            forgeTag
              ? `<span class="absolute -top-1 -right-2 px-1 rounded-md bg-amber-500 text-slate-950 font-black text-[9px] shadow-sm">${forgeTag}</span>`
              : ""
          }
        </div>
        <span class="block text-[10.5px] font-black truncate">${item.name}</span>
        <div class="flex items-center justify-center gap-1 flex-wrap">
          <span class="text-[9px] font-extrabold px-1.5 py-0.2 rounded-md ${rInfo.badge}">${rInfo.name}</span>
          ${(() => {
            const activeDef = Object.values(ACTIVE_ITEM_DEFINITIONS).find(d => d.match(item));
            return activeDef ? `<span class="text-[8px] font-black px-1 py-0.2 rounded bg-amber-500/20 text-amber-400 border border-amber-500/40 animate-pulse">⚡ [${activeDef.shortName}]</span>` : "";
          })()}
        </div>
        <button onclick="event.stopPropagation(); window.RPG.openSlotFilterModal('${slotKey}')" class="w-full mt-1 py-0.5 rounded-lg bg-slate-800/80 hover:bg-amber-500 text-slate-300 hover:text-slate-950 text-[9px] font-bold border border-slate-700 hover:border-amber-400 flex items-center justify-center gap-1 transition-colors">
          <span>🔄</span>
          <span>Сменить</span>
        </button>
      </div>
    `;
  }

  function renderInventoryItemTileHTML(item) {
    const rInfo = RARITY_MAP[item.rarity] || RARITY_MAP.common;
    const isSelected = RPG_STATE.selectedItemUids && RPG_STATE.selectedItemUids.has(item.uid);
    const forgeTag = (item.forge_level || item.upgrade) > 0 ? `+${item.forge_level || item.upgrade}` : "";
    const slotBadge = item.slot_name || (item.slot === "weapon" ? "Оружие" : item.slot === "armor" ? "Броня" : item.slot === "relic" ? "Реликвия" : "Зелье");
    const isPotion = item.slot === "consumable" || item.type === "potion";
    const p = RPG_STATE.profile || {};
    const eq = p.equipment || {};
    const targetSlot = (item.slot || item.type || "").toLowerCase();
    const isEquippable = ["weapon", "armor", "relic"].includes(targetSlot) || targetSlot.startsWith("slot_");
    const currEquipped = isEquippable ? (eq[targetSlot] || eq[item.slot] || eq[item.type]) : null;
    const sellPrice = getItemSellPrice(item);

    let actionBtnHTML = "";
    if (!RPG_STATE.isSelectionMode) {
      if (isPotion) {
        actionBtnHTML = `
          <button onclick="event.stopPropagation(); window.RPG.useConsumable('${item.uid}')" class="w-full mt-1.5 py-1 rounded-xl bg-emerald-600 hover:bg-emerald-500 active:scale-95 text-white font-black text-[9.5px] shadow-sm flex items-center justify-center gap-1 transition-all">
            <span>🧪</span>
            <span>Пить ${item.count > 1 ? `(${item.count})` : ""}</span>
          </button>
        `;
      } else if (isEquippable) {
        if (currEquipped) {
          actionBtnHTML = `
            <button onclick="event.stopPropagation(); window.RPG.equipItem('${item.uid}')" class="w-full mt-1.5 py-1 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 active:scale-95 text-white font-black text-[9.5px] shadow-sm flex items-center justify-center gap-1 transition-all">
              <span>🔄</span>
              <span>Сменить</span>
            </button>
          `;
        } else {
          actionBtnHTML = `
            <button onclick="event.stopPropagation(); window.RPG.equipItem('${item.uid}')" class="w-full mt-1.5 py-1 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 active:scale-95 text-white font-black text-[9.5px] shadow-sm flex items-center justify-center gap-1 transition-all">
              <span>⚔️</span>
              <span>Надеть</span>
            </button>
          `;
        }
      }
    } else {
      actionBtnHTML = `
        <div class="w-full mt-1 py-1 text-center font-black text-[10px] rounded-lg ${isSelected ? 'bg-amber-500 text-slate-950' : 'bg-slate-100 dark:bg-slate-700 text-slate-400'}">
          ${isSelected ? `✓ ВЫБРАНО (+${sellPrice} 🪙)` : `+${sellPrice} 🪙`}
        </div>
      `;
    }

    return `
      <div onclick="window.RPG.handleInventoryItemClick('${item.uid}')" class="cursor-pointer p-2.5 rounded-2xl border-2 ${isSelected ? 'border-amber-400 ring-3 ring-amber-400/60 scale-102 bg-amber-500/15 shadow-md shadow-amber-500/20' : rInfo.color} flex flex-col justify-between hover:scale-102 active:scale-98 transition-all relative space-y-1 bg-white/70 dark:bg-slate-800/80 shadow-xs">
        <!-- Multi-select Checkbox Badge -->
        <button onclick="event.stopPropagation(); window.RPG.toggleItemSelection('${item.uid}')" class="absolute top-1.5 left-1.5 w-6 h-6 rounded-lg flex items-center justify-center text-xs font-black border transition-all z-10 ${isSelected ? 'bg-amber-500 border-amber-300 text-slate-950 shadow-md scale-110' : 'bg-slate-900/80 border-slate-600 text-slate-400 hover:border-amber-400 hover:text-white'}">
          ${isSelected ? "✓" : "○"}
        </button>
        <div class="flex items-center justify-between">
          <span class="text-[8.5px] font-extrabold px-1.5 py-0.2 rounded bg-black/20 ml-6">${slotBadge}</span>
          <div class="flex items-center gap-1">
            ${(() => {
              const activeDef = Object.values(ACTIVE_ITEM_DEFINITIONS).find(d => d.match(item));
              return activeDef ? `<span class="px-1 rounded bg-amber-500/20 text-amber-400 text-[8px] font-black border border-amber-500/30">⚡ АКТИВКА</span>` : "";
            })()}
            ${forgeTag ? `<span class="px-1.5 rounded-md bg-amber-500 text-slate-950 font-black text-[8.5px] shadow-sm">${forgeTag}</span>` : ""}
          </div>
        </div>
        <div class="text-center py-1">
          <span class="text-2xl block">${item.icon || "📦"}</span>
          <span class="block text-[10.5px] font-black truncate mt-0.5">${item.name}</span>
        </div>
        <div class="text-center min-h-[14px]">
          <span class="text-[8.5px] text-slate-500 dark:text-slate-400 line-clamp-2 block leading-tight">${item.bonus_desc || ""}</span>
        </div>
        ${actionBtnHTML}
      </div>
    `;
  }

  // ===========================================================================
  // 2. FARM TAB (2D ACTION ARENA OR FAST SIM)
  // ===========================================================================

  function renderFarmTabHTML() {
    const p = RPG_STATE.profile || {};
    const floor = p.dungeon_floor || 1;
    const isArena = RPG_STATE.farmMode === "arena";
    const isRaidBoss = !!ARENA.isRaidBossBattle;
    const isDungeonBoss = !!(ARENA.isBossActive && ARENA.topDownMode);
    const bossObj = ARENA.bossEntity || ARENA.currentRaidBoss || {};

    if (isRaidBoss) {
      return `
        <div class="space-y-3.5">
          <!-- Brawl Boss Fight Header -->
          <div class="p-3.5 rounded-2xl bg-gradient-to-r from-red-950 via-purple-950 to-amber-950 text-white border-2 border-red-500/50 shadow-xl flex items-center justify-between">
            <div class="flex items-center gap-3">
              <span class="text-3xl animate-bounce">👑</span>
              <div>
                <div class="flex items-center gap-2">
                  <h3 class="text-sm font-black tracking-wide uppercase text-amber-400">
                    БОЙ С БОССОМ: ${bossObj.name || "БОСС"}
                  </h3>
                  <span class="text-[9px] px-2 py-0.5 rounded-full bg-red-600 text-white font-extrabold uppercase shadow-sm">BRAWL 2D</span>
                </div>
                <p class="text-[11px] text-purple-200 font-medium">
                  Джойстик — беги в 360°, уворачивайся от тарана и ракет! Отпусти — автострельба!
                </p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <button onclick="window.RPG.toggleBossPartyMode()" class="px-2.5 py-1.5 rounded-xl bg-slate-800/90 hover:bg-slate-700 active:scale-95 text-white font-bold text-xs border border-slate-600 flex items-center gap-1 shadow-md">
                <span>${(ARENA.bossPartyMode || "trio") === "trio" ? "👥 3 Игрока" : "👤 1 Игрок"}</span>
              </button>
              <button onclick="window.RPG.exitRaidBossBattle()" class="px-3 py-1.5 rounded-xl bg-slate-800/90 hover:bg-slate-700 active:scale-95 text-slate-300 font-bold text-xs border border-slate-600 flex items-center gap-1 shadow-md">
                <span>✕ В лобби</span>
              </button>
            </div>
          </div>

          ${renderActionArenaHTML()}
        </div>
      `;
    }

    return `
      <div class="space-y-3.5">
        <!-- Floor Header & Mode Switcher -->
        <div class="p-3.5 rounded-2xl bg-gradient-to-r from-red-950 via-slate-900 to-amber-950 text-white border border-red-500/30 shadow-md flex items-center justify-between">
          <div>
            <div class="flex items-center gap-2">
              <span class="text-base">⚔️</span>
              <h3 class="text-sm font-black tracking-wide uppercase">
                Этаж ${floor} Катакомб
              </h3>
            </div>
            <p class="text-[11px] text-amber-200/80 font-medium">
              ${isArena ? (isDungeonBoss ? `👑 Бой с боссом: ${bossObj.name || "Босс этажа"}!` : "Защита тропы! Крипы бегут справа — руби и отбивай боссов!") : "Автоматическое месилово крипов"}
            </p>
          </div>

          <!-- Mode Toggle Buttons -->
          <div class="flex items-center p-1 rounded-xl bg-slate-800/80 border border-slate-700 text-[10px] font-bold">
            <button onclick="window.RPG.setFarmMode('arena')" class="px-2.5 py-1 rounded-lg transition-all ${
              isArena ? "bg-amber-500 text-slate-950 font-black" : "text-slate-400 hover:text-white"
            }">
              🎮 Арена
            </button>
            <button onclick="window.RPG.setFarmMode('sim')" class="px-2.5 py-1 rounded-lg transition-all ${
              !isArena ? "bg-amber-500 text-slate-950 font-black" : "text-slate-400 hover:text-white"
            }">
              ⚡ Авто
            </button>
          </div>
        </div>

        ${isArena ? renderActionArenaHTML() : renderFastSimHTML()}
      </div>
    `;
  }

  function renderActionArenaHTML() {
    const p = RPG_STATE.profile || {};
    const stats = p.stats || {};
    const cfg = getHeroSkillConfig();
    const isBossFight = !!(ARENA.isRaidBossBattle || (ARENA.isBossActive && ARENA.topDownMode));
    const s1CdSec = ARENA.skill1Cooldown > 0 ? Math.ceil(ARENA.skill1Cooldown / 60) : 0;
    const ultCdSec = ARENA.ultCooldown > 0 ? Math.ceil(ARENA.ultCooldown / 60) : 0;

    return `
      <div class="space-y-2">
                <!-- Canvas Arena Element -->
        <div class="relative w-full rounded-3xl overflow-hidden border-2 border-amber-500/40 shadow-2xl bg-slate-950">
          <canvas id="rpg-action-canvas" class="w-full ${isBossFight ? 'h-[520px]' : 'h-[320px]'} block cursor-crosshair"></canvas>

          ${ARENA.isRaidBossBattle ? `
          <div class="absolute top-3 left-3 z-20 flex items-center gap-1.5">
            <button onclick="window.RPG.exitRaidBossBattle()"
              class="h-7 px-2.5 rounded-full bg-slate-900/90 border border-slate-700 text-slate-300 font-bold text-[10px] flex items-center gap-1.5 shadow-lg active:scale-95 transition-all">
              <span>✕ В лобби боссов</span>
            </button>
          </div>
          ` : ""}

          <!-- Virtual Touch Joystick (Active only during boss battles) -->
          ${isBossFight ? `<div id="rpg-virtual-joystick-zone"
               class="absolute bottom-3 left-3 w-24 h-24 flex items-center justify-center pointer-events-auto z-30 select-none touch-none">
            <div id="rpg-joystick-base" class="relative w-20 h-20 rounded-full border-2 border-amber-400/50 bg-slate-900/80 shadow-2xl flex items-center justify-center backdrop-blur-md ring-2 ring-amber-500/20">
              <span class="absolute top-1 text-[9px] text-amber-300/50">▲</span>
              <span class="absolute bottom-1 text-[9px] text-amber-300/50">▼</span>
              <span class="absolute left-1.5 text-[9px] text-amber-300/50">◀</span>
              <span class="absolute right-1.5 text-[9px] text-amber-300/50">▶</span>
              <div id="rpg-joystick-knob" class="w-8 h-8 rounded-full bg-gradient-to-tr from-amber-500 to-yellow-300 shadow-xl border-2 border-white pointer-events-none flex items-center justify-center">
                <span class="text-xs font-black text-slate-950">🕹️</span>
              </div>
            </div>
          </div>` : ""}

          <!-- Active Items (above joystick) -->
          <div class="absolute bottom-28 left-3 z-20 flex flex-col gap-2">
            <button id="rpg-btn-potion" ontouchstart="event.preventDefault(); window.RPG.usePotionAction()" onmousedown="event.preventDefault(); window.RPG.usePotionAction()" onclick="window.RPG.usePotionAction()" title="Зелье / Сыр [F / 1]" class="w-10 h-10 rounded-2xl bg-emerald-600/95 border-2 border-emerald-300 text-white font-bold text-lg flex items-center justify-center shadow-lg active:scale-90 transition-transform relative">
              <span>🧪</span>
              <span id="rpg-cd-potion" class="text-[8px] font-black absolute bottom-0.5 pointer-events-none drop-shadow"></span>
            </button>
            ${(window.RPG.getEquippedActiveItems ? window.RPG.getEquippedActiveItems() : []).map((act, idx) => {
              const cdSec = act.currentCd > 0 ? Math.ceil(act.currentCd / 60) : 0;
              return `
              <button id="rpg-btn-item-${idx}" ontouchstart="event.preventDefault(); window.RPG.useActiveItemAction(${idx})" onmousedown="event.preventDefault(); window.RPG.useActiveItemAction(${idx})" onclick="window.RPG.useActiveItemAction(${idx})" title="${act.name}" class="w-10 h-10 rounded-2xl ${cdSec > 0 ? 'bg-slate-800/80 border border-slate-700 opacity-60' : 'bg-indigo-600/95 border-2 border-indigo-300'} text-white font-bold text-lg flex flex-col items-center justify-center shadow-lg active:scale-90 transition-transform relative">
                <span class="text-base">${act.def.icon || '✨'}</span>
                <span id="rpg-cd-item-${idx}" class="text-[8px] font-bold absolute bottom-0.5">${cdSec > 0 ? cdSec + 'с' : ''}</span>
              </button>`;
            }).join('')}
          </div>

          <!-- Right Action Buttons (Attack, Dash / Roll, Skill 1, Ultimate) -->
          <div class="absolute bottom-3 right-3 flex flex-col gap-1.5 z-20">
            <!-- Top row: Skill 1 + Ultimate -->
            <div class="flex items-center gap-1.5">
              <!-- Hero Skill 1 Button [E] -->
              <button id="rpg-btn-skill1" ontouchstart="event.preventDefault(); window.RPG.castSkill1Action()" onmousedown="event.preventDefault(); window.RPG.castSkill1Action()" onclick="window.RPG.castSkill1Action()" title="${cfg.skill1Name} [E]" class="w-11 h-11 rounded-2xl ${s1CdSec > 0 ? 'bg-slate-800/80 border border-slate-700 opacity-60' : 'bg-gradient-to-r from-blue-600 to-cyan-600 border-2 border-cyan-400'} text-white font-black text-sm flex flex-col items-center justify-center shadow-lg active:scale-90 transition-transform">
                <span class="text-base">${cfg.skill1Icon || '⚡'}</span>
                <span id="rpg-cd-skill1" class="text-[8px] font-bold">${s1CdSec > 0 ? `${s1CdSec}с` : 'Скилл'}</span>
              </button>

              <!-- Hero Ultimate Skill Button [Q] -->
              <button id="rpg-btn-ult" ontouchstart="event.preventDefault(); window.RPG.castUltimateAction()" onmousedown="event.preventDefault(); window.RPG.castUltimateAction()" onclick="window.RPG.castUltimateAction()" title="${cfg.ultName} [Q]" class="w-11 h-11 rounded-2xl ${ultCdSec > 0 ? 'bg-slate-800/80 border border-slate-700 opacity-60' : 'bg-gradient-to-r from-purple-600 to-indigo-600 border-2 border-purple-400'} text-white font-black text-sm flex flex-col items-center justify-center shadow-lg active:scale-90 transition-transform">
                <span class="text-base">${cfg.ultIcon || '🌟'}</span>
                <span id="rpg-cd-ult" class="text-[8px] font-bold">${ultCdSec > 0 ? `${ultCdSec}с` : 'Ульта'}</span>
              </button>
            </div>

            <!-- Bottom row: Attack + Dash (Dash only visible during boss fight) -->
            <div class="flex items-center gap-1.5">
              <!-- Attack / Shoot Button [Space / Click] -->
              <button id="rpg-btn-attack" ontouchstart="event.preventDefault(); window.RPG.playerSlashAttackAction()" onclick="window.RPG.playerSlashAttackAction()" title="Атака [Пробел / Клик]"
                class="w-11 h-11 rounded-2xl bg-gradient-to-r from-red-600 via-rose-600 to-amber-500 border-2 border-amber-300 text-white font-black text-xs flex flex-col items-center justify-center shadow-lg shadow-red-600/40 active:scale-90 transition-transform">
                <span class="text-base leading-none">⚔️</span>
                <span class="text-[8px] font-bold mt-0.5">АТАК</span>
              </button>

              ${isBossFight ? `
              <!-- Dash / Roll Button (Boss battle only) -->
              <button ontouchstart="event.preventDefault(); window.RPG.playerDashRollAction()" onmousedown="event.preventDefault(); window.RPG.playerDashRollAction()" onclick="window.RPG.playerDashRollAction()" title="Рывок / Кувырок [Shift / C]"
                class="w-11 h-11 rounded-2xl ${ARENA.dodgeCooldown > 0 ? 'bg-slate-800/80 border border-slate-700 opacity-60' : 'bg-gradient-to-r from-sky-500 to-cyan-500 border-2 border-sky-300 shadow-sky-500/40'} text-white font-black text-sm flex flex-col items-center justify-center shadow-lg active:scale-90 transition-all">
                <span class="text-base">🌀</span>
                <span class="text-[8px] leading-tight font-bold">${ARENA.dodgeCooldown > 0 ? Math.ceil(ARENA.dodgeCooldown / 60) + 'с' : 'Рывок'}</span>
              </button>
              ` : ""}
            </div>
          </div>
        </div>

        <!-- Controls Guide Toolbar -->
        <div class="p-2.5 rounded-2xl bg-slate-100 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 text-[10.5px] text-slate-500 dark:text-slate-400 flex flex-wrap items-center justify-between gap-2">
          <div class="flex items-center gap-1.5">
            <span>${isBossFight ? '🕹️ <b>Бой с боссом</b>: джойстик — перемещение, [⚔️ Атака] — огонь, [🌀 Рывок] — уворот!' : '⚔️ <b>Фарм волн</b>: [⚔️ Атака] / Авто-бой — зачистка крипов, сбор золота и лута!'}</span>
          </div>
          <div class="flex items-center gap-2">
            <!-- Auto-Attack ON / OFF Toggle Button (Wave/Dungeon/Arena) -->
            <button id="rpg-auto-attack-btn" onclick="window.RPG.toggleArenaAutoAttack()" class="px-2.5 py-1 rounded-xl text-xs font-black transition-all ${ARENA.player.autoAttack ? 'bg-amber-500/20 text-amber-500 border border-amber-500/40 shadow-sm' : 'bg-slate-200 dark:bg-slate-700 text-slate-500'}" title="Включить или выключить автоматический удар">
              Авто-удар: ${ARENA.player.autoAttack ? "ВКЛ ⚔️" : "ВЫКЛ ✋"}
            </button>
            <button id="rpg-wave-confirm-btn" onclick="window.RPG.toggleArenaWaveConfirm()" class="px-2.5 py-1 rounded-xl text-xs font-black transition-all ${ARENA.autoAdvanceWaves ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-sm' : 'bg-slate-200 dark:bg-slate-700 text-slate-500'}" title="${ARENA.autoAdvanceWaves ? 'Подтверждение волн отключено' : 'Подтверждение волн включено'}">
              Авто-волны: ${ARENA.autoAdvanceWaves ? "ВКЛ ⏩" : "ВЫКЛ ⏸️"}
            </button>
          </div>
        </div>
      </div>
    `;
  }

  function renderFastSimHTML() {
    const p = RPG_STATE.profile || {};
    const stats = p.stats || {};
    const battle = RPG_STATE.lastBattle;

    return `
      <div class="space-y-3.5">
        <!-- Arena Display -->
        <div class="theme-card p-4 rounded-3xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm space-y-4">
          <!-- Floor & Wave Synchronized Status -->
          <div class="flex items-center justify-between px-3 py-2 rounded-2xl bg-slate-100 dark:bg-slate-900/60 border border-slate-200/60 dark:border-slate-700/60 text-xs font-bold text-slate-600 dark:text-slate-300">
            <span>⚔️ Этаж ${p.dungeon_floor || 1} • Волна <b class="text-amber-500">${((p.dungeon_cleared || 0) % 20) + 1} / 20</b></span>
            <span class="ml-3">🐉 Боссов убито: <b class="text-emerald-400">${p.boss_kills || 0}</b></span>
            <span>🏆 Зачищено всего: <b class="text-emerald-500">${p.dungeon_cleared || 0} волн</b></span>
          </div>

          <div class="flex items-center justify-between gap-3">
            <!-- Hero Side -->
            <div class="flex-1 text-center space-y-1.5 p-3 rounded-2xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200/60 dark:border-slate-700/60">
              <div class="text-3xl">${p.class_avatar || p.class_icon || "🛡️"}</div>
              <div class="text-xs font-black truncate">${p.user_name || p.class_name}</div>
              <div class="space-y-1">
                ${(() => {
                  const hMax = battle?.hero_hp_max || stats.hp_max || 180;
                  const hCur = battle?.hero_hp_left !== undefined ? battle.hero_hp_left : hMax;
                  const hPct = Math.max(0, Math.min(100, Math.round((hCur / hMax) * 100)));
                  return `
                    <div class="flex justify-between text-[10px] font-bold text-slate-500 dark:text-slate-400">
                      <span>HP</span>
                      <span class="${hCur <= 0 ? 'text-rose-500 font-black' : ''}">${hCur.toLocaleString()} / ${hMax.toLocaleString()}</span>
                    </div>
                    <div class="w-full h-2 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                      <div class="h-full ${hCur <= 0 ? 'bg-rose-500' : 'bg-emerald-500'} transition-all duration-300" style="width: ${hPct}%"></div>
                    </div>
                  `;
                })()}
              </div>
            </div>

            <!-- VS Badge -->
            <div class="flex flex-col items-center justify-center">
              <span class="text-xs font-black px-2.5 py-1 rounded-xl bg-red-500/10 text-red-600 border border-red-500/30">VS</span>
            </div>

            <!-- Enemy Side -->
            <div class="flex-1 text-center space-y-1.5 p-3 rounded-2xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200/60 dark:border-slate-700/60">
              <div class="text-3xl">${battle?.enemy_icon || "👾"}</div>
              <div class="text-xs font-black truncate">${battle?.enemy_name || "Пачка крипов"}</div>
              <div class="space-y-1">
                ${(() => {
                  const eMax = battle?.enemy_hp_max || 100;
                  const eCur = battle?.enemy_hp_left !== undefined ? battle.enemy_hp_left : (battle?.victory ? 0 : eMax);
                  const ePct = Math.max(0, Math.min(100, Math.round((eCur / eMax) * 100)));
                  return `
                    <div class="flex justify-between text-[10px] font-bold text-slate-500 dark:text-slate-400">
                      <span>HP Врагов</span>
                      <span>${eCur <= 0 ? '💀 0 (Повержен)' : `${eCur.toLocaleString()} (${ePct}%)`}</span>
                    </div>
                    <div class="w-full h-2 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                      <div class="h-full bg-red-500 transition-all duration-300" style="width: ${ePct}%"></div>
                    </div>
                  `;
                })()}
              </div>
            </div>
          </div>

          <!-- Streak & Victory banner if just fought -->
          ${
            battle
              ? `
            <div class="p-3 rounded-2xl ${
              battle.victory
                ? "bg-gradient-to-r from-amber-500/10 via-emerald-500/10 to-amber-500/10 border border-emerald-500/30 text-emerald-700 dark:text-emerald-300"
                : battle.is_draw
                  ? "bg-gradient-to-r from-amber-500/10 to-orange-500/10 border border-amber-500/40 text-amber-700 dark:text-amber-300"
                  : "bg-red-500/10 border border-red-500/30 text-red-600"
            } text-center space-y-1">
              <div class="text-xs font-black tracking-wide">
                ${
                  battle.victory
                    ? (battle.streak_title || "ВОЛНА ЗАЧИЩЕНА! 🏆")
                    : battle.is_draw
                      ? `⏳ НИЧЬЯ (ТАЙМАУТ ${battle.rounds_fought || 400} РАУНДОВ)!`
                      : "💀 ВАШ ГЕРОЙ ПАЛ В БОЮ!"
                }
              </div>
              ${battle.description ? `<div class="text-[10.5px] font-medium opacity-90">${battle.description}</div>` : ""}
              ${
                battle.victory
                  ? `
                <div class="flex items-center justify-center gap-3 text-[11px] font-bold">
                  <span>+${battle.gold_earned} 🪙</span>
                  <span>+${battle.xp_earned} XP</span>
                  ${battle.crits_count > 0 ? `<span>🔥 ${battle.crits_count} критов</span>` : ""}
                  ${battle.rounds_fought ? `<span>⏱️ ${battle.rounds_fought} раундов</span>` : ""}
                </div>
              `
                  : ""
              }
            </div>
          `
              : ""
          }

          <!-- Action Controls -->
          <div class="grid grid-cols-2 gap-2">
            <button onclick="window.RPG.slashWave()" ${RPG_STATE.isFighting ? "disabled" : ""} class="py-3 px-4 rounded-2xl bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 active:scale-95 text-white font-black text-sm shadow-md shadow-red-600/20 flex items-center justify-center gap-2 transition-all ${
              RPG_STATE.isFighting ? "opacity-60 cursor-not-allowed" : ""
            }">
              <span>⚔️</span>
              <span>${RPG_STATE.isFighting ? "Месилово..." : "Зарубить волну"}</span>
            </button>

            <button onclick="window.RPG.toggleAutoFarm()" class="py-3 px-4 rounded-2xl ${
              RPG_STATE.autoFarm
                ? "bg-amber-500 text-slate-950 font-black animate-pulse"
                : "bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200 font-bold hover:bg-slate-300"
            } active:scale-95 text-sm shadow-sm flex items-center justify-center gap-2 transition-all">
              <span>⚡</span>
              <span>${RPG_STATE.autoFarm ? "Стоп авто-фарм" : "Авто-месилово"}</span>
            </button>
          </div>
        </div>

        <!-- Combat Feed / Log -->
        <div class="theme-card p-3.5 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm space-y-2">
          <div class="flex items-center justify-between text-xs font-black uppercase text-slate-500 dark:text-slate-400">
            <span>📜 Лог сражения</span>
            <span>Сессия: ${RPG_STATE.killsSession} волн</span>
          </div>

          <div class="p-2.5 rounded-xl bg-slate-100 dark:bg-slate-900/60 max-h-36 overflow-y-auto space-y-1 font-mono text-[11px]">
            ${
              RPG_STATE.combatLog.length === 0
                ? `<div class="text-slate-400 text-center py-2">Нажмите «Зарубить волну» для фарма золота и опыта!</div>`
                : RPG_STATE.combatLog.map((line) => `<div class="leading-tight text-slate-700 dark:text-slate-300">${line}</div>`).join("")
            }
          </div>
        </div>
      </div>
    `;
  }

  // ===========================================================================
  // 3. CO-OP BOSS RAIDS HTML
  // ===========================================================================

  function renderCoopRaidsHTML() {
    if (RPG_STATE.coopRoomId && RPG_STATE.coopRoomData) {
      return renderActiveCoopBattleHTML();
    }

        const TAG_MAP = {
      golem: { tag: "Начальный", color: "border-stone-500/60 bg-stone-500/5" },
      lich: { tag: "Нежить", color: "border-cyan-500/60 bg-cyan-500/5" },
      tormentor: { tag: "Магический", color: "border-purple-500/60 bg-purple-500/5" },
      dragon: { tag: "Рейдовый", color: "border-rose-500/60 bg-rose-500/5" },
      pudge_boss: { tag: "Мясник", color: "border-emerald-600/60 bg-emerald-600/5" },
      faceless_void: { tag: "Хронос", color: "border-purple-600/60 bg-purple-600/5" },
      roshan: { tag: "Хозяин Ямы", color: "border-amber-500/60 bg-amber-500/5" },
      tidehunter: { tag: "Сверх-Ранг", color: "border-teal-500/60 bg-teal-500/5" },
      sf_boss: { tag: "Сверх-Ранг", color: "border-red-600/60 bg-red-600/5" },
      necrophos: { tag: "Сверх-Ранг", color: "border-emerald-600/60 bg-emerald-600/5" },
      terrorblade: { tag: "Сверх-Ранг", color: "border-violet-700/60 bg-violet-700/5" },
      invoker_boss: { tag: "Сверх-Ранг", color: "border-yellow-500/60 bg-yellow-500/5" },
      chaos_knight: { tag: "Сверх-Ранг", color: "border-amber-600/60 bg-amber-600/5" },
      dark_tormentor: { tag: "Сверх-Ранг", color: "border-purple-700/60 bg-purple-700/5" },
      storm_spirit: { tag: "Сверх-Ранг", color: "border-sky-500/60 bg-sky-500/5" },
      doom: { tag: "Сверх-Ранг", color: "border-orange-600/60 bg-orange-600/5" },
      primal_beast: { tag: "Сверх-Ранг", color: "border-red-700/60 bg-red-700/5" },
      phantom_roshan: { tag: "Сверх-Ранг", color: "border-cyan-400/60 bg-cyan-400/5" },
      tinker_boss: { tag: "Сверх-Босс", color: "border-yellow-600/60 bg-yellow-600/5" },
      enigma: { tag: "Финальный Босс", color: "border-indigo-600/60 bg-indigo-600/5" }
    };

    const bosses = (RPG_STATE.coopBosses && RPG_STATE.coopBosses.length > 0)
      ? RPG_STATE.coopBosses.map(b => ({
          id: b.id,
          name: b.name,
          icon: b.icon || "🗿",
          hp: b.hp_display ? `${b.hp_display} HP` : `${formatCompact(b.max_hp || b.hp)} HP`,
          desc: b.desc || "Могущественный рейд-босс",
          tag: (TAG_MAP[b.id] || {}).tag || "Рейдовый",
          color: (TAG_MAP[b.id] || {}).color || "border-purple-500/60 bg-purple-500/5"
        }))
      : [
          { id: "golem", name: "Древний Гранитный Голем", icon: "🗿", hp: "75,000 HP", desc: "[75k HP] Гигант из древнего гранита с тяжелыми разломами земли.", tag: "Начальный", color: "border-stone-500/60 bg-stone-500/5" },
          { id: "lich", name: "Архилич Некрополя", icon: "☠️", hp: "225,000 HP", desc: "[225k HP] Владыка темных заклятий, ледяных сфер и телепортации.", tag: "Нежить", color: "border-cyan-500/60 bg-cyan-500/5" },
          { id: "tormentor", name: "Древний Терзатель", icon: "🔮", hp: "700,000 HP", desc: "[700k HP] Отражает входящий урон кристальным панцирем. Дропает Shard!", tag: "Магический", color: "border-purple-500/60 bg-purple-500/5" },
          { id: "dragon", name: "Дракон Инферно", icon: "🌋", hp: "2.2M HP", desc: "[2.2M HP] Испепеляет арену потоками лавы и огненными взмахами крыльев.", tag: "Рейдовый", color: "border-rose-500/60 bg-rose-500/5" },
          { id: "pudge_boss", name: "Мясник из Чрева (Pudge)", icon: "🪝", hp: "7.5M HP", desc: "[7.5M HP] Тесак, ржавый крюк цепью и отравляющая вонь гнили.", tag: "Мясник", color: "border-emerald-600/60 bg-emerald-600/5" },
          { id: "faceless_void", name: "Хроно-Владыка (Faceless Void)", icon: "⏳", hp: "25M HP", desc: "[25M HP] Повелитель времени, двойные баши и купол Хроносферы.", tag: "Хронос", color: "border-purple-600/60 bg-purple-600/5" },
          { id: "roshan", name: "Рошан Свирепый (Roshan)", icon: "🐲", hp: "85M HP", desc: "[85M HP] КУЛЬТОВЫЙ ХОЗЯИН ЯМЫ! Дропает Aegis of the Immortal, Сыр и Divine Rapier!", tag: "Хозяин Ямы", color: "border-amber-500/60 bg-amber-500/5" },
          { id: "tidehunter", name: "Левиафан Бездны (Tidehunter)", icon: "🐙", hp: "300M HP", desc: "[300M HP] Владыка пучин. Чешуя Кракена гасит урон, Раваж сносит арену.", tag: "Сверх-Ранг", color: "border-teal-500/60 bg-teal-500/5" },
          { id: "sf_boss", name: "Архидемон Nevermore", icon: "💀", hp: "1B HP", desc: "[1 МИЛЛИАРД HP] Собирает легион душ. Тройные коилы и Реквием Душ!", tag: "Сверх-Ранг", color: "border-red-600/60 bg-red-600/5" },
          { id: "necrophos", name: "Чумной Владыка (Necrophos)", icon: "🧟", hp: "3.5B HP", desc: "[3.5 МИЛЛИАРДА HP] Аура чумы истощает здоровье, Коса Смерти рубит наповал!", tag: "Сверх-Ранг", color: "border-emerald-600/60 bg-emerald-600/5" },
          { id: "terrorblade", name: "Демон Бездны (Terrorblade)", icon: "😈", hp: "12B HP", desc: "[12 МИЛЛИАРДОВ HP] Метаморфоза в крылатого демона и разрыв души Sunder!", tag: "Сверх-Ранг", color: "border-violet-700/60 bg-violet-700/5" },
          { id: "invoker_boss", name: "Демиург Арсенала (Invoker)", icon: "🧙‍♂️", hp: "42B HP", desc: "[42 МИЛЛИАРДА HP] Повелитель всех стихий. Обрушивает хаос-метеоры!", tag: "Сверх-Ранг", color: "border-yellow-500/60 bg-yellow-500/5" },
          { id: "chaos_knight", name: "Всадник Хаоса (Chaos Knight)", icon: "🐎", hp: "150B HP", desc: "[150 МИЛЛИАРДОВ HP] Призывает фантомы и пробивает непредсказуемыми критами!", tag: "Сверх-Ранг", color: "border-amber-600/60 bg-amber-600/5" },
          { id: "dark_tormentor", name: "Тёмный Терзатель Бездны", icon: "💎", hp: "550B HP", desc: "[550 МИЛЛИАРДОВ HP] Мутировавший Терзатель Тьмы с отражением урона!", tag: "Сверх-Ранг", color: "border-purple-700/60 bg-purple-700/5" },
          { id: "storm_spirit", name: "Громовой Дух (Storm Spirit)", icon: "⚡", hp: "2T HP", desc: "[2 ТРИЛЛИОНА HP] Молниеносные перелеты через всю арену и статические мины!", tag: "Сверх-Ранг", color: "border-sky-500/60 bg-sky-500/5" },
          { id: "doom", name: "Вестник Апокалипсиса (Lord Doom)", icon: "👹", hp: "7.5T HP", desc: "[7.5 ТРИЛЛИОНОВ HP] Владыка преисподней с чистым уроном и роком!", tag: "Сверх-Ранг", color: "border-orange-600/60 bg-orange-600/5" },
          { id: "primal_beast", name: "Первобытный Титан (Primal Beast)", icon: "🦣", hp: "28T HP", desc: "[28 ТРИЛЛИОНОВ HP] Неукротимый сокрушитель материков с яростным топотом!", tag: "Сверх-Ранг", color: "border-red-700/60 bg-red-700/5" },
          { id: "phantom_roshan", name: "Призрачный Рошан Хаоса", icon: "👻", hp: "100T HP", desc: "[100 ТРИЛЛИОНОВ HP] Восставший из Бездны призрак Рошана с астральным Slam!", tag: "Сверх-Ранг", color: "border-cyan-400/60 bg-cyan-400/5" },
          { id: "tinker_boss", name: "Архиинженер (Omega Tinker)", icon: "🤖", hp: "350T HP", desc: "[350 ТРИЛЛИОНОВ HP] Лазер, шквал ракет и марш сотен боевых роботов!", tag: "Сверх-Босс", color: "border-yellow-600/60 bg-yellow-600/5" },
          { id: "enigma", name: "Пожиратель Миров (Enigma Cosmic)", icon: "🌌", hp: "1.2Q HP", desc: "[1.2 КВАДРИЛЛИОНА HP!] Битва на века! Схлопывает арену в Черную Дыру!", tag: "Финальный Босс", color: "border-indigo-600/60 bg-indigo-600/5" }
        ];

    return `
      <div class="space-y-3.5">
        <div class="p-3.5 rounded-2xl bg-gradient-to-r from-purple-950 via-slate-900 to-amber-950 text-white border border-purple-500/30 shadow-md">
          <div class="flex items-center gap-2">
            <span class="text-xl">🐉</span>
            <div>
              <h3 class="text-sm font-black tracking-wide uppercase">Совместные Рейды на Боссов (до 3 игроков)</h3>
              <p class="text-[11px] text-purple-200/80">Идите на босса втроем! Герои стоят по кругу, а босс в центре бьет всех по очереди. Награды сохраняются в профиль.</p>
            </div>
          </div>
        </div>

        <!-- Join Room by Code -->
        <div class="p-3 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 flex items-center gap-2 shadow-sm">
          <input id="coop-room-code-input" type="text" placeholder="Код рейда (напр. 1234)" class="flex-1 px-3 py-2 text-xs rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 font-mono text-slate-800 dark:text-slate-200 uppercase outline-none focus:border-purple-500" />
          <button onclick="window.RPG.joinCoopRoom()" class="px-4 py-2 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 active:scale-95 text-white font-black text-xs shadow-sm flex items-center gap-1">
            <span>Войти</span>
          </button>
        </div>

        <!-- Boss Picker -->
        <div class="space-y-2.5">
          ${bosses
            .map(
              (b) => `
            <div class="p-3.5 rounded-2xl border-2 ${b.color} bg-white dark:bg-slate-800 shadow-sm space-y-2.5 transition-all">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2.5">
                  <span class="text-3xl">${b.icon}</span>
                  <div>
                    <h4 class="text-xs font-black text-slate-800 dark:text-white">${b.name}</h4>
                    <span class="text-[10px] font-bold text-red-500">${b.hp}</span>
                  </div>
                </div>
                <span class="text-[10px] font-extrabold px-2 py-0.5 rounded-md bg-purple-500/20 text-purple-600 dark:text-purple-400">${b.tag}</span>
              </div>

              <p class="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed font-normal">${b.desc}</p>

              <div class="space-y-1.5 pt-1">
                <button onclick="window.RPG.startRaidBossActionBattle('${b.id}')" class="w-full py-2.5 rounded-xl bg-gradient-to-r from-red-600 via-rose-600 to-amber-600 hover:from-red-500 hover:to-amber-500 active:scale-95 text-white font-black text-xs shadow-lg shadow-red-600/30 flex items-center justify-center gap-2 border border-red-400/40">
                  <span>⚔️</span>
                  <span>В бой на Арену (Экшен 60 FPS)</span>
                </button>
                <div class="grid grid-cols-2 gap-1.5">
                  <button onclick="window.RPG.startRaidBossActionBattle('${b.id}')" class="py-2 rounded-xl bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 active:scale-95 text-white font-black text-[11px] shadow-sm flex items-center justify-center gap-1 border border-red-400/40">
                    <span>⚔️</span>
                    <span>2D Дуэль 1v1</span>
                  </button>
                  <button onclick="window.RPG.createCoopRaid('${b.id}', false)" class="py-2 rounded-xl bg-gradient-to-r from-purple-700 to-indigo-700 hover:from-purple-600 active:scale-95 text-white font-bold text-[11px] shadow-sm flex items-center justify-center gap-1">
                    <span>👥</span>
                    <span>Кооп (3 чел)</span>
                  </button>
                </div>
              </div>
            </div>
          `
            )
            .join("")}
        </div>
      </div>
    `;
  }

  function renderCoopHeroCard(hero, role, label, isCurrentTurn, isBossTarget) {
    if (!hero || !hero.name || hero.name === "Свободный слот") {
      return `
        <div class="w-24 sm:w-28 p-2 rounded-2xl border-2 border-dashed border-slate-300 dark:border-slate-700/80 bg-slate-100/50 dark:bg-slate-900/40 text-center space-y-1 shadow-sm">
          <span class="text-lg opacity-40">➕</span>
          <div class="text-[9.5px] font-bold text-slate-400">${label}</div>
          <button onclick="window.RPG.addCoopBot()" class="px-2 py-0.5 rounded-lg bg-purple-600 hover:bg-purple-500 active:scale-95 text-white font-black text-[8px] shadow-xs">
            🤖 Бот
          </button>
        </div>
      `;
    }

    const hpPct = Math.max(0, Math.min(100, Math.round((hero.hp / (hero.hp_max || 1)) * 100)));
    const mpPct = Math.max(0, Math.min(100, Math.round((hero.mp / (hero.mp_max || 1)) * 100)));
    const isDead = hero.is_dead || hero.hp <= 0;

    let borderClass = "border-slate-200 dark:border-slate-700";
    if (isDead) {
      borderClass = "border-rose-900/60 opacity-50 grayscale";
    } else if (isCurrentTurn) {
      borderClass = "border-amber-400 ring-2 ring-amber-400/80 shadow-lg shadow-amber-500/20";
    } else if (isBossTarget) {
      borderClass = "border-red-500 ring-2 ring-red-500/80 shadow-lg shadow-red-500/20 animate-pulse";
    }

    return `
      <div class="w-24 sm:w-28 p-1.5 rounded-2xl bg-white/95 dark:bg-slate-800/95 border-2 ${borderClass} transition-all space-y-1 text-center shadow-md relative">
        ${isCurrentTurn ? `<span class="absolute -top-2 left-1/2 -translate-x-1/2 px-1.5 py-0.2 rounded-md bg-amber-500 text-slate-950 font-black text-[7.5px] shadow-sm animate-pulse whitespace-nowrap">⚡ ХОД</span>` : ""}
        ${isBossTarget && !isDead ? `<span class="absolute -bottom-2 left-1/2 -translate-x-1/2 px-1.5 py-0.2 rounded-md bg-red-600 text-white font-black text-[7.5px] shadow-sm whitespace-nowrap">🎯 ЦЕЛЬ</span>` : ""}
        ${hero.is_defending ? `<span class="absolute -top-1.5 right-1 text-[10px]">🛡️</span>` : ""}

        <div class="flex items-center justify-center">
          <span class="text-xl">${isDead ? "💀" : (hero.class_icon || "🛡️")}</span>
        </div>
        <div class="text-[9.5px] font-black truncate text-slate-900 dark:text-white px-0.5">${hero.name}</div>
        
        <!-- HP -->
        <div class="space-y-0.5">
          <div class="w-full h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
            <div class="h-full ${hpPct > 35 ? 'bg-emerald-500' : 'bg-red-500'} transition-all duration-300" style="width: ${hpPct}%"></div>
          </div>
          <div class="text-[8px] font-bold text-slate-500 dark:text-slate-400 leading-none">${hero.hp}/${hero.hp_max}</div>
        </div>

        <!-- MP -->
        <div class="w-full h-1 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
          <div class="h-full bg-sky-400 transition-all duration-300" style="width: ${mpPct}%"></div>
        </div>
      </div>
    `;
  }

  function renderActiveCoopBattleHTML() {
    const r = RPG_STATE.coopRoomData;
    const boss = r.boss || {};
    const p1 = r.players?.host || {};
    const p2 = r.players?.player_2 || r.players?.opponent || {};
    const p3 = r.players?.player_3 || {};
    const yourRole = r.your_role;
    const isYourTurn = r.is_your_turn;
    const bossTarget = r.boss_target;

    const bossHpPct = Math.max(0, Math.min(100, Math.round((boss.hp / (boss.hp_max || 1)) * 100)));
    const targetName = bossTarget === "host" ? p1.name : bossTarget === "player_2" || bossTarget === "opponent" ? p2.name : bossTarget === "player_3" ? p3.name : "";

    return `
      <div class="space-y-3.5">
        <!-- Header Status -->
        <div class="p-3 rounded-2xl bg-slate-900 text-white flex items-center justify-between border ${r.is_solo ? 'border-rose-500/40' : 'border-purple-500/40'}">
          <div class="flex items-center gap-2">
            <span class="text-xl">${boss.icon || "🐉"}</span>
            <div>
              <h4 class="text-xs font-black">${boss.name || "Босс"} ${r.is_solo ? '<span class="text-[9px] px-1.5 py-0.2 rounded bg-rose-600 text-white font-extrabold ml-1">СОЛО 1v1</span>' : ''}</h4>
              <span class="text-[10px] text-slate-400">
                ${r.status === "waiting" ? (r.is_solo ? "Готов к бою 1v1" : "Ожидание героев (до 3 игроков)") : r.status === "playing" ? (r.is_solo ? "Идет дуэль 1 на 1!" : "Идет круговой бой!") : "Рейд завершен"}
              </span>
            </div>
          </div>
          <div class="flex items-center gap-1.5">
            <button onclick="window.RPG.startRaidBossActionBattle('${boss.id || 'golem'}')" class="px-2.5 py-1 rounded-lg bg-gradient-to-r from-red-600 to-amber-600 hover:from-red-500 text-white text-[10px] font-black shadow-sm flex items-center gap-1">
              <span>⚔️</span>
              <span>На Арену</span>
            </button>
            <button onclick="navigator.clipboard && navigator.clipboard.writeText('${r.room_id}'); alert('Код комнаты скопирован: ${r.room_id}');" class="px-2 py-1 rounded-lg bg-purple-900/60 border border-purple-500/40 text-[10px] font-bold text-purple-200">
              #${r.room_id} 📋
            </button>
            <button onclick="window.RPG.leaveCoopRoom()" class="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-bold text-slate-300">
              ✕
            </button>
          </div>
        </div>

        <!-- Boss Big Bar -->
        <div class="theme-card p-3 rounded-2xl bg-white dark:bg-slate-800 border ${boss.shield_active ? "border-purple-500/80 shadow-md shadow-purple-900/30" : "border-slate-200 dark:border-slate-700"} space-y-1.5 transition-all">
          <div class="flex items-center justify-between text-xs font-black">
            <span class="text-red-600 dark:text-red-400 flex items-center gap-1.5">
              <span>${boss.icon || "🐲"}</span>
              <span>${boss.name}</span>
              ${boss.shield_active ? `<span class="px-2 py-0.5 rounded-full bg-purple-900/80 text-purple-200 border border-purple-400 text-[10px] font-black animate-pulse flex items-center gap-1"><span>🔮</span><span>ЩИТ 50%</span></span>` : ""}
            </span>
            <span class="text-[11px]">${boss.hp} / ${boss.hp_max} HP (${bossHpPct}%)</span>
          </div>
          <div class="w-full h-3 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
            <div class="h-full bg-gradient-to-r from-red-600 to-rose-500 transition-all duration-300" style="width: ${bossHpPct}%"></div>
          </div>
        </div>

        <!-- 2D ACTION ARENA FAST-LAUNCH BANNER -->
        <div class="p-3.5 rounded-2xl bg-gradient-to-r from-red-600 via-rose-600 to-amber-600 text-white shadow-xl shadow-red-950/60 border-2 border-amber-400 flex items-center justify-between gap-3 animate-pulse">
          <div class="flex items-center gap-2.5">
            <span class="text-2xl">⚔️</span>
            <div>
              <span class="text-xs font-black block">НАСТОЯЩИЙ 2D ЭКШЕН-БОЙ НА АРЕНЕ!</span>
              <span class="text-[10px] text-amber-100">Свободное движение героя, увороты, удары и скиллы в 60 FPS</span>
            </div>
          </div>
          <button onclick="window.RPG.startRaidBossActionBattle('${boss.id || 'golem'}')" class="px-4 py-2.5 rounded-xl bg-amber-400 hover:bg-amber-300 active:scale-95 text-slate-950 font-black text-xs shadow-lg whitespace-nowrap">
            В БОЙ 2D ⚡
          </button>
        </div>

        <!-- ARENA DISPLAY: 1v1 SHOWDOWN OR 3-HERO CIRCULAR -->
        ${
          r.is_solo
            ? `
          <div class="theme-card p-4 rounded-3xl bg-gradient-to-b from-slate-900 via-rose-950/30 to-slate-950 border-2 border-rose-500/40 shadow-2xl space-y-3 relative overflow-hidden">
            <div class="text-[10px] font-black uppercase text-center text-rose-400 tracking-wider flex items-center justify-center gap-1.5">
              <span>🗡️</span>
              <span>СОЛО-РЕЙД: ДУЭЛЬ 1 НА 1</span>
            </div>

            <!-- Big Action Arena Button -->
            <button onclick="window.RPG.startRaidBossActionBattle('${boss.id || 'golem'}')" class="w-full py-3 rounded-2xl bg-gradient-to-r from-red-600 via-rose-600 to-amber-600 text-white font-black text-xs shadow-lg active:scale-95 flex items-center justify-center gap-2 border-2 border-amber-400/60">
              <span class="text-base">⚔️</span>
              <span>ВЫЙТИ В 2D БОЙ НА АРЕНУ (РЕАЛЬНОЕ ВРЕМЯ)</span>
            </button>

            <div class="flex items-center justify-around py-3">
              <!-- Solo Hero Card -->
              <div class="flex flex-col items-center">
                <span class="text-[9px] font-extrabold text-slate-400 mb-1">ТВОЙ ГЕРОЙ</span>
                ${renderCoopHeroCard(p1, "host", "Герой", (r.turn === "host"), (bossTarget === "host"))}
              </div>

              <!-- VS Badge -->
              <div class="flex flex-col items-center justify-center px-2">
                <span class="text-3xl font-black text-rose-500 animate-pulse tracking-widest">VS</span>
                <span class="text-[8px] font-extrabold text-rose-300 uppercase px-2 py-0.5 rounded-full bg-rose-900/60 border border-rose-500/40 mt-1">1 на 1</span>
              </div>

              <!-- Boss Card -->
              <div class="flex flex-col items-center">
                <span class="text-[9px] font-extrabold text-red-400 mb-1">РЕЙД БОСС</span>
                <div class="w-24 sm:w-28 p-2 rounded-2xl bg-gradient-to-b from-slate-900 to-red-950/90 border-2 border-red-500/70 shadow-lg text-center space-y-1 relative">
                  <div class="text-2xl animate-bounce">${boss.icon || "🐉"}</div>
                  <div class="text-[9.5px] font-black text-red-300 truncate px-0.5">${boss.name.split(" ")[0]}</div>
                  <div class="space-y-0.5">
                    <div class="w-full h-1.5 rounded-full bg-slate-700 overflow-hidden">
                      <div class="h-full bg-red-500 transition-all duration-300" style="width: ${bossHpPct}%"></div>
                    </div>
                    <div class="text-[8px] font-bold text-amber-300">${boss.hp} / ${boss.hp_max}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        `
            : `
          <!-- CIRCULAR ARENA: 3 HEROES AROUND CENTRAL BOSS -->
          <div class="theme-card p-3.5 rounded-3xl bg-radial from-slate-900 via-purple-950/30 to-slate-950 border-2 border-purple-500/30 shadow-2xl space-y-2 relative overflow-hidden">
            <div class="text-[10px] font-black uppercase text-center text-purple-300 tracking-wider flex items-center justify-center gap-1.5">
              <span>⭕</span>
              <span>Круговая Арена Рейда (Босс в центре)</span>
            </div>

            <!-- Circular Battle Arena Layout -->
            <div class="relative w-full max-w-[320px] mx-auto min-h-[290px] flex flex-col justify-between items-center py-1">
              <!-- Decorative circle track -->
              <div class="absolute inset-4 rounded-full border border-dashed border-purple-500/25 pointer-events-none"></div>

              <!-- Position 1: Player 1 (Top / North) -->
              <div class="z-10">
                ${renderCoopHeroCard(p1, "host", "Игрок 1", (r.turn === "host"), (bossTarget === "host"))}
              </div>

              <!-- Position Center: RAID BOSS -->
              <div id="coop-boss-token" class="z-20 my-1 text-center p-3 rounded-full bg-gradient-to-b from-slate-900 to-red-950/90 border-2 border-red-500/70 shadow-2xl shadow-red-900/60 relative transition-transform duration-200">
                <span class="text-4xl block animate-pulse">${boss.icon || "🐉"}</span>
                <div class="text-[10px] font-black text-red-400 truncate max-w-[80px] mx-auto">${boss.name.split(" ")[0]}</div>
                <div class="text-[9px] font-extrabold text-amber-300">${boss.hp} HP</div>
                ${targetName ? `
                  <div class="text-[7.5px] px-1.5 py-0.2 rounded-full bg-red-600 text-white font-black mt-0.5 whitespace-nowrap shadow-sm">
                    🎯 Очередь: ${targetName}
                  </div>
                ` : ""}
              </div>

              <!-- Position 2 & 3: Player 2 (Left) & Player 3 (Right) -->
              <div class="z-10 w-full flex items-center justify-between px-1">
                <div>
                  ${renderCoopHeroCard(p2, "player_2", "Игрок 2", (r.turn === "player_2" || r.turn === "opponent"), (bossTarget === "player_2" || bossTarget === "opponent"))}
                </div>
                <div>
                  ${renderCoopHeroCard(p3, "player_3", "Игрок 3", (r.turn === "player_3"), (bossTarget === "player_3"))}
                </div>
              </div>
            </div>
          </div>
        `
        }

        <!-- Actions -->
        ${
          r.status === "playing"
            ? (() => {
                const myRole = r.your_role;
                const myHero = myRole === "host" ? p1 : (myRole === "player_2" || myRole === "opponent") ? p2 : p3;
                const skillCd = myHero?.skill_cooldown || 0;
                const canSkill = isYourTurn && skillCd === 0;

                return `
          <div class="theme-card p-3 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 space-y-2">
            <div class="text-xs font-black text-center ${isYourTurn ? "text-amber-500 animate-pulse" : "text-slate-400"}">
              ${isYourTurn ? "🔥 ВАШ ХОД! Выберите действие:" : `⏳ Ход: ${r.turn === "host" ? p1.name : r.turn === "player_2" || r.turn === "opponent" ? p2.name : p3.name}, ждем...`}
            </div>
            <div class="grid grid-cols-4 gap-1.5">
              <button onclick="window.RPG.sendCoopAction('attack')" ${!isYourTurn ? "disabled" : ""} class="py-2.5 rounded-xl bg-gradient-to-r from-red-600 to-rose-600 active:scale-95 text-white font-bold text-xs flex flex-col items-center justify-center gap-0.5 ${!isYourTurn ? "opacity-40 cursor-not-allowed" : "shadow-md shadow-red-600/20"}">
                <span>⚔️</span>
                <span>Атака</span>
              </button>
              <button onclick="window.RPG.sendCoopAction('skill')" ${!canSkill ? "disabled" : ""} class="py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 active:scale-95 text-white font-bold text-xs flex flex-col items-center justify-center gap-0.5 ${!canSkill ? "opacity-40 cursor-not-allowed" : "shadow-md shadow-purple-600/20"}">
                <span>⚡</span>
                <span>${skillCd > 0 ? `КД (${skillCd})` : "Скилл"}</span>
              </button>
              <button onclick="window.RPG.sendCoopAction('defend')" ${!isYourTurn ? "disabled" : ""} class="py-2.5 rounded-xl bg-gradient-to-r from-sky-600 to-blue-600 active:scale-95 text-white font-bold text-xs flex flex-col items-center justify-center gap-0.5 ${!isYourTurn ? "opacity-40 cursor-not-allowed" : "shadow-md shadow-sky-600/20"} ${boss.shield_active ? "ring-2 ring-sky-300 animate-pulse" : ""}">
                <span>🛡️</span>
                <span>Блок</span>
              </button>
              <button onclick="window.RPG.sendCoopAction('potion')" ${!isYourTurn ? "disabled" : ""} class="py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 active:scale-95 text-white font-bold text-xs flex flex-col items-center justify-center gap-0.5 ${!isYourTurn ? "opacity-40 cursor-not-allowed" : "shadow-md shadow-emerald-600/20"}">
                <span>🧪</span>
                <span>Зелье</span>
              </button>
            </div>
            ${boss.shield_active ? `
              <div class="p-2.5 rounded-xl bg-gradient-to-r from-purple-950/90 via-slate-900 to-purple-950/90 border-2 border-purple-500/80 text-center animate-pulse space-y-0.5 shadow-lg shadow-purple-950/40">
                <div class="text-[11px] font-black text-purple-300 flex items-center justify-center gap-1.5">
                  <span>🔮</span>
                  <span>ОТРАЖАЮЩИЙ ЩИТ БОССА АКТИВЕН!</span>
                  <span>🔮</span>
                </div>
                <p class="text-[10px] text-purple-200">Любая атака отразит 50% урона обратно в героя! Используйте Блок 🛡️ или Зелье 🧪!</p>
              </div>
            ` : ""}
          </div>
        `;
              })()
            : r.status === "finished" && r.winner === "heroes"
            ? `
          <div class="theme-card p-4 rounded-3xl bg-gradient-to-b from-amber-950/40 via-slate-900 to-slate-950 border-2 border-amber-500/80 shadow-2xl space-y-3.5 text-center animate-scale-up">
            <div class="text-4xl animate-bounce">🏆</div>
            <div>
              <h3 class="text-base font-black text-amber-400">ВЕЛИКАЯ ПОБЕДА НАД РЕЙД-БОССОМ!</h3>
              <p class="text-xs text-slate-300 font-medium">${boss.name || "Босс"} пал под натиском героев!</p>
            </div>

            ${r.victory_rewards?.item ? `
              <div class="p-3 rounded-2xl bg-slate-800/90 border border-amber-500/50 space-y-1.5 text-center">
                <span class="text-3xl block">${r.victory_rewards.item.icon || "🎁"}</span>
                <h4 class="text-xs font-black text-amber-300">${r.victory_rewards.item.name}</h4>
                <div class="text-[10px] font-extrabold text-amber-400">${r.victory_rewards.item.bonus_desc || ""}</div>
                <div class="text-[9px] text-emerald-400 font-bold">✨ Легендарный дроп добавлен в инвентарь!</div>
              </div>
            ` : ""}

            <div class="flex items-center justify-around p-2 rounded-xl bg-slate-800/60 text-xs font-black text-amber-300">
              <span>+${r.victory_rewards?.gold_earned || boss.gold_reward || 1200} 🪙</span>
              <span>+${r.victory_rewards?.xp_earned || boss.xp_reward || 850} ✨</span>
              <span>+${r.victory_rewards?.gems_earned || 35} 💎</span>
            </div>

            <div class="flex items-center gap-2">
              <button onclick="window.RPG.fetchProfile(); RPG_STATE.activeTab = 'inventory'; renderRoot();" class="flex-1 py-3 rounded-2xl bg-gradient-to-r from-amber-500 to-yellow-400 text-slate-950 font-black text-xs shadow-lg shadow-amber-500/20 active:scale-95">
                ОТКРЫТЬ РЮКЗАК 🎒
              </button>
              <button onclick="window.RPG.leaveCoopRoom()" class="flex-1 py-3 rounded-2xl bg-slate-800 hover:bg-slate-700 text-white font-black text-xs active:scale-95">
                В ЛОББИ РЕЙДА ⚔️
              </button>
            </div>
          </div>
        ` : r.status === "finished" && r.winner === "boss" ? `
          <div class="theme-card p-4 rounded-3xl bg-slate-900 border-2 border-rose-600/70 shadow-2xl space-y-3 text-center animate-scale-up">
            <div class="text-4xl">💀</div>
            <h3 class="text-base font-black text-rose-500">РЕЙД ПРОВАЛЕН</h3>
            <p class="text-xs text-slate-300">Все герои пали в неравном бою. Улучшите экипировку и попробуйте снова!</p>
            <button onclick="window.RPG.leaveCoopRoom()" class="w-full py-3 rounded-2xl bg-rose-600 hover:bg-rose-500 text-white font-black text-xs shadow-lg active:scale-95">
              ВЕРНУТЬСЯ В ЛОББИ ⚔️
            </button>
          </div>
        ` : ""
        }

        <!-- Co-op Combat Feed / Log -->
        <div class="theme-card p-3 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 space-y-1.5">
          <div class="flex items-center justify-between text-xs font-black uppercase text-slate-500 dark:text-slate-400">
            <span>📜 Лог рейда (Босс бьет по кругу)</span>
            <span class="text-amber-500 text-[10px]">Круг целей</span>
          </div>

          <div class="p-2.5 rounded-xl bg-slate-100 dark:bg-slate-900/60 max-h-32 overflow-y-auto space-y-1 font-mono text-[10.5px]">
            ${
              !r.combat_log || r.combat_log.length === 0
                ? `<div class="text-slate-400 text-center py-2">Рейд начался! Атакуйте босса по очереди.</div>`
                : r.combat_log.map((entry) => {
                    const txt = typeof entry === "string" ? entry : (entry.text || "");
                    const isBoss = typeof entry === "object" && entry.type === "boss_attack";
                    const isVictory = typeof entry === "object" && entry.type === "victory";
                    const isDefeat = typeof entry === "object" && entry.type === "defeat";
                    const colorClass = isVictory ? "text-emerald-500 font-bold" : isDefeat ? "text-rose-500 font-bold" : isBoss ? "text-red-400" : "text-slate-700 dark:text-slate-300";
                    return `<div class="leading-tight ${colorClass}">${txt}</div>`;
                  }).join("")
            }
          </div>
        </div>
      </div>
    `;
  }

  // ===========================================================================
  // 4. PVP DUELS & LEADERBOARD HTML
  // ===========================================================================

  function renderPvPDuelsHTML() {
    if (RPG_STATE.pvpRoomId && RPG_STATE.pvpRoomData) {
      return renderActivePvPDuelHTML();
    }

    const p = RPG_STATE.profile || {};
    const classmates = RPG_STATE.classmates || [];

    return `
      <div class="space-y-3.5">
        <div class="p-3.5 rounded-2xl bg-gradient-to-r from-red-950 via-slate-900 to-amber-950 text-white border border-red-500/30 shadow-md">
          <div class="flex items-center justify-between">
            <div>
              <h3 class="text-sm font-black tracking-wide uppercase">1v1 Дуэли Одноклассников</h3>
              <p class="text-[11px] text-red-200/80">Сразитесь экипировкой с одноклассником! Рейтинг: <b>${p.pvp_rating || 1000}</b></p>
            </div>
            <span class="text-2xl">🥊</span>
          </div>
        </div>

        <div class="space-y-2">
          <h4 class="text-xs font-black uppercase text-slate-500">Одноклассники в сети:</h4>
          ${
            classmates.length === 0
              ? `<div class="p-4 text-center text-xs text-slate-400 theme-card rounded-2xl">Одноклассники не найдены. Поделитесь ботом!</div>`
              : classmates
                  .map(
                    (c) => `
              <div class="p-3 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 flex items-center justify-between shadow-sm">
                <div class="flex items-center gap-2.5">
                  <div class="w-8 h-8 rounded-xl bg-amber-500/10 text-amber-600 font-black text-xs flex items-center justify-center">
                    ${c.name ? c.name[0] : "👤"}
                  </div>
                  <div>
                    <span class="text-xs font-bold text-slate-800 dark:text-white block">${c.name}</span>
                    <span class="text-[10px] text-slate-400">Рейтинг: 1000</span>
                  </div>
                </div>
                <button onclick="window.RPG.challengeClassmate(${c.tg_id}, '${c.name}')" class="px-3 py-1.5 rounded-xl bg-red-600 hover:bg-red-500 active:scale-95 text-white font-bold text-xs shadow-sm">
                  Вызвать ⚔️
                </button>
              </div>
            `
                  )
                  .join("")}
        </div>
      </div>
    `;
  }

  function renderActivePvPDuelHTML() {
    const r = RPG_STATE.pvpRoomData;
    const host = r.players?.host || {};
    const opp = r.players?.opponent || {};
    const isYourTurn = r.is_your_turn;

    return `
      <div class="space-y-3.5">
        <div class="p-3 rounded-2xl bg-slate-900 text-white flex items-center justify-between border border-red-500/40">
          <h4 class="text-xs font-black">1v1 Дуэль</h4>
          <button onclick="window.RPG.leavePvPRoom()" class="px-2.5 py-1 rounded-lg bg-slate-800 text-xs font-bold text-slate-300">
            Сдаться
          </button>
        </div>

        <div class="grid grid-cols-2 gap-2">
          <!-- Player 1 -->
          <div class="p-3 rounded-2xl bg-white dark:bg-slate-800 border ${r.turn === "host" ? "border-amber-500 shadow-md" : "border-slate-200 dark:border-slate-700"} text-center space-y-1">
            <span class="text-3xl">${host.class_icon || "🗡️"}</span>
            <div class="text-xs font-black truncate">${host.name}</div>
            <div class="text-xs font-extrabold text-emerald-500">${host.hp} HP</div>
          </div>

          <!-- Player 2 -->
          <div class="p-3 rounded-2xl bg-white dark:bg-slate-800 border ${r.turn === "opponent" ? "border-amber-500 shadow-md" : "border-slate-200 dark:border-slate-700"} text-center space-y-1">
            <span class="text-3xl">${opp.class_icon || "🛡️"}</span>
            <div class="text-xs font-black truncate">${opp.name}</div>
            <div class="text-xs font-extrabold text-emerald-500">${opp.hp} HP</div>
          </div>
        </div>

        ${
          r.status === "playing"
            ? `
          <div class="theme-card p-3 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 space-y-2">
            <div class="text-xs font-black text-center ${isYourTurn ? "text-amber-500 animate-pulse" : "text-slate-400"}">
              ${isYourTurn ? "ВАШ ХОД!" : "Ход соперника..."}
            </div>
            <div class="grid grid-cols-3 gap-2">
              <button onclick="window.RPG.sendPvPAction('attack')" ${!isYourTurn ? "disabled" : ""} class="py-2.5 rounded-xl bg-red-600 active:scale-95 text-white font-bold text-xs flex flex-col items-center justify-center gap-0.5 ${!isYourTurn ? "opacity-40" : ""}">
                <span>⚔️</span>
                <span>Удар</span>
              </button>
              <button onclick="window.RPG.sendPvPAction('skill')" ${!isYourTurn ? "disabled" : ""} class="py-2.5 rounded-xl bg-purple-600 active:scale-95 text-white font-bold text-xs flex flex-col items-center justify-center gap-0.5 ${!isYourTurn ? "opacity-40" : ""}">
                <span>⚡</span>
                <span>Скилл</span>
              </button>
              <button onclick="window.RPG.sendPvPAction('defend')" ${!isYourTurn ? "disabled" : ""} class="py-2.5 rounded-xl bg-sky-600 active:scale-95 text-white font-bold text-xs flex flex-col items-center justify-center gap-0.5 ${!isYourTurn ? "opacity-40" : ""}">
                <span>🛡️</span>
                <span>Щит</span>
              </button>
            </div>
          </div>
        `
            : ""
        }
      </div>
    `;
  }

  function renderLeaderboardHTML() {
    const list = RPG_STATE.leaderboard || [];

    return `
      <div class="space-y-3.5">
        <div class="p-3.5 rounded-2xl bg-gradient-to-r from-amber-600 to-yellow-500 text-slate-950 shadow-md flex items-center justify-between">
          <div>
            <h3 class="text-sm font-black tracking-wide uppercase">Рейтинг natarGRP 11 «Б»</h3>
            <p class="text-[11px] font-bold opacity-90">Сильнейшие воины класса</p>
          </div>
          <span class="text-2xl">🏆</span>
        </div>

        <div class="space-y-1.5">
          ${
            list.length === 0
              ? `<div class="p-6 text-center text-xs text-slate-400 theme-card rounded-2xl">Рейтинг пока пуст. Будьте первым!</div>`
              : list
                  .map(
                    (p, idx) => `
              <div class="p-2.5 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 flex items-center justify-between shadow-sm">
                <div class="flex items-center gap-2.5">
                  <span class="w-6 text-center font-black text-xs ${idx === 0 ? "text-amber-500 text-sm" : idx === 1 ? "text-slate-400" : idx === 2 ? "text-amber-700" : "text-slate-400"}">
                    ${idx === 0 ? "🥇" : idx === 1 ? "🥈" : idx === 2 ? "🥉" : `#${idx + 1}`}
                  </span>
                  <div class="text-xl">${p.class_avatar || p.class_icon || "🛡️"}</div>
                  <div>
                    <span class="text-xs font-bold text-slate-800 dark:text-white block truncate">${p.name || "Воин"}</span>
                    <span class="text-[10px] text-slate-400">${p.class_name || ""} • Ур. ${p.level}</span>
                  </div>
                </div>
                <div class="text-right">
                  <span class="text-xs font-black text-amber-500 block">${p.pvp_rating || 1000} 🏆</span>
                  <span class="text-[9.5px] text-slate-400">${p.dungeon_floor || 1} этаж</span>
                </div>
              </div>
            `
                  )
                  .join("")}
        </div>
      </div>
    `;
  }

  // ===========================================================================
  // MODALS: ITEM INSPECT, FORGE & REWARD CHEST
  // ===========================================================================

  function renderItemModalHTML(item) {
    const rInfo = RARITY_MAP[item.rarity] || RARITY_MAP.common;
    const forgeTag = item.forge_level > 0 ? `+${item.forge_level}` : "";
    const slotName = item.slot_name || (item.slot === "weapon" ? "Оружие" : item.slot === "armor" ? "Броня" : item.slot === "relic" ? "Реликвия" : "Зелье");

    const p = RPG_STATE.profile || {};
    const eq = p.equipment || {};
    const isEquipped = Object.values(eq).some(it => it && it.uid === item.uid);

    let deltaHTML = "";
    if (!isEquipped && ["weapon", "armor", "relic"].includes(item.slot)) {
      const curr = eq[item.slot];
      if (!curr) {
        deltaHTML = `
          <div class="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-[10.5px] font-bold text-emerald-600 dark:text-emerald-400 text-center">
            ✨ Слот пуст: надев предмет, вы получите полный бонус!
          </div>
        `;
      } else {
        const deltas = [];
        if (item.slot === "weapon") {
          const itemMin = item.min_atk || item.base_min || 0;
          const itemMax = item.max_atk || item.base_max || 0;
          const currMin = curr.min_atk || curr.base_min || 0;
          const currMax = curr.max_atk || curr.base_max || 0;
          const dMin = itemMin - currMin;
          const dMax = itemMax - currMax;
          if (dMin !== 0 || dMax !== 0) {
            const sign = dMax >= 0 ? "+" : "";
            const col = dMax >= 0 ? "text-emerald-500" : "text-rose-500";
            deltas.push(`<span class="${col} font-bold">${dMax >= 0 ? "▲" : "▼"} ${sign}${dMin}..${sign}${dMax} Урон</span>`);
          }
        } else if (item.slot === "armor") {
          const itemDef = item.defense || item.base_def || 0;
          const itemHp = item.hp_bonus || item.base_hp || 0;
          const currDef = curr.defense || curr.base_def || 0;
          const currHp = curr.hp_bonus || curr.base_hp || 0;
          const dDef = itemDef - currDef;
          const dHp = itemHp - currHp;
          if (dDef !== 0) {
            const sign = dDef >= 0 ? "+" : "";
            const col = dDef >= 0 ? "text-emerald-500" : "text-rose-500";
            deltas.push(`<span class="${col} font-bold">${dDef >= 0 ? "▲" : "▼"} ${sign}${dDef} Броня</span>`);
          }
          if (dHp !== 0) {
            const sign = dHp >= 0 ? "+" : "";
            const col = dHp >= 0 ? "text-emerald-500" : "text-rose-500";
            deltas.push(`<span class="${col} font-bold">${dHp >= 0 ? "▲" : "▼"} ${sign}${dHp} HP</span>`);
          }
        }
        if (deltas.length > 0) {
          deltaHTML = `
            <div class="p-2 rounded-xl bg-slate-100 dark:bg-slate-800 text-[10.5px] text-center border border-slate-200 dark:border-slate-700">
              <span class="text-slate-400 block text-[9.5px]">Сравнение с надетым [${curr.name}]:</span>
              <div class="flex items-center justify-center gap-2 mt-0.5">${deltas.join(" | ")}</div>
            </div>
          `;
        }
      }
    }

    const isConsumable = item.slot === "consumable" || item.type === "potion";

    return `
      <div class="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4">
        <div class="w-full max-w-sm rounded-3xl bg-white dark:bg-slate-900 border-2 ${rInfo.color} p-5 space-y-4 shadow-2xl animate-scale-up">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-1.5">
              <span class="text-[10px] font-extrabold px-2 py-0.5 rounded-lg ${rInfo.badge}">${rInfo.name}</span>
              <span class="text-[10px] font-black px-2 py-0.5 rounded-lg bg-black/20 text-slate-600 dark:text-slate-300">[${slotName}]</span>
              ${isEquipped ? `<span class="text-[9.5px] font-black px-1.5 py-0.5 rounded-md bg-emerald-500 text-white">НАДЕТО</span>` : ""}
            </div>
            <button onclick="window.RPG.closeItemModal()" class="w-7 h-7 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-400 hover:text-white flex items-center justify-center text-xs">
              ✕
            </button>
          </div>

          <div class="text-center space-y-2">
            <div class="relative inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-b from-slate-800 to-slate-900 border-2 border-amber-500/40 shadow-lg shadow-amber-500/10">
              <span class="text-4xl leading-none">${item.icon || "📦"}</span>
              ${forgeTag ? `<span class="absolute -top-1 -right-2 px-1.5 rounded-md bg-amber-500 text-slate-950 font-black text-xs shadow-sm">${forgeTag}</span>` : ""}
            </div>
            <h3 class="text-sm font-black text-slate-900 dark:text-white">${item.name}</h3>
            <p class="text-xs font-bold text-amber-500">${item.bonus_desc || ""}</p>
            ${(() => {
              const matchedDef = Object.values(ACTIVE_ITEM_DEFINITIONS).find(d => d.match(item));
              if (!matchedDef) return "";
              return `
                <div class="p-2 rounded-xl bg-gradient-to-r from-emerald-500/20 via-teal-500/20 to-emerald-500/20 border border-emerald-500/40 text-[10.5px] font-bold text-emerald-400 text-center space-y-0.5">
                  <div class="flex items-center justify-center gap-1 text-emerald-300 font-black uppercase text-[10px]">
                    <span>⚡</span> <span>АКТИВНЫЙ ПРЕДМЕТ</span>
                  </div>
                  <span>${matchedDef.description}</span>
                  <div class="text-[9px] text-amber-300 font-extrabold mt-1">
                    ${isEquipped ? '✅ Экипирован: кнопка активна на боевом экране [Клавиша: R / 1 или тап]' : '💡 Наденьте в слот, чтобы применять способность кнопкой в бою!'}
                  </div>
                </div>
              `;
            })()}
          </div>

          ${deltaHTML}

          <div class="space-y-2 pt-2 border-t border-slate-100 dark:border-slate-800">
            ${
              isEquipped
                ? `
              <button onclick="window.RPG.openSlotFilterModal('${Object.keys(eq).find(k => eq[k]?.uid === item.uid) || item.slot || 'slot_1'}')" class="w-full py-2.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 active:scale-95 text-white font-black text-xs shadow-md flex items-center justify-center gap-1.5">
                <span>🔄</span>
                <span>Сменить на другой предмет (${slotName})</span>
              </button>
              <button onclick="window.RPG.unequipItem('${item.uid}')" class="w-full py-2.5 rounded-xl bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 active:scale-95 text-white font-black text-xs shadow-md flex items-center justify-center gap-1.5">
                <span>🎒</span>
                <span>Снять в рюкзак</span>
              </button>
            `
                : !isConsumable
                  ? `
              <button onclick="window.RPG.equipItem('${item.uid}')" class="w-full py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 active:scale-95 text-white font-black text-xs shadow-md flex items-center justify-center gap-1.5">
                <span>⚔️</span>
                <span>${eq[item.slot || item.type] ? `Сменить [${eq[item.slot || item.type].name}] ➔ [${item.name}]` : "Надеть в слот снаряжения"}</span>
              </button>
            `
                  : `
              <button onclick="window.RPG.useConsumable('${item.uid}')" class="w-full py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 active:scale-95 text-white font-black text-xs shadow-md flex items-center justify-center gap-1.5">
                <span>🧪</span>
                <span>Использовать ${item.count ? `(${item.count} шт.)` : ""}</span>
              </button>
            `
            }

            ${
              !isConsumable
                ? `
              <button onclick="window.RPG.openForge('${item.uid}')" class="w-full py-2.5 rounded-xl bg-gradient-to-r from-amber-600 to-yellow-500 hover:from-amber-500 hover:to-yellow-400 active:scale-95 text-slate-950 font-black text-xs shadow-md">
                Заточить в Кузнице (+1..+99) ⚒️
              </button>
            `
                : ""
            }

            ${
              isEquipped
                ? `
              <button onclick="window.RPG.sellItem('${item.uid}')" class="w-full py-2.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-500 active:scale-95 font-bold text-xs flex items-center justify-center gap-1.5 transition-all">
                <span>💰</span>
                <span>Снять и продать (+${getItemSellPrice(item)} 🪙)</span>
              </button>
            `
                : `
              <button onclick="window.RPG.toggleItemSelection('${item.uid}'); window.RPG.closeItemModal();" class="w-full py-2.5 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-500 font-black text-xs flex items-center justify-center gap-1.5">
                <span>☑️</span>
                <span>Выбрать для продажи (+${getItemSellPrice(item)} 🪙)</span>
              </button>
              <button onclick="window.RPG.sellItem('${item.uid}')" class="w-full py-2 rounded-xl bg-slate-100 dark:bg-slate-800 text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/30 font-bold text-xs">
                Продать этот предмет (+${getItemSellPrice(item)} 🪙)
              </button>
            `
            }
          </div>
        </div>
      </div>
    `;
  }

  function renderForgeModalHTML(item) {
    const p = RPG_STATE.profile || {};
    const userGold = p.gold || 0;
    const userGems = p.gems || 0;
    const currentUpg = item.upgrade || item.forge_level || 0;
    const targetUpg = currentUpg + 1;
    const isMax = currentUpg >= 100;

    let rate = 1.0;
    let goldCost = targetUpg * 350;
    let gemsCost = 0;

    if (targetUpg <= 3) {
      rate = 1.0;
      goldCost = targetUpg * 350;
      gemsCost = 0;
    } else if (targetUpg <= 6) {
      rate = 0.98;
      goldCost = targetUpg * 800;
      gemsCost = 2;
    } else if (targetUpg <= 9) {
      rate = 0.90;
      goldCost = targetUpg * 2000;
      gemsCost = 6;
    } else if (targetUpg <= 12) {
      rate = 0.75;
      goldCost = targetUpg * 5500;
      gemsCost = 15;
    } else if (targetUpg <= 15) {
      rate = 0.60;
      goldCost = targetUpg * 15000;
      gemsCost = 45;
    } else {
      rate = 0.50;
      goldCost = targetUpg * 25000;
      gemsCost = 45 + (targetUpg - 15) * 2;
    }

    const successPct = isMax ? 0 : Math.round(rate * 100);
    const canAffordGold = userGold >= goldCost;
    const canAffordGems = userGems >= gemsCost;
    const canAfford = canAffordGold && canAffordGems && !isMax;

    let chanceColor = "text-emerald-400";
    if (successPct <= 25) chanceColor = "text-rose-400";
    else if (successPct <= 45) chanceColor = "text-orange-400";
    else if (successPct <= 65) chanceColor = "text-yellow-400";

    // Collect all forgeable equipment & inventory items
    const eq = p.equipment || {};
    const inv = p.inventory || [];
    const allForgeable = [
      ...(eq.slot_1 ? [{ ...eq.slot_1, locLabel: "Слот 1" }] : []),
      ...(eq.slot_2 ? [{ ...eq.slot_2, locLabel: "Слот 2" }] : []),
      ...(eq.slot_3 ? [{ ...eq.slot_3, locLabel: "Слот 3" }] : []),
      ...(eq.slot_4 ? [{ ...eq.slot_4, locLabel: "Слот 4" }] : []),
      ...(eq.slot_5 ? [{ ...eq.slot_5, locLabel: "Слот 5" }] : []),
      ...(eq.slot_6 ? [{ ...eq.slot_6, locLabel: "Слот 6" }] : []),
      ...inv.filter((i) => {
        const itype = (i.type || "").toLowerCase();
        const islot = (i.slot || "").toLowerCase();
        return itype !== "consumable" && islot !== "consumable" && itype !== "potion";
      }).map((i) => ({ ...i, locLabel: "Рюкзак" }))
    ];

    // Compute preview stat deltas (+15% per level)
    let previewStats = "";
    const itemT = (item.type || item.slot || "").toLowerCase();
    if (itemT === "weapon") {
      const curMin = item.min_atk || item.base_min || 16;
      const curMax = item.max_atk || item.base_max || 24;
      const nextMin = Math.floor(curMin * 1.15) + 2;
      const nextMax = Math.floor(curMax * 1.15) + 4;
      previewStats = `
        <div class="p-2 rounded-xl bg-slate-800/80 border border-amber-500/30 text-[11px] font-bold text-amber-300">
          ⚔️ Урон: ${curMin}..${curMax} ➔ <span class="text-emerald-400 font-extrabold">${nextMin}..${nextMax}</span> (+15%)
        </div>
      `;
    } else if (itemT === "armor") {
      const curDef = item.defense || item.base_def || 10;
      const curHp = item.hp_bonus || item.base_hp || 40;
      const nextDef = Math.floor(curDef * 1.15) + 2;
      const nextHp = Math.floor(curHp * 1.15) + 20;
      previewStats = `
        <div class="p-2 rounded-xl bg-slate-800/80 border border-amber-500/30 text-[11px] font-bold text-amber-300">
          🛡️ Броня: ${curDef} ➔ <span class="text-emerald-400 font-extrabold">${nextDef}</span> | ❤️ HP: +${curHp} ➔ <span class="text-emerald-400 font-extrabold">+${nextHp}</span>
        </div>
      `;
    } else {
      previewStats = `
        <div class="p-2 rounded-xl bg-slate-800/80 border border-amber-500/30 text-[11px] font-bold text-amber-300">
          ✨ Все параметры реликвии увеличатся на <span class="text-emerald-400 font-extrabold">+15%</span>!
        </div>
      `;
    }

    return `
      <div class="fixed inset-0 z-50 bg-black/80 backdrop-blur-xs flex items-center justify-center p-4">
        <div class="w-full max-w-sm rounded-3xl bg-slate-900 border-2 border-amber-500/60 p-5 space-y-3.5 shadow-2xl text-white animate-scale-up">
          <div class="flex items-center justify-between">
            <h3 class="text-xs font-black uppercase text-amber-400 flex items-center gap-1.5">
              <span>⚒️</span> Кузница Заточки (+0..+100)
            </h3>
            <button onclick="window.RPG.closeForgeModal()" class="w-7 h-7 rounded-full bg-slate-800 text-slate-400 hover:text-white flex items-center justify-center text-xs">
              ✕
            </button>
          </div>

          ${
            RPG_STATE.forgeSuccessAnimation
              ? `<div class="p-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 text-white font-black text-xs text-center shadow-lg animate-bounce flex items-center justify-center gap-1.5">
                  <span>🔥</span> ЗАТОЧКА УСПЕШНА! Уровень +${currentUpg}! <span>✨</span>
                </div>`
              : (RPG_STATE.forgeFailMessage
                  ? `<div class="p-2.5 rounded-xl bg-gradient-to-r from-rose-700 to-red-600 text-white font-black text-xs text-center shadow-lg flex items-center justify-center gap-1.5">
                      <span>💥</span> ${RPG_STATE.forgeFailMessage}
                    </div>`
                  : "")
          }

          <div class="text-center space-y-2 py-1">
            <div class="text-4xl ${RPG_STATE.forgeSuccessAnimation ? "animate-bounce" : ""}">${item.icon || "⚔️"}</div>
            <h4 class="text-sm font-black">${item.name} <span class="text-amber-400 font-extrabold">+${currentUpg}</span></h4>
            ${
              item.bonus_desc
                ? `
              <div class="p-2 rounded-xl bg-slate-800/60 border border-slate-700 text-xs font-bold text-slate-300">
                ${item.bonus_desc}
              </div>
            `
                : ""
            }
            ${previewStats}
            <div class="space-y-0.5 pt-1">
              <span class="text-xs ${chanceColor} block font-black">
                ${isMax ? "МАКСИМАЛЬНЫЙ УРОВЕНЬ (+100)" : `Шанс успеха: ${successPct}%`}
              </span>
              <span class="text-[9.5px] text-emerald-400 block font-medium">
                🛡️ Безопасность: при неудаче предмет НЕ сломается и не сбросит уровень!
              </span>
            </div>
          </div>

          <!-- Quick Item Selector Chips -->
          ${
            allForgeable.length > 1
              ? `
            <div class="space-y-1">
              <span class="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Другие предметы:</span>
              <div class="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
                ${allForgeable
                  .map(
                    (it) => `
                  <button onclick="window.RPG.openForge('${it.uid}')" class="px-2 py-1 rounded-lg text-[10.5px] font-bold whitespace-nowrap flex items-center gap-1 border transition-all ${
                      it.uid === item.uid
                        ? "bg-amber-500/20 border-amber-400 text-amber-300"
                        : "bg-slate-800 border-slate-700 text-slate-400 hover:text-white"
                    }">
                    <span>${it.icon || "🗡️"}</span>
                    <span>${it.name.split(" ")[0]}</span>
                    <span class="text-amber-400 text-[9px] font-black">${(it.upgrade || it.forge_level) ? `+${it.upgrade || it.forge_level}` : ""}</span>
                  </button>
                `
                  )
                  .join("")}
              </div>
            </div>
          `
              : ""
          }

          <div class="p-2.5 rounded-xl bg-slate-800/50 border border-slate-700 flex items-center justify-between text-xs font-bold">
            <span class="text-slate-400">Стоимость заточки:</span>
            <div class="flex items-center gap-2">
              <span class="${canAffordGold ? "text-amber-400 font-black" : "text-red-400 font-black"}">🪙 ${goldCost.toLocaleString()}</span>
              ${gemsCost > 0 ? `<span class="${canAffordGems ? "text-cyan-400 font-black" : "text-red-400 font-black"}">💎 ${gemsCost}</span>` : ""}
            </div>
          </div>

          <div class="space-y-2">
            <button onclick="window.RPG.forgeCurrentItem()" ${!canAfford ? "disabled" : ""} class="w-full py-3 rounded-xl bg-gradient-to-r from-amber-500 to-yellow-400 hover:from-amber-400 active:scale-95 text-slate-950 font-black text-xs shadow-md ${
              !canAfford ? "opacity-40 cursor-not-allowed" : ""
            }">
              ${isMax ? "Максимальный уровень заточки (+100)" : (canAfford ? `Заточить до +${targetUpg} (${successPct}% шанс) 🔥` : (!canAffordGold ? `Не хватает золота (нужно 🪙 ${goldCost})` : `Не хватает кристаллов (нужно 💎 ${gemsCost})`))}
            </button>
          </div>
        </div>
      </div>
    `;
  }


  function renderChestModalHTML(chest) {
    const item = chest.item || {};
    const rInfo = RARITY_MAP[item.rarity] || RARITY_MAP.common;
    const isOpened = chest.opened;

    return `
      <div class="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
        <div class="w-full max-w-sm rounded-3xl bg-slate-900 border-2 border-amber-500 p-6 space-y-4 shadow-2xl text-white text-center animate-scale-up">
          <div class="text-5xl ${!isOpened ? "animate-bounce" : "scale-110 transition-transform"}">
            ${!isOpened ? (chest.chest_icon || "🎁") : "✨"}
          </div>

          <h3 class="text-base font-black text-amber-400">${chest.chest_name || "Наградной Сундук"}</h3>

          ${
            !isOpened
              ? `
            <p class="text-xs text-slate-300 font-medium">Поздравляем с зачисткой этажа! Внутри гарантированный функциональный артефакт и сокровища.</p>
            <button onclick="window.RPG.claimChestReward()" class="w-full py-3.5 rounded-2xl bg-gradient-to-r from-amber-500 via-yellow-400 to-amber-500 active:scale-95 text-slate-950 font-black text-sm shadow-xl shadow-amber-500/30">
              ОТКРЫТЬ СУНДУК 🎁
            </button>
          `
              : `
            <div class="p-4 rounded-2xl border-2 ${rInfo.color} space-y-2 bg-slate-800/80">
              <span class="text-4xl block">${item.icon || "⚔️"}</span>
              <h4 class="text-sm font-black">${item.name}</h4>
              <div class="flex items-center justify-center gap-1.5">
                <span class="text-[10px] font-extrabold px-2 py-0.5 rounded-md ${rInfo.badge}">${rInfo.name}</span>
                <span class="text-[10px] font-black px-2 py-0.5 rounded-md bg-black/30">[${item.slot_name || "Снаряжение"}]</span>
              </div>
              <p class="text-xs text-amber-400 font-bold">${item.bonus_desc || ""}</p>
            </div>

            <div class="flex items-center justify-center gap-4 text-xs font-extrabold text-amber-300">
              <span>+${chest.gold_reward || 200} 🪙</span>
              <span>+${chest.gems_reward || 10} 💎</span>
            </div>

            <button onclick="window.RPG.closeChestModal()" class="w-full py-3 rounded-2xl bg-emerald-600 hover:bg-emerald-500 active:scale-95 text-white font-black text-xs shadow-md">
              Забрать награду в инвентарь 🎒
            </button>
          `
          }
        </div>
      </div>
    `;
  }

  function renderShopModalHTML() {
    const p = RPG_STATE.profile || {};
    const catalog = RPG_STATE.shopCatalog || [];
    const filter = RPG_STATE.shopFilter || "all";
    const userGold = p.gold || 0;
    const userGems = p.gems || 0;

    const filterTabs = [
      { id: "all", label: "Все товары" },
      { id: "mage", label: "Магия 🔮" },
      { id: "agi", label: "Ловкость 🏹" },
      { id: "str", label: "Сила 💪" },
      { id: "weapon", label: "Оружие ⚔️" },
      { id: "armor", label: "Броня 🛡️" },
      { id: "relic", label: "Реликвии 💍" },
      { id: "potion", label: "Зелья 🧪" }
    ];

    const filteredItems = catalog.filter((it) => {
      if (filter === "all") return true;
      if (filter === "mage") {
        const desc = ((it.bonus_desc || "") + " " + (it.name || "")).toLowerCase();
        return (it.int && it.int > 0) || (it.spell_amp && it.spell_amp > 0) || (it.ult_boost && it.ult_boost > 0) || (it.ult_cd && it.ult_cd > 0) || (it.cooldown_reduct && it.cooldown_reduct > 0) || desc.includes("интеллект") || desc.includes("маг") || desc.includes("заклинаний") || desc.includes("мана") || desc.includes("ульт");
      }
      if (filter === "agi") {
        const desc = ((it.bonus_desc || "") + " " + (it.name || "")).toLowerCase();
        return (it.agi && it.agi > 0) || (it.atk_speed && it.atk_speed > 0) || (it.dodge && it.dodge > 0) || desc.includes("ловкост") || desc.includes("скор. атаки") || desc.includes("уворот");
      }
      if (filter === "str") {
        const desc = ((it.bonus_desc || "") + " " + (it.name || "")).toLowerCase();
        return (it.str && it.str > 0) || (it.hp && it.hp > 0) || (it.hp_regen && it.hp_regen > 0) || desc.includes("сила") || desc.includes("жизни") || desc.includes("регенерац");
      }
      if (filter === "weapon") return it.slot === "weapon" || it.type === "weapon";
      if (filter === "armor") return it.slot === "armor" || it.type === "armor";
      if (filter === "relic") return it.slot === "relic" || it.type === "relic";
      if (filter === "potion") return it.slot === "consumable" || it.type === "potion";
      return true;
    });

    return `
      <div class="fixed inset-0 z-50 bg-black/75 backdrop-blur-xs flex items-center justify-center p-3 sm:p-4">
        <div class="w-full max-w-lg max-h-[88vh] flex flex-col rounded-3xl bg-slate-900 border-2 border-emerald-500/60 p-4 sm:p-5 space-y-3 shadow-2xl text-white animate-scale-up">
          <!-- Header -->
          <div class="flex items-center justify-between border-b border-slate-800 pb-2">
            <div class="flex items-center gap-2">
              <span class="text-2xl">🏪</span>
              <div>
                <h3 class="text-sm font-black uppercase text-emerald-400">Тайная Лавка Снаряжения</h3>
                <div class="flex items-center gap-2 text-[11px] font-bold text-amber-300">
                  <span>🪙 ${(userGold).toLocaleString()}</span>
                  <span>💎 ${userGems}</span>
                </div>
              </div>
            </div>
            <button onclick="window.RPG.closeShopModal()" class="w-7 h-7 rounded-full bg-slate-800 text-slate-400 hover:text-white flex items-center justify-center text-xs">
              ✕
            </button>
          </div>

          <!-- Category Filters -->
          <div class="flex items-center gap-1 overflow-x-auto pb-1 text-[10.5px] font-bold">
            ${filterTabs
              .map(
                (t) => `
              <button onclick="window.RPG.setShopFilter('${t.id}')" class="px-2.5 py-1 rounded-xl whitespace-nowrap transition-all ${
                  filter === t.id
                    ? "bg-emerald-500 text-slate-950 font-black shadow-sm"
                    : "bg-slate-800 text-slate-400 hover:text-white"
                }">
                ${t.label}
              </button>
            `
              )
              .join("")}
          </div>

          <!-- Catalog List -->
          <div class="flex-1 overflow-y-auto space-y-2 pr-1 custom-scrollbar">
            ${
              RPG_STATE.shopLoading
                ? `
                <div class="py-14 text-center text-slate-400 text-xs flex flex-col items-center justify-center gap-3">
                  <div class="w-8 h-8 border-3 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
                  <span class="font-bold text-slate-300">Загрузка товаров лавки... 🏪</span>
                </div>
              `
                : filteredItems.length === 0
                ? `
                <div class="py-10 text-center text-slate-400 text-xs space-y-3">
                  <span class="text-3xl block">📦</span>
                  <p>В этой категории товары отсутствуют или обновляются.</p>
                  <button onclick="window.RPG.reloadShopCatalog()" class="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-amber-400 font-black text-xs border border-slate-700">
                    🔄 Обновить ассортимент
                  </button>
                </div>
              `
                : filteredItems
                    .map((item) => {
                      const rInfo = RARITY_MAP[item.rarity] || RARITY_MAP.common;
                      const costGold = item.price_gold || 0;
                      const costGems = item.price_gems || 0;
                      const canAfford = userGold >= costGold && userGems >= costGems;
                      const isBuying = RPG_STATE.buyingItemId === item.id;
                      const slotBadge = item.slot_name || (item.slot === "weapon" ? "Оружие" : item.slot === "armor" ? "Броня" : item.slot === "relic" ? "Реликвия" : "Зелье");

                      return `
                        <div class="p-3 rounded-2xl bg-slate-800/70 border border-slate-700/80 flex items-center justify-between gap-3 hover:border-emerald-500/40 transition-colors">
                          <div class="flex items-center gap-3 min-w-0">
                            <div class="w-10 h-10 rounded-xl bg-slate-900 border border-slate-700 flex items-center justify-center text-2xl shrink-0">
                              ${item.icon || "📦"}
                            </div>
                            <div class="min-w-0">
                              <div class="flex items-center gap-1.5 flex-wrap">
                                <span class="text-xs font-black truncate">${item.name}</span>
                                <span class="text-[9px] font-extrabold px-1.5 py-0.2 rounded-md ${rInfo.badge}">${rInfo.name}</span>
                                <span class="text-[9px] font-bold px-1 rounded bg-black/30 text-slate-300">[${slotBadge}]</span>
                              </div>
                              <p class="text-[10px] text-amber-300/90 font-medium line-clamp-2 leading-tight mt-0.5">${item.bonus_desc || ""}</p>
                            </div>
                          </div>

                          <div class="shrink-0 text-right space-y-1">
                            <div class="text-[11px] font-extrabold flex items-center justify-end gap-1.5">
                              ${costGold > 0 ? `<span class="${userGold >= costGold ? 'text-amber-400' : 'text-rose-400'}">${costGold} 🪙</span>` : ""}
                              ${costGems > 0 ? `<span class="${userGems >= costGems ? 'text-cyan-400' : 'text-rose-400'}">${costGems} 💎</span>` : ""}
                            </div>
                            <button onclick="window.RPG.buyShopItem('${item.id}')" ${!canAfford || isBuying ? "disabled" : ""} class="px-3 py-1.5 rounded-xl text-xs font-black transition-all active:scale-95 ${
                              canAfford && !isBuying
                                ? "bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 text-slate-950 shadow-md shadow-emerald-500/20"
                                : "bg-slate-700 text-slate-400 opacity-50 cursor-not-allowed"
                            }">
                              ${isBuying ? "Покупка..." : "Купить"}
                            </button>
                          </div>
                        </div>
                      `;
                    })
                    .join("")
            }
          </div>
        </div>
      </div>
    `;
  }

  function renderSlotFilterModalHTML(slotKey) {
    const p = RPG_STATE.profile || {};
    const inv = p.inventory || [];
    const eq = p.equipment || {};
    const sKey = (slotKey || "").toLowerCase();
    const currEquipped = eq[sKey] || eq[slotKey];
    const slotRu = sKey.startsWith("slot_") ? "Слот " + sKey.split("_")[1] : sKey;
    const matchingItems = inv.filter((it) => {
      const islot = (it.slot || it.type || "").toLowerCase();
      return islot === "weapon" || islot === "armor" || islot === "relic" || islot.startsWith("slot_");
    });

    return `
      <div class="fixed inset-0 z-50 bg-black/75 backdrop-blur-xs flex items-center justify-center p-4">
        <div class="w-full max-w-sm max-h-[85vh] flex flex-col rounded-3xl bg-white dark:bg-slate-900 border-2 border-amber-500/60 p-5 space-y-3 shadow-2xl animate-scale-up text-slate-900 dark:text-white">
          <div class="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
            <h3 class="text-xs font-black uppercase tracking-wider text-amber-500 flex items-center gap-1.5">
              <span>🛡️</span> Выбор снаряжения: ${slotRu}
            </h3>
            <button onclick="window.RPG.closeSlotFilterModal()" class="w-7 h-7 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-400 hover:text-white flex items-center justify-center text-xs">
              ✕
            </button>
          </div>

          ${
            currEquipped
              ? `
            <!-- Currently Equipped Item Banner -->
            <div class="p-3 rounded-2xl bg-amber-500/10 border border-amber-500/40 space-y-1.5 shrink-0">
              <div class="flex items-center justify-between text-[10px] font-black text-amber-500 dark:text-amber-400 uppercase">
                <span>🛡️ Сейчас надето:</span>
                <button onclick="window.RPG.unequipItem('${slotKey}')" class="text-rose-500 hover:text-rose-400 font-bold underline text-[9.5px]">
                  Снять в рюкзак
                </button>
              </div>
              <div class="flex items-center gap-2.5">
                <span class="text-2xl">${currEquipped.icon || "🗡️"}</span>
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-1">
                    <span class="text-xs font-black truncate">${currEquipped.name}</span>
                    ${(currEquipped.forge_level || currEquipped.upgrade) ? `<span class="px-1 rounded bg-amber-500 text-slate-950 font-black text-[8px]">+${currEquipped.forge_level || currEquipped.upgrade}</span>` : ""}
                  </div>
                  <span class="text-[10px] text-slate-500 dark:text-slate-400 truncate block">${currEquipped.bonus_desc || ""}</span>
                </div>
              </div>
            </div>
          `
              : ""
          }

          <div class="flex-1 overflow-y-auto space-y-2 pr-1 custom-scrollbar">
            ${
              matchingItems.length === 0
                ? `
              <div class="py-6 text-center space-y-3">
                <span class="text-3xl block">🎒</span>
                <p class="text-xs text-slate-400">В вашем рюкзаке пока нет других предметов типа <b>${slotRu}</b>.</p>
                <button onclick="window.RPG.closeSlotFilterModal(); window.RPG.openShopModal(); window.RPG.setShopFilter('${slotKey}');" class="px-4 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 active:scale-95 text-white font-black text-xs shadow-md">
                  Купить ${slotRu} в Лавке Снаряжения 🏪
                </button>
              </div>
            `
                : matchingItems
                    .map((item) => {
                      const rInfo = RARITY_MAP[item.rarity] || RARITY_MAP.common;
                      const forgeTag = (item.forge_level || item.upgrade) > 0 ? `+${item.forge_level || item.upgrade}` : "";
                      return `
                        <div class="p-3 rounded-2xl border-2 ${rInfo.color} flex items-center justify-between gap-2 bg-slate-50 dark:bg-slate-800/60">
                          <div class="flex items-center gap-2.5 min-w-0">
                            <span class="text-2xl shrink-0">${item.icon || "📦"}</span>
                            <div class="min-w-0">
                              <div class="flex items-center gap-1">
                                <span class="text-xs font-black truncate">${item.name}</span>
                                ${forgeTag ? `<span class="px-1 rounded bg-amber-500 text-slate-950 font-black text-[8px]">${forgeTag}</span>` : ""}
                              </div>
                              <span class="text-[10px] text-slate-500 dark:text-slate-400 truncate block">${item.bonus_desc || ""}</span>
                            </div>
                          </div>
                          <button onclick="window.RPG.equipItem('${item.uid}', '${slotKey}')" class="px-3.5 py-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-black text-xs shrink-0 shadow-sm flex items-center gap-1">
                            <span>⚔️</span>
                            <span>${currEquipped ? "Сменить" : "Надеть"}</span>
                          </button>
                        </div>
                      `;
                    })
                    .join("")
            }
          </div>
        </div>
      </div>
    `;
  }

  function renderHeroSelectHTML() {
    const heroes = RPG_STATE.heroesList || [];

    return `
      <div class="space-y-4 py-2">
        <div class="text-center space-y-1">
          <h2 class="text-base font-black text-slate-900 dark:text-white tracking-tight flex items-center justify-center gap-1.5">
            <span>⚔️</span> Выберите героя natarGRP
          </h2>
          <p class="text-xs text-slate-400">У каждого героя уникальный основной атрибут (+1 Урон за очко) и коронный скилл!</p>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          ${heroes
            .map(
              (h) => `
            <div class="p-3.5 rounded-2xl bg-white dark:bg-slate-800 border-2 border-slate-200 dark:border-slate-700 hover:border-amber-500 transition-all space-y-2.5 shadow-sm">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2.5">
                  <span class="text-3xl">${h.avatar || h.icon}</span>
                  <div>
                    <h3 class="text-xs font-black text-slate-900 dark:text-white">${h.name}</h3>
                    <span class="text-[10px] font-extrabold px-1.5 py-0.2 rounded-md ${
                      h.attr === "Сила" ? "bg-red-500/10 text-red-600" : h.attr === "Ловкость" ? "bg-emerald-500/10 text-emerald-600" : "bg-sky-500/10 text-sky-600"
                    }">
                      Основной: ${h.attr}
                    </span>
                  </div>
                </div>
              </div>

              <p class="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed font-normal">${h.desc}</p>

              <div class="p-2 rounded-xl bg-slate-50 dark:bg-slate-900/60 text-[10.5px] font-bold text-amber-600 dark:text-amber-400">
                ⚡ ${h.skill?.name}: ${h.skill?.desc}
              </div>

              <button onclick="window.RPG.selectHero('${h.id}')" class="w-full py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-yellow-400 hover:from-amber-400 active:scale-95 text-slate-950 font-black text-xs shadow-md">
                Выбрать героя ⚔️
              </button>
            </div>
          `
            )
            .join("")}
        </div>
      </div>
    `;
  }

  // ===========================================================================
  // PUBLIC API EXPOSURE
  // ===========================================================================

