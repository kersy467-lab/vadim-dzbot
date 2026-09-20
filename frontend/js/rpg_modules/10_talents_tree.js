// ============================================================
// 10_talents_tree.js — Интерактивное Визуальное Древо Талантов (Skill Tree)
// 3 ветки (ATK, TANK, UTIL) × 5 тиров с SVG связями и плашкой прокачки
// ============================================================

window._selectedTalentId = window._selectedTalentId || null;
window._talentTreeFilter = window._talentTreeFilter || "all";

const TREE_BRANCH_THEMES = {
  atk: {
    label: "🗡️ Атака",
    colX: 45,
    activeStroke: "#ef4444",
    glowColor: "rgba(239, 68, 68, 0.6)",
    nodeBought: "bg-red-950 border-red-500 shadow-red-500/50 shadow-md",
    nodeAvail: "bg-slate-900 border-red-500/80 shadow-red-500/30 animate-pulse",
    textColor: "text-red-400"
  },
  tank: {
    label: "🛡️ Выживание",
    colX: 135,
    activeStroke: "#3b82f6",
    glowColor: "rgba(59, 130, 246, 0.6)",
    nodeBought: "bg-blue-950 border-blue-500 shadow-blue-500/50 shadow-md",
    nodeAvail: "bg-slate-900 border-blue-500/80 shadow-blue-500/30 animate-pulse",
    textColor: "text-blue-400"
  },
  util: {
    label: "✨ Утилита",
    colX: 225,
    activeStroke: "#a855f7",
    glowColor: "rgba(168, 85, 247, 0.6)",
    nodeBought: "bg-purple-950 border-purple-500 shadow-purple-500/50 shadow-md",
    nodeAvail: "bg-slate-900 border-purple-500/80 shadow-purple-500/30 animate-pulse",
    textColor: "text-purple-400"
  },
  flask: {
    label: "🧪 Фляга",
    colX: 315,
    activeStroke: "#10b981",
    glowColor: "rgba(16, 185, 129, 0.6)",
    nodeBought: "bg-emerald-950 border-emerald-500 shadow-emerald-500/50 shadow-md",
    nodeAvail: "bg-slate-900 border-emerald-500/80 shadow-emerald-500/30 animate-pulse",
    textColor: "text-emerald-400"
  }
};

const TIER_Y = {
  1: 385,
  2: 305,
  3: 225,
  4: 145,
  5: 60
};

const ROOT_POS = { x: 180, y: 465 };

