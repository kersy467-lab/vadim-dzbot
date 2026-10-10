import { esc, number, pathEntries, findBranch, bindAction } from './next_game_common.js?v=20261010_shell_v2';

function factoryFacts(branch) {
  const recipe = branch.factory || {};
  return `<span>${number(recipe.build_cost, 0)} cash на строительство</span><span>Выпуск: ${number(recipe.output_quantity, 3)} ${esc(recipe.output_unit)} ${esc(recipe.output_name)} / ${Math.ceil(Number(recipe.cycle_seconds || 0) / 60)} мин.</span>`;
}

function renderFork(state, route) {
  const last = route.at(-1);
  if (!last) return '';
  const consumed = new Set(state.consumed_branch_ids || []);
  const hasFacility = consumed.has(last.branch.id) || (state.facilities || []).some((facility) => facility.branch_id === last.branch.id);
  const targets = (last.branch.next_branch_ids || []).map((id) => findBranch(state.corporations, id)).filter(Boolean);
  if (!targets.length) return '<section class="next-game-panel"><h2>Финальный этап</h2><p>После строительства последнего предприятия доступно перерождение. Сохраняются PVC и права акционеров.</p><button type="button" data-next-view="progression" class="next-game-primary">Условия перерождения</button></section>';
  return `<section class="next-game-panel next-game-checkpoint"><span class="next-game-eyebrow">СЛЕДУЮЩИЙ ЭТАП</span><h2>Выбери направление</h2><p>Открытие требует построенного завода «${esc(last.branch.name)}» и указанного уровня компании.</p><div class="next-game-fork">${targets.map(({ sector, branch }) => {
    const requiredLevel = Math.max(route.length + 1, Number(branch.requirements?.company_level || 1));
    const canAdvance = hasFacility && Number(state.company.level) >= requiredLevel;
    return `<article class="next-game-graph-node is-upcoming"><div class="next-game-node-dot">${requiredLevel}</div><span class="next-game-eyebrow">${esc(sector.name)}${branch.epoch_name ? ` · ${esc(branch.epoch_name)}` : ''}</span><h3>${esc(branch.name)}</h3><div class="next-game-node-facts">${factoryFacts(branch)}<span>На цикл ${number(branch.factory.operating_cost, 0)} cash · нужен уровень ${requiredLevel}</span></div><button type="button" data-next-branch="${esc(branch.id)}" class="next-game-primary" ${canAdvance ? '' : 'disabled'}>Открыть ветку</button><button type="button" data-next-inspect="${esc(branch.id)}" class="next-game-text-button">Рецепт и дальнейшие пути</button></article>`;
  }).join('')}</div></section>`;
}

function renderBranchDetail(state, id) {
  const target = findBranch(state.corporations, id);
  if (!target) return '';
  const { branch, sector } = target;
  const recipe = branch.factory;
  const inputs = (recipe.input_items || []).map((item) => `${esc(item.name)} · ${number(item.quantity, 3)} ${esc(item.unit)}`).join('<br>') || 'Сырьё не требуется';
  const next = (branch.next_branch_ids || []).map((branchId) => findBranch(state.corporations, branchId)).filter(Boolean);
  return `<section class="next-game-panel next-game-branch-detail"><div class="next-game-dashboard-heading"><h2>${esc(branch.name)}</h2><button type="button" data-next-close-detail class="next-game-secondary" aria-label="Закрыть описание">×</button></div><p>${esc(sector.name)} · ${esc(branch.outputs)}</p><div class="next-game-node-facts">${factoryFacts(branch)}<span>Расход ${number(recipe.operating_cost, 0)} cash за цикл</span></div><div class="next-game-recipe"><b>Ресурсы на цикл</b><span>${inputs}</span></div><h3>Следующие направления</h3>${next.length ? `<div class="next-game-discovery-links">${next.map(({ branch: node }) => `<button type="button" data-next-inspect="${esc(node.id)}" class="next-game-secondary">${esc(node.name)} · ${number(node.factory.build_cost, 0)} cash</button>`).join('')}</div>` : '<p>Финальный этап этого направления.</p>'}</section>`;
}

function renderCatalog(state, options) {
  const sectorId = options.sectorId || state.company.sector_id || state.corporations?.[0]?.id;
  const query = String(options.query || '').toLocaleLowerCase('ru');
  const sector = (state.corporations || []).find((item) => item.id === sectorId);
  const branches = (sector?.branches || []).filter((branch) => !query || `${branch.name} ${branch.outputs} ${branch.factory?.output_name}`.toLocaleLowerCase('ru').includes(query));
  const page = Math.max(0, Math.min(Number(options.page || 0), Math.ceil(branches.length / 12) - 1));
  const visible = branches.slice(page * 12, page * 12 + 12);
  const route = new Set(state.company.branch_path || []);
  return `<section class="next-game-panel next-game-catalog"><h2>Все направления</h2><p>Исследуй ветки каждой корпорации. Открытие доступно по маршруту развития.</p><label for="next-game-catalog-sector">Корпорация</label><select id="next-game-catalog-sector" data-next-catalog-sector>${(state.corporations || []).map((row) => `<option value="${esc(row.id)}" ${row.id === sectorId ? 'selected' : ''}>${esc(row.name)} · ${row.branches?.length || 0} веток</option>`).join('')}</select><label for="next-game-catalog-search">Найти направление или товар</label><input id="next-game-catalog-search" data-next-catalog-search type="search" value="${esc(options.query)}" placeholder="Например, сталь или энергетика"><div class="next-game-catalog-grid">${visible.map((branch) => `<button type="button" class="next-game-catalog-node ${route.has(branch.id) ? 'is-selected' : ''}" data-next-inspect="${esc(branch.id)}"><b>${esc(branch.name)}</b><span>${branch.epoch_name ? `${esc(branch.epoch_name)} · ` : ''}${number(branch.factory.build_cost, 0)} cash</span><small>${route.has(branch.id) ? 'В вашем маршруте' : esc(branch.factory.output_name)}</small></button>`).join('') || '<p>Направлений с таким названием нет.</p>'}</div><div class="next-game-pagination"><span>${branches.length ? `${page * 12 + 1}–${Math.min((page + 1) * 12, branches.length)} из ${branches.length}` : '0 результатов'}</span><button type="button" data-next-catalog-page="${page - 1}" class="next-game-secondary" ${page ? '' : 'disabled'} aria-label="Предыдущие направления">←</button><button type="button" data-next-catalog-page="${page + 1}" class="next-game-secondary" ${(page + 1) * 12 < branches.length ? '' : 'disabled'} aria-label="Следующие направления">→</button></div></section>`;
}

