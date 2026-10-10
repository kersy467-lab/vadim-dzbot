import { esc, number, icon } from './next_game_common.js?v=20261010_shell_v2';

export const mainTabs = [
  ['overview', 'Обзор'], ['map', 'Развитие'], ['factories', 'Заводы'],
  ['market', 'Биржа'], ['more', 'Ещё'],
];

export function renderHeader(company) {
  return `<header class="next-game-header"><div class="next-game-header-top"><button type="button" data-next-legacy class="next-game-back">← Основная игра</button><span class="next-game-kicker">НАТБИРЖА 2.0 · ТЕСТ</span></div>${company ? `<div class="next-game-company"><div><h1>${esc(company.name)}</h1><span>Компания #${esc(company.id)} · уровень ${number(company.level, 0)}</span></div><div class="next-game-cash"><b>${number(company.cash)}</b><span>cash</span></div></div>` : '<h1>НАТБИРЖА 2.0</h1>'}</header>`;
}

export function renderShell(company, activeView = 'overview') {
  const navView = mainTabs.some(([id]) => id === activeView) ? activeView : 'more';
  return `<div class="next-game-screen">${renderHeader(company)}<div class="next-game-content" data-next-content aria-live="polite"></div><nav class="next-game-nav" aria-label="Разделы игры 2.0">${mainTabs.map(([id, label]) => `<button type="button" data-next-view="${id}" ${navView === id ? 'class="is-active" aria-current="page"' : ''}>${icon(id)}<span>${label}</span></button>`).join('')}</nav></div>`;
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
