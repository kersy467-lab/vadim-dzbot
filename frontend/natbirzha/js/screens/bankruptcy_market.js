import { NatAPI } from '../api.js?v=20260925_deals_v6';
import { store } from '../state.js?v=20260925_deals_v6';

const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[char]));

const money = (value) => `${Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} cash`;

export async function renderBankruptcyMarket(container, showToast, onBack = () => {}) {
  container.innerHTML = '<div class="p-6 text-center text-xs text-slate-400">Загрузка рынка банкротов…</div>';
  try {
    const result = await NatAPI.getBankruptcyMarketLots();
    const lots = result.lots || [];
    const company = store.company || {};
    container.innerHTML = `<div class="market-contrast-surface mx-auto max-w-md space-y-4 p-4 pb-24">
      <button class="bankruptcy-market-back text-xs font-bold text-blue-600">← Все разделы биржи</button>
      <header><h2 class="text-xl font-black">Рынок банкротов</h2><p class="text-xs text-slate-500">Здесь продаются конфискованные заводы, предприятия и акции. Заводы и предприятия можно купить в любой отрасли; к их себестоимости добавлено 30% государству.</p></header>
      <div class="glass-card rounded-xl p-3 text-[10px] text-slate-500">Ваш баланс: <b>${money(company.cash)}</b></div>
      ${lots.length ? lots.map((lot) => `<article class="glass-card rounded-2xl p-3 space-y-2">
        <div class="flex items-start justify-between gap-2"><div class="min-w-0"><h3 class="text-sm font-black">${escapeHtml(lot.title)}</h3><p class="mt-0.5 text-[10px] text-slate-500">Компания: ${escapeHtml(lot.former_company_name)} · ${lot.asset_kind === 'STOCK' ? `${Number(lot.quantity || 0).toLocaleString('ru-RU')} акций` : `Отрасль: ${escapeHtml(lot.industry)} · Уровень ${Number(lot.level || 1)}`}</p></div><span class="shrink-0 rounded-lg bg-amber-50 px-2 py-1 text-[9px] font-bold text-amber-700 dark:bg-amber-950/30 dark:text-amber-200">${lot.asset_kind === 'BUSINESS' ? 'Предприятие' : lot.asset_kind === 'STOCK' ? 'Акции' : 'Завод'}</span></div>
        <div class="grid grid-cols-2 gap-2 text-[10px]"><div><span class="text-slate-500">${lot.asset_kind === 'STOCK' ? 'Себестоимость акций' : 'Себестоимость'}</span><b class="block">${money(lot.cost_basis)}</b></div><div><span class="text-slate-500">Цена покупки</span><b class="block">${money(lot.ask_price)}</b></div></div>
        <div class="text-[9px] text-slate-500">${lot.asset_kind === 'STOCK' ? 'Цена рассчитана по текущей котировке; выручка от продажи поступит государству.' : `В цену включена государственная наценка ${money(lot.state_premium)}.`}</div>
        <button class="bankruptcy-lot-buy w-full rounded-lg bg-gradient-to-r from-pink-500 to-violet-600 px-3 py-2 text-xs font-bold text-white disabled:opacity-50" data-lot-id="${Number(lot.id)}" data-price="${Number(lot.ask_price)}">${lot.asset_kind === 'STOCK' ? `Купить ${Number(lot.quantity || 0).toLocaleString('ru-RU')} акций` : lot.asset_kind === 'FACTORY' ? 'Купить завод' : 'Купить предприятие'}</button>
      </article>`).join('') : '<div class="glass-card rounded-2xl p-5 text-center text-xs text-slate-500">Сейчас конфискованных активов на продаже нет.</div>'}
    </div>`;

    container.querySelector('.bankruptcy-market-back')?.addEventListener('click', onBack);
    container.querySelectorAll('.bankruptcy-lot-buy').forEach((button) => {
      button.addEventListener('click', async () => {
        const price = Number(button.dataset.price || 0);
        if (!confirm(`Купить предприятие за ${money(price)}? Деньги поступят государству.`)) return;
        button.disabled = true;
        try {
          const bought = await NatAPI.buyBankruptcyMarketLot(button.dataset.lotId);
          const updatedCompany = await NatAPI.getMyCompany();
          store.setCompany(updatedCompany);
          showToast(`Куплено: ${escapeHtml(bought.title)}. Государству перечислено ${money(bought.paid)}.`, 'success');
          await renderBankruptcyMarket(container, showToast, onBack);
        } catch (error) {
          showToast(error.message || 'Не удалось купить предприятие.', 'error');
          button.disabled = false;
        }
      });
    });
  } catch (error) {
    container.innerHTML = `<div class="market-contrast-surface mx-auto max-w-md space-y-3 p-4 pb-24"><button class="bankruptcy-market-back text-xs font-bold text-blue-600">← Все разделы биржи</button><div class="glass-card rounded-xl p-4 text-xs text-rose-500">Не удалось загрузить рынок банкротов: ${escapeHtml(error.message)}</div></div>`;
    container.querySelector('.bankruptcy-market-back')?.addEventListener('click', onBack);
  }
}
