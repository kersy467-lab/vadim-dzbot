function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));
}

function number(value, digits = 0) {
  return Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: digits });
}

function leaderboard(title, data, metric) {
  if (!data) return '';
  const rows = (data.leaders || []).map((row) => {
    let value = '';
    if (metric === 'cash') value = `${number(row.cash, 2)} cash`;
    if (metric === 'level') value = `ур. ${number(row.level)} · ${number(row.xp)} XP`;
    if (metric === 'production_24h') value = `${number(row.production_24h, 2)} cash-экв.`;
    return `<li class="next-game-rank-row ${row.is_mine ? 'is-mine' : ''}"><span class="next-game-rank-place">#${number(row.rank)}</span><span class="next-game-rank-company"><b>${esc(row.name)}</b><small>${esc(row.sector_name)}</small></span><strong>${value}</strong></li>`;
  }).join('');
  const mine = data.my_rank;
  const myValue = mine ? metric === 'cash' ? `${number(mine.cash, 2)} cash`
    : metric === 'level' ? `ур. ${number(mine.level)} · ${number(mine.xp)} XP`
      : `${number(mine.production_24h, 2)} cash-экв.` : '—';
  const myRow = mine && mine.rank > (data.leaders || []).length
    ? `<li class="next-game-rank-row is-mine"><span class="next-game-rank-place">#${number(mine.rank)}</span><span class="next-game-rank-company"><b>${esc(mine.name)} · вы</b><small>${esc(mine.sector_name)}</small></span><strong>${myValue}</strong></li>` : '';
  return `<article class="next-game-panel next-game-leaderboard"><h2>${esc(title)}</h2><ol>${rows || '<li class="next-game-rank-empty">Компаний пока нет</li>'}${myRow}</ol></article>`;
}

export function renderCompetition(state) {
  if (!state) {
    return '<section class="next-game-panel"><h2>Рейтинг компаний</h2><p>Не удалось загрузить рейтинг.</p><button type="button" data-next-competition-retry class="next-game-primary">Повторить</button></section>';
  }
  const metrics = state.rankings || {};
  return `<section class="next-game-panel next-game-competition"><header><div><h2>Лига корпораций 2.0</h2><p>${number(state.company_count)} компаний · отдельный тестовый рейтинг, старая экономика не затрагивается.</p></div></header><div class="next-game-rank-grid">${leaderboard('Капитал', metrics.cash, 'cash')}${leaderboard('Развитие', metrics.level, 'level')}${leaderboard('Выпуск за сутки', metrics.production_24h, 'production_24h')}</div><p class="next-game-bank-note">Выпуск оценивается по фактическому производству за последние 24 часа и базовым ценам 2.0.</p></section>`;
}
