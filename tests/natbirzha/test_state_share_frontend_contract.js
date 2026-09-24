const fs = require('fs');
const path = require('path');
const assert = require('assert');

const root = path.join(__dirname, '../..');
const read = (relativePath) => {
  const fullPath = path.join(root, relativePath);
  return fs.existsSync(fullPath) ? fs.readFileSync(fullPath, 'utf8') : '';
};

const api = read('frontend/natbirzha/js/api.js');
const creator = read('frontend/natbirzha/js/screens/creator.js');
const creatorShares = read('frontend/natbirzha/js/screens/creator_shares.js');
const stocks = read('frontend/natbirzha/js/screens/stocks.js');
const marketShares = read('frontend/natbirzha/js/screens/state_share_market.js');
const marketFinance = read('frontend/natbirzha/js/screens/market_finance.js');
const market = read('frontend/natbirzha/js/screens/market.js');
const bankruptcyMarket = read('frontend/natbirzha/js/screens/bankruptcy_market.js');

[
  'getStateShares', 'buyStateShares', 'sellStateShares',
  'getCreatorShares', 'issueCreatorShares',
].forEach((method) => assert(api.includes(`${method}:`), `NatAPI must expose ${method}`));
[
  "request('/api/natbirzha/shares')",
  "request('/api/natbirzha/creator/shares')",
  "request('/api/natbirzha/creator/shares/issue'",
].forEach((endpoint) => assert(api.includes(endpoint), `NatAPI must use ${endpoint}`));

assert(creator.includes('data-tab="shares"') && creator.includes('loadCreatorShares'),
  'the State panel must expose a dedicated government shares tab');
[
  'share-title', 'share-purpose', 'share-volume', 'share-price',
  'share-projected-profit', 'share-dividend-rate',
].forEach((field) => assert(creatorShares.includes(field), `state share issuance must include ${field}`));
assert(creatorShares.includes('NatAPI.issueCreatorShares') && creatorShares.includes('NatAPI.getCreatorShares'),
  'the State panel must manually issue shares and reload its issue list');
assert(creatorShares.includes('не пополняет казну') && creatorShares.includes('confirm('),
  'issuance must explain and confirm that shares themselves do not create Treasury cash');

assert(stocks.includes('renderBankruptcyMarket') && stocks.includes('Рынок банкротов'),
  'the securities screen must link to the bankruptcy asset market');
assert(marketShares.includes('NatAPI.getStateShares') && marketShares.includes('NatAPI.getPortfolio'),
  'the player screen must load state share issues and portfolio holdings');
assert(marketFinance.includes('renderStateShareMarket') && marketFinance.includes('state_shares'),
  'the reachable Market screen must open the state share market and portfolio section');
assert(market.includes('data-section="bankruptcy_market"') && market.includes('renderBankruptcyMarket'),
  'the main Market menu must provide a route to the bankruptcy asset market');
assert(api.includes('getBankruptcyMarketLots:') && api.includes('buyBankruptcyMarketLot:'),
  'NatAPI must expose bankruptcy market listing and purchase methods');
assert(bankruptcyMarket.includes('cost_basis') && bankruptcyMarket.includes('state_premium')
  && bankruptcyMarket.includes('buyBankruptcyMarketLot') && bankruptcyMarket.includes('Рынок банкротов'),
  'the bankruptcy market must show cost basis, state premium, and purchase controls');
assert(marketShares.includes('NatAPI.buyStateShares') && marketShares.includes('NatAPI.sellStateShares'),
  'the player screen must let players buy from and redeem shares with the Treasury');
assert(marketShares.includes('remaining_volume') && marketShares.includes('dividends_earned'),
  'state share offers and holdings must show available supply and earned dividends');
assert(marketShares.includes('shares_held') && marketShares.includes('state_share_dividend_payments'),
  'state share screen must show the company position and past government dividends');
['issue_price', 'projected_annual_profit', 'dividend_rate_pct'].forEach((field) => {
  assert(marketShares.includes(field), `state share offers must show ${field}`);
});
assert(marketShares.includes('escapeHtml') && creatorShares.includes('escapeHtml'),
  'creator-entered issue text must be escaped before rendering');
assert(creatorShares.includes('showFeedback(successMessage, \'success\')')
  && creatorShares.includes('target.textContent = message'),
  'creator-specific success detail must be written as text content');
const sharedApiImport = "from '../api.js?v=20260921_broker1';";
assert(marketShares.includes(sharedApiImport) && creatorShares.includes(sharedApiImport),
  'new screens must share the app API module instance that receives the navigation abort signal');
assert((marketShares.match(/error\?\.name === 'AbortError'/g) || []).length >= 2,
  'state share load and trade handlers must ignore aborted requests');
assert(!marketShares.includes("getMyCompany().catch(() => null)")
  && marketShares.includes("if (error?.name === 'AbortError') throw error"),
  'balance refresh must propagate aborts to the trade handler before it can toast or redraw');
assert(creatorShares.includes("showToast('Выпуск государственных акций создан.'")
  && !creatorShares.includes('showToast(successMessage'),
  'creator success toast must not interpolate the creator-entered issue title');
assert(creatorShares.includes("showToast(escapeHtml(message), 'error')")
  && marketShares.includes("showToast(escapeHtml(error.message || 'Не удалось выполнить операцию.'), 'error')"),
  'dynamic creator error text must be escaped before reaching the HTML-rendered toast');
assert(marketShares.includes('let stateShareRenderGeneration = 0')
  && marketShares.includes('const generation = ++stateShareRenderGeneration')
  && marketShares.includes('const isCurrent = () => generation === stateShareRenderGeneration'),
  'state share rendering must have a generation token for internal Market navigation');
assert((marketShares.match(/if \(!isCurrent\(\)\) return;/g) || []).length >= 3
  && (marketShares.match(/error\?\.name === 'AbortError' \|\| !isCurrent\(\)/g) || []).length >= 2,
  'state share load and trade handlers must stop before stale DOM, store, or toast updates');
const invalidateIndex = marketShares.indexOf('stateShareRenderGeneration += 1;');
const backCallIndex = marketShares.indexOf('onBack();', invalidateIndex);
assert(invalidateIndex >= 0 && backCallIndex > invalidateIndex,
  'the state share back button must invalidate pending renders before returning to Market home');
assert((marketShares.match(/addEventListener\('click', returnToMarket\)/g) || []).length === 2,
  'both the normal and load-error back buttons must invalidate pending state share renders');
assert(marketShares.includes('let tradePending = false')
  && marketShares.includes("container.querySelectorAll('.state-share-buy, .state-share-sell')")
  && marketShares.includes('if (tradePending || !isCurrent()) return;')
  && marketShares.includes('setTradeButtonsPending(true)')
  && marketShares.includes('setTradeButtonsPending(false)'),
  'one pending state share trade must lock all buy/sell controls and restore them on current-generation errors');

console.log('State share creator and player UI contracts verified.');
