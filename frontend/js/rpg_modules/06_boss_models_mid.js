// ============================================================================
// 06_boss_models_mid.js — Procedural Vector Models for Bosses 7–13
// (Roshan, Tidehunter, SF, Necrophos, Terrorblade, Invoker, Chaos Knight)
// ============================================================================

function drawBossModelMid(ctx, b, bId, time) {
  const facing = b.facing || 1;
  let assetName = null;
  if (bId.includes("roshan") && !bId.includes("phantom")) assetName = "roshan";
  if (bId.includes("terrorblade") || bId.includes("террорблейд")) assetName = "terrorblade";

  if (assetName && typeof RPG_ASSETS !== "undefined" && RPG_ASSETS.bosses[assetName]) {
    const bossAsset = RPG_ASSETS.bosses[assetName];
    if (bossAsset && bossAsset.complete && bossAsset.naturalWidth > 0) {
      ctx.save();
      if (facing === -1) {
        ctx.scale(-1, 1);
      }
      const size = b.radius * 6.0;
      ctx.drawImage(bossAsset, -size / 2, -size / 1.1, size, size);
      ctx.restore();
      return true;
    }
  }

  // 7. ROSHAN (Рошан Свирепый)
  if (bId.includes("roshan") && !bId.includes("phantom")) {
    ctx.save();
    // Hulking Pit Beast Body
    ctx.fillStyle = "#451a03";
    ctx.strokeStyle = "#92400e";
    ctx.lineWidth = 3.5;
    ctx.beginPath();
    ctx.ellipse(0, 2, 28, 26, 0, 0, Math.PI * 2);
    ctx.fill(); ctx.stroke();

    // Spiky Rock Carapace on Back
    ctx.fillStyle = "#292524";
    ctx.beginPath();
    ctx.moveTo(-16, -12); ctx.lineTo(-24, -22); ctx.lineTo(-8, -18);
    ctx.lineTo(0, -26); ctx.lineTo(8, -18); ctx.lineTo(24, -22); ctx.lineTo(16, -12);
    ctx.closePath();
    ctx.fill();

    // Massive Curved Demon Horns
    ctx.strokeStyle = "#ea580c";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(-12 * facing, -18); ctx.quadraticCurveTo(-28 * facing, -38, -14 * facing, -42);
    ctx.moveTo(12 * facing, -18); ctx.quadraticCurveTo(28 * facing, -38, 14 * facing, -42);
    ctx.stroke();

    // Glowing Molten Eyes & Maw
    ctx.fillStyle = "#facc15";
    ctx.shadowColor = "#ea580c"; ctx.shadowBlur = 12;
    ctx.fillRect(-8 * facing, -18, 4 * facing, 3);
    ctx.fillRect(4 * facing, -18, 4 * facing, 3);
    ctx.fillStyle = "#ef4444";
    ctx.beginPath();
    ctx.moveTo(-6 * facing, -8); ctx.lineTo(6 * facing, -8); ctx.lineTo(0, 2);
    ctx.closePath();
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  // 8. TIDEHUNTER (Левиафан Бездны)
  if (bId.includes("tidehunter") || bId.includes("левиафан")) {
    ctx.save();
    // Colossal Amphibious Green Body
    ctx.fillStyle = "#064e3b";
    ctx.strokeStyle = "#10b981";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.ellipse(0, 2, 27, 25, 0, 0, Math.PI * 2);
    ctx.fill(); ctx.stroke();

    // Fish-Scale Ridges & Fins
    ctx.fillStyle = "#047857";
    ctx.beginPath();
    ctx.moveTo(-18 * facing, -14); ctx.lineTo(-26 * facing, -20); ctx.lineTo(-14 * facing, -6);
    ctx.moveTo(18 * facing, -14); ctx.lineTo(26 * facing, -20); ctx.lineTo(14 * facing, -6);
    ctx.fill();

    // Giant Rusted Heavy Anchor in Arm
    const aBob = Math.sin(time * 0.16) * 3;
    ctx.strokeStyle = "#78716c";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(22 * facing, -18 + aBob); ctx.lineTo(22 * facing, 16 + aBob);
    ctx.arc(22 * facing, 10 + aBob, 10, 0, Math.PI);
    ctx.stroke();

    // Fierce Yellow Sea-Beast Eyes
    ctx.fillStyle = "#fef08a";
    ctx.shadowColor = "#34d399"; ctx.shadowBlur = 8;
    ctx.fillRect(-8 * facing, -14, 4 * facing, 4);
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  // 9. SHADOW FIEND (Архидемон Nevermore)
  if (bId.includes("sf_boss") || bId.includes("nevermore")) {
    const sBob = Math.sin(time * 0.2) * 3;
    ctx.save();
    ctx.translate(0, sBob);

    // Swirling Shadow Pitch-Black Smoldering Body
    ctx.fillStyle = "#09090b";
    ctx.strokeStyle = "#dc2626";
    ctx.lineWidth = 2.5;
    ctx.shadowColor = "#b91c1c"; ctx.shadowBlur = 14;
    ctx.beginPath();
    ctx.moveTo(0, -26);
    ctx.quadraticCurveTo(20, -10, 14, 16);
    ctx.quadraticCurveTo(0, 26, -14, 16);
    ctx.quadraticCurveTo(-20, -10, 0, -26);
    ctx.closePath();
    ctx.fill(); ctx.stroke();

    // Glowing Crimson Ribcage
    ctx.strokeStyle = "#f87171";
    ctx.lineWidth = 2;
    for (let r = 0; r < 4; r++) {
      ctx.beginPath();
      ctx.moveTo(-10, -12 + r * 6); ctx.lineTo(10, -12 + r * 6);
      ctx.stroke();
    }

    // Fiery Horns & Demon Blade Hands
    ctx.strokeStyle = "#ef4444";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(-10 * facing, -24); ctx.lineTo(-18 * facing, -36);
    ctx.moveTo(10 * facing, -24); ctx.lineTo(18 * facing, -36);
    // Blade Arms
    ctx.moveTo(-18 * facing, 2); ctx.lineTo(-32 * facing, 14);
    ctx.moveTo(18 * facing, 2); ctx.lineTo(32 * facing, 14);
    ctx.stroke();
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  // 10. NECROPHOS (Чумной Владыка)
  if (bId.includes("necrophos") || bId.includes("чумной")) {
    const pBob = Math.sin(time * 0.12) * 3;
    ctx.save();
    ctx.translate(0, pBob);

    // Rotten Plague Robes
    ctx.fillStyle = "#14532d";
    ctx.strokeStyle = "#84cc16";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, -24); ctx.lineTo(16, 20); ctx.lineTo(-16, 20);
    ctx.closePath();
    ctx.fill(); ctx.stroke();

    // Pale Skull Head with Mitre Crown
    ctx.fillStyle = "#f1f5f9";
    ctx.beginPath();
    ctx.arc(0, -20, 8, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#166534";
    ctx.beginPath();
    ctx.moveTo(-6, -26); ctx.lineTo(0, -36); ctx.lineTo(6, -26);
    ctx.closePath();
    ctx.fill();

    // Venomous Curved Scythe
    ctx.strokeStyle = "#65a30d";
    ctx.lineWidth = 3.5;
    ctx.beginPath();
    ctx.moveTo(14 * facing, -32); ctx.lineTo(14 * facing, 22);
    ctx.quadraticCurveTo(28 * facing, -38, 36 * facing, -22);
    ctx.stroke();

    // Swirling Plague Particles
    for (let p = 0; p < 4; p++) {
      const pAng = time * 0.1 + p * 1.57;
      const px = Math.cos(pAng) * 22;
      const py = Math.sin(pAng) * 12;
      ctx.fillStyle = "#a3e635";
      ctx.fillRect(px, py, 2.5, 2.5);
    }
    ctx.restore();
    return true;
  }

  // 11. TERRORBLADE (Демон Бездны)
  if (bId.includes("terrorblade") || bId.includes("демон бездны")) {
    ctx.save();
    // Fractured Obsidian Torso
    ctx.fillStyle = "#18181b";
    ctx.strokeStyle = "#7c3aed";
    ctx.lineWidth = 2.5;
    ctx.shadowColor = "#8b5cf6"; ctx.shadowBlur = 12;
    ctx.beginPath();
    ctx.roundRect(-14, -20, 28, 38, 4);
    ctx.fill(); ctx.stroke();

    // Dual Arc Curved Crescent Blades
    ctx.strokeStyle = "#a78bfa";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(-22 * facing, -2, 14, -Math.PI / 2, Math.PI / 2);
    ctx.arc(22 * facing, -2, 14, Math.PI / 2, -Math.PI / 2);
    ctx.stroke();

    // Demon Wings
    ctx.fillStyle = "rgba(109, 40, 217, 0.75)";
    ctx.beginPath();
    ctx.moveTo(-12 * facing, -12); ctx.lineTo(-34 * facing, -30); ctx.lineTo(-24 * facing, 2);
    ctx.moveTo(12 * facing, -12); ctx.lineTo(34 * facing, -30); ctx.lineTo(24 * facing, 2);
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  // 12. INVOKER (Демиург Арсенала)
  if (bId.includes("invoker_boss") || bId.includes("инвокер") || bId.includes("арсенал")) {
    const iBob = Math.sin(time * 0.14) * 3;
    ctx.save();
    ctx.translate(0, iBob);

    // Regal Cape & Armor
    ctx.fillStyle = "#7c2d12";
    ctx.strokeStyle = "#facc15";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, -24); ctx.lineTo(16, 20); ctx.lineTo(-16, 20);
    ctx.closePath();
    ctx.fill(); ctx.stroke();

    // High Upturned Regal Mantle Collar
    ctx.fillStyle = "#facc15";
    ctx.beginPath();
    ctx.moveTo(-10, -22); ctx.lineTo(-18, -34); ctx.lineTo(-6, -26);
    ctx.moveTo(10, -22); ctx.lineTo(18, -34); ctx.lineTo(6, -26);
    ctx.fill();

    // Majestic Blond Hair & Glowing Eyes
    ctx.fillStyle = "#fef08a";
    ctx.beginPath();
    ctx.arc(0, -22, 8, 0, Math.PI * 2);
    ctx.fill();

    // 3 Orbiting Mystic Spheres: Quas (Blue), Wex (Purple), Exort (Orange)
    const orbs = [
      { c: "#38bdf8", angOff: 0 },
      { c: "#c084fc", angOff: 2.09 },
      { c: "#f97316", angOff: 4.18 }
    ];
    for (const o of orbs) {
      const oAng = time * 0.08 + o.angOff;
      const ox = Math.cos(oAng) * 26;
      const oy = Math.sin(oAng) * 14 - 14;
      ctx.fillStyle = o.c;
      ctx.shadowColor = o.c; ctx.shadowBlur = 10;
      ctx.beginPath();
      ctx.arc(ox, oy, 5, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  // 13. CHAOS KNIGHT (Всадник Хаоса)
  if (bId.includes("chaos_knight") || bId.includes("всадник хаоса")) {
    ctx.save();
    // Armored Warhorse Torso
    ctx.fillStyle = "#1e1b4b";
    ctx.strokeStyle = "#f59e0b";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.ellipse(0, 4, 24, 18, 0, 0, Math.PI * 2);
    ctx.fill(); ctx.stroke();

    // Flaming Mane & Hooves
    ctx.fillStyle = "#ef4444";
    ctx.beginPath();
    ctx.moveTo(12 * facing, -6); ctx.lineTo(24 * facing, -18); ctx.lineTo(18 * facing, -2);
    ctx.fill();

    // Armored Helm with Spiked Horns
    ctx.fillStyle = "#0f172a";
    ctx.beginPath();
    ctx.moveTo(-6 * facing, -18); ctx.lineTo(6 * facing, -18); ctx.lineTo(0, -32);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = "#f59e0b";
    ctx.lineWidth = 2;
    ctx.stroke();

    // Spiked Chaos Flail in Arm
    const fSpin = time * 0.16;
    const fx = -20 * facing + Math.cos(fSpin) * 12;
    const fy = -4 + Math.sin(fSpin) * 12;
    ctx.strokeStyle = "#d97706";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(-16 * facing, 2); ctx.lineTo(fx, fy);
    ctx.stroke();
    ctx.fillStyle = "#ef4444";
    ctx.beginPath();
    ctx.arc(fx, fy, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
    return true;
  }

  return false;
}
