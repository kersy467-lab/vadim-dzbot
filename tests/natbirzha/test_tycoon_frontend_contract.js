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
console.log('Tycoon repeatable-business and sale-confirmation UI contracts verified.');
