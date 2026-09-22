import { NatAPI } from '../api.js';
import { getItemInfo } from '../items.js';
import { getSpecializationName } from '../localization.js';
import { store } from '../state.js';

let refreshTimer = null;

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
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days) return `${days}д ${hours}ч`;
  if (hours) return `${hours}ч ${String(minutes).padStart(2, '0')}м`;
  return `${minutes}м`;
}

function remainingUntil(readyAt) {
  if (!readyAt) return 0;
  const time = new Date(String(readyAt).replace(' ', 'T')).getTime();
  return Number.isFinite(time) ? Math.max(0, Math.ceil((time - Date.now()) / 1000)) : 0;
}

function statusLabel(status) {
  return {
    ACTIVE: ['Работает', 'tycoon-status-active'],
    UPGRADING: ['Модернизация', 'tycoon-status-upgrading'],
    PAUSED_SUPPLY: ['Нет снабжения', 'tycoon-status-warning'],
    PAUSED_MANUAL: ['На паузе', 'tycoon-status-muted'],
    PAUSED_MAINTENANCE: ['Обслуживание', 'tycoon-status-warning'],
    PAUSED_STORAGE: ['Склад заполнен', 'tycoon-status-warning'],
    BANKRUPT: ['Банкротство', 'tycoon-status-danger'],
    MERGING: ['Слияние', 'tycoon-status-upgrading'],
  }[status] || ['Состояние неизвестно', 'tycoon-status-muted'];
}

function resourceChips(entries, direction = '', period = 'ч') {
  const values = Object.entries(entries || {});
  if (!values.length) return '<span class="text-xs text-slate-400">нет</span>';
  return values.map(([id, amount]) => {
    const item = getItemInfo(id);
    const sign = direction === 'out' ? '＋' : direction === 'in' ? '−' : '';
    return `<span class="tycoon-resource-chip">${item.icon} ${sign}${money(amount)}/${period} ${esc(item.name)}</span>`;
  }).join('');
}

function resourceRequirements(entries) {
  const values = Object.entries(entries || {});
  if (!values.length) return '';
  return values.map(([id, amount]) => {
    const item = getItemInfo(id);
    return `${item.icon} ${money(amount)} ${esc(item.name)}`;
  }).join(' · ');
}

function supplyControls(business, summary) {
  const inputs = Object.keys(business.inputs_per_hour || {});
  if (!inputs.length) return '';
  const automation = summary.supply_automation || {};
  if (!automation.unlocked) {
    return `<div class="mt-3 rounded-xl border border-slate-200 dark:border-slate-700 p-2.5 text-xs text-slate-500 dark:text-slate-300"><b>📦 Снабжение вручную</b><div class="mt-1">Автозакупка откроется на 15 уровне компании. Сейчас запасайтесь перед AFK самостоятельно.</div></div>`;
  }
  const rows = inputs.map((itemId) => {
    const item = getItemInfo(itemId);
    const policy = business.supply_policies?.[itemId] || { mode: 'MANUAL' };
    const stockHours = Number(business.stock_hours_by_item?.[itemId] || 0);
    return `<div class="mt-2 rounded-lg bg-slate-50 dark:bg-slate-900/40 p-2"><div class="flex items-center justify-between gap-2"><span>${item.icon} ${esc(item.name)}</span><b>${stockHours.toFixed(1)} ч</b></div><div class="grid grid-cols-3 gap-1 mt-1.5"><button type="button" class="tycoon-mini ${policy.mode === 'MANUAL' ? 'tycoon-mini-active' : ''}" data-action="supply-mode" data-id="${business.id}" data-item="${esc(itemId)}" data-mode="MANUAL">Вручную</button><button type="button" class="tycoon-mini ${policy.mode === 'AUTO_MARKET' ? 'tycoon-mini-active' : ''}" data-action="supply-mode" data-id="${business.id}" data-item="${esc(itemId)}" data-mode="AUTO_MARKET">Биржа</button><button type="button" class="tycoon-mini ${policy.mode === 'AUTO_MARKET_NPC' ? 'tycoon-mini-active' : ''}" data-action="supply-mode" data-id="${business.id}" data-item="${esc(itemId)}" data-mode="AUTO_MARKET_NPC">Биржа + гос.</button></div></div>`;
  }).join('');
  return `<details class="mt-3 rounded-xl border border-slate-200 dark:border-slate-700 p-2.5"><summary class="cursor-pointer text-xs font-black">⚙️ Автоснабжение · ${automation.used || 0}/${automation.max || 0}</summary>${rows}<div class="mt-2 text-[10px] text-slate-400">Авто закупает, когда остаётся меньше 2 часов, и пополняет примерно до 8 часов. Сначала ищет предложения игроков; Госрезерв используется только в смешанном режиме.</div></details>`;
}

