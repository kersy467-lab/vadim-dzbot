(function() {
  'use strict';

  function renderGames() {
    if (window.GAMES && typeof window.GAMES.render === 'function') {
      window.GAMES.render();
    }
  }

  // GAME 2: TIC-TAC-TOE (Крестики-нолики с поддержкой Онлайн-дуэли через бота)
  // ==============================================================================
  let tttBoard = ["", "", "", "", "", "", "", "", ""];
  let tttTurn = "X";
  let tttMode = "bot"; // 'bot', 'local', 'online'
  let tttScore = { X: 0, O: 0, draw: 0 };
  let tttGameOver = false;

  // Online Duel State
  let onlineState = "lobby"; // 'lobby', 'loading', 'waiting', 'playing', 'finished', 'rejected'
  let onlineRoomId = null;
  let onlineRoomData = null;
  let onlineOpponentName = "";
  let onlinePollTimer = null;
  let isOnlinePolling = false;
  let classmatesList = [];
  let classmatesFilter = "";
  let isLoadingClassmates = false;

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function renderTicTacToeHTML() {
    return `
      <div class="theme-card rounded-3xl p-4 bg-white dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700 shadow-sm space-y-3.5 max-w-sm mx-auto text-center">
        <!-- Game Mode Selector -->
        <div class="grid grid-cols-3 gap-1 p-1 rounded-xl bg-slate-100 dark:bg-slate-700/80 text-[11px] font-bold">
          <button onclick="window.GAMES.setTTTMode('bot')" class="py-1.5 px-2 rounded-lg transition-all flex items-center justify-center gap-1 ${tttMode === 'bot' ? 'bg-white dark:bg-slate-800 text-blue-600 dark:text-blue-400 shadow-sm' : 'text-slate-500 dark:text-slate-400'}">
            <span>🤖</span><span>С ботом</span>
          </button>
          <button onclick="window.GAMES.setTTTMode('local')" class="py-1.5 px-2 rounded-lg transition-all flex items-center justify-center gap-1 ${tttMode === 'local' ? 'bg-white dark:bg-slate-800 text-blue-600 dark:text-blue-400 shadow-sm' : 'text-slate-500 dark:text-slate-400'}">
            <span>👥</span><span>На двоих</span>
          </button>
          <button onclick="window.GAMES.setTTTMode('online')" class="py-1.5 px-2 rounded-lg transition-all flex items-center justify-center gap-1 ${tttMode === 'online' ? 'bg-white dark:bg-slate-800 text-blue-600 dark:text-blue-400 shadow-sm' : 'text-slate-500 dark:text-slate-400'}">
            <span>🌐</span><span>Онлайн дуэль</span>
          </button>
        </div>

        ${tttMode === 'online' ? renderOnlineTTTHTML() : renderLocalTTTHTML()}
      </div>
    `;
  }

  function renderLocalTTTHTML() {
    return `
      <!-- Turn indicator & Reset -->
      <div class="flex items-center justify-between px-1">
        <div id="ttt-status" class="text-xs font-bold text-slate-500">
          Ход: <span class="text-blue-600 dark:text-blue-400 text-sm font-black">${tttTurn}</span>
        </div>
        <button onclick="window.GAMES.resetTTT()" class="p-1.5 px-2.5 rounded-xl bg-slate-100 dark:bg-slate-700 text-xs font-bold text-slate-500 hover:text-slate-800 dark:hover:text-white flex items-center gap-1 transition-all active:scale-95">
          <span>🔄</span> Заново
        </button>
      </div>

      <!-- 3x3 Board -->
      <div class="grid grid-cols-3 gap-2 w-64 h-64 mx-auto p-2 rounded-2xl bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 select-none">
        ${[0, 1, 2, 3, 4, 5, 6, 7, 8].map(i => `
          <button
            id="ttt-cell-${i}"
            onclick="window.GAMES.cellClickTTT(${i})"
            class="w-full h-full rounded-xl bg-white dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700 text-3xl font-black flex items-center justify-center transition-all hover:bg-blue-50/50 active:scale-95 shadow-sm">
          </button>
        `).join('')}
      </div>

      <!-- Scoreboard -->
      <div class="flex items-center justify-center gap-4 text-xs font-bold pt-1">
        <span class="text-blue-600">Крестики (X): <b id="ttt-score-x">${tttScore.X}</b></span>
        <span class="text-slate-400">Ничьи: <b id="ttt-score-d">${tttScore.draw}</b></span>
        <span class="text-rose-500">Нолики (O): <b id="ttt-score-o">${tttScore.O}</b></span>
      </div>
    `;
  }

  function renderOnlineTTTHTML() {
    if (onlineState === "loading") {
      return `
        <div class="py-12 space-y-3">
          <div class="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p class="text-xs font-bold text-slate-500">Подключение к игре...</p>
        </div>
      `;
    }

    if (onlineState === "waiting") {
      const oppName = onlineOpponentName || (onlineRoomData?.opponent?.name) || "Одноклассник";
      return `
        <div class="py-8 space-y-4">
          <div class="w-16 h-16 rounded-3xl bg-blue-50 dark:bg-blue-950/50 text-blue-600 dark:text-blue-400 flex items-center justify-center text-3xl mx-auto shadow-inner animate-pulse">
            ⏳
          </div>
          <div class="space-y-1">
            <h3 class="text-sm font-black text-slate-800 dark:text-white">Вызов отправлен: ${escapeHtml(oppName)}</h3>
            <p class="text-[11px] text-slate-400 max-w-xs mx-auto">
              Бот отправил однокласснику приглашение с кнопкой входа. Ждем подключения...
            </p>
          </div>
          <button
            onclick="window.GAMES.cancelOnlineGame()"
            class="px-4 py-2 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 font-bold text-xs transition-all active:scale-95">
            ❌ Отменить вызов
          </button>
        </div>
      `;
    }

    if (onlineState === "rejected") {
      return `
        <div class="py-8 space-y-3">
          <div class="text-4xl">❌</div>
          <h3 class="text-sm font-black text-slate-800 dark:text-white">Вызов отклонен или отменен</h3>
          <p class="text-xs text-slate-400">Соперник отклонил приглашение или вызов был отменен.</p>
          <button
            onclick="window.GAMES.backToLobby()"
            class="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow-sm transition-all active:scale-95">
            🔙 Вернуться к списку
          </button>
        </div>
      `;
    }

    if (onlineState === "playing" || onlineState === "finished") {
      const hostName = onlineRoomData?.host?.name || "Хост";
      const oppName = onlineRoomData?.opponent?.name || "Соперник";
      const yourRole = onlineRoomData?.your_role;
      const isYourTurn = onlineRoomData?.is_your_turn;
      const isFinished = onlineState === "finished";

      let statusHTML = "";
      if (isFinished) {
        if (onlineRoomData.winner === "draw") {
          statusHTML = `<div class="p-2.5 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-600 dark:text-amber-400 text-xs font-extrabold">🤝 Боевая ничья!</div>`;
        } else if (onlineRoomData.winner === yourRole) {
          statusHTML = `<div class="p-2.5 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400 text-xs font-extrabold animate-pulse">🎉 Победа! Ты выиграл дуэль!</div>`;
        } else {
          const winnerName = onlineRoomData.winner === "X" ? hostName : oppName;
          statusHTML = `<div class="p-2.5 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-400 text-xs font-extrabold">😔 Победил ${escapeHtml(winnerName)}</div>`;
        }
      } else {
        if (isYourTurn) {
          statusHTML = `<div class="p-2.5 rounded-2xl bg-blue-50 dark:bg-blue-950/50 border border-blue-200 dark:border-blue-800 text-blue-600 dark:text-blue-400 text-xs font-extrabold animate-pulse">👉 Твой ход! Поставь ${yourRole}</div>`;
        } else {
          const waitingFor = onlineRoomData?.turn === "X" ? hostName : oppName;
          statusHTML = `<div class="p-2.5 rounded-2xl bg-slate-100 dark:bg-slate-700/60 text-slate-500 dark:text-slate-400 text-xs font-bold">⏳ Ход соперника (${escapeHtml(waitingFor)})...</div>`;
        }
      }

      return `
        <!-- Matchup Header -->
        <div class="flex items-center justify-between p-2 rounded-2xl bg-slate-100 dark:bg-slate-700/60 text-xs font-bold">
          <div class="flex items-center gap-1.5 min-w-0 pr-1 ${yourRole === 'X' ? 'text-blue-600 dark:text-blue-400' : 'text-slate-700 dark:text-slate-200'}">
            <span class="w-5 h-5 rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-300 flex items-center justify-center font-black text-[11px] shrink-0">X</span>
            <span class="truncate max-w-[85px]">${escapeHtml(hostName)}${yourRole === 'X' ? ' (Вы)' : ''}</span>
          </div>
          <span class="text-[10px] font-black text-slate-400 uppercase tracking-widest shrink-0">VS</span>
          <div class="flex items-center gap-1.5 min-w-0 pl-1 ${yourRole === 'O' ? 'text-rose-600 dark:text-rose-400' : 'text-slate-700 dark:text-slate-200'}">
            <span class="truncate max-w-[85px]">${escapeHtml(oppName)}${yourRole === 'O' ? ' (Вы)' : ''}</span>
            <span class="w-5 h-5 rounded-full bg-rose-100 dark:bg-rose-900/50 text-rose-600 dark:text-rose-300 flex items-center justify-center font-black text-[11px] shrink-0">O</span>
          </div>
        </div>

        <!-- Status / Turn Banner -->
        ${statusHTML}

        <!-- 3x3 Board -->
        <div class="grid grid-cols-3 gap-2 w-64 h-64 mx-auto p-2 rounded-2xl bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 select-none">
          ${[0, 1, 2, 3, 4, 5, 6, 7, 8].map(i => {
            const val = onlineRoomData?.board?.[i] || "";
            const canClick = !isFinished && isYourTurn && val === "";
            return `
              <button
                id="online-cell-${i}"
                ${canClick ? `onclick="window.GAMES.makeOnlineMove(${i})"` : 'disabled'}
                class="w-full h-full rounded-xl bg-white dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700 text-3xl font-black flex items-center justify-center transition-all ${
                  val === 'X' ? 'text-blue-600' : val === 'O' ? 'text-rose-500' : ''
                } ${canClick ? 'hover:bg-blue-50/50 dark:hover:bg-slate-700 active:scale-95 cursor-pointer shadow-sm' : 'cursor-default'}" style="touch-action: manipulation;">
                ${val}
              </button>
            `;
          }).join('')}
        </div>

        <!-- Action Buttons -->
        <div class="space-y-2 pt-1">
          ${isFinished ? `
            ${onlineRoomData?.rematch_requested_by ? `
              ${onlineRoomData.rematch_requested_by === yourRole ? `
                <div class="p-2.5 rounded-xl bg-slate-100 dark:bg-slate-700 text-xs font-bold text-slate-500 flex items-center justify-center gap-1.5">
                  <span class="animate-spin">⏳</span> Ждем согласие соперника на реванш...
                </div>
              ` : `
                <button
                  onclick="window.GAMES.requestRematch()"
                  class="w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 active:scale-95 text-white font-black text-xs shadow-md transition-all flex items-center justify-center gap-1.5">
                  <span>🔥</span> Соперник ждет реванш! Принять бой
                </button>
              `}
            ` : `
              <button
                onclick="window.GAMES.requestRematch()"
                class="w-full py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 active:scale-95 text-white font-black text-xs shadow-md transition-all flex items-center justify-center gap-1.5">
                <span>🔄</span> Предложить реванш
              </button>
            `}
            <button
              onclick="window.GAMES.leaveOnlineGame()"
              class="w-full py-2 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-700 text-slate-500 font-bold text-xs transition-all active:scale-95">
              🚪 Выйти в лобби
            </button>
          ` : `
            <button
              onclick="window.GAMES.leaveOnlineGame()"
              class="text-xs text-slate-400 hover:text-rose-500 font-medium transition-all">
              Сдаться и выйти
            </button>
          `}
        </div>
      `;
    }

    // Default: Lobby
    return `
      <div class="space-y-3">
        <div class="text-left px-1 space-y-0.5">
          <h3 class="text-xs font-black text-slate-800 dark:text-white flex items-center gap-1">
            <span>⚔️</span> Вызов одноклассника
          </h3>
          <p class="text-[11px] text-slate-400">
            Бот мгновенно пришлет однокласснику в Telegram кнопку входа в игру
          </p>
        </div>

        <!-- Search & Refresh -->
        <div class="flex items-center gap-1.5">
          <input
            type="text"
            id="classmate-filter-input"
            value="${escapeHtml(classmatesFilter)}"
            oninput="window.GAMES.filterClassmates(this.value)"
            placeholder="🔍 Поиск одноклассника..."
            class="flex-1 px-3 py-2 rounded-xl bg-slate-100 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500">
          <button
            onclick="window.GAMES.refreshClassmates()"
            title="Обновить"
            class="p-2 rounded-xl bg-slate-100 dark:bg-slate-700 text-slate-500 hover:text-slate-800 dark:hover:text-white transition-all active:scale-95">
            🔄
          </button>
        </div>

        <!-- Classmates List Container -->
        <div id="classmates-wrapper">
          ${isLoadingClassmates ? `
            <div class="py-8 text-center text-xs text-slate-400 space-y-2">
              <div class="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
              <span>Загрузка одноклассников...</span>
            </div>
          ` : renderClassmateList()}
        </div>
      </div>
    `;
  }

  function renderClassmateList() {
    const q = (classmatesFilter || "").toLowerCase().trim();
    const filtered = classmatesList.filter(c => {
      const name = (c.name || c.full_name || "").toLowerCase();
      return !q || name.includes(q);
    });

    if (filtered.length === 0) {
      return `
        <div class="py-8 text-center text-xs text-slate-400">
          ${q ? "Никого не найдено по запросу" : "Одноклассники не найдены"}
        </div>
      `;
    }

    return `
      <div id="classmates-container" class="space-y-1.5 max-h-56 overflow-y-auto pr-1">
        ${filtered.map(c => {
          const name = c.name || c.full_name || "Одноклассник";
          const initial = name.charAt(0).toUpperCase();
          return `
            <div class="flex items-center justify-between p-2 rounded-2xl bg-slate-50 dark:bg-slate-700/50 border border-slate-200/60 dark:border-slate-700 hover:border-blue-300 dark:hover:border-blue-500/50 transition-all">
              <div class="flex items-center gap-2 min-w-0 pr-2">
                <div class="w-7 h-7 rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-300 font-black text-xs flex items-center justify-center shrink-0">
                  ${initial}
                </div>
                <div class="truncate text-left">
                  <div class="text-xs font-bold text-slate-800 dark:text-white truncate">${escapeHtml(name)}</div>
                  <div class="text-[10px] text-slate-400">11 «Б»</div>
                </div>
              </div>
              <button
                onclick="window.GAMES.inviteClassmate(${c.tg_id}, '${escapeHtml(name)}')"
                class="shrink-0 px-3 py-1.5 rounded-xl font-black text-xs bg-blue-600 hover:bg-blue-700 active:scale-95 text-white shadow-sm transition-all flex items-center gap-1">
                <span>⚔️</span> Вызвать
              </button>
            </div>
          `;
        }).join("")}
      </div>
    `;
  }

  function initTicTacToe() {
    tttBoard = ["", "", "", "", "", "", "", "", ""];
    tttTurn = "X";
    tttGameOver = false;
    updateTTTDOM();
  }

  function setTTTMode(mode) {
    stopOnlinePolling();
    if (typeof mode === "boolean") {
      mode = mode ? "bot" : "local";
    }
    tttMode = mode;
    if (mode === "online") {
      onlineState = "lobby";
      loadClassmates();
    } else {
      tttScore = { X: 0, O: 0, draw: 0 };
      initTicTacToe();
    }
    renderGames();
  }

  function resetTTT() {
    if (tttMode === "online") {
      if (onlineState === "playing" || onlineState === "finished") {
        requestRematch();
      } else {
        loadClassmates();
      }
    } else {
      initTicTacToe();
    }
  }

  function cellClickTTT(idx) {
    if (tttGameOver || tttBoard[idx] !== "") return;

    makeMoveTTT(idx, tttTurn);

    if (!tttGameOver && tttMode === "bot" && tttTurn === "O") {
      setTimeout(() => {
        botMoveTTT();
      }, 300);
    }
  }

  function makeMoveTTT(idx, player) {
    tttBoard[idx] = player;
    updateTTTDOM();

    if (window.Telegram?.WebApp?.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.impactOccurred("light");
    }

    const winner = checkWinnerTTT();
    if (winner) {
      tttGameOver = true;
      const statusEl = document.getElementById("ttt-status");
      if (winner === "draw") {
        tttScore.draw++;
        if (statusEl) statusEl.innerHTML = `<span class="text-amber-500 font-extrabold text-sm">🤝 Ничья!</span>`;
      } else {
        tttScore[winner]++;
        if (statusEl) statusEl.innerHTML = `<span class="text-emerald-500 font-extrabold text-sm">🎉 Победил ${winner}!</span>`;
        if (window.Telegram?.WebApp?.HapticFeedback) {
          window.Telegram.WebApp.HapticFeedback.notificationOccurred("success");
        }
      }
      updateScoreTTT();
      return;
    }

    tttTurn = tttTurn === "X" ? "O" : "X";
    const statusEl = document.getElementById("ttt-status");
    if (statusEl) statusEl.innerHTML = `Ход: <span class="text-blue-600 dark:text-blue-400 text-sm font-black">${tttTurn}</span>`;
  }

  function botMoveTTT() {
    if (tttGameOver) return;

    // 1. Can bot win in 1 move?
    for (let i = 0; i < 9; i++) {
      if (tttBoard[i] === "") {
        tttBoard[i] = "O";
        if (checkWinnerTTT() === "O") {
          tttBoard[i] = "";
          makeMoveTTT(i, "O");
          return;
        }
        tttBoard[i] = "";
      }
    }

    // 2. Can player win in 1 move? Block them!
    for (let i = 0; i < 9; i++) {
      if (tttBoard[i] === "") {
        tttBoard[i] = "X";
        if (checkWinnerTTT() === "X") {
          tttBoard[i] = "";
          makeMoveTTT(i, "O");
          return;
        }
        tttBoard[i] = "";
      }
    }

    // 3. Take center if available
    if (tttBoard[4] === "") {
      makeMoveTTT(4, "O");
      return;
    }

    // 4. Random empty cell
    const empty = [];
    for (let i = 0; i < 9; i++) {
      if (tttBoard[i] === "") empty.push(i);
    }
    if (empty.length > 0) {
      const chosen = empty[Math.floor(Math.random() * empty.length)];
      makeMoveTTT(chosen, "O");
    }
  }

  function checkWinnerTTT() {
    const lines = [
      [0, 1, 2], [3, 4, 5], [6, 7, 8], // Rows
      [0, 3, 6], [1, 4, 7], [2, 5, 8], // Cols
      [0, 4, 8], [2, 4, 6]             // Diagonals
    ];
    for (let [a, b, c] of lines) {
      if (tttBoard[a] && tttBoard[a] === tttBoard[b] && tttBoard[a] === tttBoard[c]) {
        return tttBoard[a];
      }
    }
    if (tttBoard.every(cell => cell !== "")) return "draw";
    return null;
  }

  function updateTTTDOM() {
    for (let i = 0; i < 9; i++) {
      const cell = document.getElementById(`ttt-cell-${i}`);
      if (cell) {
        cell.textContent = tttBoard[i];
        cell.className = `w-full h-full rounded-xl bg-white dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700 text-3xl font-black flex items-center justify-center transition-all ${
          tttBoard[i] === "X" ? "text-blue-600" : tttBoard[i] === "O" ? "text-rose-500" : ""
        }`;
      }
    }
  }

  function updateScoreTTT() {
    const xEl = document.getElementById("ttt-score-x");
    const oEl = document.getElementById("ttt-score-o");
    const dEl = document.getElementById("ttt-score-d");
    if (xEl) xEl.textContent = tttScore.X;
    if (oEl) oEl.textContent = tttScore.O;
    if (dEl) dEl.textContent = tttScore.draw;
  }

  // --- ONLINE MULTIPLAYER LOGIC ---

  async function loadClassmates() {
    isLoadingClassmates = true;
    renderGames();
    try {
      classmatesList = await api.getClassmates();
    } catch (e) {
      console.warn("Could not load classmates:", e);
      classmatesList = [];
    } finally {
      isLoadingClassmates = false;
      renderGames();
    }
  }

  function filterClassmates(val) {
    classmatesFilter = val;
    const wrapper = document.getElementById("classmates-wrapper");
    if (wrapper) {
      wrapper.innerHTML = renderClassmateList();
    }
  }

  async function inviteClassmate(tgId, oppName) {
    onlineOpponentName = oppName;
    onlineState = "waiting";
    renderGames();

    try {
      let myName = "Одноклассник";
      try {
        const me = await api.getMe();
        if (me && me.full_name) myName = me.full_name;
      } catch (e) {}

      const res = await api.inviteGame(tgId, myName, "tictactoe", "white", oppName);
      onlineRoomId = res.room_id;
      onlineRoomData = res;
      startOnlinePolling();
    } catch (e) {
      alert("Не удалось отправить вызов: " + (e.message || "Ошибка"));
      onlineState = "lobby";
      renderGames();
    }
  }

  async function openTTTOnlineRoom(roomId) {
    if (window.currentGame) window.currentGame = "tictactoe";
    tttMode = "online";
    onlineRoomId = roomId;
    onlineState = "loading";
    renderGames();

    try {
      let myName = "Игрок";
      try {
        const me = await api.getMe();
        if (me && me.full_name) myName = me.full_name;
      } catch (e) {}

      const room = await api.joinGameRoom(roomId, myName);
      onlineRoomData = room;
      if (room.status === "finished") {
        onlineState = "finished";
      } else if (room.status === "waiting") {
        onlineState = "waiting";
      } else {
        onlineState = "playing";
      }
      renderGames();
      startOnlinePolling();
    } catch (e) {
      console.error("Failed to join online room:", e);
      onlineState = "rejected";
      renderGames();
    }
  }

  async function openOnlineRoom(roomId, gameType) {
    if (gameType === "chess" && window.GAMES_CHESS && typeof window.GAMES_CHESS.openChessOnlineRoom === "function") {
      return window.GAMES_CHESS.openChessOnlineRoom(roomId);
    }
    try {
      const room = await api.getGameRoom(roomId);
      if (room && room.game_type === "chess" && window.GAMES_CHESS && typeof window.GAMES_CHESS.openChessOnlineRoom === "function") {
        return window.GAMES_CHESS.openChessOnlineRoom(roomId);
      }
    } catch (e) {}
    return openTTTOnlineRoom(roomId);
  }

  async function makeOnlineMove(cellIdx) {
    if (!onlineRoomId || !onlineRoomData || !onlineRoomData.is_your_turn) return;
    if (onlineRoomData.board[cellIdx] !== "") return;

    if (window.Telegram?.WebApp?.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.impactOccurred("light");
    }

    try {
      const updated = await api.sendGameMove(onlineRoomId, cellIdx);
      handleRoomUpdate(updated);
    } catch (e) {
      console.warn("Move error:", e);
    }
  }

  async function requestRematch() {
    if (!onlineRoomId) return;
    try {
      const updated = await api.rematchGame(onlineRoomId);
      handleRoomUpdate(updated);
      renderGames();
    } catch (e) {
      alert("Ошибка реванша: " + (e.message || "Ошибка"));
    }
  }

  async function cancelOnlineGame() {
    if (onlineRoomId) {
      try {
        await api.cancelGame(onlineRoomId);
      } catch (e) {}
    }
    stopOnlinePolling();
    onlineRoomId = null;
    onlineRoomData = null;
    onlineState = "lobby";
    renderGames();
  }

  function leaveOnlineGame() {
    stopOnlinePolling();
    onlineRoomId = null;
    onlineRoomData = null;
    onlineState = "lobby";
    renderGames();
  }

  function backToLobby() {
    stopOnlinePolling();
    onlineRoomId = null;
    onlineRoomData = null;
    onlineState = "lobby";
    loadClassmates();
  }

  function startOnlinePolling() {
    stopOnlinePolling();
    isOnlinePolling = true;
    pollRoomState();
  }

  function stopOnlinePolling() {
    isOnlinePolling = false;
    if (onlinePollTimer) {
      clearTimeout(onlinePollTimer);
      onlinePollTimer = null;
    }
  }

  async function pollRoomState() {
    if (!isOnlinePolling || !onlineRoomId) return;

    try {
      const data = await api.getGameRoom(onlineRoomId);
      handleRoomUpdate(data);
    } catch (e) {
      console.warn("Error polling online room:", e);
    }

    if (isOnlinePolling && onlineRoomId) {
      onlinePollTimer = setTimeout(pollRoomState, 800);
    }
  }

  function handleRoomUpdate(data) {
    if (!data) return;
    const oldStatus = onlineRoomData ? onlineRoomData.status : null;
    const oldTurn = onlineRoomData ? onlineRoomData.turn : null;
    const oldBoard = onlineRoomData ? JSON.stringify(onlineRoomData.board) : "";
    const oldRematch = onlineRoomData ? onlineRoomData.rematch_requested_by : null;

    onlineRoomData = data;

    if (data.status === "rejected" || data.status === "canceled") {
      stopOnlinePolling();
      onlineState = "rejected";
      renderGames();
      return;
    }

    if (data.status === "waiting") {
      if (onlineState !== "waiting") {
        onlineState = "waiting";
        renderGames();
      }
      return;
    }

    if (data.status === "playing") {
      if (onlineState !== "playing" || oldBoard !== JSON.stringify(data.board) || oldTurn !== data.turn) {
        onlineState = "playing";
        renderGames();
        if (window.Telegram?.WebApp?.HapticFeedback) {
          window.Telegram.WebApp.HapticFeedback.impactOccurred("light");
        }
      }
      return;
    }

    if (data.status === "finished") {
      if (onlineState !== "finished") {
        onlineState = "finished";
        renderGames();
        if (window.Telegram?.WebApp?.HapticFeedback) {
          if (data.winner === data.your_role) {
            window.Telegram.WebApp.HapticFeedback.notificationOccurred("success");
          } else if (data.winner === "draw") {
            window.Telegram.WebApp.HapticFeedback.notificationOccurred("warning");
          } else {
            window.Telegram.WebApp.HapticFeedback.notificationOccurred("error");
          }
        }
      } else if (oldRematch !== data.rematch_requested_by) {
        renderGames();
      }
      return;
    }
  }

  // ==============================================================================


  window.GAMES_TICTACTOE = {
    renderHTML: renderTicTacToeHTML,
    init: initTicTacToe,
    cleanup: function() {
      stopOnlinePolling();
    },
    setTTTMode: setTTTMode,
    cellClickTTT: cellClickTTT,
    resetTTT: resetTTT,
    openOnlineRoom: openOnlineRoom,
    inviteClassmate: inviteClassmate,
    makeOnlineMove: makeOnlineMove,
    requestRematch: requestRematch,
    cancelOnlineGame: cancelOnlineGame,
    leaveOnlineGame: leaveOnlineGame,
    backToLobby: backToLobby,
    filterClassmates: filterClassmates,
    loadClassmates: loadClassmates
  };
})();
