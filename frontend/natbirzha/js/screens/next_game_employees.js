/** Employee collection and PVC case screen for NATBIRZHA 2.0. */

const RARITY_LABELS = {
  common: 'Обычный',
  rare: 'Редкий',
  epic: 'Эпический',
  legendary: 'Легендарный',
};

const RARITY_CLASSES = {
  common: 'is-common',
  rare: 'is-rare',
  epic: 'is-epic',
  legendary: 'is-legendary',
};

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));
}

function formatNumber(value, digits = 0) {
  return Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: digits });
}

function oddsPercent(probability) {
  return `${formatNumber(Number(probability || 0) * 100, 2)}%`;
}

export function renderEmployeeCard(employee) {
  const rarity = employee.rarity || 'common';
  const source = employee.source === 'milestone' ? 'Награда за уровень компании' : 'Сотрудник из кейса';
  const assignment = employee.branch_id
    ? '<span class="ng-employee-assignment">Назначен на завод</span>'
    : '<span class="ng-employee-assignment is-free">Свободен</span>';
  const removal = employee.source === 'case' && !employee.facility_id
    ? `<button type="button" class="ng-employee-delete" data-employee-delete="${Number(employee.id)}">Удалить</button>`
    : employee.source === 'milestone'
      ? '<small class="ng-employee-protected">Награда за уровень · нельзя удалить</small>'
      : '<small class="ng-employee-protected">Сначала снимите назначение на заводе</small>';
  return `<article class="ng-employee-card ${RARITY_CLASSES[rarity] || RARITY_CLASSES.common}" data-employee-card="${Number(employee.id)}">
    <div class="ng-employee-card-top"><span class="ng-employee-level">УР. ${formatNumber(employee.level, 0)}</span><span class="ng-employee-rarity">${esc(RARITY_LABELS[rarity] || rarity)}</span></div>
    <h3>${esc(employee.name)}</h3><p class="ng-employee-source">${source}</p>
    <div class="ng-employee-output-bonus"><b>+${formatNumber(employee.production_bonus_pct, 0)}%</b><span>к выпуску завода за цикл</span></div>
    ${assignment}<div class="ng-employee-card-actions">${removal}</div>
  </article>`;
}

export function renderEmployeeInventory(data = {}) {
  const caseInfo = data.case || { price_pvc: 25, odds: [] };
  const employees = data.employees || [];
  const cards = employees.map(renderEmployeeCard).join('');
  const odds = (caseInfo.odds || []).map((row) => `<li class="ng-employee-odds-row ${RARITY_CLASSES[row.rarity] || ''}">
    <span><b>${esc(RARITY_LABELS[row.rarity] || row.rarity)}</b><small>уровни ${formatNumber(row.level_min)}–${formatNumber(row.level_max)} · +${formatNumber(row.production_bonus_pct)}% к выпуску</small></span>
    <strong>${oddsPercent(row.probability)}</strong>
  </li>`).join('');
  const affordable = Number(data.pvc_balance || 0) >= Number(caseInfo.price_pvc || 25);
  return `<section class="next-game-view-heading ng-employee-heading"><div class="next-game-view-heading-top"><button type="button" data-next-view="more" class="next-game-back">← Ещё</button><span>КОМАНДА · NATBIRZHA 2.0</span></div><div class="next-game-view-title"><span aria-hidden="true">♙</span><div><h2>Сотрудники</h2><small>Коллекция специалистов и кейсы за PVC</small></div></div></section>
  <section class="next-game-panel ng-employee-case-panel"><div class="ng-employee-case-copy"><span class="ng-employee-eyebrow">КЕЙС СПЕЦИАЛИСТОВ</span><h3>Открой нового сотрудника</h3><p>Назначьте сотрудника на завод: он повысит выпуск на 8–10% за цикл. Расход cash и потребление сырья не меняются.</p><div class="ng-employee-wallet">Баланс <b data-employee-wallet>${formatNumber(data.pvc_balance, 2)} PVC</b></div></div>
    <div class="ng-employee-case-action"><div class="ng-employee-case-art" data-case-reveal aria-live="polite"><span class="ng-employee-case-vault" data-case-motion aria-hidden="true"><i class="ng-employee-case-lid"></i><i class="ng-employee-case-body"><b></b></i></span><small data-case-caption>Содержимое откроется после оплаты</small></div><button type="button" class="next-game-primary ng-employee-open" data-employee-case-open ${affordable ? '' : 'disabled'}>Открыть за ${formatNumber(caseInfo.price_pvc)} PVC</button><p class="ng-employee-case-error" data-case-error role="status" hidden></p></div>
  </section>
  <section class="next-game-panel ng-employee-odds-panel"><div class="ng-employee-section-heading"><div><span class="ng-employee-eyebrow">ЧЕСТНЫЕ ШАНСЫ</span><h3>Вероятность и бонус</h3></div><b>${formatNumber(caseInfo.price_pvc)} PVC / кейс</b></div><p>Шансы указаны для каждого открытия. Редкость определяет уровень и бонус к выпуску.</p><ul class="ng-employee-odds">${odds || '<li>Нет данных о шансах кейса</li>'}</ul></section>
  <section class="next-game-panel ng-employee-inventory-panel"><div class="ng-employee-section-heading"><div><span class="ng-employee-eyebrow">ВАША КОМАНДА</span><h3>Инвентарь сотрудников</h3></div><b data-employee-count>${employees.length} шт.</b></div><p>Гарантированные сотрудники выдаются на уровнях компании 5, 15, 30 и 45. Их нельзя удалить.</p><div class="ng-employee-grid" data-employee-list>${cards || '<p class="ng-employee-empty">Сотрудники появятся после достижения уровня или открытия кейса.</p>'}</div></section>`;
}

