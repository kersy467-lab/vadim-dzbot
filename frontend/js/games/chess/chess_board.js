// frontend/js/games/chess/chess_board.js
(function() {
  'use strict';

  const CHESS_SYMBOLS = {
    "P": "♟", "N": "♞", "B": "♝", "R": "♜", "Q": "♛", "K": "♚",
    "p": "♟", "n": "♞", "b": "♝", "r": "♜", "q": "♛", "k": "♚"
  };

  const CHESS_FILES = ["a", "b", "c", "d", "e", "f", "g", "h"];

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

  function renderPiece(char) {
    if (!char) return "";
    const svg = window.CHESS_SVGS ? window.CHESS_SVGS[char] : null;
    if (svg) {
      return `
        <span class="inline-flex items-center justify-center w-full h-full pointer-events-none select-none transition-transform transform group-active:scale-90">
          ${svg}
        </span>
      `;
    }
    const isWhite = char === char.toUpperCase();
    const glyph = CHESS_SYMBOLS[char] || char;
    return `
      <span class="select-none leading-none inline-block font-black text-2xl sm:text-3xl transition-transform transform group-active:scale-90 ${
        isWhite
          ? 'text-white'
          : 'text-slate-900 drop-shadow-[0_1px_1px_rgba(255,255,255,0.7)]'
      }" style="${isWhite ? 'color:#fff;-webkit-text-stroke:1.2px #1e293b;paint-order:stroke fill;' : ''}">
        ${glyph}
      </span>
    `;
  }

  function renderBoardGrid(options) {
    const {
      board,
      isFlipped,
      selectedSquare,
      legalTargetSquares,
      lastMoveFrom,
      lastMoveTo,
      chessRoomData
    } = options;

    const rRange = isFlipped ? [7, 6, 5, 4, 3, 2, 1, 0] : [0, 1, 2, 3, 4, 5, 6, 7];
    const cRange = isFlipped ? [7, 6, 5, 4, 3, 2, 1, 0] : [0, 1, 2, 3, 4, 5, 6, 7];

    return `
      <div class="w-full max-w-[320px] aspect-square mx-auto rounded-2xl overflow-hidden shadow-lg border-2 border-amber-950/40 select-none grid grid-cols-8 grid-rows-8 relative transition-all duration-300" style="touch-action: manipulation;">
        ${rRange.map(r => cRange.map(c => {
          const sq = rcToSquare(r, c);
          const piece = board[r][c];
          const isLight = (r + c) % 2 === 0;
          const isSelected = sq === selectedSquare;
          const isLastMove = sq === lastMoveFrom || sq === lastMoveTo;
          const isLegalTarget = legalTargetSquares && legalTargetSquares.has(sq);

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
              onclick="(window.GAMES_CHESS || window.GAMES).chessSquareClick('${sq}')"
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

              ${renderPiece(piece)}

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
    `;
  }

  window.CHESS_BOARD = {
    CHESS_SYMBOLS,
    CHESS_FILES,
    rcToSquare,
    squareToRC,
    parseFen,
    renderPiece,
    renderBoardGrid
  };
})();
