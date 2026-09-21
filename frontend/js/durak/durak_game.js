/**
 * durak_game.js — Игровой стол, веер карт, перетаскивание (Drag-and-Drop) и синхронизация.
 * Экспортирует window.DURAK_GAME = { renderGame, isGameOver, connectWS, disconnectWS }
 */
(function () {
  'use strict';

  let _ws = null;
  let _pingInterval = null;
  let _pollInterval = null;
  let _reconnectTimer = null;
  let _targetedSlotIndex = null;
  let _outsideClickListener = null;

  function clearOutsideClickListener() {
    if (_outsideClickListener) {
      document.removeEventListener('click', _outsideClickListener);
      document.removeEventListener('touchend', _outsideClickListener);
      _outsideClickListener = null;
    }
  }

  function isGameOver(s) {
    return Boolean(s && s.phase === 'done');
  }

  function renderGame(container, ctx) {
    if (!container || !ctx.getState()) return;
    const s = ctx.getState();
    const uid = ctx.getUserId();
    const myHand = (s.hands && s.hands[String(uid)]) || [];

    const phase = s.phase;
    const isAttacker = s.current_attacker === uid;
    const isDefender = s.current_defender === uid;
    const canAct = (isAttacker && phase === 'attack') || (isDefender && phase === 'defend');
    const selectedCard = ctx.getSelectedCard();

    // ── Веер карт в руке (вид от первого лица, как в руке игрока)
    const handHTML = window.DURAK_CARDS.renderFanHand(myHand, selectedCard, canAct, isGameOver(s));

    // ── Стол (карты атаки и отбоя: отбой поверх со смещением, нижняя карта видна)
    let tableHTML = '';
    if (s.table && s.table.length > 0) {
      s.table.forEach((slot, idx) => {
        const isOpen = slot.defend === null;
        const isTargeted = isDefender && phase === 'defend' && _targetedSlotIndex === idx;
        const canClickSlot = isDefender && phase === 'defend' && isOpen;
        const slotClass = 'dk-slot' + (isTargeted ? ' dk-slot--targeted' : '') + (canClickSlot ? ' dk-slot--clickable' : '');
        const atkCard = window.DURAK_CARDS.cardHTML(slot.attack, false);
        let defCardHTML = '';
        if (slot.defend) {
          defCardHTML = `<div class="dk-slot__def">${window.DURAK_CARDS.cardHTML(slot.defend, false)}</div>`;
        } else if (isDefender && phase === 'defend') {
          defCardHTML = `<div class="dk-slot__empty-def">${isTargeted ? '🎯' : '?'}</div>`;
        }
        tableHTML += `<div class="${slotClass}" data-slot-idx="${idx}" title="${canClickSlot ? 'Сбросьте сюда карту для отбоя' : ''}"><div class="dk-slot__atk">${atkCard}</div>${defCardHTML}</div>`;
      });
    }

    // ── Статус & Подсказки действий
    let statusText = '';
    if (isGameOver(s)) {
      ctx.refreshUserCoins();
      const pot = s.total_pot || (s.stake ? s.stake * 2 : 0);
      if (s.winner === uid) statusText = s.stake > 0 ? `🏆 <b>Вы победили!</b> Выигрыш: <b>+${pot} 🪙</b>` : '🏆 <b>Вы победили!</b>';
      else if (s.loser === uid) statusText = s.stake > 0 ? `🃏 <b>Вы — дурак!</b> Потеряно: <b>-${s.stake} 🪙</b>` : '🃏 <b>Вы — дурак!</b>';
      else if (!s.winner && !s.loser) statusText = '🤝 <b>Ничья!</b> Все карты сброшены одновременно.';
      else statusText = s.loser ? `🃏 Дурак: игрок ${s.loser}` : '🤝 Партия окончена';
    } else if (isAttacker) {
      statusText = (phase === 'attack')
        ? ((s.table && s.table.length > 0) ? '➕ Перетащите карту на стол или нажмите «Бито»' : '⚔️ Перетащите карту на стол для атаки')
        : '⏳ Ожидание защиты соперника…';
    } else if (isDefender) {
      statusText = (phase === 'defend') ? '🛡 Перетащите карту на атакующую, чтобы отбить' : '⏳ Ожидание решения атакующего…';
    } else {
      statusText = `⏳ Ожидание хода игрока ${s.current_attacker}`;
    }

    // ── Кнопка действия в боковой панели («Бито» / «Взять» / «Меню»)
    let actionBtnHTML = '';
    if (!isGameOver(s)) {
      if (isAttacker && phase === 'attack' && s.table && s.table.length > 0) {
        actionBtnHTML = `<button class="dk-btn dk-btn--pass" id="dk-btn-pass">✅ Бито</button>`;
      }
      if (isDefender && phase === 'defend') {
        actionBtnHTML = `<button class="dk-btn dk-btn--take" id="dk-btn-take">📥 Взять</button>`;
      }
    } else {
      actionBtnHTML = `<button class="dk-btn dk-btn--new" id="dk-btn-new">🎮 Меню</button>`;
    }

    // ── Соперники (вверху экрана)
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

    // ── Колода и козырь (в правом столбце)
    let deckColHTML = '';
    if (s.trump_card || s.deck_count > 0) {
      const trumpCardView = s.trump_card
        ? `<div class="dk-trump-under" title="Козырь: ${s.trump_card.suit}">${window.DURAK_CARDS.cardHTML(s.trump_card, false)}</div>`
        : '';
      const deckBadge = s.deck_count > 0 ? `<span class="dk-deck-badge">${s.deck_count}</span>` : '';
      const deckTop = s.deck_count > 0
        ? `<div class="dk-deck-top" title="В колоде: ${s.deck_count}"><div class="dk-card dk-card--back"><img src="/static/img/cards/back.svg" class="dk-card__img" alt="Колода" />${deckBadge}</div></div>`
        : `<div class="dk-deck-top" title="Колода пуста"><div class="dk-card dk-card--empty">∅</div></div>`;
      deckColHTML = `<div class="dk-deck-col">${trumpCardView}${deckTop}</div>`;
    }

    const potBadge = s.stake > 0 ? `<span class="dk-pot">💰 Банк: <b>${s.total_pot || s.stake * 2} 🪙</b></span>` : '';

    container.innerHTML = `
      <div class="dk-game">
        <div class="dk-header"><div class="dk-header-info">${potBadge}</div><button class="dk-btn dk-btn--exit" id="dk-btn-exit">✕ Выйти</button></div>
        <div class="dk-opponents">${opponentsHTML}</div>
        <div class="dk-status">${statusText}</div>
        <div class="dk-arena">
          <div class="dk-table" id="dk-table">${tableHTML || '<span class="dk-table__empty">Стол пуст<br>(перетащите карту сюда)</span>'}</div>
          <div class="dk-sidebar">
            ${deckColHTML}
            <div class="dk-action-col">${actionBtnHTML}</div>
          </div>
        </div>
        <div class="dk-hand-section">
          <button class="dk-nav-arrow dk-nav-arrow--left" id="dk-arrow-left" title="Предыдущая карта" ${myHand.length === 0 ? 'disabled' : ''}>◀</button>
          <div class="dk-hand-wrap" id="dk-hand-wrap">${handHTML}</div>
          <button class="dk-nav-arrow dk-nav-arrow--right" id="dk-arrow-right" title="Следующая карта" ${myHand.length === 0 ? 'disabled' : ''}>▶</button>
        </div>
      </div>`;

    // ── Листание карт стрелками ◀ и ▶
    function cycleCard(step) {
      if (!myHand || myHand.length === 0) return;
      const cur = ctx.getSelectedCard();
      let idx = -1;
      if (cur) {
        idx = myHand.findIndex(c => c.suit === cur.suit && c.rank === cur.rank);
      }
      let nextIdx;
      if (idx === -1) {
        nextIdx = step > 0 ? 0 : (myHand.length - 1);
      } else {
        nextIdx = (idx + step + myHand.length) % myHand.length;
      }
      ctx.setSelectedCard(myHand[nextIdx]);
      if (window.Telegram?.WebApp?.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.selectionChanged();
      }
      renderGame(container, ctx);
    }

    const arrowLeft = container.querySelector('#dk-arrow-left');
    if (arrowLeft && myHand.length > 0) {
      arrowLeft.addEventListener('click', (e) => {
        e.stopPropagation();
        cycleCard(-1);
      });
    }
    const arrowRight = container.querySelector('#dk-arrow-right');
    if (arrowRight && myHand.length > 0) {
      arrowRight.addEventListener('click', (e) => {
        e.stopPropagation();
        cycleCard(1);
      });
    }

    // ── Подключение Drag-and-Drop контроллера
    if (window.DURAK_DRAG) {
      window.DURAK_DRAG.attach({
        container: container,
        canAct: canAct && !isGameOver(s),
        isAttacker: isAttacker && phase === 'attack',
        isDefender: isDefender && phase === 'defend',
        trumpSuit: s.trump_suit,
        tableSlots: s.table || [],
        onAttack: (card) => executeAttack(ctx, container, card),
        onDefend: (card, targetSlot) => executeDefend(ctx, container, card, targetSlot),
        onSelectCard: (card) => {
          const cur = ctx.getSelectedCard();
          ctx.setSelectedCard((cur && cur.suit === card.suit && cur.rank === card.rank) ? null : card);
          renderGame(container, ctx);
        }
      });
    }

    // ── Снятие выбора при клике в произвольную точку экрана (вне карт и стрелок)
    clearOutsideClickListener();
    if (selectedCard) {
      setTimeout(() => {
        if (!ctx.getSelectedCard()) return;
        _outsideClickListener = (e) => {
          if (!ctx.getSelectedCard()) {
            clearOutsideClickListener();
            return;
          }
          if (e.target.closest('.dk-fan-card') || e.target.closest('.dk-nav-arrow') || e.target.closest('.dk-btn')) {
            return;
          }
          clearOutsideClickListener();
          ctx.setSelectedCard(null);
          renderGame(container, ctx);
        };
        document.addEventListener('click', _outsideClickListener);
        document.addEventListener('touchend', _outsideClickListener);
      }, 50);
    }

    // ── Кнопки «Бито», «Взять», «В меню», «Выход»
    const btnTake = container.querySelector('#dk-btn-take');
    if (btnTake) btnTake.addEventListener('click', () => sendMove(ctx, container, { action: 'take' }));

    const btnPass = container.querySelector('#dk-btn-pass');
    if (btnPass) btnPass.addEventListener('click', () => sendMove(ctx, container, { action: 'pass' }));

    const btnNew = container.querySelector('#dk-btn-new');
    if (btnNew) btnNew.addEventListener('click', () => ctx.exitToMenu());

    const btnExit = container.querySelector('#dk-btn-exit');
    if (btnExit) {
      btnExit.addEventListener('click', async () => {
        const curSt = ctx.getState();
        if (!isGameOver(curSt) && curSt && curSt.stake > 0) {
          const isOnline = curSt.player_ids && (!curSt.bot_indices || !curSt.bot_indices.includes(-1)) && curSt.player_ids.length > 1;
          const msg = isOnline
            ? 'Вы уверены, что хотите выйти? Вам будет засчитано поражение, а ставка перейдет сопернику.'
            : 'Вы уверены, что хотите выйти? Ваша ставка будет возвращена.';
          if (typeof confirm !== 'undefined' && !confirm(msg)) return;
        }
        await ctx.exitToMenu();
      });
    }
  }

  async function executeAttack(ctx, container, card) {
    const s = ctx.getState();
    if (s && s.table && s.table.length > 0) {
      const allowedRanks = new Set();
      for (const slot of s.table) {
        allowedRanks.add(String(slot.attack.rank));
        if (slot.defend) allowedRanks.add(String(slot.defend.rank));
      }
      if (!allowedRanks.has(String(card.rank))) {
        showError(container, ctx, 'Можно подкидывать только карты тех же рангов');
        return;
      }
    }
    await sendMove(ctx, container, { action: 'attack', card });
  }

  async function executeDefend(ctx, container, card, targetSlot) {
    const s = ctx.getState();
    if (!targetSlot || !targetSlot.attack) {
      showError(container, ctx, 'Выберите атакующую карту для отбоя');
      return;
    }
    if (!window.DURAK_CARDS.cardBeats(card, targetSlot.attack, s.trump_suit)) {
      showError(container, ctx, 'Этой картой нельзя отбить данную карту');
      return;
    }
    _targetedSlotIndex = null;
    await sendMove(ctx, container, { action: 'defend', attack_card: targetSlot.attack, card });
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
      el.innerHTML = `⚠️ <span style="color:#e11d48;font-weight:700;">${msg}</span>`;
      setTimeout(() => renderGame(container, ctx), 2200);
    }
  }

  function connectWS(roomId, uid, onStateUpdate, onWaitingUpdate, onCanceled, onOpponentLeft) {
    disconnectWS();
    const protocol = (typeof window !== "undefined" && window.location && window.location.protocol === 'https:') ? 'wss:' : 'ws:';
    const host = (typeof window !== "undefined" && window.location && window.location.host) ? window.location.host : 'localhost';
    const url = `${protocol}//${host}/api/ws/durak/${roomId}/${uid}`;

    function createWebSocket() {
      try {
        _ws = new WebSocket(url);
      } catch (e) {
        console.warn('WS connect failed, fallback', e);
        return;
      }

      _ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'state' && onStateUpdate) onStateUpdate(data.state);
          else if (data.type === 'waiting' && onWaitingUpdate) onWaitingUpdate(data.players, data.stake);
          else if (data.type === 'canceled') {
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
        if (_reconnectTimer) clearTimeout(_reconnectTimer);
        _reconnectTimer = setTimeout(() => {
          if (!_ws || _ws.readyState === WebSocket.CLOSED) createWebSocket();
        }, 2000);
      };
    }

    createWebSocket();
    _pingInterval = setInterval(() => {
      if (_ws && _ws.readyState === WebSocket.OPEN) _ws.send('ping');
    }, 25000);

    _pollInterval = setInterval(async () => {
      if (!_ws || _ws.readyState !== WebSocket.OPEN) {
        try {
          const resp = await fetch(`/api/durak/state/${roomId}?user_id=${uid}`);
          if (resp.ok) {
            const data = await resp.json();
            if (data && data.state && onStateUpdate) onStateUpdate(data.state);
          }
        } catch (e) {}
      }
    }, 2500);
  }

  function disconnectWS() {
    clearOutsideClickListener();
    if (window.DURAK_DRAG) window.DURAK_DRAG.cleanup();
    if (_pingInterval) { clearInterval(_pingInterval); _pingInterval = null; }
    if (_pollInterval) { clearInterval(_pollInterval); _pollInterval = null; }
    if (_reconnectTimer) { clearTimeout(_reconnectTimer); _reconnectTimer = null; }
    if (_ws) { try { _ws.close(); } catch (e) {} _ws = null; }
  }

  window.DURAK_GAME = { renderGame, isGameOver, connectWS, disconnectWS };
})();