function assetPanel(business, catalog) {
  const assets = business.assets || {};
  const specialization = business.specialization;
  const vehicles = assets.vehicles || [];
  const employees = assets.employees || [];
  const projects = assets.projects || [];
  const vehicleOptions = (catalog?.vehicles || []).filter(item => specialization === 'logistics' && Number(business.stage) >= Number(item.min_business_stage || 1));
  const employeeOptions = (catalog?.employees || []).filter(item => (item.specializations || []).includes(specialization) && Number(business.stage) >= Number(item.min_business_stage || 1));
  const projectOptions = (catalog?.projects || []).filter(item => (item.specializations || []).includes(specialization) && Number(business.stage) >= Number(item.min_stage || 1));
  if (!vehicles.length && !employees.length && !projects.length && !vehicleOptions.length && !employeeOptions.length && !projectOptions.length) return '';
  const vehicleRows = vehicles.map(row => `<div class="flex items-center justify-between gap-2 text-[10px] py-1"><span>${esc(row.icon)} ${esc(row.name)} · ${Number(row.condition).toFixed(0)}%</span><button class="tycoon-mini" data-action="repair-vehicle" data-vehicle-id="${row.id}">Ремонт</button></div>`).join('');
  const employeeRows = employees.map(row => `<div class="flex items-center justify-between gap-2 text-[10px] py-1"><span>${esc(row.icon)} ${esc(row.name)} · ${money(row.salary_per_hour)} cash/ч</span><button class="tycoon-mini" data-action="fire-employee" data-employee-id="${row.id}">Уволить</button></div>`).join('');
  const projectRows = projects.slice(0, 4).map(row => `<div class="flex justify-between gap-2 text-[10px] py-1"><span>${esc(row.name)}</span><b>${row.status === 'ACTIVE' ? duration(remainingUntil(row.ready_at)) : 'готово'}</b></div>`).join('');
  return `<details class="mt-3 rounded-xl border border-indigo-300/40 dark:border-indigo-700/50 p-2.5"><summary class="cursor-pointer text-xs font-black">🏢 Управление активами</summary>
    ${vehicleRows ? `<div class="mt-2"><div class="text-[9px] uppercase text-slate-400">Автопарк ${assets.vehicle_slots?.used || 0}/${assets.vehicle_slots?.max || 0}</div>${vehicleRows}</div>` : ''}
    ${vehicleOptions.length ? `<div class="flex flex-wrap gap-1 mt-2">${vehicleOptions.slice(-3).map(item => `<button class="tycoon-mini" data-action="buy-vehicle" data-id="${business.id}" data-vehicle-type="${esc(item.id)}">${esc(item.icon)} ${esc(item.name)} · ${money(item.cost)}</button>`).join('')}</div>` : ''}
    ${employeeRows ? `<div class="mt-2"><div class="text-[9px] uppercase text-slate-400">Команда ${assets.employee_slots?.used || 0}/${assets.employee_slots?.max || 0}</div>${employeeRows}</div>` : ''}
    ${employeeOptions.length ? `<div class="flex flex-wrap gap-1 mt-2">${employeeOptions.slice(-3).map(item => `<button class="tycoon-mini" data-action="hire-employee" data-id="${business.id}" data-role="${esc(item.id)}">+ ${esc(item.name)} · ${money(item.hire_cost)}</button>`).join('')}</div>` : ''}
    ${(projectRows || projectOptions.length) ? `<div class="mt-2"><div class="text-[9px] uppercase text-slate-400">Проекты ${assets.project_slots?.used || 0}/${assets.project_slots?.max || 0}</div>${projectRows}<div class="flex flex-wrap gap-1 mt-1">${projectOptions.map(item => `<button class="tycoon-mini" data-action="start-project" data-id="${business.id}" data-project-type="${esc(item.id)}">▶ ${esc(item.name)}</button>`).join('')}</div></div>` : ''}
  </details>`;
}

