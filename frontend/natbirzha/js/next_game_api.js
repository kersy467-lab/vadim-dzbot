/** Separate API surface for the isolated NATBIRZHA 2.0 game. */
export function createNextGameAPI(request) {
  return {
    getNextGameMap: () => request('/api/natbirzha/next-game/map'),
    getNextGameCompetition: () => request('/api/natbirzha/next-game/competition'),
    getNextGameCompetition: () => request('/api/natbirzha/next-game/competition'),
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
