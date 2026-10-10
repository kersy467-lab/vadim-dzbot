import { NatAPI } from '../api.js?v=20261010_active_production_v1';

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));
}

function number(value, digits = 2) {
  return Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: digits });
}

function quote(value) {
  return value == null ? '—' : number(value, 4);
}

function renderIssue(issue, company) {
  const orders = (issue.open_orders || []).slice(0, 6).map((order) =>
    `<li><span>${order.side === 'BUY' ? 'Покупка' : 'Продажа'} · ${esc(order.company_name)}</span><b>${number(order.remaining_shares, 0)} шт. × ${number(order.limit_price, 4)}</b></li>`
  ).join('');
  const price = issue.best_ask || issue.last_price || issue.initial_price;
  const canBuy = Number(issue.company_id) !== Number(company.id);
  const status = issue.status === 'OPEN' ? 'Торги открыты' : esc(issue.status);
  return `<article class="next-game-capital-issue"><header><div><h3>${esc(issue.company_name)}</h3><p>IPO ${number(issue.float_shares, 0)} из ${number(issue.total_shares, 0)} акций · ${status}</p></div><b>${number(issue.last_price, 4)} cash</b></header><div class="next-game-capital-quotes"><span>Покупка: ${quote(issue.best_bid)}</span><span>Продажа: ${quote(issue.best_ask)}</span></div><details class="next-game-disclosure" name="equity-issuer"><summary>Выбрать · ${esc(issue.company_name)}</summary><div class="next-game-bank-loan"><label>Количество акций</label><input data-equity-shares type="number" min="1" max="1000000" step="1" value="100"><label>Лимитная цена за акцию</label><input data-equity-price type="number" min="0.01" step="0.01" value="${Number(price || 0).toFixed(4)}"><div class="next-game-capital-actions"><button type="button" data-equity-side="BUY" data-equity-issue="${issue.id}" ${canBuy ? '' : 'disabled'}>Купить</button><button type="button" data-equity-side="SELL" data-equity-issue="${issue.id}">Продать</button></div><ul>${orders || '<li>Заявок пока нет</li>'}</ul></div></details></article>`;
}

export function renderCapital(state) {
  const equity = state.equity || {};
  const issues = (equity.issues || []).map((issue) => renderIssue(issue, state.company)).join('');
  const positions = (equity.positions || []).map((position) =>
    `<li><span>${esc(position.issuer_name)} · ${number(position.shares, 0)} акций</span><b>${number(position.market_value)} cash</b><small>Цена ${number(position.last_price, 4)} · средняя ${number(position.average_price, 4)} · дивиденды ${number(position.dividends_received)} cash</small></li>`
  ).join('');
  const ownOrders = (equity.my_orders || []).map((order) =>
    `<li><span>${order.side === 'BUY' ? 'Покупка' : 'Продажа'} · ${esc(order.company_name)} · ${number(order.remaining_shares, 0)} акций × ${number(order.limit_price, 4)}</span><button type="button" data-equity-cancel="${order.id}">Снять</button></li>`
  ).join('');
  const history = [
    ...(equity.trades || []).map((trade) => ({
      date: trade.executed_at,
      label: `${esc(trade.buyer_company_name)} купила у ${esc(trade.seller_company_name)}`,
      value: `${number(trade.shares, 0)} × ${number(trade.price, 4)}`,
    })),
    ...(equity.dividends || []).map((dividend) => ({
      date: dividend.created_at,
      label: `${esc(dividend.issuer_name)} выплатила дивиденды`,
      value: `${number(dividend.total_paid)} cash · ${number(dividend.per_share, 4)} / акцию`,
    })),
  ].sort((left, right) => String(right.date || '').localeCompare(String(left.date || ''))).slice(0, 12);
  const activity = history.map((row) => `<li><span>${row.label}</span><b>${row.value}</b></li>`).join('');
  const ownIssue = equity.own_issue;
  const ipoAction = equity.eligible_to_ipo
    ? '<button type="button" data-equity-ipo class="next-game-primary">Открыть IPO · выставить 10% акций</button>'
    : ownIssue
      ? `<article class="next-game-capital-own"><b>IPO компании открыто</b><span>${number(ownIssue.last_price, 4)} cash за акцию · старт ${number(ownIssue.initial_price, 4)}</span><details class="next-game-disclosure"><summary>Открыть выплату дивидендов</summary><div class="next-game-bank-loan"><label>Дивиденд на одну акцию</label><input data-equity-dividend type="number" min="0.01" step="0.01" value="0.10"><button type="button" data-equity-dividend-pay>Выплатить дивиденды</button></div></details></article>`
      : `<p class="next-game-capital-hint">IPO откроется с уровня ${number(equity.ipo_minimum_level, 0)} после постройки первого завода.</p>`;
  return `<section class="next-game-panel next-game-capital"><div><h2>Капитал и IPO</h2><p>Акции компаний торгуются между игроками. Один владелец не может купить собственные акции; цена реальной сделки ограничена движением ±15% от предыдущей.</p></div><div class="next-game-capital-opening">${ipoAction}</div><div class="next-game-capital-positions"><h3>Портфель</h3><ul>${positions || '<li>Акций пока нет</li>'}</ul></div><div class="next-game-capital-market"><h3>Рынок акций</h3>${issues || '<p>Пока нет открытых IPO. Первая компания может разместить акции с 5-го уровня.</p>'}</div><div class="next-game-capital-positions"><h3>Мои заявки</h3><ul>${ownOrders || '<li>Открытых заявок нет</li>'}</ul></div><div class="next-game-capital-positions"><h3>Последние сделки и дивиденды</h3><ul>${activity || '<li>Истории пока нет</li>'}</ul></div></section>`;
}

