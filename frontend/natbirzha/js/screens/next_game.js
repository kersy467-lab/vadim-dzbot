import { NatAPI } from '../api.js?v=20261012_employee_cases_v1';
import { registerScreenCleanup } from '../screen_lifecycle.js?v=20260928_mobile_perf_v1';
import { esc, bindAction, icon } from './next_game_common.js?v=20261012_employee_cases_v1';
import { renderShell, renderHeader, renderMore, renderSubview } from './next_game_shell.js?v=20261012_employee_cases_v1';
import { renderOverview } from './next_game_overview.js?v=20261011_continuous_progression_v1';
import { renderDevelopment, bindDevelopment } from './next_game_development.js?v=20261012_route_continuation_v1';
import { renderFactories, bindFactories } from './next_game_factories.js?v=20261012_release_readiness_v1';

const entries = new WeakMap();
const initialRequests = new WeakMap();
let activeNextGameView = 'overview';

function retireSession(session) {
  session.releaseScreenCleanup?.();
  session.releaseScreenCleanup = null;
  session.version += 1;
  session.view = 'factories';
  activeNextGameView = 'factories';
  if (entries.get(session.container) === session) entries.delete(session.container);
}

function currentCreatorAccess() {
  const user = window.NatApp?.store?.user;
  const creatorButton = document.getElementById('creator-nav-btn');
  return Boolean(user?.is_creator === true || user?.role === 'admin'
    || (creatorButton && !creatorButton.classList.contains('hidden')));
}

function renderCompanyForm(container, showToast) {
  container.innerHTML = `<div class="next-game-screen">${renderHeader(null)}<section class="next-game-panel"><h2>Создай компанию</h2><p>В тестовом мире 2.0 у компании собственные заводы, cash и сохранение.</p><label for="next-game-company-name">Название компании</label><input id="next-game-company-name" maxlength="80" minlength="2" value="Новая корпорация"><button id="next-game-create" type="button" class="next-game-primary">Создать компанию</button></section></div>`;
  container.querySelector('[data-next-legacy]')?.addEventListener('click', () => window.NatApp?.navigateTo('overview'));
  bindAction(container, '#next-game-create', () => {
    const name = container.querySelector('#next-game-company-name')?.value.trim();
    if (!name || name.length < 2) throw new Error('Название должно быть не короче двух символов');
    return NatAPI.createNextGameCompany(name);
  }, () => renderNextGame(container, showToast), showToast, 'Компания создана');
}

async function loadSection(session, section) {
  if (session.loaded.has(section)) return;
  const version = session.version;
  const snapshot = await NatAPI.getNextGameMap(section);
  if (version !== session.version) return;
  // A section response omits other finance data; keep already loaded sections.
  const { banking, equity, ...base } = snapshot;
  Object.assign(session.state, base);
  if (section === 'bank') session.state.banking = banking;
  if (section === 'capital') session.state.equity = equity;
  session.loaded.add(section);
  const header = session.container.querySelector('.next-game-header');
  if (header) header.outerHTML = renderHeader(session.state, currentCreatorAccess());
}

async function renderFinance(content, session, view, refresh) {
  if (view === 'bank') {
    await loadSection(session, 'bank');
    const { renderBank, bindBankActions } = await import('./next_game_bank.js?v=20261010_shell_v2');
    content.innerHTML = renderSubview('Банк', renderBank(session.state));
    bindBankActions(content, session.showToast, session.state, refresh);
  } else if (view === 'capital') {
    await loadSection(session, 'capital');
    const { renderCapital, bindCapitalActions } = await import('./next_game_capital.js?v=20261010_shell_v2');
    content.innerHTML = renderSubview('Инвестиции', renderCapital(session.state));
    bindCapitalActions(content, session.state, session.showToast, refresh);
  } else {
    if (!session.loaded.has('competition')) {
      session.state.competition = await NatAPI.getNextGameCompetition();
      session.loaded.add('competition');
    }
    const { renderCompetition } = await import('./next_game_competition.js?v=20261010_shell_v2');
    content.innerHTML = renderSubview('Рейтинг', renderCompetition(session.state.competition));
    content.querySelector('[data-next-competition-retry]')?.addEventListener('click', () => {
      session.loaded.delete('competition');
      mountActive(session);
    });
  }
}

function refreshSessionState(session) {
  if (session.refreshPromise) return session.refreshPromise;
  const { container, state, showToast } = session;
  const task = NatAPI.getNextGameMap('overview').then((snapshot) => {
    if (entries.get(container) !== session) return null;
    if (snapshot.recovery?.requires_ack) {
      void renderNextGame(container, showToast);
      return null;
    }
    Object.assign(state, snapshot);
    session.updatedAt = Date.now();
    session.loaded.clear();
    const header = container.querySelector('.next-game-header');
    if (header) header.outerHTML = renderHeader(state, currentCreatorAccess());
    return snapshot;
  }).finally(() => {
    if (session.refreshPromise === task) session.refreshPromise = null;
  });
  session.refreshPromise = task;
  return task;
}

