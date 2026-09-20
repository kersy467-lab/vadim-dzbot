// ============================================================================
// 06_boss_models_late.js — Procedural Vector Models for Bosses 14–20
// (Dark Tormentor, Storm Spirit, Doom, Primal Beast, Phantom Roshan, Tinker, Enigma)
// ============================================================================

function drawBossModelLate(ctx, b, bId, time) {
  const facing = b.facing || 1;

  // 14. DARK TORMENTOR (Тёмный Терзатель Бездны)
  if (bId.includes("dark_tormentor") || bId.includes("тёмный терзатель")) {
    const rot = time * 0.04;
    ctx.save();
    ctx.rotate(-rot);
    ctx.fillStyle = "#1e1b4b";
    ctx.strokeStyle = "#c084fc";
    ctx.lineWidth = 3.5;
    ctx.shadowColor = "#7c3aed"; ctx.shadowBlur = 18;
    ctx.beginPath();
    ctx.moveTo(0, -32); ctx.lineTo(26, 0); ctx.lineTo(0, 32); ctx.lineTo(-26, 0);
    ctx.closePath();
    ctx.fill(); ctx.stroke();
    // Inner Singularity Eye
    ctx.fillStyle = "#a855f7";
    ctx.beginPath();
    ctx.arc(0, 0, 10, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    // 6 Orbiting Void Needles
    for (let s = 0; s < 6; s++) {
      const sAng = rot * 2.2 + s * (Math.PI / 3);
      const sx = Math.cos(sAng) * 40;
      const sy = Math.sin(sAng) * 24;
      ctx.fillStyle = "#e9d5ff";
      ctx.fillRect(sx - 3, sy - 3, 6, 6);
    }
    return true;
  }

  // 15. STORM SPIRIT (Громовой Дух)
  if (bId.includes("storm_spirit") || bId.includes("громовой дух")) {
    const sBob = Math.sin(time * 0.22) * 4;
    ctx.save();
    ctx.translate(0, sBob);
    // Jovial Electric Djinn Body
    ctx.fillStyle = "#0284c7";
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 3;
    ctx.shadowColor = "#38bdf8"; ctx.shadowBlur = 14;
    ctx.beginPath();
    ctx.ellipse(0, 2, 22, 24, 0, 0, Math.PI * 2);
    ctx.fill(); ctx.stroke();

    // Silken Vest
    ctx.fillStyle = "#dc2626";
    ctx.beginPath();
    ctx.moveTo(-10, -12); ctx.lineTo(10, -12); ctx.lineTo(6, 14); ctx.lineTo(-6, 14);
    ctx.closePath();
    ctx.fill();

    // Whimsical Topknot / Mustache & Crackling Eyes
    ctx.fillStyle = "#0369a1";
    ctx.beginPath();
    ctx.arc(0, -20, 9, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#facc15";
    ctx.fillRect(-5 * facing, -21, 3 * facing, 2.5);
    ctx.fillRect(2 * facing, -21, 3 * facing, 2.5);

    // Electric Sparks Trailing
    ctx.strokeStyle = "#facc15";
    ctx.lineWidth = 2;
    for (let sp = 0; sp < 4; sp++) {
      const spAng = time * 0.2 + sp * 1.57;
      const spx = Math.cos(spAng) * 26;
      const spy = Math.sin(spAng) * 18;
      ctx.beginPath();
      ctx.moveTo(spx, spy); ctx.lineTo(spx + 6, spy - 6); ctx.lineTo(spx + 2, spy - 10);
      ctx.stroke();
    }
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  // 16. DOOM (Вестник Апокалипсиса / Lord Doom)
  if (bId.includes("doom") || bId.includes("вестник")) {
    ctx.save();
    // Massive Crimson Demon Torso
    ctx.fillStyle = "#7f1d1d";
    ctx.strokeStyle = "#ef4444";
    ctx.lineWidth = 3.5;
    ctx.beginPath();
    ctx.roundRect(-18, -22, 36, 42, 6);
    ctx.fill(); ctx.stroke();

    // Leathery Demonic Wings
    ctx.fillStyle = "#450a0a";
    ctx.beginPath();
    ctx.moveTo(-16 * facing, -12); ctx.lineTo(-44 * facing, -38); ctx.lineTo(-30 * facing, 8);
    ctx.moveTo(16 * facing, -12); ctx.lineTo(44 * facing, -38); ctx.lineTo(30 * facing, 8);
    ctx.fill();

    // Curved Horned Helm & Flaming Eyes
    ctx.fillStyle = "#18181b";
    ctx.beginPath();
    ctx.moveTo(-10 * facing, -22); ctx.lineTo(10 * facing, -22); ctx.lineTo(0, -38);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = "#f59e0b";
    ctx.lineWidth = 3;
    ctx.stroke();

    // Giant Flaming Sword of Doom
    const swBob = Math.sin(time * 0.18) * 3;
    ctx.fillStyle = "#fbbf24";
    ctx.strokeStyle = "#dc2626";
    ctx.lineWidth = 2.5;
    ctx.shadowColor = "#f97316"; ctx.shadowBlur = 14;
    ctx.beginPath();
    ctx.rect(22 * facing, -34 + swBob, 6, 44);
    ctx.fill(); ctx.stroke();
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  // 17. PRIMAL BEAST (Первобытный Титан)
  if (bId.includes("primal_beast") || bId.includes("первобытный")) {
    ctx.save();
    // Colossal Quad-Legged Beast Body
    ctx.fillStyle = "#78350f";
    ctx.strokeStyle = "#d97706";
    ctx.lineWidth = 3.5;
    ctx.beginPath();
    ctx.ellipse(0, 4, 32, 25, 0, 0, Math.PI * 2);
    ctx.fill(); ctx.stroke();

    // Stone Carapace Plates
    ctx.fillStyle = "#451a03";
    for (let p = -2; p <= 2; p++) {
      ctx.fillRect(p * 10 - 4, -14, 8, 10);
    }

    // Heavy Horned Battering Snout
    ctx.fillStyle = "#92400e";
    ctx.beginPath();
    ctx.moveTo(16 * facing, -8); ctx.lineTo(34 * facing, 4); ctx.lineTo(18 * facing, 16);
    ctx.closePath();
    ctx.fill();

    // Massive Curved Forward Horns
    ctx.strokeStyle = "#fbbf24";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(22 * facing, -6); ctx.quadraticCurveTo(38 * facing, -24, 46 * facing, -8);
    ctx.stroke();
    ctx.restore();
    return true;
  }

  // 18. PHANTOM ROSHAN (Призрачный Рошан Хаоса)
  if (bId.includes("phantom_roshan") || bId.includes("призрачный рошан")) {
    const fBob = Math.sin(time * 0.14) * 4;
    ctx.save();
    ctx.translate(0, fBob);
    // Ethereal Translucent Ghost Body
    ctx.fillStyle = "rgba(6, 78, 59, 0.85)";
    ctx.strokeStyle = "#34d399";
    ctx.lineWidth = 3;
    ctx.shadowColor = "#10b981"; ctx.shadowBlur = 22;
    ctx.beginPath();
    ctx.ellipse(0, 0, 30, 26, 0, 0, Math.PI * 2);
    ctx.fill(); ctx.stroke();

    // Spectral Energy Cracks
    ctx.strokeStyle = "#6ee7b7";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.moveTo(-14, -8); ctx.lineTo(-2, 4); ctx.lineTo(16, -6);
    ctx.moveTo(-8, 8); ctx.lineTo(8, 14);
    ctx.stroke();

    // Spectral Horns & Eyes
    ctx.strokeStyle = "#a7f3d0";
    ctx.lineWidth = 3.5;
    ctx.beginPath();
    ctx.moveTo(-16 * facing, -16); ctx.quadraticCurveTo(-30 * facing, -34, -16 * facing, -38);
    ctx.stroke();
    ctx.fillStyle = "#67e8f9";
    ctx.shadowColor = "#67e8f9"; ctx.shadowBlur = 12;
    ctx.fillRect(-14 * facing, -10, 6 * facing, 4);
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  // 19. TINKER (Архиинженер / Omega Tinker)
  if (bId.includes("tinker_boss") || bId.includes("архиинженер")) {
    ctx.save();
    // Steampunk Combat Mech Cockpit
    ctx.fillStyle = "#334155";
    ctx.strokeStyle = "#facc15";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.roundRect(-22, -22, 44, 40, 8);
    ctx.fill(); ctx.stroke();

    // Mechanical Goggles Cockpit Viewport
    ctx.fillStyle = "#0284c7";
    ctx.shadowColor = "#38bdf8"; ctx.shadowBlur = 10;
    ctx.beginPath();
    ctx.arc(0, -6, 11, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;

    // Dual Rocket Pods on Shoulders
    ctx.fillStyle = "#dc2626";
    ctx.fillRect(-30, -28, 10, 16);
    ctx.fillRect(20, -28, 10, 16);
    ctx.fillStyle = "#facc15";
    ctx.fillRect(-28, -32, 6, 4);
    ctx.fillRect(22, -32, 6, 4);

    // High-Tech Laser Emitter Arm
    ctx.strokeStyle = "#94a3b8";
    ctx.lineWidth = 3.5;
    ctx.beginPath();
    ctx.moveTo(18 * facing, 6); ctx.lineTo(34 * facing, 6);
    ctx.stroke();
    ctx.fillStyle = "#ef4444";
    ctx.shadowColor = "#ef4444"; ctx.shadowBlur = 8;
    ctx.fillRect(32 * facing, 3, 5 * facing, 6);
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  // 20. ENIGMA (Пожиратель Миров / Enigma Cosmic)
  if (bId.includes("enigma") || bId.includes("пожиратель миров")) {
    const eSpin = time * 0.04;
    ctx.save();
    // Cosmic Nebula Void Entity
    ctx.fillStyle = "#1e1b4b";
    ctx.strokeStyle = "#818cf8";
    ctx.lineWidth = 3;
    ctx.shadowColor = "#6366f1"; ctx.shadowBlur = 24;
    ctx.beginPath();
    ctx.ellipse(0, 0, 26, 30, 0, 0, Math.PI * 2);
    ctx.fill(); ctx.stroke();

    // Swirling Central Singularity in Chest
    ctx.fillStyle = "#020617";
    ctx.beginPath();
    ctx.arc(0, 0, 12, 0, Math.PI * 2);
    ctx.fill();

    // Orbiting Cosmic Asteroid Fragments
    for (let a = 0; a < 5; a++) {
      const aAng = eSpin + a * 1.25;
      const ax = Math.cos(aAng) * 36;
      const ay = Math.sin(aAng) * 22;
      ctx.fillStyle = "#c7d2fe";
      ctx.beginPath();
      ctx.arc(ax, ay, 3, 0, Math.PI * 2);
      ctx.fill();
    }

    // Glowing Star Eyes
    ctx.fillStyle = "#ffffff";
    ctx.shadowColor = "#ffffff"; ctx.shadowBlur = 12;
    ctx.fillRect(-6 * facing, -16, 3 * facing, 3);
    ctx.fillRect(3 * facing, -16, 3 * facing, 3);
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  return false;
}
