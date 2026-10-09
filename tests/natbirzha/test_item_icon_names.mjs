import test from 'node:test';
import assert from 'node:assert/strict';
import { getItemIconName, getItemInfo } from '../../frontend/natbirzha/js/items.js';

test('resource metadata exposes stable icon names for common market groups', () => {
  assert.equal(getItemInfo('ai_compute').icon, 'ai');
  assert.equal(getItemInfo('clean_water').icon, 'water');
  assert.equal(getItemInfo('beer').icon, 'brewing');
  assert.equal(getItemInfo('iron_ore').icon, 'mining');
  assert.equal(getItemIconName('chips'), 'technology');
  assert.equal(getItemInfo('not_a_real_item').icon, 'resource');
  assert.equal(getItemInfo(null).icon, 'resource');
});
