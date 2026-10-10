import { esc, number, icon } from './next_game_common.js?v=20261010_shell_v2';

export const mainTabs = [
  ['overview', 'Обзор'], ['map', 'Развитие'], ['factories', 'Заводы'],
  ['market', 'Биржа'], ['more', 'Ещё'],
];

function normalizeState(stateOrCompany) {
  return stateOrCompany?.company
    ? stateOrCompany
    : { company: stateOrCompany || null, corporations: [], settings: {} };
}

function companyTicker(company) {
  if (company?.ticker) return String(company.ticker).toUpperCase().slice(0, 5);
  const initials = String(company?.name || '')
    .trim()
    .split(/[\s-]+/u)
    .filter(Boolean)
    .map((part) => Array.from(part)[0])
    .join('')
    .toUpperCase()
    .slice(0, 5);
  return initials || `НБ${company?.id || ''}`;
}

export function renderHeader(stateOrCompany, isCreator = false) {
  const state = normalizeState(stateOrCompany);
  const company = state.company;
  if (!company) {
    return `<header class="next-game-header"><div class="next-game-header-top"><button type="button" data-next-legacy class="next-game-back">← Основная игра</button><span class="next-game-world-label">Экономический мир 2.0</span></div><div class="next-game-brand-row"><div class="next-game-brand"><span class="next-game-brand-mark">НБ</span><span><b>НАТБИРЖА</b><small>11 «Б» · отдельный мир компаний</small></span></div></div></header>`;
  }

  const sector = (state.corporations || []).find((row) => row.id === company.sector_id);
  const sectorName = sector?.name || company.sector_name || 'Отрасль не выбрана';
  const level = Math.max(1, Number(company.level) || 1);
  const rebirths = Math.max(0, Number(state.settings?.rebirths ?? company.rebirths) || 0);
  const masteryRank = level >= 60 ? Math.max(0, Math.floor(((Number(company.xp) || 0) - 59000) / 1000)) : null;
  const rawXpToNext = company.xp_to_next_level ?? Math.max(0, 1000 - ((Number(company.xp) || 0) % 1000));
  const xpToNext = Math.max(0, Number(rawXpToNext) || 0);
  const levelProgress = level >= 60 ? 100 : Math.max(0, Math.min(100, 100 - xpToNext / 10));
  const masteryProgress = masteryRank == null ? 0 : Math.max(0, ((Number(company.xp) - 59000 - masteryRank * 1000) / 10));
  const tag = companyTicker(company);
  const stateButton = isCreator
    ? `<button type="button" class="next-game-admin-link" data-next-admin>${icon('state', 17)}<span>Панель государства</span></button>`
    : '';

  return `<header class="next-game-header" aria-label="Компания и игровой мир">
    <div class="next-game-header-top">
      <button type="button" data-next-legacy class="next-game-back">← Основная игра</button>
      <span class="next-game-world-label">Экономический мир 2.0</span>
    </div>
    <div class="next-game-brand-row">
      <div class="next-game-brand"><span class="next-game-brand-mark">НБ</span><span><b>НАТБИРЖА</b><small>11 «Б» · новая экономика</small></span></div>
      ${stateButton}
    </div>
    <section class="next-game-company-card" aria-label="Профиль компании">
      <div class="next-game-company-main">
        <span class="next-game-company-mark">${icon('factory', 24)}</span>
        <div class="next-game-company-details">
          <div class="next-game-company-tags"><span class="next-game-company-tag">[${esc(tag)}]</span><span class="next-game-sector-tag">${esc(sectorName)}</span></div>
          <h1>${esc(company.name)}</h1>
          <span class="next-game-company-number">Компания 2.0 · №${esc(company.id)}</span>
        </div>
        <div class="next-game-company-cash"><span>Баланс</span><b>${number(company.cash)}</b><small>cash</small></div>
      </div>
      <div class="next-game-company-stats">
        <span><small>Уровень</small><b>${number(level, 0)} <em>/ 60</em></b></span>
        <span><small>Перерождение</small><b>${number(rebirths, 0)} <em>/ 10</em></b></span>
        ${masteryRank == null ? '' : `<span><small>Мастерство</small><b>${number(masteryRank, 0)} <em>ранг</em></b></span>`}
      </div>
      <div class="next-game-company-progress" role="progressbar" aria-label="Прогресс уровня компании" aria-valuenow="${levelProgress}" aria-valuemin="0" aria-valuemax="100"><span style="width:${levelProgress}%"></span></div>
      ${masteryRank == null ? '' : `<div class="next-game-mastery-progress"><span><b>Мастерство ${number(masteryRank, 0)}</b><small>До следующего ранга</small></span><strong>${number(Math.max(0, 1000 - (Number(company.xp) - 59000 - masteryRank * 1000)), 0)} XP</strong><div role="progressbar" aria-label="Прогресс мастерства" aria-valuenow="${Math.min(100, masteryProgress)}" aria-valuemin="0" aria-valuemax="100"><span style="width:${Math.min(100, masteryProgress)}%"></span></div></div>`}
    </section>
  </header>`;
}

export function renderShell(stateOrCompany, activeView = 'overview', isCreator = false) {
  const state = normalizeState(stateOrCompany);
  const navView = mainTabs.some(([id]) => id === activeView) ? activeView : 'more';
  return `<div class="next-game-screen">${renderHeader(state, isCreator)}<div class="next-game-content" data-next-content aria-live="polite"></div><nav class="next-game-nav" aria-label="Разделы игры 2.0">${mainTabs.map(([id, label]) => `<button type="button" data-next-view="${id}" ${navView === id ? 'class="is-active" aria-current="page"' : ''}>${icon(id)}<span>${label}</span></button>`).join('')}</nav></div>`;
}

export function renderMore() {
  const groups = [
    ['Развитие', [['progression', 'Бонусы компании', 'Мастерство, ПИВОкоины и перерождение'], ['operations', 'Инфраструктура', 'Склад, земля, сотрудники и транспорт']]],
    ['Финансы', [['bank', 'Банк', 'Счета, кредиты и депозиты'], ['capital', 'Инвестиции', 'Акции компаний и IPO'], ['bonds', 'Облигации', 'Купоны и вторичный рынок'], ['civic', 'Заказы и налоги', 'Городской спрос и ежедневный расчёт']]],
    ['Партнёрство', [['contracts', 'Поставки', 'Договоры торговли между компаниями'], ['projects', 'Совместные заводы', 'Общий вклад и общий выпуск'], ['liquidation', 'Продажа предприятий', 'Имущество банкротов на вторичном рынке']]],
    ['Сообщество', [['competition', 'Рейтинг', 'Результаты компаний'], ['help', 'Помощь', 'Деньги и сырьё на любом уровне']]],
    ['Управление', [['admin', 'Администрирование', 'Состояние тестового мира']]],
  ];
  return `<section class="next-game-panel"><h2>Ещё</h2><p>Сервисы компании и правила игры.</p>${groups.map(([title, links]) => `<div class="next-game-more-group"><h3>${title}</h3><div class="next-game-more-grid">${links.map(([id, label, hint]) => `<button type="button" data-next-view="${id}" class="next-game-more-tile">${icon(id, 25)}<b>${label}</b><span>${hint}</span></button>`).join('')}</div></div>`).join('')}</section>`;
}

export function renderSubview(title, content) {
  return `<div class="next-game-subview"><button type="button" data-next-view="more" class="next-game-back">← Ещё</button><h2>${esc(title)}</h2></div>${content}`;
}
