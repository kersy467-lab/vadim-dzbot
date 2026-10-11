import assert from 'node:assert/strict';
import test from 'node:test';
import { renderHeader, renderShell, renderMore } from '../frontend/natbirzha/js/screens/next_game_shell.js';
import { renderDevelopment } from '../frontend/natbirzha/js/screens/next_game_development.js';
import { renderFactories, estimateAutonomy } from '../frontend/natbirzha/js/screens/next_game_factories.js';
import { renderOverview } from '../frontend/natbirzha/js/screens/next_game_overview.js';

function fixture(count = 35) {
  const branches = Array.from({ length: count }, (_, index) => ({
    id: `b${index}`, name: `Направление ${index}`, outputs: 'Сталь',
    is_starting_branch: index === 0, next_branch_ids: index === 0 ? ['b1', 'b2'] : [],
    factory: { facility_name: `Завод ${index}`, build_cost: 200, operating_cost: 20,
      output_name: 'Сталь', output_unit: 'т', output_quantity: 2, cycle_seconds: 600,
      inputs: { ore: 5 }, input_items: [{ item_id: 'ore', name: 'Руда', quantity: 5, unit: 'т' }] },
  }));
  return { company: { id: 1, name: '<script>', cash: 100, level: 1, xp_to_next_level: 800,
    sector_id: 'industry', branch_path: ['b0'] },
    corporations: [{ id: 'industry', name: 'Промышленность', branches }],
    market: [{ item_id: 'ore', name: 'Руда', unit: 'т', quantity: 22 }],
    facilities: [], recent_activity: [], settings: { auto_upgrade: false } };
}

test('five bottom destinations and grouped finance services use accessible vector icons', () => {
  const shell = renderShell(fixture().company, 'bank');
  assert.equal((shell.match(/data-next-view=/g) || []).length, 5);
  const nav = shell.match(/<nav class="next-game-nav"[\s\S]*?<\/nav>/)?.[0] || '';
  assert.equal((nav.match(/<svg /g) || []).length, 5);
  assert.match(shell, /data-next-view="more" class="is-active" aria-current="page"/);
  assert.match(shell, /&lt;script&gt;/);
  assert.doesNotMatch(shell, /military|upgrades|data-next-view="bank"/);
  const more = renderMore(true);
  for (const view of ['bank', 'capital', 'competition', 'help', 'contracts', 'admin']) {
    assert.match(more, new RegExp(`data-next-view="${view}"`));
  }
  for (const section of ['0.1', '0.2', '0.3', '0.4', '0.5', '0.6']) {
    assert.match(more, new RegExp(`data-service-group="${section}"`));
  }
  assert.match(more, /data-next-view="war"/);
  assert.match(more, /data-next-view="legacy-admin"/);
  assert.doesNotMatch(renderMore(false), /data-next-view="admin"|data-next-view="legacy-admin"/);
});

test('every service tile in More has a mounted screen and an API-backed section', async () => {
  const { readFile } = await import('node:fs/promises');
  const more = renderMore(true);
  const targets = [...more.matchAll(/data-next-view="([a-z-]+)"/g)].map((match) => match[1]);
  const entry = await readFile(new URL('../frontend/natbirzha/js/screens/next_game.js', import.meta.url), 'utf8');
  const api = await readFile(new URL('../frontend/natbirzha/js/next_game_api.js', import.meta.url), 'utf8');
  const legacyApi = await readFile(new URL('../frontend/natbirzha/js/api.js', import.meta.url), 'utf8');
  const services = {
    progression: ['next_game_progression.js', '/progression'],
    operations: ['next_game_operations.js', '/operations/actions'],
    bank: ['next_game_bank.js', '/bank/loan'],
    capital: ['next_game_capital.js', '/capital/ipo'],
    bonds: ['next_game_bonds.js', '/bonds'],
    civic: ['next_game_civic.js', '/civic'],
    contracts: ['next_game_contracts.js', '/partnerships/supply'],
    projects: ['next_game_contracts.js', '/partnerships/projects'],
    liquidation: ['next_game_liquidation.js', '/liquidation'],
    competition: ['next_game_competition.js', '/competition'],
    help: ['next_game_support.js', '/support'],
    admin: ['next_game_admin.js', '/admin/operations'],
    war: ['military.js', '/api/natbirzha/military/status'],
    'legacy-admin': ['creator.js', '/api/natbirzha/creator/audit-log'],
  };

  assert.equal(new Set(targets).size, 14);
  for (const target of targets) {
    const service = services[target];
    assert.ok(service, `service tile has no screen/API mapping: ${target}`);
    assert.ok(entry.includes(service[0]), `service tile has no screen module: ${target}`);
    assert.ok((api + legacyApi).includes(service[1]), `service tile has no backend API: ${target}`);
  }
});

