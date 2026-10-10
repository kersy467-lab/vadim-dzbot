import { NatAPI } from '../api.js?v=20261010_competition_v1';
import { bindBankActions, renderBank } from './next_game_bank.js?v=20261010_competition_v1';
import { bindCapitalActions, renderCapital } from './next_game_capital.js?v=20261010_capital_market_v1';
import { renderCompetition } from './next_game_competition.js?v=20261010_competition_v1';

const MAX_TRADE = 10_000;
let activeNextGameView = 'map';

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));
}

function icon(name, size = 22) {
  return window.NatIcons?.icon?.(name, size) || '';
}

function number(value, digits = 2) {
  return Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: digits });
}

function findBranch(corporations, branchId) {
  for (const sector of corporations || []) {
    const branch = sector.branches.find((item) => item.id === branchId);
    if (branch) return { sector, branch };
  }
  return null;
}

function header(company) {
  const companySummary = company
    ? `<div class="next-game-company"><b>${esc(company.name)} · ур. ${number(company.level, 0)} · до уровня ${number(company.xp_to_next_level, 0)} XP</b><span>${number(company.cash)} тестовых cash</span></div>`
    : '';
  return `<header class="next-game-header"><button type="button" data-next-legacy class="next-game-back">← Основная игра</button><div class="next-game-kicker">ИЗОЛИРОВАННЫЙ ТЕСТ · ТОЛЬКО АДМИНЫ</div><h1>НАТБИРЖА 2.0</h1><p>Новая игра собирается рядом с действующей. Здесь отдельная компания и отдельное сохранение.</p>${companySummary}</header>`;
}

function renderCompanyForm(container, showToast) {
  container.innerHTML = `<div class="next-game-screen space-y-4 max-w-md mx-auto p-4 pb-24">${header(null)}<section class="next-game-panel"><h2>Начать тест 2.0</h2><p>Создай отдельную тестовую компанию. Баланс старой игры останется прежним.</p><label for="next-game-company-name">Название компании</label><input id="next-game-company-name" maxlength="80" minlength="2" value="Новая корпорация" /><button id="next-game-create" type="button" class="next-game-primary">Создать компанию</button></section></div>`;
  container.querySelector('[data-next-legacy]')?.addEventListener('click', () => window.NatApp?.navigateTo('overview'));
  container.querySelector('#next-game-create')?.addEventListener('click', async (event) => {
    const button = event.currentTarget;
    const name = container.querySelector('#next-game-company-name')?.value?.trim();
    if (!name || name.length < 2) return showToast('Название должно быть не короче двух символов', 'error');
    button.disabled = true;
    try {
      await NatAPI.createNextGameCompany(name);
      showToast('Тестовая компания создана', 'success');
      await renderNextGame(container, showToast);
    } catch (error) {
      showToast(error.message, 'error');
      button.disabled = false;
    }
  });
}

