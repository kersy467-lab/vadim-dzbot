const fs = require('fs');
const path = require('path');
const assert = require('assert');
require('./natbirzha/test_tycoon_frontend_contract.js');
require('./natbirzha/test_creator_bond_bankruptcy_frontend.js');

console.log('=== [Natbirzha Test 1/5] Testing index.html markup & theme sync ===');
const natHtml = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/index.html'), 'utf-8');
assert(natHtml.includes('id="screen-container"'), 'index.html must have screen-container');
assert(natHtml.includes('id="bottom-nav"'), 'index.html must have bottom-nav');
assert(natHtml.includes('id="toast-container"'), 'index.html must have toast-container');
assert(natHtml.includes('id="header-stats"'), 'index.html must have header-stats');
assert(natHtml.includes('id="header-cash"'), 'index.html must have header-cash');
assert(natHtml.includes('id="header-ticker"'), 'index.html must have header-ticker');
assert(natHtml.includes('/static/natbirzha/css/natbirzha.css'), 'index.html must import natbirzha.css');
assert(natHtml.includes('/static/natbirzha/css/princess-theme.css'),
  'index.html must import the dedicated princess visual theme after the base styles');
assert(natHtml.includes('/static/natbirzha/js/app.js'), 'index.html must import app.js');
assert(natHtml.includes('app.js?v=20260925_sabotages_v2'), 'Natbirzha entrypoint must refresh its cached code after a release');
assert(natHtml.includes('syncTgTheme'), 'index.html must define syncTgTheme');
assert(natHtml.includes("window.Telegram?.WebApp?.onEvent?.('themeChanged'"), 'index.html must safely listen to themeChanged');
console.log('index.html structure and scripts verified!');

const princessTheme = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/css/princess-theme.css'), 'utf-8');
['--princess-pink', '.princess-sky', '.nav-tab.active', '.factory-map', '@media (prefers-reduced-motion: reduce)'].forEach(token => {
  assert(princessTheme.includes(token), `princess theme must define ${token}`);
});
  assert(princessTheme.split('\n').length <= 400,
    'princess theme must stay within the repository source-file limit');
  assert(princessTheme.includes('.dark .bg-slate-50') && princessTheme.includes('.dark .bg-white'),
    'dark princess theme must override light card utilities instead of rendering grey/white cards');

  const upgradesScreen = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/upgrades.js'), 'utf-8');
  assert(upgradesScreen.includes('upgrade-locked-btn'),
    'locked upgrade controls must have a dedicated readable visual treatment');
  assert(!upgradesScreen.includes('bg-slate-800/60 text-slate-500 py-2 text-[10px] font-bold cursor-not-allowed'),
    'locked upgrade controls must not be rendered as low-contrast grey buttons');

  const overviewScreen = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/overview.js'), 'utf-8');
  assert(overviewScreen.includes('capital_plan'),
    'overview must render the API capital plan when a company reaches its capital milestone');
  assert(overviewScreen.includes('capital-plan-ipo-btn'),
    'capital plan must offer a direct, reachable IPO action');
  assert(overviewScreen.includes('mastery-progress'),
    'overview must display the unbounded mastery track after level 60');
  assert(overviewScreen.includes('inventoryReserved') && overviewScreen.includes('В заявках:'),
    'overview must distinguish available inventory from quantities reserved in active sale orders');

  const militaryScreen = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/military.js'), 'utf-8');
  assert(militaryScreen.includes('target.cooldown_until'),
    'PvE screen must expose the two-hour repeat-attack cooldown to the player');
  assert(!militaryScreen.includes('!target.available || target.conquered'),
    'a historical PvE victory must not permanently disable the rematch button');
  assert(militaryScreen.includes('campaign_rank'),
    'PvE screen must show the escalating frontier campaign rank');

console.log('=== [Natbirzha Test 2/5] Testing state.js reactivity & non-destructive updates ===');
const stateScript = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/state.js'), 'utf-8');
const cleanedStateScript = stateScript.replace(/export\s+const\s+store\s+=/, 'const store =');
const stateFn = new Function(cleanedStateScript + '\nreturn { NatStateStore, store };');
const { store } = stateFn();

assert(!store.hasCompany(), 'Initial state must not have company');
store.setUser({ id: 10, full_name: 'Трейдер' });
assert(store.user && store.user.id === 10, 'User state must be set');

store.setCompany({
  company_id: 101,
  name: 'Северсталь 11 Б',
  ticker: 'ST11',
  cash: 50000,
  audited_nav: 50000,
  inventory: { steel: 10, coal: 20 },
  factories: [{ id: 1, building_type: 'smelter', level: 1 }]
});
assert(store.hasCompany(), 'hasCompany must return true after setCompany');
assert(store.company.id === 101, 'company_id must be normalized to id');
assert(store.nav === 50000, 'nav must be populated from audited_nav');
assert(store.inventory.steel === 10, 'inventory must be set');
assert(store.factories.length === 1, 'factories must be set');

store.updateCompany({ factories: [{ id: 1, building_type: 'smelter', level: 2 }], inventory: undefined });
assert(store.inventory.steel === 10, 'inventory must NOT be wiped when undefined is passed to updateCompany');
assert(store.factories[0].level === 2, 'factories must be updated');
assert(store.company.name === 'Северсталь 11 Б', 'other company fields must be preserved');

