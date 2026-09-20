(function() {
  'use strict';

  // GAME 1: 2048
  // ==============================================================================
  let board2048 = [];
  let score2048 = 0;
  let best2048 = 0;
  let isGameOver2048 = false;

  function render2048HTML() {
    best2048 = parseInt(localStorage.getItem("game_2048_best") || "0", 10);
    return `
      <div class="theme-card rounded-3xl p-4 bg-white dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700 shadow-sm space-y-4 max-w-sm mx-auto">
        <!-- Top bar: Score & New Game -->
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <div class="px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-700 text-center">
              <span class="block text-[9px] font-bold text-slate-400 uppercase">Счёт</span>
              <span id="score-2048" class="text-sm font-black text-slate-800 dark:text-white">0</span>
            </div>
            <div class="px-3 py-1.5 rounded-xl bg-amber-50 dark:bg-amber-950/40 text-center border border-amber-200/60 dark:border-amber-800/40">
              <span class="block text-[9px] font-bold text-amber-500 uppercase">Рекорд</span>
              <span id="best-2048" class="text-sm font-black text-amber-600 dark:text-amber-400">${best2048}</span>
            </div>
          </div>
          <button onclick="window.GAMES.reset2048()" class="px-3.5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 active:scale-95 text-white font-bold text-xs shadow-sm transition-all flex items-center gap-1">
            <span>🔄</span> Заново
          </button>
        </div>

        <!-- 4x4 Grid Container with Game Over overlay -->
        <div class="relative w-full aspect-square">
          <div id="grid-2048" class="w-full h-full p-2 rounded-2xl bg-slate-200 dark:bg-slate-900 grid grid-cols-4 gap-2 touch-none select-none">
            <!-- 16 cells generated in init2048 -->
          </div>
          <div id="game-over-2048" class="hidden absolute inset-0 rounded-2xl bg-slate-900/90 backdrop-blur-sm flex flex-col items-center justify-center p-6 text-center z-10 space-y-3">
            <div class="w-12 h-12 rounded-2xl bg-rose-500/20 text-rose-400 flex items-center justify-center text-2xl mx-auto shadow-inner">
              😢
            </div>
            <div>
              <h3 class="text-base font-black text-white">Игра окончена!</h3>
              <p class="text-xs text-slate-400 mt-0.5">Нет доступных ходов для объединения</p>
            </div>
            <div class="flex items-center gap-2 w-full justify-center">
              <div class="px-3 py-1.5 rounded-xl bg-slate-800/90 border border-slate-700 text-center min-w-[80px]">
                <span class="block text-[9px] font-bold text-slate-400 uppercase">Счёт</span>
                <span id="final-score-2048" class="text-sm font-black text-white">0</span>
              </div>
              <div class="px-3 py-1.5 rounded-xl bg-amber-950/50 border border-amber-800/40 text-center min-w-[80px]">
                <span class="block text-[9px] font-bold text-amber-500 uppercase">Рекорд</span>
                <span id="final-best-2048" class="text-sm font-black text-amber-400">${best2048}</span>
              </div>
            </div>
            <button onclick="window.GAMES.reset2048()" class="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 active:scale-95 text-white font-bold text-xs shadow-lg transition-all flex items-center gap-1.5">
              <span>🔄</span> Сыграть заново
            </button>
          </div>
        </div>

        <!-- Hint / Keyboard / Touch controls -->
        <div class="text-center text-[11px] text-slate-400">
          Свайпайте или используйте клавиши <span class="font-bold text-slate-600 dark:text-slate-300">W A S D</span> / стрелки
        </div>
      </div>
    `;
  }

  function init2048() {
    isGameOver2048 = false;
    const overEl = document.getElementById("game-over-2048");
    if (overEl) overEl.classList.add("hidden");

    board2048 = [
      [0, 0, 0, 0],
      [0, 0, 0, 0],
      [0, 0, 0, 0],
      [0, 0, 0, 0]
    ];
    score2048 = 0;
    addRandomTile2048();
    addRandomTile2048();
    updateBoard2048DOM();
    setupSwipe2048();
    setupKeyboard2048();
  }

  function addRandomTile2048() {
    const empty = [];
    for (let r = 0; r < 4; r++) {
      for (let c = 0; c < 4; c++) {
        if (board2048[r][c] === 0) empty.push({ r, c });
      }
    }
    if (empty.length === 0) return;
    const { r, c } = empty[Math.floor(Math.random() * empty.length)];
    board2048[r][c] = Math.random() < 0.9 ? 2 : 4;
  }

  function getTileColor(val) {
    const map = {
      2: "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 text-xl font-bold",
      4: "bg-amber-100 dark:bg-amber-900/60 text-amber-900 dark:text-amber-100 text-xl font-bold",
      8: "bg-orange-400 text-white text-xl font-extrabold",
      16: "bg-orange-500 text-white text-xl font-extrabold",
      32: "bg-red-500 text-white text-xl font-extrabold",
      64: "bg-red-600 text-white text-xl font-extrabold",
      128: "bg-yellow-400 text-slate-900 text-lg font-black shadow-md",
      256: "bg-yellow-500 text-slate-900 text-lg font-black shadow-md",
      512: "bg-yellow-600 text-white text-lg font-black shadow-md",
      1024: "bg-emerald-500 text-white text-base font-black shadow-lg",
      2048: "bg-gradient-to-tr from-amber-400 to-yellow-300 text-slate-900 text-base font-black shadow-xl ring-2 ring-yellow-400"
    };
    return map[val] || "bg-indigo-600 text-white text-sm font-black";
  }

  function updateBoard2048DOM() {
    const gridEl = document.getElementById("grid-2048");
    if (!gridEl) return;

    let html = "";
    for (let r = 0; r < 4; r++) {
      for (let c = 0; c < 4; c++) {
        const val = board2048[r][c];
        if (val === 0) {
          html += `<div class="rounded-xl bg-slate-300/40 dark:bg-slate-800/40"></div>`;
        } else {
          html += `
            <div class="rounded-xl flex items-center justify-center transition-all ${getTileColor(val)}">
              ${val}
            </div>
          `;
        }
      }
    }
    gridEl.innerHTML = html;

    const scoreEl = document.getElementById("score-2048");
    if (scoreEl) scoreEl.textContent = score2048;

    if (score2048 > best2048) {
      best2048 = score2048;
      localStorage.setItem("game_2048_best", best2048);
      const bestEl = document.getElementById("best-2048");
      if (bestEl) bestEl.textContent = best2048;
    }
  }

  function checkGameOver2048() {
    for (let r = 0; r < 4; r++) {
      for (let c = 0; c < 4; c++) {
        if (board2048[r][c] === 0) return false;
      }
    }
    for (let r = 0; r < 4; r++) {
      for (let c = 0; c < 3; c++) {
        if (board2048[r][c] === board2048[r][c + 1]) return false;
      }
    }
    for (let c = 0; c < 4; c++) {
      for (let r = 0; r < 3; r++) {
        if (board2048[r][c] === board2048[r + 1][c]) return false;
      }
    }
    return true;
  }

  function triggerGameOver2048() {
    isGameOver2048 = true;
    const overEl = document.getElementById("game-over-2048");
    if (overEl) {
      const finalScoreEl = document.getElementById("final-score-2048");
      if (finalScoreEl) finalScoreEl.textContent = score2048;
      const finalBestEl = document.getElementById("final-best-2048");
      if (finalBestEl) finalBestEl.textContent = best2048;
      overEl.classList.remove("hidden");
    }
    if (window.Telegram?.WebApp?.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.notificationOccurred("error");
    }
  }

  function move2048(direction) {
    if (isGameOver2048) return;
    let moved = false;

    function slide(row) {
      let arr = row.filter(val => val !== 0);
      for (let i = 0; i < arr.length - 1; i++) {
        if (arr[i] === arr[i + 1]) {
          arr[i] *= 2;
          score2048 += arr[i];
          arr[i + 1] = 0;
          moved = true;
        }
      }
      arr = arr.filter(val => val !== 0);
      while (arr.length < 4) arr.push(0);
      return arr;
    }

    const prevBoard = JSON.stringify(board2048);

    if (direction === "left") {
      for (let r = 0; r < 4; r++) board2048[r] = slide(board2048[r]);
    } else if (direction === "right") {
      for (let r = 0; r < 4; r++) {
        board2048[r].reverse();
        board2048[r] = slide(board2048[r]);
        board2048[r].reverse();
      }
    } else if (direction === "up") {
      for (let c = 0; c < 4; c++) {
        let col = [board2048[0][c], board2048[1][c], board2048[2][c], board2048[3][c]];
        col = slide(col);
        for (let r = 0; r < 4; r++) board2048[r][c] = col[r];
      }
    } else if (direction === "down") {
      for (let c = 0; c < 4; c++) {
        let col = [board2048[0][c], board2048[1][c], board2048[2][c], board2048[3][c]];
        col.reverse();
        col = slide(col);
        col.reverse();
        for (let r = 0; r < 4; r++) board2048[r][c] = col[r];
      }
    }

    if (JSON.stringify(board2048) !== prevBoard) {
      addRandomTile2048();
      updateBoard2048DOM();
      if (checkGameOver2048()) {
        triggerGameOver2048();
      } else if (window.Telegram?.WebApp?.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.impactOccurred("light");
      }
    }
  }

  function setupSwipe2048() {
    const gridEl = document.getElementById("grid-2048");
    if (!gridEl) return;

    let startX = 0;
    let startY = 0;

    gridEl.addEventListener("touchstart", (e) => {
      startX = e.touches[0].clientX;
      startY = e.touches[0].clientY;
    }, { passive: true });

    gridEl.addEventListener("touchend", (e) => {
      if (isGameOver2048) return;
      const diffX = e.changedTouches[0].clientX - startX;
      const diffY = e.changedTouches[0].clientY - startY;
      const absX = Math.abs(diffX);
      const absY = Math.abs(diffY);

      if (Math.max(absX, absY) > 25) {
        if (absX > absY) {
          move2048(diffX > 0 ? "right" : "left");
        } else {
          move2048(diffY > 0 ? "down" : "up");
        }
      }
    }, { passive: true });
  }

  function setupKeyboard2048() {
    if (window._2048KeyHandler) {
      window.removeEventListener("keydown", window._2048KeyHandler);
    }
    window._2048KeyHandler = function (e) {
      const activeG = window.currentGame || (window.GAMES?.getCurrentGame ? window.GAMES.getCurrentGame() : "2048");
      if (activeG !== "2048" || isGameOver2048) return;
      const key = (e.key || "").toLowerCase();
      const code = e.code || "";

      if (key === "arrowup" || code === "KeyW" || key === "w" || key === "ц") {
        e.preventDefault();
        move2048("up");
      } else if (key === "arrowdown" || code === "KeyS" || key === "s" || key === "ы") {
        e.preventDefault();
        move2048("down");
      } else if (key === "arrowleft" || code === "KeyA" || key === "a" || key === "ф") {
        e.preventDefault();
        move2048("left");
      } else if (key === "arrowright" || code === "KeyD" || key === "d" || key === "в") {
        e.preventDefault();
        move2048("right");
      }
    };
    window.addEventListener("keydown", window._2048KeyHandler);
  }

  // ==============================================================================


  window.GAMES_2048 = {
    renderHTML: render2048HTML,
    init: init2048,
    reset: init2048,
    cleanup: function() {
      if (window._2048KeyHandler) {
        window.removeEventListener('keydown', window._2048KeyHandler);
        window._2048KeyHandler = null;
      }
    }
  };
})();
