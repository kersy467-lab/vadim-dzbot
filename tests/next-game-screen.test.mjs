import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

test('admin launcher opens a lazy next-game screen without replacing legacy tab contracts', async () => {
  const [html, app, loader, api] = await Promise.all([
    read('../frontend/natbirzha/index.html'),
    read('../frontend/natbirzha/js/app.js'),
    read('../frontend/natbirzha/js/screen_loader.js'),
    read('../frontend/natbirzha/js/api.js'),
  ]);
  assert.match(html, /id="next-game-nav-btn"/);
  assert.match(app, /next-game-nav-btn/);
  assert.match(app, /user\?\.is_creator === true/);
  assert.match(app, /backToMain = tab === 'next-game' && tab === store.currentTab/);
  assert.match(loader, /'next-game': \['\.\/screens\/next_game\.js/);
  for (const method of ['getNextGameMap', 'createNextGameCompany', 'selectNextGameSector', 'selectNextGameBranch']) {
    assert.match(api, new RegExp(`${method}:`));
  }
  const tabs = [...html.matchAll(/data-tab="(overview|production|upgrades|market|military|leaderboard)"/g)];
  assert.deepEqual(tabs.map((match) => match[1]), ['overview', 'production', 'upgrades', 'market', 'military', 'leaderboard']);
});

test('next-game screen shows saved sector and branch choices with isolated-test messaging', async () => {
  const screen = await read('../frontend/natbirzha/js/screens/next_game.js');
  assert.match(screen, /НАТБИРЖА 2\.0/);
  assert.match(screen, /тестовую компанию/);
  assert.match(screen, /Выбери одну из семи стартовых корпораций/);
  assert.match(screen, /future_choices/);
  assert.match(screen, /selectNextGameSector/);
  assert.match(screen, /selectNextGameBranch/);
});
