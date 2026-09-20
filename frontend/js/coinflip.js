/**
 * coinflip.js — Модуль «Подбрасывание монетки» (Орёл / Решка) для Telegram Mini App.
 * Экспортирует window.COINFLIP = { init, cleanup, flip, setChoice, setStake, setCustomStake, setAllIn }
 */
(function () {
  'use strict';

  let containerEl = null;
  let userCoins = 0;
  let isCurrencyActive = true;
  let currentStake = 25;
  let selectedChoice = 'heads'; // 'heads' или 'tails'
  let isFlipping = false;
  let lastResult = null;
  let coinSide = 'heads';

  function injectCSS() {
    if (document.getElementById('coinflip-styles')) return;
    const style = document.createElement('style');
    style.id = 'coinflip-styles';
    style.textContent = `
      .cf-coin-wrap { perspective: 800px; width: 110px; height: 110px; margin: 0 auto; }
      .cf-coin { width: 100%; height: 100%; border-radius: 50%; transform-style: preserve-3d; transition: transform 2.5s cubic-bezier(0.2, 0.85, 0.4, 1.05); position: relative; box-shadow: 0 10px 25px rgba(245, 158, 11, 0.4); }
      .cf-side { position: absolute; width: 100%; height: 100%; border-radius: 50%; backface-visibility: hidden; display: flex; flex-direction: column; align-items: center; justify-content: center; font-weight: 900; border: 4px solid #f59e0b; background: radial-gradient(circle at 35% 35%, #fef08a, #f59e0b 60%, #b45309); color: #78350f; user-select: none; }
      .cf-tails { transform: rotateY(180deg); background: radial-gradient(circle at 35% 35%, #fef9c3, #eab308 60%, #a16207); }
    `;
    document.head.appendChild(style);
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

  function triggerHaptic(type = 'impact', style = 'medium') {
    try {
      const h = window.Telegram?.WebApp?.HapticFeedback;
      if (!h) return;
      if (type === 'impact') h.impactOccurred(style);
      else if (type === 'notification') h.notificationOccurred(style);
    } catch (e) {}
  }

  function syncStakeUI() {
    const disp = document.getElementById('cf-stake-display');
    if (disp) disp.textContent = `${currentStake} 🪙`;
    const input = document.getElementById('cf-custom-stake-input');
    if (input && document.activeElement !== input) {
      input.value = currentStake > 0 ? currentStake : '';
    }
    const btns = containerEl?.querySelectorAll('.cf-chip-btn');
    btns?.forEach(b => {
      const v = parseInt(b.textContent, 10);
      if (v === currentStake) {
        b.className = 'cf-chip-btn px-2.5 py-1.5 rounded-xl text-xs font-black border bg-amber-500 text-black border-amber-500 shadow';
      } else {
        b.className = 'cf-chip-btn px-2.5 py-1.5 rounded-xl text-xs font-black border bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 border-slate-300 dark:border-slate-600';
      }
    });
  }

  function setStake(val) {
    if (isFlipping) return;
    currentStake = Math.min(Math.max(1, val), userCoins || 1);
    syncStakeUI();
  }

  function setCustomStake(val, isChange = false) {
    if (isFlipping) return;
    let num = parseInt(val, 10);
    if (isNaN(num) || num < 1) num = isChange ? 1 : 0;
    if (userCoins > 0 && num > userCoins) num = userCoins;
    currentStake = num;
    syncStakeUI();
  }

  function setAllIn() {
    if (isFlipping) return;
    currentStake = Math.max(1, userCoins);
    syncStakeUI();
  }

  function setChoice(choice) {
    if (isFlipping) return;
    selectedChoice = choice;
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

    let statusText = 'Выберите сторону (Орёл или Решка) и бросьте монетку';
    let statusBg = 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700';
    if (isFlipping) {
      statusText = '🪙 Монетка в воздухе...';
      statusBg = 'bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border-amber-300/40';
    } else if (lastResult) {
      if (lastResult.status === 'win') {
        statusText = `🎉 Победа! Выпал ${lastResult.outcome_name}! Выигрыш: +${lastResult.payout} 🪙`;
        statusBg = 'bg-emerald-100 dark:bg-emerald-950/70 text-emerald-800 dark:text-emerald-300 border-emerald-400';
      } else {
        statusText = `Выпала ${lastResult.outcome_name}. Ставка не сыграла (-${lastResult.stake} 🪙)`;
        statusBg = 'bg-rose-100 dark:bg-rose-950/70 text-rose-800 dark:text-rose-300 border-rose-300';
      }
    }

    return `
      <div class="space-y-3 max-w-md mx-auto">
        <!-- Шапка -->
        <div class="flex items-center justify-between px-1">
          <div class="flex items-center gap-1.5 font-black text-sm text-slate-900 dark:text-white">
            <span>🪙</span> <span>Орёл и Решка</span>
          </div>
          <div class="text-xs font-black px-2.5 py-1 rounded-xl bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border border-amber-300/40">
            🪙 ${userCoins} монет
          </div>
        </div>

        <!-- 3D Монетка -->
        <div class="py-4 bg-gradient-to-b from-slate-900 to-slate-950 rounded-3xl border border-slate-800 shadow-xl flex items-center justify-center">
          <div class="cf-coin-wrap">
            <div id="cf-coin" class="cf-coin" style="transform: rotateY(${coinSide === 'tails' ? 180 : 0}deg);">
              <div class="cf-side cf-heads">
                <span class="text-4xl">🦅</span>
                <span class="text-[11px] font-black tracking-wider mt-1">ОРЁЛ</span>
              </div>
              <div class="cf-side cf-tails">
                <span class="text-4xl">👑</span>
                <span class="text-[11px] font-black tracking-wider mt-1">РЕШКА</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Статус раунда -->
        <div class="py-2 px-3 rounded-xl text-center text-xs font-bold ${statusBg} border shadow-sm">
          ${statusText}
        </div>

        <!-- Выбор стороны -->
        <div class="grid grid-cols-2 gap-2">
          <button 
            type="button" 
            onclick="window.COINFLIP.setChoice('heads')" 
            ${isFlipping ? 'disabled' : ''}
            class="p-3 rounded-2xl border-2 transition-all flex flex-col items-center gap-1 ${selectedChoice === 'heads' ? 'border-amber-500 bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-300 shadow-md scale-[1.02]' : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300'}"
          >
            <span class="text-3xl">🦅</span>
            <span class="font-black text-xs">Орёл (x2.0)</span>
            ${selectedChoice === 'heads' ? '<span class="text-[10px] font-black text-amber-500">✓ Выбрано</span>' : ''}
          </button>

          <button 
            type="button" 
            onclick="window.COINFLIP.setChoice('tails')" 
            ${isFlipping ? 'disabled' : ''}
            class="p-3 rounded-2xl border-2 transition-all flex flex-col items-center gap-1 ${selectedChoice === 'tails' ? 'border-amber-500 bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-300 shadow-md scale-[1.02]' : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300'}"
          >
            <span class="text-3xl">👑</span>
            <span class="font-black text-xs">Решка (x2.0)</span>
            ${selectedChoice === 'tails' ? '<span class="text-[10px] font-black text-amber-500">✓ Выбрано</span>' : ''}
          </button>
        </div>

        <!-- Выбор ставки -->
        <div class="p-3 bg-white dark:bg-slate-800 rounded-2xl border border-slate-200 dark:border-slate-700 space-y-2.5">
          <div class="flex items-center justify-between text-xs font-bold text-slate-600 dark:text-slate-300">
            <span>Размер ставки:</span>
            <span class="text-amber-600 dark:text-amber-400 font-black text-sm" id="cf-stake-display">${currentStake} 🪙</span>
          </div>

          <div class="flex items-center gap-1 flex-wrap">
            ${[10, 25, 50, 100, 250].map(v => `
              <button type="button" onclick="window.COINFLIP.setStake(${v})" class="cf-chip-btn px-2.5 py-1.5 rounded-xl text-xs font-black border ${currentStake === v ? 'bg-amber-500 text-black border-amber-500 shadow' : 'bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 border-slate-300 dark:border-slate-600'}">
                ${v}
              </button>
            `).join('')}
          </div>

          <div class="flex items-center gap-2">
            <input 
              type="number" 
              id="cf-custom-stake-input" 
              class="w-full text-center font-black text-sm py-1.5 px-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-white outline-none focus:border-amber-500" 
              placeholder="Своя ставка..." 
              min="1" 
              max="${userCoins}" 
              value="${currentStake > 0 ? currentStake : ''}" 
              oninput="window.COINFLIP.setCustomStake(this.value)" 
              onchange="window.COINFLIP.setCustomStake(this.value, true)"
              ${isFlipping ? 'disabled' : ''}
            />
            <button type="button" onclick="window.COINFLIP.setAllIn()" ${isFlipping ? 'disabled' : ''} class="px-3 py-1.5 rounded-xl border border-amber-400/60 bg-amber-500/10 text-amber-500 font-extrabold text-xs shrink-0">
              🔥 Ва-банк
            </button>
          </div>
        </div>

        <!-- Кнопка броска -->
        <button onclick="window.COINFLIP.flip()" ${isFlipping || currentStake <= 0 || currentStake > userCoins ? 'disabled' : ''} class="w-full py-3.5 rounded-2xl bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 disabled:opacity-50 text-slate-950 font-black text-base shadow-lg transition-all flex items-center justify-center gap-2">
          <span>🪙</span> <span>${isFlipping ? 'Монетка летит...' : `Бросить монетку! (${currentStake} 🪙)`}</span>
        </button>
      </div>
    `;
  }

  function render() {
    if (!containerEl) return;
    containerEl.innerHTML = renderHTML();
  }

  async function flip() {
    if (isFlipping || currentStake <= 0 || currentStake > userCoins) return;

    isFlipping = true;
    render();
    triggerHaptic('impact', 'medium');

    try {
      const { ok, data } = await apiCall('/api/coinflip/flip', { stake: currentStake, choice: selectedChoice });
      if (!ok) {
        isFlipping = false;
        alert(data.detail || 'Ошибка броска монетки');
        render();
        return;
      }

      // 3D анимация вращения: несколько полных оборотов + угол нужной стороны
      const coinEl = document.getElementById('cf-coin');
      const extraSpins = 5 * 360; // 5 полных оборотов
      const targetDeg = extraSpins + (data.outcome === 'tails' ? 180 : 0);
      if (coinEl) {
        coinEl.style.transition = 'transform 2.2s cubic-bezier(0.15, 0.9, 0.3, 1.05)';
        coinEl.style.transform = `rotateY(${targetDeg}deg)`;
      }

      setTimeout(() => {
        isFlipping = false;
        lastResult = data;
        coinSide = data.outcome;
        userCoins = data.coins;
        if (window.currentUser) window.currentUser.coins = userCoins;
        if (data.status === 'win') triggerHaptic('notification', 'success');
        else triggerHaptic('impact', 'light');
        render();
      }, 2300);

    } catch (e) {
      isFlipping = false;
      alert(e.message || 'Ошибка соединения');
      render();
    }
  }

  async function syncState() {
    try {
      const { ok, status, data } = await apiCall('/api/coinflip/state');
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
    containerEl = el || document.getElementById('coinflip-root');
    injectCSS();
    if (window.currentUser) {
      isCurrencyActive = Boolean(window.currentUser.currency_ecosystem_enabled);
      userCoins = Number(window.currentUser.coins || 0);
    }
    syncState();
  }

  function cleanup() {
    containerEl = null;
    isFlipping = false;
  }

  window.COINFLIP = {
    init,
    cleanup,
    flip,
    setChoice,
    setStake,
    setCustomStake,
    setAllIn,
  };
})();
