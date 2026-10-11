import { esc, number, pathEntries, findBranch, bindAction } from './next_game_common.js?v=20261011_v2_consolidation_v1';

function recipeSummary(branch) {
  const recipe = branch.factory || {};
  const cycle = Math.max(1, Math.ceil(Number(recipe.cycle_seconds || 60) / 60));
  return `${number(recipe.output_quantity, 3)} ${esc(recipe.output_unit || '')} ${esc(recipe.output_name || branch.outputs || '')} · ${cycle} мин.`;
}

function renderFork(state, route) {
  const current = route.at(-1);
  if (!current) return '';
  const hasFacility = (state.facilities || []).some((facility) => facility.branch_id === current.branch.id)
    || (state.consumed_branch_ids || []).includes(current.branch.id);
  const choices = (current.branch.next_branch_ids || []).map((id) => findBranch(state.corporations, id)).filter(Boolean);
  if (!choices.length) return `<section class="next-game-panel next-game-development-final"><span class="next-game-eyebrow">МАРШРУТ ЗАВЕРШЁН</span><h2>Открыт финальный этап</h2><button type="button" data-next-view="progression" class="next-game-secondary">Посмотреть перерождение</button></section>`;
  return `<section class="next-game-panel next-game-checkpoint"><div class="next-game-development-heading"><div><span class="next-game-eyebrow">СЛЕДУЮЩИЙ ШАГ</span><h2>Выбери направление</h2></div><span class="next-game-route-level">${choices.length} варианта</span></div><div class="next-game-fork">${choices.map(({ sector, branch }, index) => {
    const level = Math.max(route.length + 1, Number(branch.requirements?.company_level || 1));
    const available = hasFacility && Number(state.company.level) >= level;
    return `<article class="next-game-development-choice"><span class="next-game-choice-number">${String(index + 1).padStart(2, '0')}</span><div><span class="next-game-eyebrow">${esc(sector.name)} · УРОВЕНЬ ${level}</span><h3>${esc(branch.name)}</h3><p>${recipeSummary(branch)}</p><small>Строительство ${number(branch.factory.build_cost, 0)} cash · цикл ${number(branch.factory.operating_cost, 0)} cash</small></div><button type="button" data-next-branch="${esc(branch.id)}" class="next-game-primary" ${available ? '' : 'disabled'}>${available ? 'Открыть' : !hasFacility ? 'Сначала построй текущий завод' : 'Ещё рано'}</button><button type="button" data-next-inspect="${esc(branch.id)}" class="next-game-text-button">Рецепт</button></article>`;
  }).join('')}</div></section>`;
}

function renderBranchDetail(state, id) {
  const target = findBranch(state.corporations, id);
  if (!target) return '';
  const { branch, sector } = target;
  const recipe = branch.factory || {};
  const inputs = (recipe.input_items || []).map((item) => `${esc(item.name)} · ${number(item.quantity, 3)} ${esc(item.unit)}`).join('<br>') || 'Сырьё не требуется';
  const next = (branch.next_branch_ids || []).map((branchId) => findBranch(state.corporations, branchId)).filter(Boolean);
  return `<section class="next-game-panel next-game-branch-detail"><div class="next-game-development-heading"><div><span class="next-game-eyebrow">${esc(sector.name)}</span><h2>${esc(branch.name)}</h2></div><button type="button" data-next-close-detail class="next-game-secondary" aria-label="Закрыть рецепт">Закрыть</button></div><div class="next-game-recipe"><b>Выпуск</b><span>${recipeSummary(branch)}</span><b>Ресурсы на цикл</b><span>${inputs}</span><span>Расходы ${number(recipe.operating_cost, 0)} cash · постройка ${number(recipe.build_cost, 0)} cash</span></div><details class="next-game-next-choices"><summary>Куда можно развиваться дальше · ${next.length}</summary>${next.map(({ branch: item }) => `<button type="button" data-next-inspect="${esc(item.id)}" class="next-game-secondary">${esc(item.name)}</button>`).join('') || '<p>Это финальное направление.</p>'}</details></section>`;
}

