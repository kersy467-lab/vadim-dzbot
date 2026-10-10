import { NatAPI } from '../api.js?v=20261010_shell_v2';
import { esc, number } from './next_game_common.js?v=20261010_shell_v2';

function cost(quote, items) {
  if (!quote) return 'Достигнут предел';
  return `${number(quote.cash)} cash${Object.entries(quote.inputs || {}).map(([id, amount]) => ` + ${number(amount, 4)} ${esc(items.get(id)?.name || id)}`).join('')}`;
}

function command(action, label, attrs = '', disabled = false) {
  return `<button type="button" class="next-game-secondary" data-operations-action="${action}" ${attrs} ${disabled ? 'disabled' : ''}>${label}</button>`;
}

function factoryCard(row, items) {
  const effect = row.recipe.operations;
  const staff = row.employees.map((person) => `<p>${esc(person.name)} · ${number(person.salary_per_hour)} cash/ч ${command('FIRE', 'Уволить', `data-asset-id="${person.id}"`)}</p>`).join('');
  const fleet = row.vehicles.map((vehicle) => `<article><p><b>${esc(vehicle.name)}</b> · состояние ${number(vehicle.condition, 2)}%</p>${command('REPAIR', `Ремонт · ${number(vehicle.repair_cost)} cash`, `data-asset-id="${vehicle.id}"`, vehicle.condition >= 100)}${command('SCRAP', 'Списать без возврата стоимости', `data-asset-id="${vehicle.id}"`)}</article>`).join('');
  const employees = row.available_employees.map((person) => `<option value="${esc(person.id)}">${esc(person.name)} · ${number(person.hire_cost)} cash · +${number(person.output_bonus * person.quality * 100)}% выпуска · ${number(person.salary_per_hour)} cash/ч</option>`).join('');
  const vehicles = row.available_vehicles.map((vehicle) => `<option value="${esc(vehicle.id)}">${esc(vehicle.name)} · ${number(vehicle.cost)} cash · +${number(vehicle.output_bonus * 100)}% выпуска · ${number(vehicle.fuel_per_hour)} ${esc(items.get(vehicle.fuel_item)?.name || vehicle.fuel_item)}/ч · ${number(vehicle.maintenance_per_hour)} cash/ч</option>`).join('');
  const inputs = Object.entries(row.recipe.inputs).map(([id, amount]) => `${number(amount, 4)} ${esc(items.get(id)?.name || id)}`).join(', ');
  return `<details class="next-game-panel" data-operations-factory="${row.id}"><summary><b>${esc(row.name)}</b> · уровень ${number(row.level, 0)}</summary><p>За цикл: ${number(row.recipe.output_quantity, 4)} ${esc(items.get(row.recipe.output_item)?.name || row.recipe.output_item)}. Расход: ${inputs || 'сырьё не требуется'}. Затраты: ${number(row.recipe.operating_cost, 4)} cash.</p><p>Штат: +${number(effect.staff_bonus_pct)}% выпуска. Транспорт: +${number(effect.fleet_bonus_pct)}%. Автоматизация: −${number(effect.input_saving_pct)}% производственного сырья.</p>
    <details class="next-game-disclosure"><summary>Сотрудники · ${row.employees.length}/${row.staff_slots}</summary><p>Штат повышает выпуск. Зарплата начисляется за рабочие циклы, сырьё из-за найма не растёт.</p>${staff || '<p>Сотрудников пока нет.</p>'}${employees ? `<form data-operations-form="HIRE"><label>Должность<select name="kind">${employees}</select></label><button class="next-game-primary" ${row.employees.length >= row.staff_slots ? 'disabled' : ''}>Нанять</button></form>` : '<p>На текущем уровне доступные должности заняты или отсутствуют.</p>'}</details>
    <details class="next-game-disclosure"><summary>Автопарк · ${row.vehicles.length}/${row.fleet_slots}</summary><p>Транспорт повышает выпуск пропорционально состоянию. Каждый рабочий цикл расходует топливо, оплачивает обслуживание и изнашивает транспорт. При состоянии 0% бонус и расходы транспорта прекращаются.</p>${fleet || '<p>Транспорта пока нет.</p>'}${vehicles ? `<form data-operations-form="VEHICLE"><label>Транспорт<select name="kind">${vehicles}</select></label><button class="next-game-primary" ${row.vehicles.length >= row.fleet_slots ? 'disabled' : ''}>Купить транспорт</button></form>` : '<p>Автопарк недоступен этому предприятию.</p>'}</details>
    <details class="next-game-disclosure"><summary>Автоматизация · ${row.automation_level}/5</summary><p>Каждый уровень экономит 5% сырья исходного рецепта, до 25%. Топливо автопарка оплачивается полностью.</p><p>${cost(row.automation_quote, items)}</p>${command('AUTOMATION', 'Установить автоматизацию', '', !row.automation_quote)}</details>
    <details class="next-game-disclosure"><summary>Производственная лицензия · ${row.license_active ? 'действует' : 'не активна'}</summary><p>Лицензия технологии повышает выпуск на 10% в течение ${row.license_quote.days} дней. Сырьё и длительность цикла сохраняются.</p>${row.license_active ? `<p>Действует до ${esc(new Date(row.license_expires_at).toLocaleString('ru-RU'))}</p>` : `<p>${cost(row.license_quote, items)}</p>${command('LICENSE', 'Приобрести лицензию')}`}</details></details>`;
}

