import { NatAPI } from '../api.js?v=20261010_active_production_v1';
import { esc, number } from './next_game_common.js?v=20261010_shell_v2';

const requests = new WeakMap();

export async function renderNextGameLiquidation(container, state, toast, refresh) {
  const api = state.nextGameAPI || NatAPI;
  const view = state.liquidationBrowser ||= { lotId: null };
  const token = {}; requests.set(container, token);
  container.innerHTML = '<section class="next-game-panel"><p role="status">Загружаем предприятия резервного банка…</p></section>';
  try {
    const data = await api.getNextGameLiquidation();
    if (requests.get(container) !== token) return;
    render(data);
  } catch (error) {
    if (requests.get(container) !== token) return;
    container.innerHTML = `<section class="next-game-panel"><h2>Продажа предприятий</h2><p role="alert">${esc(error.message)}</p><button data-liquidation-retry class="next-game-primary">Повторить</button></section>`;
    container.querySelector('[data-liquidation-retry]')?.addEventListener('click', () => renderNextGameLiquidation(container, state, toast, refresh));
  }
  function render(data) {
    const selected = data.lots.find((row) => row.id === Number(view.lotId));
    container.innerHTML = `<section class="next-game-panel"><button data-liquidation-bank class="next-game-back">← Банк</button><h2>Предприятия резервного банка</h2>
      <p>Готовые заводы после ликвидации. Для покупки нужно открыть соответствующую ветку и иметь свободное производственное место. На счёте ${number(data.cash, 2)} cash.</p>
      <div class="next-game-simple-list">${data.lots.map((row) => `<button data-liquidation-lot="${row.id}" class="next-game-bank-account"><span><b>${esc(row.name)} · ур. ${row.level}</b><small>${number(row.price, 2)} cash · ${row.already_owned ? 'Уже построен' : row.unlocked ? 'Ветка открыта' : 'Ветка ещё не открыта'}</small></span><span>›</span></button>`).join('') || '<p>Предприятий в продаже пока нет.</p>'}</div>
      ${selected ? `<article class="next-game-bank-loan"><h3>${esc(selected.name)}</h3><p>Уровень ${selected.level} сохраняется. Цена ${number(selected.price, 2)} cash поступает в резервный банк. Первый выпуск пройдет после обычного производственного цикла.</p><button data-liquidation-buy class="next-game-primary" ${!selected.unlocked || selected.already_owned || data.cash < selected.price ? 'disabled' : ''}>Купить за ${number(selected.price, 2)} cash</button></article>` : ''}</section>`;
    container.querySelector('[data-liquidation-bank]')?.addEventListener('click', () => state.navigateNextGame?.('bank'));
    container.querySelectorAll('[data-liquidation-lot]').forEach((button) => button.addEventListener('click', () => { view.lotId = Number(button.dataset.liquidationLot); render(data); }));
    container.querySelector('[data-liquidation-buy]')?.addEventListener('click', async (event) => {
      if (event.currentTarget.disabled) return;
      event.currentTarget.disabled = true;
      try { await api.buyNextGameLiquidationLot(selected.id); toast('Предприятие куплено', 'success'); view.lotId = null; if (refresh) await refresh(); else await renderNextGameLiquidation(container, state, toast); }
      catch (error) { toast(error.message || 'Не удалось купить предприятие', 'error'); render(data); }
    });
  }
}
