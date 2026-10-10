import { sceneForBranch } from './scene_registry.mjs';
import { paint, stationPoints } from './render.mjs?v=20261010_shift_render_v1';
import {
  acceptProductionOrder,
  collectProductionCargo,
  createProductionShift,
  deliverProductionOrder,
  finishProductionCalibration,
  selectProductionOrder,
  startNextProductionShift,
  startProductionLine,
} from './gameplay.mjs?v=20261010_shift_gameplay_v1';

const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[character]));

export function renderActiveProductionScene(company, activeSession) {
  const picked = activeSession.facilities?.find((row) => row.branch_id === activeSession.selected_branch_id);
  const scene = sceneForBranch(activeSession.selected_branch_id, picked?.sector_id, picked?.scene);
  return `<section class="next-active-production" data-active-scene data-family="${escapeHtml(scene?.scene_family || 'resources')}" tabindex="0">
    <header class="active-production-header"><div><span>АКТИВНОЕ ПРОИЗВОДСТВО</span><h1>${escapeHtml(company?.name || 'Компания')} · ${escapeHtml(picked?.name || scene?.branch_name || 'Завод')}</h1></div><button type="button" data-active-exit aria-label="Закрыть сцену">×</button></header>
    <div class="active-production-summary"><b data-active-mode>Сессия активна · до ×1,50</b><span data-active-output>Проверяем состояние заводов…</span><span data-active-cycle>Загружаем ближайший производственный цикл…</span><small data-active-hint>Игровые действия только для экрана — доход считает сервер по производственным циклам.</small></div>
    <div class="active-production-canvas-wrap"><canvas data-active-canvas aria-label="2D-сцена активного производства"></canvas><div class="active-production-objective" data-active-objective></div></div>
    <div class="active-production-footer"><p data-active-task>Выбери заказ, забери груз, запусти линию и отвези готовую партию.</p><div class="active-production-game"><div class="active-production-game-stats"><b data-active-runs>Заказы: 0/5</b><span data-active-score>Очки: 0</span><span data-active-combo>Серия: 0</span><span data-active-best>Рекорд: 0</span></div><label class="active-production-order-select">Контракт на смену<select data-active-order-select aria-label="Выбор производственного заказа"></select></label><p data-active-order-details></p><div class="active-production-calibration" data-active-calibration hidden><div class="active-production-calibration-track"><i data-active-calibration-zone></i><b data-active-calibration-needle></b></div><small data-active-quality-status>Нажми, когда метка будет в зелёной зоне. Ошибки не отменяют заказ.</small></div></div><div class="active-production-controls"><div class="active-production-joystick" data-active-joystick role="application" aria-label="Виртуальный джойстик"><span></span></div><div class="active-production-actions"><b data-active-server-activity>Активная смена</b><small>Очки влияют только на личный рекорд</small><button type="button" data-active-action>Принять заказ</button><button type="button" data-active-resume hidden>Продолжить</button><button type="button" data-active-exit>Выйти</button></div></div></div>
  </section>`;
}

const clamp = (value, low, high) => Math.min(high, Math.max(low, value));

function loadLocalRecord(key) {
  try { return Math.max(0, Number(window.localStorage.getItem(key)) || 0); }
  catch { return 0; }
}

function saveLocalRecord(key, score) {
  try { window.localStorage.setItem(key, String(score)); }
  catch { /* a private browser context can disable local storage */ }
}