function renderCatalog(state, options) {
  const sectorId = options.sectorId || state.company.sector_id || state.corporations?.[0]?.id;
  const query = String(options.query || '').toLocaleLowerCase('ru');
  const sector = (state.corporations || []).find((item) => item.id === sectorId);
  const branches = (sector?.branches || []).filter((branch) => !query || `${branch.name} ${branch.outputs} ${branch.factory?.output_name}`.toLocaleLowerCase('ru').includes(query));
  const page = Math.max(0, Math.min(Number(options.page || 0), Math.ceil(branches.length / 12) - 1));
  const visible = branches.slice(page * 12, page * 12 + 12);
  const route = new Set(state.company.branch_path || []);
  const rows = visible.map((branch) => `<button type="button" class="next-game-catalog-node ${route.has(branch.id) ? 'is-selected' : ''}" data-next-inspect="${esc(branch.id)}"><b>${esc(branch.name)}</b><span>${number(branch.factory.build_cost, 0)} cash · ${esc(branch.factory.output_name)}</span></button>`).join('');
  return `<details class="next-game-development-catalog" data-next-catalog-disclosure ${options.catalogOpen ? 'open' : ''}><summary><span><b>Вся карта направлений</b><small>Поиск по отраслям, заводам и товарам</small></span><i>${(state.corporations || []).reduce((total, item) => total + (item.branches?.length || 0), 0)} направлений</i></summary><div class="next-game-catalog-controls"><label for="next-game-catalog-sector">Отрасль<select id="next-game-catalog-sector" data-next-catalog-sector>${(state.corporations || []).map((row) => `<option value="${esc(row.id)}" ${row.id === sectorId ? 'selected' : ''}>${esc(row.name)}</option>`).join('')}</select></label><label for="next-game-catalog-search">Поиск<input id="next-game-catalog-search" data-next-catalog-search type="search" value="${esc(options.query)}" placeholder="Например, сталь"></label></div><div class="next-game-catalog-grid">${rows || '<p>Направлений с таким названием нет.</p>'}</div><div class="next-game-pagination"><span>${branches.length ? `${page * 12 + 1}–${Math.min((page + 1) * 12, branches.length)} из ${branches.length}` : '0 результатов'}</span><button type="button" data-next-catalog-page="${page - 1}" class="next-game-secondary" ${page ? '' : 'disabled'} aria-label="Предыдущие направления">←</button><button type="button" data-next-catalog-page="${page + 1}" class="next-game-secondary" ${(page + 1) * 12 < branches.length ? '' : 'disabled'} aria-label="Следующие направления">→</button></div></details>`;
}