export function renderDevelopment(state, options = {}) {
  const route = pathEntries(state);
  const facilities = new Set([...(state.facilities || []).map((facility) => facility.branch_id), ...(state.consumed_branch_ids || [])]);
  const selectedSector = (state.corporations || []).find((sector) => sector.id === state.company.sector_id);
  const initial = !state.company.sector_id ? `<section class="next-game-panel"><span class="next-game-eyebrow">ПЕРВОЕ РЕШЕНИЕ</span><h2>Выбери корпорацию</h2><p>Корпорация определит начальные производства. Будущие развилки могут вести в другие отрасли.</p><div class="next-game-sector-list">${(state.corporations || []).map((sector) => `<article class="next-game-sector"><h3>${esc(sector.name)}</h3><p>${esc(sector.description)}</p><button type="button" data-sector="${esc(sector.id)}" class="next-game-secondary">Выбрать корпорацию</button></article>`).join('')}</div></section>` : !route.length ? `<section class="next-game-panel"><h2>${esc(selectedSector?.name)}: стартовая ветка</h2><p>Сравни стоимость первого предприятия и выбери направление.</p><div class="next-game-fork">${(selectedSector?.branches || []).filter((branch) => branch.is_starting_branch).map((branch) => `<article class="next-game-graph-node"><h3>${esc(branch.name)}</h3><div class="next-game-node-facts">${factoryFacts(branch)}</div><button type="button" data-branch="${esc(branch.id)}" class="next-game-primary">Выбрать путь</button><button type="button" data-next-inspect="${esc(branch.id)}" class="next-game-text-button">Изучить направление</button></article>`).join('')}</div></section>` : '';
  const graph = route.length ? `<section class="next-game-panel"><span class="next-game-eyebrow">КАРТА РАЗВИТИЯ</span><h2>Твой маршрут</h2><p>${route.length} открытых этапов. Следующая развилка продолжает цепочку.</p><ol class="next-game-graph-route">${route.map(({ branch }, index) => `<li class="next-game-graph-node ${index === route.length - 1 ? 'is-current' : 'is-complete'}"><span class="next-game-node-dot">${index + 1}</span><div><span class="next-game-eyebrow">${branch.epoch_name ? esc(branch.epoch_name) : `ЭТАП ${index + 1}`}</span><h3>${esc(branch.name)}</h3><p>${facilities.has(branch.id) ? 'Завод построен' : `Завод: ${number(branch.factory.build_cost, 0)} cash`}</p><button type="button" data-next-inspect="${esc(branch.id)}" class="next-game-text-button">Посмотреть производство</button>${!facilities.has(branch.id) ? '<button type="button" data-next-view="factories" class="next-game-secondary">Построить завод</button>' : ''}</div></li>`).join('')}</ol></section>${renderFork(state, route)}` : '';
  return `${initial}${graph}${options.inspected ? renderBranchDetail(state, options.inspected) : ''}${renderCatalog(state, options)}`;
}

export function bindDevelopment(container, state, options, api, showToast, refresh, redraw) {
  bindAction(container, '[data-sector]', (button) => api.selectNextGameSector(button.dataset.sector), refresh, showToast);
  bindAction(container, '[data-branch]', (button) => api.selectNextGameBranch(button.dataset.branch), refresh, showToast, 'Стартовая ветка открыта');
  bindAction(container, '[data-next-branch]', (button) => api.advanceNextGameBranch(button.dataset.nextBranch), refresh, showToast, 'Новое направление добавлено в маршрут');
  container.querySelectorAll('[data-next-inspect]').forEach((button) => button.addEventListener('click', () => {
    options.inspected = button.dataset.nextInspect;
    redraw();
    container.querySelector('.next-game-branch-detail')?.scrollIntoView({ block: 'start', behavior: 'smooth' });
  }));
  container.querySelector('[data-next-close-detail]')?.addEventListener('click', () => { options.inspected = null; redraw(); });
  container.querySelector('[data-next-catalog-sector]')?.addEventListener('change', (event) => {
    options.sectorId = event.currentTarget.value; options.page = 0; redraw();
  });
  container.querySelector('[data-next-catalog-search]')?.addEventListener('input', (event) => {
    const cursor = event.currentTarget.selectionStart;
    options.query = event.currentTarget.value; options.page = 0; redraw();
    const input = container.querySelector('[data-next-catalog-search]');
    input?.focus(); input?.setSelectionRange(cursor, cursor);
  });
  container.querySelectorAll('[data-next-catalog-page]').forEach((button) => button.addEventListener('click', () => {
    options.page = Number(button.dataset.nextCatalogPage); redraw();
  }));
}
