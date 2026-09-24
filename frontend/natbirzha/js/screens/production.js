import { NatAPI } from '../api.js';
import { store } from '../state.js';
import { getItemInfo } from '../items.js';
import { getBuildingName } from '../localization.js';
import { buildFactoryPages } from '../factory_map.js';
import { openCatalogModal } from './catalog.js';

let cachedRecipes = null;
let selectedPage = 1;
let cycleInterval = null;

async function getOrFetchRecipes() {
  if (cachedRecipes && Object.keys(cachedRecipes).length > 0) return cachedRecipes;
  try {
    const response = await NatAPI.getRecipes();
    if (response?.recipes) cachedRecipes = response.recipes;
  } catch (_) { /* the map still renders from the factory status */ }
  return cachedRecipes || {};
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[char]));
}

function parseDateMs(dateStr) {
  if (!dateStr) return 0;
  const normalized = typeof dateStr === 'string' ? dateStr.replace(' ', 'T') : dateStr;
  const time = new Date(normalized).getTime();
  return Number.isNaN(time) ? 0 : time;
}

function factoryType(factory) {
  return factory?.building_type || factory?.factory_type || '';
}

function recipeFor(factory, recipes, state = {}) {
  const f = factory;
  const bType = f.building_type || f.factory_type;
  const choices = Object.entries(recipes).filter(([, r]) => r.factory_type === bType);
  const selected = f.current_recipe
    || state.selectedRecipes?.[f.id]
    || f.default_recipe
    || choices[0]?.[0];
  return { id: selected, recipe: selected ? recipes[selected] : null, choices };
}

function recipeSelector(factory, selected) {
  if (selected.choices.length < 2) return '';
  const disabled = cycleState(factory).running || factory.automation_enabled ? 'disabled' : '';
  const options = selected.choices.map(([id, recipe]) => (
    `<option value="${escapeHtml(id)}" data-recipe-id="${escapeHtml(id)}" ${id === selected.id ? 'selected' : ''}>${escapeHtml(recipe.name || id)}</option>`
  )).join('');
  return `<label class="factory-recipe-picker flex items-center gap-1 text-[9px] text-slate-500"><span>Рецепт</span><select class="factory-recipe-select min-w-0 flex-1 rounded-md border border-slate-300 bg-white px-1 py-1 text-[10px] text-slate-800 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100" data-id="${factory.id}" aria-label="Выбрать рецепт для ${escapeHtml(factory.name || factory.building_type)}" ${disabled}>${options}</select></label>`;
}

function recipeSummary(recipe) {
  if (!recipe) return 'Рецепт появится после загрузки каталога';
  const input = Object.entries(recipe.inputs || {}).map(([id, amount]) => {
    const item = getItemInfo(id);
    return `${amount} ${item.unit} ${item.name}`;
  }).join(', ') || 'без затрат';
  const output = Object.entries(recipe.outputs || {}).map(([id, amount]) => {
    const item = getItemInfo(id);
    return `+${amount} ${item.unit} ${item.name}`;
  }).join(', ') || '—';
  return `📥 ${input} → 📤 ${output}`;
}

function cycleState(factory, nowMs = Date.now()) {
  const running = Boolean(factory?.cycle_ready_at || factory?.is_running);
  const readyAtMs = parseDateMs(factory?.cycle_ready_at);
  // remaining_seconds is only a server snapshot. Prefer the absolute deadline
  // so the first render and every subsequent tick stay in sync with real time.
  const remaining = readyAtMs > 0
    ? Math.max(0, Math.ceil((readyAtMs - nowMs) / 1000))
    : (typeof factory?.remaining_seconds === 'number' ? Math.max(0, factory.remaining_seconds) : 0);
  const ready = running && (readyAtMs > 0 ? remaining <= 0 : Boolean(factory?.is_ready));
  return { running, ready, remaining };
}

function recipeLines(recipe, direction) {
  if (!recipe) return '<span class="text-slate-400">Данные рецепта загружаются</span>';
  const values = Object.entries(recipe[direction] || {});
  if (!values.length) return '<span class="text-slate-400">Нет</span>';
  return values.map(([id, amount]) => {
    const item = getItemInfo(id);
    return `<span class="factory-detail-resource">${item.icon || '📦'} ${amount} ${item.unit} · ${escapeHtml(item.name)}</span>`;
  }).join('');
}

