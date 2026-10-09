export function createMarketSectionLoader(container, showToast, onBack, loadCommodities, renderCommodities) {
  let requestId = 0;
  let financePromise = null;
  let finance = null;

  const showLoading = () => {
    container.innerHTML = '<div class="max-w-md mx-auto p-8 text-center text-sm text-slate-400">Загружаем раздел…</div>';
  };
  const showError = (error) => {
    container.innerHTML = '<div class="max-w-md mx-auto p-4 text-sm text-rose-500" data-market-load-error></div>';
    container.querySelector('[data-market-load-error]').textContent = error?.message || 'Не удалось загрузить раздел.';
  };

  async function getFinance() {
    if (!financePromise) {
      financePromise = import('./market_finance.js?v=20261009_bond_income_v1')
        .then(({ createMarketFinance }) => (finance = createMarketFinance(container, showToast, onBack)));
      financePromise = financePromise.catch((error) => {
        financePromise = null;
        throw error;
      });
    }
    return financePromise;
  }

  async function openFinance(section, currentRequest) {
    showLoading();
    try {
      const currentFinance = await getFinance();
      await currentFinance.load(section);
      if (currentRequest !== requestId || !container.isConnected) return;
      currentFinance[{ portfolio: 'renderPortfolio', stocks: 'renderStocks', bonds: 'renderBonds', reference: 'renderReference' }[section]]();
    } catch (error) {
      if (currentRequest === requestId && container.isConnected) showError(error);
    }
  }

  async function openLazy(section, currentRequest) {
    const modules = {
      bankruptcy_market: ['./bankruptcy_market.js?v=20260928_mobile_perf_v1', 'renderBankruptcyMarket'],
      tax: ['./market_tax.js?v=20260929_stock_tax_safety_v1', 'renderTaxSection'],
      state_credit: ['./market_credit.js?v=20260928_mobile_perf_v1', 'renderStateCreditSection'],
      city_orders: ['./market_city_orders.js?v=20260928_mobile_perf_v1', 'renderMarketCityOrders'],
      deals: ['./market_deals.js?v=20260928_mobile_perf_v1', 'renderMarketDeals'],
    };
    const [path, exportName] = modules[section] || [];
    if (!path) return;
    showLoading();
    try {
      const module = await import(path);
      if (currentRequest !== requestId || !container.isConnected) return;
      await module[exportName](container, showToast, onBack);
    } catch (error) {
      if (currentRequest === requestId && container.isConnected) showError(error);
    }
  }

  async function open(section) {
    const currentRequest = ++requestId;
    if (['portfolio', 'stocks', 'bonds', 'reference'].includes(section)) return openFinance(section, currentRequest);
    if (section === 'commodities') {
      renderCommodities();
      try {
        await loadCommodities();
        if (currentRequest === requestId && container.isConnected) renderCommodities();
      } catch (error) {
        if (currentRequest === requestId && container.isConnected) showError(error);
      }
      return;
    }
    return openLazy(section, currentRequest);
  }

  return { open, invalidate: () => { requestId += 1; } };
}
