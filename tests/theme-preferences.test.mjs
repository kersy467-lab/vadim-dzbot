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

function luminance(hex) {
  const channels = hex.match(/[0-9a-f]{2}/gi).map((pair) => parseInt(pair, 16) / 255);
  const linear = channels.map((value) => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}

function contrastRatio(first, second) {
  const values = [luminance(first), luminance(second)].sort((a, b) => b - a);
  return (values[0] + 0.05) / (values[1] + 0.05);
}

test('seven distinct themes are available and ivory sage remains the default', () => {
  assert.equal(DEFAULT_THEME, 'ivory');
  assert.deepEqual(THEMES.map(({ id }) => id), ['ivory', 'midnight', 'pearl', 'rose', 'wood', 'botanical', 'mountain']);
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

test('all themes have palette tokens and the dark theme keeps readable high-contrast copy', async () => {
  const [variants, base] = await Promise.all([
    readFile(new URL('../frontend/natbirzha/css/theme-variants.css', import.meta.url), 'utf8'),
    readFile(new URL('../frontend/natbirzha/css/luxury-theme.css', import.meta.url), 'utf8'),
  ]);
  const css = `${variants}\n${base}`;
  for (const theme of THEMES.filter(({ id }) => id !== 'ivory')) {
    assert.match(variants, new RegExp(`html\\[data-theme="${theme.id}"\\]`));
  }
  assert.match(base, /:root[\s\S]*?--lux-ink:/);
  assert.match(css, /html\[data-theme="midnight"\][\s\S]*?--lux-ink:\s*#[fF][0-9a-f]{5}/);
  assert.match(css, /html\[data-theme="midnight"\][\s\S]*?--lux-muted:\s*#[a-fA-F0-9]{6}/);
  assert.match(variants, /html\[data-theme="midnight"\] #screen-container \[class\*="text-black"\]/);
  assert.match(variants, /html\[data-theme="midnight"\] #screen-container \[class\*="text-emerald-"\]/);
  assert.match(css, /html\[data-theme="rose"\][\s\S]*?--lux-emerald:/);
  assert.match(css, /html\[data-theme="wood"\][\s\S]*?--lux-champagne:/);
  assert.match(css, /html\[data-theme="botanical"\][\s\S]*?--lux-sage:/);
  assert.match(css, /html\[data-theme="mountain"\][\s\S]*?--lux-focus:/);
  for (const id of ['rose', 'wood', 'botanical', 'mountain']) {
    const block = variants.match(new RegExp(`html\\[data-theme="${id}"\\] \\{([^}]*)\\}`))?.[1] || '';
    const token = (name) => block.match(new RegExp(`${name}:\\s*(#[0-9a-f]{6})`, 'i'))?.[1];
    assert.ok(contrastRatio(token('--lux-ink'), token('--lux-surface')) >= 7, `${id} primary text is readable`);
    assert.ok(contrastRatio(token('--lux-muted'), token('--lux-surface-soft')) >= 4.5, `${id} secondary text is readable`);
    assert.ok(contrastRatio(token('--lux-champagne'), token('--lux-surface')) >= 4.5, `${id} gold accents are readable`);
  }
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
