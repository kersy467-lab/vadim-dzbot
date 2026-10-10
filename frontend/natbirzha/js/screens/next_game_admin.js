import { NatAPI } from '../api.js?v=20261010_active_production_v1';
import { esc, number, icon } from './next_game_common.js?v=20261010_shell_v2';

export async function renderNextGameAdmin(container, state, showToast, refresh) {
  const api = state.nextGameAPI || NatAPI;
  const [data, market] = await Promise.all([api.getNextGameAdmin(), api.getNextGameMarketCatalog()]);
  const companies = data.companies.map((c) => `<option value="${c.id}">${esc(c.name)} · #${c.id}</option>`).join('');
  const items = market.items.map((item) => `<option value="${esc(item.id)}">${esc(item.name)}</option>`).join('');
  const titles = { TREASURY_TOPUP: 'Пополнение резерва', CASH_GRANT: 'Выдача cash', ITEM_GRANT: 'Выдача ресурса', PVC_GRANT: 'Выдача ПИВОкоинов' };
  const history = data.audit.map((row) => `<li><div><b>${esc(row.action === "BANKRUPTCY_FORCE" ? `Банкротство · ${row.details.company_name || row.details.company_id}` : titles[row.action] || row.action)}</b><p>${esc(row.details.note)} · админ ${esc(row.actor_tg_id)}</p><small>${esc(new Date(row.created_at + (row.created_at.endsWith('Z') ? '' : 'Z')).toLocaleString('ru-RU'))}</small></div><strong>${number(row.details.value, 4)}</strong></li>`).join('');
  container.innerHTML = `<section class="next-game-panel"><h2>${icon('admin')} Управление 2.0</h2><p>Операции расчётного банка и тестовых компаний. Каждое действие сохраняется в журнал.</p><div class="next-game-dashboard-grid"><article><span>Резерв банка</span><b>${number(data.treasury.cash)} cash</b></article><article><span>Компаний</span><b>${data.companies.length}</b></article></div><form data-next-admin-form><label>Операция<select name="action">${Object.entries(titles).map(([id, title]) => `<option value="${id}">${title}</option>`).join('')}</select></label><label data-next-admin-target>Компания<select name="company_id">${companies}</select></label><label data-next-admin-item hidden>Ресурс<select name="item_id">${items}</select></label><label>Сумма или количество<input name="value" type="number" min=".0001" max="100000000000000" step=".0001" value="10000" required></label><label>Причина<textarea name="note" minlength="1" maxlength="240" placeholder="Компенсация за подтверждённую ошибку" required></textarea></label><button class="next-game-primary">Выполнить операцию</button><p class="next-game-footnote">Выдача cash переводит деньги из резерва. Пополнение резерва — отдельная операция эмиссии.</p></form></section><section class="next-game-panel"><h2>Журнал управления</h2>${history ? `<ul class="next-game-audit-list">${history}</ul>` : '<p>Ручных операций пока нет.</p>'}</section>`;
  const form = container.querySelector('[data-next-admin-form]');
  const select = form.elements.action;
  const visibility = () => {
    container.querySelector('[data-next-admin-target]').hidden = select.value === 'TREASURY_TOPUP';
    container.querySelector('[data-next-admin-item]').hidden = select.value !== 'ITEM_GRANT';
    form.elements.value.step = select.value === 'ITEM_GRANT' ? '.0001' : '.01';
  };
  select.addEventListener('change', visibility);
  visibility();
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = form.querySelector('button');
    button.disabled = true;
    try {
      await api.operateNextGameAdmin({ action: select.value,
        company_id: select.value === 'TREASURY_TOPUP' ? null : Number(form.elements.company_id.value),
        value: Number(form.elements.value.value), item_id: select.value === 'ITEM_GRANT' ? form.elements.item_id.value : null,
        note: form.elements.note.value.trim() });
      showToast('Операция выполнена и записана в журнал', 'success');
      await refresh();
    } catch (error) { showToast(error.message, 'error'); button.disabled = false; }
  });
  if (data.can_force_bankruptcy) {
    container.insertAdjacentHTML('beforeend', `<section class="next-game-panel"><h2>Ручное банкротство</h2><p>Изъятие имущества, списание долгов и продажа заводов резервным банком. Внешние акционеры сохранят свои акции. Автоматических банкротств в бета-тесте нет.</p><details><summary>Объявить банкротство компании</summary><form data-next-bankruptcy-form><label>Компания<select name="company_id">${companies}</select></label><label>Причина<textarea name="note" minlength="5" maxlength="500" required></textarea></label><label><input name="confirm" type="checkbox" required> Подтверждаю изъятие имущества и списание обязательств выбранной компании</label><button class="next-game-primary">Объявить банкротство</button></form></details></section>`);
    const bankruptcyForm = container.querySelector('[data-next-bankruptcy-form]');
    let forcing = false;
    bankruptcyForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (forcing || !bankruptcyForm.elements.confirm.checked) return;
      forcing = true;
      const button = bankruptcyForm.querySelector('button'); button.disabled = true;
      try {
        await api.forceNextGameBankruptcy(Number(bankruptcyForm.elements.company_id.value),
          bankruptcyForm.elements.note.value.trim(), true);
        showToast('Банкротство записано в журнал. Имущество передано резервному банку', 'success');
        await refresh?.();
      } catch (error) { showToast(error.message || 'Не удалось объявить банкротство', 'error'); }
      finally { forcing = false; button.disabled = false; }
    });
  }
}
