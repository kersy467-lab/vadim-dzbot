import { NatAPI } from '../api.js?v=20260924_creator_controls';

const money = (value) => Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: 2 });
const dateLabel = (value) => value ? new Date(value).toLocaleString('ru-RU') : '—';
const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[char]));

export async function loadCreatorCreditTab(el, showToast) {
  let status = 'PENDING';
  async function reload() {
    const data = await NatAPI.getCreatorStateCredits(status);
    const requests = data.requests || [];
    el.innerHTML = `<div class="space-y-3">
      <div class="glass-card rounded-2xl p-3 space-y-2"><div class="text-xs font-bold text-amber-400 uppercase">Заявки на государственный кредит</div>
        <p class="text-[10px] text-slate-400">Лимит — 50% текущей стоимости компании, срок до 5 дней, ставка 20% в день. Средства перечисляются после одобрения.</p>
        <div class="flex gap-2"><button class="creator-credit-filter rounded-lg px-3 py-2 text-xs font-bold ${status === 'PENDING' ? 'bg-amber-500 text-slate-950' : 'bg-slate-800 text-slate-300'}" data-status="PENDING">Ожидают</button>
          <button class="creator-credit-filter rounded-lg px-3 py-2 text-xs font-bold ${status === 'ALL' ? 'bg-amber-500 text-slate-950' : 'bg-slate-800 text-slate-300'}" data-status="ALL">Все</button></div>
      </div>
      <div class="space-y-2">${requests.map((loan) => {
        const pending = loan.status === 'PENDING';
        const tone = pending ? 'text-amber-400' : loan.status === 'ACTIVE' ? 'text-emerald-400' : 'text-slate-400';
        return `<article class="glass-card rounded-2xl p-3 space-y-1.5 text-xs"><div class="flex justify-between gap-2"><b>${escapeHtml(loan.company_name)} · заявка #${loan.id}</b><b class="${tone}">${escapeHtml(loan.status)}</b></div>
          <div class="flex justify-between"><span>Сумма / к возврату</span><b>${money(loan.principal)} / ${money(loan.total_due)} cash</b></div>
          <div class="flex justify-between"><span>Срок / ставка</span><b>${loan.term_days} дн. · 20% в день</b></div>
          <div class="flex justify-between"><span>Стоимость компании</span><b>${money(loan.company_nav)} cash</b></div>
          <div class="flex justify-between"><span>Лимит 50% · занято другими займами</span><b>${money(loan.credit_limit)} · ${money(loan.other_open_principal)} cash</b></div>
          <div class="text-[10px] text-slate-500">Подана: ${dateLabel(loan.requested_at)}${loan.reviewed_at ? ` · рассмотрена: ${dateLabel(loan.reviewed_at)}` : ''}</div>
          ${pending ? `<div class="grid grid-cols-2 gap-2 pt-1"><button class="creator-credit-decision rounded-lg bg-emerald-600 px-3 py-2 font-bold text-white" data-id="${loan.id}" data-approved="true">Одобрить</button>
            <button class="creator-credit-decision rounded-lg bg-rose-700 px-3 py-2 font-bold text-white" data-id="${loan.id}" data-approved="false">Отклонить</button></div>` : ''}
        </article>`;
      }).join('') || '<div class="glass-card rounded-xl p-4 text-center text-xs text-slate-500">Заявок нет.</div>'}</div>
    </div>`;

    el.querySelectorAll('.creator-credit-filter').forEach((button) => button.addEventListener('click', async () => {
      status = button.dataset.status;
      try { await reload(); } catch (error) { showToast(error.message, 'error'); }
    }));
    el.querySelectorAll('.creator-credit-decision').forEach((button) => button.addEventListener('click', async () => {
      const approved = button.dataset.approved === 'true';
      const action = approved ? 'одобрить' : 'отклонить';
      if (!confirm(`${action[0].toUpperCase()}${action.slice(1)} заявку #${button.dataset.id}?`)) return;
      button.disabled = true;
      try {
        const result = await NatAPI.decideCreatorStateCredit(button.dataset.id, approved);
        showToast(approved ? `Одобрено, компании перечислено ${money(result.cash_received)} cash.` : 'Заявка отклонена.', 'success');
        await reload();
      } catch (error) {
        showToast(error.message, 'error');
        button.disabled = false;
      }
    }));
  }
  await reload();
}
