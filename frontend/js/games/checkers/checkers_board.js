// frontend/js/games/checkers/checkers_board.js
(function() {
  'use strict';

  const FILES = ["a", "b", "c", "d", "e", "f", "g", "h"];

  function rcToSquare(r, c) {
    return FILES[c] + (8 - r);
  }

  function squareToRC(sq) {
    const file = sq.charAt(0).toLowerCase();
    const rank = parseInt(sq.charAt(1), 10);
    const c = FILES.indexOf(file);
    const r = 8 - rank;
    return { r, c };
  }

  function parseFen(fen) {
    if (!fen) fen = "b.b.b.b./.b.b.b.b/b.b.b.b./......../......../.w.w.w.w/w.w.w.w./.w.w.w.w w -";
    const parts = fen.split(" ");
    const rows = parts[0].split("/");
    const board = [];
    for (let r = 0; r < 8; r++) {
      const rowStr = rows[r] || "........";
      const row = [];
      for (let c = 0; c < 8; c++) {
        const ch = rowStr[c] || ".";
        row.push(ch === "." ? "" : ch);
      }
      board.push(row);
    }
    return board;
  }

  function renderPiece(char) {
    if (!char) return "";
    const isWhite = char === 'w' || char === 'W';
    const isKing = char === 'W' || char === 'B';

    if (isWhite) {
      return `
        <div class="w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-gradient-to-b from-amber-50 via-white to-amber-200 border-2 border-amber-400 shadow-md flex items-center justify-center select-none transform transition-transform group-active:scale-95">
          ${isKing ? '<span class="text-amber-600 text-sm leading-none drop-shadow font-black">👑</span>' : '<span class="w-3 h-3 rounded-full border border-amber-300 bg-amber-100/50"></span>'}
        </div>
      `;
    } else {
      return `
        <div class="w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-gradient-to-b from-slate-700 via-slate-800 to-slate-950 border-2 border-slate-600 shadow-md flex items-center justify-center select-none transform transition-transform group-active:scale-95">
          ${isKing ? '<span class="text-amber-400 text-sm leading-none drop-shadow font-black">👑</span>' : '<span class="w-3 h-3 rounded-full border border-slate-600 bg-slate-800/50"></span>'}
        </div>
      `;
    }
  }

  function renderBoard(options) {
    const {
      fen,
      isFlipped,
      selectedSquare,
      legalMoves,
      lastMove,
      mustCapture,
      onSquareClick
    } = options;

    const board = parseFen(fen);
    const rRange = isFlipped ? [7, 6, 5, 4, 3, 2, 1, 0] : [0, 1, 2, 3, 4, 5, 6, 7];
    const cRange = isFlipped ? [7, 6, 5, 4, 3, 2, 1, 0] : [0, 1, 2, 3, 4, 5, 6, 7];

    const legalTargetsForSelected = new Set(
      (legalMoves || [])
        .filter(m => selectedSquare && m.startsWith(selectedSquare))
        .map(m => m.slice(2, 4))
    );

    const piecesWithMoves = new Set((legalMoves || []).map(m => m.slice(0, 2)));

    const lastFrom = lastMove ? lastMove.slice(0, 2) : "";
    const lastTo = lastMove ? lastMove.slice(2, 4) : "";

    return `
      <div class="w-full max-w-[320px] aspect-square mx-auto rounded-2xl overflow-hidden shadow-lg border-2 border-amber-950/40 select-none grid grid-cols-8 grid-rows-8 relative transition-all duration-300" style="touch-action: manipulation;">
        ${rRange.map(r => cRange.map(c => {
          const sq = rcToSquare(r, c);
          const piece = board[r][c];
          const isDark = (r + c) % 2 === 1;
          const isSelected = sq === selectedSquare;
          const isLastMove = sq === lastFrom || sq === lastTo;
          const isLegalTarget = legalTargetsForSelected.has(sq);
          const hasMustCapture = mustCapture && piecesWithMoves.has(sq);

          let bgStyle = isDark ? "background-color: #78350f;" : "background-color: #fed7aa;";
          if (isSelected) {
            bgStyle = "background-color: #ca8a04 !important;";
          } else if (isLastMove && isDark) {
            bgStyle = "background-color: #92400e !important;";
          }

          return `
            <button
              id="checkers-sq-${sq}"
              type="button"
              onclick="${onSquareClick}('${sq}')"
              style="${bgStyle}"
              class="w-full h-full p-0 m-0 relative flex items-center justify-center cursor-pointer transition-colors group">
              
              ${(c === (isFlipped ? 7 : 0)) ? `
                <span class="absolute top-0.5 left-0.5 text-[8px] font-bold pointer-events-none opacity-60 ${isDark ? 'text-amber-200' : 'text-amber-900'}">
                  ${8 - r}
                </span>
              ` : ''}
              ${(r === (isFlipped ? 0 : 7)) ? `
                <span class="absolute bottom-0 right-0.5 text-[8px] font-bold pointer-events-none opacity-60 ${isDark ? 'text-amber-200' : 'text-amber-900'}">
                  ${FILES[c]}
                </span>
              ` : ''}

              ${renderPiece(piece)}

              ${hasMustCapture && !isSelected ? `
                <div class="absolute inset-1 rounded-full border-2 border-rose-500 animate-pulse pointer-events-none"></div>
              ` : ''}

              ${isLegalTarget ? (
                piece !== "" ? `
                  <div class="absolute inset-0.5 rounded-full border-2 border-rose-500/90 pointer-events-none animate-pulse"></div>
                ` : `
                  <div class="w-3.5 h-3.5 rounded-full bg-emerald-500/80 pointer-events-none shadow-sm animate-pulse"></div>
                `
              ) : ''}
            </button>
          `;
        }).join('')).join('')}
      </div>
    `;
  }

  window.CHECKERS_BOARD = {
    renderBoard: renderBoard,
    rcToSquare: rcToSquare,
    squareToRC: squareToRC,
    parseFen: parseFen
  };
})();
