const fs = require('fs');
const path = require('path');
const assert = require('assert');

console.log('=== [1/4] Testing ege_data.js data integrity ===');
const egeData = require('../frontend/js/ege_data.js');

assert(egeData.subjects && Array.isArray(egeData.subjects), 'subjects must be an array');
assert(egeData.subjects.length === 4, `Must have exactly 4 subjects, got ${egeData.subjects.length}`);

const rus = egeData.subjects.find(s => s.id === 'russian');
assert(rus && rus.available === true, 'Russian subject must be available');

const task4 = rus.tasks.find(t => t.number === 4);
assert(task4 && task4.available === true, 'Task 4 must be available');

const math = egeData.subjects.find(s => s.id === 'math');
assert(math && math.available === true, 'Math subject must be available');
const task18 = math.tasks.find(t => t.number === 18);
assert(task18 && task18.available === true, 'Task 18 must be available');

const RUSSIAN_VOWELS = new Set("аеёиоуыэюяАЕЁИОУЫЭЮЯ".split(""));
const validPos = new Set(["noun", "adjective", "verb", "participle", "gerund", "adverb"]);

const words = egeData.task4_words;
console.log(`Found ${words.length} words in task4_words`);
assert(words.length >= 220, `Expected at least 220 words, got ${words.length}`);

const seen = new Set();
words.forEach((w, idx) => {
  assert(w.word, `Word at index ${idx} missing word string`);
  const key = `${w.word}_${w.pos}`;
  assert(!seen.has(key), `Duplicate word found: ${key}`);
  seen.add(key);

  // Find stressed vowel(s) in word: characters that are uppercase
  const uppercaseChars = w.word.split("").filter(ch => ch === ch.toUpperCase() && ch !== ch.toLowerCase());
  assert(uppercaseChars.length >= 1, `Word ${w.word} has no uppercase stress marker`);

  uppercaseChars.forEach(ch => {
    assert(RUSSIAN_VOWELS.has(ch), `Word ${w.word}: uppercase marker '${ch}' is not a Russian vowel`);
  });

  assert(validPos.has(w.pos), `Word ${w.word} has invalid POS: ${w.pos}`);
});

console.log(`All ${words.length} words passed uppercase vowel stress and POS validation!`);

assert(Array.isArray(egeData.excluded_words), 'excluded_words must be an array');
console.log(`Excluded words array is present (length: ${egeData.excluded_words.length}).`);

console.log('=== [2/4] Testing HTML markup & elements ===');
const html = fs.readFileSync(path.join(__dirname, '../frontend/index.html'), 'utf-8');
assert(html.includes('id="pane-ege"'), 'index.html must have pane-ege');
assert(html.includes('id="pane-games"'), 'index.html must have pane-games');
assert(html.includes('data-tab="ege"'), 'index.html must have ege tab button');
assert(html.includes('data-tab="games"'), 'index.html must have games tab button');
assert(html.includes('/static/js/ege_data.js'), 'index.html must import ege_data.js');
assert(html.includes('/static/js/ege_math18_data.js'), 'index.html must import ege_math18_data.js');
assert(html.includes('/static/js/ege.js'), 'index.html must import ege.js');
assert(html.includes('/static/js/games.js'), 'index.html must import games.js');
assert(html.indexOf('id="daily-fact-widget"') > html.indexOf('id="pane-schedule"'), 'daily-fact-widget must be placed inside pane-schedule');
assert(html.indexOf('id="daily-fact-widget"') < html.indexOf('id="pane-homework"'), 'daily-fact-widget must be before pane-homework');
console.log('HTML structure, daily-fact-widget placement in pane-schedule and script tags verified!');

