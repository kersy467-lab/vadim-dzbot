const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const assert = require('node:assert/strict');

const root = path.resolve(__dirname, '../..');
const creatorPath = path.join(root, 'frontend/natbirzha/js/screens/creator.js');
const themePaths = [
  path.join(root, 'frontend/natbirzha/css/luxury-theme.css'),
  path.join(root, 'frontend/natbirzha/css/creator-theme.css'),
];
const creator = fs.readFileSync(creatorPath, 'utf8');
const theme = themePaths.map((themePath) => fs.readFileSync(themePath, 'utf8')).join('\n');

function luminance(color) {
  const channels = color.match(/[0-9a-f]{2}/gi).map((pair) => parseInt(pair, 16) / 255);
  const linear = channels.map((value) => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}

function contrastRatio(first, second) {
  const values = [luminance(first), luminance(second)].sort((a, b) => b - a);
  return (values[0] + 0.05) / (values[1] + 0.05);
}

test('creator panel has a dedicated scope and identifies the active tab', () => {
  assert.match(creator, /class="creator-screen\b/);
  assert.match(creator, /creator-tab-btn[^\n]*aria-pressed=/);
});

test('creator body and secondary text use readable ivory-theme colors', () => {
  assert.match(theme, /#screen-container\s+\.creator-screen\s+\[class\*="text-slate-100"\][\s\S]*?color:\s*var\(--lux-ink\)\s*!important/);
  assert.match(theme, /#screen-container\s+\.creator-screen\s+\[class\*="text-slate-500"\][\s\S]*?color:\s*var\(--creator-muted\)\s*!important/);
  assert.match(theme, /#screen-container\s+\.creator-screen\s+\[class\*="text-orange-"\]/);
  assert.match(theme, /#screen-container\s+\.creator-screen\s+\[class\*="text-sky-"\]/);
  assert.match(theme, /#screen-container\s+\.creator-screen\s+\[class\*="text-blue-"\]/);
  assert.match(theme, /#screen-container\s+\.creator-screen\s+\[class\*="text-violet-"\]/);

  const sage = theme.match(/--lux-sage:\s*(#[0-9a-f]{6})/i)?.[1];
  const surface = theme.match(/--lux-surface:\s*(#[0-9a-f]{6})/i)?.[1];
  const ink = theme.match(/--lux-ink:\s*(#[0-9a-f]{6})/i)?.[1];
  const muted = theme.match(/--creator-muted:\s*(#[0-9a-f]{6})/i)?.[1];
  const border = theme.match(/--creator-border:\s*(#[0-9a-f]{6})/i)?.[1];
  assert.ok(contrastRatio(ink, sage) >= 4.5, 'primary body text meets 4.5:1 contrast on creator surfaces');
  assert.ok(contrastRatio(muted, sage) >= 4.5, 'secondary text meets 4.5:1 contrast on creator surfaces');
  assert.ok(contrastRatio(border, surface) >= 2, 'creator card borders remain visible on ivory cards');
  assert.ok(contrastRatio('#9c3535', '#f8e9e6') >= 4.5, 'status copy stays readable on pale red surfaces');
  assert.ok(contrastRatio('#854c18', '#f6eddc') >= 4.5, 'warning copy stays readable on pale amber surfaces');
  assert.ok(contrastRatio('#28647b', '#fffefa') >= 4.5, 'blue status copy stays readable on ivory surfaces');
  assert.ok(contrastRatio('#57438b', '#fffefa') >= 4.5, 'violet status copy stays readable on ivory surfaces');
});

test('creator borders and primary, secondary, and active-tab controls have explicit contrast', () => {
  assert.match(theme, /#screen-container\s+\.creator-screen\s+\[class\*="border-"\][\s\S]*?border-color:\s*var\(--creator-border\)\s*!important/);
  const secondaryButtonRule = theme.match(/#screen-container\s+\.creator-screen\s+button\s*\{([^}]*)\}/)?.[1] || '';
  assert.match(secondaryButtonRule, /background:\s*var\(--lux-sage\)\s*!important/);
  assert.match(secondaryButtonRule, /color:\s*var\(--lux-ink\)\s*!important/);
  assert.match(secondaryButtonRule, /border:\s*1px solid var\(--creator-border\)\s*!important/);
  const primaryButtonRule = theme.match(/#screen-container\s+\.creator-screen\s+button\[class\*="bg-blue-"\][\s\S]*?\{([^}]*)\}/)?.[1] || '';
  assert.match(primaryButtonRule, /background:\s*var\(--lux-emerald\)\s*!important/);
  assert.match(primaryButtonRule, /color:\s*#fffefa\s*!important/);
  assert.ok(contrastRatio('#fffefa', '#17664f') >= 4.5, 'primary buttons have readable light-on-emerald text');
  assert.ok(contrastRatio('#493611', '#e9c26d') >= 4.5, 'amber actions have readable dark-on-gold text');
  const activeTabRule = theme.match(/#screen-container\s+\.creator-screen\s+\.creator-tab-btn\[aria-pressed="true"\]\s*\{([^}]*)\}/)?.[1] || '';
  assert.match(activeTabRule, /background:\s*var\(--lux-emerald\)\s*!important/);
  assert.match(activeTabRule, /color:\s*#fffefa\s*!important/);
});