store.setCompany({
  id: 101,
  inventory: { steel: 152.934 },
  inventory_total: { steel: 152.934 },
  inventory_available: { steel: 4 },
  inventory_reserved: { steel: 148.934 },
});
assert(store.inventory.steel === 4, 'market and overview inventory must expose only unreserved material as available');
assert(store.inventoryTotal.steel === 152.934, 'total inventory must remain available for stock breakdowns');
assert(store.inventoryReserved.steel === 148.934, 'reserved material must remain visible as a separate amount');

store.setTab('production');
assert(store.currentTab === 'production', 'setTab must update currentTab');
console.log('state.js reactivity and safe updates verified!');

console.log('=== [Natbirzha Test 3/5] Testing api.js request handling & error resilience ===');
const apiScript = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/api.js'), 'utf-8');
const cleanedApiScript = apiScript
  .replace(/import\s*\{[^}]+\}\s*from\s*['"]\.\/auth\.js['"];?/s, '')
  .replace(/export\s+function\s+setNavigationAbortSignal/, 'function setNavigationAbortSignal')
  .replace(/export\s+const\s+NatAPI\s+=/, 'const NatAPI =');
// Keep the lightweight CommonJS harness compatible with named helper exports.
const normalizedApiScript = cleanedApiScript.replace(/export\s*\{[^}]+\};?/g, '');

const mockBrowserWindow = {
  location: { search: '?tg_user_id=777', hostname: 'localhost' },
  Telegram: { WebApp: { initData: 'auth_signature_xyz' } }
};
const mockSessionStorage = {
  _store: {},
  getItem: function(k) { return this._store[k]; },
  setItem: function(k, v) { return this._store[k] = v; }
};
const mockCrypto = { randomUUID: () => '11111111-2222-3333-4444-555555555555' };

function authHelpersFor(targetWindow) {
  const getTelegramInitData = () => targetWindow.Telegram?.WebApp?.initData
    || mockSessionStorage.getItem('natbirzha_telegram_init_data') || '';
  const generateUUID = () => mockCrypto.randomUUID();
  return {
    generateUUID,
    getTelegramInitData,
    getTelegramUserId: () => null,
    clearStaleInitData: () => { delete mockSessionStorage._store.natbirzha_telegram_init_data; },
    getAuthHeader: () => {
      const initData = getTelegramInitData();
      if (initData) return { 'X-Telegram-Init-Data': initData };
      let guestId = mockSessionStorage.getItem('natbirzha_guest_id');
      if (!guestId) {
        guestId = generateUUID();
        mockSessionStorage.setItem('natbirzha_guest_id', guestId);
      }
      return { 'X-Natbirzha-Guest-Id': guestId };
    },
  };
}
const apiFn = new Function(
  'window', 'crypto', 'sessionStorage', 'authHelpers',
  'const { generateUUID, getTelegramInitData, clearStaleInitData, getTelegramUserId, getAuthHeader } = authHelpers;\n'
    + normalizedApiScript + '\nreturn { NatAPI, parseErrorMessage, getAuthHeader, generateUUID };',
);
const { NatAPI, parseErrorMessage, getAuthHeader, generateUUID } = apiFn(
  mockBrowserWindow, mockCrypto, mockSessionStorage, authHelpersFor(mockBrowserWindow),
);

assert(generateUUID() === '11111111-2222-3333-4444-555555555555', 'generateUUID must return UUID');
assert(getAuthHeader()['X-Telegram-Init-Data'] === 'auth_signature_xyz', 'Telegram WebApp initData must be prioritized');

const mockDevWindow = {
  location: { search: '?tg_user_id=888', hostname: '127.0.0.1' },
  Telegram: {}
};
const { getAuthHeader: getDevAuthHeader } = apiFn(
  mockDevWindow, mockCrypto, mockSessionStorage, authHelpersFor(mockDevWindow),
);
assert(!getDevAuthHeader()['X-Telegram-Init-Data'], 'Unsigned dev/query fallback must be disabled');
assert(/^[a-f0-9-]{16,}$/.test(getDevAuthHeader()['X-Natbirzha-Guest-Id']),
  'Browser access must use a generated guest session identity');
mockSessionStorage._store.natbirzha_telegram_init_data = 'carried_signed_init_data&hash=123';
const { getAuthHeader: getCarriedAuthHeader } = apiFn(
  mockDevWindow, mockCrypto, mockSessionStorage, authHelpersFor(mockDevWindow),
);
assert(getCarriedAuthHeader()['X-Telegram-Init-Data'] === 'carried_signed_init_data&hash=123',
  'Natbirzha must preserve signed initData when navigating from the parent Mini App');
delete mockSessionStorage._store.natbirzha_telegram_init_data;
assert(!apiScript.includes('initDataUnsafe'), 'api.js must not derive authority from initDataUnsafe');
assert(!apiScript.includes('tg_user_id'), 'api.js must not accept tg_user_id query identity');
assert(apiScript.includes('responseCache') && apiScript.includes('cachedGet'), 'Stable catalog requests must use a TTL cache');
assert(!apiScript.includes('renderCurrentScreen?.()'), 'Generic API errors must not force a full screen render');

const err1 = parseErrorMessage({ detail: 'Баланс исчерпан' }, 400);
assert(err1 === 'Баланс исчерпан', 'string detail must be extracted');
assert(!err1.includes('[object Object]'), 'must never contain [object Object]');

const err2 = parseErrorMessage({ detail: [{ msg: 'Field required', loc: ['name'] }] }, 422);
assert(err2 === 'Field required', 'array validation errors must be formatted cleanly');