export function bindCapitalActions(container, state, showToast, refresh) {
  container.querySelector('[data-equity-ipo]')?.addEventListener('click', async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    try {
      await NatAPI.openNextGameIPO();
      showToast('IPO открыто. Первичные акции выставлены в стакан.', 'success');
      await refresh();
    } catch (error) { showToast(error.message, 'error'); button.disabled = false; }
  });
  container.querySelectorAll('[data-equity-side]').forEach((button) => button.addEventListener('click', async () => {
    const card = button.closest('.next-game-capital-issue');
    const shares = Number(card?.querySelector('[data-equity-shares]')?.value);
    const price = Number(card?.querySelector('[data-equity-price]')?.value);
    if (!Number.isInteger(shares) || shares < 1 || !Number.isFinite(price) || price <= 0) {
      return showToast('Укажи целое число акций и положительную лимитную цену', 'error');
    }
    button.disabled = true;
    try {
      const result = await NatAPI.createNextGameShareOrder(
        Number(button.dataset.equityIssue), button.dataset.equitySide, shares, price,
      );
      showToast(result.executed_shares
        ? `Сделка исполнена: ${number(result.executed_shares, 0)} акций`
        : 'Заявка выставлена в стакан', 'success');
      await refresh();
    } catch (error) { showToast(error.message, 'error'); button.disabled = false; }
  }));
  container.querySelectorAll('[data-equity-cancel]').forEach((button) => button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      await NatAPI.cancelNextGameShareOrder(button.dataset.equityCancel);
      showToast('Заявка снята, резерв возвращён компании', 'success');
      await refresh();
    } catch (error) { showToast(error.message, 'error'); button.disabled = false; }
  }));
  container.querySelector('[data-equity-dividend-pay]')?.addEventListener('click', async (event) => {
    const button = event.currentTarget;
    const perShare = Number(container.querySelector('[data-equity-dividend]')?.value);
    if (!Number.isFinite(perShare) || perShare < 0.01) return showToast('Минимальный дивиденд — 0,01 cash на акцию', 'error');
    button.disabled = true;
    try {
      const result = await NatAPI.distributeNextGameDividend(perShare);
      showToast(`Выплачено ${number(result.total_paid)} cash акционерам`, 'success');
      await refresh();
    } catch (error) { showToast(error.message, 'error'); button.disabled = false; }
  });
}
