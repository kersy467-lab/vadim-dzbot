// ============================================================
// 10_talents_ui.js — Дерево Талантов и Алтарь Вознесения natarGRP
// ============================================================

window._cachedTalentTree = window._cachedTalentTree || null;

function renderTalentsTab() {
  const p = RPG_STATE.profile;
  if (!p) return `<div class="p-4 text-center text-white/50">Загрузка...</div>`;

  const currentHero = (p.hero_class || "").toLowerCase();
  if (window._cachedTalentTree && (window._cachedTalentTree.hero_class || "").toLowerCase() !== currentHero) {
    window._cachedTalentTree = null;
    window._selectedTalentId = null;
    if (window._talentsTabAutoLoad) setTimeout(window._talentsTabAutoLoad, 0);
  }

  const rebirths = (p.rebirth_info && p.rebirth_info.rank) || p.rebirths || 0;
  const maxRank = (p.rebirth_info && p.rebirth_info.max_rank) || 40;
  const isMaxRank = rebirths >= maxRank;
  const rebirthMult = (p.rebirth_info && p.rebirth_info.multiplier) || 1.0;
  const essence = (p.rebirth_info && p.rebirth_info.essence) || p.rebirth_essence || 0;
  const charLvl = p.level || 1;
  const talentPts = (window._cachedTalentTree && window._cachedTalentTree.talent_points !== undefined)
    ? window._cachedTalentTree.talent_points
    : (p.talent_points || 0);

  const reqLvl = (p.rebirth_info && p.rebirth_info.next_min_level) || (rebirths === 0 ? 30 : (rebirths === 1 ? 40 : (rebirths === 2 ? 45 : 50)));
  const canAscend = !isMaxRank && charLvl >= reqLvl;

  let html = `<div class="p-3 bg-slate-900 min-h-screen text-slate-200 space-y-4">`;

  // === 1. REBIRTH BANNER (АЛТАРЬ ВОЗНЕСЕНИЯ) ===
  html += `
    <div class="bg-gradient-to-r from-purple-950/90 via-slate-800 to-indigo-950/90 p-4 rounded-3xl border border-purple-500/40 shadow-xl relative overflow-hidden">
      <div class="relative z-10 flex justify-between items-center gap-3">
        <div>
          <div class="flex items-center gap-1.5">
            <h2 class="text-base font-black text-white drop-shadow-md">🌟 Алтарь Вознесения</h2>
            <span class="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/30 text-purple-300 font-extrabold border border-purple-400/30">Ранг ${rebirths}</span>
          </div>
          <div class="text-xs text-amber-300 mt-1 font-bold">
            Множитель: <span class="text-white">x${rebirthMult.toFixed(2)}</span> | ✨ Эссенция: <span class="text-white">${essence}</span>
          </div>
          <div class="text-[10.5px] text-slate-400 mt-0.5">
            ${isMaxRank
              ? `<span class="text-amber-400 font-extrabold">👑 Достигнут абсолютный предел Вознесения (Ранг ${maxRank})!</span>`
              : `Требуется: <span class="${canAscend ? 'text-emerald-400 font-bold' : 'text-amber-300 font-bold'}">${reqLvl} ур. героя</span> (текущий: ${charLvl})`
            }
          </div>
        </div>
        <div class="shrink-0">
          ${isMaxRank
            ? `<button disabled class="px-3 py-2 bg-slate-800/90 rounded-2xl font-bold text-[10px] text-amber-400 border border-amber-500/40 cursor-not-allowed">МАКС. РАНГ (${maxRank})</button>`
            : (canAscend
                ? `<button onclick="doRebirthUI()" class="px-3.5 py-2.5 bg-gradient-to-r from-purple-500 via-indigo-500 to-purple-600 rounded-2xl font-black text-xs text-white shadow-lg shadow-purple-500/40 active:scale-95 animate-pulse">ВОЗНЕСЕНИЕ 🌟</button>`
                : `<button disabled class="px-3 py-2 bg-slate-800/90 rounded-2xl font-bold text-[10px] text-slate-500 border border-slate-700/80 cursor-not-allowed">С ${reqLvl} ур.</button>`
              )
          }
        </div>
      </div>
    </div>`;

  // === 2. TALENT TREE HEADER ===
  html += `
    <div class="flex items-center justify-between px-1">
      <div>
        <h3 class="text-sm font-black text-amber-400 flex items-center gap-1.5">
          <span>⚔️</span> Древо Навыков (${p.class_name || "Герой"})
        </h3>
        <p class="text-[10.5px] text-slate-400">Интерактивное древо развития — выберите узел для прокачки</p>
      </div>
      <div class="flex items-center gap-1.5">
        <span class="text-xs font-black px-2.5 py-1 rounded-xl bg-slate-800 border border-slate-700 text-amber-300">Ур. ${charLvl}</span>
        <span class="text-xs font-black px-2.5 py-1 rounded-xl ${talentPts > 0 ? 'bg-emerald-900/60 border-emerald-500/50 text-emerald-300 animate-pulse' : 'bg-slate-800 border-slate-700 text-slate-400'} border">⭐ ${talentPts} очк.</span>
      </div>
    </div>`;

  // === 3. VISUAL TALENT TREE GRAPH ===
  html += renderVisualTalentTree(p, window._cachedTalentTree);

  // === 4. PETS SECTION ===
  html += renderPetsSection(p);

  html += `</div>`;
  return html;
}