console.log('=== [3/4] Testing app.js tab logic ===');
const appJs = fs.readFileSync(path.join(__dirname, '../frontend/js/app.js'), 'utf-8');
assert(appJs.includes('tab === "ege"'), 'app.js must handle ege tab');
assert(appJs.includes('tab === "games"'), 'app.js must handle games tab');
assert(appJs.includes('window.EGE.init'), 'app.js must call window.EGE.init');
assert(appJs.includes('window.GAMES.init'), 'app.js must call window.GAMES.init');
const lightboxJs = fs.readFileSync(path.join(__dirname, '../frontend/js/app_lightbox.js'), 'utf-8');
assert(lightboxJs.includes('typeof photo === "string"') || appJs.includes('typeof photo === "string"'), 'app_lightbox.js must support raw string URLs in showGalleryImage');
assert(lightboxJs.includes('window.openPhotoGallery = openPhotoGallery') || appJs.includes('window.openPhotoGallery = openPhotoGallery'), 'app_lightbox.js must expose openPhotoGallery on window');
console.log('app.js and app_lightbox.js tab integration and photo gallery verified!');

console.log('=== [4/4] Testing ege.js and games.js execution in mock DOM environment ===');
// Create a basic window mock
const mockApi = {
  getMe: async () => ({ id: 1, full_name: 'Тестер', is_tester: true, coins: 100 }),
  getGameRoom: async (id) => ({ room_id: id, status: 'waiting', game_type: 'tictactoe' }),
  joinGameRoom: async (id, name) => ({ room_id: id, status: 'playing', game_type: 'tictactoe' }),
  getClassmates: async () => []
};
const mockWindow = {
  EGE_DATA: egeData,
  api: mockApi,
  Telegram: {
    WebApp: {
      HapticFeedback: {
        impactOccurred: () => {},
        notificationOccurred: () => {},
        selectionChanged: () => {}
      }
    }
  }
};
global.window = mockWindow;
global.api = mockApi;
global.fetch = async (url) => ({
  ok: true,
  json: async () => ({ room_id: 'test', status: 'waiting', players: [1] })
});
const sharedElements = {};
global.document = {
  getElementById: (id) => {
    if (!sharedElements[id]) {
      sharedElements[id] = {
        innerHTML: '',
        classList: { add: () => {}, remove: () => {} },
        appendChild: () => {},
        remove: () => {}
      };
    }
    return sharedElements[id];
  },
  querySelectorAll: () => []
};

// Evaluate ege_math18_data.js
const math18Script = fs.readFileSync(path.join(__dirname, '../frontend/js/ege_math18_data.js'), 'utf-8');
eval(math18Script);
assert(mockWindow.EGE_MATH18_TASKS && Array.isArray(mockWindow.EGE_MATH18_TASKS), 'EGE_MATH18_TASKS must be an array');
assert(mockWindow.EGE_MATH18_TASKS.length === 153, `Expected 153 tasks, got ${mockWindow.EGE_MATH18_TASKS.length}`);
console.log(`Loaded ${mockWindow.EGE_MATH18_TASKS.length} math tasks successfully!`);

// Evaluate EGE submodules in order matching index.html
['ege_math18.js', 'ege_paronyms.js', 'ege_stress.js', 'ege_core.js'].forEach(m => {
  const p = path.join(__dirname, '../frontend/js/ege/', m);
  if (fs.existsSync(p)) eval(fs.readFileSync(p, 'utf-8'));
});

// Evaluate ege.js
const egeScript = fs.readFileSync(path.join(__dirname, '../frontend/js/ege.js'), 'utf-8');
eval(egeScript);
assert(mockWindow.EGE && typeof mockWindow.EGE.init === 'function', 'window.EGE.init must be defined');
assert(typeof mockWindow.EGE.startQuiz === 'function', 'window.EGE.startQuiz must be defined');
assert(typeof mockWindow.EGE.answerQuestion === 'function', 'window.EGE.answerQuestion must be defined');
assert(typeof mockWindow.EGE.selectMath18Task === 'function', 'window.EGE.selectMath18Task must be defined');
assert(typeof mockWindow.EGE.nextMath18Task === 'function', 'window.EGE.nextMath18Task must be defined');
assert(typeof mockWindow.EGE.toggleMath18Solution === 'function', 'window.EGE.toggleMath18Solution must be defined');