function renderVisualTalentTree(p, treeData) {
  if (!treeData) {
    return `
      <div class="text-center text-slate-500 text-sm py-12 bg-slate-900/60 rounded-3xl border border-slate-800">
        <div class="text-3xl mb-2 animate-bounce">🌳</div>
        Связывание с астральным древом...
        <br><button onclick="loadTalentTreeUI()" class="mt-4 px-4 py-2 bg-gradient-to-r from-amber-500 to-yellow-500 rounded-xl text-slate-950 font-black text-xs shadow-lg shadow-amber-500/20 active:scale-95">Загрузить Древо</button>
      </div>`;
  }

  const branches = treeData.branches || {};
  const charLvl = p.level || 1;
  const effectiveProgress = charLvl;
  const talentPts = (treeData && treeData.talent_points !== undefined) ? treeData.talent_points : (p.talent_points || 0);
  const filter = window._talentTreeFilter;

  // Flatten nodes for fast lookup
  const nodeMap = {};
  for (const bKey in branches) {
    for (const n of branches[bKey]) {
      nodeMap[n.id] = { ...n, branchKey: bKey };
    }
  }

  // Selected Node (default to first available or first tier if none chosen)
  let selectedNode = nodeMap[window._selectedTalentId];
  if (!selectedNode) {
    const allNodes = Object.values(nodeMap);
    selectedNode = allNodes.find(n => n.can_buy && !n.is_bought) || allNodes.find(n => n.is_bought) || allNodes[0];
  }

  let html = `
    <div class="relative bg-slate-950/90 rounded-3xl border border-slate-800/80 shadow-2xl overflow-hidden p-3 select-none">
      <!-- Background Constellation Ambient Glow -->
      <div class="absolute inset-0 pointer-events-none bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-900/20 via-slate-950/40 to-slate-950/90"></div>

      <!-- Tree Header / Filter Tabs -->
      <div class="relative z-10 flex items-center justify-between gap-1 mb-2 pb-2 border-b border-slate-800/60">
        <div class="flex items-center gap-1 overflow-x-auto no-scrollbar py-0.5">
          <button onclick="setTalentTreeFilterUI('all')" class="px-2 py-1 rounded-xl text-[10px] font-black transition-all ${filter === 'all' ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20' : 'bg-slate-900 text-slate-400 border border-slate-800'}">🌲 Все</button>
          <button onclick="setTalentTreeFilterUI('atk')" class="px-2 py-1 rounded-xl text-[10px] font-black transition-all ${filter === 'atk' ? 'bg-red-600 text-white shadow-md shadow-red-600/30' : 'bg-slate-900 text-red-300 border border-slate-800'}">🗡️ Атака</button>
          <button onclick="setTalentTreeFilterUI('tank')" class="px-2 py-1 rounded-xl text-[10px] font-black transition-all ${filter === 'tank' ? 'bg-blue-600 text-white shadow-md shadow-blue-600/30' : 'bg-slate-900 text-blue-300 border border-slate-800'}">🛡️ Выжив.</button>
          <button onclick="setTalentTreeFilterUI('util')" class="px-2 py-1 rounded-xl text-[10px] font-black transition-all ${filter === 'util' ? 'bg-purple-600 text-white shadow-md shadow-purple-600/30' : 'bg-slate-900 text-purple-300 border border-slate-800'}">✨ Утил.</button>
          <button onclick="setTalentTreeFilterUI('flask')" class="px-2 py-1 rounded-xl text-[10px] font-black transition-all ${filter === 'flask' ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/30' : 'bg-slate-900 text-emerald-300 border border-slate-800'}">🧪 Фляга</button>
        </div>
        <div class="text-[10.5px] font-bold text-amber-400 shrink-0">
          ⭐ <span class="text-white">${talentPts}</span> очк.
        </div>
      </div>

      <!-- Main Visual Tree Canvas (360x510 SVG + Positioned HTML Nodes) -->
      <div class="relative w-full max-w-[360px] mx-auto h-[510px]">
        <!-- SVG Connecting Energy Branches -->
        <svg class="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 360 510">`;

  // Draw root lines to T1
  const bKeys = ["atk", "tank", "util", "flask"];
  for (const bKey of bKeys) {
    if (filter !== "all" && filter !== bKey) continue;
    const theme = TREE_BRANCH_THEMES[bKey];
    const t1Node = (branches[bKey] || []).find(n => n.tier === 1);
    const isT1Bought = t1Node && t1Node.is_bought;
    const isT1Avail = t1Node && !t1Node.is_bought && effectiveProgress >= (t1Node.unlock_level != null ? t1Node.unlock_level : 1);

    const strokeColor = isT1Bought ? theme.activeStroke : (isT1Avail ? "#eab308" : "#334155");
    const strokeW = isT1Bought ? 3.5 : (isT1Avail ? 2.5 : 1.5);
    const dash = isT1Bought ? "" : "stroke-dasharray='4,4'";
    const opacity = isT1Bought ? 0.95 : (isT1Avail ? 0.75 : 0.35);

    html += `<line x1="${ROOT_POS.x}" y1="${ROOT_POS.y}" x2="${theme.colX}" y2="${TIER_Y[1]}" stroke="${strokeColor}" stroke-width="${strokeW}" ${dash} opacity="${opacity}" stroke-linecap="round" />`;

    // Draw lines between tiers (T1->T2, T2->T3, T3->T4, T4->T5)
    for (let t = 1; t <= 4; t++) {
      const parentNode = (branches[bKey] || []).find(n => n.tier === t);
      const childNode = (branches[bKey] || []).find(n => n.tier === t + 1);
      const isParentBought = parentNode && parentNode.is_bought;
      const isChildBought = childNode && childNode.is_bought;
      const isChildAvail = childNode && !childNode.is_bought && isParentBought && effectiveProgress >= (childNode.unlock_level != null ? childNode.unlock_level : childNode.tier * 5);

      let lineCol = "#334155";
      let lw = 1.5;
      let lDash = "stroke-dasharray='4,4'";
      let lOp = 0.35;

      if (isChildBought) {
        lineCol = theme.activeStroke;
        lw = 3.5;
        lDash = "";
        lOp = 0.95;
      } else if (isParentBought || isChildAvail) {
        lineCol = theme.activeStroke;
        lw = 2.5;
        lDash = "stroke-dasharray='6,3'";
        lOp = 0.75;
      }

      html += `<line x1="${theme.colX}" y1="${TIER_Y[t]}" x2="${theme.colX}" y2="${TIER_Y[t + 1]}" stroke="${lineCol}" stroke-width="${lw}" ${lDash} opacity="${lOp}" stroke-linecap="round" />`;
    }
  }

  html += `</svg>`;

  // 1. HERO CORE ROOT NODE at bottom
  html += `
    <div style="left: ${ROOT_POS.x - 26}px; top: ${ROOT_POS.y - 26}px;" class="absolute w-[52px] h-[52px] rounded-full bg-gradient-to-tr from-amber-600 via-yellow-500 to-amber-300 border-2 border-yellow-200 shadow-xl shadow-amber-500/40 flex flex-col items-center justify-center text-slate-950 font-black z-10 animate-pulse cursor-pointer">
      <span class="text-base leading-none">👑</span>
      <span class="text-[9px] font-black leading-none mt-0.5">Ур.${charLvl}</span>
    </div>`;

  // 2. TALENT NODES
  for (const bKey of bKeys) {
    if (filter !== "all" && filter !== bKey) continue;
    const theme = TREE_BRANCH_THEMES[bKey];
    const nodes = branches[bKey] || [];

    for (const node of nodes) {
      const isSelected = selectedNode && selectedNode.id === node.id;
      const isPerk = node.desc && node.desc.includes("[ПЕРК]");
      const y = TIER_Y[node.tier] || 250;
      const x = theme.colX;
      const size = isPerk ? 54 : 46;
      const halfSize = size / 2;

      let borderStyle = "";
      let bgStyle = "";
      let badgeHtml = "";

      const isNodeLvlMet = effectiveProgress >= (node.unlock_level != null ? node.unlock_level : (node.tier === 1 ? 1 : node.tier * 5));
      const nodeReq = node.req ? nodeMap[node.req] : null;
      const isNodeReqMet = !node.req || (nodeReq && nodeReq.is_bought);
      const isNodeAvail = !node.is_bought && isNodeLvlMet && isNodeReqMet;

      if (node.is_bought) {
        bgStyle = isPerk ? "bg-gradient-to-br from-emerald-950 to-slate-900 border-emerald-400 shadow-lg shadow-emerald-500/30" : "bg-emerald-950/90 border-emerald-500 shadow-md shadow-emerald-500/20";
        borderStyle = "border-2";
        badgeHtml = `<span class="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-emerald-500 text-slate-950 flex items-center justify-center text-[9px] font-black shadow">✓</span>`;
      } else if (isNodeAvail) {
        bgStyle = isPerk ? "bg-gradient-to-br from-amber-950 via-slate-900 to-amber-900 border-amber-400 shadow-xl shadow-amber-500/40 animate-pulse" : `${theme.nodeAvail} border-2`;
        borderStyle = isPerk ? "border-2" : "border-2";
        badgeHtml = `<span class="absolute -top-1 -right-1 px-1 py-0.2 rounded-full bg-amber-500 text-slate-950 text-[8px] font-black shadow">${node.cost || 1}⭐</span>`;
      } else {
        bgStyle = "bg-slate-900/70 border-slate-800 text-slate-600 opacity-60";
        borderStyle = "border";
        badgeHtml = `<span class="absolute -top-1 -right-1 text-[10px]">🔒</span>`;
      }

      if (isSelected) {
        bgStyle += " ring-2 ring-white ring-offset-2 ring-offset-slate-950 scale-110 z-20";
      }

      html += `
        <div style="left: ${x - halfSize}px; top: ${y - halfSize}px; width: ${size}px; height: ${size}px;"
             onclick="selectTalentNodeUI('${node.id}')"
             class="absolute rounded-2xl ${borderStyle} ${bgStyle} flex flex-col items-center justify-center cursor-pointer transition-all active:scale-95 group z-10">
          ${badgeHtml}
          <span class="${isPerk ? 'text-2xl' : 'text-xl'} leading-none filter drop-shadow">${node.icon}</span>
          <span class="text-[8px] font-black ${node.is_bought ? 'text-emerald-300' : (isNodeAvail ? 'text-amber-300' : 'text-slate-500')} leading-none mt-1">Т${node.tier}</span>
        </div>`;
    }
  }

  html += `</div>`; // End Canvas

  // 3. SELECTED TALENT INTERACTIVE DETAILS CARD (BOTTOM SHEET)
  if (selectedNode) {
    const isPerk = selectedNode.desc && selectedNode.desc.includes("[ПЕРК]");
    const theme = TREE_BRANCH_THEMES[selectedNode.branchKey] || TREE_BRANCH_THEMES.atk;
    const unlockLvl = selectedNode.unlock_level != null ? selectedNode.unlock_level : (selectedNode.tier === 1 ? 1 : selectedNode.tier * 5);
    const isLvlMet = effectiveProgress >= unlockLvl;
    const reqNode = selectedNode.req ? nodeMap[selectedNode.req] : null;
    const isReqMet = !selectedNode.req || (reqNode && reqNode.is_bought);
    const cost = selectedNode.cost || 1;
    const hasEnoughPts = talentPts >= cost;

    let buyBtnHtml = "";
    if (selectedNode.is_bought) {
      buyBtnHtml = `<div class="px-4 py-2.5 rounded-xl bg-emerald-900/60 border border-emerald-500/40 text-emerald-300 text-xs font-black flex items-center justify-center gap-1.5 shadow-sm">✓ ТАЛАНТ УЖЕ ИЗУЧЕН</div>`;
    } else if (!isLvlMet) {
      buyBtnHtml = `<div class="px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-500 text-xs font-bold flex items-center justify-center gap-1">🔒 Требуется ${unlockLvl} уровень (у вас: ${charLvl})</div>`;
    } else if (!isReqMet) {
      buyBtnHtml = `<div class="px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 text-xs font-bold flex items-center justify-center gap-1">⛓️ Сначала изучите предыдущий талант ветки (${reqNode ? reqNode.name : 'Т' + (selectedNode.tier - 1)})</div>`;
    } else if (!hasEnoughPts) {
      buyBtnHtml = `<div class="px-4 py-2.5 rounded-xl bg-amber-950/40 border border-amber-500/30 text-amber-400 text-xs font-bold flex items-center justify-center gap-1">⭐ Не хватает очков талантов (нужно: ${cost}, у вас: ${talentPts})</div>`;
    } else {
      buyBtnHtml = `
        <button onclick="buyTalentNodeUI('${selectedNode.id}')" class="w-full py-3 rounded-2xl bg-gradient-to-r from-amber-500 via-yellow-400 to-amber-500 active:scale-95 text-slate-950 font-black text-xs shadow-lg shadow-amber-500/30 flex items-center justify-center gap-2">
          <span>⚡ ИЗУЧИТЬ ТАЛАНТ</span>
          <span class="px-2 py-0.5 rounded bg-black/20 text-slate-950 text-[11px] font-extrabold">${cost} ⭐</span>
        </button>`;
    }

    html += `
      <div class="relative z-10 mt-3 p-4 rounded-2xl bg-slate-900/90 border-2 ${isPerk ? 'border-amber-400/80 shadow-amber-500/20 shadow-xl' : 'border-slate-700/80 shadow-lg'} animate-scale-up">
        <div class="flex items-start justify-between gap-2 mb-2">
          <div class="flex items-center gap-3">
            <div class="w-12 h-12 rounded-2xl ${selectedNode.is_bought ? 'bg-emerald-950 border-emerald-500' : 'bg-slate-950 border-slate-700'} border flex items-center justify-center text-3xl shrink-0 shadow-inner">
              ${selectedNode.icon}
            </div>
            <div>
              <div class="flex items-center gap-1.5 flex-wrap">
                <h4 class="font-black text-sm text-white">${selectedNode.name}</h4>
                <span class="text-[9px] font-black px-1.5 py-0.5 rounded ${theme.textColor} bg-slate-950 border border-slate-800">Т${selectedNode.tier}</span>
                ${isPerk ? '<span class="text-[8.5px] font-black px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/60 animate-pulse">✨ ПЕРК</span>' : ''}
              </div>
              <div class="text-[10px] text-slate-400 mt-0.5 font-medium">${theme.label} • Доступно с ${unlockLvl} ур. / этажа</div>
            </div>
          </div>
        </div>
        <p class="text-xs text-slate-200 bg-slate-950/60 p-2.5 rounded-xl border border-slate-800/80 mb-3 leading-relaxed">
          ${selectedNode.desc}
        </p>
        ${buyBtnHtml}
      </div>`;
  }

  html += `</div>`; // End container
  return html;
}

window.selectTalentNodeUI = function(nodeId) {
  window._selectedTalentId = nodeId;
  if (window.triggerHaptic) triggerHaptic("light");
  renderRoot();
};

window.setTalentTreeFilterUI = function(filter) {
  window._talentTreeFilter = filter;
  if (window.triggerHaptic) triggerHaptic("light");
  renderRoot();
};