function renderPetsSection(p) {
  const petDict = {
    "fairy":   { icon: "🧚", name: "Лесная Фея",          desc: "Снимает станы, +35% скорости бега" },
    "wolf":    { icon: "🐺", name: "Призрачный Волк",      desc: "Кровотечение 400 ед./сек" },
    "dragon":  { icon: "🐉", name: "Золотой Дракон",       desc: "Конус огня 1200 урона, +50% золота" },
    "phoenix": { icon: "🦅", name: "Пылающий Феникс",      desc: "Щит неуязвимости при смертельном ударе" },
    "slime":   { icon: "💧", name: "Капельный Слайм",      desc: "Лечит на 10% HP каждые 12с" },
    "donkey":  { icon: "🫏", name: "Ослик-Курьер Доты",    desc: "Носит рюкзак на 6 предметов, +40% к урону группы" },
  };

  let html = `
    <div class="space-y-2 pt-2 pb-20">
      <div class="flex items-center justify-between px-1">
        <div>
          <h3 class="text-sm font-black text-amber-400 flex items-center gap-1.5"><span>🐾</span> Боевые Питомцы</h3>
          <p class="text-[10px] text-slate-400">Летающий спутник атакует врагов и усиливает героя</p>
        </div>
        <button onclick="hatchPetUI()" class="px-3 py-1.5 rounded-xl bg-gradient-to-r from-amber-500 to-yellow-400 active:scale-95 text-slate-950 font-black text-[11px] shadow-sm">🥚 ИНКУБАТОР (50 💎)</button>
      </div>
      <div class="space-y-1.5">`;

  const pets = p.pets || [];
  if (pets.length === 0) {
    html += `<div class="text-center text-slate-500 text-xs py-4 bg-slate-800/40 rounded-2xl border border-slate-800">У вас пока нет питомцев. Откройте яйцо в Инкубаторе!</div>`;
  }

  for (const pet of pets) {
    const pData = petDict[pet.type || pet.pet_id] || { icon: "🐾", name: pet.name || "Питомец", desc: "Боевой спутник" };
    const isSel = pet.is_equipped;
    html += `
      <div class="bg-slate-800/80 rounded-2xl p-3 border ${isSel ? 'border-amber-400 shadow-md shadow-amber-500/10' : 'border-slate-700/80'} flex items-center justify-between gap-3">
        <div class="flex items-center gap-3">
          <div class="w-11 h-11 rounded-xl bg-slate-900 border border-slate-700 flex items-center justify-center text-2xl shadow-inner relative">
            ${pData.icon}
            <div class="absolute -bottom-1 -right-1 bg-amber-500 text-slate-900 text-[9px] font-black px-1 rounded border border-amber-300">${pet.stars || 1}⭐</div>
          </div>
          <div>
            <div class="font-bold text-xs text-white">${pData.name}</div>
            <div class="text-[10px] text-slate-400 mt-0.5 leading-tight">${pData.desc}</div>
            <button onclick="upgradePetUI('${pet.uid}')" class="text-[10px] text-amber-400 underline mt-0.5 block font-semibold">Синтез 3-в-1 (нужно 3 шт, 10 💎)</button>
          </div>
        </div>
        <button onclick="equipPetUI('${pet.uid}')" class="px-3 py-1.5 rounded-xl text-xs font-black transition-all shrink-0 ${isSel ? 'bg-amber-500 text-slate-950 shadow-md' : 'bg-slate-700 hover:bg-slate-600 text-slate-200'}">
          ${isSel ? 'НАДЕТ' : 'ВЗЯТЬ'}
        </button>
      </div>`;
  }

  html += `</div></div>`;
  return html;
}

