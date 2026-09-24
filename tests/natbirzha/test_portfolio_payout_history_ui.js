const fs = require('fs');
const source = fs.readFileSync('frontend/natbirzha/js/screens/market_finance.js', 'utf8');

if (!source.includes('История выплат')) throw new Error('Portfolio history label should cover all payout types.');
if (source.includes('История дивидендов')) throw new Error('Obsolete dividend-only history label remains.');
if (!source.includes('portfolio.payout_history')) throw new Error('Portfolio should render the unified payout history API field.');
if (!source.includes('row.title') || !source.includes('row.paid_at') || !source.includes('row.payout_cash')) {
  throw new Error('Payout history should show source, paid time and amount.');
}

console.log('Portfolio payout history UI contract passed.');
