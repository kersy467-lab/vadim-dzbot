import { NatAPI } from '../api.js';
import { store } from '../state.js';

const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[char]));

const money = (value) => `${Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} cash`;

export async function renderStateShareMarket(container, showToast, onBack = () => {}) {
  container.innerHTML = '<div class="p-6 text-center text-xs text-slate-400">Загрузка государственных акций…</div>';
  try {
    const [shareResult, portfolio] = await Promise.all([
      NatAPI.getStateShares(),
      NatAPI.getPortfolio(),
    ]);
    const offers = shareResult.shares || [];
    const holdings = portfolio.state_shares || [];
    const payments = portfolio.state_share_dividend_payments || [];
    render();

    function render() {
      const offerCards = offers.filter(share => share.is_active).map(share => {
        const annualDistribution = Number(share.projected_annual_profit || 0) * Number(share.dividend_rate_pct || 0) / 100;
        const available = Number(share.remaining_volume || 0);
        return `<article class="glass-card rounded-2xl p-3 space-y-2">
          <div class="flex items-start justify-between gap-2"><div class="min-w-0"><h3 class="truncate text-sm font-black">${escapeHtml(share.title)}</h3><p class="mt-0.5 text-[10px] text-slate-500">${escapeHtml(share.purpose || 'Государственный выпуск')}</p></div><span class="shrink-0 rounded-lg bg-emerald-50 px-2 py-1 text-[9px] font-bold text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300">Государство</span></div>
          <div class="grid grid-cols-2 gap-2 text-[10px]"><div><span class="text-slate-500">Фиксированная цена</span><b class="block">${money(share.issue_price)}</b></div><div><span class="text-slate-500">Доступно</span><b class="block">${available.toLocaleString('ru-RU')} / ${Number(share.total_volume || 0).toLocaleString('ru-RU')}</b></div><div><span class="text-slate-500">Прогноз прибыли за год</span><b class="block">${money(share.projected_annual_profit)}</b></div><div><span class="text-slate-500">Дивиденды от прогноза</span><b class="block">${Number(share.dividend_rate_pct || 0).toLocaleString('ru-RU')}%</b></div></div>
          <div class="rounded-lg bg-slate-100 p-2 text-[9px] text-slate-500 dark:bg-slate-900">Расчётный годовой дивиденд всего выпуска: ${money(annualDistribution)}. Выплата зависит от свободных средств казны и может быть пропорционально уменьшена.</div>
          <div class="flex items-center justify-between gap-2"><span class="text-[10px] text-slate-500">У вас: ${Number(share.shares_held || 0).toLocaleString('ru-RU')} акций</span><button class="state-share-buy rounded-lg bg-emerald-600 px-3 py-1.5 text-[10px] font-bold text-white disabled:opacity-40" data-id="${Number(share.id)}" data-max="${available}" ${available <= 0 ? 'disabled' : ''}>Купить</button></div>
        </article>`;
      }).join('') || '<div class="glass-card rounded-2xl p-5 text-center text-xs text-slate-500">Активных выпусков пока нет.</div>';

      const holdingCards = holdings.map(row => `<div class="flex items-center justify-between gap-2 rounded-xl bg-slate-100 p-2.5 text-[10px] dark:bg-slate-900"><div class="min-w-0"><b class="block truncate">${escapeHtml(row.title)}</b><span>${Number(row.shares_count).toLocaleString('ru-RU')} акций · ${money(row.market_value)}</span><span class="block text-slate-500">Дивиденды получены: ${money(row.dividends_earned)}</span></div><button class="state-share-sell shrink-0 rounded-lg bg-amber-600 px-2.5 py-1.5 font-bold text-white" data-id="${Number(row.share_id)}" data-max="${Number(row.shares_count)}">Продать казне</button></div>`).join('') || '<div class="text-xs text-slate-500">Государственных акций в портфеле пока нет.</div>';
      const paymentRows = payments.slice(0, 10).map(row => `<div class="flex justify-between gap-2 text-[10px]"><span class="truncate">${escapeHtml(row.title)} · ${escapeHtml(row.settlement_date)}</span><b class="shrink-0 text-emerald-600">+${money(row.payout_cash)}</b></div>`).join('') || '<div class="text-[10px] text-slate-500">Выплат пока нет.</div>';

      container.innerHTML = `<div class="market-contrast-surface mx-auto max-w-md space-y-4 p-4 pb-24">
        <button class="state-share-back text-xs font-bold text-blue-600">← Вернуться на биржу</button>
        <header><h2 class="text-xl font-black">Государственные акции</h2><p class="text-xs text-slate-500">Акции выпускаются вручную в панели государства. Покупка переводит ваши деньги в казну.</p></header>
        <div class="glass-card rounded-2xl p-3 text-[10px] text-amber-800 dark:bg-amber-950/20 dark:text-amber-200">Обратный выкуп идёт по той же фиксированной цене и доступен только пока в казне достаточно средств. Дивиденды выплачиваются из казны, а не создают деньги.</div>
        <div class="glass-card rounded-2xl p-3 text-xs"><div class="flex justify-between"><span>Баланс компании</span><b>${money(portfolio.cash)}</b></div><div class="mt-1 flex justify-between"><span>Получено дивидендов по госакциям</span><b>${money(portfolio.summary?.state_share_dividends_earned)}</b></div></div>
        <section class="space-y-2"><h3 class="text-xs font-bold uppercase tracking-wider text-slate-400">Доступные выпуски</h3>${offerCards}</section>
        <section class="glass-card rounded-2xl p-3 space-y-2"><h3 class="text-xs font-bold">Мои государственные акции</h3>${holdingCards}</section>
        <details class="glass-card rounded-2xl p-3"><summary class="cursor-pointer text-xs font-bold">История дивидендов</summary><div class="mt-2 space-y-2">${paymentRows}</div></details>
      </div>`;
      container.querySelector('.state-share-back')?.addEventListener('click', onBack);
      container.querySelectorAll('.state-share-buy').forEach(button => button.addEventListener('click', () => trade(button, 'buy')));
      container.querySelectorAll('.state-share-sell').forEach(button => button.addEventListener('click', () => trade(button, 'sell')));
    }

    async function trade(button, side) {
      const shareId = Number(button.dataset.id);
      const maxQuantity = Number(button.dataset.max || 0);
      const action = side === 'buy' ? NatAPI.buyStateShares : NatAPI.sellStateShares;
      const verb = side === 'buy' ? 'купить' : 'продать казне';
      const raw = prompt(`Сколько акций ${verb}? Максимум: ${maxQuantity.toLocaleString('ru-RU')}`, '1');
      if (raw === null || !raw.trim()) return;
      const quantity = Number(raw);
      if (!Number.isSafeInteger(quantity) || quantity <= 0 || quantity > maxQuantity) {
        showToast(`Укажите целое число от 1 до ${maxQuantity.toLocaleString('ru-RU')}.`, 'error');
        return;
      }
      button.disabled = true;
      try {
        const result = await action(shareId, quantity);
        const updatedCompany = await NatAPI.getMyCompany().catch(() => null);
        if (updatedCompany) store.setCompany(updatedCompany);
        showToast(side === 'buy'
          ? `Куплено ${quantity.toLocaleString('ru-RU')} акций за ${money(result.total_cost)}.`
          : `Казна выкупила ${quantity.toLocaleString('ru-RU')} акций за ${money(result.total_proceeds)}.`, 'success');
        await renderStateShareMarket(container, showToast, onBack);
      } catch (error) {
        showToast(error.message, 'error');
        button.disabled = false;
      }
    }
  } catch (error) {
    showToast(error.message, 'error');
    container.innerHTML = `<div class="space-y-3 p-4"><button id="state-share-back" class="text-xs font-bold text-blue-600">← Вернуться на биржу</button><div class="glass-card rounded-2xl p-5 text-center text-xs text-rose-500">Не удалось загрузить государственные акции.</div></div>`;
    container.querySelector('#state-share-back')?.addEventListener('click', onBack);
  }
}
