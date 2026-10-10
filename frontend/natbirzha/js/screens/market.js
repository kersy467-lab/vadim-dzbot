import { NatAPI } from '../api.js?v=20261010_active_production_v1';
import { store } from '../state.js?v=20260926_local_update_v1';
import { disposeCurrentScreen, registerScreenCleanup } from '../screen_lifecycle.js?v=20260928_mobile_perf_v1';
import { getItemInfo, ITEMS } from '../items.js?v=20261009_item_art_v1';
import { renderMarketChart } from '../market_chart.js?v=20260926_local_update_v1';
import { getCompanyInputIds, renderCommodityCatalog } from './market_commodities.js?v=20261009_item_art_v2';
import { createMarketSectionLoader } from './market_section_loader.js?v=20261009_bond_income_v1';
import { renderCommodityOrderbookView } from './market_orderbook_view.js?v=20261006_energy_buyback_mastery_v1';

const SEED_MARKET_ITEMS = [
  { id: 'steel', name: 'Сталь', unit: 'т' },
  { id: 'iron_ore', name: 'Железная руда', unit: 'т' },
  { id: 'coal', name: 'Каменный уголь', unit: 'т' },
  { id: 'energy', name: 'Электроэнергия', unit: 'МВт·ч' },
  { id: 'oil_crude', name: 'Сырая нефть', unit: 'барр.' },
  { id: 'fuel_diesel', name: 'Дизельное топливо', unit: 'л' },
  { id: 'grain', name: 'Зерно', unit: 'т' },
  { id: 'fertilizer', name: 'Удобрения', unit: 'т' },
  { id: 'wood_raw', name: 'Лес-кругляк', unit: 'м³' },
  { id: 'aluminum', name: 'Алюминий', unit: 'т' },
];
const SEEDED_ITEM_IDS = new Set(SEED_MARKET_ITEMS.map((item) => item.id));
const MARKET_ITEMS = [
  ...SEED_MARKET_ITEMS,
  ...Object.entries(ITEMS)
    .filter(([itemId]) => !SEEDED_ITEM_IDS.has(itemId))
    .map(([id, item]) => ({ id, name: item.name, unit: item.unit })),
].map((item) => ({ ...item, base: null, buy: null, sell: null }));

// The local canonical item registry provides an immediate full catalog.
// Server NPC rates are merged only for the selected material's detail view.
export function mergeNpcRatesIntoMarketItems(rates, seedItems = MARKET_ITEMS) {
  const items = seedItems.map(item => ({ ...item }));
  for (const rate of Array.isArray(rates) ? rates : []) {
    if (!rate || !rate.item_id) continue;
    const item = items.find(candidate => candidate.id === rate.item_id);
    const values = {
      name: rate.name || getItemInfo(rate.item_id).name,
      unit: rate.unit || 'шт.',
      base: Number(rate.base_price),
      buy: Number(rate.npc_buy_price),
      sell: Number(rate.npc_sell_price),
      playerSellRemainingCash: rate.player_sell_remaining_cash == null
        ? null : Number(rate.player_sell_remaining_cash),
      playerSellRemainingQuantity: rate.player_sell_remaining_quota == null
        ? null : Number(rate.player_sell_remaining_quota),
    };
    if (item) {
      Object.assign(item, Object.fromEntries(
        Object.entries(values).filter(([, value]) => value === null || Number.isFinite(value) || typeof value === 'string')
      ));
    } else {
      items.push({ id: rate.item_id, ...values });
    }
  }
  return items;
}

// Production recipes are the source of truth for the company's own market
// products. This keeps the market selector in sync when a new factory is added
// without maintaining another hard-coded industry -> item table in the UI.
export function getIndustryOutputIds(specialization, recipes, businessCatalog = []) {
  if (!specialization) return [];
  const outputs = new Set();
  if (recipes && typeof recipes === 'object') {
    for (const recipe of Object.values(recipes)) {
      if (!recipe || recipe.specialization !== specialization) continue;
      for (const itemId of Object.keys(recipe.outputs || {})) outputs.add(itemId);
    }
  }
  for (const business of Array.isArray(businessCatalog) ? businessCatalog : []) {
    if (!business || business.specialization !== specialization) continue;
    for (const itemId of Object.keys(business.outputs_per_hour || {})) outputs.add(itemId);
  }
  return [...outputs];
}

