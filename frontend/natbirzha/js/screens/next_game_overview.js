import { esc, number, pathEntries, icon } from './next_game_common.js?v=20261011_v2_consolidation_v1';

function progressPercent(company, masteryRank) {
  if (masteryRank == null) {
    const gained = 1000 - Number(company.xp_to_next_level ?? 1000);
    return Math.max(0, Math.min(100, gained / 10));
  }
  const masteryXp = Number(company.xp || 0) - 59000 - masteryRank * 1000;
  return Math.max(0, Math.min(100, masteryXp / 10));
}

export function renderOverview(state) {
  const company = state.company;
  const facilities = state.facilities || [];
  const working = facilities.filter((facility) => facility.status === 'active').length;
  const blocked = facilities.filter((facility) => facility.status === 'blocked').length;
  const route = pathEntries(state);
  const latest = route.at(-1)?.branch;
  const masteryRank = Number(company.level) >= 60
    ? Math.max(0, Math.floor(((Number(company.xp) || 0) - 59000) / 1000))
    : null;
  const progress = progressPercent(company, masteryRank);
  const production = state.production || {};
  const autonomy = production.autonomy_seconds == null ? 'Без ограничений'
    : production.autonomy_seconds < 60 ? 'Меньше минуты' : `${number(production.autonomy_seconds / 3600, 1)} ч`;
  const nextAction = !company.sector_id ? 'Выбрать отрасль' : !route.length ? 'Выбрать первый завод'
    : !facilities.length ? 'Построить первый завод' : blocked ? 'Пополнить сырьё' : 'Продолжить развитие';
  const nextView = !company.sector_id || !route.length ? 'map' : !facilities.length ? 'factories' : blocked ? 'market' : 'map';
  const routeLabel = latest?.name || 'Отрасль ещё не выбрана';
  const xpRemaining = masteryRank == null
    ? `До следующего уровня ${number(company.xp_to_next_level, 0)} XP`
    : `До мастерства ${number(masteryRank + 1, 0)} · ${number(Math.max(0, 1000 - ((Number(company.xp) || 0) - 59000 - masteryRank * 1000)), 0)} XP`;
  const stateLabel = blocked ? ['is-warning', 'Нужно сырьё'] : facilities.length ? ['is-live', 'Производство работает'] : ['is-idle', 'Готово к запуску'];
  const productionPanel = `<section class="next-game-panel next-game-production-panel"><div class="next-game-section-heading"><span class="next-game-section-mark">${icon('factories', 20)}</span><div><span class="next-game-eyebrow">ПРОИЗВОДСТВО</span><h2>Ресурсы и выпуск</h2></div></div><div class="next-game-dashboard-grid"><article><span>Запаса сырья хватит</span><b>${facilities.length ? esc(autonomy) : 'Заводы не построены'}</b></article><article><span>Расчётная прибыль</span><b>${number(production.profit_per_hour || 0)} <small>cash/ч</small></b></article></div>${(production.shortages || []).slice(0, 3).map((item) => `<p class="next-game-blocked-reason">${esc(item.name)}: не хватает ${number(item.missing, 3)} ${esc(item.unit)}</p>`).join('')}</section>`;

  return `<section class="next-game-overview-card">
    <div class="next-game-overview-heading"><span class="next-game-overview-mark">${icon('activity', 23)}</span><div><span class="next-game-eyebrow">КОМПАНИЯ</span><h2>Операционная сводка</h2></div><span class="next-game-operating-state ${stateLabel[0]}"><i></i>${stateLabel[1]}</span></div>
    <button type="button" class="next-game-primary next-game-overview-action" data-next-view="${nextView}">${nextAction}<span aria-hidden="true">→</span></button>
    <div class="next-game-overview-finance"><div><span>Прогноз прибыли</span><strong>${number(production.profit_per_hour || 0)}</strong><small>cash-экв. в час · по ценам NPC</small></div><span class="next-game-finance-art">${icon('capital', 26)}</span></div>
    <div class="next-game-overview-metrics"><article><span>${icon('factories', 16)} Заводы в работе</span><b>${working}<small> / ${facilities.length}</small></b></article><article><span>${icon('energy', 16)} Автономность</span><b>${facilities.length ? esc(autonomy) : '—'}</b></article></div>
    <div class="next-game-overview-route"><div><span>МАРШРУТ РАЗВИТИЯ</span><b>${esc(routeLabel)}</b></div><span class="next-game-route-level">Ур. ${number(company.level, 0)}</span></div>
    <div class="next-game-progress" role="progressbar" aria-label="Прогресс уровня" aria-valuenow="${progress}" aria-valuemin="0" aria-valuemax="100"><span style="width:${progress}%"></span></div>
    <div class="next-game-overview-xp"><span>${route.length} этапов открыто</span><span>${esc(xpRemaining)}</span></div>
  </section>${productionPanel}<section class="next-game-panel next-game-economy-panel"><div class="next-game-section-heading"><span class="next-game-section-mark">${icon('cash', 20)}</span><div><span class="next-game-eyebrow">БЫСТРЫЙ ПЕРЕХОД</span><h2>Что дальше</h2></div></div><div class="next-game-quick-links"><button type="button" data-next-view="factories" class="next-game-secondary"><span>${icon('factories', 20)}</span><span><b>Открыть заводы</b><small>Производство, улучшения и склад</small></span><i aria-hidden="true">→</i></button><button type="button" data-next-view="market" class="next-game-secondary"><span>${icon('market', 20)}</span><span><b>Открыть биржу</b><small>Ресурсы, заявки и сделки</small></span><i aria-hidden="true">→</i></button></div></section>`;
}