const err3 = parseErrorMessage({ detail: { reason: 'insufficient_inventory', needed: 10, available: 2 } }, 400);
assert(err3.includes('Недостаточно ресурсов на складе') || err3.includes('insufficient_inventory'), 'detail reason must be translated or formatted');
assert(!err3.includes('[object Object]'), 'detail object must never format to [object Object]');

const err4 = parseErrorMessage({}, 500);
assert(err4.includes('Ошибка сервера (500)'), 'empty object must produce readable server error');

const requiredMethods = [
  'login', 'getMyCompany', 'expandTerritory', 'getBusinessCapacity', 'expandBusinessCapacity', 'createCompany', 'respecCompany',
  'upgradeAllBusinesses',
  'getProductionStatus', 'getRecipes', 'getInventory', 'getFactoryUpgrades', 'buildFactory', 'triggerProduction', 'setFactoryAutomation',
  'getOrderbook', 'getNpcRates', 'placeOrder', 'cancelOrder', 'npcTrade', 'getTaxStatus', 'payTax',
  'getStocksList', 'issueIPO', 'buyShares', 'getPortfolio',
  'getMilitaryStatus', 'recruitUnits', 'getCurrentTournament', 'joinAlliance',
  'getPveTargets', 'scoutPveTarget', 'attackPveTarget', 'getBattleHistory',
  'getTournamentTargets', 'attackTournamentTarget', 'getTournamentHistory',
  'getReferenceInstruments', 'tradeReferenceInstrument',
  'getStateBonds', 'createBondListing', 'buyBondListing', 'cancelBondListing',
  'getBankruptcyStatus', 'submitRestructuring', 'getIndustryUpgradeCatalog', 'getIndustryUpgrade', 'purchaseIndustryUpgrade',
  'getCreatorWorldResetPreview', 'resetCreatorWorld',
  'getStateCredit', 'requestStateCredit', 'repayStateCredit', 'renameCompany'
];
requiredMethods.forEach(m => {
  assert(typeof NatAPI[m] === 'function', `NatAPI.${m} must be defined`);
});
console.log('api.js methods, auth headers and error handling resilience verified!');

console.log('=== [Natbirzha Test 4/5] Testing screen modules syntax & exports ===');
const factoryMapPath = path.join(__dirname, '../frontend/natbirzha/js/factory_map.js');
assert(fs.existsSync(factoryMapPath), 'factory_map.js must define the territory projection');
const factoryMapCode = fs.readFileSync(factoryMapPath, 'utf-8');
['BIOMES', 'getFactoryPage', 'getFactorySlot', 'getBiomeForPage', 'buildFactoryPages'].forEach((name) => {
  assert(factoryMapCode.includes(`export ${name === 'BIOMES' ? 'const' : 'function'} ${name}`),
    `factory_map.js must export ${name}`);
});
assert(factoryMapCode.includes("'map_page'") && factoryMapCode.includes("'map_slot'"),
  'factory map must honor explicit map_page coordinates');
assert(factoryMapCode.includes('null'), 'factory map must preserve empty slots as null');
const natCss = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/css/natbirzha.css'), 'utf-8');
['.factory-map', '.factory-slot', '.factory-biome-grass', '.factory-biome-desert', '.factory-biome-snow'].forEach((selector) => {
  assert(natCss.includes(selector), `natbirzha.css must define ${selector}`);
});
assert(natCss.includes('grid-template-columns: repeat(3'), 'factory map must use a responsive three-column grid');

const screens = ['onboarding.js', 'overview.js', 'production.js', 'upgrades.js', 'market.js', 'stocks.js', 'military.js', 'leaderboard.js', 'help.js'];
screens.forEach(s => {
  const code = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/', s), 'utf-8');
  const renderFnName = 'render' + s[0].toUpperCase() + s.slice(1).replace('.js', '');
  assert(code.includes(`export function ${renderFnName}`) || code.includes(`export async function ${renderFnName}`),
    `${s} must export ${renderFnName}`);
});

const moderationCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/creator_moderation.js'), 'utf-8');
assert(moderationCode.includes('creator-world-reset-btn') && moderationCode.includes('resetCreatorWorld'),
  'creator moderation must expose the destructive all-world reset control');
assert(moderationCode.includes('СБРОСИТЬ НАТБИРЖУ'),
  'world reset UI must require an explicit typed confirmation phrase');

const onboardingCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/onboarding.js'), 'utf-8');
[
  'miner', 'agrarian', 'power_engineer', 'water', 'oilman',
  'metallurgist', 'chemist', 'construction', 'technoprom', 'logistics',
].forEach((industry) => {
  assert(onboardingCode.includes(`id: '${industry}'`), `onboarding must expose industry: ${industry}`);
});
assert(onboardingCode.includes('getIndustryOverview') && onboardingCode.includes('company_count'),
  'onboarding must show live company counts for each industry');
assert(onboardingCode.includes("status_color === 'green'") && onboardingCode.includes('pressureStyle'),
  'onboarding must implement green/yellow/red industry recommendations');
assert(onboardingCode.includes('цвет — рекомендация, а не запрет') || onboardingCode.includes('Цвет — рекомендация, а не запрет'),
  'industry pressure must remain a recommendation rather than a hard ban');
[
  'Угольный разрез', 'Зерновое хозяйство', 'Дизельная электростанция', 'Артезианская скважина',
  'Малая нефтяная скважина', 'Чугунолитейный цех', 'Завод минеральных удобрений',
  'Лесозаготовительный участок', 'Электронная мастерская', 'Курьерская служба',
].forEach((starter) => {
  assert(onboardingCode.includes(starter), `onboarding must show starter enterprise: ${starter}`);
});

const marketCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/market.js'), 'utf-8');
const marketTaxCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/market_tax.js'), 'utf-8');
assert(marketCode.includes('data-section=\"tax\"') && marketCode.includes('renderTaxSection'),
  'market home must expose the mandatory tax section');
assert(marketCode.indexOf('data-section=\"tax\"') < marketCode.indexOf('data-section=\"state_credit\"'),
  'state credit must appear directly after the tax section in the market menu');
const stateCreditCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/market_credit.js'), 'utf-8');
assert(stateCreditCode.includes('RATE_PCT = 20') && stateCreditCode.includes('Срок') && stateCreditCode.includes('Погасить'),
  'state credit screen must show the daily rate, requested term and repayment controls');
assert(stateCreditCode.includes('max="5"') && stateCreditCode.toLowerCase().includes('одобрения')
  && stateCreditCode.includes('Подать заявку'),
  'state credit screen must enforce the five-day limit and explain approval before disbursement');
const creatorScreenCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/creator.js'), 'utf-8');
const creatorCreditCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/creator_credit.js'), 'utf-8');
const creatorPlayersCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/creator_players.js'), 'utf-8');
assert(creatorScreenCode.includes('data-tab="credits"') && creatorScreenCode.includes('loadCreatorCreditTab'),
  'creator panel must expose a separate credit-approval tab');
assert(creatorScreenCode.includes('grid grid-cols-3') && !creatorScreenCode.includes('overflow-x-auto pb-1 text-xs font-bold'),
  'government controls must be visible in a wrapping grid instead of hidden in a horizontal tab strip');
assert(creatorScreenCode.includes('data-tab="players"') && creatorScreenCode.includes('data-tab="bonds"') && creatorScreenCode.includes('data-tab="sabotages"'),
  'player bankruptcy, bond bankruptcy and sabotages sections must remain directly navigable');
assert(fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/app.js'), 'utf-8').includes('creator.js?v=20260925_sabotages_v2'),
  'app.js must reload the updated creator panel module');
assert(creatorScreenCode.includes('creator_credit.js?v=20260925_sabotages_v2')
  && creatorScreenCode.includes('creator_players.js?v=20260925_sabotages_v2')
  && creatorScreenCode.includes('creator_bond_api.js?v=20260925_sabotages_v2')
  && creatorScreenCode.includes('creator_sabotages.js?v=20260925_sabotages_v2'),
  'creator tabs and bankruptcy actions must load their current screen modules');
assert(creatorCreditCode.includes('NatAPI.getCreatorStateCredits') && creatorCreditCode.includes('NatAPI.decideCreatorStateCredit'),
  'creator credit tab must load and decide pending credit requests');
assert(creatorPlayersCode.includes('NatAPI.sendCreatorWarning') && creatorPlayersCode.includes('NatAPI.declareCreatorBankruptcy'),
  'player cards must expose warning and forced-bankruptcy actions');
assert(marketTaxCode.includes('13%') && marketTaxCode.includes('Производство остановлено') && marketTaxCode.includes('Оплатить всё'),
  'tax screen must explain the rate, production block and payment action');
assert(marketTaxCode.includes('штраф не начисляется на штраф'),
  'tax screen must make the non-compounding penalty rule explicit');

const stocksCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/stocks.js'), 'utf-8');
assert(stocksCode.includes('Доступно с ${ipoMinLevel} уровня компании') && stocksCode.includes('IPO с ${ipoMinLevel} уровня') && stocksCode.includes('IPO_MIN_LEVEL_FALLBACK = 7'),
  'stocks screen must explain IPO unlock level instead of making the feature appear missing');
assert(stocksCode.includes('ipo-dividend-rate') && stocksCode.includes('min="5"'),
  'stocks screen must require an explicit dividend policy with a 5% minimum');
assert(stocksCode.includes('NatAPI.issueIPO({') && stocksCode.includes('company_sale_pct: companySalePct')
  && stocksCode.includes('total_shares: ipoTotalShares'),
  'stocks screen must submit dividend, company sale percentage and share count to the backend');

const prodCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/production.js'), 'utf-8');
assert(prodCode.includes("from '../factory_map.js"), 'production.js must use the pure factory map projection');
['factory-map', 'factory-slot', 'factory-next-page', 'factory-collect-btn', 'factory-build-btn'].forEach((hook) => {
  assert(prodCode.includes(hook), `production.js must render ${hook}`);
});
assert(prodCode.includes('cycle_ready_at') && prodCode.includes('remaining_seconds'),
  'production.js must use server cycle timing fields');
assert(prodCode.includes('f.building_type || f.factory_type'), 'production.js must handle both building_type and factory_type');
assert(prodCode.includes('r.factory_type === bType'), 'production.js must render server recipes for the exact factory type');
assert(prodCode.includes('f.current_recipe'), 'production.js must honor server cycle state');
assert(prodCode.includes('NatAPI.triggerProduction'), 'factory map must use the unified production mutation endpoint');
assert(prodCode.includes('factory-collect-btn') && prodCode.includes('openCatalogModal'),
  'factory map must wire collect and catalog actions');
assert(prodCode.includes('button.disabled = true') && prodCode.includes('refreshMap'),
  'factory mutations must lock the clicked control and refresh the map state');
assert(prodCode.includes('applyCycleResult(factory, result)') &&
  prodCode.includes('bindCountdown(root, state, showToast);'),
  'factory start and refresh must restart the live countdown on the current screen');
assert(prodCode.includes('factory-automation-toggle') && prodCode.includes('NatAPI.setFactoryAutomation'),
  'factory cards must expose the persistent automation toggle');
