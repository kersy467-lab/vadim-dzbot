import { esc, number, pathEntries, bindAction } from './next_game_common.js?v=20261011_v2_consolidation_v1';

export function estimateAutonomy(recipe, state) {
  const items = new Map((state.market || state.inventory || []).map((item) => [item.item_id, item]));
  let cycles = Number(recipe.operating_cost) > 0
    ? Math.floor(Number(state.company.cash || 0) / Number(recipe.operating_cost))
    : Infinity;
  for (const [id, amount] of Object.entries(recipe.inputs || {})) {
    if (Number(amount) > 0) cycles = Math.min(cycles, Math.floor(Number(items.get(id)?.quantity || 0) / amount));
  }
  const safeCycles = Math.max(0, cycles);
  return { cycles: safeCycles, seconds: safeCycles * Number(recipe.cycle_seconds || 0) };
}

function autonomyLabel(estimate) {
  if (!Number.isFinite(estimate.cycles)) return 'Без ограничений по запасам';
  if (!estimate.cycles) return 'Запасов не хватает на один цикл';
  const minutes = Math.floor(estimate.seconds / 60);
  return `${number(estimate.cycles, 0)} циклов · ${minutes >= 60 ? `${number(minutes / 60, 1)} ч` : `${minutes} мин`}`;
}

function inventoryMarkup(items) {
  const rows = [...items.values()].filter((item) => Number(item.quantity) > 0)
    .map((item) => `<li><span>${esc(item.name || item.item_id)}</span><b>${number(item.quantity, 3)} ${esc(item.unit || '')}</b></li>`)
    .join('');
  return `<details class="next-game-inventory-disclosure"><summary>Склад компании <span>${items.size} поз.</span></summary>${rows ? `<ul class="next-game-inventory">${rows}</ul>` : '<p>Склад пока пуст.</p>'}</details>`;
}

function inputMarkup(recipe, items) {
  return Object.entries(recipe.inputs || {}).map(([id, quantity]) => {
    const item = items.get(id);
    const fallback = recipe.input_items?.find((row) => row.item_id === id);
    const stock = Number(item?.quantity || 0);
    const missing = Math.max(0, Number(quantity) - stock);
    return `<li><span>${esc(item?.name || fallback?.name || id)}</span><b>${number(quantity, 3)} ${esc(item?.unit || fallback?.unit || '')}</b><small>На складе ${number(stock, 3)}${missing ? ` · нужно ещё ${number(missing, 3)}` : ''}</small></li>`;
  }).join('');
}

function facilityCard({ branch, sector, index, facility, state, items, consumed }) {
  if (!facility && consumed.has(branch.id)) {
    return `<article class="next-game-factory-card is-merged"><div><span class="next-game-eyebrow">ЭТАП ${index + 1}</span><h3>${esc(branch.name)}</h3><p>Входит в объединённый комплекс.</p></div><button type="button" data-next-view="progression" class="next-game-secondary">Открыть объединение</button></article>`;
  }

  const recipe = facility?.recipe || branch.factory || {};
  const blocked = facility?.status === 'blocked';
  const status = facility ? blocked ? 'Остановлен' : 'Работает' : 'Не построен';
  const output = `${number(recipe.output_quantity, 3)} ${esc(recipe.output_unit || '')} ${esc(recipe.output_name || branch.outputs || '')}`;
  const minutes = Math.max(1, Math.ceil(Number(recipe.cycle_seconds || 60) / 60));
  const inputs = inputMarkup(recipe, items);
  const buildCost = Number(recipe.build_cost || 0);
  const canBuild = Number(state.company.cash || 0) >= buildCost;
  const canUpgrade = facility && facility.upgrade_cost != null
    && Number(state.company.level) >= Number(facility.required_company_level)
    && Number(state.company.cash) >= Number(facility.upgrade_cost);
  const upgrade = facility?.upgrade_cost != null
    ? `<button type="button" data-next-upgrade="${esc(branch.id)}" class="next-game-primary" ${canUpgrade ? '' : 'disabled'}>Улучшить до ${number(facility.upgrade_level, 0)} уровня · ${number(facility.upgrade_cost, 0)} cash</button><small>Нужен уровень компании ${number(facility.required_company_level, 0)}.</small>`
    : facility ? '<small class="next-game-factory-max">Максимальный уровень</small>'
      : `<button type="button" data-next-build="${esc(branch.id)}" class="next-game-primary" ${canBuild ? '' : 'disabled'}>Построить · ${number(buildCost, 0)} cash</button>${canBuild ? '' : `<small>Не хватает ${number(buildCost - Number(state.company.cash || 0), 0)} cash.</small>`}`;
  const autonomy = facility ? autonomyLabel(estimateAutonomy(recipe, state)) : 'Пока не построен';

  return `<article class="next-game-factory-card ${blocked ? 'is-blocked' : facility ? 'is-working' : 'is-idle'}">
    <div class="next-game-factory-card-head"><span class="next-game-factory-mark" aria-hidden="true">${index + 1}</span><div class="next-game-factory-title"><span class="next-game-eyebrow">ЭТАП ${index + 1} · ${esc(sector.name)}</span><h3>${esc(recipe.facility_name || branch.name)}</h3><p>${esc(branch.name)}</p></div><span class="next-game-status ${blocked ? 'is-blocked' : facility ? '' : 'is-idle'}">${status}</span></div>
    <div class="next-game-factory-output"><span>Выпуск за цикл</span><b>${output}</b><small>Каждые ${minutes} мин.</small></div>
    <div class="next-game-factory-details"><div><span>Уровень</span><b>${facility ? number(facility.level, 0) : '—'}</b></div><div><span>Автономность</span><b>${esc(autonomy)}</b></div><div><span>Расход</span><b>${number(recipe.operating_cost, 0)} cash/цикл</b></div></div>
    ${inputs ? `<details class="next-game-factory-inputs"><summary>Сырьё на цикл <span>${Object.keys(recipe.inputs || {}).length}</span></summary><ul>${inputs}</ul></details>` : '<p class="next-game-factory-no-inputs">Сырьё не требуется</p>'}
    ${facility?.blocked_reason ? `<p class="next-game-blocked-reason">Не хватает: ${esc(facility.blocked_reason)}</p><button type="button" data-next-view="market" class="next-game-secondary">Пополнить склад</button>` : ''}
    <div class="next-game-factory-action">${upgrade}</div>
  </article>`;
}

