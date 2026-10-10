import { sceneForBranch } from './scene_registry.mjs';

const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[character]));

export function renderActiveProductionScene(company, activeSession) {
  const picked = activeSession.facilities?.find((row) => row.branch_id === activeSession.selected_branch_id);
  const scene = sceneForBranch(activeSession.selected_branch_id, picked?.sector_id, picked?.scene);
  return `<section class="next-active-production" data-active-scene data-family="${escapeHtml(scene?.scene_family || 'resources')}" tabindex="-1">
    <header class="active-production-header"><div><span>АКТИВНОЕ ПРОИЗВОДСТВО</span><h1>${escapeHtml(company?.name || 'Компания')} · ${escapeHtml(picked?.name || scene?.branch_name || 'Завод')}</h1></div><button type="button" data-active-exit aria-label="Закрыть сцену">×</button></header>
    <div class="active-production-summary"><b data-active-mode>Сессия активна · до ×1,50</b><span data-active-output>Проверяем состояние заводов…</span><span data-active-cycle>Загружаем ближайший производственный цикл…</span><small data-active-hint>Игровые действия только для экрана — доход считает сервер по производственным циклам.</small></div>
    <div class="active-production-canvas-wrap"><canvas data-active-canvas aria-label="2D-сцена активного производства"></canvas><div class="active-production-objective" data-active-objective></div></div>
    <div class="active-production-footer"><p data-active-task>Подойди к отмеченному участку. Движение: джойстик, касание карты или WASD.</p><div class="active-production-controls"><div class="active-production-joystick" data-active-joystick role="application" aria-label="Виртуальный джойстик"><span></span></div><div class="active-production-actions"><b data-active-runs>Рейсы: 0</b><small>Визуальная статистика</small><button type="button" data-active-resume hidden>Продолжить</button><button type="button" data-active-exit>Выйти</button></div></div></div>
  </section>`;
}

const clamp = (value, low, high) => Math.min(high, Math.max(low, value));

function roundedRect(ctx, x, y, width, height, radius) {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.beginPath(); ctx.moveTo(x + r, y); ctx.lineTo(x + width - r, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + r);
  ctx.lineTo(x + width, y + height - r); ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
  ctx.lineTo(x + r, y + height); ctx.quadraticCurveTo(x, y + height, x, y + height - r);
  ctx.lineTo(x, y + r); ctx.quadraticCurveTo(x, y, x + r, y); ctx.closePath();
}

function markerPoints(width, height) {
  return [{ x: width * 0.23, y: height * 0.35 }, { x: width * 0.77, y: height * 0.65 }];
}