function detailedFactoryCard(factory, recipes, state) {
  const selected = recipeFor(factory, recipes, state);
  const recipe = selected.recipe;
  const hint = factory.start_hint || {};
  const efficiency = Math.round(Number(factory.efficiency || 1) * 100);
  const duration = Number(recipe?.duration || recipe?.base_duration || factory.cycle_duration || 60);
  return `<article class="factory-detail-card snap-start">
    <div class="flex items-start justify-between gap-2"><div><div class="text-base font-black">${escapeHtml(factory.name || factoryType(factory))}</div><div class="text-xs text-slate-500">Уровень завода: ${factory.level || 1} · эффективность ${efficiency}%</div></div><span class="text-2xl">${factory.icon || '🏭'}</span></div>
    <div class="factory-detail-section"><div class="factory-detail-label">Входные ресурсы</div><div class="factory-detail-resources">${recipeLines(recipe, 'inputs')}</div></div>
    <div class="factory-detail-section"><div class="factory-detail-label">Производит</div><div class="factory-detail-resources">${recipeLines(recipe, 'outputs')}</div></div>
    <div class="grid grid-cols-2 gap-2 text-xs"><div><span class="text-slate-500">Цикл</span><b class="block">${duration} сек.</b></div><div><span class="text-slate-500">Рабочие</span><b class="block">${factory.workers || 0} чел.</b></div><div><span class="text-slate-500">Рецепт</span><b class="block truncate">${escapeHtml(selected.recipe?.name || selected.id || '—')}</b></div><div><span class="text-slate-500">Статус</span><b class="block">${factory.automation_enabled ? '🤖 автомат' : '🖐️ вручную'}</b></div></div>
    <div class="rounded-xl bg-pink-50/70 dark:bg-fuchsia-950/30 p-2 text-xs"><b>Что нужно сейчас:</b> ${escapeHtml(hint.message || 'Можно запускать цикл')}</div>
  </article>`;
}

// The production mutation returns the authoritative absolute timestamps, but
// the status endpoint is fetched separately. Apply the mutation response
// immediately so the card cannot remain on its idle snapshot while the refresh
// request is in flight (or while the countdown interval is being restarted).
function applyCycleResult(factory, result) {
  if (!factory || result?.status !== 'running') return factory;
  factory.current_recipe = result.recipe_id || factory.current_recipe;
  factory.cycle_started_at = result.started_at || factory.cycle_started_at;
  factory.cycle_ready_at = result.ready_at || factory.cycle_ready_at;
  factory.is_running = true;
  factory.is_ready = false;
  const remaining = Number(result.remaining_seconds ?? result.duration_seconds);
  if (Number.isFinite(remaining) && remaining >= 0) {
    factory.remaining_seconds = remaining;
  }
  return factory;
}

function nextStep(action) {
  return {
    open_market: 'market', upgrade_workers: 'upgrades', open_premium: 'military',
    gain_xp: 'help', check_recipe: 'help', contact_creator: 'help'
  }[action] || null;
}

function automationStatus(factory) {
  const status = factory?.automation_status || 'MANUAL';
  const reason = factory?.automation_pause_reason || '';
  if (status === 'RUNNING') return { label: '🤖 Авто: работает', cls: 'text-emerald-600 dark:text-emerald-400' };
  if (status === 'IDLE') return { label: '🤖 Авто: ожидание запуска', cls: 'text-blue-600 dark:text-blue-400' };
  if (status === 'WAITING_COLLECTION') return { label: '📦 Авто: пауза — освободите склад', cls: 'text-amber-600 dark:text-amber-400' };
  if (status === 'WAITING_INPUTS') {
    let detail = reason || 'не хватает ресурсов';
    if (reason.startsWith('insufficient_')) {
      const item = getItemInfo(reason.replace('insufficient_', ''));
      detail = `не хватает: ${item.name}`;
    } else if (reason === 'automation_upgrade_required') {
      detail = 'нужен 1 уровень автоматизации';
    } else if (reason === 'company_level_required') {
      detail = 'нужен 6 уровень компании';
    }
    return { label: `⏸️ Авто: ${detail}`, cls: 'text-amber-600 dark:text-amber-400' };
  }
  return { label: '🖐️ Ручной режим', cls: 'text-slate-500' };
}