// Test Math 18 default hidden solution behavior
mockWindow.EGE.selectSubject('math');
const mathHtmlInitial = sharedElements['pane-ege'] ? sharedElements['pane-ege'].innerHTML : '';
assert(mathHtmlInitial.includes('Открыть полное пошаговое решение'), 'Solution must be hidden by default');
assert(!mathHtmlInitial.includes('Ход решения'), 'Solution stream must NOT be visible by default');

// Toggle to show solution
mockWindow.EGE.toggleMath18Solution();
const mathHtmlOpen = sharedElements['pane-ege'] ? sharedElements['pane-ege'].innerHTML : '';
assert(mathHtmlOpen.includes('Скрыть решение'), 'Button should say "Скрыть решение"');
assert(mathHtmlOpen.includes('Ход решения'), 'Solution stream should be visible after toggle');

// Navigate to next task -> should be hidden by default again
mockWindow.EGE.nextMath18Task();
const mathHtmlNext = sharedElements['pane-ege'] ? sharedElements['pane-ege'].innerHTML : '';
assert(mathHtmlNext.includes('Открыть полное пошаговое решение'), 'Solution must be hidden again upon navigating to next task');
assert(!mathHtmlNext.includes('Ход решения'), 'Solution stream must NOT be visible upon navigating to next task');

console.log('window.EGE module loaded, math 18 default hidden solution verified!');

// Evaluate games.js
const gamesScript = fs.readFileSync(path.join(__dirname, '../frontend/js/games.js'), 'utf-8');
eval(gamesScript);
assert(mockWindow.GAMES && typeof mockWindow.GAMES.init === 'function', 'window.GAMES.init must be defined');
assert(typeof mockWindow.GAMES.switchGame === 'function', 'window.GAMES.switchGame must be defined');
assert(typeof mockWindow.GAMES.reset2048 === 'function', 'window.GAMES.reset2048 must be defined');
assert(typeof mockWindow.GAMES.cellClickTTT === 'function', 'window.GAMES.cellClickTTT must be defined');
assert(typeof mockWindow.GAMES.startSnakeGame === 'function', 'window.GAMES.startSnakeGame must be defined');
assert(typeof mockWindow.GAMES.setChessColor === 'function', 'window.GAMES.setChessColor must be defined');

// Test tester-only RPG game restriction
mockWindow.GAMES.updateTesterStatus(false);
mockWindow.GAMES.switchGame('rpg');
assert(mockWindow.GAMES.getCurrentGame() !== 'rpg', 'Non-tester must not be able to switch to RPG game');
assert(mockWindow.GAMES.getCurrentGame() === '2048', 'Non-tester should fall back to 2048');

mockWindow.GAMES.updateTesterStatus(true);
mockWindow.GAMES.switchGame('rpg');
assert(mockWindow.GAMES.getCurrentGame() === 'rpg', 'Tester must be able to switch to RPG game');

// Test tester-only Natbirzha banner exposure
mockWindow.GAMES.updateTesterStatus(false);
const paneNonTester = sharedElements['pane-games'] ? sharedElements['pane-games'].innerHTML : '';
assert(!paneNonTester.includes('НАТБИРЖА'), 'Non-tester must not see Natbirzha banner');

mockWindow.GAMES.updateTesterStatus(true);
const paneTester = sharedElements['pane-games'] ? sharedElements['pane-games'].innerHTML : '';
assert(paneTester.includes('НАТБИРЖА'), 'Tester must see Natbirzha banner');
assert(paneTester.includes('/app/natbirzha'), 'Natbirzha banner must link to /app/natbirzha');
console.log('window.GAMES module loaded, tester-only RPG & Natbirzha banner restrictions verified!');

console.log('=== [5/5] Testing multiplayer games & online room routing ===');
['game_2048.js', 'game_tictactoe.js', 'game_snake.js', 'game_tetris.js', 'game_chess.js'].forEach(m => {
  const p = path.join(__dirname, '../frontend/js/games/', m);
  if (fs.existsSync(p)) eval(fs.readFileSync(p, 'utf-8'));
});

['durak_cards.js', 'durak_menu.js', 'durak_game.js'].forEach(m => {
  const p = path.join(__dirname, '../frontend/js/durak/', m);
  if (fs.existsSync(p)) eval(fs.readFileSync(p, 'utf-8'));
});
eval(fs.readFileSync(path.join(__dirname, '../frontend/js/durak.js'), 'utf-8'));