function businessCard(business, summary, assetCatalog) {
  const [label, statusClass] = statusLabel(business.status);
  const next = business.next_upgrade;
  const isUpgrading = business.status === 'UPGRADING';
  const rest = remainingUntil(business.upgrade_ready_at);
  const profit = Number(business.estimated_profit_per_hour ?? business.net_per_hour ?? 0);
  const autonomy = business.autonomy_hours == null ? null : Number(business.autonomy_hours);
  const milestone = next?.milestone;
  const upgrade = next && !isUpgrading
    ? `<button type="button" class="tycoon-action tycoon-upgrade" data-action="upgrade" data-id="${business.id}">Улучшить до ${next.target_stage} · ${money(next.cost)} cash</button>`
    : '';
  const saleMode = business.sale_mode || null;
  const saleControl = business.mechanic === 'resource_production'
    ? `<div class="mt-3 rounded-xl border border-slate-200 dark:border-slate-700 p-2.5"><div class="text-[10px] uppercase tracking-wide text-slate-400 mb-1.5">Реализация продукции</div><div class="grid grid-cols-2 gap-2"><button type="button" class="tycoon-action ${saleMode === 'NPC' ? 'tycoon-upgrade' : 'tycoon-secondary'}" data-action="sale-mode" data-mode="NPC" data-id="${business.id}">💰 Госрезерв</button><button type="button" class="tycoon-action ${saleMode === 'HOLD' ? 'tycoon-upgrade' : 'tycoon-secondary'}" data-action="sale-mode" data-mode="HOLD" data-id="${business.id}">📦 На склад</button></div><div class="mt-1.5 text-[10px] text-slate-400">Госрезерв даёт cash автоматически. «На склад» сохраняет товар для биржи и собственных цепочек.</div></div>`
    : '';
  const lifecycle = business.status === 'PAUSED_MANUAL'
    ? `<button type="button" class="tycoon-action tycoon-secondary" data-action="resume" data-id="${business.id}">Возобновить</button>`
    : (!isUpgrading && !['BANKRUPT', 'PAUSED_SUPPLY', 'MERGING'].includes(business.status)
      ? `<button type="button" class="tycoon-action tycoon-secondary" data-action="pause" data-id="${business.id}">Пауза</button>` : '');
  return `<article class="tycoon-business-card">
    <div class="flex items-start justify-between gap-3">
      <div class="flex items-start gap-2 min-w-0"><span class="tycoon-business-icon">${esc(business.icon || '🏢')}</span><div class="min-w-0"><h3 class="tycoon-business-title">${esc(business.catalog_name || business.name || 'Предприятие')}</h3><div class="text-xs text-slate-400">Уровень ${business.stage}/${business.max_stage}</div></div></div>
      <span class="tycoon-status ${statusClass}">${label}</span>
    </div>
    <p class="mt-2 text-xs text-slate-500 dark:text-slate-300">${esc(business.description || '')}</p>
    <div class="tycoon-rate-row"><span>Оценочная прибыль</span><strong class="${profit >= 0 ? 'tycoon-rate-positive' : 'tycoon-rate-negative'}">${profit >= 0 ? '+' : ''}${money(profit)} cash/ч</strong></div>
    <div class="tycoon-meter"><span style="width:${Math.max(2, Math.min(100, Number(business.stage || 1) / Math.max(1, Number(business.max_stage || 1)) * 100))}%"></span></div>
    <div class="tycoon-subgrid"><div><span>Обслуживание</span><b>${money(business.maintenance_per_hour)} cash/ч</b></div><div><span>Автономность</span><b>${autonomy == null ? 'не ограничена' : `${autonomy.toFixed(1)} ч`}</b></div></div>
    <div class="tycoon-resource-line"><span class="text-xs text-slate-400">Каждые ${business.resource_tick_minutes || 15} мин · расход</span><div>${resourceChips(business.inputs_per_tick || business.inputs_per_hour, 'in', `${business.resource_tick_minutes || 15}м`)}</div></div>
    <div class="tycoon-resource-line"><span class="text-xs text-slate-400">Каждые ${business.resource_tick_minutes || 15} мин · выпуск</span><div>${resourceChips(business.outputs_per_tick || business.outputs_per_hour, 'out', `${business.resource_tick_minutes || 15}м`)}</div></div>
    ${milestone ? `<div class="mt-3 rounded-xl border border-amber-300/40 bg-amber-50/70 dark:bg-amber-950/25 p-3 text-xs"><b>Следующий рубеж: ${esc(milestone.label)}</b><div class="mt-1 text-slate-600 dark:text-slate-300">${esc(milestone.description || '')}</div><div class="mt-1">${resourceRequirements(milestone.resources)}</div></div>` : ''}
    ${isUpgrading ? `<div class="tycoon-upgrade-timer">⏳ До уровня ${business.next_upgrade?.target_stage || Number(business.stage) + 1}: <b data-countdown="${esc(business.upgrade_ready_at)}">${duration(rest)}</b></div>` : ''}
    ${saleControl}
    ${supplyControls(business, summary)}
    ${assetPanel(business, assetCatalog)}
    <div class="tycoon-actions">${upgrade}${lifecycle}<button type="button" class="tycoon-action tycoon-danger" data-action="sell" data-id="${business.id}">Продать</button></div>
  </article>`;
}

