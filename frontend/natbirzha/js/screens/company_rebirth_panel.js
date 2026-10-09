import { NatAPI } from '../api.js?v=20261009_perf_tuning_v1';
import { store } from '../state.js?v=20260926_local_update_v1';

function node(tag, text, className = '') {
  const element = document.createElement(tag);
  element.textContent = text;
  element.className = className;
  return element;
}

export async function renderCompanyRebirthPanel(container, showToast, onBack) {
  const wrapper = node('div', '', 'max-w-md mx-auto p-4 pb-24 space-y-3');
  const back = node('button', '← Обзор', 'text-sm text-rose-400');
  back.addEventListener('click', onBack);
  wrapper.append(back, node('h2', '🌅 Перерождение', 'text-xl font-black'));
  const body = node('div', 'Загружаем условия…', 'glass-card rounded-2xl p-4 space-y-3');
  wrapper.append(body);
  container.replaceChildren(wrapper);
  try {
    const status = await NatAPI.getRebirthStatus();
    if (!wrapper.isConnected) return;
    body.replaceChildren(
      node('p', `Перерождений: ${status.count}/${status.max_count} · бонус производства: +${status.bonus_pct}%`, 'font-bold'),
      node('p', `После следующего перерождения: +${status.next_bonus_pct}% к выпуску товаров. Расход сырья не растёт.`, 'text-sm'),
      node('p', `Сбрасываются: ${status.reset}.`, 'text-sm text-rose-400'),
      node('p', `Сохраняются: ${status.preserved}.`, 'text-sm text-emerald-400'),
      node('p', 'Налоги, включая начисленные за текущие сутки, закрываются из прежнего баланса перед сбросом.', 'text-xs text-slate-400'),
    );
    if (status.next_factory) body.append(node('p', `Новая ступень: ${status.next_factory}. Она станет доступна в новой жизни после достижения 60 уровня и выполнения требований предыдущего завода.`, 'text-sm'));
    for (const reason of status.reasons || []) body.append(node('p', `• ${reason}`, 'text-xs text-amber-400'));
    const button = node('button', 'Начать новую жизнь', 'w-full rounded-xl bg-indigo-600 text-white p-3 font-bold disabled:opacity-50');
    button.disabled = !status.available;
    button.addEventListener('click', async () => {
      if (!confirm(`Перерождение сбросит: ${status.reset}. Сохранятся: ${status.preserved}. Это действие нельзя отменить. Продолжить?`)) return;
      button.disabled = true;
      try {
        const result = await NatAPI.rebirthCompany(status.count);
        store.setCompany(await NatAPI.getMyCompany());
        showToast(`Перерождение ${result.rebirth_count}: +${result.production_bonus_pct}% производства`, 'success');
        onBack();
      } catch (error) {
        showToast(error.message, 'error');
        button.disabled = false;
      }
    });
    body.append(button);
  } catch (error) {
    if (wrapper.isConnected) body.textContent = error.message;
  }
}
