import { sceneForBranch } from './scene_registry.mjs';
import { paint } from './render.mjs?v=20261011_rhythm_render_v1';
import { createTimingGameState, pointerAt, updateTimingGameState } from './gameplay.mjs?v=20261011_rhythm_game_v1';

const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[character]));

export function renderActiveProductionScene(company, activeSession) {
  const picked = activeSession.facilities?.find((row) => row.branch_id === activeSession.selected_branch_id);
  const scene = sceneForBranch(activeSession.selected_branch_id, picked?.sector_id, picked?.scene);
  return `<section class="next-active-production" data-active-scene data-family="${escapeHtml(scene?.scene_family || 'resources')}" tabindex="0">
    <header class="active-production-header"><div><span>АКТИВНОЕ ПРОИЗВОДСТВО</span><h1>${escapeHtml(company?.name || 'Компания')} · ${escapeHtml(picked?.name || scene?.branch_name || 'Завод')}</h1></div><button type="button" data-active-exit aria-label="Закрыть сцену">×</button></header>
    <div class="active-production-summary"><b data-active-mode>Ритм цеха · ×1,00</b><span data-active-output>Проверяем состояние заводов…</span><span data-active-cycle>Загружаем ближайший производственный цикл…</span><small data-active-hint>Попадай в движущиеся зоны: сервер учитывает подтверждённый множитель выпуска до ×5.</small></div>
    <div class="active-production-canvas-wrap"><canvas data-active-canvas aria-label="Мини-игра: попади стрелкой в золотую или синюю зону"></canvas><div class="active-production-objective" data-active-objective>ПОПАДИ В ЗОНУ · БОНУС ДО ×5</div></div>
    <div class="active-production-footer"><div class="active-production-game"><div class="active-production-game-stats"><b data-active-multiplier>×1,00 к выпуску</b><span data-active-charge>Заряд: 0/16</span><span data-active-streak>Серия: 0</span></div><p data-active-task>Золотая зона даёт +2 заряда и меняет направление стрелки. Синяя даёт +1, промах снимает 1 заряд.</p><div class="active-production-progress" aria-label="Заряд множителя"><i data-active-progress></i></div><div class="active-production-controls"><b data-active-server-activity>Серверная сессия активна</b><button type="button" data-active-tap>Ударить по метке</button><button type="button" data-active-resume hidden>Продолжить</button><button type="button" data-active-exit>Выйти</button></div><small class="active-production-footnote">Бонусный выпуск не тратит ресурсы. На склад он добавится с учётом свободного места.</small></div></div>
  </section>`;
}

const resultText = {
  gold: 'Точно! +2 заряда. Стрелка поменяла направление.',
  blue: 'Хорошо! Синяя зона дала +1 заряд.',
  miss: 'Промах: −1 заряд. Попробуй ещё раз.',
  too_soon: 'Слишком быстро — дождись следующего прохода стрелки.',
};

