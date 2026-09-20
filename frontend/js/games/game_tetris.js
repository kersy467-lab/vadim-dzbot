(function() {
  'use strict';

  // GAME 4: TETRIS (Классический Тетрис)
  // ==============================================================================
  const TETRIS_COLS = 10;
  const TETRIS_ROWS = 20;

  const TETRIS_SHAPES = {
    I: [
      [0, 0, 0, 0],
      [1, 1, 1, 1],
      [0, 0, 0, 0],
      [0, 0, 0, 0]
    ],
    O: [
      [1, 1],
      [1, 1]
    ],
    T: [
      [0, 1, 0],
      [1, 1, 1],
      [0, 0, 0]
    ],
    S: [
      [0, 1, 1],
      [1, 1, 0],
      [0, 0, 0]
    ],
    Z: [
      [1, 1, 0],
      [0, 1, 1],
      [0, 0, 0]
    ],
    J: [
      [1, 0, 0],
      [1, 1, 1],
      [0, 0, 0]
    ],
    L: [
      [0, 0, 1],
      [1, 1, 1],
      [0, 0, 0]
    ]
  };

  const TETRIS_COLORS = {
    I: "#06b6d4", // cyan
    O: "#eab308", // yellow
    T: "#a855f7", // purple
    S: "#10b981", // emerald
    Z: "#ef4444", // red
    J: "#3b82f6", // blue
    L: "#f97316"  // orange
  };

  let tetrisGrid = [];
  let tetrisScore = 0;
  let tetrisLines = 0;
  let tetrisLevel = 1;
  let tetrisBest = 0;
  let tetrisPiece = null;
  let tetrisNextPiece = null;
  let tetrisRunning = false;
  let tetrisPaused = false;
  let tetrisGameOver = false;

  function renderTetrisHTML() {
    tetrisBest = parseInt(localStorage.getItem("game_tetris_best") || "0", 10);
    return `
      <div class="theme-card rounded-3xl p-3 sm:p-4 bg-white dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700 shadow-sm space-y-3 max-w-sm mx-auto select-none">
        <!-- Top Stats Bar -->
        <div class="grid grid-cols-4 gap-1.5 text-center">
          <div class="px-2 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-700">
            <span class="block text-[9px] font-bold text-slate-400 uppercase">Счёт</span>
            <span id="tetris-score" class="text-xs sm:text-sm font-black text-slate-800 dark:text-white">${tetrisScore}</span>
          </div>
          <div class="px-2 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-700">
            <span class="block text-[9px] font-bold text-slate-400 uppercase">Линии</span>
            <span id="tetris-lines" class="text-xs sm:text-sm font-black text-blue-600 dark:text-blue-400">${tetrisLines}</span>
          </div>
          <div class="px-2 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-700">
            <span class="block text-[9px] font-bold text-slate-400 uppercase">Уровень</span>
            <span id="tetris-level" class="text-xs sm:text-sm font-black text-violet-600 dark:text-violet-400">${tetrisLevel}</span>
          </div>
          <div class="px-2 py-1.5 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200/60 dark:border-amber-800/40">
            <span class="block text-[9px] font-bold text-amber-500 uppercase">Рекорд</span>
            <span id="tetris-best" class="text-xs sm:text-sm font-black text-amber-600 dark:text-amber-400">${tetrisBest}</span>
          </div>
        </div>

        <!-- Main Game Area: Board + Sidebar -->
        <div class="flex items-start justify-center gap-3 pt-1">
          <!-- Canvas Container -->
          <div class="relative rounded-2xl overflow-hidden bg-slate-900 border-2 border-slate-800 shadow-inner" style="width: 200px; height: 400px;">
            <canvas id="tetris-canvas" width="200" height="400" class="block w-full h-full"></canvas>

            <!-- Overlay for Start / Pause / Game Over -->
            <div id="tetris-overlay" class="${tetrisRunning && !tetrisPaused ? 'hidden' : ''} absolute inset-0 bg-slate-900/90 backdrop-blur-sm flex flex-col items-center justify-center p-4 text-center z-10 space-y-3">
              ${renderTetrisOverlayContent()}
            </div>
          </div>

          <!-- Sidebar: Next Piece & Controls -->
          <div class="flex flex-col items-center gap-3 w-24">
            <!-- Next Piece Box -->
            <div class="w-full p-2 rounded-2xl bg-slate-100 dark:bg-slate-700/60 border border-slate-200/60 dark:border-slate-700 text-center">
              <span class="block text-[10px] font-bold text-slate-400 uppercase mb-1">След.</span>
              <div class="w-16 h-16 mx-auto flex items-center justify-center bg-slate-900/60 dark:bg-slate-900 rounded-xl overflow-hidden shadow-inner">
                <canvas id="tetris-next-canvas" width="64" height="64" class="block"></canvas>
              </div>
            </div>

            <!-- Pause / Restart Quick Actions -->
            <div class="w-full space-y-1.5">
              <button
                onclick="window.GAMES.toggleTetrisPause()"
                id="btn-tetris-pause"
                class="w-full py-2 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 text-xs font-bold transition-all active:scale-95 flex items-center justify-center gap-1 shadow-sm">
                <span>${tetrisPaused ? '▶️' : '⏸️'}</span>
                <span>${tetrisPaused ? 'Пуск' : 'Пауза'}</span>
              </button>
              <button
                onclick="window.GAMES.startTetrisGame()"
                class="w-full py-2 rounded-xl bg-blue-600 hover:bg-blue-700 active:scale-95 text-white text-xs font-bold transition-all shadow-sm flex items-center justify-center gap-1">
                <span>🔄</span>
                <span>Заново</span>
              </button>
            </div>
          </div>
        </div>

        <!-- Mobile Touch Controls -->
        <div class="space-y-1.5 pt-1">
          <div class="grid grid-cols-5 gap-1 max-w-[280px] mx-auto">
            <button
              type="button"
              onpointerdown="window.GAMES.tetrisMoveLeft()"
              class="py-3 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200 font-black text-base active:scale-90 shadow-sm transition-all select-none touch-none flex items-center justify-center"
              title="Влево">
              ◀️
            </button>
            <button
              type="button"
              onpointerdown="window.GAMES.tetrisRotate()"
              class="py-3 rounded-xl bg-amber-500/15 hover:bg-amber-500/25 text-amber-600 dark:text-amber-400 font-black text-base active:scale-90 shadow-sm transition-all select-none touch-none flex items-center justify-center border border-amber-500/30"
              title="Поворот">
              🔄
            </button>
            <button
              type="button"
              onpointerdown="window.GAMES.tetrisMoveRight()"
              class="py-3 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200 font-black text-base active:scale-90 shadow-sm transition-all select-none touch-none flex items-center justify-center"
              title="Вправо">
              ▶️
            </button>
            <button
              type="button"
              onpointerdown="window.GAMES.tetrisSoftDrop()"
              class="py-3 rounded-xl bg-blue-500/15 hover:bg-blue-500/25 text-blue-600 dark:text-blue-400 font-black text-base active:scale-90 shadow-sm transition-all select-none touch-none flex items-center justify-center border border-blue-500/30"
              title="Вниз">
              ⬇️
            </button>
            <button
              type="button"
              onpointerdown="window.GAMES.tetrisHardDrop()"
              class="py-3 rounded-xl bg-rose-500/15 hover:bg-rose-500/25 text-rose-600 dark:text-rose-400 font-black text-base active:scale-90 shadow-sm transition-all select-none touch-none flex items-center justify-center border border-rose-500/30"
              title="Сброс">
              ⏬
            </button>
          </div>

          <!-- Desktop Controls Legend -->
          <div class="text-center text-[10px] text-slate-400">
            ПК: <span class="font-bold text-slate-600 dark:text-slate-300">W/↑</span> поворот, <span class="font-bold text-slate-600 dark:text-slate-300">A/D/←/→</span> движение, <span class="font-bold text-slate-600 dark:text-slate-300">Пробел</span> сброс, <span class="font-bold text-slate-600 dark:text-slate-300">P</span> пауза
          </div>
        </div>
      </div>
    `;
  }

  function renderTetrisOverlayContent() {
    if (tetrisGameOver) {
      return `
        <div class="w-12 h-12 rounded-2xl bg-rose-500/20 text-rose-400 flex items-center justify-center text-2xl mx-auto shadow-inner">
          💥
        </div>
        <div>
          <h3 class="text-base font-black text-white">Игра окончена!</h3>
          <p class="text-xs text-slate-400 mt-0.5">Башня достигла вершины</p>
        </div>
        <div class="space-y-1 text-xs text-slate-300 bg-slate-800/80 p-2.5 rounded-xl border border-slate-700 w-full max-w-[170px] mx-auto">
          <div>Счёт: <span class="font-bold text-white">${tetrisScore}</span></div>
          <div>Линии: <span class="font-bold text-blue-400">${tetrisLines}</span></div>
          <div>Рекорд: <span class="font-bold text-amber-400">${tetrisBest}</span></div>
        </div>
        <button
          onclick="window.GAMES.startTetrisGame()"
          class="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 active:scale-95 text-white font-bold text-xs shadow-lg transition-all flex items-center gap-1.5">
          <span>🎮</span> Играть снова
        </button>
      `;
    }
    if (tetrisPaused) {
      return `
        <div class="text-3xl">⏸️</div>
        <h3 class="text-base font-black text-white">Пауза</h3>
        <p class="text-xs text-slate-400">Нажмите «Продолжить», чтобы вернуться к игре</p>
        <button
          onclick="window.GAMES.toggleTetrisPause()"
          class="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 active:scale-95 text-white font-bold text-xs shadow-md transition-all">
          ▶️ Продолжить
        </button>
      `;
    }
    return `
      <div class="text-4xl">🧱</div>
      <h3 class="text-base font-black text-white">Классический Тетрис</h3>
      <p class="text-xs text-slate-400">Собирай линии и ставь новые рекорды на перемене</p>
      <button
        onclick="window.GAMES.startTetrisGame()"
        class="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 active:scale-95 text-white font-black text-xs shadow-lg transition-all">
        🚀 Начать игру
      </button>
    `;
  }

  function initTetris() {
    tetrisGrid = createTetrisGrid();
    tetrisBest = parseInt(localStorage.getItem("game_tetris_best") || "0", 10);
    drawTetrisCanvas();
    drawTetrisNextPiece();
    setupTetrisKeyboard();
  }

  function createTetrisGrid() {
    const g = [];
    for (let r = 0; r < TETRIS_ROWS; r++) {
      g.push(new Array(TETRIS_COLS).fill(0));
    }
    return g;
  }

  function getRandomTetrisPiece() {
    const types = ["I", "O", "T", "S", "Z", "J", "L"];
    const type = types[Math.floor(Math.random() * types.length)];
    const shape = TETRIS_SHAPES[type].map(row => [...row]);
    const color = TETRIS_COLORS[type];
    const x = Math.floor((TETRIS_COLS - shape[0].length) / 2);
    const y = 0;
    return { type, shape, color, x, y };
  }

  function startTetrisGame() {
    tetrisGrid = createTetrisGrid();
    tetrisScore = 0;
    tetrisLines = 0;
    tetrisLevel = 1;
    tetrisRunning = true;
    tetrisPaused = false;
    tetrisGameOver = false;

    tetrisPiece = getRandomTetrisPiece();
    tetrisNextPiece = getRandomTetrisPiece();

    const overlay = document.getElementById("tetris-overlay");
    if (overlay) overlay.classList.add("hidden");

    updateTetrisStatsDOM();
    drawTetrisCanvas();
    drawTetrisNextPiece();
    resetTetrisSpeed();
  }

  function toggleTetrisPause() {
    if (!tetrisRunning || tetrisGameOver) return;
    tetrisPaused = !tetrisPaused;

    const overlay = document.getElementById("tetris-overlay");
    const btnPause = document.getElementById("btn-tetris-pause");

    if (tetrisPaused) {
      if (window._tetrisInterval) {
        clearInterval(window._tetrisInterval);
        window._tetrisInterval = null;
      }
      if (overlay) {
        overlay.classList.remove("hidden");
        overlay.innerHTML = renderTetrisOverlayContent();
      }
      if (btnPause) {
        btnPause.innerHTML = `<span>▶️</span><span>Пуск</span>`;
      }
    } else {
      if (overlay) overlay.classList.add("hidden");
      if (btnPause) {
        btnPause.innerHTML = `<span>⏸️</span><span>Пауза</span>`;
      }
      resetTetrisSpeed();
    }
  }

  function rotateTetrisMatrix(matrix) {
    const N = matrix.length;
    const res = [];
    for (let r = 0; r < N; r++) {
      res[r] = [];
      for (let c = 0; c < N; c++) {
        res[r][c] = matrix[N - 1 - c][r];
      }
    }
    return res;
  }

  function checkTetrisCollision(piece, grid, offsetX = 0, offsetY = 0) {
    if (!piece) return true;
    const shape = piece.shape;
    const px = piece.x + offsetX;
    const py = piece.y + offsetY;

    for (let r = 0; r < shape.length; r++) {
      for (let c = 0; c < shape[r].length; c++) {
        if (shape[r][c]) {
          const nx = px + c;
          const ny = py + r;
          if (nx < 0 || nx >= TETRIS_COLS || ny >= TETRIS_ROWS) return true;
          if (ny >= 0 && grid[ny] && grid[ny][nx]) return true;
        }
      }
    }
    return false;
  }

  function tetrisRotate() {
    if (!tetrisRunning || tetrisPaused || !tetrisPiece) return;
    const rotatedShape = rotateTetrisMatrix(tetrisPiece.shape);
    const kicks = [0, 1, -1, 2, -2];

    for (let kick of kicks) {
      if (!checkTetrisCollision({ ...tetrisPiece, shape: rotatedShape, x: tetrisPiece.x + kick }, tetrisGrid)) {
        tetrisPiece.shape = rotatedShape;
        tetrisPiece.x += kick;
        drawTetrisCanvas();
        if (window.Telegram?.WebApp?.HapticFeedback) {
          window.Telegram.WebApp.HapticFeedback.selectionChanged();
        }
        return;
      }
    }
  }

  function tetrisMoveLeft() {
    if (!tetrisRunning || tetrisPaused || !tetrisPiece) return;
    if (!checkTetrisCollision(tetrisPiece, tetrisGrid, -1, 0)) {
      tetrisPiece.x -= 1;
      drawTetrisCanvas();
      if (window.Telegram?.WebApp?.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.impactOccurred("light");
      }
    }
  }

  function tetrisMoveRight() {
    if (!tetrisRunning || tetrisPaused || !tetrisPiece) return;
    if (!checkTetrisCollision(tetrisPiece, tetrisGrid, 1, 0)) {
      tetrisPiece.x += 1;
      drawTetrisCanvas();
      if (window.Telegram?.WebApp?.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.impactOccurred("light");
      }
    }
  }

  function tetrisSoftDrop() {
    if (!tetrisRunning || tetrisPaused || !tetrisPiece) return;
    if (!checkTetrisCollision(tetrisPiece, tetrisGrid, 0, 1)) {
      tetrisPiece.y += 1;
      tetrisScore += 1;
      updateTetrisStatsDOM();
      drawTetrisCanvas();
    } else {
      lockTetrisPiece();
    }
  }

  function tetrisHardDrop() {
    if (!tetrisRunning || tetrisPaused || !tetrisPiece) return;
    let droppedRows = 0;
    while (!checkTetrisCollision(tetrisPiece, tetrisGrid, 0, 1)) {
      tetrisPiece.y += 1;
      droppedRows += 1;
    }
    tetrisScore += droppedRows * 2;
    updateTetrisStatsDOM();
    if (window.Telegram?.WebApp?.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.impactOccurred("heavy");
    }
    lockTetrisPiece();
  }

  function lockTetrisPiece() {
    for (let r = 0; r < tetrisPiece.shape.length; r++) {
      for (let c = 0; c < tetrisPiece.shape[r].length; c++) {
        if (tetrisPiece.shape[r][c]) {
          const gy = tetrisPiece.y + r;
          const gx = tetrisPiece.x + c;
          if (gy >= 0 && gy < TETRIS_ROWS && gx >= 0 && gx < TETRIS_COLS) {
            tetrisGrid[gy][gx] = tetrisPiece.color;
          }
        }
      }
    }

    let cleared = 0;
    for (let r = TETRIS_ROWS - 1; r >= 0; r--) {
      if (tetrisGrid[r].every(cell => cell !== 0)) {
        tetrisGrid.splice(r, 1);
        tetrisGrid.unshift(new Array(TETRIS_COLS).fill(0));
        cleared++;
        r++;
      }
    }

    if (cleared > 0) {
      tetrisLines += cleared;
      const pointMap = [0, 100, 300, 500, 800];
      tetrisScore += (pointMap[cleared] || (cleared * 200)) * tetrisLevel;
      tetrisLevel = Math.floor(tetrisLines / 10) + 1;
      if (window.Telegram?.WebApp?.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.notificationOccurred("success");
      }
      resetTetrisSpeed();
    }

    if (tetrisScore > tetrisBest) {
      tetrisBest = tetrisScore;
      localStorage.setItem("game_tetris_best", tetrisBest);
    }
    updateTetrisStatsDOM();

    tetrisPiece = tetrisNextPiece;
    tetrisNextPiece = getRandomTetrisPiece();

    if (checkTetrisCollision(tetrisPiece, tetrisGrid)) {
      endTetrisGame();
      return;
    }

    drawTetrisCanvas();
    drawTetrisNextPiece();
  }

  function resetTetrisSpeed() {
    if (window._tetrisInterval) clearInterval(window._tetrisInterval);
    const speed = Math.max(90, 750 - (tetrisLevel - 1) * 65);
    window._tetrisInterval = setInterval(tetrisTick, speed);
  }

  function tetrisTick() {
    if (!tetrisRunning || tetrisPaused || !tetrisPiece) return;
    if (!checkTetrisCollision(tetrisPiece, tetrisGrid, 0, 1)) {
      tetrisPiece.y += 1;
      drawTetrisCanvas();
    } else {
      lockTetrisPiece();
    }
  }

  function endTetrisGame() {
    tetrisRunning = false;
    tetrisGameOver = true;
    if (window._tetrisInterval) {
      clearInterval(window._tetrisInterval);
      window._tetrisInterval = null;
    }
    const overlay = document.getElementById("tetris-overlay");
    if (overlay) {
      overlay.classList.remove("hidden");
      overlay.innerHTML = renderTetrisOverlayContent();
    }
    if (window.Telegram?.WebApp?.HapticFeedback) {
      window.Telegram.WebApp.HapticFeedback.notificationOccurred("error");
    }
  }

  function updateTetrisStatsDOM() {
    const scoreEl = document.getElementById("tetris-score");
    if (scoreEl) scoreEl.textContent = tetrisScore;

    const linesEl = document.getElementById("tetris-lines");
    if (linesEl) linesEl.textContent = tetrisLines;

    const levelEl = document.getElementById("tetris-level");
    if (levelEl) levelEl.textContent = tetrisLevel;

    const bestEl = document.getElementById("tetris-best");
    if (bestEl) bestEl.textContent = tetrisBest;
  }

  function drawTetrisCanvas() {
    const canvas = document.getElementById("tetris-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const cellPx = 20;

    ctx.fillStyle = "#0f172a";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.strokeStyle = "rgba(255, 255, 255, 0.04)";
    ctx.lineWidth = 1;
    for (let c = 0; c <= TETRIS_COLS; c++) {
      ctx.beginPath();
      ctx.moveTo(c * cellPx, 0);
      ctx.lineTo(c * cellPx, canvas.height);
      ctx.stroke();
    }
    for (let r = 0; r <= TETRIS_ROWS; r++) {
      ctx.beginPath();
      ctx.moveTo(0, r * cellPx);
      ctx.lineTo(canvas.width, r * cellPx);
      ctx.stroke();
    }

    for (let r = 0; r < TETRIS_ROWS; r++) {
      for (let c = 0; c < TETRIS_COLS; c++) {
        if (tetrisGrid[r] && tetrisGrid[r][c]) {
          drawTetrisBlock(ctx, c * cellPx, r * cellPx, cellPx, tetrisGrid[r][c]);
        }
      }
    }

    if (tetrisPiece && tetrisRunning) {
      let ghostY = tetrisPiece.y;
      while (!checkTetrisCollision(tetrisPiece, tetrisGrid, 0, ghostY - tetrisPiece.y + 1)) {
        ghostY++;
      }
      if (ghostY > tetrisPiece.y) {
        for (let r = 0; r < tetrisPiece.shape.length; r++) {
          for (let c = 0; c < tetrisPiece.shape[r].length; c++) {
            if (tetrisPiece.shape[r][c]) {
              const gx = (tetrisPiece.x + c) * cellPx;
              const gy = (ghostY + r) * cellPx;
              ctx.strokeStyle = tetrisPiece.color;
              ctx.fillStyle = "rgba(255, 255, 255, 0.08)";
              ctx.lineWidth = 1.5;
              ctx.strokeRect(gx + 1.5, gy + 1.5, cellPx - 3, cellPx - 3);
              ctx.fillRect(gx + 1.5, gy + 1.5, cellPx - 3, cellPx - 3);
            }
          }
        }
      }

      for (let r = 0; r < tetrisPiece.shape.length; r++) {
        for (let c = 0; c < tetrisPiece.shape[r].length; c++) {
          if (tetrisPiece.shape[r][c]) {
            const px = (tetrisPiece.x + c) * cellPx;
            const py = (tetrisPiece.y + r) * cellPx;
            drawTetrisBlock(ctx, px, py, cellPx, tetrisPiece.color);
          }
        }
      }
    }
  }

  function drawTetrisBlock(ctx, x, y, size, color) {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.roundRect(x + 1, y + 1, size - 2, size - 2, 3);
    ctx.fill();

    ctx.fillStyle = "rgba(255, 255, 255, 0.25)";
    ctx.fillRect(x + 2, y + 2, size - 4, 2);
    ctx.fillRect(x + 2, y + 2, 2, size - 4);

    ctx.fillStyle = "rgba(0, 0, 0, 0.3)";
    ctx.fillRect(x + 2, y + size - 3, size - 4, 2);
    ctx.fillRect(x + size - 3, y + 2, 2, size - 4);
  }

  function drawTetrisNextPiece() {
    const canvas = document.getElementById("tetris-next-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!tetrisNextPiece) return;

    const shape = tetrisNextPiece.shape;
    const cellPx = 13;
    const pieceW = shape[0].length * cellPx;
    const pieceH = shape.length * cellPx;
    const offsetX = Math.floor((canvas.width - pieceW) / 2);
    const offsetY = Math.floor((canvas.height - pieceH) / 2);

    for (let r = 0; r < shape.length; r++) {
      for (let c = 0; c < shape[r].length; c++) {
        if (shape[r][c]) {
          drawTetrisBlock(ctx, offsetX + c * cellPx, offsetY + r * cellPx, cellPx, tetrisNextPiece.color);
        }
      }
    }
  }

  function setupTetrisKeyboard() {
    if (window._tetrisKeyHandler) {
      window.removeEventListener("keydown", window._tetrisKeyHandler);
    }
    window._tetrisKeyHandler = function (e) {
      const activeG = window.currentGame || (window.GAMES?.getCurrentGame ? window.GAMES.getCurrentGame() : "tetris");
      if (activeG !== "tetris") return;
      const key = (e.key || "").toLowerCase();
      const code = e.code || "";

      if (key === "arrowleft" || code === "KeyA" || key === "a" || key === "ф") {
        e.preventDefault();
        tetrisMoveLeft();
      } else if (key === "arrowright" || code === "KeyD" || key === "d" || key === "в") {
        e.preventDefault();
        tetrisMoveRight();
      } else if (key === "arrowup" || code === "KeyW" || key === "w" || key === "ц" || key === "r" || key === "к") {
        e.preventDefault();
        tetrisRotate();
      } else if (key === "arrowdown" || code === "KeyS" || key === "s" || key === "ы") {
        e.preventDefault();
        tetrisSoftDrop();
      } else if (code === "Space" || key === " ") {
        e.preventDefault();
        tetrisHardDrop();
      } else if (key === "p" || key === "з") {
        e.preventDefault();
        toggleTetrisPause();
      }
    };
    window.addEventListener("keydown", window._tetrisKeyHandler);
  }

  // ==============================================================================


  window.GAMES_TETRIS = {
    renderHTML: renderTetrisHTML,
    init: initTetris,
    cleanup: function() {
      if (window._tetrisInterval) {
        clearInterval(window._tetrisInterval);
        window._tetrisInterval = null;
      }
      if (window._tetrisKeyHandler) {
        window.removeEventListener('keydown', window._tetrisKeyHandler);
        window._tetrisKeyHandler = null;
      }
      tetrisRunning = false;
    },
    startTetrisGame: startTetrisGame,
    toggleTetrisPause: toggleTetrisPause,
    tetrisMoveLeft: tetrisMoveLeft,
    tetrisMoveRight: tetrisMoveRight,
    tetrisRotate: tetrisRotate,
    tetrisSoftDrop: tetrisSoftDrop,
    tetrisHardDrop: tetrisHardDrop
  };
})();
