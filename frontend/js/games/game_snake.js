(function() {
  'use strict';

  // GAME 3: SNAKE (Змейка)
  // ==============================================================================
  let snake = [];
  let snakeFood = { x: 5, y: 5 };
  let snakeDir = { x: 1, y: 0 };
  let snakeScore = 0;
  let snakeBest = 0;
  let snakeRunning = false;

  function renderSnakeHTML() {
    snakeBest = parseInt(localStorage.getItem("game_snake_best") || "0", 10);
    return `
      <div class="theme-card rounded-3xl p-4 bg-white dark:bg-slate-800 border border-slate-200/80 dark:border-slate-700 shadow-sm space-y-3 max-w-sm mx-auto text-center">
        <!-- Top bar -->
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <div class="px-3 py-1 rounded-xl bg-slate-100 dark:bg-slate-700 text-center">
              <span class="block text-[9px] font-bold text-slate-400 uppercase">Яблок</span>
              <span id="snake-score" class="text-sm font-black text-slate-800 dark:text-white">0</span>
            </div>
            <div class="px-3 py-1 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 text-center border border-emerald-200/60 dark:border-emerald-800/40">
              <span class="block text-[9px] font-bold text-emerald-500 uppercase">Рекорд</span>
              <span id="snake-best" class="text-sm font-black text-emerald-600 dark:text-emerald-400">${snakeBest}</span>
            </div>
          </div>
          <button onclick="window.GAMES.startSnakeGame()" class="px-3.5 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs shadow-sm transition-all">
            ▶️ Старт
          </button>
        </div>

        <!-- Canvas & Touch Zone -->
        <div id="snake-touch-zone" class="relative w-full aspect-square max-w-[290px] mx-auto rounded-2xl overflow-hidden bg-slate-900 border-2 border-slate-800 shadow-inner select-none cursor-pointer" style="touch-action: none;">
          <canvas id="snake-canvas" width="290" height="290" class="w-full h-full block"></canvas>
          <div id="snake-overlay" class="absolute inset-0 bg-black/60 flex flex-col items-center justify-center gap-2 text-white">
            <span class="text-3xl">🐍</span>
            <p class="text-xs font-bold">Нажмите «Старт» для игры</p>
          </div>
        </div>

        <!-- Gesture / Swipe Control Hint -->
        <div class="p-3 rounded-2xl bg-slate-50 dark:bg-slate-700/40 border border-slate-200/70 dark:border-slate-700 text-center space-y-1">
          <div class="text-xs font-bold text-slate-700 dark:text-slate-200 flex items-center justify-center gap-1.5">
            <span class="text-base">👆</span>
            <span>Управление жестами (свайпами)</span>
          </div>
          <p class="text-[11px] text-slate-400">
            Смахивайте пальцем по экрану в нужную сторону для поворота
          </p>
        </div>
      </div>
    `;
  }

  const GRID_SIZE = 14; // 14x14 cells (20px each)
  let snakeTouchStartX = 0;
  let snakeTouchStartY = 0;

  function setupSnakeTouchListeners() {
    const zone = document.getElementById("snake-touch-zone");
    if (!zone || zone._touchSetup) return;
    zone._touchSetup = true;

    zone.addEventListener("touchstart", (e) => {
      if (e.touches && e.touches.length > 0) {
        snakeTouchStartX = e.touches[0].clientX;
        snakeTouchStartY = e.touches[0].clientY;
      }
    }, { passive: true });

    zone.addEventListener("touchmove", (e) => {
      if (!snakeRunning || !e.touches || e.touches.length === 0) return;
      const curX = e.touches[0].clientX;
      const curY = e.touches[0].clientY;
      const diffX = curX - snakeTouchStartX;
      const diffY = curY - snakeTouchStartY;
      const threshold = 18;

      if (Math.max(Math.abs(diffX), Math.abs(diffY)) >= threshold) {
        if (Math.abs(diffX) > Math.abs(diffY)) {
          setSnakeDir(diffX > 0 ? 1 : -1, 0);
        } else {
          setSnakeDir(0, diffY > 0 ? 1 : -1);
        }
        snakeTouchStartX = curX;
        snakeTouchStartY = curY;
        if (window.Telegram?.WebApp?.HapticFeedback) {
          window.Telegram.WebApp.HapticFeedback.selectionChanged();
        }
      }
      e.preventDefault();
    }, { passive: false });

    if (!window._snakeKeySetup) {
      window._snakeKeySetup = true;
      window.addEventListener("keydown", (e) => {
        const activeG = window.currentGame || (window.GAMES?.getCurrentGame ? window.GAMES.getCurrentGame() : "snake");
        if (activeG !== "snake" || !snakeRunning) return;
        if (e.key === "ArrowUp" || e.code === "KeyW") setSnakeDir(0, -1);
        else if (e.key === "ArrowDown" || e.code === "KeyS") setSnakeDir(0, 1);
        else if (e.key === "ArrowLeft" || e.code === "KeyA") setSnakeDir(-1, 0);
        else if (e.key === "ArrowRight" || e.code === "KeyD") setSnakeDir(1, 0);
      });
    }
  }

  function initSnake() {
    snake = [
      { x: 4, y: 7 },
      { x: 3, y: 7 },
      { x: 2, y: 7 }
    ];
    snakeDir = { x: 1, y: 0 };
    snakeScore = 0;
    snakeRunning = false;
    spawnFood();
    drawSnakeCanvas();
    setupSnakeTouchListeners();
  }

  function spawnFood() {
    snakeFood = {
      x: Math.floor(Math.random() * GRID_SIZE),
      y: Math.floor(Math.random() * GRID_SIZE)
    };
  }

  function startSnakeGame() {
    initSnake();
    snakeRunning = true;
    const overlay = document.getElementById("snake-overlay");
    if (overlay) overlay.classList.add("hidden");

    if (window._snakeInterval) clearInterval(window._snakeInterval);
    window._snakeInterval = setInterval(snakeTick, 140);
  }

  function setSnakeDir(dx, dy) {
    if (!snakeRunning) return;
    // Prevent 180-degree turn
    if (snakeDir.x + dx === 0 && snakeDir.y + dy === 0) return;
    snakeDir = { x: dx, y: dy };
  }

  function snakeTick() {
    if (!snakeRunning) return;

    const head = { x: snake[0].x + snakeDir.x, y: snake[0].y + snakeDir.y };

    // Wall collision
    if (head.x < 0 || head.x >= GRID_SIZE || head.y < 0 || head.y >= GRID_SIZE) {
      endSnakeGame();
      return;
    }

    // Body collision
    for (let seg of snake) {
      if (seg.x === head.x && seg.y === head.y) {
        endSnakeGame();
        return;
      }
    }

    snake.unshift(head);

    // Food collision
    if (head.x === snakeFood.x && head.y === snakeFood.y) {
      snakeScore++;
      spawnFood();
      const scoreEl = document.getElementById("snake-score");
      if (scoreEl) scoreEl.textContent = snakeScore;

      if (snakeScore > snakeBest) {
        snakeBest = snakeScore;
        localStorage.setItem("game_snake_best", snakeBest);
        const bestEl = document.getElementById("snake-best");
        if (bestEl) bestEl.textContent = snakeBest;
      }

      if (window.Telegram?.WebApp?.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.impactOccurred("medium");
      }
    } else {
      snake.pop();
    }

    drawSnakeCanvas();
  }

  function endSnakeGame() {
    snakeRunning = false;
    if (window._snakeInterval) clearInterval(window._snakeInterval);

    const overlay = document.getElementById("snake-overlay");
    if (overlay) {
      overlay.classList.remove("hidden");
      overlay.innerHTML = `
        <span class="text-3xl">💥</span>
        <p class="text-sm font-black text-rose-400">Игра окончена!</p>
        <p class="text-xs text-slate-300">Счёт: ${snakeScore}</p>
        <button onclick="window.GAMES.startSnakeGame()" class="mt-2 px-3 py-1.5 rounded-xl bg-emerald-600 text-white font-bold text-xs">Играть снова</button>
      `;
    }
  }

  function drawSnakeCanvas() {
    const canvas = document.getElementById("snake-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const cellPx = canvas.width / GRID_SIZE;

    // Clear background
    ctx.fillStyle = "#0f172a"; // dark slate
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw grid lines faintly
    ctx.strokeStyle = "rgba(255, 255, 255, 0.04)";
    ctx.lineWidth = 1;
    for (let i = 0; i <= GRID_SIZE; i++) {
      ctx.beginPath();
      ctx.moveTo(i * cellPx, 0);
      ctx.lineTo(i * cellPx, canvas.height);
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(0, i * cellPx);
      ctx.lineTo(canvas.width, i * cellPx);
      ctx.stroke();
    }

    // Draw Food (Apple)
    ctx.fillStyle = "#ef4444"; // red
    ctx.beginPath();
    ctx.arc((snakeFood.x + 0.5) * cellPx, (snakeFood.y + 0.5) * cellPx, cellPx * 0.4, 0, Math.PI * 2);
    ctx.fill();

    // Draw Snake
    snake.forEach((seg, i) => {
      ctx.fillStyle = i === 0 ? "#10b981" : "#34d399"; // emerald
      ctx.beginPath();
      ctx.roundRect(seg.x * cellPx + 1, seg.y * cellPx + 1, cellPx - 2, cellPx - 2, 4);
      ctx.fill();
    });
  }

  // ==============================================================================


  window.GAMES_SNAKE = {
    renderHTML: renderSnakeHTML,
    init: initSnake,
    cleanup: function() {
      if (window._snakeInterval) {
        clearInterval(window._snakeInterval);
        window._snakeInterval = null;
      }
    },
    startSnakeGame: startSnakeGame,
    setSnakeDir: setSnakeDir
  };
})();
