import test from 'node:test';
import assert from 'node:assert/strict';
import {
  angleInZone,
  advancePointer,
  createTimingGameState,
  pointerAt,
  tapFeedback,
} from '../frontend/natbirzha/js/active_production/gameplay.mjs';

test('pointer motion wraps and respects the server-selected direction', () => {
  assert.equal(advancePointer(350, 1, 120, 0.25), 20);
  assert.equal(advancePointer(10, -1, 120, 0.25), 340);
  assert.equal(advancePointer(50, 1, 120, -5), 50);
});

test('timing zones wrap around zero and keep gold and blue targets distinct', () => {
  assert.equal(angleInZone(2, 355, 8), true);
  assert.equal(angleInZone(20, 355, 8), false);
  assert.equal(tapFeedback(5, 355), 'gold');
  assert.equal(tapFeedback(175, 355), 'blue');
  assert.equal(tapFeedback(100, 355), 'miss');
});

test('timing state synchronizes server time and exposes no client-authored multiplier', () => {
  const state = createTimingGameState({
    pointer_angle: 350, target_angle: 355, direction: 1, speed: 120,
    charge: 8, streak: 4, multiplier: 3, server_now: '2026-10-11T12:00:00.000',
  }, 1000);

  assert.equal(pointerAt(state, 1250), 20);
  assert.equal(state.charge, 8);
  assert.equal(state.streak, 4);
  assert.equal(state.multiplier, 3);
});
