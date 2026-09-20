import { NatAPI } from '../api.js';
import { store } from '../state.js';

let refreshTimer = null;

const ICONS = {
  retail_chain: '🛍️', agroholding: '🌾', energy_company: '⚡', water_utility: '💧',
  mining_company: '⛏️', oil_gas_company: '🛢️', metallurgy_combine: '🏭',
  chemical_concern: '⚗️', technoprom: '💻', logistics_company: '🚚',
  construction_company: '🏗️', it_company: '🧠', bank_business: '🏦',
  real_estate_company: '🏢',
};

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));
}

function money(value) {
  return Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: 0 });
}

function duration(value) {
  const seconds = Math.max(0, Math.ceil(Number(value || 0)));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = seconds % 60;
  return hours ? `${hours}ч ${String(minutes).padStart(2, '0')}м` : `${minutes}м ${String(rest).padStart(2, '0')}с`;
}

function remainingUntil(readyAt) {
  if (!readyAt) return 0;
  const time = new Date(String(readyAt).replace(' ', 'T')).getTime();
  return Number.isFinite(time) ? Math.max(0, Math.ceil((time - Date.now()) / 1000)) : 0;
}

function statusLabel(status) {
  return {
    ACTIVE: ['Работает', 'tycoon-status-active'],
    UPGRADING: ['Улучшение', 'tycoon-status-upgrading'],
    PAUSED_SUPPLY: ['Нет снабжения', 'tycoon-status-warning'],
    PAUSED_MANUAL: ['На паузе', 'tycoon-status-muted'],
    PAUSED_MAINTENANCE: ['Обслуживание', 'tycoon-status-warning'],
    BANKRUPT: ['Банкротство', 'tycoon-status-danger'],
  }[status] || ['Активен', 'tycoon-status-active'];
}

function resourceChips(entries, direction) {
  const values = Object.entries(entries || {});
  if (!values.length) return '<span class="text-xs text-slate-400">нет</span>';
  return values.map(([id, amount]) => `<span class="tycoon-resource-chip">${direction === 'out' ? '＋' : '−'}${amount}/ч ${esc(id)}</span>`).join('');
}

function businessCard(business, showToast) {
  const [label, statusClass] = statusLabel(business.status);
  const next = business.next_upgrade;
  const isUpgrading = business.status === 'UPGRADING';
  const rest = remainingUntil(business.upgrade_ready_at);
  const icon = ICONS[business.business_type] || '🏢';
  const rate = Number(business.net_per_hour || 0);
  const upgrade = next && !isUpgrading
    ? `<button type="button" class="tycoon-action tycoon-upgrade" data-action="upgrade" data-id="${business.id}">Улучшить до ${next.target_stage} · ${money(next.cost)} cash</button>`
    : '';
  const lifecycle = business.status === 'PAUSED_MANUAL'
    ? `<button type="button" class="tycoon-action tycoon-secondary" data-action="resume" data-id="${business.id}">Возобновить</button>`
    : (!isUpgrading && !['BANKRUPT', 'PAUSED_SUPPLY'].includes(business.status)
      ? `<button type="button" class="tycoon-action tycoon-secondary" data-action="pause" data-id="${business.id}">Пауза</button>` : '');
  return `<article class="tycoon-business-card">
    <div class="flex items-start justify-between gap-3">
      <div class="flex items-start gap-2 min-w-0"><span class="tycoon-business-icon">${icon}</span><div class="min-w-0"><h3 class="tycoon-business-title">${esc(business.name || business.business_type)}</h3><div class="text-xs text-slate-400">Стадия ${business.stage}/${business.max_stage} · ${esc(business.business_type)}</div></div></div>
      <span class="tycoon-status ${statusClass}">${label}</span>
    </div>
    <div class="tycoon-rate-row"><span>Чистый доход</span><strong class="${rate >= 0 ? 'tycoon-rate-positive' : 'tycoon-rate-negative'}">${rate >= 0 ? '+' : ''}${money(rate)} cash/ч</strong></div>
    <div class="tycoon-meter"><span style="width:${Math.max(2, Math.min(100, Number(business.stage || 1) / Math.max(1, Number(business.max_stage || 1)) * 100))}%"></span></div>
    <div class="tycoon-subgrid"><div><span>Расходы</span><b>${money(business.maintenance_per_hour)} cash/ч</b></div><div><span>Мощность</span><b>${business.mechanic === 'resource_production' ? 'ресурсы/ч' : 'cash/ч'}</b></div></div>
    <div class="tycoon-resource-line"><span class="text-xs text-slate-400">Вход</span><div>${resourceChips(business.inputs_per_hour, 'in')}</div></div>
    <div class="tycoon-resource-line"><span class="text-xs text-slate-400">Выход</span><div>${resourceChips(business.outputs_per_hour, 'out')}</div></div>
    ${isUpgrading ? `<div class="tycoon-upgrade-timer">⏳ До стадии ${business.next_upgrade?.target_stage || Number(business.stage) + 1}: <b data-countdown="${esc(business.upgrade_ready_at)}">${duration(rest)}</b></div>` : ''}
    <div class="tycoon-actions">${upgrade}${lifecycle}<button type="button" class="tycoon-action tycoon-danger" data-action="sell" data-id="${business.id}">Продать</button></div>
  </article>`;
}

