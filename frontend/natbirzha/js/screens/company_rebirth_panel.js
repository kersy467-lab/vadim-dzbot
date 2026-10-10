import { NatAPI } from '../api.js?v=20261010_active_production_v1';
import { store } from '../state.js?v=20260926_local_update_v1';

function node(tag, text, className = '') {
  const element = document.createElement(tag);
  element.textContent = text;
  element.className = className;
  return element;
}

const pct = (value) => Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: 2 });
const factor = (value) => Number(value || 1).toLocaleString('ru-RU', { maximumFractionDigits: 4 });

export async function renderCompanyRebirthPanel(container, showToast, onBack) {
  const wrapper = node('div', '', 'max-w-md mx-auto p-4 pb-24 space-y-3');
  const back = node('button', '← Обзор', 'min-h-10 text-sm font-semibold text-emerald-800');
  back.addEventListener('click', onBack);
  wrapper.append(back, node('h2', 'Перерождение', 'text-xl font-black text-slate-900'));
  const body = node('div', 'Загружаем условия…', 'glass-card rounded-2xl p-4 space-y-3');
  wrapper.append(body);
  container.replaceChildren(wrapper);

  try {
    const status = await NatAPI.getRebirthStatus();
    if (!wrapper.isConnected) return;
    body.replaceChildren();

    const summary = node('section', '', 'rounded-2xl border p-4 shadow-sm');
    summary.style.setProperty('background', '#eef7f1', 'important');
    summary.style.setProperty('border-color', '#b8d5c2', 'important');
    summary.style.setProperty('color', '#173b2f', 'important');
    summary.append(
      node('div', `Перерождений: ${status.count}/${status.max_count}`, 'text-lg font-black'),
      node('p', `Перерождения дают ${pct(status.total_pct)}% базового выпуска (×${factor(status.multiplier)}; бонус +${pct(status.bonus_pct)}%). После следующего: ${pct(status.next_total_pct)}% от базы (×${factor(status.next_multiplier)}). Расход сырья не растёт.`, 'mt-1 text-sm leading-relaxed'),
      node('p', `Прокачка отрасли за PVC: +${pct(status.pvc_bonus_pct)}%. Сейчас вместе с перерождениями: ${pct(status.combined_total_pct)}% от базы (×${factor(Number(status.combined_total_pct || 100) / 100)}); после следующего перерождения: ${pct(status.next_combined_total_pct)}%. Мастерство и улучшения заводов считаются отдельно.`, 'mt-2 text-xs leading-relaxed'),
      node('p', 'Акции и дивиденды сохраняются. Котировка сбрасывается на 99%; инвесторы могут продать акции через обычную биржу. Облигации списываются, их стоимость остаётся в казне.', 'mt-2 text-xs leading-relaxed'),
    );
    for (const textNode of summary.querySelectorAll('p')) {
      textNode.style.setProperty('color', '#334155', 'important');
    }
    body.append(summary);

    const announceCard = node('section', '', 'rounded-2xl border border-amber-200 bg-amber-50/80 p-3');
    announceCard.append(node('div', 'Объявление игрокам', 'text-sm font-black text-amber-950'));
    if (status.announcement_sent) {
      announceCard.append(node('p', 'Объявление уже отправлено для этого этапа перерождения.', 'mt-1 text-xs text-slate-700'));
    } else if (status.announcement_available) {
      announceCard.append(
        node('p', 'Игроки получат личное сообщение о падении цены акций и продолжении дивидендов.', 'mt-1 text-xs leading-relaxed text-slate-700'),
      );
      const announceButton = node('button', 'Отправить объявление', 'mt-3 min-h-11 w-full rounded-xl bg-amber-500 px-3 py-2 text-sm font-black text-slate-950 disabled:opacity-50');
      announceButton.addEventListener('click', async () => {
        announceButton.disabled = true;
        try {
          const result = await NatAPI.announceRebirth(status.count);
          showToast(`Объявление: доставлено ${result.delivered} из ${result.recipient_count}, ошибок ${result.failed}.`, result.failed ? 'info' : 'success');
          await renderCompanyRebirthPanel(container, showToast, onBack);
        } catch (error) {
          showToast(error.message, 'error');
          announceButton.disabled = false;
        }
      });
      announceCard.append(announceButton);
    } else {
      announceCard.append(node('p', `Кнопка объявления появится после открытия предприятия «${status.announcement_gate_name}».`, 'mt-1 text-xs text-slate-700'));
    }
    body.append(announceCard);

    const rebirthButton = node('button', status.available ? 'Начать новую жизнь' : 'Перерождение пока недоступно', `w-full min-h-12 rounded-xl p-3 font-black shadow-sm disabled:cursor-not-allowed disabled:opacity-100 ${status.available ? 'bg-emerald-800 text-white' : 'border border-slate-300 bg-slate-100 text-slate-700'}`);
    rebirthButton.disabled = !status.available;
    rebirthButton.addEventListener('click', async () => {
      if (!confirm(`Перерождение сбросит: ${status.reset}. Сохранятся: ${status.preserved}. Это действие нельзя отменить. Продолжить?`)) return;
      rebirthButton.disabled = true;
      try {
        const result = await NatAPI.rebirthCompany(status.count);
        store.setCompany(await NatAPI.getMyCompany());
        const stockText = result.stock_rebase
          ? ` Цена акций: ${Number(result.stock_rebase.price_before).toLocaleString('ru-RU')} → ${Number(result.stock_rebase.price_after).toLocaleString('ru-RU')}.`
          : '';
        showToast(`Перерождение ${result.rebirth_count}: выпуск ${pct(result.production_multiplier_pct)}% от базы (бонус +${pct(result.production_bonus_pct)}%).${stockText}`, 'success');
        onBack();
      } catch (error) {
        showToast(error.message, 'error');
        rebirthButton.disabled = false;
      }
    });
    body.append(rebirthButton);

    for (const reason of status.reasons || []) {
      body.append(node('p', `• ${reason}`, 'text-xs text-amber-800'));
    }
    if (status.next_factory) {
      body.append(node('p', `Следующая ступень: ${status.next_factory}. Она станет доступна в новой жизни после достижения 60 уровня и выполнения требований предыдущего завода.`, 'text-sm leading-relaxed text-slate-700'));
    }
    body.append(node('p', 'Налоги, начисленные за текущие сутки, закрываются из прежнего баланса перед сбросом.', 'text-xs text-slate-500'));
  } catch (error) {
    if (wrapper.isConnected) body.textContent = error.message;
  }
}
