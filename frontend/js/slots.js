/**
 * slots.js — Модуль «Слоты» (Однорукий бандит) на 3 барабана для Telegram Mini App.
 * Экспортирует window.SLOTS = { init, cleanup, spin, setStake, setCustomStake, setAllIn, togglePaytable }
 */
(function () {
  'use strict';

  let containerEl = null;
  let userCoins = 0;
  let isCurrencyActive = true;
  let currentStake = 25;
  let isSpinning = false;
  let lastResult = null;
  let showPaytable = false;
  let spinIntervals = [null, null, null];

  const SYMBOLS = ["🍒", "🍋", "🍇", "🔔", "💎", "7️⃣"];
  let displayedReels = ["7️⃣", "💎", "🍒"];

  function getUserId() {
    if (window.currentUser?.tg_id || window.currentUser?.id) return window.currentUser.tg_id || window.currentUser.id;
    try {
      const p = new URLSearchParams(window.location.search);
      const u = p.get('tg_user_id') || p.get('uid') || p.get('user_id');
      if (u) return parseInt(u, 10);
      if (window.Telegram?.WebApp?.initDataUnsafe?.user?.id) return window.Telegram.WebApp.initDataUnsafe.user.id;
      const c = localStorage.getItem('cached_tg_uid');
      if (c && /^[0-9]+$/.test(c)) return parseInt(c, 10);
    } catch (e) {}
    return 0;
  }

  async function apiCall(endpoint, body = null) {
    const uid = getUserId();
    const sep = endpoint.includes('?') ? '&' : '?';
    const url = uid ? `${endpoint}${sep}tg_user_id=${uid}` : endpoint;
    const headers = { 'Content-Type': 'application/json' };
    if (uid) headers['X-Telegram-User-Id'] = String(uid);
    try {
      const rawInit = window.Telegram?.WebApp?.initData;
      if (rawInit && /^[\x20-\x7E]*$/.test(rawInit)) headers['X-Telegram-Init-Data'] = rawInit;
    } catch (e) {}

    const opts = { headers };
    if (body !== null) {
      opts.method = 'POST';
      const payload = typeof body === 'object' && body !== null ? { ...body } : {};
      if (uid && !payload.user_id) payload.user_id = uid;
      if (uid && !payload.tg_user_id) payload.tg_user_id = uid;
      opts.body = JSON.stringify(payload);
    }

    const res = await fetch(url, opts);
    let data = {};
    try {
      data = await res.json();
    } catch (e) {
      data = { detail: `HTTP ${res.status}: ${res.statusText || 'Ошибка ответа сервера'}` };
    }
    return { ok: res.ok, status: res.status, data };
  }

  function triggerHaptic(type = 'impact', style = 'medium') {
    try {
      const h = window.Telegram?.WebApp?.HapticFeedback;
      if (!h) return;
      if (type === 'impact') h.impactOccurred(style);
      else if (type === 'notification') h.notificationOccurred(style);
    } catch (e) {}
  }

  function fmtNum(n) {
    if (typeof n !== 'number') n = Number(n) || 0;
    return n.toLocaleString('ru-RU');
  }

  function syncStakeUI() {
    const disp = document.getElementById('slots-stake-display');
    if (disp) disp.textContent = `${fmtNum(currentStake)} 🪙`;
    const spinBtn = document.getElementById('slots-spin-btn');
    if (spinBtn && !isSpinning) {
      spinBtn.innerHTML = `<span>🎰</span> <span>Крутить! (${fmtNum(currentStake)} 🪙)</span>`;
      spinBtn.disabled = currentStake <= 0 || (userCoins > 0 && currentStake > userCoins);
    }
    const input = document.getElementById('slots-custom-stake-input');
    if (input && document.activeElement !== input) {
      input.value = currentStake > 0 ? currentStake : '';
    }
    const btns = containerEl?.querySelectorAll('.slots-chip-btn');
    btns?.forEach(b => {
      const v = parseInt(b.textContent.replace(/\s+/g, ''), 10);
      if (v === currentStake) {
        b.className = 'slots-chip-btn px-2.5 py-1.5 rounded-xl text-xs font-black border bg-amber-500 text-black border-amber-500 shadow';
      } else {
        b.className = 'slots-chip-btn px-2.5 py-1.5 rounded-xl text-xs font-black border bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 border-slate-300 dark:border-slate-600';
      }
    });
  }

  function setStake(val) {
    if (isSpinning) return;
    currentStake = Math.min(Math.max(1, val), userCoins || 1);
    syncStakeUI();
  }

  function setCustomStake(val, isChange = false) {
    if (isSpinning) return;
    const cleanStr = String(val || '').replace(/\s+/g, '');
    let num = parseInt(cleanStr, 10);
    if (isNaN(num) || num < 1) num = isChange ? 1 : 0;
    if (userCoins > 0 && num > userCoins) num = userCoins;
    currentStake = num;
    syncStakeUI();
  }

  function setAllIn() {
    if (isSpinning) return;
    currentStake = Math.max(1, userCoins);
    syncStakeUI();
  }

  function togglePaytable() {
    showPaytable = !showPaytable;
    render();
  }

  function renderHTML() {
    if (!isCurrencyActive) {
      return `
        <div class="p-6 text-center space-y-4 bg-white dark:bg-slate-800 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-sm max-w-sm mx-auto my-4">
          <div class="text-4xl">🪙🔒</div>
          <h3 class="text-base font-black text-slate-900 dark:text-white">Игровая экосистема отключена</h3>
          <p class="text-xs text-slate-500 dark:text-slate-400">Включите экосистему в боте: <b>⚙️ Настройки → 🪙 Игровая экосистема</b></p>
        </div>`;
    }

    let statusText = 'Выберите ставку и нажмите «Крутить!»';
    let statusBg = 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700';
    if (isSpinning) {
      statusText = '🎰 Барабаны вращаются...';
      statusBg = 'bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border-amber-300/40';
    } else if (lastResult) {
      if (lastResult.status === 'jackpot') {
        statusText = `🔥 ДЖЕКПОТ! ${lastResult.combination} (+${fmtNum(lastResult.payout)} 🪙)!`;
        statusBg = 'bg-amber-500 text-black border-amber-400 font-black animate-pulse';
      } else if (lastResult.payout > 0) {
        statusText = `🎉 ${lastResult.combination}! Выигрыш: +${fmtNum(lastResult.payout)} 🪙 (x${lastResult.multiplier})`;
        statusBg = 'bg-emerald-100 dark:bg-emerald-950/70 text-emerald-800 dark:text-emerald-300 border-emerald-400';
      } else {
        statusText = `Выпало [ ${lastResult.reels.join(' ')} ]. Ставка не сыграла (-${fmtNum(lastResult.stake)} 🪙)`;
        statusBg = 'bg-rose-100 dark:bg-rose-950/70 text-rose-800 dark:text-rose-300 border-rose-300';
      }
    }

    const paytableHTML = showPaytable ? `
      <div class="p-2.5 bg-slate-100 dark:bg-slate-900/90 rounded-2xl border border-slate-200 dark:border-slate-700 text-xs space-y-1 text-slate-700 dark:text-slate-300">
        <div class="font-black text-slate-900 dark:text-white flex justify-between"><span>📜 Таблица выплат</span><button onclick="window.SLOTS.togglePaytable()" class="text-slate-400">✕</button></div>
        <div class="grid grid-cols-2 gap-1 pt-0.5 text-[11px] font-semibold">
          <div>7️⃣ 7️⃣ 7️⃣ — <b class="text-amber-500">50x</b> (Джекпот)</div><div>💎 💎 💎 — <b class="text-blue-400">30x</b></div>
          <div>🔔 🔔 🔔 — <b class="text-yellow-400">15x</b></div><div>🍇 🍇 🍇 — <b class="text-purple-400">10x</b></div>
          <div>🍋 🍋 🍋 — <b class="text-lime-400">7x</b></div><div>🍒 🍒 🍒 — <b class="text-rose-400">7x</b></div>
          <div>Пара 7️⃣ / 💎 — <b>2.5x–3x</b></div><div>Пара 🔔 — <b>2x</b></div>
          <div>Пара 🍒 — <b>1.5x</b></div><div>Пара 🍇 / 🍋 — <b>0.5x–0.9x</b></div>
        </div>
      </div>` : '';

    return `
      <div class="space-y-3 max-w-md mx-auto">
        <!-- Шапка -->
        <div class="flex items-center justify-between px-1">
          <div class="flex items-center gap-1.5 font-black text-sm text-slate-900 dark:text-white">
            <span>🎰</span> <span>Однорукий бандит</span>
            <button onclick="window.SLOTS.togglePaytable()" class="ml-1 text-[11px] text-amber-500 font-bold underline" title="Таблица выплат">инфо</button>
          </div>
          <div class="text-xs font-black px-2.5 py-1 rounded-xl bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border border-amber-300/40">
            🪙 ${fmtNum(userCoins)} монет
          </div>
        </div>

        <!-- Таблица выплат -->
        ${paytableHTML}

        <!-- Игровой автомат: 3 барабана -->
        <div class="p-4 bg-gradient-to-b from-slate-900 to-slate-950 rounded-3xl border-4 border-amber-500/80 shadow-2xl space-y-3">
          <div class="grid grid-cols-3 gap-2.5">
            ${[0, 1, 2].map(i => `
              <div id="slots-reel-${i}" class="h-24 rounded-2xl bg-gradient-to-b from-slate-800 to-slate-900 border-2 border-slate-700 flex items-center justify-center text-5xl select-none shadow-inner transition-transform">
                ${displayedReels[i] || '🍒'}
              </div>
            `).join('')}
          </div>
        </div>

        <!-- Статус раунда -->
        <div class="py-2 px-3 rounded-xl text-center text-xs font-bold ${statusBg} border shadow-sm">
          ${statusText}
        </div>

        <!-- Выбор ставки -->
        <div class="p-3 bg-white dark:bg-slate-800 rounded-2xl border border-slate-200 dark:border-slate-700 space-y-2.5">
          <div class="flex items-center justify-between text-xs font-bold text-slate-600 dark:text-slate-300">
            <span>Размер ставки:</span>
            <span class="text-amber-600 dark:text-amber-400 font-black text-sm" id="slots-stake-display">${fmtNum(currentStake)} 🪙</span>
          </div>

          <div class="flex items-center gap-1 flex-wrap">
            ${[10, 25, 50, 100, 250].map(v => `
              <button type="button" onclick="window.SLOTS.setStake(${v})" class="slots-chip-btn px-2.5 py-1.5 rounded-xl text-xs font-black border ${currentStake === v ? 'bg-amber-500 text-black border-amber-500 shadow' : 'bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 border-slate-300 dark:border-slate-600'}">
                ${v}
              </button>
            `).join('')}
          </div>

          <div class="flex items-center gap-2">
            <input 
              type="number" 
              id="slots-custom-stake-input" 
              class="w-full text-center font-black text-sm py-1.5 px-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-white outline-none focus:border-amber-500" 
              placeholder="Своя ставка..." 
              min="1" 
              max="${userCoins}" 
              value="${currentStake > 0 ? currentStake : ''}" 
              oninput="window.SLOTS.setCustomStake(this.value)" 
              onchange="window.SLOTS.setCustomStake(this.value, true)"
              ${isSpinning ? 'disabled' : ''}
            />
            <button type="button" onclick="window.SLOTS.setAllIn()" ${isSpinning ? 'disabled' : ''} class="px-3 py-1.5 rounded-xl border border-amber-400/60 bg-amber-500/10 text-amber-500 font-extrabold text-xs shrink-0">
              🔥 Ва-банк
            </button>
          </div>
        </div>

        <!-- Кнопка вращения -->
        <button id="slots-spin-btn" onclick="window.SLOTS.spin()" ${isSpinning || currentStake <= 0 || currentStake > userCoins ? 'disabled' : ''} class="w-full py-3.5 rounded-2xl bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 disabled:opacity-50 text-slate-950 font-black text-base shadow-lg transition-all flex items-center justify-center gap-2">
          <span>🎰</span> <span>${isSpinning ? 'Крутим...' : `Крутить! (${fmtNum(currentStake)} 🪙)`}</span>
        </button>
      </div>
    `;
  }

  function render() {
    if (!containerEl) return;
    containerEl.innerHTML = renderHTML();
  }

  async function spin() {
    if (isSpinning || currentStake <= 0 || currentStake > userCoins) return;

    isSpinning = true;
    render();
    triggerHaptic('impact', 'medium');

    // Запуск визуального вращения барабанов
    [0, 1, 2].forEach(i => {
      spinIntervals[i] = setInterval(() => {
        const randomSym = SYMBOLS[Math.floor(Math.random() * SYMBOLS.length)];
        const reelEl = document.getElementById(`slots-reel-${i}`);
        if (reelEl) reelEl.textContent = randomSym;
      }, 75);
    });

    try {
      const { ok, data } = await apiCall('/api/slots/spin', { stake: currentStake });
      if (!ok) {
        clearIntervals();
        isSpinning = false;
        alert(data.detail || 'Ошибка вращения слотов');
        render();
        return;
      }

      // Последовательная остановка барабанов для эффекта интриги
      const targetReels = data.reels;
      const delays = [600, 1000, 1400];

      delays.forEach((delay, idx) => {
        setTimeout(() => {
          if (spinIntervals[idx]) clearInterval(spinIntervals[idx]);
          displayedReels[idx] = targetReels[idx];
          const reelEl = document.getElementById(`slots-reel-${idx}`);
          if (reelEl) {
            reelEl.textContent = targetReels[idx];
            reelEl.classList.add('scale-110');
            setTimeout(() => reelEl.classList.remove('scale-110'), 200);
          }
          triggerHaptic('impact', 'light');

          if (idx === 2) {
            // Остановка последнего барабана
            setTimeout(() => {
              isSpinning = false;
              lastResult = data;
              userCoins = data.coins;
              if (window.currentUser) window.currentUser.coins = userCoins;
              if (data.status === 'jackpot') triggerHaptic('notification', 'success');
              else if (data.payout > 0) triggerHaptic('impact', 'heavy');
              render();
            }, 300);
          }
        }, delay);
      });

    } catch (e) {
      clearIntervals();
      isSpinning = false;
      alert(e.message || 'Ошибка соединения');
      render();
    }
  }

  function clearIntervals() {
    spinIntervals.forEach(iv => { if (iv) clearInterval(iv); });
    spinIntervals = [null, null, null];
  }

  async function syncState() {
    try {
      const { ok, status, data } = await apiCall('/api/slots/state');
      if (status === 400 && data.detail && data.detail.includes('экосистем')) {
        isCurrencyActive = false;
      } else if (ok) {
        userCoins = data.coins || 0;
        if (window.currentUser) window.currentUser.coins = userCoins;
        isCurrencyActive = true;
      }
    } catch (e) {}
    render();
  }

  function init(el) {
    containerEl = el || document.getElementById('slots-root');
    if (window.currentUser) {
      isCurrencyActive = Boolean(window.currentUser.currency_ecosystem_enabled);
      userCoins = Number(window.currentUser.coins || 0);
    }
    syncState();
  }

  function cleanup() {
    clearIntervals();
    containerEl = null;
    isSpinning = false;
  }

  window.SLOTS = {
    init,
    cleanup,
    spin,
    setStake,
    setCustomStake,
    setAllIn,
    togglePaytable,
  };
})();
