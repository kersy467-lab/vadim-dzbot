(function () {
  'use strict';

  let room = null;
  let type = 'ege_stress_duel';
  let classmates = [];
  let leaderboard = [];
  let poll = null;
  let leaderboardPoll = null;
  let sending = false;
  let refreshGeneration = 0;
  let sendError = '';
  let myRating = { rating: 0, rank: 'Рекрут', medal: 'Рекрут', rank_image: '/static/assets/ranks/recruit.png' };

  let timerTicker = null;
  let localRemaining = 35.0;
  let timerLimit = 35.0;
  let timerMode = 'main';
  let timerExpiredHandled = false;

  const esc = value => String(value ?? '').replace(/[&<>\"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch]));
  const myName = () => window.currentUser?.ege_nickname || window.currentUser?.full_name || 'Игрок';
  const rankName = profile => profile?.rank || profile?.medal || 'Рекрут';
  const rankImage = profile => profile?.rank_image || profile?.medal_image || '/static/assets/ranks/recruit.png';
  const ratingText = profile => `${esc(rankName(profile))} · ${Number(profile?.rating || 0)} MMR`;

  function clearPoll() {
    if (poll) clearInterval(poll);
    poll = null;
  }

  function clearLeaderboardPoll() {
    if (leaderboardPoll) clearInterval(leaderboardPoll);
    leaderboardPoll = null;
  }

  function clearTimer() {
    if (timerTicker) clearInterval(timerTicker);
    timerTicker = null;
  }

  function syncTimerWithRoom() {
    if (!room || room.status !== 'playing' || room.your_finished) {
      clearTimer();
      return;
    }
    const mode = room.timer_mode || (room.is_sudden_death ? 'sudden' : 'main');
    const limit = Number(room.timer_limit || (mode === 'sudden' ? 5 : 35));
    const serverRemaining = Number(room.time_remaining !== undefined ? room.time_remaining : limit);
    if (!timerTicker || timerMode !== mode || Math.abs(localRemaining - serverRemaining) > 1.2) {
      timerMode = mode;
      timerLimit = limit;
      localRemaining = Math.max(0, serverRemaining);
      timerExpiredHandled = false;
      startTimer();
    }
  }

  function startTimer() {
    clearTimer();
    timerTicker = setInterval(() => {
      if (!room || room.status !== 'playing' || room.your_finished) {
        clearTimer();
        return;
      }
      localRemaining = Math.max(0, localRemaining - 0.1);
      updateTimerUI();
      if (localRemaining <= 0) {
        clearTimer();
        if (!timerExpiredHandled && !sending) {
          timerExpiredHandled = true;
          answer('__timeout__');
        }
      }
    }, 100);
  }

  function updateTimerUI() {
    const valEl = document.getElementById('ege-timer-val');
    const barEl = document.getElementById('ege-timer-bar');
    if (!valEl) return;
    const isDanger = localRemaining <= (timerMode === 'sudden' ? 2.0 : 5.0);
    valEl.textContent = `${localRemaining.toFixed(1)} с`;
    valEl.className = `font-mono text-xs font-black transition-colors ${isDanger ? 'text-red-500 animate-pulse' : 'text-blue-600'}`;
    if (barEl) {
      const pct = Math.max(0, Math.min(100, (localRemaining / timerLimit) * 100));
      barEl.style.width = `${pct}%`;
      barEl.className = `h-full rounded-full transition-all duration-100 ${isDanger ? 'bg-red-500' : 'bg-blue-600'}`;
    }
  }

  function startLeaderboardPoll() {
    clearLeaderboardPoll();
    leaderboardPoll = setInterval(async () => {
      if (room) return;
      try {
        const [profile, top] = await Promise.all([window.api.getEgeRating(), window.api.getEgeLeaderboard()]);
        myRating = profile || myRating;
        leaderboard = top?.players || leaderboard;
        redraw();
      } catch (_) {}
    }, 600000);
  }

  function renderRankCard(profile) {
    const place = profile?.top_position ? `#${Number(profile.top_position)} в общем топе` : 'Топ обновляется каждые 10 минут';
    return `<div class="theme-card rounded-3xl p-4 flex items-center gap-3">
      <img src="${esc(rankImage(profile))}" alt="${esc(rankName(profile))}" class="w-20 h-20 object-contain rounded-2xl">
      <div class="min-w-0 text-left"><div class="text-[11px] uppercase tracking-wider text-slate-400 font-bold">${esc(myName())}</div>
      <div class="font-black text-lg">${esc(rankName(profile))}</div><div class="text-blue-600 font-black">${Number(profile?.rating || 0)} MMR</div>
      <div class="text-[11px] text-slate-400">${esc(place)}</div></div></div>`;
  }

  function renderTop() {
    const rows = (leaderboard || []).slice(0, 10).map(p => `<div class="flex items-center gap-2 py-2 border-b border-slate-100 dark:border-slate-800 last:border-0">
      <span class="w-7 text-center font-black text-xs">#${Number(p.position)}</span>
      <img src="${esc(p.rank_image)}" class="w-9 h-9 object-contain" alt="">
      <span class="flex-1 min-w-0"><span class="block truncate text-xs font-bold">${esc(p.nickname)}</span><span class="block text-[10px] text-slate-400">${esc(p.rank)}</span></span>
      <span class="text-xs font-black">${Number(p.rating)} MMR</span>
    </div>`).join('');
    return `<div class="theme-card rounded-2xl p-3"><div class="flex items-center justify-between mb-1"><span class="font-black text-sm">🏆 Общий топ</span><span class="text-[10px] text-slate-400">обновление ~10 мин</span></div>${rows || '<p class="text-xs text-slate-400 py-3 text-center">Пока нет игроков в рейтинге.</p>'}</div>`;
  }

  function renderLobby() {
    const names = classmates.map(c => `<button onclick="window.EGE.inviteDuel(${Number(c.tg_id)}, '${esc(c.name).replace(/'/g, '')}')" class="w-full flex justify-between items-center p-3 rounded-2xl bg-slate-50 dark:bg-slate-800 text-left">
      <span class="flex items-center gap-2 min-w-0"><img src="${esc(rankImage(c))}" class="w-10 h-10 object-contain"><span class="min-w-0"><span class="font-bold text-sm block truncate">${esc(c.name || 'Игрок')}</span><span class="text-[11px] text-slate-400">${ratingText(c)}</span></span></span><span class="text-xs text-blue-600 font-bold">Вызвать ⚔️</span>
    </button>`).join('') || '<p class="text-xs text-slate-400 text-center py-3">Пока некого вызвать. Другому игроку нужно запустить бота и выбрать ник.</p>';
    return `<div class="space-y-3">
      <div class="text-center"><div class="text-3xl">🎓⚔️</div><h2 class="font-black text-xl">ЕГЭ Арена</h2><p class="text-xs text-slate-500">Рейтинговые дуэли по русскому языку</p></div>
      ${renderRankCard(myRating)}
      <div class="theme-card rounded-3xl p-4 space-y-3"><div class="grid grid-cols-2 gap-2"><button onclick="window.EGE.duelType('ege_stress_duel')" class="p-3 rounded-2xl font-bold text-xs ${type === 'ege_stress_duel' ? 'bg-blue-600 text-white' : 'bg-slate-100 dark:bg-slate-700'}">Ударения</button><button onclick="window.EGE.duelType('ege_vocabulary_duel')" class="p-3 rounded-2xl font-bold text-xs ${type === 'ege_vocabulary_duel' ? 'bg-blue-600 text-white' : 'bg-slate-100 dark:bg-slate-700'}">Словарные слова</button></div><button onclick="window.EGE.findDuel()" ${sending ? 'disabled' : ''} class="w-full py-3 rounded-2xl bg-blue-600 text-white font-black hover:bg-blue-700 disabled:opacity-60">${sending ? '🔎 Ищем дуэль…' : '🔍 Найти дуэль'}</button>${sendError ? `<p class="text-xs text-red-600 text-center">${esc(sendError)}</p>` : ''}<p class="text-[11px] text-slate-400 text-center">10 вопросов · победа +30 MMR · поражение −25 MMR</p></div>
      <div class="theme-card rounded-2xl p-3 space-y-2"><div class="flex justify-between"><p class="text-xs font-bold text-slate-500">Игроки</p><button onclick="window.EGE.editArenaNickname()" class="text-[11px] text-blue-600 font-bold">✏️ Ник</button></div>${names}</div>
      ${renderTop()}
    </div>`;
  }

  function renderBattle() {
    syncTimerWithRoom();
    const own = Number(room.your_answers || 0), all = Number(room.round_size || 10);
    const isSudden = Boolean(room.is_sudden_death || (room.sudden_round && Number(room.sudden_round) > 0));
    const suddenRound = Number(room.sudden_round || 0);

    if (room.your_finished || own >= all) {
      clearTimer();
      const correct = own - Number(room.your_errors || 0);
      const waitText = isSudden
        ? 'Вы ответили на дополнительный вопрос. Ждём ответ соперника — дуэль идёт до первой ошибки!'
        : 'Результат сохранён. Ждём, пока соперник завершит все задания — победитель пока не определяется.';
      const badge = isSudden
        ? `<div class="inline-block px-3 py-1 rounded-full bg-amber-500/20 text-amber-500 font-black text-xs mb-1">⚡ Внезапная смерть! (Раунд ${suddenRound})</div>`
        : '';
      return `<div class="theme-card rounded-3xl p-6 text-center space-y-3">${badge}<div class="text-4xl">✅</div><h3 class="font-black">Вы закончили</h3><p class="text-sm">Правильных: <b>${correct}</b> · ошибок: <b>${Number(room.your_errors || 0)}</b></p><p class="text-xs text-slate-500">${waitText}</p><div class="text-xs font-bold text-blue-600">Соперник: ${Number(room.opponent_answers || 0)}/${all}</div></div>`;
    }
    const q = room.question;
    if (!q) return `<div class="theme-card rounded-3xl p-6 text-center"><div class="text-4xl">⏳</div><p class="text-xs mt-2">Получаем следующее слово…</p></div>`;
    let task = '';
    if (q.mode === 'stress') {
      task = `<p class="text-xs text-slate-500">Нажмите ударную гласную</p><div class="flex flex-wrap justify-center gap-2 py-3">${[...q.word].map((letter, i) => q.vowel_indexes.includes(i) ? `<button ${sending ? 'disabled' : ''} onclick="window.EGE.duelAnswer(${i})" class="w-10 h-12 rounded-2xl bg-slate-100 dark:bg-slate-700 font-black text-xl hover:scale-105 active:scale-95 transition-transform">${letter}</button>` : `<span class="w-7 h-12 flex items-center justify-center font-black text-xl">${letter}</span>`).join('')}</div>`;
    } else {
      task = `<p class="text-xs text-slate-500">Впишите словарное слово полностью</p><div class="text-3xl font-black py-3 tracking-[0.18em]">${esc(q.masked)}</div><input id="ege-duel-vocab-input" ${sending ? 'disabled' : ''} onkeydown="if(event.key==='Enter') window.EGE.duelCheck()" placeholder="Напишите слово" class="w-full px-4 py-3 rounded-2xl border text-center font-bold dark:bg-slate-700"><button ${sending ? 'disabled' : ''} onclick="window.EGE.duelCheck()" class="mt-2 w-full py-3 rounded-2xl bg-blue-600 text-white font-bold hover:bg-blue-700 active:scale-98 transition-all">Проверить</button>`;
    }
    const feedback = sending ? '<p class="text-xs text-blue-600 font-bold">Проверяем…</p>' : (sendError ? `<p class="text-xs text-red-600 font-bold">${esc(sendError)}</p>` : '');
    const suddenBanner = isSudden
      ? `<div class="p-2.5 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-500 font-bold text-xs">⚡ Внезапная смерть! Раунд ${suddenRound} — играем до первой ошибки!</div>`
      : '';
    const isDanger = localRemaining <= (isSudden ? 2.0 : 5.0);
    const timerPct = Math.max(0, Math.min(100, (localRemaining / timerLimit) * 100));
    const timerLabel = isSudden ? '⚡ 5 с на слово' : '⏱️ 35 с на 10 заданий';
    const timerWidget = `<div class="rounded-2xl p-2.5 bg-slate-50 dark:bg-slate-800 border border-slate-200/60 dark:border-slate-700/60 text-left">
      <div class="flex justify-between items-center text-xs font-black mb-1">
        <span class="text-slate-500 dark:text-slate-400 flex items-center gap-1">${timerLabel}</span>
        <span id="ege-timer-val" class="font-mono text-xs font-black transition-colors ${isDanger ? 'text-red-500 animate-pulse' : 'text-blue-600'}">${localRemaining.toFixed(1)} с</span>
      </div>
      <div class="h-2 w-full rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
        <div id="ege-timer-bar" class="h-full rounded-full transition-all duration-100 ${isDanger ? 'bg-red-500' : 'bg-blue-600'}" style="width:${timerPct}%"></div>
      </div>
    </div>`;
    const progressText = isSudden
      ? `<span>⚡ Доп. раунд ${suddenRound}</span><span>Ты ${own}/${all} · соперник ${Number(room.opponent_answers || 0)}/${all}</span>`
      : `<span>Слово ${Math.min(own + 1, all)} из ${all}</span><span>Ты ${own}/${all} · соперник ${Number(room.opponent_answers || 0)}/${all}</span>`;
    return `<div class="theme-card rounded-3xl p-5 text-center space-y-3.5">
      ${suddenBanner}
      <div class="grid grid-cols-2 gap-2 text-[11px] font-bold"><span class="rounded-xl bg-blue-50 dark:bg-blue-950/30 px-2 py-1.5">Ты: ${ratingText(room.your_rating || myRating)}</span><span class="rounded-xl bg-slate-100 dark:bg-slate-800 px-2 py-1.5">Соперник: ${ratingText(room.rival_rating)}</span></div>
      ${timerWidget}
      <div class="flex justify-between text-xs font-bold">${progressText}</div>
      <div class="h-2 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden"><div class="h-full bg-blue-600 rounded-full" style="width:${Math.min(100, own / all * 100)}%"></div></div>
      ${task}
      ${feedback}
    </div>`;
  }

  function renderFinished() {
    clearPoll();
    clearTimer();
    const result = room.result || 'draw';
    const isSudden = Boolean(room.is_sudden_death || (room.sudden_round && Number(room.sudden_round) > 0));
    const title = result === 'win' ? 'ПОБЕДА' : result === 'loss' ? 'ПОРАЖЕНИЕ' : 'НИЧЬЯ';
    const icon = result === 'win' ? '🏆' : result === 'loss' ? '❌' : '🤝';
    const rival = String(room.host?.tg_id) === String(window.api?.getTelegramUserId?.() || '') ? room.opponent : room.host;
    const change = Number(room.your_rating_change || 0);
    const profile = room.your_rating || myRating;
    myRating = profile;
    const suddenNote = isSudden ? ` (Внезапная смерть: ${room.sudden_round} доп. раунд)` : '';
    const winnerName = room.winner_name || (result === 'win' ? myName() : rival?.name || 'Соперник');
    const winnerLine = result === 'draw'
      ? `Ничья${suddenNote}`
      : `Победитель: ${esc(winnerName)}${suddenNote}`;
    return `<div class="theme-card rounded-3xl p-5 text-center space-y-4"><div class="text-5xl">${icon}</div><h3 class="font-black text-xl">${title}</h3><div class="text-sm font-bold">${winnerLine}</div><div class="font-black text-lg">${esc(myName())} ${Number(room.your_score || 0)} : ${Number(room.opponent_score || 0)} ${esc(rival?.name || 'Соперник')}</div><div class="grid grid-cols-2 gap-2 text-xs"><div class="rounded-2xl bg-slate-50 dark:bg-slate-800 p-3"><b>Вы</b><br>✅ ${Number(room.your_score || 0)}<br>❌ ${Number(room.your_errors || 0)} ошибок</div><div class="rounded-2xl bg-slate-50 dark:bg-slate-800 p-3"><b>${esc(rival?.name || 'Соперник')}</b><br>✅ ${Number(room.opponent_score || 0)}<br>❌ ${Number(room.opponent_errors || 0)} ошибок</div></div><img src="${esc(rankImage(profile))}" class="w-28 h-28 object-contain mx-auto"><div class="font-black text-blue-600">${ratingText(profile)}</div><div class="text-sm font-black ${change > 0 ? 'text-emerald-600' : change < 0 ? 'text-red-500' : 'text-slate-400'}">${change > 0 ? '+' : ''}${change} MMR</div><button onclick="window.EGE.rematchDuel()" class="w-full py-3 rounded-2xl bg-blue-600 text-white font-bold">Реванш</button><button onclick="window.EGE.leaveDuel()" class="w-full py-2 text-xs text-slate-500 font-bold">Вернуться в лобби</button></div>`;
  }

  function renderDuelTab() {
    if (!room) { clearTimer(); return renderLobby(); }
    if (room.status === 'waiting') {
      clearTimer();
      const oppName = esc(room.opponent?.name || room.opponent_name || 'соперника');
      const waitingText = room.matchmaking_search
        ? `Сообщение отправлено игрокам рейтинга${room.matchmaking_recipient_count ? ` (${Number(room.matchmaking_recipient_count)})` : ''}. Как только кто-нибудь примет дуэль, игра начнётся.`
        : 'Приглашение отправлено. Если соперник не отвечает, вы можете отменить вызов и вернуться в лобби.';
      return `<div class="theme-card rounded-3xl p-6 text-center space-y-4">
        <div class="text-4xl">⏳</div>
        <h3 class="font-black text-lg">Ждём ${oppName}…</h3>
        <p class="text-xs text-slate-500">${waitingText}</p>
        <button onclick="window.EGE.cancelDuel()" class="w-full py-3 rounded-2xl bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200 font-bold text-xs transition-colors flex items-center justify-center gap-1.5">
          <span>❌ Отменить вызов</span>
        </button>
      </div>`;
    }
    if (room.status === 'finished') return renderFinished();
    return renderBattle();
  }

  function renderArenaHome() { return renderDuelTab(); }
  function redraw() { const root = document.getElementById('ege-subtab-container') || document.getElementById('pane-ege'); if (root) root.innerHTML = renderDuelTab(); }

  async function refresh() {
    if (!room || sending) return;
    const generation = refreshGeneration;
    try {
      const updated = await window.api.getGameRoom(room.room_id);
      if (!sending && generation === refreshGeneration) {
        if (!updated || updated.status === 'canceled' || updated.status === 'rejected') {
          clearPoll(); clearTimer(); room = null; initLobby(); return;
        }
        room = updated;
        if (room.status === 'finished') clearPoll();
        redraw();
      }
    } catch (_) {}
  }

  function startPoll() { clearPoll(); poll = setInterval(() => refresh().catch(() => {}), 3000); }

  async function invite(id, name) {
    if (Number(id) === Number(window.api?.getTelegramUserId?.())) return;
    clearLeaderboardPoll();
    room = await window.api.inviteGame(id, myName(), type, 'white', name);
    sendError = ''; startPoll(); redraw();
  }

  async function findDuel() {
    if (sending) return;
    clearLeaderboardPoll();
    sending = true; sendError = ''; redraw();
    try {
      room = await window.api.findEgeDuel(type);
      sendError = '';
      startPoll();
    } catch (error) {
      room = null;
      sendError = error?.message || 'Не удалось начать поиск дуэли.';
    } finally { sending = false; redraw(); }
  }

  async function answer(answerValue) {
    if (sending || !room || !room.question) return;
    sending = true; sendError = ''; refreshGeneration += 1; redraw();
    try {
      room = await window.api.sendGameMove(room.room_id, { answer: answerValue });
      if (room.status === 'finished') clearPoll(); else startPoll();
    } catch (error) {
      sendError = error?.message || 'Не удалось отправить ответ.';
    } finally { sending = false; redraw(); }
  }

  function checkVocabulary() { answer(document.getElementById('ege-duel-vocab-input')?.value || ''); }

  async function open(roomId, gameType) {
    type = gameType || 'ege_stress_duel';
    clearLeaderboardPoll();
    room = await window.api.joinGameRoom(roomId, myName());
    sendError = ''; startPoll();
    if (window.switchTab) window.switchTab('ege');
    if (window.EGE_CORE?.setSubTab && window.currentUser?.has_full_access) window.EGE_CORE.setSubTab('duel');
    redraw();
  }

  async function initLobby() {
    try {
      const [people, profile, top] = await Promise.all([window.api.getEgePlayers(), window.api.getEgeRating(), window.api.getEgeLeaderboard()]);
      classmates = people || [];
      myRating = profile || myRating;
      leaderboard = top?.players || [];
    } catch (_) { classmates = []; }
    startLeaderboardPoll();
    redraw();
  }

  async function rematch() {
    room = await window.api.rematchGame(room.room_id);
    sending = false; sendError = ''; startPoll(); redraw();
  }

  async function editNickname() {
    const value = window.prompt('Новый игровой ник (2–24 символа):', window.currentUser?.ege_nickname || '');
    if (!value) return;
    try {
      const profile = await window.api.setEgeNickname(value);
      myRating = profile;
      if (window.currentUser) window.currentUser.ege_nickname = profile.nickname;
      await initLobby();
    } catch (e) { window.alert(e?.message || 'Не удалось изменить ник'); }
  }

  async function cancelInvite() {
    const currentRoomId = room?.room_id;
    leave();
    if (currentRoomId) {
      try { await window.api.cancelGame(currentRoomId); } catch (_) {}
    }
  }

  function leave() { clearPoll(); clearLeaderboardPoll(); clearTimer(); room = null; initLobby(); }
  function cleanup() { clearPoll(); clearLeaderboardPoll(); clearTimer(); sending = false; }

  window.EGE_DUEL = {
    renderDuelTab, renderArenaHome, initLobby, cleanup,
    findDuel,
    duelType: value => { type = value; redraw(); }, invite, inviteDuel: invite,
    answer, duelAnswer: answer, duelCheck: checkVocabulary, open,
    rematch, rematchDuel: rematch, editArenaNickname: editNickname,
    leaveDuel: leave, cancelDuel: cancelInvite, cancelInvite,
    duelTimeout: () => answer('__timeout__'),
  };
  window.EGE = Object.assign(window.EGE || {}, window.EGE_DUEL);
})();
