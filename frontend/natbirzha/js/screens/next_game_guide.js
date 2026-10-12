import { icon } from './next_game_common.js?v=20261012_player_guide_v1';

const FLOW = [
  ['factories', 'Построй', 'завод'],
  ['operations', 'Пополняй', 'сырьё'],
  ['activity', 'Получи', 'выпуск и XP'],
  ['cash', 'Заработай', 'cash'],
  ['map', 'Открой', 'следующий этап'],
];

const STEPS = [
  ['map', '1', 'Выбери путь', 'Во вкладке «Развитие» открой доступное направление. Карта показывает текущий этап и следующие варианты.'],
  ['factories', '2', 'Запусти завод', 'Во вкладке «Заводы» построй открытый завод. Циклы идут сами, пока хватает денег на расходы и сырья на складе.'],
  ['market', '3', 'Пополняй склад', 'Нажми на название сырья в карточке завода — биржа откроет именно этот товар. Сравни предложения и купи недостающее.'],
  ['cash', '4', 'Продай выпуск и расти', 'Выставь готовый товар для других компаний или продай доступному NPC. Следи за автономностью; автоулучшение поможет поднять завод до 9 уровня.'],
];

const FAQ = [
  ['Завод остановился — что делать?', 'Открой его карточку: там указано, чего не хватает. Нажми на сырьё, чтобы перейти к нужному товару на бирже.'],
  ['Почему прибыль меньше ожиданий?', 'Цикл тратит cash и ресурсы. Проверь расходы и запас сырья; менеджер уменьшает только расход cash, но не потребление ресурсов.'],
  ['Что искать в разделе «Ещё»?', 'Там собраны банк, инвестиции, облигации, сотрудники, помощь, договоры, рейтинг и военные действия. Это дополнительные инструменты, основной путь остаётся в четырёх вкладках.'],
];

function flowMarkup() {
  return FLOW.map(([glyph, title, caption], index) => `<li class="ng-guide-flow-step"><span class="ng-guide-flow-icon">${icon(glyph, 22)}</span><b>${title}</b><small>${caption}</small>${index < FLOW.length - 1 ? '<span class="ng-guide-flow-arrow" aria-hidden="true">›</span>' : ''}</li>`).join('');
}

function stepMarkup([glyph, number, title, description]) {
  return `<article class="ng-guide-step"><span class="ng-guide-step-number">${number}</span><span class="ng-guide-step-icon">${icon(glyph, 21)}</span><div><h3>${title}</h3><p>${description}</p></div></article>`;
}

export function renderNextGameGuide(container) {
  container.innerHTML = `<section class="next-game-view-heading ng-guide-heading"><div class="next-game-view-heading-top"><button type="button" data-next-view="more" class="next-game-back">← Ещё</button><span>БЫСТРЫЙ СТАРТ · 2.0</span></div><div class="next-game-view-title"><span>${icon('help', 23)}</span><div><h2>Как играть</h2><small>Короткий маршрут от первого завода до роста компании</small></div></div></section>
    <section class="next-game-panel ng-guide-hero"><div><span class="next-game-eyebrow">ЭКОНОМИКА В ДВУХ СЛОВАХ</span><h3>Производи. Торгуй. Развивайся.</h3><p>Заводы превращают сырьё в товары. Продажи приносят деньги, а развитие открывает новые производства.</p></div><ol class="ng-guide-flow" aria-label="Схема игрового цикла">${flowMarkup()}</ol></section>
    <section class="next-game-panel ng-guide-steps"><div class="ng-guide-section-title"><span class="next-game-eyebrow">ТВОИ ПЕРВЫЕ ШАГИ</span><h3>Начни с этого</h3></div>${STEPS.map(stepMarkup).join('')}<div class="ng-guide-shortcuts"><button type="button" data-next-view="map">Открыть развитие <span>→</span></button><button type="button" data-next-view="factories">Открыть заводы <span>→</span></button><button type="button" data-next-view="market">Открыть биржу <span>→</span></button></div></section>
    <section class="next-game-panel ng-guide-tips"><div class="ng-guide-section-title"><span class="next-game-eyebrow">ПОДСКАЗКИ</span><h3>Если что-то непонятно</h3></div><div class="ng-guide-faq">${FAQ.map(([question, answer]) => `<details><summary>${question}</summary><p>${answer}</p></details>`).join('')}</div></section>`;
}

export { FLOW, STEPS, FAQ };
