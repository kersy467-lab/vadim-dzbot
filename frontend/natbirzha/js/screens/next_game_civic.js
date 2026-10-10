import { NatAPI } from '../api.js?v=20261010_active_production_v1';
import { esc, number } from './next_game_common.js?v=20261010_shell_v2';

const requests = new WeakMap();
const date = (value) => new Date(value).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' });

export async function renderNextGameCivic(container, state, showToast, refresh) {
  const api = state.nextGameAPI || NatAPI;
  const view = state.civicBrowser ||= { orderId: null };
  const token = {}; requests.set(container, token);
  container.innerHTML = '<section class="next-game-panel"><p role="status">Загружаем городские заказы и налоги…</p></section>';
  try {
    const data = await api.getNextGameCivic();
    if (requests.get(container) !== token) return;
    render(data);
  } catch (error) {
    if (requests.get(container) !== token) return;
    container.innerHTML = `<section class="next-game-panel"><h2>Город и налоги</h2><p role="alert">${esc(error.message)}</p><button data-civic-retry class="next-game-primary">Повторить</button></section>`;
    container.querySelector('[data-civic-retry]')?.addEventListener('click', () => renderNextGameCivic(container, state, showToast, refresh));
  }
  function render(data) {
    const order = data.orders.find((row) => row.id === Number(view.orderId));
    container.innerHTML = `<section class="next-game-panel"><button data-civic-bank class="next-game-back">← Банк</button><h2>Город и налоги</h2>
      <p>На счёте ${number(data.cash, 2)} cash. Город закупает товары по 108% базовой цены. Можно выполнить часть заказа.</p>
      <article class="next-game-bank-loan"><h3>Городские закупки</h3><div class="next-game-simple-list">${data.orders.map((row) => `<button data-civic-order="${row.id}" class="next-game-bank-account"><span><b>${esc(row.name)}</b><small>${number(row.unit_price, 2)} cash/${esc(row.unit)} · нужно ${number(row.remaining_quantity, 4)}</small><small>На складе ${number(row.available_quantity, 4)} · до ${esc(date(row.expires_at))}</small></span><span>›</span></button>`).join('') || '<p>Бюджет закупок исчерпан. Новые заказы появятся в 11:00 UTC+5.</p>'}</div>
      ${order ? `<form data-civic-fulfill><h4>Поставка: ${esc(order.name)}</h4><label>Количество<input name="quantity" type="number" min="0.0001" max="${Math.min(order.available_quantity, order.remaining_quantity)}" step="0.0001" value="${Math.min(1, order.available_quantity, order.remaining_quantity)}" required></label><button class="next-game-primary" ${order.available_quantity <= 0 ? 'disabled' : ''}>Продать городу</button></form>` : ''}</article>
      <article class="next-game-bank-loan"><h3>Налог на операционную прибыль — 13%</h3><p>Начисляется ежедневно в 11:00 UTC+5 по продажам, закупкам сырья и расходам производства. Налог оплачивается вручную со счёта компании. Убыток ${number(data.loss_carry, 2)} cash переносится на следующие дни.</p><p>Следующее начисление: ${esc(date(data.next_assessment_at))}</p>
      ${data.taxes.map((row) => `<div class="next-game-bank-account"><span><b>${number(row.amount, 2)} cash · ${row.status === 'FORGIVEN' ? 'Списан' : row.status === 'PAID' ? 'Оплачен' : 'К оплате'}</b><small>До ${esc(date(row.period_end))} · прибыль ${number(row.operating_profit, 2)}</small></span>${row.status === 'DUE' ? `<button data-civic-pay="${row.id}" class="next-game-secondary">Оплатить</button>` : ''}</div>`).join('') || '<p>Начислений пока нет.</p>'}</article>
      <article class="next-game-bank-loan"><h3>Экономические события</h3>${data.events.map((row) => `<p>${esc((state.corporations || []).find((sector) => sector.id === row.sector_id)?.name || row.sector_id)}: выпуск +25% до ${esc(date(row.ends_at))}</p>`).join('') || '<p>Сейчас активных событий нет.</p>'}<p>Событие повышает только выпуск продукции на срок до 24 часов.</p>
      ${data.can_create_event ? `<details><summary>Создать событие</summary><form data-civic-event><label>Отрасль<select name="sector_id">${(state.corporations || []).map((sector) => `<option value="${esc(sector.id)}">${esc(sector.name)}</option>`).join('')}</select></label><label>Длительность, часы<input name="duration_hours" type="number" min="1" max="24" step="1" value="6" required></label><button class="next-game-primary">Начать событие</button></form></details>` : ''}</article>
    </section>`;
    container.querySelector('[data-civic-bank]')?.addEventListener('click', () => state.navigateNextGame?.('bank'));
    container.querySelectorAll('[data-civic-order]').forEach((button) => button.addEventListener('click', () => { view.orderId = Number(button.dataset.civicOrder); render(data); }));
    let busy = false;
    async function mutate(action) {
      if (busy) return; busy = true;
      const disabled = [...container.querySelectorAll('button,input')].map((el) => [el, el.disabled]);
      disabled.forEach(([el]) => { el.disabled = true; });
      try { await action(); showToast('Операция выполнена', 'success'); if (refresh) await refresh(); else await renderNextGameCivic(container, state, showToast); }
      catch (error) { showToast(error.message || 'Не удалось выполнить операцию', 'error'); }
      finally { busy = false; disabled.forEach(([el, previous]) => { el.disabled = previous; }); }
    }
    container.querySelectorAll('[data-civic-pay]').forEach((button) => button.addEventListener('click', () => void mutate(() => api.payNextGameTax(Number(button.dataset.civicPay)))));
    container.querySelector('[data-civic-fulfill]')?.addEventListener('submit', (event) => {
      event.preventDefault(); const values = new FormData(event.currentTarget);
      void mutate(() => api.fulfillNextGameCityOrder(order.id, Number(values.get('quantity'))));
    });
    container.querySelector('[data-civic-event]')?.addEventListener('submit', (event) => {
      event.preventDefault(); const values = new FormData(event.currentTarget);
      void mutate(() => api.createNextGameEconomicEvent(String(values.get('sector_id')), Number(values.get('duration_hours'))));
    });
  }
}
