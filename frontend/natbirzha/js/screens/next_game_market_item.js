import { renderMarketChart } from '../market_chart.js?v=20260926_local_update_v1';
import { getItemInfo } from '../items.js?v=20261009_item_art_v1';

export const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[char]));
export const number = (value, digits = 2) => Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: digits });

export function bookRows(rows, unit, side) {
  return rows.length ? rows.slice(0, 10).map((row) => `<div class="depth-${side} flex justify-between rounded px-2 py-1 font-mono text-xs">
    <b>${number(row.limit_price, 4)}</b><span>${number(row.remaining_quantity, 4)} ${esc(unit)}</span>
  </div>`).join('') : '<p class="text-xs text-slate-500">Нет заявок</p>';
}

export function renderNextMarketItem(container, data, options) {
  const { api, onBack, reload, showToast, refresh } = options;
  const { item, npc } = data;
  const meta = getItemInfo(item.id);
  const icon = window.NatIcons?.icon?.(meta.icon, 28) || '';
  const history = data.history || [];
  const ownOrders = data.user_orders || [];
  const active = ownOrders.filter((row) => row.status === 'OPEN');
  const closed = ownOrders.filter((row) => row.status !== 'OPEN');
  const reference = data.reference_price == null ? 'Пока нет сделок' : `${number(data.reference_price, 4)} cash`;
  const advance = data.advance_reference_price;
  container.innerHTML = `<div class="next-market market-contrast-surface space-y-4 max-w-md mx-auto p-4 pb-24">
    <button type="button" class="market-back text-xs font-bold text-pink-500">← Список сырья</button>
    <div class="flex items-center gap-3">${icon}<div><h2 class="text-xl font-black">${esc(item.name)}</h2>
      <p class="text-xs text-slate-500">Склад: ${number(data.inventory_quantity, 4)} ${esc(item.unit)} · ${number(data.cash)} cash</p></div></div>
    <section class="glass-card rounded-2xl p-4 space-y-3 border-l-4 border-l-amber-500">
      <h3 class="text-xs font-bold uppercase text-amber-600">Резервный фонд NPC</h3>
      <div class="grid grid-cols-2 gap-2"><div class="next-market-quote next-market-quote-sell"><span>Скупка Госрезервом</span><b>${number(npc.sell_price)} cash</b></div>
        <div class="next-market-quote next-market-quote-buy"><span>Продажа Госрезерва</span><b>${number(npc.buy_price)} cash</b></div></div>
      <p class="text-[10px] text-slate-500">Резерв: ${number(npc.treasury_quantity, 4)} ${esc(item.unit)} · свободные средства ${number(npc.treasury_cash)} cash</p>
      <div class="next-market-advance text-xs"><b>Аванс от казны: ${advance == null ? 'пока недоступен' : `цена продажи до ${number(advance, 4)} cash / ${esc(item.unit)}`}</b>
        <p>${advance == null ? 'Для расчёта нужны оплаченные сделки других компаний.' : 'На оставшийся товар в ордере — до 30 000 cash при наличии средств казны. Общий непогашенный аванс компании ограничен 30 000 cash.'}</p>
        <details><summary>Как определяется цена</summary><p>Минимум 3 сделки за 24 часа между 2 парами других компаний, суммарный оборот от 1 000 cash. Цена не выше последней сделки, медианы и скупки NPC. Пока аванс не погашен продажами, ордер нельзя снять.</p></details></div>
      <p class="text-xs">Покупка у NPC без дневного ограничения.${data.npc?.buyback_remaining_cash != null ? ` Выкуп этого товара: осталось ${number(data.npc.buyback_remaining_cash, 2)} cash до 11:00 UTC+5.` : ' Выкуп без дневного лимита, в пределах свободных денег банка.'}</p>
      <form data-npc-form class="space-y-2"><label class="text-xs block">Количество (${esc(item.unit)})
        <input name="quantity" type="number" min="0.0001" max="10000" step="0.0001" value="10" required class="next-market-input" /></label>
        <div class="grid grid-cols-2 gap-2"><button name="side" value="SELL" class="next-market-action next-market-sell">Сдать NPC</button>
          <button name="side" value="BUY" class="next-market-action next-market-buy">Купить у NPC</button></div></form>
    </section>
    <section class="glass-card rounded-2xl p-4 space-y-3"><div class="flex justify-between"><h3 class="text-xs font-bold uppercase text-slate-500">Биржевой стакан</h3>
      <button type="button" data-book-refresh class="text-xs text-pink-500">Обновить</button></div>
      ${renderMarketChart(history, { label: `Сделки: ${item.name}`, height: 140 })}
      <p class="text-[10px] text-slate-500">Последняя сделка между компаниями: ${reference}</p>
      <div class="grid grid-cols-2 gap-3"><div><h4 class="text-xs font-bold text-rose-500 mb-2">Продажа (Asks)</h4>${bookRows(data.asks || [], item.unit, 'ask')}</div>
        <div><h4 class="text-xs font-bold text-emerald-500 mb-2">Покупка (Bids)</h4>${bookRows(data.bids || [], item.unit, 'bid')}</div></div>
    </section>
    <section class="glass-card rounded-2xl p-4 space-y-3"><h3 class="text-xs font-bold uppercase text-slate-500">Выставить биржевой ордер</h3>
      <form data-limit-form class="space-y-3"><div class="grid grid-cols-2 gap-2"><label class="next-market-side"><input type="radio" name="side" value="BUY" checked /> Покупка</label>
        <label class="next-market-side"><input type="radio" name="side" value="SELL" /> Продажа</label></div>
        <div class="grid grid-cols-2 gap-2"><label class="text-xs">Количество (${esc(item.unit)})<input name="quantity" type="number" min="0.0001" max="10000" step="0.0001" value="10" required class="next-market-input" /></label>
          <label class="text-xs">Цена (cash)<input name="price" type="number" min="0.0001" step="0.0001" value="${Number(data.reference_price || item.base_price)}" required class="next-market-input" /></label></div>
        <p class="text-[10px] text-slate-500">При покупке резервируется cash, при продаже — товар. Исполнение по цене встречной заявки.</p>
        <button class="next-market-action next-market-buy w-full">Разместить ордер в стакан</button></form>
    </section>
    <section class="glass-card rounded-2xl p-4 space-y-2"><h3 class="text-xs font-bold uppercase text-slate-500">Ваши активные ордера</h3>
      ${active.length ? active.map((row) => `<div class="next-market-own-order"><span><b class="${row.side === 'BUY' ? 'text-emerald-500' : 'text-rose-500'}">${row.side === 'BUY' ? 'ПОКУПКА' : 'ПРОДАЖА'}</b><br>${number(row.remaining_quantity, 4)} @ ${number(row.limit_price, 4)} cash</span>
        ${row.advance_locked ? `<span class="text-amber-600 text-[10px]">🔒 Аванс ${number(row.advance_paid)} cash<br>Осталось погасить ${number(row.outstanding_amount)} cash</span>` : `<button type="button" data-cancel-order="${Number(row.id)}" class="text-rose-500 text-xs font-bold">Отменить</button>`}</div>`).join('') : '<p class="text-xs text-slate-500">Активных ордеров пока нет.</p>'}
      ${closed.length ? `<details><summary class="text-xs cursor-pointer">История моих ордеров (${closed.length})</summary>${closed.slice(0, 20).map((row) => `<p class="text-xs py-1">${row.side === 'BUY' ? 'Покупка' : 'Продажа'} ${number(row.quantity, 4)} @ ${number(row.limit_price, 4)} · ${row.status === 'FILLED' ? 'Исполнен' : 'Отменён'}</p>`).join('')}</details>` : ''}
    </section>
    <section class="glass-card rounded-2xl p-4 space-y-2"><h3 class="text-xs font-bold uppercase text-slate-500">Последние сделки</h3>
      ${history.length ? history.slice(-20).reverse().map((row) => `<div class="flex justify-between text-xs"><span>${esc(new Date(row.timestamp).toLocaleString('ru-RU'))}</span><b>${number(row.quantity, 4)} @ ${number(row.price, 4)}</b></div>`).join('') : '<p class="text-xs text-slate-500">Сделок между компаниями пока нет.</p>'}
    </section>
  </div>`;
  container.querySelector('.market-back')?.addEventListener('click', onBack);
  container.querySelector('[data-book-refresh]')?.addEventListener('click', reload);
  async function mutate(button, action) {
    const surface = container.querySelector('.next-market');
    if (!surface || surface.dataset.busy === '1') return;
    surface.dataset.busy = '1';
    surface.querySelectorAll('button, input').forEach((element) => { element.disabled = true; });
    try {
      await action();
      showToast('Операция выполнена', 'success');
      await refresh?.();
      if (surface.isConnected) await reload();
    } catch (error) {
      showToast(error.message || 'Не удалось выполнить операцию', 'error');
    } finally {
      surface.dataset.busy = '0';
      surface.querySelectorAll('button, input').forEach((element) => { element.disabled = false; });
    }
  }
  container.querySelector('[data-npc-form]')?.addEventListener('submit', (event) => {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    const side = event.submitter?.value;
    if (!['BUY', 'SELL'].includes(side)) return;
    void mutate(event.submitter, () => api.tradeNextGameMarket(item.id, side, Number(values.get('quantity'))));
  });
  container.querySelector('[data-limit-form]')?.addEventListener('submit', (event) => {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    void mutate(event.submitter, () => api.createNextGameLimitOrder(item.id, values.get('side'), Number(values.get('quantity')), Number(values.get('price'))));
  });
  container.querySelectorAll('[data-cancel-order]').forEach((button) => {
    button.addEventListener('click', () => void mutate(button, () => api.cancelNextGameOrder(Number(button.dataset.cancelOrder))));
  });
}
