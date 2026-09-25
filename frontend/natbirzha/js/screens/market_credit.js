import { NatAPI } from '../api.js?v=20260925_deals_v6';
import { store } from '../state.js?v=20260925_deals_v6';

const RATE_PCT = 20;
const money = (value) => Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: 2 });
const dateLabel = (value) => value ? new Date(value).toLocaleString('ru-RU') : '—';

function loanCard(loan) {
  const labels = { PENDING: 'ОЖИДАЕТ РЕШЕНИЯ', ACTIVE: 'АКТИВЕН', DEFAULTED: 'ПРОСРОЧЕН', PAID: 'ПОГАШЕН', REJECTED: 'ОТКЛОНЁН' };
  const tones = { PENDING: 'text-amber-600', ACTIVE: 'text-emerald-600', DEFAULTED: 'text-rose-600', PAID: 'text-slate-500', REJECTED: 'text-slate-500' };
  const canRepay = ['ACTIVE', 'DEFAULTED'].includes(loan.status);
  return `<article class="glass-card rounded-2xl p-4 space-y-2 text-xs">
    <div class="flex items-center justify-between gap-2"><b>Государственный кредит #${loan.id}</b><b class="${tones[loan.status] || 'text-slate-500'}">${labels[loan.status] || loan.status}</b></div>
    <div class="flex justify-between"><span>Сумма</span><b>${money(loan.principal)} cash</b></div>
    <div class="flex justify-between"><span>${canRepay ? 'К возврату осталось' : 'К возврату по графику'}</span><b>${money(loan.remaining_debt)} cash</b></div>
    <div class="flex justify-between"><span>Ставка и срок</span><b>${RATE_PCT}%/день · ${Number(loan.term_days)} дн.</b></div>
    <div class="flex justify-between"><span>${loan.status === 'PENDING' ? 'Срок начнётся после одобрения' : 'Вернуть до'}</span><b>${dateLabel(loan.due_at)}</b></div>
    ${loan.status === 'PENDING' ? '<p class="text-amber-600">Заявка отправлена. Деньги поступят после решения создателя.</p>' : ''}
    ${canRepay ? `<div class="flex gap-2 pt-1"><input class="state-credit-repay min-w-0 flex-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-white/70 dark:bg-slate-900 px-3 py-2" type="number" min="0.01" max="${Number(loan.remaining_debt)}" step="0.01" value="${Number(loan.remaining_debt)}" aria-label="Сумма погашения кредита #${loan.id}">
      <button class="state-credit-repay-btn rounded-lg bg-emerald-600 px-3 py-2 font-bold text-white" data-id="${loan.id}">Погасить</button></div>` : ''}
  </article>`;
}