test('factory screen uses passive production and no active game or multiplier UI', async () => {
  const { readFile } = await import('node:fs/promises');
  const entry = await readFile(new URL('../frontend/natbirzha/js/screens/next_game.js', import.meta.url), 'utf8');
  const factories = await readFile(new URL('../frontend/natbirzha/js/screens/next_game_factories.js', import.meta.url), 'utf8');
  const html = await readFile(new URL('../frontend/natbirzha/index.html', import.meta.url), 'utf8');

  assert.match(entry, /registerScreenCleanup/);
  assert.doesNotMatch(entry, /active-production|mountActiveProductionScene|startNextGameActiveProduction/);
  assert.doesNotMatch(factories, /×\s*1[,.]|data-active-production|Играть в сцене|множитель/iu);
  assert.match(factories, /data-next-upgrade/);
  assert.match(factories, /data-next-auto-upgrade/);
  assert.doesNotMatch(html, /next-game-active-production\.css/);
});

test('company header restores identity, sector, progression and creator-only state access', () => {
  const state = fixture();
  state.company.ticker = 'NORTH';
  state.company.level = 60;
  state.company.xp = 110000;
  state.company.xp_to_next_level = 0;
  state.settings.rebirths = 2;

  const header = renderHeader(state, true);
  assert.match(header, /NORTH/);
  assert.match(header, /Промышленность/);
  assert.match(header, /<small>Уровень<\/small><b>60/u);
  assert.match(header, /<small>Мастерство<\/small><b>51/u);
  assert.match(header, /<small>Перерождение<\/small><b>2\s*<em>\/ 10/u);
  assert.match(header, /data-next-admin/);
  assert.doesNotMatch(renderHeader(state, false), /data-next-admin/);
});

test('development displays connected route, two gated choices and bounded catalog', () => {
  const state = fixture(1000);
  const markup = renderDevelopment(state);
  assert.match(markup, /next-game-graph-route/);
  assert.equal((markup.match(/data-next-branch=/g) || []).length, 2);
  assert.equal((markup.match(/class="next-game-catalog-node/g) || []).length, 12);
  assert.match(markup, /1–12 из 1000/);
  assert.match(markup, /data-next-branch="b1"[^>]+disabled/);
  state.company.level = 2;
  state.facilities.push({ branch_id: 'b0' });
  assert.doesNotMatch(renderDevelopment(state), /data-next-branch="b1"[^>]+disabled/);
  assert.match(renderDevelopment(state, { page: 1 }), /13–24 из 1000/);
  assert.match(renderDevelopment(state, { query: 'Направление 999', inspected: 'b999' }), /Ресурсы на цикл/);
});

test('autonomy respects cash and limiting input with visible shortages and build affordability', () => {
  const state = fixture();
  const recipe = state.corporations[0].branches[0].factory;
  assert.deepEqual(estimateAutonomy(recipe, state), { cycles: 4, seconds: 2400 });
  state.market[0].quantity = 2;
  assert.deepEqual(estimateAutonomy(recipe, state), { cycles: 0, seconds: 0 });
  let markup = renderFactories(state);
  assert.match(markup, /нужно ещё 3/);
  assert.match(markup, /data-next-build="b0"[^>]+disabled/);
  state.company.cash = 500;
  markup = renderFactories(state);
  assert.doesNotMatch(markup, /data-next-build="b0"[^>]+disabled/);
  state.facilities.push({ branch_id: 'b0', recipe, status: 'blocked', level: 1, blocked_reason: 'Руда' });
  assert.match(renderFactories(state), /Запасов не хватает на один цикл/);
  assert.match(renderFactories(state), /Пополнить склад/);
});

test('overview uses remaining XP and offers the correct first production action', () => {
  const state = fixture();
  state.recent_activity = [{ action: 'BUY', cash_change: -99, item_name: 'Руда', created_at: '2026-10-11T10:00:00Z' }];
  const markup = renderOverview(state);
  assert.match(markup, /aria-valuenow="20"/);
  assert.match(markup, /data-next-view="factories">Построить первый завод/);
  assert.doesNotMatch(markup, /Последние операции|ЖУРНАЛ КОМПАНИИ|Руда/);
});

test('More routes mount legacy war and the complete old administration panel inside V2', async () => {
  const { readFile } = await import('node:fs/promises');
  const entry = await readFile(new URL('../frontend/natbirzha/js/screens/next_game.js', import.meta.url), 'utf8');
  const app = await readFile(new URL('../frontend/natbirzha/js/app.js', import.meta.url), 'utf8');
  const html = await readFile(new URL('../frontend/natbirzha/index.html', import.meta.url), 'utf8');
  assert.match(entry, /renderMilitary/);
  assert.match(entry, /renderCreator/);
  assert.match(entry, /legacy-admin/);
  assert.match(entry, /view === 'war'/);
  assert.match(app, /screen_loader\.js\?v=20261011_v2_consolidation_v1/);
  assert.match(html, /app\.js\?v=20261011_v2_consolidation_v1/);
});
