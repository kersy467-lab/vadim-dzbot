import { esc, number, pathEntries, icon } from './next_game_common.js?v=20261010_experience_v1';

export function renderOverview(state) {
  const company = state.company;
  const facilities = state.facilities || [];
  const active = facilities.filter((facility) => facility.status === 'active').length;
  const blocked = facilities.filter((facility) => facility.status === 'blocked').length;
  const route = pathEntries(state);
  const latest = route.at(-1)?.branch;
  const totalXp = Number(company.xp) || 0;
  const masteryRank = Number(company.level) >= 60
    ? Math.max(0, Math.floor((totalXp - 59000) / 1000))
    : null;
  const xpInLevel = Math.max(0, 1000 - Number(company.xp_to_next_level ?? 1000));
  const masteryXp = masteryRank == null ? 0 : totalXp - 59000 - masteryRank * 1000;
  const progress = masteryRank == null
    ? Math.max(0, Math.min(100, xpInLevel / 10))
    : Math.max(0, Math.min(100, masteryXp / 10));
  const nextAction = !company.sector_id ? 'Выбрать корпорацию' : !route.length ? 'Выбрать стартовую ветку' : !facilities.length ? 'Построить первый завод' : blocked ? 'Пополнить ресурсы' : 'Продолжить развитие';
  const nextView = !company.sector_id || !route.length ? 'map' : !facilities.length ? 'factories' : blocked ? 'market' : 'map';
  const production = state.production || {};
  const autonomy = production.autonomy_seconds == null ? 'Нет расхода ресурсов' : production.autonomy_seconds < 60 ? 'Меньше минуты' : `${number(production.autonomy_seconds / 3600, 1)} ч`;
  const productionPanel = `<section class="next-game-panel next-game-production-panel"><div class="next-game-section-heading"><span class="next-game-section-mark">${icon('factories', 20)}</span><div><span class="next-game-eyebrow">ПРОИЗВОДСТВЕННЫЙ ЦИКЛ</span><h2>Ресурсы и выпуск</h2></div></div><div class="next-game-dashboard-grid"><article><span>Автономность всех заводов</span><b>${facilities.length ? autonomy : 'Заводов ещё нет'}</b></article><article><span>Маржа при продаже NPC</span><b>${number(production.profit_per_hour || 0)} <small>cash/ч</small></b></article></div><p>${esc(production.method || 'Общий расход всех предприятий; продажи не включены в запас времени.')}</p><p>Маржа — оценка по ценам NPC до налога. Товар остаётся на складе до продажи.</p>${(production.shortages || []).slice(0, 5).map((item) => `<p class="next-game-blocked-reason">${esc(item.name)}: не хватает ${number(item.missing, 3)} ${esc(item.unit)} на общий цикл</p>`).join('')}</section>`;
  const activity = (state.recent_activity || []).slice(0, 8).map((row) => {
    const amount = Number(row.cash_change || 0);
    const cash = amount ? `${amount > 0 ? '+' : ''}${number(amount)} cash` : '';
    const goods = row.item_name && Number(row.quantity_change) ? `${row.quantity_change > 0 ? '+' : ''}${number(row.quantity_change, 3)} ${row.unit || ''} ${row.item_name}` : '';
    const when = row.created_at ? new Date(row.created_at).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' }) : '';
    const labels = {
      STARTUP_CAPITAL: ['Стартовый капитал', 'cash'], BUILD: ['Строительство завода', 'factories'],
      BUY: ['Покупка ресурса', 'market'], SELL: ['Продажа товара', 'market'],
      OPERATING_COST: ['Расходы производства', 'cash'], PRODUCTION_INPUT: ['Сырьё списано', 'factories'],
      PRODUCTION_OUTPUT: ['Выпуск товара', 'factories'], UPGRADE: ['Улучшение завода', 'progression'],
    };
    const [label, glyph] = labels[row.action] || [row.action || 'Операция', 'activity'];
    const positive = amount ? amount > 0 : Number(row.quantity_change || 0) >= 0;
    return `<li><span class="next-game-activity-icon" data-kind="${positive ? 'positive' : 'negative'}">${icon(glyph, 17)}</span><span class="next-game-activity-copy"><b>${esc(label)}</b><small>${esc(when)}</small></span><strong class="${positive ? 'is-positive' : 'is-negative'}">${esc(cash || goods || '—')}</strong></li>`;
  }).join('');
  const operatingState = blocked ? ['is-warning', 'Нужно сырьё'] : facilities.length ? ['is-live', 'Производство работает'] : ['is-idle', 'Готово к запуску'];
  const routeLabel = latest ? latest.name : 'Направление ещё не выбрано';
  const openedStages = route.length === 1 ? '1 этап открыт' : `${route.length} ${route.length >= 2 && route.length <= 4 ? 'этапа открыто' : 'этапов открыто'}`;
  const xpRemaining = masteryRank == null
    ? `До уровня ${number(company.xp_to_next_level, 0)} XP`
    : `До мастерства ${number(masteryRank + 1, 0)} · ${number(Math.max(0, 1000 - masteryXp), 0)} XP`;
  return `<section class="next-game-overview-card">
    <div class="next-game-overview-heading"><span class="next-game-overview-mark">${icon('activity', 23)}</span><div><span class="next-game-eyebrow">ПАНЕЛЬ КОМПАНИИ</span><h2>Операционная сводка</h2></div><span class="next-game-operating-state ${operatingState[0]}"><i></i>${operatingState[1]}</span></div>
    <button type="button" class="next-game-primary next-game-overview-action" data-next-view="${nextView}">${nextAction}<span aria-hidden="true">→</span></button>
    <div class="next-game-overview-finance"><div><span>Прогноз маржи</span><strong>${number(production.profit_per_hour || 0)}</strong><small>cash-экв. за час · по ценам NPC</small></div><span class="next-game-finance-art">${icon('capital', 26)}</span></div>
    <div class="next-game-overview-metrics"><article><span>${icon('factories', 16)} Заводы в работе</span><b>${active}<small> / ${facilities.length}</small></b></article><article><span>${icon('energy', 16)} Автономность</span><b>${facilities.length ? autonomy : '—'}</b></article></div>
    <div class="next-game-overview-route"><div><span>МАРШРУТ РАЗВИТИЯ</span><b>${esc(routeLabel)}</b></div><span class="next-game-route-level">Ур. ${number(company.level, 0)}</span></div>
    <div class="next-game-progress" role="progressbar" aria-label="Прогресс уровня" aria-valuenow="${progress}" aria-valuemin="0" aria-valuemax="100"><span style="width:${progress}%"></span></div>
    <div class="next-game-overview-xp"><span>${openedStages}</span><span>${xpRemaining}</span></div>
  </section>${productionPanel}<section class="next-game-panel next-game-economy-panel"><div class="next-game-section-heading"><span class="next-game-section-mark">${icon('cash', 20)}</span><div><span class="next-game-eyebrow">УПРАВЛЕНИЕ КОМПАНИЕЙ</span><h2>Быстрые действия</h2></div></div><p>Проверь выпуск, пополни склад или распредели свободный капитал.</p><div class="next-game-quick-links"><button type="button" data-next-view="factories" class="next-game-secondary"><span>${icon('factories', 20)}</span><span><b>Производство и склад</b><small>Заводы, запасы и улучшения</small></span><i aria-hidden="true">→</i></button><button type="button" data-next-view="market" class="next-game-secondary"><span>${icon('market', 20)}</span><span><b>Открыть биржу</b><small>Ресурсы, заявки и сделки</small></span><i aria-hidden="true">→</i></button></div></section><section class="next-game-panel next-game-activity"><div class="next-game-section-heading"><span class="next-game-section-mark is-gold">${icon('activity', 20)}</span><div><span class="next-game-eyebrow">ЖУРНАЛ КОМПАНИИ</span><h2>Последние операции</h2></div></div>${activity ? `<ul>${activity}</ul>` : '<p>Операций пока нет. Начни с карты развития.</p>'}</section>`;
}