function renderMarket(state) {
  const items = state.market || [];
  if (!items.length) return '';
  const marketOrders = state.market_orders || {};
  const allOrders = marketOrders.open_orders || [];
  const myOrders = marketOrders.my_orders || [];
  const allTrades = marketOrders.trades || [];
  return `<section class="next-game-panel next-game-market"><div><h2>Рынок 2.0</h2><p>Резерв казны: ${number(state.treasury?.cash)} cash. Показаны только товары выбранного производства. Сделки между компаниями ведутся отдельно от расчётов с казной.</p></div><div class="next-game-market-list">${items.map((item) => {
    const amount = Math.max(0, Math.min(10, Number(item.quantity || 0)));
    const book = allOrders.filter((order) => order.item_id === item.item_id);
    const bids = book.filter((order) => order.side === 'BUY').slice(0, 3).map((order) => `<li><span>${esc(order.company_name)} · ${number(order.remaining_quantity, 4)} ${esc(item.unit)}</span><b>${number(order.limit_price, 4)}</b></li>`).join('');
    const asks = book.filter((order) => order.side === 'SELL').slice(0, 3).map((order) => `<li><span>${esc(order.company_name)} · ${number(order.remaining_quantity, 4)} ${esc(item.unit)}</span><b>${number(order.limit_price, 4)}</b></li>`).join('');
    const own = myOrders.filter((order) => order.item_id === item.item_id).map((order) => `<li><span>${order.side === 'BUY' ? 'BID' : 'ASK'} · ${number(order.remaining_quantity, 4)} ${esc(item.unit)} × ${number(order.limit_price, 4)}</span><button type="button" data-next-cancel-order="${esc(order.id)}">Отменить</button></li>`).join('');
    const history = allTrades.filter((trade) => trade.item_id === item.item_id).slice(0, 4).map((trade) => `<li><span>${esc(trade.buyer_name)} ← ${esc(trade.seller_name)} · ${number(trade.quantity, 4)} ${esc(item.unit)}</span><b>${number(trade.price, 4)} cash</b></li>`).join('');
    return `<article class="next-game-market-item" data-next-item="${esc(item.item_id)}"><div class="next-game-market-heading"><b>${esc(item.name)}</b><span>На складе: ${number(item.quantity, 4)} ${esc(item.unit)}</span></div><div class="next-game-market-stocks"><span>Резерв казны: ${number(item.npc_quantity, 3)} ${esc(item.unit)}</span><span>Покупка ${number(item.buy_price)} · продажа ${number(item.sell_price)} cash/${esc(item.unit)}</span></div><div class="next-game-orderbook"><div><b>BID</b><ul>${bids || '<li><span>Заявок нет</span></li>'}</ul></div><div><b>ASK</b><ul>${asks || '<li><span>Заявок нет</span></li>'}</ul></div></div><label for="next-game-qty-${esc(item.item_id)}">Количество</label><input id="next-game-qty-${esc(item.item_id)}" data-next-quantity type="number" min="0.0001" max="${MAX_TRADE}" step="0.0001" value="${amount || 1}" /><div class="next-game-trade-actions"><button type="button" class="next-game-secondary" data-next-trade="BUY" ${Number(item.npc_quantity) <= 0 ? 'disabled' : ''}>Купить у казны</button><button type="button" class="next-game-secondary" data-next-trade="SELL" ${Number(item.quantity) <= 0 ? 'disabled' : ''}>Продать казне</button></div><div class="next-game-limit-forms"><label>BID · цена за единицу<input type="number" min="0.0001" step="0.0001" data-next-order-price="BUY" value="${Number(item.buy_price).toFixed(4)}" /></label><button type="button" class="next-game-secondary" data-next-limit="BUY">Заявка BID</button><label>ASK · цена за единицу<input type="number" min="0.0001" step="0.0001" data-next-order-price="SELL" value="${Number(item.sell_price).toFixed(4)}" /></label><button type="button" class="next-game-secondary" data-next-limit="SELL">Заявка ASK</button></div>${own ? `<div class="next-game-own-orders"><b>Мои заявки</b><ul>${own}</ul></div>` : ''}${history ? `<div class="next-game-trade-history"><b>История межкорпоративных сделок</b><ul>${history}</ul></div>` : ''}</article>`;
  }).join('')}</div></section>`;
}

