export function normalizeAngle(value) {
  const angle = Number(value);
  return Number.isFinite(angle) ? ((angle % 360) + 360) % 360 : 0;
}

export function advancePointer(angle, direction, speed, seconds) {
  return normalizeAngle(Number(angle) + (Number(direction) < 0 ? -1 : 1)
    * Number(speed) * Math.max(0, Number(seconds) || 0));
}

export function angleInZone(angle, center, halfWidth) {
  const distance = Math.abs(((normalizeAngle(angle) - normalizeAngle(center) + 540) % 360) - 180);
  return distance <= Number(halfWidth);
}

export function tapFeedback(pointerAngle, targetAngle, goldHalfWidth = 28, blueHalfWidth = 22) {
  if (angleInZone(pointerAngle, targetAngle, goldHalfWidth)) return 'gold';
  if (angleInZone(pointerAngle, Number(targetAngle) + 180, blueHalfWidth)) return 'blue';
  return 'miss';
}

export function createTimingGameState(serverState = {}, localNow = 0) {
  return {
    pointerAngle: normalizeAngle(serverState.pointer_angle),
    targetAngle: normalizeAngle(serverState.target_angle),
    direction: Number(serverState.direction) < 0 ? -1 : 1,
    speed: Math.max(1, Number(serverState.speed) || 132),
    goldHalfWidth: Math.max(1, Number(serverState.gold_half_width) || 28),
    blueHalfWidth: Math.max(1, Number(serverState.blue_half_width) || 22),
    charge: Math.max(0, Math.min(16, Number(serverState.charge) || 0)),
    streak: Math.max(0, Number(serverState.streak) || 0),
    multiplier: Math.max(1, Math.min(5, Number(serverState.multiplier) || 1)),
    maximumMultiplier: Math.max(1, Math.min(5, Number(serverState.maximum_multiplier) || 5)),
    syncedAt: Number(localNow) || 0,
    lastResult: null,
  };
}

export function pointerAt(state, localNow) {
  const elapsed = Math.max(0, (Number(localNow) - state.syncedAt) / 1000);
  return advancePointer(state.pointerAngle, state.direction, state.speed, elapsed);
}

export function updateTimingGameState(previous, serverState = {}, localNow = 0) {
  const next = createTimingGameState(serverState, localNow);
  next.lastResult = previous?.lastResult || null;
  return next;
}
