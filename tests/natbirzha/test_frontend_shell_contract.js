const fs = require('fs');
const path = require('path');
const assert = require('assert');

console.log('=== [Natbirzha Test 1/5] Testing index.html markup & theme sync ===');
const natHtml = fs.readFileSync(path.join(__dirname, '../../frontend/natbirzha/index.html'), 'utf-8');
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
assert(natHtml.includes('app.js?v=20260925_grant_v1') || natHtml.includes('app.js?v=20260925_deals_v9') || natHtml.includes('app.js?v=20260925_deals_v8') || natHtml.includes('app.js?v=20260925_deals_v7') || natHtml.includes('app.js?v=20260925_supply_deals'), 'Natbirzha entrypoint must refresh its cached code after a release');
assert(natHtml.includes('syncTgTheme'), 'index.html must define syncTgTheme');
assert(natHtml.includes("window.Telegram?.WebApp?.onEvent?.('themeChanged'"), 'index.html must safely listen to themeChanged');
console.log('index.html structure and scripts verified!');

const princessTheme = fs.readFileSync(path.join(__dirname, '../../frontend/natbirzha/css/princess-theme.css'), 'utf-8');
['--princess-pink', '.princess-sky', '.nav-tab.active', '@media (prefers-reduced-motion: reduce)'].forEach(token => {
  assert(princessTheme.includes(token), `princess theme must define ${token}`);
});
  assert(princessTheme.split('\n').length <= 400,
    'princess theme must stay within the repository source-file limit');
  assert(princessTheme.includes('.dark .bg-slate-50') && princessTheme.includes('.dark .bg-white'),
    'dark princess theme must override light card utilities instead of rendering grey/white cards');

  const upgradesScreen = fs.readFileSync(path.join(__dirname, '../../frontend/natbirzha/js/screens/upgrades.js'), 'utf-8');
  assert(upgradesScreen.includes('upgrade-locked-btn'),
    'locked upgrade controls must have a dedicated readable visual treatment');
  assert(!upgradesScreen.includes('bg-slate-800/60 text-slate-500 py-2 text-[10px] font-bold cursor-not-allowed'),
    'locked upgrade controls must not be rendered as low-contrast grey buttons');

  const overviewScreen = fs.readFileSync(path.join(__dirname, '../../frontend/natbirzha/js/screens/overview.js'), 'utf-8');
  assert(overviewScreen.includes('capital_plan'),
    'overview must render the API capital plan when a company reaches its capital milestone');
  assert(overviewScreen.includes('capital-plan-ipo-btn'),
    'capital plan must offer a direct, reachable IPO action');
  assert(overviewScreen.includes('mastery-progress'),
    'overview must display the unbounded mastery track after level 60');
  assert(overviewScreen.includes('inventoryReserved') && overviewScreen.includes('В заявках:'),
    'overview must distinguish available inventory from quantities reserved in active sale orders');

  const militaryScreen = fs.readFileSync(path.join(__dirname, '../../frontend/natbirzha/js/screens/military.js'), 'utf-8');
  assert(militaryScreen.includes('target.cooldown_until'),
    'PvE screen must expose the two-hour repeat-attack cooldown to the player');
  assert(!militaryScreen.includes('!target.available || target.conquered'),
    'a historical PvE victory must not permanently disable the rematch button');
  assert(militaryScreen.includes('campaign_rank'),
    'PvE screen must show the escalating frontier campaign rank');

console.log('=== [Natbirzha Test 2/5] Testing state.js reactivity & non-destructive updates ===');
const stateScript = fs.readFileSync(path.join(__dirname, '../../frontend/natbirzha/js/state.js'), 'utf-8');
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
const apiScript = fs.readFileSync(path.join(__dirname, '../../frontend/natbirzha/js/api.js'), 'utf-8');
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
  'login', 'getMyCompany', 'expandBusinessCapacity', 'createCompany', 'respecCompany',
  'upgradeAllBusinesses',
  'getProductionStatus', 'getRecipes',
  'getOrderbook', 'getNpcRates', 'placeOrder', 'cancelOrder', 'npcTrade', 'getTaxStatus', 'payTax',
  'getStocksList', 'issueIPO', 'buyShares', 'getPortfolio',
  'getMilitaryStatus', 'recruitUnits', 'getCurrentTournament', 'joinAlliance',
  'getPveTargets', 'scoutPveTarget', 'attackPveTarget', 'getBattleHistory',
  'getTournamentTargets', 'attackTournamentTarget', 'getTournamentHistory',
  'getReferenceInstruments', 'tradeReferenceInstrument',
  'getStateBonds', 'createBondListing', 'buyBondListing', 'cancelBondListing',
  'getIndustryUpgradeCatalog', 'getIndustryUpgrade', 'purchaseIndustryUpgrade',
  'getCreatorWorldResetPreview', 'resetCreatorWorld',
  'getStateCredit', 'requestStateCredit', 'repayStateCredit', 'renameCompany'
];
requiredMethods.forEach(m => {
  assert(typeof NatAPI[m] === 'function', `NatAPI.${m} must be defined`);
});
assert(apiScript.includes('joinTournament:'), 'api.js must expose tournament registration');
['getSupplyDealCompanies', 'getSupplyDealCompanyResources', 'createSupplyDeal', 'getSupplyDeals', 'acceptSupplyDeal', 'rejectSupplyDeal', 'cancelSupplyDeal']
  .forEach(m => assert(apiScript.includes(`${m}:`), `api.js must expose ${m}`));
console.log('api.js methods, auth headers and error handling resilience verified!');

const marketScreen = fs.readFileSync(path.join(__dirname, '../../frontend/natbirzha/js/screens/market.js'), 'utf-8');
assert(marketScreen.includes("market_deals.js?v=20260925_supply_deals"), 'Market must load the separately cached deal screen');
assert(marketScreen.indexOf('data-section="state_credit"') < marketScreen.indexOf('data-section="deals"'),
  'Deals must be the final section in the market menu');
