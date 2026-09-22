/**
 * durak_cards.js — Карточный рендеринг и стили для игры «Дурак».
 * Экспортирует window.DURAK_CARDS = { cardHTML, cardKey, injectCSS, SUIT_COLOR }
 */
(function () {
  'use strict';

  const SUIT_COLOR = { '♠': '#1a1a2e', '♣': '#16213e', '♥': '#e94560', '♦': '#e94560' };
  const SUIT_NAME_MAP = { '♠': 'spades', '♣': 'clubs', '♥': 'hearts', '♦': 'diamonds' };

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
    const imgSrc = `/static/img/cards/${card.rank}_${suitName}.png`;

    return `
      <div class="dk-card${cls}${sel}" data-suit="${card.suit}" data-rank="${card.rank}">
        <img src="${imgSrc}" onerror="this.onerror=null;this.src='/static/img/cards/${card.rank}_${suitName}.svg'" class="dk-card__img" alt="${card.rank}${card.suit}" />
      </div>`;
  }

  function cardKey(card) {
    if (!card) return '';
    return `${card.suit}${card.rank}`;
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
      
      /* Блок выбора ставки */
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

      /* Рейтинг */
      .dk-leaderboard-box { width:100%; max-width:320px; display:flex; flex-direction:column; gap:6px; max-height:260px; overflow-y:auto; padding:4px; }
      .dk-lead-row { display:flex; align-items:center; justify-content:space-between; padding:8px 12px; background:rgba(0,0,0,0.03); border-radius:10px; font-size:0.85rem; }
      .dk-lead-row--me { background:rgba(37, 99, 235, 0.1); border:1px solid rgba(37, 99, 235, 0.3); }
      .dk-lead-rank { font-weight:800; width:45px; }
      .dk-lead-info { display:flex; flex-direction:column; flex:1; text-align:left; }
      .dk-lead-name { font-weight:700; }
      .dk-lead-uname { font-size:0.7rem; color:#64748b; }
      .dk-lead-coins { font-weight:800; color:#b45309; }

      /* Игровой экран */
      .dk-game { display:flex; flex-direction:column; height:100%; padding:6px; gap:8px; }
      .dk-header { display:flex; align-items:center; justify-content:space-between; font-size:.9rem; padding:0 4px; }
      .dk-header-info { display:flex; align-items:center; gap:8px; }
      
      /* Колода и козырь на столе */
      .dk-deck-cluster { display:flex; align-items:center; justify-content:center; gap:16px; padding:8px; background:rgba(15,23,42,0.04); border-radius:14px; border:1px solid rgba(15,23,42,0.06); }
      .dk-trump-slot { display:flex; flex-direction:column; align-items:center; gap:4px; }
      .dk-trump-slot .dk-card { border:2px solid #facc15; box-shadow:0 0 12px rgba(234,179,8,0.35); }
      .dk-trump-tag { font-size:0.65rem; font-weight:900; color:#b45309; background:#fef3c7; border:1px solid #fde68a; padding:2px 6px; border-radius:6px; letter-spacing:0.5px; }
      .dk-deck-slot { display:flex; flex-direction:column; align-items:center; gap:4px; position:relative; }
      .dk-deck-badge { position:absolute; bottom:-6px; right:-6px; background:#1e293b; color:#fff; font-size:0.7rem; font-weight:800; padding:2px 6px; border-radius:10px; border:1.5px solid #fff; box-shadow:0 2px 4px rgba(0,0,0,0.25); }
      .dk-deck-label { font-size:0.65rem; font-weight:700; color:#64748b; }

      .dk-opponents { display:flex; flex-wrap:wrap; gap:6px; justify-content:center; }
      .dk-opponent { font-size:.8rem; background:rgba(0,0,0,.06); border-radius:8px; padding:4px 10px; font-weight:600; }
      .dk-status { text-align:center; font-size:.9rem; font-weight:600; padding:6px; background:rgba(0,0,0,.05); border-radius:8px; }
      .dk-table { min-height:92px; display:flex; flex-wrap:wrap; gap:8px; align-items:center; justify-content:center;
                  background:rgba(0,120,60,.08); border-radius:14px; padding:10px; border:1px dashed rgba(0,120,60,.25); }
      .dk-table__empty { color:#94a3b8; font-size:.85rem; font-weight:500; }
      .dk-slot { display:flex; flex-direction:column; align-items:center; gap:3px; }
      .dk-slot__arr { font-size:.7rem; color:#94a3b8; line-height:1; }
      .dk-hand { display:flex; flex-wrap:wrap; gap:6px; justify-content:center; padding:6px 0; min-height:86px; }
      .dk-actions { display:flex; gap:8px; flex-wrap:wrap; justify-content:center; padding:4px 0; }

      /* Карта */
      .dk-card { width:58px; height:82px; border-radius:8px; display:inline-flex;
                 align-items:center; justify-content:center; user-select:none;
                 position:relative; transition:transform .15s ease, filter .15s ease; background:#fff; box-shadow:0 2px 6px rgba(0,0,0,0.12); }
      .dk-card__img { width:100%; height:100%; object-fit:contain; pointer-events:none; border-radius:8px; }
      .dk-card--back { width:58px; height:82px; }
      .dk-card--empty { width:58px; height:82px; background:rgba(0,0,0,.04); border:2px dashed #cbd5e1;
                        border-radius:8px; color:#94a3b8; font-size:1.5rem; display:flex;
                        align-items:center; justify-content:center; box-shadow:none; }
      .dk-card--selectable { cursor:pointer; }
      .dk-card--selectable:hover { transform:translateY(-6px); filter:drop-shadow(0 6px 14px rgba(0,0,0,.22)); }
      .dk-card--selected { transform:translateY(-10px); filter:drop-shadow(0 8px 18px rgba(225,29,72,.45)); }

      /* Кнопки */
      .dk-btn { padding:10px 18px; border:none; border-radius:10px; cursor:pointer;
                font-size:.9rem; font-weight:600; transition:opacity .15s, transform .1s; }
      .dk-btn:active { transform:scale(0.98); }
      .dk-btn:disabled { opacity:.4; cursor:not-allowed; }
      .dk-btn--primary { background:#2563eb; color:#fff; width:100%; max-width:280px; }
      .dk-btn--leaderboard { background:#f59e0b; color:#fff; width:100%; max-width:280px; }
      .dk-btn--attack { background:#e94560; color:#fff; }
      .dk-btn--defend { background:#16a34a; color:#fff; }
      .dk-btn--take { background:#ca8a04; color:#fff; }
      .dk-btn--pass { background:#6b7280; color:#fff; }
      .dk-btn--new { background:#7c3aed; color:#fff; }
      .dk-btn--exit { background:none; border:1.5px solid #cbd5e1; color:#64748b; padding:6px 12px; font-size:.8rem; border-radius:8px; }
      .dk-input { border:1.5px solid #cbd5e1; border-radius:8px; padding:8px 12px; font-size:.9rem; width:140px; }
      .dk-select { border:1.5px solid #cbd5e1; border-radius:8px; padding:6px 10px; font-size:.9rem; }
      .dk-label { font-size:.9rem; display:flex; align-items:center; gap:8px; }
      .dk-error { padding:24px; text-align:center; color:#e94560; font-weight:600; }
      .dk-waiting { display:flex; flex-direction:column; align-items:center; gap:12px; padding:32px; }
      .dk-waiting__title { font-size:1.4rem; font-weight:700; }
      .dk-waiting__count { color:#888; }
      .dk-waiting__stake { color:#b45309; font-weight:700; font-size:1rem; }
      .dk-waiting__hint { background:rgba(0,0,0,.05); border-radius:8px; padding:10px 16px; font-size:.85rem; }
    `;
    document.head.appendChild(style);
  }

  window.DURAK_CARDS = { cardHTML, cardKey, injectCSS, SUIT_COLOR };
})();
