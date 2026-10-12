import { NatAPI } from '../api.js?v=20261010_active_production_v1';
import { esc, number, icon } from './next_game_common.js?v=20261010_shell_v2';

export async function renderNextGameAdmin(container, state, showToast, refresh) {
  const api = state.nextGameAPI || NatAPI;
  const data = await api.getNextGameAdmin();
  const currentCompanyId = Number(state.company?.id);
  const companies = data.companies.map((c) => `<option value="${c.id}" ${Number(c.id) === currentCompanyId ? 'selected' : ''}>${esc(c.name)} · #${c.id}</option>`).join('');
  const initialCompany = data.companies.find((c) => Number(c.id) === currentCompanyId) || data.companies[0];
  const titles = { TREASURY_TOPUP: 'Пополнение резерва', CASH_GRANT: 'Выдача cash', ITEM_GRANT: 'Выдача ресурса', PVC_GRANT: 'Выдача ПИВОкоинов' };
  const history = data.audit.map((row) => `<li><div><b>${esc(row.action === "BANKRUPTCY_FORCE" ? `Банкротство · ${row.details.company_name || row.details.company_id}` : titles[row.action] || row.action)}</b><p>${esc(row.details.note)} · админ ${esc(row.actor_tg_id)}</p><small>${esc(new Date(row.created_at + (row.created_at.endsWith('Z') ? '' : 'Z')).toLocaleString('ru-RU'))}</small></div><strong>${number(row.details.value, 4)}</strong></li>`).join('');
  container.innerHTML = `<section class="next-game-panel"><h2>${icon('admin')} Управление 2.0</h2><p>Операции расчётного банка и тестовых компаний. Каждое действие сохраняется в журнал.</p><div class="next-game-dashboard-grid"><article><span>Резерв банка</span><b>${number(data.treasury.cash)} cash</b></article><article><span>Компаний</span><b>${data.companies.length}</b></article><article><span data-next-admin-company-name>${esc(initialCompany?.name || 'Компания не выбрана')}</span><b data-next-admin-company-cash>${number(initialCompany?.cash || 0)} cash</b></article></div><form data-next-admin-form><label>Операция<select name="action">${Object.entries(titles).map(([id, title]) => `<option value="${id}">${title}</option>`).join('')}</select></label><label data-next-admin-target>Компания 2.0<select name="company_id">${companies || '<option value="">Компаний пока нет</option>'}</select></label><label data-next-admin-item hidden>Ресурс<select name="item_id" disabled required><option value="">Выберите ресурс</option></select></label><label>Сумма или количество<input name="value" type="number" min=".0001" max="100000000000000" step=".01" value="10000" required></label><label>Причина<textarea name="note" minlength="1" maxlength="240" placeholder="Компенсация за подтверждённую ошибку" required></textarea></label><button type="submit" class="next-game-primary">Выполнить операцию</button><p class="next-game-footnote">Выдача cash переводит деньги из резерва выбранной компании 2.0. Пополнение резерва — отдельная операция.</p></form></section><section class="next-game-panel"><h2>Журнал управления</h2>${history ? `<ul class="next-game-audit-list">${history}</ul>` : '<p>Ручных операций пока нет.</p>'}</section>`;
  const form = container.querySelector('[data-next-admin-form]');
  const select = form.elements.action;
  const companySelect = form.elements.company_id;
  const itemSelect = form.elements.item_id;
  const itemGroup = container.querySelector('[data-next-admin-item]');
  let marketItemsLoaded = false;
  let marketItemsRequest = null;
  const updateCompanyBalance = () => {
    const company = data.companies.find((row) => Number(row.id) === Number(companySelect.value));
    container.querySelector('[data-next-admin-company-name]').textContent = company?.name || 'Компания не выбрана';
    container.querySelector('[data-next-admin-company-cash]').textContent = `${number(company?.cash || 0)} cash`;
  };
  const loadMarketItems = () => {
    if (marketItemsLoaded || marketItemsRequest) return marketItemsRequest;
    itemSelect.disabled = true;
    marketItemsRequest = api.getNextGameMarketCatalog().then((market) => {
      itemSelect.replaceChildren();
      const placeholder = document.createElement('option');
      placeholder.value = '';
      placeholder.textContent = 'Выберите ресурс';
      itemSelect.append(placeholder);
      for (const item of market.items || []) {
        const option = document.createElement('option');
        option.value = String(item.id);
        option.textContent = item.name;
        itemSelect.append(option);
      }
      marketItemsLoaded = true;
    }).catch((error) => {
      showToast(error.message || 'Не удалось загрузить каталог ресурсов', 'error');
      select.value = 'CASH_GRANT';
    }).finally(() => {
      marketItemsRequest = null;
      visibility();
    });
    return marketItemsRequest;
  };
  const visibility = () => {
    container.querySelector('[data-next-admin-target]').hidden = select.value === 'TREASURY_TOPUP';
    const itemGrant = select.value === 'ITEM_GRANT';
    itemGroup.hidden = !itemGrant;
    itemSelect.required = itemGrant;
    itemSelect.disabled = !itemGrant || !marketItemsLoaded;
    form.elements.value.step = select.value === 'ITEM_GRANT' ? '.0001' : '.01';
    if (itemGrant && !marketItemsLoaded) void loadMarketItems();
  };
  companySelect.addEventListener('change', updateCompanyBalance);
  select.addEventListener('change', visibility);
  visibility();
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (select.value === 'ITEM_GRANT' && (!marketItemsLoaded || !itemSelect.value)) {
      showToast('Дождись загрузки каталога и выбери ресурс', 'error');
      return;
    }
    if (select.value !== 'TREASURY_TOPUP' && !companySelect.value) {
      showToast('Сначала выбери компанию 2.0', 'error');
      return;
    }
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
