const assert = require('assert');
const fs = require('fs');
const path = require('path');

const read = (relativePath) => fs.readFileSync(
  path.join(__dirname, '../../', relativePath),
  'utf8',
);

const market = read('frontend/natbirzha/js/screens/market.js');
const marketLoader = read('frontend/natbirzha/js/screens/market_section_loader.js');
const commodities = read('frontend/natbirzha/js/screens/market_commodities.js');
const app = read('frontend/natbirzha/js/app.js');
const api = read('frontend/natbirzha/js/api.js');
const screenLoader = read('frontend/natbirzha/js/screen_loader.js');
const indexHtml = read('frontend/natbirzha/index.html');
const upgrades = read('frontend/natbirzha/js/screens/upgrades.js');

function javascriptFiles(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const fullPath = path.join(directory, entry.name);
    return entry.isDirectory() ? javascriptFiles(fullPath) : entry.name.endsWith('.js') ? [fullPath] : [];
  });
}

const commodityOpen = marketLoader.match(/if \(section === 'commodities'\) \{([\s\S]*?)\n    \}/)?.[1] || '';
assert(
  /renderCommodities\(\);[\s\S]*?await loadCommodities\(\)/.test(commodityOpen),
  'the commodity catalog should render before waiting for its data requests',
);

const eagerMarketData = market.match(/async function ensureMarketData\(\) \{([\s\S]*?)\n  \}/)?.[1] || '';
assert(
  !eagerMarketData.includes('NatAPI.getEmpireSummary()'),
  'opening the commodity catalog should not wait for the company empire summary',
);
assert(
  !eagerMarketData.includes('NatAPI.getNpcRates()')
    && market.includes('NatAPI.getNpcRates(itemId)'),
  'the catalog should avoid all live quotes and request a targeted quote for the selected material',
);
assert(
  commodities.includes('loadCompanyInputs'),
  'the company empire summary should load only when the needed-input category is opened',
);
assert(
  !commodities.includes('item.buy') && !commodities.includes('item.sell'),
  'catalog rows should list materials without rendering live quotes for every material',
);
assert(
  api.includes('getNpcRates: (itemId = null)') && api.includes('encodeURIComponent(itemId)'),
  'the API wrapper should support an encoded item_id for targeted NPC quotes while preserving the all-rates call',
);
assert(
  api.includes('NatAPI') && app.includes("./api.js?v=20261010_active_production_v1")
    && screenLoader.includes("./screens/market.js?v=20261009_item_art_v2")
    && screenLoader.includes("./screens/upgrades.js?v=20261009_luxury_ui_v2")
    && screenLoader.includes("./screens/tycoon.js?v=20261010_auto_upgrade_v1")
    && app.includes("./screen_loader.js?v=20261010_active_production_v1")
    && app.includes("./icons.mjs?v=20261010_semantic_icons_v4")
    && indexHtml.includes('/js/app.js?v=20261010_active_production_v1'),
  'changed frontend entry, loader, and upgrade assets should use fresh cache-bust versions',
);
const apiImportVersions = new Set(javascriptFiles(path.join(__dirname, '../../frontend/natbirzha/js'))
  .flatMap((file) => [...fs.readFileSync(file, 'utf8').matchAll(/(?:^|\/)api\.js\?v=([^&'"\s]+)/g)].map((match) => match[1])));
assert(
  apiImportVersions.size === 1 && apiImportVersions.has('20261010_active_production_v1'),
  'all frontend imports of api.js should share one fresh module URL for navigation cancellation state',
);

const renderStart = app.indexOf('const renderScreen = await loadScreen(renderTab)');
const mountIndex = app.indexOf('container.replaceChildren(renderContainer);', renderStart);
const rendererIndex = app.indexOf('await renderScreen(renderContainer, showToast);', renderStart);
const navigationCheckIndex = app.lastIndexOf('if (renderNavigationId !== navigationId)', mountIndex);
const completedRenderCheckIndex = app.indexOf('if (renderNavigationId !== navigationId)', rendererIndex);
assert(
  mountIndex !== -1 && rendererIndex !== -1 && mountIndex < rendererIndex
    && navigationCheckIndex > renderStart && navigationCheckIndex < mountIndex
    && completedRenderCheckIndex > rendererIndex,
  'the screen loader should mount only the current render before awaiting it and check navigation again after completion',
);
assert(
  app.includes('navigationAbortController?.abort()')
    && app.includes('if (activeRenderPromise) return activeRenderPromise;'),
  'navigation should abort stale API requests while keeping screen rendering serialized',
);

const renderUpgradesStart = upgrades.indexOf('export async function renderUpgrades');
const loadingScreenIndex = upgrades.indexOf('renderUpgradeLoading(container)', renderUpgradesStart);
const upgradeSummaryIndex = upgrades.indexOf('await NatAPI.getBusinessUpgradeSummary()', renderUpgradesStart);
assert(
  loadingScreenIndex !== -1 && upgradeSummaryIndex !== -1 && loadingScreenIndex < upgradeSummaryIndex,
  'the upgrades screen should show a loading state before requesting its upgrade summary',
);
assert(
  !upgrades.includes('renderFactoryUpgrades')
    && !upgrades.includes('NatAPI.getProductionStatus()')
    && !upgrades.includes('Прокачка производств'),
  'the obsolete factory-upgrade UI must never flash while the V2 upgrades screen is loading',
);
assert(
  upgrades.includes('registerScreenCleanup')
    && upgrades.includes('upgradesRenderGeneration += 1;')
    && upgrades.includes('if (!isCurrent()) return;'),
  'a stale upgrade summary must not replace content after navigation changes',
);

console.log('Frontend market and upgrades loading contracts verified.');
