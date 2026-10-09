const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

const tycoonPath = path.join(__dirname, '../../frontend/natbirzha/js/screens/tycoon.js');
const tycoon = fs.readFileSync(tycoonPath, 'utf8');
assert(tycoon.includes('renderInventoryRunwayStat(summary.inventory_runway)'),
  'Tycoon must render the runway from the already loaded empire summary');
assert(!tycoon.includes('NatAPI.getMyCompany('),
  'Tycoon must not add a company status request to obtain the runway');
assert(tycoon.includes('statGrid.append(toggle)'),
  'the view toggle remains a separate stat after the runway card');
const gridStart = tycoon.indexOf('<div class="tycoon-stat-grid">');
const gridEnd = tycoon.indexOf('</div></div>', gridStart);
assert(gridStart >= 0 && gridEnd > gridStart,
  'the Tycoon stat grid should keep its original six cards');
assert.strictEqual((tycoon.slice(gridStart, gridEnd).match(/class="tycoon-stat"/g) || []).length, 6,
  'the runway must extend the existing six summary cards');
assert(tycoon.indexOf('statGrid.append(toggle)') < tycoon.indexOf('statGrid.insertAdjacentHTML("beforeend", renderInventoryRunwayStat(summary.inventory_runway))'),
  'the runway must be appended after the existing six cards and seventh view toggle');

const helperStart = tycoon.indexOf('export function renderInventoryRunwayStat(');
const helperEnd = tycoon.indexOf('\nfunction resourceQuantity(', helperStart);
assert(helperStart >= 0 && helperEnd > helperStart,
  'Tycoon must expose its runway stat renderer for a focused behavior test');
const helperSource = tycoon.slice(helperStart + 'export '.length, helperEnd).trim();
const sandbox = {
  esc: (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char])),
};
vm.runInNewContext(`${helperSource}; globalThis.renderInventoryRunwayStat = renderInventoryRunwayStat;`, sandbox);
const render = sandbox.renderInventoryRunwayStat;

const noConsumers = render({ status: 'NO_CONSUMERS', hours: null, active_consuming_business_count: 0, limiting_resources: [] });
assert(noConsumers.includes('class="tycoon-stat"') && noConsumers.includes('0 ресурсных предприятий V2'),
  'no consumers must be shown as an explicit eighth stat');
assert(noConsumers.includes('цикловые рецепты фабрик не учитываются'),
  'the stat must clarify that legacy factory cycles are not included');

const zeroStock = render({ status: 'OUT_OF_STOCK', hours: 0, active_consuming_business_count: 1, limiting_resources: [
  { item_id: 'energy', name: 'Электроэнергия' },
] });
assert(zeroStock.includes('0 ч') && zeroStock.includes('1 ресурсное предприятие V2') && zeroStock.includes('Электроэнергия'),
  'zero stock must show immediate exhaustion, the consumer count, and the limiting resource');

const runway = render({ status: 'RUNWAY', hours: 2, active_consuming_business_count: 2, limiting_resources: [
  { item_id: 'energy', name: 'Электроэнергия' },
] });
assert(runway.includes('2 ч') && runway.includes('2 ресурсных предприятия V2') && runway.includes('Электроэнергия'),
  'normal runway must show hours, active V2 resource-business count, and limiting resources');
assert(runway.includes('работают + ждут поставку'),
  'the scope label must state that the runway includes businesses waiting for supply');
console.log('Tycoon warehouse runway stat contract verified.');
