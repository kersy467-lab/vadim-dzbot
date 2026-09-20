import { NatAPI } from '../api.js';
import { store } from '../state.js';

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
  const companyLevel = Number(myCompany.level || 1);
  const ipoUnlocked = companyLevel >= 2;
  const dividendRate = Number(myCompany.stock?.dividend_rate_pct || myCompany.dividend_rate_pct || 5);

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
                ${isPublic ? '60% основатель, 40% free-float в открытом обращении' : `Доступно с 2 уровня компании. Сейчас: ${companyLevel} ур.`}
              </div>
            </div>
          </div>
          ${!isPublic ? `
            <button id="open-ipo-btn" ${ipoUnlocked ? '' : 'disabled'} class="px-3 py-1.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-bold text-xs shadow-md active:scale-95 transition-all disabled:opacity-40 disabled:cursor-not-allowed">
              ${ipoUnlocked ? 'Выйти на IPO' : 'IPO с 2 уровня'}
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
          </div>
        ` : ''}
      </div>

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
                  <div class="text-[10px] text-slate-400">${b.coupon_rate}% · ${b.maturity_days} дн. · остаток ${b.remaining_volume}/${b.total_volume}</div>
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
          При выходе на биржу выпускается 10,000 акций. 60% остаётся у вас, 40% выставляется на свободный рынок.
        </p>
        <label class="block text-xs text-slate-400 space-y-1">
          <span class="font-bold text-slate-700 dark:text-slate-300">Обязательные дивиденды, % от чистой дневной прибыли</span>
          <input id="ipo-dividend-rate" type="number" min="5" max="50" step="0.5" value="5" class="w-full px-3 py-2 rounded-xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white font-mono" />
          <span class="text-[10px]">Минимум 5%. Ниже 5% выйти на IPO нельзя.</span>
        </label>
        <div class="p-3 rounded-xl bg-slate-100 dark:bg-slate-800 text-xs space-y-1 font-mono">
          <div class="flex justify-between">
            <span class="text-slate-500">Оценка NAV:</span>
            <span class="font-bold text-slate-900 dark:text-white">${store.nav || 10000} cash</span>
          </div>
          <div class="flex justify-between">
            <span class="text-slate-500">Цена размещения:</span>
            <span class="font-bold text-emerald-500">${((store.nav || 10000) / 10000).toFixed(4)} cash / акция</span>
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
  const ipoModal = container.querySelector('#ipo-modal');
  container.querySelector('#open-ipo-btn')?.addEventListener('click', () => {
    ipoModal.classList.remove('hidden');
    ipoModal.classList.add('flex');
  });
  container.querySelector('#close-ipo-modal-btn')?.addEventListener('click', () => {
    ipoModal.classList.add('hidden');
    ipoModal.classList.remove('flex');
  });

  container.querySelector('#confirm-ipo-btn')?.addEventListener('click', async () => {
    const btn = container.querySelector('#confirm-ipo-btn');
    try {
      btn.disabled = true;
      btn.innerText = 'Размещение...';
      const rate = Number(container.querySelector('#ipo-dividend-rate')?.value || 5);
      if (!Number.isFinite(rate) || rate < 5 || rate > 50) {
        throw new Error('Дивиденды при IPO должны быть от 5% до 50%.');
      }
      await NatAPI.issueIPO({ dividend_rate_pct: rate });
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
