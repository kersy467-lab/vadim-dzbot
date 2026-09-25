import { getItemInfo } from '../items.js?v=20260925_deals_v9';

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

export function renderCommodityCatalog(container, options) {
  const { items, inventory, inputIds, state, onBack, onSelect } = options;
  const tabs = [
    { id: 'search', label: 'Поиск' },
    { id: 'industry', label: 'Моя продукция' },
    { id: 'needed', label: 'Нужно заводам' },
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
    ${state.category === 'search' ? `<label class="block"><span class="sr-only">Поиск материала</span><input id="commodity-search" type="search" value="${escapeMarketText(state.query || '')}" placeholder="Название или код материала" class="w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 text-xs text-slate-900 dark:text-white" /></label>` : ''}
    <div class="space-y-1.5">${rows || `<div class="glass-card rounded-xl p-4 text-center text-xs text-slate-500">${emptyText}</div>`}</div>
  </div>`;

  container.querySelector('.market-back')?.addEventListener('click', onBack);
  container.querySelectorAll('.commodity-category-tab').forEach((button) => {
    button.addEventListener('click', () => {
      state.category = button.dataset.category;
      state.query = '';
      renderCommodityCatalog(container, options);
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
