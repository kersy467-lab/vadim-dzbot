import { normalizeAngle, pointerAt } from './gameplay.mjs?v=20261011_rhythm_game_v1';

const radians = (degrees) => (Number(degrees) - 90) * Math.PI / 180;

function drawArc(ctx, x, y, radius, center, halfWidth, color, width) {
  ctx.beginPath();
  ctx.arc(x, y, radius, radians(center - halfWidth), radians(center + halfWidth));
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.lineCap = 'round';
  ctx.stroke();
}

function drawTicks(ctx, x, y, radius, now) {
  ctx.save();
  ctx.strokeStyle = 'rgba(48, 74, 69, .23)';
  ctx.lineWidth = 1;
  for (let index = 0; index < 48; index += 1) {
    const angle = radians(index * 7.5);
    const major = index % 4 === 0;
    const inner = radius - (major ? 12 : 6);
    ctx.beginPath();
    ctx.moveTo(x + Math.cos(angle) * inner, y + Math.sin(angle) * inner);
    ctx.lineTo(x + Math.cos(angle) * radius, y + Math.sin(angle) * radius);
    ctx.stroke();
  }
  ctx.restore();
}

function drawPointer(ctx, x, y, radius, angle, color) {
  const theta = radians(angle);
  const tipX = x + Math.cos(theta) * (radius + 5);
  const tipY = y + Math.sin(theta) * (radius + 5);
  ctx.save();
  ctx.shadowColor = color;
  ctx.shadowBlur = 14;
  ctx.strokeStyle = color;
  ctx.lineWidth = 4;
  ctx.lineCap = 'round';
  ctx.beginPath();
  ctx.moveTo(x - Math.cos(theta) * 12, y - Math.sin(theta) * 12);
  ctx.lineTo(tipX, tipY);
  ctx.stroke();
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(tipX, tipY, 5, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

export function paint(ctx, width, height, scene, game, now) {
  const family = scene?.scene_family || 'resources';
  const accent = family === 'energy' ? '#d89b29'
    : family === 'technology' ? '#6384c9'
      : family === 'materials' ? '#b86c47' : '#368a70';
  const x = width / 2;
  const y = height / 2 + 6;
  const size = Math.min(width, height);
  const outer = size * 0.39;
  const ring = outer * 0.2;
  const target = normalizeAngle(game?.targetAngle || 0);
  const blue = normalizeAngle(target + 180);
  const angle = pointerAt(game, now);
  const pulse = 0.5 + Math.sin(Number(now) / 340) * 0.5;

  ctx.clearRect(0, 0, width, height);
  const background = ctx.createLinearGradient(0, 0, width, height);
  background.addColorStop(0, 'rgba(255,255,255,.96)');
  background.addColorStop(1, family === 'technology' ? '#e7edf9' : '#e4eee5');
  ctx.fillStyle = background;
  ctx.fillRect(0, 0, width, height);

  ctx.fillStyle = 'rgba(255,255,255,.5)';
  for (let index = 0; index < 7; index += 1) {
    const spotX = (index * 83 + 29) % width;
    const spotY = (index * 47 + 17) % height;
    ctx.beginPath();
    ctx.arc(spotX, spotY, 2 + (index % 3), 0, Math.PI * 2);
    ctx.fill();
  }

  ctx.fillStyle = 'rgba(40,69,63,.055)';
  ctx.beginPath();
  ctx.arc(x, y, outer + 28, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = 'rgba(255,255,255,.75)';
  ctx.beginPath();
  ctx.arc(x, y, outer + 16, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = 'rgba(48,74,69,.11)';
  ctx.lineWidth = ring;
  ctx.beginPath();
  ctx.arc(x, y, outer, 0, Math.PI * 2);
  ctx.stroke();

  drawArc(ctx, x, y, outer, target, game?.goldHalfWidth || 28,
    `rgba(232, 166, 44, ${0.72 + pulse * 0.2})`, ring);
  drawArc(ctx, x, y, outer, blue, game?.blueHalfWidth || 22,
    'rgba(59, 166, 207, .88)', ring);
  drawTicks(ctx, x, y, outer + 16, now);

  ctx.strokeStyle = 'rgba(255,255,255,.85)';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.arc(x, y, outer - ring * 0.58, 0, Math.PI * 2);
  ctx.stroke();
  drawPointer(ctx, x, y, outer + ring * 0.05, angle, accent);

  const hub = ctx.createRadialGradient(x - 8, y - 10, 4, x, y, outer * 0.47);
  hub.addColorStop(0, '#ffffff');
  hub.addColorStop(1, family === 'technology' ? '#dfe7f7' : '#e4eee5');
  ctx.fillStyle = hub;
  ctx.beginPath();
  ctx.arc(x, y, outer * 0.47, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = 'rgba(48,74,69,.16)';
  ctx.lineWidth = 1.5;
  ctx.stroke();

  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillStyle = '#71837b';
  ctx.font = '800 10px system-ui, sans-serif';
  ctx.fillText('РИТМ ЦЕХА', x, y - 19);
  ctx.fillStyle = '#263d37';
  ctx.font = `900 ${Math.max(25, Math.min(39, outer * 0.42))}px system-ui, sans-serif`;
  ctx.fillText(`×${Number(game?.multiplier || 1).toFixed(2)}`, x, y + 9);
  ctx.fillStyle = '#74847c';
  ctx.font = '700 9px system-ui, sans-serif';
  ctx.fillText(`ЗАРЯД ${Number(game?.charge || 0)}/16`, x, y + 32);

  for (const [center, label, color] of [
    [target, 'ЗОЛОТО +2', '#956515'], [blue, 'СИНИЙ +1', '#277090'],
  ]) {
    const theta = radians(center);
    const labelRadius = outer + ring * 0.95;
    ctx.fillStyle = color;
    ctx.font = '800 9px system-ui, sans-serif';
    ctx.fillText(label, x + Math.cos(theta) * labelRadius, y + Math.sin(theta) * labelRadius);
  }

  if (game?.lastResult) {
    const messages = { gold: 'ТОЧНО!', blue: 'ХОРОШО!', miss: 'МИМО', too_soon: 'СЛИШКОМ РАНО' };
    ctx.fillStyle = game.lastResult === 'gold' ? '#9a6815'
      : game.lastResult === 'blue' ? '#277090' : '#9e5145';
    ctx.font = '900 12px system-ui, sans-serif';
    ctx.fillText(messages[game.lastResult] || '', x, y + outer + 18);
  }
}
