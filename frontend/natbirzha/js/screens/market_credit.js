import { NatAPI } from '../api.js';
import { store } from '../state.js';

const RATE_PCT = 7.5;
const money = (value) => Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: 2 });
const dateLabel = (value) => value ? new Date(value).toLocaleString('ru-RU') : '—';

function loanCard(loan) {
  const status = loan.status === 'DEFAULTED' ? 'ПРОСРОЧЕН' : 'АКТИВЕН';
  const badge = loan.status === 'DEFAULTED' ? 'text-rose-600' : 'text-emerald-600';
  return `<article class="glass-card rounded-2xl p-4 space-y-2 text-xs">
    <div class="flex items-center justify-between gap-2"><b>Государственный кредит #${loan.id}</b><b class="${badge}">${status}</b></div>
    <div class="flex justify-between"><span>Получено</span><b>${money(loan.principal)} cash</b></div>
    <div class="flex justify-between"><span>К возврату осталось</span><b>${money(loan.remaining_debt)} cash</b></div>
    <div class="flex justify-between"><span>Ставка и срок</span><b>${RATE_PCT}%/день · ${Number(loan.term_days)} дн.</b></div>
    <div class="flex justify-between"><span>Вернуть до</span><b>${dateLabel(loan.due_at)}</b></div>
    <div class="flex gap-2 pt-1">
      <input class="state-credit-repay min-w-0 flex-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-white/70 dark:bg-slate-900 px-3 py-2" type="number" min="0.01" max="${Number(loan.remaining_debt)}" step="0.01" value="${Number(loan.remaining_debt)}" aria-label="Сумма погашения кредита #${loan.id}">
      <button class="state-credit-repay-btn rounded-lg bg-emerald-600 px-3 py-2 font-bold text-white" data-id="${loan.id}">Погасить</button>
    </div>
  </article>`;
}

export async function renderStateCreditSection(container, showToast, onBack) {
  container.innerHTML = '<div class="p-8 text-center text-xs text-slate-400">Загружаем государственные кредиты…</div>';
  try {
    const data = await NatAPI.getStateCredit();
    const loans = data.loans || [];
    const outstanding = loans.filter((loan) => ['ACTIVE', 'DEFAULTED'].includes(loan.status));
    container.innerHTML = `<div class="market-contrast-surface space-y-4 max-w-md mx-auto p-4 pb-24">
      <button class="state-credit-back text-xs font-bold text-blue-600">← Назад к бирже</button>
      <div><h2 class="text-xl font-black">🏦 Кредит государства</h2><p class="text-xs text-slate-500">Введите сумму и срок. Проценты простые: 7,5% от суммы за каждый день.</p></div>
      <div class="glass-card rounded-2xl p-4 text-xs space-y-2">
        <div class="flex justify-between"><span>Доступно в казне</span><b>${money(data.treasury_cash)} cash</b></div>
        <div class="flex justify-between"><span>Ставка</span><b>${Number(data.interest_rate_pct || RATE_PCT)}% в день</b></div>
        <p class="text-slate-500">Стоимость кредита не растёт сложным процентом: проценты рассчитываются один раз по сумме и выбранному сроку.</p>
      </div>
      <form class="state-credit-form glass-card rounded-2xl p-4 space-y-3">
        <label class="block text-xs font-bold">Сумма кредита, cash
          <input class="state-credit-principal mt-1 w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-white/70 dark:bg-slate-900 p-3 text-sm" type="number" min="0.01" step="0.01" required placeholder="Например, 100 000">
        </label>
        <label class="block text-xs font-bold">Срок, дней
          <input class="state-credit-days mt-1 w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-white/70 dark:bg-slate-900 p-3 text-sm" type="number" min="1" max="365" step="1" value="1" required>
        </label>
        <div class="rounded-xl bg-slate-100 dark:bg-slate-900/70 p-3 text-xs">К возврату: <b class="state-credit-total">0 cash</b></div>
        <button class="state-credit-submit w-full rounded-xl bg-blue-600 py-3 font-black text-white">Получить кредит</button>
      </form>
      <section class="space-y-2"><h3 class="font-black">Мои государственные кредиты</h3>${outstanding.map(loanCard).join('') || '<div class="glass-card rounded-xl p-3 text-xs text-slate-500">Открытых кредитов нет.</div>'}</section>
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
      if (!(principal > 0) || !Number.isInteger(termDays) || termDays < 1 || termDays > 365) {
        showToast('Введите положительную сумму и срок от 1 до 365 дней', 'error');
        return;
      }
      const totalDue = principal * (1 + (RATE_PCT / 100) * termDays);
      if (!confirm(`Получить ${money(principal)} cash на ${termDays} дн.? К возврату ${money(totalDue)} cash.`)) return;
      const button = form.querySelector('.state-credit-submit');
      button.disabled = true;
      try {
        const result = await NatAPI.requestStateCredit(principal, termDays);
        if (result.remaining_cash != null) store.updateCompany({ cash: result.remaining_cash });
        showToast(`Кредит получен: ${money(result.cash_received)} cash. К возврату ${money(result.loan?.total_due ?? totalDue)} cash.`, 'success');
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