function factorySlot(factory, state) {
  if (!factory) {
    return `<button class="factory-slot factory-slot-empty factory-build-btn" type="button" aria-label="Построить завод">
      <span class="text-3xl leading-none">＋</span><span class="text-[10px] font-bold">Построить завод</span>
    </button>`;
  }

  const { running, ready, remaining } = cycleState(factory);
  const selected = recipeFor(factory, state.recipes, state);
  const hint = factory.start_hint || {};
  const step = nextStep(hint.next_action);
  const duration = Math.max(1, Number(selected.recipe?.duration || selected.recipe?.base_duration || factory.cycle_duration || 60));
  const progress = running && !ready ? Math.max(4, Math.min(96, Math.round((1 - remaining / duration) * 100))) : (ready ? 100 : 0);
  const statusClass = ready ? 'factory-slot-ready' : (running ? 'factory-slot-running' : '');
  const icon = factory.icon || (factory.specialization === 'agrarian' ? '🌾' : '🏭');
  const bType = factoryType(factory);
  const title = escapeHtml((factory.name && factory.name !== bType) ? factory.name : getBuildingName(bType));
  const status = ready ? '✅ Готово к сбору' : (running ? `⏳ ${remaining} сек.` : '⭕ Нажмите, чтобы запустить');
  const autoState = automationStatus(factory);
  const autoUnlocked = Boolean(factory.automation_unlocked || Number(factory.automation_level || 0) >= 1);
  const autoEnabled = Boolean(factory.automation_enabled);
  const autoControl = autoUnlocked
    ? `<button type="button" class="factory-automation-toggle w-full py-1.5 rounded-lg border ${autoEnabled ? 'border-emerald-500 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' : 'border-slate-300 dark:border-slate-700 text-slate-500'}" data-id="${factory.id}" data-enabled="${autoEnabled ? '1' : '0'}">${autoEnabled ? '🤖 Автоматизация: ВКЛ' : '🤖 Автоматизация: ВЫКЛ'}</button>`
    : `<div class="text-[9px] text-slate-500">🤖 Автоматизация: откройте прокачку с 6 ур. компании</div>`;
  const button = ready
    ? `<button type="button" class="factory-collect-btn w-full py-1.5 rounded-lg bg-emerald-600 text-white" data-id="${factory.id}">📦 Забрать</button>`
    : (running
      ? `<button type="button" class="factory-start-btn w-full py-1.5 rounded-lg bg-slate-500/70 text-white" data-id="${factory.id}" disabled>⏳ Выполняется</button>`
      : `<button type="button" class="factory-start-btn w-full py-1.5 rounded-lg bg-blue-600 text-white" data-id="${factory.id}">▶️ Запустить</button>`);

  return `<article class="factory-slot ${statusClass} factory-start-card" data-factory-id="${factory.id}" tabindex="0" role="button" aria-label="${title}">
    <div class="flex items-start justify-between gap-1"><span class="factory-slot-icon">${icon}</span><span class="factory-slot-meta">ур. ${factory.level || 1}</span></div>
    <div class="factory-slot-title" title="${title}">${title}</div>
    <div class="factory-slot-meta">${escapeHtml(status)}</div>
    <div class="factory-slot-progress"><span style="width:${progress}%"></span></div>
    <div class="factory-slot-meta truncate" title="${escapeHtml(recipeSummary(selected.recipe))}">${escapeHtml(recipeSummary(selected.recipe))}</div>
    ${recipeSelector(factory, selected)}
    <div class="text-[9px] font-semibold ${autoState.cls}" title="${escapeHtml(factory.automation_pause_reason || '')}">${escapeHtml(autoState.label)}</div>
    ${!running && hint.message ? `<div class="text-[9px] text-amber-700 dark:text-amber-300 truncate" title="${escapeHtml(hint.message)}">${escapeHtml(hint.message)}${step ? ` <button type="button" class="factory-next-step underline" data-tab="${step}">Что сделать?</button>` : ''}</div>` : ''}
    ${autoControl}
    ${button}
  </article>`;
}

function renderMap(root, state, showToast) {
  const pages = buildFactoryPages(state.factories, state.maxSlots);
  selectedPage = Math.max(1, Math.min(selectedPage, pages.length));
  const page = pages[selectedPage - 1];
  root.innerHTML = `<section class="factory-map ${page.biome.pageClass} space-y-2" data-page="${page.page}">
    <div class="flex items-center justify-between gap-2"><div><div class="text-sm font-black">${page.biome.title}</div><div class="text-[10px] text-slate-600 dark:text-slate-300">Территория ${page.page} · 9 мест</div></div><span class="text-[10px] font-bold px-2 py-1 rounded-full bg-white/55 dark:bg-slate-900/45">${state.factories.length}/${state.maxSlots} заводов</span></div>
    <div class="factory-map-grid">${page.slots.map((factory) => factorySlot(factory, state)).join('')}</div>
    <div class="factory-map-controls"><button type="button" class="factory-prev-page bg-white/60 dark:bg-slate-900/50" ${selectedPage <= 1 ? 'disabled' : ''}>‹</button><div class="factory-map-dots">${pages.map((entry) => `<span class="factory-map-dot ${entry.page === selectedPage ? 'active' : ''}"></span>`).join('')}</div><button type="button" class="factory-next-page bg-white/60 dark:bg-slate-900/50" ${selectedPage >= pages.length ? 'disabled' : ''}>›</button></div>
  </section>`;
  bindMap(root, state, showToast);
}