assert(mockWindow.GAMES_CHESS && typeof mockWindow.GAMES_CHESS.openChessOnlineRoom === 'function', 'window.GAMES_CHESS.openChessOnlineRoom must be defined');
assert(mockWindow.GAMES_TICTACTOE && typeof mockWindow.GAMES_TICTACTOE.openOnlineRoom === 'function', 'window.GAMES_TICTACTOE.openOnlineRoom must be defined');
assert(mockWindow.DURAK && typeof mockWindow.DURAK.joinRoom === 'function', 'window.DURAK.joinRoom must be defined');

// Test openOnlineRoom routing
mockWindow.GAMES.openOnlineRoom('test_chess_room', 'chess');
assert(mockWindow.GAMES.getCurrentGame() === 'chess', 'openOnlineRoom should switch game to chess');

mockWindow.GAMES.openOnlineRoom('test_durak_room', 'durak');
assert(mockWindow.GAMES.getCurrentGame() === 'durak', 'openOnlineRoom should switch game to durak');

mockWindow.GAMES.openOnlineRoom('test_ttt_room', 'tictactoe');
assert(mockWindow.GAMES.getCurrentGame() === 'tictactoe', 'openOnlineRoom should switch game to tictactoe');

mockWindow.GAMES.switchGame('casino');
assert(mockWindow.GAMES.getCasinoSubGame() === 'durak', 'default casino subgame should be durak');
mockWindow.GAMES.switchCasinoSubGame('blackjack');
assert(mockWindow.GAMES.getCasinoSubGame() === 'blackjack', 'should switch to blackjack');
mockWindow.GAMES.switchCasinoSubGame('roulette');
assert(mockWindow.GAMES.getCasinoSubGame() === 'roulette', 'should switch to roulette');
mockWindow.GAMES.switchCasinoSubGame('dice');
assert(mockWindow.GAMES.getCasinoSubGame() === 'dice', 'should switch to dice');
mockWindow.GAMES.switchCasinoSubGame('slots');
assert(mockWindow.GAMES.getCasinoSubGame() === 'slots', 'should switch to slots');
mockWindow.GAMES.switchCasinoSubGame('coinflip');
assert(mockWindow.GAMES.getCasinoSubGame() === 'coinflip', 'should switch to coinflip');
mockWindow.GAMES.switchCasinoSubGame('leaderboard');
assert(mockWindow.GAMES.getCasinoSubGame() === 'leaderboard', 'should switch to leaderboard');

['blackjack.js', 'roulette.js', 'dice.js', 'slots.js', 'coinflip.js', 'casino_leaderboard.js'].forEach(m => {
  const p = path.join(__dirname, '../frontend/js/', m);
  if (fs.existsSync(p)) eval(fs.readFileSync(p, 'utf-8'));
});

assert(mockWindow.BLACKJACK && typeof mockWindow.BLACKJACK.setCustomStake === 'function', 'BLACKJACK.setCustomStake must be defined');
assert(mockWindow.DICE && typeof mockWindow.DICE.setCustomStake === 'function', 'DICE.setCustomStake must be defined');
assert(mockWindow.ROULETTE && typeof mockWindow.ROULETTE.setCustomChip === 'function', 'ROULETTE.setCustomChip must be defined');
assert(mockWindow.SLOTS && typeof mockWindow.SLOTS.setCustomStake === 'function', 'SLOTS.setCustomStake must be defined');
assert(mockWindow.COINFLIP && typeof mockWindow.COINFLIP.setCustomStake === 'function', 'COINFLIP.setCustomStake must be defined');
assert(mockWindow.CASINO_LEADERBOARD && typeof mockWindow.CASINO_LEADERBOARD.init === 'function', 'CASINO_LEADERBOARD.init must be defined');

console.log('Multiplayer online room opening, game switching, casino sub-tabs, custom stakes and exports verified without ReferenceError!');

