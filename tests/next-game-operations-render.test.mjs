import assert from 'node:assert/strict';
import test from 'node:test';
import { renderOperations } from '../frontend/natbirzha/js/screens/next_game_operations.js';

const quote = { cash: 25000, inputs: { steel: 5 } };
const data = {
  cash: 50000, policy: 'Расходы только за рабочие циклы',
  items: [{ id: 'steel', name: 'Сталь' }, { id: 'energy', name: 'Энергия' }],
  capacity: { used_slots: 1, production_slots: 12, warehouse_capacity: 100000,
    land_level: 0, warehouse_level: 0, land_quote: quote, warehouse_quote: quote },
  facilities: [{ id: 1, name: '<script>завод</script>', level: 5,
    employees: [], vehicles: [], available_employees: [], available_vehicles: [],
    automation_level: 0, automation_quote: quote, license_quote: { ...quote, days: 7 },
    staff_slots: 3, fleet_slots: 2, license_active: false,
    recipe: { inputs: { steel: 5 }, output_quantity: 10, output_item: 'energy', operating_cost: 100,
      operations: { staff_bonus_pct: 0, fleet_bonus_pct: 0, input_saving_pct: 0 } } }],
};

test('management uses collapsed sections, exact resource quotes and safe factory names', () => {
  const markup = renderOperations(data);
  assert.match(markup, /data-operations-factory="1"/);
  assert.match(markup, /&lt;script&gt;завод&lt;\/script&gt;/);
  assert.doesNotMatch(markup, /<script>/);
  assert.doesNotMatch(markup, /<details[^>]*\bopen\b/);
  assert.match(markup, /5 Сталь/);
  assert.match(markup, /data-operations-action="WAREHOUSE"/);
  assert.match(markup, /Сырьё и длительность цикла сохраняются/);
});

test('capped capacity and automation disable their commands', () => {
  const markup = renderOperations({ ...data,
    capacity: { ...data.capacity, land_quote: null, warehouse_quote: null },
    facilities: [{ ...data.facilities[0], automation_level: 5, automation_quote: null }] });
  for (const action of ['LAND', 'WAREHOUSE', 'AUTOMATION']) {
    assert.match(markup, new RegExp(`data-operations-action="${action}"[^>]*disabled`));
  }
});
