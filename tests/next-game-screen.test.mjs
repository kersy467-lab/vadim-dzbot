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

test('next-game screen shows saved sector and branch choices with isolated-test messaging', async () => {
  const [screen, api, nextGameApi, bankScreen, capitalScreen, competitionScreen] = await Promise.all([
    read('../frontend/natbirzha/js/screens/next_game.js'),
    read('../frontend/natbirzha/js/api.js'),
    read('../frontend/natbirzha/js/next_game_api.js'),
    read('../frontend/natbirzha/js/screens/next_game_bank.js'),
    read('../frontend/natbirzha/js/screens/next_game_capital.js'),
    read('../frontend/natbirzha/js/screens/next_game_competition.js'),
  ]);
  assert.match(screen, /НАТБИРЖА 2\.0/);
  assert.match(screen, /тестовую компанию/);
  assert.match(screen, /Выбери одну из семи стартовых корпораций/);
  assert.match(screen, /future_choices/);
  assert.match(screen, /selectNextGameSector/);
  assert.match(screen, /selectNextGameBranch/);
  assert.match(screen, /buildNextGameFacility/);
  assert.match(screen, /tradeNextGameMarket/);
  assert.match(screen, /next_branch_ids/);
  assert.match(screen, /data-next-view/);
  assert.match(bankScreen, /Расчётный банк 2\.0/);
  assert.match(screen, /input_items/);
  assert.match(bankScreen, /requestNextGameBankLoan/);
  assert.match(bankScreen, /repayNextGameBankLoan/);
  assert.match(bankScreen, /Срочный вклад/);
  assert.match(bankScreen, /openNextGameBankDeposit/);
  assert.match(bankScreen, /withdrawNextGameBankDeposit/);
  assert.match(screen, /advanceNextGameBranch/);
  assert.match(screen, /blocked_reason/);
  assert.match(screen, /data-next-upgrade/);
  assert.match(screen, /без дополнительного расхода сырья/);
  assert.match(screen, /История межкорпоративных сделок/);
  assert.match(screen, /Сделки между компаниями ведутся отдельно от расчётов с казной/);
  assert.match(bankScreen, /Казённые операции записываются в двойной журнал/);
  assert.match(api, /\.\.\.createNextGameAPI\(request\)/);
  assert.match(nextGameApi, /buildNextGameFacility:/);
  assert.match(nextGameApi, /tradeNextGameMarket:/);
  assert.match(nextGameApi, /upgradeNextGameFacility:/);
  assert.match(nextGameApi, /openNextGameBankDeposit:/);
  assert.match(nextGameApi, /withdrawNextGameBankDeposit:/);
  for (const method of ['openNextGameIPO', 'createNextGameShareOrder', 'cancelNextGameShareOrder', 'distributeNextGameDividend']) {
    assert.match(nextGameApi, new RegExp(`${method}:`));
  }
  assert.match(screen, /renderCapital/);
  assert.match(screen, /Капитал/);
  assert.match(screen, /Рейтинг/);
  assert.match(screen, /getNextGameCompetition/);
  assert.match(competitionScreen, /Лига корпораций 2\.0/);
  assert.match(competitionScreen, /production_24h/);
  assert.match(capitalScreen, /data-equity-ipo/);
  assert.match(capitalScreen, /data-equity-side/);
  assert.match(capitalScreen, /data-equity-dividend-pay/);
});

test('2.0 banking accounts expose idempotent account opening and fee-backed company payments', async () => {
  const [bankingApi, bankScreen, routes, snapshot] = await Promise.all([
    read('../frontend/natbirzha/js/next_game_api.js'),
    read('../frontend/natbirzha/js/screens/next_game_bank.js'),
    read('../backend/natbirzha/api/next_game_banking_routes.py'),
    read('../backend/natbirzha/services/next_game_banking_service.py'),
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
  assert.match(snapshot, /Недостаточно cash на платёж и банковскую комиссию/);
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
