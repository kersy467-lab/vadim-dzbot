import { NatAPI } from '../api.js?v=20260925_sabotages_v2';

export async function loadCreatorSabotages(el, showToast) {
  const [activeRes, catalogRes] = await Promise.all([
    NatAPI.getActiveSabotage().catch(err => {
      console.error('getActiveSabotage error:', err);
      return { active: false, sabotage: null };
    }),
    NatAPI.getSabotagesCatalog().catch(err => {
      console.error('getSabotagesCatalog error:', err);
      return [];
    }),
  ]);

  const active = activeRes?.active ? activeRes.sabotage : null;
  const catalog = Array.isArray(catalogRes) ? catalogRes : [];

  const formatSeconds = (sec) => {
    if (!sec || sec <= 0) return 'Истекает…';
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    return `${h} ч ${m} мин`;
  };

  const buildEffectsList = (spec) => {
    const list = [];
    if (spec.one_time_stock_shock) list.push(`📉 Разовый обвал акций: ${Math.round(spec.one_time_stock_shock * 100)}%`);
    if (spec.credit_rate_delta) list.push(`💳 Ставка кредитов: +${Math.round(spec.credit_rate_delta * 100)}%`);
    if (spec.bond_price_mult && spec.bond_price_mult !== 1.0) {
      const p = Math.round((spec.bond_price_mult - 1.0) * 100);
      list.push(`📜 Цена гособлигаций: ${p}%`);
    }
    if (spec.block_dividends) list.push('🚫 Выплаты дивидендов: ЗАМОРОЖЕНЫ');
    if (spec.block_new_credits) list.push('🚫 Новые госкредиты: ЗАБЛОКИРОВАНЫ');
    if (spec.income_multipliers) {
      for (const [s, m] of Object.entries(spec.income_multipliers)) {
        const p = Math.round((m - 1.0) * 100);
        list.push(`🏭 Доходность «${s}»: ${p > 0 ? '+' : ''}${p}%`);
      }
    }
    if (spec.other_income_mult && spec.other_income_mult !== 1.0) {
      const p = Math.round((spec.other_income_mult - 1.0) * 100);
      list.push(`🏭 Доходность остальных отраслей: ${p}%`);
    }
    if (spec.resource_multipliers) {
      for (const [r, m] of Object.entries(spec.resource_multipliers)) {
        const p = Math.round((m - 1.0) * 100);
        list.push(`📦 Ресурс «${r}»: ${p > 0 ? '+' : ''}${p}%`);
      }
    }
    return list;
  };

  let activeCardHtml = '';
  if (active) {
    const effects = buildEffectsList(active.details || {});
    activeCardHtml = `
      <div class="rounded-2xl border-2 border-rose-500 bg-rose-950/40 p-4 space-y-3 shadow-xl shadow-rose-950/40 animate-pulse-slow">
        <div class="flex justify-between items-start">
          <div>
            <span class="inline-block px-2 py-0.5 rounded-full bg-rose-600 text-white text-[9px] font-black uppercase tracking-wider mb-1">
              🚨 АКТИВНЫЙ САБОТАЖ
            </span>
            <div class="text-base font-black text-white flex items-center gap-1.5">
              <span>${active.icon || '⚠️'}</span>
              <span>${active.title}</span>
            </div>
          </div>
          <div class="text-right">
            <div class="text-[10px] text-rose-300 font-bold">Осталось:</div>
            <div class="text-xs font-mono font-black text-amber-300">${formatSeconds(active.remaining_seconds)}</div>
          </div>
        </div>

        <div class="text-[11px] text-rose-100/90 leading-relaxed">
          ${active.description || ''}
        </div>

        <div class="rounded-xl bg-slate-950/60 border border-rose-500/30 p-2.5 space-y-1">
          <div class="text-[10px] font-bold text-rose-300 uppercase">Действующие эффекты:</div>
          ${effects.map(e => `<div class="text-[10px] text-slate-200 font-mono">• ${e}</div>`).join('')}
        </div>

        <button id="stop-sabotage-btn" class="w-full rounded-xl bg-rose-600 hover:bg-rose-500 active:scale-95 py-2.5 text-xs font-black text-white shadow-lg transition-all cursor-pointer">
          🛑 Завершить саботаж досрочно
        </button>
      </div>
    `;
  }

  const catalogHtml = catalog.map(spec => {
    const effects = buildEffectsList(spec);
    const isThisActive = active && active.sabotage_id === spec.id;
    return `
      <div class="glass-card rounded-2xl p-3 border ${isThisActive ? 'border-rose-500 bg-rose-950/20' : 'border-slate-800 bg-slate-900/60'} space-y-2">
        <div class="flex justify-between items-center">
          <div class="font-bold text-xs text-white flex items-center gap-1.5">
            <span class="text-base">${spec.icon}</span>
            <span>${spec.name}</span>
          </div>
          <span class="px-2 py-0.5 rounded-lg bg-slate-800 text-[10px] font-bold text-slate-300 font-mono">
            ⏳ ${spec.duration_hours} ч
          </span>
        </div>

        <div class="text-[11px] text-slate-400 leading-snug">
          ${spec.description}
        </div>

        <details class="text-[10px] text-slate-300">
          <summary class="cursor-pointer text-amber-400 font-bold hover:underline select-none">
            🔍 Подробные модификаторы (${effects.length})
          </summary>
          <div class="mt-1.5 space-y-0.5 pl-2 border-l-2 border-amber-500/40">
            ${effects.map(e => `<div class="font-mono text-slate-200">• ${e}</div>`).join('')}
          </div>
        </details>

        <div class="pt-1">
          ${isThisActive ? `
            <div class="w-full py-2 rounded-xl bg-rose-900/40 border border-rose-500/40 text-center text-[10px] font-black text-rose-300">
              🔴 ЭТОТ КРИЗИС ДЕЙСТВУЕТ ПРЯМО СЕЙЧАС
            </div>
          ` : `
            <button class="launch-sab-btn w-full py-2 rounded-xl ${active ? 'bg-slate-800 text-slate-500 cursor-not-allowed' : 'bg-amber-600 hover:bg-amber-500 text-slate-950 cursor-pointer'} text-[11px] font-black transition-all" data-id="${spec.id}" data-name="${spec.name}" ${active ? 'disabled' : ''}>
              ${active ? '⚠️ Дождитесь окончания текущего саботажа' : '⚠️ Запустить этот саботаж'}
            </button>
          `}
        </div>
      </div>
    `;
  }).join('');

  el.innerHTML = `
    <div class="space-y-3">
      <div class="flex justify-between items-center px-1">
        <div>
          <div class="text-xs font-black text-white uppercase tracking-wider">🎭 Экономические саботажи</div>
          <div class="text-[10px] text-slate-400">Управление кризисами и потрясениями рынка</div>
        </div>
        <button id="refresh-sab-btn" class="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs cursor-pointer">
          🔄
        </button>
      </div>

      ${activeCardHtml}

      <div class="space-y-2">
        <div class="text-[11px] font-bold text-slate-400 uppercase tracking-wide px-1">
          Каталог саботажей (${catalog.length})
        </div>
        <div class="grid grid-cols-1 gap-2.5">
          ${catalogHtml}
        </div>
      </div>
    </div>
  `;

  el.querySelector('#refresh-sab-btn')?.addEventListener('click', () => {
    loadCreatorSabotages(el, showToast);
  });

  el.querySelector('#stop-sabotage-btn')?.addEventListener('click', async (event) => {
    if (!confirm('Завершить действующий саботаж досрочно? Все рыночные параметры вернутся в норму.')) return;
    const btn = event.currentTarget;
    btn.disabled = true;
    btn.textContent = 'Останавливаю…';
    try {
      await NatAPI.stopCreatorSabotage('CREATOR_MANUAL_STOP');
      showToast('Саботаж успешно завершён!', 'success');
      await loadCreatorSabotages(el, showToast);
    } catch (e) {
      btn.disabled = false;
      btn.textContent = '🛑 Завершить саботаж досрочно';
      showToast(e.message, 'error');
    }
  });

  el.querySelectorAll('.launch-sab-btn').forEach(btn => {
    btn.addEventListener('click', async (event) => {
      const b = event.currentTarget;
      const sabId = b.dataset.id;
      const sabName = b.dataset.name;
      if (!confirm(`Вы действительно хотите активировать «${sabName}»?\n\nВсем игрокам биржи будет разослано экстренное оповещение.`)) {
        return;
      }
      b.disabled = true;
      b.textContent = 'Запускаю…';
      try {
        await NatAPI.launchCreatorSabotage(sabId);
        showToast(`Саботаж «${sabName}» успешно активирован!`, 'success');
        await loadCreatorSabotages(el, showToast);
      } catch (e) {
        b.disabled = false;
        b.textContent = '⚠️ Запустить этот саботаж';
        showToast(e.message, 'error');
      }
    });
  });
}
