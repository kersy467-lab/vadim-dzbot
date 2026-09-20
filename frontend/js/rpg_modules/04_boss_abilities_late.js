// ============================================================================
// 04_boss_abilities_late.js — Signature Attacks & Ultimates for Bosses 11–20
// (Terrorblade, Invoker, CK, Dark Tormentor, Storm, Doom, Primal Beast, Phantom Roshan, Tinker, Enigma)
// ============================================================================

function executeBossAbilityLate(boss, p, bId, abilityType, ARENA) {
  const pAng = Math.atan2(p.y - boss.y, p.x - boss.x);

  // 11. TERRORBLADE: Conjure Image or Sunder (Разрыв Души)
  if (bId.includes("terrorblade") || bId.includes("демон бездны")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "😈 РАЗРЫВ ДУШИ (SUNDER)!", "#a855f7");
      triggerHaptic("heavy");
      const curHp = (p && typeof p.currentHp === "number" && !isNaN(p.currentHp) && p.currentHp > 0) ? p.currentHp : 0;
      const siphonDmg = Math.max(0, Math.floor(curHp * 0.25));
      if (siphonDmg > 0) {
        applyDamageToPlayer(siphonDmg, "sunder");
        const curBossHp = (typeof boss.hp === "number" && !isNaN(boss.hp) && boss.hp > 0) ? boss.hp : boss.maxHp;
        const healAmt = Math.min(boss.maxHp * 0.08, siphonDmg * 10);
        boss.hp = Math.min(boss.maxHp, curBossHp + healAmt);
        spawnFloatingText(p.x, p.y - 25, `🩸 SUNDER -${siphonDmg}`, "#a855f7");
      }
      if (typeof applyStatusEffectToPlayer === "function") {
        applyStatusEffectToPlayer({ slow: true, slowDuration: 90, slowRatio: 0.4 });
      }
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "👥 ИЛЛЮЗИЯ ТЬМЫ!", "#7c3aed");
      for (let im = 0; im < 2; im++) {
        const iAng = pAng + (im === 0 ? -0.4 : 0.4);
        ARENA.bossProjectiles.push({
          x: boss.x, y: boss.y,
          vx: Math.cos(iAng) * 3.8, vy: Math.sin(iAng) * 3.8,
          radius: 9, color: "#8b5cf6", timer: 150,
          dmg: calculateBossAttackDamage(boss, 0.7),
          slow: true, slowDuration: 60, slowRatio: 0.5,
          label: "👥 ТЕНЕВОЙ БОЛТ"
        });
      }
    }
    return true;
  }

  // 12. INVOKER: Chaos Meteor or Sun Strike (Солнечный Удар)
  if (bId.includes("invoker_boss") || bId.includes("инвокер")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "☀️ СОЛНЕЧНЫЙ УДАР (SUN STRIKE)!", "#facc15");
      triggerHaptic("heavy");
      ARENA.dangerZones.push({
        type: "circle", cx: p.x, cy: p.y, r: 55,
        timer: 48, phase: "telegraph", activeFrames: 14,
        damage: calculateBossAttackDamage(boss, 2.0),
        burn: true, burnDuration: 120, burnDmg: Math.floor(boss.atk * 0.28),
        color: "#facc15", label: "☀️ SUN STRIKE (ОЖОГ)"
      });
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "☄️ МЕТЕОР ХАОСА!", "#f97316");
      const mx = boss.x + Math.cos(pAng) * 220;
      const my = boss.y + Math.sin(pAng) * 220;
      ARENA.dangerZones.push({
        type: "line", x1: boss.x, y1: boss.y, x2: mx, y2: my, width: 48,
        timer: 36, phase: "telegraph", activeFrames: 24,
        damage: calculateBossAttackDamage(boss, 1.25),
        burn: true, burnDuration: 150, burnDmg: Math.floor(boss.atk * 0.22),
        slow: true, slowDuration: 90, slowRatio: 0.4,
        color: "#ea580c", label: "☄️ МЕТЕОР (ОЖОГ & ЗАМЕДЛЕНИЕ)"
      });
    }
    return true;
  }

  // 13. CHAOS KNIGHT: Chaos Bolt or Phantasm (Фантазм)
  if (bId.includes("chaos_knight") || bId.includes("всадник хаоса")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "🐎 ФАНТАЗМ ХАОСА (PHANTASM)!", "#f59e0b");
      triggerHaptic("heavy");
      for (let c = -1; c <= 1; c++) {
        const cAng = pAng + c * 0.35;
        ARENA.bossProjectiles.push({
          x: boss.x, y: boss.y,
          vx: Math.cos(cAng) * 4.4, vy: Math.sin(cAng) * 4.4,
          radius: 14, color: "#f59e0b", timer: 140,
          dmg: calculateBossAttackDamage(boss, 1.15),
          slow: true, slowDuration: 75, slowRatio: 0.45,
          label: "🐎 ФАНТАЗМ"
        });
      }
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "⚡ CHAOS BOLT!", "#ef4444");
      const randDmgMult = 0.6 + Math.random() * 0.8;
      const randStun = Math.floor(45 + Math.random() * 55);
      ARENA.bossProjectiles.push({
        x: boss.x, y: boss.y,
        vx: Math.cos(pAng) * 4.8, vy: Math.sin(pAng) * 4.8,
        radius: 11, color: "#ef4444", timer: 140,
        dmg: calculateBossAttackDamage(boss, randDmgMult),
        stun: randStun, label: `⚡ CHAOS BOLT (СТАН ${Math.round(randStun/60*10)/10}с!)`
      });
    }
    return true;
  }

  // 14. DARK TORMENTOR: Void Needles or Singularity Pulse (Пульс Сингулярности)
  if (bId.includes("dark_tormentor") || bId.includes("тёмный терзатель")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "🌌 ПУЛЬС СИНГУЛЯРНОСТИ!", "#c084fc");
      triggerHaptic("heavy");
      ARENA.cameraTrauma = 0.9;
      p.x = p.x * 0.6 + boss.x * 0.4;
      p.y = p.y * 0.6 + boss.y * 0.4;
      ARENA.dangerZones.push({
        type: "circle", cx: boss.x, cy: boss.y, r: 120,
        timer: 36, phase: "telegraph", activeFrames: 18,
        damage: calculateBossAttackDamage(boss, 1.65),
        stun: 75, color: "#9333ea", label: "🌌 СИНГУЛЯРНОСТЬ (СТАН!)"
      });
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "✨ ШТОРМ ИГЛ БЕЗДНЫ!", "#e9d5ff");
      for (let n = 0; n < 12; n++) {
        const nAng = (n * Math.PI * 2) / 12;
        ARENA.bossProjectiles.push({
          x: boss.x, y: boss.y,
          vx: Math.cos(nAng) * 3.6, vy: Math.sin(nAng) * 3.6,
          radius: 8, color: "#c084fc", timer: 160,
          dmg: calculateBossAttackDamage(boss, 0.8),
          silence: 60, label: "✨ ИГЛА (САЙЛЕНС 1с)"
        });
      }
    }
    return true;
  }

  // 15. STORM SPIRIT: Static Remnant or Ball Lightning (Шаровая Молния)
  if (bId.includes("storm_spirit") || bId.includes("громовой")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "⚡ ШАРОВАЯ МОЛНИЯ (BALL LIGHTNING)!", "#38bdf8");
      triggerHaptic("heavy");
      ARENA.cameraTrauma = 0.8;
      const targetX = p.x + Math.cos(pAng) * 80;
      const targetY = p.y + Math.sin(pAng) * 80;
      ARENA.dangerZones.push({
        type: "line", x1: boss.x, y1: boss.y, x2: targetX, y2: targetY, width: 44,
        timer: 20, phase: "telegraph", activeFrames: 10,
        damage: calculateBossAttackDamage(boss, 1.5),
        stun: 60, color: "#38bdf8", label: "⚡ ШАРОВАЯ МОЛНИЯ (СТАН 1с!)"
      });
      boss.x = Math.max(40, Math.min(ARENA.width - 40, targetX));
      boss.y = Math.max(40, Math.min(ARENA.height - 40, targetY));
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "⚡ ЭЛЕКТРО-РЕЗЕРВ (STATIC REMNANT)!", "#facc15");
      ARENA.dangerZones.push({
        type: "circle", cx: boss.x, cy: boss.y, r: 60,
        timer: 15, phase: "telegraph", activeFrames: 120,
        damage: calculateBossAttackDamage(boss, 0.95),
        slow: true, slowDuration: 90, slowRatio: 0.35,
        color: "#facc15", label: "⚡ РЕМНАНТ (ШОК)"
      });
    }
    return true;
  }

  // 16. DOOM: Scorched Earth or DOOM (Печать Рока)
  if (bId.includes("doom") || bId.includes("вестник")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "🔥 ПЕЧАТЬ РОКА (DOOM)!", "#dc2626");
      triggerHaptic("heavy");
      ARENA.cameraTrauma = 1.0;
      p.doomDebuffTimer = 240;
      if (typeof applyStatusEffectToPlayer === "function") {
        applyStatusEffectToPlayer({ silence: 240 });
      }
      ARENA.dangerZones.push({
        type: "circle", cx: p.x, cy: p.y, r: 65,
        timer: 24, phase: "telegraph", activeFrames: 14,
        damage: calculateBossAttackDamage(boss, 1.4),
        silence: 240, color: "#7f1d1d", label: "🔥 DOOM (САЙЛЕНС 4с & УРОН!)"
      });
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "🌋 ВЫЖЖЕННАЯ ЗЕМЛЯ (SCORCHED EARTH)!", "#f97316");
      ARENA.dangerZones.push({
        type: "circle", cx: boss.x, cy: boss.y, r: 95,
        timer: 15, phase: "telegraph", activeFrames: 90, isDot: true,
        damage: calculateBossAttackDamage(boss, 0.4),
        burn: true, burnDuration: 90, burnDmg: Math.floor(boss.atk * 0.18),
        color: "#ea580c", label: "🌋 ПЛАМЯ АДА (ОЖОГ)"
      });
    }
    return true;
  }

  // 17. PRIMAL BEAST: Onslaught Rush or Pulverize (Вбивание в Землю)
  if (bId.includes("primal_beast") || bId.includes("первобытный")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "🦣 ВБИВАНИЕ В ЗЕМЛЮ (PULVERIZE)!", "#b45309");
      triggerHaptic("heavy");
      ARENA.cameraTrauma = 1.0;
      for (let pw = 0; pw < 3; pw++) {
        ARENA.dangerZones.push({
          type: "circle", cx: boss.x, cy: boss.y, r: 70 + pw * 30,
          timer: 18 + pw * 16, phase: "telegraph", activeFrames: 14,
          damage: calculateBossAttackDamage(boss, 1.25),
          stun: 65, color: "#92400e", label: "🦣 ВБИВАНИЕ (СТАН 1с!)"
        });
      }
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "💨 НЕИСТОВЫЙ РАЗБЕГ (ONSLAUGHT)!", "#f59e0b");
      boss.state = "telegraph_charge";
      boss.stateTimer = 45;
      boss.chargeAngle = pAng;
      boss.chargeVx = Math.cos(pAng) * 4.8;
      boss.chargeVy = Math.sin(pAng) * 4.8;
    }
    return true;
  }

  // 18. PHANTOM ROSHAN: Astral Slam or Astral Tear (Астральный Разрыв)
  if (bId.includes("phantom_roshan") || bId.includes("призрачный рошан")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "👻 АСТРАЛЬНЫЙ РАЗРЫВ ХАОСА!", "#34d399");
      triggerHaptic("heavy");
      ARENA.cameraTrauma = 1.0;
      for (let as = 0; as < 8; as++) {
        const asAng = (as * Math.PI * 2) / 8;
        ARENA.bossProjectiles.push({
          x: boss.x, y: boss.y,
          vx: Math.cos(asAng) * 3.8, vy: Math.sin(asAng) * 3.8,
          radius: 12, color: "#10b981", timer: 180,
          dmg: calculateBossAttackDamage(boss, 1.3),
          silence: 90, slow: true, slowDuration: 90, slowRatio: 0.4,
          label: "👻 АСТРАЛ (САЙЛЕНС 1.5с)"
        });
      }
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "💥 АСТРАЛЬНЫЙ SLAM!", "#6ee7b7");
      ARENA.dangerZones.push({
        type: "circle", cx: boss.x, cy: boss.y, r: 85,
        timer: 28, phase: "telegraph", activeFrames: 16,
        damage: calculateBossAttackDamage(boss, 1.1),
        slow: true, slowDuration: 120, slowRatio: 0.3,
        color: "#059669", label: "👻 АСТРАЛЬНЫЙ СЛЭМ"
      });
    }
    return true;
  }

  // 19. TINKER: Laser Beam or March of the Machines (Марш Роботов)
  if (bId.includes("tinker_boss") || bId.includes("архиинженер")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "🤖 МАРШ РОБОТОВ (MARCH OF MACHINES)!", "#facc15");
      triggerHaptic("heavy");
      for (let bot = 0; bot < 12; bot++) {
        const bx = 40 + (bot * (ARENA.width - 80)) / 11;
        ARENA.bossProjectiles.push({
          x: bx, y: 15,
          vx: (Math.random() - 0.5) * 1.2, vy: 2.2 + Math.random() * 0.8,
          radius: 7, color: "#eab308", timer: 240, isSpiderBot: true,
          dmg: calculateBossAttackDamage(boss, 0.45),
          slow: true, slowDuration: 45, slowRatio: 0.5,
          label: "🤖 РОБОТ-ПАУК"
        });
      }
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "🔴 ОСЛЕПЛЯЮЩИЙ ЛАЗЕР!", "#ef4444");
      ARENA.dangerZones.push({
        type: "line", x1: boss.x, y1: boss.y,
        x2: boss.x + Math.cos(pAng) * 260, y2: boss.y + Math.sin(pAng) * 260,
        width: 32, timer: 30, phase: "telegraph", activeFrames: 18,
        damage: calculateBossAttackDamage(boss, 1.2),
        blind: true, blindDuration: 150,
        color: "#ef4444", label: "🔴 ЛАЗЕР (ОСЛЕПЛЕНИЕ 2.5с!)"
      });
    }
    return true;
  }

  // 20. ENIGMA: Midnight Pulse or BLACK HOLE (Чёрная Дыра)
  if (bId.includes("enigma") || bId.includes("пожиратель миров")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "🌌 ЧЁРНАЯ ДЫРА (BLACK HOLE)!", "#6366f1");
      triggerHaptic("heavy");
      ARENA.cameraTrauma = 1.0;
      ARENA.bossTelegraphs.push({
        type: "black_hole", cx: ARENA.width / 2, cy: ARENA.height / 2,
        r: 125, timer: 180, color: "#1e1b4b",
        dmg: calculateBossAttackDamage(boss, 0.45)
      });
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "💜 ПУЛЬС ПОЛУНОЧИ (MIDNIGHT PULSE)!", "#818cf8");
      ARENA.dangerZones.push({
        type: "circle", cx: p.x, cy: p.y, r: 90,
        timer: 20, phase: "telegraph", activeFrames: 90, isDot: true,
        damage: calculateBossAttackDamage(boss, 0.4),
        slow: true, slowDuration: 60, slowRatio: 0.4,
        color: "#4338ca", label: "💜 MIDNIGHT PULSE"
      });
    }
    return true;
  }

  return false;
}
