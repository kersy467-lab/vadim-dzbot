import { NatAPI } from '../api.js';
import { store } from '../state.js';
import { getItemInfo } from '../items.js';

let activeFilter = 'all';

export async function openCatalogModal(showToast, onBuilt) {
  let modal = document.getElementById('catalog-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'catalog-modal';
    modal.className = 'fixed inset-0 z-50 flex items-center justify-center p-3 bg-black/75 backdrop-blur-sm';
    document.body.appendChild(modal);
  }

  modal.innerHTML = `
    <div class="glass-card rounded-2xl w-full max-w-lg max-h-[90vh] flex flex-col overflow-hidden shadow-2xl border border-slate-700">
      <div class="p-4 border-b border-slate-700/60 flex items-center justify-between bg-slate-900/60">
        <div>
          <h3 id="catalog-count" class="text-base font-black text-white flex items-center gap-2">
            <span>🏭</span> Каталог предприятий
          </h3>
          <p class="text-[11px] text-slate-400">Выберите производство для вашей экономической цепочки</p>
        </div>
        <button id="close-catalog" class="w-8 h-8 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 flex items-center justify-center font-bold text-sm">✕</button>
      </div>

      <!-- Filters -->
      <div class="p-2 border-b border-slate-800 bg-slate-950/40 flex flex-wrap gap-1.5 text-[11px] font-bold">
        <button data-cat="all" class="cat-btn min-h-9 px-2.5 py-1.5 rounded-lg whitespace-nowrap ${activeFilter === 'all' ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-300'}">Все</button>
        <button data-cat="own" class="cat-btn min-h-9 px-2.5 py-1.5 rounded-lg whitespace-nowrap ${activeFilter === 'own' ? 'bg-amber-600 text-white' : 'bg-slate-800 text-amber-400'}">⭐ Моя отрасль</button>
        <button data-cat="recommended" class="cat-btn min-h-9 px-2.5 py-1.5 rounded-lg whitespace-nowrap ${activeFilter === 'recommended' ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-emerald-400'}">💰 Выгоднее</button>
        <button data-cat="available" class="cat-btn min-h-9 px-2.5 py-1.5 rounded-lg whitespace-nowrap ${activeFilter === 'available' ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-emerald-400'}">Доступные</button>
        <button data-cat="unavailable" class="cat-btn min-h-9 px-2.5 py-1.5 rounded-lg whitespace-nowrap ${activeFilter === 'unavailable' ? 'bg-rose-600 text-white' : 'bg-slate-800 text-rose-400'}">Недоступные</button>
        <button data-cat="extraction" class="cat-btn min-h-9 px-2.5 py-1.5 rounded-lg whitespace-nowrap ${activeFilter === 'extraction' ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-300'}">Добыча</button>
        <button data-cat="processing" class="cat-btn min-h-9 px-2.5 py-1.5 rounded-lg whitespace-nowrap ${activeFilter === 'processing' ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-300'}">Переработка</button>
        <button data-cat="industry" class="cat-btn min-h-9 px-2.5 py-1.5 rounded-lg whitespace-nowrap ${activeFilter === 'industry' ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-300'}">Пром-сть</button>
        <button data-cat="hightech" class="cat-btn min-h-9 px-2.5 py-1.5 rounded-lg whitespace-nowrap ${activeFilter === 'hightech' ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-300'}">Технологии</button>
      </div>

      <!-- Items List -->
      <div id="catalog-list" class="p-3 space-y-2.5 overflow-y-auto flex-1">
        <div class="p-8 text-center text-xs text-slate-400">Загрузка каталога...</div>
      </div>
    </div>
  `;

  modal.classList.remove('hidden');
  modal.querySelector('#close-catalog')?.addEventListener('click', () => modal.classList.add('hidden'));
  modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.classList.add('hidden');
  });

  let cachedCatalog = null;
  const loadList = async () => {
    const listEl = modal.querySelector('#catalog-list');
    if (!listEl) return;
    if (cachedCatalog) {
      renderCatalogCards(listEl, cachedCatalog, showToast, onBuilt, modal);
      return;
    }
    try {
      const res = await NatAPI.getBuildingsCatalog();
      cachedCatalog = res?.catalog || [];
      const count = Number.isFinite(Number(res?.total)) ? Number(res.total) : cachedCatalog.length;
      const countEl = modal.querySelector('#catalog-count');
      if (countEl) countEl.innerHTML = `<span>🏭</span> Каталог предприятий (${count})`;
      renderCatalogCards(listEl, cachedCatalog, showToast, onBuilt, modal);
    } catch (err) {
      listEl.innerHTML = `<div class="p-4 text-center text-xs text-rose-400">Не удалось загрузить каталог: ${err.message}</div>`;
    }
  };

  modal.querySelectorAll('.cat-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      activeFilter = btn.dataset.cat;
      modal.querySelectorAll('.cat-btn').forEach(b => {
        b.className = `cat-btn min-h-9 px-2.5 py-1.5 rounded-lg whitespace-nowrap ${b.dataset.cat === activeFilter ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-300'}`;
      });
      loadList();
    });
  });

  await loadList();
}

