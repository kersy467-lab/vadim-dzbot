import { NatAPI } from '../api.js?v=20260927_hospital_v1';
import { getItemInfo } from '../items.js?v=20260926_local_update_v1';

const FACILITIES = {
  hospital: { title: 'Военный госпиталь', icon: '🏥', barClass: 'bg-emerald-500' },
  repair_depot: { title: 'Ремонтное депо', icon: '🛠️', barClass: 'bg-blue-500' },
};

const UNIT_NAMES = {
  infantry: 'Пехота',
  border_guards: 'Пограничники',
  tanks: 'Бронетехника',
  drones: 'БПЛА',
  air_defense: 'ПВО',
  aircraft: 'Авиация',
};
const TREATMENT_RULES = {
  infantry: { cash: 10, batch: 100, minutes: 1 },
  border_guards: { cash: 20, batch: 100, minutes: 1 },
  tanks: { cash: 200, batch: 10, minutes: 2, materials: { steel: 0.5 } },
  drones: { cash: 100, batch: 20, minutes: 1, materials: { electronics: 0.2 } },
  air_defense: { cash: 300, batch: 5, minutes: 3, materials: { steel: 0.8, electronics: 0.3 } },
  aircraft: { cash: 1_000, batch: 2, minutes: 5, materials: { aluminum: 2, jet_fuel: 1 } },
};

const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[char]));
const number = (value) => (Number(value) || 0).toLocaleString('ru-RU');

function timeLeft(value) {
  const timestamp = Date.parse(value || '');
  if (!Number.isFinite(timestamp)) return 'время неизвестно';
  const seconds = Math.max(0, Math.floor((timestamp - Date.now()) / 1000));
  if (!seconds) return 'завершено';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainder = seconds % 60;
  return hours ? `${hours} ч ${minutes} мин` : minutes ? `${minutes} мин ${remainder} с` : `${remainder} с`;
}

function quoteItems(items) {
  const rows = Array.isArray(items)
    ? items.map((item) => [item.item_id || item.item || item.id, item.quantity ?? item.qty ?? item.amount])
    : Object.entries(items || {});
  return rows.filter(([itemId, quantity]) => itemId && Number(quantity) > 0).map(([itemId, quantity]) => {
    const item = getItemInfo(itemId);
    return `<span class="inline-flex items-center gap-1 rounded-lg bg-slate-900/5 dark:bg-white/5 px-2 py-1">${esc(item.icon)} ${esc(item.name)} × ${number(quantity)}</span>`;
  }).join('');
}

function treatmentEstimate(unitType, count) {
  const rule = TREATMENT_RULES[unitType];
  if (!rule) return '';
  const materials = Object.entries(rule.materials || {}).map(([itemId, perUnit]) => {
    const item = getItemInfo(itemId);
    return `${number(perUnit * count)} ${item.name}`;
  });
  const minutes = Math.max(1, Math.ceil(count / rule.batch)) * rule.minutes;
  const minuteLabel = minutes % 10 === 1 && minutes % 100 !== 11 ? 'минута'
    : minutes % 10 >= 2 && minutes % 10 <= 4 && (minutes % 100 < 12 || minutes % 100 > 14) ? 'минуты' : 'минут';
  return `${number(rule.cash * count)} cash${materials.length ? ` + ${materials.join(' + ')}` : ''} · ${minutes} ${minuteLabel}`;
}