function requirementState(item, summary, owned, catalogMap) {
  const missing = [];
  if (Number(summary.level || 1) < Number(item.company_level_required || 1)) {
    missing.push(`уровень компании ${item.company_level_required}`);
  }
  if (Number(summary.territory_tiles || 0) < Number(item.territory_required || 0)) {
    missing.push(`территория ${item.territory_required}`);
  }
  Object.entries(item.prerequisites || {}).forEach(([id, stage]) => {
    const business = owned.get(id);
    if (!business || Number(business.stage) < Number(stage)) {
      missing.push(`${catalogMap.get(id)?.name || 'предыдущее предприятие'} ур. ${stage}`);
    }
  });
  if (Number(summary.cash || 0) < Number(item.open_cost || 0)) missing.push('недостаточно cash');
  return { available: missing.length === 0, missing };
}

function catalogCard(item, requirement, opened) {
  const output = resourceChips(item.outputs_per_hour, 'out');
  const firstMilestone = item.milestones?.['10'] || item.milestones?.[10];
  const disabled = !requirement.available || opened;
  return `<article class="tycoon-catalog-card ${disabled ? 'opacity-80' : ''}">
    <div class="flex items-start justify-between gap-2"><div class="flex items-start gap-2"><span class="text-2xl">${esc(item.icon || '🏢')}</span><div><h3 class="font-black text-slate-900 dark:text-white">${esc(item.name)}</h3><p class="text-xs text-slate-500 dark:text-slate-300">50 уровней · этап ${item.industry_order}</p></div></div><span class="text-lg">${opened ? '✅' : requirement.available ? '🔓' : '🔒'}</span></div>
    <p class="mt-2 text-xs text-slate-500 dark:text-slate-300">${esc(item.description || '')}</p>
    <div class="mt-2 text-xs"><span class="text-slate-400">Производит</span><div class="mt-1">${output}</div></div>
    ${firstMilestone ? `<div class="mt-2 text-xs text-amber-700 dark:text-amber-300">Первый рубеж: <b>${esc(firstMilestone.label)}</b></div>` : ''}
    ${Object.keys(item.open_resources || {}).length ? `<div class="mt-2 text-xs text-slate-500 dark:text-slate-300"><span class="text-slate-400">Ресурсы открытия:</span> ${resourceRequirements(item.open_resources)}</div>` : ''}
    <div class="mt-2 text-xs text-slate-500 dark:text-slate-300">${requirement.missing.length ? `Нужно: ${esc(requirement.missing.join(' · '))}` : `Открытие: ${money(item.open_cost)} cash`}</div>
    <button type="button" class="tycoon-open-btn" data-action="open" data-type="${esc(item.id)}" ${disabled ? 'disabled' : ''}>${opened ? 'Уже открыто' : requirement.available ? `Открыть за ${money(item.open_cost)} cash` : 'Пока недоступно'}</button>
  </article>`;
}

