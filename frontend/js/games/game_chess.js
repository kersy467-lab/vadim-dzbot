// frontend/js/games/game_chess.js
(function() {
  'use strict';

  function renderGames() {
    if (window.GAMES && typeof window.GAMES.render === 'function') {
      window.GAMES.render();
    }
  }

  function haptic(type, arg) {
    if (!window.Telegram?.WebApp?.HapticFeedback) return;
    const hf = window.Telegram.WebApp.HapticFeedback;
    if (type === 'sel') hf.selectionChanged();
    else if (type === 'imp') hf.impactOccurred(arg || 'light');
    else if (type === 'not') hf.notificationOccurred(arg || 'success');
  }

  let chessState = "lobby"; // 'lobby' | 'loading' | 'waiting' | 'playing' | 'finished' | 'rejected'
  let chessRoomId = null;
  let chessRoomData = null;
  let chessOpponentName = "";
  let chessSelectedSquare = null; // e.g. "e2"
  let chessPendingPromotion = null; // { from: "e7", to: "e8" }
  let chessClassmatesList = [];
  let chessClassmatesFilter = "";
  let isChessLoadingClassmates = false;
  let chessPollTimer = null;
  let isChessPolling = false;
  let chessSelectedColor = "white"; // 'white' | 'black' | 'random'
  let chessIsLocal = false;
  let chessIsBot = false;
  let chessLocalAutoRotate = true;
  let chessManualFlipped = false;

  function toggleChessAutoRotate() {
    chessLocalAutoRotate = !chessLocalAutoRotate;
    haptic('sel');
    renderGames();
  }

  function flipChessBoardManual() {
    chessManualFlipped = !chessManualFlipped;
    haptic('imp', 'light');
    renderGames();
  }

  function setChessColor(color) {
    if (["white", "black", "random"].includes(color)) {
      chessSelectedColor = color;
      haptic('sel');
      renderGames();
    }
  }

  async function startBotChessGame(color) {
    const chosenColor = color || chessSelectedColor || "white";
    chessIsBot = true;
    chessIsLocal = false;
    chessManualFlipped = false;
    chessState = "loading";
    renderGames();

    try {
      const res = await api.createBotGame("chess", chosenColor);
      if (res && res.room_id) {
        chessRoomId = res.room_id;
        chessRoomData = res;
        chessState = "playing";
      } else {
        alert(res?.detail || "Ошибка создания игры против бота");
        chessState = "lobby";
      }
    } catch (e) {
      console.error(e);
      alert("Не удалось запустить игру против бота");
      chessState = "lobby";
    }
    renderGames();
  }

  async function startLocalChessGame() {
    chessIsBot = false;
    chessIsLocal = true;
    chessLocalAutoRotate = true;
    chessManualFlipped = false;
    chessState = "loading";
    renderGames();

    try {
      const res = await api.createLocalGame("chess", "Белые");
      if (res && res.room_id) {
        chessRoomId = res.room_id;
        chessRoomData = res;
        chessState = "playing";
      } else {
        alert(res?.detail || "Ошибка создания локальной игры");
        chessState = "lobby";
      }
    } catch (e) {
      console.error(e);
      alert("Не удалось запустить игру");
      chessState = "lobby";
    }
    renderGames();
  }

  async function loadChessClassmates() {
    if (isChessLoadingClassmates) return;
    isChessLoadingClassmates = true;
    renderGames();

    try {
      chessClassmatesList = await api.getClassmates();
    } catch (e) {
      console.warn("Could not load classmates for chess:", e);
      chessClassmatesList = [];
    } finally {
      isChessLoadingClassmates = false;
      renderGames();
    }
  }

  function filterChessClassmates(val) {
    chessClassmatesFilter = val;
    const wrapper = document.getElementById("chess-classmates-wrapper");
    if (wrapper && window.CHESS_UI) {
      wrapper.innerHTML = window.CHESS_UI.renderClassmatesList(chessClassmatesList, chessClassmatesFilter);
    }
  }

  async function inviteChessClassmate(tgId, oppName) {
    chessIsBot = false;
    chessIsLocal = false;
    chessOpponentName = oppName;
    chessState = "waiting";
    renderGames();

    try {
      let myName = "Одноклассник";
      try {
        const me = await api.getMe();
        if (me && me.full_name) myName = me.full_name;
      } catch (e) {}

      const res = await api.inviteGame(tgId, myName, "chess", chessSelectedColor, oppName);
      chessRoomId = res.room_id;
      chessRoomData = res;
      startChessPolling();
    } catch (e) {
      alert("Не удалось отправить вызов в шахматы: " + (e.message || "Ошибка"));
      chessState = "lobby";
      renderGames();
    }
  }

  async function openChessOnlineRoom(roomId) {
    if (window.currentGame) window.currentGame = "chess";
    chessIsBot = false;
    chessIsLocal = false;
    chessRoomId = roomId;
    chessState = "loading";
    renderGames();

    try {
      let myName = "Игрок";
      try {
        const me = await api.getMe();
        if (me && me.full_name) myName = me.full_name;
      } catch (e) {}

      const room = await api.joinGameRoom(roomId, myName);
      chessRoomData = room;
      chessState = room.status === "finished" ? "finished" : (room.status === "waiting" ? "waiting" : "playing");
      renderGames();
      startChessPolling();
    } catch (e) {
      console.error("Failed to join chess online room:", e);
      chessState = "rejected";
      renderGames();
    }
  }

  function chessSquareClick(sq) {
    if (!chessRoomData || chessRoomData.status !== "playing" || !chessRoomData.is_your_turn) return;

    const board = window.CHESS_BOARD ? window.CHESS_BOARD.parseFen(chessRoomData.fen) : [];
    const { r, c } = window.CHESS_BOARD ? window.CHESS_BOARD.squareToRC(sq) : { r: 0, c: 0 };
    const piece = board[r] ? board[r][c] : "";
    const yourRole = chessRoomData.your_role;
    const isMyPiece = piece && (
      (yourRole === "white" && piece === piece.toUpperCase()) ||
      (yourRole === "black" && piece === piece.toLowerCase())
    );

    if (chessSelectedSquare) {
      const legalMoves = (chessRoomData.legal_moves || []).filter(m => m.startsWith(chessSelectedSquare));
      const matchingMove = legalMoves.find(m => m.slice(2, 4) === sq);

      if (matchingMove) {
        const promoMoves = legalMoves.filter(m => m.slice(2, 4) === sq && m.length === 5);
        if (promoMoves.length > 0) {
          chessPendingPromotion = { from: chessSelectedSquare, to: sq };
          renderGames();
          return;
        }

        const uci = chessSelectedSquare + sq;
        chessSelectedSquare = null;
        sendChessMove(uci);
        return;
      }

      if (isMyPiece) {
        chessSelectedSquare = sq;
        haptic('sel');
        renderGames();
        return;
      }

      chessSelectedSquare = null;
      renderGames();
      return;
    }

    if (isMyPiece) {
      chessSelectedSquare = sq;
      haptic('sel');
      renderGames();
    }
  }

  function choosePromotion(pieceLetter) {
    if (!chessPendingPromotion) return;
    const uci = chessPendingPromotion.from + chessPendingPromotion.to + pieceLetter.toLowerCase();
    chessPendingPromotion = null;
    chessSelectedSquare = null;
    sendChessMove(uci);
  }

  async function sendChessMove(uci) {
    if (!chessRoomId) return;
    haptic('imp', 'light');

    try {
      const updated = await api.sendGameMove(chessRoomId, uci);
      handleChessRoomUpdate(updated);
    } catch (e) {
      console.warn("Chess move error:", e);
    }
  }

  async function resignChessGame() {
    if (!chessRoomId || chessRoomData?.status !== "playing") return;
    if (!confirm("Вы действительно хотите сдаться в этой партии?")) return;

    try {
      const updated = await api.resignGame(chessRoomId);
      handleChessRoomUpdate(updated);
    } catch (e) {
      alert("Ошибка при сдаче: " + (e.message || "Ошибка"));
    }
  }

  async function requestChessRematch() {
    if (!chessRoomId) return;
    try {
      const updated = await api.rematchGame(chessRoomId);
      handleChessRoomUpdate(updated);
      renderGames();
    } catch (e) {
      alert("Ошибка реванша: " + (e.message || "Ошибка"));
    }
  }

  function leaveChessGame() {
    stopChessPolling();
    chessRoomId = null;
    chessRoomData = null;
    chessIsLocal = false;
    chessIsBot = false;
    chessManualFlipped = false;
    chessState = "lobby";
    renderGames();
  }

  async function cancelChessGame() {
    if (chessRoomId && chessState === "waiting") {
      try { await api.cancelGame(chessRoomId); } catch (e) { console.warn("Cancel chess error:", e); }
    }
    leaveChessGame();
  }

  function startChessPolling() {
    if (chessIsLocal || chessIsBot) return;
    stopChessPolling();
    isChessPolling = true;
    pollChessRoomState();
  }

  function stopChessPolling() {
    isChessPolling = false;
    if (chessPollTimer) {
      clearTimeout(chessPollTimer);
      chessPollTimer = null;
    }
  }

  async function pollChessRoomState() {
    if (!isChessPolling || !chessRoomId || chessIsLocal || chessIsBot) return;
    try {
      const data = await api.getGameRoom(chessRoomId);
      handleChessRoomUpdate(data);
    } catch (e) {
      console.warn("Error polling chess room:", e);
    }
    if (isChessPolling && chessRoomId) {
      chessPollTimer = setTimeout(pollChessRoomState, 800);
    }
  }

  function handleChessRoomUpdate(data) {
    if (!data) return;
    const oldFen = chessRoomData ? chessRoomData.fen : null;
    chessRoomData = data;
    chessIsBot = !!data.is_bot;

    if (data.status === "rejected" || data.status === "canceled") {
      stopChessPolling();
      chessState = "rejected";
      renderGames();
      return;
    }

    if (data.status === "waiting") {
      if (chessState !== "waiting") {
        chessState = "waiting";
        renderGames();
      }
      return;
    }

    if (data.status === "playing") {
      if (chessState !== "playing" || oldFen !== data.fen) {
        chessState = "playing";
        renderGames();
        haptic('imp', 'light');
      }
      return;
    }

    if (data.status === "finished") {
      if (chessState !== "finished") {
        chessState = "finished";
        renderGames();
        haptic('not', (chessIsLocal || data.winner === data.your_role) ? 'success' : (data.winner === 'draw' ? 'warning' : 'error'));
      } else {
        renderGames();
      }
    }
  }

  function renderChessHTML() {
    if (!window.CHESS_UI) return "";
    return `
      <div class="theme-card rounded-3xl p-3 sm:p-4 bg-white dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700 shadow-sm space-y-3 max-w-sm mx-auto text-center">
        ${window.CHESS_UI.renderChessContentHTML({
          chessState, chessRoomData, chessOpponentName, chessSelectedColor,
          chessClassmatesFilter, isChessLoadingClassmates, chessClassmatesList,
          chessIsLocal, chessIsBot, chessLocalAutoRotate, chessManualFlipped,
          chessSelectedSquare, chessPendingPromotion
        })}
      </div>
    `;
  }

  function initChess() {
    if (!chessRoomId) {
      chessState = "lobby";
      if (!isChessLoadingClassmates && chessClassmatesList.length === 0) {
        loadChessClassmates();
      }
    }
  }

  const exportObj = {
    renderHTML: renderChessHTML, init: initChess, cleanup: stopChessPolling,
    startBotChessGame, startLocalChessGame, toggleChessAutoRotate, flipChessBoardManual,
    openChessOnlineRoom, inviteChessClassmate, chessSquareClick, choosePromotion,
    resignChessGame, requestChessRematch, cancelChessGame,
    leaveChessGame, backToChessLobby: leaveChessGame, filterChessClassmates,
    loadChessClassmates, refreshChessClassmates: loadChessClassmates, setChessColor
  };

  window.GAMES_CHESS = exportObj;
  if (!window.GAMES) window.GAMES = {};
  Object.assign(window.GAMES, exportObj);
})();
