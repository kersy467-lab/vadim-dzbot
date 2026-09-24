/**
 * Natbirzha API Client
 * Handles Telegram initData or browser guest authentication and Idempotency-Key generation.
 */

import {
  generateUUID,
  getTelegramInitData,
  clearStaleInitData,
  getTelegramUserId,
  getAuthHeader,
} from './auth.js';

// App navigation owns this signal. A request started for a screen that the
// player has already left must not keep the old screen alive.
let navigationAbortSignal = null;
export function setNavigationAbortSignal(signal) {
  navigationAbortSignal = signal || null;
}

// Immutable catalog-like responses are reused briefly across tabs. Dynamic
// balances, inventories and order books intentionally never enter this cache.
const responseCache = new Map();

function cachedGet(endpoint, ttlMs) {
  const now = Date.now();
  const cached = responseCache.get(endpoint);
  if (cached && cached.expiresAt > now) return Promise.resolve(cached.data);

  return request(endpoint).then((data) => {
    responseCache.set(endpoint, { data, expiresAt: Date.now() + ttlMs });
    return data;
  });
}

const REASON_MAP = {
  'insufficient_inventory': 'Недостаточно ресурсов на складе',
  'insufficient_cash': 'Недостаточно cash на балансе',
  'maximum_territory_limit': 'Достигнут максимум территории',
  'factory_not_found': 'Предприятие не найдено',
  'company_not_found': 'Компания не найдена',
  'npc_rare_reserve_empty': 'Редкий запас Госрезерва на сегодня закончился',
  'inventory_overflow': 'Склад переполнен',
  'cooldown': 'Эта цель недавно проиграла вам. Повторная атака будет доступна через 2 часа',
  'tournament_not_active': 'PvP доступно только во время активного турнира',
  'tournament_not_found': 'Турнир не найден',
  'attacker_not_participant': 'Ваша компания не участвует в этом турнире',
  'target_not_participant': 'Выбранная компания не участвует в турнире',
  'self_attack': 'Нельзя атаковать собственную компанию',
  'empty_army': 'Сначала сформируйте армию',
  'target_empty_army': 'У цели не осталось армии',
  'insufficient_ground_force': 'Для захвата нужна выжившая наземная армия',
  'insufficient_supply': 'Недостаточно продовольствия, топлива или военного снаряжения для операции',
  'already_conquered': 'Эта PvE-корпорация уже захвачена',
  'prerequisite': 'Сначала захватите предыдущую PvE-корпорацию',
  'company_level': 'Уровень компании слишком низкий для этой цели',
};

function parseErrorMessage(data, status) {
  if (!data) return `Ошибка сервера (${status})`;
  if (typeof data === 'string') return data;

  const detail = data.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map(e => e.msg || e.message || (typeof e === 'object' ? JSON.stringify(e) : String(e))).join('; ');
  }
  if (detail && typeof detail === 'object') {
    if (typeof detail.error === 'string') return detail.error;
    if (typeof detail.reason === 'string') return REASON_MAP[detail.reason] || detail.reason;
    if (typeof detail.message === 'string') return detail.message;
    return JSON.stringify(detail);
  }
  if (typeof data.message === 'string') return data.message;
  if (typeof data.error === 'string') return data.error;
  if (data.reason && typeof data.reason === 'string') return data.reason;
  return `Ошибка сервера (${status})`;
}

