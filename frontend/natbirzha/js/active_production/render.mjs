function roundedRect(ctx, x, y, width, height, radius) {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.beginPath(); ctx.moveTo(x + r, y); ctx.lineTo(x + width - r, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + r);
  ctx.lineTo(x + width, y + height - r); ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
  ctx.lineTo(x + r, y + height); ctx.quadraticCurveTo(x, y + height, x, y + height - r);
  ctx.lineTo(x, y + r); ctx.quadraticCurveTo(x, y, x + r, y); ctx.closePath();
}

export function stationPoints(width, height) {
  return {
    source: { x: width * 0.17, y: height * 0.63 },
    workstation: { x: width * 0.5, y: height * 0.31 },
    destination: { x: width * 0.83, y: height * 0.63 },
  };
}

function drawStation(ctx, family, point, title, variant, pulse, isDestination = false) {
  const x = point.x; const y = point.y;
  const accents = { resources: '#9c6b3d', energy: '#e9bb43', oilgas: '#44859a', materials: '#cf7750', infrastructure: '#47866f', technology: '#6176b6', bank: '#aa8945' };
  const accent = accents[family] || accents.resources;
  ctx.save();
  ctx.fillStyle = `rgba(39, 65, 53, ${0.10 + pulse * 0.06})`;
  ctx.beginPath(); ctx.ellipse(x, y + 23, 67, 18, 0, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = '#fffdf6'; ctx.strokeStyle = accent; ctx.lineWidth = 4;
  roundedRect(ctx, x - 43, y - 37, 86, 61, 12); ctx.fill(); ctx.stroke();
  ctx.fillStyle = accent;
  if (isDestination && family === 'resources') {
    ctx.fillRect(x - 24, y - 14, 38, 24); ctx.fillStyle = '#f4dfb5'; ctx.fillRect(x - 18, y - 8, 18, 12);
    ctx.fillStyle = accent; ctx.beginPath(); ctx.arc(x - 18, y + 15, 6, 0, Math.PI * 2); ctx.arc(x + 9, y + 15, 6, 0, Math.PI * 2); ctx.fill();
  } else if (isDestination && family === 'energy') {
    ctx.fillRect(x - 27, y - 5, 16, 23); ctx.fillRect(x - 7, y - 17, 17, 35); ctx.fillRect(x + 14, y - 1, 13, 19);
    ctx.fillStyle = '#fff2bb'; ctx.fillRect(x - 2, y - 11, 6, 7); ctx.fillRect(x + 18, y + 4, 5, 6);
  } else if (isDestination && family === 'oilgas') {
    ctx.beginPath(); ctx.ellipse(x, y - 15, 23, 8, 0, 0, Math.PI * 2); ctx.fill(); ctx.fillRect(x - 23, y - 15, 46, 29);
    ctx.beginPath(); ctx.ellipse(x, y + 14, 23, 8, 0, 0, Math.PI); ctx.fill();
  } else if (isDestination && family === 'materials') {
    ctx.fillRect(x - 28, y + 9, 56, 7); ctx.fillRect(x - 22, y - 7, 19, 16); ctx.fillRect(x + 3, y - 12, 19, 21);
    ctx.fillStyle = '#ffe9d8'; ctx.fillRect(x - 18, y - 3, 11, 7); ctx.fillRect(x + 7, y - 8, 11, 7);
  } else if (isDestination && family === 'infrastructure') {
    ctx.beginPath(); ctx.moveTo(x - 28, y - 6); ctx.lineTo(x, y - 24); ctx.lineTo(x + 28, y - 6); ctx.fill();
    ctx.fillRect(x - 23, y - 6, 46, 24); ctx.fillStyle = '#fff6dc'; ctx.fillRect(x - 16, y - 1, 10, 8); ctx.fillRect(x + 6, y - 1, 10, 8);
  } else if (isDestination && family === 'technology') {
    ctx.fillRect(x - 24, y - 15, 48, 32); ctx.strokeStyle = '#fff'; ctx.lineWidth = 2;
    for (let pin = -17; pin <= 17; pin += 8) { ctx.beginPath(); ctx.moveTo(x + pin, y - 20); ctx.lineTo(x + pin, y - 15); ctx.moveTo(x + pin, y + 17); ctx.lineTo(x + pin, y + 22); ctx.stroke(); }
    ctx.fillStyle = '#dfe5ff'; ctx.fillRect(x - 11, y - 7, 22, 16);
  } else if (isDestination && family === 'bank') {
    ctx.fillRect(x - 28, y - 3, 56, 20); ctx.fillStyle = '#fff5dc'; ctx.fillRect(x - 20, y - 12, 40, 10);
    ctx.fillStyle = accent; ctx.beginPath(); ctx.arc(x, y - 17, 8, 0, Math.PI * 2); ctx.fill();
  } else if (family === 'resources') {
    ctx.beginPath(); ctx.moveTo(x - 28, y + 7); ctx.lineTo(x - 9, y - 23); ctx.lineTo(x + 9, y + 7); ctx.fill();
    ctx.beginPath(); ctx.moveTo(x - 5, y + 7); ctx.lineTo(x + 13, y - 14); ctx.lineTo(x + 31, y + 7); ctx.fill();
  } else if (family === 'energy') {
    ctx.fillRect(x - 23, y - 17, 46, 35); ctx.fillStyle = '#fff6ce';
    ctx.beginPath(); ctx.moveTo(x + 3, y - 13); ctx.lineTo(x - 11, y + 1); ctx.lineTo(x - 2, y + 1); ctx.lineTo(x - 8, y + 13); ctx.lineTo(x + 12, y - 4); ctx.lineTo(x + 3, y - 4); ctx.fill();
  } else if (family === 'oilgas') {
    ctx.strokeStyle = accent; ctx.lineWidth = 5; ctx.beginPath(); ctx.moveTo(x - 24, y + 11); ctx.lineTo(x - 8, y - 17); ctx.lineTo(x + 15, y + 11); ctx.moveTo(x - 31, y - 4); ctx.lineTo(x + 27, y - 4); ctx.stroke();
    ctx.beginPath(); ctx.arc(x + 20, y + 7, 8, 0, Math.PI * 2); ctx.fill();
  } else if (family === 'materials') {
    ctx.fillRect(x - 23, y - 15, 46, 31); ctx.fillStyle = '#fff3e8'; ctx.fillRect(x - 13, y - 4, 26, 20); ctx.fillStyle = accent; ctx.fillRect(x - 20, y - 21, 11, 8); ctx.fillRect(x + 9, y - 21, 11, 8);
  } else if (family === 'infrastructure') {
    ctx.beginPath(); ctx.moveTo(x - 27, y - 4); ctx.lineTo(x, y - 23); ctx.lineTo(x + 28, y - 4); ctx.fill(); ctx.fillRect(x - 22, y - 4, 44, 23); ctx.fillStyle = '#fffdf6'; ctx.fillRect(x - 7, y + 3, 14, 16);
  } else if (family === 'technology') {
    for (let i = 0; i < 3; i += 1) { ctx.fillRect(x - 27 + i * 20, y - 22, 15, 42); ctx.fillStyle = '#d8e1ff'; ctx.fillRect(x - 23 + i * 20, y - 15, 7, 5); ctx.fillStyle = accent; }
  } else {
    ctx.fillRect(x - 26, y - 13, 52, 32); ctx.fillStyle = '#fff7df'; ctx.fillRect(x - 19, y - 6, 38, 7); ctx.fillStyle = accent; ctx.fillRect(x - 9, y + 7, 18, 13);
  }
  ctx.fillStyle = '#34463e'; ctx.font = '700 12px system-ui'; ctx.textAlign = 'center'; ctx.fillText(title, x, y + 49, 92);
  ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(x + 33, y - 29, 12, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = accent; ctx.font = '700 10px system-ui'; ctx.fillText(String(variant + 1), x + 33, y - 25);
  ctx.restore();
}

export function paint(ctx, width, height, scene, game, now) {
  const color = scene?.scene_family === 'energy' ? '#edf3da' : scene?.scene_family === 'technology' ? '#e8eef7' : '#e8efe0';
  ctx.clearRect(0, 0, width, height); ctx.fillStyle = color; ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = 'rgba(255,255,255,.45)';
  for (let i = 0; i < 9; i += 1) {
    const x = ((i * 137 + 33) % width); const y = ((i * 79 + 22) % height);
    ctx.beginPath(); ctx.arc(x, y, 10 + (i % 3) * 4, 0, Math.PI * 2); ctx.fill();
  }
  const { source, workstation, destination } = stationPoints(width, height);
  ctx.strokeStyle = 'rgba(77, 122, 99, .32)'; ctx.lineWidth = 12; ctx.setLineDash([11, 10]);
  ctx.beginPath(); ctx.moveTo(source.x, source.y); ctx.lineTo(workstation.x, workstation.y); ctx.lineTo(destination.x, destination.y); ctx.stroke(); ctx.setLineDash([]);
  const pulse = (Math.sin(now / 430) + 1) / 2;
  drawStation(ctx, scene?.scene_family, source, 'ПРИЁМКА', scene?.microvariant || 0, pulse);
  drawStation(ctx, scene?.scene_family, workstation, scene?.workstation || 'ЛИНИЯ', (scene?.microvariant || 0) + 1, pulse);
  drawStation(ctx, scene?.scene_family, destination, scene?.delivery_marker || 'СКЛАД', (scene?.microvariant || 0) + 2, pulse, true);
  const target = ({ pickup: source, work: workstation, calibrate: workstation, deliver: destination })[game.shift.phase];
  if (target) { ctx.strokeStyle = '#218866'; ctx.lineWidth = 3 + pulse * 2; ctx.beginPath(); ctx.arc(target.x, target.y, 48 + pulse * 7, 0, Math.PI * 2); ctx.stroke(); }
  ctx.fillStyle = '#2b5c49'; ctx.beginPath(); ctx.ellipse(game.actor.x, game.actor.y + 14, 19, 7, 0, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = scene?.scene_family === 'infrastructure' ? '#397e6b' : '#d3983c';
  roundedRect(ctx, game.actor.x - 18, game.actor.y - 8, 36, 21, 8); ctx.fill();
  ctx.fillStyle = '#fff4cf'; ctx.beginPath(); ctx.arc(game.actor.x, game.actor.y - 13, 9, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = '#3e5148'; ctx.beginPath(); ctx.arc(game.actor.x - 10, game.actor.y + 14, 5, 0, Math.PI * 2); ctx.arc(game.actor.x + 10, game.actor.y + 14, 5, 0, Math.PI * 2); ctx.fill();
  if (game.hasCargo) { ctx.fillStyle = '#d4aa57'; ctx.fillRect(game.actor.x - 7, game.actor.y - 34, 14, 13); ctx.strokeStyle = '#8b6832'; ctx.strokeRect(game.actor.x - 7, game.actor.y - 34, 14, 13); }
}
