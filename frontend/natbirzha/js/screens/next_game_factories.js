import { esc, number, pathEntries, bindAction } from './next_game_common.js?v=20261010_shell_v2';

export function estimateAutonomy(recipe, state) {
  const items = new Map((state.market || state.inventory || []).map((item) => [item.item_id, item]));
  const costs = Number(recipe.operating_cost || 0);
  let cycles = costs > 0 ? Math.floor(Number(state.company.cash || 0) / costs) : Infinity;
  const inputs = Object.entries(recipe.inputs || {});
  for (const [id, amount] of inputs) {
    if (Number(amount) > 0) cycles = Math.min(cycles, Math.floor(Number(items.get(id)?.quantity || 0) / amount));
  }
  return { cycles: Math.max(0, cycles), seconds: Math.max(0, cycles) * Number(recipe.cycle_seconds || 0) };
}

function autonomyLabel(estimate) {
  if (!Number.isFinite(estimate.cycles)) return 'Без ограничений по запасам';
  if (!estimate.cycles) return 'Запасов не хватает на один цикл';
  const minutes = Math.floor(estimate.seconds / 60);
  return `${number(estimate.cycles, 0)} циклов · ${minutes >= 60 ? `${number(minutes / 60, 1)} ч` : `${minutes} мин`}`;
}

export function renderFactories(state) {
  const route = pathEntries(state);
  if (!route.length) return '<section class="next-game-panel"><h2>Предприятия</h2><p>Выбери стартовую ветку на карте развития, чтобы построить первый завод.</p><button type="button" data-next-view="map" class="next-game-primary">Выбрать направление</button></section>';
  const items = new Map((state.market || state.inventory || []).map((item) => [item.item_id, item]));
  const facilities = new Map((state.facilities || []).map((facility) => [facility.branch_id, facility]));
  const consumed = new Set(state.consumed_branch_ids || []);
  const cards = route.map(({ sector, branch }, index) => {
    const facility = facilities.get(branch.id);
    if (!facility && consumed.has(branch.id)) return `<article class="next-game-facility-card"><h3>${esc(branch.name)}</h3><p>Предприятие входит в объединённый комплекс. Источники восстановятся при разделении комплекса.</p><button type="button" data-next-view="progression" class="next-game-secondary">Управлять объединением</button></article>`;
    const recipe = facility?.recipe || branch.factory;
    const inputRows = Object.entries(recipe.inputs || {}).map(([id, amount]) => {
      const item = items.get(id);
      const stock = Number(item?.quantity || 0);
      const short = Math.max(0, Number(amount) - stock);
      return `<li><span>${esc(item?.name || recipe.input_items?.find((row) => row.item_id === id)?.name || id)}</span><b>${number(amount, 3)} ${esc(item?.unit || '')}</b><small>Запас ${number(stock, 3)}${short ? ` · не хватает ${number(short, 3)}` : ''}</small></li>`;
    }).join('');
    const canUpgrade = facility && facility.upgrade_cost != null && Number(state.company.level) >= Number(facility.required_company_level) && Number(state.company.cash) >= Number(facility.upgrade_cost);
    const status = facility ? facility.status === 'blocked' ? ['is-blocked', 'Остановлен'] : ['', 'Работает'] : ['is-idle', 'Не построен'];
    const upgrade = facility?.upgrade_cost != null ? `<button type="button" data-next-upgrade="${esc(branch.id)}" class="next-game-secondary" ${canUpgrade ? '' : 'disabled'}>Улучшить до ур. ${number(facility.upgrade_level, 0)} · ${number(facility.upgrade_cost, 0)} cash</button><small>Нужен уровень компании ${number(facility.required_company_level, 0)}. Расход сырья не растёт.</small>` : '<small>Достигнут максимальный уровень завода.</small>';
    const buildCost = Number(recipe.build_cost || 0);
    return `<article class="next-game-facility-card"><div class="next-game-facility-heading"><div><span class="next-game-eyebrow">ЭТАП ${index + 1} · ${esc(sector.name)}</span><h3>${esc(recipe.facility_name)}</h3><p>${esc(branch.name)}</p></div><span class="next-game-status ${status[0]}">${status[1]}</span></div><div class="next-game-recipe"><b>Выпуск за цикл</b><span>${number(recipe.output_quantity, 3)} ${esc(recipe.output_unit)} ${esc(recipe.output_name)} · ${Math.ceil(recipe.cycle_seconds / 60)} мин.</span><b>Сырьё и расходы</b>${inputRows ? `<ul class="next-game-input-list">${inputRows}</ul>` : '<span>Сырьё не требуется</span>'}<span>${number(recipe.operating_cost, 0)} cash за цикл</span></div>${facility ? `<div class="next-game-facility-meta"><b>Автономность: ${autonomyLabel(estimateAutonomy(recipe, state))}</b><span>Запасы общие для всех заводов; оценка для этого производства.</span><span>Уровень ${number(facility.level, 0)} · бонус выпуска +${number((Number(facility.output_multiplier || 1) - 1) * 100, 0)}%</span><span>${facility.seconds_to_cycle > 0 ? `До цикла ≈ ${Math.ceil(facility.seconds_to_cycle / 60)} мин.` : 'Цикл готов при наличии ресурсов.'}</span></div>${facility.blocked_reason ? `<p class="next-game-blocked-reason">Не хватает для работы: ${esc(facility.blocked_reason)}</p><button type="button" data-next-view="market" class="next-game-primary">Пополнить ресурсы</button>` : ''}${upgrade}` : `<p>Стоимость строительства: ${number(buildCost, 0)} cash</p><button type="button" data-next-build="${esc(branch.id)}" class="next-game-primary" ${Number(state.company.cash) < buildCost ? 'disabled' : ''}>Построить завод</button>${Number(state.company.cash) < buildCost ? `<small>Не хватает ${number(buildCost - Number(state.company.cash), 0)} cash.</small>` : ''}`}</article>`;
  }).join('');
  const inventory = [...items.values()].filter((item) => Number(item.quantity) > 0).map((item) => `<li><span>${esc(item.name || item.item_id)}</span><b>${number(item.quantity, 3)} ${esc(item.unit)}</b></li>`).join('');
  return `<section class="next-game-panel"><h2>Производство</h2><p>Каждая ветка маршрута открывает отдельное предприятие.</p><button type="button" data-next-view="operations" class="next-game-secondary">Склад, сотрудники и транспорт</button><label class="next-game-auto-setting"><input type="checkbox" data-next-auto-upgrade ${state.settings?.auto_upgrade ? 'checked' : ''}><span><b>Автоулучшение до уровня 9</b><small>Раз в минуту покупать доступный уровень за cash при выполнении условий.</small></span></label><div class="next-game-facility-list">${cards}</div></section><section class="next-game-panel"><h2>Склад компании</h2>${inventory ? `<ul class="next-game-inventory">${inventory}</ul>` : '<p>Склад пуст. Пополни сырьё на рынке.</p>'}<button type="button" data-next-view="market" class="next-game-secondary">Открыть рынок</button></section>`;
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