assert(prodCode.includes('automation_status') && prodCode.includes('automation_pause_reason'),
  'factory cards must render server automation state and pause reason');
assert(prodCode.includes('не покупает сырьё'),
  'automation UI must state that it never auto-buys missing resources');
const productionCore = prodCode
  .replace(/^import[^;]+;\s*$/gm, '')
  .replace(/export\s+function\s+renderProduction[\s\S]*/, '')
  .split('function nextStep')[0];
const productionCoreFn = new Function(`${productionCore}\nreturn { applyCycleResult, cycleState };`);
const { applyCycleResult, cycleState } = productionCoreFn();
const timerNow = Date.now();
const timerState = cycleState({
  cycle_ready_at: new Date(timerNow + 5000).toISOString(),
  remaining_seconds: 1,
  is_running: true,
}, timerNow);
assert(timerState.remaining >= 4,
  'countdown must derive remaining seconds from cycle_ready_at, not a stale initial snapshot');
const startedFactory = { id: 42, is_running: false, current_recipe: null, cycle_ready_at: null };
const startResult = {
  status: 'running',
  recipe_id: 'mine_coal',
  started_at: new Date(timerNow).toISOString(),
  ready_at: new Date(timerNow + 54000).toISOString(),
  duration_seconds: 54,
  remaining_seconds: 54,
};
applyCycleResult(startedFactory, startResult);
assert(startedFactory.is_running === true && startedFactory.current_recipe === 'mine_coal',
  'successful production start must immediately update local factory state');
assert(startedFactory.cycle_ready_at === startResult.ready_at && startedFactory.remaining_seconds === 54,
  'successful production start must copy the server deadline so the timer starts without tab navigation');

const marketCoreCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/market.js'), 'utf-8');
const appSourceCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/app.js'), 'utf-8');
const marketCommodityCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/market_commodities.js'), 'utf-8');
const marketFinanceCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/market_finance.js'), 'utf-8');
const marketCreditCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/market_credit.js'), 'utf-8');
const stockScreenCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/stocks.js'), 'utf-8');
const natApiCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/api.js'), 'utf-8');
assert(marketCoreCode.includes('finally'), 'market.js place order must have finally block to re-enable button');
assert(marketCoreCode.includes('renderCommodityCatalog'), 'commodity market must route to its material catalog');
assert(marketCommodityCode.includes('commodity-category-tab'), 'commodity market must expose category tabs');
assert(marketCommodityCode.includes('market-commodity-row'), 'commodity categories must use compact horizontal rows');
assert(marketCommodityCode.includes('data-commodity-item'), 'selecting a compact commodity row must open its trading screen');
assert(marketCommodityCode.includes('Моя продукция') && marketCommodityCode.includes('Нужно заводам') && marketCommodityCode.includes('Поиск'),
  'commodity market must offer search, own products and factory input categories');

// Every canonical production output must be selectable in the NPC market.
// The API is the source of truth; this regression test prevents a hard-coded
// subset from silently hiding outputs such as natural gas and copper.
assert(marketCoreCode.includes('mergeNpcRatesIntoMarketItems'),
  'market.js must merge every server NPC rate into the resource selector');
assert(marketCoreCode.includes('getIndustryOutputIds') && marketCoreCode.includes('prioritizeIndustryItems'),
  'market.js must prioritize products from the company\'s own industry');
assert(marketCoreCode.includes('finance.renderStocks') && marketFinanceCode.includes('market-ipo-open-btn') && marketFinanceCode.includes('market-ipo-dividend-rate'),
  'the reachable stocks section must expose IPO and its dividend policy');
assert(marketFinanceCode.includes('NatAPI.issueIPO'),
  'the reachable stocks section must submit the IPO request');
['market-ipo-dividend-rate', 'market-ipo-company-sale-pct', 'market-ipo-total-shares'].forEach((field) => {
  assert(marketFinanceCode.includes(field), `market IPO form must ask the user for ${field}`);
});
['ipo-dividend-rate', 'ipo-company-sale-pct', 'ipo-total-shares'].forEach((field) => {
  assert(stockScreenCode.includes(field), `stock screen IPO form must ask the user for ${field}`);
});
assert(marketFinanceCode.includes('market-dividend-rate-save') && stockScreenCode.includes('save-stock-dividend-rate'),
  'the issuer must be able to change dividend rate from both stock entry points');
assert(stockScreenCode.includes('company_sale_pct') && stockScreenCode.includes('total_shares')
  && marketFinanceCode.includes('company_sale_pct') && marketFinanceCode.includes('total_shares'),
  'both IPO entry points must submit company sale percentage and total shares');
assert(natApiCode.includes('updateStockDividendRate'),
  'stock API client must support dividend policy changes');
assert(appSourceCode.includes('overview.js?v=20260925_sabotages_v2'),
  'overview inventory fixes must be loaded from a fresh screen module');
assert(marketCoreCode.includes("market_credit.js?v=20260925_sabotages_v2"),
  'market credit screen must use a cache-busted module URL');
assert(marketCreditCode.includes("../api.js?v=20260925_sabotages_v2"),
  'credit screen must import the current API module containing state-credit methods');
const marketHelperCode = marketCoreCode
  .replace(/^import[^;]+;\s*$/gm, '')
  .replace(/export\s+function\s+mergeNpcRatesIntoMarketItems/, 'function mergeNpcRatesIntoMarketItems')
  .replace(/export\s+function\s+getIndustryOutputIds/, 'function getIndustryOutputIds')
  .replace(/export\s+function\s+prioritizeIndustryItems/, 'function prioritizeIndustryItems')
  .replace(/export\s+async\s+function\s+renderMarket[\s\S]*/, '')
  .replace(/export\s+function\s+renderMarket[\s\S]*/, '');
