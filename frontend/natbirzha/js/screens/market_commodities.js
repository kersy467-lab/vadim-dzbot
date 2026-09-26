import { getItemInfo } from '../items.js?v=20260926_local_update_v1';

export function getCompanyInputIds(businesses, factories, recipes) {
  const inputs = new Set();
  for (const business of Array.isArray(businesses) ? businesses : []) {
    for (const itemId of Object.keys(business?.inputs_per_hour || {})) inputs.add(itemId);
  }

  const recipeCatalog = recipes && typeof recipes === 'object' ? recipes : {};
  for (const factory of Array.isArray(factories) ? factories : []) {
    const factoryType = factory?.building_type || factory?.factory_type;
    const requestedRecipe = factory?.current_recipe || factory?.default_recipe;
    const recipeId = requestedRecipe && recipeCatalog[requestedRecipe]
      ? requestedRecipe
      : Object.entries(recipeCatalog).find(([, recipe]) => recipe?.factory_type === factoryType)?.[0];
    for (const itemId of Object.keys(recipeCatalog[recipeId]?.inputs || {})) inputs.add(itemId);
  }
  return [...inputs];
}

function escapeMarketText(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));
}

function formatPrice(value) {
  const amount = Number(value);
  return Number.isFinite(amount) ? amount.toLocaleString('ru-RU', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }) : '—';
}

export function rankLiquidityRows(rows) {
  return (Array.isArray(rows) ? rows : [])
    .filter((row) => Number.isFinite(Number(row?.buyer_cash_paid)) && Number(row.buyer_cash_paid) > 0)
    .slice()
    .sort((left, right) =>
      Number(right.buyer_cash_paid) - Number(left.buyer_cash_paid)
      || String(left.item_id || '').localeCompare(String(right.item_id || ''), 'ru')
    );
}

