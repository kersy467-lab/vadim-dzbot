import { NatAPI } from '../api.js';

export async function loadCreatorModeration(el, showToast) {
  const [data, resetPreview] = await Promise.all([
    NatAPI.getCreatorMarket().catch(err => {
      console.error('getCreatorMarket error:', err);
      return { restrictions: [], orders: [] };
    }),
    NatAPI.getCreatorWorldResetPreview().catch(err => {
      console.error('getCreatorWorldResetPreview error:', err);
      return { affected_companies: 0, creator_starting_cash: 500000, normal_starting_cash: 50000, tester_starting_pvc: 200, confirmation_phrase: 'СБРОСИТЬ НАТБИРЖУ' };
    }),
  ]);
  const affected = Number(resetPreview?.affected_companies || 0).toLocaleString('ru-RU');
  const creatorCash = Number(resetPreview?.creator_starting_cash || 500000).toLocaleString('ru-RU');
  const normalCash = Number(resetPreview?.normal_starting_cash || 50000).toLocaleString('ru-RU');
  const testerPvc = Number(resetPreview?.tester_starting_pvc || 200).toLocaleString('ru-RU');
  const resetPhrase = String(resetPreview?.confirmation_phrase || 'СБРОСИТЬ НАТБИРЖУ');

  el.innerHTML = `
    <div class="grid grid-cols-2 gap-2">
      <button id="open-warn-btn" class="py-2.5 px-3 rounded-xl bg-amber-600 hover:bg-amber-500 text-slate-950 text-xs font-bold transition-all">
        ⚠️ Предупреждение
      </button>
      <button id="open-restr-btn" class="py-2.5 px-3 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold transition-all">
        🛑 Ограничение цен
      </button>
    </div>

    <div class="glass-card rounded-2xl p-3 space-y-2">
      <div class="text-xs font-bold text-rose-400">Действующие ценовые ограничения (${data.restrictions.length})</div>
      ${data.restrictions.length === 0 ? '<div class="text-[11px] text-slate-500">Нет активных ограничений цен.</div>' : ''}
      <div class="space-y-1.5">
        ${data.restrictions.map(r => `
          <div class="rounded-xl border border-rose-500/30 bg-rose-950/20 p-2 text-[11px] flex justify-between items-center">
            <div>
              <div class="font-bold text-white">${r.item_id ? r.item_id : 'Все товары'} ${r.company_id ? `(Комп. #${r.company_id})` : '(Весь рынок)'}</div>
              <div class="text-[10px] text-rose-300">Диапазон: [${r.min_price ?? '—'}, ${r.max_price ?? '—'}] ₽ · ${r.reason}</div>
            </div>
            <button class="remove-restr-btn px-2 py-1 rounded bg-rose-800 hover:bg-rose-700 text-white text-[10px] font-bold" data-id="${r.id}">Снять</button>
          </div>
        `).join('')}
      </div>
    </div>

    <div class="glass-card rounded-2xl p-3 space-y-2">
      <div class="text-xs font-bold text-slate-300">Активные ордера на бирже (${data.orders.length})</div>
      ${data.orders.length === 0 ? '<div class="text-[11px] text-slate-500">Биржевой стакан пуст.</div>' : ''}
      <div class="space-y-1 max-h-48 overflow-y-auto">
        ${data.orders.map(o => `
          <div class="rounded-lg border border-slate-700/60 bg-slate-900/50 p-2 text-[10px] flex justify-between items-center font-mono">
            <div>
              <span class="${o.order_type === 'BUY' ? 'text-emerald-400' : 'text-rose-400'} font-bold">${o.order_type}</span>
              <span class="text-slate-200">#${o.company_id} · ${o.item_id}</span>
            </div>
            <div class="text-right">
              <div class="font-bold text-white">${o.price} ₽</div>
              <div class="text-slate-500">${o.remaining_qty} шт.</div>
            </div>
          </div>
        `).join('')}
      </div>
    </div>

    <div class="rounded-2xl border border-orange-500/50 bg-orange-950/30 p-4 space-y-2.5">
      <div>
        <div class="text-xs font-black uppercase tracking-wide text-orange-300">🔄 Сбросить только себя</div>
        <div class="mt-1 text-[11px] leading-relaxed text-orange-100/80">
          Удаляет только твою компанию и весь твой игровой прогресс. Остальные игроки <b class="text-white">не затрагиваются</b>.
          Твой аккаунт (роль admin, tg_id) сохраняется — при следующем входе автоматически получишь <b class="text-white">500 000 cash + 500 PVC</b>.
        </div>
      </div>
      <button id="creator-self-reset-btn" class="w-full rounded-xl bg-orange-600 hover:bg-orange-500 active:scale-95 px-3 py-2.5 text-xs font-black text-white shadow-lg transition-all cursor-pointer">
        🔄 Сбросить только мой аккаунт
      </button>
    </div>

    <div class="rounded-2xl border border-rose-500/60 bg-rose-950/35 p-4 space-y-3 shadow-lg shadow-rose-950/20">
      <div>
        <div class="text-xs font-black uppercase tracking-wide text-rose-300">💣 Полный сброс всех аккаунтов (Игра с нуля)</div>
        <div class="mt-1 text-[11px] leading-relaxed text-rose-100/80">
          Удаляет все компании и всю игровую историю: заводы, склады, армию, биржу, IPO, облигации, PvE/PvP,
          лицензии, PVC-балансы и прогресс. Глобальные Telegram-пользователи не удаляются — сохраняются роль админа и флаг тестера.
        </div>
      </div>
      <div class="grid grid-cols-2 gap-2 text-[10px]">
        <div class="rounded-xl bg-rose-950/50 border border-rose-500/20 p-2"><span class="text-rose-300">Профилей сейчас</span><div class="text-base font-black text-white">${affected}</div></div>
        <div class="rounded-xl bg-rose-950/50 border border-rose-500/20 p-2"><span class="text-rose-300">После нового входа</span><div class="font-bold text-white">Админ ${creatorCash} cash</div><div class="text-rose-100/70">Остальные ${normalCash} cash</div></div>
      </div>
      <div class="rounded-xl bg-slate-950/35 border border-rose-500/20 p-2 text-[10px] text-rose-100/80">
        Тестеры при создании новой компании снова получают <b class="text-white">${testerPvc} PVC + ${testerPvc} NAT</b>. Админ также получает ${testerPvc} PVC + ${testerPvc} NAT.
      </div>
      <div class="space-y-1.5">
        <label class="block text-[10px] text-rose-200/80 font-bold uppercase">Подтверждение для сброса:</label>
        <input id="creator-world-reset-input" type="text" value="${resetPhrase}" class="w-full rounded-xl border border-rose-500/40 bg-slate-900 px-3 py-2 text-xs font-mono text-center text-rose-200" placeholder="Введите: ${resetPhrase}" />
      </div>
      <button id="creator-world-reset-btn" class="w-full rounded-xl bg-rose-600 hover:bg-rose-500 active:scale-95 px-3 py-3 text-xs font-black text-white shadow-lg shadow-rose-950/30 transition-all cursor-pointer">
        💣 СБРОСИТЬ ВСЕ АККАУНТЫ (ИГРА С НУЛЯ)
      </button>
      <div class="text-[9px] text-rose-200/60 text-center">Контрольная фраза: ${resetPhrase} (нажмите кнопку и подтвердите)</div>
    </div>
  `;

  el.querySelectorAll('.remove-restr-btn').forEach(b => {
    b.addEventListener('click', async () => {
      try {
        if (!confirm('Снять это ценовое ограничение?')) return;
        await NatAPI.removeCreatorRestriction(Number(b.dataset.id));
        showToast('Ограничение успешно снято', 'success');
        await loadCreatorModeration(el, showToast);
      } catch (e) {
        showToast(e.message, 'error');
      }
    });
  });

  el.querySelector('#creator-self-reset-btn')?.addEventListener('click', async (event) => {
    const button = event.currentTarget;
    if (!confirm('Сбросить только СВОЙ аккаунт? Твоя компания и весь прогресс будут удалены. Остальные игроки не пострадают.')) return;
    button.disabled = true;
    button.textContent = 'Сбрасываю…';
    try {
      const result = await NatAPI.resetSelf();
      showToast(result.message || 'Аккаунт сброшен! Перезагружаю…', 'success');
      setTimeout(() => window.location.reload(), 1200);
    } catch (e) {
      button.disabled = false;
      button.textContent = '🔄 Сбросить только мой аккаунт';
      showToast(e.message, 'error');
    }
  });

  el.querySelector('#open-warn-btn')?.addEventListener('click', async () => {
    const compId = prompt('Введите ID компании:');
    if (!compId) return;
    const reason = prompt('Причина официального предупреждения:');
    if (!reason) return;
    try {
      await NatAPI.sendCreatorWarning(Number(compId), reason);
      showToast(`Предупреждение выдано компании #${compId}`, 'success');
      await loadCreatorModeration(el, showToast);
    } catch (e) {
      showToast(e.message, 'error');
    }
  });

  el.querySelector('#open-restr-btn')?.addEventListener('click', async () => {
    const item = prompt('Товар (оставьте пустым для всех):', '') || null;
    const minP = prompt('Минимальная цена (₽):', '');
    const maxP = prompt('Максимальная цена (₽):', '');
    const reason = prompt('Официальная причина ограничения цен:');
    if (!reason) return;
    try {
      await NatAPI.setCreatorRestriction({
        item_id: item ? item.trim() : null,
        min_price: minP ? parseFloat(minP) : null,
        max_price: maxP ? parseFloat(maxP) : null,
        reason: reason.trim(),
      });
      showToast('Ценовое ограничение установлено на сервере', 'success');
      await loadCreatorModeration(el, showToast);
    } catch (e) {
      showToast(e.message, 'error');
    }
  });

  el.querySelector('#creator-world-reset-btn')?.addEventListener('click', async event => {
    const button = event.currentTarget;
    if (!confirm(`Это действие удалит абсолютно все (${affected}) компании и весь прогресс. Все игроки начнут игру заново с нуля. Продолжить?`)) return;
    const inputEl = el.querySelector('#creator-world-reset-input');
    let entered = (inputEl?.value || '').trim();
    if (entered !== resetPhrase) {
      entered = prompt(`Для сброса мира введите точно:\n${resetPhrase}`, resetPhrase);
      if (entered !== resetPhrase) {
        showToast('Сброс отменён: контрольная фраза не совпала.', 'error');
        return;
      }
    }
    button.disabled = true;
    button.textContent = 'Сбрасываю абсолютно все профили…';
    try {
      const result = await NatAPI.resetCreatorWorld(entered);
      showToast(`НАТБИРЖА успешно сброшена! Удалено компаний: ${result.affected_companies}. Игра начинается с нуля!`, 'success');
      setTimeout(() => window.location.reload(), 1000);
    } catch (e) {
      button.disabled = false;
      button.textContent = '💣 СБРОСИТЬ ВСЕ АККАУНТЫ (ИГРА С НУЛЯ)';
      showToast(e.message, 'error');
    }
  });
}