const commodityHelperCode = marketCommodityCode
  .replace(/^import[^;]+;\s*$/gm, '')
  .replace(/export\s+function\s+getCompanyInputIds/, 'function getCompanyInputIds')
  .replace(/export\s+function\s+renderCommodityCatalog[\s\S]*/, '');
const marketHelperFn = new Function(`${marketHelperCode}\nreturn { MARKET_ITEMS, getIndustryOutputIds, mergeNpcRatesIntoMarketItems, prioritizeIndustryItems };`);
const { MARKET_ITEMS: initialMarketItems, getIndustryOutputIds, mergeNpcRatesIntoMarketItems, prioritizeIndustryItems } = marketHelperFn();
const { getCompanyInputIds } = new Function(`${commodityHelperCode}\nreturn { getCompanyInputIds };`)();
const mergedMarketItems = mergeNpcRatesIntoMarketItems([
  { item_id: 'gas_natural', name: 'Природный газ', unit: 'тыс. м³', base_price: 45, npc_buy_price: 36, npc_sell_price: 56.25 },
  { item_id: 'energy', name: 'Электроэнергия', unit: 'МВт·ч', base_price: 10, npc_buy_price: 8, npc_sell_price: 12.5,
    daily_quota: null, remaining_npc_quota: null, liquidity_unlimited: true },
  { item_id: 'copper', name: 'Медь первичная', unit: 'т', base_price: 140, npc_buy_price: 112, npc_sell_price: 210 },
], initialMarketItems);
assert(mergedMarketItems.some(item => item.id === 'gas_natural'), 'natural gas must be visible in the NPC market');
assert(mergedMarketItems.some(item => item.id === 'copper'), 'copper must be visible in the NPC market');
const mergedCopper = mergedMarketItems.find(item => item.id === 'copper');
assert(mergedCopper.base === 140 && mergedCopper.buy === 112 && mergedCopper.sell === 210,
  'the market must show copper at the authoritative higher price and NPC spread');
const mergedEnergy = mergedMarketItems.find(item => item.id === 'energy');
assert(!('npcDemandRemainingQuota' in mergedEnergy) && !('npcDemandQuotaLabel' in mergedEnergy),
  'regular NPC market items must not carry the removed daily-liquidity quota into the UI');
assert(marketCommodityCode.includes('Моя продукция') && marketCommodityCode.includes("item.isIndustry"),
  'own-industry materials must have a dedicated product category');
assert(!marketCode.includes('hasNpcDemandQuota') && !marketCode.includes('npcDemandQuotaLabel'),
  'NPC sell controls must not disable or label ordinary trades by a daily liquidity quota');
assert(marketCode.includes('refreshNpcRates'),
  'NPC rates must still refresh after trades for prices and rare-resource availability');
const oilOutputs = getIndustryOutputIds('oilman', {
  pump_oil_crude: { specialization: 'oilman', outputs: { oil_crude: 4 } },
  pump_gas_field: { specialization: 'oilman', outputs: { gas_natural: 3.5 } },
  mine_coal: { specialization: 'miner', outputs: { coal: 5 } },
});
assert(oilOutputs.includes('oil_crude') && oilOutputs.includes('gas_natural') && !oilOutputs.includes('coal'),
  'industry output discovery must use recipe specialization and exact outputs');
const prioritizedMarketItems = prioritizeIndustryItems([
  { id: 'steel', name: 'Сталь' },
  { id: 'gas_natural', name: 'Природный газ' },
  { id: 'oil_crude', name: 'Сырая нефть' },
], oilOutputs);
assert(prioritizedMarketItems[0].id === 'gas_natural' && prioritizedMarketItems[1].id === 'oil_crude',
  'own-industry products must appear first in the market selector');
assert(prioritizedMarketItems[0].isIndustry === true && prioritizedMarketItems[2].isIndustry !== true,
  'own-industry products must be marked for yellow highlighting');
const companyInputs = getCompanyInputIds(
  [{ inputs_per_hour: { energy: 1, water: 0.5 } }],
  [{ building_type: 'sawmill', current_recipe: 'lumber' }],
  {
    lumber: { factory_type: 'sawmill', inputs: { wood_raw: 2, energy: 1 } },
    other: { factory_type: 'steelworks', inputs: { iron_ore: 3 } },
  },
);
assert(companyInputs.length === 3 && companyInputs.includes('energy') && companyInputs.includes('water') && companyInputs.includes('wood_raw'),
  'needed materials must combine deduplicated inputs from owned businesses and selected factory recipes');

const milCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/military.js'), 'utf-8');
assert(milCode.includes('joinAlliance'), 'military.js must support joining alliances');
assert(milCode.includes('PvE-границы'), 'military.js must expose PvE borders');
assert(milCode.includes('attackPveTarget'), 'military.js must wire PvE attacks');
assert(milCode.includes('Требования к армии'), 'PvE cards must explain mixed-army requirements');
assert(milCode.includes('force_composition'), 'PvE cards must explain when army composition blocks an attack');
assert(milCode.includes('attackTournamentTarget'), 'military.js must wire tournament PvP attacks');
assert(milCode.includes('getTournamentHistory'), 'military.js must show tournament history and personal results');
assert(milCode.includes('joinTournament'), 'military.js must submit tournament registration');
const tournamentUiCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/military_tournament.js'), 'utf-8');
assert(tournamentUiCode.includes('tournament-join-btn'), 'tournament screen must show a join button to non-participants');
assert(apiScript.includes('joinTournament:'), 'api.js must expose tournament registration');
assert(milCode.includes('Pivocoins') && milCode.includes('premium'), 'military.js must expose the separate Pivocoins premium branch');
assert(milCode.includes('purchasePremiumLicense') && milCode.includes('purchasePremiumUpgrade'), 'military.js must wire premium licenses and upgrades');
assert(milCode.includes('border_guards') && milCode.includes('aircraft'), 'military.js must render all six unit types');
assert(natHtml.includes('>Война<'), 'bottom navigation must call the military screen War');
assert(natHtml.includes('data-tab="leaderboard"'), 'bottom navigation must expose the Top screen');

const leaderboardCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/leaderboard.js'), 'utf-8');
assert(leaderboardCode.includes('getLeaderboard') && leaderboardCode.includes('military_rating'), 'leaderboard.js must expose all server-ranked categories');

const helpCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/help.js'), 'utf-8');
assert(helpCode.includes('Pivocoins') && helpCode.includes('IPO') && helpCode.includes('Война'), 'help.js must explain core company progression systems');

assert(marketFinanceCode.includes('getReferenceInstruments'), 'market finance module must load official reference instruments');
assert(marketFinanceCode.includes('tradeReferenceInstrument'), 'market finance module must wire reference trades');
assert(marketFinanceCode.includes("from '../market_chart.js") && marketCode.includes("from '../market_chart.js"), 'market modules must use the shared market chart renderer');
assert(marketFinanceCode.includes('item.history') && marketFinanceCode.includes('stock.history') && marketFinanceCode.includes('bond.history'),
  'market charts must use server-provided history for currencies, stocks and bonds');
assert(marketCode.includes('market-contrast-surface'), 'every market surface must use the readable princess contrast layer');
assert(marketFinanceCode.includes('createBondListing'), 'market finance module must expose secondary bond listings');
assert(marketFinanceCode.includes('getPortfolio') && marketFinanceCode.includes('renderPortfolio'),
  'market finance module must expose a unified portfolio for stocks, bonds, currencies and metals');
assert(marketFinanceCode.includes('payout_history') && marketFinanceCode.includes('История выплат') && marketFinanceCode.includes('next_dividend_at'),
  'portfolio must show payout history and the next expected share payout');
assert(marketCode.includes('market-section-btn') && marketFinanceCode.includes('renderStockDetail') && marketFinanceCode.includes('renderBondDetail'),
  'market modules must expose the agreed vertical market sections and drill-down cards');
assert((natHtml.match(/data-tab="stocks"/g) || []).length === 0,
  'stocks must be opened from the single Market tab, not a duplicate bottom tab');

const creatorCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/creator.js'), 'utf-8');
assert(creatorCode.includes('tourn-reward-first') && creatorCode.includes('tourn-reward-second') && creatorCode.includes('tourn-reward-third'),
  'creator.js must expose three independent custom tournament reward fields');
assert(creatorCode.includes('reward_first_pvc') && creatorCode.includes('reward_second_pvc') && creatorCode.includes('reward_third_pvc'),
  'creator.js must submit all three custom tournament rewards');
assert(creatorCode.includes('getCreatorPremiumLedger') && creatorCode.includes('Журнал PVC'),
  'creator.js must expose the auditable Pivocoins ledger');
assert(creatorPlayersCode.includes('getCreatorPlayers') && creatorPlayersCode.includes('Список игроков'),
  'creator player module must expose searchable player-company administration');


const upgradesCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/upgrades.js'), 'utf-8');
assert(upgradesCode.includes('upgrade_options'), 'upgrades.js must render server-authoritative upgrade options');
assert(!upgradesCode.includes('calcUpgrade('), 'upgrades.js must not duplicate upgrade price formulas');
assert(upgradesCode.includes('upgrade-help-btn'), 'blocked upgrades must link to relevant help');
assert(upgradesCode.includes('max_level') && upgradesCode.includes('Автозапуск'),
  'automation upgrade card must show the server max tier and explain the automatic cycle behavior');

const overviewCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/overview.js'), 'utf-8');
assert(overviewCode.includes('rename-company-btn') && overviewCode.includes('NatAPI.renameCompany'),
  'overview must expose company renaming for the 10,000 cash fee');
assert(overviewCode.includes('level_progress_pct') && overviewCode.includes('is_max_level') && overviewCode.includes('max_level'),
  'overview must render server-authoritative long-term level progress');
assert(!overviewCode.includes("((company.level || 1) * 150)"),
  'overview must not fall back to the obsolete ten-level linear XP formula');

const tycoonCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/tycoon.js'), 'utf-8');
assert(tycoonCode.includes('summary.progression') && tycoonCode.includes('xp_to_next'),
  'tycoon must render the server-authoritative company XP progress');
assert(tycoonCode.includes('work_xp_per_hour') && tycoonCode.includes('Продуктивная работа предприятия'),
  'tycoon must explain how productive business work earns XP');

const productionCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/production.js'), 'utf-8');
assert(productionCode.includes('production-help-btn'), 'empty production must link to relevant help');
assert(productionCode.includes('start_hint') && productionCode.includes('factory-next-step'), 'factory cards must show the server-derived next step');
assert(productionCode.includes('factory-details-btn') && productionCode.includes('factory-details-modal'),
  'production screen must expose a readable detailed factory view');