function renderFactories(state, pathEntries) {
  if (!pathEntries.length) return '';
  const items = new Map((state.market || []).map((item) => [item.item_id, item]));
  const facilities = new Map((state.facilities || []).map((facility) => [facility.branch_id, facility]));
  const facilityCards = pathEntries.map(({ sector, branch }, index) => {
    const facility = facilities.get(branch.id);
    const recipe = facility?.recipe || branch.factory;
    const inputs = Object.entries(recipe.inputs).map(([itemId, quantity]) => {
      const item = items.get(itemId);
      return `${esc(item?.name || itemId)}: ${number(quantity, 3)} ${esc(item?.unit || '')}`;
    });
    const status = facility
      ? facility.status === 'blocked' ? '<span class="next-game-status is-blocked">Остановлен</span>' : '<span class="next-game-status">Работает</span>'
      : '<span class="next-game-status is-idle">Не построен</span>';
    const nextCycle = facility?.seconds_to_cycle > 0
      ? `Следующий цикл примерно через ${Math.ceil(facility.seconds_to_cycle / 60)} мин.`
      : 'Цикл готов к запуску при наличии ресурсов.';
    const canUpgrade = Boolean(facility && facility.upgrade_cost !== null && Number(state.company.level) >= Number(facility.required_company_level) && Number(state.company.cash) >= Number(facility.upgrade_cost));
    const upgrade = facility?.upgrade_cost !== null && facility?.upgrade_cost !== undefined
      ? `<button type="button" data-next-upgrade="${esc(branch.id)}" class="next-game-secondary" ${canUpgrade ? '' : 'disabled'}>Улучшить до ${number(facility.upgrade_level, 0)} ур. · ${number(facility.upgrade_cost, 0)} cash</button><small>Нужен уровень компании ${number(facility.required_company_level, 0)} · выпуск растёт без дополнительного расхода сырья.</small>`
      : '<span>Максимальный уровень завода</span>';
    const action = facility ? `<div class="next-game-facility-meta"><span>Выпуск: ${number(recipe.output_quantity, 3)} ${esc(recipe.output_unit)} · цикл ${Math.ceil(recipe.cycle_seconds / 60)} мин.</span><span>${esc(nextCycle)}</span><span>Уровень завода ${number(facility.level, 0)} · бонус выпуска +${number((Number(facility.output_multiplier || 1) - 1) * 100, 0)}%</span></div>${facility.blocked_reason ? `<p class="next-game-blocked-reason">Не хватает для работы: ${esc(facility.blocked_reason)}</p>` : ''}${upgrade}`
      : `<p>Строительство: ${number(recipe.build_cost, 0)} cash · цикл ${Math.ceil(recipe.cycle_seconds / 60)} мин.</p><button type="button" data-next-build="${esc(branch.id)}" class="next-game-primary">Построить завод этапа ${index + 1}</button>`;
    return `<article class="next-game-facility-card"><div class="next-game-facility-heading"><div><h3>${esc(recipe.facility_name)}</h3><p>${esc(sector.name)} · ${esc(branch.name)} · выпуск ${esc(recipe.output_name)}</p></div>${status}</div><div class="next-game-recipe"><b>Ресурсы на цикл</b><span>${inputs.length ? inputs.join(' · ') : 'Не нужны'}</span><b>Расход на цикл</b><span>${number(recipe.operating_cost, 0)} cash</span></div>${action}</article>`;
  }).join('');
  return `<section class="next-game-panel next-game-facility"><div><h2>Предприятия по маршруту</h2><p>Каждая открытая ветка становится отдельным производством.</p></div><div class="next-game-facility-list">${facilityCards}</div></section>`;
}

function renderOverview(state, pathEntries) {
  const company = state.company;
  const facilities = state.facilities || [];
  const active = facilities.filter((facility) => facility.status === 'active').length;
  const blocked = facilities.length - active;
  const activity = (state.recent_activity || []).slice(0, 8).map((row) => {
    const actionNames = {
      STARTUP_CAPITAL: 'Стартовый капитал', BUILD: 'Строительство', BUY: 'Покупка ресурса',
      SELL: 'Продажа товара', OPERATING_COST: 'Расходы производства',
      PRODUCTION_INPUT: 'Списание сырья', PRODUCTION_OUTPUT: 'Выпуск товара',
    };
    const amount = Number(row.cash_change || 0);
    const cash = amount ? `${amount > 0 ? '+' : ''}${number(amount)} cash` : '';
    const goods = row.item_name && Number(row.quantity_change)
      ? `${row.quantity_change > 0 ? '+' : ''}${number(row.quantity_change, 3)} ${esc(row.unit)} ${esc(row.item_name)}` : '';
    const when = row.created_at ? new Date(row.created_at).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' }) : '';
    return `<li><span>${esc(actionNames[row.action] || row.action)}</span><b>${esc(cash || goods || '—')}</b><time>${esc(when)}</time></li>`;
  }).join('');
  const route = pathEntries.map(({ branch }) => branch.name).join(' → ') || 'Маршрут ещё не выбран';
  return `<section class="next-game-panel next-game-dashboard"><div class="next-game-dashboard-heading"><div><h2>Пульс компании</h2><p>${esc(route)}</p></div><span class="next-game-level">Уровень ${number(company.level, 0)}</span></div><div class="next-game-dashboard-grid"><article><span>Касса</span><b>${number(company.cash)} cash</b></article><article><span>До уровня</span><b>${number(company.xp_to_next_level, 0)} XP</b></article><article><span>Работает заводов</span><b>${active} / ${facilities.length}</b></article><article><span>Требуют ресурсов</span><b>${blocked}</b></article></div><div class="next-game-progress"><span style="width:${Math.max(0, Math.min(100, (Number(company.xp || 0) % 1000) / 10))}%"></span></div><p>Прогресс развития: ${number(Number(company.xp || 0) % 1000, 0)} / 1 000 XP</p></section><section class="next-game-panel next-game-activity"><div><h2>Последние операции</h2><p>История только новой экономики 2.0.</p></div>${activity ? `<ul>${activity}</ul>` : '<p>Операций пока нет.</p>'}</section>`;
}

