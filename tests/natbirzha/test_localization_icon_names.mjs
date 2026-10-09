import test from 'node:test';
import assert from 'node:assert/strict';
import { ICON_NAMES } from '../../frontend/natbirzha/js/icons.mjs';
import { getBuildingIcon, getBuildingName, getSpecializationIcon } from '../../frontend/natbirzha/js/localization.js';

test('each game industry has a stable icon name, including legacy AI profiles', () => {
  const industries = [
    'agrarian', 'miner', 'metallurgist', 'oilman', 'power_engineer', 'ai_data',
    'forester', 'chemist', 'technoprom', 'water', 'construction', 'logistics', 'brewery',
  ];
  for (const industry of industries) assert.ok(ICON_NAMES.includes(getSpecializationIcon(industry)));
  assert.equal(getSpecializationIcon('ai_data'), 'ai');
  assert.equal(getSpecializationIcon('forester'), 'ai');
});

test('building labels are plain text and factory families resolve to drawn icons', () => {
  assert.equal(getBuildingIcon('solar_plant'), 'energy');
  assert.equal(getBuildingIcon('ml_training_center'), 'ai');
  assert.equal(getBuildingIcon('unknown_factory'), 'factory');
  assert.doesNotMatch(getBuildingName('solar_plant'), /^\p{Extended_Pictographic}/u);
});
