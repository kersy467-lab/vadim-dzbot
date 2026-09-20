(function() {
  'use strict';

  function renderGames() {
    if (window.GAMES && typeof window.GAMES.render === 'function') {
      window.GAMES.render();
    }
  }

  // GAME 5: CHESS (Шахматы - онлайн дуэль и режим на 2 игроков на 1 телефоне)
  // ==============================================================================
  let chessState = "lobby"; // 'lobby', 'loading', 'waiting', 'playing', 'finished', 'rejected'
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
  let chessLocalAutoRotate = true;
  let chessManualFlipped = false;

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function toggleChessAutoRotate() {
    chessLocalAutoRotate = !chessLocalAutoRotate;
    if (window.Telegram?.WebApp?.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.selectionChanged();
    }
    renderGames();
  }

  function flipChessBoardManual() {
    chessManualFlipped = !chessManualFlipped;
    if (window.Telegram?.WebApp?.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.impactOccurred("light");
    }
    renderGames();
  }

  async function startLocalChessGame() {
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
        renderGames();
      } else {
        alert(res?.detail || "Ошибка создания локальной игры");
        chessState = "lobby";
        renderGames();
      }
    } catch (e) {
      console.error(e);
      alert("Не удалось запустить игру");
      chessState = "lobby";
      renderGames();
    }
  }

  function setChessColor(color) {
    if (["white", "black", "random"].includes(color)) {
      chessSelectedColor = color;
      if (window.Telegram?.WebApp?.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.selectionChanged();
      }
      renderGames();
    }
  }

  const CHESS_SYMBOLS = {
    "P": "♙", "N": "♘", "B": "♗", "R": "♖", "Q": "♕", "K": "♔",
    "p": "♟", "n": "♞", "b": "♝", "r": "♜", "q": "♛", "k": "♚"
  };

  const CHESS_FILES = ["a", "b", "c", "d", "e", "f", "g", "h"];

  function initChess() {
    if (!chessRoomId) {
      chessState = "lobby";
      if (!isChessLoadingClassmates && chessClassmatesList.length === 0) {
        loadChessClassmates();
      }
    }
  }

  function parseFen(fen) {
    if (!fen) fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
    const parts = fen.split(" ");
    const rows = parts[0].split("/");
    const board = [];
    for (let r = 0; r < 8; r++) {
      const rowStr = rows[r] || "8";
      const row = [];
      for (let i = 0; i < rowStr.length; i++) {
        const ch = rowStr[i];
        if (ch >= "1" && ch <= "8") {
          const num = parseInt(ch, 10);
          for (let k = 0; k < num; k++) row.push("");
        } else {
          row.push(ch);
        }
      }
      board.push(row);
    }
    return board;
  }

  function rcToSquare(r, c) {
    return CHESS_FILES[c] + (8 - r);
  }

  function squareToRC(sq) {
    const file = sq.charAt(0);
    const rank = parseInt(sq.charAt(1), 10);
    const c = CHESS_FILES.indexOf(file);
    const r = 8 - rank;
    return { r, c };
  }

  function renderChessPiece(char) {
    if (!char) return "";
    const isWhite = char === char.toUpperCase();
    const glyph = CHESS_SYMBOLS[char] || char;
    return `
      <span class="select-none leading-none inline-block font-black text-2xl sm:text-3xl transition-transform transform group-active:scale-90 ${
        isWhite
          ? 'text-white drop-shadow-[0_2px_2px_rgba(0,0,0,0.95)]'
          : 'text-slate-900 drop-shadow-[0_1px_1px_rgba(255,255,255,0.7)]'
      }">
        ${glyph}
      </span>
    `;
  }

  function renderChessHTML() {
    return `
      <div class="theme-card rounded-3xl p-3 sm:p-4 bg-white dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700 shadow-sm space-y-3 max-w-sm mx-auto text-center">
        ${renderChessContentHTML()}
      </div>
    `;
  }

  function renderChessContentHTML() {
    if (chessState === "loading") {
      return `
        <div class="py-12 space-y-3">
          <div class="w-10 h-10 border-4 border-amber-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p class="text-xs font-bold text-slate-500">Подключение к шахматной партии...</p>
        </div>
      `;
    }

    if (chessState === "waiting") {
      const oppName = chessOpponentName || (chessRoomData?.black?.name || chessRoomData?.white?.name) || "Одноклассник";
      const hostColor = chessRoomData?.host_color || (chessSelectedColor === "black" ? "black" : "white");
      const colorBadge = hostColor === "black"
        ? `<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-slate-800 text-white border border-slate-600 text-[10px] font-bold">⚫ Твой цвет: Черные</span>`
        : `<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-900 border border-amber-300 text-[10px] font-bold">⚪ Твой цвет: Белые</span>`;

      return `
        <div class="py-8 space-y-4">
          <div class="w-16 h-16 rounded-3xl bg-amber-50 dark:bg-amber-950/50 text-amber-600 dark:text-amber-400 flex items-center justify-center text-3xl mx-auto shadow-inner animate-pulse">
            ♟️
          </div>
          <div class="space-y-1.5">
            <h3 class="text-sm font-black text-slate-800 dark:text-white">Вызов отправлен: ${escapeHtml(oppName)}</h3>
            <div>${colorBadge}</div>
            <p class="text-[11px] text-slate-400 max-w-xs mx-auto pt-1">
              Бот отправил однокласснику приглашение с кнопкой входа. Ждем, пока он нажмет «Принять вызов»...
            </p>
          </div>
          <button
            onclick="window.GAMES.cancelChessGame()"
            class="px-4 py-2 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 font-bold text-xs transition-all active:scale-95">
            ❌ Отменить вызов
          </button>
        </div>
      `;
    }

    if (chessState === "rejected") {
      return `
        <div class="py-8 space-y-3">
          <div class="text-4xl">❌</div>
          <h3 class="text-sm font-black text-slate-800 dark:text-white">Вызов отклонен или отменен</h3>
          <p class="text-xs text-slate-400">Соперник не смог сыграть партию в этот раз.</p>
          <button
            onclick="window.GAMES.backToChessLobby()"
            class="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow-sm transition-all active:scale-95">
            🔙 Вернуться к списку
          </button>
        </div>
      `;
    }

    if (chessState === "playing" || chessState === "finished") {
      const yourRole = chessRoomData?.your_role; // 'white' | 'black' | null
      let isFlipped = false;
      if (chessIsLocal) {
        if (chessLocalAutoRotate) {
          isFlipped = (chessRoomData?.turn === "black");
          if (chessManualFlipped) isFlipped = !isFlipped;
        } else {
          isFlipped = chessManualFlipped;
        }
      } else {
        isFlipped = (yourRole === "black");
      }

      const isYourTurn = chessIsLocal ? (chessState === "playing") : chessRoomData?.is_your_turn;
      const isFinished = chessState === "finished";
      const board = parseFen(chessRoomData?.fen);

      const whiteName = chessRoomData?.white?.name || "Белые";
      const blackName = chessRoomData?.black?.name || "Черные";

      const oppName = isFlipped ? whiteName : blackName;
      const oppRole = isFlipped ? "white" : "black";
      const myName = isFlipped ? blackName : whiteName;
      const myRole = isFlipped ? "black" : "white";

      const oppCaptured = (isFlipped ? chessRoomData?.captured_pieces?.by_white : chessRoomData?.captured_pieces?.by_black) || [];
      const myCaptured = (isFlipped ? chessRoomData?.captured_pieces?.by_black : chessRoomData?.captured_pieces?.by_white) || [];

      let statusHTML = "";
      if (isFinished) {
        const winner = chessRoomData?.winner;
        const reason = chessRoomData?.termination_reason;
        if (winner === "draw") {
          let reasonText = "Ничья";
          if (reason === "stalemate") reasonText = "Пат (Ничья)";
          else if (reason === "insufficient_material") reasonText = "Недостаточно фигур";
          else if (reason === "repetition") reasonText = "Троекратное повторение";
          else if (reason === "fifty_moves") reasonText = "Правило 50 ходов";
          statusHTML = `<div class="p-2.5 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-600 dark:text-amber-400 text-xs font-extrabold">🤝 ${reasonText}! Боевая ничья!</div>`;
        } else if (chessIsLocal) {
          const winnerText = winner === "white" ? "Белые ⚪" : "Черные ⚫";
          const reasonText = reason === "resignation" ? "сдачей" : (reason === "checkmate" ? "матом" : "победа");
          statusHTML = `<div class="p-2.5 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400 text-xs font-extrabold animate-pulse">🏆 ПОБЕДА: ${winnerText} (${reasonText})!</div>`;
        } else if (winner === yourRole) {
          const reasonText = reason === "resignation" ? "Соперник сдался" : "Мат сопернику";
          statusHTML = `<div class="p-2.5 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400 text-xs font-extrabold animate-pulse">🏆 ПОБЕДА! ${reasonText}!</div>`;
        } else {
          const reasonText = reason === "resignation" ? "Вы сдались" : "Вам поставлен мат";
          statusHTML = `<div class="p-2.5 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-400 text-xs font-extrabold">😔 Поражение (${reasonText})</div>`;
        }
      } else {
        if (chessRoomData?.is_check) {
          const target = chessRoomData.turn === "white" ? "Белому королю" : "Черному королю";
          statusHTML = `<div class="p-2 rounded-xl bg-rose-500/15 border border-rose-500/40 text-rose-600 dark:text-rose-400 text-xs font-black animate-pulse">⚠️ ШАХ ${target}!</div>`;
        } else {
          if (chessIsLocal) {
            const turnName = chessRoomData.turn === "white" ? "Белые ⚪" : "Черные ⚫";
            statusHTML = `<div class="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400 text-xs font-extrabold">🟢 Ходят: ${turnName}</div>`;
          } else if (isYourTurn) {
            statusHTML = `<div class="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400 text-xs font-extrabold animate-pulse">🟢 Твой ход (${yourRole === 'white' ? 'Белые ♔' : 'Черные ♚'})</div>`;
          } else {
            statusHTML = `<div class="p-2 rounded-xl bg-slate-100 dark:bg-slate-700/60 text-slate-500 dark:text-slate-400 text-xs font-bold">⏳ Ход соперника (${oppName})...</div>`;
          }
        }
      }

      const legalMovesForSelected = chessSelectedSquare
        ? (chessRoomData?.legal_moves || []).filter(m => m.startsWith(chessSelectedSquare))
        : [];
      const legalTargetSquares = new Set(legalMovesForSelected.map(m => m.slice(2, 4)));

      const lastMove = chessRoomData?.last_move || "";
      const lastMoveFrom = lastMove.slice(0, 2);
      const lastMoveTo = lastMove.slice(2, 4);

      const rRange = isFlipped ? [7, 6, 5, 4, 3, 2, 1, 0] : [0, 1, 2, 3, 4, 5, 6, 7];
      const cRange = isFlipped ? [7, 6, 5, 4, 3, 2, 1, 0] : [0, 1, 2, 3, 4, 5, 6, 7];

      return `
        <!-- Local Mode Rotation Controls -->
        ${chessIsLocal ? `
          <div class="flex items-center justify-between p-2 rounded-2xl bg-amber-500/10 border border-amber-500/25 text-[11px] font-bold">
            <span class="text-amber-700 dark:text-amber-300 flex items-center gap-1.5">
              <span>👥</span> 1 телефон (2 игрока)
            </span>
            <div class="flex items-center gap-1">
              <button
                type="button"
                onclick="window.GAMES.toggleChessAutoRotate()"
                title="Автоматически поворачивать доску к игроку, чей сейчас ход"
                class="px-2 py-1 rounded-xl text-[10px] font-bold transition-all flex items-center gap-1 ${
                  chessLocalAutoRotate
                    ? 'bg-amber-600 text-white shadow-sm'
                    : 'bg-white dark:bg-slate-700 text-slate-500'
                }">
                <span>🔄 Автоповорот:</span>
                <span>${chessLocalAutoRotate ? 'ВКЛ' : 'ВЫКЛ'}</span>
              </button>
              <button
                type="button"
                onclick="window.GAMES.flipChessBoardManual()"
                title="Перевернуть доску на 180°"
                class="p-1 px-2 rounded-xl bg-white dark:bg-slate-700 hover:bg-slate-100 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 text-[10px] font-bold shadow-sm transition-all active:scale-95 flex items-center gap-1">
                <span>↕️</span> Повернуть
              </button>
            </div>
          </div>
        ` : ''}

        <!-- Top Player Bar -->
        <div class="flex items-center justify-between p-2 rounded-2xl bg-slate-100 dark:bg-slate-700/60 text-xs font-bold">
          <div class="flex items-center gap-1.5 min-w-0 pr-1">
            <span class="w-6 h-6 rounded-lg ${oppRole === 'white' ? 'bg-amber-100 text-amber-900 border border-amber-300' : 'bg-slate-800 text-white border border-slate-600'} flex items-center justify-center font-black text-xs shrink-0">
              ${oppRole === 'white' ? '♔' : '♚'}
            </span>
            <div class="text-left truncate">
              <div class="truncate text-slate-800 dark:text-white flex items-center gap-1">
                <span>${escapeHtml(oppName)}</span>
                ${chessIsLocal && chessRoomData?.turn === oppRole && !isFinished ? '<span class="text-emerald-600 dark:text-emerald-400 font-black text-[10px] uppercase tracking-wider">(Ходит)</span>' : ''}
              </div>
              <div class="text-[10px] text-slate-400 font-normal tracking-tight">
                ${oppCaptured.length > 0 ? oppCaptured.map(p => CHESS_SYMBOLS[p] || p).join(' ') : 'Без взятий'}
              </div>
            </div>
          </div>
          ${!isFinished && !chessIsLocal && !isYourTurn ? '<span class="text-[10px] text-amber-500 font-black animate-pulse uppercase">Думает...</span>' : ''}
        </div>

        <!-- Status / Turn Banner -->
        ${statusHTML}

        <!-- 8x8 Chess Board -->
        <div class="w-full max-w-[320px] aspect-square mx-auto rounded-2xl overflow-hidden shadow-lg border-2 border-amber-950/40 select-none grid grid-cols-8 grid-rows-8 relative transition-all duration-300" style="touch-action: manipulation;">
          ${rRange.map(r => cRange.map(c => {
            const sq = rcToSquare(r, c);
            const piece = board[r][c];
            const isLight = (r + c) % 2 === 0;
            const isSelected = sq === chessSelectedSquare;
            const isLastMove = sq === lastMoveFrom || sq === lastMoveTo;
            const isLegalTarget = legalTargetSquares.has(sq);

            const isKingInCheck = chessRoomData?.is_check && (
              (chessRoomData.turn === "white" && piece === "K") ||
              (chessRoomData.turn === "black" && piece === "k")
            );

            let bgStyle = isLight ? "background-color: #f0d9b5;" : "background-color: #b58863;";
            if (isSelected) {
              bgStyle = "background-color: #cdd26a !important;";
            } else if (isKingInCheck) {
              bgStyle = "background: radial-gradient(circle, #ef4444 0%, #dc2626 70%, #991b1b 100%) !important;";
            } else if (isLastMove) {
              bgStyle = isLight ? "background-color: #d8ce66;" : "background-color: #aaa23a;";
            }

            return `
              <button
                id="chess-sq-${sq}"
                type="button"
                onclick="window.GAMES.chessSquareClick('${sq}')"
                style="${bgStyle}"
                class="w-full h-full p-0 m-0 relative flex items-center justify-center cursor-pointer transition-colors group">
                
                ${(c === (isFlipped ? 7 : 0)) ? `
                  <span class="absolute top-0.5 left-0.5 text-[8px] font-bold pointer-events-none opacity-60 ${isLight ? 'text-[#b58863]' : 'text-[#f0d9b5]'}">
                    ${8 - r}
                  </span>
                ` : ''}
                ${(r === (isFlipped ? 0 : 7)) ? `
                  <span class="absolute bottom-0 right-0.5 text-[8px] font-bold pointer-events-none opacity-60 ${isLight ? 'text-[#b58863]' : 'text-[#f0d9b5]'}">
                    ${CHESS_FILES[c]}
                  </span>
                ` : ''}

                ${renderChessPiece(piece)}

                ${isLegalTarget ? (
                  piece !== "" ? `
                    <div class="absolute inset-0.5 rounded-full border-2 border-rose-500/80 pointer-events-none animate-pulse"></div>
                  ` : `
                    <div class="w-3 h-3 rounded-full bg-emerald-600/60 pointer-events-none shadow-sm"></div>
                  `
                ) : ''}
              </button>
            `;
          }).join('')).join('')}
        </div>

        <!-- Pawn Promotion Picker Modal (if applicable) -->
        ${chessPendingPromotion ? `
          <div class="p-2.5 rounded-2xl bg-amber-50 dark:bg-amber-950/60 border border-amber-200 dark:border-amber-800 space-y-2">
            <div class="text-xs font-black text-amber-800 dark:text-amber-200">Превращение пешки в:</div>
            <div class="flex items-center justify-center gap-2">
              <button onclick="window.GAMES.choosePromotion('q')" class="w-10 h-10 rounded-xl bg-white dark:bg-slate-700 shadow border text-2xl font-black active:scale-95">♕</button>
              <button onclick="window.GAMES.choosePromotion('r')" class="w-10 h-10 rounded-xl bg-white dark:bg-slate-700 shadow border text-2xl font-black active:scale-95">♖</button>
              <button onclick="window.GAMES.choosePromotion('b')" class="w-10 h-10 rounded-xl bg-white dark:bg-slate-700 shadow border text-2xl font-black active:scale-95">♗</button>
              <button onclick="window.GAMES.choosePromotion('n')" class="w-10 h-10 rounded-xl bg-white dark:bg-slate-700 shadow border text-2xl font-black active:scale-95">♘</button>
            </div>
          </div>
        ` : ''}

        <!-- Bottom Player Bar -->
        <div class="flex items-center justify-between p-2 rounded-2xl bg-slate-100 dark:bg-slate-700/60 text-xs font-bold">
          <div class="flex items-center gap-1.5 min-w-0 pr-1">
            <span class="w-6 h-6 rounded-lg ${myRole === 'white' ? 'bg-amber-100 text-amber-900 border border-amber-300' : 'bg-slate-800 text-white border border-slate-600'} flex items-center justify-center font-black text-xs shrink-0">
              ${myRole === 'white' ? '♔' : '♚'}
            </span>
            <div class="text-left truncate">
              <div class="truncate text-slate-800 dark:text-white flex items-center gap-1">
                <span>${escapeHtml(myName)}</span>
                ${chessIsLocal ? (chessRoomData?.turn === myRole && !isFinished ? '<span class="text-emerald-600 dark:text-emerald-400 font-black text-[10px] uppercase tracking-wider">(Ходит)</span>' : '') : '(Вы)'}
              </div>
              <div class="text-[10px] text-slate-400 font-normal tracking-tight">
                ${myCaptured.length > 0 ? myCaptured.map(p => CHESS_SYMBOLS[p] || p).join(' ') : 'Без взятий'}
              </div>
            </div>
          </div>
          ${!isFinished ? `
            <button
              onclick="window.GAMES.resignChessGame()"
              class="px-2.5 py-1 rounded-lg text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/30 text-xs font-bold transition-all">
              🏳️ Сдаться
            </button>
          ` : ''}
        </div>

        <!-- Actions (Finished) -->
        ${isFinished ? `
          <div class="space-y-2 pt-1">
            ${chessIsLocal ? `
              <button
                onclick="window.GAMES.requestChessRematch()"
                class="w-full py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 active:scale-95 text-white font-black text-xs shadow-md transition-all flex items-center justify-center gap-1.5">
                <span>🔄</span> Сыграть новую партию
              </button>
            ` : (chessRoomData?.rematch_requested_by ? `
              ${chessRoomData.rematch_requested_by === yourRole ? `
                <div class="p-2.5 rounded-xl bg-slate-100 dark:bg-slate-700 text-xs font-bold text-slate-500 flex items-center justify-center gap-1.5">
                  <span class="animate-spin">⏳</span> Ждем согласие соперника на реванш...
                </div>
              ` : `
                <button
                  onclick="window.GAMES.requestChessRematch()"
                  class="w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 active:scale-95 text-white font-black text-xs shadow-md transition-all flex items-center justify-center gap-1.5">
                  <span>🔥</span> Соперник ждет реванш! Принять бой
                </button>
              `}
            ` : `
              <button
                onclick="window.GAMES.requestChessRematch()"
                class="w-full py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 active:scale-95 text-white font-black text-xs shadow-md transition-all flex items-center justify-center gap-1.5">
                <span>🔄</span> Предложить реванш (смена цвета)
              </button>
            `)}
            <button
              onclick="window.GAMES.leaveChessGame()"
              class="w-full py-2 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-700 text-slate-500 font-bold text-xs transition-all active:scale-95">
              🚪 Выйти в лобби
            </button>
          </div>
        ` : ''}
      `;
    }

    // Default: Lobby
    return `
      <div class="space-y-3">
        <!-- Local Mode: 2 Players on 1 Phone -->
        <div class="p-3 rounded-2xl bg-gradient-to-r from-amber-500/15 via-orange-500/10 to-amber-500/15 border border-amber-500/30 text-left space-y-2 shadow-sm">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-1.5 font-black text-xs text-slate-800 dark:text-white">
              <span class="text-base">👥</span>
              <span>Режим на 2 на 1 телефоне</span>
            </div>
            <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500 text-white shadow-sm">Оффлайн</span>
          </div>
          <p class="text-[11px] text-slate-500 dark:text-slate-400">
            Сыграйте партию вдвоем на одном экране на перемене. Экран будет автоматически поворачиваться к тому, чей сейчас ход!
          </p>
          <button
            type="button"
            onclick="window.GAMES.startLocalChessGame()"
            class="w-full py-2.5 rounded-xl bg-amber-600 hover:bg-amber-700 active:scale-95 text-white font-black text-xs shadow-md transition-all flex items-center justify-center gap-1.5">
            <span>⚔️</span> Начать игру на одном телефоне
          </button>
        </div>

        <div class="relative flex py-1 items-center">
          <div class="flex-grow border-t border-slate-200 dark:border-slate-700"></div>
          <span class="flex-shrink mx-2 text-[10px] font-bold text-slate-400 uppercase tracking-wider">или онлайн-дуэль</span>
          <div class="flex-grow border-t border-slate-200 dark:border-slate-700"></div>
        </div>

        <div class="text-left px-1 space-y-0.5">
          <h3 class="text-xs font-black text-slate-800 dark:text-white flex items-center gap-1">
            <span>♟️</span> Шахматная онлайн-дуэль
          </h3>
          <p class="text-[11px] text-slate-400">
            Бот мгновенно пришлет однокласснику в Telegram кнопку входа в игру
          </p>
        </div>

        <!-- Color Selector: White / Random / Black -->
        <div class="p-2.5 rounded-2xl bg-slate-50 dark:bg-slate-700/40 border border-slate-200/80 dark:border-slate-700 space-y-1.5">
          <div class="text-left text-[11px] font-bold text-slate-600 dark:text-slate-300 flex items-center justify-between">
            <span>Выбор цвета:</span>
            <span class="text-[10px] font-medium text-amber-600 dark:text-amber-400">
              ${chessSelectedColor === 'white' ? 'Белые (ходишь первым)' : (chessSelectedColor === 'black' ? 'Черные (ходишь вторым)' : 'Случайный (50/50)')}
            </span>
          </div>
          <div class="grid grid-cols-3 gap-1.5">
            <button
              onclick="window.GAMES.setChessColor('white')"
              class="py-2 px-1 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-1 active:scale-95 ${
                chessSelectedColor === 'white'
                  ? 'bg-white dark:bg-slate-600 text-slate-900 dark:text-white shadow-md border-2 border-amber-500 font-black'
                  : 'bg-white/60 dark:bg-slate-700/60 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-600 hover:bg-white dark:hover:bg-slate-600'
              }">
              <span class="text-base leading-none">⚪</span>
              <span>Белый</span>
            </button>
            <button
              onclick="window.GAMES.setChessColor('random')"
              class="py-2 px-1 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-1 active:scale-95 ${
                chessSelectedColor === 'random'
                  ? 'bg-white dark:bg-slate-600 text-slate-900 dark:text-white shadow-md border-2 border-amber-500 font-black'
                  : 'bg-white/60 dark:bg-slate-700/60 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-600 hover:bg-white dark:hover:bg-slate-600'
              }">
              <span class="text-base leading-none">🎲</span>
              <span>Случайно</span>
            </button>
            <button
              onclick="window.GAMES.setChessColor('black')"
              class="py-2 px-1 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-1 active:scale-95 ${
                chessSelectedColor === 'black'
                  ? 'bg-white dark:bg-slate-600 text-slate-900 dark:text-white shadow-md border-2 border-amber-500 font-black'
                  : 'bg-white/60 dark:bg-slate-700/60 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-600 hover:bg-white dark:hover:bg-slate-600'
              }">
              <span class="text-base leading-none">⚫</span>
              <span>Черный</span>
            </button>
          </div>
        </div>

        <!-- Search & Refresh -->
        <div class="flex items-center gap-1.5">
          <input
            type="text"
            id="chess-classmate-input"
            value="${escapeHtml(chessClassmatesFilter)}"
            oninput="window.GAMES.filterChessClassmates(this.value)"
            placeholder="🔍 Поиск одноклассника..."
            class="flex-1 px-3 py-2 rounded-xl bg-slate-100 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500">
          <button
            onclick="window.GAMES.refreshChessClassmates()"
            title="Обновить"
            class="p-2 rounded-xl bg-slate-100 dark:bg-slate-700 text-slate-500 hover:text-slate-800 dark:hover:text-white transition-all active:scale-95">
            🔄
          </button>
        </div>

        <!-- Classmates List Container -->
        <div id="chess-classmates-wrapper">
          ${isChessLoadingClassmates ? `
            <div class="py-8 text-center text-xs text-slate-400 space-y-2">
              <div class="w-6 h-6 border-2 border-amber-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
              <span>Загрузка одноклассников...</span>
            </div>
          ` : renderChessClassmatesListHTML()}
        </div>
      </div>
    `;
  }

  function renderChessClassmatesListHTML() {
    const q = (chessClassmatesFilter || "").toLowerCase().trim();
    const filtered = chessClassmatesList.filter(c => {
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
      <div id="chess-classmates-container" class="space-y-1.5 max-h-56 overflow-y-auto pr-1">
        ${filtered.map(c => {
          const name = c.name || c.full_name || "Одноклассник";
          const initial = name.charAt(0).toUpperCase();
          return `
            <div class="flex items-center justify-between p-2 rounded-2xl bg-slate-50 dark:bg-slate-700/50 border border-slate-200/60 dark:border-slate-700 hover:border-amber-400 dark:hover:border-amber-500/50 transition-all">
              <div class="flex items-center gap-2 min-w-0 pr-2">
                <div class="w-7 h-7 rounded-full bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300 font-black text-xs flex items-center justify-center shrink-0">
                  ${initial}
                </div>
                <div class="truncate text-left">
                  <div class="text-xs font-bold text-slate-800 dark:text-white truncate">${escapeHtml(name)}</div>
                  <div class="text-[10px] text-slate-400">11 «Б»</div>
                </div>
              </div>
              <button
                onclick="window.GAMES.inviteChessClassmate(${c.tg_id}, '${escapeHtml(name)}')"
                class="shrink-0 px-3 py-1.5 rounded-xl font-black text-xs bg-amber-600 hover:bg-amber-700 active:scale-95 text-white shadow-sm transition-all flex items-center gap-1">
                <span>♟️</span> Вызвать
              </button>
            </div>
          `;
        }).join("")}
      </div>
    `;
  }

  async function loadChessClassmates() {
    if (isChessLoadingClassmates) return;
    isChessLoadingClassmates = true;

    const wrapper = document.getElementById("chess-classmates-wrapper");
    if (wrapper) {
      wrapper.innerHTML = `
        <div class="py-8 text-center text-xs text-slate-400 space-y-2">
          <div class="w-6 h-6 border-2 border-amber-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <span>Загрузка одноклассников...</span>
        </div>
      `;
    }

    try {
      chessClassmatesList = await api.getClassmates();
    } catch (e) {
      console.warn("Could not load classmates for chess:", e);
      chessClassmatesList = [];
    } finally {
      isChessLoadingClassmates = false;
      const w = document.getElementById("chess-classmates-wrapper");
      if (w) {
        w.innerHTML = renderChessClassmatesListHTML();
      }
    }
  }

  function filterChessClassmates(val) {
    chessClassmatesFilter = val;
    const wrapper = document.getElementById("chess-classmates-wrapper");
    if (wrapper) {
      wrapper.innerHTML = renderChessClassmatesListHTML();
    }
  }

  async function inviteChessClassmate(tgId, oppName) {
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
      if (room.status === "finished") {
        chessState = "finished";
      } else if (room.status === "waiting") {
        chessState = "waiting";
      } else {
        chessState = "playing";
      }
      renderGames();
      startChessPolling();
    } catch (e) {
      console.error("Failed to join chess online room:", e);
      chessState = "rejected";
      renderGames();
    }
  }

  function chessSquareClick(sq) {
    if (!chessRoomData || chessRoomData.status !== "playing") return;
    if (!chessRoomData.is_your_turn) return;

    const board = parseFen(chessRoomData.fen);
    const { r, c } = squareToRC(sq);
    const piece = board[r][c];
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
        if (window.Telegram?.WebApp?.HapticFeedback) {
          window.Telegram.WebApp.HapticFeedback.selectionChanged();
        }
        renderGames();
        return;
      }

      chessSelectedSquare = null;
      renderGames();
      return;
    }

    if (isMyPiece) {
      chessSelectedSquare = sq;
      if (window.Telegram?.WebApp?.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.selectionChanged();
      }
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
    if (window.Telegram?.WebApp?.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.impactOccurred("light");
    }

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

  async function cancelChessGame() {
    if (chessRoomId) {
      try {
        await api.cancelGame(chessRoomId);
      } catch (e) {}
    }
    stopChessPolling();
    chessRoomId = null;
    chessRoomData = null;
    chessIsLocal = false;
    chessManualFlipped = false;
    chessState = "lobby";
    renderGames();
  }

  function leaveChessGame() {
    stopChessPolling();
    chessRoomId = null;
    chessRoomData = null;
    chessIsLocal = false;
    chessManualFlipped = false;
    chessState = "lobby";
    renderGames();
  }

  function backToChessLobby() {
    stopChessPolling();
    chessRoomId = null;
    chessRoomData = null;
    chessIsLocal = false;
    chessManualFlipped = false;
    chessState = "lobby";
    loadChessClassmates();
  }

  function startChessPolling() {
    if (chessIsLocal) return; // No polling needed for local games
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
    if (!isChessPolling || !chessRoomId || chessIsLocal) return;

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
    const oldStatus = chessRoomData ? chessRoomData.status : null;
    const oldFen = chessRoomData ? chessRoomData.fen : null;
    const oldRematch = chessRoomData ? chessRoomData.rematch_requested_by : null;

    chessRoomData = data;

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
        if (window.Telegram?.WebApp?.HapticFeedback) {
          window.Telegram.WebApp.HapticFeedback.impactOccurred("light");
        }
      }
      return;
    }

    if (data.status === "finished") {
      if (chessState !== "finished") {
        chessState = "finished";
        renderGames();
        if (window.Telegram?.WebApp?.HapticFeedback) {
          if (chessIsLocal || data.winner === data.your_role) {
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

  window.GAMES_CHESS = {
    renderHTML: renderChessHTML,
    init: initChess,
    cleanup: function() {
      stopChessPolling();
    },
    startLocalChessGame: startLocalChessGame,
    toggleChessAutoRotate: toggleChessAutoRotate,
    flipChessBoardManual: flipChessBoardManual,
    openChessOnlineRoom: openChessOnlineRoom,
    inviteChessClassmate: inviteChessClassmate,
    chessSquareClick: chessSquareClick,
    choosePromotion: choosePromotion,
    resignChessGame: resignChessGame,
    requestChessRematch: requestChessRematch,
    cancelChessGame: cancelChessGame,
    leaveChessGame: leaveChessGame,
    backToChessLobby: backToChessLobby,
    filterChessClassmates: filterChessClassmates,
    loadChessClassmates: loadChessClassmates,
    setChessColor: setChessColor
  };
})();