function bindEconomyActions(container, hasPath, showToast) {
  if (!hasPath) return;
  container.querySelectorAll('[data-next-build]').forEach((button) => button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      await NatAPI.buildNextGameFacility(button.dataset.nextBuild);
      showToast('Завод построен. Начинается отдельное производство 2.0.', 'success');
      await renderNextGame(container, showToast);
    } catch (error) {
      showToast(error.message, 'error');
      button.disabled = false;
    }
  }));
  container.querySelectorAll('[data-next-upgrade]').forEach((button) => button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      const result = await NatAPI.upgradeNextGameFacility(button.dataset.nextUpgrade);
      showToast(`Завод улучшен до уровня ${number(result.facility.level, 0)} · выпуск +${number((result.output_multiplier - 1) * 100, 0)}%`, 'success');
      await renderNextGame(container, showToast);
    } catch (error) {
      showToast(error.message, 'error');
      button.disabled = false;
    }
  }));
  container.querySelectorAll('[data-next-trade]').forEach((button) => button.addEventListener('click', async () => {
    const itemCard = button.closest('.next-game-market-item');
    const itemId = itemCard?.dataset.nextItem;
    const quantity = Number(itemCard?.querySelector('[data-next-quantity]')?.value);
    if (!itemId || !Number.isFinite(quantity) || quantity <= 0 || quantity > MAX_TRADE) {
      return showToast(`Укажи количество от 0 до ${number(MAX_TRADE, 0)}`, 'error');
    }
    button.disabled = true;
    try {
      await NatAPI.tradeNextGameMarket(itemId, button.dataset.nextTrade, quantity);
      showToast(button.dataset.nextTrade === 'BUY' ? 'Ресурс куплен в казне 2.0' : 'Товар продан в казну 2.0', 'success');
      await renderNextGame(container, showToast);
    } catch (error) {
      showToast(error.message, 'error');
      button.disabled = false;
    }
  }));
  container.querySelectorAll('[data-next-limit]').forEach((button) => button.addEventListener('click', async () => {
    const itemCard = button.closest('.next-game-market-item');
    const itemId = itemCard?.dataset.nextItem;
    const side = button.dataset.nextLimit;
    const quantity = Number(itemCard?.querySelector('[data-next-quantity]')?.value);
    const price = Number(itemCard?.querySelector(`[data-next-order-price="${side}"]`)?.value);
    if (!itemId || !Number.isFinite(quantity) || quantity <= 0 || quantity > MAX_TRADE
        || Math.abs(quantity - Math.round(quantity * 10_000) / 10_000) > 1e-9
        || !Number.isFinite(price) || price <= 0) {
      return showToast('Проверь количество (до 4 знаков) и положительную лимитную цену', 'error');
    }
    button.disabled = true;
    try {
      const result = await NatAPI.createNextGameLimitOrder(itemId, side, quantity, price);
      showToast(result.executed_quantity > 0
        ? `Исполнено ${number(result.executed_quantity, 4)} ${esc(itemId)}`
        : 'Лимитная заявка выставлена', 'success');
      await renderNextGame(container, showToast);
    } catch (error) {
      showToast(error.message, 'error');
      button.disabled = false;
    }
  }));
  container.querySelectorAll('[data-next-cancel-order]').forEach((button) => button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      await NatAPI.cancelNextGameOrder(button.dataset.nextCancelOrder);
      showToast('Остаток заявки возвращён компании', 'success');
      await renderNextGame(container, showToast);
    } catch (error) {
      showToast(error.message, 'error');
      button.disabled = false;
    }
  }));
}

