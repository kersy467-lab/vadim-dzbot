  function drawProceduralHero(ctx, p, heroClass, time = (ARENA.frameCount || 0), isAttacking, comboStep) {
    time = (time != null ? time : (ARENA.frameCount || 0));
    const hClass = (heroClass || "pudge").toLowerCase();
    const bob = Math.sin(time * 0.14) * 2;
    const facing = (p && p.facing !== undefined) ? p.facing : 1;

    ctx.save();
    ctx.translate(p.x, p.y + bob);
    if (facing === -1) {
      ctx.scale(-1, 1);
    }

    // 1. Soft Oval Ground Shadow
    ctx.fillStyle = "rgba(0, 0, 0, 0.38)";
    ctx.beginPath();
    ctx.ellipse(0, p.radius + 3 - bob, p.radius * 0.95, 5, 0, 0, Math.PI * 2);
    ctx.fill();

    // Invulnerability / Dash Ghost Aura
    if (p.isInvulnerable > 0) {
      ctx.strokeStyle = "rgba(56, 189, 248, 0.85)";
      ctx.lineWidth = 2.5;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.arc(0, 0, p.radius + 6, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Crit Buff Glow
    if (p.critBuff) {
      ctx.fillStyle = "rgba(250, 204, 21, 0.25)";
      ctx.beginPath();
      ctx.arc(0, 0, p.radius + 8, 0, Math.PI * 2);
      ctx.fill();
    }

    if (typeof RPG_ASSETS !== "undefined" && RPG_ASSETS.heroes[hClass]) {
      const heroAsset = RPG_ASSETS.heroes[hClass];
      if (heroAsset && heroAsset.complete && heroAsset.naturalWidth > 0) {
        const size = p.radius * 5.0; // adjust scale
        ctx.drawImage(heroAsset, -size / 2, -size / 1.1, size, size);
        ctx.restore();
        return;
      }
    }

    // Class-specific Procedural Vector Geometry
    if (hClass.includes("pudge")) {
      // --- PUDGE (Мясник) ---
      // Rot gas wisps
      if (p.rotActive > 0 || (time % 20 < 10)) {
        ctx.fillStyle = "rgba(34, 197, 94, 0.22)";
        for (let i = 0; i < 3; i++) {
          const rx = Math.sin(time * 0.1 + i * 2) * 16;
          const ry = -18 - (time * 0.4 + i * 8) % 18;
          ctx.beginPath();
          ctx.arc(rx, ry, 5 + i, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      // Big round body (decaying greenish flesh)
      ctx.fillStyle = "#3d4b35";
      ctx.beginPath();
      ctx.ellipse(0, 2, 17, 18, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#1e2619";
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Stitches across belly
      ctx.strokeStyle = "#141c10";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(-6, -4); ctx.lineTo(4, 8);
      ctx.moveTo(-7, 2); ctx.lineTo(-1, -2);
      ctx.moveTo(0, 7); ctx.lineTo(6, 3);
      ctx.stroke();

      // Blood-stained butcher apron
      ctx.fillStyle = "#7f1d1d";
      ctx.beginPath();
      ctx.moveTo(-8, -4);
      ctx.lineTo(8, -4);
      ctx.lineTo(10, 16);
      ctx.lineTo(-10, 16);
      ctx.closePath();
      ctx.fill();

      // Apron blood splatters
      ctx.fillStyle = "#450a0a";
      ctx.beginPath();
      ctx.arc(-2, 4, 3, 0, Math.PI * 2);
      ctx.arc(4, 10, 2.5, 0, Math.PI * 2);
      ctx.fill();

      // Head
      ctx.fillStyle = "#4a5940";
      ctx.beginPath();
      ctx.arc(2, -13, 9, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // Glowing yellow sinister eye
      ctx.fillStyle = "#facc15";
      ctx.shadowColor = "#facc15";
      ctx.shadowBlur = 6;
      ctx.beginPath();
      ctx.arc(5, -14, 2, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

      // Heavy Iron Cleaver (in right hand)
      const cleaverAngle = isAttacking ? (comboStep === 2 ? 1.4 : 0.8) : 0.15;
      ctx.save();
      ctx.translate(8, 2);
      ctx.rotate(cleaverAngle);
      // Cleaver blade
      ctx.fillStyle = "#1e293b";
      ctx.strokeStyle = "#94a3b8";
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.rect(0, -18, 14, 12);
      ctx.fill();
      ctx.stroke();
      // Sharp cutting edge
      ctx.fillStyle = "#e2e8f0";
      ctx.fillRect(12, -18, 2.5, 12);
      // Wooden handle
      ctx.fillStyle = "#78350f";
      ctx.fillRect(-2, -6, 4, 10);
      ctx.restore();

      // Hook chain (left hand)
      ctx.strokeStyle = "#64748b";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(-10, 4);
      ctx.quadraticCurveTo(-16, 12, -12, 16);
      ctx.stroke();
      // Hook curve
      ctx.strokeStyle = "#cbd5e1";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.arc(-13, 17, 4, 0, Math.PI * 1.5, false);
      ctx.stroke();

    } else if (hClass.includes("juggernaut")) {
      // --- JUGGERNAUT (Юрнеро) ---
      // Flowing red/orange samurai hakama
      ctx.fillStyle = "#b91c1c";
      ctx.beginPath();
      ctx.moveTo(-8, 0);
      ctx.lineTo(8, 0);
      ctx.lineTo(11, 17);
      ctx.lineTo(-11, 17);
      ctx.closePath();
      ctx.fill();

      // Gold obi sash
      ctx.fillStyle = "#f59e0b";
      ctx.fillRect(-9, 0, 18, 4);

      // Emerald green vest
      ctx.fillStyle = "#047857";
      ctx.beginPath();
      ctx.moveTo(-7, -10);
      ctx.lineTo(7, -10);
      ctx.lineTo(8, 0);
      ctx.lineTo(-8, 0);
      ctx.closePath();
      ctx.fill();

      // White demon ancestral mask
      ctx.fillStyle = "#fef3c7";
      ctx.strokeStyle = "#d97706";
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.ellipse(3, -12, 7.5, 8.5, 0.1, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // Red mask warpaint stripes
      ctx.strokeStyle = "#dc2626";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(1, -16); ctx.lineTo(1, -8);
      ctx.moveTo(5, -16); ctx.lineTo(5, -8);
      ctx.stroke();

      // Glowing amber eye slits
      ctx.fillStyle = "#f59e0b";
      ctx.shadowColor = "#f59e0b";
      ctx.shadowBlur = 6;
      ctx.fillRect(4, -13, 3, 1.5);
      ctx.shadowBlur = 0;

      // Fluttering samurai ponytail
      const hairWave = Math.sin(time * 0.2) * 3;
      ctx.strokeStyle = "#18181b";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(-4, -14);
      ctx.quadraticCurveTo(-12, -18 + hairWave, -16, -12 + hairWave);
      ctx.stroke();

      // Curved Katana with glowing edge
      const swordSwing = isAttacking ? (comboStep === 2 ? 1.6 : 0.9) : -0.3;
      ctx.save();
      ctx.translate(6, -2);
      ctx.rotate(swordSwing);
      // Tsuba guard
      ctx.fillStyle = "#d97706";
      ctx.fillRect(-2, -2, 4, 4);
      // Blade
      ctx.strokeStyle = "#f8fafc";
      ctx.lineWidth = 2;
      ctx.shadowColor = "#f59e0b";
      ctx.shadowBlur = 8;
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.quadraticCurveTo(10, -18, 16, -26);
      ctx.stroke();
      ctx.shadowBlur = 0;
      // Katana hilt
      ctx.fillStyle = "#451a03";
      ctx.fillRect(-2, 2, 4, 9);
      ctx.restore();

    } else if (hClass.includes("invoker")) {
      // --- INVOKER (Карл) ---
      // Levitation float
      const lev = Math.sin(time * 0.1) * 3;
      ctx.translate(0, -lev);

      // Royal crimson cape with high standing collar
      ctx.fillStyle = "#881337";
      ctx.beginPath();
      ctx.moveTo(-9, -15);
      ctx.lineTo(4, -15);
      ctx.lineTo(8, 17);
      ctx.lineTo(-14, 18);
      ctx.closePath();
      ctx.fill();
      // Gold embroidery border
      ctx.strokeStyle = "#facc15";
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Royal purple & gold robes
      ctx.fillStyle = "#581c87";
      ctx.beginPath();
      ctx.moveTo(-6, -7);
      ctx.lineTo(6, -7);
      ctx.lineTo(8, 15);
      ctx.lineTo(-6, 15);
      ctx.closePath();
      ctx.fill();

      // Head & blonde hair
      ctx.fillStyle = "#fed7aa";
      ctx.beginPath();
      ctx.arc(1, -12, 7, 0, Math.PI * 2);
      ctx.fill();
      // Flowing platinum blonde hair
      ctx.fillStyle = "#fef08a";
      ctx.beginPath();
      ctx.moveTo(-6, -14);
      ctx.quadraticCurveTo(-11, -8, -13, 2);
      ctx.lineTo(-4, -10);
      ctx.closePath();
      ctx.fill();

      // Glowing arcane eyes
      ctx.fillStyle = "#e0e7ff";
      ctx.shadowColor = "#818cf8";
      ctx.shadowBlur = 6;
      ctx.fillRect(3, -13, 2.5, 2);
      ctx.shadowBlur = 0;

      // Arcane Crystal Staff
      ctx.save();
      ctx.translate(9, -2);
      ctx.strokeStyle = "#eab308";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(0, 15); ctx.lineTo(0, -20);
      ctx.stroke();
      // Floating crystal at staff head
      ctx.fillStyle = "#38bdf8";
      ctx.shadowColor = "#38bdf8";
      ctx.shadowBlur = 10;
      ctx.beginPath();
      ctx.moveTo(0, -28); ctx.lineTo(4, -22); ctx.lineTo(0, -16); ctx.lineTo(-4, -22);
      ctx.closePath();
      ctx.fill();
      ctx.shadowBlur = 0;
      ctx.restore();

      // 3 REVOLVING ELEMENTAL ORBS IN 3D ORBIT (Quas, Wex, Exort)
      const orbitR = 21;
      const orbs = [
        { name: "Quas", color: "#38bdf8", glow: "#0284c7", angle: time * 0.05 },
        { name: "Wex", color: "#c084fc", glow: "#9333ea", angle: time * 0.05 + 2.094 },
        { name: "Exort", color: "#f97316", glow: "#ea580c", angle: time * 0.05 + 4.188 }
      ];
      for (const orb of orbs) {
        const ox = Math.cos(orb.angle) * orbitR;
        const oy = Math.sin(orb.angle) * (orbitR * 0.42) - 8;
        ctx.fillStyle = orb.color;
        ctx.shadowColor = orb.glow;
        ctx.shadowBlur = 9;
        ctx.beginPath();
        ctx.arc(ox, oy, 4.5, 0, Math.PI * 2);
        ctx.fill();
        // Bright core
        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(ox - 1, oy - 1, 1.8, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;
      }

    } else if (hClass.includes("phantom") || hClass.includes("pa")) {
      // --- PHANTOM ASSASSIN (Мортред) ---
      // Shadow cloak dissolving into mist
      ctx.fillStyle = "rgba(15, 23, 42, 0.9)";
      ctx.beginPath();
      ctx.moveTo(-6, -10);
      ctx.lineTo(6, -10);
      ctx.lineTo(9, 16);
      ctx.lineTo(-12, 16);
      ctx.closePath();
      ctx.fill();

      // Cyan misty trail motes
      ctx.fillStyle = "rgba(34, 211, 238, 0.45)";
      for (let i = 0; i < 3; i++) {
        const mx = -10 - (time * 0.6 + i * 5) % 12;
        const my = 8 + Math.sin(time * 0.2 + i) * 6;
        ctx.beginPath();
        ctx.arc(mx, my, 2.5, 0, Math.PI * 2);
        ctx.fill();
      }

      // Torso / armor
      ctx.fillStyle = "#0e7490";
      ctx.beginPath();
      ctx.moveTo(-5, -6); ctx.lineTo(5, -6); ctx.lineTo(6, 6); ctx.lineTo(-5, 6);
      ctx.closePath();
      ctx.fill();

      // Assassin Cowl / Hood
      ctx.fillStyle = "#0f172a";
      ctx.beginPath();
      ctx.arc(2, -12, 8, 0, Math.PI * 2);
      ctx.fill();
      ctx.beginPath();
      ctx.moveTo(-6, -12); ctx.lineTo(8, -12); ctx.lineTo(4, -3);
      ctx.closePath();
      ctx.fill();

      // Glowing Cyan Assassin Slit Eyes
      ctx.fillStyle = "#22d3ee";
      ctx.shadowColor = "#22d3ee";
      ctx.shadowBlur = 9;
      ctx.fillRect(4, -13, 3, 1.5);
      ctx.shadowBlur = 0;

      // Dual Phantom Daggers with Cyan Poison
      const dagAngle = isAttacking ? 1.2 : 0.2;
      ctx.save();
      ctx.translate(7, 2);
      ctx.rotate(dagAngle);
      // Dagger 1
      ctx.strokeStyle = "#22d3ee";
      ctx.lineWidth = 2.5;
      ctx.shadowColor = "#22d3ee";
      ctx.shadowBlur = 7;
      ctx.beginPath();
      ctx.moveTo(0, 0); ctx.lineTo(12, -10); ctx.lineTo(15, -9);
      ctx.stroke();
      ctx.shadowBlur = 0;
      // Dagger 2
      ctx.strokeStyle = "#67e8f9";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(-2, 4); ctx.lineTo(8, -4);
      ctx.stroke();
      ctx.restore();

    } else if (hClass.includes("shadow_fiend") || hClass.includes("sf")) {
      // --- SHADOW FIEND (Невермор) ---
      // Swirling Demonic Shadow Vortex Base (no feet)
      const swirl = Math.sin(time * 0.25) * 4;
      ctx.fillStyle = "#09090b";
      ctx.beginPath();
      ctx.moveTo(-10, 0);
      ctx.quadraticCurveTo(swirl, 16, 2, 22);
      ctx.quadraticCurveTo(-swirl, 16, 10, 0);
      ctx.closePath();
      ctx.fill();

      // Demon Spire Shoulders
      ctx.fillStyle = "#18181b";
      ctx.beginPath();
      ctx.moveTo(-16, -14); ctx.lineTo(-6, -4); ctx.lineTo(0, -6);
      ctx.lineTo(6, -4); ctx.lineTo(16, -14); ctx.lineTo(8, 2); ctx.lineTo(-8, 2);
      ctx.closePath();
      ctx.fill();

      // Roaring Soul-Furnace Chest Core
      const pulse = 1 + Math.sin(time * 0.2) * 0.25;
      ctx.fillStyle = "#ea580c";
      ctx.shadowColor = "#f97316";
      ctx.shadowBlur = 12 * pulse;
      ctx.beginPath();
      ctx.arc(0, -3, 6 * pulse, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#fef08a";
      ctx.beginPath();
      ctx.arc(0, -3, 3, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

      // Horned Demon Head
      ctx.fillStyle = "#09090b";
      ctx.beginPath();
      ctx.arc(1, -14, 7, 0, Math.PI * 2);
      ctx.fill();
      // Curved ram horns
      ctx.strokeStyle = "#450a0a";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.moveTo(-4, -16); ctx.quadraticCurveTo(-11, -24, -8, -26);
      ctx.moveTo(6, -16); ctx.quadraticCurveTo(13, -24, 10, -26);
      ctx.stroke();

      // Glowing Crimson Eyes & Fangs
      ctx.fillStyle = "#ef4444";
      ctx.shadowColor = "#ef4444";
      ctx.shadowBlur = 8;
      ctx.fillRect(2, -15, 3, 1.8);
      ctx.fillRect(1, -11, 4, 1.2);
      ctx.shadowBlur = 0;

      // Soul Fire Hands
      ctx.fillStyle = "#f97316";
      ctx.shadowColor = "#f97316";
      ctx.shadowBlur = 8;
      ctx.beginPath();
      ctx.arc(12, 0, 4, 0, Math.PI * 2);
      ctx.arc(-12, 0, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

    } else if (hClass.includes("wraith_king") || hClass.includes("wk")) {
      // --- WRAITH KING (Остарион) ---
      // Tattered emerald mantle
      ctx.fillStyle = "#064e3b";
      ctx.beginPath();
      ctx.moveTo(-9, -10); ctx.lineTo(7, -10); ctx.lineTo(10, 18); ctx.lineTo(-13, 18);
      ctx.closePath();
      ctx.fill();

      // Spectral Green Plate Armor
      ctx.fillStyle = "#065f46";
      ctx.strokeStyle = "#10b981";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.rect(-8, -6, 16, 16);
      ctx.fill();
      ctx.stroke();

      // Skeletal Skull Face
      ctx.fillStyle = "#e2e8f0";
      ctx.beginPath();
      ctx.arc(1, -12, 7.5, 0, Math.PI * 2);
      ctx.fill();

      // Blazing Emerald Soul Fire in Eye Sockets
      ctx.fillStyle = "#10b981";
      ctx.shadowColor = "#10b981";
      ctx.shadowBlur = 10;
      ctx.beginPath();
      ctx.arc(3, -13, 2.2, 0, Math.PI * 2);
      ctx.arc(-1, -13, 2.2, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

      // Spiked Golden Bone Crown
      ctx.fillStyle = "#eab308";
      ctx.strokeStyle = "#ca8a04";
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(-7, -17);
      ctx.lineTo(-5, -23);
      ctx.lineTo(-2, -18);
      ctx.lineTo(1, -26);
      ctx.lineTo(4, -18);
      ctx.lineTo(7, -23);
      ctx.lineTo(9, -17);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();

      // Colossal Runic Zweihander Broadsword
      const swordSwing = isAttacking ? 1.4 : 0.2;
      ctx.save();
      ctx.translate(9, 2);
      ctx.rotate(swordSwing);
      // Giant blade with green soul edge
      ctx.fillStyle = "#1e293b";
      ctx.strokeStyle = "#10b981";
      ctx.lineWidth = 2;
      ctx.shadowColor = "#10b981";
      ctx.shadowBlur = 9;
      ctx.beginPath();
      ctx.moveTo(-3, 0); ctx.lineTo(3, 0); ctx.lineTo(4, -28); ctx.lineTo(0, -33); ctx.lineTo(-4, -28);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.shadowBlur = 0;
      // Skull crossguard
      ctx.fillStyle = "#eab308";
      ctx.fillRect(-7, 0, 14, 3.5);
      // Hilt
      ctx.fillStyle = "#451a03";
      ctx.fillRect(-1.5, 3.5, 3, 9);
      ctx.restore();

    } else if (hClass.includes("anti_mage") || hClass.includes("am")) {
      // --- ANTI-MAGE (Магина) ---
      // Indigo monk pants
      ctx.fillStyle = "#312e81";
      ctx.beginPath();
      ctx.moveTo(-7, 0); ctx.lineTo(7, 0); ctx.lineTo(9, 17); ctx.lineTo(-9, 17);
      ctx.closePath();
      ctx.fill();

      // Gold sash belt
      ctx.fillStyle = "#f59e0b";
      ctx.fillRect(-8, 0, 16, 3.5);

      // Muscular torso with purple mana burn tattoos
      ctx.fillStyle = "#fed7aa";
      ctx.beginPath();
      ctx.rect(-6, -9, 12, 9);
      ctx.fill();
      // Glowing purple tattoos
      ctx.strokeStyle = "#c084fc";
      ctx.lineWidth = 1.5;
      ctx.shadowColor = "#a855f7";
      ctx.shadowBlur = 6;
      ctx.beginPath();
      ctx.moveTo(-4, -7); ctx.lineTo(-1, -3); ctx.lineTo(3, -7);
      ctx.stroke();
      ctx.shadowBlur = 0;

      // Monk head
      ctx.fillStyle = "#fed7aa";
      ctx.beginPath();
      ctx.arc(0, -13, 7, 0, Math.PI * 2);
      ctx.fill();

      // Purple Monk Blindfold
      ctx.fillStyle = "#6b21a8";
      ctx.fillRect(-6, -15, 13, 4.5);
      ctx.fillStyle = "#e9d5ff";
      ctx.fillRect(-2, -14, 5, 2);

      // Twin Crescent Mana Glaives in both hands
      const glaiveSwing = isAttacking ? 1.3 : 0.1;
      ctx.save();
      ctx.translate(6, 0);
      ctx.rotate(glaiveSwing);
      // Front Glaive
      ctx.strokeStyle = "#c084fc";
      ctx.lineWidth = 3;
      ctx.shadowColor = "#9333ea";
      ctx.shadowBlur = 9;
      ctx.beginPath();
      ctx.arc(2, -4, 11, -Math.PI * 0.4, Math.PI * 0.6, false);
      ctx.stroke();
      ctx.shadowBlur = 0;
      // Handle
      ctx.fillStyle = "#e2e8f0";
      ctx.fillRect(0, -7, 4, 6);
      ctx.restore();

      // Back Glaive
      ctx.save();
      ctx.translate(-7, 2);
      ctx.rotate(-glaiveSwing * 0.8);
      ctx.strokeStyle = "#a855f7";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.arc(-2, -4, 9, -Math.PI * 0.5, Math.PI * 0.5, true);
      ctx.stroke();
      ctx.restore();

    } else {
      // --- DEFAULT WARRIOR / HERO FALLBACK ---
      ctx.fillStyle = "#1e293b";
      ctx.beginPath(); ctx.arc(0, 0, 14, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = "#facc15"; ctx.lineWidth = 2; ctx.stroke();
      ctx.fillStyle = "#facc15";
      ctx.fillRect(4, -10, 4, 20);
    }

    ctx.restore();
  }

  // ===========================================================================
  // PROCEDURAL CREEP & MONSTER SPRITE RENDERER
  // ===========================================================================

  function drawProceduralCreep(ctx, c, time = (ARENA.frameCount || 0)) {
    time = (time != null ? time : (ARENA.frameCount || 0));
    const bob = Math.sin(time * 0.16 + c.x * 0.05) * 1.8;
    const type = (c.archetype || c.team || "melee").toLowerCase();

    ctx.save();
    ctx.translate(c.x, c.y + bob + (c.jumpY || 0));

    // Ground Shadow (pinned to road floor even if boss is leaping high in the air)
    const shadowScale = c.isBoss ? Math.max(0.35, 1.0 - Math.abs(c.jumpY || 0) / 95) : 1.0;
    ctx.fillStyle = `rgba(0, 0, 0, ${0.32 * shadowScale})`;
    ctx.beginPath();
    ctx.ellipse(0, c.radius + 2 - bob - (c.jumpY || 0), (c.radius * 0.9) * shadowScale, 4.5 * shadowScale, 0, 0, Math.PI * 2);
    ctx.fill();

    // God Mode Aura
    if (c.isGodMode || c.enrageStage === "god_mode") {
      const pulse = 1 + Math.sin(time * 0.25) * 0.15;
      ctx.strokeStyle = "rgba(239, 68, 68, 0.85)";
      ctx.lineWidth = 3;
      ctx.shadowColor = "#ef4444";
      ctx.shadowBlur = 14;
      ctx.beginPath();
      ctx.arc(0, 0, (c.radius + 8) * pulse, 0, Math.PI * 2);
      ctx.stroke();
      ctx.shadowBlur = 0;
    }

    // Stagger / Stun indicator stars
    if (c.state === "stagger" || c.isStaggered) {
      ctx.fillStyle = "#facc15";
      ctx.shadowColor = "#facc15";
      ctx.shadowBlur = 6;
      for (let s = 0; s < 3; s++) {
        const starAng = time * 0.15 + s * 2.09;
        const sx = Math.cos(starAng) * (c.radius + 6);
        const sy = Math.sin(starAng) * 4 - c.radius - 8;
        ctx.beginPath();
        ctx.arc(sx, sy, 2.5, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.shadowBlur = 0;
    }

    // Panic sweat drops
    if (c.state === "panic") {
      ctx.fillStyle = "#38bdf8";
      for (let w = 0; w < 2; w++) {
        const px = (w === 0 ? -6 : 6);
        const py = -c.radius - 10 + (time * 0.3 + w * 4) % 10;
        ctx.beginPath();
        ctx.arc(px, py, 2, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Captain Aura on Ground
    if (type === "captain" || c.isCaptain) {
      const auraPulse = 1 + Math.sin(time * 0.1) * 0.12;
      ctx.strokeStyle = "rgba(250, 204, 21, 0.65)";
      ctx.lineWidth = 2.5;
      ctx.setLineDash([6, 6]);
      ctx.beginPath();
      ctx.ellipse(0, c.radius + 2 - bob, 48 * auraPulse, 16 * auraPulse, 0, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Captain Buff Ring on Minions
    if (c.hasCaptainBuff) {
      ctx.strokeStyle = "rgba(234, 179, 8, 0.4)";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(0, 0, c.radius + 4, 0, Math.PI * 2);
      ctx.stroke();
    }

    // ARCHETYPE RENDERING:
    if (c.isBoss) {
      // --- EPIC BOSS SPRITES (Proportional scaling) ---
      const bScale = (c.radius || 44) / 28;
      ctx.save();
      ctx.scale(bScale, bScale);

      const bId = (c.bossType || c.boss_id || c.id || c.name || "").toLowerCase();
      let drawn = false;

      if (typeof RPG_ASSETS !== "undefined") {
        let assetKey = null;
        if (bId.includes("roshan") || bId.includes("рошан") || bId.includes("огненный демон")) assetKey = "roshan";
        else if (bId.includes("terrorblade") || bId.includes("террорблейд") || bId.includes("демон бездны")) assetKey = "terrorblade";
        else if (bId.includes("void") || bId.includes("хроно") || bId.includes("faceless") || bId.includes("хроно-владыка")) assetKey = "faceless_void";
        else if (bId.includes("мясник") || bId.includes("butcher")) assetKey = "butcher";
        else if (bId.includes("повелитель теней") || bId.includes("shadow")) assetKey = "shadow_lord";

        if (assetKey && RPG_ASSETS.bosses && RPG_ASSETS.bosses[assetKey]) {
          const bossAsset = RPG_ASSETS.bosses[assetKey];
          if (bossAsset && bossAsset.complete && bossAsset.naturalWidth > 0) {
            const size = 110; 
            ctx.drawImage(bossAsset, -size / 2, -size / 1.1, size, size);
            drawn = true;
          }
        }
      }

      if (!drawn && typeof drawBossModelEarly === "function") drawn = drawBossModelEarly(ctx, c, bId, time);
      if (!drawn && typeof drawBossModelMid === "function") drawn = drawBossModelMid(ctx, c, bId, time);
      if (!drawn && typeof drawBossModelLate === "function") drawn = drawBossModelLate(ctx, c, bId, time);

      if (!drawn) {
        // Fallback Colossus Brute
        ctx.fillStyle = "#334155";
        ctx.strokeStyle = "#ea580c";
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.ellipse(0, 0, 26, 22, 0, 0, Math.PI * 2);
        ctx.fill(); ctx.stroke();
        ctx.strokeStyle = "#f97316";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(-12, -8); ctx.lineTo(-2, 4); ctx.lineTo(14, -6);
        ctx.stroke();
      }
      ctx.restore();

    } else if (type.includes("defender")) {
      // --- SHIELDED DEFENDER (Пехотинец со щитом) ---
      // Heavy plate body
      ctx.fillStyle = "#334155";
      ctx.beginPath();
      ctx.rect(-8, -12, 16, 22);
      ctx.fill();
      // Helmet with narrow slit
      ctx.fillStyle = "#1e293b";
      ctx.beginPath();
      ctx.arc(0, -14, 8, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#facc15";
      ctx.fillRect(-4, -15, 6, 1.8);

      // Giant Tower Heater Shield (Facing Left towards player)
      const shieldBroken = c.shieldBrokenTimer > 0;
      ctx.save();
      ctx.translate(-10, 0);
      if (shieldBroken) {
        ctx.rotate(-0.4);
        ctx.strokeStyle = "#ef4444";
      } else {
        ctx.strokeStyle = "#38bdf8";
      }
      // Shield Face
      ctx.fillStyle = shieldBroken ? "#475569" : "#1e293b";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(0, -18);
      ctx.lineTo(-10, -16);
      ctx.lineTo(-10, 10);
      ctx.lineTo(0, 18);
      ctx.lineTo(6, 10);
      ctx.lineTo(6, -16);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();

      // Shield Cross / Crest
      ctx.fillStyle = shieldBroken ? "#991b1b" : "#eab308";
      ctx.fillRect(-6, -6, 8, 3);
      ctx.fillRect(-4, -10, 4, 11);

      // Guard Shield Sheen
      if (!shieldBroken) {
        ctx.fillStyle = "rgba(56, 189, 248, 0.25)";
        ctx.shadowColor = "#38bdf8";
        ctx.shadowBlur = 8;
        ctx.beginPath();
        ctx.arc(-5, 0, 14, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;
      }
      ctx.restore();

      // Spear behind shield
      ctx.strokeStyle = "#94a3b8";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(-16, -4); ctx.lineTo(12, -4);
      ctx.stroke();

    } else if (type.includes("ranged") || type.includes("mage") || type.includes("маг")) {
      // --- RANGED MAGE / ARCHER ---
      const isRadiant = type.includes("radiant") || type.includes("свет");
      // Robes
      ctx.fillStyle = isRadiant ? "#15803d" : "#581c87";
      ctx.beginPath();
      ctx.moveTo(-6, -10); ctx.lineTo(6, -10); ctx.lineTo(9, 15); ctx.lineTo(-9, 15);
      ctx.closePath();
      ctx.fill();

      // Pointed Hood
      ctx.fillStyle = isRadiant ? "#166534" : "#3b0764";
      ctx.beginPath();
      ctx.moveTo(-8, -8); ctx.lineTo(8, -8); ctx.lineTo(0, -22);
      ctx.closePath();
      ctx.fill();

      // Glowing Eyes in hood darkness
      ctx.fillStyle = isRadiant ? "#38bdf8" : "#f43f5e";
      ctx.shadowColor = ctx.fillStyle;
      ctx.shadowBlur = 6;
      ctx.fillRect(-4, -12, 2.5, 1.8);
      ctx.shadowBlur = 0;

      // Wooden Staff with Pulsing Magic Orb
      ctx.save();
      ctx.translate(-9, -2);
      ctx.strokeStyle = "#78350f";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(0, 16); ctx.lineTo(0, -18);
      ctx.stroke();

      // Pulsing magic orb at tip
      const orbPulse = 1 + Math.sin(time * 0.2) * 0.2;
      ctx.fillStyle = isRadiant ? "#38bdf8" : "#c084fc";
      ctx.shadowColor = ctx.fillStyle;
      ctx.shadowBlur = 10 * orbPulse;
      ctx.beginPath();
      ctx.arc(0, -22, 4.5 * orbPulse, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
      ctx.restore();

    } else if (type.includes("catapult") || type.includes("катапульта")) {
      // --- SIEGE CATAPULT ---
      // Heavy timber cart chassis
      ctx.fillStyle = "#78350f";
      ctx.fillRect(-14, -6, 28, 12);

      // Spiked wheels with spokes
      ctx.strokeStyle = "#451a03";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.arc(-8, 8, 6.5, 0, Math.PI * 2);
      ctx.arc(8, 8, 6.5, 0, Math.PI * 2);
      ctx.stroke();

      // Throwing arm with counterweight
      ctx.strokeStyle = "#92400e";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(8, -4); ctx.lineTo(-14, -18);
      ctx.stroke();

      // Flaming rock in bucket
      ctx.fillStyle = "#ea580c";
      ctx.shadowColor = "#f97316"; ctx.shadowBlur = 8;
      ctx.beginPath();
      ctx.arc(-15, -19, 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

        } else if (type.includes("warlock")) {
      // --- WARLOCK: Horned purple cowl, flaming obsidian staff, burning magma eye ---
      ctx.fillStyle = "#3b0764";
      ctx.beginPath();
      ctx.arc(0, -2, c.radius, 0, Math.PI * 2);
      ctx.fill();
      // Horns
      ctx.fillStyle = "#18181b";
      ctx.beginPath();
      ctx.moveTo(-c.radius * 0.6, -c.radius * 0.7);
      ctx.lineTo(-c.radius * 1.1, -c.radius * 1.4);
      ctx.lineTo(-c.radius * 0.3, -c.radius);
      ctx.moveTo(c.radius * 0.6, -c.radius * 0.7);
      ctx.lineTo(c.radius * 1.1, -c.radius * 1.4);
      ctx.lineTo(c.radius * 0.3, -c.radius);
      ctx.fill();
      // Flaming Eye
      ctx.fillStyle = "#ea580c";
      ctx.beginPath();
      ctx.arc(-3, -2, 3, 0, Math.PI * 2);
      ctx.arc(3, -2, 3, 0, Math.PI * 2);
      ctx.fill();
    } else if (type.includes("irongolem")) {
      // --- IRONCLAD GOLEM: Heavy gunmetal cubic plating with glowing magma core ---
      ctx.fillStyle = "#1e293b";
      ctx.fillRect(-c.radius * 0.9, -c.radius * 0.9, c.radius * 1.8, c.radius * 1.8);
      ctx.fillStyle = "#f97316";
      ctx.beginPath();
      ctx.arc(0, 0, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#475569";
      ctx.lineWidth = 2.5;
      ctx.strokeRect(-c.radius * 0.9, -c.radius * 0.9, c.radius * 1.8, c.radius * 1.8);
    } else if (type.includes("hound")) {
      // --- INFERNAL HOUND: Low feral quadruped, flame teeth ---
      ctx.fillStyle = "#450a0a";
      ctx.beginPath();
      ctx.ellipse(0, 0, c.radius * 1.2, c.radius * 0.7, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#dc2626";
      ctx.beginPath();
      ctx.arc(-c.radius * 0.8, -2, 3, 0, Math.PI * 2);
      ctx.fill();
    } else if (type.includes("necromancer")) {
      // --- NECROMANCER: Emerald bone skull mask ---
      ctx.fillStyle = "#022c22";
      ctx.beginPath();
      ctx.arc(0, -2, c.radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#10b981";
      ctx.beginPath();
      ctx.arc(-3, -3, 2.5, 0, Math.PI * 2);
      ctx.arc(3, -3, 2.5, 0, Math.PI * 2);
      ctx.fill();
    } else if (type.includes("assassin")) {
      // --- SHADOW BLADE ASSASSIN: Dark ninja with glowing violet daggers ---
      ctx.fillStyle = "#0f172a";
      ctx.beginPath();
      ctx.arc(0, -3, c.radius * 0.85, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#c084fc";
      ctx.fillRect(-c.radius - 4, -1, 6, 2);
      ctx.fillRect(c.radius - 2, -1, 6, 2);
    } else if (type.includes("centaur_conqueror")) {
      // --- CENTAUR CONQUEROR: Golden plate, battleaxe ---
      ctx.fillStyle = "#78350f";
      ctx.beginPath();
      ctx.ellipse(0, 2, c.radius * 1.2, c.radius * 0.8, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#facc15";
      ctx.fillRect(-c.radius * 0.5, -c.radius - 2, c.radius, 8);
    } else if (type.includes("drake")) {
      // --- INFERNAL DRAKE: Wings and fiery snout ---
      ctx.fillStyle = "#9a3412";
      ctx.beginPath();
      ctx.arc(0, -4, c.radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#ea580c";
      ctx.beginPath();
      ctx.moveTo(-c.radius * 1.2, -6);
      ctx.lineTo(-c.radius * 0.3, -c.radius);
      ctx.lineTo(-c.radius * 0.3, 0);
      ctx.moveTo(c.radius * 1.2, -6);
      ctx.lineTo(c.radius * 0.3, -c.radius);
      ctx.lineTo(c.radius * 0.3, 0);
      ctx.fill();
    } else if (type.includes("void_terror")) {
      // --- VOID TERROR: Cosmic dark eye with violet rings ---
      ctx.fillStyle = "#1e1b4b";
      ctx.beginPath();
      ctx.arc(0, 0, c.radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#818cf8";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.ellipse(0, 0, c.radius + 5, c.radius * 0.4, time * 0.05, 0, Math.PI * 2);
      ctx.stroke();
    } else if (type.includes("ancient_titan")) {
      // --- ANCIENT EARTH TITAN: Giant granite colossus with cyan runes ---
      ctx.fillStyle = "#334155";
      ctx.beginPath();
      ctx.arc(0, 0, c.radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#38bdf8";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.moveTo(-c.radius * 0.5, 0);
      ctx.lineTo(0, -c.radius * 0.6);
      ctx.lineTo(c.radius * 0.5, 0);
      ctx.stroke();
    } else if (type.includes("apocalypse_doomguard")) {
      // --- APOCALYPSE DOOMGUARD: Towering winged demon lord ---
      ctx.fillStyle = "#7f1d1d";
      ctx.beginPath();
      ctx.arc(0, -4, c.radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#dc2626";
      ctx.beginPath();
      ctx.moveTo(-c.radius * 1.4, -c.radius);
      ctx.lineTo(-c.radius * 0.4, 0);
      ctx.lineTo(-c.radius * 0.4, -c.radius * 0.5);
      ctx.moveTo(c.radius * 1.4, -c.radius);
      ctx.lineTo(c.radius * 0.4, 0);
      ctx.lineTo(c.radius * 0.4, -c.radius * 0.5);
      ctx.fill();
    } else if (type.includes("astral_phantom")) {
      // --- ASTRAL PHANTOM: Cyan translucent luminous ghost ---
      ctx.fillStyle = "rgba(56, 189, 248, 0.75)";
      ctx.beginPath();
      ctx.arc(0, -2, c.radius, 0, Math.PI * 2);
      ctx.fill();
    } else if (type.includes("captain") || c.isCaptain) {
      // --- ELITE CAPTAIN ---
      // Golden armor
      ctx.fillStyle = "#b45309";
      ctx.strokeStyle = "#facc15";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.rect(-9, -10, 18, 20);
      ctx.fill(); ctx.stroke();

      // Winged Helmet
      ctx.fillStyle = "#1e293b";
      ctx.beginPath();
      ctx.arc(0, -14, 8, 0, Math.PI * 2);
      ctx.fill();
      // Wings on helm
      ctx.fillStyle = "#facc15";
      ctx.beginPath();
      ctx.moveTo(-6, -16); ctx.lineTo(-15, -24); ctx.lineTo(-6, -20);
      ctx.moveTo(6, -16); ctx.lineTo(15, -24); ctx.lineTo(6, -20);
      ctx.fill();

      // Royal standard / war banner on back
      ctx.strokeStyle = "#78350f"; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(6, 10); ctx.lineTo(6, -30); ctx.stroke();
      ctx.fillStyle = "#dc2626";
      ctx.beginPath();
      ctx.moveTo(6, -30); ctx.lineTo(24, -24); ctx.lineTo(6, -18);
      ctx.closePath();
      ctx.fill();

      // Dual swords
      ctx.strokeStyle = "#f8fafc";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(-4, 0); ctx.lineTo(-18, -8);
      ctx.moveTo(2, 4); ctx.lineTo(-14, 14);
      ctx.stroke();

    } else {
      // --- MELEE GRUNTS (Radiant / Dire) ---
      const isDire = type.includes("dire") || type.includes("тьма");
      if (isDire) {
        // Dire Ghoul / Fiend
        ctx.fillStyle = "#450a0a";
        ctx.beginPath();
        ctx.ellipse(0, 0, 11, 14, -0.2, 0, Math.PI * 2);
        ctx.fill();
        // Spiked black iron shoulder
        ctx.fillStyle = "#18181b";
        ctx.beginPath();
        ctx.moveTo(2, -12); ctx.lineTo(10, -20); ctx.lineTo(6, -8);
        ctx.closePath();
        ctx.fill();
        // Burning red eye
        ctx.fillStyle = "#ef4444";
        ctx.shadowColor = "#ef4444"; ctx.shadowBlur = 6;
        ctx.fillRect(-7, -8, 3, 2);
        ctx.shadowBlur = 0;
        // Dual jagged rusted axes
        ctx.strokeStyle = "#94a3b8"; ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(-2, 0); ctx.lineTo(-15, -6);
        ctx.stroke();
      } else {
        // Radiant Swordsman
        ctx.fillStyle = "#166534";
        ctx.beginPath();
        ctx.ellipse(0, 0, 11, 13, 0.1, 0, Math.PI * 2);
        ctx.fill();
        // Round oak shield
        ctx.fillStyle = "#78350f"; ctx.strokeStyle = "#d97706"; ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(-7, 2, 7.5, 0, Math.PI * 2);
        ctx.fill(); ctx.stroke();
        // Short iron sword
        ctx.strokeStyle = "#cbd5e1"; ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(2, 0); ctx.lineTo(12, -12);
        ctx.stroke();
      }
    }

    // Telegraph indicator (danger icon / raised weapon flash)
    if (c.state === "telegraph") {
      ctx.strokeStyle = "#ef4444";
      ctx.lineWidth = 2;
      ctx.shadowColor = "#ef4444";
      ctx.shadowBlur = 9;
      ctx.beginPath();
      ctx.arc(0, 0, c.radius + 5, 0, Math.PI * 2);
      ctx.stroke();
      ctx.shadowBlur = 0;
    }

    ctx.restore();
  }

  // ===========================================================================
  // PROCEDURAL ALLIED MINION (WK Skeleton)
  // ===========================================================================

  function drawProceduralMinion(ctx, m, time = (ARENA.frameCount || 0)) {
    time = (time != null ? time : (ARENA.frameCount || 0));
    const bob = Math.sin(time * 0.2 + m.x * 0.1) * 1.5;
    ctx.save();
    ctx.translate(m.x, m.y + bob);

    // Shadow
    ctx.fillStyle = "rgba(0,0,0,0.28)";
    ctx.beginPath();
    ctx.ellipse(0, m.radius + 2, m.radius * 0.8, 3.5, 0, 0, Math.PI * 2);
    ctx.fill();

    // Ivory ribcage
    ctx.strokeStyle = "#e2e8f0";
    ctx.lineWidth = 1.8;
    ctx.beginPath();
    ctx.moveTo(0, -6); ctx.lineTo(0, 6);
    ctx.moveTo(-5, -3); ctx.lineTo(5, -3);
    ctx.moveTo(-4, 0); ctx.lineTo(4, 0);
    ctx.moveTo(-3, 3); ctx.lineTo(3, 3);
    ctx.stroke();

    // Skull
    ctx.fillStyle = "#f8fafc";
    ctx.beginPath();
    ctx.arc(0, -10, 5.5, 0, Math.PI * 2);
    ctx.fill();

    // Glowing turquoise eyes
    ctx.fillStyle = "#2dd4bf";
    ctx.shadowColor = "#2dd4bf";
    ctx.shadowBlur = 6;
    ctx.fillRect(-2, -11, 1.6, 1.6);
    ctx.fillRect(1, -11, 1.6, 1.6);
    ctx.shadowBlur = 0;

    // Rusted blade
    ctx.strokeStyle = "#94a3b8";
    ctx.lineWidth = 1.8;
    ctx.beginPath();
    ctx.moveTo(4, 0); ctx.lineTo(14, -6);
    ctx.stroke();

    ctx.restore();
  }

  // ===========================================================================
  // PROCEDURAL PICKUPS: COINS, GEMS, CHESTS
  // ===========================================================================

  function drawProceduralCoin(ctx, x, y, radius, time = (ARENA.frameCount || 0)) {
    time = (time != null ? time : (ARENA.frameCount || 0));
    ctx.save();
    ctx.translate(x, y);

    // Beveled 3D Gold Rim
    ctx.fillStyle = "#b45309";
    ctx.beginPath();
    ctx.arc(0, 0, radius, 0, Math.PI * 2);
    ctx.fill();

    // Inner Radiant Gold Face
    ctx.fillStyle = "#facc15";
    ctx.beginPath();
    ctx.arc(0, 0, radius * 0.82, 0, Math.PI * 2);
    ctx.fill();

    // Embossed center star / crest
    ctx.fillStyle = "#eab308";
    ctx.beginPath();
    ctx.moveTo(0, -radius * 0.5);
    ctx.lineTo(radius * 0.35, 0);
    ctx.lineTo(0, radius * 0.5);
    ctx.lineTo(-radius * 0.35, 0);
    ctx.closePath();
    ctx.fill();

    // Rotating specular sparkle glint
    const glintAng = time * 0.08;
    const gx = Math.cos(glintAng) * (radius * 0.45);
    const gy = Math.sin(glintAng) * (radius * 0.45);
    ctx.fillStyle = "#ffffff";
    ctx.beginPath();
    ctx.arc(gx, gy, radius * 0.22, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
  }

  function drawProceduralGem(ctx, x, y, radius, colorHex, time = (ARENA.frameCount || 0)) {
    time = (time != null ? time : (ARENA.frameCount || 0));
    ctx.save();
    ctx.translate(x, y);
    const col = colorHex || "#38bdf8";

    // Glowing faceted diamond polygon
    ctx.fillStyle = col;
    ctx.shadowColor = col;
    ctx.shadowBlur = 8;
    ctx.beginPath();
    ctx.moveTo(0, -radius);
    ctx.lineTo(radius * 0.85, -radius * 0.35);
    ctx.lineTo(0, radius);
    ctx.lineTo(-radius * 0.85, -radius * 0.35);
    ctx.closePath();
    ctx.fill();
    ctx.shadowBlur = 0;

    // Specular facet
    ctx.fillStyle = "rgba(255, 255, 255, 0.65)";
    ctx.beginPath();
    ctx.moveTo(0, -radius);
    ctx.lineTo(radius * 0.4, -radius * 0.35);
    ctx.lineTo(0, 0);
    ctx.closePath();
    ctx.fill();

    ctx.restore();
  }

  function drawProceduralChest(ctx, x, y, time = (ARENA.frameCount || 0), isLanded, isOpened) {
    time = (time != null ? time : (ARENA.frameCount || 0));
    ctx.save();
    ctx.translate(x, y);

    // God Ray Light Pillar when landed
    if (isLanded) {
      const rayAlpha = 0.22 + Math.sin(time * 0.06) * 0.08;
      const grad = ctx.createLinearGradient(0, 0, 0, -220);
      grad.addColorStop(0, `rgba(250, 204, 21, ${rayAlpha * 1.5})`);
      grad.addColorStop(1, "rgba(250, 204, 21, 0)");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.moveTo(-24, 0); ctx.lineTo(24, 0); ctx.lineTo(38, -220); ctx.lineTo(-38, -220);
      ctx.closePath();
      ctx.fill();
    }

    // Shadow
    ctx.fillStyle = "rgba(0,0,0,0.4)";
    ctx.beginPath();
    ctx.ellipse(0, 12, 22, 6, 0, 0, Math.PI * 2);
    ctx.fill();

    // Wooden Chest Base
    ctx.fillStyle = "#78350f";
    ctx.strokeStyle = "#b45309";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.roundRect(-16, -6, 32, 20, 3);
    ctx.fill();
    ctx.stroke();

    // Iron Banding & Corner Brackets
    ctx.fillStyle = "#eab308";
    ctx.fillRect(-16, -6, 4, 20);
    ctx.fillRect(12, -6, 4, 20);
    ctx.fillRect(-2, -6, 4, 20);

    // Lid (Closed or Tilted Open)
    if (isOpened) {
      ctx.save();
      ctx.translate(-16, -6);
      ctx.rotate(-0.8);
      ctx.fillStyle = "#92400e";
      ctx.strokeStyle = "#facc15";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.roundRect(0, -10, 34, 10, 3);
      ctx.fill(); ctx.stroke();
      ctx.restore();

      // Golden Treasure Rays pouring from open chest
      ctx.fillStyle = "rgba(250, 204, 21, 0.45)";
      ctx.shadowColor = "#facc15"; ctx.shadowBlur = 12;
      ctx.beginPath();
      ctx.arc(0, -4, 8, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
    } else {
      ctx.fillStyle = "#92400e";
      ctx.strokeStyle = "#eab308";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.roundRect(-17, -15, 34, 11, [4, 4, 0, 0]);
      ctx.fill(); ctx.stroke();

      // Brass Keyhole Lock
      ctx.fillStyle = "#facc15";
      ctx.beginPath();
      ctx.arc(0, -4, 3.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#1e293b";
      ctx.fillRect(-1, -4, 2, 4);
    }

    ctx.restore();
  }

  // ===========================================================================
  // PROCEDURAL ENVIRONMENT: TREES & CLOUDS
  // ===========================================================================

  function drawProceduralTree(ctx, x, y, time = (ARENA.frameCount || 0)) {
    time = (time != null ? time : (ARENA.frameCount || 0));
    ctx.save();
    ctx.translate(x, y);

    // Gnarled Trunk
    ctx.fillStyle = "#5c3a21";
    ctx.beginPath();
    ctx.moveTo(-5, 0); ctx.lineTo(-3, -22); ctx.lineTo(3, -22); ctx.lineTo(6, 0);
    ctx.closePath();
    ctx.fill();

    // Ambient Leaf Sway
    const sway = Math.sin(time * 0.04 + x * 0.1) * 2;

    // Multi-tiered Lush Foliage Canopies
    ctx.fillStyle = "#166534";
    ctx.beginPath();
    ctx.arc(sway, -34, 16, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = "#15803d";
    ctx.beginPath();
    ctx.arc(-8 + sway * 0.8, -26, 12, 0, Math.PI * 2);
    ctx.arc(8 + sway * 0.8, -26, 12, 0, Math.PI * 2);
    ctx.fill();

    // Sunlit Top Leaf Highlights
    ctx.fillStyle = "#22c55e";
    ctx.beginPath();
    ctx.arc(sway, -40, 8, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
  }

  function drawProceduralCloud(ctx, cloud) {
    ctx.save();
    ctx.fillStyle = "rgba(255, 255, 255, 0.42)";
    ctx.beginPath();
    ctx.arc(cloud.x, cloud.y, 14, 0, Math.PI * 2);
    ctx.arc(cloud.x + 12, cloud.y - 5, 17, 0, Math.PI * 2);
    ctx.arc(cloud.x + 26, cloud.y, 13, 0, Math.PI * 2);
    ctx.arc(cloud.x + 14, cloud.y + 4, 12, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  // ===========================================================================
  // DEVIL MAY CRY STYLE METER HUD (D, C, B, A, S, SS, SSS)
  // ===========================================================================

  function drawStyleMeterHUD(ctx, styleMeter, combo, customW) {
    if (!styleMeter) return;
    const rank = styleMeter.rank || "D";
    const w = customW || ARENA.width || 360;
    const x = Math.round(w / 2);
    const y = 30;

    const rankColors = {
      D: { text: "#94a3b8", glow: "#64748b" },
      C: { text: "#06b6d4", glow: "#0891b2" },
      B: { text: "#10b981", glow: "#059669" },
      A: { text: "#f59e0b", glow: "#d97706" },
      S: { text: "#f97316", glow: "#ea580c" },
      SS: { text: "#ef4444", glow: "#dc2626" },
      SSS: { text: "#f43f5e", glow: "#e11d48" }
    };
    const cfg = rankColors[rank] || rankColors.D;

    ctx.save();
    // Glass HUD Backplate
    ctx.fillStyle = "rgba(15, 23, 42, 0.78)";
    ctx.strokeStyle = cfg.text;
    ctx.lineWidth = 1.5;
    ctx.shadowColor = cfg.glow;
    ctx.shadowBlur = 8;
    ctx.beginPath();
    safeRoundRect(ctx, x - 38, y - 17, 76, 34, 8);
    ctx.fill();
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Glowing Rank Letter
    ctx.font = "900 22px 'Impact', sans-serif";
    ctx.fillStyle = cfg.text;
    ctx.shadowColor = cfg.glow;
    ctx.shadowBlur = 10;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(rank, x - 16, y);
    ctx.shadowBlur = 0;

    // Style Meter Progress Bar
    const prog = Math.max(0, Math.min(1, styleMeter.progress || 0));
    ctx.fillStyle = "rgba(0,0,0,0.6)";
    ctx.fillRect(x - 4, y - 5, 36, 4);
    ctx.fillStyle = cfg.text;
    ctx.fillRect(x - 4, y - 5, 36 * prog, 4);

    // Combo Counter (if active)
    if (combo && combo.count > 1) {
      ctx.font = "italic 800 8.5px sans-serif";
      ctx.fillStyle = "#facc15";
      ctx.fillText(`${combo.count} COMBO!`, x + 14, y + 6);
    } else {
      ctx.font = "bold 7px sans-serif";
      ctx.fillStyle = "#94a3b8";
      ctx.fillText("STYLE", x + 14, y + 6);
    }

    ctx.restore();
  }

  // ===========================================================================
  // PROCEDURAL PROJECTILES (NO EMOJIS)
  // ===========================================================================

  function drawProceduralProjectile(ctx, proj, time = (ARENA.frameCount || 0)) {
    time = (time != null ? time : (ARENA.frameCount || 0));
    ctx.save();
    ctx.translate(proj.x, proj.y);

    if (proj.type === "meteor") {
      // --- INVOKER CHAOS METEOR (Пылающая «Котлета») ---
      const r = proj.radius || 34;

      // 1. Draw Burn Trail behind in local coords
      if (proj.burnTrail) {
        for (const tr of proj.burnTrail) {
          const relX = tr.x - proj.x;
          const relY = tr.y - proj.y;
          const trAlpha = Math.min(1.0, tr.timer / 80);
          ctx.fillStyle = `rgba(234, 88, 12, ${0.45 * trAlpha})`;
          ctx.beginPath();
          ctx.ellipse(relX, relY, 20, 6, 0, 0, Math.PI * 2);
          ctx.fill();
          // Inner ember
          ctx.fillStyle = `rgba(254, 240, 138, ${0.7 * trAlpha})`;
          ctx.beginPath();
          ctx.arc(relX + (Math.sin(tr.timer * 0.3) * 6), relY - 2, 2.5, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      ctx.rotate(proj.angle || (time * 0.12));

      // 2. Fiery Magma Aura / Outer Blaze
      ctx.fillStyle = "rgba(234, 88, 12, 0.45)";
      ctx.shadowColor = "#f97316";
      ctx.shadowBlur = 24;
      ctx.beginPath();
      ctx.arc(0, 0, r + 7, 0, Math.PI * 2);
      ctx.fill();

      // 3. Molten Volcanic Rock Body (Charred dark obsidian stone)
      ctx.fillStyle = "#1c1917";
      ctx.beginPath();
      ctx.arc(0, 0, r, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

      // 4. Glowing Magma Veins & Lava Cracks
      ctx.strokeStyle = "#f97316";
      ctx.lineWidth = 3.5;
      ctx.beginPath();
      ctx.moveTo(-r * 0.7, -r * 0.3);
      ctx.lineTo(-r * 0.2, 0);
      ctx.lineTo(r * 0.3, -r * 0.4);
      ctx.lineTo(r * 0.8, -r * 0.1);
      ctx.moveTo(-r * 0.3, r * 0.5);
      ctx.lineTo(0, r * 0.2);
      ctx.lineTo(r * 0.4, r * 0.6);
      ctx.stroke();

      // White-hot inner crack lines
      ctx.strokeStyle = "#fef08a";
      ctx.lineWidth = 1.6;
      ctx.beginPath();
      ctx.moveTo(-r * 0.2, 0);
      ctx.lineTo(r * 0.3, -r * 0.4);
      ctx.stroke();

      // Molten craters
      ctx.fillStyle = "#ea580c";
      ctx.beginPath();
      ctx.arc(-r * 0.35, -r * 0.2, 5, 0, Math.PI * 2);
      ctx.arc(r * 0.2, r * 0.3, 5.5, 0, Math.PI * 2);
      ctx.arc(-r * 0.1, r * 0.45, 4, 0, Math.PI * 2);
      ctx.fill();

      // White-hot crater centers
      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.arc(-r * 0.35, -r * 0.2, 2, 0, Math.PI * 2);
      ctx.arc(r * 0.2, r * 0.3, 2.2, 0, Math.PI * 2);
      ctx.fill();

    } else if (proj.type === "wind_blade") {
      // Crescent Wind Blade / Cleave Wave
      const col = proj.color || "#facc15";
      const rad = proj.radius || 20;
      ctx.shadowColor = col;
      ctx.shadowBlur = proj.isHeavy ? 16 : 10;
      ctx.strokeStyle = col;
      ctx.lineWidth = proj.isHeavy ? 5 : 3.5;
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.arc(0, 0, rad, -Math.PI * 0.45, Math.PI * 0.45);
      ctx.stroke();

      // Bright inner core
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 1.8;
      ctx.beginPath();
      ctx.arc(0, 0, rad - 2, -Math.PI * 0.35, Math.PI * 0.35);
      ctx.stroke();

      // Trailing wind sparks
      ctx.fillStyle = col;
      ctx.beginPath();
      ctx.arc(-rad * 0.4, -rad * 0.3, 2, 0, Math.PI * 2);
      ctx.arc(-rad * 0.4, rad * 0.3, 2, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

    } else if (proj.type === "dagger" || proj.type === "companion_dagger") {
      // Throwing Dagger (PA / Squad Companion)
      ctx.rotate(Math.atan2(proj.vy || 0, proj.vx || 1) || 0);
      const isCrit = !!proj.isCrit;
      // Trail
      ctx.strokeStyle = isCrit ? "rgba(239, 68, 68, 0.65)" : "rgba(34, 211, 238, 0.5)";
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.moveTo(-16, 0); ctx.lineTo(0, 0);
      ctx.stroke();

      // Steel blade
      ctx.fillStyle = "#e2e8f0";
      ctx.strokeStyle = "#22d3ee";
      ctx.lineWidth = 1.5;
      ctx.shadowColor = "#22d3ee";
      ctx.shadowBlur = 8;
      ctx.beginPath();
      ctx.moveTo(8, 0); ctx.lineTo(-4, -4); ctx.lineTo(-4, 4);
      ctx.closePath();
      ctx.fill(); ctx.stroke();
      ctx.shadowBlur = 0;

    } else if (proj.isBossFireball || proj.type === "fireball") {
      // Blazing Boss Fireball
      ctx.fillStyle = "#f97316";
      ctx.shadowColor = "#ea580c";
      ctx.shadowBlur = 14;
      ctx.beginPath();
      ctx.arc(0, 0, 8, 0, Math.PI * 2);
      ctx.fill();
      // White hot core
      ctx.fillStyle = "#fef08a";
      ctx.beginPath();
      ctx.arc(0, 0, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

      // Trailing flame wisps
      ctx.fillStyle = "rgba(234, 88, 12, 0.6)";
      for (let f = 0; f < 3; f++) {
        const fx = 8 + (time * 0.5 + f * 4) % 12;
        const fy = Math.sin(time * 0.3 + f) * 3;
        ctx.beginPath();
        ctx.arc(fx, fy, 3.5 - f * 0.8, 0, Math.PI * 2);
        ctx.fill();
      }

    } else if (proj.type === "topdown_shot") {
      const ang = Math.atan2(proj.vy || 0, proj.vx || 1);
      ctx.rotate(ang);
      const col = proj.color || (proj.isCrit ? "#f59e0b" : "#38bdf8");
      ctx.fillStyle = col;
      ctx.shadowColor = col;
      ctx.shadowBlur = proj.isCrit ? 16 : 10;
      ctx.beginPath();
      ctx.ellipse(0, 0, (proj.radius || 6) * 1.5, (proj.radius || 6) * 0.85, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.ellipse(2, 0, (proj.radius || 6) * 0.75, (proj.radius || 6) * 0.45, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
      ctx.fillStyle = col;
      ctx.beginPath();
      ctx.arc(-8, 0, 3, 0, Math.PI * 2);
      ctx.arc(-14, 0, 1.8, 0, Math.PI * 2);
      ctx.fill();
    } else if (proj.reflected) {
      // REFLECTED RADIANT GOLDEN BOLT
      ctx.fillStyle = "#facc15";
      ctx.shadowColor = "#facc15";
      ctx.shadowBlur = 16;
      ctx.beginPath();
      ctx.arc(0, 0, 7.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.arc(0, 0, 3.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

      // Speed streak
      ctx.strokeStyle = "rgba(250, 204, 21, 0.75)";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(-16, 0); ctx.lineTo(0, 0);
      ctx.stroke();

    } else {
      // General Magic Bolt (Player or Enemy Caster)
      const col = proj.color || "#38bdf8";
      ctx.fillStyle = col;
      ctx.shadowColor = col;
      ctx.shadowBlur = 10;
      ctx.beginPath();
      ctx.arc(0, 0, 5.5, 0, Math.PI * 2);
      ctx.fill();
      // Bright center
      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.arc(0, 0, 2.2, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

      // Sparkle tail
      const dir = (proj.speed && proj.speed < 0) ? -1 : 1;
      ctx.fillStyle = col;
      ctx.beginPath();
      ctx.arc(-dir * 7, 0, 3, 0, Math.PI * 2);
      ctx.arc(-dir * 12, 0, 1.8, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.restore();
  }


    function renderGrandBossHUD(ctx, w, h, boss, time) {
    if (!boss) return;

    const bannerX = 8;
    const bannerY = 56; // Опустили вниз, чтобы не перекрывалось кнопками (было 7)
    const bannerW = w - 16;
    const bannerH = 48;

    // Background Ornate Slate Box
    ctx.save();
    ctx.fillStyle = "rgba(15, 23, 42, 0.94)";
    ctx.beginPath();
    safeRoundRect(ctx, bannerX, bannerY, bannerW, bannerH, 12);
    ctx.fill();

      const isGod = boss.isGodMode || boss.enrageStage === "god_mode";
    ctx.strokeStyle = isGod ? "#ef4444" : (boss.enraged ? "#f97316" : (boss.isStaggered ? "#ec4899" : "#f59e0b"));
    ctx.lineWidth = isGod ? 2.5 : 1.8;
    ctx.beginPath();
    safeRoundRect(ctx, bannerX, bannerY, bannerW, bannerH, 12);
    ctx.stroke();

    // 1. Top Row: Title & Party Mode Toggle
    ctx.font = "bold 10px sans-serif";
    ctx.fillStyle = isGod ? "#ef4444" : (boss.enraged ? "#f87171" : "#facc15");
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    let enrageLabel = "";
    const elapsedSec = Math.floor((Date.now() - (boss.battleStartTime || Date.now())) / 1000);
    const remSec = Math.max(0, 300 - elapsedSec);
    const remM = Math.floor(remSec / 60);
    const remS = remSec % 60;
    const timerStr = `${remM}:${remS < 10 ? "0" : ""}${remS}`;

    if (isGod) {
      enrageLabel = "💀 РЕЖИМ БОГА!";
    } else if (boss.enrageStage === "enraged" || boss.enraged) {
      enrageLabel = `🔥 БЕЗУМИЕ (${timerStr})`;
    } else if (boss.enrageStage === "furious") {
      enrageLabel = `⚡ ЯРОСТЬ (${timerStr})`;
    } else if (boss.enrageStage === "angry") {
      enrageLabel = `😡 ЗЛОЙ (${timerStr})`;
    } else {
      enrageLabel = `⏱️ ${timerStr}`;
    }
    const bossTitle = `👑 ${boss.name || "БОСС"} • ${enrageLabel}`;
    ctx.fillText(bossTitle.length > 28 ? bossTitle.slice(0, 27) + "…" : bossTitle, bannerX + 10, bannerY + 11);

    // Party Button on Canvas HUD
    const btnW = 86;
    const btnH = 18;
    const btnX = bannerX + bannerW - btnW - 6;
    const btnY = bannerY + 3;
    const isTrio = (ARENA.bossPartyMode || "trio") === "trio";

    ctx.fillStyle = isTrio ? "rgba(16, 185, 129, 0.25)" : "rgba(168, 85, 247, 0.25)";
    ctx.beginPath();
    safeRoundRect(ctx, btnX, btnY, btnW, btnH, 6);
    ctx.fill();

    ctx.strokeStyle = isTrio ? "#10b981" : "#a855f7";
    ctx.lineWidth = 1;
    ctx.beginPath();
    safeRoundRect(ctx, btnX, btnY, btnW, btnH, 6);
    ctx.stroke();

    ctx.font = "bold 9px sans-serif";
    ctx.fillStyle = isTrio ? "#6ee7b7" : "#d8b4fe";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(isTrio ? "👥 Отряд: 3" : "👤 Бой: Соло", btnX + btnW / 2, btnY + btnH / 2);
    ARENA._partyBtnBounds = { x: btnX, y: btnY, w: btnW, h: btnH };

    // 2. Main Boss HP Bar
    const hpBarX = bannerX + 10;
    const hpBarY = bannerY + 22;
    const hpBarW = bannerW - 20;
    const hpBarH = 12;
    const hpPct = Math.max(0, Math.min(1, boss.hp / boss.maxHp));

    ctx.fillStyle = "rgba(0, 0, 0, 0.75)";
    ctx.beginPath();
    safeRoundRect(ctx, hpBarX, hpBarY, hpBarW, hpBarH, 4);
    ctx.fill();

    // HP Fill Gradient
    const hpGrad = ctx.createLinearGradient(hpBarX, 0, hpBarX + hpBarW, 0);
    if (isGod) {
      hpGrad.addColorStop(0, "#7f1d1d");
      hpGrad.addColorStop(0.5, "#ef4444");
      hpGrad.addColorStop(1, "#b91c1c");
    } else if (boss.enraged) {
      hpGrad.addColorStop(0, "#ea580c");
      hpGrad.addColorStop(1, "#dc2626");
    } else {
      hpGrad.addColorStop(0, "#dc2626");
      hpGrad.addColorStop(1, "#b91c1c");
    }
    ctx.fillStyle = hpGrad;
    ctx.beginPath();
    safeRoundRect(ctx, hpBarX, hpBarY, hpBarW * hpPct, hpBarH, 4);
    ctx.fill();

    // HP Text
    ctx.font = "bold 8.5px sans-serif";
    ctx.fillStyle = "#ffffff";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.shadowColor = "#000000";
    ctx.shadowBlur = 4;
    ctx.fillText(`${formatCompact(boss.hp)} / ${formatCompact(boss.maxHp)} (${Math.ceil(hpPct * 100)}%)`, hpBarX + hpBarW / 2, hpBarY + hpBarH / 2);
    ctx.shadowBlur = 0;

    // 3. Poise / Stagger Bar & Badges
    const poiseBarX = hpBarX;
    const poiseBarY = hpBarY + hpBarH + 3;
    const poiseBarW = hpBarW - 100;
    const poiseBarH = 5;
    const poiseVal = boss.poise !== undefined ? boss.poise : 300;
    const poiseMax = boss.maxPoise || 300;
    const poisePct = Math.max(0, Math.min(1, poiseVal / poiseMax));

    ctx.fillStyle = "rgba(0, 0, 0, 0.65)";
    ctx.beginPath();
    safeRoundRect(ctx, poiseBarX, poiseBarY, poiseBarW, poiseBarH, 2.5);
    ctx.fill();

    ctx.fillStyle = boss.isStaggered ? "#ec4899" : "#f59e0b";
    ctx.beginPath();
    safeRoundRect(ctx, poiseBarX, poiseBarY, poiseBarW * (boss.isStaggered ? 1.0 : poisePct), poiseBarH, 2.5);
    ctx.fill();

    // Poise / Stagger Label
    ctx.font = "bold 7px sans-serif";
    ctx.fillStyle = boss.isStaggered ? "#f472b6" : "#fde68a";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillText(boss.isStaggered ? "💫 ОШЕЛОМЛЕН (+150%)!" : `⚡ БАЛАНС ${Math.ceil(poiseVal)}/${poiseMax}`, poiseBarX + 4, poiseBarY + poiseBarH / 2);

    // Badges on the right of poise bar
    let badgeX = poiseBarX + poiseBarW + 6;
    if (isGod) {
      ctx.fillStyle = "#ef4444";
      ctx.font = "bold 7.5px sans-serif";
      ctx.fillText("⚡ БОГ", badgeX, poiseBarY + poiseBarH / 2);
      badgeX += 34;
    } else if (boss.enraged) {
      ctx.fillStyle = "#ef4444";
      ctx.font = "bold 7.5px sans-serif";
      ctx.fillText("🔥 ЯРОСТЬ", badgeX, poiseBarY + poiseBarH / 2);
      badgeX += 46;
    }
    if (boss.tormentorShield) {
      ctx.fillStyle = "#c084fc";
      ctx.font = "bold 7.5px sans-serif";
      ctx.fillText("🔮 ЩИТ", badgeX, poiseBarY + poiseBarH / 2);
    }

    ctx.restore();
  }

