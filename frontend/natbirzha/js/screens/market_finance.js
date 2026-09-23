import { NatAPI } from '../api.js?v=20260921_broker1';
import { store } from '../state.js';
import { getSpecializationName } from '../localization.js';
import { marketChange, renderMarketChart } from '../market_chart.js';
import { renderStateShareMarket } from './state_share_market.js';

const esc = (value) => String(value ?? '').replace(/[&<>'"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[ch]));
const money = (value) => `${Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} cash`;
const pnl = (value) => `<span class="${Number(value || 0) >= 0 ? 'text-emerald-600' : 'text-rose-600'} font-mono font-bold">${Number(value || 0) >= 0 ? '+' : ''}${money(value)}</span>`;
const ICONS = { USD: '💵', EUR: '💶', GOLD: '🥇', SILVER: '🥈' };
const NAMES = { USD: 'Доллар США', EUR: 'Евро', GOLD: 'Золото', SILVER: 'Серебро' };

function bondStatusLabel(status) {
  return ({ ACTIVE: 'Активен', OFFERING: 'Размещение', MATURED: 'Погашен', CLOSED: 'Закрыт', CANCELLED: 'Отменён' }[String(status || '').toUpperCase()] || 'Статус неизвестен');
}

function changeHtml(points, suffix = '') {
  const change = marketChange(points);
  const positive = change.absolute >= 0;
  return `<span class="broker-change ${positive ? 'is-up' : 'is-down'}">${positive ? '+' : ''}${change.absolute.toLocaleString('ru-RU', { maximumFractionDigits: 2 })}${suffix} · ${positive ? '+' : ''}${change.percent.toFixed(2)}%</span>`;
}

function chartCard(points, label, options = {}) {
  return `<div class="broker-chart-card">${renderMarketChart(points, { ...options, label })}</div>`;
}

function bookRows(rows, side) {
  if (!rows?.length) return '<div class="broker-book-empty">Нет заявок</div>';
  return rows.map(row => `<div class="broker-book-row ${side === 'BUY' ? 'is-bid' : 'is-ask'}"><span>${Number(row.price).toFixed(2)}</span><b>${Number(row.quantity).toLocaleString('ru-RU')}</b></div>`).join('');
}

export function createMarketFinance(container, showToast, onBack) {
  let instruments = { instruments: [], portfolio: [] };
  let bonds = { bonds: [], holdings: [], listings: [] };
  let stocks = { stocks: [] };
  const view = { stockTab: 'overview' };
  const stockHistoryCache = new Map();
  const shell = (title, subtitle, body) => `<div class="market-contrast-surface space-y-4 max-w-md mx-auto p-4 pb-24"><button class="market-back text-xs font-bold text-blue-600">← Все разделы рынка</button><div><h2 class="text-xl font-black">${title}</h2><p class="text-xs text-slate-500">${subtitle}</p></div>${body}</div>`;
  const bindBack = (target = onBack) => container.querySelector('.market-back')?.addEventListener('click', target);

  async function load() {
    const [instrumentResult, bondResult, stockResult] = await Promise.allSettled([
      NatAPI.getReferenceInstruments(), NatAPI.getStateBonds(), NatAPI.getStocksList(),
    ]);
    if (instrumentResult.status === 'fulfilled') instruments = instrumentResult.value || instruments;
    if (bondResult.status === 'fulfilled') bonds = bondResult.value || bonds;
    if (stockResult.status === 'fulfilled') stocks = stockResult.value || stocks;
  }

  async function renderPortfolio() {
    container.innerHTML = '<div class="p-6 text-center text-xs text-slate-400">Загрузка портфеля…</div>';
    let portfolio;
    try { portfolio = await NatAPI.getPortfolio(); } catch (error) { showToast(error.message, 'error'); return onBack(); }
    const summary = portfolio.summary || {};
    const stockBody = (portfolio.stocks || []).map(row => `<div class="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50"><div class="flex justify-between"><b>${esc(row.issuer_company)}</b><span>${row.shares_count} акций</span></div><div class="flex justify-between text-xs"><span>${money(row.market_value)}</span>${pnl(row.unrealized_pnl)}</div><div class="text-[10px] text-slate-500">Дивиденды: ${money(row.dividends_earned)} · ${row.next_dividend_at ? `следующая выплата ${new Date(row.next_dividend_at).toLocaleString('ru-RU')}` : 'выплаты недоступны'}</div></div>`).join('') || '<div class="text-xs text-slate-400">Акций пока нет</div>';
    const bondBody = (portfolio.bonds || []).map(row => `<div class="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50"><div class="flex justify-between"><b>${esc(row.title)}</b><span>${row.quantity} шт.</span></div><div class="flex justify-between text-xs"><span>${money(row.market_value)}</span>${pnl(row.unrealized_pnl)}</div></div>`).join('') || '<div class="text-xs text-slate-400">Облигаций пока нет</div>';
    const stateShareBody = (portfolio.state_shares || []).map(row => `<div class="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50"><div class="flex justify-between"><b>${esc(row.title)}</b><span>${Number(row.shares_count).toLocaleString('ru-RU')} акций</span></div><div class="text-[10px] text-slate-500">${money(row.market_value)} · дивиденды ${money(row.dividends_earned)}</div></div>`).join('') || '<div class="text-xs text-slate-400">Акций государства пока нет</div>';
    const instrumentBody = (portfolio.instruments || []).map(row => `<div class="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 flex justify-between"><b>${esc(NAMES[row.instrument_code] || row.instrument_code)}</b><span>${row.quantity} · ${money(row.market_value_rub)}</span></div>`).join('') || '<div class="text-xs text-slate-400">Инструментов пока нет</div>';
    const publicPayments = (portfolio.dividend_payments || []).slice(0, 20).map(row => `<div class="flex justify-between p-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/20 text-xs"><span>${esc(row.issuer_company)} · ${esc(row.settlement_date)}</span><b>+${money(row.payout_cash)}</b></div>`).join('');
    const stateSharePayments = (portfolio.state_share_dividend_payments || []).slice(0, 20).map(row => `<div class="flex justify-between p-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/20 text-xs"><span>${esc(row.title)} · ${esc(row.settlement_date)}</span><b>+${money(row.payout_cash)}</b></div>`).join('');
    const paymentsBody = publicPayments + stateSharePayments || '<div class="text-xs text-slate-400">Дивидендных выплат пока не было</div>';
    container.innerHTML = shell('Мой портфель', 'Все финансовые активы компании', `<div class="space-y-3"><div class="glass-card rounded-2xl p-4 grid grid-cols-2 gap-2 text-xs"><div><span class="text-slate-500">Баланс</span><b class="block text-base">${money(portfolio.cash)}</b></div><div><span class="text-slate-500">Стоимость активов</span><b class="block text-base">${money(summary.market_value)}</b></div><div>Результат<br>${pnl(summary.unrealized_pnl)}</div><div>Выплаты<br><b>${money(Number(summary.dividends_earned || 0) + Number(summary.coupons_earned || 0))}</b></div></div><details class="glass-card rounded-2xl p-4" open><summary class="font-black">📈 Акции</summary><div class="space-y-2 pt-3">${stockBody}</div></details><details class="glass-card rounded-2xl p-4"><summary class="font-black">🏛️ Облигации</summary><div class="space-y-2 pt-3">${bondBody}</div></details><details class="glass-card rounded-2xl p-4"><summary class="font-black">🏛️ Акции государства</summary><div class="space-y-2 pt-3">${stateShareBody}</div></details><details class="glass-card rounded-2xl p-4"><summary class="font-black">💱 Валюты и металлы</summary><div class="space-y-2 pt-3">${instrumentBody}</div></details><details class="glass-card rounded-2xl p-4"><summary class="font-black">💸 История дивидендов</summary><div class="space-y-2 pt-3">${paymentsBody}</div></details></div>`);
    bindBack();
  }

  function renderStocks() {
    const list = stocks.stocks || [];
    const ownId = Number(store.company?.id || store.company?.company_id || 0);
    const ownStock = list.find(item => Number(item.company_id) === ownId);
    const level = Number(store.company?.level || 1);
    const ipoLevel = Number(store.company?.capital_plan?.ipo_available_from_level || 18);
    const ipo = ownStock ? '' : `<div class="glass-card rounded-2xl p-4 space-y-3"><div class="font-bold">🚀 Выход на IPO</div><div class="text-xs text-slate-500">Доступно с ${ipoLevel} уровня. Сейчас: ${level} ур.</div><input id="market-ipo-dividend-rate" type="number" min="5" max="100" step="0.5" value="5" class="w-full rounded-lg border p-2 bg-white dark:bg-slate-900"><button id="market-ipo-open-btn" class="w-full py-2 rounded-xl bg-blue-600 text-white font-bold" ${level >= ipoLevel ? '' : 'disabled'}>Выйти на IPO</button></div>`;
    const body = list.map(stock => `<button class="stock-card glass-card rounded-xl p-3 w-full text-left flex justify-between" data-id="${stock.stock_id}"><span><b>${esc(stock.company_name)}</b><br><small>${esc(getSpecializationName(stock.specialization))} · дивиденды ${Number(stock.dividend_rate_pct || 5).toFixed(1)}%</small></span><strong>${Number(stock.current_price || 0).toFixed(2)} cash</strong></button>`).join('') || '<div class="glass-card rounded-2xl p-6 text-center text-sm text-slate-500">Публичных компаний пока нет</div>';
    container.innerHTML = shell('Акции компаний', 'Цена зависит от бизнеса и реального стакана заявок', `<div class="space-y-3">${ipo}${body}</div>`); bindBack();
    container.querySelectorAll('.stock-card').forEach(btn => btn.addEventListener('click', () => renderStockDetail(Number(btn.dataset.id))));
    container.querySelector('#market-ipo-open-btn')?.addEventListener('click', async (event) => {
      const rate = Number(container.querySelector('#market-ipo-dividend-rate')?.value); if (rate < 5 || rate > 100) return showToast('Укажите дивиденды от 5% до 100%', 'error');
      event.currentTarget.disabled = true;
      try { await NatAPI.issueIPO({ dividend_rate_pct: rate }); stockHistoryCache.clear(); store.setCompany(await NatAPI.getMyCompany()); await load(); showToast('Компания вышла на IPO', 'success'); renderStocks(); } catch (error) { showToast(error.message, 'error'); event.currentTarget.disabled = false; }
    });
  }

  function renderStateShares() {
    return renderStateShareMarket(container, showToast, onBack);
  }

  async function renderStockDetail(id) {
    const stock = (stocks.stocks || []).find(item => Number(item.stock_id) === id); if (!stock) return renderStocks();
    let book = { bids: [], asks: [], own_orders: [], best_bid: null, best_ask: null, current_price: stock.current_price };
    try { book = await NatAPI.getStockOrderbook(id); } catch (_) {}
    const historyKey = String(id);
    let history = stockHistoryCache.get(historyKey) || stock.history || [];
    if (!stockHistoryCache.has(historyKey)) {
      try {
        const payload = await NatAPI.getStockHistory(id);
        history = payload.history || history;
        stockHistoryCache.set(historyKey, history);
      } catch (_) {}
    }
    const overview = `<div class="space-y-3"><div class="broker-quote"><div><div class="broker-price">${Number(stock.current_price || 0).toFixed(2)} cash</div>${changeHtml(history)}</div><div class="broker-spread"><span>Bid ${book.best_bid ?? '—'}</span><span>Ask ${book.best_ask ?? '—'}</span></div></div>${chartCard(history, `График ${stock.company_name}`)}<div class="broker-stat-grid"><div><span>Оценка компании</span><b>${money(stock.last_valuation)}</b></div><div><span>Акций</span><b>${Number(stock.total_shares || 0).toLocaleString('ru-RU')}</b></div><div><span>Дивиденды</span><b>${Number(stock.dividend_rate_pct || 0).toFixed(1)}%</b></div><div><span>Свободный float</span><b>${Number(stock.float_shares || 0).toLocaleString('ru-RU')}</b></div></div></div>`;
    const ownOrders = (book.own_orders || []).map(row => `<div class="broker-own-order"><span>${row.side === 'BUY' ? 'Купить' : 'Продать'} ${row.remaining} @ ${Number(row.price).toFixed(2)}</span><button class="stock-order-cancel" data-id="${row.order_id}">Снять</button></div>`).join('') || '<div class="broker-book-empty">У вас нет активных заявок</div>';
    const band = book.price_band || {};
    const orderbook = `<div class="space-y-3"><div class="broker-book"><div><h4>Покупка</h4>${bookRows(book.bids, 'BUY')}</div><div><h4>Продажа</h4>${bookRows(book.asks, 'SELL')}</div></div><div class="text-[10px] text-slate-500">Допустимый ценовой коридор: ${band.min ?? '—'}–${band.max ?? '—'} cash</div><div class="broker-order-form"><select id="stock-order-side"><option value="BUY">Купить</option><option value="SELL">Продать</option></select><input id="stock-order-qty" type="number" min="1" step="1" value="1" placeholder="Количество"><input id="stock-order-price" type="number" min="${band.min ?? 0.01}" max="${band.max ?? ''}" step="0.01" value="${Number(book.best_ask || stock.current_price || 1).toFixed(2)}" placeholder="Цена"><button id="stock-order-submit">Выставить заявку</button></div><div class="space-y-2"><b class="text-xs">Ваши заявки</b>${ownOrders}</div></div>`;
    container.innerHTML = shell(esc(stock.company_name), `${esc(getSpecializationName(stock.specialization))} · биржевой тикер #${stock.stock_id}`, `<div class="broker-tabs"><button data-tab="overview" class="stock-tab ${view.stockTab === 'overview' ? 'is-active' : ''}">Обзор</button><button data-tab="orderbook" class="stock-tab ${view.stockTab === 'orderbook' ? 'is-active' : ''}">Стакан</button></div><div class="glass-card rounded-2xl p-3">${view.stockTab === 'overview' ? overview : orderbook}</div>`); bindBack(renderStocks);
    container.querySelectorAll('.stock-tab').forEach(btn => btn.addEventListener('click', () => { view.stockTab = btn.dataset.tab; renderStockDetail(id); }));
    container.querySelector('#stock-order-submit')?.addEventListener('click', async () => {
      const side = container.querySelector('#stock-order-side').value;
      const quantity = Number(container.querySelector('#stock-order-qty').value);
      const price = Number(container.querySelector('#stock-order-price').value);
      try { await NatAPI.placeStockOrder(id, side, quantity, price); stockHistoryCache.clear(); await load(); showToast('Заявка отправлена в стакан', 'success'); renderStockDetail(id); } catch (error) { showToast(error.message, 'error'); }
    });
    container.querySelectorAll('.stock-order-cancel').forEach(btn => btn.addEventListener('click', async () => { try { await NatAPI.cancelStockOrder(btn.dataset.id); stockHistoryCache.clear(); await load(); renderStockDetail(id); } catch (error) { showToast(error.message, 'error'); } }));
  }

  function renderBonds() {
    const ownId = Number(store.company?.id || store.company?.company_id || 0);
    const issues = (bonds.bonds || []).map(bond => `<div class="glass-card rounded-xl p-3"><button class="bond-card w-full text-left" data-id="${bond.id}"><div class="flex justify-between"><b>${esc(bond.title)}</b><strong>${money(bond.market_price ?? bond.face_value)}</strong></div><div class="text-xs text-slate-500">Купон ${bond.coupon_rate}% · ${esc(bondStatusLabel(bond.status))}</div></button>${bond.is_active ? `<button class="bond-primary-buy mt-2 w-full py-1.5 rounded-lg bg-blue-600 text-white text-xs font-bold" data-id="${bond.id}">Купить у государства</button>` : ''}</div>`).join('') || '<div class="text-sm text-slate-500">Активных выпусков пока нет</div>';
    const holdings = (bonds.holdings || []).filter(row => Number(row.available_quantity || 0) > 0).map(row => `<div class="flex justify-between p-2 rounded-lg bg-amber-50 dark:bg-amber-950/20 text-xs"><span>${esc(row.title)} · ${row.available_quantity} шт.</span><button class="bond-list text-blue-600 font-bold" data-id="${row.bond_id}" data-max="${row.available_quantity}">Продать</button></div>`).join('') || '<div class="text-xs text-slate-400">Свободных облигаций нет</div>';
    const listings = (bonds.listings || []).filter(row => row.status === 'OPEN').map(row => `<div class="flex justify-between gap-2 p-2 rounded-lg bg-slate-50 dark:bg-slate-800/50 text-xs"><span>Выпуск #${row.bond_id} · ${row.quantity} шт. · ${money(row.total_cost)}</span>${Number(row.seller_company_id) === ownId ? `<button class="bond-list-cancel text-rose-500 font-bold" data-id="${row.listing_id}">Снять</button>` : `<button class="bond-list-buy text-indigo-600 font-bold" data-id="${row.listing_id}">Купить</button>`}</div>`).join('') || '<div class="text-xs text-slate-400">Открытых предложений нет</div>';
    container.innerHTML = shell('Государственные облигации', 'Рыночная цена строится по реальным сделкам вторичного рынка', `<div class="space-y-3">${issues}<details class="glass-card rounded-xl p-3"><summary class="font-black">Ваши облигации</summary><div class="space-y-2 mt-2">${holdings}</div></details><details class="glass-card rounded-xl p-3"><summary class="font-black">Вторичный рынок</summary><div class="space-y-2 mt-2">${listings}</div></details></div>`); bindBack();
    container.querySelectorAll('.bond-card').forEach(btn => btn.addEventListener('click', () => renderBondDetail(Number(btn.dataset.id))));
    container.querySelectorAll('.bond-primary-buy').forEach(btn => btn.addEventListener('click', async () => { const qty = parseInt(prompt('Количество облигаций:', '1'), 10); if (!qty) return; try { await NatAPI.buyStateBonds(btn.dataset.id, qty); await load(); showToast('Облигации куплены', 'success'); renderBonds(); } catch (e) { showToast(e.message, 'error'); } }));
    container.querySelectorAll('.bond-list').forEach(btn => btn.addEventListener('click', async () => { const qty = parseInt(prompt(`Количество (до ${btn.dataset.max}):`, '1'), 10); const price = parseFloat(prompt('Цена за облигацию:', '1000')); if (!qty || !price) return; try { await NatAPI.createBondListing(btn.dataset.id, qty, price); await load(); renderBonds(); } catch (e) { showToast(e.message, 'error'); } }));
    container.querySelectorAll('.bond-list-buy').forEach(btn => btn.addEventListener('click', async () => { try { await NatAPI.buyBondListing(btn.dataset.id); await load(); renderBonds(); } catch (e) { showToast(e.message, 'error'); } }));
    container.querySelectorAll('.bond-list-cancel').forEach(btn => btn.addEventListener('click', async () => { try { await NatAPI.cancelBondListing(btn.dataset.id); await load(); renderBonds(); } catch (e) { showToast(e.message, 'error'); } }));
  }

  function renderBondDetail(id) {
    const bond = (bonds.bonds || []).find(item => Number(item.id) === id); if (!bond) return renderBonds();
    const history = bond.history || [];
    const asks = bookRows(bond.orderbook_asks || [], 'SELL');
    container.innerHTML = shell(esc(bond.title), 'Государственный выпуск · реальная история вторичного рынка', `<div class="glass-card rounded-2xl p-4 space-y-3"><div class="broker-quote"><div><div class="broker-price">${money(bond.market_price ?? bond.face_value)}</div>${changeHtml(history, ' cash')}</div><div class="broker-spread"><span>Номинал ${money(bond.face_value)}</span><span>Купон ${bond.coupon_rate}%</span></div></div>${chartCard(history, `График ${bond.title}`)}<div class="broker-stat-grid"><div><span>До погашения</span><b>${bond.maturity_days || '—'} дн.</b></div><div><span>Лучшее предложение</span><b>${bond.best_ask ? money(bond.best_ask) : '—'}</b></div></div><details class="broker-book-single"><summary>Предложения вторичного рынка</summary>${asks}</details><button class="bond-buy w-full py-2 rounded-xl bg-blue-600 text-white font-bold">Купить у государства</button></div>`); bindBack(renderBonds);
    container.querySelector('.bond-buy')?.addEventListener('click', async () => { const qty = parseInt(prompt('Количество облигаций:', '1'), 10); if (!qty) return; try { await NatAPI.buyStateBonds(id, qty); await load(); showToast('Облигации куплены', 'success'); renderBondDetail(id); } catch (error) { showToast(error.message, 'error'); } });
  }

  function renderReference() {
    const body = `<div class="space-y-2">${(instruments.instruments || []).map(item => `<button class="reference-card glass-card rounded-xl p-3 w-full text-left" data-code="${item.code}"><div class="flex justify-between"><b>${ICONS[item.code] || '💱'} ${esc(NAMES[item.code] || item.code)}</b><strong>${item.reference_rub ? `${Number(item.reference_rub).toFixed(2)} ₽` : '—'}</strong></div><div class="mt-1">${changeHtml(item.history, ' ₽')}</div>${renderMarketChart(item.history, { label: `График ${NAMES[item.code] || item.code}`, height: 92 })}</button>`).join('')}</div>`;
    container.innerHTML = shell('Валюты и металлы', 'Исторические официальные котировки Банка России', body); bindBack();
    container.querySelectorAll('.reference-card').forEach(btn => btn.addEventListener('click', () => renderReferenceDetail(btn.dataset.code)));
  }

  function renderReferenceDetail(code) {
    const item = (instruments.instruments || []).find(row => row.code === code); if (!item) return renderReference();
    const unit = ['GOLD', 'SILVER'].includes(code) ? '₽/г' : '₽';
    container.innerHTML = shell(`${ICONS[code] || '💱'} ${esc(NAMES[code] || code)}`, 'Официальный ориентир ЦБ РФ · сделки игры исполняются со спредом', `<div class="glass-card rounded-2xl p-4 space-y-3"><div class="broker-quote"><div><div class="broker-price">${Number(item.reference_rub || 0).toFixed(2)} ${unit}</div>${changeHtml(item.history, ` ${unit}`)}</div><div class="broker-spread"><span>Купить ${Number(item.buy_rub || 0).toFixed(2)}</span><span>Продать ${Number(item.sell_rub || 0).toFixed(2)}</span></div></div>${chartCard(item.history, `График ${NAMES[code] || code}`)}<div class="grid grid-cols-2 gap-2"><button class="reference-trade py-2 rounded-xl bg-blue-600 text-white font-bold" data-side="buy">Купить</button><button class="reference-trade py-2 rounded-xl bg-emerald-600 text-white font-bold" data-side="sell">Продать</button></div><div class="text-[10px] text-slate-500">Котировки валют и драгоценных металлов сохраняются сервером из официальной истории Банка России. Это не выдуманный график.</div></div>`); bindBack(renderReference);
    container.querySelectorAll('.reference-trade').forEach(btn => btn.addEventListener('click', async () => { const qty = parseFloat(prompt('Количество:', '1')); if (!qty) return; try { await NatAPI.tradeReferenceInstrument(code, btn.dataset.side, qty); await load(); showToast('Сделка исполнена', 'success'); renderReferenceDetail(code); } catch (error) { showToast(error.message, 'error'); } }));
  }

  return { load, renderPortfolio, renderStocks, renderStateShares, renderBonds, renderReference };
}
