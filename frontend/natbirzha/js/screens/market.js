import { NatAPI } from '../api.js?v=20260920_liquidity1';
import { store } from '../state.js';
import { getSpecializationName } from '../localization.js';
import { renderMarketChart, trendOf } from '../market_chart.js';

const MARKET_ITEMS = [
  { id: 'steel', name: 'Сталь', unit: 'т', base: 90.0, buy: 72.0, sell: 112.5 },
  { id: 'iron_ore', name: 'Железная руда', unit: 'т', base: 35.0, buy: 28.0, sell: 43.75 },
  { id: 'coal', name: 'Каменный уголь', unit: 'т', base: 30.0, buy: 24.0, sell: 37.5 },
  { id: 'energy', name: 'Электроэнергия', unit: 'МВт·ч', base: 10.0, buy: 8.0, sell: 12.5 },
  { id: 'oil_crude', name: 'Сырая нефть', unit: 'барр.', base: 50.0, buy: 40.0, sell: 62.5 },
  { id: 'fuel_diesel', name: 'Дизельное топливо', unit: 'л', base: 1.2, buy: 0.96, sell: 1.5 },
  { id: 'grain', name: 'Зерно', unit: 'т', base: 20.0, buy: 16.0, sell: 25.0 },
  { id: 'fertilizer', name: 'Удобрения', unit: 'т', base: 50.0, buy: 40.0, sell: 62.5 },
  { id: 'wood_raw', name: 'Лес-кругляк', unit: 'м³', base: 25.0, buy: 20.0, sell: 31.25 },
  { id: 'aluminum', name: 'Алюминий', unit: 'т', base: 110.0, buy: 88.0, sell: 137.5 },
];

