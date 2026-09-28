import { NatAPI } from '../api.js?v=20260928_market_frontend_perf_v1';
import { formatNumber } from '../format.js';

const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[char]));
const cash = (value) => `${formatNumber(Number(value) || 0, 1)} cash`;
const listOf = (data, ...keys) => {
  if (Array.isArray(data)) return data;
  for (const key of keys) if (Array.isArray(data?.[key])) return data[key];
  return [];
};
const statusLabel = (status) => ({
  PENDING: 'Ожидает ответа', ACTIVE: 'Работает', COMPLETED: 'Завершён',
  REJECTED: 'Отклонено', CANCELLED: 'Отменено', BREACHED: 'Прервано',
}[status] || status || '—');
const contributionMarkup = (sides) => (Array.isArray(sides) ? sides : []).map((side) => `
  <div class="rounded-lg bg-slate-500/5 p-2"><div class="text-[11px] font-bold">${esc(side.company_name || 'Компания')}: ${cash(side.cash_contribution)}</div>
    ${(Array.isArray(side.materials) ? side.materials : []).map((item) => `<div class="flex justify-between gap-2 text-[11px] text-slate-500"><span>${esc(item.name || item.item_name || item.item_id)}</span><span>${formatNumber(Number(item.quantity) || 0, 1)} ${esc(item.unit || 'ед.')}</span></div>`).join('')}
  </div>`).join('');

