/**
 * blackjack.js — Модуль игры «Блэкджек (21 очко)» на монеты для Telegram Mini App.
 * Экспортирует window.BLACKJACK = { init, cleanup, deal, hit, stand, doubleDown }
 */
(function () {
  'use strict';

  let containerEl = null;
  let currentGameState = null;
  let selectedStake = 25;
  let userCoins = 0;
  let isCurrencyActive = true;
  let isLoading = false;

  const SUIT_NAME_MAP = { '♠': 'spades', '♣': 'clubs', '♥': 'hearts', '♦': 'diamonds' };

  function renderCardHTML(card) {
    if (!card) return '';
    if (card.hidden) {
      return `
        <div class="bj-card bj-card--back">
          <img src="/static/img/cards/back.svg" class="bj-card__img" alt="Скрытая карта" />
        </div>`;
    }
    const suitName = card.suit_name || SUIT_NAME_MAP[card.suit] || 'spades';
    const rank = card.rank || '';
    const imgSrc = `/static/img/cards/${rank}_${suitName}.png`;
    const svgSrc = `/static/img/cards/${rank}_${suitName}.svg`;
    return `
      <div class="bj-card" data-suit="${card.suit}" data-rank="${rank}">
        <img src="${imgSrc}" onerror="this.onerror=null;this.src='${svgSrc}'" class="bj-card__img" alt="${rank}${card.suit}" />
      </div>`;
  }

  function getStatusBadge(state) {
    if (!state || state.phase === 'betting') {
      return { text: 'Сделайте ставку и начните раздачу', color: 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300' };
    }
    if (state.phase === 'player_turn') {
      return { text: 'Ваш ход: возьмите карту, остановитесь или удвойте', color: 'bg-blue-100 dark:bg-blue-900/50 text-blue-800 dark:text-blue-300' };
    }
    const st = state.status;
    if (st === 'blackjack') return { text: `🎉 Блэкджек! Выигрыш 3:2 (+${state.net_profit} 🪙)`, color: 'bg-amber-100 dark:bg-amber-900/60 text-amber-900 dark:text-amber-200 border-amber-400' };
    if (st === 'player_win') return { text: `🏆 Победа! (+${state.net_profit} 🪙)`, color: 'bg-emerald-100 dark:bg-emerald-900/60 text-emerald-800 dark:text-emerald-200' };
    if (st === 'dealer_bust') return { text: `💥 У дилера перебор! Победа (+${state.net_profit} 🪙)`, color: 'bg-emerald-100 dark:bg-emerald-900/60 text-emerald-800 dark:text-emerald-200' };
    if (st === 'player_bust') return { text: `💀 Перебор! (-${state.stake} 🪙)`, color: 'bg-rose-100 dark:bg-rose-900/60 text-rose-800 dark:text-rose-200' };
    if (st === 'dealer_win') return { text: `Дилер победил (-${state.stake} 🪙)`, color: 'bg-rose-100 dark:bg-rose-900/60 text-rose-800 dark:text-rose-200' };
    if (st === 'push') return { text: `🤝 Ничья (Возврат ставки ${state.stake} 🪙)`, color: 'bg-slate-200 dark:bg-slate-700 text-slate-800 dark:text-slate-200' };
    return { text: 'Раунд завершен', color: 'bg-slate-100 dark:bg-slate-800 text-slate-600' };
  }

  function injectCSS() {
    if (document.getElementById('bj-styles')) return;
    const style = document.createElement('style');
    style.id = 'bj-styles';
    style.textContent = `
      .bj-table { background: radial-gradient(circle at center, #1b4332 0%, #081c15 100%); border-radius: 18px; padding: 14px; color: #fff; box-shadow: inset 0 0 20px rgba(0,0,0,0.6); position: relative; }
      .bj-card { width: 58px; height: 82px; border-radius: 6px; box-shadow: 0 4px 10px rgba(0,0,0,0.45); transition: transform 0.2s; background: #fff; display: inline-flex; align-items: center; justify-content: center; overflow: hidden; flex-shrink: 0; }
      .bj-card__img { width: 100%; height: 100%; object-fit: fill; }
      .bj-hand { display: flex; gap: 8px; justify-content: center; min-height: 86px; align-items: center; flex-wrap: wrap; }
      .bj-btn { font-weight: 800; border-radius: 12px; padding: 10px 14px; transition: all 0.15s; display: inline-flex; align-items: center; justify-content: center; gap: 6px; }
      .bj-btn:active:not(:disabled) { transform: scale(0.96); }
      .bj-btn:disabled { opacity: 0.45; cursor: not-allowed; }
      .bj-chip { padding: 5px 10px; border-radius: 10px; font-weight: 800; font-size: 0.8rem; border: 1.5px solid rgba(255,255,255,0.25); background: rgba(0,0,0,0.35); color: #fff; cursor: pointer; transition: all 0.15s; }
      .bj-chip.active { background: #f59e0b; color: #000; border-color: #f59e0b; box-shadow: 0 0 10px rgba(245,158,11,0.5); }
    `;
    document.head.appendChild(style);
  }

  function triggerHaptic(type) {
    try {
      if (window.Telegram?.WebApp?.HapticFeedback) {
        if (type === 'win') window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
        else if (type === 'loss') window.Telegram.WebApp.HapticFeedback.notificationOccurred('error');
        else window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
      }
    } catch (e) {}
  }

  function renderLockedHTML() {
    return `
      <div class="p-6 text-center space-y-4 bg-white dark:bg-slate-800 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-sm max-w-sm mx-auto my-4">
        <div class="text-4xl">🪙🔒</div>
        <h3 class="text-base font-black text-slate-900 dark:text-white">Игровая экосистема отключена</h3>
        <p class="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
          Чтобы играть в <b>«21 Очко» (Блэкджек)</b> и <b>«Дурак»</b> со ставками на монеты, включите экосистему в настройках Telegram-бота:
        </p>
        <div class="bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 p-2.5 rounded-xl text-xs font-bold text-amber-800 dark:text-amber-300">
          Меню бота → ⚙️ Настройки → 🪙 Игровая экосистема
        </div>
      </div>
    `;
  }

  function renderHTML() {
    if (!isCurrencyActive) return renderLockedHTML();

    const state = currentGameState;
    const isPlaying = state && state.phase === 'player_turn';
    const isDone = state && state.phase === 'done';
    const badge = getStatusBadge(state);

    const dealerCards = (state && state.dealer_cards) ? state.dealer_cards.map(renderCardHTML).join('') : '<div class="text-xs text-emerald-200/60">Карты еще не розданы</div>';
    const playerCards = (state && state.player_cards) ? state.player_cards.map(renderCardHTML).join('') : '<div class="text-xs text-emerald-200/60">Карты еще не розданы</div>';

    const dealerScoreText = (state && state.dealer_score) ? `${state.dealer_score} ${state.dealer_is_soft ? '(софт)' : ''}` : '0';
    const playerScoreText = (state && state.player_score) ? `${state.player_score} ${state.player_is_soft ? '(софт)' : ''}` : '0';

    const canDouble = isPlaying && state.can_double && userCoins >= state.stake;

    return `
      <div class="space-y-3 max-w-md mx-auto">
        <!-- Верхняя плашка баланса и названия -->
        <div class="flex items-center justify-between px-1">
          <div class="flex items-center gap-1.5 font-black text-sm text-slate-900 dark:text-white">
            <span>🃏</span> <span>21 Очко (Блэкджек)</span>
          </div>
          <div class="text-xs font-black px-2.5 py-1 rounded-xl bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border border-amber-300/40">
            🪙 ${userCoins} монет
          </div>
        </div>

        <!-- Переключатель режима: Соло / Общий стол -->
        <div class="grid grid-cols-2 gap-1.5 p-1 bg-slate-100 dark:bg-slate-800/90 rounded-xl border border-slate-200 dark:border-slate-700">
          <button type="button" class="py-1 px-2 rounded-lg text-xs font-black bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm">
            🤖 Соло (Дилер)
          </button>
          <button type="button" onclick="window.BLACKJACK?.openTableLobby ? window.BLACKJACK.openTableLobby() : (window.BLACKJACK_TABLE?.openLobby && window.BLACKJACK_TABLE.openLobby(document.getElementById('blackjack-root')))" class="py-1 px-2 rounded-lg text-xs font-extrabold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-colors flex items-center justify-center gap-1">
            <span>👥 Общий стол</span>
            <span class="px-1 py-0.2 rounded bg-amber-500/20 text-amber-500 text-[10px] font-black">NEW</span>
          </button>
        </div>

        <!-- Игровой стол сукно -->
        <div class="bj-table space-y-3 text-center">
          <!-- Дилер -->
          <div>
            <div class="flex items-center justify-center gap-2 mb-1.5 text-xs font-bold text-emerald-200">
              <span>🤵 Дилер</span>
              <span class="px-2 py-0.5 rounded-md bg-black/40 text-amber-300 font-mono text-[11px]">${dealerScoreText}</span>
            </div>
            <div class="bj-hand" id="bj-dealer-hand">${dealerCards}</div>
          </div>

          <!-- Центральный статус -->
          <div class="py-1 px-3 rounded-xl text-xs font-bold ${badge.color} border transition-all">
            ${badge.text}
          </div>

          <!-- Игрок -->
          <div>
            <div class="bj-hand mb-1.5" id="bj-player-hand">${playerCards}</div>
            <div class="flex items-center justify-center gap-2 text-xs font-bold text-emerald-200">
              <span>👤 Вы</span>
              <span class="px-2 py-0.5 rounded-md bg-black/40 text-amber-300 font-mono text-[11px]">${playerScoreText}</span>
              ${state && state.stake ? `<span class="text-[11px] text-amber-300/90 font-mono ml-1">Ставка: ${state.stake} 🪙</span>` : ''}
            </div>
          </div>
        </div>

        <!-- Кнопки действий игрока -->
        ${isPlaying ? `
          <div class="grid grid-cols-3 gap-2">
            <button onclick="window.BLACKJACK.hit()" ${isLoading ? 'disabled' : ''} class="bj-btn bg-blue-600 hover:bg-blue-700 text-white text-xs shadow-md">
              <span>➕</span> <span>Взять</span>
            </button>
            <button onclick="window.BLACKJACK.stand()" ${isLoading ? 'disabled' : ''} class="bj-btn bg-amber-600 hover:bg-amber-700 text-white text-xs shadow-md">
              <span>🛑</span> <span>Хватит</span>
            </button>
            <button onclick="window.BLACKJACK.doubleDown()" ${(!canDouble || isLoading) ? 'disabled' : ''} class="bj-btn bg-purple-600 hover:bg-purple-700 text-white text-xs shadow-md" title="${!canDouble ? 'Доступно только на 2 картах при балансе' : 'Удвоить ставку и взять 1 карту'}">
              <span>⚡</span> <span>Удвоить</span>
            </button>
          </div>
        ` : `
          <!-- Выбор ставки и кнопка раздачи -->
          <div class="p-3 bg-white dark:bg-slate-800/90 rounded-2xl border border-slate-200 dark:border-slate-700 space-y-2.5">
            <div class="flex items-center justify-between text-xs font-bold text-slate-600 dark:text-slate-300">
              <span>Ставка:</span>
              <span class="text-amber-600 dark:text-amber-400 font-extrabold text-sm" id="bj-stake-display">${selectedStake} 🪙</span>
            </div>

            <!-- Чипы -->
            <div class="flex gap-1.5 justify-center flex-wrap">
              ${[10, 25, 50, 100, 250].map(v => `
                <button type="button" onclick="window.BLACKJACK.setStake(${v})" class="bj-chip ${selectedStake === v ? 'active' : ''}">${v}</button>
              `).join('')}
            </div>

            <!-- Произвольная ставка и Ва-банк -->
            <div class="flex items-center gap-2">
              <div class="relative flex-1">
                <input 
                  type="number" 
                  id="bj-custom-stake-input" 
                  class="w-full text-center font-black text-sm py-1.5 px-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-white outline-none focus:border-amber-500" 
                  placeholder="Своя ставка..." 
                  min="1" 
                  max="${userCoins}" 
                  value="${selectedStake > 0 ? selectedStake : ''}" 
                  oninput="window.BLACKJACK.setCustomStake(this.value)"
                  onchange="window.BLACKJACK.setCustomStake(this.value, true)"
                />
              </div>
              <button type="button" onclick="window.BLACKJACK.setAllIn()" class="bj-chip text-amber-500 font-black py-1.5 px-3" title="Поставить все монеты">
                🔥 Ва-банк
              </button>
            </div>

            <button id="bj-deal-btn" onclick="window.BLACKJACK.deal()" ${userCoins < selectedStake || selectedStake <= 0 || isLoading ? 'disabled' : ''} class="bj-btn w-full bg-emerald-600 hover:bg-emerald-700 text-white text-sm shadow-md py-2.5">
              <span>▶️</span> <span class="bj-deal-text">${isDone ? 'Сыграть снова' : 'Раздать карты'} (${selectedStake} 🪙)</span>
            </button>
          </div>
        `}
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

  async function syncState() {
    try {
      const { ok, status, data } = await apiCall('/api/blackjack/state');
      if (status === 400 && data.detail && data.detail.includes('экосистем')) {
        isCurrencyActive = false;
      } else if (ok) {
        currentGameState = data.state;
        if (typeof data.coins === 'number') {
          userCoins = data.coins;
          if (window.currentUser) window.currentUser.coins = userCoins;
        }
        isCurrencyActive = true;
      }
    } catch (e) {}
    render();
  }

  async function performAction(endpoint, body = {}) {
    if (isLoading) return;
    isLoading = true;
    triggerHaptic('impact');
    try {
      const { ok, data } = await apiCall(endpoint, body);
      if (!ok) {
        alert(data.detail || 'Ошибка выполнения действия');
      } else {
        currentGameState = data.state;
        if (typeof data.coins === 'number') {
          userCoins = data.coins;
          if (window.currentUser) window.currentUser.coins = userCoins;
        }
        const st = data.state?.status;
        if (['blackjack', 'player_win', 'dealer_bust'].includes(st)) triggerHaptic('win');
        else if (['player_bust', 'dealer_win'].includes(st)) triggerHaptic('loss');
      }
    } catch (e) {
      alert(e.message || 'Ошибка соединения с сервером');
    } finally {
      isLoading = false;
      render();
    }
  }

  const deal = async () => { if (userCoins >= selectedStake && selectedStake > 0) await performAction('/api/blackjack/deal', { stake: selectedStake }); };
  const hit = () => performAction('/api/blackjack/hit');
  const stand = () => performAction('/api/blackjack/stand');
  const doubleDown = () => performAction('/api/blackjack/double');

  function syncStakeUI() {
    const disp = document.getElementById('bj-stake-display');
    if (disp) disp.textContent = `${selectedStake} 🪙`;
    const input = document.getElementById('bj-custom-stake-input');
    if (input && document.activeElement !== input) input.value = selectedStake > 0 ? selectedStake : '';
    const chips = containerEl?.querySelectorAll('.bj-chip');
    chips?.forEach(c => {
      const v = parseInt(c.textContent, 10);
      if (v === selectedStake) c.classList.add('active');
      else c.classList.remove('active');
    });
    const dealBtn = document.getElementById('bj-deal-btn');
    if (dealBtn) {
      dealBtn.disabled = userCoins < selectedStake || selectedStake <= 0 || isLoading;
      const textSpan = dealBtn.querySelector('.bj-deal-text');
      const isDone = currentGameState && currentGameState.phase === 'done';
      if (textSpan) textSpan.textContent = `${isDone ? 'Сыграть снова' : 'Раздать карты'} (${selectedStake} 🪙)`;
    }
  }

  function setStake(amount) { selectedStake = Math.min(Math.max(1, amount), userCoins || 1); syncStakeUI(); }
  function setCustomStake(amount, isChange = false) {
    let num = parseInt(amount, 10);
    if (isNaN(num) || num < 1) num = isChange ? 1 : 0;
    if (userCoins > 0 && num > userCoins) num = userCoins;
    selectedStake = num;
    syncStakeUI();
  }
  function setAllIn() { selectedStake = Math.max(1, userCoins); syncStakeUI(); }

  function init(el) {
    containerEl = el || document.getElementById('blackjack-root');
    injectCSS();
    if (window.currentUser) {
      isCurrencyActive = Boolean(window.currentUser.currency_ecosystem_enabled);
      userCoins = Number(window.currentUser.coins || 0);
      if (selectedStake > userCoins && userCoins > 0) selectedStake = Math.min(25, userCoins);
    }
    syncState();
  }

  function openTableLobby() {
    const el = containerEl || document.getElementById('blackjack-root');
    if (window.BLACKJACK_TABLE?.openLobby) {
      window.BLACKJACK_TABLE.openLobby(el);
      return;
    }
    const s = document.createElement('script');
    s.src = '/static/js/blackjack/blackjack_table.js?v=20260918_table_fix1';
    s.onload = () => {
      if (window.BLACKJACK_TABLE?.openLobby) window.BLACKJACK_TABLE.openLobby(el);
    };
    document.head.appendChild(s);
  }

  function cleanup() {
    containerEl = null;
    currentGameState = null;
  }

  window.BLACKJACK = {
    init: init,
    cleanup: cleanup,
    render: render,
    deal: deal,
    hit: hit,
    stand: stand,
    doubleDown: doubleDown,
    setStake: setStake,
    setCustomStake: setCustomStake,
    setAllIn: setAllIn,
    openTableLobby: openTableLobby,
  };
})();
