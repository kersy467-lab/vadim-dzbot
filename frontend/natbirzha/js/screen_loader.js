const screens = {
  onboarding: ['./screens/onboarding.js?v=20260928_mobile_perf_v1', 'renderOnboarding'],
  overview: ['./screens/overview.js?v=20260928_mobile_perf_v1', 'renderOverview'],
  production: ['./screens/tycoon.js?v=20260929_future_business_prices_v1', 'renderTycoon'],
  upgrades: ['./screens/upgrades.js?v=20260928_upgrade_legacy_cleanup_v1', 'renderUpgrades'],
  market: ['./screens/market.js?v=20260929_market_state_advance_v1', 'renderMarket'],
  stocks: ['./screens/stocks.js?v=20260928_mobile_perf_v1', 'renderStocks'],
  military: ['./screens/military.js?v=20260928_mobile_perf_v1', 'renderMilitary'],
  creator: ['./screens/creator.js?v=20260928_mobile_perf_v1', 'renderCreator'],
  leaderboard: ['./screens/leaderboard.js?v=20260928_mobile_perf_v1', 'renderLeaderboard'],
  help: ['./screens/help.js?v=20260928_mobile_perf_v1', 'renderHelp'],
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
