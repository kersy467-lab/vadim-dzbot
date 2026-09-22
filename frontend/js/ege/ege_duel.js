(function () {
  'use strict';
  let room = null, type = 'ege_stress_duel', classmates = [], poll = null;
  let sending = false, refreshGeneration = 0, sendError = '';
  const vowels = 'аеёиоуыэюя';
  const esc = value => String(value || '').replace(/[&<>\"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[char]));
  const myName = () => window.currentUser?.full_name || window.currentUser?.display_name || 'Одноклассник';

  function renderDuelTab() {
    if (!room) return renderLobby();
    if (room.status === 'waiting') return `<div class="theme-card rounded-3xl p-6 text-center space-y-3"><div class="text-4xl">⏳</div><h3 class="font-black">Ждём соперника</h3><p class="text-xs text-slate-500">Приглашение уже отправлено. Экран обновится, когда одноклассник подключится.</p></div>`;
    if (room.status === 'finished') return renderFinished();
    return renderBattle();
  }

  function renderLobby() {
    const names = classmates.map(c => `<button onclick="window.EGE.inviteDuel(${Number(c.tg_id)}, '${esc(c.name).replace(/'/g, '')}')" class="w-full flex justify-between items-center p-3 rounded-2xl bg-slate-50 dark:bg-slate-800 text-left"><span class="font-bold text-sm">${esc(c.name || 'Одноклассник')}</span><span class="text-xs text-blue-600">Вызвать ⚔️</span></button>`).join('') || '<p class="text-xs text-slate-400 text-center py-3">Загружаем одноклассников…</p>';
    return `<div class="space-y-3"><div class="theme-card rounded-3xl p-5 text-center space-y-2"><div class="text-3xl">⚔️</div><h3 class="font-black">ЕГЭ-дуэль</h3><p class="text-xs text-slate-500">10 слов каждому. При 10/10 у обоих — внезапная смерть.</p><div class="grid grid-cols-2 gap-2 pt-2"><button onclick="window.EGE.duelType('ege_stress_duel')" class="p-3 rounded-2xl font-bold text-xs ${type === 'ege_stress_duel' ? 'bg-blue-600 text-white' : 'bg-slate-100 dark:bg-slate-700'}">Ударения</button><button onclick="window.EGE.duelType('ege_vocabulary_duel')" class="p-3 rounded-2xl font-bold text-xs ${type === 'ege_vocabulary_duel' ? 'bg-blue-600 text-white' : 'bg-slate-100 dark:bg-slate-700'}">Словарные слова</button></div></div><div class="theme-card rounded-2xl p-3 space-y-2"><p class="text-xs font-bold text-slate-500">Вызвать одноклассника</p>${names}</div></div>`;
  }

  function renderBattle() {
    const own = room.your_answers || 0, all = room.round_size || 10;
    if (own >= all) return `<div class="theme-card rounded-3xl p-6 text-center space-y-3"><div class="text-4xl">⏳</div><h3 class="font-black">Раунд пройден</h3><p class="text-xs text-slate-500">Ты ответил на все ${all} слов. Соперник отвечает в своём темпе; когда он закончит, появится результат или следующий раунд.</p><div class="text-xs font-bold text-blue-600">Соперник: ${room.opponent_answers || 0}/${all}</div></div>`;
    const question = room.question;
    if (!question) return `<div class="theme-card rounded-3xl p-6 text-center space-y-3"><div class="text-4xl">⏳</div><h3 class="font-black">Получаем следующее слово…</h3><p class="text-xs text-slate-500">Проверь соединение, если экран не обновится.</p></div>`;
    const status = room.sudden_round ? `🔥 Внезапная смерть · раунд ${room.sudden_round}` : `Слово ${Math.min(own + 1, all)} из ${all}`;
    let task = '';
    if (question.mode === 'stress') task = `<p class="text-xs text-slate-500">Нажмите ударную гласную</p><div class="flex flex-wrap justify-center gap-2 py-3">${[...question.word].map((letter, i) => question.vowel_indexes.includes(i) ? `<button ${sending ? 'disabled' : ''} onclick="window.EGE.duelAnswer(${i})" class="w-10 h-12 rounded-2xl bg-slate-100 dark:bg-slate-700 font-black text-xl">${letter}</button>` : `<span class="w-7 h-12 flex items-center justify-center font-black text-xl">${letter}</span>`).join('')}</div>`;
    else task = `<p class="text-xs text-slate-500">Впишите словарное слово полностью</p><div class="text-3xl font-black py-3 tracking-[0.18em]">${esc(question.masked)}</div><input id="ege-duel-vocab-input" ${sending ? 'disabled' : ''} onkeydown="if(event.key==='Enter') window.EGE.duelCheck()" placeholder="Напишите слово" class="w-full px-4 py-3 rounded-2xl border text-center font-bold dark:bg-slate-700"><button ${sending ? 'disabled' : ''} onclick="window.EGE.duelCheck()" class="mt-2 w-full py-3 rounded-2xl bg-blue-600 text-white font-bold">Проверить</button>`;
    const feedback = sending ? '<p class="text-xs text-blue-600 font-bold">Проверяем ответ…</p>' : (sendError ? `<p class="text-xs text-red-600 font-bold">${esc(sendError)}</p>` : '');
    return `<div class="theme-card rounded-3xl p-5 text-center space-y-4"><div class="flex justify-between text-xs font-bold"><span>${status}</span><span>Ты ${own}/${all} · соперник ${room.opponent_answers || 0}/${all}</span></div><div class="h-2 rounded-full bg-slate-100"><div class="h-full bg-blue-600 rounded-full" style="width:${Math.min(100, own / all * 100)}%"></div></div>${task}${feedback}</div>`;
  }

  function renderFinished() {
    const mine = window.api?.getTelegramUserId?.() || null;
    const win = String(room.winner) === String(mine);
    return `<div class="theme-card rounded-3xl p-6 text-center space-y-3"><div class="text-4xl">${win ? '🏆' : '📚'}</div><h3 class="font-black">${win ? 'Ты победил!' : 'Дуэль завершена'}</h3><p class="text-xs text-slate-500">Ошибок: у тебя ${room.your_errors || 0}. ${room.sudden_round ? 'Решила внезапная смерть.' : ''}</p><button onclick="window.EGE.rematchDuel()" class="w-full py-3 rounded-2xl bg-blue-600 text-white font-bold">Реванш</button></div>`;
  }

  function redraw() { const root = document.getElementById('ege-subtab-container'); if (root) root.innerHTML = renderDuelTab(); }
  async function refresh() {
    if (!room || sending) return;
    const generation = refreshGeneration;
    const updated = await window.api.getGameRoom(room.room_id);
    if (!sending && generation === refreshGeneration) { room = updated; redraw(); }
  }
  async function invite(id, name) { room = await window.api.inviteGame(id, myName(), type, 'white', name); sendError = ''; startPoll(); redraw(); }
  async function answer(answer) {
    if (sending || !room || !room.question) return;
    sending = true;
    sendError = '';
    refreshGeneration += 1;
    redraw();
    try {
      room = await window.api.sendGameMove(room.room_id, { answer });
    } catch (error) {
      sendError = error?.message || 'Не удалось отправить ответ. Нажмите ещё раз.';
    } finally {
      sending = false;
      redraw();
    }
  }
  function checkVocabulary() {
    const answer = document.getElementById('ege-duel-vocab-input')?.value || '';
    answerQuestion(answer);
  }
  async function open(roomId, gameType) { type = gameType; room = await window.api.joinGameRoom(roomId, myName()); sendError = ''; startPoll(); if (window.switchTab) window.switchTab('ege'); if (window.EGE_CORE?.selectTask) window.EGE_CORE.selectTask(gameType === 'ege_stress_duel' ? 4 : 9); if (window.EGE_CORE?.setSubTab) window.EGE_CORE.setSubTab('duel'); }
  function startPoll() { clearInterval(poll); poll = setInterval(() => refresh().catch(() => {}), 2500); }
  async function initLobby() { try { classmates = await window.api.getClassmates(); } catch (_) { classmates = []; } redraw(); }
  const answerQuestion = answer;
  window.EGE_DUEL = { renderDuelTab, initLobby, duelType: value => { type = value; redraw(); }, invite, inviteDuel: invite, answer, duelAnswer: answer, duelCheck: checkVocabulary, open, rematch: async () => { room = await window.api.rematchGame(room.room_id); sending = false; sendError = ''; redraw(); }, rematchDuel: async () => { room = await window.api.rematchGame(room.room_id); sending = false; sendError = ''; redraw(); } };
})();
