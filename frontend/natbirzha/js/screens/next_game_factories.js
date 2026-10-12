import { esc, number, pathEntries, bindAction } from './next_game_common.js?v=20261011_continuous_progression_v1';
import { renderFactoryMap, bindFactoryMap, centerFactoryMapNode } from './next_game_factory_map.js?v=20261012_factory_map_v1';

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
    const name = item?.name || fallback?.name || id;
    const unit = item?.unit || fallback?.unit || '';
    const resourceIcon = globalThis.window?.NatIcons?.icon?.(`item:${id}`, 22) || '';
    return `<li><button type="button" class="next-game-factory-input" data-next-material="${esc(id)}" aria-label="Открыть биржу: ${esc(name)}"><span class="next-game-factory-input-icon" aria-hidden="true">${resourceIcon}</span><span class="next-game-factory-input-name">${esc(name)}</span><b>${number(quantity, 3)} ${esc(unit)}</b><small>На складе ${number(stock, 3)}${missing ? ` · нужно ещё ${number(missing, 3)}` : ''}</small><span class="next-game-factory-input-arrow" aria-hidden="true">›</span></button></li>`;
  }).join('');
}

function facilityCard({ branch, sector, index, facility, state, items, consumed }) {
  const searchText = `${sector.name} ${branch.name} ${branch.factory?.facility_name || ''} ${branch.factory?.output_name || ''}`.toLocaleLowerCase('ru-RU');
  if (!facility && consumed.has(branch.id)) {
    return `<article class="next-game-factory-card is-merged" data-factory-search-text="${esc(searchText)}"><div><span class="next-game-eyebrow">ЭТАП ${index + 1}</span><h3>${esc(branch.name)}</h3><p>Входит в объединённый комплекс.</p></div><button type="button" data-next-view="progression" class="next-game-secondary">Открыть объединение</button></article>`;
  }

  const recipe = facility?.recipe || branch.factory || {};
  const blocked = facility?.status === 'blocked';
  const status = facility ? blocked ? 'Остановлен' : 'Работает' : 'Не построен';
  const output = `${number(recipe.output_quantity, 3)} ${esc(recipe.output_unit || '')} ${esc(recipe.output_name || branch.outputs || '')}`;
  const minutes = Math.max(1, Math.ceil(Number(recipe.cycle_seconds || 60) / 60));
  const inputs = inputMarkup(recipe, items);
  const firstMissingInput = Object.entries(recipe.inputs || {}).find(([id, quantity]) =>
    Number(items.get(id)?.quantity || 0) + 1e-9 < Number(quantity))?.[0];
  const buildCost = Number(recipe.build_cost || 0);
  const canBuild = Number(state.company.cash || 0) >= buildCost;
  const canUpgrade = facility && facility.upgrade_cost != null
    && Number(state.company.level) >= Number(facility.required_company_level)
    && Number(state.company.cash) >= Number(facility.upgrade_cost);
  const pendingLevel = Number(facility?.upgrade_target_level || 0);
  const remaining = Number(facility?.upgrade_seconds_remaining || 0);
  const upgrade = pendingLevel
    ? `<div class="next-game-upgrade-pending"><b>Улучшение до ${number(pendingLevel, 0)} уровня</b><span>Осталось около ${number(remaining, 0)} сек.</span><small>Списано и учтено в казне: ${number(facility.upgrade_reserved_cash, 0)} cash. Завод пока работает на ${number(facility.level, 0)} уровне.</small></div>`
    : facility?.upgrade_cost != null
      ? `<button type="button" data-next-upgrade="${esc(branch.id)}" class="next-game-primary" ${canUpgrade ? '' : 'disabled'}>Начать улучшение до ${number(facility.upgrade_level, 0)} · ${number(facility.upgrade_cost, 0)} cash · ${number(facility.upgrade_duration_seconds, 0)} сек.</button><small>Нужен уровень компании ${number(facility.required_company_level, 0)}.</small>`
      : facility ? `<small class="next-game-factory-max">${Number(facility.level) === 50 ? 'Максимальный уровень 50' : 'Сохранённый уровень ' + number(facility.level, 0) + ' · предел улучшений 50'}</small>`
      : `<button type="button" data-next-build="${esc(branch.id)}" class="next-game-primary" ${canBuild ? '' : 'disabled'}>Построить · ${number(buildCost, 0)} cash</button>${canBuild ? '' : `<small>Не хватает ${number(buildCost - Number(state.company.cash || 0), 0)} cash.</small>`}`;
  const autonomy = facility ? autonomyLabel(estimateAutonomy(recipe, state)) : 'Пока не построен';

  return `<article class="next-game-factory-card ${blocked ? 'is-blocked' : facility ? 'is-working' : 'is-idle'}" data-factory-search-text="${esc(searchText)}">
    <div class="next-game-factory-card-head"><span class="next-game-factory-mark" aria-hidden="true">${index + 1}</span><div class="next-game-factory-title"><span class="next-game-eyebrow">ЭТАП ${index + 1} · ${esc(sector.name)}</span><h3>${esc(recipe.facility_name || branch.name)}</h3><p>${esc(branch.name)}</p></div><span class="next-game-status ${blocked ? 'is-blocked' : facility ? '' : 'is-idle'}">${status}</span></div>
    <div class="next-game-factory-output"><span>Выпуск за цикл</span><b>${output}</b><small>Каждые ${minutes} мин.</small></div>
    <div class="next-game-factory-details"><div><span>Уровень</span><b>${facility ? number(facility.level, 0) : '—'}</b></div><div><span>Автономность</span><b>${esc(autonomy)}</b></div><div><span>Расход</span><b>${number(recipe.operating_cost, 0)} cash/цикл</b></div></div>
    ${inputs ? `<details class="next-game-factory-inputs"><summary>Сырьё на цикл <span>${Object.keys(recipe.inputs || {}).length}</span></summary><ul>${inputs}</ul></details>` : '<p class="next-game-factory-no-inputs">Сырьё не требуется</p>'}
    ${facility?.blocked_reason ? `<p class="next-game-blocked-reason">Не хватает: ${esc(facility.blocked_reason)}</p><button type="button" ${firstMissingInput ? `data-next-material="${esc(firstMissingInput)}"` : 'data-next-view="market"'} class="next-game-secondary">${firstMissingInput ? 'Купить недостающее сырьё' : 'Открыть биржу'}</button>` : ''}
    <div class="next-game-factory-action">${upgrade}</div>
  </article>`;
}

