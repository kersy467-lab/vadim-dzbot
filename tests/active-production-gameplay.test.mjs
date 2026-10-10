import test from 'node:test';
import assert from 'node:assert/strict';
import * as productionGameplay from '../frontend/natbirzha/js/active_production/gameplay.mjs';
import {
  acceptProductionOrder,
  collectProductionCargo,
  createProductionShift,
  deliverProductionOrder,
  finishProductionCalibration,
  selectProductionOrder,
  startNextProductionShift,
  startProductionLine,
} from '../frontend/natbirzha/js/active_production/gameplay.mjs';

const scene = {
  visual_pickup: 'Медная заготовка',
  workstation: 'Прокатный стан',
  delivery_marker: 'Склад готовой продукции',
};

test('the chosen contract preference survives sessions and is scoped to a facility', () => {
  const values = new Map();
  const storage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
  };

  assert.equal(typeof productionGameplay.saveProductionOrderPreference, 'function');
  assert.equal(typeof productionGameplay.loadProductionOrderPreference, 'function');
  productionGameplay.saveProductionOrderPreference(storage, 'branch-1', 'precision');

  assert.equal(productionGameplay.loadProductionOrderPreference(storage, 'branch-1'), 'precision');
  assert.equal(productionGameplay.loadProductionOrderPreference(storage, 'branch-2'), 'standard');
  values.set('natbirzha:active-order-choice:branch-1', 'invalid');
  assert.equal(productionGameplay.loadProductionOrderPreference(storage, 'branch-1'), 'standard');
});

test('a saved contract choice is used for the next order and next shift', () => {
  let shift = createProductionShift(scene, { selectedOrderId: 'precision' });
  assert.equal(shift.selectedOrderId, 'precision');

  for (let index = 0; index < 5; index += 1) {
    shift = acceptProductionOrder(shift);
    shift = collectProductionCargo(shift);
    shift = startProductionLine(shift);
    shift = finishProductionCalibration(shift, shift.activeOrder.target);
    shift = deliverProductionOrder(shift);
    if (shift.phase === 'offer') assert.equal(shift.selectedOrderId, 'precision');
  }

  shift = startNextProductionShift(shift);
  assert.equal(shift.selectedOrderId, 'precision');
});

test('the shift offers a safe route and a higher-scoring precision order', () => {
  let shift = createProductionShift(scene);
  assert.equal(shift.phase, 'offer');
  assert.deepEqual(shift.offers.map(({ id }) => id), ['standard', 'precision']);

  shift = selectProductionOrder(shift, 'precision');
  shift = acceptProductionOrder(shift);

  assert.equal(shift.phase, 'pickup');
  assert.equal(shift.activeOrder.id, 'precision');
  assert.equal(shift.activeOrder.cargo, 'Медная заготовка №1');
  assert.equal(shift.activeOrder.workstation, 'Прокатный стан');
});

test('an order needs pickup, line operation, calibration and delivery before scoring', () => {
  let shift = acceptProductionOrder(createProductionShift(scene));
  assert.equal(shift.phase, 'pickup');
  assert.equal(deliverProductionOrder(shift), shift);

  shift = collectProductionCargo(shift);
  assert.equal(shift.phase, 'work');
  shift = startProductionLine(shift);
  assert.equal(shift.phase, 'calibrate');
  assert.equal(shift.score, 0);

  shift = finishProductionCalibration(shift, shift.activeOrder.target);
  assert.equal(shift.phase, 'deliver');
  assert.equal(shift.quality, 2);
  assert.equal(shift.score, 0);
  const basePoints = shift.activeOrder.basePoints;

  shift = deliverProductionOrder(shift);
  assert.equal(shift.phase, 'offer');
  assert.equal(shift.completedOrders, 1);
  assert.ok(shift.lastResult.points > basePoints);
  assert.equal(shift.combo, 1);
});

test('a missed calibration still completes the order without blocking or losing points', () => {
  let shift = createProductionShift(scene);
  shift = selectProductionOrder(shift, 'precision');
  shift = acceptProductionOrder(shift);
  shift = collectProductionCargo(shift);
  shift = startProductionLine(shift);
  shift = finishProductionCalibration(shift, 0.02);
  assert.equal(shift.phase, 'deliver');
  assert.equal(shift.quality, 0);

  shift = deliverProductionOrder(shift);
  assert.equal(shift.completedOrders, 1);
  assert.equal(shift.combo, 0);
  assert.equal(shift.score, 140);
});

test('five orders close a shift and the next shift preserves the local record', () => {
  let shift = createProductionShift(scene);
  for (let index = 0; index < 5; index += 1) {
    shift = acceptProductionOrder(shift);
    shift = collectProductionCargo(shift);
    shift = startProductionLine(shift);
    shift = finishProductionCalibration(shift, shift.activeOrder.target);
    shift = deliverProductionOrder(shift);
  }

  assert.equal(shift.phase, 'complete');
  assert.equal(shift.completedOrders, 5);
  const record = shift.score;
  shift = startNextProductionShift(shift);
  assert.equal(shift.phase, 'offer');
  assert.equal(shift.completedOrders, 0);
  assert.equal(shift.score, 0);
  assert.equal(shift.bestScore, record);
});