function bindMap(root, state, showToast) {
  root.querySelector('.factory-prev-page')?.addEventListener('click', () => { selectedPage -= 1; renderMap(root, state, showToast); });
  root.querySelector('.factory-next-page')?.addEventListener('click', () => { selectedPage += 1; renderMap(root, state, showToast); });
  root.querySelectorAll('.factory-build-btn').forEach((button) => button.addEventListener('click', () => {
    openCatalogModal(showToast, async () => refreshMap(root, state, showToast));
  }));
  root.querySelectorAll('.factory-next-step').forEach((button) => button.addEventListener('click', (event) => {
    event.stopPropagation();
    window.NatApp?.navigateTo(button.dataset.tab);
  }));
  root.querySelectorAll('.factory-automation-toggle').forEach((button) => button.addEventListener('click', async (event) => {
    event.stopPropagation();
    if (button.disabled) return;
    const factoryId = Number(button.dataset.id);
    const enable = button.dataset.enabled !== '1';
    button.disabled = true;
    const oldText = button.textContent;
    button.textContent = '⏳ Сохранение…';
    try {
      await NatAPI.setFactoryAutomation(factoryId, enable);
      if (enable) delete state.selectedRecipes[factoryId];
      showToast(enable ? 'Автоматизация включена' : 'Автоматизация выключена', 'success');
      await refreshMap(root, state, showToast);
    } catch (error) {
      showToast(error.message, 'error');
      button.disabled = false;
      button.textContent = oldText;
    }
  }));
  root.querySelectorAll('.factory-recipe-select').forEach((select) => {
    select.addEventListener('click', (event) => event.stopPropagation());
    select.addEventListener('change', (event) => {
      event.stopPropagation();
      state.selectedRecipes[select.dataset.id] = select.value;
      renderMap(root, state, showToast);
    });
  });
  root.querySelectorAll('.factory-start-btn, .factory-collect-btn').forEach((button) => button.addEventListener('click', async (event) => {
    event.stopPropagation();
    await mutateFactory(button, root, state, showToast);
  }));
  root.querySelectorAll('.factory-start-card').forEach((card) => card.addEventListener('click', async (event) => {
    if (event.target.closest('button') || event.target.closest('select')) return;
    const factory = state.factories.find((entry) => String(entry.id) === String(card.dataset.factoryId));
    if (factory && !cycleState(factory).running) await mutateFactory(card, root, state, showToast);
  }));
}

async function mutateFactory(button, root, state, showToast) {
  const factoryId = button.dataset?.id || button.closest('[data-factory-id]')?.dataset.factoryId;
  const factory = state.factories.find((entry) => String(entry.id) === String(factoryId));
  if (!factory || button.disabled) return;
  const selected = recipeFor(factory, state.recipes, state);
  button.disabled = true;
  const oldText = button.textContent;
  button.textContent = '⏳ Сохранение…';
  try {
    const result = await NatAPI.triggerProduction(factory.id, selected.id);
    applyCycleResult(factory, result);
    renderMap(root, state, showToast);
    bindCountdown(root, state, showToast);
    showToast(result.status === 'running' ? 'Цикл запущен!' : 'Продукция добавлена на склад!', 'success');
    await refreshMap(root, state, showToast);
  } catch (error) {
    showToast(error.message, 'error');
    button.disabled = false;
    button.textContent = oldText;
  }
}

async function refreshMap(root, state, showToast) {
  const [data, company] = await Promise.all([
    NatAPI.getProductionStatus(),
    NatAPI.getMyCompany().catch(() => null),
  ]);
  if (Array.isArray(data?.factories)) state.factories = data.factories;
  if (company) store.setCompany(company);
  renderMap(root, state, showToast);
  bindCountdown(root, state, showToast);
}

