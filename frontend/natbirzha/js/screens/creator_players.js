import { NatAPI } from '../api.js?v=20260925_deals_v9';

const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[char]));

export async function loadCreatorPlayersTab(el, showToast) {
  let search = '';
  let sort = 'last_activity_at';
  let page = 1;

  async function reload() {
    const data = await NatAPI.getCreatorPlayers({ search, sort, page });
    const pages = Math.max(1, Math.ceil(data.total / data.page_size));
    el.innerHTML = `<div class="space-y-3">
      <div class="glass-card rounded-2xl p-3 space-y-2">
        <div class="text-xs font-bold text-amber-400 uppercase">Список игроков</div>
        <form id="creator-player-filter" class="flex gap-2">
          <input id="creator-player-search" value="${escapeHtml(search)}" class="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-950 px-2 py-2 text-xs text-white" placeholder="Компания или Telegram">
          <select id="creator-player-sort" class="rounded-lg border border-slate-700 bg-slate-950 px-2 py-2 text-[10px] text-white">
            <option value="last_activity_at" ${sort === 'last_activity_at' ? 'selected' : ''}>Активность</option>
            <option value="assets" ${sort === 'assets' ? 'selected' : ''}>Активы</option>
            <option value="level" ${sort === 'level' ? 'selected' : ''}>Уровень</option>
            <option value="army" ${sort === 'army' ? 'selected' : ''}>Армия</option>
            <option value="military_rating" ${sort === 'military_rating' ? 'selected' : ''}>Рейтинг</option>
            <option value="pvc_balance" ${sort === 'pvc_balance' ? 'selected' : ''}>PVC</option>
          </select>
          <button class="rounded-lg bg-amber-500 px-3 text-xs font-black text-slate-950">Найти</button>
        </form>
        <div class="text-[10px] text-slate-500">${data.total} компаний · стр. ${data.page}/${pages}</div>
      </div>
      <div class="space-y-2">${data.players.map((player) => `<article class="glass-card rounded-2xl p-3 text-[10px]">
        <div class="flex justify-between gap-2"><div class="min-w-0"><div class="truncate text-xs font-black text-white">${escapeHtml(player.company_name)}</div>
          <div class="truncate text-slate-400">${escapeHtml(player.telegram_name || player.telegram_username || 'Telegram не указан')} · ур. ${player.level}</div></div>
          <div class="text-right font-mono text-amber-400">${Math.round(player.assets).toLocaleString('ru-RU')}<div class="text-[9px] text-slate-500">активы</div></div></div>
        <div class="mt-2 grid grid-cols-3 gap-1.5 text-slate-400"><span>Cash <b class="text-slate-100">${Math.round(player.cash).toLocaleString('ru-RU')}</b></span>
          <span>Земля <b class="text-slate-100">${player.territory}</b></span><span>Заводы <b class="text-slate-100">${player.factory_count}</b></span>
          <span>Армия <b class="text-slate-100">${Math.round(player.army).toLocaleString('ru-RU')}</b></span><span>Рейтинг <b class="text-slate-100">${player.military_rating}</b></span>
          <span>PVC <b class="text-amber-400">${player.pvc_balance}</b></span></div>
        <div class="mt-1 text-[9px] text-slate-500">Последняя игровая активность: ${new Date(player.last_activity_at).toLocaleString('ru-RU')}</div>
        <div class="mt-2 grid grid-cols-2 gap-2"><button data-id="${player.company_id}" class="creator-player-warning rounded-lg border border-amber-500/40 bg-amber-950/30 px-2 py-2 text-[10px] font-bold text-amber-300">⚠️ Предупредить</button>
          <button data-id="${player.company_id}" data-name="${escapeHtml(player.company_name)}" class="creator-player-bankruptcy rounded-lg border border-rose-500/40 bg-rose-950/30 px-2 py-2 text-[10px] font-bold text-rose-300">Банкротство</button></div>
      </article>`).join('') || '<div class="glass-card rounded-2xl p-5 text-center text-xs text-slate-500">Ничего не найдено.</div>'}</div>
      <div class="flex justify-between"><button id="creator-players-prev" class="rounded-lg bg-slate-800 px-3 py-2 text-xs disabled:opacity-40" ${page <= 1 ? 'disabled' : ''}>← Назад</button>
        <button id="creator-players-next" class="rounded-lg bg-slate-800 px-3 py-2 text-xs disabled:opacity-40" ${page >= pages ? 'disabled' : ''}>Далее →</button></div>
    </div>`;

    el.querySelector('#creator-player-filter')?.addEventListener('submit', async (event) => {
      event.preventDefault();
      search = el.querySelector('#creator-player-search').value.trim();
      sort = el.querySelector('#creator-player-sort').value;
      page = 1;
      try { await reload(); } catch (error) { showToast(error.message, 'error'); }
    });
    el.querySelector('#creator-players-prev')?.addEventListener('click', async () => {
      page -= 1;
      try { await reload(); } catch (error) { showToast(error.message, 'error'); }
    });
    el.querySelector('#creator-players-next')?.addEventListener('click', async () => {
      page += 1;
      try { await reload(); } catch (error) { showToast(error.message, 'error'); }
    });
    el.querySelectorAll('.creator-player-warning').forEach((button) => button.addEventListener('click', async () => {
      const reason = prompt('Причина предупреждения игроку:')?.trim();
      if (!reason) return;
      button.disabled = true;
      try {
        await NatAPI.sendCreatorWarning(button.dataset.id, reason);
        showToast('Предупреждение отправлено.', 'success');
      } catch (error) {
        showToast(error.message, 'error');
        button.disabled = false;
      }
    }));
    el.querySelectorAll('.creator-player-bankruptcy').forEach((button) => button.addEventListener('click', async () => {
      const name = button.dataset.name || 'компании';
      if (!confirm(`Объявить компанию «${name}» банкротом? 70% заводов и предприятий выставятся на рынок банкротов; деньги и вложенные акции перейдут государству; 70% сырья продадутся по активным заявкам.`)) return;
      button.disabled = true;
      try {
        const result = await NatAPI.declareCreatorBankruptcy(button.dataset.id);
        showToast(`Банкротство оформлено: ${Number(result.cash_transferred).toLocaleString('ru-RU')} cash передано казне, ${Number(result.lots_created)} предприятий выставлено на рынок банкротов.`, 'success');
        await reload();
      } catch (error) {
        showToast(error.message, 'error');
        button.disabled = false;
      }
    }));
  }

  await reload();
}
