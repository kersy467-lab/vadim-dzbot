import { NatAPI } from '../api.js?v=20261009_rebirth_v1';
import { store } from '../state.js?v=20260926_local_update_v1';

function node(tag, text, className = '') {
  const element = document.createElement(tag);
  element.textContent = text;
  element.className = className;
  return element;
}

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

    const summary = node('section', '', 'rounded-2xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-white p-4 shadow-sm');
    summary.append(
      node('div', `Перерождений: ${status.count}/${status.max_count}`, 'text-lg font-black text-emerald-950'),
      node('p', `Сейчас: +${status.bonus_pct}% к выпуску товаров. После следующего перерождения: +${status.next_bonus_pct}%, без роста расхода сырья.`, 'mt-1 text-sm leading-relaxed text-slate-700'),
      node('p', 'Акции и дивиденды сохраняются. Котировка сбрасывается на 99%; инвесторы могут продать акции через обычную биржу. Облигации списываются, их стоимость остаётся в казне.', 'mt-2 text-xs leading-relaxed text-slate-600'),
    );
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

    const rebirthButton = node('button', status.available ? 'Начать новую жизнь' : 'Перерождение пока недоступно', 'w-full min-h-12 rounded-xl bg-gradient-to-r from-emerald-700 to-emerald-500 p-3 font-black text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-50');
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
        showToast(`Перерождение ${result.rebirth_count}: +${result.production_bonus_pct}% производства.${stockText}`, 'success');
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
