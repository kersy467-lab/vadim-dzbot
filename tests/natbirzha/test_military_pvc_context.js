const fs = require('fs');
const path = require('path');
const assert = require('assert');

const sourcePath = path.join(__dirname, '../../frontend/natbirzha/js/screens/military.js');
const source = fs.readFileSync(sourcePath, 'utf8')
  .replace(/^import .*;\r?$/gm, '')
  .replace('export async function renderMilitary', 'async function renderMilitary');

let premiumCatalogRequests = 0;
const NatAPI = {
  getMilitaryStatus: async () => ({}),
  getPremiumWallet: async () => ({ balance: 250, currency: 'PVC' }),
  getPremiumLedger: async () => ({ entries: [] }),
  getPremiumLicenseCatalog: async () => {
    premiumCatalogRequests += 1;
    return { licenses: [{ code: 'test-license', title: 'Старая лицензия', description: 'Тест', price_pvc: 123, duration_hours: 48 }] };
  },
  getPremiumLicenses: async () => ({ licenses: [] }),
  getPremiumUpgradeCatalog: async () => ({ upgrades: [] }),
  getPremiumUpgrades: async () => ({ upgrades: [] }),
  getIndustryUpgradeCatalog: async () => ({ upgrades: [] }),
  getIndustryUpgrade: async () => ({ upgrade: null }),
};
const store = { company: null, inventory: {}, setCompany() {} };
const renderMilitary = new Function(
  'NatAPI', 'store', 'getItemInfo', 'renderTournamentSection', 'bindHospitalHandlers', 'renderHospitalSection',
  'armyRequirementText', 'esc', 'number', 'timeLeft', 'unavailableReason',
  `${source}\nreturn renderMilitary;`,
)(
  NatAPI,
  store,
  (id) => ({ name: id }),
  () => '',
  () => {},
  () => '',
  () => '',
  (value) => String(value ?? ''),
  (value) => String(value ?? 0),
  () => '',
  () => '',
);

function makeContainer() {
  let html = '';
  const clickHandlers = new Map();
  return {
    get innerHTML() { return html; },
    set innerHTML(value) { html = value; },
    querySelector() { return null; },
    querySelectorAll(selector) {
      if (selector !== '.war-section-btn') return [];
      const sections = [...html.matchAll(/data-section="([^"]+)"/g)].map((match) => match[1]);
      return sections.map((section) => ({
        dataset: { section },
        addEventListener(event, handler) {
          if (event === 'click') clickHandlers.set(section, handler);
        },
      }));
    },
    async clickSection(section) {
      const handler = clickHandlers.get(section);
      assert(handler, `section ${section} should be available`);
      await handler();
    },
  };
}

async function waitForInitialRender() {
  await new Promise((resolve) => setTimeout(resolve, 0));
}

(async () => {
  const legacyContainer = makeContainer();
  await renderMilitary(legacyContainer, () => {});
  await waitForInitialRender();
  assert(legacyContainer.innerHTML.includes('data-section="premium"'),
    'the default legacy 1.5 War screen must keep its PVC tab');
  await legacyContainer.clickSection('premium');
  assert(legacyContainer.innerHTML.includes('Старая лицензия') && legacyContainer.innerHTML.includes('123 PVC'),
    'the legacy War PVC catalog must keep rendering its old catalog price');

  const requestsBeforeNextGame = premiumCatalogRequests;
  const nextGameContainer = makeContainer();
  await renderMilitary(nextGameContainer, () => {}, { includePvcShop: false });
  await waitForInitialRender();
  assert(nextGameContainer.innerHTML.includes('data-section="army"'),
    'the NATBIRZHA 2.0 War view must keep its military sections');
  assert(!nextGameContainer.innerHTML.includes('data-section="premium"')
    && !nextGameContainer.innerHTML.includes('Старая лицензия'),
  'the NATBIRZHA 2.0 War view must omit the duplicate PVC shop');
  assert.strictEqual(premiumCatalogRequests, requestsBeforeNextGame,
    'the NATBIRZHA 2.0 War view must not load the legacy PVC catalog');
  console.log('NATBIRZHA War PVC context checks: PASS');
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