export function renderDevelopment(state, options = {}) {
  const route = pathEntries(state);
  const owned = new Set([...(state.facilities || []).map((facility) => facility.branch_id), ...(state.consumed_branch_ids || [])]);
  const sector = (state.corporations || []).find((item) => item.id === state.company.sector_id);
  const initial = !state.company.sector_id
    ? `<section class="next-game-panel"><span class="next-game-eyebrow">ПЕРВОЕ РЕШЕНИЕ</span><h2>Выбери отрасль</h2><div class="next-game-sector-list">${(state.corporations || []).map((item) => `<button type="button" data-sector="${esc(item.id)}" class="next-game-sector"><b>${esc(item.name)}</b><span>${item.branches?.length || 0} предприятий</span></button>`).join('')}</div></section>`
    : !route.length ? `<section class="next-game-panel"><span class="next-game-eyebrow">СТАРТОВОЕ ПРОИЗВОДСТВО · ${esc(sector?.name || '')}</span><h2>С чего начнём?</h2><div class="next-game-fork">${(sector?.branches || []).filter((branch) => branch.is_starting_branch).map((branch) => `<article class="next-game-development-choice"><div><h3>${esc(branch.name)}</h3><p>${recipeSummary(branch)}</p><small>Строительство ${number(branch.factory.build_cost, 0)} cash</small></div><button type="button" data-branch="${esc(branch.id)}" class="next-game-primary">Выбрать</button><button type="button" data-next-inspect="${esc(branch.id)}" class="next-game-text-button">Рецепт</button></article>`).join('')}</div></section>` : '';
  const routeMarkup = route.length ? `<section class="next-game-panel next-game-development-route"><div class="next-game-development-heading"><div><span class="next-game-eyebrow">ВАША ЦЕПОЧКА</span><h2>${route.length} этапа развития</h2></div><span class="next-game-route-level">Уровень ${number(state.company.level, 0)}</span></div><ol class="next-game-graph-route">${route.map(({ branch }, index) => `<li class="next-game-development-step ${index === route.length - 1 ? 'is-current' : 'is-complete'}"><span class="next-game-choice-number">${String(index + 1).padStart(2, '0')}</span><div><span class="next-game-eyebrow">${esc(branch.epoch_name || `ЭТАП ${index + 1}`)}</span><h3>${esc(branch.name)}</h3><small>${owned.has(branch.id) ? 'Завод построен' : `Постройка ${number(branch.factory.build_cost, 0)} cash`} · ${esc(branch.factory.output_name)}</small></div><button type="button" data-next-inspect="${esc(branch.id)}" class="next-game-text-button">Состав</button>${!owned.has(branch.id) ? '<button type="button" data-next-view="factories" class="next-game-secondary">К заводам</button>' : ''}</li>`).join('')}</ol></section>${renderFork(state, route)}` : '';
  return `<section class="next-game-development"><header class="next-game-development-banner"><span class="next-game-eyebrow">СТРАТЕГИЯ КОМПАНИИ</span><h2>Развитие</h2><p>Выбирай отрасль, строй цепочку предприятий и открывай новые направления.</p></header>${initial}${routeMarkup}${options.inspected ? renderBranchDetail(state, options.inspected) : ''}${renderCatalog(state, options)}</section>`;
}

export function bindDevelopment(container, state, options, api, showToast, refresh, redraw) {
  bindAction(container, '[data-sector]', (button) => api.selectNextGameSector(button.dataset.sector), refresh, showToast);
  bindAction(container, '[data-branch]', (button) => api.selectNextGameBranch(button.dataset.branch), refresh, showToast, 'Стартовая ветка открыта');
  bindAction(container, '[data-next-branch]', (button) => api.advanceNextGameBranch(button.dataset.nextBranch), refresh, showToast, 'Новое направление добавлено в маршрут');
  container.querySelector('[data-next-catalog-disclosure]')?.addEventListener('toggle', (event) => {
    options.catalogOpen = event.currentTarget.open;
  });
  container.querySelectorAll('[data-next-inspect]').forEach((button) => button.addEventListener('click', () => {
    options.inspected = button.dataset.nextInspect;
    options.catalogOpen = Boolean(button.closest('[data-next-catalog-disclosure]'));
    redraw();
    container.querySelector('.next-game-branch-detail')?.scrollIntoView({ block: 'start', behavior: 'smooth' });
  }));
  container.querySelector('[data-next-close-detail]')?.addEventListener('click', () => { options.inspected = null; redraw(); });
  container.querySelector('[data-next-catalog-sector]')?.addEventListener('change', (event) => {
    options.sectorId = event.currentTarget.value;
    options.page = 0;
    options.catalogOpen = true;
    redraw();
  });
  container.querySelector('[data-next-catalog-search]')?.addEventListener('input', (event) => {
    const cursor = event.currentTarget.selectionStart;
    options.query = event.currentTarget.value;
    options.page = 0;
    options.catalogOpen = true;
    redraw();
    const input = container.querySelector('[data-next-catalog-search]');
    input?.focus();
    input?.setSelectionRange(cursor, cursor);
  });
  container.querySelectorAll('[data-next-catalog-page]').forEach((button) => button.addEventListener('click', () => {
    options.page = Number(button.dataset.nextCatalogPage);
    options.catalogOpen = true;
    redraw();
  }));
}
