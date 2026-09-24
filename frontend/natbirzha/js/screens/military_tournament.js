const TOURNAMENT_LABELS = {
  AUTO: 'Автоматический', ACTIVE: 'Идёт', PENDING: 'Запланирован', SCHEDULED: 'Запланирован', FINISHED: 'Завершён', RESOLVED: 'Завершён',
};

const esc = (value) => String(value ?? '').replace(/[&<>'"]/g, ch => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
}[ch]));
const number = (value) => Number(value || 0).toLocaleString('ru-RU');
const tournamentLabel = (value) => TOURNAMENT_LABELS[value] || 'Турнир';

function timeLeft(value) {
  if (!value) return 'нет таймера';
  const seconds = Math.max(0, Math.floor((new Date(value).getTime() - Date.now()) / 1000));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return seconds <= 0 ? 'завершено' : `${hours} ч ${minutes} мин`;
}

export function renderTournamentSection({ tournamentData, tournamentTargets, army }) {
  const tournament = tournamentData?.tournament;
  if (!tournament) return '<div class="glass-card rounded-2xl p-5 text-xs text-slate-400 text-center">Следующий турнир создаётся автоматически. Участвовать можно после формирования армии.</div>';
  const rewards = tournament.rewards_pvc || [150, 100, 70];
  const isActive = tournament.status === 'ACTIVE';
  const canJoin = !tournament.is_participant && ['PENDING', 'SCHEDULED', 'ACTIVE'].includes(tournament.status);
  const hasArmy = Number(army.army_strength || 0) > 0;
  const joinAction = canJoin
    ? `<div class="space-y-1"><button class="tournament-join-btn w-full py-2 rounded-xl bg-amber-500 text-slate-950 text-xs font-bold disabled:opacity-50" ${hasArmy ? '' : 'disabled'}>${hasArmy ? 'Войти в турнир' : 'Сначала сформируйте армию'}</button><div class="text-[9px] text-slate-400">Запись доступна до окончания турнира.</div></div>`
    : '';
  return `<div class="space-y-3">
    <div class="glass-card rounded-2xl p-4 border-l-4 border-l-amber-500 space-y-3">
      <div class="flex justify-between"><div><div class="text-sm font-black">Турнир #${tournament.cycle_number || tournament.id}</div><div class="text-[10px] text-slate-400">${esc(tournamentLabel(tournament.tournament_type || 'AUTO'))} · ${esc(tournamentLabel(tournament.status))}</div></div><div class="text-right text-[10px]"><div class="text-amber-500 font-bold">${timeLeft(tournament.finish_time)}</div><div>${tournament.is_participant ? 'Вы участвуете' : 'Нет участия'}</div></div></div>
      <div class="grid grid-cols-3 gap-2 text-center">${rewards.map((reward, i) => `<div class="rounded-xl bg-amber-50 dark:bg-amber-950/30 p-2"><div class="text-[9px] text-slate-400">${i + 1} место</div><div class="text-xs font-black text-amber-500">${reward} PVC</div></div>`).join('')}</div>
      ${joinAction}
    </div>
    <div class="glass-card rounded-2xl p-4 space-y-2"><h3 class="text-xs font-bold uppercase text-slate-400">Топ по силе армии</h3>${(tournamentData.participants || []).slice(0, 10).map((row, index) => `<div class="flex justify-between text-xs p-2 rounded-lg bg-slate-50 dark:bg-slate-800/50"><span><b>#${row.rank || index + 1}</b> ${esc(row.company_name)}</span><span class="font-mono">${number(row.current_strength || row.strength)} · ${row.rating || 1000} р.</span></div>`).join('') || '<div class="text-xs text-slate-400">Нет участников</div>'}</div>
    ${isActive ? `<div class="glass-card rounded-2xl p-4 space-y-2"><h3 class="text-xs font-bold uppercase text-slate-400">Цели PvP</h3>${tournamentTargets.map(target => `<div class="flex items-center justify-between gap-2 p-2 rounded-xl bg-slate-50 dark:bg-slate-800/50"><div><div class="text-xs font-bold">${esc(target.company_name)}</div><div class="text-[9px] text-slate-400">≈${number(target.approximate_strength)} силы · ${target.rating} р. · ${target.wins}/${target.losses}</div></div><button class="attack-pvp-btn px-3 py-1.5 rounded-lg ${target.attack_available ? 'bg-rose-600 text-white' : 'bg-slate-200 text-slate-400'} text-xs font-bold disabled:opacity-50" data-company-id="${target.company_id}" ${target.attack_available ? '' : 'disabled'}>${target.attack_available ? 'Атака' : timeLeft(target.cooldown_until)}</button></div>`).join('') || '<div class="text-xs text-slate-400">Других участников пока нет</div>'}</div>` : '<div class="glass-card rounded-2xl p-4 text-xs text-slate-400">PvP доступно только в активные 18 часов турнира.</div>'}
  </div>`;
}