function renderCatalogCards(listEl, catalog, showToast, onBuilt, modal) {
  let filtered = catalog;
  if (activeFilter === 'own') {
    filtered = catalog.filter(b => b.is_own_specialization);
  } else if (activeFilter === 'recommended') {
    filtered = catalog.filter(b => b.recommended_for_specialization);
  } else if (activeFilter === 'available') {
    filtered = catalog.filter(b => b.can_build);
  } else if (activeFilter === 'unavailable') {
    filtered = catalog.filter(b => !b.can_build);
  } else if (activeFilter !== 'all') {
    filtered = catalog.filter(b => b.category === activeFilter);
  }

  if (filtered.length === 0) {
    listEl.innerHTML = '<div class="p-8 text-center text-xs text-slate-400">В этой категории нет доступных производств.</div>';
    return;
  }

  listEl.innerHTML = filtered.map(b => {
    const isOwn = Boolean(b.is_own_specialization);
    const unlocked = Boolean(b.unlocked);
    const canAfford = Boolean(b.can_afford);
    const hasSlot = Boolean(b.has_construction_slot);
    const hasLicense = Boolean(b.required_license_active);
    const profitability = b.profitability || {};

    const inList = Object.entries(b.inputs || {}).map(([k, v]) => {
      const info = getItemInfo(k);
      return `${v} ${info.unit} ${info.name}`;
    }).join(', ') || 'Без затрат';

    const outList = Object.entries(b.outputs || {}).map(([k, v]) => {
      const info = getItemInfo(k);
      return `+${v} ${info.unit} ${info.name}`;
    }).join(', ') || '—';

    let btnHtml = '';
    if (!unlocked) {
      btnHtml = `<button disabled class="w-full py-2 rounded-xl bg-slate-800/80 text-slate-500 text-xs font-bold cursor-not-allowed">🔒 Требуется ур. ${b.level_required}</button>`;
    } else if (!hasLicense) {
      btnHtml = `<button disabled class="w-full py-2 rounded-xl bg-slate-800/80 text-amber-300 text-xs font-bold cursor-not-allowed">🔐 Нужна лицензия</button>`;
    } else if (!hasSlot) {
      btnHtml = `<button disabled class="w-full py-2 rounded-xl bg-slate-800/80 text-amber-300 text-xs font-bold cursor-not-allowed">Нет свободного строительного слота</button>`;
    } else if (!canAfford) {
      btnHtml = `<button disabled class="w-full py-2 rounded-xl bg-slate-800/80 text-rose-400/80 text-xs font-bold cursor-not-allowed">Не хватает: ${Math.round(b.build_cost).toLocaleString('ru-RU')} ₽</button>`;
    } else {
      btnHtml = `<button data-id="${b.id}" class="btn-build w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow-lg shadow-emerald-600/25 transition-all">Построить за ${Math.round(b.build_cost).toLocaleString('ru-RU')} ₽</button>`;
    }

    const efficiencyLabel = isOwn
      ? '🌟 Ваша отрасль (100%)'
      : (b.is_licensed_foreign ? '🔐 Лицензия (12%)' : '⚠️ Чужая отрасль (10%)');
    const estimateLabel = Number.isFinite(Number(profitability.net_per_cycle))
      ? `Оценка NPC: ${Number(profitability.net_per_cycle) >= 0 ? '+' : ''}${Math.round(profitability.net_per_cycle).toLocaleString('ru-RU')} ₽/цикл · ${Number(profitability.net_per_hour) >= 0 ? '+' : ''}${Math.round(profitability.net_per_hour).toLocaleString('ru-RU')} ₽/ч`
      : 'Оценка рентабельности недоступна';
    const paybackLabel = profitability.payback_hours === null || profitability.payback_hours === undefined
      ? 'Окупаемость не рассчитана'
      : `Оценка окупаемости: ${Number(profitability.payback_hours).toLocaleString('ru-RU')} ч`;
    const recommendation = b.recommended_for_specialization
      ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 whitespace-nowrap">💰 Приоритет №${b.recommendation_rank} в отрасли</span>`
      : '';

    return `
      <div class="p-3.5 rounded-xl border ${isOwn ? 'border-amber-500/40 bg-amber-950/10' : 'border-slate-800 bg-slate-900/40'} space-y-2">
        <div class="flex items-start justify-between gap-2">
          <div>
            <div class="text-xs font-black text-white flex items-center gap-1.5">
              <span>${b.name}</span>
            </div>
            <div class="text-[10px] text-slate-400 mt-0.5">${b.description || ''}</div>
          </div>
          <div class="flex flex-col items-end gap-1">
            <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${isOwn ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' : 'bg-slate-800 text-slate-400'} whitespace-nowrap">${efficiencyLabel}</span>
            ${recommendation}
          </div>
        </div>

        <div class="rounded-lg bg-slate-950/40 p-2 text-[10px] ${Number(profitability.net_per_cycle) > 0 ? 'text-emerald-300' : 'text-amber-300'}">
          <div class="font-bold">${estimateLabel}</div>
          <div>${paybackLabel}</div>
          <div class="text-slate-500">Оценка маржи по ценам NPC; без зарплат, налогов и сделок игроков.</div>
        </div>

        <div class="text-[11px] space-y-0.5 bg-slate-950/40 p-2 rounded-lg font-mono">
          <div class="text-slate-400 flex items-center justify-between">
            <span>📥 Вход:</span> <span class="text-slate-300 font-sans text-right">${inList}</span>
          </div>
          <div class="text-emerald-400 flex items-center justify-between font-bold">
            <span>📤 Выход:</span> <span class="text-emerald-300 font-sans text-right">${outList}</span>
          </div>
        </div>

        <div class="flex items-center justify-between text-[10px] text-slate-400 px-1">
          <span>⏱️ ${b.cycle_duration} сек</span>
          <span>👷 ${b.workers_required} раб.</span>
          <span>⚡ ${b.energy_required} кВт</span>
          <span>🔒 Ур. ${b.level_required}</span>
        </div>

        <div>
          ${btnHtml}
        </div>
      </div>
    `;
  }).join('');

  listEl.querySelectorAll('.btn-build').forEach(btn => {
    btn.addEventListener('click', async () => {
      const bId = btn.dataset.id;
      if (!bId || btn.disabled) return;
      btn.disabled = true;
      btn.innerText = 'Строительство...';
      try {
        const res = await NatAPI.buildEnterprise(bId);
        if (res.remaining_cash !== undefined) {
          store.updateCompany({ cash: res.remaining_cash });
        }
        const paid = Number(res.cost_paid || 0).toLocaleString('ru-RU');
        showToast(`Построено: ${res.name || bId}. Списано ${paid} ₽.`, 'success');
        modal.classList.add('hidden');
        if (onBuilt) await onBuilt();
      } catch (err) {
        showToast(err.message, 'error');
        btn.disabled = false;
        btn.innerText = 'Попробовать снова';
      }
    });
  });
}
