import { NatAPI } from '../api.js?v=20261010_active_production_v1';
import { esc, number, icon } from './next_game_common.js?v=20261010_shell_v2';

export async function renderNextGameSupport(container, state, showToast, refresh) {
  const data = await NatAPI.getNextGameSupport();
  const options = (data.items || []).map((item) => `<option value="${esc(item.id)}">${esc(item.name)} · ${esc(item.unit)}</option>`).join('');
  const cards = (data.requests || []).map((row) => {
    const mine = row.company_id === data.company_id;
    const remaining = Math.max(0, row.goal - row.received);
    return `<article class="next-game-aid-card" data-aid="${row.id}"><div class="next-game-aid-heading"><h3>${esc(row.company_name)}</h3><span>${mine ? 'Ваш запрос' : 'Нужна помощь'}</span></div><b>${esc(row.name)} · ${number(remaining, 4)} ${esc(row.unit)}</b><p>${esc(row.description || 'Помогите пополнить оборотные средства и запустить производство.')}</p><progress max="${row.goal}" value="${row.received}" aria-label="Получено помощи"></progress><small>Получено ${number(row.received, 4)} из ${number(row.goal, 4)} ${esc(row.unit)}</small>${mine ? '<button type="button" data-aid-close class="next-game-secondary">Закрыть запрос</button>' : `<form data-aid-donate><label>Количество помощи<input name="quantity" type="number" min="${row.item_id ? '.0001' : '.01'}" step="${row.item_id ? '.0001' : '.01'}" max="${remaining}" value="${Math.min(remaining, row.item_id ? 10 : 1000)}" required></label><button class="next-game-primary">Помочь компании</button></form>`}</article>`;
  }).join('');
  container.innerHTML = `<section class="next-game-panel"><div class="next-game-dashboard-heading"><div><h2>${icon('help')} Помощь компаниям</h2><p>Деньги и ресурсы от других игроков. Доступна на любом уровне.</p></div></div><details class="next-game-disclosure"><summary>Попросить помощь</summary><form data-aid-create><label>Что необходимо<select name="item"><option value="">Деньги · cash</option>${options}</select></label><label>Сколько нужно<input name="goal" type="number" min=".0001" max="1000000000" step=".0001" value="10000" required></label><label>Для чего<textarea name="description" maxlength="240" placeholder="На сырьё для нового предприятия" required></textarea></label><button class="next-game-primary">Опубликовать запрос</button></form></details></section><section class="next-game-panel"><h2>Открытые запросы</h2>${cards ? `<div class="next-game-community-list">${cards}</div>` : '<p>Сейчас все компании обеспечены. Первый запрос появится здесь.</p>'}</section>`;
  const submit = (form, action, message) => form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = form.querySelector('button');
    button.disabled = true;
    try { await action(new FormData(form)); showToast(message, 'success'); await refresh(); }
    catch (error) { showToast(error.message, 'error'); button.disabled = false; }
  });
  submit(container.querySelector('[data-aid-create]'), (fields) => NatAPI.createNextGameAidRequest(
    fields.get('item') || null, fields.get('goal'), fields.get('description')), 'Запрос помощи опубликован');
  container.querySelectorAll('[data-aid-donate]').forEach((form) => submit(form,
    (fields) => NatAPI.donateNextGameAid(Number(form.closest('[data-aid]').dataset.aid), fields.get('quantity')), 'Помощь передана'));
  container.querySelectorAll('[data-aid-close]').forEach((button) => button.addEventListener('click', async () => {
    button.disabled = true;
    try { await NatAPI.closeNextGameAid(Number(button.closest('[data-aid]').dataset.aid)); await refresh(); }
    catch (error) { showToast(error.message, 'error'); button.disabled = false; }
  }));
}
