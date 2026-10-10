import { NatAPI } from '../api.js?v=20261010_shell_v2';
import { esc, number, bindAction } from './next_game_common.js?v=20261010_shell_v2';

function render(data) {
  const fusion = data.fusion || {};
  const sources = fusion.eligible_sources || [];
  const options = sources.map((source) => `<option value="${source.id}">${esc(source.name)} · ур. ${source.level}</option>`).join('');
  return `<section class="next-game-panel"><button type="button" data-next-view="more" class="next-game-back">← Ещё</button><h2>Развитие компании</h2><p>Общий множитель выпуска: <strong>×${number(data.production_multiplier, 3)}</strong>. Ресурсы и расходы цикла сохраняются.</p></section>
  <section class="next-game-panel"><h2>PVC-улучшения</h2><p>Баланс: <strong>${number(data.pvc_balance)} PVC</strong> · уровень ${data.pvc_level}/${data.max_pvc_level}. Бонус выпуска +${number(data.pvc_bonus_pct, 0)}%.</p><p>Каждый уровень добавляет 5% выпуска и оплачивается из вашего PVC-баланса.</p><button type="button" data-pvc-upgrade class="next-game-primary" ${data.pvc_upgrade_price == null || data.pvc_balance < data.pvc_upgrade_price ? 'disabled' : ''}>${data.pvc_upgrade_price == null ? 'Максимальный уровень' : `Улучшить за ${number(data.pvc_upgrade_price, 0)} PVC`}</button></section>
  <section class="next-game-panel"><h2>Мастерство</h2><p>Ранг ${data.mastery_rank} · бонус выпуска +${data.mastery_bonus_pct}%. После уровня 60 каждая следующая 1000 XP даёт ранг мастерства.</p><p>Следующий ранг: ${number(data.mastery_next_rank_xp, 0)} XP.</p></section>
  <section class="next-game-panel"><h2>Объединение заводов</h2><p>Объедините два предприятия уровня 5 или выше с одинаковым продуктом. Исходные предприятия заменяются одним комплексом: выпуск на 25% больше суммы их прежнего выпуска, входы и расходы складываются. Плата — 10% стоимости стройки, минимум 2500 cash.</p>${sources.length >= 2 ? `<label>Первое предприятие<select data-fusion-first>${options}</select></label><label>Второе предприятие<select data-fusion-second>${options}</select></label><button type="button" data-fusion-create class="next-game-primary">Объединить предприятия</button>` : '<p>Для объединения нужны два подходящих предприятия.</p>'}
  ${(fusion.mergers || []).map((merger) => `<article class="next-game-factory-card"><h3>${esc(merger.name)}</h3><p>${merger.sources.map((source) => `${esc(source.name || 'Исходное предприятие')} · ур. ${source.level}`).join(' + ')}</p><p>После разделения восстановятся прежние уровни источников. Плата объединения и улучшения комплекса не возвращаются.</p><button type="button" data-fusion-dissolve="${merger.id}" class="next-game-secondary">Разделить комплекс</button></article>`).join('')}</section>
  <section class="next-game-panel"><h2>Перерождение ${data.rebirths}/${data.max_rebirths}</h2><p>Каждое перерождение умножает выпуск на 1,25. Требуется построенное предприятие последней эпохи.</p><p>Уровень, XP, маршрут, заводы и склад сбрасываются. Деньги и товары передаются резерву; вклады закрываются, долги погашаются, чужие акции и кредитные требования передаются резервному банку. Свои акции и акционеры сохраняются, последняя котировка уменьшается в 100 раз. PVC и его улучшения сохраняются. Новый старт — 10000 cash из казны.</p><p>Облигации списываются в резерв без выплаты невыплаченных купонов. При нехватке cash на погашение долга перезапуск отменяется полностью.</p>${(data.rebirth_blockers || []).map((reason) => `<p class="next-game-blocked-reason">${esc(reason)}</p>`).join('')}<label><input type="checkbox" data-rebirth-confirm> Подтверждаю передачу активов и перезапуск компании</label><button type="button" data-rebirth-start class="next-game-primary" ${data.rebirth_ready ? '' : 'disabled'}>Переродиться</button></section>`;
}

export async function renderNextGameProgression(container, state, showToast, refresh) {
  const data = await NatAPI.getNextGameProgression();
  container.innerHTML = render(data);
  bindAction(container, '[data-pvc-upgrade]', () => NatAPI.upgradeNextGamePVC(), refresh, showToast, 'PVC-улучшение оплачено');
  bindAction(container, '[data-fusion-create]', () => {
    const first = Number(container.querySelector('[data-fusion-first]').value);
    const second = Number(container.querySelector('[data-fusion-second]').value);
    if (first === second) throw new Error('Выберите два разных предприятия');
    const a = data.fusion.eligible_sources.find((source) => source.id === first);
    const b = data.fusion.eligible_sources.find((source) => source.id === second);
    if (a.output_item !== b.output_item) throw new Error('У предприятий должен быть одинаковый конечный продукт');
    return NatAPI.fuseNextGameFactories([first, second]);
  }, refresh, showToast, 'Источники заменены объединённым комплексом');
  bindAction(container, '[data-fusion-dissolve]', (button) => NatAPI.dissolveNextGameFactories(Number(button.dataset.fusionDissolve)), refresh, showToast, 'Исходные предприятия восстановлены');
  bindAction(container, '[data-rebirth-start]', () => {
    if (!container.querySelector('[data-rebirth-confirm]').checked) throw new Error('Подтвердите передачу активов и перезапуск');
    return NatAPI.rebirthNextGameCompany(true);
  }, refresh, showToast, 'Компания начала новый цикл');
}