// === EVENT HANDLERS ===

window.loadTalentTreeUI = async function() {
  try {
    const data = await api.getTalentTree();
    window._cachedTalentTree = data;
    renderRoot();
  } catch (e) {
    alert("Ошибка загрузки дерева талантов: " + (e.message || e));
  }
};

window.buyTalentNodeUI = async function(nodeId) {
  try {
    if (window.triggerHaptic) triggerHaptic("medium");
    const res = await api.buyTalentNode(nodeId);
    if (res && res.profile) {
      RPG_STATE.profile = res.profile;
      if (window.syncArenaPlayerStats) syncArenaPlayerStats();
      window._cachedTalentTree = await api.getTalentTree();
      if (window.triggerHaptic) triggerHaptic("success");
      renderRoot();
    }
  } catch (err) {
    if (window.triggerHaptic) triggerHaptic("error");
    alert(err.message || "Ошибка покупки таланта");
  }
};

window.doRebirthUI = async function() {
  if (!confirm("Совершить Вознесение? Уровень сбросится до 1, но вы сохраните все предметы, заточку, питомцев и получите постоянный множитель статов!")) return;
  try {
    if (window.triggerHaptic) triggerHaptic("heavy");
    const res = await api.doRebirth();
    if (res.profile) {
      RPG_STATE.profile = res.profile;
      if (typeof ARENA !== "undefined") {
        ARENA.waveNumber = 1;
        ARENA.totalCreepsSpawned = 0;
        ARENA.creepsKilledInWave = 0;
        ARENA.creeps = [];
      }
      if (window.syncArenaPlayerStats) syncArenaPlayerStats();
      if (window.triggerHaptic) triggerHaptic("success");
      window._cachedTalentTree = null;
      renderRoot();
    }
  } catch(e) { alert(e.message || "Ошибка перерождения"); }
};

window.hatchPetUI = async function() {
  try {
    if (window.triggerHaptic) triggerHaptic("medium");
    const res = await api.hatchPetCrate();
    if (res.profile) {
      RPG_STATE.profile = res.profile;
      if (window.triggerHaptic) triggerHaptic("success");
      alert("Выпал питомец: " + (res.pet_cfg ? res.pet_cfg.name : "Новый питомец!"));
      renderRoot();
    }
  } catch(e) { alert(e.message || "Ошибка открытия яйца"); }
};

window.equipPetUI = async function(petUid) {
  try {
    if (window.triggerHaptic) triggerHaptic("light");
    const res = await api.equipPet(petUid);
    if (res.profile) {
      RPG_STATE.profile = res.profile;
      if (window.syncArenaPlayerStats) syncArenaPlayerStats();
      const eqPet = (res.profile.pets || []).find(p => p.is_equipped);
      if (eqPet) localStorage.setItem("rpg_active_pet", eqPet.type || eqPet.pet_id);
      else localStorage.removeItem("rpg_active_pet");
      renderRoot();
    }
  } catch(e) { alert(e.message || "Ошибка экипировки"); }
};

window.selectPetUI = window.equipPetUI;

window.upgradePetUI = async function(petUid) {
  try {
    if (window.triggerHaptic) triggerHaptic("medium");
    const res = await api.upgradePet(petUid);
    if (res.profile) {
      RPG_STATE.profile = res.profile;
      if (window.syncArenaPlayerStats) syncArenaPlayerStats();
      if (window.triggerHaptic) triggerHaptic("success");
      alert("Питомец успешно улучшен!");
      renderRoot();
    }
  } catch(e) { alert(e.message || "Ошибка улучшения питомца"); }
};

window.upgradeTalentUI = async function(talentId) {
  try {
    if (window.triggerHaptic) triggerHaptic("light");
    const res = await api.upgradeTalent(talentId);
    if (res.profile) {
      RPG_STATE.profile = res.profile;
      if (window.syncArenaPlayerStats) syncArenaPlayerStats();
      renderRoot();
    }
  } catch(e) { alert(e.message || "Ошибка улучшения таланта"); }
};

// Auto-load talent tree data when tab opens
window._talentsTabAutoLoad = function() {
  const currentHero = (RPG_STATE.profile?.hero_class || "").toLowerCase();
  if ((!window._cachedTalentTree || (window._cachedTalentTree.hero_class || "").toLowerCase() !== currentHero) && RPG_STATE.profile) {
    api.getTalentTree().then(data => {
      window._cachedTalentTree = data;
      renderRoot();
    }).catch(() => {});
  }
};