function render(root, state, showToast) {
  const summary = state.summary || {};
  const businesses = summary.businesses || [];
  const specialization = summary.specialization || store.company?.specialization;
  const ownCatalog = state.catalog
    .filter((item) => item.specialization === specialization)
    .sort((a, b) => Number(a.industry_order) - Number(b.industry_order));
  const owned = new Map(businesses.map((item) => [item.business_type, item]));
  const catalogMap = new Map(ownCatalog.map((item) => [item.id, item]));
  const profit = Number(summary.estimated_profit_per_hour || 0);
  root.innerHTML = `<div class="tycoon-screen space-y-4 max-w-md mx-auto p-4 pb-24">
    <div class="tycoon-hero"><div><div class="text-xs uppercase tracking-widest text-pink-200">НАТБИРЖА · IDLE TYCOON</div><h2 class="text-2xl font-black text-white mt-1">${esc(getSpecializationName(specialization))}</h2><p class="text-xs text-pink-100/80 mt-1">Ваша отрасль — отдельная карьерная ветка. Предприятия работают постоянно, пока хватает снабжения.</p></div><span class="text-4xl">🏭</span></div>
    <div class="tycoon-stat-grid"><div class="tycoon-stat"><span>Баланс</span><b>${money(summary.cash)} cash</b></div><div class="tycoon-stat"><span>Оценочная прибыль</span><b class="${profit >= 0 ? 'tycoon-rate-positive' : 'tycoon-rate-negative'}">${profit >= 0 ? '+' : ''}${money(profit)}/ч</b></div><div class="tycoon-stat"><span>Компания</span><b>ур. ${summary.level || 1}</b></div><div class="tycoon-stat"><span>Мощности</span><b>${summary.slots?.used || 0}/${summary.slots?.max || 0}</b></div><div class="tycoon-stat"><span>Крупные проекты</span><b>${summary.project_slots?.used || 0}/${summary.project_slots?.max || 1}</b></div></div>
    ${state.settlement?.settled_hours > 0 ? `<div class="tycoon-offline">🌙 Рассчитано офлайн: ${Number(state.settlement.settled_hours).toFixed(1)} ч. Денежный поток: <b>${money(state.settlement.net_cash)} cash</b>${Number(state.settlement.xp_gained || 0) ? ` · XP +${money(state.settlement.xp_gained)}` : ''}</div>` : ''}
    ${Number(state.settlement?.skipped_offline_hours || 0) > 0 ? `<div class="tycoon-offline border-amber-400/40">⏱️ Лимит офлайн-работы исчерпан. Не рассчитано: ${Number(state.settlement.skipped_offline_hours).toFixed(1)} ч. Текущий лимит: ${state.settlement.offline_cap_hours || summary.offline_cap_hours || 24} ч.</div>` : ''}
    ${state.settlement?.tax?.blocked ? `<div class="tycoon-offline border-rose-500/60 bg-rose-50/80 dark:bg-rose-950/30">⛔ Предприятия остановлены из-за просроченного налога. К оплате: <b>${money(state.settlement.tax.total_due)} cash</b>. Оплатите задолженность во вкладке «Биржа → Налог».</div>` : ''}
    <section><div class="flex items-center justify-between mb-2"><h3 class="text-lg font-black text-slate-900 dark:text-white">Ваши предприятия</h3><span class="text-xs text-slate-500 dark:text-slate-300">${businesses.length} объектов</span></div>${businesses.length ? `<div class="space-y-3">${businesses.map((business) => businessCard(business, summary, state.assetCatalog)).join('')}</div>` : `<div class="tycoon-empty">Предприятий пока нет. Откройте стартовый объект своей отрасли.</div>`}</section>
    <section><div class="mb-2"><h3 class="text-lg font-black text-slate-900 dark:text-white">Карьерная ветка</h3><p class="text-xs text-slate-500 dark:text-slate-300">${ownCatalog.length} уникальных предприятий · по 50 уровней каждое. Чужие отрасли здесь не смешиваются.</p></div><div class="grid gap-3">${ownCatalog.map((item) => catalogCard(item, requirementState(item, summary, owned, catalogMap), owned.has(item.id))).join('')}</div></section>
  </div>`;
  bind(root, showToast);
}

