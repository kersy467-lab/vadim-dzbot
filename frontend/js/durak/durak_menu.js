/**
 * durak_menu.js — Меню, выбор ставок, рейтинг и лобби для игры «Дурак».
 * Экспортирует window.DURAK_MENU = { showMenu, showLeaderboard, showOnlineMenu, renderWaiting }
 */
(function () {
  'use strict';

  function showMenu(container, ctx) {
    if (!container) return;
    const coins = ctx.getUserCoins();
    let selectedStake = ctx.getSelectedStake();
    if (selectedStake > coins) {
      selectedStake = coins;
      ctx.setSelectedStake(selectedStake);
    }

    container.innerHTML = `
      <div class="dk-menu">
        <div class="dk-menu__title">🃏 Дурак</div>
        <div class="dk-menu__subtitle">Классическая карточная игра 11 «Б»</div>

        <!-- Баланс монет -->
        <div class="dk-coins-badge">
          🪙 Баланс: <b>${coins}</b> монет
        </div>

        <!-- Блок выбора ставки -->
        <div class="dk-stake-box">
          <div class="dk-stake-header">
            <span class="dk-stake-title">Ставка на игру:</span>
            <span class="dk-stake-val" id="dk-stake-val">${selectedStake} 🪙</span>
          </div>

          <!-- Быстрые пресеты -->
          <div class="dk-stake-group" id="dk-stake-group">
            <button type="button" class="dk-stake-opt ${selectedStake === 0 ? 'active' : ''}" data-val="0">Без ставки</button>
            <button type="button" class="dk-stake-opt ${selectedStake === 10 ? 'active' : ''}" data-val="10">10</button>
            <button type="button" class="dk-stake-opt ${selectedStake === 25 ? 'active' : ''}" data-val="25">25</button>
            <button type="button" class="dk-stake-opt ${selectedStake === 50 ? 'active' : ''}" data-val="50">50</button>
            <button type="button" class="dk-stake-opt ${selectedStake === 100 ? 'active' : ''}" data-val="100">100</button>
          </div>

          <!-- Произвольная ставка и Ва-банк -->
          <div class="dk-custom-stake-wrap">
            <div class="dk-input-with-icon">
              <span class="dk-input-icon">🪙</span>
              <input 
                type="number" 
                id="dk-custom-stake-input" 
                class="dk-stake-input" 
                placeholder="Своя ставка..." 
                min="0" 
                max="${coins}" 
                value="${selectedStake > 0 ? selectedStake : ''}" 
              />
            </div>
            <button type="button" class="dk-btn-all-in" id="dk-stake-all-in" title="Поставить все монеты">
              🔥 Ва-банк
            </button>
          </div>
          <div class="dk-stake-hint" id="dk-stake-hint">
            ${coins === 0 ? 'У вас 0 монет (игра доступна без ставки)' : `Доступно для ставки: ${coins} 🪙`}
          </div>
        </div>

        <!-- Режимы игры -->
        <button class="dk-btn dk-btn--primary" id="dk-mode-bot">🤖 Против бота</button>
        <button class="dk-btn dk-btn--primary" id="dk-mode-online">👥 Онлайн комната</button>
        
        <div class="dk-menu__room-join" style="display:flex; gap:8px; width:100%; max-width:280px;">
          <input class="dk-input" id="dk-join-id" placeholder="Код комнаты" style="flex:1;" />
          <button class="dk-btn" id="dk-join-btn" style="background:#0284c7; color:#fff; padding:8px 14px;">Вступить</button>
        </div>
      </div>`;

    const stakeValEl = container.querySelector('#dk-stake-val');
    const stakeInputEl = container.querySelector('#dk-custom-stake-input');
    const presetBtns = container.querySelectorAll('.dk-stake-opt');

    function syncStake(val, fromInput = false) {
      let num = parseInt(val, 10);
      if (isNaN(num) || num < 0) num = 0;
      if (num > coins) num = coins;

      ctx.setSelectedStake(num);
      if (stakeValEl) stakeValEl.textContent = `${num} 🪙`;

      presetBtns.forEach(btn => {
        const pval = parseInt(btn.dataset.val, 10);
        if (pval === num) btn.classList.add('active');
        else btn.classList.remove('active');
      });

      if (!fromInput && stakeInputEl) {
        stakeInputEl.value = num > 0 ? num : '';
      }
    }

    presetBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        syncStake(btn.dataset.val, false);
      });
    });

    if (stakeInputEl) {
      stakeInputEl.addEventListener('input', (e) => {
        syncStake(e.target.value, true);
      });
      stakeInputEl.addEventListener('change', (e) => {
        syncStake(e.target.value, false);
      });
    }

    const allInBtn = container.querySelector('#dk-stake-all-in');
    if (allInBtn) {
      allInBtn.addEventListener('click', () => {
        syncStake(coins, false);
      });
    }

    container.querySelector('#dk-mode-bot').addEventListener('click', () => {
      if (ctx.getSelectedStake() > coins) {
        alert(`Недостаточно монет! Ваш баланс: ${coins} 🪙`);
        return;
      }
      ctx.startBotGame();
    });

    container.querySelector('#dk-mode-online').addEventListener('click', () => {
      if (ctx.getSelectedStake() > coins) {
        alert(`Недостаточно монет! Ваш баланс: ${coins} 🪙`);
        return;
      }
      showOnlineMenu(container, ctx);
    });

    container.querySelector('#dk-join-btn').addEventListener('click', () => {
      const rid = container.querySelector('#dk-join-id').value.trim();
      if (rid) ctx.joinRoom(rid);
    });
  }

  function showLeaderboard(container, ctx) {
    if (window.GAMES && typeof window.GAMES.switchCasinoSubGame === 'function') {
      window.GAMES.switchCasinoSubGame('leaderboard');
    }
  }

  function showOnlineMenu(container, ctx) {
    if (!container) return;
    const stake = ctx.getSelectedStake();
    container.innerHTML = `
      <div class="dk-menu">
        <div class="dk-menu__title">👥 Онлайн «Дурак»</div>
        <div class="dk-coins-badge">Ставка: <b>${stake}</b> 🪙 (с каждого игрока)</div>
        <label class="dk-label">Количество игроков:
          <select class="dk-select" id="dk-players-count">
            <option value="2">2 игрока</option>
            <option value="3">3 игрока</option>
            <option value="4">4 игрока</option>
            <option value="5">5 игроков</option>
            <option value="6">6 игроков</option>
          </select>
        </label>
        <button class="dk-btn dk-btn--primary" id="dk-create-online">Создать комнату</button>
        <button class="dk-btn" id="dk-back-menu" style="background:#e2e8f0; color:#1e293b;">← Назад</button>
      </div>`;

    container.querySelector('#dk-create-online').addEventListener('click', async () => {
      const cnt = parseInt(container.querySelector('#dk-players-count').value, 10);
      ctx.createOnlineRoom(cnt, stake);
    });

    container.querySelector('#dk-back-menu').addEventListener('click', () => {
      showMenu(container, ctx);
    });
  }

  function renderWaiting(container, roomId, players, stake, onCancel, isCreator = true) {
    if (!container) return;
    const stakeText = stake > 0 ? `<div class="dk-waiting__stake">💰 Ставка: <b>${stake} 🪙</b></div>` : '';
    const shareUrl = `${window.location.origin}/app?room=${roomId}&game=durak`;
    const exitBtnText = isCreator ? '✕ Отменить комнату' : '✕ Выйти из комнаты';
    container.innerHTML = `
      <div class="dk-waiting">
        <div class="dk-waiting__title">⏳ Ожидание игроков…</div>
        <div class="dk-waiting__count">Подключено: ${players.length}</div>
        ${stakeText}
        <div class="dk-waiting__hint">Код комнаты: <b>${roomId}</b></div>
        
        <div style="display:flex; flex-direction:column; gap:8px; width:100%; max-width:280px; margin:12px 0;">
          <button type="button" class="dk-btn" id="dk-copy-link" style="background:#2563eb; color:#fff; font-weight:700; padding:10px; border-radius:12px;">🔗 Скопировать ссылку</button>
          <button type="button" class="dk-btn" id="dk-share-tg" style="background:#0284c7; color:#fff; font-weight:700; padding:10px; border-radius:12px;">✈️ Поделиться в Telegram</button>
        </div>

        <button class="dk-btn dk-btn--exit" id="dk-cancel-room">${exitBtnText}</button>
      </div>`;

    const copyBtn = container.querySelector('#dk-copy-link');
    if (copyBtn) {
      copyBtn.addEventListener('click', async () => {
        try {
          if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(shareUrl);
          } else {
            const ta = document.createElement('textarea');
            ta.value = shareUrl;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
          }
          copyBtn.textContent = '✅ Ссылка скопирована!';
          if (window.Telegram?.WebApp?.HapticFeedback) {
            window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
          }
          setTimeout(() => { if (copyBtn) copyBtn.textContent = '🔗 Скопировать ссылку'; }, 2500);
        } catch (e) {
          prompt('Скопируйте ссылку вручную:', shareUrl);
        }
      });
    }

    const shareBtn = container.querySelector('#dk-share-tg');
    if (shareBtn) {
      shareBtn.addEventListener('click', () => {
        const text = `🃏 Сыграем в Дурака на перемене! Заходи в комнату: ${roomId}`;
        const tgLink = `https://t.me/share/url?url=${encodeURIComponent(shareUrl)}&text=${encodeURIComponent(text)}`;
        if (window.Telegram?.WebApp?.openTelegramLink) {
          window.Telegram.WebApp.openTelegramLink(tgLink);
        } else {
          window.open(tgLink, '_blank');
        }
      });
    }

    const cancelBtn = container.querySelector('#dk-cancel-room');
    if (cancelBtn && onCancel) {
      cancelBtn.addEventListener('click', onCancel);
    }
  }

  window.DURAK_MENU = { showMenu, showLeaderboard, showOnlineMenu, renderWaiting };
})();
