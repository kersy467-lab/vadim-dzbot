import { NatAPI } from '../api.js?v=20260925_deals_v6';

export async function loadCreatorOverview(el, showToast) {
  const [data, metrics] = await Promise.all([
    NatAPI.getCreatorOverview(),
    NatAPI.getCreatorEconomyMetrics(7),
  ]);
  el.innerHTML = `
    <div class="glass-card rounded-2xl p-4 border border-amber-500/30 bg-amber-950/20 space-y-2">
      <div class="text-xs text-amber-400 font-bold uppercase tracking-wider">Государственная Казна</div>
      <div class="text-2xl font-black text-white font-mono">${Math.round(data.treasury_cash).toLocaleString('ru-RU')} ₽</div>
      <div class="text-[10px] text-slate-400">Изолированный баланс государства (не смешивается с игроками)</div>
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
