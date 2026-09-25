import { NatAPI } from '../api.js?v=20260925_energy_mechanic_v5_energy_mechanic_v5';
import { store } from '../state.js?v=20260925_energy_mechanic_v5_energy_mechanic_v5';
import { renderBankruptcyMarket } from './bankruptcy_market.js?v=20260925_energy_mechanic_v5_energy_mechanic_v5';

const IPO_MIN_LEVEL_FALLBACK = 7;

export async function renderStocks(container, showToast) {
  let stocksList = [];
  let stateBonds = [];
  let bondHoldings = [];
  try {
    const [stocksRes, bondsRes] = await Promise.all([
      NatAPI.getStocksList(),
      NatAPI.getStateBonds().catch(() => ({ bonds: [], holdings: [] })),
    ]);
    stocksList = stocksRes.stocks || [];
    stateBonds = bondsRes.bonds || [];
    bondHoldings = bondsRes.holdings || [];
  } catch (err) {
    console.error('Failed to load securities:', err);
  }

  const myCompany = store.company || {};
  const isPublic = myCompany.is_public;
  const companyId = Number(myCompany.id || myCompany.company_id || 0);
  const ownStock = stocksList.find((stock) => Number(stock.company_id) === companyId);
  const companyLevel = Number(myCompany.level || 1);
  const ipoMinLevel = Number(myCompany.capital_plan?.ipo_available_from_level || IPO_MIN_LEVEL_FALLBACK);
  const ipoUnlocked = companyLevel >= ipoMinLevel;
  const dividendRate = Number(ownStock?.dividend_rate_pct || myCompany.stock?.dividend_rate_pct || 5);
  const totalShares = Number(ownStock?.total_shares || 0);
  const floatShares = Number(ownStock?.float_shares || 0);
  const founderShares = Number(ownStock?.founder_shares || Math.max(0, totalShares - floatShares));
  const floatPct = Number(ownStock?.company_sale_pct ?? (totalShares ? (totalShares - founderShares) * 100 / totalShares : 0));

  container.innerHTML = `
    <div class="space-y-4 max-w-md mx-auto p-4 pb-24">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-xl font-black text-slate-900 dark:text-white">Фондовая Биржа</h2>
          <p class="text-xs text-slate-500">Акции, первичное размещение (IPO) и дивиденды</p>
        </div>
      </div>

      <!-- IPO Banner / Status -->
      <div class="glass-card rounded-2xl p-4 shadow-sm border-l-4 ${isPublic ? 'border-l-emerald-500' : 'border-l-blue-500'} space-y-3">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="text-xl">${isPublic ? '🏛️' : '🚀'}</span>
            <div>
              <div class="text-xs font-bold text-slate-900 dark:text-white">
                ${isPublic ? 'Ваша корпорация торгуется на бирже' : 'Выход на IPO'}
              </div>
              <div class="text-[11px] text-slate-400">
                ${isPublic ? `${totalShares ? (founderShares * 100 / totalShares).toFixed(1) : '—'}% основателю · ${floatPct.toFixed(1)}% выставлено рынку` : `Доступно с ${ipoMinLevel} уровня компании. Сейчас: ${companyLevel} ур.`}
              </div>
            </div>
          </div>
          ${!isPublic ? `
            <button id="open-ipo-btn" ${ipoUnlocked ? '' : 'disabled'} class="px-3 py-1.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-bold text-xs shadow-md active:scale-95 transition-all disabled:opacity-40 disabled:cursor-not-allowed">
              ${ipoUnlocked ? 'Выйти на IPO' : `IPO с ${ipoMinLevel} уровня`}
            </button>
          ` : `
            <span class="text-xs font-bold font-mono text-emerald-500">АКТИВНО</span>
          `}
        </div>

        ${isPublic ? `
          <div class="grid grid-cols-2 gap-2 pt-2 border-t border-slate-200 dark:border-slate-800 text-xs">
            <div>
              <span class="text-slate-400 text-[11px]">Дивидендный пул:</span>
              <div class="font-mono font-bold text-emerald-500">${dividendRate}% от чистой прибыли</div>
            </div>
            <div>
              <span class="text-slate-400 text-[11px]">Режим выплат:</span>
              <div class="font-mono font-bold text-slate-300">Ежедневно 00:01</div>
            </div>
            ${ownStock ? `<div class="col-span-2 rounded-xl bg-slate-50 dark:bg-slate-800/60 p-3 space-y-2">
              <div class="text-[11px] text-slate-400">Настройка дивидендов для вашей компании</div>
              <div class="flex gap-2">
                <input id="stock-dividend-rate" type="number" min="6" max="100" step="0.5" value="${Math.max(6, dividendRate)}" aria-label="Новый процент дивидендов" class="min-w-0 flex-1 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-3 py-2 font-mono text-xs text-slate-900 dark:text-white" />
                <button id="save-stock-dividend-rate" type="button" class="shrink-0 rounded-lg bg-emerald-600 px-3 py-2 text-[11px] font-bold text-white">Изменить</button>
              </div>
              <div class="text-[10px] text-slate-500">Ставку можно повышать или снижать, минимум при изменении — 6%.</div>
            </div>` : ''}
          </div>
        ` : ''}
      </div>

      <button id="open-bankruptcy-market" class="glass-card w-full rounded-2xl p-3 text-left shadow-sm border border-amber-500/30">
        <div class="text-xs font-bold text-amber-700 dark:text-amber-300">🏭 Рынок банкротов</div>
        <div class="mt-1 text-[10px] text-slate-500">Конфискованные заводы, предприятия и акции — покупки идут в казну</div>
      </button>

      <!-- State Bonds -->
      <div class="glass-card rounded-2xl p-4 shadow-sm space-y-3">
        <div class="flex items-center justify-between">
          <div>
            <h3 class="text-xs font-bold uppercase tracking-wider text-slate-400">Государственные облигации</h3>
            <div class="text-[10px] text-slate-500 mt-0.5">Покупка переводит cash компании в государственную казну</div>
          </div>
          <span class="text-xs font-mono text-slate-400">${stateBonds.filter(b => b.is_active).length} выпусков</span>
        </div>
        ${bondHoldings.length ? `<div class="rounded-xl bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900 p-2.5 text-[10px]">
          <div class="font-bold text-amber-700 dark:text-amber-300 mb-1">Ваш портфель ОФЗ</div>
          ${bondHoldings.map(h => `<div class="flex justify-between gap-2"><span>${h.title} × ${h.quantity}</span><span class="font-mono">${Number(h.invested_cash).toLocaleString('ru-RU')} cash</span></div>`).join('')}
        </div>` : ''}
        <div class="space-y-2">
          ${stateBonds.filter(b => b.is_active).length === 0 ? `<div class="text-center py-4 text-xs text-slate-400">Активных выпусков пока нет.</div>` : stateBonds.filter(b => b.is_active).map(b => `
            <div class="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
              <div class="flex items-start justify-between gap-2">
                <div>
                  <div class="font-bold text-xs text-slate-900 dark:text-white">${b.title}</div>
                  <div class="text-[10px] text-slate-400">${b.coupon_rate}% · ${Number(b.coupon_rate / 2).toLocaleString('ru-RU')}% в день, выплата раз в минуту · ${b.maturity_days} дн. · остаток ${b.remaining_volume}/${b.total_volume}</div>
                </div>
                <div class="text-right shrink-0">
                  <div class="font-mono font-black text-xs">${Number(b.face_value).toLocaleString('ru-RU')} cash</div>
                  <button class="buy-bond-btn mt-1 px-2.5 py-1 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-bold text-[10px]" data-bond-id="${b.id}" data-title="${b.title}" data-face="${b.face_value}" data-remaining="${b.remaining_volume}">Купить</button>
                </div>
              </div>
              <div class="text-[9px] text-slate-500 mt-1 italic">${b.purpose}</div>
            </div>`).join('')}
        </div>
      </div>

      <!-- Stock Market List -->
      <div class="glass-card rounded-2xl p-4 shadow-sm space-y-3">
        <div class="flex items-center justify-between">
          <h3 class="text-xs font-bold uppercase tracking-wider text-slate-400">Котировки публичных корпораций</h3>
          <span class="text-xs font-mono text-slate-400">${stocksList.length} эмитентов</span>
        </div>

        <div class="space-y-2">
          ${stocksList.length === 0 ? `
            <div class="text-center py-6 text-slate-400 text-xs">
              На бирже пока нет размещённых акций. Будьте первыми!
            </div>
          ` : stocksList.map(s => `
            <div class="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 flex items-center justify-between">
              <div>
                <div class="flex items-center gap-1.5">
                  <span class="font-mono font-black text-xs text-blue-600 dark:text-blue-400">[${s.company_name ? s.company_name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0,5) : '???'}]</span>
                  <span class="font-bold text-xs text-slate-900 dark:text-white">${s.company_name}</span>
                </div>
                <div class="text-[10px] text-slate-400 mt-0.5">Free-float: ${s.float_shares?.toLocaleString()} шт.</div>
              </div>
              <div class="text-right">
                <div class="font-mono font-black text-xs text-slate-900 dark:text-white">${s.current_price?.toFixed(2)} cash</div>
                <button
                  class="buy-shares-btn mt-1 px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-[10px] active:scale-95 transition-all"
                  data-stock-id="${s.stock_id}"
                  data-ticker="${s.company_name ? s.company_name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0,5) : '???'}"
                  data-price="${s.current_price}"
                >
                  Купить
                </button>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    </div>

    <!-- IPO Modal -->
    <div id="ipo-modal" class="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm hidden items-center justify-center p-4">
      <div class="glass-card rounded-2xl max-w-sm w-full p-5 space-y-4 shadow-2xl">
        <div class="flex items-center justify-between">
          <h3 class="font-black text-slate-900 dark:text-white text-base">Первичное размещение (IPO)</h3>
          <button id="close-ipo-modal-btn" class="text-slate-400 hover:text-slate-600 text-lg">✕</button>
        </div>
        <p class="text-xs text-slate-400">
          Выберите дивиденды, долю компании для продажи и общее число акций. На рынок можно выставить не больше 50% компании.
        </p>
        <label class="block text-xs text-slate-400 space-y-1">
          <span class="font-bold text-slate-700 dark:text-slate-300">Обязательные дивиденды, % от чистой дневной прибыли</span>
          <input id="ipo-dividend-rate" type="number" min="5" max="100" step="0.5" value="5" class="w-full px-3 py-2 rounded-xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white font-mono" />
          <span class="text-[10px]">При размещении минимум 5%. После IPO изменение ставки — от 6%.</span>
        </label>
        <label class="block text-xs text-slate-400 space-y-1">
          <span class="font-bold text-slate-700 dark:text-slate-300">Продаваемая доля компании, %</span>
          <input id="ipo-company-sale-pct" type="number" min="0.1" max="50" step="0.5" value="40" class="w-full px-3 py-2 rounded-xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white font-mono" />
          <span class="text-[10px]">Максимум 50%; остальная доля останется у основателя.</span>
        </label>
        <label class="block text-xs text-slate-400 space-y-1">
          <span class="font-bold text-slate-700 dark:text-slate-300">Общее количество акций</span>
          <input id="ipo-total-shares" type="number" min="4000" step="1" value="10000" class="w-full px-3 py-2 rounded-xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white font-mono" />
          <span class="text-[10px]">Минимум 4 000 акций.</span>
        </label>
        <div class="p-3 rounded-xl bg-slate-100 dark:bg-slate-800 text-xs space-y-1 font-mono">
          <div class="flex justify-between">
            <span class="text-slate-500">Оценка NAV:</span>
            <span class="font-bold text-slate-900 dark:text-white">${store.nav || 10000} cash</span>
          </div>
          <div class="flex justify-between">
            <span class="text-slate-500">Акции в свободном обращении:</span>
            <span id="ipo-float-shares-preview" class="font-bold text-emerald-500">4 000 / 10 000</span>
          </div>
        </div>
        <button
          id="confirm-ipo-btn"
          class="w-full py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs active:scale-98 transition-all"
        >
          🚀 Подтвердить выпуск акций
        </button>
      </div>
    </div>
  `;

  // IPO Modal handlers
  container.querySelector('#open-bankruptcy-market')?.addEventListener('click', () => {
    renderBankruptcyMarket(container, showToast, () => renderStocks(container, showToast));
  });

  const ipoModal = container.querySelector('#ipo-modal');
  container.querySelector('#open-ipo-btn')?.addEventListener('click', () => {
    ipoModal.classList.remove('hidden');
    ipoModal.classList.add('flex');
  });
  container.querySelector('#close-ipo-modal-btn')?.addEventListener('click', () => {
    ipoModal.classList.add('hidden');
    ipoModal.classList.remove('flex');
  });

  const updateIpoFloatPreview = () => {
    const shares = Number(container.querySelector('#ipo-total-shares')?.value || 0);
    const pct = Number(container.querySelector('#ipo-company-sale-pct')?.value || 0);
    const preview = container.querySelector('#ipo-float-shares-preview');
    if (preview) preview.textContent = `${Math.max(0, Math.floor(shares * pct / 100)).toLocaleString('ru-RU')} / ${Math.max(0, shares).toLocaleString('ru-RU')}`;
  };
  container.querySelector('#ipo-total-shares')?.addEventListener('input', updateIpoFloatPreview);
  container.querySelector('#ipo-company-sale-pct')?.addEventListener('input', updateIpoFloatPreview);

  container.querySelector('#save-stock-dividend-rate')?.addEventListener('click', async (event) => {
    const button = event.currentTarget;
    const rate = Number(container.querySelector('#stock-dividend-rate')?.value);
    if (!ownStock || !Number.isFinite(rate) || rate < 6 || rate > 100) {
      showToast('Укажите ставку дивидендов от 6% до 100%.', 'error');
      return;
    }
    button.disabled = true;
    try {
      await NatAPI.updateStockDividendRate(ownStock.stock_id, rate);
      showToast('Ставка дивидендов изменена.', 'success');
      renderStocks(container, showToast);
    } catch (err) {
      showToast(err.message, 'error');
      button.disabled = false;
    }
  });

  container.querySelector('#confirm-ipo-btn')?.addEventListener('click', async () => {
    const btn = container.querySelector('#confirm-ipo-btn');
    try {
      btn.disabled = true;
      btn.innerText = 'Размещение...';
      const rate = Number(container.querySelector('#ipo-dividend-rate')?.value || 5);
      const companySalePct = Number(container.querySelector('#ipo-company-sale-pct')?.value);
      const ipoTotalShares = Number(container.querySelector('#ipo-total-shares')?.value);
      if (!Number.isFinite(rate) || rate < 5 || rate > 100) {
        throw new Error('Дивиденды при IPO должны быть от 5% до 100%.');
      }
      if (!Number.isFinite(companySalePct) || companySalePct < 0.1 || companySalePct > 50) {
        throw new Error('Укажите продаваемую долю компании от 0,1% до 50%.');
      }
      if (!Number.isInteger(ipoTotalShares) || ipoTotalShares < 4000) {
        throw new Error('Для IPO нужно выпустить минимум 4 000 акций.');
      }
      await NatAPI.issueIPO({
        dividend_rate_pct: rate,
        company_sale_pct: companySalePct,
        total_shares: ipoTotalShares,
      });
      ipoModal.classList.add('hidden');
      showToast('IPO успешно проведено! Акции вышли на биржу.', 'success');
      const refreshed = await NatAPI.getMyCompany();
      store.setCompany(refreshed);
      renderStocks(container, showToast);
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      btn.disabled = false;
      btn.innerText = '🚀 Подтвердить выпуск акций';
    }
  });


  // Buy state bonds: real player cash -> state treasury transfer.
  container.querySelectorAll('.buy-bond-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const bondId = Number(btn.dataset.bondId);
      const remaining = Number(btn.dataset.remaining || 0);
      const face = Number(btn.dataset.face || 0);
      const raw = prompt(`Сколько облигаций «${btn.dataset.title}» купить по ${face.toLocaleString('ru-RU')} cash?`, '1');
      const quantity = Number.parseInt(raw, 10);
      if (!quantity || quantity <= 0 || quantity > remaining) {
        if (quantity > remaining) showToast(`Доступно только ${remaining} шт.`, 'error');
        return;
      }
      try {
        btn.disabled = true;
        const result = await NatAPI.buyStateBonds(bondId, quantity);
        showToast(`Куплено ${result.quantity_bought} облигаций на ${Number(result.total_cost).toLocaleString('ru-RU')} cash`, 'success');
        const refreshed = await NatAPI.getMyCompany();
        store.setCompany(refreshed);
        await renderStocks(container, showToast);
      } catch (err) {
        showToast(err.message, 'error');
        btn.disabled = false;
      }
    });
  });

  // Buy shares handler
  container.querySelectorAll('.buy-shares-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const stockId = btn.getAttribute('data-stock-id');
      const ticker = btn.getAttribute('data-ticker');
      const price = parseFloat(btn.getAttribute('data-price'));
      const countStr = prompt(`Сколько акций [${ticker}] купить по цене ${price.toFixed(4)} cash?`, '1000');
      const count = parseInt(countStr, 10);
      if (!count || count <= 0) return;

      try {
        await NatAPI.buyShares(parseInt(stockId), count);
        showToast(`Ордер на покупку акций [${ticker}] размещен!`, 'success');
        const refreshed = await NatAPI.getMyCompany();
        store.setCompany(refreshed);
        renderStocks(container, showToast);
      } catch (err) {
        showToast(err.message, 'error');
      }
    });
  });
}
