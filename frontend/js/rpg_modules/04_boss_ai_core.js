// ============================================================================
// 04_boss_ai_core.js — Boss AI Dispatcher, Ability Rotation & Ultimate Gauge
// ============================================================================

function updateCustomBossAI(boss, p, ARENA) {
  if (!boss || boss.hp <= 0) return;

  // Initialize timers if missing
  if (boss.skillCooldown == null) boss.skillCooldown = 180; // ~3s initial grace
  if (boss.ultimateMeter == null) boss.ultimateMeter = 0;
  if (boss.meleeCooldown == null) boss.meleeCooldown = 60;
  if (!ARENA.bossTelegraphs) ARENA.bossTelegraphs = [];

  const bId = (boss.bossType || boss.boss_id || boss.id || boss.name || "").toLowerCase();

  // Enrage Stages based on Timer or HP (5-minute hard cap = God Mode)
  boss.battleStartTime = boss.battleStartTime || Date.now();
  boss.enrageTimer = (boss.enrageTimer || 0) + 1;
  const elapsedMs = Date.now() - boss.battleStartTime;
  const isGodMode = elapsedMs >= 300000 || boss.enrageTimer >= 18000;

  if (isGodMode) {
    if (!boss.isGodMode) {
      boss.isGodMode = true;
      triggerHaptic("heavy");
      if (ARENA.cameraTrauma !== undefined) ARENA.cameraTrauma = 1.0;
      spawnFloatingText(boss.x, boss.y - 45, "⚡⚡ РЕЖИМ БОГА! ⚡⚡", "#ef4444");
    }
    boss.enrageStage = "god_mode";
    // 5% max HP regen per sec
    const regenPerSec = Math.max(500, Math.floor((boss.maxHp || 10000) * 0.05));
    const regenPerFrame = Math.max(1, Math.floor(regenPerSec / 60));
    boss.hp = Math.min(boss.maxHp, boss.hp + regenPerFrame);
    if (ARENA.frameCount % 60 === 0) {
      spawnFloatingText(boss.x, boss.y - 30, `✨ +${Math.round(regenPerSec)} РЕГЕН БОГА`, "#22c55e");
    }
  } else {
    const hpPct = boss.hp / (boss.maxHp || 1);
    if (boss.enrageTimer > 5400 || hpPct <= 0.15) {
      boss.enrageStage = "enraged";
    } else if (boss.enrageTimer > 3600 || hpPct <= 0.40) {
      boss.enrageStage = "furious";
    } else if (boss.enrageTimer > 1800 || hpPct <= 0.70) {
      boss.enrageStage = "angry";
    }
  }

  const bSpeedMult = boss.isGodMode ? 3.5 : (boss.enrageStage === "enraged" ? 1.3 : boss.enrageStage === "furious" ? 1.18 : boss.enrageStage === "angry" ? 1.08 : 1.0);

  // Decrement cooldowns & charge Ultimate meter
  const cdReduction = boss.isGodMode ? 3 : 1;
  boss.skillCooldown = Math.max(0, boss.skillCooldown - cdReduction);
  boss.meleeCooldown = Math.max(0, boss.meleeCooldown - cdReduction);
  boss.chargeCooldown = Math.max(0, (boss.chargeCooldown || 0) - cdReduction);
  
  let ultChargeRate = boss.isGodMode ? 0.8 : (boss.enrageStage === "enraged" ? 0.14 : 0.08);
  if (bId.includes("faceless_void") || bId.includes("хроно")) {
    if (!boss.isGodMode) ultChargeRate *= 0.25; // Massive nerf to Chronosphere cooldown (4x longer, ~1.5 - 2 mins)
  }
  boss.ultimateMeter = Math.min(100, (boss.ultimateMeter || 0) + ultChargeRate);

  // Find nearest target (player or active companion)
  let closestTarget = p;
  let minDist = Math.hypot(p.x - boss.x, p.y - boss.y);
  for (const comp of (ARENA.bossCompanions || [])) {
    if (comp.hp > 0) {
      const d = Math.hypot(comp.x - boss.x, comp.y - boss.y);
      if (d < minDist) { minDist = d; closestTarget = comp; }
    }
  }

  // Handle Doom debuff on player
  if (p.doomDebuffTimer > 0) {
    p.doomDebuffTimer--;
    if (ARENA.frameCount % 30 === 0) {
      const dDmg = Math.max(8, Math.floor((p.maxHp || 400) * 0.035));
      applyDamageToPlayer(dDmg, "doom");
      spawnFloatingText(p.x, p.y - 20, `🔥 DOOM -${dDmg}`, "#dc2626");
    }
  }

  // Update Special Boss Telegraphs (Black Hole & Chronosphere)
  for (let bti = ARENA.bossTelegraphs.length - 1; bti >= 0; bti--) {
    const bt = ARENA.bossTelegraphs[bti];
    bt.timer--;

    // 1. BLACK HOLE PULL
    if (bt.type === "black_hole") {
      const dHole = Math.hypot(p.x - bt.cx, p.y - bt.cy);
      if (dHole < bt.r + 65) {
        // Gravitational vortex pull towards center
        const pPullAng = Math.atan2(bt.cy - p.y, bt.cx - p.x);
        p.x += Math.cos(pPullAng) * 3.4;
        p.y += Math.sin(pPullAng) * 3.4;
        applyStatusEffectToPlayer({ silence: 25, slow: true, slowDuration: 25, slowRatio: 0.3 });
        if (ARENA.frameCount % 20 === 0) {
          const bhDmg = Math.floor(bt.dmg || calculateBossAttackDamage(boss, 0.45));
          applyDamageToPlayer(bhDmg, "black_hole");
          spawnFloatingText(p.x, p.y - 20, `🌌 ЧЁРНАЯ ДЫРА -${bhDmg}`, "#6366f1");
          ARENA.cameraTrauma = 0.4;
          triggerHaptic("heavy");
        }
      }
    }
    // 2. CHRONOSPHERE TIME FREEZE
    else if (bt.type === "chronosphere") {
      const dChrono = Math.hypot(p.x - bt.cx, p.y - bt.cy);
      if (dChrono < bt.r) {
        p.isFrozenInTime = true;
        applyStatusEffectToPlayer({ stun: 12 });
      } else {
        p.isFrozenInTime = false;
      }
    }
    // 3. ROTATING RESONANCE BEAM (Ancient Tormentor Laser)
    else if (bt.type === "rotating_beam") {
      bt.angle += bt.rotSpeed;
      const bx2 = bt.cx + Math.cos(bt.angle) * bt.length;
      const by2 = bt.cy + Math.sin(bt.angle) * bt.length;
      const lineDist = distToSegment(p.x, p.y, bt.cx, bt.cy, bx2, by2);
      if (lineDist < p.radius + 16 && (ARENA.frameCount % 12 === 0)) {
        const baseBeamDmg = Math.floor(bt.damage || calculateBossAttackDamage(boss, 3.2));
        const pctMelt = Math.floor((p.maxHp || 1000) * 0.08); // 8% HP melt per tick
        const bmDmg = baseBeamDmg + pctMelt;
        applyDamageToPlayer(bmDmg, "beam");
        spawnFloatingText(p.x, p.y - 20, `🔮 СМЕРТЕЛЬНЫЙ ЛАЗЕР -${bmDmg}!`, "#e879f9");
        triggerHaptic("heavy");
        if (ARENA.cameraTrauma !== undefined) ARENA.cameraTrauma = Math.min(1.0, (ARENA.cameraTrauma || 0) + 0.35);
        applyStatusEffectToPlayer({ burn: true, burnDuration: 90, burnDmg: Math.floor((boss.atk || 320) * 0.6) });
      }
    }

    if (bt.timer <= 0) {
      if (bt.type === "chronosphere") p.isFrozenInTime = false;
      ARENA.bossTelegraphs.splice(bti, 1);
    }
  }

  // BOSS STATE MACHINE
  if (boss.state === "chase" || !boss.state) {
    boss.state = "chase";

    // Dynamic Pursuit
    const bAng = Math.atan2(closestTarget.y - boss.y, closestTarget.x - boss.x);
    const moveSpd = (boss.speed || 1.45) * bSpeedMult;
    boss.x += Math.cos(bAng) * moveSpd;
    boss.y += Math.sin(bAng) * moveSpd;
    boss.facing = Math.cos(bAng) >= 0 ? 1 : -1;

    // 1. Trigger Signature ULTIMATE if meter is full (100%)
    if (boss.ultimateMeter >= 100) {
      boss.ultimateMeter = 0;
      boss.skillCooldown = 160;
      let casted = false;
      if (typeof executeBossAbilityEarly === "function") {
        casted = executeBossAbilityEarly(boss, p, bId, "ultimate", ARENA);
      }
      if (!casted && typeof executeBossAbilityLate === "function") {
        casted = executeBossAbilityLate(boss, p, bId, "ultimate", ARENA);
      }
      return;
    }

    // 2. Trigger Signature Normal Ability (every ~4-6 seconds)
    if (boss.skillCooldown <= 0 && minDist > 60) {
      boss.skillCooldown = 260;
      let casted = false;
      if (typeof executeBossAbilityEarly === "function") {
        casted = executeBossAbilityEarly(boss, p, bId, "normal", ARENA);
      }
      if (!casted && typeof executeBossAbilityLate === "function") {
        casted = executeBossAbilityLate(boss, p, bId, "normal", ARENA);
      }
      if (casted) return;
    }

    // 3. Trigger Melee Strike if close
    if (minDist < (boss.radius + p.radius + 24) && boss.meleeCooldown <= 0) {
      boss.state = "telegraph_melee";
      boss.stateTimer = 45;
      boss.meleeCooldown = 90;
      spawnFloatingText(boss.x, boss.y - 30, "⚠️ ЗАМАХ!", "#f59e0b");
    }
  } else if (boss.state === "telegraph_melee") {
    boss.stateTimer--;
    if (boss.stateTimer <= 0) {
      boss.state = "chase";
      ARENA.cameraTrauma = 0.45;
      triggerHaptic("heavy");
      if (Math.hypot(p.x - boss.x, p.y - boss.y) < (boss.radius + p.radius + 28) && !p.isInvulnerable) {
        const rawDmg = calculateBossAttackDamage(boss, 1.25);
        const actualDmg = applyDamageToPlayer(rawDmg, "melee");
        spawnFloatingText(p.x, p.y - 25, `💥 УДАР -${actualDmg}`, "#ef4444");
        applyStatusEffectToPlayer({ stun: 30 });
        if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
      }
    }
  }

  // Contact damage check
  if (Math.hypot(p.x - boss.x, p.y - boss.y) < (boss.radius + p.radius) && !p.isInvulnerable) {
    if ((ARENA.frameCount % 25) === 0) {
      const rawDmg = calculateBossAttackDamage(boss, 0.65);
      const actualDmg = applyDamageToPlayer(rawDmg, "contact");
      spawnFloatingText(p.x, p.y - 20, `💥 -${actualDmg}`, "#ef4444");
      triggerHaptic("medium");
      if (p.currentHp <= 0) { handlePlayerArenaDeath(); }
    }
  }

  // Handle Chain Frost bounces and Meat Hook pulling
  updateSpecialProjectiles(ARENA, boss, p);
}