assert(productionCode.includes('factory-detail-card') && productionCode.includes('Входные ресурсы'),
  'detailed factory view must show inputs, outputs and cycle information');

const catalogCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/screens/catalog.js'), 'utf-8');
assert(catalogCode.includes('data-cat="unavailable"'), 'catalog.js must expose unavailable filter');
assert(catalogCode.includes('data-cat="recommended"') && catalogCode.includes('b.recommended_for_specialization'),
  'catalog.js must let players filter server-ranked factories in their industry');
assert(catalogCode.includes('res?.total') && !catalogCode.includes('Каталог предприятий (48)'),
  'catalog.js must show the actual server catalog size instead of a stale hard-coded count');
assert(catalogCode.includes('b.can_build') && !catalogCode.includes('compCash >= b.build_cost'),
  'catalog.js must render the server build decision without reproducing affordability logic');
assert(catalogCode.includes('b.profitability') && catalogCode.includes('b.build_cost'),
  'catalog.js must render server profitability estimates and mastery-adjusted build cost');
assert(catalogCode.includes('Списано ${paid}'),
  'successful construction must show the amount the server actually charged');
assert(catalogCode.includes('flex-wrap'), 'catalog filters must wrap instead of hiding actions beyond a narrow mobile viewport');

const appCode = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/app.js'), 'utf-8');
assert(!appCode.includes('Откройте НАТБИРЖУ из Telegram'),
  'Natbirzha must not block browser guests behind the Telegram-only screen');
assert(appCode.includes("msgText === '[object Object]'"), 'app.js showToast must guard against [object Object]');
assert(appCode.includes('window.NatApp'), 'app.js must expose window.NatApp');
assert(appCode.includes('navigateTo'), 'app.js must export navigateTo');
assert(appCode.includes('activeRenderPromise'), 'app.js must serialize overlapping async screen renders');
assert(appCode.includes('renderRequested'), 'app.js must coalesce rapid tab switches to the latest tab');
assert(appCode.includes('navigationId') && appCode.includes('AbortController'), 'app.js must cancel stale navigation requests');
assert(appCode.includes('renderContainer') && appCode.includes('container.replaceChildren(renderContainer)'), 'a stale screen must render off-DOM before it can be mounted');
assert(apiScript.includes('setNavigationAbortSignal'), 'api.js must attach the active navigation abort signal to requests');
assert(apiScript.includes("getRecipes: () => cachedGet") && apiScript.includes("getBuildingsCatalog: () => cachedGet"), 'Recipes and enterprise catalog must be cached');
assert(marketCode.includes('orderbookRequestId') && marketCode.includes('requestId !== orderbookRequestId'), 'Market must ignore a slow orderbook response for an older resource');
assert(appCode.includes('user?.is_creator === true'), 'creator UI must rely on server-provided creator flag');
assert(!appCode.includes('1053722876'), 'creator UI must not hardcode privileged Telegram IDs');

const commonAppCode = fs.readFileSync(path.join(__dirname, '../frontend/js/app.js'), 'utf-8');
assert(commonAppCode.includes('me.is_tester || me.role === "admin"'),
  'common Mini App must expose Natbirzha to the effective configured admin role');
assert(commonAppCode.includes('prepareNatbirzhaNavigation'),
  'common Mini App must provide prepareNatbirzhaNavigation');
console.log('All screen modules and app.js integration verified!');

console.log('=== [Natbirzha Test 5/5] Testing games.js Natbirzha banner exposure & items localization ===');
const gamesCode = fs.readFileSync(path.join(__dirname, '../frontend/js/games.js'), 'utf-8');
assert(gamesCode.includes('НАТБИРЖА'), 'games.js must contain Natbirzha banner definition');
assert(!gamesCode.includes('${isTesterUser ? `<a href="/app/natbirzha"'), 'games.js must not restrict Natbirzha banner to testers');
assert(!gamesCode.includes('>Beta<'), 'games.js must not contain Beta badge');
assert(gamesCode.includes('/app/natbirzha'), 'Natbirzha banner must link to /app/natbirzha');
assert(gamesCode.includes('prepareNatbirzhaNavigation'),
  'Natbirzha banner must call prepareNatbirzhaNavigation to carry over Telegram auth');

const itemsScript = fs.readFileSync(path.join(__dirname, '../frontend/natbirzha/js/items.js'), 'utf-8');
const cleanedItemsScript = itemsScript.replace(/export\s+const\s+ITEMS\s+=/, 'const ITEMS =').replace(/export\s+function\s+getItemInfo/, 'function getItemInfo');
const itemsFn = new Function(cleanedItemsScript + '\nreturn { ITEMS, getItemInfo };');
const { ITEMS, getItemInfo } = itemsFn();
assert(ITEMS.water && ITEMS.water.name === 'Техническая вода', 'water must map to Russian name');
assert(ITEMS.grid_quota && ITEMS.grid_quota.name === 'Квота энергосети', 'grid_quota must map to Russian name');
assert(ITEMS.steel && ITEMS.steel.name === 'Конструкционная сталь', 'steel must map to Russian name');
assert(getItemInfo('WATER').name === 'Техническая вода', 'getItemInfo must be case-insensitive');
assert(getItemInfo('UNKNOWN_X').icon === '📦', 'getItemInfo must have safe fallback');

assert(overviewCode.includes('getItemInfo'), 'overview.js must use getItemInfo for warehouse items');
console.log('Natbirzha banner in games.js and items.js localization verified!');

console.log('\n🌟 ALL NATBIRZHA FRONTEND TESTS PASSED WITH 100% SUCCESS! 🌟');
