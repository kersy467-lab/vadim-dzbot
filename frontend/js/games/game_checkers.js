// frontend/js/games/game_checkers.js
(function() {
  'use strict';

  function renderGames() {
    if (window.GAMES && typeof window.GAMES.render === 'function') {
      window.GAMES.render();
    }
  }

  let checkersState = "lobby"; // 'lobby' | 'loading' | 'waiting' | 'playing' | 'finished' | 'rejected'
  let checkersRoomId = null;
  let checkersRoomData = null;
  let checkersOpponentName = "";
  let checkersSelectedSquare = null;
  let checkersClassmatesList = [];
  let checkersClassmatesFilter = "";
  let isCheckersLoadingClassmates = false;
  let checkersPollTimer = null;
  let isCheckersPolling = false;
  let _checkersWsConn = null; // GameWS connection (primary channel)
  let checkersSelectedColor = "white"; // 'white' | 'black' | 'random'
  let checkersIsLocal = false;
  let checkersIsBot = false;
  let checkersLocalAutoRotate = true;
  let checkersManualFlipped = false;

  function toggleAutoRotate() { checkersLocalAutoRotate = !checkersLocalAutoRotate; window.Telegram?.WebApp?.HapticFeedback?.selectionChanged(); renderGames(); }
  function flipBoardManual() { checkersManualFlipped = !checkersManualFlipped; window.Telegram?.WebApp?.HapticFeedback?.impactOccurred("light"); renderGames(); }
  function setColor(color) {
    if (["white", "black", "random"].includes(color)) {
      checkersSelectedColor = color; window.Telegram?.WebApp?.HapticFeedback?.selectionChanged(); renderGames();
    }
  }

  async function startBotGame(color) {
    const chosenColor = color || checkersSelectedColor || "white";
    checkersIsBot = true;
    checkersIsLocal = false;
    checkersManualFlipped = false;
    checkersState = "loading";
    renderGames();

    try {
      const res = await api.createBotGame("checkers", chosenColor);
      if (res && res.room_id) {
        checkersRoomId = res.room_id;
        checkersRoomData = res;
        checkersState = "playing";
      } else {
        alert(res?.detail || "Ошибка создания игры против бота");
        checkersState = "lobby";
      }
    } catch (e) {
      console.error(e);
      alert("Не удалось запустить шашки против бота");
      checkersState = "lobby";
    }
    renderGames();
  }

  async function startLocalGame() {
    checkersIsBot = false;
    checkersIsLocal = true;
    checkersLocalAutoRotate = true;
    checkersManualFlipped = false;
    checkersState = "loading";
    renderGames();

    try {
      const res = await api.createLocalGame("checkers", "Белые");
      if (res && res.room_id) {
        checkersRoomId = res.room_id;
        checkersRoomData = res;
        checkersState = "playing";
        renderGames();
      } else {
        alert(res?.detail || "Ошибка создания локальной игры");
        checkersState = "lobby";
        renderGames();
      }
    } catch (e) {
      console.error(e);
      alert("Не удалось запустить шашки на телефоне");
      checkersState = "lobby";
      renderGames();
    }
  }

  async function inviteClassmate(tgId, oppName) {
    checkersIsBot = false;
    checkersOpponentName = oppName;
    checkersState = "waiting";
    renderGames();

    try {
      let myName = "Одноклассник";
      try {
        const me = await api.getMe();
        if (me && me.full_name) myName = me.full_name;
      } catch (e) {}

      const res = await api.inviteGame(tgId, myName, "checkers", checkersSelectedColor, oppName);
      checkersRoomId = res.room_id;
      checkersRoomData = res;
      startPolling();
    } catch (e) {
      alert("Не удалось отправить вызов в шашки: " + (e.message || "Ошибка"));
      checkersState = "lobby";
      renderGames();
    }
  }

  async function openOnlineRoom(roomId) {
    if (window.currentGame) window.currentGame = "checkers";
    checkersRoomId = roomId;
    checkersState = "loading";
    renderGames();

    try {
      let myName = "Игрок";
      try {
        const me = await api.getMe();
        if (me && me.full_name) myName = me.full_name;
      } catch (e) {}

      const room = await api.joinGameRoom(roomId, myName);
      checkersRoomData = room;
      checkersState = room.status === "finished" ? "finished" : (room.status === "waiting" ? "waiting" : "playing");
      renderGames();
      startPolling();
    } catch (e) {
      console.error("Failed to join checkers online room:", e);
      checkersState = "rejected";
      renderGames();
    }
  }

  function squareClick(sq) {
    if (!checkersRoomData || checkersRoomData.status !== "playing") return;
    if (!checkersRoomData.is_your_turn) return;

    const board = window.CHECKERS_BOARD ? window.CHECKERS_BOARD.parseFen(checkersRoomData.fen) : null;
    if (!board) return;

    const { r, c } = window.CHECKERS_BOARD.squareToRC(sq);
    const piece = board[r][c];
    const yourRole = checkersRoomData.your_role;
    const isMyPiece = piece && (
      (yourRole === "white" && (piece === 'w' || piece === 'W')) ||
      (yourRole === "black" && (piece === 'b' || piece === 'B'))
    );

    const activeJump = checkersRoomData.active_jump_piece;

    if (checkersSelectedSquare) {
      const legalMoves = (checkersRoomData.legal_moves || []).filter(m => m.startsWith(checkersSelectedSquare));
      const matchingMove = legalMoves.find(m => m.slice(2, 4) === sq);

      if (matchingMove) {
        const uci = checkersSelectedSquare + sq;
        checkersSelectedSquare = null;
        sendMove(uci);
        return;
      }

      if (isMyPiece && !activeJump) {
        checkersSelectedSquare = sq;
        if (window.Telegram?.WebApp?.HapticFeedback) window.Telegram.WebApp.HapticFeedback.selectionChanged();
        renderGames();
        return;
      }

      if (!activeJump) {
        checkersSelectedSquare = null;
        renderGames();
      }
      return;
    }

    if (isMyPiece) {
      if (activeJump && activeJump !== sq) return;
      checkersSelectedSquare = sq;
      if (window.Telegram?.WebApp?.HapticFeedback) window.Telegram.WebApp.HapticFeedback.selectionChanged();
      renderGames();
    }
  }

  async function sendMove(uci) {
    if (!checkersRoomId) return;
    if (window.Telegram?.WebApp?.HapticFeedback) window.Telegram.WebApp.HapticFeedback.impactOccurred("light");

    try {
      const updated = await api.sendGameMove(checkersRoomId, uci);
      handleRoomUpdate(updated);
    } catch (e) {
      console.warn("Checkers move error:", e);
    }
  }

  async function resignGame() {
    if (!checkersRoomId || checkersRoomData?.status !== "playing") return;
    if (!confirm("Вы действительно хотите сдаться в партии?")) return;

    try {
      const updated = await api.resignGame(checkersRoomId);
      handleRoomUpdate(updated);
    } catch (e) {
      alert("Ошибка: " + (e.message || "Ошибка"));
    }
  }

  async function requestRematch() {
    if (!checkersRoomId) return;
    try {
      const updated = await api.rematchGame(checkersRoomId);
      handleRoomUpdate(updated);
      renderGames();
    } catch (e) {
      alert("Ошибка реванша: " + (e.message || "Ошибка"));
    }
  }

  function leaveGame() {
    stopPolling();
    checkersRoomId = null;
    checkersRoomData = null;
    checkersIsLocal = false;
    checkersIsBot = false;
    checkersManualFlipped = false;
    checkersSelectedSquare = null;
    checkersState = "lobby";
    renderGames();
  }

  async function cancelCheckersGame() {
    if (checkersRoomId && checkersState === "waiting") {
      try { await api.cancelGame(checkersRoomId); } catch (e) { console.warn("Cancel checkers error:", e); }
    }
    leaveGame();
  }

  function startPolling() {
    if (checkersIsLocal || checkersIsBot) return;
    stopPolling();
    const userId = window.AppState?.tgUserId || 0;
    if (window.GameWS && checkersRoomId && userId) {
      _checkersWsConn = window.GameWS.connect(
        checkersRoomId, userId,
        (data) => handleRoomUpdate(data),
        () => { _checkersWsConn = null; }
      );
    } else {
      isCheckersPolling = true;
      pollState();
    }
  }

  function stopPolling() {
    isCheckersPolling = false;
    if (checkersPollTimer) { clearTimeout(checkersPollTimer); checkersPollTimer = null; }
    if (_checkersWsConn) { _checkersWsConn.disconnect(); _checkersWsConn = null; }
  }

  async function pollState() {
    // HTTP-fallback (используется только если GameWS недоступен)
    if (!isCheckersPolling || !checkersRoomId || checkersIsLocal || checkersIsBot) return;
    try {
      const data = await api.getGameRoom(checkersRoomId);
      handleRoomUpdate(data);
    } catch (e) {
      console.warn("Error polling checkers:", e);
    }
    if (isCheckersPolling && checkersRoomId) {
      checkersPollTimer = setTimeout(pollState, 1500);
    }
  }

  function handleRoomUpdate(data) {
    if (!data) return;
    const oldFen = checkersRoomData ? checkersRoomData.fen : null;
    const oldRematch = checkersRoomData ? checkersRoomData.rematch_requested_by : null;
    checkersRoomData = data;
    checkersIsBot = !!data.is_bot;

    if (data.active_jump_piece) {
      checkersSelectedSquare = data.active_jump_piece;
    } else if (checkersSelectedSquare && !data.legal_moves?.some(m => m.startsWith(checkersSelectedSquare))) {
      checkersSelectedSquare = null;
    }

    if (data.status === "rejected" || data.status === "canceled") {
      stopPolling();
      checkersState = "rejected";
      renderGames();
      return;
    }
    if (data.status === "waiting") {
      if (checkersState !== "waiting") { checkersState = "waiting"; renderGames(); }
      return;
    }
    if (data.status === "playing") {
      if (checkersState !== "playing" || oldFen !== data.fen) {
        checkersState = "playing";
        renderGames();
        if (window.Telegram?.WebApp?.HapticFeedback) window.Telegram.WebApp.HapticFeedback.impactOccurred("light");
      }
      return;
    }
    if (data.status === "finished") {
      if (checkersState !== "finished" || oldRematch !== data.rematch_requested_by) {
        checkersState = "finished";
        renderGames();
        if (window.Telegram?.WebApp?.HapticFeedback) {
          if (checkersIsLocal || data.winner === data.your_role) window.Telegram.WebApp.HapticFeedback.notificationOccurred("success");
          else window.Telegram.WebApp.HapticFeedback.notificationOccurred("error");
        }
      }
    }
  }

  async function loadClassmates() {
    if (isCheckersLoadingClassmates) return;
    isCheckersLoadingClassmates = true;
    try {
      checkersClassmatesList = await api.getClassmates();
    } catch (e) {
      checkersClassmatesList = [];
    } finally {
      isCheckersLoadingClassmates = false;
      renderGames();
    }
  }

  function initCheckers() {
    if (!checkersRoomId) {
      checkersState = "lobby";
      if (!isCheckersLoadingClassmates && checkersClassmatesList.length === 0) {
        loadClassmates();
      }
    }
  }

  function renderHTML() {
    let content = "";
    if (checkersState === "loading") {
      content = `
        <div class="py-12 space-y-3">
          <div class="w-10 h-10 border-4 border-amber-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p class="text-xs font-bold text-slate-500">Загрузка партии в шашки...</p>
        </div>
      `;
    } else if (checkersState === "waiting") {
      content = window.CHECKERS_UI ? window.CHECKERS_UI.renderWaiting(checkersRoomData, checkersOpponentName) : "";
    } else if (checkersState === "rejected") {
      content = window.CHECKERS_UI ? window.CHECKERS_UI.renderRejected() : "";
    } else if (checkersState === "playing" || checkersState === "finished") {
      content = window.CHECKERS_UI ? window.CHECKERS_UI.renderPlaying({
        state: checkersState,
        data: checkersRoomData,
        isLocal: checkersIsLocal,
        autoRotate: checkersLocalAutoRotate,
        manualFlipped: checkersManualFlipped,
        selectedSquare: checkersSelectedSquare
      }) : "";
    } else {
      content = window.CHECKERS_UI ? window.CHECKERS_UI.renderLobby(checkersSelectedColor, checkersClassmatesFilter, checkersClassmatesList) : "";
    }

    return `
      <div class="theme-card rounded-3xl p-3 sm:p-4 bg-white dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700 shadow-sm space-y-3 max-w-sm mx-auto text-center">
        ${content}
      </div>
    `;
  }

  window.GAMES_CHECKERS = {
    init: initCheckers,
    cleanup: function() { stopPolling(); },
    renderHTML: renderHTML,
    startBotGame: startBotGame,
    startBotCheckersGame: startBotGame,
    startLocalGame: startLocalGame,
    cancelCheckersGame: cancelCheckersGame,
    cancelGame: cancelCheckersGame,
    toggleAutoRotate: toggleAutoRotate,
    flipBoardManual: flipBoardManual,
    setColor: setColor,
    inviteClassmate: inviteClassmate,
    openOnlineRoom: openOnlineRoom,
    squareClick: squareClick,
    resignGame: resignGame,
    requestRematch: requestRematch,
    leaveGame: leaveGame,
    filterClassmates: (val) => { checkersClassmatesFilter = val; renderGames(); },
    loadClassmates: loadClassmates
  };
})();