function upgradeMarkup(facilityId, facility, quote) {
  const maxed = Number(facility.level || 0) >= Number(facility.max_level || quote?.max_level || 0);
  const target = Number(quote?.target_level || Number(facility.level || 0) + 1);
  const resources = quoteItems(quote?.items);
  const price = quote
    ? `<div class="text-[10px] text-slate-500">Стоимость: <b class="text-amber-500">${number(quote.cash)} cash</b>${resources ? ` · ${resources}` : ''}</div>`
    : `<div class="text-[10px] text-slate-500">${maxed ? 'Максимальный уровень' : 'Стоимость улучшения недоступна'}</div>`;
  return `<div class="space-y-2 border-t border-slate-300/20 pt-3">
    <div class="flex items-center justify-between gap-2"><span class="text-[10px] text-slate-400">${maxed ? 'Уровень максимальный' : `Следующий уровень: ${number(target)}`}</span>
      <button type="button" data-hospital-action="upgrade" data-facility="${esc(facilityId)}" class="rounded-lg bg-indigo-600 px-3 py-1.5 text-[10px] font-bold text-white disabled:opacity-50" ${quote && !maxed ? '' : 'disabled'}>${maxed ? 'Максимум' : 'Улучшить'}</button></div>
    ${price}
  </div>`;
}

function wardMarkup(ward) {
  const unitType = String(ward.unit_type || '');
  const wounded = Math.max(0, Math.floor(Number(ward.wounded_count) || 0));
  const healing = Math.max(0, Math.floor(Number(ward.healing_count) || 0));
  const ready = Boolean(ward.ready);
  const busy = healing > 0;
  const unitName = UNIT_NAMES[unitType] || unitType || 'Подразделение';
  const timer = busy && !ready
    ? `<div class="text-[10px] text-amber-500">⏳ Осталось: <time data-hospital-timer data-ready-at="${esc(ward.healing_ready_at)}" data-ready-count="${healing}">${esc(timeLeft(ward.healing_ready_at))}</time></div>`
    : '';
  const healingStatus = busy
    ? `<div class="text-[10px] ${ready ? 'text-emerald-500' : 'text-slate-500'}">На лечении: ${number(healing)}${ready ? ' · готово к выдаче' : ''}</div>`
    : '';
  const collectButton = ready
    ? `<button type="button" data-hospital-action="collect" data-unit-type="${esc(unitType)}" class="rounded-lg bg-emerald-600 px-3 py-1.5 text-[10px] font-bold text-white">Забрать ${number(healing)}</button>`
    : '';
  const controls = wounded > 0
    ? `<div class="grid grid-cols-[5rem_1fr_1fr] gap-2 items-center pt-2">
        <input type="number" inputmode="numeric" min="1" max="${wounded}" value="1" aria-label="Количество: ${esc(unitName)}" data-hospital-quantity="${esc(unitType)}" class="w-full rounded-lg border border-slate-300/30 bg-white/70 dark:bg-slate-950/30 px-2 py-2 text-center text-xs disabled:opacity-50" ${busy ? 'disabled' : ''}>
        <button type="button" data-hospital-action="treat" data-unit-type="${esc(unitType)}" class="rounded-lg bg-blue-600 px-2 py-2 text-[10px] font-bold text-white disabled:opacity-50" ${busy ? 'disabled' : ''}>Лечить</button>
        <button type="button" data-hospital-action="instant" data-unit-type="${esc(unitType)}" class="rounded-lg bg-amber-500 px-2 py-2 text-[10px] font-bold text-slate-950 disabled:opacity-50" ${busy ? 'disabled' : ''}>Сразу · +50% cash</button>
      </div><div class="text-[9px] text-slate-500" data-hospital-estimate="${esc(unitType)}">Обычное: ${treatmentEstimate(unitType, 1)} · мгновенно: ${number((TREATMENT_RULES[unitType]?.cash || 0) * 1.5)} cash</div>`
    : '';
  return `<div class="rounded-xl bg-slate-50 dark:bg-slate-800/50 p-3 space-y-1" data-hospital-ward="${esc(unitType)}">
    <div class="flex items-start justify-between gap-2"><div><div class="text-xs font-bold">${esc(unitName)}</div><div class="text-[10px] text-slate-500">Раненые: <b>${number(wounded)}</b></div></div>${collectButton}</div>
    ${healingStatus}${timer}${busy && !ready && wounded > 0 ? '<div class="text-[9px] text-slate-400">Заберите текущую партию перед следующим лечением.</div>' : ''}
    ${controls}
  </div>`;
}

