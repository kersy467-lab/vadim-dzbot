// frontend/js/games/chess/chess_ui.js
(function() {
  'use strict';

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function renderLobbyHTML(props) {
    const {
      chessSelectedColor,
      chessClassmatesFilter,
      isChessLoadingClassmates,
      chessClassmatesList
    } = props;

    return `
      <div class="space-y-3.5">
        <div class="text-left px-1">
          <h2 class="text-base font-black text-slate-800 dark:text-white flex items-center gap-1.5">
            <span>♟️</span> Шахматы
          </h2>
          <p class="text-xs text-slate-400">Сыграй против умного ИИ, на одном телефоне или брось вызов однокласснику</p>
        </div>

        <!-- 1. Игра против бота (ИИ) -->
        <div class="p-3 rounded-2xl bg-gradient-to-br from-amber-500/10 via-amber-600/5 to-slate-100 dark:to-slate-800/80 border border-amber-500/30 text-left space-y-2.5">
          <div class="flex items-center justify-between">
            <span class="text-xs font-black text-amber-700 dark:text-amber-400 flex items-center gap-1.5">
              <span>🤖</span> Игра против бота
            </span>
            <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-700 dark:text-amber-300 border border-amber-500/30">
              ⚡ Minimax 3 шага
            </span>
          </div>
          <p class="text-[11px] text-slate-500 dark:text-slate-400">
            ИИ с альфа-бета отсечением, позиционной оценкой и защитой от зацикливания ходов.
          </p>
          <div class="grid grid-cols-3 gap-1.5 pt-0.5">
            ${[
              { id: 'white', icon: '⚪', label: 'Белый' },
              { id: 'random', icon: '🎲', label: 'Случайно' },
              { id: 'black', icon: '⚫', label: 'Черный' }
            ].map(c => `
              <button onclick="(window.GAMES_CHESS || window.GAMES).setChessColor('${c.id}')" class="py-1.5 px-1 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-1 active:scale-95 ${chessSelectedColor === c.id ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow border-2 border-amber-500 font-black' : 'bg-white/60 dark:bg-slate-700/60 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-600 hover:bg-white'}">
                <span>${c.icon}</span> ${c.label}
              </button>
            `).join('')}
          </div>
          <button
            onclick="(window.GAMES_CHESS || window.GAMES).startBotChessGame()"
            class="w-full py-2.5 rounded-xl bg-gradient-to-r from-amber-600 to-amber-700 hover:from-amber-700 hover:to-amber-800 active:scale-95 text-white font-black text-xs shadow-md transition-all flex items-center justify-center gap-1.5">
            <span>⚔️</span> Сыграть с ботом
          </button>
        </div>

        <!-- 2. Локальный режим на 2 игрока -->
        <div class="p-3 rounded-2xl bg-slate-50 dark:bg-slate-700/40 border border-slate-200/80 dark:border-slate-700 text-left space-y-2">
          <div class="text-xs font-black text-slate-800 dark:text-white flex items-center gap-1.5">
            <span>👥</span> 1 телефон (2 игрока)
          </div>
          <p class="text-[11px] text-slate-400">Играйте вдвоем на одном смартфоне с автоповоротом доски</p>
          <button
            onclick="(window.GAMES_CHESS || window.GAMES).startLocalChessGame()"
            class="w-full py-2.5 rounded-xl bg-slate-800 hover:bg-slate-900 active:scale-95 text-white font-black text-xs shadow-sm transition-all flex items-center justify-center gap-1.5">
            <span>⚔️</span> Игра на одном телефоне
          </button>
        </div>

        <!-- 3. Онлайн-дуэль -->
        <div class="text-left px-1 pt-1 space-y-0.5">
          <h3 class="text-xs font-black text-slate-800 dark:text-white flex items-center gap-1">
            <span>♟️</span> Онлайн-дуэль с одноклассником
          </h3>
          <p class="text-[11px] text-slate-400">Бот мгновенно отправит вызов в Telegram</p>
        </div>

        <div class="flex items-center gap-1.5">
          <input
            type="text"
            id="chess-classmate-input"
            value="${escapeHtml(chessClassmatesFilter)}"
            oninput="(window.GAMES_CHESS || window.GAMES).filterChessClassmates(this.value)"
            placeholder="🔍 Поиск одноклассника..."
            class="flex-1 px-3 py-2 rounded-xl bg-slate-100 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 text-xs focus:outline-none focus:ring-2 focus:ring-amber-500">
          <button
            onclick="(window.GAMES_CHESS || window.GAMES).refreshChessClassmates()"
            title="Обновить"
            class="p-2 rounded-xl bg-slate-100 dark:bg-slate-700 text-slate-500 hover:text-slate-800 dark:hover:text-white transition-all active:scale-95">
            🔄
          </button>
        </div>

        <div id="chess-classmates-wrapper">
          ${isChessLoadingClassmates ? `
            <div class="py-6 text-center text-xs text-slate-400 space-y-2">
              <div class="w-6 h-6 border-2 border-amber-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
              <span>Загрузка одноклассников...</span>
            </div>
          ` : renderClassmatesList(chessClassmatesList, chessClassmatesFilter)}
        </div>
      </div>
    `;
  }

  function renderClassmatesList(list, filter) {
    const q = (filter || "").toLowerCase().trim();
    const filtered = (list || []).filter(c => {
      const name = (c.name || c.full_name || "").toLowerCase();
      return !q || name.includes(q);
    });

    if (filtered.length === 0) {
      return `
        <div class="py-6 text-center text-xs text-slate-400">
          ${q ? "Никого не найдено по запросу" : "Одноклассники не найдены"}
        </div>
      `;
    }

    return `
      <div id="chess-classmates-container" class="space-y-1.5 max-h-52 overflow-y-auto pr-1">
        ${filtered.map(c => {
          const name = c.name || c.full_name || "Одноклассник";
          const initial = name.charAt(0).toUpperCase();
          return `
            <div class="flex items-center justify-between p-2 rounded-2xl bg-slate-50 dark:bg-slate-700/50 border border-slate-200/60 dark:border-slate-700 hover:border-amber-400 transition-all">
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
                onclick="(window.GAMES_CHESS || window.GAMES).inviteChessClassmate(${c.tg_id}, '${escapeHtml(name)}')"
                class="shrink-0 px-3 py-1.5 rounded-xl font-black text-xs bg-amber-600 hover:bg-amber-700 active:scale-95 text-white shadow-sm transition-all flex items-center gap-1">
                <span>⚔️</span> Вызов
              </button>
            </div>
          `;
        }).join("")}
      </div>
    `;
  }

  function renderStatusBanner(roomData, isYourTurn, isLocal, isBot, yourRole) {
    if (!roomData) return "";
    const isFinished = roomData.status === "finished";

    if (isFinished) {
      const winner = roomData.winner;
      const reason = roomData.termination_reason;
      if (winner === "draw") {
        let reasonText = "Ничья";
        if (reason === "stalemate") reasonText = "Пат (Ничья)";
        else if (reason === "insufficient_material") reasonText = "Недостаточно фигур";
        else if (reason === "repetition") reasonText = "Троекратное повторение";
        else if (reason === "fifty_moves") reasonText = "Правило 50 ходов";
        return `<div class="p-2.5 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-600 dark:text-amber-400 text-xs font-extrabold">🤝 ${reasonText}! Боевая ничья!</div>`;
      }
      if (isLocal) {
        const winnerText = winner === "white" ? "Белые ⚪" : "Черные ⚫";
        const reasonText = reason === "resignation" ? "сдачей" : (reason === "checkmate" ? "матом" : "победа");
        return `<div class="p-2.5 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400 text-xs font-extrabold animate-pulse">🏆 ПОБЕДА: ${winnerText} (${reasonText})!</div>`;
      }
      if (winner === yourRole) {
        const reasonText = reason === "resignation" ? "Соперник сдался" : "Мат сопернику";
        return `<div class="p-2.5 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400 text-xs font-extrabold animate-pulse">🏆 ПОБЕДА! ${reasonText}!</div>`;
      }
      const reasonText = reason === "resignation" ? "Вы сдались" : "Вам поставлен мат";
      return `<div class="p-2.5 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-400 text-xs font-extrabold">😔 Поражение (${reasonText})</div>`;
    }

    if (roomData.is_check) {
      const target = roomData.turn === "white" ? "Белому королю" : "Черному королю";
      return `<div class="p-2 rounded-xl bg-rose-500/15 border border-rose-500/40 text-rose-600 dark:text-rose-400 text-xs font-black animate-pulse">⚠️ ШАХ ${target}!</div>`;
    }

    if (isLocal) {
      const turnName = roomData.turn === "white" ? "Белые ⚪" : "Черные ⚫";
      return `<div class="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400 text-xs font-extrabold">🟢 Ходят: ${turnName}</div>`;
    }

    if (isYourTurn) {
      const roleStr = yourRole === 'white' ? 'Белые ♔' : 'Черные ♚';
      return `<div class="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400 text-xs font-extrabold animate-pulse">🟢 Твой ход (${roleStr})</div>`;
    }

    const oppLabel = isBot ? "🤖 Бот думает..." : "⏳ Ход соперника...";
    return `<div class="p-2 rounded-xl bg-slate-100 dark:bg-slate-700/60 text-slate-500 dark:text-slate-400 text-xs font-bold">${oppLabel}</div>`;
  }

  function renderChessContentHTML(props) {
    const {
      chessState,
      chessRoomData,
      chessOpponentName,
      chessIsLocal,
      chessIsBot,
      chessLocalAutoRotate,
      chessManualFlipped,
      chessSelectedSquare,
      chessPendingPromotion
    } = props;

    if (chessState === "loading") {
      return `
        <div class="py-12 space-y-3">
          <div class="w-10 h-10 border-4 border-amber-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p class="text-xs font-bold text-slate-500">Подключение к шахматной партии...</p>
        </div>
      `;
    }

    if (chessState === "waiting") {
      const opp = chessOpponentName || chessRoomData?.black?.name || "Одноклассник";
      return `
        <div class="py-8 space-y-4">
          <div class="w-16 h-16 rounded-3xl bg-amber-50 dark:bg-amber-950/50 text-amber-600 dark:text-amber-400 flex items-center justify-center text-3xl mx-auto shadow-inner animate-pulse">♟️</div>
          <div class="space-y-1">
            <h3 class="text-sm font-black text-slate-800 dark:text-white">Вызов отправлен: ${escapeHtml(opp)}</h3>
            <p class="text-[11px] text-slate-400">Ждем, пока соперник примет вызов в Telegram...</p>
          </div>
          <button onclick="(window.GAMES_CHESS || window.GAMES).cancelChessGame()" class="px-4 py-2 rounded-xl bg-rose-500/10 text-rose-600 font-bold text-xs active:scale-95">❌ Отменить вызов</button>
        </div>
      `;
    }

    if (chessState === "rejected") {
      return `
        <div class="py-8 space-y-3">
          <div class="text-4xl">❌</div>
          <h3 class="text-sm font-black text-slate-800 dark:text-white">Вызов отклонен или отменен</h3>
          <button onclick="(window.GAMES_CHESS || window.GAMES).leaveChessGame()" class="px-4 py-2 rounded-xl bg-amber-600 text-white font-bold text-xs shadow-sm active:scale-95">🔙 Вернуться к выбору</button>
        </div>
      `;
    }

    if (chessState === "playing" || chessState === "finished") {
      const yourRole = chessRoomData?.your_role;
      let isFlipped = false;
      if (chessIsLocal) {
        isFlipped = chessLocalAutoRotate ? (chessRoomData?.turn === "black") : chessManualFlipped;
        if (chessLocalAutoRotate && chessManualFlipped) isFlipped = !isFlipped;
      } else {
        isFlipped = (yourRole === "black");
      }

      const isYourTurn = chessIsLocal ? (chessState === "playing") : chessRoomData?.is_your_turn;
      const isFinished = chessState === "finished";
      const board = window.CHESS_BOARD ? window.CHESS_BOARD.parseFen(chessRoomData?.fen) : [];

      const whiteName = chessRoomData?.white?.name || "Белые";
      const blackName = chessRoomData?.black?.name || "Черные";
      const oppName = isFlipped ? whiteName : blackName;
      const oppRole = isFlipped ? "white" : "black";
      const myName = isFlipped ? blackName : whiteName;
      const myRole = isFlipped ? "black" : "white";

      const oppCaptured = (isFlipped ? chessRoomData?.captured_pieces?.by_white : chessRoomData?.captured_pieces?.by_black) || [];
      const myCaptured = (isFlipped ? chessRoomData?.captured_pieces?.by_black : chessRoomData?.captured_pieces?.by_white) || [];

      const legalMovesForSelected = chessSelectedSquare
        ? (chessRoomData?.legal_moves || []).filter(m => m.startsWith(chessSelectedSquare))
        : [];
      const legalTargetSquares = new Set(legalMovesForSelected.map(m => m.slice(2, 4)));

      const lastMove = chessRoomData?.last_move || "";
      const lastMoveFrom = lastMove.slice(0, 2);
      const lastMoveTo = lastMove.slice(2, 4);

      return `
        ${chessIsLocal ? `
          <div class="flex items-center justify-between p-2 rounded-2xl bg-amber-500/10 border border-amber-500/25 text-[11px] font-bold">
            <span class="text-amber-700 dark:text-amber-300 flex items-center gap-1.5">👥 1 телефон (2 игрока)</span>
            <div class="flex items-center gap-1">
              <button onclick="(window.GAMES_CHESS || window.GAMES).toggleChessAutoRotate()" class="px-2 py-1 rounded-xl text-[10px] font-bold ${chessLocalAutoRotate ? 'bg-amber-600 text-white shadow-sm' : 'bg-white dark:bg-slate-700 text-slate-500'}">🔄 Автоповорот: ${chessLocalAutoRotate ? 'ВКЛ' : 'ВЫКЛ'}</button>
              <button onclick="(window.GAMES_CHESS || window.GAMES).flipChessBoardManual()" class="px-2 py-1 rounded-xl bg-white dark:bg-slate-700 text-[10px] font-bold shadow-sm active:scale-95">↕️ Повернуть</button>
            </div>
          </div>
        ` : ''}

        <!-- Top Player Bar -->
        <div class="flex items-center justify-between p-2 rounded-2xl bg-slate-100 dark:bg-slate-700/60 text-xs font-bold">
          <div class="flex items-center gap-1.5 min-w-0 pr-1">
            <span class="w-6 h-6 rounded-lg ${oppRole === 'white' ? 'bg-amber-100 text-amber-900 border border-amber-300' : 'bg-slate-800 text-white border border-slate-600'} flex items-center justify-center font-black text-xs shrink-0">${oppRole === 'white' ? '♔' : '♚'}</span>
            <div class="text-left truncate">
              <div class="truncate text-slate-800 dark:text-white">${escapeHtml(oppName)}</div>
              <div class="text-[10px] text-slate-400">${oppCaptured.length > 0 ? oppCaptured.map(p => window.CHESS_BOARD?.CHESS_SYMBOLS[p] || p).join(' ') : 'Без взятий'}</div>
            </div>
          </div>
          ${!isFinished && !chessIsLocal && !isYourTurn ? '<span class="text-[10px] text-amber-500 font-black animate-pulse">Думает...</span>' : ''}
        </div>

        ${renderStatusBanner(chessRoomData, isYourTurn, chessIsLocal, chessIsBot, yourRole)}

        ${window.CHESS_BOARD ? window.CHESS_BOARD.renderBoardGrid({
          board,
          isFlipped,
          selectedSquare: chessSelectedSquare,
          legalTargetSquares,
          lastMoveFrom,
          lastMoveTo,
          chessRoomData
        }) : ''}

        <!-- Pawn Promotion Picker Modal -->
        ${chessPendingPromotion ? `
          <div class="p-2.5 rounded-2xl bg-amber-50 dark:bg-amber-950/60 border border-amber-200 dark:border-amber-800 space-y-2">
            <div class="text-xs font-black text-amber-800 dark:text-amber-200">Превращение пешки в:</div>
            <div class="flex items-center justify-center gap-2">
              <button onclick="(window.GAMES_CHESS || window.GAMES).choosePromotion('q')" class="w-10 h-10 rounded-xl bg-white dark:bg-slate-700 shadow border flex items-center justify-center p-1 active:scale-95">${window.CHESS_SVGS ? window.CHESS_SVGS[myRole === 'black' ? 'q' : 'Q'] : '♛'}</button>
              <button onclick="(window.GAMES_CHESS || window.GAMES).choosePromotion('r')" class="w-10 h-10 rounded-xl bg-white dark:bg-slate-700 shadow border flex items-center justify-center p-1 active:scale-95">${window.CHESS_SVGS ? window.CHESS_SVGS[myRole === 'black' ? 'r' : 'R'] : '♜'}</button>
              <button onclick="(window.GAMES_CHESS || window.GAMES).choosePromotion('b')" class="w-10 h-10 rounded-xl bg-white dark:bg-slate-700 shadow border flex items-center justify-center p-1 active:scale-95">${window.CHESS_SVGS ? window.CHESS_SVGS[myRole === 'black' ? 'b' : 'B'] : '♝'}</button>
              <button onclick="(window.GAMES_CHESS || window.GAMES).choosePromotion('n')" class="w-10 h-10 rounded-xl bg-white dark:bg-slate-700 shadow border flex items-center justify-center p-1 active:scale-95">${window.CHESS_SVGS ? window.CHESS_SVGS[myRole === 'black' ? 'n' : 'N'] : '♞'}</button>
            </div>
          </div>
        ` : ''}

        <!-- Bottom Player Bar -->
        <div class="flex items-center justify-between p-2 rounded-2xl bg-slate-100 dark:bg-slate-700/60 text-xs font-bold">
          <div class="flex items-center gap-1.5 min-w-0 pr-1">
            <span class="w-6 h-6 rounded-lg ${myRole === 'white' ? 'bg-amber-100 text-amber-900 border border-amber-300' : 'bg-slate-800 text-white border border-slate-600'} flex items-center justify-center font-black text-xs shrink-0">${myRole === 'white' ? '♔' : '♚'}</span>
            <div class="text-left truncate">
              <div class="truncate text-slate-800 dark:text-white">${escapeHtml(myName)} ${chessIsLocal ? '' : '(Вы)'}</div>
              <div class="text-[10px] text-slate-400">${myCaptured.length > 0 ? myCaptured.map(p => window.CHESS_BOARD?.CHESS_SYMBOLS[p] || p).join(' ') : 'Без взятий'}</div>
            </div>
          </div>
          ${!isFinished ? `
            <button onclick="(window.GAMES_CHESS || window.GAMES).resignChessGame()" class="px-2.5 py-1 rounded-lg text-rose-500 hover:bg-rose-50 text-xs font-bold transition-all">🏳️ Сдаться</button>
          ` : ''}
        </div>

        <!-- Finished Actions -->
        ${isFinished ? `
          <div class="space-y-2 pt-1">
            <button onclick="(window.GAMES_CHESS || window.GAMES).requestChessRematch()" class="w-full py-2.5 rounded-xl bg-amber-600 hover:bg-amber-700 active:scale-95 text-white font-black text-xs shadow-md transition-all flex items-center justify-center gap-1.5">
              <span>🔄</span> Реванш ${chessIsBot ? '(со сменой сторон)' : ''}
            </button>
            <button onclick="(window.GAMES_CHESS || window.GAMES).leaveChessGame()" class="w-full py-2 rounded-xl bg-slate-200 dark:bg-slate-700 hover:bg-slate-300 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 font-bold text-xs transition-all active:scale-95">
              🔙 Выйти в меню шахмат
            </button>
          </div>
        ` : ''}
      `;
    }

    return renderLobbyHTML(props);
  }

  window.CHESS_UI = {
    escapeHtml,
    renderLobbyHTML,
    renderClassmatesList,
    renderStatusBanner,
    renderChessContentHTML
  };
})();
