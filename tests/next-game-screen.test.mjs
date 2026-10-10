import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

test('admin launcher opens a lazy next-game screen without replacing legacy tab contracts', async () => {
  const [html, app, loader, api, nextGameApi] = await Promise.all([
    read('../frontend/natbirzha/index.html'),
    read('../frontend/natbirzha/js/app.js'),
    read('../frontend/natbirzha/js/screen_loader.js'),
    read('../frontend/natbirzha/js/api.js'),
    read('../frontend/natbirzha/js/next_game_api.js'),
  ]);
  assert.match(html, /id="next-game-nav-btn"/);
  assert.match(html, /\/static\/natbirzha\/js\/app\.js\?v=20261010_launcher_visibility_v1/);
  assert.match(app, /next-game-nav-btn/);
  assert.match(app, /is-next-game/);
  assert.match(app, /renderTab !== 'next-game'/);
  assert.match(app, /user\?\.is_creator === true/);
  assert.match(app, /next-game-nav-btn'\)\?\.classList\.toggle\('hidden', !isCreator\)/);
  assert.match(app, /backToMain = tab === 'next-game' && tab === store.currentTab/);
  assert.match(loader, /'next-game': \['\.\/screens\/next_game\.js/);
  for (const method of [
    'getNextGameMap', 'createNextGameCompany', 'selectNextGameSector',
    'selectNextGameBranch', 'advanceNextGameBranch', 'buildNextGameFacility',
    'tradeNextGameMarket', 'upgradeNextGameFacility',
  ]) {
    assert.match(nextGameApi, new RegExp(`${method}:`));
  }
  assert.match(api, /\.\.\.createNextGameAPI\(request\)/);
  const tabs = [...html.matchAll(/data-tab="(overview|production|upgrades|market|military|leaderboard)"/g)];
  assert.deepEqual(tabs.map((match) => match[1]), ['overview', 'production', 'upgrades', 'market', 'military', 'leaderboard']);
});

test('modular 2.0 screen preserves saved routes, factory actions and lazy economic sections', async () => {
  const [screen, development, factories, shell, api] = await Promise.all([
    read('../frontend/natbirzha/js/screens/next_game.js'),
    read('../frontend/natbirzha/js/screens/next_game_development.js'),
    read('../frontend/natbirzha/js/screens/next_game_factories.js'),
    read('../frontend/natbirzha/js/screens/next_game_shell.js'),
    read('../frontend/natbirzha/js/next_game_api.js'),
  ]);
  for (const action of ['selectNextGameSector', 'selectNextGameBranch', 'advanceNextGameBranch']) assert.ok(development.includes(action));
  for (const action of ['buildNextGameFacility', 'upgradeNextGameFacility', 'updateNextGameSettings']) assert.ok(factories.includes(action));
  assert.match(development, /next_branch_ids/);
  assert.match(factories, /blocked_reason/);
  assert.match(factories, /data-next-upgrade/);
  assert.match(screen, /getNextGameMap\('overview'\)/);
  assert.match(screen, /version !== session.version/);
  for (const module of ['market', 'bank', 'capital', 'bonds', 'contracts', 'progression', 'operations', 'civic']) assert.ok(screen.includes(`next_game_${module}.js`));
  assert.match(shell, /НАТБИРЖА 2\.0/);
  assert.match(shell, /Инвестиции/);
  assert.match(shell, /Помощь/);
  assert.ok(!shell.includes("['military'"));
  for (const method of ['openNextGameIPO', 'createNextGameShareOrder', 'cancelNextGameShareOrder', 'distributeNextGameDividend']) assert.ok(api.includes(`${method}:`));
});

test('2.0 banking accounts expose idempotent account opening and fee-backed company payments', async () => {
  const [bankingApi, bankScreen, routes, service, snapshot] = await Promise.all([
    read('../frontend/natbirzha/js/next_game_api.js'),
    read('../frontend/natbirzha/js/screens/next_game_bank.js'),
    read('../backend/natbirzha/api/next_game_banking_routes.py'),
    read('../backend/natbirzha/services/next_game_banking_service.py'),
    read('../backend/natbirzha/services/next_game_banking_read.py'),
  ]);
  assert.match(bankingApi, /openNextGameCorporateAccount:/);
  assert.match(bankingApi, /makeNextGameCompanyPayment:/);
  assert.match(bankingApi, /requestNextGameBusinessLoan:/);
  assert.match(bankingApi, /repayNextGameBusinessLoan:/);
  assert.match(bankScreen, /data-bank-account-open/);
  assert.match(bankScreen, /data-bank-payment-send/);
  assert.match(bankScreen, /data-bank-corporate-loan-request/);
  assert.match(bankScreen, /data-bank-business-loan-repay/);
  assert.match(bankScreen, /Комиссия за платёж/);
  assert.match(routes, /Depends\(get_current_creator\)/);
  assert.match(routes, /Idempotency-Key/);
  assert.match(snapshot, /fee_income/);
  assert.match(service, /Недостаточно cash на платёж и банковскую комиссию/);
});

test('2.0 direct finance contracts are escrowed, cancellable, and repayable in the bank screen', async () => {
  const [api, screen, routes, service] = await Promise.all([
    read('../frontend/natbirzha/js/next_game_api.js'),
    read('../frontend/natbirzha/js/screens/next_game_bank.js'),
    read('../backend/natbirzha/api/next_game_finance_routes.py'),
    read('../backend/natbirzha/services/next_game_finance_service.py'),
  ]);
  for (const method of [
    'createNextGameDirectLoanOffer', 'acceptNextGameDirectLoanOffer',
    'cancelNextGameDirectLoanOffer', 'repayNextGameDirectLoan',
  ]) assert.match(api, new RegExp(`${method}:`));
  for (const control of [
    'data-next-finance-offer', 'data-next-finance-accept',
    'data-next-finance-cancel', 'data-next-finance-repay',
  ]) assert.match(screen, new RegExp(control));
  assert.match(screen, /Прямые займы компаний/);
  assert.match(routes, /Depends\(get_current_creator\)/);
  assert.match(routes, /Idempotency-Key/);
  assert.match(service, /DIRECT_LOAN_ESCROW/);
  assert.match(service, /DIRECT_LOAN_DISBURSED/);
  assert.match(service, /DIRECT_LOAN_REPAY/);
});
