import { getItemInfo } from '../items.js?v=20260928_ai_compute_fix_v1';

const RUNNING_STATUSES = new Set(['ACTIVE', 'UPGRADING']);
const SUPPLY_STATUSES = new Set(['ACTIVE', 'UPGRADING', 'PAUSED_SUPPLY']);

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));
}

function quantity(value) {
  return Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: 3 });
}

function businessWord(value) {
  const count = Math.abs(Number(value) || 0);
  const lastTwo = count % 100;
  const last = count % 10;
  if (lastTwo >= 11 && lastTwo <= 14) return 'предприятий';
  if (last === 1) return 'предприятие';
  if (last >= 2 && last <= 4) return 'предприятия';
  return 'предприятий';
}

function cycleInputs(business, tickMinutes) {
  if (business.inputs_per_tick && Object.keys(business.inputs_per_tick).length) {
    return business.inputs_per_tick;
  }
  const factor = Math.max(1, Number(tickMinutes) || 15) / 60;
  return Object.fromEntries(Object.entries(business.inputs_per_hour || {}).map(
    ([itemId, rate]) => [itemId, Number(rate) * factor],
  ));
}

function supplyGaps(summary, contributingBusinesses) {
  const tickMinutes = summary.resource_tick_minutes || 15;
  const required = new Map();
  for (const business of contributingBusinesses) {
    for (const [itemId, amount] of Object.entries(cycleInputs(business, tickMinutes))) {
      const need = Number(amount);
      if (!Number.isFinite(need) || need <= 0) continue;
      const entry = required.get(itemId) || { amount: 0, businesses: new Set() };
      entry.amount += need;
      entry.businesses.add(business.catalog_name || business.name || 'Предприятие');
      required.set(itemId, entry);
    }
  }

  const inventory = summary.inventory_available || {};
  return [...required.entries()].map(([itemId, entry]) => ({
    item: getItemInfo(itemId),
    amount: entry.amount,
    available: Math.max(0, Number(inventory[itemId]) || 0),
    businesses: [...entry.businesses],
  })).map((row) => ({ ...row, missing: Math.max(0, row.amount - row.available) }))
    .filter((row) => row.missing > 0.000001);
}

export function renderProductionReadiness(summary = {}) {
  const allBusinesses = Array.isArray(summary.businesses) ? summary.businesses : [];
  const businesses = allBusinesses.filter((business) =>
    !business.contract_expired && !['BANKRUPT', 'MERGING'].includes(business.status),
  );
  const running = businesses.filter((business) => RUNNING_STATUSES.has(business.status));
  const supplyPaused = businesses.filter((business) => business.status === 'PAUSED_SUPPLY');
  const contributors = businesses.filter((business) => SUPPLY_STATUSES.has(business.status));
  const gaps = supplyGaps(summary, contributors);
  const total = businesses.length;

  let title = 'Нет работающих предприятий';
  if (total && running.length === total) title = 'Все предприятия работают';
  else if (running.length) title = 'Часть предприятий остановлена';
  else if (supplyPaused.length) title = 'Производство остановлено из-за сырья';

  const tone = supplyPaused.length || gaps.length
    ? 'border-amber-400/50 bg-amber-50/80 dark:bg-amber-950/25'
    : running.length === total && total > 0
      ? 'border-emerald-400/50 bg-emerald-50/80 dark:bg-emerald-950/25'
      : 'border-slate-300/50 bg-slate-50/80 dark:bg-slate-900/40';
  const gapContent = gaps.length
    ? `<div class="mt-2 space-y-1.5"><div class="text-[10px] font-bold uppercase tracking-wide text-amber-700 dark:text-amber-300">Не хватает на ближайший цикл · ${Number(summary.resource_tick_minutes) || 15} мин</div>${gaps.map((row) => {
      const affected = row.businesses.slice(0, 3).map(escapeHtml).join(', ');
      const extra = row.businesses.length > 3 ? ` и ещё ${row.businesses.length - 3}` : '';
      return `<div class="rounded-lg bg-white/70 dark:bg-slate-900/40 px-2.5 py-2 text-xs"><b>${row.item.icon} ${escapeHtml(row.item.name)}</b>: не хватает <b>${quantity(row.missing)} ${escapeHtml(row.item.unit)}</b><div class="text-[10px] text-slate-500 dark:text-slate-400">Нужно ${quantity(row.amount)}, доступно ${quantity(row.available)}${affected ? ` · заводы: ${affected}${extra}` : ''}</div></div>`;
    }).join('')}</div>`
    : supplyPaused.length
      ? '<div class="mt-2 text-[11px] text-slate-600 dark:text-slate-300">Сырья на ближайший цикл хватает. Если заводы не возобновились, проверьте остальные условия в их карточках.</div>'
      : '';

  const otherPaused = [
    ['PAUSED_MANUAL', 'ручная пауза'],
    ['PAUSED_MAINTENANCE', 'обслуживание'],
    ['PAUSED_STORAGE', 'переполнен склад'],
  ].map(([status, label]) => {
    const count = businesses.filter((business) => business.status === status).length;
    return count ? `${label}: ${count}` : '';
  }).filter(Boolean);

  return `<section class="rounded-2xl border ${tone} p-3.5" aria-label="Состояние производства">
    <div class="flex items-start justify-between gap-3"><div><div class="text-[10px] font-bold uppercase tracking-wide text-slate-500 dark:text-slate-400">🏭 Состояние производства</div><div class="mt-0.5 text-sm font-black text-slate-900 dark:text-white">${title}</div></div><div class="shrink-0 rounded-full bg-white/70 dark:bg-slate-900/40 px-2.5 py-1 text-xs font-black">${running.length}/${total} работают</div></div>
    ${supplyPaused.length ? `<div class="mt-1 text-[11px] text-slate-600 dark:text-slate-300">Без снабжения: ${supplyPaused.length} ${businessWord(supplyPaused.length)}</div>` : ''}
    ${otherPaused.length ? `<div class="mt-1 text-[10px] text-slate-500 dark:text-slate-400">${otherPaused.join(' · ')}</div>` : ''}
    ${gapContent}
  </section>`;
}
