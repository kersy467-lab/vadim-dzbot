export function renderCommodityOrderbookView(options) {
  const { container, selectedItemId, marketItems, orderbookData, store, showToast, NatAPI, renderMarketChart, loadOrderbook, refreshNpcRates, renderCommodityBrowser, rerender } = options;
  function renderView() {
    const itemInfo = marketItems.find(i => i.id === selectedItemId) || marketItems[0];
    const bids = orderbookData?.bids || [];
    const asks = orderbookData?.asks || [];
    const tradeHistory = orderbookData?.history || [];
    const userOrders = orderbookData?.user_orders || [];
    const userInvQty = store.inventory[selectedItemId] || 0;
    const formatQuote = (value) => {
      const price = Number(value);
      return Number.isFinite(price) && price > 0 ? price.toFixed(2) : '—';
    };
    const hasNpcQuote = Number.isFinite(Number(itemInfo.buy)) && Number(itemInfo.buy) > 0
      && Number.isFinite(Number(itemInfo.sell)) && Number(itemInfo.sell) > 0;
  
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
            <span class="text-[10px] font-mono text-slate-400">База: ${formatQuote(itemInfo.base)} cash</span>
          </div>
          <div class="grid grid-cols-2 gap-2 text-xs">
            <div class="p-2 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800">
              <div class="text-[10px] font-semibold text-emerald-700 dark:text-emerald-300">Скупка NPC (Пол -20%)</div>
              <div class="font-mono font-black text-sm text-emerald-600 dark:text-emerald-400">${formatQuote(itemInfo.buy)} cash</div>
              <button class="npc-sell-btn mt-1 w-full py-1 rounded bg-emerald-600 text-white font-bold text-[11px] active:scale-95 transition-all disabled:opacity-50" ${hasNpcQuote ? '' : 'disabled'}>
                Сдать NPC
              </button>
            </div>
            <div class="p-2 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800">
              <div class="text-[10px] font-semibold text-rose-700 dark:text-rose-300">Продажа NPC (Потолок +50%)</div>
              <div class="font-mono font-black text-sm text-rose-600 dark:text-rose-400">${formatQuote(itemInfo.sell)} cash</div>
              <button class="npc-buy-btn mt-1 w-full py-1 rounded bg-rose-600 text-white font-bold text-[11px] active:scale-95 transition-all disabled:opacity-50" ${hasNpcQuote ? '' : 'disabled'}>
                Купить у NPC
              </button>
            </div>
          </div>
          <div class="rounded-lg bg-emerald-50/70 px-2.5 py-2 text-[10px] text-emerald-800 dark:bg-emerald-950/20 dark:text-emerald-200">
            ${hasNpcQuote ? `Скупка этого товара Госрезервом: ${Number.isFinite(itemInfo.playerSellRemainingCash) ? `${itemInfo.playerSellRemainingCash.toLocaleString('ru-RU', { maximumFractionDigits: 0 })} cash (${Number(itemInfo.playerSellRemainingQuantity || 0).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ${itemInfo.unit})` : 'без ограничений'}.` : 'Котировка недоступна. Обновите раздел и повторите попытку.'}
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
                <input type="number" id="order-price" min="0.1" step="0.1" value="${hasNpcQuote ? formatQuote(itemInfo.base) : ''}" required class="w-full px-3 py-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-xs font-mono text-slate-900 dark:text-white" />
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
      const qtyStr = prompt(`Сколько единиц ${itemInfo.name} сдать NPC по цене ${formatQuote(itemInfo.buy)} cash?`, '10');
      const qty = parseFloat(qtyStr);
      if (!qty || qty <= 0) return;
      try {
        const res = await NatAPI.npcTrade({ item_id: selectedItemId, operation: 'sell', quantity: qty });
        showToast(res.message || 'Сделка с NPC завершена!', 'success');
        const refreshed = await NatAPI.getMyCompany();
        store.setCompany(refreshed);
        await Promise.all([loadOrderbook(), refreshNpcRates()]);
        rerender();
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  
    container.querySelector('.npc-buy-btn')?.addEventListener('click', async () => {
      const qtyStr = prompt(`Сколько единиц ${itemInfo.name} купить у NPC по цене ${formatQuote(itemInfo.sell)} cash?`, '10');
      const qty = parseFloat(qtyStr);
      if (!qty || qty <= 0) return;
      try {
        const res = await NatAPI.npcTrade({ item_id: selectedItemId, operation: 'buy', quantity: qty });
        showToast(res.message || 'Сделка с NPC завершена!', 'success');
        const refreshed = await NatAPI.getMyCompany();
        store.setCompany(refreshed);
        await Promise.all([loadOrderbook(), refreshNpcRates()]);
        rerender();
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
        rerender();
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
          rerender();
        } catch (err) {
          showToast(err.message, 'error');
        }
      });
    });
  }
  renderView();
}
