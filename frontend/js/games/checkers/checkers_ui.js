// frontend/js/games/checkers/checkers_ui.js
(function() {
  'use strict';

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
  }

  function renderWaiting(data, oppName) {
    const name = oppName || data?.opponent?.name || "Одноклассник";
    return `
      <div class="py-8 space-y-4">
        <div class="w-16 h-16 rounded-3xl bg-amber-50 dark:bg-amber-950/50 text-amber-600 dark:text-amber-400 flex items-center justify-center text-3xl mx-auto animate-pulse">⚪⚫</div>
        <div class="space-y-1.5">
          <h3 class="text-sm font-black text-slate-800 dark:text-white">Вызов отправлен: ${escapeHtml(name)}</h3>
          <p class="text-[11px] text-slate-400 max-w-xs mx-auto">Бот отправил приглашение. Ждем подтверждения...</p>
        </div>
        <button onclick="window.GAMES.leaveCheckersGame()" class="px-4 py-2 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 font-bold text-xs active:scale-95">❌ Отменить вызов</button>
      </div>
    `;
  }

  function renderRejected() {
    return `
      <div class="py-8 space-y-3">
        <div class="text-4xl">❌</div>
        <h3 class="text-sm font-black text-slate-800 dark:text-white">Вызов отклонен или отменен</h3>
        <p class="text-xs text-slate-400">Соперник не смог сыграть сейчас.</p>
        <button onclick="window.GAMES.leaveCheckersGame()" class="px-4 py-2 rounded-xl bg-blue-600 text-white font-bold text-xs active:scale-95">🔙 В лобби</button>
      </div>
    `;
  }

  function renderPlaying(ctx) {
    const { data, isLocal, autoRotate, manualFlipped, selectedSquare } = ctx;
    let isFlipped = isLocal ? (autoRotate ? (data?.turn === "black") : false) : (data?.your_role === "black");
    if (manualFlipped) isFlipped = !isFlipped;

    const isFinished = ctx.state === "finished";
    const yourRole = data?.your_role;
    const isYourTurn = isLocal ? (ctx.state === "playing") : data?.is_your_turn;

    let statusHTML = "";
    if (isFinished) {
      const winner = data?.winner;
      const winnerText = winner === "white" ? "Белые ⚪" : "Черные ⚫";
      if (isLocal) {
        statusHTML = `<div class="p-2.5 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400 text-xs font-extrabold animate-pulse">🏆 ПОБЕДА: ${winnerText}!</div>`;
      } else if (winner === yourRole) {
        statusHTML = `<div class="p-2.5 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400 text-xs font-extrabold animate-pulse">🏆 ПОБЕДА! Все шашки соперника повержены!</div>`;
      } else {
        statusHTML = `<div class="p-2.5 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-400 text-xs font-extrabold">😔 Поражение</div>`;
      }
    } else {
      if (data?.must_capture) {
        statusHTML = `<div class="p-2 rounded-xl bg-rose-500/15 border border-rose-500/40 text-rose-600 dark:text-rose-400 text-xs font-black animate-pulse">⚡ ОБЯЗАТЕЛЬНОЕ ВЗЯТИЕ!</div>`;
      } else if (isLocal) {
        const tName = data?.turn === "white" ? "Белые ⚪" : "Черные ⚫";
        statusHTML = `<div class="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400 text-xs font-extrabold">🟢 Ходят: ${tName}</div>`;
      } else if (isYourTurn) {
        statusHTML = `<div class="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400 text-xs font-extrabold animate-pulse">🟢 Твой ход (${yourRole === 'white' ? 'Белые ⚪' : 'Черные ⚫'})</div>`;
      } else {
        statusHTML = `<div class="p-2 rounded-xl bg-slate-100 dark:bg-slate-700/60 text-slate-500 dark:text-slate-400 text-xs font-bold">⏳ Ход соперника...</div>`;
      }
    }

    const boardHTML = window.CHECKERS_BOARD ? window.CHECKERS_BOARD.renderBoard({
      fen: data?.fen,
      isFlipped: isFlipped,
      selectedSquare: selectedSquare,
      legalMoves: data?.legal_moves || [],
      lastMove: data?.last_move,
      mustCapture: data?.must_capture,
      onSquareClick: "window.GAMES.checkersSquareClick"
    }) : "";

    return `
      ${isLocal ? `
        <div class="flex items-center justify-between p-2 rounded-2xl bg-amber-500/10 border border-amber-500/25 text-[11px] font-bold">
          <span class="text-amber-700 dark:text-amber-300 flex items-center gap-1">👥 2 игрока на 1 телефоне</span>
          <div class="flex items-center gap-1">
            <button onclick="window.GAMES.toggleCheckersAutoRotate()" class="px-2 py-1 rounded-xl text-[10px] font-bold ${autoRotate ? 'bg-amber-600 text-white' : 'bg-white dark:bg-slate-700 text-slate-500'}">
              🔄 Авто: ${autoRotate ? 'ВКЛ' : 'ВЫКЛ'}
            </button>
            <button onclick="window.GAMES.flipCheckersBoardManual()" class="p-1 px-2 rounded-xl bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 text-[10px] font-bold shadow-sm active:scale-95">↕️ Повернуть</button>
          </div>
        </div>
      ` : ''}

      ${statusHTML}
      ${boardHTML}

      <div class="flex items-center justify-between pt-1">
        ${!isFinished ? `
          <button onclick="window.GAMES.resignCheckersGame()" class="px-3 py-1.5 rounded-xl text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/30 text-xs font-bold">🏳️ Сдаться</button>
        ` : `
          <button onclick="window.GAMES.requestCheckersRematch()" class="flex-1 py-2.5 mr-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-black text-xs shadow-md active:scale-95">🔄 Реванш</button>
        `}
        <button onclick="window.GAMES.leaveCheckersGame()" class="px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 text-xs font-bold active:scale-95">🚪 Выход</button>
      </div>
    `;
  }

  function renderLobby(color, filterText, classmates) {
    const filtered = classmates.filter(c => {
      const q = (filterText || "").toLowerCase();
      return !q || (c.name || c.full_name || "").toLowerCase().includes(q);
    });

    return `
      <div class="space-y-3">
        <div class="p-3 rounded-2xl bg-gradient-to-r from-amber-500/15 via-orange-500/10 to-amber-500/15 border border-amber-500/30 text-left space-y-2 shadow-sm">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-1.5 font-black text-xs text-slate-800 dark:text-white">
              <span class="text-base">👥</span><span>2 игрока на 1 телефоне</span>
            </div>
            <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500 text-white">Оффлайн</span>
          </div>
          <p class="text-[11px] text-slate-500 dark:text-slate-400">Сыграйте партию в шашки на перемене на одном экране!</p>
          <button type="button" onclick="window.GAMES.startLocalCheckersGame()" class="w-full py-2.5 rounded-xl bg-amber-600 hover:bg-amber-700 active:scale-95 text-white font-black text-xs shadow-md transition-all flex items-center justify-center gap-1.5">
            <span>⚪⚫</span> Начать игру на одном телефоне
          </button>
        </div>

        <div class="relative flex py-1 items-center">
          <div class="flex-grow border-t border-slate-200 dark:border-slate-700"></div>
          <span class="flex-shrink mx-2 text-[10px] font-bold text-slate-400 uppercase">или онлайн-дуэль</span>
          <div class="flex-grow border-t border-slate-200 dark:border-slate-700"></div>
        </div>

        <div class="p-2 rounded-2xl bg-slate-50 dark:bg-slate-700/40 border border-slate-200/80 dark:border-slate-700 grid grid-cols-3 gap-1.5">
          ${['white', 'random', 'black'].map(c => `
            <button onclick="window.GAMES.setCheckersColor('${c}')" class="py-1.5 rounded-xl text-xs font-bold transition-all ${color === c ? 'bg-white dark:bg-slate-600 text-slate-900 dark:text-white border-2 border-amber-500 shadow-sm font-black' : 'text-slate-500 hover:bg-white/50'}">
              ${c === 'white' ? '⚪ Белые' : (c === 'black' ? '⚫ Черные' : '🎲 Случайно')}
            </button>
          `).join('')}
        </div>

        <input type="text" value="${escapeHtml(filterText)}" oninput="window.GAMES.filterCheckersClassmates(this.value)" placeholder="🔍 Поиск одноклассника..." class="w-full px-3 py-2 rounded-xl bg-slate-100 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 text-xs focus:outline-none">

        <div class="space-y-1.5 max-h-56 overflow-y-auto pr-1">
          ${filtered.map(c => `
            <div class="flex items-center justify-between p-2 rounded-2xl bg-slate-50 dark:bg-slate-700/50 border border-slate-200/60 dark:border-slate-700">
              <span class="text-xs font-bold text-slate-800 dark:text-white truncate">${escapeHtml(c.name || c.full_name)}</span>
              <button onclick="window.GAMES.inviteCheckersClassmate(${c.tg_id}, '${escapeHtml(c.name || c.full_name)}')" class="shrink-0 px-3 py-1.5 rounded-xl font-black text-xs bg-amber-600 text-white shadow-sm active:scale-95">⚪⚫ Вызвать</button>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  window.CHECKERS_UI = {
    renderWaiting: renderWaiting,
    renderRejected: renderRejected,
    renderPlaying: renderPlaying,
    renderLobby: renderLobby
  };
})();