async function mountActive(session) {
  const version = ++session.version;
  const { container, state, showToast } = session;
  const view = session.view;
  const content = container.querySelector('[data-next-content]');
  if (!content) return;
  container.querySelectorAll('.next-game-nav [data-next-view]').forEach((button) => {
    const active = button.dataset.nextView === (['overview', 'map', 'factories', 'market', 'more'].includes(view) ? view : 'more');
    button.classList.toggle('is-active', active);
    if (active) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
  });
  const refresh = async () => {
    await refreshSessionState(session);
    if (entries.get(container) === session) await mountActive(session);
  };
  const redraw = () => mountActive(session);
  try {
    if (view === 'overview') content.innerHTML = renderOverview(state);
    else if (view === 'map') {
      content.innerHTML = renderDevelopment(state, session.development);
      bindDevelopment(content, state, session.development, NatAPI, showToast, refresh, redraw);
    } else if (view === 'factories') {
      content.innerHTML = renderFactories(state, session.factories);
      bindFactories(content, state, NatAPI, showToast, refresh, session.factories, redraw);
    } else if (view === 'more') content.innerHTML = renderMore(currentCreatorAccess());
    else {
      if (['admin', 'legacy-admin'].includes(view) && !currentCreatorAccess()) {
        throw new Error('Этот раздел доступен только администраторам');
      }
      content.innerHTML = '<section class="next-game-panel"><p role="status">Загрузка раздела…</p></section>';
      // Detached mount keeps a slow request from overwriting a newer selected tab.
      const target = document.createElement('div');
      target.className = 'next-game-module';
      if (view === 'war') {
        target.innerHTML = `<section class="next-game-legacy-view"><header class="next-game-view-heading"><div class="next-game-view-heading-top"><button type="button" data-next-view="more" class="next-game-back">← Все сервисы</button><span>0.6 · ВОЙНА</span></div><div class="next-game-view-title"><span>${icon('war', 23)}</span><div><h2>Военные действия</h2><small>Армия, границы, альянсы и турниры</small></div></div></header><div data-next-legacy-war></div></section>`;
        const { renderMilitary } = await import('./military.js?v=20261011_v2_consolidation_v1');
        await renderMilitary(target.querySelector('[data-next-legacy-war]'), showToast, { includePvcShop: false });
      } else if (['legacy-admin', 'legacy-moderation', 'legacy-sabotages', 'legacy-bonds'].includes(view)) {
        const legacyTabs = {
          'legacy-moderation': { tab: 'market', title: 'Модерация рынка' },
          'legacy-sabotages': { tab: 'sabotages', title: 'Саботажи' },
          'legacy-bonds': { tab: 'bonds', title: 'Гособлигации' },
        };
        const shortcut = legacyTabs[view];
        const title = shortcut ? `Панель основной игры · ${shortcut.title}` : 'Панель основной игры';
        target.innerHTML = `<section class="next-game-legacy-view"><header class="next-game-view-heading"><div class="next-game-view-heading-top"><button type="button" data-next-view="admin" class="next-game-back">← Управление 2.0</button><span>ИНСТРУМЕНТЫ · 1.5</span></div><div class="next-game-view-title"><span>${icon(shortcut?.tab === 'market' ? 'market' : shortcut?.tab === 'bonds' ? 'bonds' : shortcut?.tab === 'sabotages' ? 'war' : 'admin')}</span><div><h2>${title}</h2><small>Действия здесь относятся только к основной игре 1.5</small></div></div></header><div data-next-legacy-admin></div></section>`;
        const { renderCreator } = await import('./creator.js?v=20261012_admin_tools_v1');
        await renderCreator(target.querySelector('[data-next-legacy-admin]'), showToast, {
          ...(shortcut ? { initialTab: shortcut.tab } : {}),
          onExit: () => state.navigateNextGame?.('admin'),
        });
      } else if (view === 'market') {
        const { renderNextGameMarket } = await import('./next_game_market.js?v=20261012_market_flow_v1');
        await renderNextGameMarket(target, state, showToast, () => refreshSessionState(session));
      } else if (['bank', 'capital', 'competition'].includes(view)) await renderFinance(target, session, view, refresh);
      else if (view === 'bonds') {
        const { renderNextGameBonds } = await import('./next_game_bonds.js?v=20261010_shell_v2');
        await renderNextGameBonds(target, state, showToast, refresh);
      } else if (view === 'progression') {
        const { renderNextGameProgression } = await import('./next_game_progression.js?v=20261011_continuous_progression_v1');
        await renderNextGameProgression(target, state, showToast, refresh);
      } else if (view === 'liquidation') {
        const { renderNextGameLiquidation } = await import('./next_game_liquidation.js?v=20261010_shell_v2');
        await renderNextGameLiquidation(target, state, showToast, refresh);
      } else if (view === 'operations') {
        const { renderNextGameOperations } = await import('./next_game_operations.js?v=20261012_market_flow_v1');
        await renderNextGameOperations(target, state, showToast, refresh);
      } else if (view === 'employees') {
        const { renderNextGameEmployees } = await import('./next_game_employees.js?v=20261012_employee_cases_v1');
        await renderNextGameEmployees(target, showToast, NatAPI);
      } else if (view === 'civic') {
        const { renderNextGameCivic } = await import('./next_game_civic.js?v=20261010_shell_v2');
        await renderNextGameCivic(target, state, showToast, refresh);
      }
      else if (view === 'help') {
        const { renderNextGameSupport } = await import('./next_game_support.js?v=20261010_shell_v2');
        await renderNextGameSupport(target, state, showToast, refresh);
      } else if (view === 'contracts' || view === 'projects') {
        const { renderNextGameContracts } = await import('./next_game_contracts.js?v=20261012_release_readiness_v1');
        await renderNextGameContracts(target, state, showToast, refresh);
      } else if (view === 'admin') {
        const { renderNextGameAdmin } = await import('./next_game_admin.js?v=20261012_market_flow_v1');
        await renderNextGameAdmin(target, state, showToast, refresh);
      } else throw new Error('Раздел не найден');
      if (version !== session.version || entries.get(container) !== session) return;
      content.replaceChildren(target);
    }
  } catch (error) {
    if (version !== session.version) return;
    content.innerHTML = `<section class="next-game-panel"><h2>Раздел недоступен</h2><p class="next-game-blocked-reason">${esc(error.message || 'Не удалось загрузить данные')}</p><button type="button" data-next-retry class="next-game-primary">Повторить</button><button type="button" data-next-view="more" class="next-game-secondary">Открыть сервисы</button></section>`;
    content.querySelector('[data-next-retry]')?.addEventListener('click', redraw);
  }
}

