import { NatAPI } from '../api.js?v=20261010_shell_v2';
import { renderCommodityCatalog } from './market_commodities.js?v=20261009_item_art_v2';
import { esc, renderNextMarketItem } from './next_game_market_item.js?v=20261010_market_v2';

const requests = new WeakMap();

export async function loadSelectedMarketItem(container, itemId, load, render, onError) {
  const token = {};
  const mounted = container.isConnected;
  requests.set(container, token);
  container.innerHTML = '<div data-next-market-loading class="p-4 text-xs text-slate-500">Загружаем стакан…</div>';
  const marker = container.querySelector('[data-next-market-loading]');
  try {
    const data = await load(itemId);
    if (requests.get(container) !== token || container.querySelector('[data-next-market-loading]') !== marker || (mounted && !marker?.isConnected)) return;
    render(data);
  } catch (error) {
    if (requests.get(container) !== token || container.querySelector('[data-next-market-loading]') !== marker || (mounted && !marker?.isConnected)) return;
    onError(error);
  }
}

export async function renderNextGameMarket(container, state, showToast, refresh) {
  const market = state.marketBrowser ||= { view: 'home', category: 'search', query: '' };
  const api = state.nextGameAPI || NatAPI;
  const rerender = () => renderNextGameMarket(container, state, showToast, refresh);
  const home = () => { requests.delete(container); market.view = 'home'; void rerender(); };
  const catalog = async () => {
    requests.delete(container);
    market.view = 'catalog';
    {
      container.innerHTML = '<div data-next-catalog-loading class="p-4 text-xs text-slate-500">Загружаем материалы…</div>';
      const marker = container.querySelector('[data-next-catalog-loading]');
      const mounted = container.isConnected;
      try {
        market.catalog = await api.getNextGameMarketCatalog();
        if (market.view !== 'catalog' || container.querySelector('[data-next-catalog-loading]') !== marker || (mounted && !marker?.isConnected)) return;
      } catch (error) {
        if (container.querySelector('[data-next-catalog-loading]') === marker && (!mounted || marker?.isConnected)) showError(error, catalog);
        return;
      }
    }
    const data = market.catalog;
    renderCommodityCatalog(container, {
      items: data.items, inventory: data.inventory, inputIds: data.input_ids,
      state: market, onBack: home, onSelect: selectItem,
      liquidityDescription: 'Оплаченный оборот товаров за скользящие 24 часа · реальные сделки между компаниями',
      loadLiquidity: async () => {
        const result = await api.getNextGameMarketLiquidity();
        return result;
      },
      get liquidityData() { return market.liquidityData; },
      loadCompanyInputs: () => Promise.resolve(data.input_ids),
    });
    market.companyInputsLoaded = true;
  };
  function showError(error, retry) {
    container.innerHTML = `<div class="next-market p-4 space-y-3"><button type="button" data-market-home>← Биржа</button><p role="alert">${esc(error.message || 'Рынок недоступен')}</p><button type="button" data-market-retry>Повторить</button></div>`;
    container.querySelector('[data-market-home]')?.addEventListener('click', home);
    container.querySelector('[data-market-retry]')?.addEventListener('click', retry);
  }
  async function selectItem(itemId) {
    market.view = 'item';
    market.itemId = itemId;
    await loadSelectedMarketItem(container, itemId, (id) => api.getNextGameMarketItem(id),
      (data) => renderNextMarketItem(container, data, {
        api, onBack: catalog, reload: () => selectItem(itemId), showToast,
        refresh: async () => { market.catalog = null; await refresh?.(); },
      }), (error) => showError(error, () => selectItem(itemId)));
  }
  if (market.view === 'catalog') return catalog();
  if (market.view === 'item' && market.itemId) return selectItem(market.itemId);
  requests.delete(container);
  const sections = [
    ['catalog', 'Сырьё и материалы', 'Стакан, NPC и торговые ордера', 'mining'],
    ['capital', 'Акции и капитал', 'IPO, акции компаний и дивиденды', 'chart'],
    ['bank', 'Банк', 'Кредиты, вклады и платежи', 'money'],
    ['bonds', 'Облигации', 'Купоны резервного банка и вторичный рынок', 'money'],
    ['contracts', 'Контракты', 'Договоры поставки и займы', 'document'],
    ['projects', 'Проекты', 'Совместные заводы', 'construction'],
  ];
  container.innerHTML = `<div class="next-market market-contrast-surface space-y-4 max-w-md mx-auto p-4 pb-24">
    <div><h2 class="text-xl font-black">Биржа</h2><p class="text-xs text-slate-500">Товары, капитал и финансовые инструменты</p></div>
    <div class="next-market-sections">${sections.map(([id, name, description, icon]) => `<button type="button" data-market-section="${id}" class="next-market-tile glass-card rounded-2xl p-4 text-left">
      <span class="next-market-tile-icon">${window.NatIcons?.icon?.(icon, 30) || ''}</span><span><b>${name}</b><small>${description}</small></span><span class="text-pink-500">›</span></button>`).join('')}</div>
  </div>`;
  container.querySelectorAll('[data-market-section]').forEach((button) => {
    button.addEventListener('click', () => {
      const section = button.dataset.marketSection;
      if (section === 'catalog') void catalog();
      else state.navigateNextGame?.(section);
    });
  });
}