function applyStatusEffectToPlayer(effect) {
  if (!effect) return;
  const p = ARENA.player;
  if (!p || p.isInvulnerable) return;

  // BKB (Black King Bar) magic immunity blocks all debuffs!
  if (p.bkbActive > 0) {
    if (ARENA.frameCount % 30 === 0) spawnFloatingText(p.x, p.y - 30, "🛡️ БКБ (ИММУНИТЕТ)!", "#facc15");
    return;
  }

  // 1. STUN
  const stunFrames = effect.stun || (effect.isStun ? (effect.stunDuration || 60) : 0);
  if (stunFrames > 0) {
    if (!p.stunTimer || p.stunTimer < stunFrames) {
      p.stunTimer = stunFrames;
      spawnFloatingText(p.x, p.y - 32, "💫 ОГЛУШЕНИЕ!", "#facc15");
      triggerHaptic("heavy");
    }
  }

  // 2. SLOW
  if (effect.slow || effect.slowEffect) {
    const sDur = effect.slowDuration || 90;
    const sRatio = effect.slowRatio || effect.slowEffect || 0.45;
    if (!p.slowTimer || p.slowTimer < sDur) {
      p.slowTimer = sDur;
      p.slowRatio = sRatio;
      spawnFloatingText(p.x, p.y - 26, "❄️ ЗАМЕДЛЕНИЕ!", "#38bdf8");
      triggerHaptic("light");
    }
  }

  // 3. SILENCE / DOOM
  const silFrames = effect.silence || effect.silenceDuration || 0;
  if (silFrames > 0) {
    if (!p.silenceTimer || p.silenceTimer < silFrames) {
      p.silenceTimer = silFrames;
      spawnFloatingText(p.x, p.y - 32, "🔇 БЕЗМОЛВИЕ!", "#c084fc");
      triggerHaptic("medium");
    }
  }

  // 4. BURN DoT
  if (effect.burn) {
    p.burnTimer = effect.burnDuration || 120;
    p.burnDmg = effect.burnDmg || Math.max(10, Math.floor(calculateBossAttackDamage(ARENA.bossEntity, 0.16)));
    spawnFloatingText(p.x, p.y - 22, "🔥 ОЖОГ!", "#f97316");
  }

  // 5. POISON DoT
  if (effect.poison) {
    p.poisonTimer = effect.poisonDuration || 120;
    p.poisonDmg = effect.poisonDmg || Math.max(10, Math.floor(calculateBossAttackDamage(ARENA.bossEntity, 0.16)));
    spawnFloatingText(p.x, p.y - 22, "☣️ ОТРАВЛЕНИЕ!", "#84cc16");
  }

  // 6. BLIND
  if (effect.blind) {
    p.blindTimer = effect.blindDuration || 120;
    spawnFloatingText(p.x, p.y - 30, "🔴 ОСЛЕПЛЕНИЕ!", "#ef4444");
  }

  // 7. KNOCKBACK
  if (effect.knockback && effect.knockbackAngle != null) {
    const kbDist = effect.knockbackDist || 35;
    p.x = Math.max(30, Math.min(490, p.x + Math.cos(effect.knockbackAngle) * kbDist));
    p.y = Math.max(40, Math.min(680, p.y + Math.sin(effect.knockbackAngle) * kbDist));
  }
}