export function ensureIndustryProductsAvailable(items, outputIds, itemInfo = getItemInfo) {
  const result = Array.isArray(items) ? items.map((item) => ({ ...item })) : [];
  const existingIds = new Set(result.map((item) => String(item?.id || '')));
  for (const rawId of Array.isArray(outputIds) ? outputIds : []) {
    const itemId = String(rawId || '').trim();
    if (!itemId || existingIds.has(itemId)) continue;
    const metadata = itemInfo(itemId);
    result.push({ id: itemId, name: metadata.name, unit: metadata.unit });
    existingIds.add(itemId);
  }
  return result;
}

export function prioritizeIndustryItems(items, preferredIds) {
  const preferred = new Set(Array.isArray(preferredIds) ? preferredIds : []);
  return (Array.isArray(items) ? items : [])
    .map((item, index) => ({ ...item, isIndustry: preferred.has(item.id), _marketOrder: index }))
    .sort((left, right) => Number(right.isIndustry) - Number(left.isIndustry) || left._marketOrder - right._marketOrder)
    .map(({ _marketOrder, ...item }) => item);
}

export async function renderMarket(container, showToast) {
  let selectedItemId = 'steel';
  let marketItems = MARKET_ITEMS.map(item => ({ ...item }));
  let recipesData = { recipes: {} };
  let orderbookData = null;
  let orderbookRequestId = 0;
  let marketDataPromise = null;
  let marketDataLoaded = false;
  let companyInputPromise = null;
  let companyInputIds = [];
  const commodityCatalogState = { category: 'search', query: '', liquidityLoaded: false };
  let liquidityRefreshTimer = null;
  let liquidityRefreshAt = 0;
  let liquidityVisibilityHandler = null;
  let liquidityCleanupRegistered = false;

  function clearLiquidityRefresh() {
    if (liquidityRefreshTimer) clearTimeout(liquidityRefreshTimer);
    liquidityRefreshTimer = null;
    liquidityRefreshAt = 0;
    if (liquidityVisibilityHandler) {
      document.removeEventListener('visibilitychange', liquidityVisibilityHandler);
      liquidityVisibilityHandler = null;
    }
  }

  function ensureLiquidityCleanup() {
    if (liquidityCleanupRegistered) return;
    registerScreenCleanup(() => {
      clearLiquidityRefresh();
      liquidityCleanupRegistered = false;
    });
    liquidityCleanupRegistered = true;
  }

  function scheduleLiquidityRefresh() {
    if (commodityCatalogState.category !== 'liquidity'
      || !container.querySelector('.commodity-category-tabs')) {
      clearLiquidityRefresh();
      return;
    }
    if (liquidityRefreshTimer) return;

    ensureLiquidityCleanup();
    const halfHourMs = 30 * 60 * 1000;
    liquidityRefreshAt = (Math.floor(Date.now() / halfHourMs) + 1) * halfHourMs + 3000;
    const refresh = () => {
      if (document.hidden || Date.now() < liquidityRefreshAt) return;
      clearLiquidityRefresh();
      if (commodityCatalogState.category !== 'liquidity') return;
      void commodityCatalogState.reloadLiquidity?.();
      scheduleLiquidityRefresh();
    };
    liquidityVisibilityHandler = refresh;
    document.addEventListener('visibilitychange', liquidityVisibilityHandler);
    liquidityRefreshTimer = setTimeout(refresh, Math.max(0, liquidityRefreshAt - Date.now()));
  }

  async function ensureMarketData() {
    if (marketDataLoaded) return;
    if (!marketDataPromise) {
      marketDataPromise = Promise.all([
        NatAPI.getRecipes().catch(() => null),
        NatAPI.getBusinessCatalog(store.company?.specialization).catch(() => ({ items: [] })),
      ]).then(([loadedRecipes, businessCatalog]) => {
        recipesData = loadedRecipes || recipesData;
        const industryOutputs = getIndustryOutputIds(
          store.company?.specialization, recipesData.recipes, businessCatalog?.items || []
        );
        companyInputIds = getCompanyInputIds([], store.factories, recipesData.recipes);
        marketItems = prioritizeIndustryItems(ensureIndustryProductsAvailable(marketItems, industryOutputs), industryOutputs);
        marketDataLoaded = true;
        return companyInputIds;
      });
    }
    return marketDataPromise;
  }

  async function ensureCompanyInputs() {
    if (!companyInputPromise) {
      companyInputPromise = Promise.all([
        ensureMarketData(),
        NatAPI.getBusinessInputItems().catch(() => ({ items: [] })),
      ]).then(([, data]) => {
        const inputIds = new Set(getCompanyInputIds([], store.factories, recipesData.recipes));
        for (const itemId of data?.items || []) inputIds.add(itemId);
        companyInputIds = [...inputIds];
        return companyInputIds;
      });
    }
    return companyInputPromise;
  }

  async function loadOrderbook(itemId = selectedItemId, requestId = ++orderbookRequestId) {
    orderbookData = null;
    try {
      const data = await NatAPI.getOrderbook(itemId);
      if (requestId !== orderbookRequestId || itemId !== selectedItemId) return false;
      orderbookData = data;
      return true;
    } catch (err) {
      if (requestId !== orderbookRequestId || itemId !== selectedItemId) return false;
      console.error('Failed to load orderbook:', err);
      return false;
    }
  }



  async function refreshNpcRates(itemId = selectedItemId, requestId = orderbookRequestId) {
    const data = await NatAPI.getNpcRates(itemId).catch(() => null);
    if (requestId !== orderbookRequestId || itemId !== selectedItemId) return null;
    if (data && Array.isArray(data.rates)) {
      marketItems = mergeNpcRatesIntoMarketItems(data.rates, marketItems);
    }
    return data;
  }
  function renderCommodityBrowser() {
    orderbookRequestId += 1;
    renderCommodityCatalog(container, {
      items: marketItems,
      inventory: store.inventory,
      inputIds: companyInputIds,
      state: commodityCatalogState,
      loadLiquidity: () => NatAPI.getMarketLiquidity(),
      onCategoryChange: (category) => {
        if (category === 'liquidity') scheduleLiquidityRefresh();
        else clearLiquidityRefresh();
      },
      loadCompanyInputs: ensureCompanyInputs,
      onBack: renderMarketHome,
      onSelect: async (itemId) => {
        if (!marketItems.some((item) => item.id === itemId)) return;
        sectionLoader.invalidate();
        selectedItemId = itemId;
        const requestId = ++orderbookRequestId;
        orderbookData = null;
        container.innerHTML = `<div class="market-contrast-surface max-w-md mx-auto p-8 text-center text-sm text-slate-400"><button type="button" class="market-back mb-4 text-xs font-bold text-pink-500">← Список сырья</button><div>Загружаем котировку и стакан…</div></div>`;
        container.querySelector('.market-back')?.addEventListener('click', renderCommodityBrowser);
        await Promise.all([
          loadOrderbook(itemId, requestId),
          refreshNpcRates(itemId, requestId),
        ]);
        if (requestId !== orderbookRequestId || !container.isConnected) return;
        renderView();
      },
    });
  }

  function renderMarketHome() {
    clearLiquidityRefresh();
    commodityCatalogState.liquidityRequestId = Number(commodityCatalogState.liquidityRequestId || 0) + 1;
    commodityCatalogState.liquidityLoaded = false;
    commodityCatalogState.liquidityLoading = false;
    commodityCatalogState.liquidityData = null;
    commodityCatalogState.liquidityError = null;
    sectionLoader.invalidate();
    orderbookRequestId += 1;
    container.innerHTML = `<div class="market-contrast-surface space-y-4 max-w-md mx-auto p-4 pb-24"><div><h2 class="text-xl font-black">Биржа</h2><p class="text-xs text-slate-500">Выберите раздел рынка</p></div><div class="grid gap-3"><button class="market-section-btn glass-card rounded-2xl p-5 text-left border-2 border-blue-200 dark:border-blue-900" data-section="portfolio"><div>${window.NatIcons.icon('money', 24)}</div><div class="font-black mt-2">Мой портфель</div><div class="text-xs text-slate-500">Акции, облигации, валюты, металлы и выплаты</div></button><button class="market-section-btn glass-card rounded-2xl p-5 text-left" data-section="stocks"><div>${window.NatIcons.icon('stock', 24)}</div><div class="font-black mt-2">Акции компаний</div><div class="text-xs text-slate-500">Игроки, вышедшие на IPO</div></button><button class="market-section-btn glass-card rounded-2xl p-5 text-left" data-section="bankruptcy_market"><div>${window.NatIcons.icon('factory', 24)}</div><div class="font-black mt-2">Рынок банкротов</div><div class="text-xs text-slate-500">Заводы конфискованных компаний, наценка государства 30%</div></button><button class="market-section-btn glass-card rounded-2xl p-5 text-left" data-section="bonds"><div>${window.NatIcons.icon('document', 24)}</div><div class="font-black mt-2">Государственные облигации</div><div class="text-xs text-slate-500">Купоны, погашение и вторичный рынок</div></button><button class="market-section-btn glass-card rounded-2xl p-5 text-left" data-section="reference"><div>${window.NatIcons.icon('coin', 24)}</div><div class="font-black mt-2">Валюты и металлы</div><div class="text-xs text-slate-500">Курсы официальных инструментов</div></button><button class="market-section-btn glass-card rounded-2xl p-5 text-left" data-section="commodities"><div>${window.NatIcons.icon('resource', 24)}</div><div class="font-black mt-2">Сырьё и материалы</div><div class="text-xs text-slate-500">Стакан, NPC и торговые ордера</div></button><button class="market-section-btn glass-card rounded-2xl p-5 text-left" data-section="tax"><div>${window.NatIcons.icon('document', 24)}</div><div class="font-black mt-2">Налог</div><div class="text-xs text-slate-500">13% от чистой прибыли раз в сутки в 11:00 MSK+2</div></button><button class="market-section-btn glass-card rounded-2xl p-5 text-left" data-section="state_credit"><div>${window.NatIcons.icon('money', 24)}</div><div class="font-black mt-2">Кредит государства</div><div class="text-xs text-slate-500">Ставка повышена до 20% в день · выдача после одобрения</div></button><button class="market-section-btn glass-card rounded-2xl p-5 text-left border border-cyan-300/60" data-section="city_orders"><div>${window.NatIcons.icon('building', 24)}</div><div class="font-black mt-2">Заказы города</div><div class="text-xs text-slate-500">Сдавайте ресурсы в госзаказы и получайте оплату</div></button><button class="market-section-btn glass-card rounded-2xl p-5 text-left border border-indigo-300/60" data-section="deals"><div>${window.NatIcons.icon('handshake', 24)}</div><div class="font-black mt-2">Сделки</div><div class="text-xs text-slate-500">Договорные поставки между компаниями</div></button></div></div>`;
    container.querySelectorAll('.market-section-btn').forEach((button) => button.addEventListener('click', () => {
      void sectionLoader.open(button.dataset.section);
    }));
  }

  function returnToMarketHome() {
    disposeCurrentScreen();
    renderMarketHome();
  }

  const sectionLoader = createMarketSectionLoader(
    container, showToast, returnToMarketHome, ensureMarketData, renderCommodityBrowser
  );

  function renderView() {
    if (!container.isConnected) return;
    renderCommodityOrderbookView({
      container, selectedItemId, marketItems, orderbookData, store, showToast,
      NatAPI, renderMarketChart, loadOrderbook, refreshNpcRates, renderCommodityBrowser,
      rerender: renderView,
    });
  }
  renderMarketHome();
}