function drawStation(ctx, family, point, title, variant, pulse, isDestination = false) {
  const x = point.x; const y = point.y;
  const accents = { resources: '#9c6b3d', energy: '#e9bb43', oilgas: '#44859a', materials: '#cf7750', infrastructure: '#47866f', technology: '#6176b6', bank: '#aa8945' };
  const accent = accents[family] || accents.resources;
  ctx.save();
  ctx.fillStyle = `rgba(39, 65, 53, ${0.10 + pulse * 0.06})`;
  ctx.beginPath(); ctx.ellipse(x, y + 23, 67, 18, 0, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = '#fffdf6'; ctx.strokeStyle = accent; ctx.lineWidth = 4;
  roundedRect(ctx, x - 43, y - 37, 86, 61, 12); ctx.fill(); ctx.stroke();
  ctx.fillStyle = accent;
  if (isDestination && family === 'resources') {
    ctx.fillRect(x - 24, y - 14, 38, 24); ctx.fillStyle = '#f4dfb5'; ctx.fillRect(x - 18, y - 8, 18, 12);
    ctx.fillStyle = accent; ctx.beginPath(); ctx.arc(x - 18, y + 15, 6, 0, Math.PI * 2); ctx.arc(x + 9, y + 15, 6, 0, Math.PI * 2); ctx.fill();
  } else if (isDestination && family === 'energy') {
    ctx.fillRect(x - 27, y - 5, 16, 23); ctx.fillRect(x - 7, y - 17, 17, 35); ctx.fillRect(x + 14, y - 1, 13, 19);
    ctx.fillStyle = '#fff2bb'; ctx.fillRect(x - 2, y - 11, 6, 7); ctx.fillRect(x + 18, y + 4, 5, 6);
  } else if (isDestination && family === 'oilgas') {
    ctx.beginPath(); ctx.ellipse(x, y - 15, 23, 8, 0, 0, Math.PI * 2); ctx.fill(); ctx.fillRect(x - 23, y - 15, 46, 29);
    ctx.beginPath(); ctx.ellipse(x, y + 14, 23, 8, 0, 0, Math.PI); ctx.fill();
  } else if (isDestination && family === 'materials') {
    ctx.fillRect(x - 28, y + 9, 56, 7); ctx.fillRect(x - 22, y - 7, 19, 16); ctx.fillRect(x + 3, y - 12, 19, 21);
    ctx.fillStyle = '#ffe9d8'; ctx.fillRect(x - 18, y - 3, 11, 7); ctx.fillRect(x + 7, y - 8, 11, 7);
  } else if (isDestination && family === 'infrastructure') {
    ctx.beginPath(); ctx.moveTo(x - 28, y - 6); ctx.lineTo(x, y - 24); ctx.lineTo(x + 28, y - 6); ctx.fill();
    ctx.fillRect(x - 23, y - 6, 46, 24); ctx.fillStyle = '#fff6dc'; ctx.fillRect(x - 16, y - 1, 10, 8); ctx.fillRect(x + 6, y - 1, 10, 8);
  } else if (isDestination && family === 'technology') {
    ctx.fillRect(x - 24, y - 15, 48, 32); ctx.strokeStyle = '#fff'; ctx.lineWidth = 2;
    for (let pin = -17; pin <= 17; pin += 8) { ctx.beginPath(); ctx.moveTo(x + pin, y - 20); ctx.lineTo(x + pin, y - 15); ctx.moveTo(x + pin, y + 17); ctx.lineTo(x + pin, y + 22); ctx.stroke(); }
    ctx.fillStyle = '#dfe5ff'; ctx.fillRect(x - 11, y - 7, 22, 16);
  } else if (isDestination && family === 'bank') {
    ctx.fillRect(x - 28, y - 3, 56, 20); ctx.fillStyle = '#fff5dc'; ctx.fillRect(x - 20, y - 12, 40, 10);
    ctx.fillStyle = accent; ctx.beginPath(); ctx.arc(x, y - 17, 8, 0, Math.PI * 2); ctx.fill();
  } else if (family === 'resources') {
    ctx.beginPath(); ctx.moveTo(x - 28, y + 7); ctx.lineTo(x - 9, y - 23); ctx.lineTo(x + 9, y + 7); ctx.fill();
    ctx.beginPath(); ctx.moveTo(x - 5, y + 7); ctx.lineTo(x + 13, y - 14); ctx.lineTo(x + 31, y + 7); ctx.fill();
  } else if (family === 'energy') {
    ctx.fillRect(x - 23, y - 17, 46, 35); ctx.fillStyle = '#fff6ce';
    ctx.beginPath(); ctx.moveTo(x + 3, y - 13); ctx.lineTo(x - 11, y + 1); ctx.lineTo(x - 2, y + 1); ctx.lineTo(x - 8, y + 13); ctx.lineTo(x + 12, y - 4); ctx.lineTo(x + 3, y - 4); ctx.fill();
  } else if (family === 'oilgas') {
    ctx.strokeStyle = accent; ctx.lineWidth = 5; ctx.beginPath(); ctx.moveTo(x - 24, y + 11); ctx.lineTo(x - 8, y - 17); ctx.lineTo(x + 15, y + 11); ctx.moveTo(x - 31, y - 4); ctx.lineTo(x + 27, y - 4); ctx.stroke();
    ctx.beginPath(); ctx.arc(x + 20, y + 7, 8, 0, Math.PI * 2); ctx.fill();
  } else if (family === 'materials') {
    ctx.fillRect(x - 23, y - 15, 46, 31); ctx.fillStyle = '#fff3e8'; ctx.fillRect(x - 13, y - 4, 26, 20); ctx.fillStyle = accent; ctx.fillRect(x - 20, y - 21, 11, 8); ctx.fillRect(x + 9, y - 21, 11, 8);
  } else if (family === 'infrastructure') {
    ctx.beginPath(); ctx.moveTo(x - 27, y - 4); ctx.lineTo(x, y - 23); ctx.lineTo(x + 28, y - 4); ctx.fill(); ctx.fillRect(x - 22, y - 4, 44, 23); ctx.fillStyle = '#fffdf6'; ctx.fillRect(x - 7, y + 3, 14, 16);
  } else if (family === 'technology') {
    for (let i = 0; i < 3; i += 1) { ctx.fillRect(x - 27 + i * 20, y - 22, 15, 42); ctx.fillStyle = '#d8e1ff'; ctx.fillRect(x - 23 + i * 20, y - 15, 7, 5); ctx.fillStyle = accent; }
  } else {
    ctx.fillRect(x - 26, y - 13, 52, 32); ctx.fillStyle = '#fff7df'; ctx.fillRect(x - 19, y - 6, 38, 7); ctx.fillStyle = accent; ctx.fillRect(x - 9, y + 7, 18, 13);
  }
  ctx.fillStyle = '#34463e'; ctx.font = '700 12px system-ui'; ctx.textAlign = 'center'; ctx.fillText(title, x, y + 49);
  ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(x + 33, y - 29, 12, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = accent; ctx.font = '700 10px system-ui'; ctx.fillText(String(variant + 1), x + 33, y - 25);
  ctx.restore();
}

function paint(ctx, width, height, scene, game, now) {
  const color = scene?.scene_family === 'energy' ? '#edf3da' : scene?.scene_family === 'technology' ? '#e8eef7' : '#e8efe0';
  ctx.clearRect(0, 0, width, height); ctx.fillStyle = color; ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = 'rgba(255,255,255,.45)';
  for (let i = 0; i < 9; i += 1) {
    const x = ((i * 137 + 33) % width); const y = ((i * 79 + 22) % height);
    ctx.beginPath(); ctx.arc(x, y, 10 + (i % 3) * 4, 0, Math.PI * 2); ctx.fill();
  }
  const [source, destination] = markerPoints(width, height);
  ctx.strokeStyle = 'rgba(77, 122, 99, .32)'; ctx.lineWidth = 12; ctx.setLineDash([11, 10]);
  ctx.beginPath(); ctx.moveTo(source.x, source.y); ctx.lineTo(destination.x, destination.y); ctx.stroke(); ctx.setLineDash([]);
  const pulse = (Math.sin(now / 430) + 1) / 2;
  drawStation(ctx, scene?.scene_family, source, game.hasCargo ? 'ОБРАБОТКА' : scene?.workstation || 'УЧАСТОК', scene?.microvariant || 0, pulse);
  drawStation(ctx, scene?.scene_family, destination, scene?.delivery_marker || 'СКЛАД', (scene?.microvariant || 0) + 2, pulse, true);
  const target = game.hasCargo ? destination : source;
  ctx.strokeStyle = '#218866'; ctx.lineWidth = 3 + pulse * 2; ctx.beginPath(); ctx.arc(target.x, target.y, 48 + pulse * 7, 0, Math.PI * 2); ctx.stroke();
  ctx.fillStyle = '#2b5c49'; ctx.beginPath(); ctx.ellipse(game.actor.x, game.actor.y + 14, 19, 7, 0, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = scene?.scene_family === 'infrastructure' ? '#397e6b' : '#d3983c';
  roundedRect(ctx, game.actor.x - 18, game.actor.y - 8, 36, 21, 8); ctx.fill();
  ctx.fillStyle = '#fff4cf'; ctx.beginPath(); ctx.arc(game.actor.x, game.actor.y - 13, 9, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = '#3e5148'; ctx.beginPath(); ctx.arc(game.actor.x - 10, game.actor.y + 14, 5, 0, Math.PI * 2); ctx.arc(game.actor.x + 10, game.actor.y + 14, 5, 0, Math.PI * 2); ctx.fill();
  if (game.hasCargo) { ctx.fillStyle = '#d4aa57'; ctx.fillRect(game.actor.x - 7, game.actor.y - 34, 14, 13); ctx.strokeStyle = '#8b6832'; ctx.strokeRect(game.actor.x - 7, game.actor.y - 34, 14, 13); }
}

export function mountActiveProductionScene(container, { company, activeSession, api, onExit, showToast = () => {} }) {
  const sceneRoot = document.createElement('div'); sceneRoot.innerHTML = renderActiveProductionScene(company, activeSession);
  container.replaceChildren(sceneRoot.firstElementChild);
  const root = container.querySelector('[data-active-scene]');
  const canvas = root.querySelector('[data-active-canvas]'); const ctx = canvas.getContext('2d');
  const selected = activeSession.facilities?.find((row) => row.branch_id === activeSession.selected_branch_id);
  const scene = sceneForBranch(activeSession.selected_branch_id, selected?.sector_id, selected?.scene);
  const mode = root.querySelector('[data-active-mode]'); const output = root.querySelector('[data-active-output]');
  const cycleLabel = root.querySelector('[data-active-cycle]');
  const hint = root.querySelector('[data-active-hint]'); const task = root.querySelector('[data-active-task]');
  const objective = root.querySelector('[data-active-objective]'); const runCount = root.querySelector('[data-active-runs]');
  const resumeButton = root.querySelector('[data-active-resume]');
  const production = activeSession.production || {};
  output.textContent = `${production.active || 0}/${production.total || 0} заводов работают`;
  const controller = new AbortController(); const keys = new Set();
  const game = { actor: { x: 0, y: 0 }, hasCargo: false, deliveries: 0, lastPulse: 0,
    inputCounter: 0, lastSentCounter: 0, lastAction: 'idle', direction: { x: 0, y: 0 }, target: null,
    paused: false, closed: false, frame: 0, pulseTimer: 0, loopAt: 0, pulseBusy: false,
    nextCycleAt: activeSession.facilities?.map((row) => row.next_cycle_at).filter(Boolean)
      .sort((left, right) => Date.parse(left) - Date.parse(right))[0] || null, lastCountdown: 0 };
  let width = 1; let height = 1; let pulseSequence = 0; let currentSession = activeSession;

  const resize = () => {
    const rect = canvas.getBoundingClientRect(); const ratio = Math.min(2, window.devicePixelRatio || 1);
    width = Math.max(1, rect.width); height = Math.max(1, rect.height);
    canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    if (!game.actor.x) { game.actor.x = width * 0.5; game.actor.y = height * 0.52; }
  };
  resize(); window.addEventListener('resize', resize, { signal: controller.signal });
  const countInput = (action) => { game.inputCounter += 1; game.lastAction = action; };
  const setMove = (event) => {
    const rect = joystick.getBoundingClientRect(); const dx = event.clientX - (rect.left + rect.width / 2);
    const dy = event.clientY - (rect.top + rect.height / 2); const length = Math.hypot(dx, dy) || 1;
    game.direction = { x: dx / length, y: dy / length };
  };
  const joystick = root.querySelector('[data-active-joystick]');
  joystick.addEventListener('pointerdown', (event) => {
    joystick.setPointerCapture(event.pointerId); setMove(event); countInput('move');
  }, { signal: controller.signal });
  joystick.addEventListener('pointermove', (event) => { if (joystick.hasPointerCapture(event.pointerId)) setMove(event); }, { signal: controller.signal });
  const releaseJoystick = (event) => { if (joystick.hasPointerCapture(event.pointerId)) joystick.releasePointerCapture(event.pointerId); game.direction = { x: 0, y: 0 }; };
  joystick.addEventListener('pointerup', releaseJoystick, { signal: controller.signal });
  joystick.addEventListener('pointercancel', releaseJoystick, { signal: controller.signal });
  canvas.addEventListener('pointerdown', (event) => {
    const rect = canvas.getBoundingClientRect();
    game.target = { x: clamp(event.clientX - rect.left, 18, width - 18), y: clamp(event.clientY - rect.top, 18, height - 18) };
    countInput('move'); root.focus({ preventScroll: true });
  }, { signal: controller.signal });
  document.addEventListener('keydown', (event) => {
    if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'w', 'a', 's', 'd'].includes(event.key)) return;
    if (game.paused || game.closed) return;
    event.preventDefault(); keys.add(event.key.toLowerCase());
  }, { signal: controller.signal });
  document.addEventListener('keyup', (event) => keys.delete(event.key.toLowerCase()), { signal: controller.signal });

  const pauseServer = async (reason = 'page_hidden') => {
    if (!currentSession?.session_id || game.paused || game.closed) return;
    game.paused = true; clearInterval(game.pulseTimer); cancelAnimationFrame(game.frame);
    mode.textContent = 'Пауза · бонус остановлен'; resumeButton.hidden = false;
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
    const action = game.inputCounter > game.lastSentCounter ? game.lastAction : 'idle';
    try {
      const response = await api.pulseNextGameActiveProduction({
        session_id: currentSession.session_id, session_token: currentSession.session_token,
        sequence: ++pulseSequence, scene_action: action, user_input_counter: game.inputCounter,
      });
      game.lastSentCounter = game.inputCounter;
      mode.textContent = response.active ? 'Сессия активна · до ×1,50' : 'Пауза · бонус ×1,00';
      output.textContent = `${response.working_facilities || 0}/${response.total_facilities || 0} заводов работают`;
      game.nextCycleAt = response.nearest_cycle_at || game.nextCycleAt;
      if (response.idle_warning) task.textContent = 'Перевези следующую партию или смени участок, чтобы продолжить активную сессию.';
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
    if (length > 0.1) {
      game.actor.x = clamp(game.actor.x + dx / length * 150 * elapsed, 20, width - 20);
      game.actor.y = clamp(game.actor.y + dy / length * 150 * elapsed, 20, height - 20);
      if (timestamp - game.lastPulse > 600) { countInput('move'); game.lastPulse = timestamp; }
      game.target = null;
    } else if (game.target) {
      const diffX = game.target.x - game.actor.x; const diffY = game.target.y - game.actor.y; const distance = Math.hypot(diffX, diffY);
      if (distance < 4) game.target = null;
      else { game.actor.x += diffX / distance * 140 * elapsed; game.actor.y += diffY / distance * 140 * elapsed; }
    }
    const [source, destination] = markerPoints(width, height); const marker = game.hasCargo ? destination : source;
    if (Math.hypot(marker.x - game.actor.x, marker.y - game.actor.y) < 58) {
      game.hasCargo = !game.hasCargo;
      if (!game.hasCargo) { game.deliveries += 1; runCount.textContent = `Рейсы: ${game.deliveries}`; }
      countInput(game.hasCargo ? 'pickup' : 'deliver');
      task.textContent = game.hasCargo ? `Партия доставлена на участок. Теперь отвези её к: ${scene?.delivery_marker || 'складу'}.` : `Собрал ${scene?.visual_pickup || 'груз'}. Отвези его к следующей точке.`;
    }
    objective.textContent = game.hasCargo ? `Везёшь: ${scene?.visual_pickup || 'груз'}` : `Задача: ${scene?.workstation || 'участок'}`;
    paint(ctx, width, height, scene, game, timestamp);
    game.frame = requestAnimationFrame(drawFrame);
  };
  const startTimers = () => {
    game.loopAt = performance.now(); game.frame = requestAnimationFrame(drawFrame);
    game.pulseTimer = window.setInterval(sendPulse, 15_000);
  };
  const resume = async () => {
    resumeButton.disabled = true;
    try {
      currentSession = await api.startNextGameActiveProduction(activeSession.selected_branch_id);
      pulseSequence = 0; game.lastSentCounter = 0; game.lastAction = 'idle'; game.paused = false;
      mode.textContent = 'Сессия активна · до ×1,50'; resumeButton.hidden = true;
      task.textContent = 'Двигайся к выделенной точке, затем доставь визуальную партию на склад.';
      startTimers(); sendPulse();
    } catch (error) { showToast(error.message || 'Не удалось возобновить сцену', 'error'); }
    finally { resumeButton.disabled = false; }
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
  window.addEventListener('pagehide', () => { void pauseServer('page_hidden'); }, { signal: controller.signal });
  window.addEventListener('offline', () => { void pauseServer('offline'); }, { signal: controller.signal });
  window.addEventListener('online', () => {
    if (!game.paused) return;
    hint.textContent = 'Подключение восстановлено. Нажми «Продолжить», чтобы открыть новую серверную сессию.';
    resumeButton.hidden = false;
  }, { signal: controller.signal });
  startTimers();
  return { destroy };
}
