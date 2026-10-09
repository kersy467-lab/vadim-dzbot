import test from 'node:test';
import assert from 'node:assert/strict';
import { readdir, readFile } from 'node:fs/promises';
import { ICON_NAMES, renderIcon, splitLegacyIcons } from '../frontend/natbirzha/js/icons.mjs';
import { ITEMS, getItemInfo } from '../frontend/natbirzha/js/items.js';

const requiredIcons = [
  'overview', 'factory', 'upgrade', 'market', 'military', 'leaderboard', 'state',
  'energy', 'water', 'mining', 'agriculture', 'oil', 'metallurgy', 'construction',
  'chemistry', 'technology', 'ai', 'logistics', 'brewing', 'money', 'stock',
  'shield', 'warning', 'lock', 'arrow-left', 'resource',
];

test('the interface icon registry covers navigation, industries, resources and actions', () => {
  for (const name of requiredIcons) {
    assert.ok(ICON_NAMES.includes(name), `missing icon registration: ${name}`);
    assert.match(renderIcon(name), /^<svg\b/);
    assert.match(renderIcon(name), /<path\b/);
  }
});

test('unknown names fall back to a safe decorative resource icon', () => {
  const markup = renderIcon('not-a-real-icon');
  assert.match(markup, /aria-hidden="true"/);
  assert.match(markup, /<svg\b/);
  assert.doesNotMatch(markup, /not-a-real-icon/);
  assert.equal(renderIcon('toString'), renderIcon('resource'));
  assert.equal(renderIcon('⚡'), renderIcon('energy'));
});

test('every catalog item renders as its own colorful drawn resource illustration', () => {
  for (const [itemId] of Object.entries(ITEMS)) {
    const item = getItemInfo(itemId);
    const markup = renderIcon(item.icon, { size: 22, label: item.name });
    assert.match(markup, new RegExp(`data-item="${itemId}"`), `missing item art: ${itemId}`);
    assert.match(markup, /<linearGradient\b/);
    assert.match(markup, /fill="#[0-9a-f]{6}"/i);
    assert.doesNotMatch(markup, /stroke="currentColor"/);
  }
});

test('resource illustration module is cache-busted in Telegram webviews', async () => {
  const appModule = await readFile(new URL('../frontend/natbirzha/js/app.js', import.meta.url), 'utf8');
  const iconModule = await readFile(new URL('../frontend/natbirzha/js/icons.mjs', import.meta.url), 'utf8');
  assert.match(appModule, /icons\.mjs\?v=20261009_item_art_v2/);
  assert.match(iconModule, /from '\.\/resource_icons\.mjs\?v=20261009_item_art_v2'/);
});

test('item-art cache version reaches every screen module that renders resource icons', async () => {
  const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');
  const [app, loader, overview, market, tycoon, military, creator, production] = await Promise.all([
    read('../frontend/natbirzha/js/app.js'),
    read('../frontend/natbirzha/js/screen_loader.js'),
    read('../frontend/natbirzha/js/screens/overview.js'),
    read('../frontend/natbirzha/js/screens/market.js'),
    read('../frontend/natbirzha/js/screens/tycoon.js'),
    read('../frontend/natbirzha/js/screens/military.js'),
    read('../frontend/natbirzha/js/screens/creator.js'),
    read('../frontend/natbirzha/js/screens/production.js'),
  ]);
  assert.match(app, /screen_loader\.js\?v=20261009_item_art_v2/);
  assert.match(loader, /screens\/overview\.js\?v=20261009_item_art_v2/);
  assert.match(loader, /screens\/market\.js\?v=20261009_item_art_v2/);
  assert.match(loader, /screens\/tycoon\.js\?v=20261009_item_art_v2/);
  assert.match(loader, /screens\/military\.js\?v=20261009_item_art_v2/);
  assert.match(market, /market_commodities\.js\?v=20261009_item_art_v2/);
  assert.match(overview, /company_aid_panel\.js\?v=20261009_item_art_v2/);
  assert.match(tycoon, /tycoon_production_status\.js\?v=20261009_item_art_v2/);
  assert.match(military, /military_hospital\.js\?v=20261009_item_art_v2/);
  assert.match(creator, /creator_moderation\.js\?v=20261009_item_art_v2/);
  assert.match(production, /catalog\.js\?v=20261009_item_art_v2/);
});

test('labels and classes are escaped and decorative icons are hidden from assistive tech', () => {
  const decorative = renderIcon('market');
  assert.match(decorative, /aria-hidden="true"/);

  const labeled = renderIcon('market', {
    size: 24,
    className: 'nav-icon" onload="alert(1)',
    label: '<Биржа> & акции',
  });
  assert.match(labeled, /role="img" aria-label="&lt;Биржа&gt; &amp; акции"/);
  assert.match(labeled, /class="nav-icon&quot; onload=&quot;alert\(1\)"/);
  assert.match(labeled, /<title>&lt;Биржа&gt; &amp; акции<\/title>/);
  assert.match(labeled, /width="24" height="24"/);
});

test('icon size is bounded to keep generated inline SVG predictable', () => {
  assert.match(renderIcon('factory', { size: -10 }), /width="1" height="1"/);
  assert.match(renderIcon('factory', { size: 1000 }), /width="96" height="96"/);
});