function renderBranchCheckpoint(state, pathEntries) {
  const last = pathEntries.at(-1);
  if (!last) return '';
  const requiredLevel = pathEntries.length + 1;
  const hasFacility = (state.facilities || []).some((facility) => facility.branch_id === last.branch.id);
  const canAdvance = hasFacility && Number(state.company.level) >= requiredLevel;
  const options = last.branch.next_branch_ids.map((branchId) => {
    const target = findBranch(state.corporations, branchId);
    if (!target) return '';
    const alreadySelected = state.company.branch_path.includes(branchId);
    const button = alreadySelected
      ? '<span class="next-game-choice">Уже в маршруте</span>'
      : canAdvance
        ? `<button type="button" data-next-branch="${esc(branchId)}">Выбрать направление</button>`
        : `<span class="next-game-locked">Нужен уровень ${requiredLevel} и завод текущего этапа</span>`;
    const factory = target.branch.factory;
    const inputs = factory.input_items.map((item) => `${esc(item.name)} ${number(item.quantity, 3)} ${esc(item.unit)}`).join(' · ') || 'без сырья';
    return `<article class="next-game-branch"><div><b>${esc(target.branch.name)}</b><p>${esc(target.sector.name)} · выпускает ${number(factory.output_quantity, 3)} ${esc(factory.output_unit)} ${esc(factory.output_name)} за ${Math.ceil(factory.cycle_seconds / 60)} мин.</p><small>Завод: ${number(factory.build_cost, 0)} cash · на цикл: ${inputs} · ${number(factory.operating_cost, 0)} cash</small></div>${button}</article>`;
  }).join('');
  return `<section class="next-game-panel next-game-checkpoint"><div><h2>Следующая развилка</h2><p>Нужен уровень ${requiredLevel} и построенный завод «${esc(last.branch.name)}». Сравни выпуск и стоимость двух маршрутов заранее.</p></div><div class="next-game-branches">${options}</div></section>`;
}

function renderDevelopmentPath(state, pathEntries) {
  if (!pathEntries.length) return '';
  const facilities = new Map((state.facilities || []).map((facility) => [facility.branch_id, facility]));
  const steps = pathEntries.map(({ sector, branch }, index) => {
    const factory = branch.factory;
    const facility = facilities.get(branch.id);
    const inputs = factory.input_items.map((item) => `${esc(item.name)} ${number(item.quantity, 3)} ${esc(item.unit)}`).join(' · ') || 'Без сырья';
    const status = facility
      ? facility.status === 'blocked' ? '<span class="next-game-status is-blocked">Нужны ресурсы</span>' : '<span class="next-game-status">Работает</span>'
      : '<span class="next-game-status is-idle">Завод не построен</span>';
    return `<article class="next-game-path-step"><span class="next-game-step-number">${String(index + 1).padStart(2, '0')}</span><div class="next-game-path-copy"><div class="next-game-path-heading"><b>${esc(factory.facility_name)}</b>${status}</div><p>${esc(sector.name)} · ${esc(branch.name)}</p><div class="next-game-path-facts"><span>Выпуск ${number(factory.output_quantity, 3)} ${esc(factory.output_unit)} ${esc(factory.output_name)} / ${Math.ceil(factory.cycle_seconds / 60)} мин.</span><span>Строительство ${number(factory.build_cost, 0)} cash</span><span>Сырьё: ${inputs}</span></div></div></article>`;
  }).join('');
  return `<section class="next-game-route"><div class="next-game-route-heading"><h2>Твой маршрут</h2><span>${pathEntries.length} этапа</span></div><div class="next-game-route-list">${steps}</div></section>`;
}