function updateSpecialProjectiles(ARENA, boss, p) {
  for (let pi = ARENA.bossProjectiles.length - 1; pi >= 0; pi--) {
    const proj = ARENA.bossProjectiles[pi];

    // Chain Frost Bouncing & Impact
    if (proj.isChainFrost) {
      if (proj.x <= 20 || proj.x >= ARENA.width - 20) { proj.vx *= -1; proj.bouncesLeft--; }
      if (proj.y <= 25 || proj.y >= ARENA.height - 25) { proj.vy *= -1; proj.bouncesLeft--; }
      if (Math.hypot(p.x - proj.x, p.y - proj.y) < (p.radius + proj.radius + 6) && !p.isInvulnerable) {
        const cDmg = applyDamageToPlayer(proj.dmg || calculateBossAttackDamage(boss, 1.5), "chain_frost");
        spawnFloatingText(p.x, p.y - 25, `❄️ ЦЕПНОЙ МОРОЗ -${cDmg}`, "#38bdf8");
        applyStatusEffectToPlayer({ stun: 35, slow: true, slowDuration: 120, slowRatio: 0.35 });
        proj.bouncesLeft--;
        proj.vx = -proj.vx;
        proj.vy = -proj.vy;
      }
      if (proj.bouncesLeft <= 0) { ARENA.bossProjectiles.splice(pi, 1); continue; }
    }

    // Pudge Meat Hook Drag & Stun
    if (proj.isMeatHook) {
      if (Math.hypot(p.x - proj.x, p.y - proj.y) < (p.radius + proj.radius + 8)) {
        p.x = Math.max(30, Math.min(490, boss.x + Math.cos(Math.atan2(p.y - boss.y, p.x - boss.x)) * (boss.radius + 18)));
        p.y = Math.max(40, Math.min(680, boss.y + Math.sin(Math.atan2(p.y - boss.y, p.x - boss.x)) * (boss.radius + 18)));
        const hookDmg = applyDamageToPlayer(proj.dmg || calculateBossAttackDamage(boss, 1.25), "meat_hook");
        spawnFloatingText(p.x, p.y - 25, `🪝 ПРИТЯНУТ ХУКОМ -${hookDmg}!`, "#ef4444");
        applyStatusEffectToPlayer({ stun: 60 });
        triggerHaptic("heavy");
        ARENA.bossProjectiles.splice(pi, 1);
        continue;
      }
    }
  }
}

function distToSegment(px, py, x1, y1, x2, y2) {
  const l2 = (x2 - x1) * (x2 - x1) + (y2 - y1) * (y2 - y1);
  if (l2 === 0) return Math.hypot(px - x1, py - y1);
  let t = ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / l2;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(px - (x1 + t * (x2 - x1)), py - (y1 + t * (y2 - y1)));
}
