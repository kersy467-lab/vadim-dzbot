const fs = require('fs');
const source = fs.readFileSync('frontend/natbirzha/js/screens/market_finance.js', 'utf8');

if (!source.includes('История выплат')) throw new Error('Portfolio history label should cover all payout types.');
if (source.includes('История дивидендов')) throw new Error('Obsolete dividend-only history label remains.');
if (!source.includes('portfolio.payout_history')) throw new Error('Portfolio should render the unified payout history API field.');
if (!source.includes('row.title') || !source.includes('row.paid_at') || !source.includes('row.payout_cash')) {
  throw new Error('Payout history should show source, paid time and amount.');
}
if (!source.includes('row.coupons_earned') || !source.includes('Купоны получены')) {
  throw new Error('Bond holdings should show coupon income received for each bond.');
}
if (!source.includes('Получено купонами:')) {
  throw new Error('The state-bond screen should show income next to the owned bonds.');
}

console.log('Portfolio payout history UI contract passed.');