async function reload(root, showToast) {
  const [summary, catalog, assetCatalog] = await Promise.all([
    NatAPI.getEmpireSummary(), NatAPI.getBusinessCatalog(), NatAPI.getBusinessAssetCatalog(),
  ]);
  store.updateCompany({ cash: summary.cash, specialization: summary.specialization, level: summary.level });
  render(root, { summary, catalog: catalog.items || [], assetCatalog, settlement: summary.settlement }, showToast);
}

function bind(root, showToast) {
  root.querySelectorAll('[data-action]').forEach((button) => button.addEventListener('click', async () => {
    const action = button.dataset.action;
    button.disabled = true;
    try {
      if (action === 'open') await NatAPI.openBusiness(button.dataset.type);
      if (action === 'upgrade') await NatAPI.upgradeBusiness(button.dataset.id);
      if (action === 'pause') await NatAPI.pauseBusiness(button.dataset.id);
      if (action === 'resume') await NatAPI.resumeBusiness(button.dataset.id);
      if (action === 'sale-mode') await NatAPI.setBusinessSaleMode(button.dataset.id, button.dataset.mode);
      if (action === 'supply-mode') {
        const mode = button.dataset.mode;
        await NatAPI.setBusinessSupplyPolicy(button.dataset.id, button.dataset.item, {
          mode, min_hours_stock: mode === 'MANUAL' ? 0 : 2, target_hours_stock: mode === 'MANUAL' ? 0 : 8,
          max_unit_price: null, allow_state_reserve: mode === 'AUTO_MARKET_NPC',
        });
      }
      if (action === 'buy-vehicle') await NatAPI.purchaseBusinessVehicle(button.dataset.id, button.dataset.vehicleType);
      if (action === 'repair-vehicle') await NatAPI.repairBusinessVehicle(button.dataset.vehicleId);
      if (action === 'hire-employee') await NatAPI.hireBusinessEmployee(button.dataset.id, button.dataset.role);
      if (action === 'fire-employee') await NatAPI.fireBusinessEmployee(button.dataset.employeeId);
      if (action === 'start-project') await NatAPI.startBusinessProject(button.dataset.id, button.dataset.projectType);
      if (action === 'sell') {
        if (!window.confirm('Продать предприятие и вернуть 40% вложенного капитала?')) return;
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
  container.innerHTML = '<div class="p-8 text-center text-xs text-slate-400">Загрузка отрасли…</div>';
  try {
    await reload(container, showToast);
    refreshTimer = setInterval(() => {
      container.querySelectorAll('[data-countdown]').forEach((node) => {
        node.textContent = duration(remainingUntil(node.dataset.countdown));
      });
    }, 1000);
  } catch (error) {
    container.innerHTML = `<div class="p-8 text-center"><div class="text-3xl">⚠️</div><p class="mt-2 text-sm font-bold">Не удалось открыть предприятия</p><p class="mt-1 text-xs text-slate-500">${esc(error.message)}</p></div>`;
  }
}