function renderManagers(state) {
  const managers = state.managers || [];
  const facilities = state.facilities || [];
  const rarities = { common: 'обычный', rare: 'редкий', epic: 'эпический', legendary: 'легендарный' };
  const countWord = managers.length === 1 ? 'специалист'
    : managers.length % 10 >= 2 && managers.length % 10 <= 4
      && (managers.length % 100 < 12 || managers.length % 100 > 14) ? 'специалиста' : 'специалистов';
  const occupied = new Map(managers.filter((row) => row.branch_id).map((row) => [row.branch_id, row.id]));
  const cards = managers.map((manager) => {
    const choices = facilities.map((facility) => {
      const name = facility.name || facility.recipe?.facility_name || facility.branch_id;
      const busy = occupied.has(facility.branch_id) && occupied.get(facility.branch_id) !== manager.id;
      const selected = manager.branch_id === facility.branch_id ? ' selected' : '';
      const disabled = busy ? ' disabled' : '';
      return '<option value="' + esc(facility.branch_id) + '"' + selected + disabled + '>'
        + esc(name) + ' · ур. ' + number(facility.level, 0)
        + (busy ? ' · назначен другой менеджер' : '') + '</option>';
    }).join('');
    return '<article class="next-game-manager-card is-' + esc(manager.rarity) + '">'
      + '<div class="next-game-manager-card-heading"><span class="next-game-manager-seal">'
      + number(manager.production_bonus_pct, 0) + '%</span><div><b>' + esc(manager.name)
      + '</b><small>' + esc(rarities[manager.rarity] || manager.rarity) + ' · '
      + (manager.source === 'case'
        ? 'сотрудник ур. ' + number(manager.level, 0)
        : 'награда за ' + number(manager.reward_level, 0) + ' уровень') + '</small></div></div>'
      + '<p>Увеличивает выпуск на ' + number(manager.production_bonus_pct, 0)
      + '% за цикл. Расход cash и сырьё не растут.</p>'
      + '<label>Завод<select data-next-manager-select><option value="">Не назначен</option>'
      + choices + '</select></label><button type="button" data-next-manager-assign="'
      + manager.id + '" class="next-game-secondary">Сохранить назначение</button></article>';
  }).join('');
  const summary = managers.length
    ? '<div class="next-game-manager-grid">' + cards + '</div>'
    : '<p>Менеджеры гарантированно открываются на уровнях 5, 15, 30 и 45. Ближайший специалист: '
      + ([5, 15, 30, 45].find((level) => level > Number(state.company?.level || 1))
        || 'все награды получены') + '.</p>';
  return '<details class="next-game-panel next-game-manager-panel">'
    + '<summary class="next-game-manager-summary"><span class="next-game-manager-summary-title">'
    + '<span class="next-game-eyebrow">КОМАНДА И СПЕЦИАЛИСТЫ</span><b>Менеджеры заводов</b></span>'
    + '<span class="next-game-manager-summary-meta"><span class="next-game-manager-count">'
    + managers.length + ' ' + countWord + '</span><span class="next-game-manager-toggle" aria-hidden="true"></span></span></summary>'
    + '<div class="next-game-manager-content"><p>Назначьте специалиста на завод: он повышает выпуск на 8–10% без роста расходов и потребления сырья.</p>'
    + summary + '</div></details>';
}