function renderSectorMap(container, state, showToast) {
  const company = state.company;
  const selectedSector = state.corporations.find((item) => item.id === company.sector_id);
  const pathEntries = (company.branch_path || []).map((branchId) => findBranch(state.corporations, branchId)).filter(Boolean);
  const pathLabel = pathEntries.map(({ branch }) => branch.name).join(' → ');
  const visibleSectors = company.sector_id
    ? state.corporations.filter((sector) => sector.id === company.sector_id)
    : state.corporations;
  const cards = visibleSectors.map((sector) => {
    const chosen = sector.id === company.sector_id;
    const branches = (!company.branch_path?.length ? sector.branches.filter((branch) => branch.is_starting_branch) : []).map((branch) => {
      const branchChosen = company.branch_path?.includes(branch.id);
      const canChoose = chosen && !company.branch_path?.length && branch.is_starting_branch;
      const recipe = branch.factory;
      return `<article class="next-game-branch ${branchChosen ? 'is-selected' : ''}"><div><b>${esc(branch.name)}</b><p>${esc(branch.outputs)}</p><small>${number(recipe.build_cost, 0)} cash · выпуск ${number(recipe.output_quantity, 3)} ${esc(recipe.output_unit)} ${esc(recipe.output_name)} / ${Math.ceil(recipe.cycle_seconds / 60)} мин.</small></div>${canChoose ? `<button type="button" data-branch="${esc(branch.id)}">Выбрать путь</button>` : branchChosen ? '<span class="next-game-choice">Выбрано</span>' : '<span class="next-game-locked">После открытия ветки</span>'}${branchChosen ? `<div class="next-game-future"><span>Дальнейшая развилка</span>${branch.future_choices.map((choice) => `<i>${esc(choice)}</i>`).join('')}</div>` : ''}</article>`;
    }).join('');
    const canChooseSector = !company.sector_id;
    const sectorAction = canChooseSector
      ? `<button type="button" data-sector="${esc(sector.id)}" class="next-game-secondary">Выбрать корпорацию</button>`
      : chosen ? '<span class="next-game-choice">Ваша корпорация</span>' : '<span class="next-game-locked">Закрыто в тесте</span>';
    return `<section class="next-game-sector ${chosen ? 'is-selected' : ''}"><div class="next-game-sector-heading"><span class="next-game-icon">${icon(sector.icon)}</span><div><h2>${esc(sector.name)}</h2><p>${esc(sector.description)}</p></div></div>${sectorAction}${chosen && branches ? `<div class="next-game-branches">${branches}</div>` : ''}</section>`;
  }).join('');
  const checkpoint = renderBranchCheckpoint(state, pathEntries);
  const routeDescription = pathEntries.length
    ? `Маршрут: ${esc(selectedSector.name)} → ${esc(pathLabel)}`
    : selectedSector ? `Выбери первую ветку корпорации «${esc(selectedSector.name)}»` : 'Выбери одну из семи стартовых корпораций';
  const mapView = `<section class="next-game-panel next-game-development"><div class="next-game-map-intro"><b>Карта развития</b><span>${routeDescription}</span></div>${renderDevelopmentPath(state, pathEntries)}<div class="next-game-sector-list">${cards}</div>${checkpoint}</section>`;
  const views = {
    overview: renderOverview(state, pathEntries),
    map: mapView,
    factories: pathEntries.length ? renderFactories(state, pathEntries) : '<section class="next-game-panel"><h2>Сначала выбери стартовую ветку на карте</h2></section>',
    market: pathEntries.length ? renderMarket(state) : '<section class="next-game-panel"><h2>Рынок откроется после выбора производственной ветки</h2></section>',
    bank: renderBank(state),
    capital: renderCapital(state),
    competition: renderCompetition(state.competition),
  };
  const tabs = [
    ['overview', 'Обзор'], ['map', 'Карта'], ['factories', 'Заводы'],
    ['market', 'Рынок'], ['capital', 'Капитал'], ['bank', 'Банк'], ['competition', 'Рейтинг'],
  ].map(([id, label]) => `<button type="button" data-next-view="${id}" class="${activeNextGameView === id ? 'is-active' : ''}">${label}</button>`).join('');
  container.innerHTML = `<div class="next-game-screen space-y-4 max-w-md mx-auto p-4 pb-8">${header(company)}<nav class="next-game-nav" aria-label="Разделы игры 2.0">${tabs}</nav>${views[activeNextGameView] || mapView}<p class="next-game-footnote">Новая игра живёт отдельно: собственные заводы, рынок, банк-казна и карта развития.</p></div>`;
  container.querySelectorAll('[data-next-view]').forEach((button) => button.addEventListener('click', () => {
    activeNextGameView = button.dataset.nextView;
    if (activeNextGameView === 'competition') {
      button.disabled = true;
      NatAPI.getNextGameCompetition().then((data) => {
        state.competition = data;
        renderSectorMap(container, state, showToast);
      }).catch((error) => {
        showToast(error.message, 'error');
        state.competition = null;
        renderSectorMap(container, state, showToast);
      }).finally(() => { button.disabled = false; });
      return;
    }
    renderSectorMap(container, state, showToast);
  }));
  container.querySelector('[data-next-legacy]')?.addEventListener('click', () => window.NatApp?.navigateTo('overview'));
  container.querySelector('[data-next-competition-retry]')?.addEventListener('click', async (event) => {
    event.currentTarget.disabled = true;
    try {
      state.competition = await NatAPI.getNextGameCompetition();
      renderSectorMap(container, state, showToast);
    } catch (error) {
      showToast(error.message, 'error');
      event.currentTarget.disabled = false;
    }
  });
  if (activeNextGameView === 'map') {
  container.querySelectorAll('[data-sector]').forEach((button) => button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      await NatAPI.selectNextGameSector(button.dataset.sector);
      await renderNextGame(container, showToast);
    } catch (error) {
      showToast(error.message, 'error');
      button.disabled = false;
    }
  }));
  container.querySelectorAll('[data-branch]').forEach((button) => button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      await NatAPI.selectNextGameBranch(button.dataset.branch);
      showToast('Ветка сохранена в тестовом мире 2.0', 'success');
      await renderNextGame(container, showToast);
    } catch (error) {
      showToast(error.message, 'error');
      button.disabled = false;
    }
  }));
  container.querySelectorAll('[data-next-branch]').forEach((button) => button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      await NatAPI.advanceNextGameBranch(button.dataset.nextBranch);
      showToast('Новое направление добавлено в маршрут 2.0', 'success');
      await renderNextGame(container, showToast);
    } catch (error) {
      showToast(error.message, 'error');
      button.disabled = false;
    }
  }));
  }
  if (activeNextGameView === 'factories' || activeNextGameView === 'market') {
    bindEconomyActions(container, pathEntries.length > 0, showToast);
  }
  const refresh = () => renderNextGame(container, showToast);
  if (activeNextGameView === 'bank') bindBankActions(container, showToast, state, refresh);
  if (activeNextGameView === 'capital') bindCapitalActions(container, state, showToast, refresh);
}

export async function renderNextGame(container, showToast = () => {}) {
  container.innerHTML = '<div class="next-game-screen p-6 text-center">Загружаем отдельный мир 2.0…</div>';
  try {
    const state = await NatAPI.getNextGameMap();
    if (!state.company) renderCompanyForm(container, showToast);
    else renderSectorMap(container, state, showToast);
  } catch (error) {
    container.innerHTML = `<div class="next-game-screen p-6"><section class="next-game-panel"><button type="button" data-next-legacy class="next-game-back">← Основная игра</button><h1>НАТБИРЖА 2.0</h1><p>Не удалось открыть тестовый мир: ${esc(error.message)}</p><button type="button" id="next-game-retry" class="next-game-primary">Повторить</button></section></div>`;
    container.querySelector('[data-next-legacy]')?.addEventListener('click', () => window.NatApp?.navigateTo('overview'));
    container.querySelector('#next-game-retry')?.addEventListener('click', () => renderNextGame(container, showToast));
  }
}
