import { NatAPI } from '../api.js?v=20261010_active_production_v1';
import { esc, number } from './next_game_common.js?v=20261010_shell_v2';

const requests = new WeakMap();

export async function renderNextGameBankruptcy(container, state, toast, refresh) {
  const api = state.nextGameAPI || NatAPI;
  const token = {}; requests.set(container, token);
  container.innerHTML = '<section class="next-game-panel"><p role="status">Загружаем решение о банкротстве…</p></section>';
  try {
    const data = await api.getNextGameRecovery();
    if (requests.get(container) !== token) return;
    if (!data.requires_ack) {
      container.innerHTML = '<section class="next-game-panel"><h2>Восстановление компании</h2><p>Компания может продолжать работу.</p><button data-recovery-return class="next-game-primary">К компании</button></section>';
      container.querySelector('[data-recovery-return]')?.addEventListener('click', () => refresh ? refresh() : state.navigateNextGame?.('overview'));
      return;
    }
    container.innerHTML = `<section class="next-game-panel" role="alert"><h2>ВЫ БАНКРОТ</h2><p>${esc(data.note)}</p>
      <p>Имущество передано резервному банку. Заводы выставлены на продажу, долги списаны. Права внешних акционеров компании сохранены.</p>
      <article class="next-game-bank-loan"><h3>Начать заново</h3><p>Новый старт: ${number(data.restart_grant || 100000)} cash из резервного банка. Уровень и маршрут будут сброшены. PVC и число перерождений сохраняются.</p>
      <button data-recovery-restart class="next-game-primary" ${data.can_restart ? '' : 'disabled'}>Перезапуск · +${number(data.restart_grant || 100000)} cash</button>
      ${data.can_restart ? '' : '<p>В резерве пока недостаточно свободных средств.</p>'}</article>
      <article class="next-game-bank-loan"><h3>Продолжить</h3><p>Текущий уровень и маршрут сохранятся. Изъятое имущество не возвращается, новый капитал не выдается.</p><button data-recovery-continue class="next-game-secondary">Продолжить с текущим маршрутом</button></article>
      <details><summary>Списанные обязательства</summary>${(data.writeoffs || []).map((row) => `<p>${esc(row.kind)} #${row.id}: ${number(row.amount, 2)} cash</p>`).join('') || '<p>Обязательств не было.</p>'}</details></section>`;
    let busy = false;
    async function recover(restart) {
      if (busy) return; busy = true;
      container.querySelectorAll('button').forEach((button) => { button.disabled = true; });
      try { await api.recoverNextGameCompany(restart); toast('Решение принято', 'success'); await refresh?.(); }
      catch (error) { toast(error.message || 'Не удалось восстановить компанию', 'error'); await renderNextGameBankruptcy(container, state, toast, refresh); }
      finally { busy = false; }
    }
    container.querySelector('[data-recovery-restart]')?.addEventListener('click', () => void recover(true));
    container.querySelector('[data-recovery-continue]')?.addEventListener('click', () => void recover(false));
  } catch (error) {
    if (requests.get(container) !== token) return;
    container.innerHTML = `<section class="next-game-panel"><h2>Восстановление компании</h2><p role="alert">${esc(error.message)}</p><button data-recovery-retry class="next-game-primary">Повторить</button></section>`;
    container.querySelector('[data-recovery-retry]')?.addEventListener('click', () => renderNextGameBankruptcy(container, state, toast, refresh));
  }
}