export function mountActiveProductionScene(container, { company, activeSession, api, onExit, showToast = () => {} }) {
  const sceneRoot = document.createElement('div'); sceneRoot.innerHTML = renderActiveProductionScene(company, activeSession);
  container.replaceChildren(sceneRoot.firstElementChild);
  const root = container.querySelector('[data-active-scene]');
  root.focus({ preventScroll: true });
  const canvas = root.querySelector('[data-active-canvas]'); const ctx = canvas.getContext('2d');
  const selected = activeSession.facilities?.find((row) => row.branch_id === activeSession.selected_branch_id);
  const scene = sceneForBranch(activeSession.selected_branch_id, selected?.sector_id, selected?.scene);
  const mode = root.querySelector('[data-active-mode]'); const output = root.querySelector('[data-active-output]');
  const cycleLabel = root.querySelector('[data-active-cycle]');
  const hint = root.querySelector('[data-active-hint]'); const task = root.querySelector('[data-active-task]');
  const objective = root.querySelector('[data-active-objective]'); const runCount = root.querySelector('[data-active-runs]');
  const scoreLabel = root.querySelector('[data-active-score]'); const comboLabel = root.querySelector('[data-active-combo]');
  const bestLabel = root.querySelector('[data-active-best]'); const serverActivity = root.querySelector('[data-active-server-activity]');
  const orderSelect = root.querySelector('[data-active-order-select]'); const orderDetails = root.querySelector('[data-active-order-details]');
  const actionButton = root.querySelector('[data-active-action]'); const calibration = root.querySelector('[data-active-calibration]');
  const calibrationZone = root.querySelector('[data-active-calibration-zone]'); const calibrationNeedle = root.querySelector('[data-active-calibration-needle]');
  const qualityStatus = root.querySelector('[data-active-quality-status]'); const resumeButton = root.querySelector('[data-active-resume]');
  const production = activeSession.production || {};
  output.textContent = `${production.active || 0}/${production.total || 0} заводов работают`;
  const controller = new AbortController(); const keys = new Set();
  const recordKey = `natbirzha:active-shift-best:${activeSession.selected_branch_id}`;
  let savedBest = loadLocalRecord(recordKey);
  const game = { actor: { x: 0, y: 0 }, hasCargo: false, shift: createProductionShift(scene, { bestScore: savedBest }),
    activityCounter: 0, lastSentCounter: 0, lastAction: 'idle', direction: { x: 0, y: 0 }, target: null,
    paused: false, pauseRequested: false, closed: false, frame: 0, pulseTimer: 0, loopAt: 0, pulseBusy: false,
    calibrationPosition: 0, lastHudSignature: '',
    nextCycleAt: activeSession.facilities?.map((row) => row.next_cycle_at).filter(Boolean)
      .sort((left, right) => Date.parse(left) - Date.parse(right))[0] || null, lastCountdown: 0 };
  let width = 1; let height = 1; let pulseSequence = 0; let currentSession = activeSession;

  const resetInput = () => {
    keys.clear();
    game.direction = { x: 0, y: 0 };
    game.target = null;
    game.lastSentCounter = game.activityCounter;
    game.lastAction = 'idle';
  };

  const resize = () => {
    const rect = canvas.getBoundingClientRect(); const ratio = Math.min(2, window.devicePixelRatio || 1);
    width = Math.max(1, rect.width); height = Math.max(1, rect.height);
    canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    if (!game.actor.x) { game.actor.x = width * 0.5; game.actor.y = height * 0.52; }
  };
  resize(); window.addEventListener('resize', resize, { signal: controller.signal });
  const recordInteraction = (action) => {
    game.activityCounter += 1;
    game.lastAction = action;
  };
  const phaseTarget = () => {
    const points = stationPoints(width, height);
    return ({ pickup: points.source, work: points.workstation, deliver: points.destination })[game.shift.phase] || null;
  };
  const isNear = (point) => Boolean(point && Math.hypot(point.x - game.actor.x, point.y - game.actor.y) < 64);
  const updateActionAvailability = () => {
    const needsProximity = ['pickup', 'work', 'deliver'].includes(game.shift.phase);
    const disabled = game.paused || game.closed || (needsProximity && !isNear(phaseTarget()));
    if (actionButton.disabled !== disabled) actionButton.disabled = disabled;
  };
  const updateGameplayUi = () => {
    const shift = game.shift;
    const actions = {
      offer: 'Принять заказ', pickup: 'Забрать груз', work: 'Запустить линию',
      calibrate: 'Зафиксировать качество', deliver: 'Сдать заказ', complete: 'Начать новую смену',
    };
    const signatures = {
      offer: 'Выбери заказ: стандартный проще, точный приносит больше очков за точную настройку.',
      pickup: `Забери партию «${shift.activeOrder?.cargo || 'груз'}» на приёмке.`,
      work: `Доставь груз к линии «${shift.activeOrder?.workstation || scene?.workstation || 'цех'}» и запусти её.`,
      calibrate: 'Метка движется по шкале. Зафиксируй её в зелёной зоне; заказ можно выполнить в любом случае.',
      deliver: `Отвези готовую партию к точке «${shift.activeOrder?.delivery || scene?.delivery_marker || 'склад'}».`,
      complete: `Смена закрыта: ${shift.score} очков. Можно сразу начать следующую.`,
    };
    const signature = `${shift.phase}:${shift.completedOrders}:${shift.score}:${shift.combo}:${shift.selectedOrderId}:${shift.lastResult?.points || 0}`;
    runCount.textContent = `Заказы: ${shift.completedOrders}/5`;
    scoreLabel.textContent = `Очки: ${shift.score}`;
    comboLabel.textContent = `Серия: ${shift.combo}`;
    bestLabel.textContent = `Рекорд: ${savedBest}`;
    orderSelect.disabled = shift.phase !== 'offer';
    if (shift.phase === 'offer') {
      const options = shift.offers.map((item) => {
        const option = document.createElement('option');
        option.value = item.id;
        option.textContent = `${item.label} · ${item.basePoints}+ очков`;
        return option;
      });
      orderSelect.replaceChildren(...options);
      orderSelect.value = shift.selectedOrderId;
    }
    orderDetails.textContent = shift.phase === 'offer'
      ? `Маршрут партии: приёмка → ${scene?.workstation || 'линия'} → ${scene?.delivery_marker || 'склад'}. Очки — только личный рекорд.`
      : shift.phase === 'complete'
        ? `Результат смены: ${shift.score}. Лучший результат на этом устройстве: ${savedBest}.`
        : `${shift.activeOrder?.cargo || ''} · ${shift.activeOrder?.workstation || ''} · ${shift.activeOrder?.delivery || ''}`;
    actionButton.textContent = actions[shift.phase] || actions.offer;
    calibration.hidden = shift.phase !== 'calibrate';
    if (shift.activeOrder) {
      calibrationZone.style.left = `${(shift.activeOrder.target - shift.activeOrder.tolerance) * 100}%`;
      calibrationZone.style.width = `${shift.activeOrder.tolerance * 200}%`;
    }
    if (shift.phase === 'calibrate') qualityStatus.textContent = 'Попади в зелёную зону. Если промахнёшься, заказ всё равно завершится без штрафа.';
    else if (shift.lastResult) qualityStatus.textContent = `Последняя партия: +${shift.lastResult.points} очков · качество ${shift.lastResult.quality}/2.`;
    if (game.lastHudSignature !== signature) {
      task.textContent = signatures[shift.phase] || signatures.offer;
      objective.textContent = ({
        offer: 'ВЫБЕРИ ЗАКАЗ', pickup: 'ЗАБЕРИ ПАРТИЮ', work: 'ЗАПУСТИ ЛИНИЮ',
        calibrate: 'НАСТРОЙКА', deliver: 'ОТГРУЗИ ПАРТИЮ', complete: 'СМЕНА ЗАКРЫТА',
      })[shift.phase] || 'ПРОИЗВОДСТВО';
      game.lastHudSignature = signature;
    }
    updateActionAvailability();
  };
  const setMove = (event) => {
    const rect = joystick.getBoundingClientRect(); const dx = event.clientX - (rect.left + rect.width / 2);
    const dy = event.clientY - (rect.top + rect.height / 2); const length = Math.hypot(dx, dy) || 1;
    game.direction = { x: dx / length, y: dy / length };
  };
  const joystick = root.querySelector('[data-active-joystick]');
  joystick.addEventListener('pointerdown', (event) => {
    joystick.setPointerCapture(event.pointerId); setMove(event);
  }, { signal: controller.signal });
  joystick.addEventListener('pointermove', (event) => { if (joystick.hasPointerCapture(event.pointerId)) setMove(event); }, { signal: controller.signal });
  const releaseJoystick = (event) => { if (joystick.hasPointerCapture(event.pointerId)) joystick.releasePointerCapture(event.pointerId); game.direction = { x: 0, y: 0 }; };
  joystick.addEventListener('pointerup', releaseJoystick, { signal: controller.signal });
  joystick.addEventListener('pointercancel', releaseJoystick, { signal: controller.signal });
  canvas.addEventListener('pointerdown', (event) => {
    const rect = canvas.getBoundingClientRect();
    game.target = { x: clamp(event.clientX - rect.left, 18, width - 18), y: clamp(event.clientY - rect.top, 18, height - 18) };
    root.focus({ preventScroll: true });
  }, { signal: controller.signal });
  root.addEventListener('keydown', (event) => {
    if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'w', 'a', 's', 'd'].includes(event.key)) return;
    if (game.paused || game.closed) return;
    event.preventDefault(); keys.add(event.key.toLowerCase());
  }, { signal: controller.signal });
  root.addEventListener('keyup', (event) => keys.delete(event.key.toLowerCase()), { signal: controller.signal });
  orderSelect.addEventListener('change', () => {
    game.shift = selectProductionOrder(game.shift, orderSelect.value);
    recordInteraction('interact');
    updateGameplayUi();
  }, { signal: controller.signal });
  actionButton.addEventListener('click', () => {
    const phase = game.shift.phase;
    if (['pickup', 'work', 'deliver'].includes(phase) && !isNear(phaseTarget())) return;
    if (phase === 'offer') {
      game.shift = acceptProductionOrder(game.shift);
      recordInteraction('interact');
    } else if (phase === 'pickup') {
      game.shift = collectProductionCargo(game.shift);
      game.hasCargo = true;
      recordInteraction('pickup');
    } else if (phase === 'work') {
      game.shift = startProductionLine(game.shift);
      game.calibrationPosition = 0;
      recordInteraction('interact');
    } else if (phase === 'calibrate') {
      game.shift = finishProductionCalibration(game.shift, game.calibrationPosition);
      recordInteraction('interact');
      const quality = game.shift.quality || 0;
      showToast(quality === 2 ? 'Идеальная настройка' : quality === 1 ? 'Хорошая настройка' : 'Партия готова — без штрафа', 'success');
    } else if (phase === 'deliver') {
      game.shift = deliverProductionOrder(game.shift);
      game.hasCargo = false;
      recordInteraction('deliver');
      showToast(`Заказ выполнен: +${game.shift.lastResult?.points || 0} очков`, 'success');
      if (game.shift.phase === 'complete' && game.shift.score > savedBest) {
        savedBest = game.shift.score;
        saveLocalRecord(recordKey, savedBest);
      }
    } else if (phase === 'complete') {
      game.shift = startNextProductionShift(game.shift);
      recordInteraction('interact');
    }
    updateGameplayUi();
  }, { signal: controller.signal });

  const pauseServer = async (reason = 'page_hidden') => {
    if (!currentSession?.session_id || game.closed) return;
    game.pauseRequested = true;
    if (game.paused) return;
    resetInput();
    game.paused = true; clearInterval(game.pulseTimer); cancelAnimationFrame(game.frame);
    mode.textContent = 'Пауза · бонус остановлен'; resumeButton.hidden = false;
    updateActionAvailability();
    try { await api.pauseNextGameActiveProduction(currentSession.session_id, currentSession.session_token); }
    catch { hint.textContent = 'Нет связи с сервером. После тайм-аута сессии заводы вернутся к обычному режиму.'; }
    if (reason === 'page_hidden') task.textContent = 'Сцена на паузе, пока приложение было скрыто.';
  };
  const sendPulse = async () => {
    if (game.pulseBusy || game.paused || game.closed) return;
    if (!navigator.onLine) {
      mode.textContent = 'Нет связи · активный режим приостановлен';
      hint.textContent = 'Подключение восстановится — нажми «Продолжить», чтобы открыть новую серверную сессию.';
      resumeButton.hidden = false;
      return;
    }
    game.pulseBusy = true;
    const submittedActivityCounter = game.activityCounter;
    const action = submittedActivityCounter > game.lastSentCounter ? game.lastAction : 'idle';
    try {
      const response = await api.pulseNextGameActiveProduction({
        session_id: currentSession.session_id, session_token: currentSession.session_token,
        sequence: ++pulseSequence, scene_action: action, user_input_counter: submittedActivityCounter,
      });
      game.lastSentCounter = submittedActivityCounter;
      mode.textContent = response.active ? 'Сессия активна · до ×1,50' : 'Пауза · бонус ×1,00';
      serverActivity.textContent = response.active ? 'Сервер подтвердил активность' : 'Активность приостановлена';
      output.textContent = `${response.working_facilities || 0}/${response.total_facilities || 0} заводов работают`;
      game.nextCycleAt = response.nearest_cycle_at || game.nextCycleAt;
      if (response.idle_warning) task.textContent = 'Заверши действие по заказу или выбери следующий участок, чтобы сохранить активную смену.';
      else if (!response.active) task.textContent = 'Сделай действие на сцене, чтобы возобновить активный режим.';
      hint.textContent = 'До ×1,50 выпуска: сервер учитывает только подтверждённое время каждого цикла.';
    } catch {
      mode.textContent = 'Связь потеряна · ждём сервер';
      hint.textContent = 'Без подтверждения сервера активный бонус не начисляется; игровой экран не меняет склад или баланс.';
    } finally { game.pulseBusy = false; }
  };
  const drawFrame = (timestamp) => {
    if (game.paused || game.closed) return;
    const elapsed = Math.min(0.05, Math.max(0, (timestamp - game.loopAt) / 1000)); game.loopAt = timestamp;
    if (timestamp - game.lastCountdown > 1000 && game.nextCycleAt) {
      const seconds = Math.max(0, Math.ceil((Date.parse(game.nextCycleAt) - Date.now()) / 1000));
      cycleLabel.textContent = seconds ? `Ближайший производственный цикл примерно через ${Math.ceil(seconds / 60)} мин.` : 'Ближайший цикл готов к серверному расчёту';
      game.lastCountdown = timestamp;
    }
    let dx = game.direction.x; let dy = game.direction.y;
    if (keys.has('arrowleft') || keys.has('a')) dx -= 1;
    if (keys.has('arrowright') || keys.has('d')) dx += 1;
    if (keys.has('arrowup') || keys.has('w')) dy -= 1;
    if (keys.has('arrowdown') || keys.has('s')) dy += 1;
    const length = Math.hypot(dx, dy);
    if (game.shift.phase !== 'calibrate' && length > 0.1) {
      game.actor.x = clamp(game.actor.x + dx / length * 150 * elapsed, 20, width - 20);
      game.actor.y = clamp(game.actor.y + dy / length * 150 * elapsed, 20, height - 20);
      game.target = null;
    } else if (game.shift.phase !== 'calibrate' && game.target) {
      const diffX = game.target.x - game.actor.x; const diffY = game.target.y - game.actor.y; const distance = Math.hypot(diffX, diffY);
      if (distance < 4) game.target = null;
      else { game.actor.x += diffX / distance * 140 * elapsed; game.actor.y += diffY / distance * 140 * elapsed; }
    }
    if (game.shift.phase === 'calibrate') {
      const sweep = (timestamp % 2200) / 2200;
      game.calibrationPosition = sweep < 0.5 ? sweep * 2 : (1 - sweep) * 2;
      calibrationNeedle.style.left = `${game.calibrationPosition * 100}%`;
    }
    updateActionAvailability();
    paint(ctx, width, height, scene, game, timestamp);
    game.frame = requestAnimationFrame(drawFrame);
  };
  const startTimers = () => {
    game.loopAt = performance.now(); game.frame = requestAnimationFrame(drawFrame);
    game.pulseTimer = window.setInterval(sendPulse, 15_000);
  };
  const resume = async () => {
    resumeButton.disabled = true;
    resetInput();
    game.pauseRequested = false;
    try {
      const resumedSession = await api.startNextGameActiveProduction(activeSession.selected_branch_id);
      if (game.closed || game.pauseRequested || document.hidden) {
        if (!game.closed) { resetInput(); resumeButton.hidden = false; }
        try { await api.pauseNextGameActiveProduction(resumedSession.session_id, resumedSession.session_token); }
        catch { /* the heartbeat timeout is the fallback for a hidden or closed app */ }
        return;
      }
      currentSession = resumedSession;
      pulseSequence = 0; game.activityCounter = 0;
      game.lastSentCounter = game.activityCounter; game.lastAction = 'idle'; game.paused = false;
      mode.textContent = 'Сессия активна · до ×1,50'; resumeButton.hidden = true;
      serverActivity.textContent = 'Активная смена';
      updateGameplayUi();
      startTimers(); sendPulse();
    } catch (error) { if (!game.closed) showToast(error.message || 'Не удалось возобновить сцену', 'error'); }
    finally { if (!game.closed) resumeButton.disabled = false; }
  };
  resumeButton.addEventListener('click', resume, { signal: controller.signal });
  const destroy = async (status = 'PAUSED') => {
    if (game.closed) return;
    game.closed = true; clearInterval(game.pulseTimer); cancelAnimationFrame(game.frame); controller.abort();
    if (currentSession?.session_id) {
      const action = status === 'STOPPED' ? api.stopNextGameActiveProduction : api.pauseNextGameActiveProduction;
      try { await action(currentSession.session_id, currentSession.session_token); } catch { /* heartbeat expiry is the fallback */ }
    }
  };
  root.querySelectorAll('[data-active-exit]').forEach((button) => button.addEventListener('click', async () => {
    await destroy('STOPPED'); onExit?.();
  }, { signal: controller.signal }));
  document.addEventListener('visibilitychange', () => { if (document.hidden) void pauseServer('page_hidden'); }, { signal: controller.signal });
  window.addEventListener('blur', () => { void pauseServer('focus_lost'); }, { signal: controller.signal });
  window.addEventListener('pagehide', () => { void pauseServer('page_hidden'); }, { signal: controller.signal });
  window.addEventListener('offline', () => { void pauseServer('offline'); }, { signal: controller.signal });
  window.addEventListener('online', () => {
    if (!game.paused) return;
    hint.textContent = 'Подключение восстановлено. Нажми «Продолжить», чтобы открыть новую серверную сессию.';
    resumeButton.hidden = false;
  }, { signal: controller.signal });
  updateGameplayUi();
  startTimers();
  return { destroy };
}