function startSession(container, state, showToast) {
  const previous = entries.get(container);
  if (previous) retireSession(previous);
  const session = { container, state, showToast, view: activeNextGameView, loaded: new Set(), version: 0, development: {}, factories: { mode: 'map' }, updatedAt: Date.now(), refreshPromise: null };
  entries.set(container, session);
  session.releaseScreenCleanup = registerScreenCleanup(() => retireSession(session));
  const navigate = (view) => {
    if (view === 'projects' || view === 'contracts') state.partnershipView = view === 'projects' ? 'projects' : 'supply';
    if (session.view === 'market' && view !== 'market' && state.marketBrowser?.view === 'item') {
      state.marketBrowser.view = 'home';
      delete state.marketBrowser.itemId;
    }
    session.view = view;
    activeNextGameView = view;
    const needsOverviewSnapshot = ['overview', 'map', 'factories'].includes(view);
    const shouldRefresh = needsOverviewSnapshot && Date.now() - session.updatedAt > 30000;
    void mountActive(session);
    if (shouldRefresh) {
      void refreshSessionState(session).then(() => {
        if (entries.get(container) === session && ['overview', 'map', 'factories'].includes(session.view)) {
          return mountActive(session);
        }
      }).catch((error) => {
        if (entries.get(container) === session) showToast(error.message, 'error');
      });
    }
  };
  state.navigateNextGame = navigate;
  session.navigate = navigate;
  container.innerHTML = renderShell(state, session.view, currentCreatorAccess());
  container.querySelector('.next-game-screen').addEventListener('click', (event) => {
    const button = event.target.closest('[data-next-view], [data-next-legacy], [data-next-admin]');
    if (!button || button.disabled) return;
    if (button.hasAttribute('data-next-legacy')) window.NatApp?.navigateTo('overview');
    else if (button.hasAttribute('data-next-admin')) navigate('admin');
    else navigate(button.dataset.nextView);
  });
  container.querySelector('.next-game-screen').addEventListener('next-game-navigate', (event) => {
    if (event.detail?.view) navigate(event.detail.view);
  });
  return mountActive(session);
}

export async function renderNextGame(container, showToast = () => {}) {
  const previous = entries.get(container);
  if (previous) retireSession(previous);
  const token = {};
  initialRequests.set(container, token);
  entries.delete(container);
  container.innerHTML = '<div class="next-game-screen"><section class="next-game-panel"><p role="status">Загружаем компанию 2.0…</p></section></div>';
  try {
    const state = await NatAPI.getNextGameMap('overview');
    if (initialRequests.get(container) !== token) return;
    if (state.recovery?.requires_ack) {
      const { renderNextGameBankruptcy } = await import('./next_game_bankruptcy.js?v=20261010_shell_v2');
      container.innerHTML = '<div class="next-game-screen next-game-bankruptcy-screen"></div>';
      await renderNextGameBankruptcy(container.firstElementChild, state, showToast, () => renderNextGame(container, showToast));
    } else if (!state.company) renderCompanyForm(container, showToast);
    else await startSession(container, state, showToast);
  } catch (error) {
    if (initialRequests.get(container) !== token) return;
    container.innerHTML = `<div class="next-game-screen">${renderHeader(null)}<section class="next-game-panel"><h2>Не удалось открыть игру 2.0</h2><p class="next-game-blocked-reason">${esc(error.message)}</p><button type="button" id="next-game-retry" class="next-game-primary">Повторить</button></section></div>`;
    container.querySelector('[data-next-legacy]')?.addEventListener('click', () => window.NatApp?.navigateTo('overview'));
    container.querySelector('#next-game-retry')?.addEventListener('click', () => renderNextGame(container, showToast));
  }
}
