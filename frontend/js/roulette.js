/**
 * roulette.js — Модуль Европейской Рулетки на монеты для Telegram Mini App.
 * Экспортирует window.ROULETTE = { init, cleanup, spin, addBet, clearBets, setChip }
 */
(function () {
  'use strict';

  let containerEl = null;
  let userCoins = 0;
  let isCurrencyActive = true;
  let selectedChip = 25;
  let activeBets = {}; // betKey -> amount
  let isSpinning = false;
  let lastSpin = null;

  const WHEEL_NUMBERS = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26];
  const REDS = new Set([1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]);

  function getNumColor(num) {
    if (num === 0) return 'green';
    return REDS.has(num) ? 'red' : 'black';
  }

  function getNumBg(color) {
    if (color === 'green') return 'bg-emerald-600 text-white';
    if (color === 'red') return 'bg-rose-600 text-white';
    return 'bg-slate-900 text-white';
  }

  function injectCSS() {
    if (document.getElementById('roulette-styles')) return;
    const style = document.createElement('style');
    style.id = 'roulette-styles';
    style.textContent = `
      .rl-tape-wrap { position: relative; overflow: hidden; height: 60px; background: #0f172a; border-radius: 14px; border: 2px solid #334155; }
      .rl-tape { display: flex; transition: transform 3.5s cubic-bezier(0.15, 0.9, 0.25, 1); will-change: transform; }
      .rl-cell { min-width: 48px; height: 56px; display: flex; align-items: center; justify-content: center; font-weight: 900; font-size: 15px; border-right: 1px solid rgba(255,255,255,0.1); }
      .rl-pointer { position: absolute; top: 0; left: 50%; transform: translateX(-50%); width: 0; height: 0; border-left: 9px solid transparent; border-right: 9px solid transparent; border-top: 11px solid #facc15; z-index: 10; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.5)); }
      .rl-bet-btn { position: relative; padding: 10px 6px; border-radius: 12px; font-weight: 800; font-size: 11px; text-align: center; border: 1.5px solid transparent; transition: all 0.15s; }
      .rl-bet-btn:active { transform: scale(0.96); }
      .rl-badge-bet { position: absolute; top: -6px; right: -6px; background: #f59e0b; color: #000; border-radius: 10px; font-size: 9px; font-weight: 900; padding: 1px 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.4); }
    `;
    document.head.appendChild(style);
  }

  function getTotalStake() {
    return Object.values(activeBets).reduce((acc, v) => acc + v, 0);
  }

  function addBet(type, value) {
    if (isSpinning) return;
    const key = value !== undefined ? `${type}:${value}` : type;
    const total = getTotalStake();
    if (total + selectedChip > userCoins) {
      alert(`Недостаточно монет. Ваш баланс: ${userCoins} 🪙`);
      return;
    }
    activeBets[key] = (activeBets[key] || 0) + selectedChip;
    render();
  }

  function clearBets() {
    if (isSpinning) return;
    activeBets = {};
    render();
  }

  function syncChipUI() {
    const disp = document.getElementById('rl-chip-display');
    if (disp) disp.textContent = `${selectedChip} 🪙`;
    const input = document.getElementById('rl-custom-chip-input');
    if (input && document.activeElement !== input) {
      input.value = selectedChip > 0 ? selectedChip : '';
    }
    const chipBtns = containerEl?.querySelectorAll('.rl-chip-btn');
    chipBtns?.forEach(c => {
      const v = parseInt(c.textContent, 10);
      if (v === selectedChip) {
        c.className = 'rl-chip-btn px-2 py-1 rounded-lg text-xs font-black border bg-amber-500 text-black border-amber-500 shadow';
      } else {
        c.className = 'rl-chip-btn px-2 py-1 rounded-lg text-xs font-black border bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 border-slate-300 dark:border-slate-600';
      }
    });
  }

  function setChip(val) {
    selectedChip = Math.min(Math.max(1, val), userCoins || 1);
    syncChipUI();
  }

  function setCustomChip(val, isChange = false) {
    let num = parseInt(val, 10);
    if (isNaN(num) || num < 1) num = isChange ? 1 : 0;
    if (userCoins > 0 && num > userCoins) num = userCoins;
    selectedChip = num;
    syncChipUI();
  }

  function setAllIn() {
    const remain = Math.max(1, userCoins - getTotalStake());
    selectedChip = remain;
    syncChipUI();
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

    const totalStake = getTotalStake();
    const tapeItems = [...WHEEL_NUMBERS, ...WHEEL_NUMBERS, ...WHEEL_NUMBERS];

    const tapeHTML = tapeItems.map(n => {
      const col = getNumColor(n);
      const bg = getNumBg(col);
      return `<div class="rl-cell ${bg}">${n}</div>`;
    }).join('');

    const b = activeBets;
    const betBadge = (key) => b[key] ? `<span class="rl-badge-bet">${b[key]}🪙</span>` : '';

    let statusText = 'Выберите фишку и сделайте ставки на столе';
    let statusBg = 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300';
    if (lastSpin) {
      const colName = lastSpin.color === 'red' ? 'Красное' : (lastSpin.color === 'black' ? 'Чёрное' : 'Зеро');
      if (lastSpin.net_profit > 0) {
        statusText = `🎉 Выпало ${lastSpin.winning_number} (${colName})! Выигрыш: +${lastSpin.net_profit} 🪙`;
        statusBg = 'bg-emerald-100 dark:bg-emerald-950/70 text-emerald-800 dark:text-emerald-300 border-emerald-400';
      } else {
        statusText = `Выпало ${lastSpin.winning_number} (${colName}). Ставка не сыграла (-${lastSpin.total_stake} 🪙)`;
        statusBg = 'bg-rose-100 dark:bg-rose-950/70 text-rose-800 dark:text-rose-300 border-rose-300';
      }
    }

    return `
      <div class="space-y-3 max-w-md mx-auto">
        <!-- Шапка -->
        <div class="flex items-center justify-between px-1">
          <div class="flex items-center gap-1.5 font-black text-sm text-slate-900 dark:text-white">
            <span>🎡</span> <span>Европейская Рулетка</span>
          </div>
          <div class="text-xs font-black px-2.5 py-1 rounded-xl bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border border-amber-300/40">
            🪙 ${userCoins} монет
          </div>
        </div>

        <!-- Барабан / Лента -->
        <div class="rl-tape-wrap">
          <div class="rl-pointer"></div>
          <div class="rl-tape" id="rl-tape">${tapeHTML}</div>
        </div>

        <!-- Статус раунда -->
        <div class="py-1.5 px-3 rounded-xl text-center text-xs font-bold ${statusBg} border">
          ${statusText}
        </div>

        <!-- Фишки и произвольная ставка -->
        <div class="p-2.5 bg-white dark:bg-slate-800 rounded-2xl border border-slate-200 dark:border-slate-700 space-y-2">
          <div class="flex items-center justify-between text-xs font-bold text-slate-600 dark:text-slate-300">
            <span>Номинал фишки:</span>
            <span class="text-amber-600 dark:text-amber-400 font-extrabold text-sm" id="rl-chip-display">${selectedChip} 🪙</span>
          </div>

          <div class="flex items-center justify-between gap-1 flex-wrap">
            <div class="flex gap-1 flex-wrap">
              ${[10, 25, 50, 100, 250].map(v => `
                <button type="button" onclick="window.ROULETTE.setChip(${v})" class="rl-chip-btn px-2 py-1 rounded-lg text-xs font-black border ${selectedChip === v ? 'bg-amber-500 text-black border-amber-500 shadow' : 'bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 border-slate-300 dark:border-slate-600'}">
                  ${v}
                </button>
              `).join('')}
            </div>
            <button type="button" onclick="window.ROULETTE.clearBets()" ${totalStake === 0 || isSpinning ? 'disabled' : ''} class="px-2 py-1 rounded-lg text-xs font-bold text-slate-400 hover:text-rose-500">
              Очистить
            </button>
          </div>

          <!-- Произвольный номинал и Ва-банк -->
          <div class="flex items-center gap-2">
            <div class="relative flex-1">
              <input 
                type="number" 
                id="rl-custom-chip-input" 
                class="w-full text-center font-black text-sm py-1.5 px-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-white outline-none focus:border-amber-500" 
                placeholder="Своя фишка..." 
                min="1" 
                max="${userCoins}" 
                value="${selectedChip > 0 ? selectedChip : ''}" 
                oninput="window.ROULETTE.setCustomChip(this.value)" 
                onchange="window.ROULETTE.setCustomChip(this.value, true)"
              />
            </div>
            <button type="button" onclick="window.ROULETTE.setAllIn()" class="px-3 py-1.5 rounded-xl border border-amber-400/60 bg-amber-500/10 text-amber-500 font-extrabold text-xs" title="Фишка на весь оставшийся баланс">
              🔥 Ва-банк
            </button>
          </div>
        </div>

        <!-- Сетка основных внешних ставок -->
        <div class="space-y-1.5">
          <div class="grid grid-cols-2 gap-2">
            <button onclick="window.ROULETTE.addBet('red')" class="rl-bet-btn bg-rose-600 text-white shadow-sm hover:bg-rose-700">🔴 Красное (1:1) ${betBadge('red')}</button>
            <button onclick="window.ROULETTE.addBet('black')" class="rl-bet-btn bg-slate-900 text-white shadow-sm hover:bg-black">⚫ Чёрное (1:1) ${betBadge('black')}</button>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <button onclick="window.ROULETTE.addBet('even')" class="rl-bet-btn bg-slate-200 dark:bg-slate-700 text-slate-800 dark:text-slate-200">Чёт (1:1) ${betBadge('even')}</button>
            <button onclick="window.ROULETTE.addBet('odd')" class="rl-bet-btn bg-slate-200 dark:bg-slate-700 text-slate-800 dark:text-slate-200">Нечет (1:1) ${betBadge('odd')}</button>
          </div>
          <div class="grid grid-cols-2 gap-2">
            <button onclick="window.ROULETTE.addBet('low')" class="rl-bet-btn bg-slate-200 dark:bg-slate-700 text-slate-800 dark:text-slate-200">1–18 (1:1) ${betBadge('low')}</button>
            <button onclick="window.ROULETTE.addBet('high')" class="rl-bet-btn bg-slate-200 dark:bg-slate-700 text-slate-800 dark:text-slate-200">19–36 (1:1) ${betBadge('high')}</button>
          </div>
          <div class="grid grid-cols-3 gap-1.5">
            <button onclick="window.ROULETTE.addBet('dozen1')" class="rl-bet-btn bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 border-blue-200">1–12 (2:1) ${betBadge('dozen1')}</button>
            <button onclick="window.ROULETTE.addBet('dozen2')" class="rl-bet-btn bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 border-blue-200">13–24 (2:1) ${betBadge('dozen2')}</button>
            <button onclick="window.ROULETTE.addBet('dozen3')" class="rl-bet-btn bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300 border-blue-200">25–36 (2:1) ${betBadge('dozen3')}</button>
          </div>
          <button onclick="window.ROULETTE.addBet('straight', 0)" class="w-full rl-bet-btn bg-emerald-700 text-white font-black hover:bg-emerald-800">🟢 Зеро 0 (35:1) ${betBadge('straight:0')}</button>
        </div>

        <!-- Кнопка запуска -->
        <button onclick="window.ROULETTE.spin()" ${totalStake === 0 || isSpinning ? 'disabled' : ''} class="w-full py-3 rounded-2xl bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-slate-950 font-black text-sm shadow-md transition-all flex items-center justify-center gap-2">
          <span>🎡</span> <span>${isSpinning ? 'Колесо вращается...' : `Крутить! (Ставка: ${totalStake} 🪙)`}</span>
        </button>
      </div>
    `;
  }

  function render() {
    if (!containerEl) return;
    containerEl.innerHTML = renderHTML();
  }

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

  async function spin() {
    const totalStake = getTotalStake();
    if (isSpinning || totalStake <= 0 || totalStake > userCoins) return;

    isSpinning = true;
    render();

    const betsPayload = Object.entries(activeBets).map(([k, amount]) => {
      if (k.startsWith('straight:')) {
        return { type: 'straight', value: parseInt(k.split(':')[1], 10), amount };
      }
      return { type: k, amount };
    });

    try {
      const { ok, data } = await apiCall('/api/roulette/spin', { bets: betsPayload });
      if (!ok) {
        alert(data.detail || 'Ошибка вращения');
        isSpinning = false;
        render();
        return;
      }

      // Анимация ленты к выигрышному числу
      const winNum = data.winning_number;
      const idxInWheel = WHEEL_NUMBERS.indexOf(winNum);
      const targetIndex = WHEEL_NUMBERS.length + idxInWheel; // берем средний круг
      const cellWidth = 48;
      const containerWidth = containerEl.querySelector('.rl-tape-wrap')?.offsetWidth || 340;
      const offset = (targetIndex * cellWidth) - (containerWidth / 2) + (cellWidth / 2);

      const tapeEl = document.getElementById('rl-tape');
      if (tapeEl) {
        tapeEl.style.transform = `translateX(-${offset}px)`;
      }

      setTimeout(() => {
        isSpinning = false;
        lastSpin = data;
        userCoins = data.coins;
        if (window.currentUser) window.currentUser.coins = userCoins;
        render();
      }, 3500);

    } catch (e) {
      alert(e.message || 'Ошибка соединения');
      isSpinning = false;
      render();
    }
  }

  async function syncState() {
    try {
      const { ok, status, data } = await apiCall('/api/roulette/state');
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
    containerEl = el || document.getElementById('roulette-root');
    injectCSS();
    if (window.currentUser) {
      isCurrencyActive = Boolean(window.currentUser.currency_ecosystem_enabled);
      userCoins = Number(window.currentUser.coins || 0);
    }
    syncState();
  }

  function cleanup() {
    containerEl = null;
    activeBets = {};
    isSpinning = false;
  }

  window.ROULETTE = {
    init,
    cleanup,
    spin,
    addBet,
    clearBets,
    setChip,
    setCustomChip,
    setAllIn,
  };
})();
