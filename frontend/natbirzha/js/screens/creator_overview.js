import { NatAPI } from '../api.js?v=20261009_perf_tuning_v1';

export async function loadCreatorOverview(el, showToast) {
  const [data, metrics, maintData, stateEconomy] = await Promise.all([
    NatAPI.getCreatorOverview(),
    NatAPI.getCreatorEconomyMetrics(7),
    NatAPI.getMaintenanceStatus().catch(() => ({ maintenance_mode: false })),
    NatAPI.getCreatorStateEconomy(),
  ]);
  const isMaint = Boolean(maintData?.maintenance_mode);

  el.innerHTML = `
    <div class="glass-card rounded-2xl p-4 border border-amber-500/30 bg-amber-950/20 space-y-2">
      <div class="text-xs text-amber-400 font-bold uppercase tracking-wider">Государственная Казна</div>
      <div class="text-2xl font-black text-white font-mono">${Math.round(stateEconomy.treasury_cash).toLocaleString('ru-RU')} cash</div>
      <div class="text-[10px] text-slate-400">Изолированный баланс государства (не смешивается с игроками)</div>
    </div>
    <div class="glass-card rounded-2xl p-4 border space-y-3" style="background-color:${stateEconomy.default_mode ? '#FFF1F1' : '#EEF7F1'};border-color:${stateEconomy.default_mode ? '#E7A7AD' : '#A9CEB7'}">
      <div class="flex items-start justify-between gap-3">
        <div>
          <div class="text-xs font-black uppercase tracking-wide" style="color:${stateEconomy.default_mode ? '#8E303B' : '#18583C'}">${stateEconomy.default_mode ? 'Дефолт казны' : 'Казна работает штатно'}</div>
          <div class="mt-1 text-[10px]" style="color:#344A3F">Налог ${Number(stateEconomy.tax_rate_pct).toLocaleString('ru-RU')}% · порог дефолта ${Number(stateEconomy.default_threshold_cash).toLocaleString('ru-RU')} cash</div>
          <div class="mt-1 text-[10px]" style="color:#465B50">При дефолте выкуп у игроков дешевле на 10%, продажа NPC дороже на 10%.</div>
        </div>
      </div>
      <div class="flex items-center justify-between gap-3 border-t pt-3" style="border-color:#C9DDD0">
        <div>
          <div class="text-xs font-bold" style="color:#263B30">Экспорт госрезерва</div>
          <div class="text-[10px]" style="color:#4E6256">${stateEconomy.export_fraction_pct}% запасов каждые ${stateEconomy.export_interval_minutes} мин · выручка поступает в казну</div>
        </div>
        <button id="creator-toggle-state-exports" class="shrink-0 rounded-xl px-3 py-2 text-[10px] font-black ${stateEconomy.foreign_exports_enabled ? 'bg-emerald-500 text-slate-950' : 'bg-slate-800 text-slate-200 border border-slate-600'}">${stateEconomy.foreign_exports_enabled ? 'ЭКСПОРТ ВКЛ.' : 'ВКЛЮЧИТЬ'}</button>
      </div>
      ${stateEconomy.stock.length ? `<div class="space-y-1 border-t pt-2" style="border-color:#C9DDD0"><div class="text-[10px] font-bold" style="color:#344A3F">Запасы для экспорта</div>${stateEconomy.stock.map((row) => `<div class="flex justify-between gap-2 text-[10px]" style="color:#344A3F"><span>${row.name}: ${Number(row.quantity).toLocaleString('ru-RU')} (${Number(row.export_quantity_per_cycle).toLocaleString('ru-RU')} за цикл)</span><span class="shrink-0 font-mono font-bold" style="color:#176E4B">+${Number(row.export_estimate).toLocaleString('ru-RU')}</span></div>`).join('')}</div>` : '<div class="border-t pt-2 text-[10px]" style="border-color:#C9DDD0;color:#4E6256">Запасов для экспорта пока нет. Товары появятся, когда компании продадут их Госрезерву.</div>'}
    </div>
    <div class="glass-card rounded-2xl p-4 border ${isMaint ? 'border-amber-500/60 bg-amber-950/30' : 'border-slate-800'} space-y-2">
      <div class="flex items-center justify-between">
        <div>
          <div class="text-xs font-black text-amber-400 uppercase tracking-wide flex items-center gap-1.5">
            <span>🛠️</span> Технический перерыв
          </div>
          <div class="text-[10px] text-slate-400">Плашка видна всем игрокам, кроме админов</div>
        </div>
        <button id="creator-toggle-maint-btn" class="px-3 py-1.5 rounded-xl font-bold text-xs transition-all ${isMaint ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20' : 'bg-slate-800 text-slate-300 border border-slate-700'}">
          ${isMaint ? '🔴 ВКЛЮЧЕН' : '⚪ ВЫКЛЮЧЕН'}
        </button>
      </div>
    </div>
    <div class="grid grid-cols-2 gap-2">
      ${stat('Компаний в игре', data.total_companies, 'text-white')}
      ${stat('Построено заводов', data.total_factories, 'text-white')}
      ${stat('Активных ордеров', data.active_orders, 'text-emerald-400')}
      ${stat('Ограничений цен', data.active_restrictions, 'text-rose-400')}
    </div>
    <div class="glass-card rounded-2xl p-4 space-y-2">
      <div class="text-xs font-bold text-violet-300">Экономика · последние ${metrics.window_days} дней</div>
      <div class="grid grid-cols-3 gap-2 text-center">
        ${metric('Источники', metrics.cash_sources, 'text-emerald-400')}
        ${metric('Стоки', metrics.cash_sinks, 'text-rose-400')}
        ${metric('Net faucet', metrics.net_cash_faucet, Number(metrics.net_cash_faucet) > 0 ? 'text-amber-300' : 'text-sky-300')}
      </div>
      <div class="text-[9px] text-slate-500">${metrics.events} событий. Баланс меняйте по данным, а не по одному удачному/неудачному игроку.</div>
    </div>
    <div class="glass-card rounded-2xl p-4 space-y-2">
      <div class="text-xs font-bold text-amber-300">Тестовое начисление себе</div>
      <div class="text-[10px] text-slate-400">Только собственной компании Создателя; операция попадает в аудит и экономическую телеметрию.</div>
      <div class="grid grid-cols-2 gap-2"><input id="creator-self-cash" type="number" min="0" max="10000000" placeholder="cash" class="rounded-xl bg-slate-950 border border-slate-700 px-3 py-2 text-xs"><input id="creator-self-pvc" type="number" min="0" max="10000" placeholder="PVC" class="rounded-xl bg-slate-950 border border-slate-700 px-3 py-2 text-xs"></div>
      <button id="creator-self-grant" class="w-full rounded-xl bg-amber-500 py-2 text-xs font-black text-slate-950">Начислить себе</button>
    </div>
    <div class="glass-card rounded-2xl p-4 space-y-1"><div class="text-xs text-slate-400 font-bold">Денежная масса в обороте</div><div class="text-base font-black font-mono text-blue-400">${Math.round(data.cash_in_circulation).toLocaleString('ru-RU')} ₽</div></div>`;

  el.querySelector('#creator-toggle-maint-btn')?.addEventListener('click', async () => {
    try {
      const res = await NatAPI.toggleMaintenance();
      showToast(res.maintenance_mode ? 'Технический перерыв включен' : 'Технический перерыв выключен', 'info');
      await loadCreatorOverview(el, showToast);
    } catch (error) {
      showToast(error.message, 'error');
    }
  });

  el.querySelector('#creator-toggle-state-exports')?.addEventListener('click', async () => {
    try {
      await NatAPI.setCreatorForeignExports(!stateEconomy.foreign_exports_enabled);
      showToast(stateEconomy.foreign_exports_enabled ? 'Экспорт запасов остановлен' : 'Экспорт запасов включён', 'success');
      await loadCreatorOverview(el, showToast);
    } catch (error) {
      showToast(error.message, 'error');
    }
  });

  el.querySelector('#creator-self-grant')?.addEventListener('click', async () => {
    const cash = Number(el.querySelector('#creator-self-cash')?.value || 0);
    const pvc = Number(el.querySelector('#creator-self-pvc')?.value || 0);
    if (cash <= 0 && pvc <= 0) return showToast('Укажите cash или PVC', 'error');
    if (!confirm(`Начислить собственной компании ${cash || 0} cash и ${pvc || 0} PVC?`)) return;
    try {
      const result = await NatAPI.grantCreatorSelf(cash, pvc);
      showToast(`Баланс: ${Number(result.cash_after).toLocaleString('ru-RU')} cash · ${result.pvc_after} PVC`, 'success');
      await loadCreatorOverview(el, showToast);
    } catch (error) { showToast(error.message, 'error'); }
  });
}

function stat(label, value, tone) {
  return `<div class="glass-card rounded-xl p-3"><div class="text-[10px] text-slate-400">${label}</div><div class="text-lg font-bold font-mono ${tone}">${Number(value || 0).toLocaleString('ru-RU')}</div></div>`;
}
function metric(label, value, tone) {
  return `<div class="rounded-xl bg-slate-950/50 p-2"><div class="text-[9px] text-slate-500">${label}</div><div class="text-xs font-black font-mono ${tone}">${Math.round(Number(value || 0)).toLocaleString('ru-RU')}</div></div>`;
}