export function renderFactories(state) {
  const route = pathEntries(state);
  if (!route.length) {
    return '<section class="next-game-panel"><span class="next-game-eyebrow">ПРОИЗВОДСТВО</span><h2>Заводы компании</h2><p>Сначала выбери первое направление развития.</p><button type="button" data-next-view="map" class="next-game-primary">Открыть развитие</button></section>';
  }

  const items = new Map((state.market || state.inventory || []).map((item) => [item.item_id, item]));
  const facilities = new Map((state.facilities || []).map((facility) => [facility.branch_id, facility]));
  const consumed = new Set(state.consumed_branch_ids || []);
  const cards = route.map(({ sector, branch }, index) => facilityCard({
    branch, sector, index, facility: facilities.get(branch.id), state, items, consumed,
  })).join('');
  const working = [...facilities.values()].filter((facility) => facility.status === 'active').length;
  const stopped = [...facilities.values()].filter((facility) => facility.status === 'blocked').length;

  return `<section class="next-game-factory-page">
    <header class="next-game-factory-intro"><span class="next-game-eyebrow">ПРОИЗВОДСТВЕННЫЙ ЦЕХ</span><h2>Заводы и склад</h2><p>Все циклы идут автоматически. Здесь видны выпуск, сырьё и стоимость улучшений.</p><div class="next-game-factory-counts"><span><b>${working}</b> работают</span><span><b>${stopped}</b> требуют ресурсов</span><span><b>${route.length}</b> этапа открыто</span></div></header>
    <label class="next-game-auto-setting"><input type="checkbox" data-next-auto-upgrade ${state.settings?.auto_upgrade ? 'checked' : ''}><span><b>Автоулучшение до 9 уровня</b><small>Покупает доступное улучшение, когда хватает cash и уровня компании.</small></span></label>
    <div class="next-game-facility-list">${cards}</div>
    ${inventoryMarkup(items)}
    <button type="button" data-next-view="operations" class="next-game-secondary next-game-factory-operations">Склад, сотрудники и транспорт</button>
  </section>`;
}

export function bindFactories(container, state, api, showToast, refresh) {
  bindAction(container, '[data-next-build]', (button) => api.buildNextGameFacility(button.dataset.nextBuild), refresh, showToast, 'Завод построен');
  bindAction(container, '[data-next-upgrade]', (button) => api.upgradeNextGameFacility(button.dataset.nextUpgrade), refresh, showToast, 'Завод улучшен');
  container.querySelector('[data-next-auto-upgrade]')?.addEventListener('change', async (event) => {
    const input = event.currentTarget;
    input.disabled = true;
    try {
      await api.updateNextGameSettings({ auto_upgrade: input.checked });
      await refresh();
    } catch (error) {
      input.checked = !input.checked;
      input.disabled = false;
      showToast(error.message, 'error');
    }
  });
}