function facilityMarkup(facilityId, facility = {}, quote) {
  const meta = FACILITIES[facilityId];
  const level = Number(facility.level) || 0;
  const maxLevel = Number(facility.max_level || quote?.max_level) || 0;
  const capacity = Math.max(0, Number(facility.capacity) || 0);
  const occupied = Math.max(0, Number(facility.occupied) || 0);
  const available = Math.max(0, Number(facility.available) || 0);
  const progress = capacity > 0 ? Math.max(0, Math.min(100, occupied / capacity * 100)) : 0;
  const wards = (Array.isArray(facility.wards) ? facility.wards : []).map(wardMarkup).join('');
  const capacityLabel = facilityId === 'hospital' ? 'Занято коек' : 'Занято ремонтных мест';
  return `<section class="glass-card rounded-2xl p-4 space-y-3" aria-label="${esc(meta.title)}">
    <div class="flex items-start justify-between gap-3"><div><h3 class="text-sm font-black">${meta.icon} ${esc(meta.title)}</h3><div class="text-[10px] text-slate-500 mt-1">Уровень ${number(level)} / ${number(maxLevel)}</div></div><div class="text-right"><div class="text-xs font-mono font-bold">${number(occupied)} / ${number(capacity)}</div><div class="text-[9px] text-slate-400">${number(available)} свободно</div></div></div>
    <div class="space-y-1"><div class="h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700" role="progressbar" aria-label="${esc(capacityLabel)}" aria-valuemin="0" aria-valuemax="${capacity}" aria-valuenow="${occupied}"><div class="h-full ${meta.barClass} transition-all" style="width:${progress}%"></div></div><div class="text-[9px] text-slate-400">${esc(capacityLabel)} · ${number(occupied)} из ${number(capacity)}</div></div>
    ${upgradeMarkup(facilityId, { ...facility, max_level: maxLevel }, quote)}
    <div class="space-y-2 border-t border-slate-300/20 pt-3"><h4 class="text-[10px] font-bold uppercase text-slate-400">${facilityId === 'hospital' ? 'Раненые подразделения' : 'Повреждённая техника'}</h4>${wards || '<div class="text-[10px] text-slate-500">Нет подразделений для лечения или ремонта.</div>'}</div>
  </section>`;
}

export function renderHospitalSection({ status, upgradeQuotes } = {}) {
  const facilities = status || {};
  const quotes = upgradeQuotes || {};
  const hasWounded = ['hospital', 'repair_depot'].some((key) =>
    (facilities[key]?.wards || []).some((ward) => Number(ward.wounded_count) > 0));
  return `<div class="space-y-3" data-hospital-section>
    <div class="glass-card rounded-2xl p-4 flex items-center justify-between gap-3"><div><h3 class="text-xs font-bold uppercase text-slate-400">Госпиталь и ремонт</h3><p class="mt-1 text-[10px] text-slate-500">Лечите раненых и возвращайте технику в строй.</p></div><button type="button" data-hospital-action="treat-all" class="shrink-0 rounded-xl bg-emerald-600 px-3 py-2 text-[10px] font-bold text-white disabled:opacity-50" ${hasWounded ? '' : 'disabled'}>Лечить всех на доступные средства</button></div>
    ${facilityMarkup('hospital', facilities.hospital, quotes.hospital)}
    ${facilityMarkup('repair_depot', facilities.repair_depot, quotes.repair_depot)}
  </div>`;
}

const bindings = new WeakMap();

