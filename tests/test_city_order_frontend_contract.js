const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '..');
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');

const market = read('frontend/natbirzha/js/screens/market.js');
const screen = read('frontend/natbirzha/js/screens/market_city_orders.js');
const api = read('frontend/natbirzha/js/api.js');
const app = read('frontend/natbirzha/js/app.js');
const html = read('frontend/natbirzha/index.html');

const cityMenu = market.indexOf('data-section="city_orders"');
const dealsMenu = market.indexOf('data-section="deals"');
if (cityMenu < 0 || dealsMenu < 0 || cityMenu >= dealsMenu) {
  throw new Error('City Orders must appear immediately before Deals in the market menu.');
}
if (!market.includes("section === 'city_orders'")) throw new Error('City Orders menu action is not wired.');
if (!api.includes('getCityOrders:') || !api.includes('deliverCityOrder:')) {
  throw new Error('City Orders API methods are missing.');
}
if (!api.includes("'Idempotency-Key': idempotencyKey") || !screen.includes('localStorage.getItem(key)')) {
  throw new Error('Delivery retries must carry and retain an operation key.');
}
if (!screen.includes("row.available") || !screen.includes('deliveryKey(store.company')
  || !screen.includes('30_000')) {
  throw new Error('The City Orders screen must use available inventory and a stable retry key.');
}
const sharedApiVersion = app.match(/api\.js\?v=([^'\"]+)/)?.[1];
const entryVersion = html.match(/app\.js\?v=([^'\"]+)/)?.[1];
if (!sharedApiVersion
  || !app.includes(`market.js?v=20260926_joint_factory_v1`)
  || !market.includes(`api.js?v=${sharedApiVersion}`)
  || !screen.includes(`api.js?v=${sharedApiVersion}`)
  || !entryVersion
  || !market.includes("state.js?v=20260926_local_update_v1")
  || !screen.includes("state.js?v=20260926_local_update_v1")
  || entryVersion !== '20260927_hospital_v2') {
  throw new Error('City Orders frontend cache-busting or shared API/store module identity is missing.');
}
for (const file of [
  'frontend/natbirzha/js/screens/market_city_orders.js',
  'frontend/natbirzha/js/api.js',
  'frontend/natbirzha/js/screens/market.js',
]) {
  const lines = read(file).split(/\r?\n/).length;
  if (lines > 400) throw new Error(`${file} exceeds the source file size limit (${lines} lines).`);
}
console.log('City Orders frontend contract passed.');
