import { NatAPI } from '../api.js?v=20261010_shell_v2';
import { esc, bindAction } from './next_game_common.js?v=20261010_shell_v2';
import { renderShell, renderHeader, renderMore, renderSubview } from './next_game_shell.js?v=20261010_experience_v1';
import { renderOverview } from './next_game_overview.js?v=20261010_experience_v1';
import { renderDevelopment, bindDevelopment } from './next_game_development.js?v=20261010_shell_v2';
import { renderFactories, bindFactories } from './next_game_factories.js?v=20261010_shell_v2';

const entries = new WeakMap();
const initialRequests = new WeakMap();
let activeNextGameView = 'overview';

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
    const snapshot = await NatAPI.getNextGameMap('overview');
    if (snapshot.recovery?.requires_ack) return renderNextGame(container, showToast);
    Object.assign(state, snapshot);
    session.updatedAt = Date.now();
    session.loaded.clear();
    const header = container.querySelector('.next-game-header');
    if (header) header.outerHTML = renderHeader(state, currentCreatorAccess());
    await mountActive(session);
  };
  const redraw = () => mountActive(session);
  try {
    if (view === 'overview') content.innerHTML = renderOverview(state);
    else if (view === 'map') {
      content.innerHTML = renderDevelopment(state, session.development);
      bindDevelopment(content, state, session.development, NatAPI, showToast, refresh, redraw);
    } else if (view === 'factories') {
      content.innerHTML = renderFactories(state);
      bindFactories(content, state, NatAPI, showToast, refresh);
    } else if (view === 'more') content.innerHTML = renderMore();
    else {
      content.innerHTML = '<section class="next-game-panel"><p role="status">Загрузка раздела…</p></section>';
      // Detached mount keeps a slow request from overwriting a newer selected tab.
      const target = document.createElement('div');
      target.className = 'next-game-module';
      if (view === 'market') {
        const { renderNextGameMarket } = await import('./next_game_market.js?v=20261010_visual_recovery_v3');
        await renderNextGameMarket(target, state, showToast, refresh);
      } else if (['bank', 'capital', 'competition'].includes(view)) await renderFinance(target, session, view, refresh);
      else if (view === 'bonds') {
        const { renderNextGameBonds } = await import('./next_game_bonds.js?v=20261010_shell_v2');
        await renderNextGameBonds(target, state, showToast, refresh);
      } else if (view === 'progression') {
        const { renderNextGameProgression } = await import('./next_game_progression.js?v=20261010_shell_v2');
        await renderNextGameProgression(target, state, showToast, refresh);
      } else if (view === 'liquidation') {
        const { renderNextGameLiquidation } = await import('./next_game_liquidation.js?v=20261010_shell_v2');
        await renderNextGameLiquidation(target, state, showToast, refresh);
      } else if (view === 'operations') {
        const { renderNextGameOperations } = await import('./next_game_operations.js?v=20261010_shell_v2');
        await renderNextGameOperations(target, state, showToast, refresh);
      } else if (view === 'civic') {
        const { renderNextGameCivic } = await import('./next_game_civic.js?v=20261010_shell_v2');
        await renderNextGameCivic(target, state, showToast, refresh);
      }
      else if (view === 'help') {
        const { renderNextGameSupport } = await import('./next_game_support.js?v=20261010_shell_v2');
        await renderNextGameSupport(target, state, showToast, refresh);
      } else if (view === 'contracts' || view === 'projects') {
        const { renderNextGameContracts } = await import('./next_game_contracts.js?v=20261010_shell_v2');
        await renderNextGameContracts(target, state, showToast, refresh);
      } else if (view === 'admin') {
        const { renderNextGameAdmin } = await import('./next_game_admin.js?v=20261010_shell_v2');
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
  const session = { container, state, showToast, view: activeNextGameView, loaded: new Set(), version: 0, development: {}, updatedAt: Date.now() };
  entries.set(container, session);
  const navigate = (view) => {
    if (view === 'projects' || view === 'contracts') state.partnershipView = view === 'projects' ? 'projects' : 'supply';
    session.view = view;
    activeNextGameView = view;
    if (Date.now() - session.updatedAt > 30000) {
      const version = ++session.version;
      NatAPI.getNextGameMap('overview').then((snapshot) => {
        if (entries.get(container) !== session || version !== session.version) return;
        if (snapshot.recovery?.requires_ack) return renderNextGame(container, showToast);
        Object.assign(state, snapshot); session.updatedAt = Date.now(); session.loaded.clear();
        const header = container.querySelector('.next-game-header');
        if (header) header.outerHTML = renderHeader(state, currentCreatorAccess());
        return mountActive(session);
      }).catch((error) => {
        if (entries.get(container) !== session || version !== session.version) return;
        showToast(error.message, 'error'); mountActive(session);
      });
    } else mountActive(session);
  };
  state.navigateNextGame = navigate;
  container.innerHTML = renderShell(state, session.view, currentCreatorAccess());
  container.querySelector('.next-game-screen').addEventListener('click', (event) => {
    const button = event.target.closest('[data-next-view], [data-next-legacy], [data-next-admin]');
    if (!button || button.disabled) return;
    if (button.hasAttribute('data-next-legacy')) window.NatApp?.navigateTo('overview');
    else if (button.hasAttribute('data-next-admin')) window.NatApp?.navigateTo('creator');
    else navigate(button.dataset.nextView);
  });
  container.querySelector('.next-game-screen').addEventListener('next-game-navigate', (event) => {
    if (event.detail?.view) navigate(event.detail.view);
  });
  return mountActive(session);
}

export async function renderNextGame(container, showToast = () => {}) {
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
