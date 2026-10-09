import { NatAPI } from '../api.js?v=20261010_theme_auto_upgrade_next_game_v1';

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));
}

function icon(name, size = 22) {
  return window.NatIcons?.icon?.(name, size) || '';
}

function header(company) {
  return `<header class="next-game-header"><div class="next-game-kicker">ИЗОЛИРОВАННЫЙ ТЕСТ · ТОЛЬКО АДМИНЫ</div><h1>НАТБИРЖА 2.0</h1><p>Новая игра собирается рядом с действующей. Здесь отдельная компания и отдельное сохранение.</p>${company ? `<div class="next-game-company"><b>${esc(company.name)}</b><span>${Number(company.cash || 0).toLocaleString('ru-RU')} тестовых cash</span></div>` : ''}</header>`;
}

function renderCompanyForm(container, showToast) {
  container.innerHTML = `<div class="next-game-screen space-y-4 max-w-md mx-auto p-4 pb-24">${header(null)}<section class="next-game-panel"><h2>Начать тест 2.0</h2><p>Создай отдельную тестовую компанию. Баланс старой игры останется прежним.</p><label for="next-game-company-name">Название компании</label><input id="next-game-company-name" maxlength="80" minlength="2" value="Новая корпорация" /><button id="next-game-create" type="button" class="next-game-primary">Создать компанию</button></section></div>`;
  container.querySelector('#next-game-create')?.addEventListener('click', async (event) => {
    const button = event.currentTarget;
    const name = container.querySelector('#next-game-company-name')?.value?.trim();
    if (!name || name.length < 2) return showToast('Название должно быть не короче двух символов', 'error');
    button.disabled = true;
    try {
      await NatAPI.createNextGameCompany(name);
      showToast('Тестовая компания создана', 'success');
      await renderNextGame(container, showToast);
    } catch (error) {
      showToast(error.message, 'error');
      button.disabled = false;
    }
  });
}

function renderSectorMap(container, state, showToast) {
  const company = state.company;
  const selectedSector = state.corporations.find((item) => item.id === company.sector_id);
  const selectedBranch = selectedSector?.branches.find((item) => item.id === company.branch_path?.[0]);
  const cards = state.corporations.map((sector) => {
    const chosen = sector.id === company.sector_id;
    const branches = sector.branches.map((branch) => {
      const branchChosen = company.branch_path?.[0] === branch.id;
      const canChoose = chosen && !company.branch_path?.length;
      return `<article class="next-game-branch ${branchChosen ? 'is-selected' : ''}"><div><b>${esc(branch.name)}</b><p>${esc(branch.outputs)}</p></div>${canChoose ? `<button type="button" data-branch="${esc(branch.id)}">Выбрать путь</button>` : branchChosen ? '<span class="next-game-choice">Выбрано</span>' : '<span class="next-game-locked">После открытия ветки</span>'}${branchChosen ? `<div class="next-game-future"><span>Дальнейшая развилка</span>${branch.future_choices.map((choice) => `<i>${esc(choice)}</i>`).join('')}</div>` : ''}</article>`;
    }).join('');
    const canChooseSector = !company.sector_id;
    const sectorAction = canChooseSector
      ? `<button type="button" data-sector="${esc(sector.id)}" class="next-game-secondary">Выбрать корпорацию</button>`
      : chosen ? '<span class="next-game-choice">Ваша корпорация</span>' : '<span class="next-game-locked">Закрыто в тесте</span>';
    return `<section class="next-game-sector ${chosen ? 'is-selected' : ''}"><div class="next-game-sector-heading"><span class="next-game-icon">${icon(sector.icon)}</span><div><h2>${esc(sector.name)}</h2><p>${esc(sector.description)}</p></div></div>${sectorAction}${chosen ? `<div class="next-game-branches">${branches}</div>` : ''}</section>`;
  }).join('');
  container.innerHTML = `<div class="next-game-screen space-y-4 max-w-md mx-auto p-4 pb-24">${header(company)}<section class="next-game-map-intro"><b>Карта развития</b><span>${selectedBranch ? `Путь: ${esc(selectedSector.name)} → ${esc(selectedBranch.name)}` : selectedSector ? `Выбери первую ветку корпорации «${esc(selectedSector.name)}»` : 'Выбери одну из семи стартовых корпораций'}</span></section><div class="next-game-sector-list">${cards}</div><p class="next-game-footnote">Пока доступны стартовый выбор и первая развилка. Следующие шаги показаны на карте и будут открываться в следующих этапах 2.0.</p></div>`;
  container.querySelectorAll('[data-sector]').forEach((button) => button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      await NatAPI.selectNextGameSector(button.dataset.sector);
      await renderNextGame(container, showToast);
    } catch (error) {
      showToast(error.message, 'error');
      button.disabled = false;
    }
  }));
  container.querySelectorAll('[data-branch]').forEach((button) => button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      await NatAPI.selectNextGameBranch(button.dataset.branch);
      showToast('Ветка сохранена в тестовом мире 2.0', 'success');
      await renderNextGame(container, showToast);
    } catch (error) {
      showToast(error.message, 'error');
      button.disabled = false;
    }
  }));
}

export async function renderNextGame(container, showToast = () => {}) {
  container.innerHTML = '<div class="next-game-screen p-6 text-center">Загружаем отдельный мир 2.0…</div>';
  try {
    const state = await NatAPI.getNextGameMap();
    if (!state.company) renderCompanyForm(container, showToast);
    else renderSectorMap(container, state, showToast);
  } catch (error) {
    container.innerHTML = `<div class="next-game-screen p-6"><section class="next-game-panel"><h1>НАТБИРЖА 2.0</h1><p>Не удалось открыть тестовый мир: ${esc(error.message)}</p><button type="button" id="next-game-retry" class="next-game-primary">Повторить</button></section></div>`;
    container.querySelector('#next-game-retry')?.addEventListener('click', () => renderNextGame(container, showToast));
  }
}
