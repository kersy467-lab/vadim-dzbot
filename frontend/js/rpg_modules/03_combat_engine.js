  function applyDamageToBoss(boss, rawDmg, isCrit) {
    if (!boss || boss.hp <= 0 || isNaN(boss.hp)) return 0;
    if (rawDmg == null || isNaN(rawDmg) || rawDmg <= 0) return 0;

    const p = ARENA.player;
    const stats = RPG_STATE.profile?.stats || {};
    const eq = RPG_STATE.profile?.equipment || {};

      // Boss defense: stored on entity, or fallback by tier
    const BOSS_DEF_BY_TIER = {
      golem: 35, lich: 50, tormentor: 75, dragon: 105, pudge_boss: 140,
      faceless_void: 180, roshan: 230, tidehunter: 290, sf_boss: 370,
      necrophos: 460, terrorblade: 570, invoker_boss: 700, chaos_knight: 860,
      dark_tormentor: 1050, storm_spirit: 1300, doom: 1600, primal_beast: 1950,
      phantom_roshan: 2400, tinker_boss: 3000, enigma: 3800
    };
    let bossDefense = boss.defense !== undefined ? boss.defense : 35;
    if (!boss.defense) {
      const bId = ((boss.bossType || boss.id || boss.name) || "golem").toLowerCase();
      for (const [k, v] of Object.entries(BOSS_DEF_BY_TIER)) {
        if (bId.includes(k)) { bossDefense = v; break; }
      }
    }

    // Passive Items on Boss: Desolator & Assault Cuirass Minus Armor
    const hasDeso = Object.values(eq).some(it => it && (it.name?.includes("Desolator") || it.name?.includes("Опустошитель") || it.bonus?.minus_armor));
    const hasAC = Object.values(eq).some(it => it && (it.name?.includes("Assault") || it.name?.includes("Штурма") || it.bonus?.minus_armor_aura));
    if (hasDeso) {
      if (!boss.desoDebuff) {
        spawnFloatingText(boss.x, boss.y - 30, "🩸 -10 БРОНИ (DESOLATOR)", "#dc2626");
      }
      boss.desoDebuff = 300; // 5 seconds debuff
    }
    const totalArmorShred = (boss.desoDebuff > 0 ? 10 : 0) + (hasAC ? 10 : 0);
    const effectiveArmor = Math.max(0, bossDefense - totalArmorShred);

    // Hyperbolic armor reduction: DR = armor / (armor + 100)
    const armorDR = effectiveArmor / (effectiveArmor + 100);

    // Apply defense reduction to raw damage
    let afterArmor = Math.max(1, Math.floor(rawDmg * (1.0 - armorDR)));

    // Passive Item: MKB True Strike & Pure Bonus (+120 pure damage that ignores armor)
    const hasMkb = Object.values(eq).some(it => it && (it.name?.includes("Monkey") || it.name?.includes("Обезьян") || it.bonus?.pure_proc));
    if (hasMkb && Math.random() < 0.75) {
      afterArmor += 120;
      spawnFloatingText(boss.x, boss.y - 40, "🎯 MKB +120 ПИРС!", "#38bdf8");
    }

    // Passive Item: Mjollnir Chain Lightning (25% chance for 220 electric burst)
    const hasMjollnir = Object.values(eq).some(it => it && (it.name?.includes("Mjollnir") || it.name?.includes("Мьёльнир") || it.bonus?.lightning_proc));
    if (hasMjollnir && Math.random() < 0.25) {
      afterArmor += 220;
      spawnFloatingText(boss.x, boss.y - 35, "⚡ МЬЁЛЬНИР -220!", "#38bdf8");
      if (!ARENA.shockwaves) ARENA.shockwaves = [];
      ARENA.shockwaves.push({ x: boss.x, y: boss.y, radius: 15, maxRadius: 55, alpha: 0.9, color: "#38bdf8" });
    }

    // Passive Item: Eye of Skadi (Slows boss movement and attacks by 40%)
    const hasSkadi = Object.values(eq).some(it => it && (it.name?.includes("Skadi") || it.name?.includes("Скади") || it.bonus?.frost_slow));
    if (hasSkadi) {
      if (!boss.skadiSlow) {
        spawnFloatingText(boss.x, boss.y - 25, "❄️ СКАДИ -40% СКОРОСТЬ", "#38bdf8");
      }
      boss.skadiSlow = 240;
      boss.speed = Math.max(0.70, (boss.baseSpeed || 1.45) * 0.60);
    }

    // Stagger bonus (+50% damage when boss is staggered / poise broken)
    const staggerMult = boss.isStaggered ? 1.5 : 1.0;

    // Passive Item: Daedalus Crit Multiplier
    const hasDaedalus = Object.values(eq).some(it => it && (it.name?.includes("Daedalus") || it.name?.includes("Даэдалус") || it.bonus?.crit_mult));
    let critMult = isCrit ? (hasDaedalus ? 2.5 : 1.5) : 1.0;

    let finalDmg = Math.max(1, Math.floor(afterArmor * staggerMult * critMult));

    // Single-hit sanity cap (protects against one-shot exploits or overflow bugs, up to 50% boss max HP per hit)
    const maxSingleHit = Math.max(5000, Math.floor((boss.maxHp || 1000) * 0.50));
    finalDmg = Math.min(finalDmg, maxSingleHit);

    const curBossHp = (!isNaN(boss.hp) && boss.hp > 0) ? boss.hp : (boss.maxHp || 1000);
    boss.hp = Math.max(0, curBossHp - finalDmg);

    // Passive Item: Satanic & General Lifesteal (only heals living player)
    const lifestealPct = stats.lifesteal || 0;
    if (p && !p.isDead && typeof p.currentHp === "number" && p.currentHp > 0 && lifestealPct > 0) {
      const pMax = p.maxHp || 500;
      const rawHeal = Math.floor(finalDmg * (lifestealPct / 100));
      const heal = Math.max(1, Math.min(Math.floor(pMax * 0.05), 5000, rawHeal));
      p.currentHp = Math.min(pMax, p.currentHp + heal);
      if (ARENA.frameCount % 10 === 0) {
        spawnFloatingText(p.x, p.y - 25, `+${heal} HP 🩸`, "#22c55e");
      }
    }

    // BOSS PHASES (Epic Boss Phase Transitions):
    // Phase 2 at 66% HP: Boss Enrages, gains speed and a radial shockwave!
    const hpRatio = boss.hp / boss.maxHp;
    if (hpRatio <= 0.66 && !boss._phase2Triggered) {
      boss._phase2Triggered = true;
      boss.enrageStage = "angry";
      boss.speed = (boss.speed || 1.4) * 1.15;
      spawnFloatingText(boss.x, boss.y - 45, "🔥 БОСС ВПАДАЕТ В ЯРОСТЬ! ФАЗА 2!", "#ea580c");
      triggerHaptic("heavy");
      if (ARENA.cameraTrauma !== undefined) ARENA.cameraTrauma = 0.65;
      if (!ARENA.shockwaves) ARENA.shockwaves = [];
      ARENA.shockwaves.push({ x: boss.x, y: boss.y, radius: 10, maxRadius: 90, alpha: 1.0, color: "#ea580c" });
    }
    // Phase 3 at 33% HP: Desperation Frenzy!
    if (hpRatio <= 0.33 && !boss._phase3Triggered) {
      boss._phase3Triggered = true;
      boss.enrageStage = "enraged";
      boss.speed = (boss.speed || 1.4) * 1.20;
      spawnFloatingText(boss.x, boss.y - 45, "⚡ СМЕРТЕЛЬНАЯ ФАЗА! БОСС БЕЗУМЕН!", "#ef4444");
      triggerHaptic("heavy");
      if (ARENA.cameraTrauma !== undefined) ARENA.cameraTrauma = 0.85;
      if (!ARENA.shockwaves) ARENA.shockwaves = [];
      ARENA.shockwaves.push({ x: boss.x, y: boss.y, radius: 10, maxRadius: 120, alpha: 1.0, color: "#ef4444" });
    }

    if (boss.hp <= 0 && ARENA.isRaidBossBattle && ARENA.waveState !== "boss_victory") {
      handleRaidBossDefeat();
    }

    return finalDmg;
  }

  // UNIVERSAL SAFE DAMAGE: Routes all damage through applyDamageToBoss if target is a boss!
  function safeDamageCreep(c, rawDmg, isCrit) {
    if (!c || c.hp <= 0 || isNaN(c.hp)) return 0;
    if (rawDmg == null || isNaN(rawDmg) || rawDmg <= 0) return 0;
    if (c.isBoss) {
      return applyDamageToBoss(c, rawDmg, isCrit);
    }
    const dmg = Math.max(1, Math.floor(rawDmg));
    c.hp = Math.max(0, c.hp - dmg);
    return dmg;
  }

  function calculateBossAttackDamage(boss, baseMult = 1.0) {
    if (!boss) return 50;
    const p = ARENA.player;
    const stats = RPG_STATE.profile?.stats || {};
    const def = Math.max(0, stats.defense || 5);

    // Real boss attack: from entity, template, or tier scaling fallback
    const BOSS_TIER_ATK = {
      golem: 140, lich: 210, tormentor: 320, dragon: 500, pudge_boss: 800,
      faceless_void: 1250, roshan: 1950, tidehunter: 3000, sf_boss: 4600,
      necrophos: 7000, terrorblade: 11000, invoker_boss: 17500, chaos_knight: 26500,
      dark_tormentor: 42000, storm_spirit: 64000, doom: 98000, primal_beast: 150000,
      phantom_roshan: 230000, tinker_boss: 350000, enigma: 500000
    };
    let bossAtk = boss.atk || boss.baseAtk;
    if (!bossAtk) {
      const bId = ((boss && (boss.id || boss.bossType || boss.name)) || "golem").toLowerCase();
      for (const [k, v] of Object.entries(BOSS_TIER_ATK)) {
        if (bId.includes(k)) { bossAtk = v; break; }
      }
      bossAtk = bossAtk || 140;
    }

    // Phase Enrage multiplier (when boss is enraged/furious/angry or in God Mode)
    let enrageMult = 1.0;
    const isGod = boss.isGodMode || boss.enrageStage === "god_mode";
    if (isGod) enrageMult = 15.0;
    else if (boss.enrageStage === "enraged") enrageMult = 1.40;
    else if (boss.enrageStage === "furious") enrageMult = 1.25;
    else if (boss.enrageStage === "angry") enrageMult = 1.15;

    let rawDmg = Math.floor(bossAtk * baseMult * enrageMult);

    // Hyperbolic player defense reduction: DR = def / (def + 80), max 80%
    const dr = isGod ? 0 : Math.min(0.80, (def * 1.0) / (def + 80));
    let finalDmg = Math.max(10, Math.floor(rawDmg * (1.0 - dr)));

    if (isGod) {
      const pMax = p ? (p.maxHp || stats.hp_max || 1000) : 1000;
      finalDmg = Math.max(finalDmg, Math.floor(pMax * 0.70));
    }

    if (p && p.isBlocking && !isGod) {
      finalDmg = Math.floor(finalDmg * 0.40);
    }

    return finalDmg;
  }

  function applyDamageToPlayer(rawDmg, attackType = "normal") {
    const p = ARENA.player;
    if (!p || p.isDead || (typeof p.currentHp === "number" && p.currentHp <= 0) || (typeof p.isInvulnerable === "number" && p.isInvulnerable > 0)) return 0;

    const stats = RPG_STATE.profile?.stats || {};
    const eq = RPG_STATE.profile?.equipment || {};

    const isMagic = (attackType === "magic" || attackType === "spell" || attackType === "burn" || attackType === "poison" ||
      attackType === "beam" || attackType === "chain_frost" || attackType === "danger_zone" || attackType === "black_hole" ||
      attackType === "doom" || attackType === "sunder");

    // 1. Evasion (for physical/attack hits) & Boss MKB (20% pierce chance)
    const canEvade = !isMagic;
    const dodgeChance = Math.min(70, stats.dodge_chance || 0);
    const bossMkbProcced = canEvade && (Math.random() < 0.20);
    
    if (canEvade && !bossMkbProcced && dodgeChance > 0 && Math.random() * 100 < dodgeChance) {
      spawnFloatingText(p.x, p.y - 25, "💨 УВОРОТ!", "#38bdf8");
      triggerHaptic("light");
      // PA PERK: Blur Heal (Restores 2.5% max HP on dodge, capped)
      if (window.hasTalentPerk && window.hasTalentPerk("perk_blur_heal")) {
        const healAmt = Math.max(1, Math.min(Math.floor((p.maxHp || 500) * 0.025), 3000));
        p.currentHp = Math.min(p.maxHp || 500, (p.currentHp || 0) + healAmt);
        spawnFloatingText(p.x, p.y - 45, `💚 +${healAmt} (РАЗМЫТИЕ)`, "#10b981");
      }
      return 0;
    }

    // 2. Passive Item: Radiance Blind (17% chance boss misses attack, bypassable by MKB)
    const hasRadiance = Object.values(eq).some(it => it && (it.name?.includes("Radiance") || it.name?.includes("Сияние") || it.bonus?.miss_aura));
    if (hasRadiance && canEvade && !bossMkbProcced && Math.random() < 0.17) {
      spawnFloatingText(p.x, p.y - 25, "💨 ПРОМАХ БОССА!", "#f59e0b");
      triggerHaptic("light");
      return 0;
    }

    // Juggernaut PERK: Blade Parry (15% chance to parry boss/creep melee attack and counter-attack)
    if (window.hasTalentPerk && window.hasTalentPerk("perk_blade_parry") && canEvade && Math.random() < 0.15) {
      spawnFloatingText(p.x, p.y - 25, "⚔️ ПАРИРОВАНИЕ КЛИНКОМ!", "#f59e0b");
      triggerHaptic("medium");
      const counterDmg = Math.max(10, Math.floor((stats.attack || 50) * 1.5));
      if (ARENA.isBossActive && ARENA.bossEntity && ARENA.bossEntity.hp > 0) {
        applyDamageToBoss(ARENA.bossEntity, counterDmg, true);
        spawnFloatingText(ARENA.bossEntity.x, ARENA.bossEntity.y - 25, `💥 КОНТРАТАКА -${counterDmg}!`, "#eab308");
      } else if (ARENA.creeps && ARENA.creeps.length > 0) {
        const tgt = ARENA.creeps.find(c => c.hp > 0);
        if (tgt) {
          safeDamageCreep(tgt, counterDmg);
          spawnFloatingText(tgt.x, tgt.y - 25, `💥 КОНТРАТАКА -${counterDmg}!`, "#eab308");
        }
      }
      return 0;
    }

    let finalDmg = Math.max(1, rawDmg);

    // 3. Magic Resistance: Reducts all magic, elemental and spell damage (up to 80% cap)
    if (isMagic) {
      const mr = Math.min(80, Math.max(0, stats.magic_resist || 0));
      if (mr > 0) {
        finalDmg = Math.max(1, Math.floor(finalDmg * (1.0 - mr / 100)));
      }
    }

    // 4. Passive Item: Vanguard / Crimson Guard Damage Block (70% chance, capped at 50% on bosses)
    const damageBlock = stats.damage_block || 0;
    if (damageBlock > 0 && Math.random() < 0.70) {
      const isBossEncounter = !!(ARENA.isRaidBossBattle || ARENA.isBossActive || ARENA.bossArenaMode);
      const effectiveBlock = isBossEncounter ? Math.min(damageBlock, Math.floor(finalDmg * 0.50)) : damageBlock;
      finalDmg = Math.max(1, finalDmg - effectiveBlock);
      spawnFloatingText(p.x, p.y - 20, `🛡️ БЛОК -${effectiveBlock} (АВАНГАРД)`, "#94a3b8");
    }

    // 5. Passive Item: Blade Mail Damage Return (Reflect 35% damage back to boss)
    const reflectPct = stats.reflect || 0;
    if (reflectPct > 0) {
      const reflectDmg = Math.max(1, Math.floor(rawDmg * (reflectPct / 100)));
      if (ARENA.isRaidBossBattle && ARENA.bossEntity && ARENA.bossEntity.hp > 0) {
        applyDamageToBoss(ARENA.bossEntity, reflectDmg);
        spawnFloatingText(ARENA.bossEntity.x, ARENA.bossEntity.y - 25, `🪞 ВОЗВРАТКА -${reflectDmg}!`, "#c084fc");
      } else if (ARENA.creeps && ARENA.creeps.length > 0) {
        const targetCreep = ARENA.creeps.find(c => c.hp > 0);
        if (targetCreep) {
          safeDamageCreep(targetCreep, reflectDmg);
          spawnFloatingText(targetCreep.x, targetCreep.y - 25, `🪞 ВОЗВРАТКА -${reflectDmg}!`, "#c084fc");
        }
      }
    }

    const pMax = Math.max(100, p.maxHp || 500);
    const nowFrame = ARENA.frameCount || 0;

    // Leshrac PERK: Earth Armor (Stone skin reduces physical damage up to 30% on low HP)
    if (window.hasTalentPerk && window.hasTalentPerk("perk_earth_armor") && !isMagic) {
      const missingPct = Math.max(0, 1 - ((p.currentHp || 0) / pMax));
      const armorReductionPct = Math.min(30, Math.floor((missingPct * 100) / 3));
      if (armorReductionPct > 0) {
        finalDmg = Math.max(1, Math.floor(finalDmg * (1 - armorReductionPct / 100)));
      }
    }

    // Invoker PERK: Mana Shield (30% incoming damage absorbed by MP: 1 MP = 2 HP)
    if (window.hasTalentPerk && window.hasTalentPerk("perk_mana_shield") && (p.currentMp || 0) > 0 && finalDmg > 1) {
      const absorbTarget = Math.floor(finalDmg * 0.30);
      const neededMp = Math.ceil(absorbTarget / 2);
      const usedMp = Math.min(p.currentMp, neededMp);
      const actualAbsorbed = usedMp * 2;
      p.currentMp = Math.max(0, p.currentMp - usedMp);
      finalDmg = Math.max(1, finalDmg - actualAbsorbed);
      if (actualAbsorbed > 0 && Math.random() < 0.35) {
        spawnFloatingText(p.x, p.y - 35, `🔮 ЩИТ РАЗУМА -${actualAbsorbed}`, "#818cf8");
      }
    }

    // Anti-Mage PERK: Blink Reflex (Auto-blinks with i-frame if taking >20% max HP)
    if (window.hasTalentPerk && window.hasTalentPerk("perk_blink_reflex") && finalDmg >= pMax * 0.20 && (!ARENA.blinkReflexCd || nowFrame > ARENA.blinkReflexCd)) {
      ARENA.blinkReflexCd = nowFrame + 1200; // 20s cooldown
      p.isInvulnerable = 30; // 0.5s i-frame
      spawnFloatingText(p.x, p.y - 35, "⚡ РЕФЛЕКС СКАЧКА!", "#a855f7");
      triggerHaptic("heavy");
      return 0;
    }

    // 6. PET PHOENIX: Supernova Lethal Protection (Saves from death every 30s)
    const equippedPet = (RPG_STATE.profile?.pets || []).find(pt => pt.is_equipped);
    const petType = equippedPet ? (equippedPet.type || equippedPet.pet_id) : localStorage.getItem("rpg_active_pet");
    if (petType === "phoenix" && finalDmg >= p.currentHp && (!p._phoenixShieldFrame || (ARENA.frameCount || 0) - p._phoenixShieldFrame > 1800)) {
      p._phoenixShieldFrame = ARENA.frameCount || 0;
      p.isInvulnerable = 180; // 3 seconds of immunity
      p.currentHp = Math.max(1, Math.floor(pMax * 0.35));
      spawnFloatingText(p.x, p.y - 30, "🦅 СВЕРХНОВАЯ ЗАЩИТА!", "#f59e0b");
      triggerHaptic("heavy");
      return 0;
    }

    // 7. HEALTH GATE PROTECTION:
    // Saves player ONCE per 60s from an unexpected lethal hit if they were at high health (>60% HP)
    const bossIsGod = ARENA.bossEntity && (ARENA.bossEntity.isGodMode || ARENA.bossEntity.enrageStage === "god_mode");
    if (!bossIsGod && p.currentHp > pMax * 0.60 && finalDmg >= p.currentHp && (!p._lastHealthGateFrame || nowFrame - p._lastHealthGateFrame > 3600)) {
      p._lastHealthGateFrame = nowFrame;
      finalDmg = Math.max(1, p.currentHp - 1);
      p.currentHp = 1;
      p.isInvulnerable = 18; // Brief 0.3s window to react
      spawnFloatingText(p.x, p.y - 30, "🛡️ СПАСЕНИЕ ОТ ВАНШОТА!", "#38bdf8");
      triggerHaptic("heavy");
      return finalDmg;
    }

    p.currentHp = Math.max(0, p.currentHp - finalDmg);
    if (p.currentHp <= 0) {
      p.currentHp = 0;
      p.isDead = true;
      p.isInvulnerable = 0;
      handlePlayerArenaDeath();
    }
    return finalDmg;
  }

  function setupArenaListeners(canvas) {
    function handleCanvasTap(cx, cy, screenX, screenY) {
      if (ARENA.waveState === "boss_victory") {
        const reward = RPG_STATE.lastBossChestReward;
        ARENA.waveState = "fighting";
        ARENA.isRaidBossBattle = false;
        ARENA._wasRaidBossBattle = true;
        RPG_STATE.lastBossChestReward = null;
        if (reward) {
          openChestModal(reward);
        } else {
          exitRaidBossBattle();
        }
        return;
      }
      if (ARENA.fallingChest && ARENA.fallingChest.landed && !ARENA.fallingChest.opened) {
        const fc = ARENA.fallingChest;
        if (Math.hypot(cx - fc.x, cy - fc.y) < 65) {
          fc.opened = true;
          if (RPG_STATE.lastBossChestReward) {
            openChestModal(RPG_STATE.lastBossChestReward);
          }
          return;
        }
      }
      if (ARENA.waveState === "boss_defeat") {
        const tapX = screenX !== undefined ? screenX : cx;
        const tapY = screenY !== undefined ? screenY : cy;
        if (ARENA._bossDefeatRetryBounds) {
          const rb = ARENA._bossDefeatRetryBounds;
          if (tapX >= rb.x - 10 && tapX <= rb.x + rb.w + 10 && tapY >= rb.y - 8 && tapY <= rb.y + rb.h + 8) {
            triggerHaptic("medium");
            if (ARENA.isRaidBossBattle && ARENA.currentRaidBoss && ARENA.currentRaidBoss.id) {
              startRaidBossActionBattle(ARENA.currentRaidBoss.id);
            } else {
              retryCurrentFloor();
            }
            return;
          }
        }
        if (ARENA._bossDefeatExitBounds) {
          const eb = ARENA._bossDefeatExitBounds;
          if (tapX >= eb.x - 10 && tapX <= eb.x + eb.w + 10 && tapY >= eb.y - 8 && tapY <= eb.y + eb.h + 8) {
            triggerHaptic("medium");
            if (ARENA.isRaidBossBattle) {
              exitRaidBossBattle();
            } else {
              retryCurrentFloor();
            }
            return;
          }
        }
        return;
      }
      if (ARENA.waveState === "prompt" || ARENA.waveState === "retry_prompt") {
        if (ARENA.waveState === "retry_prompt") {
          retryCurrentFloor();
        } else {
          if (ARENA._promptDisableBtnBounds) {
            const db = ARENA._promptDisableBtnBounds;
            if (cx >= db.x && cx <= db.x + db.w && cy >= db.y && cy <= db.y + db.h) {
              if (window.RPG && window.RPG.toggleArenaWaveConfirm) {
                if (!ARENA.autoAdvanceWaves) {
                  window.RPG.toggleArenaWaveConfirm();
                } else {
                  confirmNextWave();
                }
                return;
              }
            }
          }
          confirmNextWave();
        }
        return;
      }
      if (ARENA.isBossActive && ARENA._partyBtnBounds) {
        const pb = ARENA._partyBtnBounds;
        if (cx >= pb.x && cx <= pb.x + pb.w && cy >= pb.y && cy <= pb.y + pb.h) {
          window.RPG.toggleBossPartyMode();
          return;
        }
      }
      if (ARENA.blockWindowActive) {
        playerBlock();
        return;
      }
      if (ARENA.qteActive) {
        hitQTE();
        return;
      }
      if (ARENA.waveState === "fighting") {
        if (ARENA.topDownMode || ARENA.isRaidBossBattle) {
          fireTopDownAttack({ cx, cy });
        } else {
          playerSlashAttack();
        }
      }
    }

    function getEventArenaCoords(clientX, clientY) {
      const rect = canvas.getBoundingClientRect();
      const clientW = ARENA.cachedClientW || canvas.clientWidth || (rect.width > 50 ? rect.width : 360);
      const clientH = ARENA.cachedClientH || canvas.clientHeight || (rect.height > 50 ? rect.height : 320);
      const screenX = (clientX - rect.left) * (clientW / (rect.width || clientW));
      const screenY = (clientY - rect.top) * (clientH / (rect.height || clientH));

      if (ARENA.topDownMode || ARENA.isRaidBossBattle) {
        const zoom = Math.min(clientW / 520, clientH / 720);
        const offX = (clientW - 520 * zoom) / 2;
        const offY = (clientH - 720 * zoom) / 2;
        return {
          cx: Math.max(0, Math.min(520, (clientX - rect.left - offX) / zoom)),
          cy: Math.max(0, Math.min(720, (clientY - rect.top - offY) / zoom)),
          screenX,
          screenY
        };
      }
      return {
        cx: (clientX - rect.left) * (ARENA.width / (rect.width || 360)),
        cy: (clientY - rect.top) * (ARENA.height / (rect.height || 320)),
        screenX,
        screenY
      };
    }

    canvas.onclick = (e) => {
      const { cx, cy, screenX, screenY } = getEventArenaCoords(e.clientX, e.clientY);
      handleCanvasTap(cx, cy, screenX, screenY);
    };

    canvas.ontouchstart = (e) => {
      e.preventDefault();
      const touch = e.changedTouches[0];
      const { cx, cy, screenX, screenY } = getEventArenaCoords(touch.clientX, touch.clientY);
      handleCanvasTap(cx, cy, screenX, screenY);
    };

    // Boss arena movement: touchmove for continuous direction
    canvas.ontouchmove = (e) => {
      e.preventDefault();
      // No manual movement in 2D side-scroller anymore!
    };

    canvas.ontouchend = (e) => {
      e.preventDefault();
      if (ARENA.bossArenaMode) {
        const touch = Array.from(e.changedTouches).find(t => t.identifier === ARENA._touchMoveId);
        if (touch) {
          ARENA.moveInput.left = false;
          ARENA.moveInput.right = false;
          ARENA._touchMoveId = null;
        }
      }
    };

    window.onkeyup = (e) => {
      const k = e.key.toLowerCase();
      if (ARENA.keysPressed) {
        delete ARENA.keysPressed[k];
        if (ARENA.topDownMode || ARENA.isRaidBossBattle) {
          let kx = 0, ky = 0;
          if (ARENA.keysPressed["w"] || ARENA.keysPressed["arrowup"]) ky -= 1;
          if (ARENA.keysPressed["s"] || ARENA.keysPressed["arrowdown"]) ky += 1;
          if (ARENA.keysPressed["a"] || ARENA.keysPressed["arrowleft"]) kx -= 1;
          if (ARENA.keysPressed["d"] || ARENA.keysPressed["arrowright"]) kx += 1;
          const kmag = Math.hypot(kx, ky);
          if (kmag > 0) {
            ARENA.joystick.dx = kx / kmag;
            ARENA.joystick.dy = ky / kmag;
            ARENA.player.isMoving = true;
            ARENA.player.facingAngle = Math.atan2(ky, kx);
          } else {
            ARENA.joystick.dx = 0;
            ARENA.joystick.dy = 0;
            ARENA.player.isMoving = false;
          }
        }
      }
      if (!ARENA.bossArenaMode) return;
      if (k === "a" || k === "arrowleft") ARENA.moveInput.left = false;
      if (k === "d" || k === "arrowright") ARENA.moveInput.right = false;
    };

    window.onkeydown = (e) => {
      if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.isContentEditable)) return;
      if (RPG_STATE.activeTab !== "farm" || RPG_STATE.farmMode !== "arena") return;
      const k = e.key.toLowerCase();

      // WASD / Arrow keys for Top-Down free movement
      if (ARENA.topDownMode || ARENA.isRaidBossBattle) {
        if (!ARENA.keysPressed) ARENA.keysPressed = {};
        if (["w", "arrowup", "s", "arrowdown", "a", "arrowleft", "d", "arrowright"].includes(k)) {
          ARENA.keysPressed[k] = true;
          let kx = 0, ky = 0;
          if (ARENA.keysPressed["w"] || ARENA.keysPressed["arrowup"]) ky -= 1;
          if (ARENA.keysPressed["s"] || ARENA.keysPressed["arrowdown"]) ky += 1;
          if (ARENA.keysPressed["a"] || ARENA.keysPressed["arrowleft"]) kx -= 1;
          if (ARENA.keysPressed["d"] || ARENA.keysPressed["arrowright"]) kx += 1;

          const kmag = Math.hypot(kx, ky);
          if (kmag > 0) {
            ARENA.joystick.dx = kx / kmag;
            ARENA.joystick.dy = ky / kmag;
            ARENA.joystick.power = 1.0;
            ARENA.player.isMoving = true;
            ARENA.player.facingAngle = Math.atan2(ky, kx);
          } else {
            ARENA.joystick.dx = 0;
            ARENA.joystick.dy = 0;
            ARENA.player.isMoving = false;
          }
          e.preventDefault();
          return;
        }
        if (k === "shift" || k === "c") {
          playerPerformDashRoll();
          e.preventDefault();
          return;
        }
      }
      // Boss Arena Movement (A/D or Arrows)
      if (ARENA.bossArenaMode) {
        if (k === "a" || k === "arrowleft") { ARENA.moveInput.left = true; e.preventDefault(); return; }
        if (k === "d" || k === "arrowright") { ARENA.moveInput.right = true; e.preventDefault(); return; }
        if (k === "shift" || k === "c") { playerBossArenaDodge(); e.preventDefault(); return; }
      }
      if (k === " " || k === "spacebar" || k === "enter") {
        e.preventDefault();
        if (ARENA.waveState === "prompt") {
          confirmNextWave();
        } else if (ARENA.waveState === "retry_prompt") {
          retryCurrentFloor();
        } else if (ARENA.waveState === "boss_defeat") {
          if (ARENA.currentRaidBoss && ARENA.currentRaidBoss.id) {
            startRaidBossActionBattle(ARENA.currentRaidBoss.id);
          } else {
            exitRaidBossBattle();
          }
        } else if (ARENA.blockWindowActive) {
          playerBlock();
        } else if (ARENA.qteActive) {
          hitQTE();
        } else {
          playerSlashAttack();
        }
      } else if (k === "e") {
        castPlayerSkill1();
      } else if (k === "q") {
        castPlayerUltimate();
      } else if (k === "f") {
        usePlayerPotion();
      } else if (k === "r" || k === "1") {
        useActiveItemAction(0);
      } else if (k === "t" || k === "2") {
        useActiveItemAction(1);
      } else if (k === "shift" || k === "c") {
        playerPerformDash();
      } else if (k === "b") {
        playerBlock();
      }
    };
  }

  function startArenaLoop() {
    stopArenaLoop();
    if (ARENA.startLoopTimeout) {
      cancelAnimationFrame(ARENA.startLoopTimeout);
      clearTimeout(ARENA.startLoopTimeout);
      ARENA.startLoopTimeout = null;
    }
    const canvas = document.getElementById("rpg-action-canvas");
    if (canvas) {
      const r = canvas.getBoundingClientRect();
      const hasSize = (r.width > 50) || (canvas.clientWidth > 50);
      if (!hasSize) {
        // Canvas not laid out yet — retry on next frame
        ARENA.startLoopTimeout = requestAnimationFrame(() => startArenaLoop());
        return;
      }
      const isBossFightActive = !!((ARENA.isRaidBossBattle || ARENA.isBossActive) && ARENA.bossEntity);
      if (!isBossFightActive) {
        initArenaCanvas();
      } else if (!ARENA.ctx || ARENA.canvas !== canvas) {
        bindArenaCanvas(canvas);
      }
    }
    ARENA.running = true;
    function loop() {
      if (!ARENA.running) return;
      try {
        updateArena();
        renderArena();
      } catch (err) {
        console.error("Arena animation frame error:", err);
      }
      if (ARENA.running) {
        ARENA.animId = requestAnimationFrame(loop);
      }
    }
    ARENA.animId = requestAnimationFrame(loop);
  }

  function stopArenaLoop() {
    ARENA.running = false;
    if (ARENA.animId) {
      cancelAnimationFrame(ARENA.animId);
      ARENA.animId = null;
    }
    if (ARENA.startLoopTimeout) {
      cancelAnimationFrame(ARENA.startLoopTimeout);
      clearTimeout(ARENA.startLoopTimeout);
      ARENA.startLoopTimeout = null;
    }
  }

  // ---------------------------------------------------------------------------
  // MAIN GAME LOOP UPDATE
  // ---------------------------------------------------------------------------

