import { NatAPI } from '../api.js?v=20260925_deals_v9';
import { formatNumber } from '../format.js';
import { store } from '../state.js?v=20260925_deals_v9';

const TERMS = [
  [600, '10 минут'], [1800, '30 минут'], [3600, '1 час'], [7200, '2 часа'],
  [21600, '6 часов'], [43200, '12 часов'], [86400, '24 часа'],
];

const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[char]));
const cash = (value) => `${formatNumber(Number(value) || 0, 1)} cash`;
const quantity = (value, unit) => `${formatNumber(Number(value) || 0, 3)} ${esc(unit || 'ед.')}`;
const dealStatus = (status) => ({
  PENDING: 'Ожидает ответа', ACTIVE: 'Активна', COMPLETED: 'Завершена',
  REJECTED: 'Отклонена', CANCELLED: 'Отменена', BREACHED: 'Прервана при банкротстве',
}[status] || status);
const formatRemaining = (seconds) => {
  const safe = Math.max(0, Math.floor(Number(seconds) || 0));
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const secs = safe % 60;
  return hours ? `${hours} ч ${minutes} мин` : minutes ? `${minutes} мин ${secs} сек` : `${secs} сек`;
};

export async function renderMarketDeals(container, showToast, onBack) {
  let viewTimer = null;
  let selectedCompany = null;
  let selectedResource = null;

  const clearTimer = () => {
    if (viewTimer) clearInterval(viewTimer);
    viewTimer = null;
  };
  const toast = (message, type = 'success') => showToast?.(message, type);
  const shell = (title, body) => {
    clearTimer();
    container.innerHTML = `<div class="market-contrast-surface space-y-4 max-w-md mx-auto p-4 pb-24">
      <button type="button" class="deals-back text-sm font-bold text-pink-500">← Биржа</button>
      <div><h2 class="text-xl font-black">🤝 ${esc(title)}</h2><p class="text-xs text-slate-500">Временные поставки между компаниями</p></div>
      ${body}</div>`;
    container.querySelector('.deals-back')?.addEventListener('click', onBack);
  };

  async function renderHome() {
    shell('Сделки', `<div class="grid gap-3">
      <button class="deals-nav glass-card rounded-2xl p-4 text-left" data-view="create"><b>➕ Создать сделку</b><div class="text-xs text-slate-500 mt-1">Выберите поставщика и согласуйте условия</div></button>
      <button class="deals-nav glass-card rounded-2xl p-4 text-left" data-view="incoming"><b>📥 Входящие</b><div class="text-xs text-slate-500 mt-1">Предложения другим компаниям</div></button>
      <button class="deals-nav glass-card rounded-2xl p-4 text-left" data-view="outgoing"><b>📤 Исходящие</b><div class="text-xs text-slate-500 mt-1">Ваши ожидающие предложения</div></button>
      <button class="deals-nav glass-card rounded-2xl p-4 text-left" data-view="active"><b>⚙️ Активные</b><div class="text-xs text-slate-500 mt-1">Поставки, оплата и время до завершения</div></button>
      <button class="deals-nav glass-card rounded-2xl p-4 text-left" data-view="history"><b>🗂 История</b><div class="text-xs text-slate-500 mt-1">Завершённые и отменённые сделки</div></button>
    </div>`);
    container.querySelectorAll('.deals-nav').forEach((button) => button.addEventListener('click', () => {
      if (button.dataset.view === 'create') renderCompanyPicker();
      else renderList(button.dataset.view);
    }));
  }

  async function renderCompanyPicker() {
    shell('Создать сделку', '<div class="text-sm text-slate-500">Загружаю активные компании…</div>');
    try {
      const data = await NatAPI.getSupplyDealCompanies();
      const companies = data.companies || [];
      shell('Выберите поставщика', companies.length ? `<div class="space-y-2">${companies.map((company) => `
        <button type="button" class="deal-company glass-card rounded-xl p-3 w-full text-left" data-id="${Number(company.company_id)}">
          <div class="flex justify-between gap-2"><b>${esc(company.company_name)}</b><span class="text-xs">ур. ${Number(company.level) || 1}</span></div>
          <div class="text-xs text-slate-500 mt-1">Игрок: ${esc(company.player_name)} · ${esc(company.specialization)}</div>
          <div class="text-xs text-indigo-500 mt-2">Производит: ${(company.resources || []).length ? company.resources.map((row) => esc(row.name)).join(' · ') : 'нет действующих производств'}</div>
        </button>`).join('')}</div>` : '<div class="glass-card rounded-xl p-4 text-sm text-slate-500">Пока нет других активных компаний.</div>');
      container.querySelectorAll('.deal-company').forEach((button) => button.addEventListener('click', () => selectCompany(Number(button.dataset.id))));
    } catch (error) {
      shell('Выберите поставщика', `<div class="glass-card rounded-xl p-4 text-sm text-rose-500">${esc(error.message)}</div>`);
    }
  }

  async function selectCompany(companyId) {
    selectedCompany = null;
    selectedResource = null;
    shell('Ресурсы поставщика', '<div class="text-sm text-slate-500">Загружаю реальные производства…</div>');
    try {
      selectedCompany = await NatAPI.getSupplyDealCompanyResources(companyId);
      const resources = selectedCompany.resources || [];
      shell('Выберите ресурс', `<div class="glass-card rounded-xl p-3 mb-3"><b>${esc(selectedCompany.company_name)}</b><div class="text-xs text-slate-500 mt-1">Игрок: ${esc(selectedCompany.player_name)} · ур. ${Number(selectedCompany.level) || 1} · ${esc(selectedCompany.specialization)}</div></div>
        <div class="space-y-2">${resources.map((resource) => `<button class="deal-resource glass-card rounded-xl p-3 w-full text-left" data-item="${esc(resource.item_id)}">
          <div class="flex justify-between gap-3"><b>${esc(resource.name)}</b><span class="text-xs">${quantity(resource.outputs_per_hour, `${resource.unit}/ч`)}</span></div>
          <div class="text-xs text-slate-500 mt-1">Ориентир рынка: ${cash(resource.reference_price)}</div>
        </button>`).join('') || '<div class="glass-card rounded-xl p-4 text-sm text-slate-500">У компании нет активного предприятия, производящего доступный ресурс.</div>'}</div>`);
      container.querySelectorAll('.deal-resource').forEach((button) => button.addEventListener('click', () => {
        selectedResource = resources.find((row) => row.item_id === button.dataset.item);
        renderTermsForm();
      }));
    } catch (error) {
      shell('Ресурсы поставщика', `<div class="glass-card rounded-xl p-4 text-sm text-rose-500">${esc(error.message)}</div>`);
    }
  }

  function renderTermsForm(preview = false, values = {}) {
    if (!selectedCompany || !selectedResource) return renderCompanyPicker();
    const price = Number(selectedResource.reference_price) || 0;
    const controls = `<div class="glass-card rounded-2xl p-4 space-y-3">
      <div><b>${esc(selectedResource.name)}</b><div class="text-xs text-slate-500">Поставщик: ${esc(selectedCompany.company_name)}</div></div>
      <label class="block text-xs">Максимум в час (${esc(selectedResource.unit)})<input id="deal-qty" type="number" min="0.001" max="1000000" step="0.001" value="${Number(values.quantity_per_hour ?? 10)}" class="mt-1 w-full rounded-lg p-3 bg-slate-100 dark:bg-slate-800"></label>
      <label class="block text-xs">Скидка от текущей рыночной цены (%)<input id="deal-discount" type="number" min="0" max="50" step="0.1" value="${Number(values.discount_pct ?? 10)}" class="mt-1 w-full rounded-lg p-3 bg-slate-100 dark:bg-slate-800"></label>
      <label class="block text-xs">Срок<select id="deal-term" class="mt-1 w-full rounded-lg p-3 bg-slate-100 dark:bg-slate-800">${TERMS.map(([seconds, label]) => `<option value="${seconds}" ${(Number(values.term_seconds ?? 7200) === seconds) ? 'selected' : ''}>${label}</option>`).join('')}</select></label>
      <label class="block text-xs">Вознаграждение поставщика<select id="deal-reward" class="mt-1 w-full rounded-lg p-3 bg-slate-100 dark:bg-slate-800"><option value="PROFIT_SHARE" ${values.reward_type !== 'FIXED_CASH' ? 'selected' : ''}>Доля положительной прибыли</option><option value="FIXED_CASH" ${values.reward_type === 'FIXED_CASH' ? 'selected' : ''}>Единовременная выплата</option></select></label>
      <label class="deal-share-field block text-xs">Доля прибыли (%)<input id="deal-share" type="number" min="0.1" max="50" step="0.1" value="${Number(values.profit_share_pct ?? 5)}" class="mt-1 w-full rounded-lg p-3 bg-slate-100 dark:bg-slate-800"></label>
      <label class="deal-cash-field hidden block text-xs">Выплата (cash)<input id="deal-cash" type="number" min="0.01" step="0.1" value="${Number(values.fixed_cash ?? 1000)}" class="mt-1 w-full rounded-lg p-3 bg-slate-100 dark:bg-slate-800"></label>
      ${preview ? `<div class="border-t border-slate-300/30 pt-3 text-sm space-y-1"><b>🤝 ПРЕДЛОЖЕНИЕ О СДЕЛКЕ</b>
        <div>Покупатель: ${esc(store.company?.name || 'Ваша компания')}</div><div>Поставщик: ${esc(selectedCompany.company_name)}</div>
        <div>${esc(selectedResource.name)} · <span data-preview-qty>${formatNumber(values.quantity_per_hour ?? 10)}</span> ${esc(selectedResource.unit)}/ч</div>
        <div>Цена сейчас: <span data-preview-price>${cash(price * (1 - Number(values.discount_pct ?? 10) / 100))}</span> (рынок − <span data-preview-discount>${formatNumber(values.discount_pct ?? 10)}</span>%)</div>
        <div>Срок: <span data-preview-term>${esc(TERMS.find(([seconds]) => seconds === Number(values.term_seconds ?? 7200))?.[1] || '2 часа')}</span></div><div>Вознаграждение: <span data-preview-reward>${values.reward_type === 'FIXED_CASH' ? `фиксированная выплата ${cash(values.fixed_cash ?? 1000)}` : `${formatNumber(values.profit_share_pct ?? 5)}% положительной прибыли`}</span></div>
        <div class="text-xs text-slate-500">Цена в сделке каждый раз рассчитывается сервером по текущей цене ресурса.</div>
      </div>` : ''}
      <button type="button" id="deal-preview" class="w-full rounded-xl p-3 font-bold bg-indigo-600 text-white">${preview ? 'Отправить предложение' : 'Проверить условия'}</button>
    </div>`;
    shell(preview ? 'Проверьте условия' : 'Условия поставки', `<div class="text-xs text-slate-500">Максимальная скидка и доля прибыли — 50%. Поставка ограничивается вашим спросом, лимитом и фактическим складом поставщика.</div>${controls}`);

    const reward = container.querySelector('#deal-reward');
    const shareField = container.querySelector('.deal-share-field');
    const cashField = container.querySelector('.deal-cash-field');
    const updateRewardFields = () => {
      const fixed = reward.value === 'FIXED_CASH';
      shareField.classList.toggle('hidden', fixed);
      cashField.classList.toggle('hidden', !fixed);
    };
    reward.addEventListener('change', updateRewardFields);
    updateRewardFields();
    const termName = () => TERMS.find(([seconds]) => seconds === Number(container.querySelector('#deal-term').value))?.[1] || '—';
    const syncPreview = () => {
      if (!preview) return;
      const qty = Math.max(0, Number(container.querySelector('#deal-qty').value) || 0);
      const discount = Math.min(50, Math.max(0, Number(container.querySelector('#deal-discount').value) || 0));
      container.querySelector('[data-preview-qty]').textContent = formatNumber(qty, 3);
      container.querySelector('[data-preview-price]').textContent = cash(price * (1 - discount / 100));
      container.querySelector('[data-preview-discount]').textContent = formatNumber(discount, 1);
      container.querySelector('[data-preview-term]').textContent = termName();
      container.querySelector('[data-preview-reward]').textContent = reward.value === 'FIXED_CASH'
        ? `фиксированная выплата ${cash(container.querySelector('#deal-cash').value)}`
        : `${formatNumber(container.querySelector('#deal-share').value, 1)}% положительной прибыли`;
    };
    container.querySelectorAll('#deal-qty, #deal-discount, #deal-term, #deal-share, #deal-cash').forEach((input) => input.addEventListener('input', syncPreview));
    reward.addEventListener('change', syncPreview);
    const button = container.querySelector('#deal-preview');
    button.addEventListener('click', async () => {
      const qty = Number(container.querySelector('#deal-qty').value);
      const discount = Number(container.querySelector('#deal-discount').value);
      const rewardType = reward.value;
      const rewardValue = rewardType === 'FIXED_CASH'
          ? Number(container.querySelector('#deal-cash').value)
          : Number(container.querySelector('#deal-share').value);
      if (!preview) {
        renderTermsForm(true, {
          quantity_per_hour: qty, discount_pct: discount,
          term_seconds: Number(container.querySelector('#deal-term').value),
          reward_type: rewardType,
          profit_share_pct: rewardType === 'PROFIT_SHARE' ? rewardValue : null,
          fixed_cash: rewardType === 'FIXED_CASH' ? rewardValue : null,
        });
        return;
      }
      if (!(qty > 0 && qty <= 1_000_000) || !(discount >= 0 && discount <= 50) || !(rewardValue > 0 && rewardValue <= 50 && rewardType === 'PROFIT_SHARE' || rewardValue > 0 && rewardType === 'FIXED_CASH')) {
        toast('Проверьте объём, скидку и вознаграждение.', 'error');
        return;
      }
      button.disabled = true;
      button.textContent = 'Отправляем…';
      try {
        const created = await NatAPI.createSupplyDeal({
          supplier_company_id: selectedCompany.company_id,
          item_id: selectedResource.item_id,
          quantity_per_hour: qty,
          discount_pct: discount,
          term_seconds: Number(container.querySelector('#deal-term').value),
          reward_type: rewardType,
          profit_share_pct: rewardType === 'PROFIT_SHARE' ? rewardValue : null,
          fixed_cash: rewardType === 'FIXED_CASH' ? rewardValue : null,
        });
        toast('Предложение отправлено. Сделка начнётся после принятия поставщиком.');
        renderDealDetail(created.id, created);
      } catch (error) {
        toast(error.message || 'Не удалось создать предложение', 'error');
        button.disabled = false;
        button.textContent = 'Отправить предложение';
      }
    });
    syncPreview();
  }

  async function renderList(view) {
    const labels = { incoming: 'Входящие', outgoing: 'Исходящие', active: 'Активные', history: 'История' };
    shell(labels[view] || 'Сделки', '<div class="text-sm text-slate-500">Загружаю…</div>');
    try {
      const data = await NatAPI.getSupplyDeals(view);
      const items = data.items || [];
      const cards = items.map((deal) => `<button class="deal-open glass-card rounded-xl p-3 w-full text-left" data-id="${Number(deal.id)}">
        <div class="flex items-center justify-between gap-2"><b>${esc(deal.item_name)}</b><span class="text-xs ${deal.status === 'ACTIVE' ? 'text-emerald-500' : 'text-slate-500'}">${esc(dealStatus(deal.status))}</span></div>
        <div class="text-xs text-slate-500 mt-1">${deal.viewer_role === 'buyer' ? `Поставщик: ${esc(deal.supplier_company_name)}` : `Покупатель: ${esc(deal.buyer_company_name)}`}</div>
        <div class="text-xs mt-2">${quantity(deal.quantity_per_hour, `${deal.unit}/ч`)} · ${cash(deal.unit_price)} / ${esc(deal.unit)}</div>
        ${deal.status === 'ACTIVE' ? `<div class="text-xs text-indigo-500 mt-1">Осталось: <span class="deal-countdown" data-remaining="${Number(deal.remaining_seconds) || 0}">${formatRemaining(deal.remaining_seconds)}</span></div>` : ''}
      </button>`).join('');
      shell(labels[view], `${items.length ? `<div class="space-y-2">${cards}</div>` : '<div class="glass-card rounded-xl p-4 text-sm text-slate-500">В этом разделе пока нет сделок.</div>'}`);
      container.querySelectorAll('.deal-open').forEach((button) => button.addEventListener('click', () => renderDealDetail(Number(button.dataset.id))));
      if (view === 'active') startCountdowns();
    } catch (error) {
      shell(labels[view], `<div class="glass-card rounded-xl p-4 text-sm text-rose-500">${esc(error.message)}</div>`);
    }
  }

  function startCountdowns() {
    viewTimer = setInterval(() => container.querySelectorAll('.deal-countdown').forEach((node) => {
      const remaining = Math.max(0, Number(node.dataset.remaining) - 1);
      node.dataset.remaining = String(remaining);
      node.textContent = formatRemaining(remaining);
    }), 1000);
  }

  async function renderDealDetail(dealId, initial = null) {
    shell('Детали сделки', '<div class="text-sm text-slate-500">Загружаю условия…</div>');
    try {
      const deal = initial || await NatAPI.getSupplyDeal(dealId);
      const reward = deal.reward_type === 'PROFIT_SHARE'
        ? `${formatNumber(deal.profit_share_pct, 1)}% положительной прибыли покупателя`
        : `единовременно ${cash(deal.fixed_cash)}`;
      const history = (deal.settlements || []).map((row) => `<div class="flex justify-between gap-2 border-t border-slate-300/20 pt-2 text-xs">
        <span>${row.type === 'DELIVERY' ? `Поставка: ${quantity(row.quantity, deal.unit)} по ${cash(row.unit_price)} (рынок ${cash(row.market_reference_price)})` : row.type === 'PROFIT_SHARE' ? `Доля прибыли: база ${cash(row.profit_base_cash)}` : `Фиксированная выплата`}</span><b>${cash(row.cash_amount)}</b>
      </div>`).join('');
      const incoming = deal.status === 'PENDING' && deal.viewer_role === 'supplier';
      const outgoing = deal.status === 'PENDING' && deal.viewer_role === 'buyer';
      shell('Сделка', `<div class="glass-card rounded-2xl p-4 space-y-2 text-sm">
        <div class="flex justify-between gap-2"><b>${esc(dealStatus(deal.status))}</b><span class="text-xs text-slate-500">#${Number(deal.id)}</span></div>
        <div>Покупатель: <b>${esc(deal.buyer_company_name)}</b></div><div>Поставщик: <b>${esc(deal.supplier_company_name)}</b></div>
        <div class="border-t border-slate-300/20 pt-2"><b>${esc(deal.item_name)}</b> · ${quantity(deal.quantity_per_hour, `${deal.unit}/ч`)}</div>
        <div>Цена сейчас: <b>${cash(deal.unit_price)} / ${esc(deal.unit)}</b> · рынок − ${formatNumber(deal.discount_pct, 1)}%</div>
        <div>Начальная оценка рынка: ${cash(deal.quoted_reference_price)} / ${esc(deal.unit)}</div>
        <div>Срок: ${esc(TERMS.find(([seconds]) => seconds === Number(deal.term_seconds))?.[1] || `${deal.term_seconds} сек`)}</div>
        <div>Вознаграждение: <b>${esc(reward)}</b></div>
        ${deal.status === 'ACTIVE' ? `<div class="text-indigo-500">⏳ Осталось: <span id="deal-detail-countdown" data-remaining="${Number(deal.remaining_seconds) || 0}">${formatRemaining(deal.remaining_seconds)}</span></div>` : ''}
        <div class="grid grid-cols-2 gap-2 text-xs pt-2"><div>Поставлено<br><b>${quantity(deal.delivered_quantity, deal.unit)}</b></div><div>Оплачено за ресурс<br><b>${cash(deal.resource_cash_paid)}</b></div><div>Экономия покупателя<br><b>${cash(deal.savings_cash)}</b></div>${deal.reward_type === 'PROFIT_SHARE' ? `<div>Доля прибыли выплачена<br><b>${cash(deal.profit_share_paid)}</b></div>` : `<div>Фиксированно выплачено<br><b>${cash(deal.fixed_cash_paid)}</b></div>`}</div>
        <div class="text-[10px] text-slate-500">Начало: ${esc(deal.starts_at || 'после принятия')}<br>Окончание: ${esc(deal.expires_at || '—')}</div>
        ${incoming ? '<div class="grid grid-cols-2 gap-2 pt-2"><button id="deal-accept" class="rounded-xl p-3 font-bold bg-emerald-600 text-white">✅ Принять</button><button id="deal-reject" class="rounded-xl p-3 font-bold bg-rose-600 text-white">❌ Отклонить</button></div>' : ''}
        ${outgoing ? '<button id="deal-cancel" class="w-full rounded-xl p-3 font-bold bg-rose-600 text-white mt-2">Отменить предложение</button>' : ''}
      </div>
      ${history ? `<div class="glass-card rounded-2xl p-4 space-y-2"><b>Операции сделки</b>${history}</div>` : '<div class="glass-card rounded-2xl p-4 text-sm text-slate-500">Поставок пока нет.</div>'}`);
      const mutate = async (action) => {
        try {
          const labels = { accept: 'Сделка принята', reject: 'Предложение отклонено', cancel: 'Предложение отменено' };
          await NatAPI[`${action}SupplyDeal`](dealId);
          toast(labels[action]);
          renderDealDetail(dealId);
        } catch (error) { toast(error.message || 'Операция не выполнена', 'error'); }
      };
      container.querySelector('#deal-accept')?.addEventListener('click', () => mutate('accept'));
      container.querySelector('#deal-reject')?.addEventListener('click', () => mutate('reject'));
      container.querySelector('#deal-cancel')?.addEventListener('click', () => mutate('cancel'));
      if (deal.status === 'ACTIVE') {
        viewTimer = setInterval(() => {
          const node = container.querySelector('#deal-detail-countdown');
          if (!node) return;
          const remaining = Math.max(0, Number(node.dataset.remaining) - 1);
          node.dataset.remaining = String(remaining);
          node.textContent = formatRemaining(remaining);
        }, 1000);
      }
    } catch (error) {
      shell('Сделка', `<div class="glass-card rounded-xl p-4 text-sm text-rose-500">${esc(error.message)}</div>`);
    }
  }

  await renderHome();
}