function openFactoryDetails(container, state) {
  const modal = container.querySelector('#factory-details-modal');
  if (!modal) return;
  modal.querySelector('.factory-details-list').innerHTML = state.factories.length
    ? state.factories.map((factory) => detailedFactoryCard(factory, state.recipes, state)).join('')
    : '<div class="text-sm text-slate-500">Заводов пока нет. Откройте Каталог.</div>';
  modal.classList.remove('hidden');
  modal.querySelector('.factory-details-close')?.focus();
}

function bindCountdown(root, state, showToast) {
  if (cycleInterval) clearInterval(cycleInterval);
  cycleInterval = setInterval(() => {
    const active = state.factories.some((factory) => {
      const cycle = cycleState(factory);
      return cycle.running && !cycle.ready;
    });
    if (!active) {
      clearInterval(cycleInterval);
      renderMap(root, state, showToast);
      return;
    }
    renderMap(root, state, showToast);
  }, 1000);
}

export async function renderProduction(container, showToast) {
  const [data, recipes] = await Promise.all([
    NatAPI.getProductionStatus().catch(() => null),
    getOrFetchRecipes(),
  ]);
  const factories = Array.isArray(data?.factories) ? data.factories : (store.factories || []);
  if (factories.length) store.updateCompany({ factories });
  const maxSlots = Number(data?.factory_slots?.max || store.company?.factory_slots?.max || data?.max_factory_slots || factories.length || 1);
  const state = { factories, recipes, maxSlots, selectedRecipes: {} };

  container.innerHTML = `<div class="space-y-4 max-w-md mx-auto p-4 pb-24 min-w-0 overflow-hidden">
    <div class="flex justify-between items-center gap-2"><div><h2 class="text-xl font-black">Заводы</h2><p class="text-xs text-slate-500">Нажмите на свободный завод, чтобы запустить цикл</p></div><div class="flex flex-wrap justify-end gap-2"><button id="factory-details-btn" type="button" class="factory-details-btn px-3 py-2 rounded-xl bg-pink-100 text-pink-700 dark:bg-fuchsia-900/70 dark:text-pink-100 text-xs font-bold">📋 Подробнее</button><button id="go-upgrades" type="button" class="px-3 py-2 rounded-xl bg-pink-100 text-pink-700 dark:bg-fuchsia-900/70 dark:text-pink-100 text-xs font-bold">⚡ Прокачка</button><button class="production-help-btn px-2 py-2 rounded-xl bg-pink-100 text-pink-700 dark:bg-fuchsia-900/70 dark:text-pink-100 text-xs font-bold" type="button" aria-label="Помощь по производству">?</button><button id="build" type="button" class="px-3 py-2 rounded-xl bg-blue-600 text-white text-xs font-bold">＋ Каталог</button></div></div>
    <div class="rounded-xl border border-blue-200 dark:border-blue-900 bg-blue-50/60 dark:bg-blue-950/20 px-3 py-2 text-[10px] text-slate-600 dark:text-slate-300">🤖 Автоматизация сама запускает и собирает циклы, но не покупает сырьё. Если чего-то не хватает или склад заполнен, завод остановится и покажет причину.</div>
    <div id="factory-map-container"></div>
    <div id="factory-details-modal" class="factory-details-modal hidden" role="dialog" aria-modal="true" aria-labelledby="factory-details-title"><div class="factory-details-panel"><div class="flex items-center justify-between gap-2"><div><h3 id="factory-details-title" class="text-lg font-black">Заводы подробно</h3><p class="text-xs text-slate-500">Проведите карточки вбок, чтобы посмотреть требования каждого завода.</p></div><button type="button" class="factory-details-close rounded-xl px-3 py-2 bg-pink-100 text-pink-700 dark:bg-fuchsia-900/70 dark:text-pink-100" aria-label="Закрыть подробности">✕</button></div><div class="factory-details-list"></div></div></div>
  </div>`;
  const mapRoot = container.querySelector('#factory-map-container');
  renderMap(mapRoot, state, showToast);
  bindCountdown(mapRoot, state, showToast);
  container.querySelector('#go-upgrades')?.addEventListener('click', () => window.NatApp?.navigateTo('upgrades'));
  container.querySelector('.production-help-btn')?.addEventListener('click', () => window.NatApp?.navigateTo('help'));
  container.querySelector('#factory-details-btn')?.addEventListener('click', () => openFactoryDetails(container, state));
  container.querySelector('.factory-details-close')?.addEventListener('click', () => container.querySelector('#factory-details-modal')?.classList.add('hidden'));
  container.querySelector('#build')?.addEventListener('click', () => openCatalogModal(showToast, async () => refreshMap(mapRoot, state, showToast)));
}
