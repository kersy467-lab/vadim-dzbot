import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { renderFactories } from '../frontend/natbirzha/js/screens/next_game_factories.js';
import { renderPartnerships } from '../frontend/natbirzha/js/screens/next_game_contracts.js';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

function factoryState() {
  return {
    company: { cash: 1000, level: 9, branch_path: ['bank_risk'] },
    corporations: [{ id: 'bank', name: 'Bank', branches: [{ id: 'bank_risk', name: 'Risk institute',
      factory: { facility_name: 'Risk institute', output_name: 'Risk services', output_quantity: 2,
        output_unit: 'contracts', cycle_seconds: 780, operating_cost: 100, inputs: { compute: 1 } } }] }],
    facilities: [{ branch_id: 'bank_risk', level: 9, status: 'blocked',
      blocked_reason: 'Need 0.25 contracts', recipe: { facility_name: 'Risk institute', output_name: 'Risk services',
        output_quantity: 2, output_unit: 'contracts', cycle_seconds: 780, operating_cost: 100,
        inputs: { compute: 1 } } }],
    market: [{ item_id: 'compute', name: 'Computing power', quantity: 0, unit: 'contracts' }],
    managers: [], settings: {},
  };
}

test('selected factory details and manager inventory remain readable on narrow screens', async () => {
  const state = factoryState();
  state.managers = [{ id: 1, name: 'Avery Brooks', rarity: 'epic', source: 'case', level: 28,
    reward_level: 46, discount_pct: 6, branch_id: null }];
  const markup = renderFactories(state);
  assert.match(markup, /Автономность/);
  assert.match(markup, /Запасов не хватает на один цикл/);
  assert.match(markup, /<details class="next-game-panel next-game-manager-panel"/);
  assert.doesNotMatch(markup, /<details class="next-game-panel next-game-manager-panel" open/);
  assert.doesNotMatch(markup, /Склад, сотрудники и транспорт/);
  assert.match(markup, /сотрудник ур\. 28/);
  assert.doesNotMatch(markup, /1 \/ 4/);

  const css = await read('../frontend/natbirzha/css/next-game-consolidation.css');
  assert.match(css, /@media\s*\(max-width:\s*40rem\)[\s\S]*?\.next-game-factory-selected \.next-game-factory-card\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/);
  assert.match(css, /\.next-game-factory-selected \.next-game-factory-details\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/);
  assert.match(css, /\.next-game-manager-summary\s*\{/);
});

test('contract tabs opt out of the icon-and-copy quick-link grid columns', async () => {
  const markup = renderPartnerships({
    companies: [], items: [], blueprints: [], active_projects: 0,
    supplies: [], projects: [], cash: 0,
  });
  assert.match(markup, /class="next-game-quick-links next-game-partnership-tabs"/);
  const css = await read('../frontend/natbirzha/css/next-game-consolidation.css');
  assert.match(css, /\.next-game-partnership-tabs\s*>\s*button\s*\{[^}]*display:\s*flex/);
  assert.match(css, /\.next-game-partnership-tabs\s*>\s*button\s*\{[^}]*overflow-wrap:\s*normal/);
});
