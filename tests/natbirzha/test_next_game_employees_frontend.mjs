import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { renderEmployeeInventory } from '../../frontend/natbirzha/js/screens/next_game_employees.js';

const data = {
  pvc_balance: 80,
  case: {
    price_pvc: 25,
    odds: [
      { rarity: 'common', probability: .70, level_min: 1, level_max: 10, discount_pct: 2 },
      { rarity: 'rare', probability: .22, level_min: 11, level_max: 20, discount_pct: 4 },
      { rarity: 'epic', probability: .07, level_min: 21, level_max: 30, discount_pct: 6 },
      { rarity: 'legendary', probability: .01, level_min: 31, level_max: 50, discount_pct: 8 },
    ],
  },
  employees: [
    { id: 1, name: 'Amelia Brooks', source: 'milestone', level: 5, reward_level: 5,
      rarity: 'common', discount_pct: 2, facility_id: null },
    { id: 9, name: 'Riley Morgan', source: 'case', level: 28, reward_level: 46,
      rarity: 'epic', discount_pct: 6, facility_id: null },
    { id: 10, name: 'Jordan Hayes', source: 'case', level: 18, reward_level: 47,
      rarity: 'rare', discount_pct: 4, facility_id: 2, branch_id: 'thermal' },
  ],
};

const html = renderEmployeeInventory(data);
assert.match(html, /Сотрудники/);
assert.match(html, /Открыть за 25 PVC/);
assert.match(html, /70%/);
assert.match(html, /22%/);
assert.match(html, /7%/);
assert.match(html, /1%/);
assert.match(html, /уровни 31–50/);
assert.match(html, /к расходам cash за цикл/);
assert.match(html, /Amelia Brooks/);
assert.match(html, /Riley Morgan/);
assert.match(html, /data-employee-delete="9"/);
assert.doesNotMatch(html, /data-employee-delete="10"/);
assert.match(html, /Назначен: thermal/);

const screenSource = await readFile(new URL('../../frontend/natbirzha/js/screens/next_game_employees.js', import.meta.url), 'utf8');
const css = await readFile(new URL('../../frontend/natbirzha/css/next-game-employees.css', import.meta.url), 'utf8');
assert.match(screenSource, /waitForCaseAnimation/);
assert.match(screenSource, /openNextGameEmployeeCase/);
assert.match(html, /ng-employee-case-lid/);
assert.doesNotMatch(screenSource, /Назначен: \$\{esc\(employee\.branch_id\)\}/);
assert.match(css, /@keyframes ng-case-rattle/);
assert.match(css, /@keyframes ng-case-flare/);
assert.match(css, /@keyframes ng-case-lid-open/);
assert.match(css, /prefers-reduced-motion/);
console.log('Next Game employee screen and case animation contract passed.');