export function renderCommodityCatalog(container, options) {
  const { items, inventory, inputIds, state, onBack, onSelect } = options;
  const tabs = [
    { id: 'search', label: 'Поиск' },
    { id: 'industry', label: 'Моя продукция' },
    { id: 'needed', label: 'Нужно заводам' },
    { id: 'liquidity', label: 'Ликвидность' },
  ];
  const industryItems = items.filter((item) => item.isIndustry);
  const needed = new Set(Array.isArray(inputIds) ? inputIds : []);
  const sourceItems = state.category === 'industry'
    ? industryItems
    : state.category === 'needed'
      ? items.filter((item) => needed.has(item.id))
      : items;
  const query = String(state.query || '').trim().toLocaleLowerCase('ru-RU');
  const visibleItems = state.category === 'search' && query
    ? sourceItems.filter((item) => `${item.name} ${item.id}`.toLocaleLowerCase('ru-RU').includes(query))
    : sourceItems;
  const liquidityRows = rankLiquidityRows(options.liquidityData?.items);
  const liquidityContent = state.liquidityLoading
    ? '<div class="glass-card rounded-xl p-4 text-center text-xs text-slate-500">Загружаем оборот рынка…</div>'
    : state.liquidityError
      ? `<div class="glass-card rounded-xl p-4 text-center text-xs text-rose-500">${escapeMarketText(state.liquidityError)}</div>`
      : liquidityRows.length
        ? `<div class="space-y-1.5">${liquidityRows.map((row, index) => {
          const marketItem = items.find((item) => item.id === row.item_id);
          const meta = getItemInfo(row.item_id);
          const itemName = row.name || marketItem?.name || meta.name || row.item_id;
          const unit = row.unit || marketItem?.unit || meta.unit || 'шт.';
          return `<div class="market-liquidity-row flex items-center gap-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white/80 dark:bg-slate-900/70 px-3 py-2">
            <span class="w-6 shrink-0 text-center text-[10px] font-black text-slate-400">${index + 1}</span>
            <span class="shrink-0 text-lg" aria-hidden="true">${escapeMarketText(meta.icon || '📦')}</span>
            <span class="min-w-0 flex-1"><span class="block truncate text-xs font-bold text-slate-900 dark:text-white">${escapeMarketText(itemName)}</span>
              <span class="block truncate text-[9px] text-slate-500">${formatPrice(row.quantity)} ${escapeMarketText(unit)} · ${Number(row.sale_count || 0).toLocaleString('ru-RU')} сделок</span></span>
            <span class="shrink-0 text-right"><span class="block text-xs font-black text-emerald-600 dark:text-emerald-400">${formatPrice(row.buyer_cash_paid)}</span><span class="text-[9px] text-slate-500">cash оборот</span></span>
          </div>`;
        }).join('')}</div>`
        : '<div class="glass-card rounded-xl p-4 text-center text-xs text-slate-500">За последние 24 часа оплаченных продаж пока нет.</div>';
  const liquidityUpdatedAt = options.liquidityData?.refreshed_at
    ? new Date(options.liquidityData.refreshed_at).toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
    : null;

  const rows = visibleItems.map((item) => {
    const meta = getItemInfo(item.id);
    const unit = item.unit || meta.unit || 'шт.';
    const priceLabel = state.category === 'industry'
      ? `Скупка NPC · ${formatPrice(item.buy)} cash/${escapeMarketText(unit)}`
      : state.category === 'needed'
        ? `Продажа NPC · ${formatPrice(item.sell)} cash/${escapeMarketText(unit)}`
        : `Сдать ${formatPrice(item.buy)} · купить ${formatPrice(item.sell)} cash/${escapeMarketText(unit)}`;
    const stock = Number(inventory?.[item.id] || 0);
    return `<button type="button" class="market-commodity-row flex w-full items-center gap-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white/80 dark:bg-slate-900/70 px-3 py-2 text-left" data-commodity-item="${escapeMarketText(item.id)}">
      <span class="shrink-0 text-lg" aria-hidden="true">${escapeMarketText(meta.icon || '📦')}</span>
      <span class="min-w-0 flex-1"><span class="block truncate text-xs font-bold text-slate-900 dark:text-white">${escapeMarketText(item.name)}</span><span class="block truncate text-[9px] text-slate-500">${priceLabel} · склад ${formatPrice(stock)} ${escapeMarketText(unit)}</span></span>
      <span class="shrink-0 text-base text-pink-500" aria-hidden="true">›</span>
    </button>`;
  }).join('');

  const emptyText = state.category === 'industry'
    ? 'В отраслевой ветке пока нет материалов для продажи.'
    : state.category === 'needed'
      ? 'У построенных предприятий сейчас нет входного сырья.'
      : 'По этому запросу ничего не найдено.';

  container.innerHTML = `<div class="market-contrast-surface space-y-3 max-w-md mx-auto p-4 pb-24">
    <button type="button" class="market-back text-xs font-bold text-pink-500">← Все разделы биржи</button>
    <div><h2 class="text-xl font-black">Сырьё и материалы</h2><p class="text-xs text-slate-500">Выберите материал, чтобы открыть стакан и сделки</p></div>
    <div class="commodity-category-tabs flex gap-1 overflow-x-auto no-scrollbar" role="tablist" aria-label="Категория материалов">
      ${tabs.map((tab) => `<button type="button" class="commodity-category-tab shrink-0 rounded-xl px-3 py-2 text-[10px] font-bold ${state.category === tab.id ? 'bg-pink-600 text-white' : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300'}" data-category="${tab.id}" role="tab" aria-selected="${state.category === tab.id}">${tab.label}</button>`).join('')}
    </div>
    ${state.category === 'liquidity' ? `<div class="space-y-2"><p class="text-[10px] text-slate-500">Оплаченный оборот товаров за скользящие 24 часа · снимок каждые 30 минут${liquidityUpdatedAt ? ` · обновлено ${escapeMarketText(liquidityUpdatedAt)}` : ''}</p>${liquidityContent}</div>` : ''}
    ${state.category === 'search' ? `<label class="block"><span class="sr-only">Поиск материала</span><input id="commodity-search" type="search" value="${escapeMarketText(state.query || '')}" placeholder="Название или код материала" class="w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-xs text-slate-900 dark:text-white" /></label>` : ''}
    ${state.category === 'liquidity' ? '' : `<div class="space-y-1.5">${rows || `<div class="glass-card rounded-xl p-4 text-center text-xs text-slate-500">${emptyText}</div>`}</div>`}
  </div>`;

  container.querySelector('.market-back')?.addEventListener('click', onBack);
  container.querySelectorAll('.commodity-category-tab').forEach((button) => {
    button.addEventListener('click', () => {
      state.category = button.dataset.category;
      state.query = '';
      renderCommodityCatalog(container, options);
      if (state.category === 'liquidity' && !state.liquidityLoaded && !state.liquidityLoading) {
        state.liquidityLoading = true;
        state.liquidityError = null;
        renderCommodityCatalog(container, options);
        Promise.resolve(options.loadLiquidity?.())
          .then((data) => {
            state.liquidityData = data || { items: [] };
            state.liquidityLoaded = true;
          })
          .catch((error) => {
            state.liquidityError = error?.message || 'Не удалось загрузить рейтинг ликвидности.';
          })
          .finally(() => {
            state.liquidityLoading = false;
            if (state.category === 'liquidity') renderCommodityCatalog(container, options);
          });
      }
    });
  });
  container.querySelector('#commodity-search')?.addEventListener('input', (event) => {
    const cursor = event.target.selectionStart;
    state.query = event.target.value;
    renderCommodityCatalog(container, options);
    const nextInput = container.querySelector('#commodity-search');
    nextInput?.focus();
    nextInput?.setSelectionRange(cursor, cursor);
  });
  container.querySelectorAll('[data-commodity-item]').forEach((button) => {
    button.addEventListener('click', () => onSelect(button.dataset.commodityItem));
  });
}
