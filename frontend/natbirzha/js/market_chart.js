const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[char]));

function normalizePoints(points) {
  return (Array.isArray(points) ? points : [])
    .map((point) => ({
      value: Number(point?.value ?? point?.price),
      timestamp: point?.timestamp || '',
    }))
    .filter((point) => Number.isFinite(point.value));
}

export function renderMarketChart(points, options = {}) {
  const normalized = normalizePoints(points);
  const width = 360;
  const height = Number(options.height || 132);
  const pad = { left: 8, right: 8, top: 12, bottom: 18 };
  if (normalized.length < 2) {
    return `<div class="market-chart-empty" role="img" aria-label="История котировок накапливается">История котировок накапливается</div>`;
  }
  const values = normalized.map((point) => point.value);
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const spread = Math.max(0.000001, rawMax - rawMin);
  const min = rawMin - spread * 0.12;
  const max = rawMax + spread * 0.12;
  const x = (index) => pad.left + (index * (width - pad.left - pad.right)) / Math.max(1, normalized.length - 1);
  const y = (value) => pad.top + ((max - value) * (height - pad.top - pad.bottom)) / (max - min);
  const linePoints = normalized.map((point, index) => `${x(index).toFixed(1)},${y(point.value).toFixed(1)}`).join(' ');
  const areaPoints = `${pad.left},${height - pad.bottom} ${linePoints} ${width - pad.right},${height - pad.bottom}`;
  const first = values[0];
  const last = values[values.length - 1];
  const trend = last >= first ? 'up' : 'down';
  const color = options.color || (trend === 'up' ? '#db2777' : '#7c3aed');
  const label = esc(options.label || 'График котировки');
  const grid = [0.25, 0.5, 0.75].map((ratio) => {
    const lineY = pad.top + ratio * (height - pad.top - pad.bottom);
    return `<line x1="${pad.left}" y1="${lineY.toFixed(1)}" x2="${width - pad.right}" y2="${lineY.toFixed(1)}" class="market-chart-grid-line" />`;
  }).join('');
  const startLabel = normalized[0].timestamp ? new Date(normalized[0].timestamp).toLocaleDateString('ru-RU') : '';
  const endLabel = normalized[normalized.length - 1].timestamp ? new Date(normalized[normalized.length - 1].timestamp).toLocaleDateString('ru-RU') : '';
  return `<svg viewBox="0 0 ${width} ${height}" class="market-chart" role="img" aria-label="${label}">
    <defs><linearGradient id="market-chart-fill-${trend}" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".24"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
    ${grid}<polygon points="${areaPoints}" fill="url(#market-chart-fill-${trend})" />
    <polyline points="${linePoints}" fill="none" stroke="${color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
    <circle cx="${x(normalized.length - 1).toFixed(1)}" cy="${y(last).toFixed(1)}" r="4" fill="${color}" />
    <text x="${pad.left}" y="${height - 3}" class="market-chart-label">${esc(startLabel)}</text>
    <text x="${width - pad.right}" y="${height - 3}" text-anchor="end" class="market-chart-label">${esc(endLabel)}</text>
  </svg>`;
}

export function trendOf(points) {
  const normalized = normalizePoints(points);
  if (normalized.length < 2) return 'flat';
  return normalized.at(-1).value >= normalized[0].value ? 'up' : 'down';
}
