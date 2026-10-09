import test from 'node:test';
import assert from 'node:assert/strict';
import { getItemIconName, getItemInfo } from '../../frontend/natbirzha/js/items.js';
import { renderResourceIcon } from '../../frontend/natbirzha/js/resource_icons.mjs';

test('resource metadata exposes stable icon names for common market groups', () => {
  assert.equal(getItemInfo('ai_compute').icon, 'item:ai_compute');
  assert.equal(getItemInfo('clean_water').icon, 'item:clean_water');
  assert.equal(getItemInfo('beer').icon, 'item:beer');
  assert.equal(getItemInfo('iron_ore').icon, 'item:iron_ore');
  assert.equal(getItemIconName('chips'), 'item:electronics');
  assert.equal(getItemInfo('not_a_real_item').icon, 'resource');
  assert.equal(getItemInfo(null).icon, 'resource');
});

test('resource art uses stable semantic colors for energy, water, crude oil, diesel, and beer', () => {
  const firstGradientStop = (itemId) =>
    renderResourceIcon(itemId).match(/<stop stop-color="([^"]+)"\/>/)?.[1];

  assert.equal(firstGradientStop('energy'), '#f2c14e');
  assert.equal(firstGradientStop('grid_quota'), '#f2c14e');
  assert.equal(firstGradientStop('water'), '#2496c8');
  assert.equal(firstGradientStop('oil_crude'), '#737d7e');
  assert.equal(firstGradientStop('fuel_diesel'), '#d89a22');
  assert.equal(firstGradientStop('beer'), '#e0a91f');
  assert.equal(firstGradientStop('not_a_real_item'), firstGradientStop('some_other_unknown'));
});

test('crude oil, diesel, and beer use recognizable barrel, fuel-can, and mug artwork', () => {
  const crude = renderResourceIcon('oil_crude');
  const diesel = renderResourceIcon('fuel_diesel');
  const beer = renderResourceIcon('beer');

  assert.match(crude, /fill="#202629"/);
  assert.match(crude, /M7\.3 5\.4h9\.4l1\.2 13/);
  assert.match(diesel, /M7 9h10l1 11H6L7 9z/);
  assert.match(diesel, /M9 8V6a3 3 0 0 1 6 0v2/);
  assert.match(beer, /M6 8h11v12H6z/);
  assert.match(beer, /M17 10h2a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2/);
});
