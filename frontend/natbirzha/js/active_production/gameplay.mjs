const SHIFT_LENGTH = 5;

const ORDER_TYPES = Object.freeze([
  { id: 'standard', label: 'Стандартный заказ', basePoints: 80, target: 0.24, tolerance: 0.31 },
  { id: 'precision', label: 'Точная партия', basePoints: 140, target: 0.72, tolerance: 0.13 },
]);

function orderOffers(scene, completedOrders) {
  const offset = ((completedOrders % 3) - 1) * 0.04;
  const cargo = scene?.visual_pickup || 'Груз';
  const workstation = scene?.workstation || 'Производственная линия';
  const delivery = scene?.delivery_marker || 'Склад';
  return ORDER_TYPES.map((order) => ({
    ...order,
    target: (order.target + offset) % 0.88,
    cargo: `${cargo} №${completedOrders + 1}`,
    workstation,
    delivery,
  }));
}

export function createProductionShift(scene, { bestScore = 0, shiftNumber = 1 } = {}) {
  const safeScene = {
    visual_pickup: scene?.visual_pickup || 'Груз',
    workstation: scene?.workstation || 'Производственная линия',
    delivery_marker: scene?.delivery_marker || 'Склад',
  };
  return {
    scene: safeScene,
    phase: 'offer',
    shiftNumber,
    offers: orderOffers(safeScene, 0),
    selectedOrderId: 'standard',
    activeOrder: null,
    completedOrders: 0,
    score: 0,
    bestScore: Math.max(0, Number(bestScore) || 0),
    combo: 0,
    quality: null,
    lastResult: null,
  };
}

export function selectProductionOrder(state, orderId) {
  if (state.phase !== 'offer' || !state.offers.some((order) => order.id === orderId)) return state;
  return { ...state, selectedOrderId: orderId };
}

export function acceptProductionOrder(state) {
  if (state.phase !== 'offer') return state;
  const selected = state.offers.find((order) => order.id === state.selectedOrderId);
  if (!selected) return state;
  return { ...state, phase: 'pickup', activeOrder: { ...selected, orderNumber: state.completedOrders + 1 } };
}

export function collectProductionCargo(state) {
  return state.phase === 'pickup' ? { ...state, phase: 'work' } : state;
}

export function startProductionLine(state) {
  return state.phase === 'work' ? { ...state, phase: 'calibrate' } : state;
}

function calibrationGrade(order, position) {
  const distance = Math.abs(((Number(position) - order.target + 1.5) % 1) - 0.5);
  if (distance <= order.tolerance * 0.4) return 2;
  if (distance <= order.tolerance) return 1;
  return 0;
}

export function finishProductionCalibration(state, position) {
  if (state.phase !== 'calibrate' || !state.activeOrder) return state;
  return { ...state, phase: 'deliver', quality: calibrationGrade(state.activeOrder, position) };
}

export function deliverProductionOrder(state) {
  if (state.phase !== 'deliver' || !state.activeOrder) return state;
  const quality = state.quality || 0;
  const combo = quality > 0 ? state.combo + 1 : 0;
  const qualityPoints = quality === 2 ? 60 : quality === 1 ? 25 : 0;
  const comboPoints = quality > 0 ? Math.min(combo, 4) * 10 : 0;
  const points = state.activeOrder.basePoints + qualityPoints + comboPoints;
  const score = state.score + points;
  const completedOrders = state.completedOrders + 1;
  const complete = completedOrders >= SHIFT_LENGTH;
  const lastResult = { points, quality, combo, order: state.activeOrder.label };
  return {
    ...state,
    phase: complete ? 'complete' : 'offer',
    offers: complete ? [] : orderOffers(state.scene, completedOrders),
    selectedOrderId: 'standard',
    activeOrder: null,
    completedOrders,
    score,
    bestScore: Math.max(state.bestScore, score),
    combo,
    quality: null,
    lastResult,
  };
}

export function startNextProductionShift(state) {
  if (state.phase !== 'complete') return state;
  return createProductionShift(state.scene, {
    bestScore: Math.max(state.bestScore, state.score),
    shiftNumber: state.shiftNumber + 1,
  });
}
