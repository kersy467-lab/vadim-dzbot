import { NatAPI } from '../api.js?v=20261010_shell_v2';
import { esc, number, icon, bindAction } from './next_game_common.js?v=20261010_shell_v2';

const statusNames = { OPEN: 'Предложение', ACTIVE: 'Действует', COMPLETED: 'Выполнен', CANCELLED: 'Закрыт', EXPIRED: 'Срок истёк' };

function actions(row) {
  if (row.status === 'OPEN') return `<div class="next-game-quick-links">${row.can_accept ? `<button type="button" data-partner-respond="${row.id}" data-kind="${row.kind}" data-accept="true" class="next-game-primary">Принять</button><button type="button" data-partner-respond="${row.id}" data-kind="${row.kind}" data-accept="false" class="next-game-secondary">Отклонить</button>` : `<button type="button" data-partner-cancel="${row.id}" data-kind="${row.kind}" class="next-game-secondary">Отозвать предложение</button>`}</div>`;
  if (row.status === 'ACTIVE') return `<button type="button" data-partner-cancel="${row.id}" data-kind="${row.kind}" class="next-game-secondary">${row.kind === 'supply' ? 'Завершить и вернуть остаток резерва' : 'Остановить совместный завод'}</button>`;
  return '';
}

function supplyCard(row) {
  return `<article class="next-game-facility-card"><div class="next-game-facility-heading"><div><span class="next-game-eyebrow">ПОСТАВКА #${row.id}</span><h3>${icon('market', 18)} ${esc(row.item_name)}</h3></div><span class="next-game-status ${row.status === 'OPEN' ? 'is-idle' : ''}">${statusNames[row.status] || esc(row.status)}</span></div><p>${esc(row.initiator_name)} покупает у ${esc(row.partner_name)}</p><div class="next-game-recipe"><span>Доставлено ${number(row.delivered, 4)} / ${number(row.quantity, 4)} · партия ${number(row.batch, 0)}</span><span>Цена ${number(row.unit_price, 4)} cash · скорость ${number(row.rate_per_hour, 4)} в час</span><span>Резерв ${number(row.escrow_cash)} cash · срок ${row.duration_hours} ч</span>${row.ends_at ? `<span>До ${esc(new Date(row.ends_at).toLocaleString('ru-RU'))}</span>` : '<span>Расчёт срока начнётся после принятия.</span>'}</div>${row.blocked_reason ? `<p class="next-game-blocked-reason">${esc(row.blocked_reason)}</p>` : ''}${actions(row)}</article>`;
}

function projectCard(row) {
  const recipe = row.recipe || {};
  return `<article class="next-game-facility-card"><div class="next-game-facility-heading"><div><span class="next-game-eyebrow">СОВМЕСТНЫЙ ЗАВОД #${row.id}</span><h3>${icon('factories', 18)} ${esc(recipe.facility_name || row.branch_id)}</h3></div><span class="next-game-status ${row.blocked_reason ? 'is-blocked' : row.status === 'OPEN' ? 'is-idle' : ''}">${row.blocked_reason ? 'Остановлен' : statusNames[row.status] || esc(row.status)}</span></div><p>${esc(row.initiator_name)} + ${esc(row.partner_name)}</p><div class="next-game-recipe"><span>Строительство ${number(row.build_cost)} cash · каждому по 50%</span><span>Выпуск ${number(recipe.output_quantity, 4)} ${esc(recipe.output_unit)} ${esc(recipe.output_name)} за ${Math.ceil(Number(recipe.cycle_seconds || 0) / 60)} мин.</span><span>Сырьё и расходы ${number(recipe.operating_cost)} cash на цикл делятся пополам.</span><span>Готово циклов: ${row.cycles_completed}</span></div>${row.blocked_reason ? `<p class="next-game-blocked-reason">${esc(row.blocked_reason)}</p>` : ''}${row.status === 'ACTIVE' ? '<small>Остановка не возвращает уже потраченные средства строительства.</small>' : ''}${actions(row)}</article>`;
}

function createForm(data, view) {
  const counterparties = data.companies.map((row) => `<option value="${row.id}">${esc(row.name)} · #${row.id}</option>`).join('');
  const common = `<label for="next-partner-company">Компания-партнёр</label><select id="next-partner-company">${counterparties}</select>`;
  if (view === 'supply') return `<form class="next-game-panel" data-partner-form><h3>Предложить закупку</h3>${common}<label for="next-partner-item">Товар</label><select id="next-partner-item">${data.items.map((row) => `<option value="${esc(row.id)}">${esc(row.name)} · ${esc(row.unit)}</option>`).join('')}</select><label for="next-partner-quantity">Общий объём</label><input id="next-partner-quantity" type="number" min="0.0001" max="100000" step="0.0001" value="100" required><label for="next-partner-price">Фиксированная цена за единицу, cash</label><input id="next-partner-price" type="number" min="0.0001" max="1000000" step="0.0001" value="10" required><label for="next-partner-rate">Единиц в час</label><input id="next-partner-rate" type="number" min="0.0001" max="100000" step="0.0001" value="100" required><label for="next-partner-duration">Срок, часов</label><input id="next-partner-duration" type="number" min="1" max="720" step="1" value="24" required><p data-partner-estimate>Вся стоимость резервируется сразу; остаток вернётся при закрытии.</p><button class="next-game-primary" type="submit">Отправить предложение</button></form>`;
  const blueprints = data.blueprints.map((row) => `<option value="${esc(row.id)}">${esc(row.name)} · ${number(row.factory?.build_cost)} cash</option>`).join('');
  return `<form class="next-game-panel" data-partner-form><h3>Создать совместный завод</h3>${common}<label for="next-partner-branch">Ваш открытый чертёж</label><select id="next-partner-branch">${blueprints}</select><p>Вы резервируете половину строительства. Партнёр вносит вторую половину при принятии. Каждый предоставляет половину сырья и получает половину выпуска.</p><p data-partner-project-estimate></p><button class="next-game-primary" type="submit" ${blueprints && data.active_projects < 2 ? '' : 'disabled'}>Предложить совместное производство</button>${!blueprints ? '<p>Сначала откройте направление на карте развития.</p>' : data.active_projects >= 2 ? '<p>Достигнут лимит двух активных совместных заводов.</p>' : ''}</form>`;
}

