/**
 * durak_drag.js — Drag-and-Drop контроллер для карт в игре «Дурак».
 * Экспортирует window.DURAK_DRAG = { attach, cleanup }
 */
(function () {
  'use strict';

  let _activeAvatar = null;
  let _draggedCard = null;
  let _isDragging = false;
  let _startX = 0;
  let _startY = 0;
  let _cleanupFn = null;

  function cleanup() {
    if (_activeAvatar && _activeAvatar.parentNode) {
      _activeAvatar.parentNode.removeChild(_activeAvatar);
    }
    _activeAvatar = null;
    _draggedCard = null;
    _isDragging = false;
    if (_cleanupFn) {
      _cleanupFn();
      _cleanupFn = null;
    }
    document.querySelectorAll('.dk-card--dragging').forEach(el => el.classList.remove('dk-card--dragging'));
    document.querySelectorAll('.dk-table--drop-ready').forEach(el => el.classList.remove('dk-table--drop-ready'));
    document.querySelectorAll('.dk-slot--drop-ready').forEach(el => el.classList.remove('dk-slot--drop-ready'));
  }

  function attach(opts) {
    cleanup();
    const { container, canAct, isAttacker, isDefender, trumpSuit, tableSlots, onAttack, onDefend, onSelectCard } = opts;
    if (!container || !canAct) return;

    const fanCards = container.querySelectorAll('.dk-fan-card');
    if (fanCards.length === 0) return;

    function getCoords(e) {
      if (e.touches && e.touches.length > 0) {
        return { x: e.touches[0].clientX, y: e.touches[0].clientY };
      }
      if (e.changedTouches && e.changedTouches.length > 0) {
        return { x: e.changedTouches[0].clientX, y: e.changedTouches[0].clientY };
      }
      return { x: e.clientX, y: e.clientY };
    }

    function onStart(e, cardEl) {
      if (!canAct) return;
      const { suit, rank } = cardEl.dataset;
      if (!suit || !rank) return;

      const pt = getCoords(e);
      _startX = pt.x;
      _startY = pt.y;
      _draggedCard = { suit, rank };
      _isDragging = false;

      function onMove(moveEvent) {
        const cur = getCoords(moveEvent);
        const dx = cur.x - _startX;
        const dy = cur.y - _startY;

        if (!_isDragging && (Math.abs(dx) > 7 || Math.abs(dy) > 7)) {
          _isDragging = true;
          cardEl.classList.add('dk-card--dragging');

          _activeAvatar = document.createElement('div');
          _activeAvatar.className = 'dk-drag-avatar';
          _activeAvatar.innerHTML = window.DURAK_CARDS.cardHTML(_draggedCard, false);
          document.body.appendChild(_activeAvatar);

          if (window.Telegram?.WebApp?.HapticFeedback) {
            window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
          }
        }

        if (_isDragging && _activeAvatar) {
          moveEvent.preventDefault();
          _activeAvatar.style.left = `${cur.x}px`;
          _activeAvatar.style.top = `${cur.y}px`;

          const elemBelow = document.elementFromPoint(cur.x, cur.y);
          const tableEl = container.querySelector('.dk-table');
          const slotEl = elemBelow ? elemBelow.closest('.dk-slot') : null;

          document.querySelectorAll('.dk-table--drop-ready').forEach(el => el.classList.remove('dk-table--drop-ready'));
          document.querySelectorAll('.dk-slot--drop-ready').forEach(el => el.classList.remove('dk-slot--drop-ready'));

          if (isAttacker && tableEl && (elemBelow === tableEl || tableEl.contains(elemBelow))) {
            tableEl.classList.add('dk-table--drop-ready');
          } else if (isDefender) {
            if (slotEl) {
              const idx = parseInt(slotEl.dataset.slotIdx, 10);
              const sl = (tableSlots || [])[idx];
              if (sl && sl.defend === null && window.DURAK_CARDS.cardBeats(_draggedCard, sl.attack, trumpSuit)) {
                slotEl.classList.add('dk-slot--drop-ready');
              }
            } else if (tableEl && (elemBelow === tableEl || tableEl.contains(elemBelow))) {
              const hasBeatable = (tableSlots || []).some(sl => sl.defend === null && window.DURAK_CARDS.cardBeats(_draggedCard, sl.attack, trumpSuit));
              if (hasBeatable) tableEl.classList.add('dk-table--drop-ready');
            }
          }
        }
      }

      function onEnd(endEvent) {
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onEnd);
        document.removeEventListener('touchmove', onMove);
        document.removeEventListener('touchend', onEnd);
        document.removeEventListener('touchcancel', onEnd);

        if (_isDragging && _draggedCard) {
          const cur = getCoords(endEvent);
          const elemBelow = document.elementFromPoint(cur.x, cur.y);
          const tableEl = container.querySelector('.dk-table');
          const slotEl = elemBelow ? elemBelow.closest('.dk-slot') : null;

          let handled = false;
          if (isDefender) {
            if (slotEl) {
              const idx = parseInt(slotEl.dataset.slotIdx, 10);
              const sl = (tableSlots || [])[idx];
              if (sl && sl.defend === null && window.DURAK_CARDS.cardBeats(_draggedCard, sl.attack, trumpSuit)) {
                handled = true;
                onDefend(_draggedCard, sl);
              }
            }
            if (!handled && tableEl && (elemBelow === tableEl || tableEl.contains(elemBelow))) {
              const beatable = (tableSlots || []).filter(sl => sl.defend === null && window.DURAK_CARDS.cardBeats(_draggedCard, sl.attack, trumpSuit));
              if (beatable.length > 0) {
                handled = true;
                onDefend(_draggedCard, beatable[0]);
              }
            }
          } else if (isAttacker) {
            if (tableEl && (elemBelow === tableEl || tableEl.contains(elemBelow))) {
              handled = true;
              onAttack(_draggedCard);
            }
          }

          if (handled && window.Telegram?.WebApp?.HapticFeedback) {
            window.Telegram.WebApp.HapticFeedback.notificationOccurred('success');
          }
        } else if (!_isDragging && _draggedCard) {
          onSelectCard(_draggedCard);
        }

        cleanup();
      }

      document.addEventListener('mousemove', onMove, { passive: false });
      document.addEventListener('mouseup', onEnd);
      document.addEventListener('touchmove', onMove, { passive: false });
      document.addEventListener('touchend', onEnd);
      document.addEventListener('touchcancel', onEnd);
    }

    fanCards.forEach(cardEl => {
      cardEl.addEventListener('mousedown', (e) => onStart(e, cardEl));
      cardEl.addEventListener('touchstart', (e) => onStart(e, cardEl), { passive: true });
    });

    _cleanupFn = () => {
      fanCards.forEach(cardEl => {
        cardEl.onmousedown = null;
        cardEl.ontouchstart = null;
      });
    };
  }

  window.DURAK_DRAG = { attach, cleanup };
})();
