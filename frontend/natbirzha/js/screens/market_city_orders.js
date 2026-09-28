import { NatAPI } from '../api.js?v=20260928_market_frontend_perf_v1';
import { registerScreenCleanup } from '../screen_lifecycle.js?v=20260928_mobile_perf_v1';
import { store } from '../state.js?v=20260926_local_update_v1';

const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[char]));
const numberFormat = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 6 });

function deliveryKey(companyId, orderId, quantity) {
  const key = `nat-city-order:${companyId}:${orderId}:${quantity}`;
  try {
    let value = localStorage.getItem(key);
    if (!value) {
      value = globalThis.crypto?.randomUUID?.() || `city-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      localStorage.setItem(key, value);
    }
    return { value, clear: () => localStorage.removeItem(key) };
  } catch (_) {
    return {
      value: globalThis.crypto?.randomUUID?.() || `city-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      clear: () => {},
    };
  }
}

export async function renderMarketCityOrders(container, showToast, onBack) {
  let active = true;
  let busy = false;
  let refreshTimer = null;
  let releaseScreenCleanup = null;
  const stopRefresh = () => {
    active = false;
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = null;
    releaseScreenCleanup?.();
    releaseScreenCleanup = null;
  };
  const leave = () => {
    if (!active) return;
    stopRefresh();
    onBack();
  };
  releaseScreenCleanup = registerScreenCleanup(stopRefresh);
  const renderLoading = () => {
    container.innerHTML = '<div class="max-w-md mx-auto p-4"><button class="city-orders-back text-sm font-bold text-pink-500">← Биржа</button><p class="mt-5 text-sm text-slate-500">Загружаем городские заказы…</p></div>';
    container.querySelector('.city-orders-back')?.addEventListener('click', leave);
  };

  async function load() {
    if (!active) return;
    renderLoading();
    try {
      const [ordersData, inventoryData] = await Promise.all([
        NatAPI.getCityOrders(), NatAPI.getInventory(),
      ]);
      if (!active) return;
      const inventory = new Map((inventoryData.inventory || []).map((row) => [
        row.item_id, Math.max(0, Number(row.available) || 0),
      ]));
      const inventoryTotal = {};
      const inventoryReserved = {};
      for (const row of inventoryData.inventory || []) {
        inventoryTotal[row.item_id] = Math.max(0, Number(row.quantity) || 0);
        inventoryReserved[row.item_id] = Math.max(0, Number(row.reserved) || 0);
      }
      store.updateCompany({
        inventory: inventoryTotal,
        inventory_available: Object.fromEntries(inventory),
        inventory_total: inventoryTotal,
        inventory_reserved: inventoryReserved,
      });
      const orders = ordersData.orders || [];
      container.innerHTML = `
        <div class="max-w-md mx-auto p-4 pb-24 space-y-4">
          <button class="city-orders-back text-sm font-bold text-pink-500">← Биржа</button>
          <header><h2 class="text-xl font-black">🏙️ Заказы города</h2>
            <p class="text-xs text-slate-500 mt-1">Новые задания каждые 30 минут. На поставку даётся один час.</p></header>
          ${orders.length ? orders.map((order) => {
            const available = inventory.get(order.item_id) || 0;
            const max = Math.min(available, Number(order.remaining_quantity) || 0);
            return `<article class="glass-card rounded-2xl p-4 space-y-3" data-order-id="${Number(order.id)}">
              <div class="flex justify-between gap-3"><div><div class="text-xs uppercase tracking-wide text-slate-500">${escapeHtml(order.industry_name || order.industry)}</div>
                <h3 class="font-black">${escapeHtml(order.item_name)} <span class="text-xs font-normal">${escapeHtml(order.unit)}</span></h3></div>
                <span class="text-right text-[10px] text-slate-500">до<br>${escapeHtml(new Date(order.expires_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }))}</span></div>
              <div class="grid grid-cols-2 gap-2 text-xs"><div>Остаток: <b>${numberFormat.format(order.remaining_quantity)}</b></div>
                <div>Цена: <b>${numberFormat.format(order.unit_price)} cash/${escapeHtml(order.unit)}</b></div>
                <div>Доступно у вас: <b>${numberFormat.format(available)}</b></div>
                <div>Резерв казны: <b>${numberFormat.format(order.reserved_cash)} cash</b></div></div>
              <form class="city-delivery-form flex gap-2">
                <input class="city-delivery-qty min-w-0 flex-1 rounded-xl border px-3 py-2 bg-transparent" type="number" min="0.000001" step="0.000001" max="${max}" value="${max > 0 ? max : ''}" placeholder="Количество" ${max <= 0 ? 'disabled' : ''}>
                <button class="rounded-xl bg-emerald-600 text-white px-4 py-2 font-bold disabled:opacity-40" type="submit" ${max <= 0 ? 'disabled' : ''}>Поставить</button>
              </form>
            </article>`;
          }).join('') : '<div class="glass-card rounded-2xl p-5 text-sm text-slate-500">Активных заказов пока нет. Новые появляются в начале каждого получаса.</div>'}
        </div>`;
      container.querySelector('.city-orders-back')?.addEventListener('click', leave);
      container.querySelectorAll('.city-delivery-form').forEach((form) => {
        form.addEventListener('submit', async (event) => {
          event.preventDefault();
          const card = form.closest('[data-order-id]');
          const orderId = Number(card?.dataset.orderId);
          const input = form.querySelector('.city-delivery-qty');
          const quantity = Number(input?.value);
          const max = Number(input?.max);
          if (!orderId || !Number.isFinite(quantity) || quantity <= 0 || quantity > max) {
            showToast('Количество должно укладываться в доступный остаток.', 'error');
            return;
          }
          const operation = deliveryKey(store.company?.id || store.company?.company_id, orderId, quantity);
          const button = form.querySelector('button[type="submit"]');
          busy = true;
          button.disabled = true;
          try {
            const result = await NatAPI.deliverCityOrder(orderId, quantity, operation.value);
            operation.clear();
            busy = false;
            if (result.success) {
              if (result.company_cash != null) store.updateCompany({ cash: result.company_cash });
              showToast(`Поставка принята · +${numberFormat.format(result.cash_amount)} cash`, 'success');
            } else {
              showToast('Заказ истёк и закрыт.', 'info');
            }
            await load();
          } catch (error) {
            busy = false;
            showToast(error.message || 'Не удалось выполнить поставку.', 'error');
            if (button.isConnected) button.disabled = false;
          }
        });
      });
    } catch (error) {
      if (!active) return;
      container.innerHTML = `<div class="max-w-md mx-auto p-4 space-y-3"><button class="city-orders-back text-sm font-bold text-pink-500">← Биржа</button><div class="glass-card rounded-2xl p-4 text-sm text-rose-600">${escapeHtml(error.message || 'Не удалось загрузить заказы.')}</div></div>`;
      container.querySelector('.city-orders-back')?.addEventListener('click', leave);
    }
  }

  await load();
  if (active) {
    refreshTimer = setInterval(() => {
      if (!container.isConnected) {
        stopRefresh();
        return;
      }
      if (!document.hidden && !busy && !container.querySelector('.city-delivery-qty:focus')) void load();
    }, 30_000);
  }
}

export default renderMarketCityOrders;