export async function renderMarketJointFactories(container, showToast, onBack) {
  const toast = (message, type = 'success') => showToast?.(message, type);
  const shell = (title, body) => {
    container.innerHTML = `<div class="market-contrast-surface space-y-4 max-w-md mx-auto p-4 pb-24">
      <button type="button" class="joint-back text-sm font-bold text-pink-500">← Сделки</button>
      <div><h2 class="text-xl font-black">🏭 ${esc(title)}</h2><p class="text-xs text-slate-500">Совместное предприятие двух компаний</p></div>
      ${body}</div>`;
    container.querySelector('.joint-back')?.addEventListener('click', onBack);
  };

  const showError = (title, error) => shell(title, `<div class="glass-card rounded-xl p-4 text-sm text-rose-500">${esc(error?.message || 'Не удалось загрузить данные')}</div>`);
  const partnerCompanyId = (row) => Number(row.partner_company_id ?? row.counterpart_company_id ?? row.target_company_id ?? row.company_id);
  const recipeId = (row) => row.recipe_id ?? row.partnership_id ?? row.project_type;
  const partnerName = (row) => row.partner_company_name || row.counterpart_company_name || row.company_name || row.partner_name || 'Компания';
  const projectName = (row) => row.project_name || row.recipe_name || row.name || 'Совместный завод';

  async function home() {
    shell('Совместные заводы', '<div class="text-sm text-slate-500">Загружаю проекты…</div>');
    try {
      const [summary, incoming, outgoing] = await Promise.all([
        NatAPI.getJointFactories(),
        NatAPI.getJointFactoryProposals('inbox'),
        NatAPI.getJointFactoryProposals('outbox'),
      ]);
      const factories = listOf(summary, 'items', 'factories', 'projects');
      const incomingCount = listOf(incoming, 'items', 'proposals').filter((row) => row.status === 'PENDING').length;
      const outgoingCount = listOf(outgoing, 'items', 'proposals').filter((row) => row.status === 'PENDING').length;
      const slot = summary.slot || summary.joint_slot || {};
      const slotText = slot.used || slot.occupied || summary.has_active_factory
        ? 'Занят совместным заводом' : 'Свободен';
      shell('Совместные заводы', `<div class="glass-card rounded-2xl p-4 border border-indigo-300/50">
        <div class="flex items-center justify-between gap-3"><div><b>Отдельный слот совместного завода</b><div class="text-xs text-slate-500 mt-1">${esc(slotText)} · отдельно от обычных предприятий</div></div><span class="text-2xl">🤝</span></div>
        <div class="mt-3 text-xs text-slate-500">Партнёры вместе оплачивают строительство. Дальше завод производит без текущих расходов.</div>
      </div>
      <div class="grid gap-2">
        <button type="button" data-action="create" class="joint-action glass-card rounded-xl p-4 text-left"><b>➕ Предложить совместный завод</b><div class="text-xs text-slate-500 mt-1">Выберите совместимую компанию и проект</div></button>
        <button type="button" data-action="incoming" class="joint-action glass-card rounded-xl p-4 text-left"><b>📥 Входящие предложения${incomingCount ? ` · ${incomingCount}` : ''}</b></button>
        <button type="button" data-action="outgoing" class="joint-action glass-card rounded-xl p-4 text-left"><b>📤 Исходящие предложения${outgoingCount ? ` · ${outgoingCount}` : ''}</b></button>
      </div>
      <div><h3 class="font-bold mb-2">Мои совместные заводы</h3>${factories.length ? `<div class="space-y-2">${factories.map(factoryCard).join('')}</div>` : '<div class="glass-card rounded-xl p-4 text-sm text-slate-500">Пока нет совместных заводов. Предложите партнёрство компании из совместимой отрасли.</div>'}</div>`);
      container.querySelectorAll('.joint-action').forEach((button) => button.addEventListener('click', () => {
        if (button.dataset.action === 'create') renderPartners();
        else renderProposals(button.dataset.action);
      }));
      wireFactoryCards(factories);
    } catch (error) { showError('Совместные заводы', error); }
  }

  function factoryCard(factory) {
    const id = Number(factory.id ?? factory.factory_id ?? factory.joint_factory_id);
    const level = Number(factory.level ?? factory.current_level) || 1;
    const active = (factory.status || 'ACTIVE') === 'ACTIVE';
    const outputs = listOf(factory, 'warehouse', 'outputs', 'stock');
    const claimable = listOf(factory, 'claimable', 'my_claimable', 'claimable_outputs');
    const counterpart = factory.partner_company_name || factory.counterpart_company_name || factory.other_company_name || 'Партнёр';
    const rows = outputs.length ? outputs.map((item) => `<div class="flex justify-between gap-2 text-xs"><span>${esc(item.item_name || item.name || item.item_id)}</span><span>${formatNumber(Number(item.quantity ?? item.stock) || 0, 1)} ${esc(item.unit || 'ед.')}</span></div>`).join('') : '<div class="text-xs text-slate-500">Склад пока пуст</div>';
    const claimQty = claimable.reduce((total, item) => total + (Number(item.quantity ?? item.claimable_quantity) || 0), 0);
    return `<div class="glass-card rounded-2xl p-4 space-y-3">
      <div class="flex items-start justify-between gap-2"><div><b>${esc(projectName(factory))}</b><div class="text-xs text-slate-500 mt-1">Партнёр: ${esc(counterpart)} · уровень ${level}/4</div></div><span class="rounded-full bg-emerald-100 text-emerald-700 px-2 py-1 text-[10px]">${esc(statusLabel(factory.status || 'ACTIVE'))}</span></div>
      <div class="space-y-1 border-t border-slate-300/20 pt-2"><div class="text-[10px] font-bold uppercase text-slate-400">Общий склад</div>${rows}</div>
      <div class="flex items-center justify-between gap-2 text-xs"><span>Ваша доля к получению</span><b>${formatNumber(claimQty || Number(factory.claimable_quantity) || 0, 1)} ед.</b></div>
      <div class="grid grid-cols-2 gap-2"><button type="button" class="joint-claim rounded-xl p-2.5 text-xs font-bold bg-indigo-600 text-white disabled:opacity-50" data-id="${id}" ${claimQty <= 0 && !Number(factory.claimable_quantity) ? 'disabled' : ''}>Забрать свою долю</button><button type="button" class="joint-upgrade rounded-xl p-2.5 text-xs font-bold border border-indigo-300 disabled:opacity-50" data-id="${id}" ${level >= 4 || !active ? 'disabled' : ''}>Запросить улучшение</button></div>
      <div class="text-[10px] text-slate-500">Производство не списывает деньги, материалы или обслуживание. Склад общий, доля каждого владельца учитывается отдельно.</div>
    </div>`;
  }

  function wireFactoryCards(factories) {
    container.querySelectorAll('.joint-claim').forEach((button) => button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        const result = await NatAPI.claimJointFactory(Number(button.dataset.id));
        toast(result.message || 'Ваша доля перемещена на склад компании');
        await home();
      } catch (error) { toast(error.message || 'Не удалось забрать продукцию', 'error'); button.disabled = false; }
    }));
    container.querySelectorAll('.joint-upgrade').forEach((button) => button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        const result = await NatAPI.requestJointFactoryUpgrade(Number(button.dataset.id));
        toast(result.message || 'Запрос на улучшение отправлен партнёру');
        await home();
      } catch (error) { toast(error.message || 'Не удалось запросить улучшение', 'error'); button.disabled = false; }
    }));
  }

  async function renderPartners() {
    shell('Выберите партнёра', '<div class="text-sm text-slate-500">Загружаю совместимые компании…</div>');
    try {
      const data = await NatAPI.getJointFactoryPartners();
      const partners = listOf(data, 'items', 'partners', 'options');
      shell('Выберите партнёра', partners.length ? `<div class="space-y-2">${partners.map((row, index) => `<button type="button" class="joint-partner glass-card rounded-xl p-3 w-full text-left" data-index="${index}">
        <div class="flex justify-between gap-2"><b>${esc(projectName(row))}</b><span class="text-xs text-indigo-500">${esc(row.partner_industry_name || row.specialization || '')}</span></div>
        <div class="text-xs text-slate-500 mt-1">${esc(partnerName(row))}${row.player_name ? ` · игрок ${esc(row.player_name)}` : ''}</div>
        ${row.contribution_sides?.length ? `<div class="text-xs mt-2 space-y-1">Взносы при строительстве:${contributionMarkup(row.contribution_sides)}</div>` : ''}
      </button>`).join('')}</div>` : '<div class="glass-card rounded-xl p-4 text-sm text-slate-500">Сейчас нет компаний с доступным совместным проектом. Для завода нужны два разных игрока из совместимых отраслей.</div>');
      container.querySelectorAll('.joint-partner').forEach((button) => button.addEventListener('click', () => reviewProposal(partners[Number(button.dataset.index)])));
    } catch (error) { showError('Выберите партнёра', error); }
  }

  function reviewProposal(partner) {
    const outputs = listOf(partner, 'outputs', 'preview_outputs');
    const outputRows = outputs.map((item) => `<div class="flex justify-between gap-2 text-xs"><span>${esc(item.name || item.item_name || item.item_id)}</span><b>${formatNumber(Number(item.quantity_per_hour ?? item.rate_per_hour) || 0, 1)} ${esc(item.unit || 'ед.')}/ч</b></div>`).join('');
    shell('Проверьте проект', `<div class="glass-card rounded-2xl p-4 space-y-3">
      <div><b>${esc(projectName(partner))}</b><div class="text-xs text-slate-500 mt-1">Партнёр: ${esc(partnerName(partner))}</div></div>
      <div class="text-sm">Обе стороны вносят равную долю на строительство. После принятия завод займёт отдельный слот.</div>
      ${partner.contribution_sides?.length ? `<div class="space-y-1"><b class="text-xs">Взносы каждой компании</b>${contributionMarkup(partner.contribution_sides)}</div>` : ''}
      ${outputRows ? `<div class="space-y-1"><b class="text-xs">Производство совместного завода</b>${outputRows}</div>` : ''}
      <div class="text-xs text-slate-500">Доход на долю каждого владельца ниже обычного предприятия того же уровня. Текущих расходов нет.</div>
      <button type="button" id="joint-send-proposal" class="w-full rounded-xl p-3 font-bold bg-indigo-600 text-white">Отправить предложение</button>
    </div>`);
    container.querySelector('#joint-send-proposal')?.addEventListener('click', async (buttonEvent) => {
      const button = buttonEvent.currentTarget;
      const targetId = partnerCompanyId(partner);
      if (!Number.isInteger(targetId) || targetId <= 0 || recipeId(partner) == null) {
        toast('Для этого варианта не хватает данных проекта. Обновите экран или попробуйте позже.', 'error');
        return;
      }
      button.disabled = true;
      button.textContent = 'Отправляем…';
      try {
        await NatAPI.createJointFactoryProposal({ partner_company_id: targetId, recipe_id: recipeId(partner) });
        toast('Предложение отправлено партнёру');
        await renderProposals('outgoing');
      } catch (error) { toast(error.message || 'Не удалось отправить предложение', 'error'); button.disabled = false; button.textContent = 'Отправить предложение'; }
    });
  }

  async function renderProposals(view) {
    const incoming = view === 'incoming';
    const title = incoming ? 'Входящие предложения' : 'Исходящие предложения';
    shell(title, '<div class="text-sm text-slate-500">Загружаю…</div>');
    try {
      const data = await NatAPI.getJointFactoryProposals(incoming ? 'inbox' : 'outbox');
      const proposals = listOf(data, 'items', 'proposals');
      shell(title, proposals.length ? `<div class="space-y-2">${proposals.map((proposal) => {
        const id = Number(proposal.id ?? proposal.proposal_id);
        const waiting = proposal.status === 'PENDING';
        const otherSide = incoming
          ? proposal.proposer_company_name || proposal.from_company_name || proposal.company_name
          : proposal.partner_company_name || proposal.recipient_company_name || proposal.target_company_name;
        const contribution = proposal.cash_contribution ?? proposal.cash_per_company;
        return `<div class="glass-card rounded-xl p-4 space-y-2"><div class="flex justify-between gap-2"><b>${esc(projectName(proposal))}</b><span class="text-xs text-slate-500">${esc(statusLabel(proposal.status))}</span></div>
          <div class="text-xs text-slate-500">${incoming ? 'Предлагает' : 'Партнёр'}: ${esc(otherSide || 'Компания')}</div>
          ${proposal.contribution_sides?.length ? `<div class="space-y-1"><b class="text-[11px]">Взносы каждой компании</b>${contributionMarkup(proposal.contribution_sides)}</div>` : contribution != null ? `<div class="text-xs">Вклад каждой стороны: ${cash(contribution)}</div>` : ''}
          ${proposal.message ? `<div class="text-sm">${esc(proposal.message)}</div>` : ''}
          ${waiting ? `<div class="grid grid-cols-2 gap-2 pt-1">${incoming ? `<button type="button" class="joint-proposal-mutate rounded-xl p-2.5 text-xs font-bold bg-emerald-600 text-white" data-id="${id}" data-action="accept">✅ Принять</button><button type="button" class="joint-proposal-mutate rounded-xl p-2.5 text-xs font-bold bg-rose-600 text-white" data-id="${id}" data-action="reject">Отклонить</button>` : `<button type="button" class="joint-proposal-mutate col-span-2 rounded-xl p-2.5 text-xs font-bold bg-rose-600 text-white" data-id="${id}" data-action="cancel">Отменить предложение</button>`}</div>` : ''}
        </div>`;
      }).join('')}</div>` : '<div class="glass-card rounded-xl p-4 text-sm text-slate-500">Предложений пока нет.</div>');
      container.querySelectorAll('.joint-proposal-mutate').forEach((button) => button.addEventListener('click', async () => {
        button.disabled = true;
        const action = button.dataset.action;
        try {
          await NatAPI[`${action}JointFactoryProposal`](Number(button.dataset.id));
          toast(({ accept: 'Совместный завод создан', reject: 'Предложение отклонено', cancel: 'Предложение отменено' })[action]);
          await renderProposals(view);
        } catch (error) { toast(error.message || 'Действие не выполнено', 'error'); button.disabled = false; }
      }));
    } catch (error) { showError(title, error); }
  }

  await home();
}
