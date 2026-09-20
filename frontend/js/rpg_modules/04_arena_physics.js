  function updateArena() {
    ARENA.frameCount = (ARENA.frameCount || 0) + 1;
    const p = ARENA.player;

    // Hitstop freeze (Sekiro/Hollow Knight impact pause)
    if (ARENA.hitstop > 0) {
      ARENA.hitstop--;
      updateFloatingTexts();
      return;
    }

    // Decrement parry & block timers
    if (ARENA.parryWindow > 0) ARENA.parryWindow--;
    if (ARENA.player.blockTimer > 0) {
      ARENA.player.blockTimer--;
      if (ARENA.player.blockTimer <= 0) ARENA.player.isBlocking = false;
    }

    // Always update physical loot coins & falling legendary chest
    updatePhysicalCoins();
    updateFallingChest();
    updatePetLogic();

    // Sync DOM action buttons smoothly (cooldowns & block alert)
    if (ARENA.frameCount % 6 === 0) {
      const s1El = document.getElementById("rpg-cd-skill1");
      if (s1El) {
        const s1Sec = ARENA.skill1Cooldown > 0 ? Math.ceil(ARENA.skill1Cooldown / 60) : 0;
        const txt = s1Sec > 0 ? `${s1Sec}с` : "Скилл 1";
        if (s1El.textContent !== txt) s1El.textContent = txt;
        const btn1 = document.getElementById("rpg-btn-skill1");
        if (btn1) btn1.style.opacity = s1Sec > 0 ? "0.6" : "1";
      }
      const potEl = document.getElementById("rpg-cd-potion");
      if (potEl) {
        const potSec = ARENA.potionCooldown > 0 ? Math.ceil(ARENA.potionCooldown / 60) : 0;
        const txt = potSec > 0 ? `${potSec}с` : "";
        if (potEl.textContent !== txt) potEl.textContent = txt;
        const btnPot = document.getElementById("rpg-btn-potion");
        if (btnPot) btnPot.style.opacity = potSec > 0 ? "0.6" : "1";
      }
      const ultEl = document.getElementById("rpg-cd-ult");
      if (ultEl) {
        let txt = "Ульта";
        const hClass = (RPG_STATE.profile?.hero_class || "").toLowerCase();
        if (hClass === "leshrac") {
          if (p.largoRhapsodyActive) {
            txt = "ВЫКЛ";
          } else {
            const ultSec = ARENA.ultCooldown > 0 ? Math.ceil(ARENA.ultCooldown / 60) : 0;
            txt = ultSec > 0 ? `${ultSec}с` : "ВКЛ";
          }
        } else {
          const ultSec = ARENA.ultCooldown > 0 ? Math.ceil(ARENA.ultCooldown / 60) : 0;
          txt = ultSec > 0 ? `${ultSec}с` : "Ульта";
        }
        if (ultEl.textContent !== txt) ultEl.textContent = txt;
        const btnUlt = document.getElementById("rpg-btn-ult");
        if (btnUlt) {
          if (hClass === "leshrac" && p.largoRhapsodyActive) {
            btnUlt.style.opacity = "1";
            btnUlt.style.borderColor = "#22c55e";
          } else {
            const ultSec = ARENA.ultCooldown > 0 ? Math.ceil(ARENA.ultCooldown / 60) : 0;
            btnUlt.style.opacity = ultSec > 0 ? "0.6" : "1";
            btnUlt.style.borderColor = "";
          }
        }
      }

      // Sync Active Item Cooldowns
      const activeItems = getEquippedActiveItems();
      activeItems.forEach((act, idx) => {
        const cdEl = document.getElementById(`rpg-cd-item-${idx}`);
        const btnEl = document.getElementById(`rpg-btn-item-${idx}`);
        const cdFrames = ARENA.itemCooldowns?.[act.key] || 0;
        const cdSec = cdFrames > 0 ? Math.ceil(cdFrames / 60) : 0;
        const hotkey = idx === 0 ? "R" : idx === 1 ? "T" : `${idx + 1}`;
        if (cdEl) {
          const txt = cdSec > 0 ? `КД ${cdSec}с` : `[${hotkey}] Готов ⚡`;
          if (cdEl.textContent !== txt) cdEl.textContent = txt;
        }
        if (btnEl) {
          btnEl.style.opacity = cdSec > 0 ? "0.6" : "1";
        }
      });
      const blockBtn = document.getElementById("rpg-btn-block");
      if (blockBtn) {
        if (ARENA.blockWindowActive) {
          blockBtn.className = "w-11 h-11 rounded-2xl bg-blue-500 border-2 border-white animate-bounce shadow-blue-500/50 text-white font-black text-sm flex flex-col items-center justify-center shadow-lg active:scale-90 transition-all";
        } else {
          blockBtn.className = "w-11 h-11 rounded-2xl bg-slate-800/90 border border-slate-600 text-white font-black text-sm flex flex-col items-center justify-center shadow-lg active:scale-90 transition-all";
        }
      }
    }
    // Non-fighting state handling
    if (ARENA.waveState !== "fighting") {
      if (ARENA.waveState === "wave_clear" || ARENA.waveState === "boss_intro") {
        ARENA.waveTransitionTimer--;
        if (ARENA.waveTransitionTimer <= 0) {
          if (ARENA.waveState === "wave_clear") {
            if (ARENA.autoAdvanceWaves && !RPG_STATE.activeChestModal) {
              ARENA.waveState = "prompt";
              confirmNextWave();
            } else {
              ARENA.waveState = "prompt";
            }
          } else {
            ARENA.waveState = "fighting";
          }
        }
      }
      updatePickups();
      updateFloatingTexts();
      updateClouds();
      return;
    }

    const stats = RPG_STATE.profile?.stats || {};

    // =========================================================================
    // TOP-DOWN ARCHERO-STYLE UPDATE LOOP
    // =========================================================================
    if (ARENA.topDownMode || ARENA.isRaidBossBattle) {
      // 0. Update player status effects (Stun, Freeze, Slow, DoTs)
      if (p.stunTimer > 0) p.stunTimer--;
      if (p.freezeTimer > 0) p.freezeTimer--;
      const isImmobilized = (p.stunTimer > 0) || (p.freezeTimer > 0) || p.isFrozenInTime;

      // 1. Dynamic walking speed (slowed if slowTimer active)
      let moveSpeed = 3.35 * (1.0 + Math.min(0.25, (stats.agility || 10) * 0.002));
      if (p.slowTimer > 0) {
        p.slowTimer--;
        moveSpeed *= (p.slowRatio || 0.45);
      }

      if (!isImmobilized && ARENA.player.isMoving && (Math.abs(ARENA.joystick.dx) > 0.06 || Math.abs(ARENA.joystick.dy) > 0.06)) {
        p.x += ARENA.joystick.dx * moveSpeed;
        p.y += ARENA.joystick.dy * moveSpeed;
        p.x = Math.max(30, Math.min(490, p.x));
        p.y = Math.max(40, Math.min(680, p.y));
      }

      // Continuous Auto-Fire (Run & Gun) — blocked when stunned or frozen!
      const target = (ARENA.bossEntity && ARENA.bossEntity.hp > 0) ? ARENA.bossEntity : (ARENA.creeps.find(c => c.hp > 0) || null);
      if (target && target.hp > 0 && !isImmobilized) {
        // Hero faces the boss in combat
        const toTargetAngle = Math.atan2(target.y - p.y, target.x - p.x);
        p.facingAngle = toTargetAngle;
        p.facing = target.x >= p.x ? 1 : -1;
        p.shootCooldown = (p.shootCooldown || 0) - 1;

        if (p.shootCooldown <= 0) {
          if (p.blindTimer > 0) {
            p.blindTimer--;
            if (Math.random() < 0.65) {
              p.shootCooldown = 26;
              spawnFloatingText(p.x, p.y - 20, "🔴 ПРОМАХ (ОСЛЕПЛЕНИЕ)!", "#ef4444");
            } else {
              fireTopDownAttack(null);
            }
          } else {
            fireTopDownAttack(null);
          }
        }
      }

      // Burn DoT ticking
      if (p.burnTimer > 0) {
        p.burnTimer--;
        if (ARENA.frameCount % 24 === 0) {
          const bDmg = Math.max(10, p.burnDmg || Math.floor(calculateBossAttackDamage(ARENA.bossEntity, 0.16)));
          applyDamageToPlayer(bDmg, "burn");
          spawnFloatingText(p.x, p.y - 20, `🔥 ОЖОГ -${bDmg}`, "#f97316");
          if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
        }
      }
      // Poison DoT ticking
      if (p.poisonTimer > 0) {
        p.poisonTimer--;
        if (ARENA.frameCount % 24 === 0) {
          const psDmg = Math.max(10, p.poisonDmg || Math.floor(calculateBossAttackDamage(ARENA.bossEntity, 0.16)));
          applyDamageToPlayer(psDmg, "poison");
          spawnFloatingText(p.x, p.y - 20, `☣️ ЯД -${psDmg}`, "#84cc16");
          if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
        }
      }
      if (p.silenceTimer > 0) p.silenceTimer--;

      // 2. Dash Cooldown & Invulnerability
      if (ARENA.dodgeCooldown > 0) ARENA.dodgeCooldown--;
      if (p.isInvulnerable > 0) p.isInvulnerable--;

      // 3. Update Top-Down Projectiles with Magnetic Tracking (Never misses moving boss!)
      for (let pi = ARENA.playerProjectiles.length - 1; pi >= 0; pi--) {
        const proj = ARENA.playerProjectiles[pi];
        if (proj.type === "topdown_shot") {
          // Magnetic guidance towards target so shots curve slightly and hit reliably!
          if (proj.target && proj.target.hp > 0) {
            const idealAng = Math.atan2(proj.target.y - proj.y, proj.target.x - proj.x);
            const curAng = Math.atan2(proj.vy, proj.vx);
            let dAng = idealAng - curAng;
            while (dAng < -Math.PI) dAng += Math.PI * 2;
            while (dAng > Math.PI) dAng -= Math.PI * 2;
            const steer = curAng + dAng * 0.38;
            proj.vx = Math.cos(steer) * proj.speed;
            proj.vy = Math.sin(steer) * proj.speed;
          }

          proj.x += proj.vx;
          proj.y += proj.vy;
          proj.distTraveled += proj.speed;

          // Generous hit check against boss (+20px buffer ensures zero whiffs)
          const boss = ARENA.bossEntity;
          if (boss && boss.hp > 0 && Math.hypot(proj.x - boss.x, proj.y - boss.y) < (boss.radius + proj.radius + 20)) {
            const actualDmg = applyDamageToBoss(boss, proj.dmg, proj.isCrit);
            if (boss.poise !== undefined) boss.poise = Math.max(0, boss.poise - (proj.isCrit ? 15 : 8));
            spawnFloatingText(boss.x + (Math.random() * 24 - 12), boss.y - 20, `${proj.isCrit ? "💥 КРИТ! " : ""}-${actualDmg}`, proj.isCrit ? "#ef4444" : "#facc15");
            triggerHaptic(proj.isCrit ? "heavy" : "light");
            ARENA.playerProjectiles.splice(pi, 1);
            continue;
          }

          // Check hit against other creeps
          let hitCreep = false;
          for (const c of ARENA.creeps) {
            if (c !== boss && c.hp > 0 && Math.hypot(proj.x - c.x, proj.y - c.y) < (c.radius + proj.radius + 12)) {
              if (c.isBoss) {
                applyDamageToBoss(c, proj.dmg, proj.isCrit);
              } else {
                safeDamageCreep(c, proj.dmg, false);
              }
              spawnFloatingText(c.x, c.y - 15, `-${proj.dmg}`, "#facc15");
              hitCreep = true;
              break;
            }
          }
          if (hitCreep || proj.distTraveled > proj.maxDist || proj.x < -40 || proj.x > ARENA.width + 40 || proj.y < -40 || proj.y > ARENA.height + 40) {
            ARENA.playerProjectiles.splice(pi, 1);
          }
        }
      }

      // 4. EPIC BOSS ENCOUNTER AI (Dynamic Chase, Signature Abilities & Ultimates)
      const boss = ARENA.bossEntity;
      if (boss && boss.hp > 0) {
        if (typeof updateCustomBossAI === "function") {
          updateCustomBossAI(boss, p, ARENA);
        }
        if (boss.state === "telegraph_melee") {
          boss.stateTimer--;
          if (boss.stateTimer <= 0) {
            boss.state = "melee_smash";
            boss.stateTimer = 22;
            ARENA.cameraTrauma = Math.min(1.0, (ARENA.cameraTrauma || 0) + 0.35);
            triggerHaptic("heavy");
            spawnFloatingText(boss.x, boss.y - 30, "💥 УДАР!", "#ef4444");

            // Damage player if in range (anti-one-shot protected!)
            if (Math.hypot(p.x - boss.x, p.y - boss.y) < (boss.radius + p.radius + 20) && !p.isInvulnerable) {
              const rawDmg = calculateBossAttackDamage(boss, 1.0);
              const actualDmg = applyDamageToPlayer(rawDmg, "melee");
              spawnFloatingText(p.x, p.y - 20, `💥 -${actualDmg}`, "#ef4444");
              if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
            }
            // Damage companions if in range
            for (const comp of (ARENA.bossCompanions || [])) {
              if (comp.hp > 0 && Math.hypot(comp.x - boss.x, comp.y - boss.y) < (boss.radius + 32)) {
                comp.hp = Math.max(0, comp.hp - calculateBossAttackDamage(boss, 0.8));
              }
            }
          }
        }
        else if (boss.state === "melee_smash") {
          boss.stateTimer--;
          if (boss.stateTimer <= 0) boss.state = "chase";
        }
        else if (boss.state === "telegraph_charge") {
          boss.stateTimer--;
          if (boss.stateTimer <= 0) {
            boss.state = "charging";
            boss.stateTimer = 90; // Slower rush duration
          }
        }
        else if (boss.state === "charging") {
          boss.stateTimer--;
          boss.x += boss.chargeVx;
          boss.y += boss.chargeVy;

          // Charge speed trail
          if (ARENA.frameCount % 4 === 0 && ARENA.dashGhosts) {
            ARENA.dashGhosts.push({
              x: boss.x,
              y: boss.y,
              radius: boss.radius,
              alpha: 0.4,
              color: "#ef4444"
            });
          }

          // Hit player during charge!
          if (Math.hypot(p.x - boss.x, p.y - boss.y) < (boss.radius + p.radius + 10) && !p.isInvulnerable) {
            const rawDmg = calculateBossAttackDamage(boss, 1.35);
            const actualDmg = applyDamageToPlayer(rawDmg, "charge");
            // Gentle knockback player away
            p.x += Math.cos(boss.chargeAngle) * 20;
            p.y += Math.sin(boss.chargeAngle) * 20;
            spawnFloatingText(p.x, p.y - 25, `💥 ТАРАН! -${actualDmg}`, "#ef4444");
            ARENA.cameraTrauma = 0.4;
            triggerHaptic("heavy");
            if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
          }

          // Hit arena wall -> STUNNED for 1.5 seconds! (Reward player for baiting charge into wall)
          if (boss.x <= 32 || boss.x >= ARENA.width - 32 || boss.y <= 40 || boss.y >= ARENA.height - 40) {
            boss.state = "stunned";
            boss.stateTimer = 90; // ~1.5s stun
            ARENA.cameraTrauma = 0.5;
            triggerHaptic("heavy");
            spawnFloatingText(boss.x, boss.y - 35, "💫 БОСС ВРЕЗАЛСЯ В СТЕНУ! ОШЕЛОМЛЕН!", "#facc15");
          } else if (boss.stateTimer <= 0) {
            boss.state = "chase";
          }
        }
        else if (boss.state === "stunned") {
          boss.stateTimer--;
          if (boss.stateTimer <= 0) boss.state = "chase";
        }
        else if (boss.state === "barrage") {
          boss.stateTimer--;
          if (boss.stateTimer <= 0) boss.state = "chase";
        }

        // Clamp boss inside 520x720 arena
        boss.x = Math.max(35, Math.min(485, boss.x));
        boss.y = Math.max(45, Math.min(675, boss.y));

        // Direct contact damage if player touches boss while standing
        if (Math.hypot(p.x - boss.x, p.y - boss.y) < (boss.radius + p.radius) && !p.isInvulnerable) {
          if ((ARENA.frameCount % 25) === 0) {
            const rawDmg = calculateBossAttackDamage(boss, 0.65);
            const actualDmg = applyDamageToPlayer(rawDmg, "contact");
            spawnFloatingText(p.x, p.y - 20, `💥 -${actualDmg}`, "#ef4444");
            triggerHaptic("medium");
            if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
          }
        }
      }

      // Update Boss Projectiles (Floating Rockets & Ability Missiles)
      for (let bpi = ARENA.bossProjectiles.length - 1; bpi >= 0; bpi--) {
        const bp = ARENA.bossProjectiles[bpi];
        bp.x += (bp.vx || 0);
        bp.y += (bp.vy || 0);
        bp.timer = (bp.timer || 240) - 1;

        // Hit player (anti-one-shot protected!)
        if (Math.hypot(p.x - bp.x, p.y - bp.y) < (p.radius + bp.radius) && !p.isInvulnerable) {
          const rawDmg = bp.dmg || calculateBossAttackDamage(ARENA.bossEntity, 0.85);
          const actualDmg = applyDamageToPlayer(rawDmg, bp.label || "projectile");
          const lbl = bp.label ? `${bp.label} ` : "💥 СНАРЯД ";
          spawnFloatingText(p.x, p.y - 20, `${lbl}-${actualDmg}`, bp.color || "#ef4444");
          triggerHaptic("heavy");
          ARENA.cameraTrauma = Math.min(1.0, (ARENA.cameraTrauma || 0) + 0.25);
          if (typeof applyStatusEffectToPlayer === "function") {
            applyStatusEffectToPlayer(bp);
          }
          ARENA.bossProjectiles.splice(bpi, 1);
          if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
          continue;
        }

        // Hit companions
        for (const comp of (ARENA.bossCompanions || [])) {
          if (comp.hp > 0 && Math.hypot(comp.x - bp.x, comp.y - bp.y) < (comp.radius + bp.radius)) {
            comp.hp = Math.max(0, comp.hp - (bp.dmg || 40));
            ARENA.bossProjectiles.splice(bpi, 1);
            break;
          }
        }

        // Out of bounds or expired
        if (bp.timer <= 0 || bp.x < 0 || bp.x > ARENA.width || bp.y < 0 || bp.y > ARENA.height) {
          ARENA.bossProjectiles.splice(bpi, 1);
        }
      }

      // 5. Update Dash Ghost Trails
      if (ARENA.dashGhosts) {
        for (let gi = ARENA.dashGhosts.length - 1; gi >= 0; gi--) {
          const g = ARENA.dashGhosts[gi];
          g.alpha -= 0.045;
          if (g.alpha <= 0) ARENA.dashGhosts.splice(gi, 1);
        }
      }
    }

    // ===== BOSS ARENA: Side-Scroller Movement (Only when NOT in Top-Down mode!) =====
    if (ARENA.bossArenaMode && !ARENA.topDownMode && !ARENA.isRaidBossBattle) {
      const moveSpeed = 3.2;
      if (ARENA.dodgeActive > 0) {
        // Dodge roll: fast movement + i-frame
        ARENA.dodgeActive--;
        p.x += ARENA.dodgeDir * 7.5;
        p.isInvulnerable = 1;
        // Spawn after-images
        if (ARENA.dodgeActive % 3 === 0 && ARENA.dashGhosts) {
          ARENA.dashGhosts.push({ x: p.x, y: p.y, radius: p.radius, alpha: 0.45, heroClass: (RPG_STATE.profile?.hero_class || "pudge").toLowerCase() });
        }
        if (ARENA.dodgeActive <= 0) {
          p.isInvulnerable = 0;
        }
      } else {
        if (ARENA.moveInput.left) { p.x -= moveSpeed; p.facing = -1; }
        if (ARENA.moveInput.right) { p.x += moveSpeed; p.facing = 1; }
      }
      // Clamp to arena bounds
      p.x = Math.max(25, Math.min(ARENA.width - 25, p.x));
      // Dodge cooldown
      if (ARENA.dodgeCooldown > 0) ARENA.dodgeCooldown--;
    }

    // Update danger zones (Global: Top-Down, Raid Bosses, Dungeon Waves, Side-Scroller)
    if (ARENA.dangerZones && ARENA.dangerZones.length > 0) {
      for (let dz = ARENA.dangerZones.length - 1; dz >= 0; dz--) {
        const zone = ARENA.dangerZones[dz];
        zone.timer--;
        if (zone.timer <= 0) {
          if (zone.phase === "telegraph") {
            zone.phase = "active";
            zone.timer = zone.activeFrames || 14;
          } else {
            ARENA.dangerZones.splice(dz, 1);
            continue;
          }
        }
        // Active damage zone collision
        if (zone.phase === "active") {
          let inZone = false;
          if (zone.type === "rect") {
            inZone = p.x > zone.x && p.x < zone.x + zone.w && p.y > zone.y - 30 && p.y < zone.y + zone.h + 30;
          } else if (zone.type === "circle") {
            inZone = Math.hypot(p.x - zone.cx, p.y - zone.cy) < zone.r + p.radius;
          } else if (zone.type === "line") {
            const l2 = (zone.x2 - zone.x1) * (zone.x2 - zone.x1) + (zone.y2 - zone.y1) * (zone.y2 - zone.y1);
            let d = 9999;
            if (l2 === 0) {
              d = Math.hypot(p.x - zone.x1, p.y - zone.y1);
            } else {
              let t = ((p.x - zone.x1) * (zone.x2 - zone.x1) + (p.y - zone.y1) * (zone.y2 - zone.y1)) / l2;
              t = Math.max(0, Math.min(1, t));
              d = Math.hypot(p.x - (zone.x1 + t * (zone.x2 - zone.x1)), p.y - (zone.y1 + t * (zone.y2 - zone.y1)));
            }
            inZone = d < ((zone.width || 34) / 2) + p.radius;
          } else if (zone.type === "cone") {
            const d = Math.hypot(p.x - (zone.cx || zone.x), p.y - (zone.cy || zone.y));
            if (d <= (zone.range || zone.length || 180) + p.radius) {
              let diff = Math.atan2(p.y - (zone.cy || zone.y), p.x - (zone.cx || zone.x)) - (zone.angle || 0);
              while (diff > Math.PI) diff -= Math.PI * 2;
              while (diff < -Math.PI) diff += Math.PI * 2;
              if (Math.abs(diff) <= ((zone.spread || 0.8) / 2)) inZone = true;
            }
          }

          if (inZone && !p.isInvulnerable) {
            let shouldHit = false;
            if (zone.isDot) {
              zone.lastHitFrame = zone.lastHitFrame || 0;
              if (ARENA.frameCount - zone.lastHitFrame >= 20) {
                zone.lastHitFrame = ARENA.frameCount;
                shouldHit = true;
              }
            } else if (!zone.hitPlayer) {
              zone.hitPlayer = true;
              shouldHit = true;
            }

            if (shouldHit) {
              const rawDmg = Math.floor(zone.damage || calculateBossAttackDamage(ARENA.bossEntity, 1.0));
              const actualDmg = applyDamageToPlayer(rawDmg, zone.label || "danger_zone");
              const lbl = zone.label ? `${zone.label} ` : "";
              spawnFloatingText(p.x, p.y - 25, `${lbl}-${actualDmg}`, zone.color || "#ef4444");
              ARENA.cameraTrauma = Math.min(1.0, (ARENA.cameraTrauma || 0) + 0.35);
              triggerHaptic("heavy");

              // Apply CC & Status effects to Player
              if (typeof applyStatusEffectToPlayer === "function") {
                if (zone.effect) applyStatusEffectToPlayer(zone.effect);
                if (zone.stun) applyStatusEffectToPlayer({ stun: zone.stun });
                if (zone.slow || zone.slowEffect) applyStatusEffectToPlayer({ slow: true, slowDuration: zone.slowDuration || 90, slowRatio: zone.slowRatio || zone.slowEffect || 0.45 });
                if (zone.silence) applyStatusEffectToPlayer({ silence: zone.silence });
                if (zone.burn) applyStatusEffectToPlayer({ burn: true, burnDuration: zone.burnDuration, burnDmg: zone.burnDmg });
                if (zone.poison) applyStatusEffectToPlayer({ poison: true, poisonDuration: zone.poisonDuration, poisonDmg: zone.poisonDmg });
                if (zone.blind) applyStatusEffectToPlayer({ blind: true, blindDuration: zone.blindDuration });
              }

              if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
            }
          }
        }
      }
    }


    // Passive Regen
    p.currentHp = Math.min(p.maxHp, p.currentHp + (stats.hp_regen || 1) / 60);
    p.currentMp = Math.min(p.maxMp, p.currentMp + (stats.mp_regen || 1) / 60);

    // Passive Items Update (Radiance, Heart of Tarrasque)
    if (ARENA.frameCount % 30 === 0) {
      const eq = RPG_STATE.profile?.equipment || {};
      const hasRadiance = Object.values(eq).some(it => it && (it.name?.includes("Radiance") || it.name?.includes("Сияние") || it.bonus?.radiance_burn));
      if (hasRadiance) {
        const radDmg = Math.floor((stats.max_atk || 30) * 0.45 + 65);
        if (ARENA.isRaidBossBattle && ARENA.bossEntity && ARENA.bossEntity.hp > 0) {
          const rd = applyDamageToBoss(ARENA.bossEntity, radDmg);
          spawnFloatingText(ARENA.bossEntity.x, ARENA.bossEntity.y - 18, `🔥 РАДИАНС -${rd}`, "#ea580c");
        } else {
          for (const c of ARENA.creeps) {
            if (c.isBoss) {
              const rd = applyDamageToBoss(c, radDmg);
              spawnFloatingText(c.x, c.y - 18, `🔥 РАДИАНС -${rd}`, "#ea580c");
            } else {
              c.hp -= radDmg;
              spawnFloatingText(c.x, c.y - 18, `🔥 РАДИАНС -${radDmg}`, "#ea580c");
            }
          }
        }
      }
      if (ARENA.frameCount % 60 === 0) {
        const hasTarrasque = Object.values(eq).some(it => it && (it.name?.includes("Tarrasque") || it.name?.includes("Тарраск") || it.bonus?.pct_hp_regen));
        if (hasTarrasque) {
          const heal = Math.min(Math.floor(p.maxHp * 0.015), 6000);
          p.currentHp = Math.min(p.maxHp, p.currentHp + heal);
          spawnFloatingText(p.x, p.y - 30, `+${heal} HP (ТАРАСКА) ❤️`, "#22c55e");
        }
      }
    }

    // Cooldown timers
    if (p.attackCooldown > 0) {
      p.attackCooldown--;
      if (p.attackCooldown <= 0 && p.attackQueued) {
        p.attackQueued = false;
        playerSlashAttack();
      }
    }
    if (ARENA.skill1Cooldown > 0) ARENA.skill1Cooldown--;
    if (ARENA.ultCooldown > 0) ARENA.ultCooldown--;
    if (ARENA.potionCooldown > 0) ARENA.potionCooldown--;

    // Decrement item cooldowns
    if (ARENA.itemCooldowns) {
      for (const k in ARENA.itemCooldowns) {
        if (ARENA.itemCooldowns[k] > 0) ARENA.itemCooldowns[k]--;
      }
    }
    // Active item buff timers
    if (ARENA.player.bkbActive > 0) ARENA.player.bkbActive--;
    if (ARENA.player.satanicActive > 0) ARENA.player.satanicActive--;
    if (ARENA.player.eulActive > 0) ARENA.player.eulActive--;
    if (p.slashAnimation) {
      p.slashAnimation.timer--;
      if (p.slashAnimation.timer <= 0) p.slashAnimation = null;
    }

    // Active buffs/effects timers
    if (p.fleshHeapActive > 0) p.fleshHeapActive--;
    if (p.bladeDanceActive > 0) p.bladeDanceActive--;
    if (p.counterspellActive > 0) p.counterspellActive--;
    if (p.croakTimer > 0) p.croakTimer--;

    // Largo Amphibian Rhapsody: переключаемая стойка (ВКЛ / ВЫКЛ, длится бесконечно пока есть мана).
    // Каждые 0.5 секунды (30 кадров) тратит ману, хилит Ларго и наносит AoE-урон вокруг!
    if (p.largoRhapsodyActive) {
      const rhapsodyInterval = (window.hasTalentPerk && window.hasTalentPerk("perk_pulse_storm")) ? 15 : 30;
      if (!p.largoRhapsodyTickTimer || p.largoRhapsodyTickTimer <= 0) {
        p.largoRhapsodyTickTimer = rhapsodyInterval;
      }
      p.largoRhapsodyTickTimer--;

      if (p.largoRhapsodyTickTimer <= 0) {
        p.largoRhapsodyTickTimer = rhapsodyInterval;

        // Расход маны за тик: 5 MP (или -60% при активном Кваканье Гения -> 2 MP!)
        let tickCost = 5;
        if (p.croakTimer > 0) {
          tickCost = Math.floor(tickCost * 0.4); // 2 MP
        }

        // Проверка: хватает ли маны на очередной такт
        if (p.currentMp < tickCost) {
          p.largoRhapsodyActive = false;
          spawnFloatingText(p.x, p.y - 30, "Мана закончилась! Рапсодия выключена", "#94a3b8");
          triggerHaptic("error");
        } else {
          p.currentMp -= tickCost;
          spawnFloatingText(p.x, p.y - 48, `⚡ -${tickCost} MP`, "#38bdf8");

          let ultMult = p.largoRhapsodyDmgMult || 1.0;
          if (p.edictTimer > 0) {
            ultMult += 2.5; // +250% урон от ульты пока активен 1 скилл
          }
          const spellAmp = (stats.spell_amp !== undefined ? stats.spell_amp : ((p.maxMp || 100) * 0.2));

          // 1. Исцеление Ларго (разделено на 4 для тика 0.5с): сбалансировано
          const healAmt = Math.max(12, Math.min(Math.floor(p.maxHp * 0.01), 6000) + Math.min(4000, Math.floor((stats.int || 20) * 0.25)));
          p.currentHp = Math.min(p.maxHp, p.currentHp + healAmt);
          spawnFloatingText(p.x, p.y - 30, `💚 +${healAmt} ХП (РАПСОДИЯ)`, "#22c55e");

          // 2. Гармоническая визуальная волна
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
          ARENA.cameraTrauma = Math.min(1.0, (ARENA.cameraTrauma || 0) + 0.25);
          triggerHaptic("medium");

          // 3. AoE-урон всем врагам вокруг в радиусе 280px (или линии в 2D) (разделено на 4)
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
        }
      }
    }

    // Pudge Rot effect: ticks every 15 frames while active
    if (p.rotActive > 0) {
      p.rotActive--;
      if (p.rotActive % 15 === 0) {
        const rotDmg = Math.floor((stats.max_atk || 25) * 0.9 * (p.rotDmgMult || 1.0));
        for (const c of ARENA.creeps) {
          if (c.isBoss) {
            const rd = applyDamageToBoss(c, rotDmg);
            spawnFloatingText(c.x, c.y - 12, `☣️ -${rd}`, "#22c55e");
          } else {
            c.hp -= rotDmg;
            spawnFloatingText(c.x, c.y - 12, `☣️ -${rotDmg}`, "#22c55e");
          }
        }
      }
    }

    // Special effects animation timers & top-down ability controllers
    for (let i = ARENA.specialEffects.length - 1; i >= 0; i--) {
      const fx = ARENA.specialEffects[i];
      fx.timer--;

      // Invoker Top-Down Chaos Meteor Flight & Impact
      if (fx.type === "topdown_meteor") {
        const prog = 1 - (fx.timer / (fx.maxTimer || 50));
        if (prog < 0.65) {
          const flightProg = prog / 0.65;
          fx.x = fx.startX + (fx.targetX - fx.startX) * flightProg;
          fx.y = fx.startY + (fx.targetY - fx.startY) * flightProg;
        } else {
          fx.x = fx.targetX;
          fx.y = fx.targetY;
          if (!fx.impactDone) {
            fx.impactDone = true;
            ARENA.cameraTrauma = Math.min(1.0, (ARENA.cameraTrauma || 0) + 0.75);
            triggerHaptic("heavy");
            if (!ARENA.shockwaves) ARENA.shockwaves = [];
            ARENA.shockwaves.push({ x: fx.x, y: fx.y, radius: 10, maxRadius: 110, alpha: 1.0, speed: 6, color: "#ea580c" });
            spawnFloatingText(fx.x, fx.y - 45, "💥 БАБАХ! МЕТЕОР ПРИЗЕМЛИЛСЯ!", "#ea580c");
            if (ARENA.bossEntity && ARENA.bossEntity.hp > 0) {
              ARENA.bossEntity.poise = Math.max(0, (ARENA.bossEntity.poise || 300) - 100);
            }
          }
        }
      }

      // Juggernaut Top-Down Omnislash Slashes
      if (fx.type === "topdown_omnislash" && fx.timer % 6 === 0 && fx.slashes > 0) {
        fx.slashes--;
        const boss = ARENA.bossEntity;
        if (boss && boss.hp > 0) {
          const slashDmg = Math.max(10, Math.floor((fx.dmg || 100) / 8));
          const ang = Math.random() * Math.PI * 2;
          if (!fx.slashArcs) fx.slashArcs = [];
          fx.slashArcs.push({ x: boss.x + Math.cos(ang) * 18, y: boss.y + Math.sin(ang) * 18, angle: ang });
          spawnFloatingText(boss.x + (Math.random() * 32 - 16), boss.y - 25, `⚔️ -${slashDmg}`, "#facc15");
          triggerHaptic("medium");
        }
      }

      // PA Dagger Throw
      if (fx.type === "dagger_throw") {
        const dProg = 1 - (fx.timer / (fx.maxTimer || 20));
        fx.x = fx.fromX + (fx.toX - fx.fromX) * dProg;
        fx.y = fx.fromY + (fx.toY - fx.fromY) * dProg;
        if (fx.timer === 1) {
          ARENA.specialEffects.push({ type: "slash_burst", x: fx.toX, y: fx.toY, timer: 16, maxTimer: 16, color: "#f43f5e" });
        }
      }

      // Wraith King Wraithfire Skull
      if (fx.type === "wraithfire") {
        const wProg = 1 - (fx.timer / (fx.maxTimer || 26));
        fx.x = fx.fromX + (fx.toX - fx.fromX) * wProg;
        fx.y = fx.fromY + (fx.toY - fx.fromY) * wProg;
      }

      // Pudge Meat Hook
      if (fx.type === "meat_hook") {
        const hookProg = Math.sin((1 - (fx.timer / (fx.maxTimer || 24))) * Math.PI);
        fx.curX = fx.fromX + (fx.toX - fx.fromX) * hookProg;
        fx.curY = fx.fromY + (fx.toY - fx.fromY) * hookProg;
      }

      // Legacy Omnislash (Side-Scroller waves)
      if (fx.type === "omnislash" && fx.timer % 7 === 0 && fx.slashes > 0) {
        fx.slashes--;
        if (ARENA.creeps.length > 0) {
          const target = ARENA.creeps[Math.floor(Math.random() * ARENA.creeps.length)];
          let dmg = Math.floor((stats.max_atk || 30) * 2.2 * (fx.mult || 1.0));
          if (target.archetype === "defender") {
            target.shieldBrokenTimer = 240;
            target.state = "stagger";
            target.staggerTimer = 80;
            target.stateTimer = 80;
            spawnFloatingText(target.x, target.y - 25, "💥 GUARD BREAK ОМНИСЛЕШЕМ!", "#facc15");
          }
          if (target.isBoss) {
            dmg = applyDamageToBoss(target, dmg, true);
          } else {
            safeDamageCreep(target, dmg, false);
          }
          spawnFloatingText(target.x, target.y - 20, `⚔️ КРИТ! -${dmg}`, "#facc15");
          triggerHaptic("heavy");
        }
      }
      if (fx.timer <= 0) ARENA.specialEffects.splice(i, 1);
    }

    // Boss block-window timer
    if (ARENA.blockWindowActive) {
      ARENA.blockWindowTimer--;
      if (ARENA.blockWindowTimer <= 0) {
        ARENA.blockWindowActive = false;
        let dmg = Math.floor((ARENA.bossEntity?.atk || 30) * 2);
        if (p.fleshHeapActive > 0) dmg = Math.floor(dmg * 0.6);
        p.currentHp = Math.max(0, p.currentHp - dmg);
        spawnFloatingText(p.x, p.y - 25, `💥 -${dmg} ПРОПУЩЕН!`, "#ef4444");
        triggerHaptic("error");
        if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
      }
    }

    // QTE timer
    if (ARENA.qteActive) {
      ARENA.qteTimer--;
      if (ARENA.qteTimer <= 0) ARENA.qteActive = false;
    }

    // Auto-attack (Side-Scroller waves only; Top-Down mode handles 360 targeting independently)
    if (!ARENA.topDownMode && !ARENA.isRaidBossBattle && p.autoAttack && p.attackCooldown <= 0) {
      let nearest = null;
      let nearestDist = Math.max(320, p.attackRange + 50);
      for (const c of ARENA.creeps) {
        const d = c.x - p.x;
        if (d > 0 && d < nearestDist) {
          nearest = c;
          nearestDist = d;
        }
      }
      if (nearest) {
        playerSlashAttack();
      }
    }

    // Update Telegraphs (Ground warnings)
    if (ARENA.telegraphs) {
      for (let i = ARENA.telegraphs.length - 1; i >= 0; i--) {
        const tg = ARENA.telegraphs[i];
        tg.timer--;
        if (tg.timer <= 0) {
          ARENA.telegraphs.splice(i, 1);
        }
      }
    }

    // Update Shockwaves (Radial expanding rings)
    if (ARENA.shockwaves) {
      for (let i = ARENA.shockwaves.length - 1; i >= 0; i--) {
        const sw = ARENA.shockwaves[i];
        sw.radius += sw.speed;

        const waveFrontX = sw.x - sw.radius;
        if (!sw.hitPlayer && Math.abs(waveFrontX - p.x) < 22) {
          // Check Perfect Parry
          if (ARENA.parryWindow > 0) {
            sw.hitPlayer = true;
            triggerPerfectParry();
          } else if (p.counterspellActive > 0 || p.isBlocking) {
            sw.hitPlayer = true;
            const blkDmg = Math.max(5, Math.floor(sw.damage * 0.3));
            p.currentHp = Math.max(0, p.currentHp - blkDmg);
            spawnFloatingText(p.x, p.y - 25, `🛡️ БЛОК -${blkDmg}`, "#38bdf8");
            triggerHaptic("medium");
          } else {
            sw.hitPlayer = true;
            const effDef = stats.defense || 6;
            const floor = RPG_STATE.profile?.dungeon_floor || 1;
            const dr = Math.min(0.82, (effDef * 0.05) / (1 + effDef * 0.05 + floor * 0.4));
            let finalDmg = Math.max(Math.floor(sw.damage * 0.2), Math.floor(sw.damage * (1 - dr)));
            if (p.fleshHeapActive > 0) finalDmg = Math.floor(finalDmg * 0.6);
            p.currentHp = Math.max(0, p.currentHp - finalDmg);
            ARENA.cameraTrauma = Math.min(1.0, ARENA.cameraTrauma + 0.45);
            spawnFloatingText(p.x, p.y - 25, `💥 -${finalDmg} УДАРНАЯ ВОЛНА!`, "#ef4444");
            triggerHaptic("error");
            if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
          }
        }

        if (sw.radius > sw.maxRadius) {
          ARENA.shockwaves.splice(i, 1);
        }
      }
    }

    // Guarantee Raid Boss remains in creeps array during boss fight!
    if (ARENA.isRaidBossBattle && ARENA.bossEntity) {
      ARENA.isBossActive = true;
      if (!ARENA.creeps.includes(ARENA.bossEntity)) {
        ARENA.creeps = [ARENA.bossEntity];
      }
    }

    // Creep Spawning (waves 1 to 19 only, NEVER during a Raid Boss Battle!)
    ARENA.creepSpawnTimer++;
    if (!ARENA.isRaidBossBattle && !ARENA.isBossActive && ARENA.creepSpawnTimer % 45 === 0 &&
        ARENA.totalCreepsSpawned < ARENA.creepsNeededForWave && ARENA.creeps.length < 14) {
      spawnArenaCreep();
    }

    // Deadlock safeguard: if wave is fighting, no creeps exist, and all wave creeps are considered spawned
    if (!ARENA.isRaidBossBattle && !ARENA.isBossActive && ARENA.waveState === "fighting" && ARENA.creeps.length === 0 && ARENA.totalCreepsSpawned >= ARENA.creepsNeededForWave) {
      if (ARENA.creepsKilledInWave >= ARENA.creepsNeededForWave) {
        if (typeof advanceArenaWave === "function") advanceArenaWave();
      } else {
        ARENA.totalCreepsSpawned = ARENA.creepsKilledInWave;
        if (typeof spawnArenaCreep === "function") spawnArenaCreep();
      }
    }

    // Boss phase logic & companion squad updates
    if (ARENA.isBossActive && ARENA.bossEntity) {
      updateBossPhase();
      updateBossCompanions();
    }

    // Boss Projectiles (Side-Scroller Waves only — Top-Down mode has its own dedicated 360 projectile loop!)
    if (!ARENA.topDownMode && !ARENA.isRaidBossBattle) {
      for (let i = ARENA.bossProjectiles.length - 1; i >= 0; i--) {
        const proj = ARENA.bossProjectiles[i];
        proj.x -= proj.speed;
      if (proj.x < p.x + 65 && !proj.warned) {
        proj.warned = true;
        ARENA.blockWindowActive = true;
        ARENA.blockWindowTimer = ARENA.blockWindowMax;
        triggerHaptic("warning");
      }
      if (proj.x < p.x - 20) {
        ARENA.bossProjectiles.splice(i, 1);
      }
    }

    // Player Projectiles
    for (let i = ARENA.playerProjectiles.length - 1; i >= 0; i--) {
      const proj = ARENA.playerProjectiles[i];

      // Companion Dagger (Phantom Assassin / Anti-Mage squad companion)
      if (proj.type === "companion_dagger") {
        proj.x += proj.speed;
        const boss = ARENA.bossEntity;
        if (boss && Math.abs(proj.x - boss.x) < 25) {
          const dmgTaken = applyDamageToBoss(boss, proj.dmg, proj.isCrit);
          if (boss.poise !== undefined) boss.poise = Math.max(0, boss.poise - (proj.isCrit ? 12 : 6));
          if (proj.isCrit) {
            spawnFloatingText(boss.x - 10 + Math.random() * 20, boss.y - 25 - Math.random() * 15, `💥 КРИТ! -${proj.dmg}`, "#ef4444");
            triggerHaptic("heavy");
          } else {
            spawnFloatingText(boss.x - 10 + Math.random() * 20, boss.y - 20 - Math.random() * 12, `🗡️ КИНЖАЛ -${proj.dmg}`, "#38bdf8");
          }
          if (ARENA.combo) {
            ARENA.combo.count++;
            ARENA.combo.timer = 120;
          }
          ARENA.playerProjectiles.splice(i, 1);
          continue;
        }
        if (proj.x > ARENA.width + 40) {
          ARENA.playerProjectiles.splice(i, 1);
          continue;
        }
      }

      // Wind Blade / Cleave Wave (Melee heroes cutting wave that slices through ranged creeps)
      if (proj.type === "wind_blade") {
        proj.x += proj.speed;
        for (const c of ARENA.creeps) {
          if (!proj.hitCreepIds) proj.hitCreepIds = new Set();
          const creepKey = c.id || c.uid || c.name; // Stable key! Never hit the same creep twice in one projectile!
          if (!proj.hitCreepIds.has(creepKey) && Math.abs(c.x - proj.x) < (c.radius + proj.radius)) {
            proj.hitCreepIds.add(creepKey);
            let finalDmg = proj.dmg;
            if (c.archetype === "defender") {
              c.shieldHits = (c.shieldHits || 0) + 1;
              if (c.shieldHits >= 3 || proj.isHeavy) {
                c.shieldBrokenTimer = 240;
                c.state = "stagger";
                c.staggerTimer = 80;
                c.stateTimer = 80;
                spawnFloatingText(c.x, c.y - 25, "💥 GUARD BREAK! (+100% УРОНА)", "#facc15");
                finalDmg = Math.floor(finalDmg * 1.5);
              } else if (c.shieldBrokenTimer <= 0) {
                finalDmg = Math.max(8, Math.floor(finalDmg * 0.5));
                spawnFloatingText(c.x, c.y - 20, `🛡️ БЛОК (-50%) [${3 - c.shieldHits} уд.]`, "#94a3b8");
              }
            }

            if (c.isBoss) {
              finalDmg = applyDamageToBoss(c, finalDmg, proj.isCrit);
            } else {
              safeDamageCreep(c, finalDmg, false);
            }
            spawnFloatingText(c.x, c.y - 18, `${proj.isCrit ? "⚡ КРИТ! " : ""}-${finalDmg}`, proj.isCrit ? "#f59e0b" : "#facc15");
          }
        }
        if (proj.x > ARENA.width + 40) {
          ARENA.playerProjectiles.splice(i, 1);
        }
        continue;
      }

      // Chaos Meteor («Котлета» Инвокера, падающая с неба и катящаяся по линии)
      if (proj.type === "meteor") {
        if (proj.falling) {
          proj.x += proj.vx;
          proj.y += proj.vy;
          proj.angle += 0.2;

          // Impact on ground!
          if (proj.y >= proj.targetY) {
            proj.y = proj.targetY;
            proj.falling = false;
            ARENA.cameraTrauma = Math.min(1.0, ARENA.cameraTrauma + 0.65);
            ARENA.hitstop = 8;
            triggerHaptic("heavy");

            // Ground impact shockwave & crater
            if (!ARENA.shockwaves) ARENA.shockwaves = [];
            ARENA.shockwaves.push({
              x: proj.x,
              y: proj.y + 12,
              radius: 12,
              maxRadius: 85,
              alpha: 1.0,
              color: "#ea580c"
            });
            spawnFloatingText(proj.x, proj.y - 35, "💥 БАБАХ! МЕТЕОР ПРИЗЕМЛИЛСЯ!", "#f97316");

            // Massive impact damage in landing zone
            for (const c of ARENA.creeps) {
              if (Math.abs(c.x - proj.x) < 85) {
                safeDamageCreep(c, Math.floor(proj.dmg * 0.8), false);
                c.x += 45; // knockback
                if (c.isBoss) {
                  c.poise = Math.max(0, (c.poise !== undefined ? c.poise : 300) - 80);
                  if (c.poise <= 0 && !c.isStaggered) {
                    c.isStaggered = true;
                    c.staggerTimer = 210;
                    ARENA.hitstop = 12;
                    ARENA.cameraTrauma = 0.8;
                    spawnFloatingText(c.x, c.y - 35, "💫 ОШЕЛОМЛЕН МЕТЕОРОМ!", "#facc15");
                  }
                }
                if (c.archetype === "defender") {
                  c.shieldBrokenTimer = 240;
                  c.state = "stagger";
                  c.staggerTimer = 90;
                  c.stateTimer = 90;
                  spawnFloatingText(c.x, c.y - 25, "💥 GUARD BREAK МЕТЕОРОМ!", "#facc15");
                }
              }
            }
          }
        } else {
          // Rolling along the lane
          proj.x += proj.speed;
          proj.angle += 0.15;

          // Leaves burning magma trail
          if (!proj.burnTrail) proj.burnTrail = [];
          if ((ARENA.frameCount || 0) % 5 === 0) {
            proj.burnTrail.push({
              x: proj.x - 16,
              y: proj.y + 12,
              timer: 130
            });
          }

          // Damage creeps in its path
          for (const c of ARENA.creeps) {
            if (!proj.hitCreepIds) proj.hitCreepIds = new Set();
            const creepKey = c.id || c.uid || c.name; // Stable key!
            if (!proj.hitCreepIds.has(creepKey) && Math.abs(c.x - proj.x) < (c.radius + proj.radius)) {
              proj.hitCreepIds.add(creepKey);
              let finalDmg = proj.dmg;
              if (c.isBoss) {
                c.poise = Math.max(0, (c.poise !== undefined ? c.poise : 300) - 45);
                if (c.poise <= 0 && !c.isStaggered) {
                  c.isStaggered = true;
                  c.staggerTimer = 210;
                  ARENA.hitstop = 10;
                  ARENA.cameraTrauma = 0.7;
                  spawnFloatingText(c.x, c.y - 35, "💫 ОШЕЛОМЛЕН МЕТЕОРОМ!", "#facc15");
                }
                finalDmg = applyDamageToBoss(c, finalDmg, true);
              } else {
                safeDamageCreep(c, finalDmg, false);
                c.x += 40; // knockback
              }
              if (c.archetype === "defender") {
                c.shieldBrokenTimer = 240;
                c.state = "stagger";
                c.staggerTimer = 90;
                c.stateTimer = 90;
                spawnFloatingText(c.x, c.y - 25, "💥 GUARD BREAK МЕТЕОРОМ!", "#facc15");
              }
              spawnFloatingText(c.x, c.y - 20, `☄️ -${finalDmg} ОЖОГ!`, "#ea580c");
            }
          }
        }

        // Update ground burn trail
        if (proj.burnTrail) {
          for (let b = proj.burnTrail.length - 1; b >= 0; b--) {
            proj.burnTrail[b].timer--;
            // Ticking burn damage on creeps walking over magma
            if (proj.burnTrail[b].timer % 18 === 0) {
              const tx = proj.burnTrail[b].x;
              for (const c of ARENA.creeps) {
                if (Math.abs(c.x - tx) < 32) {
                  const tick = Math.max(10, Math.floor(proj.dmg * 0.12));
                  safeDamageCreep(c, tick, false);
                  spawnFloatingText(c.x, c.y - 12, `🔥 -${tick}`, "#f97316");
                }
              }
            }
            if (proj.burnTrail[b].timer <= 0) proj.burnTrail.splice(b, 1);
          }
        }

        if (proj.x > ARENA.width + 60 && (!proj.burnTrail || proj.burnTrail.length === 0)) {
          ARENA.playerProjectiles.splice(i, 1);
        }
        continue;
      }

      // Targeted magic orb or dagger
      proj.x += proj.speed;
      let hit = false;
      for (const c of ARENA.creeps) {
        if (Math.abs(c.x - proj.x) < c.radius + 10) {
          let finalDmg = proj.dmg;
          if (c.isBoss) {
            if (c.tormentorShield) {
              const reflectDmg = Math.max(4, Math.floor(finalDmg * 0.5));
              p.currentHp = Math.max(0, p.currentHp - reflectDmg);
              spawnFloatingText(p.x, p.y - 22, `🪞 ОТРАЖЕНИЕ -${reflectDmg}!`, "#c084fc");
              if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
            }
            if (c.isStaggered) {
              finalDmg = Math.floor(finalDmg * 2.5);
            } else {
              c.poise = Math.max(0, (c.poise !== undefined ? c.poise : 300) - (proj.isCrit ? 35 : 18));
              if (c.poise <= 0) {
                c.isStaggered = true;
                c.staggerTimer = 210;
                ARENA.hitstop = 10;
                ARENA.cameraTrauma = 0.7;
                spawnFloatingText(c.x, c.y - 35, "💫 ОШЕЛОМЛЕН! (+150% УРОНА)", "#facc15");
                triggerHaptic("heavy");
              }
            }

            // MAGIC ATTACK: Bypasses heavy physical defense armor!
            if (proj.isMagic) {
              const magicDr = 0.12;
              finalDmg = Math.max(12, Math.floor(finalDmg * (1 - magicDr)));
            } else {
              const bDef = c.defense || 14;
              const dr = (bDef * 0.05) / (1 + bDef * 0.05);
              finalDmg = Math.max(6, Math.floor(finalDmg * (1 - dr)));
            }
            finalDmg = applyDamageToBoss(c, finalDmg, proj.isCrit);
          } else {
            safeDamageCreep(c, finalDmg, false);
          }

          if (c.archetype === "defender" && proj.isMagic) {
            c.shieldHits = (c.shieldHits || 0) + 1;
            if (c.shieldHits >= 3 || proj.isHeavy) {
              c.shieldBrokenTimer = 240;
              c.state = "stagger";
              c.staggerTimer = 80;
              c.stateTimer = 80;
              spawnFloatingText(c.x, c.y - 25, "💥 GUARD BREAK МАГИЕЙ!", "#38bdf8");
            }
          }
          const col = proj.isMagic ? (proj.isCrit ? "#c084fc" : "#38bdf8") : (proj.isCrit ? "#facc15" : "#f87171");
          const prefix = proj.isMagic ? (proj.isCrit ? "🔮 МАГ КРИТ! " : "✨ МАГ ") : (proj.isCrit ? "💥 КРИТ! " : "");
          const txt = (c.isBoss && c.isStaggered) ? `💥 STAGGER! -${finalDmg}` : `${prefix}-${finalDmg}`;
          spawnFloatingText(c.x, c.y - 18, txt, col);
          if (proj.slow) c.speed = Math.max(0.5, c.speed * 0.5);
          hit = true;
          triggerHaptic("light");
          break;
        }
      }
      if (hit || proj.x > ARENA.width + 40) {
        ARENA.playerProjectiles.splice(i, 1);
      }
    }

    // Allied Minions (Wraith King skeletons)
    for (let i = ARENA.alliedMinions.length - 1; i >= 0; i--) {
      const m = ARENA.alliedMinions[i];
      if (ARENA.topDownMode || ARENA.isRaidBossBattle) {
        const boss = ARENA.bossEntity;
        if (boss && boss.hp > 0) {
          const ang = Math.atan2(boss.y - m.y, boss.x - m.x);
          const dist = Math.hypot(boss.x - m.x, boss.y - m.y);
          if (dist > boss.radius + m.radius + 6) {
            m.x += Math.cos(ang) * (m.speed || 2.6);
            m.y += Math.sin(ang) * (m.speed || 2.6);
          } else {
            m.attackCd = (m.attackCd || 0) - 1;
            if (m.attackCd <= 0) {
              m.attackCd = 35;
              const dmg = applyDamageToBoss(boss, m.atk || 25, false);
              spawnFloatingText(boss.x + (Math.random() * 20 - 10), boss.y - 20, `💀 -${dmg}`, "#10b981");
            }
          }
        }
      } else {
        m.x += m.speed;
        // Attack nearest creep
        for (const c of ARENA.creeps) {
          if (c.x - m.x < 30 && c.x > m.x) {
            safeDamageCreep(c, m.atk, false);
            spawnFloatingText(c.x, c.y - 15, `☠️ -${m.atk}`, "#e2e8f0");
            m.hp -= c.atk;
            break;
          }
        }
      }
      if (m.hp <= 0 || m.x > ARENA.width + 50 || m.x < -50 || m.y < -50 || m.y > ARENA.height + 50) {
        ARENA.alliedMinions.splice(i, 1);
      }
    }

    // Update Player Dash & Timers
    if (p.dashCooldown > 0) p.dashCooldown--;
    if (p.isInvulnerable > 0) p.isInvulnerable--;
    if (p.dashTimer > 0) {
      p.dashTimer--;
      if (p.dashTimer <= 0) p.isDashing = false;
    }
    if (ARENA.combo && ARENA.combo.timer > 0) {
      ARENA.combo.timer--;
      if (ARENA.combo.timer <= 0) {
        ARENA.combo.count = 0;
        ARENA.combo.step = 0;
      }
    }
    if (ARENA.styleMeter) {
      if (ARENA.styleMeter.decayTimer > 0) {
        ARENA.styleMeter.decayTimer--;
      } else if (ARENA.styleMeter.score > 0) {
        ARENA.styleMeter.score = Math.max(0, ARENA.styleMeter.score - 3);
        addStylePoints(0, "decay");
      }
    }
    // Dash Ghosts decay
    if (ARENA.dashGhosts) {
      for (let g = ARENA.dashGhosts.length - 1; g >= 0; g--) {
        ARENA.dashGhosts[g].alpha -= 0.05;
        if (ARENA.dashGhosts[g].alpha <= 0) ARENA.dashGhosts.splice(g, 1);
      }
    }

    // Witch-Time Slow Motion Timer
    if (ARENA.sloMoTimer > 0) {
      ARENA.sloMoTimer--;
      if (ARENA.sloMoTimer <= 0) {
        ARENA.timeScale = 1.0;
      }
    }

    // Update Enemy Projectiles (Ranged Mages, Archers, Catapults & Reflected Bolts)
    if (ARENA.enemyProjectiles) {
      for (let j = ARENA.enemyProjectiles.length - 1; j >= 0; j--) {
        const proj = ARENA.enemyProjectiles[j];

        if (proj.reflected) {
          // Reflected bolt flying towards enemies!
          proj.x -= proj.speed; // speed is negative, moves right
          let hitCreep = false;
          for (const c of ARENA.creeps) {
            if (Math.abs(c.x - proj.x) < c.radius + 14) {
              safeDamageCreep(c, proj.dmg, false);
              spawnFloatingText(c.x, c.y - 24, `💥 ОТРАЖЕН! -${proj.dmg}`, "#facc15");
              ARENA.hitstop = 4;
              hitCreep = true;
              break;
            }
          }
          if (hitCreep || proj.x > ARENA.width + 60) {
            ARENA.enemyProjectiles.splice(j, 1);
          }
        } else {
          // Hostile projectile flying towards player
          proj.x -= proj.speed;

          if (Math.abs(proj.x - p.x) < 22) {
            if (p.isInvulnerable > 0) {
              spawnFloatingText(p.x, p.y - 20, "УВОРОТ! (I-FRAMES)", "#38bdf8");
              ARENA.enemyProjectiles.splice(j, 1);
            } else if (ARENA.parryWindow > 0) {
              proj.reflected = true;
              proj.speed = -Math.abs(proj.speed || 3.5) * 2.0;
              proj.dmg = Math.floor((proj.dmg || 20) * 2.5);
              proj.color = "#facc15";
              addStylePoints(300, "DEFLECT");
              spawnFloatingText(p.x + 15, p.y - 28, "🪞 ОТРАЖЕНО!", "#facc15");
              triggerHaptic("heavy");
            } else if (p.isBlocking || p.counterspellActive > 0) {
              const bDmg = Math.max(3, Math.floor(proj.dmg * 0.25));
              p.currentHp = Math.max(0, p.currentHp - bDmg);
              spawnFloatingText(p.x, p.y - 20, `🛡️ БЛОК -${bDmg}`, "#38bdf8");
              triggerHaptic("medium");
              ARENA.enemyProjectiles.splice(j, 1);
            } else {
              const def = Math.max(0, stats.defense || 5);
              const floor = RPG_STATE.profile?.dungeon_floor || 1;
              const armorDr = Math.min(0.82, (def * 0.05) / (1.0 + def * 0.05 + floor * 0.4));
              let rawDmg = Math.max(Math.floor(proj.dmg * 0.15), Math.floor(proj.dmg * (1.0 - armorDr)));
              if (p.pipeShield && p.pipeShield > 0) {
                const absorbed = Math.min(p.pipeShield, rawDmg);
                p.pipeShield -= absorbed;
                rawDmg -= absorbed;
                spawnFloatingText(p.x, p.y - 30, `🛡️ ПАЙП -${absorbed}`, "#a855f7");
              }
              if (p.fleshHeapActive > 0) rawDmg = Math.floor(rawDmg * 0.6);
              if (p.crimsonActive > 0) rawDmg = Math.max(4, rawDmg - (p.crimsonBlock || 85));
              const takenDmg = applyDamageToPlayer(rawDmg, proj.isMagic ? "magic" : "projectile");
              if (takenDmg > 0) {
                if (p.blademailActive > 0) {
                  spawnFloatingText(p.x, p.y - 25, `🪞 ВОЗВРАТКА -${takenDmg}`, "#facc15");
                }
                spawnFloatingText(p.x + 10, p.y - 20, `💥 -${takenDmg}`, "#ef4444");
                triggerHaptic("light");
                if (ARENA.styleMeter) ARENA.styleMeter.score = Math.max(0, ARENA.styleMeter.score - 120);
              }
              ARENA.enemyProjectiles.splice(j, 1);
              if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
            }
          } else if (proj.x < -20) {
            ARENA.enemyProjectiles.splice(j, 1);
          }
        }
      }
    }
    } // End of Side-Scroller Projectiles Guard

    // Check Captain Presence for Squad Buffs
    const activeCaptain = ARENA.creeps.find(c => c.archetype === "captain" || c.isCaptain);

    // Update Creeps — Tactical FSM (Approach, Telegraph, Attack, Recovery, Panic)
    for (let i = ARENA.creeps.length - 1; i >= 0; i--) {
      const c = ARENA.creeps[i];

      // 1. Creep Death Check FIRST!
      if (c.hp <= 0) {
        if (c.archetype === "captain" || c.isCaptain) {
          addStylePoints(220, "CAPTAIN DOWN");
          for (const remaining of ARENA.creeps) {
            if (remaining !== c && !remaining.isBoss) {
              remaining.state = "panic";
              remaining.stateTimer = 150; // 2.5s panic
              spawnFloatingText(remaining.x, remaining.y - 25, "😱 ПАНИКА ОТРЯДА!", "#38bdf8");
            }
          }
        }
        ARENA.creeps.splice(i, 1);
        handleCreepDeath(c);
        continue;
      }

      // Recovery of broken shield
      if (c.shieldBrokenTimer > 0) c.shieldBrokenTimer--;

      // Captain aura check
      c.hasCaptainBuff = !!(activeCaptain && activeCaptain !== c && Math.abs(activeCaptain.x - c.x) < 80);

      // Stagger / Stun state (checks both staggerTimer and stateTimer to prevent infinite loop)
      if (c.state === "stagger" || (c.staggerTimer && c.staggerTimer > 0) || (c.stateTimer && c.stateTimer > 0 && c.state === "stagger")) {
        if (c.staggerTimer > 0) c.staggerTimer--;
        if (c.stateTimer > 0) c.stateTimer--;
        if ((!c.staggerTimer || c.staggerTimer <= 0) && (!c.stateTimer || c.stateTimer <= 0)) {
          c.state = "approach";
          c.staggerTimer = 0;
          c.stateTimer = 0;
        }
        continue;
      }

      // Squad Panic State (triggers when Captain dies)
      if (c.state === "panic") {
        c.x += 1.4; // Run backwards away from player
        c.stateTimer--;
        if (c.stateTimer <= 0) c.state = "approach";
        continue;
      }

      // Tactical Distance & FSM
      const targetDist = c.range || 38;

      if (c.isBoss) {
        // Boss movement & attacks are fully driven by updateBossPhase roaming FSM!
      } else if (c.x > p.x + targetDist) {
        c.state = "approach";
        const spd = c.speed * (c.hasCaptainBuff ? 1.3 : 1.0);
        c.x -= spd;
      } else {
        // In Attack Range!
        c.attackCooldown = (c.attackCooldown || 0) + 1;

        if (c.state !== "telegraph" && c.attackCooldown >= (c.hasCaptainBuff ? 32 : 45)) {
          c.state = "telegraph";
          c.stateTimer = 22; // 22 frames telegraph warning
        }

        if (c.state === "telegraph") {
          c.stateTimer--;
          if (c.stateTimer <= 0) {
            // EXECUTE ATTACK!
            c.state = "recovery";
            c.attackCooldown = 0;

            if (c.range && c.range > 100) {
              // Ranged Caster / Archer / Catapult fires projectile!
              if (!ARENA.enemyProjectiles) ARENA.enemyProjectiles = [];
              const isRadiant = (c.archetype || "").includes("radiant");
              const isCatapult = c.archetype === "catapult";
              ARENA.enemyProjectiles.push({
                x: c.x - 14,
                y: c.y - 4,
                speed: isCatapult ? 3.0 : 3.8,
                dmg: c.atk,
                color: isCatapult ? "#f97316" : (isRadiant ? "#38bdf8" : "#c084fc"),
                isBossFireball: isCatapult,
                reflected: false
              });
            } else {
              // Melee Strike on Player!
              if (p.isInvulnerable > 0) {
                spawnFloatingText(p.x, p.y - 20, "УВОРОТ! (I-FRAMES)", "#38bdf8");
              } else {
                const isDodge = Math.random() * 100 < (stats.dodge_chance || 10);
                if (isDodge) {
                  spawnFloatingText(p.x, p.y - 20, "УВОРОТ!", "#38bdf8");
                } else if (ARENA.parryWindow > 0) {
                  c.state = "stagger";
                  c.staggerTimer = 110;
                  c.attackCooldown = -30;
                  c.x += 40;
                  ARENA.hitstop = 8;
                  ARENA.cameraTrauma = Math.min(1.0, ARENA.cameraTrauma + 0.3);
                  addStylePoints(260, "PERFECT PARRY");
                  spawnFloatingText(c.x, c.y - 25, "💫 ПАРИРОВАНО! (+150% УРОНА)", "#facc15");
                  triggerHaptic("heavy");
                } else if (p.isBlocking || p.counterspellActive > 0) {
                  const bDmg = Math.max(2, Math.floor(c.atk * 0.25));
                  p.currentHp = Math.max(0, p.currentHp - bDmg);
                  spawnFloatingText(p.x, p.y - 20, `🛡️ БЛОК -${bDmg}`, "#38bdf8");
                  triggerHaptic("medium");
                  if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
                } else {
                  const def = Math.max(0, stats.defense || 5);
                  const floor = RPG_STATE.profile?.dungeon_floor || 1;
                  // Diminishing returns formula with floor scaling and 82% hard-cap (prevents 99.9% godmode)
                  const armorDr = Math.min(0.82, (def * 0.05) / (1.0 + def * 0.05 + floor * 0.4));
                  let rawDmg = Math.max(Math.floor(c.atk * 0.15), Math.floor(c.atk * 0.85 * (1.0 - armorDr)));
                  if (c.pureDamage) rawDmg = Math.floor(c.atk * 0.85); // Pure damage ignores armor!
                  if (p.fleshHeapActive > 0) rawDmg = Math.floor(rawDmg * 0.6);
                  if (p.crimsonActive > 0) rawDmg = Math.max(4, rawDmg - (p.crimsonBlock || 85));
                  const takenDmg = applyDamageToPlayer(rawDmg, c.pureDamage ? "pure" : (c.isMagic ? "magic" : "melee"));
                  if (takenDmg > 0) {
                    if (p.blademailActive > 0) {
                      safeDamageCreep(c, takenDmg, false);
                      spawnFloatingText(c.x, c.y - 30, `🪞 ВОЗВРАТКА -${takenDmg}`, "#facc15");
                    }
                    spawnFloatingText(p.x + 10, p.y - 15 - Math.random() * 15, `-${takenDmg}`, "#ef4444");
                    triggerHaptic("light");
                    if (ARENA.styleMeter) ARENA.styleMeter.score = Math.max(0, ARENA.styleMeter.score - 80);
                  }
                  if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
                }
              }
            }
          }
        }
      }

      // Creep Death Check
      if (c.hp <= 0) {
        if (c.archetype === "captain" || c.isCaptain) {
          addStylePoints(220, "CAPTAIN DOWN");
          for (const remaining of ARENA.creeps) {
            if (remaining !== c && !remaining.isBoss) {
              remaining.state = "panic";
              remaining.stateTimer = 150; // 2.5s panic
              spawnFloatingText(remaining.x, remaining.y - 25, "😱 ПАНИКА ОТРЯДА!", "#38bdf8");
            }
          }
        }
        ARENA.creeps.splice(i, 1);
        handleCreepDeath(c);
      }
    }

    updatePickups();
    updateFloatingTexts();
    updateClouds();
  }

  function updatePickups() {
    const p = ARENA.player;
    if (!ARENA.pickups) return;
    for (let i = ARENA.pickups.length - 1; i >= 0; i--) {
      const it = ARENA.pickups[i];
      it.x -= 3.5;
      it.y -= 0.4;
      if (it.x < p.x + 30) {
        ARENA.pickups.splice(i, 1);
        if (it.type === "gold") {
          const g = it.value || 10;
          if (RPG_STATE.profile) RPG_STATE.profile.gold = (RPG_STATE.profile.gold || 0) + g;
          spawnFloatingText(p.x + 20, p.y - 25, `+${g} 🪙`, "#facc15");
        } else if (it.type === "xp") {
          const x = it.value || 15;
          if (RPG_STATE.profile) {
            RPG_STATE.profile.xp = (RPG_STATE.profile.xp || 0) + x;
            checkLevelUpInArena();
          }
          spawnFloatingText(p.x + 20, p.y - 35, `+${x} XP`, "#38bdf8");
        } else if (it.type === "loot") {
          spawnFloatingText(p.x + 20, p.y - 35, "🎁 ТРОФЕЙНЫЙ СУНДУК!", "#a855f7");
          triggerHaptic("heavy");
          api.openRpgChest(RPG_STATE.profile?.dungeon_cleared || 10)
            .then((res) => {
              if (res.profile) RPG_STATE.profile = res.profile;
              openChestModal(res);
            })
            .catch((err) => console.warn("Loot chest drop error:", err));
        }
        triggerHaptic("light");
      }
    }
  }

  function updatePhysicalCoins() {
    if (!ARENA.physicalCoins || ARENA.physicalCoins.length === 0) return;
    const p = ARENA.player;
    const gravity = 0.38;

    for (let i = ARENA.physicalCoins.length - 1; i >= 0; i--) {
      const c = ARENA.physicalCoins[i];
      c.age++;

      if (c.age > c.magnetDelay) {
        const dx = p.x - c.x;
        const dy = (p.y - 8) - c.y;
        const dist = Math.hypot(dx, dy);
        if (dist < 22) {
          c.collected = true;
          ARENA.physicalCoins.splice(i, 1);
          triggerHaptic("light");
          if (c.type === "gem") {
            if (RPG_STATE.profile) RPG_STATE.profile.gems = (RPG_STATE.profile.gems || 0) + 1;
            spawnFloatingText(p.x, p.y - 20, "+1 💎", "#38bdf8");
          } else {
            if (RPG_STATE.profile) RPG_STATE.profile.gold = (RPG_STATE.profile.gold || 0) + 15;
            spawnFloatingText(p.x, p.y - 20, "+15 🪙", "#facc15");
          }
          continue;
        }
        const pullSpeed = Math.min(12, 2.5 + (c.age - c.magnetDelay) * 0.28);
        c.x += (dx / dist) * pullSpeed;
        c.y += (dy / dist) * pullSpeed;
        c.z = Math.max(0, c.z - 0.45);
      } else {
        c.x += c.vx;
        c.y += c.vy;
        c.z += c.vz;
        c.vz -= gravity;

        if (c.z <= 0) {
          c.z = 0;
          c.vz = -c.vz * 0.52;
          c.vx *= 0.75;
          c.vy *= 0.75;
          c.bounces++;
        }
      }
    }
  }

  function updateFallingChest() {
    const fc = ARENA.fallingChest;
    if (!fc) return;

    if (!fc.landed) {
      fc.vy += 0.45;
      fc.y += fc.vy;
      if (fc.y >= fc.targetY) {
        fc.y = fc.targetY;
        fc.landed = true;
        ARENA.cameraTrauma = 0.75;
        triggerHaptic("heavy");
        ARENA.specialEffects.push({
          type: "stomp_ring",
          x: fc.x,
          y: fc.targetY + 14,
          radius: 12,
          maxRadius: 60,
          timer: 25
        });
      }
    } else {
      fc.beamAlpha = Math.min(0.85, fc.beamAlpha + 0.03);
      fc.rayAngle += 0.02;

      if (Math.random() < 0.45) {
        fc.sparkles.push({
          x: fc.x + (Math.random() * 36 - 18),
          y: fc.y + 10,
          vy: -1.2 - Math.random() * 1.8,
          alpha: 1,
          size: 2 + Math.random() * 3
        });
      }
      for (let j = fc.sparkles.length - 1; j >= 0; j--) {
        const s = fc.sparkles[j];
        s.y += s.vy;
        s.alpha -= 0.025;
        if (s.alpha <= 0) fc.sparkles.splice(j, 1);
      }
    }
  }

  function spawnLootExplosion(originX, originY, bossTmpl) {
    bossTmpl = bossTmpl || {};
    const count = 36;
    ARENA.physicalCoins = ARENA.physicalCoins || [];
    for (let i = 0; i < count; i++) {
      const isGem = (i % 3 === 0);
      const angle = (Math.PI * 2 * i) / count + (Math.random() - 0.5) * 0.5;
      const speed = 2.5 + Math.random() * 5.5;
      ARENA.physicalCoins.push({
        x: originX,
        y: originY,
        z: 15 + Math.random() * 10,
        vx: Math.cos(angle) * speed,
        vy: (Math.random() - 0.5) * 2.2,
        vz: 4.5 + Math.random() * 6.5,
        type: isGem ? "gem" : "gold",
        icon: isGem ? "💎" : "🪙",
        size: isGem ? 14 : 16,
        bounces: 0,
        age: 0,
        magnetDelay: 45 + Math.floor(Math.random() * 25),
        collected: false
      });
    }

    ARENA.fallingChest = {
      x: Math.min(ARENA.width - 70, Math.max(130, originX)),
      y: -60,
      targetY: ARENA.roadY - 22,
      vy: 1.2,
      landed: false,
      beamAlpha: 0,
      rayAngle: 0,
      opened: false,
      sparkles: []
    };
  }

  function updateFloatingTexts() {
    for (let i = ARENA.floatingTexts.length - 1; i >= 0; i--) {
      const ft = ARENA.floatingTexts[i];
      ft.y -= 0.8;
      ft.opacity -= 0.02;
      if (ft.opacity <= 0) ARENA.floatingTexts.splice(i, 1);
    }
  }

  function updateClouds() {
    for (const cloud of ARENA.clouds) {
      cloud.x -= cloud.speed;
      if (cloud.x < -40) cloud.x = ARENA.width + 40;
    }
  }

  // ---------------------------------------------------------------------------
  // BOSS ARENA: DODGE ROLL
  // ---------------------------------------------------------------------------

  function playerBossArenaDodge() {
    if (!ARENA.bossArenaMode) return;
    if (ARENA.dodgeCooldown > 0 || ARENA.dodgeActive > 0) return;
    const p = ARENA.player;
    // Determine dodge direction: away from boss or toward movement input
    if (ARENA.moveInput.left) {
      ARENA.dodgeDir = -1;
    } else if (ARENA.moveInput.right) {
      ARENA.dodgeDir = 1;
    } else {
      // Default: away from boss
      const boss = ARENA.bossEntity;
      ARENA.dodgeDir = boss && boss.x > p.x ? -1 : 1;
    }
    ARENA.dodgeActive = 12; // ~0.2s of i-frame roll
    ARENA.dodgeCooldown = 48; // ~0.8s cooldown
    if (!ARENA.dashGhosts) ARENA.dashGhosts = [];
    triggerHaptic("medium");
    spawnFloatingText(p.x, p.y - 20, "УВОРОТ!", "#38bdf8");
  }

  // ---------------------------------------------------------------------------
  // BOSS PHASE LOGIC & COMBAT FSM (Poise, Telegraphs, Shockwaves, Stagger)
  // ---------------------------------------------------------------------------

  function updateBossPhase() {
    // In Top-Down 360° Brawl Arena, boss AI and movement are handled EXCLUSIVELY by the Top-Down State Machine!
    // NEVER allow legacy side-scrolling phase shifts, teleports, leap gravity, or horizontal rushes to run!
    if (ARENA.topDownMode || ARENA.isRaidBossBattle) return;

    const boss = ARENA.bossEntity;
    if (!boss || boss.hp <= 0) return;

    const p = ARENA.player;
    if (boss.poise === undefined) {
      boss.poise = 300;
      boss.maxPoise = 300;
      boss.defense = boss.defense || 14;
    }

    // 1. Stagger Recovery
    if (boss.isStaggered) {
      boss.staggerTimer--;
      boss.jumpY = 0;
      boss.jumpVY = 0;
      if (boss.staggerTimer <= 0) {
        boss.isStaggered = false;
        boss.poise = boss.maxPoise;
        boss.actionState = "roam";
        boss.actionTimer = 0;
        spawnFloatingText(boss.x, boss.y - 30, "😤 БОСС ВОССТАНОВИЛСЯ!", "#f97316");
      }
      return; // Stunned boss cannot move or act!
    }

    const hpPct = boss.hp / boss.maxHp;

    // 2. God Mode check (5 minutes / 300 seconds)
    boss.battleStartTime = boss.battleStartTime || Date.now();
    const elapsedMs = Date.now() - boss.battleStartTime;
    boss.enrageTimer = (boss.enrageTimer || 0) + 1;
    if (elapsedMs >= 300000 || boss.enrageTimer >= 18000) {
      if (!boss.isGodMode) {
        boss.isGodMode = true;
        boss.enraged = true;
        boss.enrageStage = "god_mode";
        boss.speed = Math.max(3.0, (boss.speed || 0.85) * 3.5);
        ARENA.cameraTrauma = 1.0;
        ARENA.hitstop = 15;
        spawnFloatingText(boss.x, boss.y - 45, "⚡⚡ РЕЖИМ БОГА: БЕРСЕРК! ⚡⚡", "#ef4444");
        triggerHaptic("heavy");
      }
      const regenPerSec = Math.max(500, Math.floor((boss.maxHp || 10000) * 0.05));
      const regenPerFrame = Math.max(1, Math.floor(regenPerSec / 60));
      boss.hp = Math.min(boss.maxHp, boss.hp + regenPerFrame);
      if (ARENA.frameCount % 60 === 0) {
        spawnFloatingText(boss.x, boss.y - 30, `✨ +${Math.round(regenPerSec)} РЕГЕН БОГА`, "#22c55e");
      }
    } else if (hpPct <= 0.35 && !boss.enraged) {
      boss.enraged = true;
      boss.speed = Math.min(1.4, (boss.speed || 0.85) * 1.45);
      boss.atk = Math.floor(boss.atk * 1.35);
      ARENA.cameraTrauma = 0.95;
      ARENA.hitstop = 10;
      spawnFloatingText(boss.x, boss.y - 45, "🔥 ЯРОСТЬ БОССА (ENRAGE)! 🔥", "#ef4444");
      triggerHaptic("heavy");
    }

    // 3. Tormentor Reflective Shield
    const bId = (boss.bossType || boss.name || "").toLowerCase();
    const isTormentor = bId.includes("tormentor") || bId.includes("терзатель");
    if (isTormentor || (hpPct < 0.65 && hpPct > 0.30)) {
      boss.tormentorTimer = (boss.tormentorTimer || 0) + 1;
      if (!boss.tormentorShield && boss.tormentorTimer % 240 === 0) {
        boss.tormentorShield = true;
        boss.tormentorShieldTimer = 180; // 3 seconds
        spawnFloatingText(boss.x, boss.y - 35, "🔮 ОТРАЖАЮЩИЙ ПАНЦИРЬ!", "#c084fc");
        triggerHaptic("warning");
      }
    }
    if (boss.tormentorShield) {
      boss.tormentorShieldTimer--;
      if (boss.tormentorShieldTimer <= 0) {
        boss.tormentorShield = false;
        spawnFloatingText(boss.x, boss.y - 35, "✨ ПАНЦИРЬ СПАЛ!", "#a855f7");
      }
    }

    // 4. Boss Roaming & Action State Machine (Roam, Leap, Charge, Recoil, Teleport)
    boss.actionState = boss.actionState || "roam";
    boss.moveDir = boss.moveDir || -1;
    boss.decisionTimer = (boss.decisionTimer || 110) - 1;

    // A. LEAP WINDUP -> PREPARING JUMP
    if (boss.actionState === "leap_windup") {
      boss.actionTimer--;
      boss.x += (Math.random() - 0.5) * 2;
      if (boss.actionTimer <= 0) {
        boss.actionState = "leap";
        boss.jumpVY = -12.5;
        boss.targetX = p.x + 45;
        triggerHaptic("medium");
      }
      return;
    }

    // B. LEAP AIRBORNE
    if (boss.actionState === "leap") {
      boss.jumpY = (boss.jumpY || 0) + boss.jumpVY;
      boss.jumpVY += 0.82; // Gravity
      boss.x += (boss.targetX - boss.x) * 0.08;

      if (boss.jumpY >= 0) {
        // Crash landing
        boss.jumpY = 0;
        boss.jumpVY = 0;
        ARENA.cameraTrauma = 0.85;
        triggerHaptic("heavy");

        ARENA.specialEffects.push({
          type: "stomp_ring",
          x: boss.x,
          y: ARENA.roadY - 14,
          radius: 12,
          maxRadius: 75,
          timer: 24
        });

        ARENA.shockwaves.push({
          x: boss.x,
          y: ARENA.roadY - 14,
          radius: 15,
          maxRadius: ARENA.width + 60,
          speed: boss.enraged ? 6.5 : 4.8,
          damage: Math.floor(boss.atk * 1.35),
          hitPlayer: false
        });

        spawnFloatingText(boss.x, boss.y - 35, "💥 СОКРУШИТЕЛЬНЫЙ УДАР!", "#ef4444");

        if (Math.abs(boss.x - p.x) < 55) {
          if (ARENA.parryWindow > 0) {
            boss.isStaggered = true;
            boss.staggerTimer = 110;
            boss.actionState = "roam";
            spawnFloatingText(boss.x, boss.y - 25, "💫 ПАРИРОВАНО! (+150% УРОНА)", "#facc15");
            return;
          }
          if (!p.isInvulnerable && !p.isBlocking) {
            const rawDmg = calculateBossAttackDamage(boss, 0.95);
            const actualDmg = applyDamageToPlayer(rawDmg, "melee");
            spawnFloatingText(p.x, p.y - 25, `-${actualDmg}`, "#ef4444");
            if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
          }
        }

        boss.actionState = "recoil";
        boss.actionTimer = 40;
      }
      return;
    }

    // C. CHARGE WINDUP
    if (boss.actionState === "charge_windup") {
      boss.actionTimer--;
      boss.x += (Math.random() - 0.5) * 1.5;
      if (boss.actionTimer <= 0) {
        boss.actionState = "charging";
        boss.actionTimer = 35;
        triggerHaptic("heavy");
        spawnFloatingText(boss.x - 20, boss.y - 25, "💨 ТАРАННЫЙ РЫВОК!", "#f97316");
      }
      return;
    }

    // D. CHARGING
    if (boss.actionState === "charging") {
      boss.x -= 4.8;
      if (ARENA.specialEffects && Math.random() < 0.4) {
        ARENA.specialEffects.push({
          type: "blink_poof",
          x: boss.x + boss.radius,
          y: ARENA.roadY - 10,
          timer: 12
        });
      }

      if (boss.x <= p.x + 42 || boss.actionTimer-- <= 0) {
        if (boss.x <= p.x + 48 && !p.isInvulnerable && !p.isBlocking && ARENA.parryWindow <= 0) {
          const rawDmg = calculateBossAttackDamage(boss, 1.35);
          const actualDmg = applyDamageToPlayer(rawDmg, "charge");
          spawnFloatingText(p.x, p.y - 20, `💥 ТАРАН -${actualDmg}`, "#ef4444");
          ARENA.cameraTrauma = 0.5;
          if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
        }
        boss.actionState = "recoil";
        boss.actionTimer = 45;
      }
      return;
    }

    // E. RECOIL
    if (boss.actionState === "recoil") {
      boss.actionTimer--;
      if (boss.x < ARENA.width - 90) {
        boss.x += 1.6;
      }
      if (boss.actionTimer <= 0) {
        boss.actionState = "roam";
        boss.moveDir = -1;
      }
      return;
    }

    // F. ROAM (Active Arena Traversal)
    if (boss.actionState === "roam") {
      const minX = p.x + 48;
      const maxX = ARENA.width - 45;

      if (boss.x <= minX) {
        boss.x = minX;
        boss.attackCooldown = (boss.attackCooldown || 0) + 1;
        if (boss.attackCooldown >= 35) {
          boss.attackCooldown = 0;
          if (!p.isInvulnerable && !p.isBlocking && ARENA.parryWindow <= 0) {
            const rawDmg = calculateBossAttackDamage(boss, 0.85);
            const actualDmg = applyDamageToPlayer(rawDmg, "roam");
            spawnFloatingText(p.x, p.y - 20, `💥 -${actualDmg}`, "#ef4444");
            triggerHaptic("light");
            if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
          }
          if (Math.random() < 0.45) boss.moveDir = 1;
        }
      } else if (boss.x >= maxX) {
        boss.moveDir = -1;
      }

      if (boss.x > minX || boss.moveDir === 1) {
        const spd = (boss.speed || 0.85) * (boss.enraged ? 1.4 : 1.0);
        boss.x += boss.moveDir * spd;
      }

      // Special Move Decision
      if (boss.decisionTimer <= 0) {
        boss.decisionTimer = boss.enraged ? (80 + Math.floor(Math.random() * 50)) : (130 + Math.floor(Math.random() * 70));

        const roll = Math.random();
        const isCasterBoss = isTormentor || bId.includes("лич") || bId.includes("archlich");

        if (isCasterBoss && roll < 0.25) {
          // Phase Shift / Teleport
          const newX = boss.x > 180 ? (p.x + 55) : (ARENA.width - 65);
          ARENA.specialEffects.push({ type: "blink_poof", x: boss.x, y: boss.y, timer: 18 });
          boss.x = newX;
          ARENA.specialEffects.push({ type: "blink_poof", x: boss.x, y: boss.y, timer: 18 });
          spawnFloatingText(boss.x, boss.y - 35, "🌀 ФАЗОВЫЙ СДВИГ!", "#c084fc");
          triggerHaptic("medium");
        } else if (roll < 0.48) {
          // Attack 1: Ground Slam / Quake (Danger Circle at player pos)
          const targetX = Math.max(35, Math.min(ARENA.width - 35, p.x));
          if (!ARENA.dangerZones) ARENA.dangerZones = [];
          ARENA.dangerZones.push({
            type: "circle",
            cx: targetX,
            cy: ARENA.roadY - 8,
            r: 46,
            timer: 48,
            maxTimer: 48,
            phase: "telegraph",
            activeFrames: 14,
            damage: Math.floor(boss.atk * 1.35),
            hitPlayer: false
          });
          spawnFloatingText(boss.x, boss.y - 35, "⚠️ РАЗЛОМ ЗЕМЛИ!", "#ef4444");
          triggerHaptic("warning");
        } else if (roll < 0.74) {
          // Attack 2: Cleave / Melee Swipe (Wide red rectangle in front of boss)
          const swipeW = 100;
          const swipeX = boss.x > p.x ? (boss.x - swipeW) : boss.x;
          if (!ARENA.dangerZones) ARENA.dangerZones = [];
          ARENA.dangerZones.push({
            type: "rect",
            x: swipeX,
            y: ARENA.roadY - 26,
            w: swipeW,
            h: 38,
            timer: 42,
            maxTimer: 42,
            phase: "telegraph",
            activeFrames: 12,
            damage: Math.floor(boss.atk * 1.25),
            hitPlayer: false
          });
          spawnFloatingText(boss.x, boss.y - 35, "⚠️ СОКРУШИТЕЛЬНЫЙ ВЗМАХ!", "#f97316");
          triggerHaptic("warning");
        } else if (roll < 0.88) {
          // Attack 3: Leap Airborne (Drop danger circle where boss will land)
          boss.actionState = "leap_windup";
          boss.actionTimer = 26;
          const landX = Math.max(45, Math.min(ARENA.width - 45, p.x + 25));
          if (!ARENA.dangerZones) ARENA.dangerZones = [];
          ARENA.dangerZones.push({
            type: "circle",
            cx: landX,
            cy: ARENA.roadY - 8,
            r: 52,
            timer: 45,
            maxTimer: 45,
            phase: "telegraph",
            activeFrames: 14,
            damage: Math.floor(boss.atk * 1.5),
            hitPlayer: false
          });
          spawnFloatingText(boss.x, boss.y - 35, "⚠️ ПРЫЖОК ОЗЕМЬ!", "#ef4444");
          triggerHaptic("warning");
        } else {
          // Attack 4: Charging Ram
          boss.actionState = "charge_windup";
          boss.actionTimer = 30;
          if (!ARENA.dangerZones) ARENA.dangerZones = [];
          ARENA.dangerZones.push({
            type: "rect",
            x: 0,
            y: ARENA.roadY - 22,
            w: boss.x,
            h: 32,
            timer: 36,
            maxTimer: 36,
            phase: "telegraph",
            activeFrames: 24,
            damage: Math.floor(boss.atk * 1.1),
            hitPlayer: false
          });
          spawnFloatingText(boss.x, boss.y - 35, "⚠️ ЗАМАХ ДЛЯ РЫВКА!", "#f97316");
          triggerHaptic("warning");
        }
      }
    }

    // 5. Periodic Projectile Fireball
    boss.projectileTimer = (boss.projectileTimer || 0) + 1;
    const pInterval = boss.enraged ? 120 : 180;
    if (boss.projectileTimer % pInterval === 0 && boss.actionState !== "leap") {
      ARENA.bossProjectiles.push({
        x: boss.x - 20,
        y: boss.y - 6,
        speed: boss.enraged ? 4.2 : 2.8,
        damage: Math.floor(boss.atk * 1.1),
        warned: false
      });
      spawnFloatingText(boss.x - 15, boss.y - 20, "🔥", "#f97316");
    }
  }

  // ---------------------------------------------------------------------------
  // TRIO SQUAD COMPANIONS & PARTY CONTROLS
  // ---------------------------------------------------------------------------

  function initBossCompanions() {
    const p = ARENA.player;
    const hClass = (RPG_STATE.profile?.hero_class || "pudge").toLowerCase();

    let c1Class = "juggernaut";
    let c1Name = "Юрнеро";
    let c2Class = "pa";
    let c2Name = "Мортред";

    if (hClass.includes("juggernaut")) {
      c1Class = "wk";
      c1Name = "Остарион";
    }
    if (hClass.includes("pa")) {
      c2Class = "am";
      c2Name = "Магина";
    }

    ARENA.bossCompanions = [
      {
        id: "comp1",
        name: c1Name,
        heroClass: c1Class,
        x: p.x + 26,
        baseX: p.x + 26,
        y: p.y - 20,
        baseY: p.y - 20,
        radius: 17,
        attackCooldown: 25,
        attackPeriod: 46,
        slashAnimation: null
      },
      {
        id: "comp2",
        name: c2Name,
        heroClass: c2Class,
        x: p.x + 22,
        baseX: p.x + 22,
        y: p.y + 20,
        baseY: p.y + 20,
        radius: 17,
        attackCooldown: 48,
        attackPeriod: 60,
        slashAnimation: null
      }
    ];
  }

  function updateBossCompanions() {
    if (!ARENA.isBossActive || (ARENA.bossPartyMode || "trio") !== "trio") {
      ARENA.bossCompanions = [];
      return;
    }

    if (!ARENA.bossCompanions || ARENA.bossCompanions.length === 0) {
      initBossCompanions();
    }

    const boss = ARENA.bossEntity;
    if (!boss || boss.hp <= 0) return;

    const p = ARENA.player;
    const stats = RPG_STATE.profile?.stats || {};
    const baseAtk = Math.max(30, Math.floor(((stats.min_atk || 30) + (stats.max_atk || 50)) / 2));

    for (let ci = 0; ci < ARENA.bossCompanions.length; ci++) {
      const comp = ARENA.bossCompanions[ci];
      if (comp.slashAnimation) {
        comp.slashAnimation.timer--;
        if (comp.slashAnimation.timer <= 0) comp.slashAnimation = null;
      }

      // TOP-DOWN 3-HERO SQUAD MOVEMENT & FORMATION
      if (ARENA.topDownMode || ARENA.isRaidBossBattle) {
        // Formation: Companion 1 to the left flank, Companion 2 to the right flank
        const offsetX = ci === 0 ? -34 : 34;
        const offsetY = 14;
        const targetX = Math.max(28, Math.min(ARENA.width - 28, p.x + offsetX));
        const targetY = Math.max(38, Math.min(ARENA.height - 38, p.y + offsetY));

        // Smooth follower lerp so friends run right alongside player!
        comp.x += (targetX - comp.x) * 0.14;
        comp.y += (targetY - comp.y) * 0.14;
        comp.facing = boss.x >= comp.x ? 1 : -1;
      }

      comp.attackCooldown = (comp.attackCooldown || 0) - 1;
      if (comp.attackCooldown <= 0) {
        comp.attackCooldown = (comp.attackPeriod || 45) + Math.floor(Math.random() * 15);

        if (comp.heroClass === "juggernaut" || comp.heroClass === "wk") {
          // Warrior Companion Slash
          comp.slashAnimation = { radius: 28, timer: 12, isMagic: false };
          const dmg = applyDamageToBoss(boss, Math.floor(baseAtk * 0.38));
          if (boss.poise !== undefined) boss.poise = Math.max(0, boss.poise - 5);
          spawnFloatingText(boss.x - 12 + Math.random() * 24, boss.y - 20 - Math.random() * 10, `⚔️ ${comp.name} -${dmg}`, "#fbbf24");
        } else {
          // Ranger / Assassin Companion Projectile
          const isCrit = Math.random() < 0.30;
          const dmg = Math.floor(baseAtk * (isCrit ? 0.75 : 0.35));
          const pAngle = Math.atan2(boss.y - comp.y, boss.x - comp.x);
          ARENA.playerProjectiles.push({
            type: "topdown_shot",
            x: comp.x + Math.cos(pAngle) * 12,
            y: comp.y + Math.sin(pAngle) * 12,
            vx: Math.cos(pAngle) * 8.5,
            vy: Math.sin(pAngle) * 8.5,
            speed: 8.5,
            target: boss,
            dmg: dmg,
            isCrit: isCrit,
            radius: 5.0,
            color: isCrit ? "#f59e0b" : "#38bdf8",
            distTraveled: 0,
            maxDist: 850
          });
        }
      }
    }
  }

  function toggleBossPartyMode() {
    const cur = ARENA.bossPartyMode || "trio";
    const next = cur === "trio" ? "solo" : "trio";
    ARENA.bossPartyMode = next;
    try {
      localStorage.setItem("rpg_boss_party_mode", next);
    } catch (e) {}

    if (next === "trio") {
      initBossCompanions();
      spawnFloatingText(ARENA.player.x + 30, ARENA.player.y - 45, "👥 ОТРЯД: 3 ГЕРОЯ В БОЮ!", "#10b981");
    } else {
      ARENA.bossCompanions = [];
      spawnFloatingText(ARENA.player.x + 30, ARENA.player.y - 45, "👤 РЕЖИМ: СОЛО ДУЭЛЬ!", "#c084fc");
    }
    triggerHaptic("medium");
  }

  function spawnBossMinions() {
    const floor = RPG_STATE.profile?.dungeon_floor || 1;
    const scale = 1.0 + floor * 0.15;
    for (let i = 0; i < 4; i++) {
      ARENA.creeps.push({
        name: "Миньон Рошана",
        icon: "👻",
        team: "dire",
        badgeBg: "#4a044e",
        badgeBorder: "#c084fc",
        x: ARENA.width + 30 + i * 50,
        y: ARENA.roadY - 15 + (Math.random() * 20 - 10),
        radius: 13,
        speed: 1.8,
        hp: Math.floor(45 * scale),
        maxHp: Math.floor(45 * scale),
        atk: Math.floor(9 * scale),
        isBoss: false,
        isMinion: true,
        attackCooldown: 0
      });
    }
  }

  // ===========================================================================
  // COMBAT ENGINE HELPERS: STYLE METER, DASH & DEFLECTION
  // ===========================================================================

  function addStylePoints(pts, reason) {
    if (!ARENA.styleMeter) ARENA.styleMeter = { score: 0, rank: "D", progress: 0, decayTimer: 0, maxRank: "D" };
    const sm = ARENA.styleMeter;
    sm.score += pts;
    sm.decayTimer = 120; // 2 seconds before decay begins

    const thresholds = [
      { rank: "D", min: 0, max: 300 },
      { rank: "C", min: 300, max: 750 },
      { rank: "B", min: 750, max: 1400 },
      { rank: "A", min: 1400, max: 2200 },
      { rank: "S", min: 2200, max: 3200 },
      { rank: "SS", min: 3200, max: 4500 },
      { rank: "SSS", min: 4500, max: 99999 }
    ];

    let currentRank = "D";
    let progress = 0;
    for (let i = 0; i < thresholds.length; i++) {
      const t = thresholds[i];
      if (sm.score >= t.min) {
        currentRank = t.rank;
        if (t.max === 99999) {
          progress = 1.0;
        } else {
          progress = (sm.score - t.min) / (t.max - t.min);
        }
      }
    }

    if (currentRank !== sm.rank) {
      sm.rank = currentRank;
      triggerHaptic("heavy");
      if (currentRank === "S" || currentRank === "SS" || currentRank === "SSS") {
        spawnFloatingText(ARENA.player.x + 10, ARENA.player.y - 38, `🔥 STYLE RANK [${currentRank}]!`, "#f43f5e");
      }
    }
    sm.progress = progress;
  }

  function playerPerformDash() {
    const p = ARENA.player;
    if (p.dashCooldown > 0) return;

    p.dashCooldown = 32;
    p.isInvulnerable = 14;
    p.isDashing = true;
    p.dashTimer = 10;

    // Check for Perfect Dodge (Witch-Time)
    let perfectDodge = false;
    if (ARENA.enemyProjectiles) {
      for (const proj of ARENA.enemyProjectiles) {
        if (!proj.reflected && Math.abs(proj.x - p.x) < 65) {
          perfectDodge = true;
          break;
        }
      }
    }
    if (!perfectDodge && ARENA.bossProjectiles) {
      for (const bp of ARENA.bossProjectiles) {
        if (Math.abs(bp.x - p.x) < 65) {
          perfectDodge = true;
          break;
        }
      }
    }
    if (!perfectDodge && ARENA.creeps) {
      for (const c of ARENA.creeps) {
        if (c.state === "telegraph" && Math.abs(c.x - p.x) < 55) {
          perfectDodge = true;
          break;
        }
      }
    }

    if (perfectDodge) {
      ARENA.timeScale = 0.2;
      ARENA.sloMoTimer = 26;
      p.critBuff = true;
      ARENA.cameraTrauma = Math.min(1.0, ARENA.cameraTrauma + 0.35);
      addStylePoints(260, "PERFECT DODGE");
      spawnFloatingText(p.x + 15, p.y - 30, "⚡ PERFECT DODGE! (WITCH-TIME)", "#38bdf8");
      triggerHaptic("heavy");
    } else {
      triggerHaptic("light");
    }

    // Spawn 3 Ghost Afterimages
    if (!ARENA.dashGhosts) ARENA.dashGhosts = [];
    const heroClass = (RPG_STATE.profile?.hero_class || "pudge").toLowerCase();
    for (let g = 0; g < 3; g++) {
      ARENA.dashGhosts.push({
        x: p.x - (g * 14),
        y: p.y,
        radius: p.radius,
        heroClass: heroClass,
        alpha: 0.65 - (g * 0.18),
        decay: 0.05
      });
    }
  }

  function playerBlock() {
    const p = ARENA.player;
    ARENA.parryWindow = 16; // 16 frames perfect parry window
    ARENA.player.isBlocking = true;
    ARENA.player.blockTimer = 22;

    ARENA.specialEffects.push({
      type: "block_flash",
      x: p.x + 10,
      y: p.y,
      radius: 38,
      timer: 15
    });

    // DEFLECT ENEMY PROJECTILES (Reflect magic bolts and arrows back at enemies!)
    let deflectedAny = false;
    if (ARENA.enemyProjectiles) {
      for (const proj of ARENA.enemyProjectiles) {
        if (!proj.reflected && Math.abs(proj.x - p.x) < 65) {
          proj.reflected = true;
          proj.speed = -Math.abs(proj.speed || 3.5) * 2.0; // Fly right towards enemies at high speed
          proj.dmg = Math.floor((proj.dmg || 22) * 2.5);  // 2.5x critical reflection damage
          proj.color = "#facc15";
          ARENA.hitstop = 8;
          ARENA.cameraTrauma = Math.min(1.0, ARENA.cameraTrauma + 0.35);
          addStylePoints(300, "DEFLECT");
          spawnFloatingText(p.x + 15, p.y - 28, "🪞 ОТРАЖЕНИЕ! (2.5x УРОН)", "#facc15");
          triggerHaptic("heavy");
          deflectedAny = true;
          break;
        }
      }
    }

    if (ARENA.blockWindowActive) {
      triggerPerfectParry();
      ARENA.blockWindowActive = false;
    } else if (!deflectedAny) {
      // Active Melee Parry on attacking creeps
      let parriedMelee = false;
      if (ARENA.creeps) {
        for (const c of ARENA.creeps) {
          if (!c.isBoss && Math.abs(c.x - p.x) < 55 && (c.state === "telegraph" || c.attackCooldown > 0)) {
            c.state = "stagger";
            c.staggerTimer = 110;
            c.attackCooldown = 0;
            ARENA.hitstop = 10;
            ARENA.cameraTrauma = Math.min(1.0, ARENA.cameraTrauma + 0.35);
            addStylePoints(220, "PARRY");
            spawnFloatingText(c.x, c.y - 25, "⚡ ПАРИРОВАНИЕ! СТАН!", "#facc15");
            triggerHaptic("heavy");
            parriedMelee = true;
            break;
          }
        }
      }
      if (!parriedMelee) {
        spawnFloatingText(p.x + 15, p.y - 25, "🛡️ БЛОК / ПАРИРОВАНИЕ!", "#38bdf8");
        triggerHaptic("medium");
      }
    }
  }

  function triggerPerfectParry() {
    const boss = ARENA.bossEntity;
    ARENA.hitstop = 12; // 12-frame hitstop freeze
    ARENA.cameraTrauma = 0.8;
    ARENA.bossProjectiles = [];
    ARENA.shockwaves = [];
    triggerHaptic("heavy");

    if (boss) {
      const parryDmg = Math.floor((ARENA.player.attackRange || 25) * 2.2);
      boss.poise = Math.max(0, (boss.poise || 300) - 80);
      parryDmg = applyDamageToBoss(boss, parryDmg, true);
      spawnFloatingText(boss.x, boss.y - 30, `⚡ PERFECT PARRY! -${parryDmg} ⚡`, "#facc15");

      if (boss.poise <= 0 && !boss.isStaggered) {
        boss.isStaggered = true;
        boss.staggerTimer = 210;
        spawnFloatingText(boss.x, boss.y - 45, "💫 ОШЕЛОМЛЕН! (+150% УРОНА)", "#facc15");
      }

      if (boss.hp <= 0) {
        const idx = ARENA.creeps.indexOf(boss);
        if (idx !== -1) ARENA.creeps.splice(idx, 1);
        handleCreepDeath(boss);
      }
    }
  }

  function hitQTE() {
    if (!ARENA.qteActive) return;
    ARENA.qteActive = false;
    if (ARENA.bossEntity) {
      const stats = RPG_STATE.profile?.stats || {};
      const megaDmg = Math.floor((stats.max_atk || 30) * 5.0);
      const qDmg = applyDamageToBoss(ARENA.bossEntity, megaDmg, true);
      spawnFloatingText(ARENA.bossEntity.x, ARENA.bossEntity.y - 25, `⚡ МЕГА КРИТ! -${qDmg}`, "#facc15");
      triggerHaptic("heavy");
      if (ARENA.bossEntity.hp <= 0) {
        const idx = ARENA.creeps.indexOf(ARENA.bossEntity);
        if (idx !== -1) ARENA.creeps.splice(idx, 1);
        handleCreepDeath(ARENA.bossEntity);
      }
    }
  }

  // ---------------------------------------------------------------------------
  // DOTA 2 CREEP SPAWNING (Waves 1-19)
  // ---------------------------------------------------------------------------

  function spawnArenaCreep() {
    const floor = RPG_STATE.profile?.dungeon_floor || 1;
    const wave = ARENA.waveNumber || 1;
    // Balanced Exponential Scaling: HP scales with 1.28^floor, ATK scales with 1.23^floor
    const scaleHp = Math.pow(1.18, Math.max(0, floor - 1)) * (1.0 + (wave - 1) * 0.05);
    const scaleAtk = Math.pow(1.15, Math.max(0, floor - 1)) * (1.0 + (wave - 1) * 0.04);

    let pool = [];
    // Dynamic Creep Hierarchy based on Dungeon Floor
    if (floor >= 200) {
      pool = [
        { name: "Страж Апокалипсиса", archetype: "apocalypse_doomguard", radius: 24, speed: 0.75, baseHp: 5500, baseAtk: 250, range: 48, pureDamage: true },
        { name: "Астральный Призрак", archetype: "astral_phantom", radius: 18, speed: 1.15, baseHp: 4800, baseAtk: 300, range: 42, pureDamage: true },
        { name: "Космический Разрушитель", archetype: "cosmic_annihilator", radius: 22, speed: 0.70, baseHp: 6200, baseAtk: 340, range: 190 }
      ];
    } else if (floor >= 100) {
      pool = [
        { name: "Древний Титан Скал", archetype: "ancient_titan", radius: 24, speed: 0.50, baseHp: 2800, baseAtk: 140, range: 48, earthquake: true },
        { name: "Архимаг Хаоса", archetype: "chaos_harbinger", radius: 17, speed: 0.75, baseHp: 2200, baseAtk: 160, range: 190 },
        { name: "Паладин Падших", archetype: "fallen_paladin", radius: 19, speed: 0.80, baseHp: 2500, baseAtk: 130, range: 44 },
        { name: "Повелитель Пустоты", archetype: "void_terror", radius: 19, speed: 0.70, baseHp: 1200, baseAtk: 90, range: 180 }
      ];
    } else if (floor >= 80) {
      pool = [
        { name: "Повелитель Пустоты", archetype: "void_terror", radius: 19, speed: 0.70, baseHp: 1200, baseAtk: 90, range: 180, timeDilation: true },
        { name: "Абиссальный Бегемот", archetype: "abyssal_behemoth", radius: 22, speed: 0.65, baseHp: 1600, baseAtk: 110, range: 46 },
        { name: "Вестник Разлома", archetype: "rift_stalker", radius: 16, speed: 1.20, baseHp: 1100, baseAtk: 125, range: 40 },
        { name: "Кентавр-Завоеватель", archetype: "centaur_conqueror", radius: 20, speed: 0.75, baseHp: 900, baseAtk: 60, range: 44, retaliate: 25 }
      ];
    } else if (floor >= 50) {
      pool = [
        { name: "Кентавр-Завоеватель", archetype: "centaur_conqueror", radius: 20, speed: 0.75, baseHp: 900, baseAtk: 60, range: 44, retaliate: 25 },
        { name: "Инфернальный Дракон", archetype: "drake", radius: 20, speed: 0.85, baseHp: 850, baseAtk: 75, range: 180, fireBreath: true },
        { name: "Пламенный Маг", archetype: "pyro_magus", radius: 15, speed: 0.75, baseHp: 720, baseAtk: 82, range: 185 },
        { name: "Некромант Катакомб", archetype: "necromancer", radius: 16, speed: 0.70, baseHp: 480, baseAtk: 52, range: 175, canSummon: true }
      ];
    } else if (floor >= 40) {
      pool = [
        { name: "Некромант Катакомб", archetype: "necromancer", radius: 16, speed: 0.70, baseHp: 480, baseAtk: 52, range: 175, canSummon: true },
        { name: "Теневой Ассасин", archetype: "assassin", radius: 15, speed: 1.25, baseHp: 380, baseAtk: 65, range: 38, critChance: 35 },
        { name: "Костяной Страж", archetype: "bone_guardian", radius: 18, speed: 0.65, baseHp: 650, baseAtk: 48, range: 44 },
        { name: "Варлок Легиона", archetype: "warlock", radius: 16, speed: 0.72, baseHp: 320, baseAtk: 38, range: 180 }
      ];
    } else if (floor >= 20) {
      pool = [
        { name: "Варлок Легиона", archetype: "warlock", radius: 16, speed: 0.72, baseHp: 320, baseAtk: 38, range: 180 },
        { name: "Железный Голем", archetype: "irongolem", radius: 20, speed: 0.55, baseHp: 550, baseAtk: 42, range: 42, physResist: 0.5 },
        { name: "Адская Гончая", archetype: "hound", radius: 14, speed: 1.35, baseHp: 260, baseAtk: 45, range: 36 },
        { name: "Броне-Защитник", archetype: "defender", radius: 17, speed: 0.7, baseHp: 260, baseAtk: 24, range: 44 }
      ];
    } else if (wave <= 3) {
      pool = [
        { name: "Мечник Света", archetype: "melee_radiant", radius: 15, speed: 0.85, baseHp: 135, baseAtk: 12, range: 38 },
        { name: "Вурдалак Тьмы", archetype: "melee_dire", radius: 15, speed: 0.88, baseHp: 145, baseAtk: 14, range: 38 }
      ];
    } else if (wave <= 7) {
      pool = [
        { name: "Мечник Света", archetype: "melee_radiant", radius: 15, speed: 0.85, baseHp: 140, baseAtk: 13, range: 38 },
        { name: "Вурдалак Тьмы", archetype: "melee_dire", radius: 15, speed: 0.88, baseHp: 150, baseAtk: 14, range: 38 },
        { name: "Маг Света", archetype: "ranged_radiant", radius: 14, speed: 0.78, baseHp: 95, baseAtk: 16, range: 170 },
        { name: "Колдун Тьмы", archetype: "ranged_dire", radius: 14, speed: 0.78, baseHp: 100, baseAtk: 18, range: 175 }
      ];
    } else if (wave <= 12) {
      pool = [
        { name: "Броне-Защитник", archetype: "defender", radius: 17, speed: 0.68, baseHp: 230, baseAtk: 14, range: 44 },
        { name: "Вурдалак Тьмы", archetype: "melee_dire", radius: 15, speed: 0.9, baseHp: 160, baseAtk: 16, range: 38 },
        { name: "Колдун Тьмы", archetype: "ranged_dire", radius: 14, speed: 0.8, baseHp: 110, baseAtk: 20, range: 175 },
        { name: "Осадная Катапульта", archetype: "catapult", radius: 18, speed: 0.45, baseHp: 300, baseAtk: 26, range: 195 }
      ];
    } else {
      const hasCaptain = ARENA.creeps.some(c => c.archetype === "captain");
      if (!hasCaptain && Math.random() < 0.35) {
        pool = [
          { name: "ЭЛИТНЫЙ КАПИТАН", archetype: "captain", radius: 19, speed: 0.75, baseHp: 380, baseAtk: 26, range: 42, isCaptain: true }
        ];
      } else {
        pool = [
          { name: "Броне-Защитник", archetype: "defender", radius: 17, speed: 0.7, baseHp: 260, baseAtk: 16, range: 44 },
          { name: "Колдун Тьмы", archetype: "ranged_dire", radius: 14, speed: 0.82, baseHp: 125, baseAtk: 22, range: 175 },
          { name: "Вурдалак Тьмы", archetype: "melee_dire", radius: 15, speed: 0.92, baseHp: 180, baseAtk: 18, range: 38 },
          { name: "Осадная Катапульта", archetype: "catapult", radius: 18, speed: 0.46, baseHp: 340, baseAtk: 28, range: 195 }
        ];
      }
    }

    const t = pool[Math.floor(Math.random() * pool.length)];

    ARENA.creeps.push({
      name: t.name,
      archetype: t.archetype,
      team: t.archetype.includes("radiant") ? "radiant" : (t.archetype.includes("dire") ? "dire" : "neutral"),
      x: ARENA.width + 22 + Math.random() * 35,
      y: ARENA.roadY - 16 + (Math.random() * 20 - 10),
      radius: t.radius,
      speed: t.speed + (wave - 1) * 0.01,
      hp: Math.floor(t.baseHp * scaleHp),
      maxHp: Math.floor(t.baseHp * scaleHp),
      atk: Math.floor(t.baseAtk * scaleAtk),
      physResist: t.physResist || 0,
      retaliate: t.retaliate || 0,
      critChance: t.critChance || 0,
      canSummon: !!t.canSummon,
      fireBreath: !!t.fireBreath,
      timeDilation: !!t.timeDilation,
      earthquake: !!t.earthquake,
      pureDamage: !!t.pureDamage,
      range: t.range || 38,
      state: "approach",
      stateTimer: 0,
      shieldActive: t.archetype === "defender",
      shieldBrokenTimer: 0,
      isCaptain: !!t.isCaptain,
      isBoss: false,
      isMinion: false,
      attackCooldown: 0
    });
    ARENA.totalCreepsSpawned++;
  }

  function updatePetLogic() {
    const p = ARENA.player;
    if (!p) return;

    // Detect equipped pet from profile or fallback to localStorage
    const equippedPet = (RPG_STATE.profile?.pets || []).find(pt => pt.is_equipped);
    const petId = equippedPet ? (equippedPet.type || equippedPet.pet_id) : (localStorage.getItem("rpg_active_pet") || null);
    if (!petId) {
      ARENA.pet = null;
      return;
    }

    const petStars = equippedPet ? (equippedPet.stars || 1) : 1;
    const starMult = 1.0 + (petStars - 1) * 0.15;

    if (!ARENA.pet) {
      ARENA.pet = { x: p.x - 25, y: p.y - 25, timer: 0 };
    }
    const pet = ARENA.pet;
    pet.type = petId;
    pet.stars = petStars;

    // Smooth trailing physics behind the player
    const targetX = p.x - (p.facing === "left" ? -32 : 32);
    const targetY = p.y - 26 + Math.sin((ARENA.frameCount || 0) * 0.08) * 6;
    pet.x += (targetX - pet.x) * 0.12;
    pet.y += (targetY - pet.y) * 0.12;

    pet.timer = (pet.timer || 0) + 1;

    const stats = RPG_STATE.profile?.stats || {};
    const playerAtk = Math.max(50, stats.max_atk || 50);
    const playerMaxHp = Math.max(100, p.maxHp || 500);

    // Target for pet attacks (boss or first alive creep)
    const target = (ARENA.bossEntity && ARENA.bossEntity.hp > 0) ? ARENA.bossEntity : (ARENA.creeps && ARENA.creeps.find(c => c.hp > 0));

    // 1. DRAGON (🔥 Дыхание Богатства: огненный снаряд каждые 6с)
    if (petId === "dragon") {
      if (pet.timer >= 360) {
        pet.timer = 0;
        if (target && target.hp > 0) {
          const dmg = Math.floor((playerAtk * 2.5 + 1200) * starMult);
          if (ARENA.playerProjectiles) {
            ARENA.playerProjectiles.push({
              x: pet.x, y: pet.y,
              vx: (target.x - pet.x) * 0.09,
              vy: (target.y - pet.y) * 0.09,
              speed: 8.5,
              target: target,
              dmg: dmg,
              color: "#f97316",
              radius: 9,
              isMagic: true,
              isCrit: true,
              isPetShot: true
            });
          }
          spawnFloatingText(pet.x, pet.y - 14, "🔥 ДЫХАНИЕ ДРАКОНА!", "#f97316");
          triggerHaptic("medium");
        }
      }
    }
    // 2. FAIRY (🧚 Пыльца Свободы: лечит HP & MP, очищает дебаффы каждые 10с)
    else if (petId === "fairy") {
      if (pet.timer >= 600) {
        pet.timer = 0;
        p.stunTimer = 0;
        p.freezeTimer = 0;
        p.slowTimer = 0;
        const healHp = Math.min(Math.floor(playerMaxHp * 0.08 * starMult), 8000 * starMult);
        const healMp = Math.floor((p.maxMp || 100) * 0.25);
        p.currentHp = Math.min(playerMaxHp, (p.currentHp || playerMaxHp) + healHp);
        p.currentMp = Math.min(p.maxMp || 100, (p.currentMp || p.maxMp || 100) + healMp);
        spawnFloatingText(p.x, p.y - 20, `🧚 ПЫЛЬЦА СВОБОДЫ! +${healHp} HP`, "#22c55e");
        triggerHaptic("light");
      }
    }
    // 3. WOLF (🐺 Кровавый Укус: наносит урон и вешает кровотечение каждые 5с)
    else if (petId === "wolf") {
      if (pet.timer >= 300) {
        pet.timer = 0;
        if (target && target.hp > 0) {
          const dmg = Math.floor((playerAtk * 1.8 + 800) * starMult);
          safeDamageCreep(target, dmg, true);
          spawnFloatingText(target.x, target.y - 25, `🐺 УКУС ВОЛКА -${dmg}!`, "#ef4444");
          if (ARENA.specialEffects) {
            ARENA.specialEffects.push({ x: target.x, y: target.y, radius: 25, color: "#dc2626", life: 20 });
          }
          triggerHaptic("medium");
        }
      }
    }
    // 4. SLIME (💧 Капля Исцеления: лечит HP каждые 12с)
    else if (petId === "slime") {
      if (pet.timer >= 720) {
        pet.timer = 0;
        const heal = Math.min(Math.floor(playerMaxHp * 0.07 * starMult), 6000 * starMult);
        p.currentHp = Math.min(playerMaxHp, (p.currentHp || playerMaxHp) + heal);
        spawnFloatingText(p.x, p.y - 22, `💧 КАПЛЯ ЖИЗНИ +${heal} HP`, "#38bdf8");
        triggerHaptic("light");
      }
    }
    // 5. DONKEY (🫏 Курьерская Доставка: усиливает урон на +35% на 4с каждые 7с)
    else if (petId === "donkey") {
      if (pet.timer >= 420) {
        pet.timer = 0;
        p.donkeyBuffTimer = 240; // 4 seconds
        spawnFloatingText(p.x, p.y - 20, "🫏 КУРЬЕР! +35% УРОНА", "#eab308");
        triggerHaptic("medium");
      }
    }
    // 6. PHOENIX (🦅 Пылающий Феникс: атакует огненным снарядом каждые 5с)
    else if (petId === "phoenix") {
      if (pet.timer >= 300) {
        pet.timer = 0;
        if (target && target.hp > 0) {
          const dmg = Math.floor((playerAtk * 2.2 + 2000) * starMult);
          if (ARENA.playerProjectiles) {
            ARENA.playerProjectiles.push({
              x: pet.x, y: pet.y,
              vx: (target.x - pet.x) * 0.10,
              vy: (target.y - pet.y) * 0.10,
              speed: 9,
              target: target,
              dmg: dmg,
              color: "#fbbf24",
              radius: 10,
              isMagic: true,
              isCrit: true,
              isPetShot: true
            });
          }
          spawnFloatingText(pet.x, pet.y - 14, "🦅 ПЛАМЯ ФЕНИКСА!", "#f59e0b");
          triggerHaptic("medium");
        }
      }
    }
  }


