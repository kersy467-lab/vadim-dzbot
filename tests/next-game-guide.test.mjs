import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';
import { renderMore } from '../frontend/natbirzha/js/screens/next_game_shell.js';
import { FAQ, FLOW, STEPS, renderNextGameGuide } from '../frontend/natbirzha/js/screens/next_game_guide.js';

test('More contains a guide tile and the guide offers direct navigation to core screens', () => {
  const more = renderMore(false);
  assert.match(more, /data-next-view="guide"/);
  assert.match(more, /Гайд по игре/);
  const container = { innerHTML: '' };
  renderNextGameGuide(container);
  for (const view of ['map', 'factories', 'market', 'more']) assert.match(container.innerHTML, new RegExp(`data-next-view="${view}"`));
  assert.equal(FLOW.length, 5);
  assert.equal(STEPS.length, 4);
  assert.equal(FAQ.length, 3);
  assert.match(container.innerHTML, /aria-label="Схема игрового цикла"/);
  assert.match(container.innerHTML, /повышает выпуск назначенного завода на 8–10%/);
  assert.doesNotMatch(container.innerHTML, /менеджер уменьшает расход cash/);
  assert.equal((container.innerHTML.match(/<svg /g) || []).length, 10);
});

test('guide stylesheet and lazy route are included in the cached mini app entry chain', async () => {
  const [html, app, loader, entry, css] = await Promise.all([
    readFile(new URL('../frontend/natbirzha/index.html', import.meta.url), 'utf8'),
    readFile(new URL('../frontend/natbirzha/js/app.js', import.meta.url), 'utf8'),
    readFile(new URL('../frontend/natbirzha/js/screen_loader.js', import.meta.url), 'utf8'),
    readFile(new URL('../frontend/natbirzha/js/screens/next_game.js', import.meta.url), 'utf8'),
    readFile(new URL('../frontend/natbirzha/css/next-game-guide.css', import.meta.url), 'utf8'),
  ]);
  assert.match(html, /next-game-guide\.css\?v=20261012_player_guide_v1/);
  assert.match(html, /app\.js\?v=20261012_theme_art_v1/);
  assert.match(app, /screen_loader\.js\?v=20261012_theme_art_v1/);
  assert.match(loader, /next_game\.js\?v=20261012_theme_art_v1/);
  assert.match(entry, /next_game_guide\.js\?v=20261012_theme_art_v1/);
  assert.match(css, /prefers-reduced-motion|ng-guide-flow/);
});