async function request(endpoint, options = {}) {
  const url = endpoint.startsWith('/') ? endpoint : `/api/natbirzha/${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...getAuthHeader(),
    ...(options.headers || {}),
  };

  // Add Idempotency-Key for state-modifying requests
  if (options.method && !['GET', 'HEAD', 'OPTIONS'].includes(options.method.toUpperCase())) {
    if (!headers['Idempotency-Key']) {
      headers['Idempotency-Key'] = generateUUID();
    }
  }

  const response = await fetch(url, {
    ...options,
    headers,
    signal: options.signal || navigationAbortSignal || undefined,
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    // On 401: purge stale cached initData and retry once with guest auth ONLY if not inside Telegram
    const isInsideTg = typeof window !== 'undefined' && Boolean(window.Telegram?.WebApp?.initData);
    if (response.status === 401 && !options._authRetried && !isInsideTg) {
      clearStaleInitData();
      const retryHeaders = {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
        ...(options.headers || {}),
      };
      const retryResp = await fetch(url, {
        ...options,
        headers: retryHeaders,
        signal: options.signal || navigationAbortSignal || undefined,
      });
      const retryData = await retryResp.json().catch(() => ({}));
      if (!retryResp.ok) {
        const errMsg = parseErrorMessage(retryData, retryResp.status);
        const err = new Error(errMsg);
        err.status = retryResp.status;
        err.data = retryData;
        throw err;
      }
      return retryData;
    }
    const errorMsg = parseErrorMessage(data, response.status);
    const error = new Error(errorMsg);
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data;
}

export const NatAPI = {
  // Auth & Company
  login: () => request('/api/natbirzha/auth/login', { method: 'POST' }),
  getMyCompany: () => request('/api/natbirzha/company/me'),
  expandTerritory: () => request('/api/natbirzha/company/territory/expand', { method: 'POST' }),
  getBusinessCapacity: () => request('/api/natbirzha/company/business-capacity'),
  expandBusinessCapacity: () => request('/api/natbirzha/company/business-capacity/expand', { method: 'POST' }),
  createCompany: (payload) => request('/api/natbirzha/company/create', { method: 'POST', body: JSON.stringify(payload) }),
  respecCompany: (specialization) => request('/api/natbirzha/company/respec', { method: 'POST', body: JSON.stringify({ new_specialization: specialization }) }),
  unlockMastery: (branch) => request('/api/natbirzha/company/mastery/unlock', { method: 'POST', body: JSON.stringify({ branch }) }),
  getLoans: () => request('/api/natbirzha/finance/loans'),
  borrow: (principal) => request('/api/natbirzha/finance/loans', { method: 'POST', body: JSON.stringify({ principal: Number(principal) }) }),
  repayLoan: (loan_id, amount) => request(`/api/natbirzha/finance/loans/${parseInt(loan_id, 10)}/repay`, { method: 'POST', body: JSON.stringify({ amount: Number(amount) }) }),
  getStateCredit: () => request('/api/natbirzha/finance/state-loans'),
  requestStateCredit: (principal, term_days) => request('/api/natbirzha/finance/state-loans', {
    method: 'POST', body: JSON.stringify({ principal: Number(principal), term_days: parseInt(term_days, 10) })
  }),
  repayStateCredit: (loan_id, amount) => request(`/api/natbirzha/finance/state-loans/${parseInt(loan_id, 10)}/repay`, {
    method: 'POST', body: JSON.stringify({ amount: Number(amount) })
  }),
  renameCompany: (name) => request('/api/natbirzha/company/rename', {
    method: 'POST', body: JSON.stringify({ name: String(name || '').trim() })
  }),

  getIndustryOverview: () => cachedGet('/api/natbirzha/company/industries', 30 * 1000),

  // NATBIRZHA 2.0 idle/tycoon businesses
  getBusinessCatalog: () => cachedGet('/api/natbirzha/businesses/catalog', 5 * 60 * 1000),
  getEmpireSummary: () => request('/api/natbirzha/company/empire-summary'),
  openBusiness: (business_type, custom_name = null) => request('/api/natbirzha/businesses/open', {
    method: 'POST',
    body: JSON.stringify({ business_type, custom_name }),
  }),
  upgradeBusiness: (business_id) => request(`/api/natbirzha/businesses/${parseInt(business_id, 10)}/upgrade`, { method: 'POST' }),
  upgradeAllBusinesses: () => request('/api/natbirzha/businesses/upgrade-all', { method: 'POST' }),
  pauseBusiness: (business_id) => request(`/api/natbirzha/businesses/${parseInt(business_id, 10)}/pause`, { method: 'POST' }),
  resumeBusiness: (business_id) => request(`/api/natbirzha/businesses/${parseInt(business_id, 10)}/resume`, { method: 'POST' }),
  sellBusiness: (business_id) => request(`/api/natbirzha/businesses/${parseInt(business_id, 10)}/sell`, { method: 'POST' }),
  setBusinessSaleMode: (business_id, mode) => request(`/api/natbirzha/businesses/${parseInt(business_id, 10)}/sale-mode`, { method: 'PUT', body: JSON.stringify({ mode }) }),
  setBusinessSupplyPolicy: (business_id, item_id, policy) => request(`/api/natbirzha/businesses/${parseInt(business_id, 10)}/supply/${encodeURIComponent(item_id)}`, { method: 'PUT', body: JSON.stringify(policy) }),
  getBusinessAssetCatalog: () => cachedGet('/api/natbirzha/business-assets/catalog', 5 * 60 * 1000),
  purchaseBusinessVehicle: (business_id, vehicle_type) => request('/api/natbirzha/business-assets/vehicles', { method: 'POST', body: JSON.stringify({ business_id: parseInt(business_id, 10), vehicle_type }) }),
  repairBusinessVehicle: (vehicle_id) => request(`/api/natbirzha/business-assets/vehicles/${parseInt(vehicle_id, 10)}/repair`, { method: 'POST' }),
  hireBusinessEmployee: (business_id, role) => request('/api/natbirzha/business-assets/employees', { method: 'POST', body: JSON.stringify({ business_id: parseInt(business_id, 10), role }) }),
  fireBusinessEmployee: (employee_id) => request(`/api/natbirzha/business-assets/employees/${parseInt(employee_id, 10)}`, { method: 'DELETE' }),
  startBusinessProject: (business_id, project_type) => request('/api/natbirzha/business-assets/projects', { method: 'POST', body: JSON.stringify({ business_id: parseInt(business_id, 10), project_type }) }),

  // Production & Buildings
  getProductionStatus: () => request('/api/natbirzha/production/factories'),
  getRecipes: () => cachedGet('/api/natbirzha/production/recipes', 5 * 60 * 1000),
  getInventory: () => request('/api/natbirzha/production/inventory'),
  getBuildingsCatalog: () => cachedGet('/api/natbirzha/buildings/catalog', 5 * 60 * 1000),
  getBuildingDetails: (factory_id) => request(`/api/natbirzha/buildings/${factory_id}`),
  getFactoryUpgrades: (factory_id) => request(`/api/natbirzha/factories/${factory_id}/upgrades`),
  buildEnterprise: (building_type) => request('/api/natbirzha/buildings/build', {
    method: 'POST',
    body: JSON.stringify({ building_type })
  }),
  buildFactory: (factory_type) => request('/api/natbirzha/buildings/build', {
    method: 'POST',
    body: JSON.stringify({ building_type: factory_type, factory_type })
  }),
  triggerProduction: (factory_id, recipe_id) => request('/api/natbirzha/production/factory/produce', {
    method: 'POST',
    body: JSON.stringify({ factory_id: parseInt(factory_id, 10), recipe_id })
  }),
  setFactoryAutomation: (factory_id, enabled) => request(`/api/natbirzha/production/factories/${parseInt(factory_id, 10)}/automation`, {
    method: 'POST',
    body: JSON.stringify({ enabled: Boolean(enabled) })
  }),

  upgradeFactory: (factory_id, upgrade_type) => request('/api/natbirzha/factories/' + factory_id + '/upgrade', { method: 'POST', body: JSON.stringify({ upgrade_type }) }),

  // Market
  getOrderbook: (item_id) => request(`/api/natbirzha/market/orderbook?item_id=${item_id}`),
  getNpcRates: () => request('/api/natbirzha/market/npc/rates'),
  placeOrder: (payload) => request('/api/natbirzha/market/order/place', { method: 'POST', body: JSON.stringify(payload) }),
  cancelOrder: (order_id) => request('/api/natbirzha/market/order/cancel', { method: 'POST', body: JSON.stringify({ order_id: parseInt(order_id, 10) }) }),
  npcTrade: (payload) => request('/api/natbirzha/market/npc/trade', { method: 'POST', body: JSON.stringify(payload) }),
  getTaxStatus: () => request('/api/natbirzha/tax'),
  payTax: (amount = null) => request('/api/natbirzha/tax/pay', { method: 'POST', body: JSON.stringify({ amount }) }),

  // Stocks & IPO
  getStocksList: () => request('/api/natbirzha/stocks/market'),
  issueIPO: (payload = {}) => request('/api/natbirzha/stocks/ipo/apply', { method: 'POST', body: JSON.stringify(payload) }),
  updateStockDividendRate: (stock_id, dividend_rate_pct) => request(`/api/natbirzha/stocks/${parseInt(stock_id, 10)}/dividend-rate`, { method: 'POST', body: JSON.stringify({ dividend_rate_pct: Number(dividend_rate_pct) }) }),
  buyShares: (stock_id, shares_count) => request('/api/natbirzha/stocks/buy', { method: 'POST', body: JSON.stringify({ stock_id: parseInt(stock_id, 10), shares_count: parseInt(shares_count, 10) }) }),
  sellShares: (stock_id, shares_count) => request('/api/natbirzha/stocks/sell', { method: 'POST', body: JSON.stringify({ stock_id: parseInt(stock_id, 10), shares_count: parseInt(shares_count, 10) }) }),
  getPortfolio: () => request('/api/natbirzha/portfolio'),
  getStockPortfolio: () => request('/api/natbirzha/stocks/portfolio'),
  getStockHistory: (stock_id) => request(`/api/natbirzha/stocks/${parseInt(stock_id, 10)}/history`),
  getStockOrderbook: (stock_id) => request(`/api/natbirzha/stocks/${parseInt(stock_id, 10)}/orderbook`),
  placeStockOrder: (stock_id, side, quantity, price) => request(`/api/natbirzha/stocks/${parseInt(stock_id, 10)}/orders`, { method: 'POST', body: JSON.stringify({ side, quantity: parseInt(quantity, 10), price: parseFloat(price) }) }),
  cancelStockOrder: (order_id) => request(`/api/natbirzha/stocks/orders/${parseInt(order_id, 10)}`, { method: 'DELETE' }),

  // Military, Alliances & Tournaments
  getMilitaryStatus: () => request('/api/natbirzha/military/status'),
  recruitUnits: (unit_type, count) => request('/api/natbirzha/military/recruit', { method: 'POST', body: JSON.stringify({ unit_type, count: parseInt(count, 10) }) }),
  upgradeMilitaryInfrastructure: (facility) => request(`/api/natbirzha/military/infrastructure/${encodeURIComponent(facility)}/upgrade`, { method: 'POST' }),
  getCurrentTournament: () => request('/api/natbirzha/military/tournaments/current'),
  joinTournament: (tournament_id) => request(`/api/natbirzha/military/tournaments/${parseInt(tournament_id, 10)}/join`, { method: 'POST' }),
  getPveTargets: () => request('/api/natbirzha/military/pve/targets'),
  scoutPveTarget: (target_code) => request(`/api/natbirzha/military/pve/targets/${encodeURIComponent(target_code)}/scout`, { method: 'POST' }),
  attackPveTarget: (target_code) => request(`/api/natbirzha/military/pve/targets/${encodeURIComponent(target_code)}/attack`, { method: 'POST' }),
  getBattleHistory: () => request('/api/natbirzha/military/battles'),
  getTournamentHistory: () => request('/api/natbirzha/military/tournaments/history'),
  getTournamentTargets: (tournament_id) => request(`/api/natbirzha/military/tournaments/${parseInt(tournament_id, 10)}/targets`),
  attackTournamentTarget: (tournament_id, company_id) => request(`/api/natbirzha/military/tournaments/${parseInt(tournament_id, 10)}/targets/${parseInt(company_id, 10)}/attack`, { method: 'POST' }),
  joinAlliance: (alliance_id) => request('/api/natbirzha/military/alliance/join', { method: 'POST', body: JSON.stringify({ alliance_id: parseInt(alliance_id, 10) }) }),

  // Official-reference instruments (server prices only)
  getReferenceInstruments: () => cachedGet('/api/natbirzha/instruments', 30 * 1000),
  tradeReferenceInstrument: (instrument_code, side, quantity) => request('/api/natbirzha/instruments/trade', {
    method: 'POST',
    body: JSON.stringify({ instrument_code, side, quantity: parseFloat(quantity) })
  }),

  // Bankruptcy
  getBankruptcyStatus: () => request('/api/natbirzha/bankruptcy/status'),
  submitRestructuring: () => request('/api/natbirzha/bankruptcy/file', { method: 'POST' }),
  resetCompany: () => request('/api/natbirzha/company/reset', { method: 'POST' }),

  // State bonds (player-facing purchase; treasury receives only transferred player cash)
  getStateBonds: () => request('/api/natbirzha/bonds'),
  buyStateBonds: (bond_id, quantity) => request(`/api/natbirzha/bonds/${bond_id}/buy`, {
    method: 'POST',
    body: JSON.stringify({ quantity: parseInt(quantity, 10) })
  }),
  createBondListing: (bond_id, quantity, unit_price) => request('/api/natbirzha/bonds/listings', {
    method: 'POST',
    body: JSON.stringify({ bond_id: parseInt(bond_id, 10), quantity: parseInt(quantity, 10), unit_price: parseFloat(unit_price) })
  }),
  buyBondListing: (listing_id) => request(`/api/natbirzha/bonds/listings/${parseInt(listing_id, 10)}/buy`, { method: 'POST' }),
  cancelBondListing: (listing_id) => request(`/api/natbirzha/bonds/listings/${parseInt(listing_id, 10)}`, { method: 'DELETE' }),

  // Creator-issued state shares (fixed-price Treasury instruments)
  getStateShares: () => request('/api/natbirzha/shares'),
  buyStateShares: (share_id, quantity) => request(`/api/natbirzha/shares/${parseInt(share_id, 10)}/buy`, {
    method: 'POST', body: JSON.stringify({ quantity: parseInt(quantity, 10) })
  }),
  sellStateShares: (share_id, quantity) => request(`/api/natbirzha/shares/${parseInt(share_id, 10)}/sell`, {
    method: 'POST', body: JSON.stringify({ quantity: parseInt(quantity, 10) })
  }),

  // Confiscated factories from forced bankruptcies; buyers may come from any industry.
  getBankruptcyMarketLots: () => request('/api/natbirzha/bankruptcy-market'),
  buyBankruptcyMarketLot: (lot_id) => request(`/api/natbirzha/bankruptcy-market/lots/${parseInt(lot_id, 10)}/buy`, { method: 'POST' }),

  // Pivocoins and time-limited premium branch
  getPremiumWallet: () => request('/api/natbirzha/premium/wallet'),
  getPremiumLedger: () => request('/api/natbirzha/premium/ledger'),
  getPremiumLicenseCatalog: () => cachedGet('/api/natbirzha/premium/licenses/catalog', 5 * 60 * 1000),
  getPremiumLicenses: () => request('/api/natbirzha/premium/licenses'),
  purchasePremiumLicense: (license_code) => request(`/api/natbirzha/premium/licenses/${encodeURIComponent(license_code)}/purchase`, { method: 'POST' }),
  getPremiumUpgradeCatalog: () => cachedGet('/api/natbirzha/premium/upgrades/catalog', 5 * 60 * 1000),
  getPremiumUpgrades: () => request('/api/natbirzha/premium/upgrades'),
  purchasePremiumUpgrade: (upgrade_code) => request(`/api/natbirzha/premium/upgrades/${encodeURIComponent(upgrade_code)}/purchase`, { method: 'POST' }),
  getIndustryUpgradeCatalog: () => cachedGet('/api/natbirzha/premium/industry-upgrades/catalog', 5 * 60 * 1000),
  getIndustryUpgrade: () => request('/api/natbirzha/premium/industry-upgrades'),
  purchaseIndustryUpgrade: () => request('/api/natbirzha/premium/industry-upgrades/purchase', { method: 'POST' }),

  // Public company rankings (all values are calculated on the server)
  getLeaderboard: (category = 'assets', page = 1) => request(`/api/natbirzha/leaderboard?category=${encodeURIComponent(category)}&page=${parseInt(page, 10)}`),

  // Creator / State Administration
  getCreatorOverview: () => request('/api/natbirzha/creator/overview'),
  grantCreatorSelf: (cash = 0, pvc = 0) => request('/api/natbirzha/creator/me/grant', { method: 'POST', body: JSON.stringify({ cash: Number(cash), pvc: parseInt(pvc, 10) || 0 }) }),
  getCreatorEconomyMetrics: (days = 7) => request(`/api/natbirzha/creator/economy/metrics?days=${parseInt(days, 10)}`),
  getCreatorMarket: () => request('/api/natbirzha/creator/market'),
  sendCreatorWarning: (company_id, reason) => request('/api/natbirzha/creator/market/warnings', { method: 'POST', body: JSON.stringify({ company_id: parseInt(company_id, 10), reason }) }),
  setCreatorRestriction: (payload) => request('/api/natbirzha/creator/market/restrictions', { method: 'POST', body: JSON.stringify(payload) }),
  removeCreatorRestriction: (restriction_id) => request(`/api/natbirzha/creator/market/restrictions/${restriction_id}`, { method: 'DELETE' }),
  issueCreatorBonds: (payload) => request('/api/natbirzha/creator/bonds/issue', { method: 'POST', body: JSON.stringify(payload) }),
  getCreatorBonds: () => request('/api/natbirzha/creator/bonds'),
  issueCreatorShares: (payload) => request('/api/natbirzha/creator/shares/issue', { method: 'POST', body: JSON.stringify(payload) }),
  getCreatorShares: () => request('/api/natbirzha/creator/shares'),
  launchCreatorTournament: (payload = {}) => request('/api/natbirzha/creator/tournaments/launch', { method: 'POST', body: JSON.stringify(payload) }),
  getCreatorAuditLog: () => request('/api/natbirzha/creator/audit-log'),
  getCreatorPremiumLedger: (company_id = null) => request(`/api/natbirzha/creator/premium/ledger${company_id ? `?company_id=${parseInt(company_id, 10)}` : ''}`),
  getCreatorPlayers: ({ search = '', sort = 'last_activity_at', page = 1 } = {}) => request(`/api/natbirzha/creator/players?search=${encodeURIComponent(search)}&sort=${encodeURIComponent(sort)}&page=${parseInt(page, 10)}`),
  getCreatorStateCredits: (status = 'PENDING') => request(`/api/natbirzha/creator/state-credits?status=${encodeURIComponent(status)}`),
  decideCreatorStateCredit: (loan_id, approved) => request(`/api/natbirzha/creator/state-credits/${parseInt(loan_id, 10)}/decision`, { method: 'POST', body: JSON.stringify({ approved: Boolean(approved) }) }),
  declareCreatorBankruptcy: (company_id) => request(`/api/natbirzha/creator/players/${parseInt(company_id, 10)}/bankruptcy`, { method: 'POST', body: JSON.stringify({}) }),
  getCreatorWorldResetPreview: () => request('/api/natbirzha/creator/world-reset/preview'),
  resetCreatorWorld: (confirmation) => request('/api/natbirzha/creator/world-reset', { method: 'POST', body: JSON.stringify({ confirmation }) }),
  resetSelf: () => request('/api/natbirzha/creator/me/reset', { method: 'POST' }),
};


export { clearStaleInitData, getTelegramUserId, getTelegramInitData, getAuthHeader };
