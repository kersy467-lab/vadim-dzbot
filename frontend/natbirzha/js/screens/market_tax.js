import { NatAPI } from '../api.js?v=20260925_sabotages_v2';
import { store } from '../state.js?v=20260925_sabotages_v2';

const money = (value) => Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: 2 });
const fmtDate = (value) => value ? new Date(`${value}T12:00:00`).toLocaleDateString('ru-RU') : '—';

function liabilityRows(rows) {
  if (!rows?.length) return '<div class="text-xs text-slate-500">Начислений пока нет.</div>';
  return rows.map((row) => `<div class="rounded-xl border ${row.overdue ? 'border-rose-400/60 bg-rose-50/70 dark:bg-rose-950/20' : 'border-slate-200 dark:border-slate-700'} p-3 text-xs space-y-1">
    <div class="flex justify-between gap-2"><b>${fmtDate(row.tax_date)}</b><span class="${row.overdue ? 'text-rose-600 font-black' : 'text-slate-500'}">${row.overdue ? 'ПРОСРОЧЕНО' : `до ${fmtDate(row.grace_until)}`}</span></div>
    <div class="flex justify-between"><span>Прибыль дня</span><b>${money(row.taxable_profit)} cash</b></div>
    <div class="flex justify-between"><span>Налог</span><b>${money(row.principal)} cash</b></div>
    ${Number(row.penalty || 0) > 0 ? `<div class="flex justify-between text-rose-600"><span>Штраф</span><b>+${money(row.penalty)} cash</b></div>` : ''}
    ${Number(row.paid || 0) > 0 ? `<div class="flex justify-between text-emerald-600"><span>Оплачено</span><b>${money(row.paid)} cash</b></div>` : ''}
    <div class="flex justify-between border-t border-slate-200 dark:border-slate-700 pt-1"><span>Осталось</span><b>${money(row.outstanding)} cash</b></div>
  </div>`).join('');
}

export async function renderTaxSection(container, showToast, onBack) {
  container.innerHTML = '<div class="p-8 text-center text-xs text-slate-400">Расчёт налога…</div>';
  try {
    const tax = await NatAPI.getTaxStatus();
    const blocked = Boolean(tax.blocked);
    const due = Number(tax.total_due || 0);
    container.innerHTML = `<div class="market-contrast-surface space-y-4 max-w-md mx-auto p-4 pb-24">
      <button class="market-tax-back text-xs font-bold text-blue-600">← Назад к бирже</button>
      <div><h2 class="text-xl font-black">🧾 Налог компании</h2><p class="text-xs text-slate-500">Обязательный налог на положительную дневную прибыль предприятий</p></div>
      <div class="rounded-2xl p-4 ${blocked ? 'bg-rose-100 dark:bg-rose-950/35 border border-rose-400' : 'glass-card'} space-y-2">
        <div class="flex justify-between"><span class="text-sm">Ставка</span><b>${Number(tax.rate_pct || 13)}%</b></div>
        <div class="flex justify-between"><span class="text-sm">Налог к оплате</span><b>${money(tax.principal_due)} cash</b></div>
        <div class="flex justify-between"><span class="text-sm">Штрафы</span><b class="${Number(tax.penalty_due || 0) ? 'text-rose-600' : ''}">${money(tax.penalty_due)} cash</b></div>
        <div class="flex justify-between border-t border-slate-300 dark:border-slate-700 pt-2"><span class="font-black">Всего</span><b class="text-lg">${money(due)} cash</b></div>
      </div>
      ${blocked ? `<div class="rounded-2xl border border-rose-500 bg-rose-50 dark:bg-rose-950/30 p-4 text-sm"><b class="text-rose-600">⛔ Производство остановлено</b><p class="mt-1 text-xs">Налог просрочен более чем на ${tax.grace_days} дня. После оплаты предприятия продолжат работать с текущего момента — простой задним числом не компенсируется.</p></div>` : tax.next_block_date ? `<div class="rounded-2xl border border-amber-300 bg-amber-50 dark:bg-amber-950/20 p-4 text-xs"><b>⏳ До блокировки: ${tax.days_until_block} дн.</b><div class="mt-1">Оплатите задолженность до ${fmtDate(tax.next_block_date)}.</div></div>` : ''}
      <div class="glass-card rounded-2xl p-4 text-xs space-y-2"><div class="flex justify-between"><span>Прибыль сегодня</span><b>${money(tax.today_profit)} cash</b></div><div class="flex justify-between"><span>Расчётный налог за сегодня</span><b>${money(tax.today_estimated_tax)} cash</b></div><p class="text-slate-500">Сегодняшний налог станет обязательством после закрытия игрового дня.</p></div>
      <div class="rounded-2xl border border-slate-200 dark:border-slate-700 p-4 text-xs space-y-1"><b>Правила</b><p>13% от положительной дневной прибыли. Задолженность можно копить ${tax.grace_days} дня. Затем все предприятия останавливаются. Каждый просроченный день добавляет штраф ${Number(tax.daily_penalty_pct || 50)}% от исходной суммы налога; штраф не начисляется на штраф.</p></div>
      <button class="market-tax-pay w-full py-3 rounded-xl bg-emerald-600 text-white font-black disabled:opacity-40" ${due > 0 ? '' : 'disabled'}>Оплатить всё · ${money(due)} cash</button>
      <section class="space-y-2"><h3 class="font-black">Последние начисления</h3>${liabilityRows(tax.liabilities)}</section>
    </div>`;
    container.querySelector('.market-tax-back')?.addEventListener('click', onBack);
    container.querySelector('.market-tax-pay')?.addEventListener('click', async (event) => {
      event.currentTarget.disabled = true;
      try {
        const result = await NatAPI.payTax();
        store.updateCompany({ cash: result.cash });
        showToast(`Налог оплачен: ${money(result.paid_now)} cash`, 'success');
        await renderTaxSection(container, showToast, onBack);
      } catch (error) {
        showToast(error.message, 'error');
        event.currentTarget.disabled = false;
      }
    });
  } catch (error) {
    container.innerHTML = `<div class="p-8 text-center text-sm"><b>Не удалось загрузить налог</b><p class="text-xs text-slate-500 mt-2">${String(error.message || error)}</p><button class="market-tax-back mt-4 text-blue-600 font-bold">← Назад</button></div>`;
    container.querySelector('.market-tax-back')?.addEventListener('click', onBack);
  }
}