export function mountActiveProductionScene(container, { company, activeSession, api, onExit, showToast = () => {} }) {
  const stage = document.createElement('div');
  stage.innerHTML = renderActiveProductionScene(company, activeSession);
  container.replaceChildren(stage.firstElementChild);
  const root = container.querySelector('[data-active-scene]');
  root.focus({ preventScroll: true });
  const canvas = root.querySelector('[data-active-canvas]');
  const ctx = canvas.getContext('2d');
  const selected = activeSession.facilities?.find((row) => row.branch_id === activeSession.selected_branch_id);
  const scene = sceneForBranch(activeSession.selected_branch_id, selected?.sector_id, selected?.scene);
  const mode = root.querySelector('[data-active-mode]');
  const output = root.querySelector('[data-active-output]');
  const cycleLabel = root.querySelector('[data-active-cycle]');
  const hint = root.querySelector('[data-active-hint]');
  const task = root.querySelector('[data-active-task]');
  const serverActivity = root.querySelector('[data-active-server-activity]');
  const multiplierLabel = root.querySelector('[data-active-multiplier]');
  const chargeLabel = root.querySelector('[data-active-charge]');
  const streakLabel = root.querySelector('[data-active-streak]');
  const progress = root.querySelector('[data-active-progress]');
  const tapButton = root.querySelector('[data-active-tap]');
  const resumeButton = root.querySelector('[data-active-resume]');
  const production = activeSession.production || {};
  output.textContent = `${production.active || 0}/${production.total || 0} заводов работают`;

  const controller = new AbortController();
  const game = {
    timing: createTimingGameState(activeSession.timing, Date.now()),
    paused: false, pauseRequested: false, closed: false, pulseBusy: false,
    frame: 0, pulseTimer: 0, loopAt: 0, activityCounter: 0, lastCountdown: 0,
    nextCycleAt: activeSession.facilities?.map((row) => row.next_cycle_at).filter(Boolean)
      .sort((left, right) => Date.parse(left) - Date.parse(right))[0] || null,
  };
  let width = 1;
  let height = 1;
  let pulseSequence = 0;
  let currentSession = activeSession;

  const resize = () => {
    const rect = canvas.getBoundingClientRect();
    const ratio = Math.min(2, window.devicePixelRatio || 1);
    width = Math.max(1, rect.width);
    height = Math.max(1, rect.height);
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  };
  resize();
  window.addEventListener('resize', resize, { signal: controller.signal });

  const updateHud = () => {
    const timing = game.timing;
    const multiplier = Number(timing.multiplier || 1);
    multiplierLabel.textContent = `×${multiplier.toFixed(2).replace('.', ',')} к выпуску`;
    chargeLabel.textContent = `Заряд: ${timing.charge}/16`;
    streakLabel.textContent = `Серия: ${timing.streak}`;
    progress.style.width = `${Math.min(100, (timing.charge / 16) * 100)}%`;
    tapButton.disabled = game.paused || game.closed || game.pulseBusy || !navigator.onLine;
    if (game.paused || !currentSession?.session_id) {
      mode.textContent = 'Пауза · бонус не накапливается';
      serverActivity.textContent = 'Сессия приостановлена';
      resumeButton.hidden = false;
    } else {
      mode.textContent = `Ритм цеха · ×${multiplier.toFixed(2).replace('.', ',')} · потолок ×5`;
      serverActivity.textContent = game.pulseBusy ? 'Синхронизация с сервером…' : 'Серверная сессия активна';
      resumeButton.hidden = true;
    }
  };

  const syncFromServer = (response, action) => {
    if (response.timing) {
      game.timing = updateTimingGameState(game.timing, response.timing, Date.now());
    }
    if (action === 'tap' && response.tap_result) {
      game.timing.lastResult = response.tap_result;
      task.textContent = resultText[response.tap_result] || resultText.miss;
      if (response.tap_result === 'gold') showToast('Точное попадание · +2 заряда', 'success');
      else if (response.tap_result === 'blue') showToast('Хорошее попадание · +1 заряд', 'success');
    }
    if (typeof response.multiplier_now === 'number') {
      hint.textContent = `Сервер подтвердил ×${response.multiplier_now.toFixed(2).replace('.', ',')}. Максимум ×5; бонус не увеличивает расход ресурсов.`;
    }
    if (Number.isFinite(response.working_facilities) && Number.isFinite(response.total_facilities)) {
      output.textContent = `${response.working_facilities}/${response.total_facilities} заводов работают`;
    }
    game.nextCycleAt = response.nearest_cycle_at || game.nextCycleAt;
    if (!response.active) {
      game.paused = true;
      mode.textContent = 'Сессия истекла · нажми «Продолжить»';
      resumeButton.hidden = false;
    } else if (response.idle_warning) {
      task.textContent = 'Нажми по метке, чтобы сохранить активную смену.';
    }
    updateHud();
  };

  const sendPulse = async (action = 'idle') => {
    if (game.pulseBusy || game.paused || game.closed) return;
    if (!navigator.onLine) {
      mode.textContent = 'Нет связи · активная смена приостановлена';
      hint.textContent = 'Проверь интернет и нажми «Продолжить», чтобы создать новую серверную сессию.';
      game.paused = true;
      updateHud();
      return;
    }
    game.pulseBusy = true;
    const counter = action === 'tap' ? ++game.activityCounter : game.activityCounter;
    updateHud();
    try {
      const response = await api.pulseNextGameActiveProduction({
        session_id: currentSession.session_id,
        session_token: currentSession.session_token,
        sequence: ++pulseSequence,
        scene_action: action,
        user_input_counter: counter,
      });
      syncFromServer(response, action);
    } catch {
      if (action === 'tap') task.textContent = 'Сервер не ответил на удар. Награда без подтверждения не начисляется.';
      mode.textContent = 'Связь потеряна · ждём сервер';
      hint.textContent = 'Мини-игра не меняет склад или баланс на клиенте; подтвердить результат может только сервер.';
    } finally {
      game.pulseBusy = false;
      updateHud();
    }
  };

  const tap = () => {
    if (game.paused || game.closed || game.pulseBusy || !navigator.onLine) return;
    void sendPulse('tap');
  };
  tapButton.addEventListener('click', tap, { signal: controller.signal });
  canvas.addEventListener('pointerdown', (event) => {
    event.preventDefault();
    tap();
  }, { signal: controller.signal });

  const pauseServer = async (reason = 'page_hidden') => {
    if (!currentSession?.session_id || game.closed || game.paused) return;
    game.pauseRequested = true;
    game.paused = true;
    clearInterval(game.pulseTimer);
    cancelAnimationFrame(game.frame);
    updateHud();
    try { await api.pauseNextGameActiveProduction(currentSession.session_id, currentSession.session_token); }
    catch { hint.textContent = 'Сервер временно недоступен. Активная сессия закроется по тайм-ауту.'; }
    if (reason === 'page_hidden') task.textContent = 'Смена остановлена, пока приложение было скрыто. Заряд сохранится.';
  };

  const drawFrame = (timestamp) => {
    if (game.paused || game.closed) return;
    if (timestamp - game.lastCountdown > 1000 && game.nextCycleAt) {
      const seconds = Math.max(0, Math.ceil((Date.parse(game.nextCycleAt) - Date.now()) / 1000));
      cycleLabel.textContent = seconds
        ? `Ближайший производственный цикл примерно через ${Math.ceil(seconds / 60)} мин.`
        : 'Ближайший цикл готов к серверному расчёту';
      game.lastCountdown = timestamp;
    }
    paint(ctx, width, height, scene, game.timing, Date.now());
    game.frame = requestAnimationFrame(drawFrame);
  };
  const startTimers = () => {
    game.frame = requestAnimationFrame(drawFrame);
    game.pulseTimer = window.setInterval(() => void sendPulse('idle'), 15_000);
  };

  const resume = async () => {
    resumeButton.disabled = true;
    game.pauseRequested = false;
    try {
      const resumed = await api.startNextGameActiveProduction(activeSession.selected_branch_id);
      if (game.closed || game.pauseRequested || document.hidden) {
        if (!game.closed) resumeButton.hidden = false;
        try { await api.pauseNextGameActiveProduction(resumed.session_id, resumed.session_token); }
        catch { /* server timeout closes the session if the app was hidden */ }
        return;
      }
      currentSession = resumed;
      pulseSequence = 0;
      game.timing = createTimingGameState(resumed.timing, Date.now());
      game.paused = false;
      task.textContent = 'Золотая зона даёт +2 заряда, синяя +1. Набери 16 зарядов для ×5 выпуска.';
      hint.textContent = 'Повышенный выпуск считает сервер по мини-игре и добавляет его без дополнительного расхода сырья.';
      updateHud();
      startTimers();
      void sendPulse('idle');
    } catch (error) {
      if (!game.closed) showToast(error.message || 'Не удалось возобновить смену', 'error');
    } finally {
      if (!game.closed) resumeButton.disabled = false;
    }
  };
  resumeButton.addEventListener('click', resume, { signal: controller.signal });

  const destroy = async (status = 'PAUSED') => {
    if (game.closed) return;
    game.closed = true;
    clearInterval(game.pulseTimer);
    cancelAnimationFrame(game.frame);
    controller.abort();
    if (currentSession?.session_id) {
      const action = status === 'STOPPED' ? api.stopNextGameActiveProduction : api.pauseNextGameActiveProduction;
      try { await action(currentSession.session_id, currentSession.session_token); }
      catch { /* heartbeat expiry is the fallback */ }
    }
  };
  root.querySelectorAll('[data-active-exit]').forEach((button) => button.addEventListener('click', async () => {
    await destroy('STOPPED');
    onExit?.();
  }, { signal: controller.signal }));
  document.addEventListener('visibilitychange', () => { if (document.hidden) void pauseServer('page_hidden'); }, { signal: controller.signal });
  window.addEventListener('blur', () => { void pauseServer('focus_lost'); }, { signal: controller.signal });
  window.addEventListener('pagehide', () => { void pauseServer('page_hidden'); }, { signal: controller.signal });
  window.addEventListener('offline', () => { void pauseServer('offline'); }, { signal: controller.signal });
  window.addEventListener('online', () => {
    if (!game.paused) return;
    hint.textContent = 'Интернет восстановлен. Нажми «Продолжить», чтобы открыть новую смену.';
    resumeButton.hidden = false;
  }, { signal: controller.signal });

  updateHud();
  startTimers();
  void sendPulse('idle');
  return { destroy };
}
