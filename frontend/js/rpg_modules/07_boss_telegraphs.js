// ============================================================================
// 07_boss_telegraphs.js — Rendering Unique Boss Visual Telegraphs & Ultimates
// (Black Hole, Chronosphere, Resonance Laser, Chains, and Special VFX)
// ============================================================================

function renderSpecialBossTelegraphs(ctx, ARENA, time) {
  if (!ARENA.bossTelegraphs) return;

  for (const bt of ARENA.bossTelegraphs) {
    ctx.save();

    // 1. BLACK HOLE (Чёрная Дыра Энигмы)
    if (bt.type === "black_hole") {
      const bhPulse = 1 + Math.sin(time * 0.1) * 0.05;
      const r = bt.r * bhPulse;

      // Outer Gravitational Accretion Disk
      const grad = ctx.createRadialGradient(bt.cx, bt.cy, r * 0.2, bt.cx, bt.cy, r);
      grad.addColorStop(0, "rgba(2, 6, 23, 0.95)");
      grad.addColorStop(0.45, "rgba(88, 28, 135, 0.75)");
      grad.addColorStop(0.85, "rgba(99, 102, 241, 0.4)");
      grad.addColorStop(1, "rgba(99, 102, 241, 0)");

      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(bt.cx, bt.cy, r, 0, Math.PI * 2);
      ctx.fill();

      // Swirling Event Horizon Rings
      ctx.strokeStyle = "rgba(168, 85, 247, 0.6)";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(bt.cx, bt.cy, r * 0.65, time * 0.08, time * 0.08 + Math.PI * 1.5);
      ctx.stroke();

      // Pure Void Center
      ctx.fillStyle = "#000000";
      ctx.beginPath();
      ctx.arc(bt.cx, bt.cy, r * 0.35, 0, Math.PI * 2);
      ctx.fill();

      // Infalling Star Matter
      for (let s = 0; s < 6; s++) {
        const sAng = -time * 0.12 + s * 1.05;
        const sDist = r * (0.4 + ((time * 0.02 + s * 0.15) % 0.55));
        ctx.fillStyle = "#e0e7ff";
        ctx.beginPath();
        ctx.arc(bt.cx + Math.cos(sAng) * sDist, bt.cy + Math.sin(sAng) * sDist, 2.5, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // 2. CHRONOSPHERE (Хроносфера Войда)
    else if (bt.type === "chronosphere") {
      const r = bt.r;
      // Translucent Violet Sphere
      ctx.fillStyle = "rgba(88, 28, 135, 0.35)";
      ctx.beginPath();
      ctx.arc(bt.cx, bt.cy, r, 0, Math.PI * 2);
      ctx.fill();

      // Glowing Temporal Grid Outline
      ctx.strokeStyle = "#c084fc";
      ctx.lineWidth = 3;
      ctx.shadowColor = "#a855f7";
      ctx.shadowBlur = 14;
      ctx.beginPath();
      ctx.arc(bt.cx, bt.cy, r, 0, Math.PI * 2);
      ctx.stroke();

      // Floating Clock Hour Hand in Center
      ctx.strokeStyle = "#f3e8ff";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.moveTo(bt.cx, bt.cy);
      ctx.lineTo(bt.cx + Math.cos(time * 0.04) * (r * 0.6), bt.cy + Math.sin(time * 0.04) * (r * 0.6));
      ctx.stroke();
      ctx.shadowBlur = 0;
    }

    // 3. ROTATING RESONANCE BEAM (Терзатель)
    else if (bt.type === "rotating_beam") {
      const bx2 = bt.cx + Math.cos(bt.angle) * bt.length;
      const by2 = bt.cy + Math.sin(bt.angle) * bt.length;

      ctx.strokeStyle = bt.color || "#e879f9";
      ctx.lineWidth = 8;
      ctx.shadowColor = "#c084fc";
      ctx.shadowBlur = 16;
      ctx.beginPath();
      ctx.moveTo(bt.cx, bt.cy);
      ctx.lineTo(bx2, by2);
      ctx.stroke();

      // Inner Core White Beam
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(bt.cx, bt.cy);
      ctx.lineTo(bx2, by2);
      ctx.stroke();
      ctx.shadowBlur = 0;
    }

    ctx.restore();
  }

  // Draw Pudge Hook Chains if projectile is Meat Hook
  for (const proj of (ARENA.bossProjectiles || [])) {
    if (proj.isMeatHook && proj.originX != null) {
      ctx.save();
      ctx.strokeStyle = "#78716c";
      ctx.lineWidth = 2.5;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(proj.originX, proj.originY);
      ctx.lineTo(proj.x, proj.y);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();
    }
  }
}
