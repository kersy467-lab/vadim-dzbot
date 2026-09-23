import { NatAPI } from '../api.js?v=20260921_broker1';

const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[char]));

const cash = (value) => `${Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} cash`;

export async function loadCreatorShares(el, showToast) {
  let issues = [];

  async function reload() {
    const data = await NatAPI.getCreatorShares();
    issues = data.shares || [];
    render();
  }

  function render() {
    el.innerHTML = `
      <div class="glass-card rounded-2xl p-4 space-y-3">
        <div>
          <div class="text-xs font-bold text-amber-400 uppercase">Выпуск государственных акций</div>
          <p class="mt-1 text-[10px] text-slate-400">Ты вручную создаёшь каждый выпуск. Расчётная годовая прибыль — прогноз для расчёта дивидендов, а выплаты идут ежедневно из средств казны.</p>
        </div>
        <div class="rounded-xl border border-amber-500/30 bg-amber-950/20 p-3 text-[10px] text-amber-100">
          Сам выпуск <b>не пополняет казну</b>. Казна получает деньги только при покупке акций игроками; обратный выкуп возможен только при достаточном остатке казны.
        </div>
        <form id="creator-share-issue-form" class="space-y-2 text-xs">
          <label class="block text-[10px] text-slate-400">Название выпуска
            <input id="share-title" required maxlength="100" class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white" placeholder="Например, Государственная энергетика">
          </label>
          <label class="block text-[10px] text-slate-400">Цель / пояснение
            <textarea id="share-purpose" maxlength="255" rows="2" class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white" placeholder="Условия и назначение выпуска"></textarea>
          </label>
          <div class="grid grid-cols-2 gap-2">
            <label class="block text-[10px] text-slate-400">Количество акций
              <input id="share-volume" type="number" min="1" max="2000000000" step="1" required class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white" placeholder="Количество">
            </label>
            <label class="block text-[10px] text-slate-400">Цена за акцию
          <input id="share-price" type="number" min="0.01" step="0.01" required class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white" placeholder="cash">
            </label>
            <label class="block text-[10px] text-slate-400">Прогноз прибыли за год
              <input id="share-projected-profit" type="number" min="0" step="0.01" required class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white" placeholder="cash">
            </label>
            <label class="block text-[10px] text-slate-400">Дивиденды от прогноза, %
              <input id="share-dividend-rate" type="number" min="0" max="100" step="0.01" value="5" required class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white">
            </label>
          </div>
          <div id="creator-share-feedback" role="status" class="min-h-4 text-[10px] text-emerald-400"></div>
          <button id="issue-state-share-btn" class="w-full rounded-xl bg-amber-500 py-2.5 font-black text-slate-950">Выпустить акции вручную</button>
        </form>
      </div>
      <div class="glass-card rounded-2xl p-3 space-y-2">
        <div class="text-xs font-bold text-slate-300">Выпуски государства (${issues.length})</div>
        <div class="space-y-2">${issues.map((share) => `
          <article class="rounded-xl border border-slate-800 bg-slate-900/60 p-3 text-[10px]">
            <div class="flex justify-between gap-2"><b class="text-xs text-white">${escapeHtml(share.title)}</b><span class="text-amber-300">${Number(share.dividend_rate_pct).toLocaleString('ru-RU')}% дивидендов</span></div>
            <div class="mt-1 text-slate-400">Выпущено ${Number(share.total_volume).toLocaleString('ru-RU')} · доступно ${Number(share.remaining_volume).toLocaleString('ru-RU')} · ${cash(share.issue_price)} / акция</div>
            <div class="mt-1 text-slate-400">Годовой прогноз: ${cash(share.projected_annual_profit)}</div>
            ${share.purpose ? `<div class="mt-1 text-slate-500">${escapeHtml(share.purpose)}</div>` : ''}
          </article>`).join('') || '<div class="py-4 text-center text-xs text-slate-500">Выпусков пока нет. Создай первый вручную выше.</div>'}
        </div>
      </div>`;

    el.querySelector('#creator-share-issue-form')?.addEventListener('submit', async (event) => {
      event.preventDefault();
      const title = el.querySelector('#share-title').value.trim();
      const purpose = el.querySelector('#share-purpose').value.trim();
      const volume = Number(el.querySelector('#share-volume').value);
      const issue_price = Number(el.querySelector('#share-price').value);
      const projected_annual_profit = Number(el.querySelector('#share-projected-profit').value);
      const dividend_rate_pct = Number(el.querySelector('#share-dividend-rate').value);
      if (!title || !Number.isInteger(volume) || volume <= 0 || !Number.isFinite(issue_price) || issue_price < 0.01
        || !Number.isFinite(projected_annual_profit) || projected_annual_profit < 0
        || !Number.isFinite(dividend_rate_pct) || dividend_rate_pct < 0 || dividend_rate_pct > 100) {
        showFeedback('Проверь поля выпуска: цена должна быть положительной, ставка — от 0 до 100%.', 'error');
        return;
      }
      if (!confirm(`Вручную выпустить ${volume.toLocaleString('ru-RU')} акций «${title}» по ${cash(issue_price)}? Сам выпуск не пополняет казну; деньги поступят только при покупке игроками.`)) return;
      const button = el.querySelector('#issue-state-share-btn');
      button.disabled = true;
      try {
        await NatAPI.issueCreatorShares({ title, purpose, volume, issue_price, projected_annual_profit, dividend_rate_pct });
        const successMessage = `Выпуск «${title}» создан. Казна пополнится только по мере покупки акций.`;
        showToast('Выпуск государственных акций создан.', 'success');
        await reload();
        showFeedback(successMessage, 'success');
      } catch (error) {
        if (error?.name === 'AbortError') return;
        const message = error.message || 'Не удалось создать выпуск.';
        showFeedback(message, 'error');
        showToast(escapeHtml(message), 'error');
      } finally {
        if (button.isConnected) button.disabled = false;
      }
    });
  }

  function showFeedback(message, tone) {
    const target = el.querySelector('#creator-share-feedback');
    if (!target) return;
    target.className = `min-h-4 text-[10px] ${tone === 'error' ? 'text-rose-400' : 'text-emerald-400'}`;
    target.textContent = message;
  }

  await reload();
}
