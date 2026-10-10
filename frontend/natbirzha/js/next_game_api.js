/** Separate API surface for the isolated NATBIRZHA 2.0 game. */
export function createNextGameAPI(request) {
  return {
    getNextGameMap: (section = 'full') => request(`/api/natbirzha/next-game/map?section=${encodeURIComponent(section)}`),
    getNextGameCompetition: () => request('/api/natbirzha/next-game/competition'),
    getNextGameRecovery: () => request('/api/natbirzha/next-game/recovery'),
    recoverNextGameCompany: (restart) => request('/api/natbirzha/next-game/recovery', { method: 'POST', body: JSON.stringify({ restart: Boolean(restart) }) }),
    forceNextGameBankruptcy: (company_id, note, confirm) => request('/api/natbirzha/next-game/admin/bankruptcy', { method: 'POST', body: JSON.stringify({ company_id: Number(company_id), note, confirm: Boolean(confirm) }) }),
    getNextGameLiquidation: () => request('/api/natbirzha/next-game/liquidation'),
    buyNextGameLiquidationLot: (id) => request(`/api/natbirzha/next-game/liquidation/${id}/buy`, { method: 'POST', body: JSON.stringify({}) }),
    getNextGameOperations: () => request('/api/natbirzha/next-game/operations'),
    nextGameOperationsAction: (payload) => request('/api/natbirzha/next-game/operations/actions', { method: 'POST', body: JSON.stringify(payload) }),
    getNextGameCivic: () => request('/api/natbirzha/next-game/civic'),
    payNextGameTax: (id) => request(`/api/natbirzha/next-game/civic/taxes/${id}/pay`, { method: 'POST', body: JSON.stringify({}) }),
    fulfillNextGameCityOrder: (id, quantity) => request(`/api/natbirzha/next-game/civic/orders/${id}/fulfill`, { method: 'POST', body: JSON.stringify({ quantity: Number(quantity) }) }),
    createNextGameEconomicEvent: (sector_id, duration_hours) => request('/api/natbirzha/next-game/civic/events', { method: 'POST', body: JSON.stringify({ sector_id, duration_hours: Number(duration_hours) }) }),
    getNextGameMarketCatalog: () => request('/api/natbirzha/next-game/market/catalog'),
    getNextGameMarketItem: (itemId) => request(`/api/natbirzha/next-game/market/items/${encodeURIComponent(itemId)}`),
    getNextGameMarketLiquidity: () => request('/api/natbirzha/next-game/market/liquidity'),
    updateNextGameSettings: (settings) => request('/api/natbirzha/next-game/settings', { method: 'PUT', body: JSON.stringify(settings) }),
    getNextGameSupport: () => request('/api/natbirzha/next-game/support'),
    createNextGameAidRequest: (item_id, goal, description) => request('/api/natbirzha/next-game/support/requests', { method: 'POST', body: JSON.stringify({ item_id, goal: Number(goal), description }) }),
    donateNextGameAid: (id, quantity) => request(`/api/natbirzha/next-game/support/requests/${id}/donate`, { method: 'POST', body: JSON.stringify({ quantity: Number(quantity) }) }),
    closeNextGameAid: (id) => request(`/api/natbirzha/next-game/support/requests/${id}`, { method: 'DELETE' }),
    getNextGameAdmin: () => request('/api/natbirzha/next-game/admin'),
    operateNextGameAdmin: (operation) => request('/api/natbirzha/next-game/admin/operations', { method: 'POST', body: JSON.stringify(operation) }),
    getNextGamePartnerships: () => request('/api/natbirzha/next-game/partnerships'),
    createNextGameSupplyDeal: (payload) => request('/api/natbirzha/next-game/partnerships/supply', { method: 'POST', body: JSON.stringify(payload) }),
    createNextGameJointProject: (payload) => request('/api/natbirzha/next-game/partnerships/projects', { method: 'POST', body: JSON.stringify(payload) }),
    respondNextGamePartnership: (kind, id, accept) => request(`/api/natbirzha/next-game/partnerships/${encodeURIComponent(kind)}/${id}/respond`, { method: 'POST', body: JSON.stringify({ accept: Boolean(accept) }) }),
    cancelNextGamePartnership: (kind, id) => request(`/api/natbirzha/next-game/partnerships/${encodeURIComponent(kind)}/${id}/cancel`, { method: 'POST', body: JSON.stringify({}) }),
    getNextGameBonds: () => request('/api/natbirzha/next-game/bonds'),
    buyNextGameBonds: (series_id, units) => request('/api/natbirzha/next-game/bonds/buy', { method: 'POST', body: JSON.stringify({ series_id: Number(series_id), units: Number(units) }) }),
    listNextGameBonds: (holding_id, units, unit_price) => request('/api/natbirzha/next-game/bonds/listings', { method: 'POST', body: JSON.stringify({ holding_id: Number(holding_id), units: Number(units), unit_price: Number(unit_price) }) }),
    buyNextGameBondListing: (id, units) => request(`/api/natbirzha/next-game/bonds/listings/${id}/buy`, { method: 'POST', body: JSON.stringify({ units: Number(units) }) }),
    cancelNextGameBondListing: (id) => request(`/api/natbirzha/next-game/bonds/listings/${id}`, { method: 'DELETE' }),
    getNextGameProgression: () => request('/api/natbirzha/next-game/progression'),
    upgradeNextGamePVC: () => request('/api/natbirzha/next-game/progression/pvc-upgrade', { method: 'POST', body: JSON.stringify({}) }),
    rebirthNextGameCompany: (confirm) => request('/api/natbirzha/next-game/progression/rebirth', { method: 'POST', body: JSON.stringify({ confirm: Boolean(confirm) }) }),
    fuseNextGameFactories: (source_ids) => request('/api/natbirzha/next-game/progression/fuse', { method: 'POST', body: JSON.stringify({ source_ids }) }),
    dissolveNextGameFactories: (merger_id) => request('/api/natbirzha/next-game/progression/dissolve', { method: 'POST', body: JSON.stringify({ merger_id: Number(merger_id) }) }),
    createNextGameCompany: (name) => request('/api/natbirzha/next-game/company', {
      method: 'POST', body: JSON.stringify({ name: String(name || '').trim() }),
    }),
    selectNextGameSector: (sector_id) => request('/api/natbirzha/next-game/sector', {
      method: 'PUT', body: JSON.stringify({ sector_id }),
    }),
    selectNextGameBranch: (branch_id) => request('/api/natbirzha/next-game/branch', {
      method: 'PUT', body: JSON.stringify({ branch_id }),
    }),
    advanceNextGameBranch: (branch_id) => request('/api/natbirzha/next-game/branch/advance', {
      method: 'PUT', body: JSON.stringify({ branch_id }),
    }),
    buildNextGameFacility: (branch_id = null) => request('/api/natbirzha/next-game/facility/build', {
      method: 'POST', body: JSON.stringify({ branch_id }),
    }),
    upgradeNextGameFacility: (branch_id) => request('/api/natbirzha/next-game/facility/upgrade', {
      method: 'POST', body: JSON.stringify({ branch_id: String(branch_id) }),
    }),
    tradeNextGameMarket: (item_id, side, quantity) => request('/api/natbirzha/next-game/market/trade', {
      method: 'POST', body: JSON.stringify({ item_id, side, quantity: Number(quantity) }),
    }),
    getNextGameMarketOrders: (item_id = null) => {
      const query = item_id ? `?item_id=${encodeURIComponent(item_id)}` : '';
      return request(`/api/natbirzha/next-game/market/orders${query}`);
    },
    getMyNextGameMarketOrders: (item_id = null) => {
      const query = item_id ? `?item_id=${encodeURIComponent(item_id)}` : '';
      return request(`/api/natbirzha/next-game/market/orders/mine${query}`);
    },
    createNextGameLimitOrder: (item_id, side, quantity, limit_price) => request('/api/natbirzha/next-game/market/orders', {
      method: 'POST', body: JSON.stringify({ item_id, side, quantity: Number(quantity), limit_price: Number(limit_price) }),
    }),
    cancelNextGameOrder: (order_id) => request(`/api/natbirzha/next-game/market/orders/${parseInt(order_id, 10)}`, {
      method: 'DELETE',
    }),
    requestNextGameBankLoan: (amount) => request('/api/natbirzha/next-game/bank/loan', {
      method: 'POST', body: JSON.stringify({ amount: Number(amount) }),
    }),
    repayNextGameBankLoan: () => request('/api/natbirzha/next-game/bank/loan/repay', {
      method: 'POST', body: JSON.stringify({}),
    }),
    openNextGameBankDeposit: (amount, term_days) => request('/api/natbirzha/next-game/bank/deposits', {
      method: 'POST', body: JSON.stringify({ amount: Number(amount), term_days: Number(term_days) }),
    }),
    withdrawNextGameBankDeposit: (deposit_id) => request(
      `/api/natbirzha/next-game/bank/deposits/${parseInt(deposit_id, 10)}/withdraw`,
      { method: 'POST', body: JSON.stringify({}) },
    ),
    openNextGameCorporateAccount: (bank_company_id) => request(
      '/api/natbirzha/next-game/banking/accounts', {
        method: 'POST', body: JSON.stringify({ bank_company_id: parseInt(bank_company_id, 10) }),
      },
    ),
    makeNextGameCompanyPayment: (bank_company_id, payee_company_id, amount) => request(
      '/api/natbirzha/next-game/banking/payments', {
        method: 'POST', body: JSON.stringify({
          bank_company_id: parseInt(bank_company_id, 10),
          payee_company_id: parseInt(payee_company_id, 10),
          amount: Number(amount),
        }),
      },
    ),
    requestNextGameBusinessLoan: (bank_company_id, amount, term_days) => request(
      '/api/natbirzha/next-game/banking/loans', {
        method: 'POST', body: JSON.stringify({
          bank_company_id: parseInt(bank_company_id, 10),
          amount: Number(amount), term_days: Number(term_days),
        }),
      },
    ),
    repayNextGameBusinessLoan: (loan_id) => request(
      `/api/natbirzha/next-game/banking/loans/${parseInt(loan_id, 10)}/repay`, {
        method: 'POST', body: JSON.stringify({}),
      },
    ),
    createNextGameDirectLoanOffer: (borrower_company_id, principal, daily_rate_bps, term_days) => request(
      '/api/natbirzha/next-game/finance/offers', {
        method: 'POST', body: JSON.stringify({
          borrower_company_id: parseInt(borrower_company_id, 10),
          principal: Number(principal), daily_rate_bps: Number(daily_rate_bps),
          term_days: Number(term_days),
        }),
      },
    ),
    acceptNextGameDirectLoanOffer: (contract_id) => request(
      `/api/natbirzha/next-game/finance/offers/${parseInt(contract_id, 10)}/accept`, {
        method: 'POST', body: JSON.stringify({}),
      },
    ),
    cancelNextGameDirectLoanOffer: (contract_id) => request(
      `/api/natbirzha/next-game/finance/offers/${parseInt(contract_id, 10)}/cancel`, {
        method: 'POST', body: JSON.stringify({}),
      },
    ),
    repayNextGameDirectLoan: (contract_id) => request(
      `/api/natbirzha/next-game/finance/loans/${parseInt(contract_id, 10)}/repay`, {
        method: 'POST', body: JSON.stringify({}),
      },
    ),
    openNextGameIPO: () => request('/api/natbirzha/next-game/capital/ipo', {
      method: 'POST', body: JSON.stringify({}),
    }),
    createNextGameShareOrder: (issue_id, side, shares, limit_price) => request(
      '/api/natbirzha/next-game/capital/orders', {
        method: 'POST', body: JSON.stringify({
          issue_id: parseInt(issue_id, 10), side: String(side),
          shares: parseInt(shares, 10), limit_price: Number(limit_price),
        }),
      },
    ),
    cancelNextGameShareOrder: (order_id) => request(
      `/api/natbirzha/next-game/capital/orders/${parseInt(order_id, 10)}`,
      { method: 'DELETE' },
    ),
    distributeNextGameDividend: (per_share) => request(
      '/api/natbirzha/next-game/capital/dividends', {
        method: 'POST', body: JSON.stringify({ per_share: Number(per_share) }),
      },
    ),
  };
}