async function waitForCaseAnimation(element) {
  const shortWait = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));
  if (typeof window === 'undefined' || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
    return shortWait(180);
  }
  // Let the browser apply the opening class before asking for its CSS animations.
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  const animations = element?.getAnimations?.().filter((animation) => animation.playState !== 'finished') || [];
  // The CSS flare has a 950 ms delay and runs for 620 ms after the rattle.
  // Keep a matching fallback for browsers that do not expose CSSAnimation objects.
  if (!animations.length) return shortWait(1650);
  const finished = Promise.all(animations.map((animation) => animation.finished.catch(() => undefined)));
  return Promise.race([finished, shortWait(2200)]);
}

export function bindEmployeeActions(container, api, showToast) {
  const openButton = container.querySelector('[data-employee-case-open]');
  openButton?.addEventListener('click', async () => {
    openButton.disabled = true;
    const reveal = container.querySelector('[data-case-reveal]');
    const motion = container.querySelector('[data-case-motion]');
    const caption = container.querySelector('[data-case-caption]');
    const error = container.querySelector('[data-case-error]');
    if (error) error.hidden = true;
    reveal?.classList.add('is-opening');
    if (caption) caption.textContent = 'Кейс открывается…';
    try {
      const [result] = await Promise.all([
        api.openNextGameEmployeeCase(),
        waitForCaseAnimation(motion),
      ]);
      const employee = result.employee;
      if (reveal) {
        reveal.classList.remove('is-opening');
        reveal.classList.add('is-revealed');
        reveal.innerHTML = `<span class="ng-employee-drop-icon" aria-hidden="true">✦</span><b>${esc(employee.name)}</b><small>${esc(RARITY_LABELS[employee.rarity] || employee.rarity)} · ур. ${formatNumber(employee.level)}</small>`;
      }
      const wallet = container.querySelector('[data-employee-wallet]');
      if (wallet) wallet.textContent = `${formatNumber(result.pvc_balance, 2)} PVC`;
      const list = container.querySelector('[data-employee-list]');
      list?.querySelector('.ng-employee-empty')?.remove();
      list?.insertAdjacentHTML('afterbegin', renderEmployeeCard(employee));
      const count = container.querySelector('[data-employee-count]');
      if (count) count.textContent = `${list?.querySelectorAll('[data-employee-card]').length || 1} шт.`;
      openButton.disabled = Number(result.pvc_balance) < Number(result.paid_pvc);
      openButton.textContent = `Открыть за ${formatNumber(result.paid_pvc)} PVC`;
      showToast(`Новый сотрудник: ${employee.name} · ${RARITY_LABELS[employee.rarity] || employee.rarity}`, 'success');
    } catch (requestError) {
      reveal?.classList.remove('is-opening');
      if (caption) caption.textContent = 'Кейс не открыт';
      if (error) {
        error.textContent = requestError.message || 'Не удалось открыть кейс';
        error.hidden = false;
      }
      showToast(requestError.message || 'Не удалось открыть кейс', 'error');
      openButton.disabled = false;
    }
  });

  container.querySelectorAll('[data-employee-delete]').forEach((button) => {
    button.addEventListener('click', async () => {
      const card = button.closest('[data-employee-card]');
      if (!card) return;
      if (!window.confirm(`Удалить сотрудника «${card.querySelector('h3')?.textContent || ''}»?`)) return;
      button.disabled = true;
      try {
        await api.deleteNextGameEmployee(Number(button.dataset.employeeDelete));
        card.remove();
        const list = container.querySelector('[data-employee-list]');
        const count = container.querySelector('[data-employee-count]');
        const remaining = list?.querySelectorAll('[data-employee-card]').length || 0;
        if (count) count.textContent = `${remaining} шт.`;
        if (list && !remaining) {
          list.innerHTML = '<p class="ng-employee-empty">Сотрудники появятся после достижения уровня или открытия кейса.</p>';
        }
        showToast('Сотрудник удалён', 'success');
      } catch (requestError) {
        showToast(requestError.message || 'Не удалось удалить сотрудника', 'error');
        button.disabled = false;
      }
    });
  });
}

export async function renderNextGameEmployees(container, showToast, api = window.NatAPI) {
  container.innerHTML = '<section class="next-game-panel"><p role="status">Загружаем команду…</p></section>';
  try {
    const data = await api.getNextGameEmployees();
    container.innerHTML = renderEmployeeInventory(data);
    bindEmployeeActions(container, api, showToast);
    return data;
  } catch (error) {
    container.innerHTML = `<section class="next-game-panel"><h2>Сотрудники</h2><p role="alert">${esc(error.message || 'Не удалось загрузить сотрудников')}</p><button type="button" data-employee-retry class="next-game-secondary">Повторить</button></section>`;
    container.querySelector('[data-employee-retry]')?.addEventListener('click', () => {
      void renderNextGameEmployees(container, showToast, api);
    });
    return null;
  }
}
