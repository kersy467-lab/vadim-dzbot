/**
 * casino_leaderboard.js — Подвкладка «Рейтинг богачей» в играх Mini App.
 * Экспортирует window.CASINO_LEADERBOARD = { init, load, render }
 */
(function () {
  'use strict';

  let containerEl = null;
  let isLoading = false;
  let leaders = [];
  let errorMsg = null;

  function injectCSS() {
    if (document.getElementById('casino-lb-styles')) return;
    const style = document.createElement('style');
    style.id = 'casino-lb-styles';
    style.textContent = `
      .clb-card { border-radius: 16px; transition: all 0.15s ease; }
      .clb-card--me { border-color: #f59e0b !important; background: rgba(245, 158, 11, 0.08) !important; }
      .clb-rank { width: 34px; height: 34px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-weight: 900; font-size: 0.85rem; flex-shrink: 0; }
      .clb-rank-1 { background: #fef3c7; color: #b45309; }
      .clb-rank-2 { background: #f1f5f9; color: #475569; }
      .clb-rank-3 { background: #ffedd5; color: #c2410c; }
      .clb-rank-other { background: rgba(0,0,0,0.05); color: #64748b; }
      .dark .clb-rank-other { background: rgba(255,255,255,0.08); color: #94a3b8; }
    `;
    document.head.appendChild(style);
  }

  function getMyUserId() {
    try {
      if (window.currentUser && window.currentUser.id) return window.currentUser.id;
      if (window.currentUser && window.currentUser.tg_id) return window.currentUser.tg_id;
      if (window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
        return window.Telegram.WebApp.initDataUnsafe.user.id;
      }
    } catch (e) {}
    return null;
  }

  function getMyCoins() {
    return Number(window.currentUser?.coins || 0);
  }

  async function loadLeaderboard() {
    if (isLoading) return;
    isLoading = true;
    errorMsg = null;
    render();

    try {
      const res = await fetch('/api/casino/leaderboard');
      if (!res.ok) {
        throw new Error(`Ошибка загрузки (${res.status})`);
      }
      const data = await res.json();
      leaders = data.leaderboard || [];
    } catch (e) {
      errorMsg = e.message || 'Не удалось загрузить рейтинг';
    } finally {
      isLoading = false;
      render();
    }
  }

  function renderHTML() {
    const myUid = getMyUserId();
    const myCoins = getMyCoins();

    let contentHTML = '';

    if (isLoading && !leaders.length) {
      contentHTML = `
        <div class="py-12 text-center text-slate-400 text-xs font-semibold animate-pulse">
          ⏳ Загрузка рейтинга игроков...
        </div>
      `;
    } else if (errorMsg) {
      contentHTML = `
        <div class="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 text-rose-700 dark:text-rose-300 text-xs text-center space-y-2">
          <p>${errorMsg}</p>
          <button onclick="window.CASINO_LEADERBOARD.load()" class="px-3 py-1 rounded-lg bg-rose-600 text-white font-bold hover:bg-rose-700 transition-all">
            Повторить попытку
          </button>
        </div>
      `;
    } else if (!leaders.length) {
      contentHTML = `
        <div class="py-10 text-center text-slate-400 text-xs font-semibold">
          Пока никто не включил игровую экосистему 🪙
        </div>
      `;
    } else {
      const rowsHTML = leaders.map(l => {
        const isMe = (myUid && (l.tg_id === myUid || l.id === myUid));
        let rankBadge = `<span class="clb-rank clb-rank-other">#${l.rank}</span>`;
        if (l.rank === 1) rankBadge = `<span class="clb-rank clb-rank-1">🥇</span>`;
        else if (l.rank === 2) rankBadge = `<span class="clb-rank clb-rank-2">🥈</span>`;
        else if (l.rank === 3) rankBadge = `<span class="clb-rank clb-rank-3">🥉</span>`;

        const uname = l.username ? `<span class="text-[11px] text-slate-400 font-medium">@${l.username}</span>` : '';

        return `
          <div class="clb-card p-2.5 bg-white dark:bg-slate-800/90 border border-slate-200/80 dark:border-slate-700 flex items-center justify-between gap-2.5 ${isMe ? 'clb-card--me shadow-sm' : ''}">
            <div class="flex items-center gap-2.5 min-w-0">
              ${rankBadge}
              <div class="min-w-0">
                <div class="text-xs font-black text-slate-900 dark:text-white truncate flex items-center gap-1">
                  <span>${l.name}</span>
                  ${isMe ? '<span class="text-[10px] px-1.5 py-0.2 bg-amber-500 text-black font-extrabold rounded-md">ВЫ</span>' : ''}
                </div>
                ${uname}
              </div>
            </div>
            <div class="text-right shrink-0">
              <span class="text-xs font-black text-amber-600 dark:text-amber-400 font-mono">${l.coins}</span>
              <span class="text-[10px] font-bold text-slate-400 ml-0.5">🪙</span>
            </div>
          </div>
        `;
      }).join('');

      contentHTML = `<div class="space-y-1.5">${rowsHTML}</div>`;
    }

    return `
      <div class="space-y-3 max-w-md mx-auto">
        <!-- Шапка рейтинга -->
        <div class="p-3 bg-gradient-to-br from-amber-500/15 via-orange-500/10 to-transparent dark:from-amber-950/40 dark:via-orange-950/20 rounded-2xl border border-amber-300/40 dark:border-amber-700/40 flex items-center justify-between">
          <div>
            <h3 class="text-sm font-black text-slate-900 dark:text-white flex items-center gap-1.5">
              <span>🏆</span> <span>Рейтинг богачей</span>
            </h3>
            <p class="text-[11px] text-slate-500 dark:text-slate-400 font-medium">Топ игроков 11 «Б» по монетам</p>
          </div>
          <div class="flex items-center gap-2">
            <div class="text-right">
              <div class="text-[10px] font-bold text-slate-400">Ваш баланс</div>
              <div class="text-xs font-black text-amber-600 dark:text-amber-400 font-mono">${myCoins} 🪙</div>
            </div>
            <button onclick="window.CASINO_LEADERBOARD.load()" ${isLoading ? 'disabled' : ''} class="w-8 h-8 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 flex items-center justify-center text-slate-600 dark:text-slate-300 hover:text-amber-500 transition-all ${isLoading ? 'opacity-50' : 'active:scale-95'}" title="Обновить рейтинг">
              🔄
            </button>
          </div>
        </div>

        <!-- Список лидеров -->
        <div id="casino-lb-container">
          ${contentHTML}
        </div>
      </div>
    `;
  }

  function render() {
    if (!containerEl) return;
    containerEl.innerHTML = renderHTML();
  }

  function init(el) {
    containerEl = el || document.getElementById('casino-leaderboard-root');
    injectCSS();
    loadLeaderboard();
  }

  window.CASINO_LEADERBOARD = {
    init: init,
    load: loadLeaderboard,
    render: render
  };
})();
