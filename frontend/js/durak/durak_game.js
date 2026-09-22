/**
 * durak_game.js — Игровой стол, визуализация козыря картой, действия и WebSocket.
 * Экспортирует window.DURAK_GAME = { renderGame, isGameOver, connectWS, disconnectWS }
 */
(function () {
  'use strict';

  let _ws = null;
  let _pingInterval = null;

  function isGameOver(s) {
    return Boolean(s && s.phase === 'done');
  }

  function renderGame(container, ctx) {
    if (!container || !ctx.getState()) return;
    const s = ctx.getState();
    const uid = ctx.getUserId();
    const myHand = (s.hands && s.hands[String(uid)]) || [];
    const isMyHandArray = Array.isArray(myHand);

    const phase = s.phase;
    const isAttacker = s.current_attacker === uid;
    const isDefender = s.current_defender === uid;
    const myTurn = isAttacker || isDefender;
    const selectedCard = ctx.getSelectedCard();

    // ── Рука игрока
    let handHTML = '';
    if (isMyHandArray) {
      handHTML = myHand.map(c => {
        const isSelected = selectedCard && window.DURAK_CARDS.cardKey(selectedCard) === window.DURAK_CARDS.cardKey(c);
        const selectable = myTurn && !isGameOver(s);
        return window.DURAK_CARDS.cardHTML(c, false, selectable, isSelected);
      }).join('');
    }

    // ── Стол (карты атаки и отбоя)
    let tableHTML = '';
    if (s.table && s.table.length > 0) {
      for (const slot of s.table) {
        const atkCard = window.DURAK_CARDS.cardHTML(slot.attack, false);
        const defCard = slot.defend
          ? window.DURAK_CARDS.cardHTML(slot.defend, false)
          : `<div class="dk-card dk-card--empty">?</div>`;
        tableHTML += `<div class="dk-slot">${atkCard}<div class="dk-slot__arr">▼</div>${defCard}</div>`;
      }
    }

    // ── Статус & Банк
    let statusText = '';
    if (isGameOver(s)) {
      ctx.refreshUserCoins();
      const pot = s.total_pot || (s.stake ? s.stake * 2 : 0);
      if (s.winner === uid) {
        statusText = s.stake > 0
          ? `🏆 <b>Вы победили!</b> Выигрыш: <b>+${pot} 🪙</b>`
          : '🏆 <b>Вы победили!</b>';
      } else if (s.loser === uid) {
        statusText = s.stake > 0
          ? `🃏 <b>Вы — дурак!</b> Потеряно: <b>-${s.stake} 🪙</b>`
          : '🃏 <b>Вы — дурак!</b>';
      } else {
        statusText = s.loser ? `🃏 Дурак: игрок ${s.loser}` : '🤝 Ничья!';
      }
    } else if (isAttacker) {
      statusText = phase === 'attack' ? '⚔️ Ваш ход — атакуйте' : '✅ Атака принята — можно подкинуть или передать ход';
    } else if (isDefender) {
      statusText = '🛡 Выберите карту для отбоя';
    } else {
      const whose = isAttacker ? 'вашего' : `игрока ${s.current_attacker}`;
      statusText = `⏳ Ожидание хода ${whose}`;
    }

    // ── Кнопки действий
    let actionsHTML = '';
    if (!isGameOver(s)) {
      if (isAttacker && phase === 'attack') {
        actionsHTML += `<button class="dk-btn dk-btn--attack" id="dk-btn-attack" ${!selectedCard ? 'disabled' : ''}>⚔️ Атаковать</button>`;
      }
      if (isAttacker && phase === 'attack' && s.table && s.table.length > 0) {
        actionsHTML += `<button class="dk-btn dk-btn--pass" id="dk-btn-pass">🔄 Передать ход</button>`;
      }
      if (isDefender && phase === 'defend') {
        actionsHTML += `<button class="dk-btn dk-btn--defend" id="dk-btn-defend" ${!selectedCard ? 'disabled' : ''}>🛡 Отбить</button>`;
        actionsHTML += `<button class="dk-btn dk-btn--take" id="dk-btn-take">📥 Взять</button>`;
      }
    } else {
      actionsHTML = `<button class="dk-btn dk-btn--new" id="dk-btn-new">🎮 В меню / Новая игра</button>`;
    }

    // ── Другие игроки (соперники)
    let opponentsHTML = '';
    if (s.player_ids) {
      for (const pid of s.player_ids) {
        if (pid === uid) continue;
        const hand = s.hands ? s.hands[String(pid)] : null;
        const count = Array.isArray(hand) ? hand.length : (hand || 0);
        const isBot = s.bot_indices && s.bot_indices.includes(pid);
        const label = isBot ? '🤖 Бот' : `Игрок ${pid}`;
        const isAtk = s.current_attacker === pid ? ' 🗡' : '';
        const isDef = s.current_defender === pid ? ' 🛡' : '';
        opponentsHTML += `<div class="dk-opponent">${label}${isAtk}${isDef}: ${count} карт</div>`;
      }
    }

    // ── Визуальный блок козыря картой и колоды
    let deckClusterHTML = '';
    if (s.trump_card || s.deck_count > 0) {
      const trumpCardView = s.trump_card
        ? `<div class="dk-trump-slot" title="Козырная масть: ${s.trump_card.suit}">
             ${window.DURAK_CARDS.cardHTML(s.trump_card, false)}
             <div class="dk-trump-tag">👑 КОЗЫРЬ</div>
           </div>`
        : '';

      const deckView = s.deck_count > 0
        ? `<div class="dk-deck-slot" title="Осталось карт: ${s.deck_count}">
             <div class="dk-card dk-card--back">
               <img src="/static/img/cards/back.svg" class="dk-card__img" alt="Колода" />
               <span class="dk-deck-badge">${s.deck_count}</span>
             </div>
             <div class="dk-deck-label">Колода</div>
           </div>`
        : `<div class="dk-deck-slot" title="Колода пуста">
             <div class="dk-card dk-card--empty">∅</div>
             <div class="dk-deck-label">Пусто</div>
           </div>`;

      deckClusterHTML = `
        <div class="dk-deck-cluster">
          ${trumpCardView}
          ${deckView}
        </div>`;
    }

    const potBadge = s.stake > 0
      ? `<span class="dk-pot">💰 Банк: <b>${s.total_pot || s.stake * 2} 🪙</b></span>`
      : '';

    container.innerHTML = `
      <div class="dk-game">
        <div class="dk-header">
          <div class="dk-header-info">
            ${potBadge}
          </div>
          <button class="dk-btn dk-btn--exit" id="dk-btn-exit">✕ Выйти</button>
        </div>
        <div class="dk-opponents">${opponentsHTML}</div>
        ${deckClusterHTML}
        <div class="dk-status">${statusText}</div>
        <div class="dk-table">${tableHTML || '<span class="dk-table__empty">Стол пуст</span>'}</div>
        <div class="dk-hand">${handHTML}</div>
        <div class="dk-actions">${actionsHTML}</div>
      </div>`;

    // ── Обработчики кликов на карты в руке
    container.querySelectorAll('.dk-card--selectable').forEach(el => {
      el.addEventListener('click', () => {
        const suit = el.dataset.suit;
        const rank = el.dataset.rank;
        const cur = ctx.getSelectedCard();
        if (cur && cur.suit === suit && cur.rank === rank) {
          ctx.setSelectedCard(null);
        } else {
          ctx.setSelectedCard({ suit, rank });
        }
        renderGame(container, ctx);
      });
    });

    // ── Обработчики кнопок
    const btnAttack = container.querySelector('#dk-btn-attack');
    if (btnAttack) btnAttack.addEventListener('click', () => doAttack(ctx, container));

    const btnDefend = container.querySelector('#dk-btn-defend');
    if (btnDefend) btnDefend.addEventListener('click', () => doDefend(ctx, container));

    const btnTake = container.querySelector('#dk-btn-take');
    if (btnTake) btnTake.addEventListener('click', () => doTake(ctx, container));

    const btnPass = container.querySelector('#dk-btn-pass');
    if (btnPass) btnPass.addEventListener('click', () => doPass(ctx, container));

    const btnNew = container.querySelector('#dk-btn-new');
    if (btnNew) btnNew.addEventListener('click', () => ctx.exitToMenu());

    const btnExit = container.querySelector('#dk-btn-exit');
    if (btnExit) {
      btnExit.addEventListener('click', async () => {
        const s = ctx.getState();
        if (!isGameOver(s) && s && s.stake > 0) {
          const isOnline = s.player_ids && (!s.bot_indices || !s.bot_indices.includes(-1)) && s.player_ids.length > 1;
          const msg = isOnline
            ? 'Вы уверены, что хотите выйти? Вам будет засчитано поражение, а ставка перейдет сопернику.'
            : 'Вы уверены, что хотите выйти? Ваша ставка будет возвращена.';
          if (typeof confirm !== 'undefined' && !confirm(msg)) {
            return;
          }
        }
        await ctx.exitToMenu();
      });
    }
  }

  async function doAttack(ctx, container) {
    const card = ctx.getSelectedCard();
    if (!card) return;
    await sendMove(ctx, container, { action: 'attack', card });
  }

  async function doDefend(ctx, container) {
    const card = ctx.getSelectedCard();
    if (!card) return;
    const s = ctx.getState();
    const openSlot = s && s.table && s.table.find(slot => slot.defend === null);
    if (!openSlot) return;
    await sendMove(ctx, container, {
      action: 'defend',
      attack_card: openSlot.attack,
      card: card
    });
  }

  async function doTake(ctx, container) {
    await sendMove(ctx, container, { action: 'take' });
  }

  async function doPass(ctx, container) {
    await sendMove(ctx, container, { action: 'pass' });
  }

  async function sendMove(ctx, container, payload) {
    try {
      const roomId = ctx.getRoomId();
      const res = await ctx.apiPost('/api/durak/move', { ...payload, room_id: roomId });
      ctx.setSelectedCard(null);
      ctx.setState(res.state);
      renderGame(container, ctx);
    } catch (e) {
      showError(container, ctx, e.message);
    }
  }

  function showError(container, ctx, msg) {
    const el = container && container.querySelector('.dk-status');
    if (el) {
      el.innerHTML = `⚠️ <span style="color:#e94560;">${msg}</span>`;
      setTimeout(() => renderGame(container, ctx), 2200);
    }
  }

  // ── WebSocket
  function connectWS(roomId, uid, onStateUpdate, onWaitingUpdate, onCanceled, onOpponentLeft) {
    disconnectWS();
    const protocol = (typeof window !== "undefined" && window.location && window.location.protocol === 'https:') ? 'wss:' : 'ws:';
    const host = (typeof window !== "undefined" && window.location && window.location.host) ? window.location.host : 'localhost';
    const url = `${protocol}//${host}/api/ws/durak/${roomId}/${uid}`;

    try {
      _ws = new WebSocket(url);
    } catch (e) {
      console.warn('WS connect failed, fallback', e);
      return;
    }

    _ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'state' && onStateUpdate) {
          onStateUpdate(data.state);
        } else if (data.type === 'waiting' && onWaitingUpdate) {
          onWaitingUpdate(data.players, data.stake);
        } else if (data.type === 'canceled') {
          if (typeof alert !== 'undefined' && data.message) alert(data.message);
          if (onCanceled) onCanceled();
        } else if (data.type === 'opponent_left') {
          if (typeof alert !== 'undefined') alert('Соперник покинул игру. Победа присуждена вам!');
          if (onOpponentLeft) onOpponentLeft(data);
          else if (onStateUpdate && data.state) onStateUpdate(data.state);
        }
      } catch (e) {}
    };

    _ws.onclose = () => {
      // Reconnect if room active
    };

    _pingInterval = setInterval(() => {
      if (_ws && _ws.readyState === WebSocket.OPEN) {
        _ws.send('ping');
      } else {
        clearInterval(_pingInterval);
      }
    }, 25000);
    if (_pingInterval && typeof _pingInterval.unref === 'function') {
      _pingInterval.unref();
    }
  }

  function disconnectWS() {
    if (_pingInterval) {
      clearInterval(_pingInterval);
      _pingInterval = null;
    }
    if (_ws) {
      try { _ws.close(); } catch (e) {}
      _ws = null;
    }
  }

  window.DURAK_GAME = { renderGame, isGameOver, connectWS, disconnectWS };
})();
