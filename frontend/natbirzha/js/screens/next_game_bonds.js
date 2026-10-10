import { NatAPI } from '../api.js?v=20261010_shell_v2';
import { esc, number, icon } from './next_game_common.js?v=20261010_shell_v2';

const requests = new WeakMap();
const date = (value) => new Date(value).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' });

export async function renderNextGameBonds(container, state, showToast, refresh) {
  const api = state.nextGameAPI || NatAPI;
  const view = state.bondBrowser ||= { seriesId: null, listingId: null };
  const token = {};
  requests.set(container, token);
  container.innerHTML = '<section class="next-game-panel"><p role="status">Загружаем облигации…</p></section>';
  try {
    const data = await api.getNextGameBonds();
    if (requests.get(container) !== token) return;
    render(data);
  } catch (error) {
    if (requests.get(container) !== token) return;
    container.innerHTML = `<section class="next-game-panel"><h2>Облигации</h2><p role="alert">${esc(error.message)}</p><button type="button" data-bond-retry class="next-game-primary">Повторить</button></section>`;
    container.querySelector('[data-bond-retry]')?.addEventListener('click', () => renderNextGameBonds(container, state, showToast, refresh));
  }
  function render(data) {
    const selected = data.series.find((row) => Number(row.id) === Number(view.seriesId));
    if (!selected) {
      container.innerHTML = `<section class="next-game-panel"><button type="button" data-bond-bank class="next-game-back">← Банк</button><h2>${icon('bank')} Облигации</h2>
        <p>Резервный банк платит купоны каждый час, а при погашении возвращает номинал. Облигации можно продать другой компании.</p>
        <p class="next-game-bank-note">На счёте ${number(data.cash)} cash · в портфеле ${number(data.holdings.reduce((sum, row) => sum + row.units, 0), 0)} облигаций</p>
        <div class="next-game-simple-list">${data.series.map((row) => `<button type="button" data-bond-series="${Number(row.id)}" class="next-game-bank-account"><span><b>${esc(row.name)}</b><small>${number(row.daily_rate * 100, 1)}% за сутки · номинал ${number(row.face_price)} cash</small></span><span>›</span></button>`).join('')}</div>
      </section>`;
      container.querySelector('[data-bond-bank]')?.addEventListener('click', () => state.navigateNextGame?.('bank'));
      container.querySelectorAll('[data-bond-series]').forEach((button) => button.addEventListener('click', () => {
        view.seriesId = Number(button.dataset.bondSeries); view.listingId = null; render(data);
      }));
      return;
    }
    const holdings = data.holdings.filter((row) => row.series_id === selected.id);
    const listings = data.listings.filter((row) => row.series_id === selected.id);
    const offer = listings.find((row) => row.id === Number(view.listingId) && !row.mine);
    const free = holdings.filter((row) => row.free_units > 0);
    container.innerHTML = `<section class="next-game-panel"><button type="button" data-bond-back class="next-game-back">← Все серии</button><h2>${esc(selected.name)}</h2>
      <p>Эмитент: ${esc(selected.issuer)} · ${number(selected.daily_rate * 100, 1)}% за сутки · срок ${selected.term_days} дней</p>
      <p class="next-game-bank-note">Номинал ${number(selected.face_price)} cash. Купоны начисляются текущему владельцу автоматически. Проценты не получают производственные бонусы.</p>
      <form data-bond-primary class="next-game-bank-loan"><h3>Купить у резервного банка</h3><label>Количество<input name="units" type="number" min="1" max="10000" step="1" value="10" required /></label>
        <button class="next-game-primary">Купить по номиналу</button></form>
      <article class="next-game-bank-loan"><h3>Мой портфель</h3>${holdings.length ? holdings.map((row) => `<div class="next-game-bank-account"><span><b>${row.units} шт. · свободно ${row.free_units}</b><small>Погашение ${esc(date(row.matures_at))}</small><small>Купоны получены ${number(row.coupon_paid, 8)} cash · следующий ${esc(date(row.next_coupon_at))}</small></span></div>`).join('') : '<p>Этой серии в портфеле пока нет.</p>'}
        ${free.length ? `<form data-bond-list><h4>Продать на вторичном рынке</h4><label>Пакет<select name="holding_id">${free.map((row) => `<option value="${row.id}">${row.free_units} шт. · до ${esc(date(row.matures_at))}</option>`).join('')}</select></label>
          <label>Количество<input name="units" type="number" min="1" max="10000" step="1" value="1" required /></label><label>Цена за облигацию, cash<input name="unit_price" type="number" min="0.0001" step="0.0001" value="${selected.face_price}" required /></label><button class="next-game-secondary">Выставить предложение</button></form>` : ''}
      </article>
      <article class="next-game-bank-loan"><h3>Вторичный рынок</h3>${listings.length ? listings.map((row) => `<div class="next-game-bank-account"><span><b>${esc(row.seller_name)} · ${number(row.unit_price, 4)} cash</b><small>${row.units} шт. · погашение ${esc(date(row.matures_at))}</small></span>
        ${row.mine ? `<button type="button" data-bond-cancel="${row.id}" class="next-game-secondary">Снять</button>` : `<button type="button" data-bond-offer="${row.id}" class="next-game-secondary">Купить</button>`}</div>`).join('') : '<p>Открытых предложений пока нет.</p>'}
        ${offer ? `<form data-bond-secondary><p>Покупка у ${esc(offer.seller_name)} по ${number(offer.unit_price, 4)} cash. Срок погашения сохраняется.</p><label>Количество<input name="units" type="number" min="1" max="${offer.units}" step="1" value="1" required /></label><button class="next-game-primary">Купить выбранные облигации</button></form>` : ''}
      </article>
    </section>`;
    container.querySelector('[data-bond-back]')?.addEventListener('click', () => { view.seriesId = null; view.listingId = null; render(data); });
    let busy = false;
    async function mutate(action) {
      if (busy) return;
      busy = true;
      container.querySelectorAll('button,input,select').forEach((element) => { element.disabled = true; });
      try {
        await action(); showToast('Операция выполнена', 'success');
        if (refresh) await refresh(); else await renderNextGameBonds(container, state, showToast);
      } catch (error) { showToast(error.message || 'Не удалось выполнить операцию', 'error'); }
      finally { busy = false; container.querySelectorAll('button,input,select').forEach((element) => { element.disabled = false; }); }
    }
    const bindForm = (selector, action) => container.querySelector(selector)?.addEventListener('submit', (event) => {
      event.preventDefault(); const values = new FormData(event.currentTarget); void mutate(() => action(values));
    });
    bindForm('[data-bond-primary]', (values) => api.buyNextGameBonds(selected.id, Number(values.get('units'))));
    bindForm('[data-bond-list]', (values) => api.listNextGameBonds(Number(values.get('holding_id')), Number(values.get('units')), Number(values.get('unit_price'))));
    bindForm('[data-bond-secondary]', (values) => api.buyNextGameBondListing(offer.id, Number(values.get('units'))));
    container.querySelectorAll('[data-bond-offer]').forEach((button) => button.addEventListener('click', () => { view.listingId = Number(button.dataset.bondOffer); render(data); }));
    container.querySelectorAll('[data-bond-cancel]').forEach((button) => button.addEventListener('click', () => void mutate(() => api.cancelNextGameBondListing(Number(button.dataset.bondCancel)))));
  }
}