export async function renderStateCreditSection(container, showToast, onBack) {
  container.innerHTML = '<div class="p-8 text-center text-xs text-slate-400">Загружаем государственные кредиты…</div>';
  try {
    const data = await NatAPI.getStateCredit();
    const loans = data.loans || [];
    const maxPrincipal = Math.min(Number(data.available_credit_limit || 0), Number(data.available_treasury_cash ?? data.treasury_cash ?? 0));
    container.innerHTML = `<div class="market-contrast-surface space-y-4 max-w-md mx-auto p-4 pb-24">
      <button class="state-credit-back text-xs font-bold text-blue-600">← Назад к бирже</button>
      <div><h2 class="text-xl font-black">🏦 Кредит государства</h2><p class="text-xs text-slate-500">Подайте заявку на 1–5 дней. Проценты простые: 20% от суммы за каждый день. Кредит выдаётся после одобрения.</p></div>
      <div class="glass-card rounded-2xl p-4 text-xs space-y-2">
        <div class="flex justify-between"><span>Доступно в казне</span><b>${money(data.treasury_cash)} cash</b></div>
        <div class="flex justify-between"><span>Стоимость компании</span><b>${money(data.company_nav)} cash</b></div>
        <div class="flex justify-between"><span>Лимит кредита (50%)</span><b>${money(data.credit_limit)} cash</b></div>
        <div class="flex justify-between"><span>Доступно для новой заявки</span><b>${money(maxPrincipal)} cash</b></div>
        <p class="text-slate-500">Заявки и непогашенный долг занимают лимит. Срок кредита начинается с момента одобрения.</p>
      </div>
      <form class="state-credit-form glass-card rounded-2xl p-4 space-y-3">
        <label class="block text-xs font-bold">Сумма кредита, cash
          <input class="state-credit-principal mt-1 w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-white/70 dark:bg-slate-900 p-3 text-sm" type="number" min="0.01" max="${maxPrincipal}" step="0.01" required placeholder="Например, 100 000">
        </label>
        <label class="block text-xs font-bold">Срок, дней
          <input class="state-credit-days mt-1 w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-white/70 dark:bg-slate-900 p-3 text-sm" type="number" min="1" max="5" step="1" value="1" required>
        </label>
        <div class="rounded-xl bg-slate-100 dark:bg-slate-900/70 p-3 text-xs">К возврату после одобрения: <b class="state-credit-total">0 cash</b></div>
        <button class="state-credit-submit w-full rounded-xl bg-blue-600 py-3 font-black text-white" ${maxPrincipal < 0.01 ? 'disabled' : ''}>Подать заявку</button>
      </form>
      <section class="space-y-2"><h3 class="font-black">Мои государственные кредиты</h3>${loans.map(loanCard).join('') || '<div class="glass-card rounded-xl p-3 text-xs text-slate-500">Заявок и кредитов нет.</div>'}</section>
    </div>`;

    container.querySelector('.state-credit-back')?.addEventListener('click', onBack);
    const form = container.querySelector('.state-credit-form');
    const principalInput = container.querySelector('.state-credit-principal');
    const daysInput = container.querySelector('.state-credit-days');
    const totalNode = container.querySelector('.state-credit-total');
    const updateQuote = () => {
      const principal = Math.max(0, Number(principalInput.value || 0));
      const days = Math.max(0, Number(daysInput.value || 0));
      totalNode.textContent = `${money(principal * (1 + (RATE_PCT / 100) * days))} cash`;
    };
    principalInput.addEventListener('input', updateQuote);
    daysInput.addEventListener('input', updateQuote);

    form?.addEventListener('submit', async (event) => {
      event.preventDefault();
      const principal = Number(principalInput.value);
      const termDays = Number(daysInput.value);
      if (!(principal > 0) || principal > maxPrincipal || !Number.isInteger(termDays) || termDays < 1 || termDays > 5) {
        showToast(`Введите сумму до ${money(maxPrincipal)} cash и срок от 1 до 5 дней`, 'error');
        return;
      }
      const totalDue = principal * (1 + (RATE_PCT / 100) * termDays);
      if (!confirm(`Подать заявку на ${money(principal)} cash на ${termDays} дн.? После одобрения к возврату ${money(totalDue)} cash.`)) return;
      const button = form.querySelector('.state-credit-submit');
      button.disabled = true;
      try {
        const result = await NatAPI.requestStateCredit(principal, termDays);
        showToast(`Заявка #${result.loan?.id} отправлена создателю. Денег пока не перечислено.`, 'success');
        await renderStateCreditSection(container, showToast, onBack);
      } catch (error) {
        showToast(error.message, 'error');
        button.disabled = false;
      }
    });

    container.querySelectorAll('.state-credit-repay-btn').forEach((button) => button.addEventListener('click', async () => {
      const card = button.closest('article');
      const amount = Number(card?.querySelector('.state-credit-repay')?.value);
      if (!(amount > 0)) return showToast('Введите сумму погашения', 'error');
      button.disabled = true;
      try {
        const result = await NatAPI.repayStateCredit(button.dataset.id, amount);
        if (result.remaining_cash != null) store.updateCompany({ cash: result.remaining_cash });
        showToast(`Погашено ${money(result.paid)} cash`, 'success');
        await renderStateCreditSection(container, showToast, onBack);
      } catch (error) {
        showToast(error.message, 'error');
        button.disabled = false;
      }
    }));
  } catch (error) {
    container.innerHTML = `<div class="market-contrast-surface p-4 text-sm"><button class="state-credit-back text-blue-600 font-bold">← Назад</button><p class="mt-4">Не удалось загрузить кредиты государства</p><p class="mt-1 text-xs text-slate-500">${String(error.message || error)}</p></div>`;
    container.querySelector('.state-credit-back')?.addEventListener('click', onBack);
  }
}