export function renderPartnerships(data, options = {}) {
  const view = options.view || 'supply';
  const rows = view === 'supply' ? data.supplies : data.projects;
  return `<div class="next-game-subview"><button type="button" data-next-view="more" class="next-game-back">← Ещё</button><h2>Договоры и заводы</h2></div><section class="next-game-panel"><div class="next-game-quick-links"><button type="button" data-partner-tab="supply" class="${view === 'supply' ? 'next-game-primary' : 'next-game-secondary'}">Поставки</button><button type="button" data-partner-tab="projects" class="${view === 'projects' ? 'next-game-primary' : 'next-game-secondary'}">Совместные заводы</button></div><p>${view === 'supply' ? 'Фиксированная цена и оплаченный резерв. Продавец должен подтвердить предложение.' : 'Два партнёра делят строительство, сырьё, расходы и выпуск поровну. Лимит — два активных завода.'}</p><button type="button" data-partner-create class="next-game-primary" ${data.companies.length ? '' : 'disabled'}>${options.showForm ? 'Закрыть форму' : 'Создать предложение'}</button>${!data.companies.length ? '<p>Нужна вторая компания в тестовом мире.</p>' : ''}</section>${options.showForm ? createForm(data, view) : ''}<section class="next-game-panel"><h2>${view === 'supply' ? 'Ваши поставки' : 'Ваши совместные заводы'}</h2><div class="next-game-facility-list">${rows.length ? rows.map(view === 'supply' ? supplyCard : projectCard).join('') : '<p>Договоров пока нет. Создайте предложение компании-партнёру.</p>'}</div></section>`;
}

export async function renderNextGameContracts(container, state, showToast, refresh) {
  const data = await NatAPI.getNextGamePartnerships();
  const options = { view: state.partnershipView || 'supply', showForm: false };
  const redraw = () => {
    container.innerHTML = renderPartnerships(data, options);
    container.querySelectorAll('[data-partner-tab]').forEach((button) => button.addEventListener('click', () => {
      options.view = button.dataset.partnerTab; options.showForm = false; redraw();
    }));
    container.querySelector('[data-partner-create]')?.addEventListener('click', () => { options.showForm = !options.showForm; redraw(); });
    bindAction(container, '[data-partner-respond]', (button) => NatAPI.respondNextGamePartnership(button.dataset.kind, Number(button.dataset.partnerRespond), button.dataset.accept === 'true'), refresh, showToast, 'Ответ сохранён');
    bindAction(container, '[data-partner-cancel]', (button) => NatAPI.cancelNextGamePartnership(button.dataset.kind, Number(button.dataset.partnerCancel)), refresh, showToast, 'Договор закрыт');
    const estimate = () => {
      const total = Number(container.querySelector('#next-partner-quantity')?.value) * Number(container.querySelector('#next-partner-price')?.value);
      const label = container.querySelector('[data-partner-estimate]');
      const button = container.querySelector('[data-partner-form] button[type="submit"]');
      if (label) label.textContent = `Резерв ${number(total)} cash. Доступно ${number(data.cash)} cash.${total > data.cash ? ' Недостаточно средств.' : ' Остаток вернётся при закрытии.'}`;
      if (button) button.disabled = !Number.isFinite(total) || total <= 0 || total > data.cash || total > 10_000_000;
    };
    container.querySelectorAll('#next-partner-quantity,#next-partner-price').forEach((input) => input.addEventListener('input', estimate));
    if (options.view === 'supply') estimate();
    const projectEstimate = () => {
      const id = container.querySelector('#next-partner-branch')?.value;
      const blueprint = data.blueprints.find((row) => row.id === id);
      const half = Number(blueprint?.factory?.build_cost || 0) / 2;
      const label = container.querySelector('[data-partner-project-estimate]');
      const button = container.querySelector('[data-partner-form] button[type="submit"]');
      if (label) label.textContent = `Ваш резерв ${number(half)} cash. Доступно ${number(data.cash)} cash.${half > data.cash ? ' Недостаточно средств.' : ''}`;
      if (button) button.disabled = !blueprint || half > data.cash || data.active_projects >= 2;
    };
    container.querySelector('#next-partner-branch')?.addEventListener('change', projectEstimate);
    if (options.view === 'projects') projectEstimate();
    container.querySelector('[data-partner-form]')?.addEventListener('submit', async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      if (!form.reportValidity()) return;
      const button = form.querySelector('button[type="submit"]');
      button.disabled = true;
      const value = (id) => container.querySelector(`#next-partner-${id}`)?.value;
      try {
        const counterparty_id = Number(value('company'));
        if (options.view === 'supply') await NatAPI.createNextGameSupplyDeal({ counterparty_id, item_id: value('item'), quantity: Number(value('quantity')), unit_price: Number(value('price')), rate_per_hour: Number(value('rate')), duration_hours: Number(value('duration')) });
        else await NatAPI.createNextGameJointProject({ counterparty_id, branch_id: value('branch') });
        showToast('Предложение отправлено', 'success');
        await refresh();
      } catch (error) { showToast(error.message, 'error'); button.disabled = false; }
    });
  };
  redraw();
}
