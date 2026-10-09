const screens = {
  onboarding: ['./screens/onboarding.js?v=20261009_luxury_ui_v2', 'renderOnboarding'],
  overview: ['./screens/overview.js?v=20261009_luxury_ui_v2', 'renderOverview'],
  production: ['./screens/tycoon.js?v=20261009_luxury_ui_v2', 'renderTycoon'],
  upgrades: ['./screens/upgrades.js?v=20261009_luxury_ui_v2', 'renderUpgrades'],
  market: ['./screens/market.js?v=20261009_luxury_ui_v2', 'renderMarket'],
  stocks: ['./screens/stocks.js?v=20261009_luxury_ui_v2', 'renderStocks'],
  military: ['./screens/military.js?v=20261009_luxury_ui_v2', 'renderMilitary'],
  creator: ['./screens/creator.js?v=20261009_luxury_ui_v2', 'renderCreator'],
  leaderboard: ['./screens/leaderboard.js?v=20261008_company_renewal_v1', 'renderLeaderboard'],
  help: ['./screens/help.js?v=20261009_luxury_ui_v2', 'renderHelp'],
};

export async function loadScreen(tab) {
  const [path, exportName] = screens[tab] || screens.overview;
  const module = await loadScreenModule(path);
  return module[exportName];
}

const screenModulePromises = new Map();

function loadScreenModule(path) {
  if (!screenModulePromises.has(path)) {
    let promise;
    promise = import(path).catch((error) => {
      if (screenModulePromises.get(path) === promise) {
        screenModulePromises.delete(path);
      }
      throw error;
    });
    screenModulePromises.set(path, promise);
  }
  return screenModulePromises.get(path);
}

export function preloadScreen(tab) {
  const [path] = screens[tab] || screens.overview;
  return loadScreenModule(path).then(() => undefined, () => undefined);
}
