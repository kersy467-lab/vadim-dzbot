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
  const more = renderMore();
  for (const view of ['bank', 'capital', 'competition', 'help', 'contracts', 'admin']) {
    assert.match(more, new RegExp(`data-next-view="${view}"`));
  }
});

test('every service tile in More has a mounted screen and an API-backed section', async () => {
  const { readFile } = await import('node:fs/promises');
  const more = renderMore();
  const targets = [...more.matchAll(/data-next-view="([a-z-]+)"/g)].map((match) => match[1]);
  const entry = await readFile(new URL('../frontend/natbirzha/js/screens/next_game.js', import.meta.url), 'utf8');
  const api = await readFile(new URL('../frontend/natbirzha/js/next_game_api.js', import.meta.url), 'utf8');
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
  };

  assert.equal(new Set(targets).size, 12);
  for (const target of targets) {
    const service = services[target];
    assert.ok(service, `service tile has no screen/API mapping: ${target}`);
    assert.ok(entry.includes(service[0]), `service tile has no screen module: ${target}`);
    assert.ok(api.includes(service[1]), `service tile has no backend API: ${target}`);
  }
});

test('active production scores timed lock-pick taps and tears down on screen navigation', async () => {
  const { readFile } = await import('node:fs/promises');
  const entry = await readFile(new URL('../frontend/natbirzha/js/screens/next_game.js', import.meta.url), 'utf8');
  const scene = await readFile(new URL('../frontend/natbirzha/js/active_production/scene.mjs', import.meta.url), 'utf8');

  assert.match(entry, /registerScreenCleanup/);
  assert.match(entry, /function retireSession/);
  assert.match(entry, /function closeActiveProduction/);
  assert.match(entry, /view !== 'active-production'/);
  assert.match(entry, /import\('\.\.\/active_production\/scene\.mjs\?v=/);
  assert.match(scene, /data-active-tap/);
  assert.match(scene, /canvas\.addEventListener\('pointerdown'/);
  assert.match(scene, /tap_at_ms: localTapAtServerMs/);
  assert.match(scene, /game\.pendingTapAt/);
  assert.match(scene, /estimateServerClockOffset/);
  assert.match(scene, /window\.addEventListener\('blur'/);
  assert.match(scene, /document\.addEventListener\('visibilitychange'/);
  assert.match(scene, /pauseServer = async/);
  assert.match(scene, /const resume = async/);
  assert.match(scene, /game\.pauseRequested = true/);
  assert.match(scene, /game\.closed \|\| game\.pauseRequested \|\| document\.hidden/);
  assert.match(scene, /const destroy = async/);
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
  assert.match(markup, /не хватает 3/);
  assert.match(markup, /data-next-build="b0"[^>]+disabled/);
  state.company.cash = 500;
  markup = renderFactories(state);
  assert.doesNotMatch(markup, /data-next-build="b0"[^>]+disabled/);
  state.facilities.push({ branch_id: 'b0', recipe, status: 'blocked', level: 1, blocked_reason: 'Руда' });
  assert.match(renderFactories(state), /Запасов не хватает на один цикл/);
  assert.match(renderFactories(state), /Пополнить ресурсы/);
});

test('overview uses remaining XP and offers the correct first production action', () => {
  const markup = renderOverview(fixture());
  assert.match(markup, /aria-valuenow="20"/);
  assert.match(markup, /data-next-view="factories">Построить первый завод/);
});
