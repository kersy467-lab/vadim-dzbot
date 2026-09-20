// ============================================================================
// 04_boss_abilities_early.js — Signature Attacks & Ultimates for Bosses 1–10
// (Golem, Lich, Tormentor, Dragon, Pudge, Void, Roshan, Tidehunter, SF, Necro)
// ============================================================================

function executeBossAbilityEarly(boss, p, bId, abilityType, ARENA) {
  const pAng = Math.atan2(p.y - boss.y, p.x - boss.x);
  const dist = Math.hypot(p.x - boss.x, p.y - boss.y);

  // 1. GOLEM: Fissure (Разлом) or Tectonic Seismic Slam (Сейсмовзрыв)
  if (bId.includes("golem") || bId.includes("голем")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "🌋 ТЕКТОНИЧЕСКИЙ СЕЙСМОВЗРЫВ!", "#f97316");
      triggerHaptic("heavy");
      ARENA.cameraTrauma = 0.8;
      for (let ring = 1; ring <= 3; ring++) {
        ARENA.dangerZones.push({
          type: "circle", cx: boss.x, cy: boss.y, r: ring * 65,
          timer: ring * 18, phase: "telegraph", activeFrames: 14,
          damage: calculateBossAttackDamage(boss, 1.4),
          stun: 60, color: "#f97316", label: "🌋 СЕЙСМОВЗРЫВ (СТАН!)"
        });
      }
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "🪨 РАЗЛОМ ЗЕМЛИ!", "#facc15");
      const fx = boss.x + Math.cos(pAng) * 160;
      const fy = boss.y + Math.sin(pAng) * 160;
      ARENA.dangerZones.push({
        type: "line", x1: boss.x, y1: boss.y, x2: fx, y2: fy, width: 36,
        timer: 35, phase: "telegraph", activeFrames: 12,
        damage: calculateBossAttackDamage(boss, 0.95),
        slow: true, slowDuration: 90, slowRatio: 0.4,
        color: "#ca8a04", label: "🪨 РАЗЛОМ (ЗАМЕДЛЕНИЕ)"
      });
    }
    return true;
  }

  // 2. LICH: Frost Nova (Ледяной взрыв) or Chain Frost (Цепной Мороз)
  if (bId.includes("lich") || bId.includes("лич")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "❄️ ЦЕПНОЙ МОРОЗ (CHAIN FROST)!", "#38bdf8");
      triggerHaptic("heavy");
      ARENA.bossProjectiles.push({
        x: boss.x, y: boss.y,
        vx: Math.cos(pAng) * 3.6, vy: Math.sin(pAng) * 3.6,
        radius: 12, color: "#38bdf8", timer: 320,
        bouncesLeft: 5, isChainFrost: true,
        dmg: calculateBossAttackDamage(boss, 1.6),
        stun: 35, slow: true, slowDuration: 120, slowRatio: 0.3,
        label: "❄️ ЦЕПНОЙ МОРОЗ (СТАН)"
      });
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "🧊 FROST NOVA!", "#0284c7");
      ARENA.dangerZones.push({
        type: "circle", cx: p.x, cy: p.y, r: 52,
        timer: 30, phase: "telegraph", activeFrames: 15,
        damage: calculateBossAttackDamage(boss, 0.9),
        slow: true, slowDuration: 100, slowRatio: 0.35,
        color: "#0284c7", label: "🧊 NOVA (ЗАМЕДЛЕНИЕ)"
      });
    }
    return true;
  }

  // 3. TORMENTOR: Needle Spread or Reflective Barrier + Resonance Beam
  if (bId.includes("tormentor") && !bId.includes("dark_tormentor")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "🔮 РЕЗОНАНСНЫЙ ЛАЗЕР БЕЗДНЫ!", "#e879f9");
      boss.shieldActive = 180;
      triggerHaptic("heavy");
      ARENA.bossTelegraphs.push({
        type: "rotating_beam", cx: boss.x, cy: boss.y,
        angle: 0, rotSpeed: 0.045, length: 320, timer: 220,
        damage: calculateBossAttackDamage(boss, 3.2), color: "#c084fc",
        burn: true, burnDuration: 120, burnDmg: Math.floor((boss.atk || 320) * 0.8)
      });
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "✨ ОСКОЛОЧНЫЙ ЗАЛП!", "#c084fc");
      for (let n = 0; n < 8; n++) {
        const ang = (n * Math.PI) / 4;
        ARENA.bossProjectiles.push({
          x: boss.x + Math.cos(ang) * 20, y: boss.y + Math.sin(ang) * 20,
          vx: Math.cos(ang) * 3.2, vy: Math.sin(ang) * 3.2,
          radius: 7, color: "#e879f9", timer: 180,
          dmg: calculateBossAttackDamage(boss, 0.75),
          slow: true, slowDuration: 60, slowRatio: 0.6,
          label: "✨ ОСКОЛОК"
        });
      }
    }
    return true;
  }

  // 4. DRAGON: Fire Breath Cone or Inferno Cataclysm
  if (bId.includes("dragon") || bId.includes("дракон")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "🌋 КАТАКЛИЗМ ИНФЕРНО!", "#ef4444");
      triggerHaptic("heavy");
      ARENA.cameraTrauma = 0.9;
      for (let m = 0; m < 5; m++) {
        const mx = 60 + Math.random() * (ARENA.width - 120);
        const my = 60 + Math.random() * (ARENA.height - 120);
        ARENA.dangerZones.push({
          type: "circle", cx: mx, cy: my, r: 48,
          timer: 25 + m * 14, phase: "telegraph", activeFrames: 16,
          damage: calculateBossAttackDamage(boss, 1.25),
          stun: 45, burn: true, burnDuration: 150, burnDmg: Math.floor(boss.atk * 0.22),
          color: "#ea580c", label: "🌋 МЕТЕОР (СТАН & ОЖОГ)"
        });
      }
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "🔥 ОГНЕННОЕ ДЫХАНИЕ!", "#f97316");
      ARENA.dangerZones.push({
        type: "cone", cx: boss.x, cy: boss.y, angle: pAng, spread: 0.6, range: 170,
        timer: 32, phase: "telegraph", activeFrames: 24,
        damage: calculateBossAttackDamage(boss, 0.85),
        burn: true, burnDuration: 120, burnDmg: Math.floor(boss.atk * 0.18),
        color: "#ef4444", label: "🔥 ПЛАМЯ (ОЖОГ)"
      });
    }
    return true;
  }

  // 5. PUDGE: Meat Hook (Мясницкий крюк) or Dismember (Расчленение)
  if (bId.includes("pudge") || bId.includes("мясник")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "🩸 РАСЧЛЕНЕНИЕ (DISMEMBER)!", "#dc2626");
      triggerHaptic("heavy");
      ARENA.dangerZones.push({
        type: "circle", cx: boss.x, cy: boss.y, r: 85,
        timer: 15, phase: "telegraph", activeFrames: 60, isDot: true,
        damage: calculateBossAttackDamage(boss, 0.35),
        poison: true, poisonDuration: 60, slow: true, slowDuration: 60, slowRatio: 0.35,
        color: "#84cc16", label: "🩸 РАСЧЛЕНЕНИЕ (ЯД & ЗАМЕДЛЕНИЕ)"
      });
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "🪝 МЯСНИЦКИЙ КРЮК!", "#78716c");
      triggerHaptic("medium");
      ARENA.bossProjectiles.push({
        x: boss.x, y: boss.y,
        vx: Math.cos(pAng) * 5.4, vy: Math.sin(pAng) * 5.4,
        radius: 10, color: "#a8a29e", timer: 120, isMeatHook: true,
        originX: boss.x, originY: boss.y,
        dmg: calculateBossAttackDamage(boss, 1.1),
        stun: 60, label: "🪝 ХУК (СТАН!)"
      });
    }
    return true;
  }

  // 6. FACELESS VOID: Time Walk or Chronosphere (Хроносфера)
  if (bId.includes("faceless_void") || bId.includes("хроно")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "⏳ ХРОНОСФЕРА (ОСТАНОВКА ВРЕМЕНИ)!", "#a855f7");
      triggerHaptic("heavy");
      ARENA.cameraTrauma = 1.0;
      ARENA.bossTelegraphs.push({
        type: "chronosphere", cx: p.x, cy: p.y, r: 105,
        timer: 140, color: "rgba(168, 85, 247, 0.45)"
      });
      boss.x = p.x + 25;
      boss.y = p.y - 25;
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "⌛ TIME WALK + BASH!", "#c084fc");
      boss.x = p.x - Math.cos(pAng) * 45;
      boss.y = p.y - Math.sin(pAng) * 45;
      ARENA.dangerZones.push({
        type: "circle", cx: boss.x, cy: boss.y, r: 55,
        timer: 24, phase: "telegraph", activeFrames: 10,
        damage: calculateBossAttackDamage(boss, 1.2),
        stun: 60, color: "#c084fc", label: "⌛ BASH (СТАН 1с!)"
      });
    }
    return true;
  }

  // 7. ROSHAN: Ground Slam or Roar of Chaos (Рёв Ярости)
  if (bId.includes("roshan") && !bId.includes("phantom")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "🐲 РЁВ ЯРОСТИ РОШАНА!", "#ef4444");
      triggerHaptic("heavy");
      ARENA.cameraTrauma = 1.0;
      if (typeof applyStatusEffectToPlayer === "function") {
        applyStatusEffectToPlayer({ knockback: true, knockbackAngle: pAng, knockbackDist: 70 });
      }
      for (let rc = 0; rc < 4; rc++) {
        ARENA.dangerZones.push({
          type: "circle", cx: p.x + (Math.random() * 80 - 40), cy: p.y + (Math.random() * 80 - 40), r: 44,
          timer: 20 + rc * 12, phase: "telegraph", activeFrames: 14,
          damage: calculateBossAttackDamage(boss, 1.1),
          stun: 55, color: "#b45309", label: "⚠️ ОБВАЛ (СТАН!)"
        });
      }
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "💥 РОШАН-СЛЭМ!", "#ea580c");
      ARENA.dangerZones.push({
        type: "circle", cx: boss.x, cy: boss.y, r: 75,
        timer: 32, phase: "telegraph", activeFrames: 12,
        damage: calculateBossAttackDamage(boss, 0.95),
        slow: true, slowDuration: 120, slowRatio: 0.3,
        color: "#ea580c", label: "💥 СЛЭМ (ЗАМЕДЛЕНИЕ)"
      });
    }
    return true;
  }

  // 8. TIDEHUNTER: Gush or Ravage (Сокрушительный Раваж)
  if (bId.includes("tidehunter") || bId.includes("левиафан")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "🐙 СОКРУШИТЕЛЬНЫЙ РАВАЖ (RAVAGE)!", "#10b981");
      triggerHaptic("heavy");
      ARENA.cameraTrauma = 1.0;
      for (let tr = 1; tr <= 4; tr++) {
        ARENA.dangerZones.push({
          type: "circle", cx: boss.x, cy: boss.y, r: tr * 68,
          timer: tr * 14, phase: "telegraph", activeFrames: 16,
          damage: calculateBossAttackDamage(boss, 1.35),
          stun: 90, color: "#059669", label: "🐙 РАВАЖ (ОГЛУШЕНИЕ 1.5с!)"
        });
      }
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "🌊 ВОДЯНАЯ СТРУЯ (GUSH)!", "#34d399");
      ARENA.bossProjectiles.push({
        x: boss.x, y: boss.y,
        vx: Math.cos(pAng) * 4.2, vy: Math.sin(pAng) * 4.2,
        radius: 12, color: "#10b981", timer: 140,
        dmg: calculateBossAttackDamage(boss, 0.85),
        slow: true, slowDuration: 120, slowRatio: 0.35,
        label: "🌊 GUSH (ЗАМЕДЛЕНИЕ)"
      });
    }
    return true;
  }

  // 9. SHADOW FIEND: Shadowraze Trio or Requiem of Souls (Реквием Душ)
  if (bId.includes("sf_boss") || bId.includes("nevermore")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "💀 РЕКВИЕМ ДУШ (REQUIEM OF SOULS)!", "#dc2626");
      triggerHaptic("heavy");
      ARENA.cameraTrauma = 1.0;
      for (let s = 0; s < 16; s++) {
        const sAng = (s * Math.PI * 2) / 16;
        ARENA.bossProjectiles.push({
          x: boss.x, y: boss.y,
          vx: Math.cos(sAng) * 3.4, vy: Math.sin(sAng) * 3.4,
          radius: 9, color: "#ef4444", timer: 180,
          dmg: calculateBossAttackDamage(boss, 1.2),
          silence: 120, slow: true, slowDuration: 120, slowRatio: 0.35,
          label: "💀 РЕКВИЕМ (САЙЛЕНС 2с!)"
        });
      }
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "🔥 ТРОЙНОЙ SHADOWRAZE!", "#f87171");
      const dists = [60, 115, 175];
      dists.forEach((d, idx) => {
        const cx = boss.x + Math.cos(pAng) * d;
        const cy = boss.y + Math.sin(pAng) * d;
        ARENA.dangerZones.push({
          type: "circle", cx, cy, r: 42,
          timer: 18 + idx * 12, phase: "telegraph", activeFrames: 12,
          damage: calculateBossAttackDamage(boss, 0.95),
          slow: true, slowDuration: 60, slowRatio: 0.5,
          color: "#b91c1c", label: `🔥 КОИЛ #${idx + 1}`
        });
      });
    }
    return true;
  }

  // 10. NECROPHOS: Death Pulse or Reaper's Scythe (Коса Смерти)
  if (bId.includes("necrophos") || bId.includes("чумной")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "☠️ КОСА СМЕРТИ (REAPER'S SCYTHE)!", "#84cc16");
      triggerHaptic("heavy");
      const missingPct = Math.max(0, 1.0 - (p.currentHp / (p.maxHp || 400)));
      const scytheDmg = calculateBossAttackDamage(boss, 1.2 + missingPct * 1.8);
      ARENA.dangerZones.push({
        type: "circle", cx: p.x, cy: p.y, r: 60,
        timer: 45, phase: "telegraph", activeFrames: 15,
        damage: scytheDmg, stun: 75,
        color: "#65a30d", label: "💀 КОСА СМЕРТИ (КАЗНЬ!)"
      });
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "💚 ПУЛЬСАЦИЯ СМЕРТИ!", "#a3e635");
      for (let dp = 0; dp < 8; dp++) {
        const dpAng = (dp * Math.PI) / 4;
        ARENA.bossProjectiles.push({
          x: boss.x, y: boss.y,
          vx: Math.cos(dpAng) * 2.8, vy: Math.sin(dpAng) * 2.8,
          radius: 8, color: "#84cc16", timer: 160,
          dmg: calculateBossAttackDamage(boss, 0.75),
          poison: true, poisonDuration: 90,
          label: "💚 ПУЛЬС СМЕРТИ (ЯД)"
        });
      }
    }
    return true;
  }

  return false;
}