export function bindHospitalHandlers(container, { showToast, onRefresh } = {}) {
  const previous = bindings.get(container);
  if (previous) {
    container.removeEventListener('click', previous.click);
    container.removeEventListener('input', previous.input);
    clearInterval(previous.timer);
  }

  const toast = (message, type = 'success') => showToast?.(message, type);
  const refresh = async () => {
    let status = null;
    try { status = await NatAPI.getHospitalStatus(); } catch (_) { /* Let the parent refresh its other military data. */ }
    await onRefresh?.(status);
  };
  const mutate = async (button, action, successMessage) => {
    button.disabled = true;
    let result;
    try {
      result = await action();
    } catch (error) {
      toast(error?.message || 'Не удалось выполнить действие', 'error');
      button.disabled = false;
      return;
    }
    const message = typeof successMessage === 'function' ? successMessage(result) : successMessage;
    if (message) toast(message, 'success');
    try { await refresh(); }
    catch (error) { toast(error?.message || 'Не удалось обновить состояние госпиталя', 'error'); }
    if (button.isConnected) button.disabled = false;
  };

  const click = (event) => {
    const button = event.target.closest?.('[data-hospital-action]');
    if (!button || !container.contains(button) || button.disabled) return;
    const action = button.dataset.hospitalAction;
    if (action === 'treat-all') {
      void mutate(button, () => NatAPI.startAllHospitalTreatments(), (result) => {
        const started = Object.keys(result?.started || {}).length;
        const skipped = Object.keys(result?.skipped || {}).length;
        if (!started) return 'Нет подразделений, лечение которых сейчас можно оплатить';
        return `Запущено: ${started}${skipped ? ` · пропущено без средств: ${skipped}` : ''}`;
      });
      return;
    }
    if (action === 'upgrade') {
      void mutate(button, () => NatAPI.upgradeMilitaryInfrastructure(button.dataset.facility), 'Военный объект улучшен');
      return;
    }
    if (action === 'collect') {
      void mutate(button, () => NatAPI.collectHospitalTreatment(button.dataset.unitType), 'Подразделение возвращено в армию');
      return;
    }
    if (action === 'treat' || action === 'instant') {
      const unitType = button.dataset.unitType;
      const input = [...container.querySelectorAll('[data-hospital-quantity]')]
        .find((field) => field.dataset.hospitalQuantity === unitType);
      const count = Math.min(Number(input?.max) || 1, Math.max(1, Math.floor(Number(input?.value) || 1)));
      void mutate(button, () => NatAPI.startHospitalTreatment(unitType, count, action === 'instant'),
        action === 'instant' ? 'Мгновенное лечение запущено' : 'Лечение запущено');
    }
  };

  const timer = setInterval(() => {
    const nodes = container.querySelectorAll('[data-hospital-timer]');
    if (!nodes.length) { clearInterval(timer); return; }
    nodes.forEach((node) => {
      const remaining = timeLeft(node.dataset.readyAt);
      node.textContent = remaining === 'завершено' ? '✓ Готово к выдаче' : remaining;
      if (remaining === 'завершено') {
        const card = node.closest('[data-hospital-ward]');
        const header = card?.querySelector('.flex.items-start.justify-between');
        if (header && !header.querySelector('[data-hospital-action="collect"]')) {
          const button = document.createElement('button');
          button.type = 'button';
          button.dataset.hospitalAction = 'collect';
          button.dataset.unitType = card.dataset.hospitalWard;
          button.className = 'rounded-lg bg-emerald-600 px-3 py-1.5 text-[10px] font-bold text-white';
          button.textContent = `Забрать ${number(node.dataset.readyCount)}`;
          header.append(button);
        }
      }
    });
  }, 1000);
  const input = (event) => {
    const field = event.target.closest?.('[data-hospital-quantity]');
    if (!field || !container.contains(field)) return;
    const type = field.dataset.hospitalQuantity;
    const count = Math.min(Number(field.max) || 1, Math.max(1, Math.floor(Number(field.value) || 1)));
    const label = container.querySelector(`[data-hospital-estimate="${type}"]`);
    if (label) label.textContent = `Обычное: ${treatmentEstimate(type, count)} · мгновенно: ${number((TREATMENT_RULES[type]?.cash || 0) * count * 1.5)} cash`;
  };
  container.addEventListener('click', click);
  container.addEventListener('input', input);
  bindings.set(container, { click, input, timer });
}
