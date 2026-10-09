import test from 'node:test';
import assert from 'node:assert/strict';
import { getItemIconName, getItemInfo } from '../../frontend/natbirzha/js/items.js';

test('resource metadata exposes stable icon names for common market groups', () => {
  assert.equal(getItemInfo('ai_compute').icon, 'item:ai_compute');
  assert.equal(getItemInfo('clean_water').icon, 'item:clean_water');
  assert.equal(getItemInfo('beer').icon, 'item:beer');
  assert.equal(getItemInfo('iron_ore').icon, 'item:iron_ore');
  assert.equal(getItemIconName('chips'), 'item:electronics');
  assert.equal(getItemInfo('not_a_real_item').icon, 'resource');
  assert.equal(getItemInfo(null).icon, 'resource');
});
