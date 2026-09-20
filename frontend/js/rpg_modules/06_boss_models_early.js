// ============================================================================
// 06_boss_models_early.js — Procedural Vector Models for Bosses 1–6
// (Golem, Lich, Tormentor, Dragon, Pudge, Faceless Void)
// ============================================================================

function drawBossModelEarly(ctx, b, bId, time) {
  const facing = b.facing || 1;
  let assetName = null;
  if (bId.includes("faceless") || bId.includes("войд")) assetName = "faceless_void";

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

  // 1. GOLEM (Древний Гранитный Голем)
  if (bId.includes("golem") || bId.includes("голем")) {
    ctx.save();
    // Massive rocky torso
    ctx.fillStyle = "#44403c";
    ctx.strokeStyle = "#78716c";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.roundRect(-24, -28, 48, 44, 8);
    ctx.fill();
    ctx.stroke();

    // Magma / Moss Glowing Cracks
    ctx.strokeStyle = "#f97316";
    ctx.lineWidth = 2;
    ctx.shadowColor = "#ea580c";
    ctx.shadowBlur = 8;
    ctx.beginPath();
    ctx.moveTo(-16, -18); ctx.lineTo(-4, -6); ctx.lineTo(12, -14);
    ctx.moveTo(-8, 2); ctx.lineTo(6, 12);
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Heavy Stone Fists
    ctx.fillStyle = "#292524";
    ctx.strokeStyle = "#a8a29e";
    ctx.lineWidth = 2.5;
    const fOff = Math.sin(time * 0.15) * 4;
    ctx.beginPath();
    ctx.arc(-28 * facing, 2 + fOff, 13, 0, Math.PI * 2);
    ctx.arc(28 * facing, -2 - fOff, 13, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Glowing Amber Golem Eye Ridge
    ctx.fillStyle = "#fbbf24";
    ctx.shadowColor = "#f59e0b";
    ctx.shadowBlur = 10;
    ctx.fillRect(-10 * facing, -22, 14 * facing, 4);
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  // 2. LICH (Архилич Некрополя)
  if (bId.includes("lich") || bId.includes("лич")) {
    const floatBob = Math.sin(time * 0.12) * 4;
    ctx.save();
    ctx.translate(0, floatBob);

    // Dark Frost Robes
    ctx.fillStyle = "#0f172a";
    ctx.strokeStyle = "#0284c7";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.moveTo(0, -26);
    ctx.lineTo(18, 20); ctx.lineTo(10, 24); ctx.lineTo(0, 19); ctx.lineTo(-10, 24); ctx.lineTo(-18, 20);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // Skeletal Skull Face
    ctx.fillStyle = "#e2e8f0";
    ctx.beginPath();
    ctx.arc(0, -22, 10, 0, Math.PI * 2);
    ctx.fill();

    // Golden Lich Crown with Ice Jewels
    ctx.fillStyle = "#facc15";
    ctx.beginPath();
    ctx.moveTo(-9, -28); ctx.lineTo(-5, -36); ctx.lineTo(0, -29); ctx.lineTo(5, -36); ctx.lineTo(9, -28);
    ctx.closePath();
    ctx.fill();

    // Glowing Cyan Frost Eyes
    ctx.fillStyle = "#38bdf8";
    ctx.shadowColor = "#38bdf8";
    ctx.shadowBlur = 10;
    ctx.fillRect(-5, -23, 3, 2.5);
    ctx.fillRect(2, -23, 3, 2.5);

    // Orbiting Frost Phylactery Spheres
    for (let s = 0; s < 3; s++) {
      const oAng = time * 0.08 + s * 2.09;
      const ox = Math.cos(oAng) * 26;
      const oy = Math.sin(oAng) * 14 - 10;
      ctx.fillStyle = "#0284c7";
      ctx.shadowColor = "#38bdf8";
      ctx.shadowBlur = 12;
      ctx.beginPath();
      ctx.arc(ox, oy, 5, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  // 3. TORMENTOR (Древний Терзатель)
  if (bId.includes("tormentor") && !bId.includes("dark_tormentor")) {
    const rot = time * 0.035;
    ctx.save();
    ctx.rotate(rot);
    ctx.fillStyle = "#581c87";
    ctx.strokeStyle = "#e879f9";
    ctx.lineWidth = 3;
    ctx.shadowColor = "#c084fc";
    ctx.shadowBlur = 16;
    ctx.beginPath();
    ctx.moveTo(0, -28); ctx.lineTo(24, 0); ctx.lineTo(0, 28); ctx.lineTo(-24, 0);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // Inner Glowing Core
    ctx.fillStyle = "#f5d0fe";
    ctx.beginPath();
    ctx.moveTo(0, -14); ctx.lineTo(13, 0); ctx.lineTo(0, 14); ctx.lineTo(-13, 0);
    ctx.closePath();
    ctx.fill();
    ctx.restore();

    // 4 Orbiting Shard Needles
    for (let s = 0; s < 4; s++) {
      const sAng = -rot * 1.8 + s * 1.57;
      const sx = Math.cos(sAng) * 36;
      const sy = Math.sin(sAng) * 22;
      ctx.fillStyle = "#d8b4fe";
      ctx.beginPath();
      ctx.moveTo(sx, sy - 7); ctx.lineTo(sx + 5, sy); ctx.lineTo(sx, sy + 7); ctx.lineTo(sx - 5, sy);
      ctx.closePath();
      ctx.fill();
    }
    return true;
  }

  // 4. DRAGON (Дракон Инферно)
  if (bId.includes("dragon") || bId.includes("дракон")) {
    const wingFlap = Math.sin(time * 0.2) * 12;
    ctx.save();
    // Huge Draconic Wings
    ctx.fillStyle = "#7f1d1d";
    ctx.strokeStyle = "#ef4444";
    ctx.lineWidth = 2.5;
    // Left wing
    ctx.beginPath();
    ctx.moveTo(-10, -8);
    ctx.quadraticCurveTo(-38, -32 + wingFlap, -48, -4 + wingFlap);
    ctx.lineTo(-24, 8);
    ctx.closePath();
    ctx.fill(); ctx.stroke();
    // Right wing
    ctx.beginPath();
    ctx.moveTo(10, -8);
    ctx.quadraticCurveTo(38, -32 - wingFlap, 48, -4 - wingFlap);
    ctx.lineTo(24, 8);
    ctx.closePath();
    ctx.fill(); ctx.stroke();

    // Armored Scaled Body
    ctx.fillStyle = "#991b1b";
    ctx.strokeStyle = "#f87171";
    ctx.beginPath();
    ctx.ellipse(0, 4, 18, 22, 0, 0, Math.PI * 2);
    ctx.fill(); ctx.stroke();

    // Horned Dragon Head
    ctx.fillStyle = "#b91c1c";
    ctx.beginPath();
    ctx.moveTo(-10 * facing, -16);
    ctx.lineTo(16 * facing, -24);
    ctx.lineTo(10 * facing, -8);
    ctx.closePath();
    ctx.fill();
    // Swept-back Horns
    ctx.strokeStyle = "#facc15";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(-6 * facing, -22); ctx.quadraticCurveTo(-18 * facing, -34, -26 * facing, -30);
    ctx.stroke();

    // Glowing Lava Breath Throat
    ctx.fillStyle = "#fbbf24";
    ctx.shadowColor = "#f97316"; ctx.shadowBlur = 12;
    ctx.beginPath();
    ctx.arc(12 * facing, -16, 4.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  // 5. PUDGE (Мясник из Чрева)
  if (bId.includes("pudge") || bId.includes("мясник")) {
    ctx.save();
    // Rotund Stitched Abomination Body
    ctx.fillStyle = "#57534e";
    ctx.strokeStyle = "#1c1917";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.ellipse(0, 4, 25, 26, 0, 0, Math.PI * 2);
    ctx.fill(); ctx.stroke();

    // Stitched Grotesque Flesh Seams
    ctx.strokeStyle = "#a8a29e";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(-12, -10); ctx.lineTo(-4, 14);
    ctx.moveTo(8, -6); ctx.lineTo(14, 16);
    ctx.stroke();

    // Bloody Butcher Apron
    ctx.fillStyle = "#7f1d1d";
    ctx.beginPath();
    ctx.moveTo(-14, -8); ctx.lineTo(14, -8); ctx.lineTo(10, 20); ctx.lineTo(-10, 20);
    ctx.closePath();
    ctx.fill();

    // Right Hand: Heavy Butcher Cleaver
    ctx.fillStyle = "#e2e8f0";
    ctx.strokeStyle = "#991b1b";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.rect(20 * facing, -12, 10 * facing, 22);
    ctx.fill(); ctx.stroke();

    // Left Hand: Rusted Chain Meat Hook
    ctx.strokeStyle = "#78716c";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(-22 * facing, 2);
    ctx.lineTo(-32 * facing, -4);
    ctx.arc(-32 * facing, 4, 8, -Math.PI / 2, Math.PI / 2);
    ctx.stroke();

    // Monstrous Jaws & Glowing Bile Eyes
    ctx.fillStyle = "#dc2626";
    ctx.fillRect(-8 * facing, -20, 5 * facing, 5);
    ctx.fillStyle = "#84cc16";
    ctx.shadowColor = "#84cc16"; ctx.shadowBlur = 8;
    ctx.fillRect(-10 * facing, -26, 4 * facing, 3);
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  // 6. FACELESS VOID (Хроно-Владыка)
  if (bId.includes("faceless_void") || bId.includes("хроно")) {
    ctx.save();
    // Time-Warped Violet Humanoid Body
    ctx.fillStyle = "#581c87";
    ctx.strokeStyle = "#a855f7";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.roundRect(-14, -18, 28, 36, 6);
    ctx.fill(); ctx.stroke();

    // Smooth Horned Alien Head (No Face!)
    ctx.fillStyle = "#3b0764";
    ctx.beginPath();
    ctx.moveTo(-12, -22); ctx.quadraticCurveTo(0, -42, 12, -22);
    ctx.closePath();
    ctx.fill(); ctx.stroke();

    // Curved Head Ridge / Horn
    ctx.strokeStyle = "#c084fc";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(0, -36); ctx.quadraticCurveTo(8 * facing, -48, 14 * facing, -44);
    ctx.stroke();

    // Glowing Mace of Aeons (Timelock Hammer)
    const maceBob = Math.sin(time * 0.18) * 3;
    ctx.fillStyle = "#c084fc";
    ctx.strokeStyle = "#f3e8ff";
    ctx.lineWidth = 2;
    ctx.shadowColor = "#a855f7"; ctx.shadowBlur = 12;
    ctx.beginPath();
    ctx.roundRect(16 * facing, -16 + maceBob, 12, 14, 4);
    ctx.fill(); ctx.stroke();
    ctx.shadowBlur = 0;

    // Mace Handle
    ctx.strokeStyle = "#94a3b8";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.moveTo(22 * facing, 0 + maceBob); ctx.lineTo(22 * facing, 18 + maceBob);
    ctx.stroke();
    ctx.restore();
    return true;
  }

  return false;
}