console.log('=== [6/6] Testing natarGRP RPG module execution and UI rendering ===');
global.Image = class Image { constructor() { this.src = ''; this.onload = null; } };
global.localStorage = { getItem: () => null, setItem: () => {} };
global.requestAnimationFrame = () => 1;
global.cancelAnimationFrame = () => {};
mockApi.getRpgProfile = async () => ({ hero_class: 'knight', level: 5, dungeon_floor: 20, stats: {} });
mockApi.getRPGShop = async () => [];
const mockCtxProxy = new Proxy({}, {
  get: (target, prop) => {
    if (prop === 'canvas') return sharedElements['rpg-action-canvas'];
    return (...args) => ({ addColorStop: () => {}, width: 10 });
  }
});
const origGetEl = global.document.getElementById;
global.document.getElementById = (id) => {
  const el = origGetEl(id);
  if (!el.getContext) el.getContext = () => mockCtxProxy;
  if (!el.getBoundingClientRect) el.getBoundingClientRect = () => ({ left: 0, top: 0, width: 800, height: 600 });
  if (!el.addEventListener) el.addEventListener = () => {};
  if (!el.removeEventListener) el.removeEventListener = () => {};
  if (!el.remove) el.remove = () => {};
  return el;
};
global.document.createElement = (tag) => global.document.getElementById('el_' + tag + '_' + Math.random());
global.document.addEventListener = () => {};

eval(fs.readFileSync(path.join(__dirname, '../frontend/js/rpg.js'), 'utf-8'));
assert(mockWindow.RPG && typeof mockWindow.RPG.init === 'function', 'window.RPG.init must be defined');
assert(typeof mockWindow.RPG.renderRoot === 'function', 'window.RPG.renderRoot must be defined');

(async () => {
  await mockWindow.RPG.loadProfile();
  mockWindow.RPG.renderRoot();
  const farmHtml = sharedElements['rpg-root'] ? sharedElements['rpg-root'].innerHTML : '';
  assert(farmHtml.includes('rpg-action-canvas'), 'Farm arena should render canvas without ReferenceError');
  assert(farmHtml.includes('h-[320px]'), 'Normal farm arena should have 320px canvas');

  // Test farm mode switching: arena -> sim -> arena
  mockWindow.RPG.setFarmMode('sim');
  const simHtml = sharedElements['rpg-root'] ? sharedElements['rpg-root'].innerHTML : '';
  assert(simHtml.includes('🎮 Арена'), 'Sim mode must have Арена button');
  assert(simHtml.includes('Зарубить волну'), 'Sim mode must have fast sim slaughter button');

  mockWindow.RPG.setFarmMode('arena');
  const arenaBackHtml = sharedElements['rpg-root'] ? sharedElements['rpg-root'].innerHTML : '';
  assert(arenaBackHtml.includes('🎮 Арена'), 'Arena mode must have Арена button');
  assert(arenaBackHtml.includes('⚡ Авто'), 'Arena mode must have Авто button');
  assert(arenaBackHtml.includes('rpg-action-canvas'), 'Arena mode must render canvas');

  // Test boss fight rendering
  if (typeof mockWindow.RPG.startRaidBossActionBattle === 'function') {
    mockWindow.RPG.startRaidBossActionBattle({ id: 'roshan', name: 'Рошан', hp: 10000, maxHp: 10000 });
    mockWindow.RPG.renderRoot();
    const bossHtml = sharedElements['rpg-root'] ? sharedElements['rpg-root'].innerHTML : '';
    assert(bossHtml.includes('h-[520px]'), 'Boss fight arena should have 520px canvas');
    assert(bossHtml.includes('rpg-virtual-joystick-zone'), 'Boss fight arena should render virtual joystick zone');
  }

  console.log('natarGRP RPG module loaded, farm mode switching and boss arenas verified without ReferenceError!');
  
  // Run dedicated Natbirzha frontend module test suite
  require('./test_natbirzha_frontend.js');

  console.log('\n🎉 ALL FRONTEND, EGE AND NATBIRZHA TESTS PASSED SUCCESSFULLY! 🚀');
  process.exit(0);
})();

