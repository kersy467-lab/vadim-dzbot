  function renderArena() {
    const canvas = document.getElementById("rpg-action-canvas");
    if (!canvas) return;

    const isTopDown = !!(ARENA.topDownMode || ARENA.isRaidBossBattle);
    const expectedClientH = isTopDown ? 520 : 320;
    const curClientW = canvas.clientWidth;

    if (ARENA.canvas !== canvas || !ARENA.ctx ||
        (curClientW > 50 && Math.abs(curClientW - (ARENA.cachedClientW || 0)) > 2) ||
        (ARENA.cachedClientH !== expectedClientH)) {
      bindArenaCanvas(canvas);
    }

    const ctx = ARENA.ctx;
    if (!ctx) return;
    const clientW = ARENA.cachedClientW || (canvas.clientWidth > 50 ? canvas.clientWidth : 360);
    const clientH = ARENA.cachedClientH || (isTopDown ? 520 : 320);
    const w = ARENA.width || clientW || 360;
    const h = ARENA.height || clientH || 320;
    const time = ARENA.frameCount || 0;

    // Camera Trauma Shake (Subtle, crisp impact feel without violent earthquake)
    let shakeX = 0, shakeY = 0;
    if (ARENA.cameraTrauma > 0) {
      ARENA.cameraTrauma = Math.max(0, ARENA.cameraTrauma - 0.08);
      const shake = Math.pow(ARENA.cameraTrauma, 2) * 3.5;
      shakeX = (Math.random() * 2 - 1) * shake;
      shakeY = (Math.random() * 2 - 1) * shake;
    }
    ctx.save();
    ctx.translate(shakeX, shakeY);

    // Camera Zoom-Out in Top-Down mode: scale 520x720 arena to fit screen (zoom ~0.69)
    if (ARENA.topDownMode || ARENA.isRaidBossBattle) {
      const zoom = Math.min(clientW / 520, clientH / 720);
      const offX = (clientW - 520 * zoom) / 2;
      const offY = (clientH - 720 * zoom) / 2;

      ctx.translate(offX, offY);
      ctx.scale(zoom, zoom);

      // Deep Obsidian Floor filling 520x720 arena
      ctx.fillStyle = "#09090b";
      ctx.fillRect(-60, -60, 520 + 120, 720 + 120);

      // 2. Tactical Tile Grid (Batched single path stroke for 60 FPS performance)
      ctx.strokeStyle = "rgba(71, 85, 105, 0.20)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let tx = 0; tx <= 520; tx += 44) {
        ctx.moveTo(tx, 0); ctx.lineTo(tx, 720);
      }
      for (let ty = 0; ty <= 720; ty += 44) {
        ctx.moveTo(0, ty); ctx.lineTo(520, ty);
      }
      ctx.stroke();

      // 3. Glowing Perimeter Hazard Walls
      ctx.strokeStyle = "rgba(234, 179, 8, 0.50)";
      ctx.lineWidth = 4;
      ctx.strokeRect(16, 16, 488, 688);

      // Inner danger border
      ctx.strokeStyle = "rgba(239, 68, 68, 0.35)";
      ctx.lineWidth = 2;
      ctx.setLineDash([14, 8]);
      ctx.strokeRect(24, 24, 472, 672);
      ctx.setLineDash([]);

      // 4. Central Magical Battle Circle
      ctx.strokeStyle = "rgba(234, 179, 8, 0.38)";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.arc(260, 360, 95, 0, Math.PI * 2);
      ctx.stroke();

      // Outer Rune Octagon
      ctx.setLineDash([10, 6]);
      ctx.strokeStyle = "rgba(168, 85, 247, 0.38)";
      ctx.beginPath();
      ctx.arc(260, 360, 150, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);

      // 5. 4 Corner Tactical Pillars (Cover Obstacles)
      const pillars = [
        { x: 70, y: 90 },
        { x: 450, y: 90 },
        { x: 70, y: 630 },
        { x: 450, y: 630 }
      ];
      for (const pil of pillars) {
        ctx.fillStyle = "rgba(0,0,0,0.45)";
        ctx.beginPath();
        ctx.ellipse(pil.x, pil.y + 10, 16, 8, 0, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = "#1e293b";
        ctx.strokeStyle = "#64748b";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(pil.x, pil.y, 13, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = "#38bdf8";
        ctx.beginPath();
        ctx.arc(pil.x, pil.y, 4, 0, Math.PI * 2);
        ctx.fill();
      }

      // 6. Boss Charge Telegraph Beam (Bright pulsing warning beam with moving chevrons)
      const bObj = ARENA.bossEntity;
      if (bObj && bObj.state === "telegraph_charge") {
        ctx.save();
        const cAng = bObj.chargeAngle || 0;
        const beamL = 440;
        const cos = Math.cos(cAng);
        const sin = Math.sin(cAng);
        const nx = -sin * 24;
        const ny = cos * 24;

        const pulse = 0.28 + Math.sin((ARENA.frameCount || 0) * 0.18) * 0.12;
        ctx.fillStyle = `rgba(239, 68, 68, ${pulse})`;
        ctx.strokeStyle = "#ef4444";
        ctx.lineWidth = 3;
        ctx.setLineDash([12, 6]);
        ctx.beginPath();
        ctx.moveTo(bObj.x + nx, bObj.y + ny);
        ctx.lineTo(bObj.x + nx + cos * beamL, bObj.y + ny + sin * beamL);
        ctx.lineTo(bObj.x - nx + cos * beamL, bObj.y - ny + sin * beamL);
        ctx.lineTo(bObj.x - nx, bObj.y - ny);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        ctx.setLineDash([]);

        // Animated moving chevron markers along the charge beam
        const animOffset = ((ARENA.frameCount || 0) * 2) % 40;
        ctx.fillStyle = "#fef08a";
        for (let st = 35 + animOffset; st < beamL; st += 40) {
          ctx.beginPath();
          ctx.arc(bObj.x + cos * st, bObj.y + sin * st, 4.5, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.restore();
      }

      // Melee Smash Telegraph Circle (Expanding pulsing red hazard zone)
      if (bObj && bObj.state === "telegraph_melee") {
        ctx.save();
        const pulse = 0.32 + Math.sin((ARENA.frameCount || 0) * 0.2) * 0.15;
        ctx.fillStyle = `rgba(239, 68, 68, ${pulse})`;
        ctx.strokeStyle = "#ef4444";
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(bObj.x, bObj.y, 65, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        ctx.restore();
      }
    } else {
      // CLASSIC SIDE-SCROLLING ROAD (Only when NOT in Top-Down / Boss Fight!)
      if (ARENA.bossArenaMode) {
        if (!ARENA.cachedBossSkyGrad) {
          ARENA.cachedBossSkyGrad = ctx.createLinearGradient(0, -24, 0, h * 0.55);
          ARENA.cachedBossSkyGrad.addColorStop(0, "#450a0a");
          ARENA.cachedBossSkyGrad.addColorStop(0.4, "#1c1917");
          ARENA.cachedBossSkyGrad.addColorStop(1, "#292524");
        }
        ctx.fillStyle = ARENA.cachedBossSkyGrad;
      } else {
        ctx.fillStyle = ARENA.cachedSkyGrad || "#3b82f6";
      }
      ctx.fillRect(-24, -24, w + 48, h * 0.55 + 24);

      // Clouds
      if (ARENA.bossArenaMode) {
        ctx.fillStyle = "rgba(249, 115, 22, 0.6)";
        for (let e = 0; e < 12; e++) {
          const ex = (e * 31 + time * 1.2) % (w + 20);
          const ey = (e * 23 + time * 0.8) % (h * 0.7);
          ctx.beginPath();
          ctx.arc(ex, ey, (e % 3) + 1, 0, Math.PI * 2);
          ctx.fill();
        }
      } else {
        for (const cloud of (ARENA.clouds || [])) {
          drawProceduralCloud(ctx, cloud);
        }
      }

      // Distant Hills
      ctx.fillStyle = ARENA.bossArenaMode ? "#1c1917" : "#22c55e";
      ctx.beginPath();
      ctx.moveTo(-24, h * 0.55);
      ctx.quadraticCurveTo(60, h * 0.42, 120, h * 0.52);
      ctx.quadraticCurveTo(180, h * 0.40, 240, h * 0.50);
      ctx.quadraticCurveTo(310, h * 0.43, w + 24, h * 0.50);
      ctx.lineTo(w + 24, h * 0.58);
      ctx.lineTo(-24, h * 0.58);
      ctx.closePath();
      ctx.fill();

      // Ground
      if (ARENA.bossArenaMode) {
        if (!ARENA.cachedBossGroundGrad) {
          ARENA.cachedBossGroundGrad = ctx.createLinearGradient(0, h * 0.55 - 4, 0, h + 24);
          ARENA.cachedBossGroundGrad.addColorStop(0, "#1c1917");
          ARENA.cachedBossGroundGrad.addColorStop(0.4, "#292524");
          ARENA.cachedBossGroundGrad.addColorStop(1, "#0c0a09");
        }
        ctx.fillStyle = ARENA.cachedBossGroundGrad;
      } else {
        ctx.fillStyle = ARENA.cachedGroundGrad || "#15803d";
      }
      ctx.fillRect(-24, h * 0.55 - 4, w + 48, h * 0.45 + 32);

      // Grass blades
      ctx.fillStyle = "#4ade80";
      for (let gx = 15; gx < w; gx += 40) {
        const gy = ARENA.roadY + 32 + (gx * 13 % 17);
        ctx.beginPath();
        ctx.moveTo(gx, gy);
        ctx.lineTo(gx - 3, gy - 6);
        ctx.lineTo(gx + 1, gy - 4);
        ctx.lineTo(gx + 4, gy - 7);
        ctx.lineTo(gx + 6, gy);
        ctx.closePath();
        ctx.fill();
      }

      // Trail
      ctx.fillStyle = "#927050";
      ctx.beginPath();
      ctx.moveTo(0, ARENA.roadY - 14);
      for (let px = 0; px <= w; px += 20) {
        ctx.lineTo(px, ARENA.roadY - 14 + Math.sin(px * 0.03) * 3);
      }
      ctx.lineTo(w, ARENA.roadY + 30);
      for (let px = w; px >= 0; px -= 20) {
        ctx.lineTo(px, ARENA.roadY + 30 + Math.sin(px * 0.04) * 2);
      }
      ctx.closePath();
      ctx.fill();

      // Light strip
      ctx.fillStyle = "#b89570";
      ctx.fillRect(0, ARENA.roadY - 2, w, 20);

      // Pebbles
      ctx.fillStyle = "#6e5238";
      const pebbles = [30, 85, 145, 210, 275, 335];
      for (const px of pebbles) {
        const py = ARENA.roadY + 6 + (px * 7 % 11);
        ctx.beginPath();
        ctx.arc(px, py, 2.5, 0, Math.PI * 2);
        ctx.fill();
      }

      // Trees
      for (const tr of [{ x: 15 }, { x: 100 }, { x: 210 }, { x: 320 }]) {
        drawProceduralTree(ctx, tr.x, ARENA.roadY - 14, time);
      }
    }

    // ---- 6.0 BOSS ARENA DANGER ZONES (Visual Telegraphs & Impact Flashes) ----
    if (ARENA.dangerZones && ARENA.dangerZones.length > 0) {
      for (const dz of ARENA.dangerZones) {
        ctx.save();
        const maxT = dz.maxTimer || 45;
        const progress = Math.min(1, Math.max(0, 1 - (dz.timer / maxT)));
        const pulse = 0.5 + Math.sin(time * 0.25) * 0.35;

        if (dz.phase === "telegraph") {
          // Warning red zone with warning border & fill
          if (dz.type === "rect") {
            ctx.fillStyle = `rgba(239, 68, 68, ${0.22 + progress * 0.32})`;
            ctx.fillRect(dz.x, dz.y, dz.w, dz.h);
            ctx.strokeStyle = `rgba(248, 113, 113, ${0.7 + pulse * 0.3})`;
            ctx.lineWidth = 2.5;
            ctx.setLineDash([6, 4]);
            ctx.strokeRect(dz.x, dz.y, dz.w, dz.h);
            // Red progress bar at bottom of rectangle
            ctx.fillStyle = "rgba(220, 38, 38, 0.75)";
            ctx.fillRect(dz.x, dz.y + dz.h - 4, dz.w * progress, 4);
          } else if (dz.type === "circle") {
            ctx.beginPath();
            ctx.arc(dz.cx, dz.cy, dz.r, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(239, 68, 68, ${0.22 + progress * 0.32})`;
            ctx.fill();
            ctx.strokeStyle = `rgba(248, 113, 113, ${0.7 + pulse * 0.3})`;
            ctx.lineWidth = 2.5;
            ctx.setLineDash([6, 4]);
            ctx.stroke();
            // Expanding inner red circle indicator
            ctx.beginPath();
            ctx.arc(dz.cx, dz.cy, dz.r * progress, 0, Math.PI * 2);
            ctx.fillStyle = "rgba(220, 38, 38, 0.4)";
            ctx.fill();
          } else if (dz.type === "line") {
            ctx.strokeStyle = dz.color || "#ef4444";
            ctx.lineWidth = dz.width || 24;
            ctx.beginPath();
            ctx.moveTo(dz.x1, dz.y1);
            ctx.lineTo(dz.x2, dz.y2);
            ctx.stroke();
          } else if (dz.type === "cone") {
            ctx.fillStyle = dz.color ? `${dz.color}44` : "rgba(239, 68, 68, 0.35)";
            ctx.beginPath();
            ctx.moveTo(dz.cx, dz.cy);
            ctx.arc(dz.cx, dz.cy, dz.range || 150, dz.angle - dz.spread / 2, dz.angle + dz.spread / 2);
            ctx.closePath();
            ctx.fill();
          }
          // Warning Exclamation Marker
          ctx.font = "bold 13px sans-serif";
          ctx.fillStyle = "#facc15";
          ctx.textAlign = "center";
          const tx = dz.type === "rect" ? (dz.x + dz.w / 2) : (dz.type === "line" ? ((dz.x1 + dz.x2) / 2) : dz.cx);
          const ty = dz.type === "rect" ? (dz.y + dz.h / 2 + 5) : (dz.type === "line" ? ((dz.y1 + dz.y2) / 2) : (dz.cy + 5));
          ctx.fillText(dz.label || "⚠️", tx, ty);
        } else if (dz.phase === "active") {
          // Impact detonation flash!
          ctx.shadowColor = dz.color || "#ef4444";
          ctx.shadowBlur = 18;
          if (dz.type === "rect") {
            ctx.fillStyle = "rgba(254, 202, 202, 0.85)";
            ctx.fillRect(dz.x, dz.y, dz.w, dz.h);
            ctx.strokeStyle = "#ffffff";
            ctx.lineWidth = 3;
            ctx.strokeRect(dz.x, dz.y, dz.w, dz.h);
          } else if (dz.type === "circle") {
            ctx.beginPath();
            ctx.arc(dz.cx, dz.cy, dz.r, 0, Math.PI * 2);
            ctx.fillStyle = "rgba(254, 202, 202, 0.85)";
            ctx.fill();
            ctx.strokeStyle = "#ffffff";
            ctx.lineWidth = 3;
            ctx.stroke();
          } else if (dz.type === "line") {
            ctx.strokeStyle = "#ffffff";
            ctx.lineWidth = (dz.width || 24) + 6;
            ctx.beginPath();
            ctx.moveTo(dz.x1, dz.y1);
            ctx.lineTo(dz.x2, dz.y2);
            ctx.stroke();
          } else if (dz.type === "cone") {
            ctx.fillStyle = "rgba(254, 202, 202, 0.85)";
            ctx.beginPath();
            ctx.moveTo(dz.cx, dz.cy);
            ctx.arc(dz.cx, dz.cy, dz.range || 150, dz.angle - dz.spread / 2, dz.angle + dz.spread / 2);
            ctx.closePath();
            ctx.fill();
          }
          ctx.shadowBlur = 0;
        }
        ctx.restore();
      }
    }

    if (typeof renderSpecialBossTelegraphs === "function") {
      renderSpecialBossTelegraphs(ctx, ARENA, time);
    }

    // ---- 6. PICKUPS & TELEGRAPHS & SHOCKWAVES ----
    // Ground Telegraphs (Boss ground attacks)
    if (ARENA.telegraphs && ARENA.telegraphs.length > 0) {
      for (const tg of ARENA.telegraphs) {
        const progress = Math.min(1, 1 - (tg.timer / tg.maxTimer));
        ctx.save();
        ctx.strokeStyle = "rgba(239, 68, 68, 0.85)";
        ctx.lineWidth = 2.5;
        ctx.setLineDash([5, 4]);
        ctx.beginPath();
        ctx.arc(tg.x, tg.y, tg.radius, 0, Math.PI * 2);
        ctx.stroke();
        ctx.fillStyle = `rgba(239, 68, 68, ${0.15 + progress * 0.35})`;
        ctx.beginPath();
        ctx.arc(tg.x, tg.y, tg.radius * progress, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }
    }

    // Radial Expanding Shockwaves
    if (ARENA.shockwaves && ARENA.shockwaves.length > 0) {
      for (const sw of ARENA.shockwaves) {
        ctx.save();
        ctx.beginPath();
        ctx.arc(sw.x, sw.y, sw.radius, 0, Math.PI * 2);
        ctx.strokeStyle = "rgba(249, 115, 22, 0.95)";
        ctx.lineWidth = 4;
        ctx.shadowColor = "#f97316";
        ctx.shadowBlur = 12;
        ctx.stroke();
        ctx.restore();
      }
    }

    // Standard Pickups
    for (const it of ARENA.pickups) {
      if (it.type === "gold") {
        drawProceduralCoin(ctx, it.x, it.y, 6.5, time);
      } else if (it.type === "loot") {
        drawProceduralChest(ctx, it.x, it.y, time, false, false);
      } else {
        drawProceduralGem(ctx, it.x, it.y, 6.5, "#38bdf8", time);
      }
    }

    // Bouncing Physical Coins & Gems (Loot Explosion)
    if (ARENA.physicalCoins && ARENA.physicalCoins.length > 0) {
      for (const c of ARENA.physicalCoins) {
        ctx.save();
        const drawY = c.y - c.z;
        ctx.beginPath();
        ctx.ellipse(c.x, c.y + 4, 5, 2.5, 0, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(0, 0, 0, 0.35)";
        ctx.fill();
        ctx.font = `${c.size}px 'Segoe UI Emoji', 'Apple Color Emoji', sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        if (c.type === "gem") {
          drawProceduralGem(ctx, c.x, drawY, 6, c.color || "#38bdf8", time);
        } else {
          drawProceduralCoin(ctx, c.x, drawY, 6.5, time);
        }
        ctx.restore();
      }
    }

    // Falling Legendary Chest & Pillar of Light
    if (ARENA.fallingChest) {
      const fc = ARENA.fallingChest;
      ctx.save();
      if (fc.landed && fc.beamAlpha > 0) {
        const grad = ctx.createLinearGradient(fc.x, 0, fc.x, fc.targetY);
        grad.addColorStop(0, "rgba(253, 224, 71, 0)");
        grad.addColorStop(0.3, `rgba(250, 204, 21, ${fc.beamAlpha * 0.35})`);
        grad.addColorStop(1, `rgba(245, 158, 11, ${fc.beamAlpha * 0.85})`);
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.moveTo(fc.x - 22, 0);
        ctx.lineTo(fc.x + 22, 0);
        ctx.lineTo(fc.x + 34, fc.targetY + 12);
        ctx.lineTo(fc.x - 34, fc.targetY + 12);
        ctx.closePath();
        ctx.fill();

        // Rotating rays
        ctx.save();
        ctx.translate(fc.x, fc.targetY);
        ctx.rotate(fc.rayAngle);
        ctx.strokeStyle = `rgba(253, 224, 71, ${fc.beamAlpha * 0.4})`;
        ctx.lineWidth = 1.5;
        for (let r = 0; r < 8; r++) {
          ctx.beginPath();
          ctx.moveTo(0, 0);
          const ra = (r * Math.PI) / 4;
          ctx.lineTo(Math.cos(ra) * 45, Math.sin(ra) * 45);
          ctx.stroke();
        }
        ctx.restore();

        for (const sp of fc.sparkles) {
          ctx.fillStyle = `rgba(255, 255, 255, ${sp.alpha})`;
          ctx.beginPath();
          ctx.arc(sp.x, sp.y, sp.size, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      drawProceduralChest(ctx, fc.x, fc.y, time, fc.landed, fc.opened);

      if (fc.landed) {
        ctx.font = "bold 9.5px sans-serif";
        ctx.fillStyle = "#fef08a";
        ctx.shadowColor = "#000000";
        ctx.shadowBlur = 4;
        ctx.fillText("НАЖМИТЕ, ЧТОБЫ ОТКРЫТЬ!", fc.x, fc.targetY + 22);
      }
      ctx.restore();
    }

    // ---- 7. ALLIED MINIONS (WK Skeletons) ----
    for (const m of ARENA.alliedMinions) {
      ctx.fillStyle = "#1e293b";
      ctx.beginPath();
      ctx.arc(m.x, m.y, m.radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#10b981";
      ctx.lineWidth = 2;
      ctx.stroke();
      drawProceduralMinion(ctx, m, time);
    }

    // ---- 8. DOTA CREEPS & BOSSES (SOLID TOKEN SPRITES) ----
    for (const c of ARENA.creeps) {
      // Ground Shadow
      ctx.fillStyle = "rgba(0,0,0,0.3)";
      ctx.beginPath();
      ctx.ellipse(c.x, c.y + c.radius * 0.8, c.radius * 0.9, c.radius * 0.35, 0, 0, Math.PI * 2);
      ctx.fill();

      // Boss shield glow
      if (c.isBoss && c.shielded) {
        ctx.strokeStyle = "rgba(168, 85, 247, 0.8)";
        ctx.lineWidth = 3.5;
        ctx.beginPath();
        ctx.arc(c.x, c.y, c.radius + 12, 0, Math.PI * 2);
        ctx.stroke();
        ctx.fillStyle = "rgba(168, 85, 247, 0.15)";
        ctx.beginPath();
        ctx.arc(c.x, c.y, c.radius + 12, 0, Math.PI * 2);
        ctx.fill();
      }

      // PROCEDURAL VECTOR CREEP / BOSS SPRITE (ZERO EMOJIS)
      drawProceduralCreep(ctx, c, time);

      // CREEP NAME TAG
      ctx.font = c.isBoss ? "bold 9.5px sans-serif" : "bold 7.5px sans-serif";
      ctx.fillStyle = c.isBoss ? "#facc15" : "#ffffff";
      ctx.fillText(c.name, c.x, c.y - c.radius - (c.isBoss ? 16 : 10));

      // HP BAR
      const barW = c.radius * 2.2;
      const barH = c.isBoss ? 6 : 4;
      const hpPct = Math.max(0, Math.min(1, c.hp / c.maxHp));
      ctx.fillStyle = "rgba(0,0,0,0.65)";
      ctx.fillRect(c.x - barW / 2, c.y - c.radius - 6, barW, barH);
      ctx.fillStyle = c.isBoss ? "#ef4444" : (c.team === "radiant" ? "#22c55e" : "#f97316");
      ctx.fillRect(c.x - barW / 2, c.y - c.radius - 6, barW * hpPct, barH);

      // BOSS POISE (STAGGER) BAR & TORMENTOR SHIELD
      if (c.isBoss) {
        const poiseBarW = barW;
        const poiseH = 3;
        const pPct = Math.max(0, Math.min(1, (c.poise !== undefined ? c.poise : 300) / (c.maxPoise || 300)));
        ctx.fillStyle = "rgba(15, 23, 42, 0.85)";
        ctx.fillRect(c.x - poiseBarW / 2, c.y - c.radius - 11, poiseBarW, poiseH);
        ctx.fillStyle = c.isStaggered ? "#ec4899" : "#fbbf24";
        ctx.fillRect(c.x - poiseBarW / 2, c.y - c.radius - 11, poiseBarW * pPct, poiseH);

        // Stagger / Stunned / Enrage badge & visual indicators
        if (c.state === "stunned") {
          ctx.font = "bold 10px sans-serif";
          ctx.fillStyle = "#facc15";
          ctx.fillText("💫 В СТЕНЕ! ОШЕЛОМЛЕН! БЕЙ!", c.x, c.y - c.radius - 20);
          // Rotating stars over boss head
          const stAngle = (ARENA.frameCount || 0) * 0.08;
          for (let s = 0; s < 3; s++) {
            const a = stAngle + (s * Math.PI * 2) / 3;
            const sx = c.x + Math.cos(a) * (c.radius * 0.75);
            const sy = c.y - c.radius * 0.9 + Math.sin(a) * 5;
            ctx.fillStyle = "#facc15";
            ctx.beginPath();
            ctx.arc(sx, sy, 4, 0, Math.PI * 2);
            ctx.fill();
          }
        } else if (c.state === "telegraph_charge") {
          ctx.font = "bold 10px sans-serif";
          ctx.fillStyle = "#ef4444";
          ctx.fillText("⚠️ ТАРАН (УЙДИ С ЛИНИИ!)", c.x, c.y - c.radius - 20);
        } else if (c.state === "telegraph_melee") {
          ctx.font = "bold 10px sans-serif";
          ctx.fillStyle = "#f97316";
          ctx.fillText("⚠️ ЗАМАХ (ОТОЙДИ!)", c.x, c.y - c.radius - 20);
        } else if (c.isStaggered) {
          ctx.font = "bold 8.5px sans-serif";
          ctx.fillStyle = "#fbbf24";
          ctx.fillText("💫 STAGGER (+150%)", c.x, c.y - c.radius - 18);
        } else if (c.enraged) {
          ctx.font = "bold 8.5px sans-serif";
          ctx.fillStyle = "#ef4444";
          ctx.fillText("🔥 ENRAGE!", c.x, c.y - c.radius - 18);
        }

        // Tormentor Reflective Shield Ring
        if (c.tormentorShield) {
          ctx.save();
          ctx.strokeStyle = "rgba(192, 132, 252, 0.95)";
          ctx.lineWidth = 3.5;
          ctx.setLineDash([6, 3]);
          ctx.beginPath();
          ctx.arc(c.x, c.y, c.radius + 14, 0, Math.PI * 2);
          ctx.stroke();
          ctx.fillStyle = "rgba(168, 85, 247, 0.18)";
          ctx.fill();
          ctx.restore();
        }
      }
    }

    // ---- 8.5 SQUAD COMPANIONS (TRIO SQUAD MODE) ----
    if (ARENA.isBossActive && (ARENA.bossPartyMode || "trio") === "trio" && ARENA.bossCompanions) {
      for (const comp of ARENA.bossCompanions) {
        // Shadow
        ctx.fillStyle = "rgba(0, 0, 0, 0.35)";
        ctx.beginPath();
        ctx.ellipse(comp.x, comp.y + comp.radius + 2, 16, 5, 0, 0, Math.PI * 2);
        ctx.fill();

        // Procedural Hero Sprite
        drawProceduralHero(ctx, comp, comp.heroClass, time, !!comp.slashAnimation, 0);

        // Name tag
        ctx.font = "bold 7.5px sans-serif";
        ctx.fillStyle = "#38bdf8";
        ctx.textAlign = "center";
        ctx.fillText(comp.name, comp.x, comp.y - comp.radius - 6);

        // Slash Arc
        if (comp.slashAnimation) {
          const csa = comp.slashAnimation;
          ctx.save();
          ctx.translate(comp.x + 18, comp.y);
          ctx.strokeStyle = "rgba(251, 191, 36, 0.9)";
          ctx.lineWidth = 3;
          ctx.beginPath();
          ctx.arc(0, 0, csa.radius, -Math.PI * 0.35, Math.PI * 0.35);
          ctx.stroke();
          ctx.restore();
        }
      }
    }

    // ---- 9. HERO (STATIONARY TOKEN, LEFT SIDE) ----
    const p = ARENA.player;
    const heroProfile = RPG_STATE.profile || {};

    // Hero Platform / Shadow
    ctx.fillStyle = "rgba(250, 204, 21, 0.2)";
    ctx.beginPath();
    ctx.ellipse(p.x, p.y + p.radius + 2, 24, 8, 0, 0, Math.PI * 2);
    ctx.fill();

    // Pudge Flesh Heap Spiked Shield Aura
    if (p.fleshHeapActive > 0) {
      ctx.strokeStyle = "rgba(239, 68, 68, 0.7)";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.radius + 8, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Juggernaut Blade Dance Whirlwind
    if (p.bladeDanceActive > 0) {
      ctx.strokeStyle = "rgba(245, 158, 11, 0.8)";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.radius + 9, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Anti-Mage Counterspell Shield
    if (p.counterspellActive > 0) {
      ctx.strokeStyle = "rgba(56, 189, 248, 0.85)";
      ctx.lineWidth = 3.5;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.radius + 10, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Largo Croak of Genius Echo Aura
    if (p.croakTimer > 0) {
      const pulse = Math.sin((ARENA.frameCount || 0) * 0.25) * 3;
      ctx.strokeStyle = "rgba(192, 132, 252, 0.85)";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.radius + 9 + pulse, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Largo Amphibian Rhapsody Aura (активна пока включена ульта)
    if (p.largoRhapsodyActive || p.largoRhapsodyTimer > 0) {
      const spin = (ARENA.frameCount || 0) * 0.08;
      const pulse = Math.sin((ARENA.frameCount || 0) * 0.15) * 4;
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.strokeStyle = "rgba(34, 197, 94, 0.85)";
      ctx.lineWidth = 3;
      ctx.setLineDash([8, 6]);
      ctx.beginPath();
      ctx.arc(0, 0, p.radius + 16 + pulse, spin, spin + Math.PI * 2);
      ctx.stroke();

      // Golden harmonic outer ring
      ctx.strokeStyle = "rgba(250, 204, 21, 0.6)";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.arc(0, 0, p.radius + 22 - pulse * 0.5, -spin * 1.5, -spin * 1.5 + Math.PI * 2);
      ctx.stroke();
      ctx.restore();

      // Spawns soft floating musical notes around Largo
      if ((ARENA.frameCount || 0) % 45 === 0) {
        spawnFloatingText(p.x + (Math.random() - 0.5) * 30, p.y - 15, "🎶", "#4ade80");
      }
    }

    // --- VISUAL PLAYER STATUS EFFECTS (STUN, SLOW, SILENCE, DOOM, DOTs) ---
    if (p.slowTimer > 0) {
      ctx.save();
      ctx.strokeStyle = "rgba(56, 189, 248, 0.85)";
      ctx.lineWidth = 2.5;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.radius + 7, time * 0.003, time * 0.003 + Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    }
    if (p.burnTimer > 0) {
      ctx.save();
      ctx.fillStyle = "rgba(249, 115, 22, 0.35)";
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.radius + 5 + Math.sin(time * 0.01) * 3, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }
    if (p.poisonTimer > 0) {
      ctx.save();
      ctx.fillStyle = "rgba(132, 204, 22, 0.35)";
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.radius + 4 + Math.cos(time * 0.01) * 3, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }
    if (p.stunTimer > 0 || p.isFrozenInTime) {
      ctx.save();
      for (let s = 0; s < 3; s++) {
        const sAng = (time * 0.006) + (s * Math.PI * 2 / 3);
        const sx = p.x + Math.cos(sAng) * (p.radius + 6);
        const sy = p.y - p.radius - 28 + Math.sin(sAng) * 4;
        ctx.fillStyle = "#facc15";
        ctx.beginPath();
        ctx.arc(sx, sy, 3.5, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.font = "bold 9px sans-serif";
      ctx.fillStyle = "#facc15";
      ctx.textAlign = "center";
      ctx.fillText(p.isFrozenInTime ? "⏳ СТОП-ВРЕМЯ" : "💫 СТАН", p.x, p.y - p.radius - 32);
      ctx.restore();
    }
    if (p.silenceTimer > 0 || p.doomDebuffTimer > 0) {
      ctx.save();
      ctx.font = "bold 9px sans-serif";
      ctx.fillStyle = p.doomDebuffTimer > 0 ? "#ef4444" : "#c084fc";
      ctx.textAlign = "center";
      ctx.fillText(p.doomDebuffTimer > 0 ? "🔥 DOOM" : "🔇 САЙЛЕНС", p.x, p.y - p.radius - 32);
      ctx.restore();
    }
    if (p.blindTimer > 0) {
      ctx.save();
      ctx.font = "bold 8.5px sans-serif";
      ctx.fillStyle = "#ef4444";
      ctx.textAlign = "center";
      ctx.fillText("🔴 ОСЛЕПЛЕНИЕ", p.x, p.y - p.radius - 22);
      ctx.restore();
    }

    // RENDER DASH GHOST AFTERIMAGES BEHIND PLAYER
    if (ARENA.dashGhosts) {
      for (const ghost of ARENA.dashGhosts) {
        ctx.save();
        ctx.globalAlpha = ghost.alpha;
        drawProceduralHero(ctx, ghost, ghost.heroClass, time, false, 0);
        ctx.restore();
      }
    }

    // PROCEDURAL VECTOR HERO SPRITE (ZERO EMOJIS)
    const hClass = (heroProfile.hero_class || heroProfile.class_id || RPG_STATE.profile?.hero_class || "pudge").toLowerCase();
    drawProceduralHero(ctx, p, hClass, time, !!p.slashAnimation, ARENA.combo ? ARENA.combo.step : 0);

    // HERO NAME
    ctx.font = "bold 8.5px sans-serif";
    ctx.fillStyle = "#facc15";
    ctx.fillText(heroProfile.class_name ? heroProfile.class_name.split(" ")[0] : "Герой", p.x, p.y - p.radius - 22);

    // HERO HP & MP BARS
    const pHpPct = Math.max(0, Math.min(1, p.currentHp / p.maxHp));
    const pMpPct = Math.max(0, Math.min(1, p.currentMp / p.maxMp));
    const pBarW = 54;
    ctx.fillStyle = "rgba(0,0,0,0.65)";
    ctx.fillRect(p.x - pBarW / 2, p.y - p.radius - 15, pBarW, 5);
    ctx.fillStyle = "#22c55e";
    ctx.fillRect(p.x - pBarW / 2, p.y - p.radius - 15, pBarW * pHpPct, 5);
    ctx.fillStyle = "rgba(0,0,0,0.65)";
    ctx.fillRect(p.x - pBarW / 2, p.y - p.radius - 9, pBarW, 4);
    ctx.fillStyle = "#38bdf8";
    ctx.fillRect(p.x - pBarW / 2, p.y - p.radius - 9, pBarW * pMpPct, 4);

    // Melee Slash Arc
    if (p.slashAnimation) {
      const sa = p.slashAnimation;
      ctx.save();
      ctx.translate(p.x + 24, p.y);
      ctx.strokeStyle = sa.isMagic ? "rgba(56, 189, 248, 0.9)" : "rgba(250, 204, 21, 0.9)";
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.arc(0, 0, sa.radius, -Math.PI * 0.4, Math.PI * 0.4);
      ctx.stroke();
      ctx.restore();
    }

    // ---- 9.1 ACTIVE BATTLE PET (FAMILIAR) ----
    if (ARENA.pet) {
      ctx.save();
      const pet = ARENA.pet;
      const petIcons = {
        slime: "💧",
        fairy: "🧚",
        wolf: "🐺",
        dragon: "🐉",
        donkey: "🫏",
        phoenix: "🦅"
      };
      const petIcon = petIcons[pet.type] || "🐾";
      const petGlow = {
        slime: "rgba(56, 189, 248, 0.35)",
        fairy: "rgba(34, 197, 94, 0.35)",
        wolf: "rgba(239, 68, 68, 0.35)",
        dragon: "rgba(249, 115, 22, 0.35)",
        donkey: "rgba(234, 179, 8, 0.35)",
        phoenix: "rgba(245, 158, 11, 0.45)"
      };
      // Gentle floating shadow/glow
      ctx.fillStyle = petGlow[pet.type] || "rgba(249, 115, 22, 0.25)";
      ctx.beginPath();
      ctx.arc(pet.x, pet.y + 12, 11, 0, Math.PI * 2);
      ctx.fill();

      ctx.font = "20px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(petIcon, pet.x, pet.y);
      ctx.restore();
    }

    // ---- 10. PLAYER PROJECTILES (Snowball, Magic Orbs, Daggers) ----
    for (const proj of ARENA.playerProjectiles) {
      drawProceduralProjectile(ctx, proj, time);
    }

    // ---- 11. SPECIAL EFFECTS (Lightning, Rot, Omnislash, Active Items) ----
    for (const fx of ARENA.specialEffects) {
      if (fx.type === "refresher_burst") {
        ctx.save();
        const progress = 1 - (fx.timer / 35);
        const curRadius = fx.radius + (fx.maxRadius - fx.radius) * progress;
        const alpha = Math.max(0, fx.timer / 35);
        ctx.shadowColor = "#22c55e";
        ctx.shadowBlur = 25;
        ctx.strokeStyle = `rgba(34, 197, 94, ${alpha * 0.9})`;
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.ellipse(fx.x, fx.y, curRadius, curRadius * 0.45, 0, 0, Math.PI * 2);
        ctx.stroke();

        ctx.fillStyle = `rgba(74, 222, 128, ${alpha * 0.25})`;
        ctx.fill();
        ctx.shadowBlur = 0;

        for (let s = 0; s < 6; s++) {
          const spX = fx.x + Math.sin(progress * 10 + s * 1.2) * (curRadius * 0.8);
          const spY = fx.y - (progress * 60 + s * 8);
          ctx.fillStyle = `rgba(187, 247, 208, ${alpha})`;
          ctx.beginPath();
          ctx.arc(spX, spY, 2.5, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.restore();
      } else if (fx.type === "dagon_beam") {
        ctx.save();
        const alpha = Math.max(0, fx.timer / 18);
        ctx.shadowColor = fx.color || "#ef4444";
        ctx.shadowBlur = 20;
        ctx.strokeStyle = `rgba(239, 68, 68, ${alpha})`;
        ctx.lineWidth = 4.5;
        ctx.beginPath();
        ctx.moveTo(fx.fromX, fx.fromY);
        const midX = (fx.fromX + fx.toX) / 2;
        const midY = (fx.fromY + fx.toY) / 2 + (Math.random() - 0.5) * 16;
        ctx.lineTo(midX, midY);
        ctx.lineTo(fx.toX, fx.toY);
        ctx.stroke();
        ctx.strokeStyle = `rgba(255, 255, 255, ${alpha * 0.9})`;
        ctx.lineWidth = 2;
        ctx.stroke();
        ctx.restore();
      } else if (fx.type === "shiva_blast") {
        ctx.save();
        const progress = 1 - (fx.timer / 45);
        const curRadius = fx.radius + (fx.maxRadius - fx.radius) * progress;
        const alpha = Math.max(0, fx.timer / 45);
        ctx.shadowColor = "#38bdf8";
        ctx.shadowBlur = 25;
        ctx.strokeStyle = `rgba(56, 189, 248, ${alpha * 0.85})`;
        ctx.lineWidth = 5;
        ctx.beginPath();
        ctx.ellipse(fx.x, fx.y, curRadius, curRadius * 0.4, 0, 0, Math.PI * 2);
        ctx.stroke();
        ctx.fillStyle = `rgba(186, 230, 253, ${alpha * 0.15})`;
        ctx.fill();
        ctx.restore();
      } else if (fx.type === "blink_poof") {
        ctx.save();
        const alpha = Math.max(0, fx.timer / 20);
        ctx.shadowColor = "#38bdf8";
        ctx.shadowBlur = 15;
        ctx.fillStyle = `rgba(56, 189, 248, ${alpha * 0.4})`;
        ctx.beginPath();
        ctx.arc(fx.x, fx.y, 25 * (1 - alpha * 0.5), 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }
      if (fx.type === "sunstrike") {
        // --- INVOKER SUN STRIKE (Солнечный луч с неба) ---
        ctx.save();
        const progress = 1 - (fx.timer / (fx.maxTimer || 42));
        const alpha = fx.timer < 10 ? (fx.timer / 10) : (progress < 0.2 ? progress / 0.2 : 1.0);

        // 1. Vertical Sun Beam from top of sky to ground
        const beamGrad = ctx.createLinearGradient(fx.x - 26, 0, fx.x + 26, 0);
        beamGrad.addColorStop(0, "rgba(250, 204, 21, 0)");
        beamGrad.addColorStop(0.3, `rgba(250, 204, 21, ${0.45 * alpha})`);
        beamGrad.addColorStop(0.5, `rgba(255, 255, 255, ${0.95 * alpha})`);
        beamGrad.addColorStop(0.7, `rgba(250, 204, 21, ${0.45 * alpha})`);
        beamGrad.addColorStop(1, "rgba(250, 204, 21, 0)");

        ctx.fillStyle = beamGrad;
        ctx.fillRect(fx.x - 28, 0, 56, fx.y + 12);

        // Core laser white line
        ctx.strokeStyle = `rgba(255, 255, 255, ${alpha})`;
        ctx.lineWidth = 4.5;
        ctx.beginPath();
        ctx.moveTo(fx.x, 0);
        ctx.lineTo(fx.x, fx.y + 12);
        ctx.stroke();

        // 2. Expanding Radiant Solar Rings on Ground
        ctx.shadowColor = "#facc15";
        ctx.shadowBlur = 20;
        ctx.strokeStyle = `rgba(251, 191, 36, ${0.9 * alpha})`;
        ctx.lineWidth = 3.5;
        ctx.beginPath();
        ctx.ellipse(fx.x, fx.y + 2, fx.radius * progress, (fx.radius * 0.4) * progress, 0, 0, Math.PI * 2);
        ctx.stroke();

        // Inner glowing disc
        ctx.fillStyle = `rgba(254, 240, 138, ${0.35 * alpha})`;
        ctx.beginPath();
        ctx.ellipse(fx.x, fx.y + 2, (fx.radius * 0.6) * progress, (fx.radius * 0.25) * progress, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;

        // Rising solar rays / sparkles
        for (let s = 0; s < 5; s++) {
          const spX = fx.x + Math.sin(fx.timer * 0.3 + s * 1.5) * (fx.radius * 0.7);
          const spY = fx.y - ((fx.timer * 4 + s * 18) % 80);
          ctx.fillStyle = `rgba(254, 240, 138, ${0.8 * alpha})`;
          ctx.beginPath();
          ctx.arc(spX, spY, 2.5, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.restore();

      } else if (fx.type === "lightning") {
        // Vertical Lightning Bolt
        ctx.save();
        ctx.strokeStyle = "rgba(186, 230, 253, 0.95)";
        ctx.lineWidth = 6;
        ctx.beginPath();
        ctx.moveTo(fx.x, 0);
        ctx.lineTo(fx.x - 8, fx.y * 0.4);
        ctx.lineTo(fx.x + 8, fx.y * 0.7);
        ctx.lineTo(fx.x, fx.y);
        ctx.stroke();

        ctx.strokeStyle = "rgba(56, 189, 248, 0.7)";
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(fx.x, fx.y, fx.radius * (1 - fx.timer / 35), 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
      } else if (fx.type === "rot") {
        // Poison Rot Cloud across entire map
        ctx.fillStyle = "rgba(34, 197, 94, 0.22)";
        ctx.fillRect(0, 0, w, h);
      } else if (fx.type === "blood_flash") {
        ctx.fillStyle = "rgba(220, 38, 38, 0.25)";
        ctx.fillRect(0, 0, w, h);
      } else if (fx.type === "omnislash") {
        ctx.strokeStyle = "rgba(250, 204, 21, 0.9)";
        ctx.lineWidth = 3.5;
        ctx.beginPath();
        const randX = 60 + Math.sin((ARENA.frameCount || 0) * 1.5 + fx.timer) * 120 + 100;
        const randY = ARENA.roadY - 30 + Math.cos((ARENA.frameCount || 0) * 2.1 + fx.timer) * 35;
        ctx.moveTo(randX - 25, randY - 20);
        ctx.lineTo(randX + 25, randY + 20);
        ctx.stroke();
      } else if (fx.type === "croak_blast") {
        // --- LARGO CROAK OF GENIUS (Музыкальная звуковая волна) ---
        ctx.save();
        const prog = 1 - (fx.timer / (fx.maxTimer || 35));
        const alpha = Math.max(0, fx.timer / (fx.maxTimer || 35));
        ctx.shadowColor = "#c084fc";
        ctx.shadowBlur = 20;
        ctx.strokeStyle = `rgba(192, 132, 252, ${alpha * 0.9})`;
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.ellipse(fx.x, fx.y, fx.radius * prog, (fx.radius * 0.45) * prog, 0, 0, Math.PI * 2);
        ctx.stroke();

        // Musical note symbols floating up
        const notes = ["🎵", "🎶", "🐸", "✨"];
        for (let s = 0; s < 3; s++) {
          const nX = fx.x + Math.sin(prog * 8 + s * 2) * (fx.radius * 0.6 * prog);
          const nY = fx.y - (prog * 50 + s * 12);
          ctx.font = "16px sans-serif";
          ctx.fillText(notes[s % notes.length], nX - 8, nY);
        }
        ctx.restore();
      } else if (fx.type === "rhapsody_beat") {
        // --- LARGO AMPHIBIAN RHAPSODY BEAT (Каждую секунду: зеленое исцеление + золотой урон) ---
        ctx.save();
        const prog = 1 - (fx.timer / (fx.maxTimer || 35));
        const alpha = Math.max(0, fx.timer / (fx.maxTimer || 35));
        
        // Healing green inner ring
        ctx.shadowColor = "#22c55e";
        ctx.shadowBlur = 25;
        ctx.strokeStyle = `rgba(34, 197, 94, ${alpha * 0.9})`;
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.ellipse(fx.x, fx.y, (fx.radius * 0.6) * prog, (fx.radius * 0.3) * prog, 0, 0, Math.PI * 2);
        ctx.stroke();

        // Golden shockwave outer ring
        ctx.shadowColor = "#facc15";
        ctx.shadowBlur = 20;
        ctx.strokeStyle = `rgba(250, 204, 21, ${alpha * 0.85})`;
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.ellipse(fx.x, fx.y, fx.radius * prog, (fx.radius * 0.45) * prog, 0, 0, Math.PI * 2);
        ctx.stroke();

        // Floating musical notes
        const notes = ["🎵", "🎶", "💚", "✨", "🐸"];
        for (let s = 0; s < 4; s++) {
          const ang = (s * Math.PI / 2) + prog * 2;
          const nX = fx.x + Math.cos(ang) * (fx.radius * 0.7 * prog);
          const nY = fx.y + Math.sin(ang) * (fx.radius * 0.35 * prog) - (prog * 30);
          ctx.font = "15px sans-serif";
          ctx.fillText(notes[s % notes.length], nX - 7, nY);
        }
        ctx.restore();
      } else if (fx.type === "rhapsody_aura") {
        // --- LARGO CONTINUOUS AURA ---
        const p = ARENA.player;
        if (p && p.largoRhapsodyTimer > 0) {
          ctx.save();
          const ang = ((ARENA.frameCount || 0) * 0.06) % (Math.PI * 2);
          ctx.strokeStyle = "rgba(34, 197, 94, 0.45)";
          ctx.lineWidth = 2.5;
          ctx.setLineDash([10, 8]);
          ctx.beginPath();
          ctx.ellipse(p.x, p.y + 4, 180, 80, ang, 0, Math.PI * 2);
          ctx.stroke();
          ctx.restore();
        }
      } else if (fx.type === "topdown_meteor") {
        // --- INVOKER CHAOS METEOR (Падающая огненная "котлета") ---
        ctx.save();
        const prog = 1 - (fx.timer / (fx.maxTimer || 50));
        if (prog < 0.65) {
          // Flight phase: flaming asteroid hurtles from sky with trailing embers
          const ang = Math.atan2(fx.targetY - fx.startY, fx.targetX - fx.startX);
          const cos = Math.cos(ang);
          const sin = Math.sin(ang);

          // Fiery tail
          const tailLen = 65;
          const grad = ctx.createLinearGradient(fx.x - cos * tailLen, fx.y - sin * tailLen, fx.x, fx.y);
          grad.addColorStop(0, "rgba(234, 88, 12, 0)");
          grad.addColorStop(0.5, "rgba(249, 115, 22, 0.7)");
          grad.addColorStop(1, "rgba(254, 240, 138, 0.95)");
          ctx.strokeStyle = grad;
          ctx.lineWidth = 20;
          ctx.lineCap = "round";
          ctx.beginPath();
          ctx.moveTo(fx.x - cos * tailLen, fx.y - sin * tailLen);
          ctx.lineTo(fx.x, fx.y);
          ctx.stroke();

          // Core burning fireball
          ctx.fillStyle = "#f97316";
          ctx.beginPath();
          ctx.arc(fx.x, fx.y, 22, 0, Math.PI * 2);
          ctx.fill();

          ctx.fillStyle = "#fef08a";
          ctx.beginPath();
          ctx.arc(fx.x, fx.y, 14, 0, Math.PI * 2);
          ctx.fill();

          // Fiery spark particles flying backwards
          for (let s = 0; s < 4; s++) {
            const spDist = 15 + ((fx.timer * 7 + s * 16) % 55);
            const spX = fx.x - cos * spDist + (Math.sin(s * 2 + fx.timer) * 8);
            const spY = fx.y - sin * spDist + (Math.cos(s * 2 + fx.timer) * 8);
            ctx.fillStyle = s % 2 === 0 ? "#ea580c" : "#fef08a";
            ctx.beginPath();
            ctx.arc(spX, spY, 3, 0, Math.PI * 2);
            ctx.fill();
          }
        } else {
          // Impact & crater explosion phase
          const impactProg = (prog - 0.65) / 0.35;
          const alpha = 1 - impactProg;

          // Scorched crater on the ground
          ctx.fillStyle = `rgba(12, 10, 9, ${0.75 * alpha})`;
          ctx.beginPath();
          ctx.ellipse(fx.targetX, fx.targetY + 8, 48, 22, 0, 0, Math.PI * 2);
          ctx.fill();

          // Expanding explosion fireball
          const expR = 24 + impactProg * 65;
          const expGrad = ctx.createRadialGradient(fx.targetX, fx.targetY, 6, fx.targetX, fx.targetY, expR);
          expGrad.addColorStop(0, `rgba(254, 240, 138, ${0.9 * alpha})`);
          expGrad.addColorStop(0.4, `rgba(249, 115, 22, ${0.8 * alpha})`);
          expGrad.addColorStop(0.8, `rgba(220, 38, 38, ${0.6 * alpha})`);
          expGrad.addColorStop(1, "rgba(220, 38, 38, 0)");
          ctx.fillStyle = expGrad;
          ctx.beginPath();
          ctx.arc(fx.targetX, fx.targetY, expR, 0, Math.PI * 2);
          ctx.fill();

          // Expanding shockwave ring
          ctx.strokeStyle = `rgba(251, 146, 60, ${0.85 * alpha})`;
          ctx.lineWidth = 3.5;
          ctx.beginPath();
          ctx.arc(fx.targetX, fx.targetY, expR * 1.15, 0, Math.PI * 2);
          ctx.stroke();
        }
        ctx.restore();

      } else if (fx.type === "blade_fury") {
        // --- JUGGERNAUT BLADE FURY / BLADE DANCE (Золотой вихрь клинков) ---
        ctx.save();
        const spinAng = (ARENA.frameCount || 0) * 0.35;
        const bAlpha = fx.timer < 10 ? fx.timer / 10 : 0.85;
        ctx.translate(fx.x, fx.y);

        // Golden spinning energy ring
        ctx.strokeStyle = `rgba(245, 158, 11, ${0.75 * bAlpha})`;
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(0, 0, fx.radius || 48, 0, Math.PI * 2);
        ctx.stroke();

        // 4 curved crescent blades swirling
        for (let b = 0; b < 4; b++) {
          const ba = spinAng + (b * Math.PI) / 2;
          ctx.save();
          ctx.rotate(ba);
          ctx.strokeStyle = `rgba(254, 240, 138, ${0.95 * bAlpha})`;
          ctx.lineWidth = 3.5;
          ctx.beginPath();
          ctx.arc(0, 0, (fx.radius || 48) - 4, 0, Math.PI * 0.45);
          ctx.stroke();
          ctx.restore();
        }
        ctx.restore();

      } else if (fx.type === "topdown_omnislash") {
        // --- JUGGERNAUT OMNISLASH (Молниеносные золотые удары по боссу) ---
        ctx.save();
        const boss = ARENA.bossEntity;
        const cx = boss ? boss.x : fx.x;
        const cy = boss ? boss.y : fx.y;

        // Render recorded slash trails
        if (fx.slashArcs) {
          for (let s = 0; s < fx.slashArcs.length; s++) {
            const arc = fx.slashArcs[s];
            const cos = Math.cos(arc.angle);
            const sin = Math.sin(arc.angle);
            const len = 42;

            ctx.strokeStyle = "rgba(250, 204, 21, 0.9)";
            ctx.lineWidth = 4;
            ctx.beginPath();
            ctx.moveTo(arc.x - cos * len, arc.y - sin * len);
            ctx.lineTo(arc.x + cos * len, arc.y + sin * len);
            ctx.stroke();

            ctx.strokeStyle = "rgba(255, 255, 255, 0.95)";
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(arc.x - cos * len, arc.y - sin * len);
            ctx.lineTo(arc.x + cos * len, arc.y + sin * len);
            ctx.stroke();
          }
        }

        // Central slash impact glow
        ctx.strokeStyle = "rgba(245, 158, 11, 0.8)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(cx, cy, 38, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();

      } else if (fx.type === "dagger_throw") {
        // --- PHANTOM ASSASSIN STIFLING DAGGER (Летящий теневой кинжал) ---
        ctx.save();
        ctx.translate(fx.x, fx.y);
        ctx.rotate(fx.angle !== undefined ? fx.angle : 0);

        // Neon cyan/crimson blur trail
        ctx.strokeStyle = "rgba(244, 63, 94, 0.65)";
        ctx.lineWidth = 5;
        ctx.beginPath();
        ctx.moveTo(-22, 0);
        ctx.lineTo(0, 0);
        ctx.stroke();

        // Dagger blade
        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.moveTo(12, 0);
        ctx.lineTo(-6, -4);
        ctx.lineTo(-2, 0);
        ctx.lineTo(-6, 4);
        ctx.closePath();
        ctx.fill();

        // Glowing crimson tip
        ctx.fillStyle = "#f43f5e";
        ctx.beginPath();
        ctx.arc(12, 0, 3.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();

      } else if (fx.type === "slash_burst") {
        // --- PA COUP DE GRACE CRITICAL SPARK BURST ---
        ctx.save();
        const prog = 1 - (fx.timer / (fx.maxTimer || 16));
        const alpha = 1 - prog;
        const rad = 10 + prog * 28;
        ctx.strokeStyle = `rgba(244, 63, 94, ${alpha})`;
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(fx.x, fx.y, rad, 0, Math.PI * 2);
        ctx.stroke();

        ctx.strokeStyle = `rgba(255, 255, 255, ${alpha * 0.9})`;
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.moveTo(fx.x - rad, fx.y - rad);
        ctx.lineTo(fx.x + rad, fx.y + rad);
        ctx.moveTo(fx.x + rad, fx.y - rad);
        ctx.lineTo(fx.x - rad, fx.y + rad);
        ctx.stroke();
        ctx.restore();

      } else if (fx.type === "coup_de_grace") {
        // --- PHANTOM ASSASSIN COUP DE GRACE (Кровавый разрез босса x6.5) ---
        ctx.save();
        const prog = 1 - (fx.timer / (fx.maxTimer || 35));
        const alpha = 1 - prog;

        // Giant crimson diagonal slash across boss
        ctx.strokeStyle = `rgba(220, 38, 38, ${0.95 * alpha})`;
        ctx.lineWidth = 6;
        ctx.beginPath();
        ctx.moveTo(fx.x - 55, fx.y - 45);
        ctx.lineTo(fx.x + 55, fx.y + 45);
        ctx.stroke();

        ctx.strokeStyle = `rgba(254, 202, 202, ${0.9 * alpha})`;
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.moveTo(fx.x - 55, fx.y - 45);
        ctx.lineTo(fx.x + 55, fx.y + 45);
        ctx.stroke();

        // Blood droplets spray
        for (let d = 0; d < 8; d++) {
          const dropX = fx.x + Math.sin(d * 1.3) * (20 + prog * 45);
          const dropY = fx.y + Math.cos(d * 1.3) * (15 + prog * 35);
          ctx.fillStyle = `rgba(185, 28, 28, ${alpha})`;
          ctx.beginPath();
          ctx.arc(dropX, dropY, 3, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.restore();

      } else if (fx.type === "shadowraze") {
        // --- SHADOW FIEND SHADOWRAZE (Инфернальный темный столб душ) ---
        ctx.save();
        const prog = 1 - (fx.timer / (fx.maxTimer || 32));
        const alpha = fx.timer < 8 ? fx.timer / 8 : (prog < 0.25 ? prog / 0.25 : 1 - (prog - 0.25) / 0.75);

        // Ground dark runic circle
        ctx.fillStyle = `rgba(88, 28, 135, ${0.4 * alpha})`;
        ctx.beginPath();
        ctx.ellipse(fx.x, fx.y + 8, (fx.radius || 46) * prog, ((fx.radius || 46) * 0.45) * prog, 0, 0, Math.PI * 2);
        ctx.fill();

        // Vertical erupting soul pillar
        const pillarH = 75 * prog;
        const grad = ctx.createLinearGradient(fx.x, fx.y + 8, fx.x, fx.y + 8 - pillarH);
        grad.addColorStop(0, `rgba(168, 85, 247, ${0.85 * alpha})`);
        grad.addColorStop(0.5, `rgba(107, 33, 168, ${0.75 * alpha})`);
        grad.addColorStop(1, `rgba(30, 27, 75, ${0.2 * alpha})`);
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.ellipse(fx.x, fx.y + 8 - pillarH / 2, 24 * (1 - prog * 0.3), pillarH / 2, 0, 0, Math.PI * 2);
        ctx.fill();

        // Soul fire core
        ctx.strokeStyle = `rgba(233, 213, 255, ${0.9 * alpha})`;
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.moveTo(fx.x, fx.y + 8);
        ctx.lineTo(fx.x, fx.y + 8 - pillarH);
        ctx.stroke();
        ctx.restore();

      } else if (fx.type === "requiem_of_souls") {
        // --- SHADOW FIEND REQUIEM OF SOULS (Расширяющееся кольцо из 12 духов) ---
        ctx.save();
        const prog = 1 - (fx.timer / (fx.maxTimer || 45));
        const alpha = 1 - prog;
        const ringRadius = 25 + prog * 180;

        // Expanding dark mist ring
        ctx.strokeStyle = `rgba(168, 85, 247, ${0.65 * alpha})`;
        ctx.lineWidth = 3.5;
        ctx.beginPath();
        ctx.arc(fx.x, fx.y, ringRadius, 0, Math.PI * 2);
        ctx.stroke();

        // 12 flying dark souls in 360 degrees
        for (let s = 0; s < 12; s++) {
          const sa = (s * Math.PI * 2) / 12 + (prog * 0.5);
          const sx = fx.x + Math.cos(sa) * ringRadius;
          const sy = fx.y + Math.sin(sa) * ringRadius;

          // Soul head
          ctx.fillStyle = `rgba(192, 132, 252, ${0.95 * alpha})`;
          ctx.beginPath();
          ctx.arc(sx, sy, 5, 0, Math.PI * 2);
          ctx.fill();

          // Soul tail directed towards center
          ctx.strokeStyle = `rgba(126, 34, 206, ${0.7 * alpha})`;
          ctx.lineWidth = 3;
          ctx.beginPath();
          ctx.moveTo(sx, sy);
          ctx.lineTo(sx - Math.cos(sa) * 16, sy - Math.sin(sa) * 16);
          ctx.stroke();
        }
        ctx.restore();

      } else if (fx.type === "meat_hook") {
        // --- PUDGE MEAT HOOK (Железная цепь с зазубренным крюком к боссу) ---
        ctx.save();
        const hx = fx.curX !== undefined ? fx.curX : fx.toX;
        const hy = fx.curY !== undefined ? fx.curY : fx.toY;
        const ang = Math.atan2(hy - fx.fromY, hx - fx.fromX);
        const dist = Math.hypot(hx - fx.fromX, hy - fx.fromY);
        const linkCount = Math.max(3, Math.floor(dist / 14));

        // Chain links
        ctx.strokeStyle = "#94a3b8";
        ctx.lineWidth = 3.5;
        for (let l = 0; l <= linkCount; l++) {
          const lx = fx.fromX + Math.cos(ang) * (l * 14);
          const ly = fx.fromY + Math.sin(ang) * (l * 14);
          ctx.beginPath();
          ctx.ellipse(lx, ly, 6, 3, ang, 0, Math.PI * 2);
          ctx.stroke();
        }

        // Curved Meat Hook Head
        ctx.translate(hx, hy);
        ctx.rotate(ang);
        ctx.fillStyle = "#cbd5e1";
        ctx.beginPath();
        ctx.moveTo(0, -6);
        ctx.lineTo(16, 0);
        ctx.lineTo(8, 12);
        ctx.lineTo(4, 8);
        ctx.lineTo(8, 0);
        ctx.closePath();
        ctx.fill();

        ctx.strokeStyle = "#ef4444";
        ctx.lineWidth = 2;
        ctx.stroke();
        ctx.restore();

      } else if (fx.type === "pudge_dismember") {
        // --- PUDGE DISMEMBER & ROT (Ядовитое облако и удары тесаком) ---
        ctx.save();
        const prog = 1 - (fx.timer / (fx.maxTimer || 45));
        const alpha = 1 - prog;

        // Toxic Green Poison Miasma
        ctx.fillStyle = `rgba(34, 197, 94, ${0.32 * alpha})`;
        ctx.beginPath();
        ctx.arc(fx.x, fx.y, 55, 0, Math.PI * 2);
        ctx.fill();

        // Poison bubbling particles
        for (let b = 0; b < 6; b++) {
          const bx = fx.x + Math.sin(b * 1.5 + fx.timer * 0.4) * 35;
          const by = fx.y + Math.cos(b * 1.5 + fx.timer * 0.4) * 35;
          ctx.fillStyle = `rgba(134, 239, 172, ${0.85 * alpha})`;
          ctx.beginPath();
          ctx.arc(bx, by, 4, 0, Math.PI * 2);
          ctx.fill();
        }

        // Red butcher cleaver slashes on boss
        ctx.strokeStyle = `rgba(239, 68, 68, ${0.9 * alpha})`;
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.moveTo(fx.x - 25, fx.y - 20);
        ctx.lineTo(fx.x + 25, fx.y + 20);
        ctx.stroke();
        ctx.restore();

      } else if (fx.type === "wraithfire") {
        // --- WRAITH KING WRAITHFIRE BLAST (Призрачный пылающий череп) ---
        ctx.save();
        ctx.translate(fx.x, fx.y);

        // Spectral green flame trail
        ctx.strokeStyle = "rgba(16, 185, 129, 0.75)";
        ctx.lineWidth = 6;
        ctx.beginPath();
        ctx.arc(0, 0, 14, 0, Math.PI * 2);
        ctx.stroke();

        // Glowing green skull orb
        ctx.fillStyle = "#10b981";
        ctx.beginPath();
        ctx.arc(0, 0, 10, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = "#a7f3d0";
        ctx.beginPath();
        ctx.arc(0, 0, 6, 0, Math.PI * 2);
        ctx.fill();

        // Eye sockets
        ctx.fillStyle = "#064e3b";
        ctx.beginPath();
        ctx.arc(-3, -2, 1.8, 0, Math.PI * 2);
        ctx.arc(3, -2, 1.8, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();

      } else if (fx.type === "wk_skeletons") {
        // --- WRAITH KING SKELETON SUMMON AURA ---
        ctx.save();
        const alpha = Math.min(1.0, fx.timer / 30);
        ctx.strokeStyle = `rgba(16, 185, 129, ${0.65 * alpha})`;
        ctx.lineWidth = 2.5;
        ctx.setLineDash([8, 4]);
        ctx.beginPath();
        ctx.arc(fx.x, fx.y, 42, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.restore();

      } else if (fx.type === "mana_slash") {
        // --- ANTI-MAGE DUAL MANA BLADE STRIKE ---
        ctx.save();
        const prog = 1 - (fx.timer / (fx.maxTimer || 24));
        const alpha = 1 - prog;

        ctx.strokeStyle = `rgba(56, 189, 248, ${0.95 * alpha})`;
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.moveTo(fx.x - 30, fx.y - 25);
        ctx.lineTo(fx.x + 30, fx.y + 25);
        ctx.moveTo(fx.x + 30, fx.y - 25);
        ctx.lineTo(fx.x - 30, fx.y + 25);
        ctx.stroke();

        ctx.strokeStyle = `rgba(255, 255, 255, ${0.9 * alpha})`;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(fx.x - 30, fx.y - 25);
        ctx.lineTo(fx.x + 30, fx.y + 25);
        ctx.moveTo(fx.x + 30, fx.y - 25);
        ctx.lineTo(fx.x - 30, fx.y + 25);
        ctx.stroke();
        ctx.restore();

      } else if (fx.type === "mana_void") {
        // --- ANTI-MAGE MANA VOID (Коллапсирующая сфера маны и взрыв) ---
        ctx.save();
        const prog = 1 - (fx.timer / (fx.maxTimer || 40));

        if (prog < 0.5) {
          // Implosion phase: void sphere condenses inward
          const imploseR = 60 * (1 - prog * 1.5);
          ctx.fillStyle = `rgba(147, 51, 234, ${0.5 + prog})`;
          ctx.beginPath();
          ctx.arc(fx.x, fx.y, Math.max(6, imploseR), 0, Math.PI * 2);
          ctx.fill();

          ctx.strokeStyle = "#38bdf8";
          ctx.lineWidth = 3;
          ctx.beginPath();
          ctx.arc(fx.x, fx.y, Math.max(10, imploseR + 10), 0, Math.PI * 2);
          ctx.stroke();
        } else {
          // Detonation phase: massive electric shockwave explosion
          const expProg = (prog - 0.5) / 0.5;
          const expRad = 15 + expProg * 90;
          ctx.strokeStyle = `rgba(56, 189, 248, ${0.9 * (1 - expProg)})`;
          ctx.lineWidth = 4;
          ctx.beginPath();
          ctx.arc(fx.x, fx.y, expRad, 0, Math.PI * 2);
          ctx.stroke();

          ctx.strokeStyle = `rgba(168, 85, 247, ${0.8 * (1 - expProg)})`;
          ctx.lineWidth = 2.5;
          ctx.beginPath();
          ctx.arc(fx.x, fx.y, expRad * 0.75, 0, Math.PI * 2);
          ctx.stroke();
        }
        ctx.restore();

      } else if (fx.type === "croak_blast") {
        // --- LARGO CROAK OF GENIUS (Акустическая волна кваканья) ---
        ctx.save();
        const prog = 1 - (fx.timer / (fx.maxTimer || 30));
        const alpha = Math.max(0, 1 - prog);
        const curR = 15 + prog * (fx.radius || 85);
        ctx.strokeStyle = `rgba(168, 85, 247, ${0.9 * alpha})`;
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.arc(fx.x, fx.y, curR, 0, Math.PI * 2);
        ctx.stroke();

        ctx.strokeStyle = `rgba(216, 180, 254, ${0.7 * alpha})`;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(fx.x, fx.y, curR * 0.7, 0, Math.PI * 2);
        ctx.stroke();

        for (let n = 0; n < 3; n++) {
          const noteAngle = (n * Math.PI * 2 / 3) + prog * 2;
          const nx = fx.x + Math.cos(noteAngle) * curR * 0.8;
          const ny = fx.y + Math.sin(noteAngle) * curR * 0.8;
          ctx.fillStyle = `rgba(250, 204, 21, ${alpha})`;
          ctx.font = "bold 14px sans-serif";
          ctx.fillText("🎵", nx - 6, ny);
        }
        ctx.restore();

      } else if (fx.type === "rhapsody_beat") {
        // --- LARGO AMPHIBIAN RHAPSODY BEAT (Гармонический взрыв хила и урона) ---
        ctx.save();
        const prog = 1 - (fx.timer / (fx.maxTimer || 25));
        const alpha = Math.max(0, 1 - prog);
        const curR = fx.radius + (fx.maxRadius - fx.radius) * prog;

        // Emerald healing pulse
        ctx.strokeStyle = `rgba(34, 197, 94, ${0.85 * alpha})`;
        ctx.lineWidth = 4.5;
        ctx.beginPath();
        ctx.arc(fx.x, fx.y, curR, 0, Math.PI * 2);
        ctx.stroke();

        // Golden harmonic ring
        ctx.strokeStyle = `rgba(250, 204, 21, ${0.75 * alpha})`;
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.arc(fx.x, fx.y, curR * 0.85, 0, Math.PI * 2);
        ctx.stroke();

        // Central harmonic soft glow
        ctx.fillStyle = `rgba(74, 222, 128, ${0.2 * alpha})`;
        ctx.beginPath();
        ctx.arc(fx.x, fx.y, curR * 0.4, 0, Math.PI * 2);
        ctx.fill();

        ctx.restore();
      }
    }

    // ---- 12. BOSS & ENEMY PROJECTILES ----
    for (const proj of ARENA.bossProjectiles) {
      if (proj.isMeatHook) {
        ctx.save();
        ctx.fillStyle = "#78716c";
        ctx.strokeStyle = "#e2e8f0";
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.arc(proj.x, proj.y, proj.radius || 10, 0, Math.PI * 2);
        ctx.fill(); ctx.stroke();
        ctx.restore();
      } else if (proj.isSpiderBot) {
        ctx.save();
        ctx.fillStyle = "#eab308";
        ctx.fillRect(proj.x - 5, proj.y - 4, 10, 8);
        ctx.strokeStyle = "#713f12";
        ctx.lineWidth = 1.5;
        ctx.strokeRect(proj.x - 5, proj.y - 4, 10, 8);
        ctx.restore();
      } else {
        drawProceduralProjectile(ctx, { x: proj.x, y: proj.y, color: proj.color, radius: proj.radius, isBossFireball: true }, time);
      }
    }
    if (ARENA.enemyProjectiles) {
      for (const proj of ARENA.enemyProjectiles) {
        drawProceduralProjectile(ctx, proj, time);
      }
    }

    // ---- 13. FLOATING TEXTS ----
    for (const ft of ARENA.floatingTexts) {
      ctx.save();
      ctx.globalAlpha = Math.max(0, ft.opacity);
      ctx.font = "bold 12px sans-serif";
      ctx.fillStyle = ft.color;
      ctx.textAlign = "center";
      ctx.fillText(ft.text, ft.x, ft.y);
      ctx.restore();
    }

    // Close Camera Trauma translate so Top HUD & Overlays remain rock-solid in screen space
    ctx.restore();

    // ---- 14. TOP HUD (Grand Boss Banner on Boss Wave or Raid Battle) ----
    if (ARENA.isRaidBossBattle || (ARENA.isBossActive && ARENA.bossEntity)) {
      const bTarget = ARENA.bossEntity || ARENA.currentRaidBoss;
      if (bTarget) renderGrandBossHUD(ctx, clientW, clientH, bTarget, time);
    } else {
      ctx.fillStyle = "rgba(15, 23, 42, 0.88)";
      ctx.beginPath();
      safeRoundRect(ctx, 10, 56, clientW - 20, 28, 12); // Moved down from 8 to 56
      ctx.fill();

      ctx.font = "bold 11px sans-serif";
      ctx.fillStyle = "#facc15";
      ctx.textAlign = "left";
      ctx.fillText(`Этаж ${RPG_STATE.profile?.dungeon_floor || 1} • Волна ${ARENA.waveNumber}/${ARENA.waveMax}`, 18, 74); // 26 -> 74

      ctx.textAlign = "right";
      ctx.fillStyle = "#94a3b8";
      const killLabel = ARENA.isRaidBossBattle
        ? `👑 РЕЙД-БОСС: ${ARENA.bossEntity?.name || "БОСС"}`
        : `Убито: ${ARENA.creepsKilledInWave}/${ARENA.creepsNeededForWave}`;
      ctx.fillText(killLabel, w - 18, 74); // 26 -> 74
    }

    // Skill 1 & Ult CD in HUD
    let cdHudY = h - 22;
    if (ARENA.skill1Cooldown > 0) {
      const sPct = ARENA.skill1Cooldown / ARENA.skill1CooldownMax;
      ctx.fillStyle = "rgba(0,0,0,0.5)";
      ctx.fillRect(10, cdHudY, 52, 9);
      ctx.fillStyle = "#38bdf8";
      ctx.fillRect(10, cdHudY, 52 * (1 - sPct), 9);
      ctx.font = "bold 7.5px sans-serif";
      ctx.fillStyle = "#e0f2fe";
      ctx.textAlign = "left";
      ctx.fillText(`Скилл ${Math.ceil(ARENA.skill1Cooldown / 60)}с`, 12, cdHudY + 7);
      cdHudY -= 11;
    }
    if (ARENA.ultCooldown > 0) {
      const ultPct = ARENA.ultCooldown / ARENA.ultCooldownMax;
      ctx.fillStyle = "rgba(0,0,0,0.5)";
      ctx.fillRect(10, cdHudY, 52, 9);
      ctx.fillStyle = "#a855f7";
      ctx.fillRect(10, cdHudY, 52 * (1 - ultPct), 9);
      ctx.font = "bold 7.5px sans-serif";
      ctx.fillStyle = "#e9d5ff";
      ctx.textAlign = "left";
      ctx.fillText(`Ульта ${Math.ceil(ARENA.ultCooldown / 60)}с`, 12, cdHudY + 7);
    }

    // ---- 15. BLOCK WINDOW (Boss special) ----
    if (ARENA.blockWindowActive) {
      const bPct = ARENA.blockWindowTimer / ARENA.blockWindowMax;
      const pulse = 0.7 + Math.sin(Date.now() / 100) * 0.3;
      ctx.save();
      ctx.fillStyle = "rgba(0,0,0,0.55)";
      ctx.fillRect(w / 2 - 75, h / 2 - 35, 150, 65);
      ctx.strokeStyle = `rgba(59, 130, 246, ${pulse})`;
      ctx.lineWidth = 3;
      ctx.strokeRect(w / 2 - 75, h / 2 - 35, 150, 65);

      ctx.font = "bold 20px sans-serif";
      ctx.fillStyle = "#3b82f6";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("🛡️ БЛОК!", w / 2, h / 2 - 10);

      ctx.fillStyle = "rgba(0,0,0,0.5)";
      ctx.fillRect(w / 2 - 55, h / 2 + 14, 110, 7);
      ctx.fillStyle = "#3b82f6";
      ctx.fillRect(w / 2 - 55, h / 2 + 14, 110 * bPct, 7);
      ctx.restore();
    }

    // ---- 16. QTE WINDOW (Boss rage) ----
    if (ARENA.qteActive) {
      const qPct = ARENA.qteTimer / ARENA.qteMaxTimer;
      const pulse = 0.7 + Math.sin(Date.now() / 80) * 0.3;
      ctx.save();
      ctx.fillStyle = "rgba(0,0,0,0.55)";
      ctx.fillRect(w / 2 - 85, h / 2 - 38, 170, 72);
      ctx.strokeStyle = `rgba(250, 204, 21, ${pulse})`;
      ctx.lineWidth = 3;
      ctx.strokeRect(w / 2 - 85, h / 2 - 38, 170, 72);

      ctx.font = "bold 22px sans-serif";
      ctx.fillStyle = "#facc15";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("⚡ МЕГА-УДАР!", w / 2, h / 2 - 8);

      ctx.fillStyle = "rgba(0,0,0,0.5)";
      ctx.fillRect(w / 2 - 65, h / 2 + 18, 130, 7);
      ctx.fillStyle = "#facc15";
      ctx.fillRect(w / 2 - 65, h / 2 + 18, 130 * qPct, 7);
      ctx.restore();
    }

    // ---- 17. WAVE PROMPT OVERLAY ----
    if (ARENA.waveState === "prompt") {
      ctx.save();
      ctx.fillStyle = "rgba(0,0,0,0.65)";
      ctx.fillRect(0, 0, w, h);

      const cardW = 270, cardH = 152;
      const cx = w / 2 - cardW / 2, cy = h / 2 - cardH / 2;

      ctx.fillStyle = "rgba(15, 23, 42, 0.95)";
      ctx.beginPath();
      safeRoundRect(ctx, cx, cy, cardW, cardH, 16);
      ctx.fill();
      ctx.strokeStyle = "#facc15";
      ctx.lineWidth = 2;
      ctx.beginPath();
      safeRoundRect(ctx, cx, cy, cardW, cardH, 16);
      ctx.stroke();

      ctx.font = "bold 15px sans-serif";
      ctx.fillStyle = "#facc15";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";

      const nextW = ARENA.waveNumber + 1;
      const isBossNext = nextW === ARENA.waveMax;
      if (ARENA.waveNumber === 0) {
        const flr = RPG_STATE.profile?.dungeon_floor || 1;
        ctx.fillText(`🏰 Новый этаж ${flr}!`, w / 2, cy + 24);
        ctx.font = "12px sans-serif";
        ctx.fillStyle = "#94a3b8";
        ctx.fillText(`Следующая: Волна 1/${ARENA.waveMax}`, w / 2, cy + 46);
      } else {
        ctx.fillText(`✅ Волна ${ARENA.waveNumber}/${ARENA.waveMax} зачищена!`, w / 2, cy + 24);
        ctx.font = "12px sans-serif";
        ctx.fillStyle = isBossNext ? "#ef4444" : "#94a3b8";
        ctx.fillText(isBossNext ? "⚠️ Следующая: БОСС ЭТАЖА!" : `Следующая: Волна ${nextW}/${ARENA.waveMax}`, w / 2, cy + 46);
      }

      // Main action button
      const btnX = w / 2 - 95, btnY = cy + 68, btnW = 190, btnH = 34;
      ctx.fillStyle = "#facc15";
      ctx.beginPath();
      safeRoundRect(ctx, btnX, btnY, btnW, btnH, 10);
      ctx.fill();

      ctx.font = "bold 13px sans-serif";
      ctx.fillStyle = "#0f172a";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("▶ Перейти дальше", w / 2, btnY + btnH / 2);

      // Disable confirmation button right on overlay
      const optBtnX = w / 2 - 95, optBtnY = cy + 110, optBtnW = 190, optBtnH = 28;
      ctx.fillStyle = "rgba(30, 41, 59, 0.95)";
      ctx.beginPath();
      safeRoundRect(ctx, optBtnX, optBtnY, optBtnW, optBtnH, 8);
      ctx.fill();
      ctx.strokeStyle = "rgba(148, 163, 184, 0.35)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      safeRoundRect(ctx, optBtnX, optBtnY, optBtnW, optBtnH, 8);
      ctx.stroke();

      ctx.font = "bold 10px sans-serif";
      ctx.fillStyle = "#38bdf8";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("⏭️ Отключить подтверждение", w / 2, optBtnY + optBtnH / 2);

      ctx.restore();
      ARENA._promptBtnBounds = { x: btnX, y: btnY, w: btnW, h: btnH };
      ARENA._promptDisableBtnBounds = { x: optBtnX, y: optBtnY, w: optBtnW, h: optBtnH };
    }

    // ---- 18. RETRY PROMPT OVERLAY (On Death — NEVER auto clear!) ----
    if (ARENA.waveState === "retry_prompt") {
      ctx.save();
      ctx.fillStyle = "rgba(0,0,0,0.7)";
      ctx.fillRect(0, 0, w, h);

      const cardW = 270, cardH = 135;
      const cx = w / 2 - cardW / 2, cy = h / 2 - cardH / 2;

      ctx.fillStyle = "rgba(15, 23, 42, 0.95)";
      ctx.beginPath();
      safeRoundRect(ctx, cx, cy, cardW, cardH, 16);
      ctx.fill();
      ctx.strokeStyle = "#ef4444";
      ctx.lineWidth = 2;
      ctx.beginPath();
      safeRoundRect(ctx, cx, cy, cardW, cardH, 16);
      ctx.stroke();

      ctx.font = "bold 16px sans-serif";
      ctx.fillStyle = "#ef4444";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("💀 ВАШ ГЕРОЙ ПАЛ!", w / 2, cy + 28);

      ctx.font = "11.5px sans-serif";
      ctx.fillStyle = "#94a3b8";
      ctx.fillText("Этаж не зачищен! Начните заново с 1-й волны.", w / 2, cy + 52);

      const btnX = w / 2 - 95, btnY = cy + 78, btnW = 190, btnH = 38;
      ctx.fillStyle = "#ef4444";
      ctx.beginPath();
      safeRoundRect(ctx, btnX, btnY, btnW, btnH, 12);
      ctx.fill();

      ctx.font = "bold 13px sans-serif";
      ctx.fillStyle = "#ffffff";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("🔄 Начать заново (1-я волна)", w / 2, btnY + btnH / 2);

      ctx.restore();
      ARENA._promptBtnBounds = { x: btnX, y: btnY, w: btnW, h: btnH };
    }

    // ---- 18b. BOSS DEFEAT OVERLAY (On Raid Boss Defeat / Player Death) ----
    if (ARENA.waveState === "boss_defeat") {
      ctx.save();
      ctx.fillStyle = "rgba(0,0,0,0.85)";
      ctx.fillRect(0, 0, clientW, clientH);

      const cardW = Math.min(300, clientW - 32);
      const cardH = 185;
      const cx = (clientW - cardW) / 2;
      const cy = (clientH - cardH) / 2;

      ctx.fillStyle = "rgba(15, 23, 42, 0.96)";
      ctx.beginPath();
      safeRoundRect(ctx, cx, cy, cardW, cardH, 16);
      ctx.fill();
      ctx.strokeStyle = "#ef4444";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      safeRoundRect(ctx, cx, cy, cardW, cardH, 16);
      ctx.stroke();

      ctx.font = "bold 15px sans-serif";
      ctx.fillStyle = "#ef4444";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("💀 ВЫ ПОГИБЛИ В БИТВЕ С БОССОМ!", clientW / 2, cy + 26);

      const bEntity = ARENA.bossEntity;
      const hpPct = bEntity && bEntity.maxHp ? Math.max(0, Math.min(100, Math.round((bEntity.hp / bEntity.maxHp) * 100))) : 0;
      const remHp = bEntity ? formatCompact(bEntity.hp) : "0";
      const totalHp = bEntity ? formatCompact(bEntity.maxHp) : "0";
      ctx.font = "11.5px sans-serif";
      ctx.fillStyle = "#e2e8f0";
      ctx.fillText(`У босса осталось: ${hpPct}% HP (${remHp} / ${totalHp})`, clientW / 2, cy + 52);
      ctx.font = "10px sans-serif";
      ctx.fillStyle = "#94a3b8";
      ctx.fillText("Прокачайте героя, подберите билд и повторите!", clientW / 2, cy + 70);

      // Button 1: Попробовать снова
      const btnW = Math.min(230, cardW - 32);
      const btnH = 34;
      const btnX = (clientW - btnW) / 2;
      const btnY = cy + 96;
      ctx.fillStyle = "#ef4444";
      ctx.beginPath();
      safeRoundRect(ctx, btnX, btnY, btnW, btnH, 10);
      ctx.fill();
      ctx.font = "bold 12px sans-serif";
      ctx.fillStyle = "#ffffff";
      ctx.fillText("🔄 Попробовать снова", clientW / 2, btnY + btnH / 2);

      // Button 2: В лобби боссов / Начать с волны 1
      const exitBtnW = btnW;
      const exitBtnH = 30;
      const exitBtnX = btnX;
      const exitBtnY = cy + 138;
      ctx.fillStyle = "#334155";
      ctx.beginPath();
      safeRoundRect(ctx, exitBtnX, exitBtnY, exitBtnW, exitBtnH, 8);
      ctx.fill();
      ctx.font = "bold 11px sans-serif";
      ctx.fillStyle = "#cbd5e1";
      const exitLabel = ARENA.isRaidBossBattle ? "🚪 В лобби боссов" : "🏠 Начать с волны 1";
      ctx.fillText(exitLabel, clientW / 2, exitBtnY + exitBtnH / 2);

      ctx.restore();
      ARENA._bossDefeatRetryBounds = { x: btnX, y: btnY, w: btnW, h: btnH };
      ARENA._bossDefeatExitBounds = { x: exitBtnX, y: exitBtnY, w: exitBtnW, h: exitBtnH };
    }

    // ---- 19. FLOOR CLEAR OVERLAY ----
    if (ARENA.waveState === "floor_clear") {
      ctx.save();
      ctx.fillStyle = "rgba(0,0,0,0.6)";
      ctx.fillRect(0, 0, w, h);
      ctx.font = "bold 22px sans-serif";
      ctx.fillStyle = "#22c55e";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("👑 ЭТАЖ 20/20 ЗАЧИЩЕН!", w / 2, h / 2 - 10);
      ctx.font = "12px sans-serif";
      ctx.fillStyle = "#94a3b8";
      ctx.fillText("Награды начислены! Следующий этаж ждёт...", w / 2, h / 2 + 20);
      ctx.restore();
    }

    // ---- 20. BOSS INTRO OVERLAY ----
    if (ARENA.waveState === "boss_intro") {
      const pulse = 0.4 + Math.sin(Date.now() / 200) * 0.2;
      ctx.save();
      ctx.fillStyle = `rgba(0,0,0,${pulse})`;
      ctx.fillRect(0, 0, w, h);
      ctx.font = "bold 24px sans-serif";
      ctx.fillStyle = "#ef4444";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("⚠️ БОСС ЭТАЖА! (Волна 20/20) ⚠️", w / 2, h / 2 - 15);
      if (ARENA.bossEntity) {
        ctx.font = "bold 16px sans-serif";
        ctx.fillStyle = "#facc15";
        ctx.fillText(ARENA.bossEntity.name, w / 2, h / 2 + 15);
      }
      ctx.restore();
    }

    // ---- 21. BOSS VICTORY SHOWCASE OVERLAY ----
    if (ARENA.waveState === "boss_victory") {
      if (!ARENA.isRaidBossBattle && !RPG_STATE.lastBossChestReward) {
        ARENA.waveState = "fighting";
        return;
      }
      ctx.save();
      ctx.fillStyle = "rgba(0, 0, 0, 0.80)";
      ctx.fillRect(0, 0, clientW, clientH);

      const cardW = Math.min(310, clientW - 32);
      const cardH = 175;
      const cx = (clientW - cardW) / 2;
      const cy = (clientH - cardH) / 2;

      ctx.fillStyle = "rgba(15, 23, 42, 0.96)";
      ctx.beginPath();
      safeRoundRect(ctx, cx, cy, cardW, cardH, 16);
      ctx.fill();
      ctx.strokeStyle = "#facc15";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      safeRoundRect(ctx, cx, cy, cardW, cardH, 16);
      ctx.stroke();

      ctx.font = "bold 16px sans-serif";
      ctx.fillStyle = "#facc15";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("👑 РЕЙД-БОСС ПОВЕРЖЕН! 🏆", clientW / 2, cy + 30);

      ctx.font = "11.5px sans-serif";
      ctx.fillStyle = "#e2e8f0";
      ctx.fillText("Великая победа! Награда ждёт вас!", clientW / 2, cy + 58);

      const btnW = Math.min(230, cardW - 32);
      const btnH = 38;
      const btnX = (clientW - btnW) / 2;
      const btnY = cy + 102;
      ctx.fillStyle = "#eab308";
      ctx.beginPath();
      safeRoundRect(ctx, btnX, btnY, btnW, btnH, 12);
      ctx.fill();

      ctx.font = "bold 13px sans-serif";
      ctx.fillStyle = "#0f172a";
      ctx.fillText("🎁 ЗАБРАТЬ НАГРАДУ", clientW / 2, btnY + btnH / 2);
      ctx.restore();
      ARENA._promptBtnBounds = { x: btnX, y: btnY, w: btnW, h: btnH };
    }

    // DMC STYLE METER HUD (D, C, B, A, S, SS, SSS) — perfectly centered in screen space
    drawStyleMeterHUD(ctx, ARENA.styleMeter, ARENA.combo, w);

    // ---- 22. BOSS ARENA MOBILE MOVEMENT HINTS (Subtle translucent touch guides) ----
    if (ARENA.bossArenaMode && ARENA.waveState === "fighting") {
      ctx.save();
      const hintY = h - 14;
      ctx.font = "bold 9.5px sans-serif";
      // Left touch zone guide
      ctx.fillStyle = ARENA.moveInput.left ? "rgba(56, 189, 248, 0.9)" : "rgba(255, 255, 255, 0.35)";
      ctx.textAlign = "left";
      ctx.fillText("◀ БЕГ ВЛЕВО", 14, hintY);
      // Right touch zone guide
      ctx.fillStyle = ARENA.moveInput.right ? "rgba(56, 189, 248, 0.9)" : "rgba(255, 255, 255, 0.35)";
      ctx.textAlign = "right";
      ctx.fillText("БЕГ ВПРАВО ▶", w - 14, hintY);
      // Center tap hint
      ctx.fillStyle = "rgba(250, 204, 21, 0.4)";
      ctx.textAlign = "center";
      ctx.fillText("⚔️ ТАП / КНОПКИ — АТАКА", w / 2, hintY);
      ctx.restore();
    }
  }


  // ===========================================================================
  // MULTIPLAYER DUELS & CO-OP (PvP & BOSSES)
  // ===========================================================================

  async function loadCoopBosses() {
    try {
      const bosses = await api.getCoopBosses();
      RPG_STATE.coopBosses = bosses || [];
      renderRoot();
    } catch (e) {
      console.error("Failed to load co-op bosses:", e);
    }
  }

  async function createCoopRaid(bossId, isSolo = false) {
    try {
      triggerHaptic("medium");
      RPG_STATE.selectedBoss = bossId;
      const myName = RPG_STATE.profile?.user_name || "Герой";
      const oppLabel = isSolo ? "Соло-рейд" : "Босс-Рейд";
      const room = await api.inviteGame(0, myName, "rpg_coop", "white", oppLabel, bossId, isSolo, RPG_STATE.profile);
      RPG_STATE.coopRoomId = room.room_id;
      RPG_STATE.coopRoomData = room;
      startCoopPolling();
      renderRoot();
    } catch (err) {
      alert(err.message || "Не удалось создать рейд");
    }
  }

  function startCoopPolling() {
    stopCoopPolling();
    RPG_STATE.coopPolling = setInterval(async () => {
      if (!RPG_STATE.coopRoomId) return;
      try {
        const updated = await api.getGameRoom(RPG_STATE.coopRoomId);
        RPG_STATE.coopRoomData = updated;
        renderRoot();
      } catch (e) {
        if (e && (e.status === 404 || (e.message && (e.message.includes("404") || e.message.includes("не найден"))))) {
          console.warn("[Coop] Room no longer exists (404), stopping polling");
          stopCoopPolling();
          RPG_STATE.coopRoomId = null;
          RPG_STATE.coopRoomData = null;
          renderRoot();
        }
      }
    }, 1500);
  }

  function stopCoopPolling() {
    if (RPG_STATE.coopPolling) {
      clearInterval(RPG_STATE.coopPolling);
      RPG_STATE.coopPolling = null;
    }
  }

  async function sendCoopAction(actionType) {
    if (!RPG_STATE.coopRoomId) return;
    try {
      triggerHaptic(actionType === "skill" ? "heavy" : "medium");
      const bossToken = document.getElementById("coop-boss-token");
      if (bossToken) {
        bossToken.style.transform = "scale(0.88) rotate(-4deg)";
        setTimeout(() => {
          if (bossToken) bossToken.style.transform = "scale(1.08) rotate(4deg)";
          setTimeout(() => {
            if (bossToken) bossToken.style.transform = "none";
          }, 150);
        }, 100);
      }
      const updated = await api.sendGameMove(RPG_STATE.coopRoomId, { action: actionType });
      RPG_STATE.coopRoomData = updated;
      renderRoot();
    } catch (err) {
      alert(err.message || "Ошибка хода в рейде");
    }
  }

  async function addCoopBot() {
    if (!RPG_STATE.coopRoomId) return;
    try {
      triggerHaptic("medium");
      const updated = await api.addCoopBot(RPG_STATE.coopRoomId);
      RPG_STATE.coopRoomData = updated;
      renderRoot();
    } catch (err) {
      alert(err.message || "Не удалось добавить бота");
    }
  }

  function leaveCoopRoom() {
    stopCoopPolling();
    RPG_STATE.coopRoomId = null;
    RPG_STATE.coopRoomData = null;
    renderRoot();
  }

  async function joinCoopRoom(targetRoomId) {
    const input = document.getElementById("coop-room-code-input");
    const roomId = targetRoomId || input?.value?.trim();
    if (!roomId) {
      alert("Введите код комнаты рейда");
      return;
    }
    try {
      triggerHaptic("medium");
      const myName = RPG_STATE.profile?.user_name || "Герой";
      const room = await api.joinGameRoom(roomId, myName);
      RPG_STATE.coopRoomId = room.room_id || roomId;
      RPG_STATE.coopRoomData = room;
      startCoopPolling();
      renderRoot();
    } catch (err) {
      alert(err.message || "Не удалось подключиться к рейду");
    }
  }

  async function loadClassmates() {
    try {
      const res = await api.getClassmates();
      RPG_STATE.classmates = res || [];
      renderRoot();
    } catch (e) {
      console.error("Failed to load classmates:", e);
    }
  }

  async function challengeClassmate(tgId, classmateName) {
    try {
      triggerHaptic("medium");
      const myName = RPG_STATE.profile?.user_name || "Дуэлянт";
      const room = await api.inviteGame(tgId, myName, "rpg_duel", "white", classmateName);
      RPG_STATE.pvpRoomId = room.room_id;
      RPG_STATE.pvpRoomData = room;
      startPvPPolling();
      renderRoot();
    } catch (err) {
      alert(err.message || "Не удалось вызвать на дуэль");
    }
  }

  function startPvPPolling() {
    stopPvPPolling();
    RPG_STATE.pvpPolling = setInterval(async () => {
      if (!RPG_STATE.pvpRoomId) return;
      try {
        const updated = await api.getGameRoom(RPG_STATE.pvpRoomId);
        RPG_STATE.pvpRoomData = updated;
        renderRoot();
      } catch (e) {
        if (e && (e.status === 404 || (e.message && (e.message.includes("404") || e.message.includes("не найден"))))) {
          console.warn("[PvP] Room no longer exists (404), stopping polling");
          stopPvPPolling();
          RPG_STATE.pvpRoomId = null;
          RPG_STATE.pvpRoomData = null;
          renderRoot();
        }
      }
    }, 1500);
  }

  function stopPvPPolling() {
    if (RPG_STATE.pvpPolling) {
      clearInterval(RPG_STATE.pvpPolling);
      RPG_STATE.pvpPolling = null;
    }
  }

  async function sendPvPAction(actionType) {
    if (!RPG_STATE.pvpRoomId) return;
    try {
      triggerHaptic("light");
      const updated = await api.sendGameMove(RPG_STATE.pvpRoomId, { action: actionType });
      RPG_STATE.pvpRoomData = updated;
      renderRoot();
    } catch (err) {
      alert(err.message || "Ошибка хода в дуэли");
    }
  }

  function leavePvPRoom() {
    stopPvPPolling();
    RPG_STATE.pvpRoomId = null;
    RPG_STATE.pvpRoomData = null;
    renderRoot();
  }

  async function loadLeaderboard() {
    try {
      const list = await api.getRpgLeaderboard();
      RPG_STATE.leaderboard = list || [];
      renderRoot();
    } catch (e) {
      console.error("Failed to load leaderboard:", e);
    }
  }

  // ===========================================================================
  // RENDERING ROOT & SUBTABS
  // ===========================================================================


