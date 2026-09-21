/**
 * durak_cards.js — Карточный рендеринг, правила старшинства, веер и стили для игры «Дурак».
 * Экспортирует window.DURAK_CARDS = { cardHTML, cardKey, injectCSS, SUIT_COLOR, cardBeats, RANK_ORDER, renderFanHand }
 */
(function () {
  'use strict';

  const SUIT_COLOR = { '♠': '#1a1a2e', '♣': '#16213e', '♥': '#e94560', '♦': '#e94560' };
  const SUIT_NAME_MAP = { '♠': 'spades', '♣': 'clubs', '♥': 'hearts', '♦': 'diamonds' };
  const RANK_ORDER = { '6': 0, '7': 1, '8': 2, '9': 3, '10': 4, 'J': 5, 'Q': 6, 'K': 7, 'A': 8 };

  function cardBeats(defCard, atkCard, trumpSuit) {
    if (!defCard || !atkCard) return false;
    const defRank = RANK_ORDER[defCard.rank];
    const atkRank = RANK_ORDER[atkCard.rank];
    if (defRank === undefined || atkRank === undefined) return false;

    if (defCard.suit === atkCard.suit) return defRank > atkRank;
    if (defCard.suit === trumpSuit && atkCard.suit !== trumpSuit) return true;
    return false;
  }

  function cardHTML(card, faceDown = false, selectable = false, selected = false) {
    if (faceDown) {
      return `
        <div class="dk-card dk-card--back">
          <img src="/static/img/cards/back.svg" class="dk-card__img" alt="Рубашка" />
        </div>`;
    }
    if (!card || !card.suit || !card.rank) {
      return `<div class="dk-card dk-card--empty">?</div>`;
    }
    const suitName = SUIT_NAME_MAP[card.suit] || 'spades';
    const sel = selected ? ' dk-card--selected' : '';
    const cls = selectable ? ' dk-card--selectable' : '';
    const color = SUIT_COLOR[card.suit] || '#111';
    const imgSrc = `/static/img/cards/${card.rank}_${suitName}.png`;
    const svgSrc = `/static/img/cards/${card.rank}_${suitName}.svg`;

    return `
      <div class="dk-card${cls}${sel}" data-suit="${card.suit}" data-rank="${card.rank}">
        <img src="${imgSrc}" onerror="this.onerror=null;this.src='${svgSrc}';this.onerror=function(){this.style.display='none';var fb=this.parentNode.querySelector('.dk-card__fallback');if(fb)fb.style.display='flex';};" class="dk-card__img" alt="${card.rank}${card.suit}" />
        <div class="dk-card__fallback" style="display:none;flex-direction:column;align-items:center;justify-content:center;width:100%;height:100%;color:${color};font-weight:900;font-size:1.1rem;line-height:1.2;">
          <span>${card.rank}</span>
          <span style="font-size:1.3rem;">${card.suit}</span>
        </div>
      </div>`;
  }

  function cardKey(card) {
    if (!card) return '';
    return `${card.suit}${card.rank}`;
  }

  function renderFanHand(cards, selectedCard, canAct, isGameOver) {
    if (!Array.isArray(cards) || cards.length === 0) {
      return '<div class="text-xs text-slate-400 py-6 font-bold text-center">Нет карт на руках</div>';
    }
    const count = cards.length;
    const mid = (count - 1) / 2;
    const maxSpread = Math.min(18, count * 3.0);
    const stepAngle = count > 1 ? (maxSpread * 2) / (count - 1) : 0;
    const maxSpan = Math.min(175, (count - 1) * 26);
    const stepSpacing = count > 1 ? maxSpan / (count - 1) : 0;

    return cards.map((c, i) => {
      const isSel = selectedCard && cardKey(selectedCard) === cardKey(c);
      const dist = i - mid;
      const rot = count > 1 ? (-maxSpread + i * stepAngle) : 0;
      const transX = dist * stepSpacing;
      const normDist = count > 1 ? dist / mid : 0;
      const transY = Math.abs(normDist) * Math.abs(normDist) * 10;
      const zIndex = isSel ? 100 : (i + 1);
      const html = cardHTML(c, false, canAct && !isGameOver, isSel);
      const style = `left:calc(50% - 31px); transform: translateX(${transX.toFixed(1)}px) translateY(${transY.toFixed(1)}px) rotate(${rot.toFixed(1)}deg); z-index:${zIndex};`;

      return `
        <div class="dk-fan-card${isSel ? ' dk-fan-card--selected' : ''}" style="${style}"
             data-card-idx="${i}" data-suit="${c.suit}" data-rank="${c.rank}"
             data-rot="${rot.toFixed(1)}" data-tx="${transX.toFixed(1)}" data-ty="${transY.toFixed(1)}">
          ${html}
        </div>`;
    }).join('');
  }

  function injectCSS() {
    if (document.getElementById('durak-css')) return;
    const style = document.createElement('style');
    style.id = 'durak-css';
    style.textContent = `
      .dk-menu { display:flex; flex-direction:column; align-items:center; gap:12px; padding:16px 12px; }
      .dk-menu__title { font-size:1.8rem; font-weight:800; }
      .dk-menu__subtitle { color:#888; margin-bottom:4px; font-size:0.85rem; }
      .dk-coins-badge { background:rgba(234, 179, 8, 0.15); border:1px solid rgba(234, 179, 8, 0.4); color:#b45309; padding:6px 14px; border-radius:12px; font-size:0.9rem; font-weight:700; }
      .dk-stake-box { display:flex; flex-direction:column; gap:8px; background:rgba(0,0,0,0.03); border:1px solid rgba(0,0,0,0.06); padding:12px 14px; border-radius:16px; width:100%; max-width:300px; }
      .dk-stake-header { display:flex; justify-content:space-between; align-items:center; }
      .dk-stake-title { font-size:0.75rem; font-weight:700; color:#64748b; text-transform:uppercase; letter-spacing:0.5px; }
      .dk-stake-val { font-size:0.9rem; font-weight:800; color:#b45309; }
      .dk-stake-group { display:flex; gap:5px; justify-content:center; flex-wrap:wrap; }
      .dk-stake-opt { padding:6px 10px; border-radius:10px; border:1.5px solid #94a3b8; background:#fff; color:#0f172a; font-size:0.8rem; font-weight:800; cursor:pointer; transition:all 0.15s; }
      .dk-stake-opt:hover:not(.active) { background:#f1f5f9; color:#0f172a; border-color:#64748b; }
      .dk-stake-opt.active { background:#2563eb; color:#ffffff !important; border-color:#2563eb; box-shadow:0 2px 6px rgba(37,99,235,0.3); }
      .dk-custom-stake-wrap { display:flex; gap:6px; align-items:center; margin-top:2px; }
      .dk-input-with-icon { position:relative; flex:1; display:flex; align-items:center; }
      .dk-input-icon { position:absolute; left:10px; font-size:0.9rem; pointer-events:none; }
      .dk-stake-input { width:100%; border:1.5px solid #cbd5e1; border-radius:10px; padding:7px 10px 7px 32px; font-size:0.85rem; font-weight:700; outline:none; transition:border-color 0.15s; background:#fff; color:#0f172a; }
      .dk-stake-input:focus { border-color:#2563eb; }
      .dk-btn-all-in { padding:7px 10px; border:1.5px solid #f59e0b; background:rgba(245, 158, 11, 0.12); color:#b45309; border-radius:10px; font-size:0.8rem; font-weight:800; cursor:pointer; white-space:nowrap; transition:all 0.15s; }
      .dk-btn-all-in:hover { background:rgba(245, 158, 11, 0.25); }
      .dk-stake-hint { font-size:0.75rem; color:#64748b; text-align:center; }
      .dk-pot { background:rgba(234, 179, 8, 0.2); border:1px solid #facc15; color:#854d0e; padding:3px 8px; border-radius:8px; font-size:0.8rem; font-weight:800; }
      .dk-game { display:flex; flex-direction:column; height:100%; padding:6px; gap:8px; }
      .dk-header { display:flex; align-items:center; justify-content:space-between; font-size:.9rem; padding:0 4px; }
      .dk-header-info { display:flex; align-items:center; gap:8px; }
      .dk-opponents { display:flex; flex-wrap:wrap; gap:6px; justify-content:center; }
      .dk-opponent { font-size:.8rem; background:rgba(0,0,0,.06); border-radius:8px; padding:4px 10px; font-weight:600; }
      .dk-status { text-align:center; font-size:.85rem; font-weight:600; padding:6px; background:rgba(0,0,0,.05); border-radius:8px; }

      /* Центральная арена: стол слева, колода и кнопка действия справа */
      .dk-arena { display:flex; gap:10px; align-items:stretch; width:100%; min-height:175px; position:relative; }
      .dk-table { flex:1; min-height:165px; display:flex; flex-wrap:wrap; gap:12px; align-items:center; justify-content:center; background:rgba(0,120,60,.08); border-radius:14px; padding:8px; border:2px dashed rgba(0,120,60,.25); transition:all 0.2s ease; position:relative; }
      .dk-table--drop-ready { border-color:#2563eb !important; background:rgba(37,99,235,0.12) !important; box-shadow:0 0 16px rgba(37,99,235,0.2) inset; }
      .dk-table__empty { color:#94a3b8; font-size:.85rem; font-weight:500; text-align:center; }

      /* Слот карт на столе (отбой кладется поверх со смещением, видно обе карты) */
      .dk-slot { position:relative; width:64px; height:92px; border-radius:8px; transition:all 0.15s ease; user-select:none; }
      .dk-slot--clickable { cursor:pointer; }
      .dk-slot--clickable:hover { transform:scale(1.05); }
      .dk-slot--targeted { outline:2.5px solid #16a34a; outline-offset:2px; border-radius:10px; }
      .dk-slot--drop-ready { outline:2.5px dashed #22c55e !important; outline-offset:3px; border-radius:10px; transform:scale(1.06); }
      .dk-slot__atk { position:absolute; top:0; left:0; z-index:1; }
      .dk-slot__def { position:absolute; top:16px; left:12px; z-index:2; filter:drop-shadow(0 4px 10px rgba(0,0,0,0.38)); }
      .dk-slot__empty-def { position:absolute; top:16px; left:12px; z-index:2; width:52px; height:74px; border:2px dashed rgba(37,99,235,0.45); border-radius:6px; display:flex; align-items:center; justify-content:center; background:rgba(37,99,235,0.08); color:#2563eb; font-size:0.9rem; font-weight:800; pointer-events:none; }

      /* Боковая панель: колода сверху, кнопка хода ниже */
      .dk-sidebar { width:74px; display:flex; flex-direction:column; align-items:center; justify-content:space-between; gap:8px; flex-shrink:0; }
      .dk-deck-col { position:relative; width:64px; height:82px; display:flex; align-items:center; justify-content:center; margin-top:4px; }
      .dk-trump-under { position:absolute; top:6px; left:-8px; transform:rotate(90deg); transform-origin:center; z-index:1; border:2px solid #facc15; border-radius:6px; box-shadow:0 0 10px rgba(234,179,8,0.4); }
      .dk-trump-under .dk-card { width:50px; height:70px; }
      .dk-deck-top { position:relative; z-index:2; }
      .dk-deck-top .dk-card { width:52px; height:74px; }
      .dk-deck-badge { position:absolute; bottom:-4px; right:-4px; background:#1e293b; color:#fff; font-size:0.7rem; font-weight:800; padding:2px 6px; border-radius:10px; border:1.5px solid #fff; z-index:3; box-shadow:0 2px 4px rgba(0,0,0,0.25); }
      .dk-action-col { width:100%; display:flex; flex-direction:column; align-items:center; gap:6px; margin-top:auto; }
      .dk-action-col .dk-btn { width:100%; padding:10px 4px; font-size:0.82rem; font-weight:800; border-radius:10px; line-height:1.2; text-align:center; box-shadow:0 3px 8px rgba(0,0,0,0.2); }

      /* Нижняя зона: стрелка ◀, веер увеличенных карт, стрелка ▶ */
      .dk-hand-section { display:flex; align-items:flex-end; justify-content:space-between; width:100%; position:relative; margin-top:auto; padding:0 2px; }
      .dk-nav-arrow { width:38px; height:38px; border-radius:50%; background:#1e293b; color:#fff; border:1.5px solid rgba(255,255,255,0.25); font-size:1.1rem; font-weight:900; display:flex; align-items:center; justify-content:center; cursor:pointer; box-shadow:0 4px 12px rgba(0,0,0,0.3); z-index:10; margin-bottom:26px; transition:all 0.15s ease; flex-shrink:0; }
      .dk-nav-arrow:hover { background:#2563eb; transform:scale(1.1); box-shadow:0 6px 16px rgba(37,99,235,0.45); }
      .dk-nav-arrow:active { transform:scale(0.92); }
      .dk-nav-arrow:disabled { opacity:0.25; cursor:not-allowed; pointer-events:none; }
      .dk-hand-wrap { flex:1; position:relative; width:100%; height:120px; margin:0 auto; display:flex; justify-content:center; align-items:flex-end; perspective:800px; user-select:none; }
      .dk-fan-card { position:absolute; bottom:0; transform-origin:50% 120%; transition:transform 0.2s cubic-bezier(0.2, 0.8, 0.3, 1), box-shadow 0.2s ease; cursor:grab; touch-action:none; }
      .dk-fan-card .dk-card { width:62px; height:86px; }
      .dk-fan-card:hover { z-index:99 !important; transform:translateY(-22px) rotate(0deg) scale(1.12) !important; box-shadow:0 12px 24px rgba(0,0,0,0.35); }
      .dk-fan-card--selected { z-index:100 !important; transform:translateY(-36px) rotate(0deg) scale(1.18) !important; box-shadow:0 16px 32px rgba(37,99,235,0.65) !important; }
      .dk-fan-card.dk-card--dragging { opacity:0.25; pointer-events:none; }

      /* Плавающий аватар при перетаскивании (уменьшается до компактного размера стола) */
      .dk-drag-avatar { position:fixed; pointer-events:none; z-index:999999; transform:translate(-50%, -50%) scale(0.95); filter:drop-shadow(0 14px 26px rgba(0,0,0,0.4)); will-change:left, top; }
      .dk-drag-avatar .dk-card { width:52px; height:74px; }

      .dk-actions { display:flex; gap:8px; flex-wrap:wrap; justify-content:center; padding:4px 0; }
      .dk-card { width:52px; height:74px; border-radius:8px; display:inline-flex; align-items:center; justify-content:center; user-select:none; position:relative; background:#fff; box-shadow:0 2px 6px rgba(0,0,0,0.14); }
      .dk-card__img { width:100%; height:100%; object-fit:contain; pointer-events:none; border-radius:8px; }
      .dk-card--back { width:52px; height:74px; }
      .dk-card--empty { width:52px; height:74px; background:rgba(0,0,0,.04); border:2px dashed #cbd5e1; border-radius:8px; color:#94a3b8; font-size:1.3rem; display:flex; align-items:center; justify-content:center; }
      .dk-btn { padding:10px 16px; border:none; border-radius:10px; cursor:pointer; font-size:.85rem; font-weight:700; transition:opacity .15s, transform .1s; }
      .dk-btn:active { transform:scale(0.98); }
      .dk-btn:disabled { opacity:.4; cursor:not-allowed; }
      .dk-btn--primary { background:#2563eb; color:#fff; width:100%; max-width:280px; }
      .dk-btn--take { background:#d97706; color:#fff; }
      .dk-btn--pass { background:#059669; color:#fff; }
      .dk-btn--new { background:#7c3aed; color:#fff; }
      .dk-btn--exit { background:none; border:1.5px solid #cbd5e1; color:#64748b; padding:5px 10px; font-size:.8rem; border-radius:8px; }
      .dk-waiting { display:flex; flex-direction:column; align-items:center; gap:12px; padding:32px; }
      .dk-waiting__title { font-size:1.4rem; font-weight:700; }
      .dk-waiting__count { color:#888; }
      .dk-waiting__stake { color:#b45309; font-weight:700; font-size:1rem; }
    `;
    document.head.appendChild(style);
  }

  window.DURAK_CARDS = { cardHTML, cardKey, injectCSS, SUIT_COLOR, cardBeats, RANK_ORDER, renderFanHand };
})();
