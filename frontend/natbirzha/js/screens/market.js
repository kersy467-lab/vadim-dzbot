import { NatAPI } from '../api.js?v=20260924_state_credit_approval';
import { store } from '../state.js';
import { getItemInfo } from '../items.js';
import { renderMarketChart } from '../market_chart.js';
import { renderTaxSection } from './market_tax.js';
import { renderStateCreditSection } from './market_credit.js?v=20260924_state_credit_approval';
import { createMarketFinance } from './market_finance.js?v=20260924_state_credit_approval';
import { getCompanyInputIds, renderCommodityCatalog } from './market_commodities.js';
import { renderBankruptcyMarket } from './bankruptcy_market.js';

const MARKET_ITEMS = [
  { id: 'steel', name: 'Сталь', unit: 'т', base: 90.0, buy: 72.0, sell: 135.0 },
  { id: 'iron_ore', name: 'Железная руда', unit: 'т', base: 35.0, buy: 28.0, sell: 52.5 },
  { id: 'coal', name: 'Каменный уголь', unit: 'т', base: 30.0, buy: 24.0, sell: 45.0 },
  { id: 'energy', name: 'Электроэнергия', unit: 'МВт·ч', base: 10.0, buy: 8.0, sell: 15.0 },
  { id: 'oil_crude', name: 'Сырая нефть', unit: 'барр.', base: 50.0, buy: 40.0, sell: 75.0 },
  { id: 'fuel_diesel', name: 'Дизельное топливо', unit: 'л', base: 1.2, buy: 0.96, sell: 1.8 },
  { id: 'grain', name: 'Зерно', unit: 'т', base: 20.0, buy: 16.0, sell: 30.0 },
  { id: 'fertilizer', name: 'Удобрения', unit: 'т', base: 50.0, buy: 40.0, sell: 75.0 },
  { id: 'wood_raw', name: 'Лес-кругляк', unit: 'м³', base: 25.0, buy: 20.0, sell: 37.5 },
  { id: 'aluminum', name: 'Алюминий', unit: 'т', base: 110.0, buy: 88.0, sell: 165.0 },
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
      name: rate.name || getItemInfo(rate.item_id).name,
      unit: rate.unit || 'шт.',
      base: Number(rate.base_price),
      buy: Number(rate.npc_buy_price),
      sell: Number(rate.npc_sell_price),
      playerSellRemainingCash: Number(rate.player_sell_remaining_cash),
      playerSellRemainingQuantity: Number(rate.player_sell_remaining_quota),
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
  const commodityCatalogState = { category: 'search', query: '' };


  async function loadOrderbook() {
    const requestId = ++orderbookRequestId;
    orderbookData = null;
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



  const finance = createMarketFinance(container, showToast, renderMarketHome);

  const [ratesData, loadedRecipes, businessCatalog, empireSummary] = await Promise.all([
    NatAPI.getNpcRates().catch(() => null),
    NatAPI.getRecipes().catch(() => null),
    NatAPI.getBusinessCatalog().catch(() => ({ items: [] })),
    NatAPI.getEmpireSummary().catch(() => null),
    finance.load(),
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
  const industryOutputs = getIndustryOutputIds(
    store.company?.specialization, recipesData.recipes, businessCatalog?.items || []
  );
  const companyInputIds = getCompanyInputIds(
    empireSummary?.businesses, store.factories, recipesData.recipes
  );
  marketItems = prioritizeIndustryItems(marketItems, industryOutputs);


  function renderCommodityBrowser() {
    renderCommodityCatalog(container, {
      items: marketItems,
      inventory: store.inventory,
      inputIds: companyInputIds,
      state: commodityCatalogState,
      onBack: renderMarketHome,
      onSelect: async (itemId) => {
        if (!marketItems.some((item) => item.id === itemId)) return;
        selectedItemId = itemId;
        await loadOrderbook();
        renderView();
      },
    });
  }

  function renderMarketHome() {
    container.innerHTML = `<div class="market-contrast-surface space-y-4 max-w-md mx-auto p-4 pb-24"><div><h2 class="text-xl font-black">Биржа</h2><p class="text-xs text-slate-500">Выберите раздел рынка</p></div><div class="grid gap-3"><button class="market-section-btn glass-card rounded-2xl p-5 text-left border-2 border-blue-200 dark:border-blue-900" data-section="portfolio"><div class="text-2xl">💼</div><div class="font-black mt-2">Мой портфель</div><div class="text-xs text-slate-500">Акции, облигации, валюты, металлы и выплаты</div></button><button class="market-section-btn glass-card rounded-2xl p-5 text-left" data-section="stocks"><div class="text-2xl">📈</div><div class="font-black mt-2">Акции компаний</div><div class="text-xs text-slate-500">Игроки, вышедшие на IPO</div></button><button class="market-section-btn glass-card rounded-2xl p-5 text-left" data-section="bankruptcy_market"><div class="text-2xl">🏭</div><div class="font-black mt-2">Рынок банкротов</div><div class="text-xs text-slate-500">Заводы конфискованных компаний, наценка государства 30%</div></button><button class="market-section-btn glass-card rounded-2xl p-5 text-left" data-section="bonds"><div class="text-2xl">🏛️</div><div class="font-black mt-2">Государственные облигации</div><div class="text-xs text-slate-500">Купоны, погашение и вторичный рынок</div></button><button class="market-section-btn glass-card rounded-2xl p-5 text-left" data-section="reference"><div class="text-2xl">💱</div><div class="font-black mt-2">Валюты и металлы</div><div class="text-xs text-slate-500">Курсы официальных инструментов</div></button><button class="market-section-btn glass-card rounded-2xl p-5 text-left" data-section="commodities"><div class="text-2xl">🪙</div><div class="font-black mt-2">Сырьё и материалы</div><div class="text-xs text-slate-500">Стакан, NPC и торговые ордера</div></button><button class="market-section-btn glass-card rounded-2xl p-5 text-left" data-section="tax"><div class="text-2xl">🧾</div><div class="font-black mt-2">Налог</div><div class="text-xs text-slate-500">13% дневной прибыли, задолженность и штрафы</div></button><button class="market-section-btn glass-card rounded-2xl p-5 text-left" data-section="state_credit"><div class="text-2xl">🏦</div><div class="font-black mt-2">Кредит государства</div><div class="text-xs text-slate-500">Займ компании под 15% в день</div></button></div></div>`;
    container.querySelectorAll('.market-section-btn').forEach((button) => button.addEventListener('click', () => {
      const section = button.dataset.section;
      if (section === 'portfolio') finance.renderPortfolio();
      else if (section === 'stocks') finance.renderStocks();
      else if (section === 'bankruptcy_market') renderBankruptcyMarket(container, showToast, renderMarketHome);
      else if (section === 'bonds') finance.renderBonds();
      else if (section === 'reference') finance.renderReference();
      else if (section === 'tax') renderTaxSection(container, showToast, renderMarketHome);
      else if (section === 'state_credit') renderStateCreditSection(container, showToast, renderMarketHome);
      else if (section === 'commodities') renderCommodityBrowser();
    }));
  }

  function renderView() {
    const itemInfo = marketItems.find(i => i.id === selectedItemId) || marketItems[0];
    const bids = orderbookData?.bids || [];
    const asks = orderbookData?.asks || [];
    const tradeHistory = orderbookData?.history || [];
    const userOrders = orderbookData?.user_orders || [];
    const userInvQty = store.inventory[selectedItemId] || 0;

    container.innerHTML = `
      <div class="space-y-4 max-w-md mx-auto p-4 pb-24">
        <button type="button" class="market-back text-xs font-bold text-pink-500">← Список сырья</button>
        <div><h2 class="text-lg font-black">${itemInfo.name}</h2><p class="text-[10px] text-slate-500">Стакан, NPC и торговые ордера · ${itemInfo.unit}</p></div>

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
              <div class="text-[10px] font-semibold text-rose-700 dark:text-rose-300">Продажа NPC (Потолок +50%)</div>
              <div class="font-mono font-black text-sm text-rose-600 dark:text-rose-400">${itemInfo.sell.toFixed(2)} cash</div>
              <button class="npc-buy-btn mt-1 w-full py-1 rounded bg-rose-600 text-white font-bold text-[11px] active:scale-95 transition-all">
                Купить у NPC
              </button>
            </div>
          </div>
          <div class="rounded-lg bg-emerald-50/70 px-2.5 py-2 text-[10px] text-emerald-800 dark:bg-emerald-950/20 dark:text-emerald-200">
            Скупка этого товара Госрезервом: ${Number.isFinite(itemInfo.playerSellRemainingCash) ? `${itemInfo.playerSellRemainingCash.toLocaleString('ru-RU', { maximumFractionDigits: 0 })} cash (${Number(itemInfo.playerSellRemainingQuantity || 0).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ${itemInfo.unit})` : 'без ограничений'}.
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
                      ${o.order_type === 'BUY' ? 'ПОКУПКА' : 'ПРОДАЖА'}
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

    container.querySelector('.market-back')?.addEventListener('click', renderCommodityBrowser);

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
