import { NatAPI } from './api.js?v=20261010_theme_auto_upgrade_next_game_v1';

function paint(button, enabled) {
  button.setAttribute('aria-pressed', String(enabled));
  button.innerHTML = `<span>Автопрокачка</span><b>${enabled ? 'Включена · до 9 ур.' : 'Выключена'}</b><small>Требуются cash и ресурсы; закупать их система не будет</small>`;
  button.classList.toggle('auto-upgrade-enabled', enabled);
}

export function mountAutoUpgradeToggle(statGrid, summary, showToast = () => {}) {
  if (!statGrid) return null;
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'tycoon-stat auto-upgrade-toggle';
  const enabled = Boolean(summary?.auto_upgrade_to_nine_enabled);
  paint(button, enabled);
  button.addEventListener('click', async () => {
    const next = button.getAttribute('aria-pressed') !== 'true';
    button.disabled = true;
    try {
      const result = await NatAPI.setAutoUpgradeToNine(next);
      const saved = Boolean(result?.enabled);
      summary.auto_upgrade_to_nine_enabled = saved;
      paint(button, saved);
      showToast(saved ? 'Автопрокачка включена до 9 уровня' : 'Автопрокачка выключена', 'success');
    } catch (error) {
      showToast(error?.message || 'Не удалось изменить настройку', 'error');
    } finally {
      button.disabled = false;
    }
  });
  statGrid.append(button);
  return button;
}
