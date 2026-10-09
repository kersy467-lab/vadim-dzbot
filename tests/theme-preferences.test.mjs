import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import {
  DEFAULT_THEME,
  THEMES,
  applyTheme,
  initThemePicker,
  normalizeThemeId,
  readThemePreference,
  writeThemePreference,
} from '../frontend/natbirzha/js/theme_preferences.mjs';

test('three named themes are available and ivory sage remains the default', () => {
  assert.equal(DEFAULT_THEME, 'ivory');
  assert.deepEqual(THEMES.map(({ id }) => id), ['ivory', 'midnight', 'pearl']);
  assert.ok(THEMES.every(({ label }) => typeof label === 'string' && label.length > 0));
});

test('theme preference normalizes invalid values and survives a reload', () => {
  const values = new Map();
  const storage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
  };

  assert.equal(normalizeThemeId('unknown'), 'ivory');
  assert.equal(readThemePreference(storage), 'ivory');
  assert.equal(writeThemePreference('midnight', storage), 'midnight');
  assert.equal(readThemePreference(storage), 'midnight');
  assert.equal(writeThemePreference('not-a-theme', storage), 'ivory');
  assert.equal(readThemePreference(storage), 'ivory');
});

test('theme storage failures fall back safely', () => {
  const unavailable = {
    getItem() { throw new Error('storage blocked'); },
    setItem() { throw new Error('storage blocked'); },
  };
  assert.equal(readThemePreference(unavailable), 'ivory');
  assert.equal(writeThemePreference('pearl', unavailable), 'pearl');
});

test('applying a theme updates the root palette and light/dark browser scheme', () => {
  const root = { dataset: {}, style: {} };
  assert.equal(applyTheme(root, 'midnight'), 'midnight');
  assert.equal(root.dataset.theme, 'midnight');
  assert.equal(root.style.colorScheme, 'dark');
  applyTheme(root, 'pearl');
  assert.equal(root.dataset.theme, 'pearl');
  assert.equal(root.style.colorScheme, 'light');
});

test('theme picker updates the palette immediately and persists the selection', () => {
  const values = new Map();
  const storage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
  };
  const root = { dataset: {}, style: {} };
  let listener;
  const selector = {
    value: '',
    addEventListener: (name, callback) => { if (name === 'change') listener = callback; },
  };
  const documentRef = {
    documentElement: root,
    getElementById: (id) => id === 'theme-select' ? selector : null,
  };

  initThemePicker({ documentRef, storage });
  assert.equal(selector.value, 'ivory');
  selector.value = 'pearl';
  listener();
  assert.equal(root.dataset.theme, 'pearl');
  assert.equal(values.get('natbirzha-theme'), 'pearl');
});

test('app shell exposes the theme selector and loads theme preferences before app startup', async () => {
  const html = await readFile(new URL('../frontend/natbirzha/index.html', import.meta.url), 'utf8');
  assert.match(html, /id="theme-select"/);
  assert.match(html, /theme_preferences\.mjs/);
  assert.ok(html.indexOf('theme_preferences.mjs') < html.indexOf('js/app.js'));
});