export function renderFactories(state, options = {}) {
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
  const waiting = route.filter(({ branch }) => !facilities.has(branch.id) && !consumed.has(branch.id)).length;
  options.mode = options.mode === 'list' ? 'list' : 'map';
  const selected = route.find(({ branch }) => branch.id === options.selectedBranchId) || route.at(-1);
  options.selectedBranchId = selected.branch.id;
  const selectedIndex = route.indexOf(selected);
  const selectedCard = facilityCard({
    ...selected, index: selectedIndex, facility: facilities.get(selected.branch.id), state, items, consumed,
  });
  const modeButton = (mode, label) => `<button type="button" data-factory-mode="${mode}" aria-pressed="${options.mode === mode}">${label}</button>`;
  const view = options.mode === 'map'
    ? `<div class="next-game-factory-map-tools"><p>Перетаскивай схему; масштабируй щипком, колёсиком или кнопками.</p><div class="next-game-factory-map-zoom"><button type="button" data-factory-zoom-out aria-label="Отдалить карту">−</button><span data-factory-zoom-level>100%</span><button type="button" data-factory-zoom-in aria-label="Приблизить карту">+</button><button type="button" data-factory-map-fit>Сбросить вид</button></div></div>${renderFactoryMap(route, facilities, consumed, options.selectedBranchId)}<section class="next-game-factory-selected" data-factory-selected><div class="next-game-factory-selected-title"><span class="next-game-eyebrow">ВЫБРАННЫЙ ЗАВОД · ЭТАП ${selectedIndex + 1}</span><b>${esc(selected.branch.factory?.facility_name || selected.branch.name)}</b></div>${selectedCard}</section>`
    : `<div class="next-game-facility-list" data-factory-list>${cards}</div>`;

  return `<section class="next-game-factory-page">
    <header class="next-game-factory-intro"><span class="next-game-eyebrow">ПРОИЗВОДСТВЕННЫЙ ЦЕХ</span><h2>Заводы и склад</h2><p>Циклы идут автоматически. Улучшение занимает время, а до завершения завод продолжает работать на прежнем уровне.</p><div class="next-game-factory-counts"><span><b>${working}</b> работают</span><span><b>${stopped}</b> требуют ресурсов</span><span><b>${route.length}</b> этапа открыто</span></div></header>
    <label class="next-game-auto-setting"><input type="checkbox" data-next-auto-upgrade ${state.settings?.auto_upgrade ? 'checked' : ''}><span><b>Автоулучшение до 9 уровня</b><small>Покупает доступное улучшение, когда хватает cash и уровня компании.</small></span></label>
    <section class="next-game-factory-explorer"><div class="next-game-factory-explorer-top"><div><span class="next-game-eyebrow">ПЛАН ПРОИЗВОДСТВА</span><b>Открыто ${route.length} этапов · ${working} работают · ${stopped} остановлены · ${waiting} ожидают постройки</b></div><div class="next-game-factory-view-switch" role="group" aria-label="Вид заводов">${modeButton('map', 'Карта')}${modeButton('list', 'Список')}</div></div><label class="next-game-factory-search"><span>Найти завод</span><input type="search" data-factory-search value="${esc(options.query || '')}" placeholder="Название или продукция"></label>${view}<p class="next-game-factory-list-empty" data-factory-empty hidden>Заводы по этому запросу не найдены.</p></section>
    ${renderManagers(state)}
    ${inventoryMarkup(items)}
  </section>`;
}

