// МОДУЛЬ МИНИ-ИГР ДЛЯ MINI APP — КООРДИНАТОР И РОУТЕР
(function () {
  'use strict';

  let currentGame = "2048"; // 'rpg', '2048', 'tictactoe', 'snake', 'tetris', 'chess', 'casino'
  let currentCasinoSubGame = "durak"; // 'durak', 'blackjack', 'roulette', 'dice', 'slots', 'coinflip', 'leaderboard'
  const CASINO_SUBGAMES = ["durak", "blackjack", "roulette", "dice", "slots", "coinflip", "leaderboard"];
  window.currentGame = currentGame;
  let isTesterUser = false;
  let isCurrencyEnabled = false;
  let userCoins = 0;
  let testerChecked = false;

  async function checkTesterStatus() {
    try {
      const p = new URLSearchParams(window.location.search);
      if (p.has("tester")) isTesterUser = p.get("tester") === "1" || p.get("tester") === "true";
      else if (p.get("role") === "tester" || localStorage.getItem("is_tester") === "1") isTesterUser = true;
      try { localStorage.setItem("is_tester", isTesterUser ? "1" : "0"); } catch (e) {}
    } catch (e) {}

    if (window.currentUser && typeof window.currentUser.is_tester !== "undefined") {
      isTesterUser = Boolean(window.currentUser.is_tester || window.currentUser.role === "admin");
      isCurrencyEnabled = Boolean(window.currentUser.currency_ecosystem_enabled);
      userCoins = Number(window.currentUser.coins || 0);
      testerChecked = true;
      return isTesterUser;
    }

    try {
      const apiObj = window.api || (typeof api !== "undefined" ? api : null);
      const me = (apiObj && typeof apiObj.getMe === "function") ? await apiObj.getMe() : null;
      if (me) {
        window.currentUser = me;
        isTesterUser = Boolean(me.is_tester || me.role === "admin");
        isCurrencyEnabled = Boolean(me.currency_ecosystem_enabled);
        userCoins = Number(me.coins || 0);
        try { localStorage.setItem("is_tester", isTesterUser ? "1" : "0"); } catch (e) {}
      }
    } catch (e) {}
    testerChecked = true;
    return isTesterUser;
  }

  function updateTesterStatus(isTester) {
    const wasTester = isTesterUser;
    isTesterUser = Boolean(isTester);
    testerChecked = true;
    try {
      localStorage.setItem("is_tester", isTesterUser ? "1" : "0");
    } catch (e) {}
    if (isTesterUser && (currentGame === "2048" || !currentGame)) {
      currentGame = "rpg";
    } else if (!isTesterUser && currentGame === "rpg") {
      currentGame = "2048";
    }
    const container = document.getElementById("pane-games");
    if (container && (wasTester !== isTesterUser || (isTesterUser && currentGame === "rpg"))) {
      renderGames();
    }
  }

  async function initGames() {
    const container = document.getElementById("pane-games");
    if (!container) return;
    await checkTesterStatus();
    const p = new URLSearchParams(window.location.search);
    if ((p.get("game") === "rpg" || p.get("tab") === "rpg") && isTesterUser) {
      currentGame = "rpg";
    } else if (isTesterUser && (currentGame === "2048" || !currentGame)) {
      currentGame = "rpg";
    } else if (!isTesterUser && currentGame === "rpg") {
      currentGame = "2048";
    }
    window.currentGame = currentGame;
    renderGames();
  }

  function renderGames() {
    const container = document.getElementById("pane-games");
    if (!container) return;

    window.currentGame = currentGame;

    const baseGames = [
      { id: "2048", icon: "🔢", name: "2048", color: "blue" },
      { id: "tictactoe", icon: "❌⭕", name: "Крестики", color: "blue" },
      { id: "snake", icon: "🐍", name: "Змейка", color: "blue" },
      { id: "tetris", icon: "🧱", name: "Тетрис", color: "blue" },
      { id: "chess", icon: "♟️", name: "Шахматы", color: "blue" },
      { id: "casino", icon: "🎰", name: "Казино", color: "red" },
    ];

    const gamesList = isTesterUser
      ? [{ id: "rpg", icon: "⚔️", name: "natarGRP", color: "amber" }, ...baseGames]
      : baseGames;

    const gameCountLabel = `${gamesList.length} игр${isTesterUser ? ' (⚔️ natarGRP)' : ''}`;

    const tabsHTML = gamesList.map(g => {
      const isCur = currentGame === g.id;
      let activeColor = "text-blue-600 dark:text-blue-400";
      if (g.color === "amber") activeColor = "text-amber-600 dark:text-amber-400";
      else if (g.color === "red") activeColor = "text-red-600 dark:text-red-400";
      const activeClass = isCur
        ? `bg-white dark:bg-slate-700 ${activeColor} shadow-sm`
        : "text-slate-500 dark:text-slate-400 hover:text-slate-700";
      return `
        <button onclick="window.GAMES.switchGame('${g.id}')" class="py-2 px-2.5 rounded-xl transition-all flex items-center justify-center gap-1 shrink-0 ${activeClass}">
          <span>${g.icon}</span>
          <span class="truncate">${g.name}</span>
        </button>
      `;
    }).join("");

    container.innerHTML = `
      <!-- Header -->
      <div class="space-y-3">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-base font-black text-slate-900 dark:text-white tracking-tight flex items-center gap-1.5">
              <span>🎮</span> Мини-игры
            </h2>
            <p class="text-xs text-slate-400 font-medium">Отдохни на перемене с пользой для ума</p>
          </div>
          <span class="text-[11px] font-bold px-2 py-0.5 rounded-lg bg-amber-50 dark:bg-slate-800 text-amber-600 dark:text-amber-400 border border-amber-100 dark:border-slate-700">${gameCountLabel}</span>
        </div>

        <!-- Natbirzha Strategy Banner (Beta testers only) -->
        ${isTesterUser ? `<a href="/app/natbirzha" onclick="window.prepareNatbirzhaNavigation ? window.prepareNatbirzhaNavigation(event) : null" class="block p-3 rounded-2xl bg-gradient-to-r from-blue-600 via-indigo-600 to-emerald-600 text-white shadow-md active:scale-98 transition-all cursor-pointer">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2.5">
              <span class="text-2xl">📈</span>
              <div>
                <div class="text-xs font-black tracking-tight flex items-center gap-1.5">
                  НАТБИРЖА <span class="text-[9px] px-1.5 py-0.5 rounded-md bg-white/20 uppercase font-bold tracking-wider">Beta</span>
                </div>
                <div class="text-[10px] text-blue-100 font-medium">Экономика, заводы, акции и турниры</div>
              </div>
            </div>
            <span class="px-2.5 py-1 rounded-xl bg-white text-blue-700 font-black text-[11px] shrink-0 shadow-sm">Играть ➔</span>
          </div>
        </a>` : ''}

        <!-- Games selector tabs -->
        <div class="gap-1 p-1 rounded-2xl bg-slate-200/70 dark:bg-slate-800/90 text-[10px] font-bold flex overflow-x-auto no-scrollbar">
          ${tabsHTML}
        </div>
      </div>

      <!-- Game Canvas / Container -->
      <div id="game-active-container" class="pt-1">
        ${renderActiveGame()}
      </div>
    `;

    // After DOM update, initialize specific game listeners
    if (currentGame === "rpg" && isTesterUser) window.RPG?.init?.();
    else if (currentGame === "2048") window.GAMES_2048?.init?.();
    else if (currentGame === "tictactoe") window.GAMES_TICTACTOE?.init?.();
    else if (currentGame === "snake") window.GAMES_SNAKE?.init?.();
    else if (currentGame === "tetris") window.GAMES_TETRIS?.init?.();
    else if (currentGame === "chess") window.GAMES_CHESS?.init?.();
    else if (currentGame === "casino") initCasinoSubGame();
  }

  function initCasinoSubGame() {
    const map = {
      durak: initDurak, blackjack: initBlackjack, roulette: initRoulette,
      dice: initDice, slots: initSlots, coinflip: initCoinflip, leaderboard: initCasinoLeaderboard
    };
    map[currentCasinoSubGame]?.();
  }

  function switchGame(gameId) {
    if (CASINO_SUBGAMES.includes(gameId)) {
      currentCasinoSubGame = gameId;
      gameId = "casino";
    }
    if (gameId === "rpg" && !isTesterUser) {
      gameId = "2048";
    }
    cleanupCurrentGame();
    currentGame = gameId;
    window.currentGame = gameId;
    renderGames();
  }

  function switchCasinoSubGame(subGameId) {
    if (!CASINO_SUBGAMES.includes(subGameId)) return;
    cleanupCurrentGame();
    currentCasinoSubGame = subGameId;
    renderGames();
  }

  function cleanupCurrentGame() {
    [window.RPG?.leavePvPRoom, window.RPG?.leaveCoopRoom,
     window.GAMES_2048?.cleanup, window.GAMES_TICTACTOE?.cleanup,
     window.GAMES_SNAKE?.cleanup, window.GAMES_TETRIS?.cleanup,
     window.GAMES_CHESS?.cleanup, window.DURAK?.destroy,
     window.BLACKJACK?.cleanup, window.ROULETTE?.cleanup,
     window.DICE?.cleanup, window.SLOTS?.cleanup, window.COINFLIP?.cleanup].forEach(fn => fn?.());
  }

  function renderActiveGame() {
    if (currentGame === "rpg") {
      if (!isTesterUser) {
        return `
          <div class="p-8 text-center bg-white dark:bg-slate-800 rounded-3xl border border-slate-200 dark:border-slate-700 shadow-sm space-y-3">
            <div class="text-4xl">🔒</div>
            <h3 class="text-base font-bold text-slate-900 dark:text-white">Игра в разработке</h3>
            <p class="text-xs text-slate-500 dark:text-slate-400 max-w-xs mx-auto">
              RPG игра natarGRP на данный момент доступна только для тестировщиков.
            </p>
          </div>
        `;
      }
      return `<div id="rpg-root"></div>`;
    }
    if (currentGame === "2048") return window.GAMES_2048?.renderHTML?.() || "";
    if (currentGame === "tictactoe") return window.GAMES_TICTACTOE?.renderHTML?.() || "";
    if (currentGame === "snake") return window.GAMES_SNAKE?.renderHTML?.() || "";
    if (currentGame === "tetris") return window.GAMES_TETRIS?.renderHTML?.() || "";
    if (currentGame === "chess") return window.GAMES_CHESS?.renderHTML?.() || "";
    if (currentGame === "casino") return renderCasinoHTML();
    return "";
  }

  function renderCasinoHTML() {
    const subTabs = [
      { id: "durak", icon: "🃏", name: "Дурак" },
      { id: "blackjack", icon: "♠️", name: "21 Очко" },
      { id: "roulette", icon: "🎡", name: "Рулетка" },
      { id: "dice", icon: "🎲", name: "Кости" },
      { id: "slots", icon: "🎰", name: "Слоты" },
      { id: "coinflip", icon: "🪙", name: "Монетка" },
      { id: "leaderboard", icon: "🏆", name: "Рейтинг" },
    ];
    const tabsHTML = subTabs.map(st => {
      const isCur = currentCasinoSubGame === st.id;
      const activeClass = isCur
        ? "bg-white dark:bg-slate-700 text-red-600 dark:text-red-400 shadow-sm"
        : "text-slate-500 dark:text-slate-400 hover:text-slate-700";
      return `
        <button onclick="window.GAMES.switchCasinoSubGame('${st.id}')" class="py-1.5 px-2 rounded-xl transition-all flex items-center justify-center gap-1 shrink-0 ${activeClass}">
          <span>${st.icon}</span>
          <span class="truncate">${st.name}</span>
        </button>
      `;
    }).join("");

    const rootMap = {
      durak: 'durak-root', blackjack: 'blackjack-root', roulette: 'roulette-root',
      dice: 'dice-root', slots: 'slots-root', coinflip: 'coinflip-root', leaderboard: 'casino-leaderboard-root'
    };
    const activeRootId = rootMap[currentCasinoSubGame] || 'durak-root';
    const subHtml = `<div id="${activeRootId}" style="min-height:400px;"></div>`;

    return `
      <div class="space-y-3">
        <div class="flex items-center gap-1 p-1 rounded-2xl bg-slate-200/70 dark:bg-slate-800/90 text-[10.5px] font-bold overflow-x-auto no-scrollbar">
          ${tabsHTML}
        </div>
        <div id="casino-active-container">
          ${subHtml}
        </div>
      </div>
    `;
  }

  function loadScript(src, cb) {
    if (typeof document === 'undefined' || typeof document.createElement !== 'function') {
      if (cb) cb();
      return;
    }
    const s = document.createElement('script');
    s.src = src;
    if (cb) s.onload = cb;
    if (document.head) document.head.appendChild(s);
  }

  function initCasinoLeaderboard() { const el = document.getElementById('casino-leaderboard-root'); if (el) window.CASINO_LEADERBOARD ? window.CASINO_LEADERBOARD.init(el) : loadScript('/static/js/casino_leaderboard.js?v=20260916_1', () => window.CASINO_LEADERBOARD?.init(el)); }
  function initRoulette() { const el = document.getElementById('roulette-root'); if (el) window.ROULETTE ? window.ROULETTE.init(el) : loadScript('/static/js/roulette.js?v=20260915_1', () => window.ROULETTE?.init(el)); }
  function initDice() { const el = document.getElementById('dice-root'); if (el) window.DICE ? window.DICE.init(el) : loadScript('/static/js/dice.js?v=20260915_1', () => window.DICE?.init(el)); }
  function initSlots() { const el = document.getElementById('slots-root'); if (el) window.SLOTS ? window.SLOTS.init(el) : loadScript('/static/js/slots.js?v=20260918_70rtp', () => window.SLOTS?.init(el)); }
  function initCoinflip() { const el = document.getElementById('coinflip-root'); if (el) window.COINFLIP ? window.COINFLIP.init(el) : loadScript('/static/js/coinflip.js?v=20260916_1', () => window.COINFLIP?.init(el)); }
  function initBlackjack() {
    const el = document.getElementById('blackjack-root');
    if (!el) return;
    loadScript('/static/js/blackjack/blackjack_table.js?v=20260918_table_fix1', () => {
      if (window.BLACKJACK) window.BLACKJACK.init(el);
      else loadScript('/static/js/blackjack.js?v=20260918_table_fix1', () => window.BLACKJACK?.init(el));
    });
  }

  function initDurak() {
    const el = document.getElementById('durak-root');
    if (!el) return;
    if (window.DURAK) return window.DURAK.init(el);
    const scripts = [
      '/static/js/durak/durak_cards.js?v=20260911_2',
      '/static/js/durak/durak_menu.js?v=20260911_2',
      '/static/js/durak/durak_game.js?v=20260911_2',
      '/static/js/durak.js?v=20260911_2'
    ];
    let idx = 0;
    function loadNext() {
      if (idx >= scripts.length) return window.DURAK?.init(el);
      loadScript(scripts[idx++], loadNext);
    }
    loadNext();
  }

  async function openOnlineRoom(roomId, gameType) {
    if (!roomId) return;
    let target = (gameType || "").toLowerCase().trim();

    if (!target) {
      try {
        if (window.api && typeof window.api.getGameRoom === "function") {
          const room = await window.api.getGameRoom(roomId);
          if (room && room.game_type) target = room.game_type;
        }
      } catch (e) {}
      if (!target) {
        try {
          const dRes = await fetch(`/api/durak/state/${roomId}`);
          if (dRes.ok) target = "durak";
        } catch (e) {}
      }
      if (!target) target = "tictactoe";
    }

    if (target === "rpg_duel") {
      if (!isTesterUser) return;
      switchGame("rpg");
      if (window.RPG?.openPvPRoom) window.RPG.openPvPRoom(roomId);
      return;
    }
    if (target === "rpg_coop") {
      if (!isTesterUser) return;
      switchGame("rpg");
      if (window.RPG?.openCoopRoom) window.RPG.openCoopRoom(roomId);
      return;
    }
    if (target === "chess") {
      switchGame("chess");
      if (window.GAMES_CHESS?.openChessOnlineRoom) return window.GAMES_CHESS.openChessOnlineRoom(roomId);
      return;
    }
    if (target === "durak") {
      currentCasinoSubGame = "durak";
      switchGame("casino");
      if (window.DURAK?.joinRoom) return window.DURAK.joinRoom(roomId);
      return;
    }
    switchGame("tictactoe");
    if (window.GAMES_TICTACTOE && typeof window.GAMES_TICTACTOE.openOnlineRoom === "function") {
      return window.GAMES_TICTACTOE.openOnlineRoom(roomId);
    }
  }

  // ПУБЛИЧНЫЙ ФАСАД window.GAMES (100% совместимость со всеми onclick в HTML)
  window.GAMES = {
    init: initGames,
    switchGame: switchGame,
    switchCasinoSubGame: switchCasinoSubGame,
    render: renderGames,
    getCurrentGame: () => (currentGame === "casino" ? currentCasinoSubGame : currentGame),
    getCasinoSubGame: () => currentCasinoSubGame,
    updateTesterStatus: updateTesterStatus,
    checkTesterStatus: checkTesterStatus,
    cleanup: cleanupCurrentGame,
    initRPG: () => window.RPG?.init?.(),
    reset2048: () => window.GAMES_2048?.reset?.(),
    setTTTMode: (m) => window.GAMES_TICTACTOE?.setTTTMode(m), cellClickTTT: (i) => window.GAMES_TICTACTOE?.cellClickTTT(i),
    resetTTT: () => window.GAMES_TICTACTOE?.resetTTT(), openOnlineRoom: openOnlineRoom,
    inviteClassmate: (id, n) => window.GAMES_TICTACTOE?.inviteClassmate(id, n), makeOnlineMove: (i) => window.GAMES_TICTACTOE?.makeOnlineMove(i),
    requestRematch: () => window.GAMES_TICTACTOE?.requestRematch(), cancelOnlineGame: () => window.GAMES_TICTACTOE?.cancelOnlineGame(),
    leaveOnlineGame: () => window.GAMES_TICTACTOE?.leaveOnlineGame(), backToLobby: () => window.GAMES_TICTACTOE?.backToLobby(),
    filterClassmates: (q) => window.GAMES_TICTACTOE?.filterClassmates(q), refreshClassmates: () => window.GAMES_TICTACTOE?.loadClassmates(),
    startSnakeGame: () => window.GAMES_SNAKE?.startSnakeGame(), setSnakeDir: (d) => window.GAMES_SNAKE?.setSnakeDir(d),
    startTetrisGame: () => window.GAMES_TETRIS?.startTetrisGame(), toggleTetrisPause: () => window.GAMES_TETRIS?.toggleTetrisPause(),
    tetrisMoveLeft: () => window.GAMES_TETRIS?.tetrisMoveLeft(), tetrisMoveRight: () => window.GAMES_TETRIS?.tetrisMoveRight(),
    tetrisRotate: () => window.GAMES_TETRIS?.tetrisRotate(), tetrisSoftDrop: () => window.GAMES_TETRIS?.tetrisSoftDrop(),
    tetrisHardDrop: () => window.GAMES_TETRIS?.tetrisHardDrop(),
    startLocalChessGame: () => window.GAMES_CHESS?.startLocalChessGame(),
    toggleChessAutoRotate: () => window.GAMES_CHESS?.toggleChessAutoRotate(), flipChessBoardManual: () => window.GAMES_CHESS?.flipChessBoardManual(),
    openChessOnlineRoom: (c) => window.GAMES_CHESS?.openChessOnlineRoom(c), inviteChessClassmate: (id, n) => window.GAMES_CHESS?.inviteChessClassmate(id, n),
    chessSquareClick: (r, c) => window.GAMES_CHESS?.chessSquareClick(r, c), choosePromotion: (p) => window.GAMES_CHESS?.choosePromotion(p),
    resignChessGame: () => window.GAMES_CHESS?.resignChessGame(), requestChessRematch: () => window.GAMES_CHESS?.requestChessRematch(),
    cancelChessGame: () => window.GAMES_CHESS?.cancelChessGame(), leaveChessGame: () => window.GAMES_CHESS?.leaveChessGame(),
    backToChessLobby: () => window.GAMES_CHESS?.backToChessLobby(), setChessColor: (c) => window.GAMES_CHESS?.setChessColor(c),
    filterChessClassmates: (q) => window.GAMES_CHESS?.filterChessClassmates(q), refreshChessClassmates: () => window.GAMES_CHESS?.loadChessClassmates(),
    initBlackjack: () => window.BLACKJACK?.init(), initRoulette: () => window.ROULETTE?.init(),
    initDice: () => window.DICE?.init(), initSlots: () => window.SLOTS?.init(),
    initCoinflip: () => window.COINFLIP?.init(), initCasinoLeaderboard: () => window.CASINO_LEADERBOARD?.init()
  };
})();
