/**
 * blackjack_table.js — Общий стол казино в Блэкджек на 2–4 игрока против Дилера.
 * Экспортирует window.BLACKJACK_TABLE = { init, cleanup, openTable, createTable, exitToMenu }
 */
(function () {
  'use strict';

  let containerEl = null;
  let currentTableState = null;
  let currentTableId = null;
  let ws = null;
  let pingTimer = null;
  let selectedStake = 25;
  let userCoins = 0;
  let isActionPending = false;

  const SUIT_NAME_MAP = { '♠': 'spades', '♣': 'clubs', '♥': 'hearts', '♦': 'diamonds' };

  function getUserId() {
    if (window.currentUser?.tg_id && window.currentUser.tg_id > 0) return parseInt(window.currentUser.tg_id, 10);
    if (window.currentUser?.id && window.currentUser.id > 0) return parseInt(window.currentUser.id, 10);
    try {
      const p = new URLSearchParams(window.location.search);
      const u = p.get('tg_user_id') || p.get('uid') || p.get('user_id');
      if (u) return parseInt(u, 10);
      if (window.Telegram?.WebApp?.initDataUnsafe?.user?.id) return parseInt(window.Telegram.WebApp.initDataUnsafe.user.id, 10);
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
    try { data = await res.json(); } catch (e) {
      data = { detail: `HTTP ${res.status}: ${res.statusText || 'Ошибка'}` };
    }
    return { ok: res.ok, status: res.status, data };
  }

  function renderCardHTML(card) {
    if (!card) return '';
    if (card.hidden) {
      return `<div class="bj-card bj-card--back"><img src="/static/img/cards/back.svg" class="bj-card__img" alt="?" /></div>`;
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

  function connectWS(tableId) {
    disconnectWS();
    const uid = getUserId();
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host || 'localhost';
    const url = `${proto}//${host}/api/blackjack/ws/${tableId}/${uid}`;

    try {
      ws = new WebSocket(url);
      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);
          if (msg.type === 'table_state' && msg.state) {
            currentTableState = msg.state;
            render();
          }
        } catch (e) {}
      };
      pingTimer = setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN) ws.send('ping');
      }, 25000);
    } catch (e) {
      console.warn('Blackjack table WS failed:', e);
    }
  }

  function disconnectWS() {
    if (pingTimer) { clearInterval(pingTimer); pingTimer = null; }
    if (ws) {
      try { ws.close(); } catch (e) {}
      ws = null;
    }
  }

  function setStake(amount) {
    selectedStake = Math.max(1, parseInt(amount, 10) || 10);
    render();
  }

  function render() {
    if (!containerEl) return;
    const s = currentTableState;
    if (!s) {
      containerEl.innerHTML = `<div class="p-6 text-center text-sm font-bold text-slate-500">Загрузка стола...</div>`;
      return;
    }

    const uid = getUserId();
    const myPlayer = s.players.find(p => Number(p.user_id) === Number(uid));
    const isMyTurn = s.phase === 'player_turns' && Number(s.active_user_id) === Number(uid);
    const isBetting = s.phase === 'lobby' || s.phase === 'betting' || s.phase === 'settled';

    // Карты дилера
    const dealerCards = s.dealer_cards?.length
      ? s.dealer_cards.map(renderCardHTML).join('')
      : '<span class="text-xs text-emerald-200/60">Карты не розданы</span>';
    const dealerScore = s.dealer_score || 0;

    // Сетка игроков (бокса)
    const playersHTML = s.players.map(p => {
      const isMe = Number(p.user_id) === Number(uid);
      const isTurn = Number(s.active_user_id) === Number(p.user_id);
      const badges = {
        acting: '<span class="px-1.5 py-0.5 rounded bg-amber-500 text-black font-black text-[10px] animate-pulse">Ходит...</span>',
        bust: '<span class="px-1.5 py-0.5 rounded bg-rose-600 text-white font-black text-[10px]">Перебор 💥</span>',
        stand: '<span class="px-1.5 py-0.5 rounded bg-blue-600 text-white font-black text-[10px]">Стоп ✋</span>',
        double: '<span class="px-1.5 py-0.5 rounded bg-purple-600 text-white font-black text-[10px]">Дабл ⚡</span>',
        blackjack: '<span class="px-1.5 py-0.5 rounded bg-amber-400 text-black font-black text-[10px]">21! 🎉</span>',
        win: `<span class="px-1.5 py-0.5 rounded bg-emerald-500 text-white font-black text-[10px]">+${p.payout} 🪙</span>`,
        dealer_win: '<span class="px-1.5 py-0.5 rounded bg-rose-500 text-white font-black text-[10px]">0 🪙</span>',
        push: '<span class="px-1.5 py-0.5 rounded bg-slate-500 text-white font-black text-[10px]">Ничья</span>',
        bet_placed: `<span class="px-1.5 py-0.5 rounded bg-emerald-600/80 text-white font-bold text-[10px]">Ставка: ${p.stake} 🪙</span>`,
      };
      const statusBadge = badges[p.status] || '';

      const borderClass = isTurn ? 'border-2 border-amber-400 shadow-md shadow-amber-400/20' : (isMe ? 'border border-blue-400/60' : 'border border-slate-700');
      const cardsHTML = p.cards?.length ? p.cards.map(renderCardHTML).join('') : '<span class="text-[10px] text-slate-400">Нет карт</span>';

      return `
        <div class="p-2.5 rounded-2xl bg-slate-900/80 ${borderClass} space-y-1.5 text-center flex flex-col items-center">
          <div class="flex items-center justify-between w-full text-[11px] font-bold">
            <span class="truncate max-w-[100px] text-slate-200">${p.name} ${isMe ? '(Вы)' : ''}</span>
            <span class="px-1.5 py-0.2 rounded bg-black/50 text-amber-300 font-mono text-[10px]">${p.score || 0}</span>
          </div>
          <div class="flex gap-1 justify-center min-h-[50px] items-center flex-wrap">${cardsHTML}</div>
          <div class="flex items-center justify-center gap-1">${statusBadge}</div>
        </div>`;
    }).join('');

    // Кнопки управления
    let controlsHTML = '';
    if (isBetting) {
      const myBetPlaced = myPlayer && myPlayer.status === 'bet_placed';
      controlsHTML = `
        <div class="space-y-2">
          ${!myBetPlaced ? `
            <div class="flex items-center justify-center gap-1 flex-wrap">
              ${[10, 25, 50, 100, 250].map(v => `
                <button type="button" onclick="window.BLACKJACK_TABLE.setStake(${v})" class="px-2 py-1 rounded-xl text-xs font-black border ${selectedStake === v ? 'bg-amber-500 text-black border-amber-500' : 'bg-slate-800 text-slate-300 border-slate-700'}">${v}</button>
              `).join('')}
            </div>
            <button onclick="window.BLACKJACK_TABLE.placeBet()" class="w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 font-black text-white text-xs shadow">
              💰 Поставить ${selectedStake} 🪙
            </button>
          ` : `
            <div class="text-xs font-bold text-emerald-400">✅ Ставка принята (${myPlayer.stake} 🪙). Ожидание других игроков...</div>
            <button onclick="window.BLACKJACK_TABLE.startDeal()" class="w-full py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 font-black text-black text-xs shadow">
              🃏 Начать раздачу!
            </button>
          `}
        </div>`;
    } else if (isMyTurn) {
      const canDouble = myPlayer && myPlayer.can_double;
      controlsHTML = `
        <div class="grid grid-cols-2 gap-2">
          <button onclick="window.BLACKJACK_TABLE.doAction('hit')" class="py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 font-black text-white text-xs shadow">
            ➕ Еще (Hit)
          </button>
          <button onclick="window.BLACKJACK_TABLE.doAction('stand')" class="py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 font-black text-white text-xs shadow">
            ✋ Хватит (Stand)
          </button>
          ${canDouble ? `
            <button onclick="window.BLACKJACK_TABLE.doAction('double')" class="col-span-2 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 font-black text-white text-xs shadow">
              ⚡ Удвоить ставку (Double)
            </button>
          ` : ''}
        </div>`;
    } else if (s.phase === 'player_turns') {
      controlsHTML = `<div class="text-xs font-bold text-amber-300 text-center py-2 animate-pulse">⏳ Ходит другой игрок...</div>`;
    } else if (s.phase === 'dealer_turn') {
      controlsHTML = `<div class="text-xs font-bold text-amber-400 text-center py-2">🤵 Дилер берет карты...</div>`;
    }

    containerEl.innerHTML = `
      <div class="space-y-3 max-w-md mx-auto">
        <!-- Шапка стола -->
        <div class="flex items-center justify-between px-1">
          <div class="flex items-center gap-2">
            <button onclick="window.BLACKJACK_TABLE.exitToMenu()" class="text-xs px-2 py-1 rounded-lg bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-bold">
              ✕ Выйти
            </button>
            <span class="text-xs font-black text-slate-800 dark:text-white">Стол #${s.table_id}</span>
          </div>
          <div class="text-xs font-black px-2.5 py-1 rounded-xl bg-amber-100 dark:bg-amber-950/60 text-amber-800 dark:text-amber-300 border border-amber-300/40">
            🪙 ${userCoins} монет
          </div>
        </div>

        <!-- Зеленое сукно стола -->
        <div class="bj-table space-y-3 text-center">
          <!-- Дилер -->
          <div>
            <div class="flex items-center justify-center gap-2 mb-1 text-xs font-bold text-emerald-200">
              <span>🤵 Дилер</span>
              <span class="px-2 py-0.5 rounded-md bg-black/40 text-amber-300 font-mono text-[11px]">${dealerScore}</span>
            </div>
            <div class="flex gap-1 justify-center min-h-[70px] items-center flex-wrap">${dealerCards}</div>
          </div>

          <!-- Сетка мест за столом -->
          <div class="grid grid-cols-${s.players.length > 2 ? '2' : s.players.length} gap-2 pt-2 border-t border-emerald-900/60">
            ${playersHTML}
          </div>
        </div>

        <!-- Панель управления игрока -->
        <div class="p-3 bg-white dark:bg-slate-800 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-sm">
          ${controlsHTML}
        </div>
      </div>`;
  }

  async function openTable(tableId, container) {
    if (container) containerEl = container;
    if (!containerEl) containerEl = document.getElementById('blackjack-root');
    currentTableId = tableId;
    userCoins = window.currentUser?.coins || 0;
    if (containerEl) {
      containerEl.innerHTML = `<div class="p-6 text-center text-sm font-bold text-slate-500 animate-pulse">Загрузка стола #${tableId}...</div>`;
    }

    const { ok, data } = await apiCall(`/api/blackjack/table/${tableId}`);
    if (!ok) {
      alert(data.detail || 'Не удалось загрузить стол');
      exitToMenu();
      return;
    }
    currentTableState = data.state;
    connectWS(tableId);
    render();
  }

  async function createTable(maxPlayers = 4, minStake = 10, container) {
    if (container) containerEl = container;
    const { ok, data } = await apiCall('/api/blackjack/table/new', { max_players: maxPlayers, min_stake: minStake });
    if (!ok) return alert(data.detail || 'Ошибка создания стола');
    openTable(data.table_id, containerEl);
  }

  async function placeBet() {
    if (isActionPending || !currentTableId) return;
    isActionPending = true;
    try {
      const { ok, data } = await apiCall('/api/blackjack/table/bet', { table_id: currentTableId, stake: selectedStake });
      if (!ok) alert(data.detail || 'Ошибка ставки');
      else userCoins = Math.max(0, userCoins - selectedStake);
    } finally { isActionPending = false; }
  }

  async function startDeal() {
    if (isActionPending || !currentTableId) return;
    isActionPending = true;
    try {
      const { ok, data } = await apiCall('/api/blackjack/table/deal', { table_id: currentTableId });
      if (!ok) alert(data.detail || 'Не удалось начать раздачу');
    } finally { isActionPending = false; }
  }

  async function doAction(act) {
    if (isActionPending || !currentTableId) return;
    isActionPending = true;
    try {
      const { ok, data } = await apiCall('/api/blackjack/table/action', { table_id: currentTableId, action: act });
      if (!ok) alert(data.detail || 'Ошибка хода');
    } finally { isActionPending = false; }
  }

  async function exitToMenu() {
    disconnectWS();
    if (currentTableId) {
      await apiCall('/api/blackjack/table/leave', { table_id: currentTableId });
      currentTableId = null;
    }
    if (window.BLACKJACK?.init && containerEl) window.BLACKJACK.init(containerEl);
  }

  async function joinTable(tableId) {
    const { ok, data } = await apiCall('/api/blackjack/table/join', { table_id: tableId });
    if (!ok) return alert(data.detail || 'Не удалось сесть за стол');
    openTable(tableId, containerEl);
  }

  function joinByCode() {
    const inp = document.getElementById('bj-table-code-input');
    const code = inp?.value?.trim();
    if (!code) return;
    joinTable(code);
  }

  async function openLobby(container) {
    if (container) containerEl = container;
    if (!containerEl) return;
    disconnectWS();

    const { ok, data } = await apiCall('/api/blackjack/tables');
    const tables = (ok && data.tables) ? data.tables : [];

    containerEl.innerHTML = `
      <div class="space-y-3 max-w-md mx-auto">
        <div class="flex items-center justify-between px-1">
          <div class="flex items-center gap-2 font-black text-sm text-slate-900 dark:text-white">
            <span>👥</span> <span>Общий стол казино</span>
          </div>
          <button onclick="window.BLACKJACK_TABLE.exitToMenu()" class="text-xs px-2.5 py-1 rounded-lg bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-bold">
            🔙 В соло
          </button>
        </div>

        <div class="p-4 bg-gradient-to-br from-emerald-900 to-slate-950 rounded-2xl border border-emerald-700/50 text-white space-y-3 shadow-lg">
          <div class="text-xs text-emerald-200/90 leading-relaxed font-semibold">Играйте за одним столом с друзьями против общего Дилера! Все видят карты друг друга в реальном времени.</div>
          <div class="grid grid-cols-2 gap-2 pt-1">
            <button onclick="window.BLACKJACK_TABLE.createTable(2, 10, window.BLACKJACK_TABLE.getContainer())" class="py-2 px-3 rounded-xl bg-amber-500 hover:bg-amber-400 font-black text-slate-950 text-xs shadow">➕ Стол на 2 места</button>
            <button onclick="window.BLACKJACK_TABLE.createTable(4, 10, window.BLACKJACK_TABLE.getContainer())" class="py-2 px-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 font-black text-slate-950 text-xs shadow">➕ Стол на 4 места</button>
          </div>
          <div class="flex gap-1.5 pt-2 border-t border-emerald-800/60">
            <input type="text" id="bj-table-code-input" placeholder="Код стола..." class="w-full text-center text-xs font-bold py-1.5 px-2.5 rounded-xl border border-emerald-700/70 bg-black/40 text-white outline-none focus:border-amber-400 uppercase" />
            <button onclick="window.BLACKJACK_TABLE.joinByCode()" class="px-3 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs shrink-0">Войти</button>
          </div>
        </div>

        <div class="p-3 bg-white dark:bg-slate-800 rounded-2xl border border-slate-200 dark:border-slate-700 space-y-2">
          <div class="text-xs font-black text-slate-700 dark:text-slate-300 flex items-center justify-between">
            <span>Открытые столы</span>
            <button onclick="window.BLACKJACK_TABLE.openLobby(window.BLACKJACK_TABLE.getContainer())" class="text-amber-500 text-[11px] font-bold">🔄 Обновить</button>
          </div>
          <div class="space-y-1.5">
            ${tables.length ? tables.map(t => `
              <div class="flex items-center justify-between p-2 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-xs">
                <div><span class="font-black text-slate-900 dark:text-white">Стол #${t.table_id}</span><span class="text-slate-400 ml-1.5">(${t.players_count}/${t.max_players} мест)</span></div>
                <button onclick="window.BLACKJACK_TABLE.joinTable('${t.table_id}')" class="px-2.5 py-1 rounded-lg bg-emerald-600 text-white font-bold text-[11px]">Сесть за стол</button>
              </div>
            `).join('') : '<div class="text-center py-4 text-xs text-slate-400">Пока нет открытых столов. Создайте первый!</div>'}
          </div>
        </div>
      </div>`;
  }

  function cleanup() {
    disconnectWS();
    containerEl = null;
  }

  window.BLACKJACK_TABLE = {
    init: openTable,
    cleanup,
    openTable,
    createTable,
    joinTable,
    joinByCode,
    openLobby,
    exitToMenu,
    placeBet,
    startDeal,
    doAction,
    setStake,
    getContainer: () => containerEl || document.getElementById('blackjack-root')
  };
})();