export function renderOperations(data) {
  const items = new Map(data.items.map((item) => [item.id, item]));
  const c = data.capacity;
  return `<section class="next-game-panel"><h2>Производственные активы</h2><p>${esc(data.policy)}</p><p>Cash компании: ${number(data.cash)}</p><details class="next-game-disclosure"><summary>Земля и производственные места · ${c.used_slots}/${c.production_slots}</summary><p>Расширение добавляет 4 места для предприятий. Уровень ${c.land_level}/10.</p><p>${cost(c.land_quote, items)}</p>${command('LAND', 'Расширить производственную площадку', '', !c.land_quote)}</details><details class="next-game-disclosure"><summary>Склад · ${number(c.warehouse_capacity, 0)} единиц каждого товара</summary><p>Расширение добавляет 50 000 единиц вместимости для каждого товара. Зарезервированные товары тоже занимают место. Уровень ${c.warehouse_level}/10.</p><p>${cost(c.warehouse_quote, items)}</p>${command('WAREHOUSE', 'Расширить склад', '', !c.warehouse_quote)}</details></section>${data.facilities.map((row) => factoryCard(row, items)).join('') || '<section class="next-game-panel"><p>Постройте предприятие на карте развития, чтобы управлять его штатом и транспортом.</p></section>'}`;
}

export async function renderNextGameOperations(container, state, showToast, refresh) {
  const data = await NatAPI.getNextGameOperations();
  container.innerHTML = renderOperations(data);
  async function run(button, payload) {
    button.disabled = true;
    try {
      await NatAPI.nextGameOperationsAction(payload);
      showToast('Производственные активы обновлены', 'success');
      await refresh();
    } catch (error) {
      showToast(error.message || 'Операция не выполнена', 'error');
      button.disabled = false;
    }
  }
  container.querySelectorAll('[data-operations-action]').forEach((button) => button.addEventListener('click', () => {
    const factory = button.closest('[data-operations-factory]');
    run(button, { action: button.dataset.operationsAction,
      ...(factory ? { facility_id: Number(factory.dataset.operationsFactory) } : {}),
      ...(button.dataset.assetId ? { asset_id: Number(button.dataset.assetId) } : {}) });
  }));
  container.querySelectorAll('[data-operations-form]').forEach((form) => form.addEventListener('submit', (event) => {
    event.preventDefault();
    run(form.querySelector('button'), { action: form.dataset.operationsForm,
      facility_id: Number(form.closest('[data-operations-factory]').dataset.operationsFactory),
      kind: new FormData(form).get('kind') });
  }));
}
