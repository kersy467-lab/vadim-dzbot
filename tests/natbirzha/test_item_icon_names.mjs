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

test('new NATBIRZHA 2.0 services keep item identity for colored market artwork', () => {
  for (const itemId of [
    'payment_services', 'credit_services', 'investment_services', 'district_heat',
    'reactor_fuel', 'storage_capacity', 'green_hydrogen', 'grid_services',
    'plasma_services', 'hydrogen_services', 'polymer_fiber', 'medical_polymer',
    'carbon_material', 'diagnostics', 'battery_pack', 'habitat_module',
    'cold_capacity', 'rail_capacity', 'port_capacity', 'air_capacity',
    'warehouse_services', 'urban_services', 'life_support', 'orbital_logistics',
    'vision_system', 'security_services', 'model_services', 'engineering_services',
    'quantum_services', 'insurance_services', 'leasing_services', 'settlement_services',
    'risk_services', 'custody_services',
  ]) {
    assert.equal(getItemInfo(itemId).icon, `item:${itemId}`, itemId);
  }
});

test('new energy and financial services have distinct semantic colors and artwork', () => {
  const gradient = (id) => renderResourceIcon(id).match(/<stop stop-color="([^"]+)"\/>/)?.[1];
  const payment = renderResourceIcon('payment_services');
  const heat = renderResourceIcon('district_heat');
  const plasma = renderResourceIcon('plasma_services');

  assert.notEqual(gradient('payment_services'), gradient('not_a_real_item'));
  assert.notEqual(gradient('district_heat'), gradient('payment_services'));
  assert.notEqual(gradient('plasma_services'), gradient('district_heat'));
  assert.match(payment, /data-item="payment_services"/);
  assert.match(heat, /data-item="district_heat"/);
  assert.match(plasma, /data-item="plasma_services"/);
  assert.doesNotMatch(payment, /M4 8 12 4 20 8v10/);
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
