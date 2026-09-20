  function spawnBossCreep() {
    const floor = RPG_STATE.profile?.dungeon_floor || 1;
    
    // Scale identically to creeps but x15 stronger
    const scaleHp = Math.pow(1.18, Math.max(0, floor - 1)) * (1.0 + 19 * 0.05); // wave 20 multiplier
    const scaleAtk = Math.pow(1.15, Math.max(0, floor - 1)) * (1.0 + 19 * 0.04);
    
    // Base creep stats for floor 20 is around 260 HP, 16 ATK. We multiply by 15!
    const baseHp = 260 * 15;
    const baseAtk = 16 * 8; // x8 ATK so it doesn't one-shot instantly but still hurts

    const bossTypes = [
      { id: "golem", name: "Древний Гранитный Голем", icon: "🗿", badgeBg: "#334155", badgeBorder: "#94a3b8" },
      { id: "lich", name: "Архилич Некрополя", icon: "☠️", badgeBg: "#18181b", badgeBorder: "#e4e4e7" },
      { id: "tormentor", name: "Древний Терзатель", icon: "🔮", badgeBg: "#4a044e", badgeBorder: "#c084fc" },
      { id: "dragon", name: "Дракон Инферно", icon: "🌋", badgeBg: "#7c2d12", badgeBorder: "#ea580c" },
      { id: "pudge_boss", name: "Мясник из Чрева", icon: "🪝", badgeBg: "#064e3b", badgeBorder: "#34d399" },
      { id: "faceless_void", name: "Хроно-Владыка", icon: "⏳", badgeBg: "#312e81", badgeBorder: "#818cf8" },
      { id: "roshan", name: "Рошан", icon: "🐲", badgeBg: "#7f1d1d", badgeBorder: "#facc15" }
    ];
    const bt = bossTypes[Math.min(bossTypes.length - 1, Math.max(0, floor - 1))];

    const stats = RPG_STATE.profile?.stats || {};
    const playerAtk = Math.max(30, Math.floor(((stats.min_atk || 30) + (stats.max_atk || 50)) / 2));
    const playerHp = Math.max(400, stats.hp_max || 400);

    const calculatedHp = Math.floor(baseHp * scaleHp);
    const calculatedAtk = Math.floor(baseAtk * scaleAtk);
    const calculatedDef = Math.floor(35 * Math.pow(1.10, Math.max(0, floor - 1)));

    const boss = {
      name: bt.name + (floor > 1 ? ` [Этаж ${floor}]` : ""),
      icon: bt.icon,
      team: "boss",
      badgeBg: bt.badgeBg,
      badgeBorder: bt.badgeBorder,
      x: (ARENA.width || 360) / 2,
      y: 95,
      radius: 30, // Scaled down for comfortable arena space
      speed: 0.65, // Active, menacing movement speed
      hp: calculatedHp,
      maxHp: calculatedHp,
      atk: calculatedAtk,
      defense: calculatedDef,
      isBoss: true,
      isMinion: false,
      shielded: false,
      attackCooldown: 0,
      state: "chase",
      stateTimer: 0,
      meleeCooldown: 60,
      chargeCooldown: 220,
      barrageCooldown: 140,
      chargeAngle: 0,
      chargeVx: 0,
      chargeVy: 0,
      facing: 1,
      enrageTimer: 0,
      battleStartTime: Date.now(),
      enrageStage: "normal",
      poise: 800,
      maxPoise: 800,
      isStaggered: false,
      staggerTimer: 0,
      bossType: (bt.name.toLowerCase().includes("терзатель") || bt.name.toLowerCase().includes("tormentor")) ? "tormentor" :
                (bt.name.toLowerCase().includes("лич") || bt.name.toLowerCase().includes("archlich")) ? "lich" :
                (bt.name.toLowerCase().includes("дракон") || bt.name.toLowerCase().includes("dragon")) ? "dragon" : "roshan"
    };

    ARENA.bossEntity = boss;
    ARENA.isBossActive = true;
    ARENA.bossPhase = 1;
    ARENA.topDownMode = true;
    ARENA.bossArenaMode = true;
    ARENA.width = 520;
    ARENA.height = 720;
    boss.x = 260;
    boss.y = 140;
    boss.radius = 32;
    ARENA.player.x = 260;
    ARENA.player.y = 620;
    ARENA.player.isMoving = false;
    ARENA.dashGhosts = [];

    ARENA.bossSpecialTimer = 0;
    ARENA.bossProjectiles = [];
    ARENA.creeps = [boss];

    if ((ARENA.bossPartyMode || "trio") === "trio") {
      initBossCompanions();
    }

    // Force full render of DOM to expand canvas to h-[520px] and activate boss controls
    RPG_STATE._forceFullRender = true;
    renderRoot();
    RPG_STATE._forceFullRender = false;

    const canvas = document.getElementById("rpg-action-canvas");
    if (canvas) {
      bindArenaCanvas(canvas);
      ARENA.width = 520;
      ARENA.height = 720;
      boss.x = 260;
      boss.y = 140;
      ARENA.player.x = 260;
      ARENA.player.y = 620;
    }
  }

  // ---------------------------------------------------------------------------
  // PLAYER ATTACK (MELEE & RANGED)
  // ---------------------------------------------------------------------------

  function fireTopDownAttack(targetPoint) {
    const p = ARENA.player;
    if (ARENA.waveState !== "fighting") return;
    if (p.shootCooldown && p.shootCooldown > 0) return;
    const stats = RPG_STATE.profile?.stats || {};
    const boss = (ARENA.bossEntity && ARENA.bossEntity.hp > 0) ? ARENA.bossEntity : (ARENA.creeps.find(c => c.hp > 0) || null);

    let fireAngle = p.facingAngle !== undefined ? p.facingAngle : -Math.PI / 2;
    let explicitTarget = boss;

    if (targetPoint && targetPoint.cx !== undefined) {
      fireAngle = Math.atan2(targetPoint.cy - p.y, targetPoint.cx - p.x);
      if (boss) {
        const toBoss = Math.atan2(boss.y - p.y, boss.x - p.x);
        let diff = Math.abs(toBoss - fireAngle);
        while (diff > Math.PI) diff = Math.PI * 2 - diff;
        if (diff < 1.1) explicitTarget = boss;
      }
    } else if (boss) {
      fireAngle = Math.atan2(boss.y - p.y, boss.x - p.x);
      explicitTarget = boss;
    }

    p.facingAngle = fireAngle;
    p.facing = Math.cos(fireAngle) >= 0 ? 1 : -1;

    const isCrit = Math.random() * 100 < (stats.crit_chance || 15);
    let baseDmg = Math.floor(((stats.min_atk || 25) + (stats.max_atk || 35)) * 0.7);
    if (p.donkeyBuffTimer && p.donkeyBuffTimer > 0) baseDmg = Math.floor(baseDmg * 1.35);
    const finalDmg = isCrit ? Math.floor(baseDmg * 2.2) : baseDmg;

    if (!ARENA.playerProjectiles) ARENA.playerProjectiles = [];
    ARENA.playerProjectiles.push({
      x: p.x + Math.cos(fireAngle) * 14,
      y: p.y + Math.sin(fireAngle) * 14,
      vx: Math.cos(fireAngle) * 10.5,
      vy: Math.sin(fireAngle) * 10.5,
      speed: 10.5,
      target: explicitTarget,
      dmg: finalDmg,
      type: "topdown_shot",
      isCrit: isCrit,
      radius: 6.5,
      color: isCrit ? "#f59e0b" : "#38bdf8",
      distTraveled: 0,
      maxDist: 850
    });

    const atkSpeed = Math.max(0.5, stats.attack_speed || 1.0);
    p.shootCooldown = Math.max(5, Math.round(60 / atkSpeed));
    triggerHaptic(isCrit ? "medium" : "light");
  }

  let _lastSlashAttackTime = 0;
  function playerSlashAttack() {
    const now = Date.now();
    if (now - _lastSlashAttackTime < 50) return;
    _lastSlashAttackTime = now;

    const p = ARENA.player;
    if (ARENA.topDownMode || ARENA.isRaidBossBattle) {
      fireTopDownAttack(null);
      return;
    }
    if (p.attackCooldown > 0) {
      if (p.attackCooldown <= 8) {
        p.attackQueued = true;
      }
      return;
    }
    const stats = RPG_STATE.profile?.stats || {};

    // 3-HIT COMBO CHAIN (Light 1 -> Light 2 -> Heavy Finisher)
    if (!ARENA.combo) ARENA.combo = { count: 0, timer: 0, step: 0, maxCombo: 0 };
    if (ARENA.combo.timer > 0) {
      ARENA.combo.step = (ARENA.combo.step + 1) % 3;
    } else {
      ARENA.combo.step = 0;
    }
    ARENA.combo.count++;
    ARENA.combo.timer = 135; // ~2.25s generous combo window for comfortable manual chaining
    ARENA.combo.maxCombo = Math.max(ARENA.combo.maxCombo, ARENA.combo.count);

    let stepMult = 2.4;
    let cdFrames = 38;
    let isHeavyFinisher = false;

    // Slower, tactile and weighty attack rate: ~1.2 to 1.6 attacks/sec (humanly clickable and readable)
    if (ARENA.combo.step === 0) {
      stepMult = 2.4;
      cdFrames = 38; // ~0.63s at 60 FPS (~1.58 atk/sec)
      addStylePoints(30, "LIGHT 1");
    } else if (ARENA.combo.step === 1) {
      stepMult = 3.2;
      cdFrames = 40; // ~0.67s at 60 FPS (~1.50 atk/sec)
      addStylePoints(55, "LIGHT 2");
    } else {
      stepMult = 5.8;
      cdFrames = 58; // ~0.97s at 60 FPS (~1.03 atk/sec heavy smash)
      isHeavyFinisher = true;
      addStylePoints(145, "HEAVY FINISHER");
    }

    let speedRate = Math.max(0.7, stats.attack_speed || 1.0);
    if (p.bladeDanceActive > 0) speedRate *= 1.5; // +50% attack speed buff

    // Attack speed formula directly scaled by stats.attack_speed
    p.attackCooldown = Math.max(8, Math.round(cdFrames / speedRate));
    triggerHaptic(isHeavyFinisher ? "heavy" : "medium");

    let isCrit = Math.random() * 100 < (stats.crit_chance || 15);
    if (p.critBuff) {
      isCrit = true;
      p.critBuff = false;
    }

    let baseDmg = Math.floor((stats.min_atk || 20) + Math.random() * ((stats.max_atk || 30) - (stats.min_atk || 20)));
    let dmg = Math.floor(baseDmg * stepMult);
    if (p.donkeyBuffTimer && p.donkeyBuffTimer > 0) dmg = Math.floor(dmg * 1.35);

    // PA PERK: Mega Coup (20% chance for x10 mega crit)
    if (isCrit) {
      if (window.hasTalentPerk && window.hasTalentPerk("perk_mega_coup") && Math.random() < 0.20) {
        dmg = Math.floor(dmg * 10.0);
        spawnFloatingText(p.x, p.y - 45, "💥 СВЕРХКРИТ x10!", "#dc2626");
        triggerHaptic("heavy");
      } else {
        dmg = Math.floor(dmg * 2.2);
      }
      // WK PERK: Vampiric Crit (Critical hits restore 100% of damage dealt)
      if (window.hasTalentPerk && window.hasTalentPerk("perk_vampiric_crit")) {
        const vampAmt = Math.min((p.maxHp || 500) - (p.currentHp || 0), dmg);
        if (vampAmt > 0) {
          p.currentHp = Math.min(p.maxHp || 500, (p.currentHp || 0) + vampAmt);
          spawnFloatingText(p.x, p.y - 30, `💚 +${vampAmt} (ВАМПИРИЗМ)`, "#22c55e");
        }
      }
    }

    // PUDGE PERK: Flesh Dismember (Every 4th attack deal x2 dmg + stun target)
    let isPudgeDismember = false;
    if (window.hasTalentPerk && window.hasTalentPerk("perk_flesh_dismember")) {
      ARENA.pudgeHitCounter = (ARENA.pudgeHitCounter || 0) + 1;
      if (ARENA.pudgeHitCounter >= 4) {
        ARENA.pudgeHitCounter = 0;
        isPudgeDismember = true;
        dmg = Math.floor(dmg * 2.0);
        spawnFloatingText(p.x, p.y - 35, "🥩 РАСЧЛЕНЕНИЕ x2!", "#ef4444");
      }
    }

    // SF PERK: Necromastery Soul Stacks (+3% damage per soul, up to 15 stacks)
    if (window.hasTalentPerk && window.hasTalentPerk("perk_necromastery_stacks") && (ARENA.sfSouls || 0) > 0) {
      dmg = Math.floor(dmg * (1.0 + ARENA.sfSouls * 0.03));
    }

    // ANTI-MAGE PERK: Mana Burn (+15% damage + target attack debuff)
    let isManaBurn = false;
    if (window.hasTalentPerk && window.hasTalentPerk("perk_mana_burn")) {
      isManaBurn = true;
      dmg = Math.floor(dmg * 1.15);
    }

    // RANGED HERO (Invoker, Shadow Fiend) — fires flying magic orb projectile
    if (p.isRanged) {
      const hClass = (RPG_STATE.profile?.hero_class || "").toLowerCase();
      const isMage = hClass === "invoker" || hClass === "mage";
      const orbCol = hClass === "shadow_fiend" ? "#c084fc" : "#38bdf8";

      // Mana empowerment for basic attacks: higher mana grants bonus magic damage!
      const spellAmpPct = (stats.spell_amp !== undefined ? stats.spell_amp : ((p.maxMp || 100) * 0.2));
      const manaMultiplier = 1.0 + ((spellAmpPct / 100) * (isMage ? 0.6 : 0.25));
      const orbDmg = Math.floor(dmg * manaMultiplier);

      ARENA.playerProjectiles.push({
        type: "magic_orb",
        x: p.x + 20,
        y: p.y - 4,
        speed: 8.8,
        dmg: orbDmg,
        isCrit: isCrit,
        isHeavy: isHeavyFinisher,
        color: orbCol,
        isMagic: true, // Tags basic attack as MAGIC DAMAGE!
        isMage: isMage
      });

      p.slashAnimation = { radius: 35, timer: 14, isMagic: true, step: ARENA.combo.step };
      return;
    }

    // MELEE HERO (Pudge, Juggernaut, PA, WK, AM) — cleave attack + wind blade wave!
    p.slashAnimation = {
      radius: isHeavyFinisher ? 85 : 65,
      timer: isHeavyFinisher ? 22 : 15,
      isMagic: false,
      step: ARENA.combo.step
    };

    if (isHeavyFinisher) {
      ARENA.cameraTrauma = Math.min(1.0, ARENA.cameraTrauma + 0.25);
    }

    // Unleash Crescent Wind Blade Projectile in player facing direction
    const pFacing = (p.facing !== undefined) ? p.facing : 1;
    if (!ARENA.playerProjectiles) ARENA.playerProjectiles = [];
    ARENA.playerProjectiles.push({
      type: "wind_blade",
      x: p.x + pFacing * 35,
      y: p.y - 6,
      speed: 10.0 * pFacing,
      dmg: Math.floor(dmg * 0.9),
      isCrit: isCrit,
      isHeavy: isHeavyFinisher,
      color: isHeavyFinisher ? "#f59e0b" : "#facc15",
      radius: isHeavyFinisher ? 28 : 20,
      hitCreepIds: new Set()
    });

    // Check direct melee hit against all creeps (direction-aware + close-quarters 360 body check)
    for (const c of ARENA.creeps) {
      // In Top-Down / Boss Fight mode, melee hit MUST be within true 2D distance!
      if (ARENA.topDownMode || ARENA.isRaidBossBattle) {
        const dist2d = Math.hypot(c.x - p.x, c.y - p.y);
        if (dist2d > (p.radius + c.radius + (isHeavyFinisher ? 50 : 32))) {
          continue; // Too far away in 2D top-down arena!
        }
      } else {
        const dx = c.x - p.x;
        const inFront = (pFacing === 1 && dx > -20 && dx < (p.attackRange + (isHeavyFinisher ? 40 : 15))) ||
                       (pFacing === -1 && dx < 20 && -dx < (p.attackRange + (isHeavyFinisher ? 40 : 15))) ||
                       (Math.abs(dx) < 45);
        if (!inFront) continue;
      }
      if (true) {
        let finalDmg = dmg;

        // Shielded Defender Guard Break Mechanics
        if (c.archetype === "defender") {
          c.shieldHits = (c.shieldHits || 0) + 1;
          if (c.shieldBrokenTimer <= 0) {
            if (isHeavyFinisher || c.shieldHits >= 3) {
              c.shieldBrokenTimer = 240;
              c.state = "stagger";
              c.staggerTimer = 80;
              c.stateTimer = 80;
              c.x += 35;
              ARENA.hitstop = 10;
              ARENA.cameraTrauma = Math.min(1.0, ARENA.cameraTrauma + 0.35);
              spawnFloatingText(c.x, c.y - 25, "💥 GUARD BREAK! (+100% УРОНА)", "#facc15");
              addStylePoints(160, "GUARD BREAK");
              triggerHaptic("heavy");
              finalDmg = Math.floor(finalDmg * 1.5);
            } else {
              finalDmg = Math.max(8, Math.floor(finalDmg * 0.5));
              spawnFloatingText(c.x, c.y - 20, `🛡️ БЛОК (-50%) [${3 - c.shieldHits} уд.]`, "#94a3b8");
              triggerHaptic("light");
            }
          }
        }

        // Check Item Passives: Desolator, Skadi, Battle Fury
        const eq = RPG_STATE.profile?.equipment || {};
        const hasBF = Object.values(eq).some(it => it && (it.name?.includes("Battle Fury") || it.name?.includes("Боевой Топор") || it.bonus?.cleave));
        const hasDeso = Object.values(eq).some(it => it && (it.name?.includes("Desolator") || it.name?.includes("Опустошитель") || it.bonus?.minus_armor));
        const hasSkadi = Object.values(eq).some(it => it && (it.name?.includes("Skadi") || it.name?.includes("Скади") || it.bonus?.frost_slow));

        if (hasDeso) {
          finalDmg = Math.floor(finalDmg * 1.24);
          if (!c.desoDebuff) {
            c.desoDebuff = 300;
            spawnFloatingText(c.x, c.y - 32, "🩸 -8 БРОНИ", "#dc2626");
          }
        }
        if (hasSkadi) {
          c.speed = Math.max(0.3, (c.speed || 0.8) * 0.55);
          spawnFloatingText(c.x, c.y - 32, "❄️ СКАДИ", "#38bdf8");
        }
        if (hasBF) {
          const cleaveDmg = Math.floor(finalDmg * 0.65);
          for (const other of ARENA.creeps) {
            if (other !== c && Math.abs(other.x - c.x) < 95) {
              safeDamageCreep(other, cleaveDmg, false);
              spawnFloatingText(other.x, other.y - 20, `🪓 КЛИВ -${cleaveDmg}`, "#f97316");
            }
          }
        }

        if (c.isBoss) {
          if (c.tormentorShield) {
            const reflectDmg = Math.max(5, Math.floor(finalDmg * 0.5));
            p.currentHp = Math.max(0, p.currentHp - reflectDmg);
            spawnFloatingText(p.x, p.y - 25, `🪞 ОТРАЖЕНИЕ -${reflectDmg}!`, "#c084fc");
            if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
          }
          if (c.isStaggered) {
            finalDmg = Math.floor(finalDmg * 2.5);
          } else {
            const poiseDmg = isCrit ? 28 : (isHeavyFinisher ? 35 : 14);
            c.poise = Math.max(0, (c.poise !== undefined ? c.poise : 300) - poiseDmg);
            if (c.poise <= 0) {
              c.isStaggered = true;
              c.staggerTimer = 210;
              ARENA.cameraTrauma = 0.7;
              ARENA.hitstop = 10;
              spawnFloatingText(c.x, c.y - 35, "💫 ОШЕЛОМЛЕН! (+150% УРОНА)", "#facc15");
              triggerHaptic("heavy");
            }
          }
          const bDef = c.defense || 14;
          const dr = (bDef * 0.05) / (1 + bDef * 0.05);
          finalDmg = Math.max(8, Math.floor(finalDmg * (1 - dr)));
          finalDmg = applyDamageToBoss(c, finalDmg, isCrit);
        } else {
          if (isHeavyFinisher && c.archetype !== "defender") {
            c.x += 30;
          }
          safeDamageCreep(c, finalDmg, false);
        }

        if (isPudgeDismember) {
          c.stunTimer = 72;
          spawnFloatingText(c.x, c.y - 35, "🥩 ОГЛУШЕНИЕ!", "#ef4444");
        }
        if (isManaBurn) {
          c.atkDebuffTimer = 180;
          c.atkDebuff = 0.15;
          spawnFloatingText(c.x, c.y - 25, "⚡ ВЫЖИГАНИЕ!", "#38bdf8");
        }

        // Lifesteal on creeps (boss lifesteal is handled safely in applyDamageToBoss)
        if (!c.isBoss && stats.lifesteal > 0) {
          const pMax = p.maxHp || 500;
          const rawHeal = Math.floor(finalDmg * (stats.lifesteal / 100));
          const heal = Math.max(1, Math.min(Math.floor(pMax * 0.05), 5000, rawHeal));
          p.currentHp = Math.min(pMax, p.currentHp + heal);
        }

        const col = (c.isBoss && c.isStaggered) ? "#fbbf24" : (isCrit ? "#facc15" : (isHeavyFinisher ? "#f97316" : "#f87171"));
        const prefix = isHeavyFinisher ? "💥 СЛЭМ! " : (isCrit ? "⚡ КРИТ! " : "");
        const txt = (c.isBoss && c.isStaggered) ? `💥 STAGGER! -${finalDmg}` : `${prefix}-${finalDmg}`;
        spawnFloatingText(c.x, c.y - 15 - Math.random() * 10, txt, col);
      }
    }
  }

  // ---------------------------------------------------------------------------
  // SKILL 1 (SPECIFIC FOR EACH DOTA HERO)
  // ---------------------------------------------------------------------------

  function castPlayerSkill1() {
    const p = ARENA.player;
    const stats = RPG_STATE.profile?.stats || {};
    const skillCfg = getHeroSkillConfig();
    const hClass = (RPG_STATE.profile?.hero_class || "pudge").toLowerCase();
    let cost = 20;
    if (p.croakTimer > 0) {
      cost = Math.floor(cost * 0.4); // 3-й скилл Ларго: -60% расхода маны!
    }

    if (p.isFrozenInTime || (p.stunTimer && p.stunTimer > 0)) {
      spawnFloatingText(p.x, p.y - 25, "💫 ОГЛУШЕНИЕ!", "#facc15");
      triggerHaptic("error");
      return;
    }
    if ((p.silenceTimer && p.silenceTimer > 0) || (p.doomDebuffTimer && p.doomDebuffTimer > 0)) {
      spawnFloatingText(p.x, p.y - 25, "🔇 БЕЗМОЛВИЕ (СКИЛЛЫ ЗАБЛОКИРОВАНЫ)!", "#c084fc");
      triggerHaptic("error");
      return;
    }

    if (ARENA.skill1Cooldown > 0) {
      const sec = Math.ceil(ARENA.skill1Cooldown / 60);
      spawnFloatingText(p.x, p.y - 25, `${skillCfg.skill1Name}: КД ${sec}с`, "#94a3b8");
      triggerHaptic("error");
      return;
    }
    if (p.currentMp < cost) {
      spawnFloatingText(p.x, p.y - 25, `Мало маны (нужно ${cost} MP)!`, "#94a3b8");
      triggerHaptic("error");
      return;
    }

    p.currentMp -= cost;
    const cdReduct1 = 1.0 - ((RPG_STATE.profile?.talents?.cooldown || 0) * 0.06);
    ARENA.skill1Cooldown = Math.floor(skillCfg.skill1Cd * cdReduct1);
    triggerHaptic("heavy");

    // TOP-DOWN 360° BOSS TARGETING FOR ALL SKILLS
    if (ARENA.topDownMode || ARENA.isRaidBossBattle) {
      const boss = ARENA.bossEntity;
      if (boss && boss.hp > 0) {
        const toBossAngle = Math.atan2(boss.y - p.y, boss.x - p.x);

        if (hClass === "invoker") {
          // Sunstrike: drops blazing solar burst directly on boss!
          ARENA.specialEffects.push({ type: "sunstrike", x: boss.x, y: boss.y, radius: 90, timer: 36, maxTimer: 36 });
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 3.8));
          spawnFloatingText(boss.x, boss.y - 35, `☀️ САНСТРАЙК! -${dmg}`, "#facc15");
          ARENA.cameraTrauma = 0.5;
          return;
        } else if (hClass === "phantom_assassin") {
          // Stifling Dagger: spinning shadowy dagger flies at boss with neon critical sparks!
          const dmg = Math.floor((stats.max_atk || 30) * 3.4);
          ARENA.specialEffects.push({
            type: "dagger_throw",
            fromX: p.x,
            fromY: p.y,
            toX: boss.x,
            toY: boss.y,
            x: p.x,
            y: p.y,
            angle: toBossAngle,
            timer: 20,
            maxTimer: 20,
            dmg: dmg
          });
          const actualDmg = applyDamageToBoss(boss, dmg, true);
          spawnFloatingText(boss.x, boss.y - 30, `🗡️ КИНЖАЛ ТЕНИ! -${actualDmg}`, "#f43f5e");
          ARENA.cameraTrauma = 0.35;
          return;
        } else if (hClass === "shadow_fiend") {
          // Triple Shadowraze: 3 erupting dark soul pillars erupt along line towards boss!
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 2.6));
          for (let r = 1; r <= 3; r++) {
            const rx = p.x + Math.cos(toBossAngle) * (r * 68);
            const ry = p.y + Math.sin(toBossAngle) * (r * 68);
            ARENA.specialEffects.push({ type: "shadowraze", x: rx, y: ry, radius: 46, timer: 32, maxTimer: 32 });
          }
          spawnFloatingText(boss.x, boss.y - 30, `🌑 КОЙЛЫ ТЕМНОТЫ! -${dmg}`, "#c084fc");
          ARENA.cameraTrauma = 0.45;
          return;
        } else if (hClass === "pudge") {
          // Meat Hook: iron chain with sharp hook shoots directly at boss!
          p.fleshHeapActive = 480;
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 2.8));
          ARENA.specialEffects.push({
            type: "meat_hook",
            fromX: p.x,
            fromY: p.y,
            toX: boss.x,
            toY: boss.y,
            timer: 24,
            maxTimer: 24,
            dmg: dmg
          });
          spawnFloatingText(boss.x, boss.y - 30, `🥩 МЯСНОЙ КРЮК! -${dmg}`, "#ef4444");
          ARENA.cameraTrauma = 0.5;
          return;
        } else if (hClass === "juggernaut") {
          // Blade Fury: swirling golden whirlwind vortex around Juggernaut!
          p.bladeDanceActive = 360;
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 3.0));
          ARENA.specialEffects.push({
            type: "blade_fury",
            x: p.x,
            y: p.y,
            radius: 52,
            timer: 45,
            maxTimer: 45,
            dmg: dmg
          });
          spawnFloatingText(boss.x, boss.y - 30, `💨 ВИХРЬ КЛИНКОВ! -${dmg}`, "#f59e0b");
          ARENA.cameraTrauma = 0.4;
          return;
        } else if (hClass === "wraith_king") {
          // Wraithfire Blast: flaming green ghost skull missile screaming at boss!
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 2.8));
          boss.poise = Math.max(0, (boss.poise || 400) - 80);
          ARENA.specialEffects.push({
            type: "wraithfire",
            fromX: p.x,
            fromY: p.y,
            toX: boss.x,
            toY: boss.y,
            timer: 26,
            maxTimer: 26,
            dmg: dmg
          });
          spawnFloatingText(boss.x, boss.y - 30, `💀 ПРИЗРАЧНЫЙ СТАН! -${dmg}`, "#10b981");
          ARENA.cameraTrauma = 0.45;
          return;
        } else if (hClass === "anti_mage") {
          // Blink Strike: poof at origin, instant dash, and dual mana slash behind boss!
          ARENA.specialEffects.push({ type: "blink_poof", x: p.x, y: p.y, timer: 18, maxTimer: 18 });
          p.x = Math.max(40, Math.min(480, boss.x - Math.cos(toBossAngle) * 50));
          p.y = Math.max(50, Math.min(670, boss.y - Math.sin(toBossAngle) * 50));
          p.counterspellActive = 240;
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 3.2));
          ARENA.specialEffects.push({ type: "mana_slash", x: boss.x, y: boss.y, timer: 24, maxTimer: 24, dmg: dmg });
          spawnFloatingText(boss.x, boss.y - 30, `⚡ ВЫПАД ИЗ ТЕНИ! -${dmg}`, "#38bdf8");
          ARENA.cameraTrauma = 0.5;
          return;
        } else if (hClass === "leshrac") {
          // Croak of Genius (3-й скилл Ларго): -60% расхода маны + эхо-урон + восстановление маны
          p.croakTimer = 480; // 8 sec
          p.currentMp = Math.min(p.maxMp, p.currentMp + 45);
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 3.4));
          boss.stunTimer = Math.max(boss.stunTimer || 0, 60); // 1.0s ministun
          ARENA.specialEffects.push({
            type: "croak_blast",
            x: boss.x,
            y: boss.y,
            radius: 85,
            timer: 30,
            maxTimer: 30,
            color: "#a855f7"
          });
          ARENA.cameraTrauma = 0.5;
          spawnFloatingText(p.x, p.y - 35, "🎵 КВАКАНЬЕ ГЕНИЯ! (+45 MP, ЭХО)", "#c084fc");
          spawnFloatingText(boss.x, boss.y - 30, `🎶 РЕХО-УРОН! -${dmg}`, "#facc15");
          return;
        }
      }
    }

    // 1. INVOKER: Sun Strike (Солнечный луч с неба с чистым уроном)
    if (hClass === "invoker") {
      let targetX = ARENA.width * 0.54;
      if (ARENA.creeps.length > 0) {
        let maxHpCreep = ARENA.creeps[0];
        for (const c of ARENA.creeps) {
          if (c.hp > maxHpCreep.hp) maxHpCreep = c;
        }
        targetX = maxHpCreep.x;
      }

      const strikeY = ARENA.roadY - 12;
      const radius = 110;
      const spellAmpPct = (stats.spell_amp !== undefined ? stats.spell_amp : ((p.maxMp || 100) * 0.2));
      const manaBonus = 1.0 + (spellAmpPct / 100) + (p.currentMp ? (p.currentMp / p.maxMp) * 0.25 : 0);
      const dmg = Math.floor((stats.max_atk || 30) * 3.6 * manaBonus);

      ARENA.specialEffects.push({
        type: "sunstrike",
        x: targetX,
        y: strikeY,
        radius: radius,
        timer: 42,
        maxTimer: 42
      });
      ARENA.cameraTrauma = Math.min(1.0, ARENA.cameraTrauma + 0.35);
      ARENA.hitstop = 4;
      spawnFloatingText(targetX, strikeY - 48, "☀️ САНСТРАЙК! (ЧИСТЫЙ УРОН)", "#facc15");

      for (const c of ARENA.creeps) {
        if (Math.abs(c.x - targetX) < radius) {
          if (c.archetype === "defender") {
            c.shieldBrokenTimer = 240;
            c.state = "stagger";
            c.staggerTimer = 85;
            c.stateTimer = 85;
            spawnFloatingText(c.x, c.y - 25, "💥 GUARD BREAK САНСТРАЙКОМ!", "#facc15");
          }
          safeDamageCreep(c, dmg, false);
          c.attackCooldown = -60; // stunned by intense solar burst
          spawnFloatingText(c.x, c.y - 20, `☀️ -${dmg} ЧИСТЫЙ!`, "#facc15");
        }
      }
      return;
    }

    // 2. PUDGE: Flesh Heap (-40% damage for 8 sec)
    if (hClass === "pudge") {
      p.fleshHeapActive = 480; // 8 sec
      spawnFloatingText(p.x + 20, p.y - 35, "🥩 ЗАЩИТНАЯ ПЛОТЬ (-40% урона)!", "#ef4444");
      return;
    }

    // 3. JUGGERNAUT: Blade Dance (+50% attack speed for 6 sec)
    if (hClass === "juggernaut") {
      p.bladeDanceActive = 360; // 6 sec
      spawnFloatingText(p.x + 20, p.y - 35, "💨 ТАНЕЦ КЛИНКА (+50% ск. атаки)!", "#f59e0b");
      return;
    }

    // 4. PHANTOM ASSASSIN: Stifling Dagger
    if (hClass === "phantom_assassin") {
      let target = null;
      let maxDist = 0;
      for (const c of ARENA.creeps) {
        if (c.x > maxDist) { maxDist = c.x; target = c; }
      }
      const daggerDmg = Math.floor((stats.max_atk || 30) * 3.2);
      ARENA.playerProjectiles.push({
        type: "dagger",
        x: p.x + 25,
        y: p.y - 5,
        speed: 12,
        dmg: daggerDmg,
        isCrit: true,
        slow: true,
        icon: "🗡️",
        color: "#f43f5e"
      });
      spawnFloatingText(p.x + 20, p.y - 35, "🗡️ КИНЖАЛ ТЕНИ!", "#f43f5e");
      return;
    }

    // 5. SHADOW FIEND: Triple Shadowraze
    if (hClass === "shadow_fiend") {
      const razes = [p.x + 90, p.x + 180, p.x + 270];
      const dmg = Math.floor((stats.max_atk || 30) * 2.2);
      for (const rx of razes) {
        ARENA.specialEffects.push({ type: "shadowraze", x: rx, y: ARENA.roadY - 15, radius: 50, timer: 30 });
        for (const c of ARENA.creeps) {
          if (Math.abs(c.x - rx) < 55) {
            safeDamageCreep(c, dmg, false);
            spawnFloatingText(c.x, c.y - 20, `🌑 -${dmg}`, "#c084fc");
          }
        }
      }
      spawnFloatingText(p.x + 30, p.y - 40, "🌑 ТРОЙНОЙ КОЙЛ!", "#a855f7");
      return;
    }

    // 6. WRAITH KING: Wraithfire Blast
    if (hClass === "wraith_king") {
      const dmg = Math.floor((stats.max_atk || 30) * 2.4);
      ARENA.playerProjectiles.push({
        type: "dagger",
        x: p.x + 25,
        y: p.y - 5,
        speed: 9,
        dmg: dmg,
        isCrit: false,
        slow: true,
        icon: "💀",
        color: "#10b981"
      });
      spawnFloatingText(p.x + 20, p.y - 35, "💀 ПРИЗРАЧНЫЙ СТАН!", "#10b981");
      return;
    }

    // 7. ANTI-MAGE: Counterspell Shield
    if (hClass === "anti_mage") {
      p.counterspellActive = 240; // 4 sec
      spawnFloatingText(p.x + 20, p.y - 35, "🛡️ ЩИТ МАГИИ!", "#38bdf8");
      // Blink strike nearest creep
      if (ARENA.creeps.length > 0) {
        const c = ARENA.creeps[0];
        const dmg = Math.floor((stats.max_atk || 30) * 2.5);
        safeDamageCreep(c, dmg, false);
        spawnFloatingText(c.x, c.y - 20, `⚡ ВЫПАД! -${dmg}`, "#a855f7");
      }
      return;
    }

    // 8. LARGO: Diabolic Edict (Магическое эхо)
    if (hClass === "leshrac") {
      p.edictTimer = 180; // 3 sec (60 fps * 3)
      p.edictDmgMult = 0.55;
      
      ARENA.specialEffects.push({
        type: "edict_aura",
        x: p.x,
        y: p.y,
        radius: 200,
        timer: 180,
        maxTimer: 180,
        color: "#c084fc"
      });
      ARENA.cameraTrauma = Math.min(1.0, ARENA.cameraTrauma + 0.3);
      spawnFloatingText(p.x, p.y - 35, "🎵 МАГИЧЕСКОЕ ЭХО!", "#c084fc");


      for (const c of ARENA.creeps) {
        if (Math.abs(c.x - targetX) < radius) {
          if (c.archetype === "defender") {
            c.shieldBrokenTimer = 240;
            c.state = "stagger";
            c.staggerTimer = 90;
            c.stateTimer = 90;
          }
          safeDamageCreep(c, dmg, false);
          c.attackCooldown = -60; // 1s ministun
          spawnFloatingText(c.x, c.y - 20, `🎶 -${dmg} РЕХО!`, "#facc15");
        }
      }
      return;
    }
  }

  // ---------------------------------------------------------------------------
  // ULTIMATE ABILITY (SPECIFIC FOR EACH DOTA HERO)
  // ---------------------------------------------------------------------------

  function castPlayerUltimate() {
    const p = ARENA.player;
    const stats = RPG_STATE.profile?.stats || {};
    const skillCfg = getHeroSkillConfig();
    const hClass = (RPG_STATE.profile?.hero_class || "pudge").toLowerCase();
    let cost = 35;
    if (p.croakTimer > 0) {
      cost = Math.floor(cost * 0.4); // 3-й скилл Ларго: -60% расхода маны!
    }

    if (p.isFrozenInTime || (p.stunTimer && p.stunTimer > 0)) {
      spawnFloatingText(p.x, p.y - 25, "💫 ОГЛУШЕНИЕ!", "#facc15");
      triggerHaptic("error");
      return;
    }
    if ((p.silenceTimer && p.silenceTimer > 0) || (p.doomDebuffTimer && p.doomDebuffTimer > 0)) {
      spawnFloatingText(p.x, p.y - 25, "🔇 БЕЗМОЛВИЕ (УЛЬТА ЗАБЛОКИРОВАНА)!", "#c084fc");
      triggerHaptic("error");
      return;
    }

    // LARGO TOGGLE ULTIMATE: AMPHIBIAN RHAPSODY (ВКЛ / ВЫКЛ)
    if (hClass === "leshrac") {
      if (p.largoRhapsodyActive) {
        // Выключение ульты
        p.largoRhapsodyActive = false;
        ARENA.ultCooldown = 30; // 0.5с защита от двойного клика
        spawnFloatingText(p.x, p.y - 35, "🛑 РАПСОДИЯ ВЫКЛЮЧЕНА", "#94a3b8");
        triggerHaptic("light");
        const ultEl = document.getElementById("rpg-cd-ult");
        if (ultEl) ultEl.textContent = "ВКЛ";
        return;
      } else {
        // Включение ульты
        if (ARENA.ultCooldown > 0) {
          const sec = Math.ceil(ARENA.ultCooldown / 60);
          spawnFloatingText(p.x, p.y - 25, `КД ${sec}с`, "#94a3b8");
          triggerHaptic("error");
          return;
        }
        let tickMpCost = 5;
        if (p.croakTimer > 0) tickMpCost = Math.floor(tickMpCost * 0.4);
        if (p.currentMp < tickMpCost) {
          spawnFloatingText(p.x, p.y - 25, `Мало маны (нужно ${tickMpCost} MP)!`, "#94a3b8");
          triggerHaptic("error");
          return;
        }

        p.largoRhapsodyActive = true;
        p.largoRhapsodyTickTimer = 30; // 0.5 сек между тактами
        p.largoRhapsodyDmgMult = 1.0 + ((stats.ult_boost || 0) / 100.0);
        ARENA.ultCooldown = 30; // 0.5с перезарядка на переключение

        // Мгновенный первый такт при включении
        p.currentMp -= tickMpCost;
        spawnFloatingText(p.x, p.y - 48, `⚡ -${tickMpCost} MP`, "#38bdf8");

        const ultMult = p.largoRhapsodyDmgMult;
        const spellAmp = (stats.spell_amp !== undefined ? stats.spell_amp : ((p.maxMp || 100) * 0.2));
        const healAmt = Math.max(12, Math.min(Math.floor(p.maxHp * 0.01), 6000) + Math.min(4000, Math.floor((stats.int || 20) * 0.25)));
        p.currentHp = Math.min(p.maxHp, p.currentHp + healAmt);
        spawnFloatingText(p.x, p.y - 30, `💚 +${healAmt} ХП (РАПСОДИЯ)`, "#22c55e");

        if (!ARENA.specialEffects) ARENA.specialEffects = [];
        ARENA.specialEffects.push({
          type: "rhapsody_beat",
          x: p.x,
          y: p.y,
          radius: 25,
          maxRadius: 280,
          timer: 28,
          maxTimer: 28,
          color: "#22c55e"
        });
        ARENA.cameraTrauma = Math.min(1.0, (ARENA.cameraTrauma || 0) + 0.3);
        triggerHaptic("heavy");

        const pulseDmg = Math.floor(((stats.max_atk || 30) * 0.7 + spellAmp * 0.25) * ultMult);
        if (ARENA.topDownMode || ARENA.isRaidBossBattle) {
          if (ARENA.bossEntity && ARENA.bossEntity.hp > 0) {
            const dist = Math.hypot(ARENA.bossEntity.x - p.x, ARENA.bossEntity.y - p.y);
            if (dist <= 280) {
              const actualDmg = applyDamageToBoss(ARENA.bossEntity, pulseDmg);
              spawnFloatingText(ARENA.bossEntity.x, ARENA.bossEntity.y - 25, `🐸 -${actualDmg} РАПСОДИЯ`, "#a855f7");
            }
          }
          for (const c of ARENA.creeps) {
            const dist = Math.hypot(c.x - p.x, c.y - p.y);
            if (dist <= 280) {
              if (c.isBoss) {
                applyDamageToBoss(c, pulseDmg);
              } else {
                c.hp -= pulseDmg;
              }
              spawnFloatingText(c.x, c.y - 15, `🐸 -${pulseDmg}`, "#a855f7");
            }
          }
        } else {
          for (const c of ARENA.creeps) {
            if (Math.abs(c.x - p.x) <= 320) {
              safeDamageCreep(c, pulseDmg, false);
              spawnFloatingText(c.x, c.y - 15, `🐸 -${pulseDmg} РАПСОДИЯ`, "#a855f7");
            }
          }
        }

        spawnFloatingText(p.x, p.y - 65, "🐸 РАПСОДИЯ ВКЛ (Каждые 0.5с: хил, урон, -MP)", "#22c55e");
        const ultEl = document.getElementById("rpg-cd-ult");
        if (ultEl) ultEl.textContent = "ВЫКЛ";
        return;
      }
    }

    if (ARENA.ultCooldown > 0) {
      const sec = Math.ceil(ARENA.ultCooldown / 60);
      spawnFloatingText(p.x, p.y - 25, `Ульта: КД ${sec}с`, "#94a3b8");
      triggerHaptic("error");
      return;
    }
    if (p.currentMp < cost) {
      spawnFloatingText(p.x, p.y - 25, `Мало маны (нужно ${cost} MP)!`, "#94a3b8");
      triggerHaptic("error");
      return;
    }

    p.currentMp -= cost;
    const ultCdReduct = Math.min(60, stats.ult_cd_reduct || 0);
    ARENA.ultCooldown = Math.max(60, Math.floor(skillCfg.ultCd * (1.0 - ultCdReduct / 100.0)));
    triggerHaptic("heavy");

    const ultMultiplier = 1.0 + ((stats.ult_boost || 0) / 100.0);

    // TOP-DOWN 360° BOSS ULTIMATES
    if (ARENA.topDownMode || ARENA.isRaidBossBattle) {
      const boss = ARENA.bossEntity;
      if (boss && boss.hp > 0) {
        if (hClass === "invoker") {
          // Chaos Meteor (Котлета) falls from sky directly on boss with massive fiery explosion!
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 5.5 * ultMultiplier));
          ARENA.specialEffects.push({
            type: "topdown_meteor",
            startX: Math.max(30, Math.min(480, boss.x - 90)),
            startY: -70,
            targetX: boss.x,
            targetY: boss.y,
            x: Math.max(30, Math.min(480, boss.x - 90)),
            y: -70,
            radius: 36,
            timer: 50,
            maxTimer: 50,
            dmg: dmg
          });
          ARENA.cameraTrauma = 0.85;
          triggerHaptic("heavy");
          spawnFloatingText(boss.x, boss.y - 45, `☄️ ХАОС МЕТЕОР! -${dmg}`, "#ea580c");
          if (window.hasTalentPerk && window.hasTalentPerk("perk_double_cataclysm")) {
            setTimeout(() => {
              if (boss && boss.hp > 0) {
                const dmg2 = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 4.0 * ultMultiplier));
                ARENA.specialEffects.push({
                  type: "topdown_meteor",
                  startX: Math.max(30, Math.min(480, boss.x + 60)),
                  startY: -70,
                  targetX: boss.x,
                  targetY: boss.y,
                  x: Math.max(30, Math.min(480, boss.x + 60)),
                  y: -70,
                  radius: 30,
                  timer: 40,
                  maxTimer: 40,
                  dmg: dmg2
                });
                spawnFloatingText(boss.x, boss.y - 60, `☄️ ВТОРОЙ МЕТЕОР! -${dmg2}`, "#f97316");
              }
            }, 350);
          }
          return;
        } else if (hClass === "juggernaut") {
          // Omnislash: rapid slashing combo around the boss!
          if (window.hasTalentPerk && window.hasTalentPerk("perk_omnislash_invuln")) {
            p.isInvulnerable = 55;
          }
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 6.0 * ultMultiplier));
          ARENA.specialEffects.push({
            type: "topdown_omnislash",
            x: boss.x,
            y: boss.y,
            timer: 52,
            maxTimer: 52,
            slashes: 8,
            dmg: dmg
          });
          ARENA.cameraTrauma = 0.9;
          triggerHaptic("heavy");
          spawnFloatingText(boss.x, boss.y - 45, `⚔️ ОМНИСЛЕШ ПО БОССУ! -${dmg}`, "#facc15");
          return;
        } else if (hClass === "phantom_assassin") {
          // Coup de Grace: blood critical strike!
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 6.5 * ultMultiplier));
          ARENA.specialEffects.push({
            type: "coup_de_grace",
            x: boss.x,
            y: boss.y,
            timer: 35,
            maxTimer: 35,
            dmg: dmg
          });
          ARENA.cameraTrauma = 1.0;
          triggerHaptic("heavy");
          spawnFloatingText(boss.x, boss.y - 45, `🩸 COUP DE GRACE x6.5! -${dmg}`, "#dc2626");
          return;
        } else if (hClass === "shadow_fiend") {
          // Requiem of Souls: blast of souls across the arena!
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 5.8 * ultMultiplier));
          ARENA.specialEffects.push({
            type: "requiem_of_souls",
            x: p.x,
            y: p.y,
            timer: 45,
            maxTimer: 45,
            dmg: dmg
          });
          if (window.hasTalentPerk && window.hasTalentPerk("perk_requiem_fear")) {
            boss.fearTimer = 150; // 2.5s
            spawnFloatingText(boss.x, boss.y - 65, "😱 СТРАХ (2.5с)!", "#a855f7");
          }
          ARENA.cameraTrauma = 0.85;
          triggerHaptic("heavy");
          spawnFloatingText(boss.x, boss.y - 45, `🌪️ РЕКВИЕМ ДУШ! -${dmg}`, "#a855f7");
          return;
        } else if (hClass === "wraith_king") {
          // Skeleton Army: massive critical strike + summon skeletons
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 5.2 * ultMultiplier));
          p.currentHp = Math.min(p.maxHp, p.currentHp + Math.floor(dmg * 0.4));
          ARENA.specialEffects.push({
            type: "wk_skeletons",
            x: p.x,
            y: p.y,
            bossX: boss.x,
            bossY: boss.y,
            timer: 180,
            maxTimer: 180
          });
          if (!ARENA.alliedMinions) ARENA.alliedMinions = [];
          for (let s = 0; s < 3; s++) {
            ARENA.alliedMinions.push({
              x: p.x + (s - 1) * 28,
              y: p.y + 20,
              radius: 12,
              hp: 150,
              maxHp: 150,
              atk: Math.floor((stats.max_atk || 30) * 0.9),
              speed: 2.8,
              heroClass: "wraith_king",
              name: "Скелет"
            });
          }
          spawnFloatingText(boss.x, boss.y - 45, `👑 АРМИЯ СКЕЛЕТОВ! -${dmg}`, "#10b981");
          return;
        } else if (hClass === "pudge") {
          // Rot & Dismember: toxic miasma & meat cleaver chops
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 4.8 * ultMultiplier));
          p.rotActive = 180;
          ARENA.specialEffects.push({
            type: "pudge_dismember",
            fromX: p.x,
            fromY: p.y,
            x: boss.x,
            y: boss.y,
            timer: 45,
            maxTimer: 45,
            dmg: dmg
          });
          spawnFloatingText(boss.x, boss.y - 45, `☣️ ЧУМНАЯ ГНИЛЬ! -${dmg}`, "#22c55e");
          return;
        } else if (hClass === "anti_mage") {
          // Mana Void: Arcane implosion on boss!
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 5.6 * ultMultiplier));
          ARENA.specialEffects.push({
            type: "mana_void",
            x: boss.x,
            y: boss.y,
            timer: 40,
            maxTimer: 40,
            dmg: dmg
          });
          ARENA.cameraTrauma = 0.9;
          spawnFloatingText(boss.x, boss.y - 45, `💥 ВЗРЫВ МАНЫ! -${dmg}`, "#38bdf8");
          return;
        }
      }
    }

    // 1. INVOKER: Chaos Meteor («Котлета» Инвокера, падающая с неба и катящаяся по всей линии)
    if (hClass === "invoker") {
      const spellAmpPct = (stats.spell_amp !== undefined ? stats.spell_amp : ((p.maxMp || 100) * 0.2));
      const manaBonus = 1.0 + (spellAmpPct / 100) + (p.currentMp ? (p.currentMp / p.maxMp) * 0.3 : 0);
      const meteorDmg = Math.floor((stats.max_atk || 30) * 3.2 * manaBonus * ultMultiplier);
      if (!ARENA.playerProjectiles) ARENA.playerProjectiles = [];

      ARENA.playerProjectiles.push({
        type: "meteor",
        x: p.x + 15,
        y: -50,
        targetY: ARENA.roadY - 16,
        vx: 2.0,
        vy: 9.5,
        falling: true,
        speed: 5.2,
        radius: 36,
        angle: 0,
        dmg: meteorDmg,
        hitCreepIds: new Set(),
        burnTrail: []
      });

      spawnFloatingText(p.x + 40, p.y - 45, `☄️ ХАОС МЕТЕОР ПАДАЕТ С НЕБА!${stats.ult_boost ? ` (+${stats.ult_boost}% Ульта)` : ""}`, "#ea580c");
      triggerHaptic("heavy");
      if (window.hasTalentPerk && window.hasTalentPerk("perk_double_cataclysm")) {
        setTimeout(() => {
          if (!ARENA.playerProjectiles) ARENA.playerProjectiles = [];
          ARENA.playerProjectiles.push({
            type: "meteor",
            x: p.x + 55,
            y: -50,
            targetY: ARENA.roadY - 16,
            vx: 2.2,
            vy: 9.5,
            falling: true,
            speed: 5.2,
            radius: 30,
            angle: 0,
            dmg: Math.floor(meteorDmg * 0.75),
            hitCreepIds: new Set(),
            burnTrail: []
          });
          spawnFloatingText(p.x + 60, p.y - 45, "☄️ ВТОРОЙ МЕТЕОР!", "#f97316");
        }, 350);
      }
      return;
    }

    // 2. PUDGE: Rot (Choking Poison Cloud for 2.5s across the whole map)
    if (hClass === "pudge") {
      p.rotActive = 150; // 2.5 sec
      p.rotDmgMult = ultMultiplier;
      ARENA.specialEffects.push({ type: "rot", timer: 150, maxTimer: 150 });
      spawnFloatingText(p.x + 30, p.y - 45, `☣️ ЧУМНАЯ ГНИЛЬ!${stats.ult_boost ? ` (+${stats.ult_boost}% Ульта)` : ""}`, "#22c55e");
      return;
    }

    // 3. JUGGERNAUT: Omnislash (8 golden slashing strikes across the field)
    if (hClass === "juggernaut") {
      if (window.hasTalentPerk && window.hasTalentPerk("perk_omnislash_invuln")) {
        p.isInvulnerable = 65;
      }
      ARENA.specialEffects.push({ type: "omnislash", slashes: 8, timer: 65, currentSlash: 0, mult: ultMultiplier });
      spawnFloatingText(p.x + 30, p.y - 45, `⚔️ ОМНИСЛЕШ ПО ВСЕЙ КАРТЕ!${stats.ult_boost ? ` (+${stats.ult_boost}% Ульта)` : ""}`, "#facc15");
      return;
    }

    // 4. PHANTOM ASSASSIN: Coup de Grace (Screen Blood Flash + x5.5 Crit)
    if (hClass === "phantom_assassin") {
      ARENA.specialEffects.push({ type: "blood_flash", timer: 20 });
      const critDmg = Math.floor((stats.max_atk || 30) * 5.5 * ultMultiplier);
      for (const c of ARENA.creeps) {
        if (c.archetype === "defender") {
          c.shieldBrokenTimer = 240;
          c.state = "stagger";
          c.staggerTimer = 80;
          c.stateTimer = 80;
        }
        safeDamageCreep(c, critDmg, false);
        spawnFloatingText(c.x, c.y - 25, `🩸 КРИТ x5.5! -${critDmg}`, "#dc2626");
      }
      spawnFloatingText(p.x + 30, p.y - 45, `🩸 COUP DE GRACE!${stats.ult_boost ? ` (+${stats.ult_boost}% Ульта)` : ""}`, "#dc2626");
      return;
    }

    // 5. SHADOW FIEND: Requiem of Souls (Waves of souls across all lanes)
    if (hClass === "shadow_fiend") {
      const dmg = Math.floor((stats.max_atk || 30) * 4.5 * ultMultiplier);
      for (let i = 0; i < 8; i++) {
        ARENA.playerProjectiles.push({
          type: "dagger",
          x: p.x + 20,
          y: p.y - 25 + i * 8,
          speed: 6.5 + i * 0.5,
          dmg: dmg,
          icon: "🌑",
          color: "#c084fc"
        });
      }
      if (window.hasTalentPerk && window.hasTalentPerk("perk_requiem_fear")) {
        for (const c of ARENA.creeps) {
          c.fearTimer = 150;
          c.speed = -1.0;
        }
        spawnFloatingText(p.x + 30, p.y - 65, "😱 СТРАХ НА ВСЕХ!", "#a855f7");
      }
      spawnFloatingText(p.x + 30, p.y - 45, `🌪️ РЕКВИЕМ ДУШ!${stats.ult_boost ? ` (+${stats.ult_boost}% Ульта)` : ""}`, "#a855f7");
      return;
    }

    // 6. WRAITH KING: Vampiric Skeleton Army (Summons 3 skeletons + full lifesteal)
    if (hClass === "wraith_king") {
      for (let i = 0; i < 3; i++) {
        ARENA.alliedMinions.push({
          x: p.x + 30 + i * 20,
          y: ARENA.roadY - 14 + (i * 12 - 12),
          speed: 2.2,
          hp: Math.floor(90 * ultMultiplier),
          maxHp: Math.floor(90 * ultMultiplier),
          atk: Math.floor((stats.max_atk || 25) * 1.4 * ultMultiplier),
          radius: 14,
          icon: "☠️"
        });
      }
      p.currentHp = Math.min(p.maxHp, p.currentHp + Math.floor(p.maxHp * 0.5 * ultMultiplier));
      spawnFloatingText(p.x + 30, p.y - 45, `👑 АРМИЯ СКЕЛЕТОВ + ИСЦЕЛЕНИЕ!${stats.ult_boost ? ` (+${stats.ult_boost}% Ульта)` : ""}`, "#10b981");
      return;
    }

    // 7. ANTI-MAGE: Mana Void
    if (hClass === "anti_mage") {
      const dmg = Math.floor((stats.max_atk || 30) * 4.8 * ultMultiplier);
      const targetX = ARENA.width * 0.6;
      ARENA.specialEffects.push({ type: "lightning", x: targetX, y: ARENA.roadY - 15, radius: 130, timer: 30 });
      for (const c of ARENA.creeps) {
        if (c.archetype === "defender") {
          c.shieldBrokenTimer = 240;
          c.state = "stagger";
          c.staggerTimer = 80;
          c.stateTimer = 80;
        }
        safeDamageCreep(c, dmg, false);
        spawnFloatingText(c.x, c.y - 20, `💥 ВЗРЫВ МАНЫ! -${dmg}`, "#8b5cf6");
      }
      spawnFloatingText(p.x + 30, p.y - 45, `💥 ВЗРЫВ МАНЫ (MANA VOID)!${stats.ult_boost ? ` (+${stats.ult_boost}% Ульта)` : ""}`, "#8b5cf6");
      return;
    }
  }


  // ===========================================================================
  // ACTIVE ITEMS SYSTEM (Refresher Orb, Dagon, Blink, BKB, Eul, Shiva, Satanic)
  // ===========================================================================

  const ACTIVE_ITEM_DEFINITIONS = {
    refresher: {
      match: (it) => it && (it.name?.toLowerCase().includes("refresher") || it.name?.toLowerCase().includes("обновлен") || it.bonus?.refresh),
      name: "Сфера Обновления (Refresher Orb)",
      shortName: "Рефрешер",
      icon: "🟢",
      cdFrames: 1500, // 25s
      cdSec: 25,
      mpCost: 40,
      description: "Мгновенно сбрасывает время перезарядки всех скиллов!",
      execute: (p, stats) => {
        ARENA.skill1Cooldown = 0;
        ARENA.ultCooldown = 0;
        p.attackCooldown = 0;
        if (p.dashCooldown) p.dashCooldown = 0;
        if (p.isBlocking) p.isBlocking = 0;
        
        // Reset any other active items except refresher itself
        if (ARENA.itemCooldowns) {
          for (const k in ARENA.itemCooldowns) {
            if (k !== "refresher") ARENA.itemCooldowns[k] = 0;
          }
        }

        // Sync DOM immediately
        const s1El = document.getElementById("rpg-cd-skill1");
        if (s1El) s1El.textContent = "Скилл 1";
        const btn1 = document.getElementById("rpg-btn-skill1");
        if (btn1) btn1.style.opacity = "1";

        const ultEl = document.getElementById("rpg-cd-ult");
        if (ultEl) ultEl.textContent = "Ульта";
        const btnUlt = document.getElementById("rpg-btn-ult");
        if (btnUlt) btnUlt.style.opacity = "1";

        // Green energy burst expanding from hero
        ARENA.specialEffects.push({
          type: "refresher_burst",
          x: p.x,
          y: p.y,
          radius: 10,
          maxRadius: 75,
          timer: 35
        });

        spawnFloatingText(p.x + 30, p.y - 45, "🟢 РЕФРЕШЕР! ВСЕ СКИЛЛЫ ГОТОВЫ! ⚡", "#22c55e");
        triggerHaptic("heavy");
        return true;
      }
    },
    dagon: {
      match: (it) => it && (it.name?.toLowerCase().includes("dagon") || it.name?.toLowerCase().includes("дагон") || it.bonus?.burst_magic),
      name: "Дагон (Dagon)",
      shortName: "Дагон",
      icon: "⚡",
      cdFrames: 720, // 12s
      cdSec: 12,
      mpCost: 25,
      description: "Мощный разряд молнии в ближайшего врага",
      execute: (p, stats, item) => {
        const baseBurst = item?.bonus?.burst_magic || 150;
        const spellAmp = stats.spell_amp || 0;
        const totalInt = stats.total_intelligence || (stats.gear_int || 0) + (p.intelligence || 10);
        const dmg = Math.floor(baseBurst * (1 + spellAmp / 100) * (1 + totalInt / 80));

        let target = null;
        let minX = 9999;
        for (const c of ARENA.creeps) {
          if (c.hp > 0 && c.x < minX) {
            minX = c.x;
            target = c;
          }
        }
        if (!target && ARENA.bossEntity && ARENA.bossEntity.hp > 0) {
          target = ARENA.bossEntity;
        }
        if (!target) {
          spawnFloatingText(p.x, p.y - 25, "Нет целей в радиусе!", "#94a3b8");
          return false;
        }

        safeDamageCreep(target, dmg, false);
        ARENA.specialEffects.push({
          type: "dagon_beam",
          fromX: p.x + 20,
          fromY: p.y - 12,
          toX: target.x,
          toY: target.y,
          timer: 18,
          color: "#ef4444"
        });

        spawnFloatingText(target.x, target.y - 30, `⚡ ДАГОН! -${dmg.toLocaleString()}`, "#ef4444");
        triggerHaptic("heavy");
        return true;
      }
    },
    blink: {
      match: (it) => it && (it.name?.toLowerCase().includes("blink") || it.name?.toLowerCase().includes("скачка") || it.bonus?.blink),
      name: "Кинжал Скачка (Blink Dagger)",
      shortName: "Блинк",
      icon: "🗡️",
      cdFrames: 480, // 8s
      cdSec: 8,
      mpCost: 0,
      description: "Мгновенный скачок со станом врагов вокруг",
      execute: (p, stats) => {
        ARENA.specialEffects.push({
          type: "blink_poof",
          x: p.x,
          y: p.y,
          timer: 20
        });
        for (const c of ARENA.creeps) {
          if (Math.abs(c.x - (p.x + 80)) < 70) {
            c.state = "stagger";
            c.staggerTimer = 90;
            safeDamageCreep(c, Math.floor((stats.max_atk || 30) * 1.5), false);
          }
        }
        spawnFloatingText(p.x + 30, p.y - 35, "🗡️ БЛИНК!", "#38bdf8");
        triggerHaptic("medium");
        return true;
      }
    },
    bkb: {
      match: (it) => it && (it.name?.toLowerCase().includes("black king bar") || it.name?.toLowerCase().includes("королевский бар") || it.bonus?.magic_immune),
      name: "Черный Королевский Бар (BKB)",
      shortName: "БКБ",
      icon: "🟡",
      cdFrames: 1500, // 25s
      cdSec: 25,
      mpCost: 0,
      description: "Золотой Аватар: 6 секунд полной неуязвимости!",
      execute: (p) => {
        p.bkbActive = 360; // 6s
        spawnFloatingText(p.x + 30, p.y - 45, "🟡 БКБ! 100% НЕУЯЗВИМОСТЬ 6 СЕК! 👑", "#eab308");
        triggerHaptic("heavy");
        return true;
      }
    },
    satanic: {
      match: (it) => it && (it.name?.toLowerCase().includes("satanic") || it.name?.toLowerCase().includes("сатаник")),
      name: "Сатаник (Satanic)",
      shortName: "Сатаник",
      icon: "🩸",
      cdFrames: 1500, // 25s
      cdSec: 25,
      mpCost: 0,
      description: "Нечестивая Ярость: 100% вампиризм на 6 секунд",
      execute: (p) => {
        p.satanicActive = 360; // 6s
        spawnFloatingText(p.x + 30, p.y - 45, "🩸 САТАНИК! 100% ВАМПИРИЗМ! 🧛", "#dc2626");
        triggerHaptic("heavy");
        return true;
      }
    },
    eul: {
      match: (it) => it && (it.name?.toLowerCase().includes("eul") || it.name?.toLowerCase().includes("эул") || it.bonus?.tornado),
      name: "Скипетр Эула (Eul's Scepter)",
      shortName: "Эул",
      icon: "🌪️",
      cdFrames: 840, // 14s
      cdSec: 14,
      mpCost: 25,
      description: "Торнадо: неуязвимость на 2.5 секунды",
      execute: (p) => {
        p.eulActive = 150; // 2.5s
        spawnFloatingText(p.x + 30, p.y - 45, "🌪️ ЭУЛ! В ТОРНАДО! 💨", "#06b6d4");
        triggerHaptic("medium");
        return true;
      }
    },
    shiva: {
      match: (it) => it && (it.name?.toLowerCase().includes("shiva") || it.name?.toLowerCase().includes("шива")),
      name: "Шива (Shiva's Guard)",
      shortName: "Шива",
      icon: "❄️",
      cdFrames: 960, // 16s
      cdSec: 16,
      mpCost: 35,
      description: "Арктический взрыв: заморозка и урон по всей арене",
      execute: (p, stats) => {
        const dmg = Math.floor((stats.max_atk || 30) * 2.6 * (1 + (stats.spell_amp || 0) / 100));
        ARENA.specialEffects.push({
          type: "shiva_blast",
          x: p.x,
          y: p.y,
          radius: 20,
          maxRadius: 280,
          timer: 45
        });
        for (const c of ARENA.creeps) {
          safeDamageCreep(c, dmg, false);
          c.state = "stagger";
          c.staggerTimer = 180;
          spawnFloatingText(c.x, c.y - 25, `❄️ -${dmg}`, "#38bdf8");
        }
        spawnFloatingText(p.x + 30, p.y - 45, "❄️ ШИВА! АРКТИЧЕСКИЙ ВЗРЫВ!", "#38bdf8");
        triggerHaptic("heavy");
        return true;
      }
    },
    meteor: {
      match: (it) => it && (it.name?.toLowerCase().includes("meteor") || it.name?.toLowerCase().includes("метеор") || it.name?.toLowerCase().includes("fallen sky")),
      name: "Метеоритный Молот (Meteor Hammer)",
      shortName: "Метеор",
      icon: "☄️",
      cdFrames: 1080, // 18s
      cdSec: 18,
      mpCost: 45,
      description: "Призывает сокрушительный метеорит со станом",
      execute: (p, stats) => {
        const meteorDmg = Math.floor((stats.max_atk || 30) * 4.2 * (1 + (stats.spell_amp || 0) / 100));
        ARENA.playerProjectiles.push({
          type: "meteor",
          x: p.x + 15,
          y: -50,
          targetY: ARENA.roadY - 16,
          vx: 2.0,
          vy: 9.5,
          falling: true,
          speed: 5.2,
          radius: 38,
          angle: 0,
          dmg: meteorDmg,
          hitCreepIds: new Set(),
          burnTrail: []
        });
        spawnFloatingText(p.x + 30, p.y - 45, "☄️ ПАДЕНИЕ МЕТЕОРА!", "#ea580c");
        triggerHaptic("heavy");
        return true;
      }
    },
    ethereal: {
      match: (it) => it && (it.name?.toLowerCase().includes("ethereal") || it.name?.toLowerCase().includes("эфирн")),
      name: "Эфирный Клинок (Ethereal Blade)",
      shortName: "Эзернал",
      icon: "🪄",
      cdFrames: 840, // 14s
      cdSec: 14,
      mpCost: 35,
      description: "Астральный выстрел: урон от Интеллекта",
      execute: (p, stats) => {
        const target = ARENA.creeps[0] || ARENA.bossEntity;
        if (!target) return false;
        const totalInt = stats.total_intelligence || (stats.gear_int || 0) + (p.intelligence || 10);
        const dmg = Math.floor(totalInt * 2.8 * (1 + (stats.spell_amp || 0) / 100) + 200);
        safeDamageCreep(target, dmg, false);
        spawnFloatingText(target.x, target.y - 30, `🪄 ЭФИРНЫЙ ВЗРЫВ! -${dmg}`, "#22c55e");
        triggerHaptic("heavy");
        return true;
      }
    },
    manta: {
      match: (it) => it && (it.name?.toLowerCase().includes("manta") || it.name?.toLowerCase().includes("манта")),
      name: "Манта Стайл (Manta Style)",
      shortName: "Манта",
      icon: "👥",
      cdFrames: 1200, // 20s
      cdSec: 20,
      mpCost: 30,
      description: "Создает 2 иллюзии героя в бою на 7 секунд",
      execute: (p) => {
        p.mantaIllusionsTimer = 420; // 7 sec
        spawnFloatingText(p.x + 30, p.y - 45, "👥 МАНТА! ИЛЛЮЗИИ В БОЮ!", "#38bdf8");
        triggerHaptic("heavy");
        return true;
      }
    },
    abyssal: {
      match: (it) => it && (it.name?.toLowerCase().includes("abyssal") || it.name?.toLowerCase().includes("бездн") || it.bonus?.abyssal_stun),
      name: "Клинок Бездны (Abyssal Blade)",
      shortName: "Абиссал",
      icon: "🗡️",
      cdFrames: 720, // 12s
      cdSec: 12,
      mpCost: 35,
      description: "Оглушает цель на 2.5с сокрушительным ударом",
      execute: (p, stats) => {
        let target = ARENA.creeps[0] || ARENA.bossEntity;
        if (!target) return false;
        const stunDmg = Math.floor((stats.max_atk || 40) * 3.2);
        safeDamageCreep(target, stunDmg, false);
        target.state = "stagger";
        target.staggerTimer = 150;
        target.stateTimer = 150;
        ARENA.cameraTrauma = 0.8;
        ARENA.hitstop = 10;
        spawnFloatingText(target.x, target.y - 30, `⚡ АБИССАЛ СТАН! -${stunDmg}`, "#facc15");
        triggerHaptic("heavy");
        return true;
      }
    },
    hex: {
      match: (it) => it && (it.name?.toLowerCase().includes("hex") || it.name?.toLowerCase().includes("вайс") || it.name?.toLowerCase().includes("хекс") || it.bonus?.hex),
      name: "Хекс (Scythe of Vyse)",
      shortName: "Хекс",
      icon: "🐑",
      cdFrames: 900, // 15s
      cdSec: 15,
      mpCost: 50,
      description: "Превращает врага в безобидную свинку на 3.5 секунды",
      execute: (p) => {
        let target = ARENA.creeps[0] || ARENA.bossEntity;
        if (!target) return false;
        target.state = "stagger";
        target.staggerTimer = 210; // 3.5s
        target.stateTimer = 210;
        spawnFloatingText(target.x, target.y - 30, "🐑 ХЕКС! ПРЕВРАЩЕНИЕ В СВИНКУ!", "#a855f7");
        triggerHaptic("heavy");
        return true;
      }
    },
    bloodthorn: {
      match: (it) => it && (it.name?.toLowerCase().includes("bloodthorn") || it.name?.toLowerCase().includes("шип") || it.bonus?.bloodthorn_silence),
      name: "Кровавый Шип (Bloodthorn)",
      shortName: "Бладторн",
      icon: "🌹",
      cdFrames: 840, // 14s
      cdSec: 14,
      mpCost: 40,
      description: "Безмолвие цели + 100% критические удары на 4.5с",
      execute: (p) => {
        p.bloodthornActive = 270;
        spawnFloatingText(p.x + 30, p.y - 45, "🌹 БЛАДТОРН! 100% КРИТЫ! 🩸", "#ef4444");
        triggerHaptic("heavy");
        return true;
      }
    },
    gleipnir: {
      match: (it) => it && (it.name?.toLowerCase().includes("gleipnir") || it.name?.toLowerCase().includes("глейпнир") || it.bonus?.gleipnir_root),
      name: "Глейпнир (Gleipnir)",
      shortName: "Глейпнир",
      icon: "⛓️",
      cdFrames: 960, // 16s
      cdSec: 16,
      mpCost: 45,
      description: "Оцепенение всех врагов на арене на 2.5с + молнии",
      execute: (p, stats) => {
        const dmg = Math.floor((stats.max_atk || 30) * 2.2);
        for (const c of ARENA.creeps) {
          c.state = "stagger";
          c.staggerTimer = 150;
          safeDamageCreep(c, dmg, false);
          spawnFloatingText(c.x, c.y - 20, `⛓️ КОРНИ! -${dmg}`, "#38bdf8");
        }
        spawnFloatingText(p.x + 30, p.y - 45, "⛓️ ГЛЕЙПНИР! ВСЯ АРЕНА СКОВАНА!", "#38bdf8");
        triggerHaptic("heavy");
        return true;
      }
    },
    blademail: {
      match: (it) => it && (it.name?.toLowerCase().includes("blade mail") || it.name?.toLowerCase().includes("возврат") || it.name?.toLowerCase().includes("шипаст") || it.bonus?.active_blademail),
      name: "Возвратка (Blade Mail)",
      shortName: "БМ",
      icon: "🛡️",
      cdFrames: 720, // 12s
      cdSec: 12,
      mpCost: 20,
      description: "Возвращает 100% урона обратно всем атакующим на 4.5с",
      execute: (p) => {
        p.blademailActive = 270;
        spawnFloatingText(p.x + 30, p.y - 45, "🛡️ БЛЕЙДМЕЙЛ АКТИВИРОВАН! 🪞", "#facc15");
        triggerHaptic("heavy");
        return true;
      }
    },
    crimson: {
      match: (it) => it && (it.name?.toLowerCase().includes("crimson") || it.name?.toLowerCase().includes("багров") || it.bonus?.active_crimson),
      name: "Багровая Защита (Crimson Guard)",
      shortName: "Кримсон",
      icon: "🔴",
      cdFrames: 1200, // 20s
      cdSec: 20,
      mpCost: 35,
      description: "Купол защиты: блокирует 85 урона от каждого удара на 8с",
      execute: (p) => {
        p.crimsonActive = 480;
        p.crimsonBlock = 85;
        spawnFloatingText(p.x + 30, p.y - 45, "🔴 КРИМСОН ГВАРД! БРОНЕКУПОЛ!", "#dc2626");
        triggerHaptic("heavy");
        return true;
      }
    },
    pipe: {
      match: (it) => it && (it.name?.toLowerCase().includes("pipe") || it.name?.toLowerCase().includes("трубк") || it.bonus?.active_pipe),
      name: "Трубка Прозрения (Pipe of Insight)",
      shortName: "Пайп",
      icon: "📯",
      cdFrames: 1080, // 18s
      cdSec: 18,
      mpCost: 40,
      description: "Магический барьер на 650 урона от снарядов и заклинаний",
      execute: (p) => {
        p.pipeShield = 650;
        spawnFloatingText(p.x + 30, p.y - 45, "📯 ПАЙП! МАГИЧЕСКИЙ ЩИТ 650!", "#a855f7");
        triggerHaptic("heavy");
        return true;
      }
    },
    armlet: {
      match: (it) => it && (it.name?.toLowerCase().includes("armlet") || it.name?.toLowerCase().includes("арматур") || it.bonus?.unholy_strength),
      name: "Арматура (Armlet of Mordiggian)",
      shortName: "Армлет",
      icon: "🧤",
      cdFrames: 120, // 2s toggle
      cdSec: 2,
      mpCost: 0,
      description: "Нечестивая сила: +40 Сила, +65 Урон, +15 Броня",
      execute: (p) => {
        p.armletActive = !p.armletActive;
        if (p.armletActive) {
          spawnFloatingText(p.x + 30, p.y - 45, "😈 АРМЛЕТ ВКЛ! +СИЛА И УРОН!", "#ef4444");
        } else {
          spawnFloatingText(p.x + 30, p.y - 45, "💤 АРМЛЕТ ВЫКЛЮЧЕН", "#94a3b8");
        }
        triggerHaptic("medium");
        return true;
      }
    },
    hurricane: {
      match: (it) => it && (it.name?.toLowerCase().includes("hurricane") || it.name?.toLowerCase().includes("force staff") || it.name?.toLowerCase().includes("ураган") || it.bonus?.active_pike),
      name: "Пика Урагана (Hurricane Pike)",
      shortName: "Пика",
      icon: "🔱",
      cdFrames: 720, // 12s
      cdSec: 12,
      mpCost: 30,
      description: "Отталкивает врагов назад на 130px",
      execute: (p) => {
        for (const c of ARENA.creeps) {
          c.x += 130;
          c.state = "stagger";
          c.staggerTimer = 60;
        }
        spawnFloatingText(p.x + 30, p.y - 45, "💨 ПИКА! ОТТАЛКИВАНИЕ ВРАГОВ!", "#38bdf8");
        triggerHaptic("heavy");
        return true;
      }
    },
    silver_edge: {
      match: (it) => it && (it.name?.toLowerCase().includes("silver") || it.name?.toLowerCase().includes("серебрян") || it.name?.toLowerCase().includes("shadow blade") || it.bonus?.active_invis),
      name: "Серебряный Клинок (Silver Edge)",
      shortName: "Сильвер",
      icon: "🗡️",
      cdFrames: 840, // 14s
      cdSec: 14,
      mpCost: 35,
      description: "Уход в невидимость: следующий удар наносит 250% урона",
      execute: (p) => {
        p.shadowWalk = 300; // 5s
        spawnFloatingText(p.x + 30, p.y - 45, "👻 ТЕНЕВОЙ ШАГ! СЛЕДУЮЩИЙ УДАР 250%!", "#94a3b8");
        triggerHaptic("heavy");
        return true;
      }
    },
  };

  function getEquippedActiveItems() {
    const eq = RPG_STATE.profile?.equipment || {};
    const result = [];
    const seenKeys = new Set();
    for (const slot of ["relic", "weapon", "armor"]) {
      const it = eq[slot];
      if (!it) continue;
      for (const [key, def] of Object.entries(ACTIVE_ITEM_DEFINITIONS)) {
        if (!seenKeys.has(key) && def.match(it)) {
          seenKeys.add(key);
          result.push({ slot, key, item: it, def });
          break;
        }
      }
    }
    return result;
  }

  function useActiveItemAction(idx = 0) {
    const activeItems = getEquippedActiveItems();
    if (!activeItems || !activeItems[idx]) {
      spawnFloatingText(ARENA.player.x, ARENA.player.y - 25, "Нет активного предмета!", "#94a3b8");
      triggerHaptic("error");
      return;
    }

    const act = activeItems[idx];
    if (!ARENA.itemCooldowns) ARENA.itemCooldowns = {};

    const currentCd = ARENA.itemCooldowns[act.key] || 0;
    if (currentCd > 0) {
      const sec = Math.ceil(currentCd / 60);
      spawnFloatingText(ARENA.player.x, ARENA.player.y - 25, `${act.def.shortName}: КД ${sec}с`, "#94a3b8");
      triggerHaptic("error");
      return;
    }

    const p = ARENA.player;
    if (p.isFrozenInTime || (p.stunTimer && p.stunTimer > 0)) {
      spawnFloatingText(p.x, p.y - 25, "💫 ОГЛУШЕНИЕ!", "#facc15");
      triggerHaptic("error");
      return;
    }
    if (p.doomDebuffTimer && p.doomDebuffTimer > 0 && act.key !== "bkb") {
      spawnFloatingText(p.x, p.y - 25, "🔥 DOOM (ПРЕДМЕТЫ ЗАБЛОКИРОВАНЫ)!", "#dc2626");
      triggerHaptic("error");
      return;
    }

    const stats = RPG_STATE.profile?.stats || {};
    const cost = act.def.mpCost || 0;

    if (cost > 0 && p.currentMp < cost) {
      spawnFloatingText(p.x, p.y - 25, `Нужно ${cost} MP!`, "#94a3b8");
      triggerHaptic("error");
      return;
    }

    if (cost > 0) {
      p.currentMp -= cost;
    }

    const ok = act.def.execute(p, stats, act.item);
    if (ok !== false) {
      ARENA.itemCooldowns[act.key] = act.def.cdFrames;
      const cdEl = document.getElementById(`rpg-cd-item-${idx}`);
      if (cdEl) cdEl.textContent = `${act.def.cdSec}с`;
      const btnEl = document.getElementById(`rpg-btn-item-${idx}`);
      if (btnEl) btnEl.style.opacity = "0.6";
    }
  }

  function usePlayerPotion() {
    const p = ARENA.player;
    if (!p || p.isDead) return;

    if (ARENA.potionCooldown > 0) {
      triggerHaptic("light");
      return;
    }

    const stats = RPG_STATE.profile?.stats || {};
    const flatBonus = stats.flask_heal_flat || 0;
    const pctBonus = stats.flask_heal_pct || 0;
    const heal = Math.max(120, Math.floor(120 + flatBonus + (p.maxHp * pctBonus)));

    if (p.currentHp >= p.maxHp && (!stats.flask_mana || p.currentMp >= p.maxMp)) {
      spawnFloatingText(p.x, p.y - 25, "Здоровье полно!", "#94a3b8");
      return;
    }

    p.currentHp = Math.min(p.maxHp, p.currentHp + heal);
    spawnFloatingText(p.x, p.y - 25, `+${heal} HP 🧪`, "#22c55e");

    if (stats.flask_mana && stats.flask_mana > 0) {
      p.currentMp = Math.min(p.maxMp, p.currentMp + stats.flask_mana);
      spawnFloatingText(p.x, p.y - 42, `+${stats.flask_mana} MP 🔮`, "#38bdf8");
    }

    if (window.hasTalentPerk && window.hasTalentPerk("perk_divine_flask")) {
      p.stunTimer = 0;
      p.freezeTimer = 0;
      p.slowTimer = 0;
      p.speedBuffTimer = 180;
      spawnFloatingText(p.x, p.y - 58, "🌟 ОЧИЩЕНИЕ И УСКОРЕНИЕ!", "#facc15");
    }

    const cdReduct = stats.flask_cd_reduct || 0;
    ARENA.potionCooldown = Math.max(120, 360 - cdReduct);
    triggerHaptic("success");
  }

  // ---------------------------------------------------------------------------
  // WAVE PROGRESSION & DEATH HANDLING
  // ---------------------------------------------------------------------------

  function handleCreepDeath(c) {
    ARENA.pickups.push({
      type: "gold",
      x: c.x + (Math.random() * 12 - 6),
      y: c.y + (Math.random() * 12 - 6),
      value: c.isBoss ? 150 : (c.isMinion ? 3 : 10)
    });
    ARENA.pickups.push({
      type: "xp",
      x: c.x + (Math.random() * 12 - 6),
      y: c.y + (Math.random() * 12 - 6),
      value: c.isBoss ? 80 : (c.isMinion ? 2 : 4)
    });

    // Chest drops strictly from Bosses (Wave 10 mini-boss and Wave 20 floor boss)
    if (!c.isMinion && c.isBoss) {
      ARENA.pickups.push({
        type: "loot",
        x: c.x,
        y: c.y,
        value: 1
      });
    }

    if (c.isBoss) {
      handleBossDefeat();
      return;
    }

    if (!c.isMinion) {
      ARENA.creepsKilledInWave++;
      // SF PERK: Necromastery Soul Stacks (+3% dmg per soul, up to 15 stacks)
      if (window.hasTalentPerk && window.hasTalentPerk("perk_necromastery_stacks")) {
        ARENA.sfSouls = Math.min(15, (ARENA.sfSouls || 0) + 1);
        spawnFloatingText(ARENA.player.x, ARENA.player.y - 40, `👻 ДУША (${ARENA.sfSouls}/15)`, "#a855f7");
      }
      if (ARENA.creepsKilledInWave >= ARENA.creepsNeededForWave) {
        advanceArenaWave();
      }
    }
  }

  async function advanceArenaWave() {
    ARENA.waveState = "wave_clear";
    ARENA.waveTransitionTimer = ARENA.autoAdvanceWaves ? 45 : 70;
    spawnFloatingText(ARENA.width / 2, 90, `✅ ВОЛНА ${ARENA.waveNumber}/${ARENA.waveMax} ЗАЧИЩЕНА!`, "#22c55e");
    triggerHaptic("medium");

    // Sync accumulated wave, gold and XP to backend database immediately!
    try {
      const currentFloor = RPG_STATE.profile?.dungeon_floor || 1;
      const totalWaveCleared = (currentFloor - 1) * 20 + ARENA.waveNumber;
      const floorMult = 1.0 + (currentFloor - 1) * 0.10;
      const baseGold = Math.floor((10 + ARENA.waveNumber * 2) * floorMult);
      const baseXp = Math.floor((15 + ARENA.waveNumber * 3) * (1.0 + (currentFloor - 1) * 0.20));

      // DMC Style Meter Reward Multiplier (D..SSS)
      const rank = ARENA.styleMeter?.rank || "D";
      const styleMultipliers = { D: 1.0, C: 1.15, B: 1.30, A: 1.50, S: 1.70, SS: 1.95, SSS: 2.30 };
      const mult = styleMultipliers[rank] || 1.0;
      const goldGain = Math.floor(baseGold * mult);
      const xpGain = Math.floor(baseXp * mult);
      const bonusGold = goldGain - baseGold;

      if (bonusGold > 0) {
        spawnFloatingText(ARENA.width / 2, 115, `🔥 СТИЛЬ [${rank}]: +${bonusGold} 🪙 БОНУС!`, "#facc15");
      }

      const res = await api.slashCreepWave({
        wave_cleared: totalWaveCleared,
        earned_gold: goldGain,
        earned_xp: xpGain,
        style_rank: rank,
        combo_max: ARENA.combo?.maxCombo || 0
      });
      if (res.profile) {
        RPG_STATE.profile = res.profile;
      }
      if (res.leveled_up) {
        showLevelUpToast(res.profile?.level || 2);
      }
      if (res.chest_reward && (ARENA.waveNumber === 10 || ARENA.waveNumber === 20)) {
        openChestModal(res.chest_reward);
      }
    } catch (e) {
      console.warn("Wave sync warning:", e);
    }
  }

  function confirmNextWave() {
    if (ARENA.waveState !== "prompt") return;

    ARENA.waveNumber++;
    ARENA.creepsKilledInWave = 0;
    ARENA.totalCreepsSpawned = 0;
    ARENA.creeps = [];
    ARENA.pickups = [];
    ARENA.bossProjectiles = [];
    ARENA.playerProjectiles = [];

    // Boss on wave 20!
    if (ARENA.waveNumber === ARENA.waveMax) {
      // Wave 20: BOSS FIGHT! Switch to 2D Boss Arena Combat!
      ARENA.waveState = "boss_intro";
      ARENA.waveTransitionTimer = 120;
      ARENA.bossArenaMode = true;
      ARENA.moveInput = { left: false, right: false };
      ARENA.dodgeCooldown = 0;
      ARENA.dodgeActive = 0;
      ARENA.dangerZones = [];
      ARENA.bossPatternPhase = "idle";
      ARENA.bossPatternTimer = 0;
      spawnBossCreep();
      triggerHaptic("heavy");
    } else if (ARENA.waveNumber > ARENA.waveMax) {
      // Completed all 20 waves and killed the boss!
      handleFloorCleared();
    } else {
      ARENA.creepsNeededForWave = Math.min(32, 14 + Math.floor((ARENA.waveNumber - 1) * 1.0));
      ARENA.waveState = "fighting";
      triggerHaptic("medium");
    }
  }

  function retryCurrentFloor() {
    // Restart from wave 1 on death
    const stats = RPG_STATE.profile?.stats || {};
    ARENA.player.maxHp = Math.max(450, stats.hp_max || 450);
    ARENA.player.currentHp = ARENA.player.maxHp;
    ARENA.player.maxMp = Math.max(80, stats.mp_max || 80);
    ARENA.player.currentMp = ARENA.player.maxMp;
    ARENA.waveNumber = 1;
    ARENA.creepsKilledInWave = 0;
    ARENA.totalCreepsSpawned = 0;
    ARENA.creepsNeededForWave = 10;
    ARENA.creeps = [];
    ARENA.pickups = [];
    ARENA.bossProjectiles = [];
    ARENA.playerProjectiles = [];
    ARENA.alliedMinions = [];
    ARENA.specialEffects = [];
    ARENA.isBossActive = false;
    ARENA.topDownMode = false;
    ARENA.isRaidBossBattle = false;
    ARENA.bossEntity = null;
    ARENA.bossPhase = 0;
    ARENA.blockWindowActive = false;
    ARENA.qteActive = false;
    ARENA.bossArenaMode = false;
    ARENA.moveInput = { left: false, right: false };
    ARENA.dangerZones = [];
    ARENA.player.x = 65;
    ARENA.player.y = ARENA.roadY - 18;
    ARENA.player.isInvulnerable = 0;
    ARENA.player.isDead = false;
    ARENA.waveState = "fighting";

    // Re-render DOM to collapse canvas back to 320px and hide boss controls
    RPG_STATE._forceFullRender = true;
    renderRoot();
    RPG_STATE._forceFullRender = false;

    const canvas = document.getElementById("rpg-action-canvas");
    if (canvas) {
      bindArenaCanvas(canvas);
    }
    triggerHaptic("medium");
  }

  async function handleFloorCleared() {
    if (ARENA.player.currentHp <= 0 || ARENA.waveState === "retry_prompt") {
      return;
    }
    ARENA.waveState = "floor_clear";
    triggerHaptic("success");
    const currentFloor = RPG_STATE.profile?.dungeon_floor || 1;
    spawnFloatingText(ARENA.width / 2, 100, `👑 ЭТАЖ ${currentFloor} ЗАЧИЩЕН!`, "#22c55e");

    try {
      const totalFloorCleared = currentFloor * 20;
      const goldGain = Math.floor(250 + currentFloor * 80 + Math.min(1500, Math.pow(currentFloor, 1.25) * 12));
      const xpGain = Math.floor(200 + currentFloor * 60 + Math.pow(currentFloor, 1.15) * 10);
      const res = await api.slashCreepWave({
        wave_cleared: totalFloorCleared,
        earned_gold: goldGain,
        earned_xp: xpGain
      });
      if (res.profile) RPG_STATE.profile = res.profile;
      if (res.chest_reward) {
        RPG_STATE.lastBossChestReward = res.chest_reward;
        openChestModal(res.chest_reward);
      }
      if (res.leveled_up) showLevelUpToast(res.profile?.level || 2);
    } catch (e) {
      console.error("Failed to sync floor clear:", e);
    }

    setTimeout(() => {
      retryCurrentFloor();
      ARENA.waveNumber = 0;
      if (ARENA.autoAdvanceWaves && !RPG_STATE.activeChestModal) {
        ARENA.waveState = "prompt";
        confirmNextWave();
      } else {
        ARENA.waveState = "prompt";
      }
    }, 4500); // 4.5s to enjoy loot explosion & falling chest
  }

  async function handleRaidBossDefeat() {
    ARENA.waveState = "boss_victory";
    ARENA.hitstop = 15;
    ARENA.cameraTrauma = 1.0;
    triggerHaptic("success");
    const bossTmpl = ARENA.currentRaidBoss || { name: "Рейд-Босс", id: "golem", gold: 600, xp: 400 };
    spawnFloatingText(ARENA.width / 2, 80, `👑 ${bossTmpl.name} ПОВЕРЖЕН! 🏆`, "#eab308");

    spawnLootExplosion(ARENA.bossEntity?.x || ARENA.width * 0.7, ARENA.roadY - 20, bossTmpl);

    try {
      const res = await api.slashCreepWave({
        is_raid_boss: true,
        boss_id: bossTmpl.id,
        earned_gold: bossTmpl.gold || 600,
        earned_xp: bossTmpl.xp || 400
      });
      if (res.profile) RPG_STATE.profile = res.profile;
      if (res.chest_reward) {
        RPG_STATE.lastBossChestReward = res.chest_reward;
      }
      if (res.leveled_up) showLevelUpToast(res.profile?.level || 2);
    } catch (e) {
      console.warn("Could not sync raid boss defeat:", e);
    }
  }

  function handleBossDefeat() {
    if (ARENA.player.currentHp <= 0 || ARENA.waveState === "retry_prompt") {
      return;
    }
    ARENA.hitstop = 15;
    ARENA.cameraTrauma = 1.0;
    triggerHaptic("heavy");

    // Disable Boss Arena Mode — restore player position
    ARENA.bossArenaMode = false;
    ARENA.topDownMode = false;
    ARENA.moveInput = { left: false, right: false };
    ARENA.dangerZones = [];
    ARENA.player.x = 65; // Reset to default stationary position
    ARENA.player.y = ARENA.roadY - 18;
    ARENA.player.isInvulnerable = 0;

    if (ARENA.isRaidBossBattle) {
      handleRaidBossDefeat();
      return;
    }
    spawnLootExplosion(ARENA.bossEntity?.x || ARENA.width * 0.7, ARENA.roadY - 20, { name: "Босс этажа", gold: 350, xp: 250 });
    ARENA.isBossActive = false;
    ARENA.bossEntity = null;
    ARENA.bossPhase = 0;
    ARENA.blockWindowActive = false;
    ARENA.qteActive = false;
    ARENA.bossProjectiles = [];
    handleFloorCleared();
  }


  function exitRaidBossBattle() {
    ARENA.isRaidBossBattle = false;
    ARENA.topDownMode = false;
    ARENA.bossEntity = null;
    ARENA.isBossActive = false;
    ARENA.bossProjectiles = [];
    ARENA.creeps = [];
    ARENA.dangerZones = [];
    ARENA.waveState = "fighting";
    RPG_STATE.lastBossChestReward = null;

    // Reset farm wave state so farm is ready and creeps spawn properly
    const currentSavedWave = ((RPG_STATE.profile?.dungeon_cleared || 0) % 20) + 1;
    ARENA.waveNumber = currentSavedWave;
    ARENA.totalCreepsSpawned = 0;
    ARENA.creepsKilledInWave = 0;
    ARENA.creepsNeededForWave = Math.min(32, 14 + Math.floor((ARENA.waveNumber - 1) * 1.0));
    ARENA.creepSpawnTimer = 0;
    if (ARENA.player) {
      ARENA.player.x = 65;
      ARENA.player.y = ARENA.roadY - 18;
      ARENA.player.isInvulnerable = 0;
    }

    const returnTab = ARENA._originTab || "coop";
    ARENA._originTab = null;
    setSubTab(returnTab);
    if (returnTab === "farm") {
      if (typeof spawnArenaCreep === "function") spawnArenaCreep();
    }
  }

  function startRaidBossActionBattle(bossId) {
    stopCoopPolling();
    stopArenaLoop();
    if (ARENA.startLoopTimeout) {
      clearTimeout(ARENA.startLoopTimeout);
      ARENA.startLoopTimeout = null;
    }

    ARENA._originTab = (RPG_STATE.activeTab && RPG_STATE.activeTab !== "farm") ? RPG_STATE.activeTab : "coop";
    ARENA._wasRaidBossBattle = true;

    RPG_STATE.coopRoomId = null;
    RPG_STATE.coopRoomData = null;

    const bossTmpls = {
      golem: { id: "golem", name: "Древний Гранитный Голем", icon: "🗿", baseHp: 75000, baseAtk: 416, defense: 35, scale: 1.35, gold: 800, xp: 600, desc: "[75 ТЫС. ХП] Каменный колосс глубин" },
      lich: { id: "lich", name: "Архилич Некрополя", icon: "☠️", baseHp: 225000, baseAtk: 1250, defense: 50, scale: 1.30, gold: 1500, xp: 1200, desc: "[225 ТЫС. ХП] Владыка темных заклятий" },
      tormentor: { id: "tormentor", name: "Древний Терзатель (Tormentor)", icon: "🔮", baseHp: 700000, baseAtk: 3888, defense: 75, scale: 1.30, gold: 2800, xp: 2200, desc: "[700 ТЫС. ХП] Отражает 35% урона" },
      dragon: { id: "dragon", name: "Дракон Инферно", icon: "🌋", baseHp: 2200000, baseAtk: 12222, defense: 105, scale: 1.50, gold: 4500, xp: 3500, desc: "[2.2 МЛН ХП] Огнедышащий титан" },
      pudge_boss: { id: "pudge_boss", name: "Мясник из Чрева (Pudge)", icon: "🪝", baseHp: 7500000, baseAtk: 41666, defense: 140, scale: 1.40, gold: 7500, xp: 5500, desc: "[7.5 МЛН ХП] Хук цепью, вонь гнили и пожирание" },
      faceless_void: { id: "faceless_void", name: "Хроно-Владыка (Faceless Void)", icon: "⏳", baseHp: 25000000, baseAtk: 138888, defense: 180, scale: 1.35, gold: 12000, xp: 8500, desc: "[25 МЛН ХП] Остановка времени и баши" },
      roshan: { id: "roshan", name: "Рошан (Roshan)", icon: "🐲", baseHp: 85000000, baseAtk: 472222, defense: 230, scale: 1.45, gold: 18000, xp: 13000, desc: "[85 МЛН ХП] Хозяин Ямы, дропает Рапиру и Сыр" },
      tidehunter: { id: "tidehunter", name: "Левиафан Бездны (Tidehunter)", icon: "🐙", baseHp: 300000000, baseAtk: 1666666, defense: 290, scale: 1.40, gold: 25000, xp: 18000, desc: "[300 МЛН ХП] Владыка пучин с якорным ударом и Раважем" },
      sf_boss: { id: "sf_boss", name: "Архидемон Nevermore", icon: "💀", baseHp: 1000000000, baseAtk: 5555555, defense: 370, scale: 1.35, gold: 35000, xp: 25000, desc: "[1 МИЛЛИАРД ХП] Пожиратель душ с черными коилами и Реквиемом" },
      necrophos: { id: "necrophos", name: "Чумной Владыка (Necrophos)", icon: "🧟", baseHp: 3500000000, baseAtk: 19444444, defense: 460, scale: 1.30, gold: 48000, xp: 34000, desc: "[3.5 МЛРД ХП] Аура мора истощает HP, Коса Смерти рубит" },
      terrorblade: { id: "terrorblade", name: "Демон Бездны (Terrorblade)", icon: "😈", baseHp: 12000000000, baseAtk: 66666666, defense: 570, scale: 1.40, gold: 65000, xp: 45000, desc: "[12 МЛРД ХП] Метаморфоза Тьмы и разрыв души Sunder" },
      invoker_boss: { id: "invoker_boss", name: "Демиург Арсенала (Invoker)", icon: "🧙‍♂️", baseHp: 42000000000, baseAtk: 233333333, defense: 700, scale: 1.25, gold: 85000, xp: 60000, desc: "[42 МЛРД ХП] Повелитель стихий, хаос-метеоров и ЭМИ" },
      chaos_knight: { id: "chaos_knight", name: "Всадник Хаоса (Chaos Knight)", icon: "🐎", baseHp: 150000000000, baseAtk: 833333333, defense: 860, scale: 1.45, gold: 110000, xp: 78000, desc: "[150 МЛРД ХП] Фантомы параллельных миров и криты" },
      dark_tormentor: { id: "dark_tormentor", name: "Тёмный Терзатель Бездны", icon: "💎", baseHp: 550000000000, baseAtk: 3055555555, defense: 1050, scale: 1.40, gold: 140000, xp: 100000, desc: "[550 МЛРД ХП] Отражает 50% урона и стреляет шипами тьмы" },
      storm_spirit: { id: "storm_spirit", name: "Громовой Дух (Storm Spirit)", icon: "⚡", baseHp: 2000000000000, baseAtk: 11111111111, defense: 1300, scale: 1.35, gold: 180000, xp: 125000, desc: "[2 ТРИЛЛИОНА ХП] Молниеносные перелеты через арену и ремнанты" },
      doom: { id: "doom", name: "Вестник Апокалипсиса (Lord Doom)", icon: "👹", baseHp: 7500000000000, baseAtk: 41666666666, defense: 1600, scale: 1.45, gold: 230000, xp: 160000, desc: "[7.5 ТРИЛЛИОНОВ ХП] Владыка Преисподней с роком и пламенем" },
      primal_beast: { id: "primal_beast", name: "Первобытный Титан (Primal Beast)", icon: "🦣", baseHp: 28000000000000, baseAtk: 155555555555, defense: 1950, scale: 1.60, gold: 290000, xp: 200000, desc: "[28 ТРИЛЛИОНОВ ХП] Сокрушитель материков с диким топотом" },
      phantom_roshan: { id: "phantom_roshan", name: "Призрачный Рошан Хаоса", icon: "👻", baseHp: 100000000000000, baseAtk: 555555555555, defense: 2400, scale: 1.55, gold: 360000, xp: 250000, desc: "[100 ТРИЛЛИОНОВ ХП] Восставший призрак Рошана с астральным Slam" },
      tinker_boss: { id: "tinker_boss", name: "Архиинженер (Omega Tinker)", icon: "🤖", baseHp: 350000000000000, baseAtk: 1944444444444, defense: 3000, scale: 1.45, gold: 450000, xp: 320000, desc: "[350 ТРИЛЛИОНОВ ХП] Ослепляющий лазер, микроракеты и марш роботов" },
      enigma: { id: "enigma", name: "Пожиратель Миров (Enigma Cosmic)", icon: "🌌", baseHp: 1200000000000000, baseAtk: 6666666666666, defense: 3800, scale: 1.35, gold: 600000, xp: 420000, desc: "[1.2 КВАДРИЛЛИОНА ХП!] Битва на века! Схлопывает пространство в Черную Дыру" }
    };

    const b = bossTmpls[bossId] || bossTmpls.golem;
    RPG_STATE.activeTab = "farm";
    RPG_STATE.farmMode = "arena";
    ARENA.isRaidBossBattle = true;
    ARENA.topDownMode = true;
    ARENA.currentRaidBoss = b;

    const stats = RPG_STATE.profile?.stats || {};
    const playerAtk = Math.max(30, Math.floor(((stats.min_atk || 30) + (stats.max_atk || 50)) / 2));
    const playerHp = Math.max(400, stats.hp_max || 400);

    const finalHp = b.baseHp;

    // 1. CREATE BOSS ENTITY (Slow, heavy, deliberate boss pacing)
    const raidBoss = {
      id: `raid_${b.id}_${Date.now()}`,
      name: b.name,
      icon: b.icon,
      x: 180,
      y: 95,
      radius: Math.floor(30 * (b.scale || 1.15)),
      speed: 1.45, // Fast, aggressive boss movement
      hp: finalHp,
      maxHp: finalHp,
      atk: b.baseAtk || 140,
      defense: b.defense !== undefined ? b.defense : 35,
      isBoss: true,
      isRaidBoss: true,
      bossType: b.id,
      isMinion: false,
      shielded: false,
      attackCooldown: 0,
      poise: 1600,
      maxPoise: 1600,
      state: "chase",
      stateTimer: 0,
      meleeCooldown: 40, // 0.65s initial wait
      chargeCooldown: 120, // 2s initial wait before first charge
      barrageCooldown: 80, // 1.3s initial wait before first barrage
      chargeAngle: 0,
      chargeVx: 0,
      chargeVy: 0,
      facing: 1,
      enrageTimer: 0,
      battleStartTime: Date.now(),
      enrageStage: "normal",
      jumpY: 0,
      jumpVY: 0
    };

    ARENA.bossEntity = raidBoss;
    ARENA.isBossActive = true;
    ARENA.bossPhase = 1;
    ARENA.creeps = [raidBoss]; // ONLY THE BOSS! NO CREEPS!
    ARENA.waveNumber = 20;
    ARENA.totalCreepsSpawned = 999;
    ARENA.creepsNeededForWave = 1;
    ARENA.creepsKilledInWave = 0;

    ARENA.playerProjectiles = [];
    ARENA.bossProjectiles = [];
    ARENA.dangerZones = [];
    ARENA.specialEffects = [];
    ARENA.floatingTexts = [];
    ARENA.dashGhosts = [];
    ARENA.waveState = "fighting";
    ARENA.bossArenaMode = true;
    ARENA.moveInput = { left: false, right: false };
    ARENA.dodgeCooldown = 0;
    ARENA.dodgeActive = 0;

    syncArenaPlayerStats();
    ARENA.player.currentHp = ARENA.player.maxHp;
    ARENA.player.currentMp = ARENA.player.maxMp;
    ARENA.player.isMoving = false;
    ARENA.player.isInvulnerable = 0;
    ARENA.player.isDead = false;
    ARENA.player.shootCooldown = 0;
    ARENA.player.facingAngle = -Math.PI / 2;
    ARENA.player.facing = 1;
    // 520 x 720 Spacious Arena Spawns
    ARENA.width = 520;
    ARENA.height = 720;
    ARENA.player.x = 260;
    ARENA.player.y = 620;
    ARENA.player.radius = 14;

    raidBoss.x = 260;
    raidBoss.y = 140;
    raidBoss.radius = 32;

    if ((ARENA.bossPartyMode || "trio") === "trio") {
      initBossCompanions();
      if (ARENA.bossCompanions[0]) {
        ARENA.bossCompanions[0].x = 220;
        ARENA.bossCompanions[0].y = 636;
        ARENA.bossCompanions[0].radius = 13;
      }
      if (ARENA.bossCompanions[1]) {
        ARENA.bossCompanions[1].x = 300;
        ARENA.bossCompanions[1].y = 636;
        ARENA.bossCompanions[1].radius = 13;
      }
    }

    // 2. Force full render of the DOM to show the Boss Fight header!
    RPG_STATE._forceFullRender = true;
    renderRoot();
    RPG_STATE._forceFullRender = false;

    const canvas = document.getElementById("rpg-action-canvas");
    if (canvas) {
      bindArenaCanvas(canvas);
      ARENA.width = 520;
      ARENA.height = 720;
      raidBoss.x = 260;
      raidBoss.y = 140;
      ARENA.player.x = 260;
      ARENA.player.y = 620;
    }

    // 3. Start unified, authoritative arena loop
    startArenaLoop();

    spawnFloatingText(ARENA.width / 2, 75, `👑 БОЙ С БОССОМ: ${b.name}! 👑`, "#ef4444");
    triggerHaptic("heavy");
  }

  function handlePlayerArenaDeath() {
    // AEGIS OF THE IMMORTAL RESURRECTION PASSIVE
    const relic = RPG_STATE.profile?.equipment?.relic;
    const isAegis = relic && (String(relic.name || "").toLowerCase().includes("aegis") || String(relic.name || "").toLowerCase().includes("эгида") || relic.icon === "🛡️" || relic.icon === "🥚");
    if (isAegis && !ARENA.aegisUsed && ARENA.player) {
      ARENA.aegisUsed = true;
      const pMax = ARENA.player.maxHp || 500;
      ARENA.player.currentHp = Math.floor(pMax * 0.65);
      ARENA.player.isInvulnerable = 60;
      spawnFloatingText(ARENA.player.x, ARENA.player.y - 35, "✨ ВОСКРЕШЕНИЕ ЭГИДОЙ! (+65% HP)", "#facc15");
      triggerHaptic("heavy");
      return;
    }

    // WRAITH KING PERK: Reincarnation (Revives with 75% HP + 50% slow on enemies)
    if (window.hasTalentPerk && window.hasTalentPerk("perk_reincarnation") && !ARENA.wkReincarnationUsed && ARENA.player) {
      ARENA.wkReincarnationUsed = true;
      const pMax = ARENA.player.maxHp || 500;
      ARENA.player.currentHp = Math.floor(pMax * 0.75);
      ARENA.player.isInvulnerable = 90;
      ARENA.player.isDead = false;
      spawnFloatingText(ARENA.player.x, ARENA.player.y - 35, "👑 ПЕРЕРОЖДЕНИЕ КОРОЛЯ! (+75% HP)", "#22c55e");
      triggerHaptic("heavy");
      if (ARENA.creeps) {
        ARENA.creeps.forEach(c => {
          c.slowTimer = 240;
          c.speed = Math.max(0.4, (c.baseSpeed || c.speed || 1.5) * 0.5);
        });
      }
      return;
    }

    // PUDGE PERK: Undying Meat (Survives with 35% HP + 2s invuln + poison explosion)
    if (window.hasTalentPerk && window.hasTalentPerk("perk_undying_meat") && !ARENA.pudgeUndyingUsed && ARENA.player) {
      ARENA.pudgeUndyingUsed = true;
      const pMax = ARENA.player.maxHp || 500;
      ARENA.player.currentHp = Math.floor(pMax * 0.35);
      ARENA.player.isInvulnerable = 120;
      ARENA.player.isDead = false;
      spawnFloatingText(ARENA.player.x, ARENA.player.y - 35, "🥩 БЕССМЕРТНАЯ ТУША! (ВЗРЫВ ЯДА)", "#84cc16");
      triggerHaptic("heavy");
      const poisonBurst = Math.max(50, Math.floor((RPG_STATE.profile?.stats?.attack || 50) * 3));
      if (ARENA.isBossActive && ARENA.bossEntity && ARENA.bossEntity.hp > 0) {
        applyDamageToBoss(ARENA.bossEntity, poisonBurst, true);
        spawnFloatingText(ARENA.bossEntity.x, ARENA.bossEntity.y - 25, `☣️ ВЗРЫВ ЯДА -${poisonBurst}!`, "#84cc16");
      }
      if (ARENA.creeps) {
        ARENA.creeps.forEach(c => {
          if (c.hp > 0) {
            safeDamageCreep(c, poisonBurst);
            spawnFloatingText(c.x, c.y - 20, `☣️ -${poisonBurst}`, "#84cc16");
          }
        });
      }
      return;
    }

    if (ARENA.player) {
      ARENA.player.currentHp = 0;
      ARENA.player.isInvulnerable = 0;
      ARENA.player.isDead = true;
    }

    if (ARENA.isRaidBossBattle) {
      ARENA.waveState = "boss_defeat";
      triggerHaptic("error");
      spawnFloatingText(ARENA.width / 2, 95, "💀 ВАШ ГЕРОЙ ПАЛ В РЕЙДЕ!", "#ef4444");
      ARENA.playerProjectiles = [];
      ARENA.bossProjectiles = [];
      if (ARENA.bossEntity) {
        ARENA.bossEntity.state = "idle";
        ARENA.bossEntity.stateTimer = 999999;
      }
      return;
    }

    ARENA.waveState = "retry_prompt"; // NEVER floor_clear!
    triggerHaptic("error");
    spawnFloatingText(ARENA.width / 2, 100, "💀 ВАШ ГЕРОЙ ПАЛ!", "#ef4444");

    setTimeout(() => {
      const stats = RPG_STATE.profile?.stats || {};
      ARENA.player.maxHp = Math.max(450, stats.hp_max || 450);
      ARENA.player.currentHp = ARENA.player.maxHp;
      ARENA.player.isDead = false;
      ARENA.player.maxMp = Math.max(80, stats.mp_max || 80);
      ARENA.player.currentMp = ARENA.player.maxMp;
      ARENA.creeps = [];
      ARENA.pickups = [];
      ARENA.bossProjectiles = [];
      ARENA.playerProjectiles = [];
      ARENA.alliedMinions = [];
      ARENA.specialEffects = [];
      ARENA.isBossActive = false;
      ARENA.topDownMode = false;
      ARENA.bossArenaMode = false;
      ARENA.bossEntity = null;
      ARENA.bossPhase = 0;
      ARENA.blockWindowActive = false;
      ARENA.qteActive = false;
      ARENA.creepsKilledInWave = 0;
      ARENA.totalCreepsSpawned = 0;
      ARENA.waveNumber = 1;
      ARENA.player.x = 65;
      ARENA.player.y = ARENA.roadY - 18;
      ARENA.waveState = "retry_prompt";
    }, 1200);
  }

  function checkLevelUpInArena() {
    const p = RPG_STATE.profile;
    if (!p) return;
    const needed = 120 + ((p.level || 1) - 1) * 160;
    if (p.xp >= needed) {
      p.xp -= needed;
      p.level = (p.level || 1) + 1;
      p.stat_points = (p.stat_points || 0) + 1;
      if (p.level % 5 === 0) p.talent_points = (p.talent_points || 0) + 1;
      showLevelUpToast(p.level);
      spawnFloatingText(ARENA.player.x + 30, ARENA.player.y - 45, `🎉 УРОВЕНЬ ${p.level}! (+1 очко)`, "#facc15");
    }
  }

  function spawnFloatingText(x, y, text, color = "#ffffff") {
    if (!ARENA.floatingTexts) ARENA.floatingTexts = [];
    if (ARENA.floatingTexts.length >= 24) {
      ARENA.floatingTexts.shift(); // Drop oldest text to avoid canvas lag
    }
    ARENA.floatingTexts.push({ x, y, text, color, opacity: 1.0 });
  }