export function bindFactories(container, state, api, showToast, refresh, options = {}, redraw = () => {}) {
  container.querySelectorAll('[data-factory-mode]').forEach((button) => button.addEventListener('click', () => {
    options.mode = button.dataset.factoryMode;
    redraw();
  }));
  if (options.mode === 'map') bindFactoryMap(container, options);
  const applySearch = (query) => {
    const normalized = String(query || '').trim().toLocaleLowerCase('ru-RU');
    const rows = [...container.querySelectorAll('[data-factory-search-text]')];
    rows.forEach((row) => {
      row.hidden = Boolean(normalized && !row.dataset.factorySearchText?.includes(normalized));
    });
    if (normalized && options.mode === 'map') {
      const match = container.querySelector('[data-factory-select]:not([hidden])');
      if (match) {
        options.selectedBranchId = match.dataset.factorySelect;
        centerFactoryMapNode(container, options, match);
      }
    }
    const empty = container.querySelector('[data-factory-empty]');
    if (empty) empty.hidden = !normalized || !rows.every((row) => row.hidden);
  };
  const search = container.querySelector('[data-factory-search]');
  if (search) {
    search.addEventListener('input', () => {
      options.query = search.value;
      applySearch(search.value);
    });
    applySearch(search.value);
  }
  container.querySelectorAll('[data-factory-select]').forEach((button) => button.addEventListener('click', async () => {
    if (Date.now() < Number(options.suppressFactoryMapClickUntil || 0)) return;
    options.selectedBranchId = button.dataset.factorySelect;
    await redraw();
    requestAnimationFrame(() => container.querySelector('[data-factory-selected]')?.scrollIntoView({
      block: 'nearest', behavior: 'smooth',
    }));
  }));
  const openMarketItem = (itemId) => {
    const market = state.marketBrowser ||= { view: 'home', category: 'needed', query: '' };
    market.view = 'item';
    market.itemId = itemId;
    market.category = 'needed';
    market.query = '';
    state.navigateNextGame?.('market');
  };
  container.querySelectorAll('[data-next-material]').forEach((button) => {
    button.addEventListener('click', () => openMarketItem(button.dataset.nextMaterial));
  });
  bindAction(container, '[data-next-build]', (button) => api.buildNextGameFacility(button.dataset.nextBuild), refresh, showToast, 'Завод построен');
  bindAction(container, '[data-next-upgrade]', (button) => api.upgradeNextGameFacility(button.dataset.nextUpgrade), refresh, showToast, 'Завод улучшен');
  container.querySelectorAll('[data-next-manager-assign]').forEach((button) => {
    button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        const managerId = Number(button.dataset.nextManagerAssign);
        const branchId = button.closest('.next-game-manager-card')
          ?.querySelector('[data-next-manager-select]')?.value || null;
        await api.assignNextGameManager(managerId, branchId);
        showToast('Назначение менеджера сохранено', 'success');
        await refresh();
      } catch (error) {
        button.disabled = false;
        showToast(error.message, 'error');
      }
    });
  });
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
