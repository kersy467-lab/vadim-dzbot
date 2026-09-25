import { NatAPI } from '../api.js?v=20260925_deals_v9';
import { getSpecializationName } from '../localization.js?v=20260925_deals_v9';

const CATEGORIES = [
  ['assets', 'Активы'],
  ['territory', 'Земля'],
  ['army', 'Армия'],
  ['cash', 'Деньги'],
  ['company_value', 'Стоимость'],
  ['military_rating', 'Рейтинг'],
];

const esc = (value) => String(value ?? '').replace(/[&<>'"]/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
}[char]));
const number = (value) => Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: 0 });

export async function renderLeaderboard(container, showToast) {
  let category = 'assets';
  let page = 1;
  let data = null;

  async function load() {
    data = await NatAPI.getLeaderboard(category, page);
  }

  function valueLabel(row) {
    if (category === 'territory') return `${number(row.value)} земли`;
    if (category === 'army') return `${number(row.value)} силы`;
    if (category === 'military_rating') return `${number(row.value)} р.`;
    return `${number(row.value)} cash`;
  }

  function render() {
    const entries = data?.entries || [];
    const pages = Math.max(1, Math.ceil(Number(data?.total || 0) / Number(data?.page_size || 20)));
    container.innerHTML = `<div class="space-y-4 max-w-md mx-auto p-4 pb-24"><div><h2 class="text-xl font-black">Топ компаний</h2><p class="text-xs text-slate-500">Место считается сервером; акции и облигации включены в активы.</p></div><div class="flex gap-2 overflow-x-auto no-scrollbar pb-1">${CATEGORIES.map(([id, title]) => `<button class="leaderboard-category px-3 py-2 rounded-xl whitespace-nowrap text-xs font-bold ${id === category ? 'bg-blue-600 text-white' : 'bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700'}" data-category="${id}">${title}</button>`).join('')}</div><div class="glass-card rounded-2xl p-3 space-y-2"><div class="flex justify-between text-[10px] text-slate-400"><span>${esc(data?.category_title || '')}</span><span>Стр. ${data?.page || 1} из ${pages}</span></div>${entries.map(row => `<div class="flex items-center justify-between gap-3 p-2.5 rounded-xl ${row.company_id === data?.my_entry?.company_id ? 'bg-blue-950/30 border border-blue-500/30' : 'bg-slate-50 dark:bg-slate-800/50'}"><div class="min-w-0"><div class="text-xs font-black truncate"><span class="text-amber-500">#${row.rank}</span> ${esc(row.company_name)}</div><div class="text-[10px] text-slate-400">ур. ${row.level} · ${esc(getSpecializationName(row.specialization))} · армия ${number(row.army)} · ${row.military_rating} р.</div></div><div class="text-xs font-mono font-bold text-right whitespace-nowrap">${valueLabel(row)}</div></div>`).join('') || '<div class="text-center py-6 text-xs text-slate-500">Компаний пока нет.</div>'}<div class="flex items-center justify-between pt-1"><button id="leaderboard-prev" class="px-3 py-2 rounded-lg bg-slate-800 text-xs disabled:opacity-40" ${page <= 1 ? 'disabled' : ''}>← Назад</button><div class="text-[10px] text-slate-400">Ваша позиция: <b class="text-white">${data?.my_rank ? `#${data.my_rank}` : '—'}</b></div><button id="leaderboard-next" class="px-3 py-2 rounded-lg bg-slate-800 text-xs disabled:opacity-40" ${page >= pages ? 'disabled' : ''}>Далее →</button></div></div></div>`;
    // Mouse wheel → horizontal scroll on the tabs row (PC / Telegram Desktop)
    const tabsRow = container.querySelector('.flex.gap-2.overflow-x-auto');
    if (tabsRow) {
      tabsRow.addEventListener('wheel', (e) => {
        if (e.deltaY !== 0) { e.preventDefault(); tabsRow.scrollLeft += e.deltaY; }
      }, { passive: false });
    }
    container.querySelectorAll('.leaderboard-category').forEach(button => button.addEventListener('click', async () => {
      category = button.dataset.category;
      page = 1;
      try { await load(); render(); } catch (error) { showToast(error.message, 'error'); }
    }));

    container.querySelector('#leaderboard-prev')?.addEventListener('click', async () => {
      page -= 1;
      try { await load(); render(); } catch (error) { showToast(error.message, 'error'); }
    });
    container.querySelector('#leaderboard-next')?.addEventListener('click', async () => {
      page += 1;
      try { await load(); render(); } catch (error) { showToast(error.message, 'error'); }
    });
  }

  await load();
  render();
}
