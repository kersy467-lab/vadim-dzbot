/**
 * dice.js — Модуль игры «Кости» (Dice) на монеты для Telegram Mini App.
 * Экспортирует window.DICE = { init, cleanup, roll, setMode, setStake, setPrediction }
 */
(function () {
  'use strict';

  let containerEl = null;
  let userCoins = 0;
  let isCurrencyActive = true;
  let selectedStake = 25;
  let currentMode = 'duel'; // 'duel' | 'over_under'
  let selectedPrediction = 'under_7'; // 'under_7' | 'over_7' | 'exact_7' | 'double'
  let isRolling = false;
  let lastResult = null;

  // Точки для каждого значения кубика от 1 до 6
  const DICE_DOTS = {
    1: [4],
    2: [0, 8],
    3: [0, 4, 8],
    4: [0, 2, 6, 8],
    5: [0, 2, 4, 6, 8],
    6: [0, 2, 3, 5, 6, 8]
  };

  function renderDieHTML(val, isRollingNow) {
    const v = Math.min(Math.max(1, val || 1), 6);
    const activeDots = new Set(DICE_DOTS[v] || [4]);
    const dotsHTML = Array.from({ length: 9 }, (_, i) => {
      return `<div class="dc-dot ${activeDots.has(i) ? 'dc-dot--active' : ''}"></div>`;
    }).join('');

    const animCls = isRollingNow ? 'dc-die--roll' : '';
    return `<div class="dc-die ${animCls}">${dotsHTML}</div>`;
  }

  function injectCSS() {
    if (document.getElementById('dice-styles')) return;
    const style = document.createElement('style');
    style.id = 'dice-styles';
    style.textContent = `
      .dc-die { width: 56px; height: 56px; background: #ffffff; border-radius: 12px; border: 2px solid #cbd5e1; box-shadow: 0 6px 12px rgba(0,0,0,0.15); display: grid; grid-template-columns: repeat(3, 1fr); grid-template-rows: repeat(3, 1fr); padding: 5px; gap: 3px; transition: transform 0.4s ease; flex-shrink: 0; }
      .dc-dot { width: 8px; height: 8px; border-radius: 50%; background: transparent; margin: auto; }
      .dc-dot--active { background: #0f172a; }
      .dc-die--roll { animation: dcRoll 0.6s ease-in-out infinite alternate; }
      @keyframes dcRoll { 0% { transform: rotate(0deg) scale(0.95); } 100% { transform: rotate(180deg) scale(1.05); } }
      .dc-mode-btn { flex: 1; padding: 8px 10px; font-weight: 800; font-size: 11px; border-radius: 12px; transition: all 0.15s; }
      .dc-chip { padding: 5px 10px; border-radius: 10px; font-weight: 800; font-size: 0.8rem; border: 1.5px solid #cbd5e1; background: #fff; color: #0f172a; cursor: pointer; }
      .dc-chip.active { background: #f59e0b; color: #000; border-color: #f59e0b; }
    `;
    document.head.appendChild(style);
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

    let statusText = 'Выберите режим, ставку и бросайте кубики!';
    let statusBg = 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300';

    if (lastResult) {
      if (lastResult.mode === 'duel') {
        if (lastResult.status === 'super_win') {
          statusText = `🔥 Супер-победа с дублем! (+${lastResult.net_profit} 🪙)`;
          statusBg = 'bg-amber-100 dark:bg-amber-950/70 text-amber-900 dark:text-amber-200 border-amber-400';
        } else if (lastResult.status === 'win') {
          statusText = `🏆 Победа над дилером! (+${lastResult.net_profit} 🪙)`;
          statusBg = 'bg-emerald-100 dark:bg-emerald-950/70 text-emerald-800 dark:text-emerald-300 border-emerald-400';
        } else if (lastResult.status === 'push') {
          statusText = `🤝 Ничья! Ставка ${lastResult.stake} 🪙 возвращена`;
          statusBg = 'bg-blue-100 dark:bg-blue-950/70 text-blue-800 dark:text-blue-300';
        } else {
          statusText = `Дилер выбросил больше (-${lastResult.stake} 🪙)`;
          statusBg = 'bg-rose-100 dark:bg-rose-950/70 text-rose-800 dark:text-rose-300';
        }
      } else {
        if (lastResult.is_won) {
          statusText = `🎉 Точно в цель! Сумма: ${lastResult.total}. Выигрыш: +${lastResult.net_profit} 🪙`;
          statusBg = 'bg-emerald-100 dark:bg-emerald-950/70 text-emerald-800 dark:text-emerald-300 border-emerald-400';
        } else {
          statusText = `Не угадали. Выпало ${lastResult.total} (-${lastResult.stake} 🪙)`;
          statusBg = 'bg-rose-100 dark:bg-rose-950/70 text-rose-800 dark:text-rose-300';
        }
      }
    }

    const pDice = (lastResult?.player_dice || lastResult?.dice || [3, 4]);
    const dDice = (lastResult?.dealer_dice || [2, 3]);

    return `
      <div class="space-y-3 max-w-md mx-auto">
        <!-- Шапка -->
        <div class="flex items-center justify-between px-1">
          <div class="flex items-center gap-1.5 font-black text-sm text-slate-900 dark:text-white">
            <span>🎲</span> <span>Кости (Dice)</span>
          </div>
          <div class="text-xs font-black px-2.5 py-1 rounded-xl bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border border-amber-300/40">
            🪙 ${userCoins} монет
          </div>
        </div>

        <!-- Переключатель режимов -->
        <div class="flex gap-1 p-1 bg-slate-200/80 dark:bg-slate-800 rounded-xl">
          <button onclick="window.DICE.setMode('duel')" class="dc-mode-btn ${currentMode === 'duel' ? 'bg-white dark:bg-slate-700 text-blue-600 dark:text-blue-400 shadow-sm' : 'text-slate-500'}">
            ⚔️ Дуэль с дилером
          </button>
          <button onclick="window.DICE.setMode('over_under')" class="dc-mode-btn ${currentMode === 'over_under' ? 'bg-white dark:bg-slate-700 text-blue-600 dark:text-blue-400 shadow-sm' : 'text-slate-500'}">
            🎯 Больше / Меньше 7
          </button>
        </div>

        <!-- Арена броска -->
        <div class="p-4 bg-gradient-to-br from-slate-900 to-indigo-950 rounded-2xl text-white space-y-3 shadow-inner">
          ${currentMode === 'duel' ? `
            <!-- Режим Дуэль -->
            <div class="flex items-center justify-around">
              <div class="text-center space-y-1">
                <div class="text-[11px] font-bold text-slate-300">🤵 Дилер (${lastResult?.dealer_total || '?'})</div>
                <div class="flex gap-2 justify-center">${renderDieHTML(dDice[0], isRolling)} ${renderDieHTML(dDice[1], isRolling)}</div>
              </div>
              <div class="text-xl font-black text-amber-400">VS</div>
              <div class="text-center space-y-1">
                <div class="text-[11px] font-bold text-slate-300">👤 Вы (${lastResult?.player_total || '?'})</div>
                <div class="flex gap-2 justify-center">${renderDieHTML(pDice[0], isRolling)} ${renderDieHTML(pDice[1], isRolling)}</div>
              </div>
            </div>
          ` : `
            <!-- Режим Больше / Меньше 7 -->
            <div class="text-center space-y-2">
              <div class="text-xs font-bold text-slate-300">Сумма очков: <span class="text-amber-400 text-base font-black">${lastResult?.total || '?'}</span></div>
              <div class="flex gap-3 justify-center">${renderDieHTML(pDice[0], isRolling)} ${renderDieHTML(pDice[1], isRolling)}</div>
            </div>
          `}
        </div>

        <!-- Статус раунда -->
        <div class="py-1.5 px-3 rounded-xl text-center text-xs font-bold ${statusBg} border">
          ${statusText}
        </div>

        <!-- Выбор ставок для режима Больше / Меньше 7 -->
        ${currentMode === 'over_under' ? `
          <div class="grid grid-cols-4 gap-1.5">
            <button onclick="window.DICE.setPrediction('under_7')" class="p-2 rounded-xl text-center border font-extrabold text-[11px] ${selectedPrediction === 'under_7' ? 'bg-blue-600 text-white border-blue-600 shadow' : 'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700'}">
              < 7 (1:1)
            </button>
            <button onclick="window.DICE.setPrediction('exact_7')" class="p-2 rounded-xl text-center border font-extrabold text-[11px] ${selectedPrediction === 'exact_7' ? 'bg-amber-600 text-white border-amber-600 shadow' : 'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700'}">
              = 7 (4:1)
            </button>
            <button onclick="window.DICE.setPrediction('over_7')" class="p-2 rounded-xl text-center border font-extrabold text-[11px] ${selectedPrediction === 'over_7' ? 'bg-blue-600 text-white border-blue-600 shadow' : 'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700'}">
              > 7 (1:1)
            </button>
            <button onclick="window.DICE.setPrediction('double')" class="p-2 rounded-xl text-center border font-extrabold text-[11px] ${selectedPrediction === 'double' ? 'bg-purple-600 text-white border-purple-600 shadow' : 'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700'}">
              Дубль (2:1)
            </button>
          </div>
        ` : ''}

        <!-- Панель фишек ставки -->
        <div class="p-3 bg-white dark:bg-slate-800 rounded-2xl border border-slate-200 dark:border-slate-700 space-y-2.5">
          <div class="flex items-center justify-between text-xs font-bold text-slate-600 dark:text-slate-300">
            <span>Ставка:</span>
            <span class="text-amber-600 dark:text-amber-400 font-extrabold text-sm" id="dc-stake-display">${selectedStake} 🪙</span>
          </div>

          <!-- Чипы -->
          <div class="flex gap-1.5 justify-center flex-wrap">
            ${[10, 25, 50, 100, 250].map(v => `
              <button onclick="window.DICE.setStake(${v})" class="dc-chip ${selectedStake === v ? 'active' : ''}">${v}</button>
            `).join('')}
          </div>

          <!-- Произвольная ставка и Ва-банк -->
          <div class="flex items-center gap-2">
            <div class="relative flex-1">
              <input 
                type="number" 
                id="dc-custom-stake-input" 
                class="w-full text-center font-black text-sm py-1.5 px-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-white outline-none focus:border-amber-500" 
                placeholder="Своя ставка..." 
                min="1" 
                max="${userCoins}" 
                value="${selectedStake > 0 ? selectedStake : ''}" 
                oninput="window.DICE.setCustomStake(this.value)"
                onchange="window.DICE.setCustomStake(this.value, true)"
              />
            </div>
            <button type="button" onclick="window.DICE.setAllIn()" class="dc-chip text-amber-500 font-black py-1.5 px-3" title="Поставить все монеты">
              🔥 Ва-банк
            </button>
          </div>
        </div>

        <!-- Кнопка броска -->
        <button id="dc-roll-btn" onclick="window.DICE.roll()" ${userCoins < selectedStake || selectedStake <= 0 || isRolling ? 'disabled' : ''} class="w-full py-3 rounded-2xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-black text-sm shadow-md transition-all flex items-center justify-center gap-2">
          <span>🎲</span> <span class="dc-roll-text">${isRolling ? 'Кубики крутятся...' : `Бросить кубики (${selectedStake} 🪙)`}</span>
        </button>
      </div>
    `;
  }

  function render() {
    if (!containerEl) return;
    containerEl.innerHTML = renderHTML();
  }

  function getUserId() {
    if (window.currentUser?.tg_id) return window.currentUser.tg_id;
    if (window.currentUser?.id) return window.currentUser.id;
    try {
      const p = new URLSearchParams(window.location.search);
      const u = p.get('tg_user_id') || p.get('uid') || p.get('user_id');
      if (u) return parseInt(u, 10);
    } catch (e) {}
    try {
      if (window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
        return window.Telegram.WebApp.initDataUnsafe.user.id;
      }
    } catch (e) {}
    try {
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

  async function roll() {
    if (isRolling || userCoins < selectedStake || selectedStake <= 0) return;
    isRolling = true;
    render();

    const endpoint = currentMode === 'duel' ? '/api/dice/duel' : '/api/dice/over_under';
    const body = currentMode === 'duel'
      ? { stake: selectedStake }
      : { stake: selectedStake, prediction: selectedPrediction };

    try {
      const { ok, data } = await apiCall(endpoint, body);
      if (!ok) {
        alert(data.detail || 'Ошибка броска');
        isRolling = false;
        render();
        return;
      }

      setTimeout(() => {
        isRolling = false;
        lastResult = data.result;
        userCoins = data.coins;
        if (window.currentUser) window.currentUser.coins = userCoins;
        render();
      }, 700);

    } catch (e) {
      alert(e.message || 'Ошибка соединения с сервером');
      isRolling = false;
      render();
    }
  }

  function setMode(mode) {
    currentMode = mode;
    lastResult = null;
    render();
  }

  function setPrediction(pred) {
    selectedPrediction = pred;
    render();
  }

  function syncStakeUI() {
    const disp = document.getElementById('dc-stake-display');
    if (disp) disp.textContent = `${selectedStake} 🪙`;
    const input = document.getElementById('dc-custom-stake-input');
    if (input && document.activeElement !== input) {
      input.value = selectedStake > 0 ? selectedStake : '';
    }
    const chips = containerEl?.querySelectorAll('.dc-chip');
    chips?.forEach(c => {
      const v = parseInt(c.textContent, 10);
      if (v === selectedStake) c.classList.add('active');
      else c.classList.remove('active');
    });
    const rollBtn = document.getElementById('dc-roll-btn');
    if (rollBtn) {
      rollBtn.disabled = userCoins < selectedStake || selectedStake <= 0 || isRolling;
      const textSpan = rollBtn.querySelector('.dc-roll-text');
      if (textSpan) textSpan.textContent = isRolling ? 'Кубики крутятся...' : `Бросить кубики (${selectedStake} 🪙)`;
    }
  }

  function setStake(amount) {
    selectedStake = Math.min(Math.max(1, amount), userCoins || 1);
    syncStakeUI();
  }

  function setCustomStake(amount, isChange = false) {
    let num = parseInt(amount, 10);
    if (isNaN(num) || num < 1) num = isChange ? 1 : 0;
    if (userCoins > 0 && num > userCoins) num = userCoins;
    selectedStake = num;
    syncStakeUI();
  }

  function setAllIn() {
    selectedStake = Math.max(1, userCoins);
    syncStakeUI();
  }

  async function syncState() {
    try {
      const { ok, status, data } = await apiCall('/api/dice/state');
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
    containerEl = el || document.getElementById('dice-root');
    injectCSS();
    if (window.currentUser) {
      isCurrencyActive = Boolean(window.currentUser.currency_ecosystem_enabled);
      userCoins = Number(window.currentUser.coins || 0);
      if (selectedStake > userCoins && userCoins > 0) selectedStake = Math.min(25, userCoins);
    }
    syncState();
  }

  function cleanup() {
    containerEl = null;
    isRolling = false;
  }

  window.DICE = {
    init,
    cleanup,
    roll,
    setMode,
    setPrediction,
    setStake,
    setCustomStake,
    setAllIn,
  };
})();
