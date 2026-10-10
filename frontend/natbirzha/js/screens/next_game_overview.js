import { esc, number, pathEntries } from './next_game_common.js?v=20261010_shell_v2';

export function renderOverview(state) {
  const company = state.company;
  const facilities = state.facilities || [];
  const active = facilities.filter((facility) => facility.status === 'active').length;
  const blocked = facilities.filter((facility) => facility.status === 'blocked').length;
  const route = pathEntries(state);
  const latest = route.at(-1)?.branch;
  const xpInLevel = Math.max(0, 1000 - Number(company.xp_to_next_level ?? 1000));
  const progress = Math.max(0, Math.min(100, xpInLevel / 10));
  const nextAction = !company.sector_id ? 'Выбрать корпорацию' : !route.length ? 'Выбрать стартовую ветку' : !facilities.length ? 'Построить первый завод' : blocked ? 'Пополнить ресурсы' : 'Продолжить развитие';
  const nextView = !company.sector_id || !route.length ? 'map' : !facilities.length ? 'factories' : blocked ? 'market' : 'map';
  const actionNames = {
    STARTUP_CAPITAL: 'Стартовый капитал', BUILD: 'Строительство', BUY: 'Покупка ресурса',
    SELL: 'Продажа товара', OPERATING_COST: 'Расходы производства',
    PRODUCTION_INPUT: 'Списание сырья', PRODUCTION_OUTPUT: 'Выпуск товара', UPGRADE: 'Улучшение завода',
  };
  const production = state.production || {};
  const autonomy = production.autonomy_seconds == null ? 'Нет расхода ресурсов' : production.autonomy_seconds < 60 ? 'Меньше минуты' : `${number(production.autonomy_seconds / 3600, 1)} ч`;
  const productionPanel = `<section class="next-game-panel"><h2>Ресурсы и выпуск</h2><div class="next-game-dashboard-grid"><article><span>Автономность всех заводов</span><b>${facilities.length ? autonomy : 'Заводов ещё нет'}</b></article><article><span>Маржа при продаже NPC</span><b>${number(production.profit_per_hour || 0)} <small>cash/ч</small></b></article></div><p>${esc(production.method || 'Общий расход всех предприятий; продажи не включены в запас времени.')}</p><p>Маржа — оценка по ценам NPC до налога. Товар остаётся на складе до продажи.</p>${(production.shortages || []).slice(0, 5).map((item) => `<p class="next-game-blocked-reason">${esc(item.name)}: не хватает ${number(item.missing, 3)} ${esc(item.unit)} на общий цикл</p>`).join('')}</section>`;
  const activity = (state.recent_activity || []).slice(0, 8).map((row) => {
    const amount = Number(row.cash_change || 0);
    const cash = amount ? `${amount > 0 ? '+' : ''}${number(amount)} cash` : '';
    const goods = row.item_name && Number(row.quantity_change) ? `${row.quantity_change > 0 ? '+' : ''}${number(row.quantity_change, 3)} ${row.unit || ''} ${row.item_name}` : '';
    const when = row.created_at ? new Date(row.created_at).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' }) : '';
    return `<li><span>${esc(actionNames[row.action] || row.action)}</span><b>${esc(cash || goods || '—')}</b><time>${esc(when)}</time></li>`;
  }).join('');
  return `<section class="next-game-panel next-game-dashboard"><div class="next-game-dashboard-heading"><div><span class="next-game-eyebrow">ВАША КОМПАНИЯ</span><h2>Пульс производства</h2></div><span class="next-game-level">Ур. ${number(company.level, 0)}</span></div><div class="next-game-dashboard-grid"><article><span>Работают</span><b>${active} <small>/ ${facilities.length} заводов</small></b></article><article><span>Нужны ресурсы</span><b>${blocked} <small>заводов</small></b></article><article><span>Открыто этапов</span><b>${route.length}</b></article><article><span>До уровня</span><b>${number(company.xp_to_next_level, 0)} <small>XP</small></b></article></div><div class="next-game-progress" role="progressbar" aria-label="Прогресс уровня" aria-valuenow="${progress}" aria-valuemin="0" aria-valuemax="100"><span style="width:${progress}%"></span></div><p>${latest ? `Текущее направление: ${esc(latest.name)}` : 'Первое решение — выбрать корпорацию и производственную ветку.'}</p><button type="button" class="next-game-primary" data-next-view="${nextView}">${nextAction}</button></section>${productionPanel}<section class="next-game-panel"><h2>Экономика компании</h2><p>Заводы используют сырьё и cash каждый цикл. На рынке можно пополнять запас и продавать выпуск.</p><div class="next-game-quick-links"><button type="button" data-next-view="factories" class="next-game-secondary">Производство и склад</button><button type="button" data-next-view="bank" class="next-game-secondary">Банк и финансирование</button></div></section><section class="next-game-panel next-game-activity"><h2>Последние операции</h2>${activity ? `<ul>${activity}</ul>` : '<p>Операций пока нет. Начни с карты развития.</p>'}</section>`;
}
