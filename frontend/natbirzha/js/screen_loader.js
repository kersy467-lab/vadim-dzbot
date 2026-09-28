const screens = {
  onboarding: ['./screens/onboarding.js?v=20260928_mobile_perf_v1', 'renderOnboarding'],
  overview: ['./screens/overview.js?v=20260928_mobile_perf_v1', 'renderOverview'],
  production: ['./screens/tycoon.js?v=20260928_mobile_perf_v1', 'renderTycoon'],
  upgrades: ['./screens/upgrades.js?v=20260928_mobile_perf_v1', 'renderUpgrades'],
  market: ['./screens/market.js?v=20260928_mobile_perf_v1', 'renderMarket'],
  stocks: ['./screens/stocks.js?v=20260928_mobile_perf_v1', 'renderStocks'],
  military: ['./screens/military.js?v=20260928_mobile_perf_v1', 'renderMilitary'],
  creator: ['./screens/creator.js?v=20260928_mobile_perf_v1', 'renderCreator'],
  leaderboard: ['./screens/leaderboard.js?v=20260928_mobile_perf_v1', 'renderLeaderboard'],
  help: ['./screens/help.js?v=20260928_mobile_perf_v1', 'renderHelp'],
};

export async function loadScreen(tab) {
  const [path, exportName] = screens[tab] || screens.overview;
  const module = await import(path);
  return module[exportName];
}
