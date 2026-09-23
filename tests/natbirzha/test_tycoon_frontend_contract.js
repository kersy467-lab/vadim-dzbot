const fs = require('fs');
const path = require('path');
const assert = require('assert');

const tycoon = fs.readFileSync(
  path.join(__dirname, '../../frontend/natbirzha/js/screens/tycoon.js'),
  'utf-8',
);
assert(tycoon.includes('instances.push(item)'), 'repeatable business instances must stay grouped by type');
assert(tycoon.includes('uniqueOwned'), 'catalog cards must still block explicitly unique owned types');
assert(tycoon.includes('Открыть ещё'), 'repeatable types must keep their open action after the first copy');
assert(tycoon.includes('Потеря составит'), 'sale confirmation must show the cash loss before selling');
assert(tycoon.includes('data-refund=') && tycoon.includes('business.sale_refund'), 'sale button must show the server refund');
assert(tycoon.includes('tycoon-view-toggle') && tycoon.includes('compactBusinessRow'), 'business tab must toggle between detailed cards and compact rows');
assert(tycoon.includes('data-action = \'upgrade\'') || tycoon.includes("dataset.action = 'upgrade'"), 'compact rows must keep a working upgrade action');
const upgrades = fs.readFileSync(
  path.join(__dirname, '../../frontend/natbirzha/js/screens/upgrades.js'),
  'utf-8',
);
assert(upgrades.includes('NatAPI.getEmpireSummary()') && upgrades.includes('NatAPI.upgradeBusiness(business.id)'), 'upgrade tab must read and upgrade Tycoon V2 businesses');
const overview = fs.readFileSync(
  path.join(__dirname, '../../frontend/natbirzha/js/screens/overview.js'),
  'utf-8',
);
assert(overview.includes('expand-capacity-btn') && overview.includes('slot_expansion'), 'overview must expose timed business-capacity expansion');
assert(!overview.includes('expand-territory-btn'), 'overview must replace territory expansion with business capacity');
const market = fs.readFileSync(
  path.join(__dirname, '../../frontend/natbirzha/js/screens/market.js'),
  'utf-8',
);
const finance = fs.readFileSync(
  path.join(__dirname, '../../frontend/natbirzha/js/screens/market_finance.js'),
  'utf-8',
);
const chart = fs.readFileSync(
  path.join(__dirname, '../../frontend/natbirzha/js/market_chart.js'),
  'utf-8',
);
assert(market.includes('Все разделы биржи'), 'raw-material market must provide a back action');
assert(finance.includes('suggested)') && finance.includes('row.unrealized_pnl_rub'), 'reference trades must prefill an affordable maximum and show holding P/L');
assert(finance.includes('Всего') || finance.includes('всего '), 'bond holdings must show total quantity explicitly');
assert(chart.includes('normalized.length === 1'), 'a bond with one recorded quote must still render a chart');
console.log('Tycoon repeatable-business and sale-confirmation UI contracts verified.');
