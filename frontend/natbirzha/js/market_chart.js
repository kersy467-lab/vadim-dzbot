const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[char]));

function normalizePoints(points) {
  return (Array.isArray(points) ? points : [])
    .map((point) => ({ value: Number(point?.value ?? point?.price), timestamp: point?.timestamp || '' }))
    .filter((point) => Number.isFinite(point.value));
}

export function marketChange(points) {
  const normalized = normalizePoints(points);
  if (normalized.length < 2) return { absolute: 0, percent: 0, direction: 'flat' };
  const first = normalized[0].value;
  const last = normalized.at(-1).value;
  const absolute = last - first;
  const percent = first ? (absolute / first) * 100 : 0;
  return { absolute, percent, direction: absolute > 0 ? 'up' : absolute < 0 ? 'down' : 'flat' };
}

export function renderMarketChart(points, options = {}) {
  const normalized = normalizePoints(points);
  const width = 360;
  const height = Number(options.height || 160);
  const pad = { left: 10, right: 44, top: 14, bottom: 20 };
  if (normalized.length === 0) {
    return `<div class="market-chart-empty" role="img" aria-label="История котировок накапливается">История котировок накапливается</div>`;
  }
  if (normalized.length === 1) normalized.push({ ...normalized[0] });
  const values = normalized.map((point) => point.value);
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const spread = Math.max(Math.abs(rawMax) * 0.002, rawMax - rawMin, 0.000001);
  const min = rawMin - spread * 0.12;
  const max = rawMax + spread * 0.12;
  const x = (index) => pad.left + (index * (width - pad.left - pad.right)) / Math.max(1, normalized.length - 1);
  const y = (value) => pad.top + ((max - value) * (height - pad.top - pad.bottom)) / Math.max(0.000001, max - min);
  const linePoints = normalized.map((point, index) => `${x(index).toFixed(1)},${y(point.value).toFixed(1)}`).join(' ');
  const areaPoints = `${pad.left},${height - pad.bottom} ${linePoints} ${width - pad.right},${height - pad.bottom}`;
  const first = values[0];
  const last = values.at(-1);
  const trend = last >= first ? 'up' : 'down';
  const color = options.color || (trend === 'up' ? '#16a34a' : '#ef4444');
  const label = esc(options.label || 'График котировки');
  const gridValues = [max, (max + min) / 2, min];
  const grid = gridValues.map((value) => {
    const gy = y(value);
    return `<line x1="${pad.left}" y1="${gy.toFixed(1)}" x2="${width - pad.right}" y2="${gy.toFixed(1)}" class="market-chart-grid-line"/><text x="${width - 2}" y="${(gy + 3).toFixed(1)}" text-anchor="end" class="market-chart-price">${Number(value).toLocaleString('ru-RU', { maximumFractionDigits: 2 })}</text>`;
  }).join('');
  const startLabel = normalized[0].timestamp ? new Date(normalized[0].timestamp).toLocaleDateString('ru-RU') : '';
  const endLabel = normalized.at(-1).timestamp ? new Date(normalized.at(-1).timestamp).toLocaleDateString('ru-RU') : '';
  return `<svg viewBox="0 0 ${width} ${height}" class="market-chart" role="img" aria-label="${label}">
    <defs><linearGradient id="market-chart-fill-${trend}" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".22"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
    ${grid}<polygon points="${areaPoints}" fill="url(#market-chart-fill-${trend})"/>
    <polyline points="${linePoints}" fill="none" stroke="${color}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
    <circle cx="${x(normalized.length - 1).toFixed(1)}" cy="${y(last).toFixed(1)}" r="3.6" fill="${color}"/>
    <text x="${pad.left}" y="${height - 3}" class="market-chart-label">${esc(startLabel)}</text>
    <text x="${width - pad.right}" y="${height - 3}" text-anchor="end" class="market-chart-label">${esc(endLabel)}</text>
  </svg>`;
}

export function trendOf(points) {
  return marketChange(points).direction;
}