// The server's NPC-rate registry is the source of truth.  Keep the small
// seed list for a fast first render, then merge every server item into it so
// production outputs (for example natural gas and copper) are never hidden
// just because the frontend seed list was not updated.
export function mergeNpcRatesIntoMarketItems(rates, seedItems = MARKET_ITEMS) {
  const items = seedItems.map(item => ({ ...item }));
  for (const rate of Array.isArray(rates) ? rates : []) {
    if (!rate || !rate.item_id) continue;
    const item = items.find(candidate => candidate.id === rate.item_id);
    const values = {
      name: rate.name || rate.item_id,
      unit: rate.unit || 'шт.',
      base: Number(rate.base_price),
      buy: Number(rate.npc_buy_price),
      sell: Number(rate.npc_sell_price),
    };
    if (item) {
      Object.assign(item, Object.fromEntries(
        Object.entries(values).filter(([, value]) => Number.isFinite(value) || typeof value === 'string')
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
export function getIndustryOutputIds(specialization, recipes) {
  if (!specialization || !recipes || typeof recipes !== 'object') return [];
  const outputs = new Set();
  for (const recipe of Object.values(recipes)) {
    if (!recipe || recipe.specialization !== specialization) continue;
    for (const itemId of Object.keys(recipe.outputs || {})) outputs.add(itemId);
  }
  return [...outputs];
}

export function prioritizeIndustryItems(items, preferredIds) {
  const preferred = new Set(Array.isArray(preferredIds) ? preferredIds : []);
  return (Array.isArray(items) ? items : [])
    .map((item, index) => ({ ...item, isIndustry: preferred.has(item.id), _marketOrder: index }))
    .sort((left, right) => Number(right.isIndustry) - Number(left.isIndustry) || left._marketOrder - right._marketOrder)
    .map(({ _marketOrder, ...item }) => item);
}

const INSTRUMENT_NAMES = { USD: 'Доллар США', EUR: 'Евро', GOLD: 'Золото', SILVER: 'Серебро' };
const INSTRUMENT_ICONS = { USD: '💵', EUR: '💶', GOLD: '🥇', SILVER: '🥈' };
const esc = (value) => String(value ?? '').replace(/[&<>'"]/g, ch => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
}[ch]));

export async function renderMarket(container, showToast) {
  let selectedItemId = 'steel';
  let marketItems = MARKET_ITEMS.map(item => ({ ...item }));
  let recipesData = { recipes: {} };
  let orderbookData = null;
  let orderbookRequestId = 0;
  let instrumentsData = { instruments: [], portfolio: [] };
  let bondsData = { bonds: [], holdings: [], listings: [] };
  let stocksData = { stocks: [] };

  const formatMoney = (value) => `${Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} cash`;
  const pnlClass = (value) => Number(value || 0) >= 0 ? 'text-emerald-600' : 'text-rose-600';
  const formatPnl = (value, suffix = 'cash') => `<span class="${pnlClass(value)} font-mono font-bold">${Number(value || 0) >= 0 ? '+' : ''}${Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ${suffix}</span>`;

  async function loadOrderbook() {
    const requestId = ++orderbookRequestId;
    try {
      const data = await NatAPI.getOrderbook(selectedItemId);
      if (requestId !== orderbookRequestId) return false;
      orderbookData = data;
      return true;
    } catch (err) {
      if (requestId !== orderbookRequestId) return false;
      console.error('Failed to load orderbook:', err);
      return false;
    }
  }

  async function loadFinancialMarkets() {
    const [instruments, bonds] = await Promise.allSettled([
      NatAPI.getReferenceInstruments(),
      NatAPI.getStateBonds(),
    ]);
    if (instruments.status === 'fulfilled') instrumentsData = instruments.value || instrumentsData;
    if (bonds.status === 'fulfilled') bondsData = bonds.value || bondsData;
    try { stocksData = await NatAPI.getStocksList(); } catch (_) { stocksData = { stocks: [] }; }
  }

  const [ratesData, loadedRecipes] = await Promise.all([
    NatAPI.getNpcRates().catch(() => null),
    NatAPI.getRecipes().catch(() => null),
    loadFinancialMarkets(),
  ]);

  recipesData = loadedRecipes || recipesData;

  if (ratesData && Array.isArray(ratesData.rates)) {
    marketItems = mergeNpcRatesIntoMarketItems(ratesData.rates, marketItems);
  }

  async function refreshNpcRates() {
    const data = await NatAPI.getNpcRates().catch(() => null);
    if (data && Array.isArray(data.rates)) {
      marketItems = mergeNpcRatesIntoMarketItems(data.rates, marketItems);
    }
    return data;
  }
  const industryOutputs = getIndustryOutputIds(store.company?.specialization, recipesData.recipes);
  marketItems = prioritizeIndustryItems(marketItems, industryOutputs);
  const firstIndustryItem = marketItems.find(item => item.isIndustry);
  if (firstIndustryItem && !marketItems.some(item => item.id === selectedItemId && item.isIndustry)) {
    selectedItemId = firstIndustryItem.id;
  }
  await loadOrderbook();

  function marketShell(title, subtitle, body) {
    return `<div class="market-contrast-surface space-y-4 max-w-md mx-auto p-4 pb-24"><button type="button" class="market-back text-xs font-bold text-blue-600">← Все разделы рынка</button><div><h2 class="text-xl font-black">${title}</h2><p class="text-xs text-slate-500">${subtitle}</p></div>${body}</div>`;
  }

  function renderMarketHome() {
    container.innerHTML = `<div class="market-contrast-surface space-y-4 max-w-md mx-auto p-4 pb-24"><div><h2 class="text-xl font-black">Биржа</h2><p class="text-xs text-slate-500">Выберите раздел рынка</p></div><div class="grid gap-3"><button class="market-section-btn glass-card rounded-2xl p-5 text-left border-2 border-blue-200 dark:border-blue-900" data-section="portfolio"><div class="text-2xl">💼</div><div class="font-black mt-2">Мой портфель</div><div class="text-xs text-slate-500">Акции, облигации, валюты, металлы и выплаты</div></button><button class="market-section-btn glass-card rounded-2xl p-5 text-left" data-section="stocks"><div class="text-2xl">📈</div><div class="font-black mt-2">Акции компаний</div><div class="text-xs text-slate-500">Игроки, вышедшие на IPO</div></button><button class="market-section-btn glass-card rounded-2xl p-5 text-left" data-section="bonds"><div class="text-2xl">🏛️</div><div class="font-black mt-2">Государственные облигации</div><div class="text-xs text-slate-500">Купоны, погашение и вторичный рынок</div></button><button class="market-section-btn glass-card rounded-2xl p-5 text-left" data-section="reference"><div class="text-2xl">💱</div><div class="font-black mt-2">Валюты и металлы</div><div class="text-xs text-slate-500">Курсы официальных инструментов</div></button><button class="market-section-btn glass-card rounded-2xl p-5 text-left" data-section="commodities"><div class="text-2xl">🪙</div><div class="font-black mt-2">Сырьё и материалы</div><div class="text-xs text-slate-500">Стакан, NPC и торговые ордера</div></button></div></div>`;
    container.querySelectorAll('.market-section-btn').forEach((button) => button.addEventListener('click', () => {
      const section = button.dataset.section;
      if (section === 'portfolio') renderPortfolio();
      else if (section === 'stocks') renderStocksMarket();
      else if (section === 'bonds') renderBondsMarket();
      else if (section === 'reference') renderReferenceMarket();
      else renderView();
    }));
  }

  async function renderPortfolio() {
    container.innerHTML = '<div class="p-6 text-center text-xs text-slate-400">Загрузка портфеля…</div>';
    let portfolio;
    try {
      portfolio = await NatAPI.getPortfolio();
    } catch (error) {
      container.innerHTML = marketShell('Мой портфель', 'Не удалось загрузить позиции', `<div class="glass-card rounded-2xl p-6 text-center text-sm text-rose-500">${esc(error.message || 'Ошибка сервера')}</div>`);
      container.querySelector('.market-back')?.addEventListener('click', renderMarketHome);
      return;
    }
    const summary = portfolio.summary || {};
    const stocks = portfolio.stocks || [];
    const bonds = portfolio.bonds || [];
    const instruments = portfolio.instruments || [];
    const payments = portfolio.dividend_payments || [];
    const stockBody = stocks.length ? stocks.map(row => `<div class="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 space-y-1"><div class="flex justify-between gap-2"><b>${esc(row.issuer_company)}</b><span>${row.shares_count} акций</span></div><div class="flex justify-between text-xs"><span>${formatMoney(row.market_value)}</span>${formatPnl(row.unrealized_pnl)}</div><div class="text-[10px] text-slate-500">Дивиденды: ${formatMoney(row.dividends_earned)} · ${row.next_dividend_at ? `следующая выплата ${new Date(row.next_dividend_at).toLocaleString('ru-RU')}` : 'выплаты недоступны'}</div></div>`).join('') : '<div class="text-xs text-slate-400">Акций пока нет</div>';
    const bondBody = bonds.length ? bonds.map(row => `<div class="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 space-y-1"><div class="flex justify-between gap-2"><b>${esc(row.title)}</b><span>${row.quantity} шт.</span></div><div class="flex justify-between text-xs"><span>${formatMoney(row.market_value)}</span>${formatPnl(row.unrealized_pnl)}</div><div class="text-[10px] text-slate-500">Купоны: ${formatMoney(row.coupons_earned)} · следующая выплата ${row.next_coupon_at ? new Date(row.next_coupon_at).toLocaleString('ru-RU') : 'не назначена'}</div></div>`).join('') : '<div class="text-xs text-slate-400">Облигаций пока нет</div>';
    const instrumentBody = instruments.length ? instruments.map(row => `<div class="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 space-y-1"><div class="flex justify-between gap-2"><b>${esc(row.instrument_code)}</b><span>${Number(row.quantity).toLocaleString('ru-RU')}</span></div><div class="flex justify-between text-xs"><span>${row.market_value_rub == null ? 'Курс недоступен' : `${Number(row.market_value_rub).toLocaleString('ru-RU')} ₽`}</span>${row.unrealized_pnl_rub == null ? '' : formatPnl(row.unrealized_pnl_rub, '₽')}</div><div class="text-[10px] text-slate-500">Средняя цена: ${Number(row.avg_cost_rub).toLocaleString('ru-RU')} ₽</div></div>`).join('') : '<div class="text-xs text-slate-400">Валют и металлов пока нет</div>';
    const paymentsBody = payments.length ? payments.slice(0, 20).map(row => `<div class="flex justify-between gap-2 p-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/20 text-xs"><span>${esc(row.issuer_company)} · ${row.settlement_date}</span><b class="text-emerald-600">+${formatMoney(row.payout_cash)}</b></div>`).join('') : '<div class="text-xs text-slate-400">Дивидендных выплат пока не было</div>';
    const body = `<div class="space-y-3"><div class="glass-card rounded-2xl p-4 grid grid-cols-2 gap-2 text-xs"><div><span class="text-slate-500">Баланс</span><b class="block text-base">${formatMoney(portfolio.cash)}</b></div><div><span class="text-slate-500">Стоимость активов</span><b class="block text-base">${formatMoney(summary.market_value)}</b></div><div><span class="text-slate-500">Нереализованный результат</span><b class="block">${formatPnl(summary.unrealized_pnl)}</b></div><div><span class="text-slate-500">Получено выплат</span><b class="block text-emerald-600">${formatMoney(Number(summary.dividends_earned || 0) + Number(summary.coupons_earned || 0))}</b></div></div><details class="glass-card rounded-2xl p-4" open><summary class="font-black cursor-pointer">📈 Акции</summary><div class="space-y-2 pt-3">${stockBody}</div></details><details class="glass-card rounded-2xl p-4"><summary class="font-black cursor-pointer">🏛️ Облигации</summary><div class="space-y-2 pt-3">${bondBody}</div></details><details class="glass-card rounded-2xl p-4"><summary class="font-black cursor-pointer">💱 Валюты и металлы</summary><div class="space-y-2 pt-3">${instrumentBody}</div></details><details class="glass-card rounded-2xl p-4"><summary class="font-black cursor-pointer">💸 История дивидендов</summary><div class="space-y-2 pt-3">${paymentsBody}</div></details></div>`;
    container.innerHTML = marketShell('Мой портфель', 'Позиции и выплаты по всем рыночным инструментам', body);
    container.querySelector('.market-back')?.addEventListener('click', renderMarketHome);
  }

  function renderStocksMarket() {
    const stocks = stocksData.stocks || [];
    const company = store.company || {};
    const companyLevel = Number(company.level || 1);
    const ipoLevel = 2;
    const ownCompanyId = Number(company.id || company.company_id || 0);
    const ownStock = stocks.find(stock => Number(stock.company_id) === ownCompanyId);
    const ipoCard = ownStock
      ? `<div class="glass-card rounded-2xl p-4 border-l-4 border-l-emerald-500"><div class="flex justify-between gap-3"><div><div class="font-bold">Компания уже на IPO</div><div class="text-xs text-slate-500 mt-1">Дивидендная политика зафиксирована для инвесторов.</div></div><span class="text-xs font-bold text-emerald-600">${Number(ownStock.dividend_rate_pct || 5).toFixed(1)}% прибыли</span></div></div>`
      : `<div class="glass-card rounded-2xl p-4 border-l-4 border-l-blue-500 space-y-3"><div class="flex justify-between gap-3"><div><div class="font-bold">🚀 Выход на IPO</div><div class="text-xs text-slate-500 mt-1">Доступно с 2 уровня компании. Сейчас: ${companyLevel} ур.</div></div><span class="text-[10px] font-bold ${companyLevel >= ipoLevel ? 'text-emerald-600' : 'text-amber-600'}">${companyLevel >= ipoLevel ? 'ДОСТУПНО' : `НУЖЕН ${ipoLevel} УР.`}</span></div><label class="block text-xs font-semibold">Обязательные дивиденды, % чистой прибыли<input id="market-ipo-dividend-rate" type="number" min="5" max="50" step="0.5" value="5" class="mt-1 w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-2 text-sm"></label><p class="text-[11px] text-slate-500">Минимум 5%. Это дневная доля чистой прибыли, которая будет выплачиваться держателям акций.</p><button id="market-ipo-open-btn" class="w-full py-2 rounded-xl bg-blue-600 text-white font-bold disabled:opacity-50" ${companyLevel >= ipoLevel ? '' : 'disabled'}>Выйти на IPO</button></div>`;
    const stockList = stocks.length ? `<div class="space-y-2">${stocks.map(stock => `<button class="stock-card glass-card rounded-xl p-3 w-full text-left flex justify-between" data-stock-id="${stock.stock_id}"><span><b>${esc(stock.company_name)}</b><br><small class="text-slate-500">${esc(getSpecializationName(stock.specialization))} · дивиденды ${Number(stock.dividend_rate_pct || 5).toFixed(1)}%</small></span><strong class="text-emerald-600">${Number(stock.current_price || 0).toFixed(2)} cash<br><small class="text-slate-400">${stock.float_shares || 0} акций</small></strong></button>`).join('')}</div>` : '<div class="glass-card rounded-2xl p-6 text-center text-sm text-slate-500">Публичных компаний пока нет</div>';
    const body = `<div class="space-y-3">${ipoCard}${stockList}</div>`;
    container.innerHTML = marketShell('Акции компаний', 'Выберите компанию, чтобы открыть график и показатели', body);
    container.querySelector('.market-back')?.addEventListener('click', renderMarketHome);
    container.querySelectorAll('.stock-card').forEach(button => button.addEventListener('click', () => renderStockDetail(Number(button.dataset.stockId))));
    const ipoButton = container.querySelector('#market-ipo-open-btn');
    ipoButton?.addEventListener('click', async () => {
      const rate = Number(container.querySelector('#market-ipo-dividend-rate')?.value);
      if (!Number.isFinite(rate) || rate < 5 || rate > 50) {
        showToast('Укажите дивиденды от 5% до 50%', 'error');
        return;
      }
      ipoButton.disabled = true;
      ipoButton.textContent = 'Размещение...';
      try {
        await NatAPI.issueIPO({ dividend_rate_pct: rate });
        showToast('Компания вышла на IPO', 'success');
        const refreshedCompany = await NatAPI.getMyCompany();
        store.setCompany(refreshedCompany);
        await loadFinancialMarkets();
        renderStocksMarket();
      } catch (error) {
        showToast(error.message, 'error');
        ipoButton.disabled = false;
        ipoButton.textContent = 'Выйти на IPO';
      }
    });
  }

  function renderStockDetail(stockId) {
    const stock = (stocksData.stocks || []).find(item => Number(item.stock_id) === stockId);
    if (!stock) return renderStocksMarket();
    const chart = renderMarketChart(stock.history, { label: `График ${stock.company_name}`, color: trendOf(stock.history) === 'up' ? '#db2777' : '#7c3aed' });
    container.innerHTML = marketShell(esc(stock.company_name), `${stock.total_shares || 0} акций · IPO ${esc(stock.ipo_date || '')}`, `<div class="glass-card rounded-2xl p-3 space-y-3"><div class="flex justify-between"><b>${Number(stock.current_price || 0).toFixed(2)} cash</b><span class="text-emerald-600">${trendOf(stock.history) === 'up' ? '↗ Рост' : '↘ Снижение'}</span></div>${chart}<div class="grid grid-cols-2 gap-2 text-xs"><div>Дивиденды<br><b>${Number(stock.dividend_rate_pct || 5).toFixed(1)}% прибыли в день</b></div><div>Уровень компании<br><b>Серверный расчёт</b></div><div>Риск банкротства<br><b>Проверяется системой</b></div><div>Общий рейтинг<br><b>${Number(stock.last_valuation || 0).toLocaleString('ru-RU')} NAV</b></div></div><div class="grid grid-cols-2 gap-2"><button class="stock-buy py-2 rounded-xl bg-blue-600 text-white font-bold" data-id="${stock.stock_id}">Купить</button><button class="stock-sell py-2 rounded-xl bg-emerald-600 text-white font-bold" data-id="${stock.stock_id}">Продать</button></div></div>`);
    container.querySelector('.market-back')?.addEventListener('click', renderStocksMarket);
    const trade = async (side) => { const qty = parseInt(prompt('Количество акций:', '1'), 10); if (!qty || qty <= 0) return; const button = container.querySelector(`.stock-${side}`); button.disabled = true; try { await (side === 'buy' ? NatAPI.buyShares(stock.stock_id, qty) : NatAPI.sellShares(stock.stock_id, qty)); showToast(side === 'buy' ? 'Акции куплены' : 'Акции проданы', 'success'); stocksData = await NatAPI.getStocksList(); renderStockDetail(stock.stock_id); } catch (error) { showToast(error.message, 'error'); button.disabled = false; } };
    container.querySelector('.stock-buy')?.addEventListener('click', () => trade('buy')); container.querySelector('.stock-sell')?.addEventListener('click', () => trade('sell'));
  }

  function renderBondsMarket() {
    const bonds = bondsData.bonds || [];
    const body = bonds.length ? `<div class="space-y-2">${bonds.map(bond => `<button class="bond-card glass-card rounded-xl p-3 w-full text-left" data-bond-id="${bond.id}"><div class="flex justify-between"><b>${esc(bond.title)}</b><strong>${Number(bond.face_value || 0).toFixed(2)} cash</strong></div><div class="text-xs text-slate-500 mt-1">Купон ${bond.coupon_rate}% · Осталось ${bond.remaining_volume} · ${esc(bond.status || '')}</div></button>`).join('')}</div>` : '<div class="glass-card rounded-2xl p-6 text-center text-sm text-slate-500">Активных выпусков пока нет</div>';
    container.innerHTML = marketShell('Государственные облигации', 'Выберите выпуск, чтобы посмотреть условия', body);
    container.querySelector('.market-back')?.addEventListener('click', renderMarketHome);
    container.querySelectorAll('.bond-card').forEach(button => button.addEventListener('click', () => renderBondDetail(Number(button.dataset.bondId))));
  }

  function renderBondDetail(bondId) {
    const bond = (bondsData.bonds || []).find(item => Number(item.id) === bondId); if (!bond) return renderBondsMarket();
    const chartPoints = bond.history?.length ? bond.history : [{ timestamp: bond.created_at, price: bond.face_value }, { timestamp: new Date().toISOString(), price: bond.face_value }];
    const chart = renderMarketChart(chartPoints, { label: `График ${bond.title}`, color: '#c026d3' });
    container.innerHTML = marketShell(esc(bond.title), 'Государственный выпуск для поддержки экономики', `<div class="glass-card rounded-2xl p-4 space-y-3">${chart}<div class="space-y-1 text-sm"><div>Процентный купон: <b>${bond.coupon_rate}%</b></div><div>Текущая цена: <b>${Number(bond.face_value || 0).toFixed(2)} cash</b></div><div>Цена погашения: <b>${Number(bond.face_value || 0).toFixed(2)} cash</b></div><div>Оставшийся срок: <b>${bond.maturity_days || '—'} дней</b></div><div>Причина: <b>${esc(bond.purpose || 'Финансирование экономики')}</b></div></div><button class="bond-buy w-full py-2 rounded-xl bg-blue-600 text-white font-bold" data-id="${bond.id}">Купить облигацию</button></div>`);
    container.querySelector('.market-back')?.addEventListener('click', renderBondsMarket);
    container.querySelector('.bond-buy')?.addEventListener('click', async (button) => { const qty = parseInt(prompt('Количество облигаций:', '1'), 10); if (!qty || qty <= 0) return; button.currentTarget.disabled = true; try { await NatAPI.buyStateBonds(bond.id, qty); showToast('Облигации куплены', 'success'); await loadFinancialMarkets(); renderBondDetail(bond.id); } catch (error) { showToast(error.message, 'error'); button.currentTarget.disabled = false; } });
  }

  function renderReferenceMarket() {
    const body = `<div class="grid grid-cols-2 gap-2">${(instrumentsData.instruments || []).map(item => `<div class="glass-card rounded-xl p-3"><b>${INSTRUMENT_ICONS[item.code] || '💱'} ${INSTRUMENT_NAMES[item.code] || item.code}</b><div class="text-xs text-slate-500 mt-1">${item.reference_rub ? `${Number(item.sell_rub).toFixed(2)} ₽` : 'Курс загружается'}</div>${renderMarketChart(item.history, { label: `График ${INSTRUMENT_NAMES[item.code] || item.code}`, height: 104 })}<button class="reference-buy mt-2 w-full py-1.5 rounded-lg bg-blue-600 text-white text-xs font-bold" data-code="${item.code}">Купить</button></div>`).join('') || '<div class="col-span-2 text-sm text-slate-500">Курсы пока не получены</div>'}</div>`;
    container.innerHTML = marketShell('Валюты и металлы', 'Официальные курсы и торговля инструментами', body);
    container.querySelector('.market-back')?.addEventListener('click', renderMarketHome);
    container.querySelectorAll('.reference-buy').forEach(button => button.addEventListener('click', async () => { const qty = parseFloat(prompt('Количество:', '1')); if (!qty || qty <= 0) return; button.disabled = true; try { await NatAPI.tradeReferenceInstrument(button.dataset.code, 'buy', qty); showToast('Инструмент куплен', 'success'); } catch (error) { showToast(error.message, 'error'); button.disabled = false; } }));
  }

  function renderView() {
    const selectorScrollLeft = container.querySelector('.market-resource-tabs')?.scrollLeft || 0;
    const itemInfo = marketItems.find(i => i.id === selectedItemId) || marketItems[0];
    const bids = orderbookData?.bids || [];
    const asks = orderbookData?.asks || [];
    const tradeHistory = orderbookData?.history || [];
    const userOrders = orderbookData?.user_orders || [];
    const userInvQty = store.inventory[selectedItemId] || 0;
    const positions = new Map((instrumentsData.portfolio || []).map(row => [row.instrument_code, row]));
    const ownCompanyId = Number(store.company?.id || store.company?.company_id || 0);

    container.innerHTML = `
      <div class="space-y-4 max-w-md mx-auto p-4 pb-24">
        <!-- Resource Selector Bar -->
        <div class="market-resource-tabs flex items-center gap-2 overflow-x-auto pb-1 no-scrollbar">
          ${marketItems.map(item => `
            <button
              class="market-item-tab px-3 py-1.5 rounded-xl text-xs font-bold whitespace-nowrap transition-all ${
                item.id === selectedItemId
                  ? `bg-blue-600 text-white shadow-md shadow-blue-500/25 ${item.isIndustry ? 'border-2 border-amber-300 ring-1 ring-amber-300' : ''}`
                  : item.isIndustry
                    ? 'bg-amber-50 dark:bg-amber-950/30 text-amber-900 dark:text-amber-200 border-2 border-amber-400 shadow-sm'
                    : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700'
              }"
              data-item-id="${item.id}"
              title="${item.isIndustry ? 'Продукт вашей отрасли' : item.name}"
            >
              ${item.isIndustry ? '★ ' : ''}${item.name}
              ${item.isIndustry ? '<span class="ml-1 text-[9px] opacity-80">Ваша отрасль</span>' : ''}
            </button>
          `).join('')}
        </div>

        <!-- Official currency and metal instruments: same Market screen -->
        <details class="glass-card rounded-2xl p-4 shadow-sm space-y-3" open>
          <summary class="cursor-pointer list-none flex items-center justify-between">
            <div><h3 class="text-xs font-bold uppercase tracking-wider text-slate-500">Валюты и металлы</h3><p class="text-[9px] text-slate-400">Официальный курс ЦБ · цена задаётся сервером</p></div><span class="text-lg">🏦</span>
          </summary>
          <div class="grid grid-cols-2 gap-2 pt-3">
            ${(instrumentsData.instruments || []).map(instrument => {
              const position = positions.get(instrument.code) || {};
              return `<div class="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 space-y-2">
                <div class="flex justify-between"><span class="text-lg">${INSTRUMENT_ICONS[instrument.code] || '💱'}</span><span class="text-[9px] font-bold ${instrument.available ? 'text-emerald-500' : 'text-rose-500'}">${instrument.available ? 'Курс актуален' : 'Торги приостановлены'}</span></div>
                <div><div class="text-xs font-black">${INSTRUMENT_NAMES[instrument.code] || instrument.code}</div><div class="text-[9px] text-slate-400">Позиция: ${Number(position.quantity || 0).toLocaleString('ru-RU')}</div></div>
                ${instrument.reference_rub ? `<div class="text-[10px] font-mono"><span class="text-emerald-600">${Number(instrument.sell_rub).toFixed(2)} ₽</span> / <span class="text-rose-600">${Number(instrument.buy_rub).toFixed(2)} ₽</span></div>` : '<div class="text-[10px] text-slate-400">Курс ещё не загружен</div>'}
                <div class="grid grid-cols-2 gap-1"><button class="instrument-trade-btn py-1.5 rounded-lg bg-blue-600 text-white text-[10px] font-bold disabled:opacity-50" data-code="${instrument.code}" data-side="buy" ${instrument.available ? '' : 'disabled'}>Купить</button><button class="instrument-trade-btn py-1.5 rounded-lg bg-emerald-600 text-white text-[10px] font-bold disabled:opacity-50" data-code="${instrument.code}" data-side="sell" ${instrument.available && Number(position.quantity || 0) > 0 ? '' : 'disabled'}>Продать</button></div>
                ${instrument.quoted_at ? `<div class="text-[8px] text-slate-400">Котировка: ${new Date(instrument.quoted_at).toLocaleDateString('ru-RU')}</div>` : ''}
              </div>`;
            }).join('') || '<div class="col-span-2 text-xs text-slate-400 text-center py-2">Официальные курсы пока не получены</div>'}
          </div>
        </details>

        <!-- State bonds and protected secondary listings -->
        <details class="glass-card rounded-2xl p-4 shadow-sm space-y-3">
          <summary class="cursor-pointer list-none flex items-center justify-between"><div><h3 class="text-xs font-bold uppercase tracking-wider text-slate-500">Гособлигации</h3><p class="text-[9px] text-slate-400">Купоны, погашение и вторичный рынок</p></div><span class="text-lg">📜</span></summary>
          <div class="space-y-3 pt-3">
            ${(bondsData.bonds || []).map(bond => `<div class="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700"><div class="flex justify-between gap-2"><div><div class="text-xs font-black">${esc(bond.title)}</div><div class="text-[9px] text-slate-400">${bond.coupon_rate}% годовых · выплата каждые ${bond.coupon_interval_days || 1} дн. · ${esc(bond.status || '')}</div></div><div class="text-right"><div class="text-xs font-mono font-bold">${Number(bond.face_value).toFixed(2)} cash</div><div class="text-[9px] text-slate-400">остаток ${bond.remaining_volume}</div></div></div>${bond.is_active ? `<button class="buy-primary-bond-btn mt-2 w-full py-1.5 rounded-lg bg-blue-600 text-white text-[10px] font-bold disabled:opacity-50" data-bond-id="${bond.id}" data-title="${esc(bond.title)}">Купить у государства</button>` : ''}</div>`).join('') || '<div class="text-xs text-slate-400">Нет выпусков</div>'}
            ${(bondsData.holdings || []).filter(row => row.available_quantity > 0).length ? `<div><div class="text-[10px] font-bold uppercase text-slate-400 mb-1">Ваш портфель</div>${bondsData.holdings.filter(row => row.available_quantity > 0).map(row => `<div class="flex items-center justify-between p-2 rounded-lg bg-amber-50 dark:bg-amber-950/20 text-xs"><span>${esc(row.title)} · ${row.quantity} шт.</span><button class="create-bond-listing-btn text-blue-600 font-bold" data-bond-id="${row.bond_id}" data-available="${row.available_quantity}">Продать</button></div>`).join('')}</div>` : ''}
            <div><div class="text-[10px] font-bold uppercase text-slate-400 mb-1">Вторичные предложения</div>${(bondsData.listings || []).filter(row => row.status === 'OPEN').map(row => `<div class="flex items-center justify-between gap-2 p-2 rounded-lg bg-slate-50 dark:bg-slate-800/50 text-xs"><div><div class="font-bold">Выпуск #${row.bond_id} · ${row.quantity} шт.</div><div class="text-[9px] text-slate-400">${Number(row.unit_price).toFixed(2)} cash/шт. · всего ${Number(row.total_cost).toFixed(2)}</div></div>${Number(row.seller_company_id) === ownCompanyId ? `<button class="cancel-bond-listing-btn text-rose-500 font-bold" data-listing-id="${row.listing_id}">Снять</button>` : `<button class="buy-bond-listing-btn px-3 py-1.5 rounded-lg bg-indigo-600 text-white font-bold disabled:opacity-50" data-listing-id="${row.listing_id}">Купить</button>`}</div>`).join('') || '<div class="text-[10px] text-slate-400">Открытых предложений нет</div>'}</div>
          </div>
        </details>

        <!-- NPC Reserve Liquidity Banner -->
        <div class="glass-card rounded-2xl p-4 shadow-sm space-y-2 border-l-4 border-l-amber-500">
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold uppercase tracking-wider text-amber-600 dark:text-amber-400">
              Резервный фонд NPC (Гарантированный коридор)
            </span>
            <span class="text-[10px] font-mono text-slate-400">База: ${itemInfo.base} cash</span>
          </div>
          <div class="grid grid-cols-2 gap-2 text-xs">
            <div class="p-2 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800">
              <div class="text-[10px] font-semibold text-emerald-700 dark:text-emerald-300">Скупка NPC (Пол -20%)</div>
              <div class="font-mono font-black text-sm text-emerald-600 dark:text-emerald-400">${itemInfo.buy.toFixed(2)} cash</div>
              <button class="npc-sell-btn mt-1 w-full py-1 rounded bg-emerald-600 text-white font-bold text-[11px] active:scale-95 transition-all disabled:opacity-50">
                Сдать NPC
              </button>
            </div>
            <div class="p-2 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800">
              <div class="text-[10px] font-semibold text-rose-700 dark:text-rose-300">Продажа NPC (Потолок +25%)</div>
              <div class="font-mono font-black text-sm text-rose-600 dark:text-rose-400">${itemInfo.sell.toFixed(2)} cash</div>
              <button class="npc-buy-btn mt-1 w-full py-1 rounded bg-rose-600 text-white font-bold text-[11px] active:scale-95 transition-all">
                Купить у NPC
              </button>
            </div>
          </div>
          <div class="text-[10px] text-slate-400">
            На вашем складе: <span class="font-mono font-bold text-slate-700 dark:text-slate-200">${userInvQty} ${itemInfo.unit}</span>
          </div>
        </div>

        <!-- Orderbook (Стакан биржи) -->
        <div class="glass-card rounded-2xl p-4 shadow-sm space-y-3">
          <div class="flex items-center justify-between">
            <h3 class="text-xs font-bold uppercase tracking-wider text-slate-400">Биржевой стакан цен</h3>
            <span class="text-[11px] text-slate-500 font-bold">${itemInfo.name}</span>
          </div>

          ${renderMarketChart(tradeHistory, { label: `График ${itemInfo.name}`, height: 104 })}

          <div class="grid grid-cols-2 gap-3 text-xs">
            <!-- Asks (Продажа) -->
            <div class="space-y-1">
              <div class="text-[10px] font-bold text-rose-500 uppercase">Продажа (Asks)</div>
              ${asks.length === 0 ? '<div class="text-slate-400 text-[10px]">Нет заявок</div>' : asks.slice(0, 5).map(a => `
                <div class="flex justify-between font-mono p-1 rounded depth-ask text-[11px]">
                  <span class="text-rose-600 font-bold">${a.price.toFixed(2)}</span>
                  <span class="text-slate-500">${a.remaining_qty} ${itemInfo.unit}</span>
                </div>
              `).join('')}
            </div>

            <!-- Bids (Покупка) -->
            <div class="space-y-1">
              <div class="text-[10px] font-bold text-emerald-500 uppercase">Покупка (Bids)</div>
              ${bids.length === 0 ? '<div class="text-slate-400 text-[10px]">Нет заявок</div>' : bids.slice(0, 5).map(b => `
                <div class="flex justify-between font-mono p-1 rounded depth-bid text-[11px]">
                  <span class="text-emerald-600 font-bold">${b.price.toFixed(2)}</span>
                  <span class="text-slate-500">${b.remaining_qty} ${itemInfo.unit}</span>
                </div>
              `).join('')}
            </div>
          </div>
        </div>

        <!-- Place Limit Order Form -->
        <div class="glass-card rounded-2xl p-4 shadow-sm space-y-3">
          <h3 class="text-xs font-bold uppercase tracking-wider text-slate-400">Выставить биржевой ордер</h3>
          <form id="place-order-form" class="space-y-3">
            <div class="grid grid-cols-2 gap-2">
              <label class="flex items-center justify-center p-2 rounded-xl border border-slate-300 dark:border-slate-700 cursor-pointer has-[:checked]:bg-emerald-600 has-[:checked]:text-white has-[:checked]:border-emerald-600 transition-all text-xs font-bold">
                <input type="radio" name="order_side" value="buy" checked class="hidden" />
                🟢 Покупка
              </label>
              <label class="flex items-center justify-center p-2 rounded-xl border border-slate-300 dark:border-slate-700 cursor-pointer has-[:checked]:bg-rose-600 has-[:checked]:text-white has-[:checked]:border-rose-600 transition-all text-xs font-bold">
                <input type="radio" name="order_side" value="sell" class="hidden" />
                🔴 Продажа
              </label>
            </div>

            <div class="grid grid-cols-2 gap-2">
              <div>
                <label class="block text-[10px] font-bold text-slate-500 mb-1 uppercase">Количество (${itemInfo.unit})</label>
                <input type="number" id="order-qty" min="1" step="1" value="10" required class="w-full px-3 py-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-xs font-mono text-slate-900 dark:text-white" />
              </div>
              <div>
                <label class="block text-[10px] font-bold text-slate-500 mb-1 uppercase">Цена (cash)</label>
                <input type="number" id="order-price" min="0.1" step="0.1" value="${itemInfo.base}" required class="w-full px-3 py-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-xs font-mono text-slate-900 dark:text-white" />
              </div>
            </div>

            <button type="submit" id="submit-order-btn" class="w-full py-2.5 rounded-xl bg-blue-600 text-white font-bold text-xs shadow-md shadow-blue-500/25 hover:bg-blue-700 active:scale-98 transition-all">
              Разместить ордер в стакан
            </button>
          </form>
        </div>

        <!-- Open User Orders -->
        ${userOrders.length > 0 ? `
          <div class="glass-card rounded-2xl p-4 shadow-sm space-y-2">
            <h3 class="text-xs font-bold uppercase tracking-wider text-slate-400">Ваши активные ордера</h3>
            <div class="space-y-1.5">
              ${userOrders.map(o => `
                <div class="p-2 rounded-lg bg-slate-50 dark:bg-slate-800/50 flex items-center justify-between text-xs font-mono">
                  <div class="flex items-center gap-2">
                    <span class="font-bold ${o.order_type === 'buy' ? 'text-emerald-500' : 'text-rose-500'}">
                      ${o.order_type.toUpperCase()}
                    </span>
                    <span>${o.remaining_quantity} @ ${o.price} cash</span>
                  </div>
                  <button class="cancel-order-btn text-rose-500 hover:text-rose-700 text-[11px] font-bold" data-order-id="${o.id}">
                    Отменить
                  </button>
                </div>
              `).join('')}
            </div>
          </div>
        ` : ''}
      </div>
    `;

    const resourceTabs = container.querySelector('.market-resource-tabs');
    if (resourceTabs) {
      resourceTabs.scrollLeft = selectorScrollLeft;
      // Mouse wheel → horizontal scroll (PC / Telegram Desktop)
      resourceTabs.addEventListener('wheel', (e) => {
        if (e.deltaY !== 0) { e.preventDefault(); resourceTabs.scrollLeft += e.deltaY; }
      }, { passive: false });
    }

    // Tab click listeners
    container.querySelectorAll('.market-item-tab').forEach(btn => {
      btn.addEventListener('click', async () => {
        const nextItemId = btn.getAttribute('data-item-id');
        if (!nextItemId || nextItemId === selectedItemId) return;
        selectedItemId = nextItemId;
        if (await loadOrderbook()) renderView();
      });
    });

    container.querySelectorAll('.instrument-trade-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const quantity = parseFloat(prompt(`Количество ${btn.dataset.code}:`, '1'));
        if (!quantity || quantity <= 0) return;
        btn.disabled = true;
        try {
          await NatAPI.tradeReferenceInstrument(btn.dataset.code, btn.dataset.side, quantity);
          await loadFinancialMarkets();
          const company = await NatAPI.getMyCompany();
          store.setCompany(company);
          showToast('Сделка исполнена по серверному курсу', 'success');
          renderView();
        } catch (err) { showToast(err.message, 'error'); btn.disabled = false; }
      });
    });

    container.querySelectorAll('.buy-primary-bond-btn').forEach(btn => btn.addEventListener('click', async () => {
      const quantity = parseInt(prompt(`Сколько облигаций «${btn.dataset.title}» купить?`, '1'), 10);
      if (!quantity || quantity <= 0) return;
      btn.disabled = true;
      try { await NatAPI.buyStateBonds(btn.dataset.bondId, quantity); await loadFinancialMarkets(); store.setCompany(await NatAPI.getMyCompany()); showToast('Облигации куплены', 'success'); renderView(); }
      catch (err) { showToast(err.message, 'error'); btn.disabled = false; }
    }));

    container.querySelectorAll('.create-bond-listing-btn').forEach(btn => btn.addEventListener('click', async () => {
      const quantity = parseInt(prompt(`Количество для продажи (доступно ${btn.dataset.available}):`, '1'), 10);
      const price = parseFloat(prompt('Цена за одну облигацию:', '1000'));
      if (!quantity || quantity <= 0 || !price || price <= 0) return;
      btn.disabled = true;
      try { await NatAPI.createBondListing(btn.dataset.bondId, quantity, price); await loadFinancialMarkets(); showToast('Облигации выставлены на вторичный рынок', 'success'); renderView(); }
      catch (err) { showToast(err.message, 'error'); btn.disabled = false; }
    }));

    container.querySelectorAll('.buy-bond-listing-btn').forEach(btn => btn.addEventListener('click', async () => {
      btn.disabled = true;
      try { await NatAPI.buyBondListing(btn.dataset.listingId); await loadFinancialMarkets(); store.setCompany(await NatAPI.getMyCompany()); showToast('Листинг куплен', 'success'); renderView(); }
      catch (err) { showToast(err.message, 'error'); btn.disabled = false; }
    }));

    container.querySelectorAll('.cancel-bond-listing-btn').forEach(btn => btn.addEventListener('click', async () => {
      btn.disabled = true;
      try { await NatAPI.cancelBondListing(btn.dataset.listingId); await loadFinancialMarkets(); showToast('Листинг снят', 'info'); renderView(); }
      catch (err) { showToast(err.message, 'error'); btn.disabled = false; }
    }));

    // NPC Trade handlers
    container.querySelector('.npc-sell-btn')?.addEventListener('click', async () => {
      const qtyStr = prompt(`Сколько единиц ${itemInfo.name} сдать NPC по цене ${itemInfo.buy.toFixed(2)} cash?`, '10');
      const qty = parseFloat(qtyStr);
      if (!qty || qty <= 0) return;
      try {
        const res = await NatAPI.npcTrade({ item_id: selectedItemId, operation: 'sell', quantity: qty });
        showToast(res.message || 'Сделка с NPC завершена!', 'success');
        const refreshed = await NatAPI.getMyCompany();
        store.setCompany(refreshed);
        await Promise.all([loadOrderbook(), refreshNpcRates()]);
        renderView();
      } catch (err) {
        showToast(err.message, 'error');
      }
    });

    container.querySelector('.npc-buy-btn')?.addEventListener('click', async () => {
      const qtyStr = prompt(`Сколько единиц ${itemInfo.name} купить у NPC по цене ${itemInfo.sell.toFixed(2)} cash?`, '10');
      const qty = parseFloat(qtyStr);
      if (!qty || qty <= 0) return;
      try {
        const res = await NatAPI.npcTrade({ item_id: selectedItemId, operation: 'buy', quantity: qty });
        showToast(res.message || 'Сделка с NPC завершена!', 'success');
        const refreshed = await NatAPI.getMyCompany();
        store.setCompany(refreshed);
        await Promise.all([loadOrderbook(), refreshNpcRates()]);
        renderView();
      } catch (err) {
        showToast(err.message, 'error');
      }
    });

    // Place Limit Order handler
    container.querySelector('#place-order-form')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const side = container.querySelector('input[name="order_side"]:checked').value;
      const amount = parseFloat(container.querySelector('#order-qty').value);
      const price = parseFloat(container.querySelector('#order-price').value);

      const btn = container.querySelector('#submit-order-btn');
      try {
        if (btn) {
          btn.disabled = true;
          btn.innerText = 'Размещение...';
        }
        await NatAPI.placeOrder({ item_id: selectedItemId, side, amount, price });
        showToast('Ордер успешно выставлен!', 'success');
        const refreshed = await NatAPI.getMyCompany();
        store.setCompany(refreshed);
        await loadOrderbook();
        renderView();
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerText = 'Разместить ордер в стакан';
        }
      }
    });

    // Cancel Order handler
    container.querySelectorAll('.cancel-order-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const orderId = btn.getAttribute('data-order-id');
        try {
          await NatAPI.cancelOrder(orderId);
          showToast('Ордер отменён', 'info');
          const refreshed = await NatAPI.getMyCompany();
          store.setCompany(refreshed);
          await loadOrderbook();
          renderView();
        } catch (err) {
          showToast(err.message, 'error');
        }
      });
    });
  }

  renderMarketHome();
}