function catalogCard(item) {
  const icon = ICONS[item.id] || '🏢';
  const output = Object.entries(item.outputs_per_hour || {}).map(([id, amount]) => `${amount}/ч ${id}`).join(', ') || `${item.base_income_per_hour}/ч cash`;
  return `<article class="tycoon-catalog-card"><div class="flex items-start gap-2"><span class="text-2xl">${icon}</span><div class="min-w-0"><h3 class="font-black text-slate-900 dark:text-white">${esc(item.name)}</h3><p class="text-xs text-slate-500 dark:text-slate-300">Тир ${item.tier} · до стадии ${item.max_stage}</p></div></div><p class="mt-2 text-xs text-slate-500 dark:text-slate-300">${item.mechanic === 'cash_income' ? `Доход: ${money(item.base_income_per_hour)} cash/ч` : `Производство: ${esc(output)}`}</p><button type="button" class="tycoon-open-btn" data-action="open" data-type="${esc(item.id)}" data-cost="${item.open_cost}">Открыть за ${money(item.open_cost)} cash</button></article>`;
}

function render(root, state, showToast) {
  const summary = state.summary || {};
  const businesses = summary.businesses || [];
  const opened = new Set(businesses.map((item) => item.business_type));
  const catalog = state.catalog.filter((item) => !opened.has(item.id));
  root.innerHTML = `<div class="tycoon-screen space-y-4 max-w-md mx-auto p-4 pb-24">
    <div class="tycoon-hero"><div><div class="text-xs uppercase tracking-widest text-pink-200">RichLife · НАТБИРЖА 2.0</div><h2 class="text-2xl font-black text-white mt-1">Моя империя</h2><p class="text-xs text-pink-100/80 mt-1">Бизнесы работают постоянно. Управляйте стадиями, капиталом и снабжением.</p></div><span class="text-4xl">🏙️</span></div>
    <div class="tycoon-stat-grid"><div class="tycoon-stat"><span>Баланс</span><b>${money(summary.cash)} cash</b></div><div class="tycoon-stat"><span>Доход в час</span><b class="tycoon-rate-positive">+${money(summary.net_cash_per_hour)}</b></div><div class="tycoon-stat"><span>Активы</span><b>${summary.slots?.used || 0}/${summary.slots?.max || 0}</b></div><div class="tycoon-stat"><span>Снабжение</span><b>${businesses.filter((item) => item.status === 'PAUSED_SUPPLY').length ? '⚠️ есть сбой' : '✓ стабильно'}</b></div></div>
    ${state.settlement?.settled_hours > 0 ? `<div class="tycoon-offline">🌙 Пока вас не было, империя рассчитала ${Number(state.settlement.settled_hours).toFixed(1)} ч. Доход: <b>+${money(state.settlement.net_cash)} cash</b></div>` : ''}
    <section><div class="flex items-center justify-between mb-2"><h3 class="text-lg font-black text-slate-900 dark:text-white">Ваши бизнесы</h3><span class="text-xs text-slate-500 dark:text-slate-300">${businesses.length} из ${summary.slots?.max || 0}</span></div>${businesses.length ? `<div class="space-y-3">${businesses.map((item) => businessCard(item, showToast)).join('')}</div>` : `<div class="tycoon-empty">Пока нет бизнесов. Откройте первое предприятие — оно начнёт работать сразу, без запуска цикла.</div>`}</section>
    <section><div class="flex items-center justify-between mb-2"><h3 class="text-lg font-black text-slate-900 dark:text-white">Открыть бизнес</h3><span class="text-xs text-slate-500 dark:text-slate-300">Каталог</span></div><div class="grid gap-3">${catalog.slice(0, 8).map(catalogCard).join('')}</div></section>
  </div>`;
  bind(root, state, showToast);
}

async function reload(root, showToast) {
  const [summary, catalog] = await Promise.all([NatAPI.getEmpireSummary(), NatAPI.getBusinessCatalog()]);
  store.updateCompany({ cash: summary.cash });
  render(root, { summary, catalog: catalog.items || [], settlement: summary.settlement }, showToast);
}

function bind(root, state, showToast) {
  root.querySelectorAll('[data-action]').forEach((button) => button.addEventListener('click', async () => {
    const action = button.dataset.action;
    button.disabled = true;
    try {
      if (action === 'open') await NatAPI.openBusiness(button.dataset.type);
      if (action === 'upgrade') await NatAPI.upgradeBusiness(button.dataset.id);
      if (action === 'pause') await NatAPI.pauseBusiness(button.dataset.id);
      if (action === 'resume') await NatAPI.resumeBusiness(button.dataset.id);
      if (action === 'sell') {
        if (!window.confirm('Продать бизнес и вернуть 40% вложенного капитала?')) return;
        await NatAPI.sellBusiness(button.dataset.id);
      }
      showToast('Империя обновлена', 'success');
      await reload(root, showToast);
    } catch (error) {
      showToast(error.message, 'error');
      button.disabled = false;
    }
  }));
}

export async function renderTycoon(container, showToast) {
  if (refreshTimer) clearInterval(refreshTimer);
  container.innerHTML = '<div class="p-8 text-center text-xs text-slate-400">Загрузка империи…</div>';
  try {
    await reload(container, showToast);
    refreshTimer = setInterval(() => {
      container.querySelectorAll('[data-countdown]').forEach((node) => {
        const rest = remainingUntil(node.dataset.countdown);
        node.textContent = duration(rest);
      });
    }, 1000);
  } catch (error) {
    container.innerHTML = `<div class="p-8 text-center"><div class="text-3xl">⚠️</div><p class="mt-2 text-sm font-bold">Не удалось открыть новую империю</p><p class="mt-1 text-xs text-slate-500">${esc(error.message)}</p></div>`;
  }
}