test('legacy interface emoji split into consistent SVG aliases without changing unknown text', () => {
  assert.deepEqual(splitLegacyIcons('⚡ Энергия 🏦'), [
    { text: '', icon: 'energy' },
    { text: ' Энергия ', icon: null },
    { text: '', icon: 'money' },
  ]);
  assert.deepEqual(splitLegacyIcons('⚠️ Ошибка'), [
    { text: '', icon: 'warning' },
    { text: ' Ошибка', icon: null },
  ]);
  assert.deepEqual(splitLegacyIcons('🧑‍💻'), [{ text: '🧑‍💻', icon: null }]);
});

test('every existing screen glyph has a drawn icon alias', async () => {
  const directory = new URL('../frontend/natbirzha/js/screens/', import.meta.url);
  const files = (await readdir(directory)).filter((name) => name.endsWith('.js'));
  const pictograph = /\p{Extended_Pictographic}/u;
  const sources = await Promise.all([
    ...files.map((file) => readFile(new URL(file, directory), 'utf8')),
    readFile(new URL('../frontend/natbirzha/js/app.js', import.meta.url), 'utf8'),
    readFile(new URL('../frontend/natbirzha/js/items.js', import.meta.url), 'utf8'),
    readFile(new URL('../frontend/natbirzha/js/localization.js', import.meta.url), 'utf8'),
  ]);
  for (const [index, source] of sources.entries()) {
    const unmapped = splitLegacyIcons(source).flatMap((part) => Array.from(part.text).filter((char) => pictograph.test(char)));
    assert.deepEqual(unmapped, [], `UI source ${index} contains an emoji that would remain unstyled`);
  }
});

test('the app shell uses the luxury theme and keeps its six navigation contracts', async () => {
  const html = await readFile(new URL('../frontend/natbirzha/index.html', import.meta.url), 'utf8');
  const app = await readFile(new URL('../frontend/natbirzha/js/app.js', import.meta.url), 'utf8');
  const iconModule = await readFile(new URL('../frontend/natbirzha/js/icons.mjs', import.meta.url), 'utf8');
  const tycoonCss = await readFile(new URL('../frontend/natbirzha/css/tycoon.css', import.meta.url), 'utf8');
  const luxuryTheme = await readFile(new URL('../frontend/natbirzha/css/luxury-theme.css', import.meta.url), 'utf8');
  const stocksScreen = await readFile(new URL('../frontend/natbirzha/js/screens/stocks.js', import.meta.url), 'utf8');
  const creatorScreen = await readFile(new URL('../frontend/natbirzha/js/screens/creator.js', import.meta.url), 'utf8');
  assert.match(html, /<html lang="ru">/);
  assert.match(html, /luxury-theme\.css/);
  assert.doesNotMatch(html, /princess-theme\.css|princess-sky/);
  assert.doesNotMatch(html, /user-scalable=no/);
  const tabs = [...html.matchAll(/data-tab="(overview|production|upgrades|market|military|leaderboard)"/g)];
  assert.deepEqual(tabs.map((match) => match[1]), [
    'overview', 'production', 'upgrades', 'market', 'military', 'leaderboard',
  ]);
  assert.match(html, /data-icon="overview"/);
  assert.match(html, /data-icon="factory"/);
  assert.doesNotMatch(tycoonCss, /princess|#ec4899|#8b5cf6|#db2777/i,
    'the specialty screen stylesheet must use the approved ivory and sage palette');
  assert.doesNotMatch(luxuryTheme, /button\[class\*="bg-blue-"\]/,
    'light blue cards and selections must not inherit the emerald CTA treatment');
  assert.match(luxuryTheme, /\.spec-btn-selected/);
  const onboarding = await readFile(new URL('../frontend/natbirzha/js/screens/onboarding.js', import.meta.url), 'utf8');
  assert.match(onboarding, /aria-pressed=/);
  assert.match(onboarding, /NatIcons\.icon\('star'/);
  assert.doesNotMatch(onboarding, /'★'|'☆'/,
    'difficulty markers must use the drawn icon set instead of text stars');
  assert.match(stocksScreen, /escapeHtml\(s\.company_name\)/,
    'stock issuer names must be escaped before being inserted into HTML');
  assert.doesNotMatch(stocksScreen, /\$\{s\.company_name\}/,
    'stock issuer names must never be interpolated into HTML raw');
  assert.match(creatorScreen, /escapeHtml\(b\.title\)/);
  assert.match(creatorScreen, /escapeHtml\(b\.purpose\)/,
    'issuer supplied bond text must be escaped in the creator panel');
  assert.match(app, /from '\.\/icons\.mjs/);
  assert.match(app, /installIconHydration\(\)/);
  assert.match(iconModule, /target\.NatIcons/);
  assert.match(iconModule, /MutationObserver/);
  assert.match(iconModule, /data-preserve-emoji/);
  assert.match(app, /\.textContent = msgText/,
    'toast messages must be inserted as text to prevent server messages from becoming executable HTML');
  assert.doesNotMatch(app, /<span>\$\{msgText\}<\/span>/,
    'toast messages must not be interpolated as raw HTML');
});
