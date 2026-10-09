const PALETTES = [
  ['#e7b84d', '#8c4f23', '#fff1b8'], ['#49b7d1', '#266e94', '#d9f8ff'],
  ['#72bd76', '#35764f', '#dcffd4'], ['#d87d61', '#98483e', '#ffe0b5'],
  ['#a58ae0', '#5847a1', '#eee4ff'], ['#55b7a0', '#286e68', '#d8fff0'],
  ['#ec8fc0', '#9a4c80', '#ffe1f1'], ['#7da5dc', '#405f9f', '#e1edff'],
  ['#d2a760', '#795a36', '#fff0c9'], ['#83c7b5', '#477d72', '#e1fff4'],
  ['#db7f78', '#934a55', '#ffe3d3'], ['#8a9ab2', '#4c5e78', '#eff4ff'],
  ['#e3a35b', '#8e5437', '#ffebc7'], ['#71b4da', '#3f709c', '#dcedff'],
  ['#b2a6d9', '#625587', '#f1eaff'], ['#accb65', '#648036', '#f1ffd1'],
  ['#f0c16a', '#a36a2e', '#fff5d1'], ['#6eafa6', '#3c706e', '#e0fff9'],
];

const ART = {
  energy: '<path d="m14 2-8 11h5l-1 9 8-12h-5z" fill="{light}" stroke="{dark}" stroke-width="1.1" stroke-linejoin="round"/>',
  water: '<path d="M12 3C10 6 6 10 6 14a6 6 0 0 0 12 0c0-4-4-8-6-11Z" fill="{light}" stroke="{dark}" stroke-width="1.1"/><path d="M8.5 15c.5 1.5 1.7 2.5 3.5 2.5" fill="none" stroke="{dark}" stroke-width="1.2" stroke-linecap="round"/>',
  organic: '<path d="M5 17C5 8 10 4 20 4c0 9-4 15-13 15" fill="{light}" stroke="{dark}" stroke-width="1.1"/><path d="M5 20 16 8m-6 6 1 5m1-9 5 1" fill="none" stroke="{dark}" stroke-width="1.1" stroke-linecap="round"/>',
  mineral: '<path d="m4 16 4-9 4 5 3-8 5 12-8 4z" fill="{light}" stroke="{dark}" stroke-width="1.1" stroke-linejoin="round"/><path d="m8 7 3 13m4-16-1 16m5-4-6 4" fill="none" stroke="{dark}" stroke-width=".9"/>',
  metal: '<path d="m4 8 8-4 8 4-8 4z" fill="{light}" stroke="{dark}" stroke-width="1.1"/><path d="m4 8v8l8 4 8-4V8m-8 4v8m-8-8 8 4 8-4" fill="none" stroke="{dark}" stroke-width="1.1" stroke-linejoin="round"/>',
  building: '<path d="M4 20V9l8-5 8 5v11z" fill="{light}" stroke="{dark}" stroke-width="1.1" stroke-linejoin="round"/><path d="M8 12h2v2H8zm6 0h2v2h-2zm-6 4h2v2H8zm6 0h2v2h-2z" fill="{dark}"/>',
  chemistry: '<path d="M9 4h6m-5 0v6l-5 8a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-8V4" fill="{light}" stroke="{dark}" stroke-width="1.1" stroke-linejoin="round"/><path d="M8 16h8m-6-3 1 .5m4 1.5 1-.5" fill="none" stroke="{dark}" stroke-width="1.1" stroke-linecap="round"/>',
  barrel: '<path d="M7 5c2 1 8 1 10 0l1 14c-2 1-10 1-12 0z" fill="{light}" stroke="{dark}" stroke-width="1.1"/><path d="M7 8c3 1 7 1 10 0m-10 8c3 1 7 1 10 0M9 5l1 14m5-14-1 14" fill="none" stroke="{dark}" stroke-width=".9"/>',
  technology: '<rect x="5" y="5" width="14" height="14" rx="2" fill="{light}" stroke="{dark}" stroke-width="1.1"/><rect x="9" y="9" width="6" height="6" rx="1" fill="none" stroke="{dark}" stroke-width="1.1"/><path d="M8 2v3m4-3v3m4-3v3M8 19v3m4-3v3m4-3v3M2 8h3m-3 4h3m-3 4h3m14-8h3m-3 4h3m-3 4h3" stroke="{dark}" stroke-width="1.1" stroke-linecap="round"/>',
  server: '<rect x="4" y="4" width="16" height="6" rx="1.5" fill="{light}" stroke="{dark}" stroke-width="1.1"/><rect x="4" y="12" width="16" height="7" rx="1.5" fill="{light}" stroke="{dark}" stroke-width="1.1"/><path d="M7 7h.1m3 0h6m-9 8h.1m3 0h6" stroke="{dark}" stroke-width="1.5" stroke-linecap="round"/>',
  transport: '<path d="M3 7h11v10H3zm11 3h4l3 3v4h-7z" fill="{light}" stroke="{dark}" stroke-width="1.1" stroke-linejoin="round"/><circle cx="7" cy="18" r="2" fill="{light}" stroke="{dark}" stroke-width="1.1"/><circle cx="18" cy="18" r="2" fill="{light}" stroke="{dark}" stroke-width="1.1"/>',
  beverage: '<path d="M7 4h9v3h3v13H6V7h1z" fill="{light}" stroke="{dark}" stroke-width="1.1" stroke-linejoin="round"/><path d="M8 11h8m-5 3h4m5-5h2v6h-3" fill="none" stroke="{dark}" stroke-width="1.1" stroke-linecap="round"/>',
  food: '<path d="M5 12h14l-1.5 8h-11z" fill="{light}" stroke="{dark}" stroke-width="1.1" stroke-linejoin="round"/><path d="M7 10c1-3 3-4 5-2 2-3 5-1 5 2M4 12h16" fill="none" stroke="{dark}" stroke-width="1.1" stroke-linecap="round"/>',
  shield: '<path d="m12 3 8 3v5c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6z" fill="{light}" stroke="{dark}" stroke-width="1.1"/><path d="m9 12 2 2 4-5" fill="none" stroke="{dark}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>',
  crystal: '<path d="m12 3 7 6-7 12L5 9z" fill="{light}" stroke="{dark}" stroke-width="1.1" stroke-linejoin="round"/><path d="m5 9 7 2 7-2m-7 2v10m-4-12 4 2 4-2" fill="none" stroke="{dark}" stroke-width=".9"/>',
  crate: '<path d="m4 8 8-4 8 4v10l-8 4-8-4z" fill="{light}" stroke="{dark}" stroke-width="1.1" stroke-linejoin="round"/><path d="m4 8 8 4 8-4m-8 4v10m-4-12 8 4m0-4-8 4" fill="none" stroke="{dark}" stroke-width="1"/>',
};

function hash(value) {
  let output = 2166136261;
  for (const char of value) output = Math.imul(output ^ char.charCodeAt(0), 16777619);
  return output >>> 0;
}

function kindFor(id) {
  if (/^(energy|grid_quota)$/.test(id)) return 'energy';
  if (/(water)/.test(id)) return 'water';
  if (/(beer|wine|spirits|cognac)/.test(id)) return 'beverage';
  if (/(ai_|cloud_compute|server|electronics|components|machinery|robots|sensor|automation|telecom|quantum|drone|accelerator)/.test(id)) return /server|cloud_compute/.test(id) ? 'server' : 'technology';
  if (/(military|armor|gear)/.test(id)) return 'shield';
  if (/(food|grain|feed|flour|meat|milk|hops|grapes|sugar|dairy|agrotech|rations)/.test(id)) return /beer|wine/.test(id) ? 'beverage' : 'food';
  if (/(construction|brick|cement|concrete|lumber|wood|paper|cellulose|cardboard|furniture|prefab|module)/.test(id)) return 'building';
  if (/(chemical|chem|reagent|fertilizer|electrolyte|bioreagent|pharma|plastic|catalyst|fuel|gas|oil|lubricant)/.test(id)) return /fuel|gas|oil|lubricant/.test(id) ? 'barrel' : 'chemistry';
  if (/(logistics|vehicle|transport|truck)/.test(id)) return 'transport';
  if (/(steel|aluminum|copper|metal|alloy|nickel|iron_ore|bauxite)/.test(id)) return 'metal';
  if (/(ore|mineral|diamond|lithium|cobalt|gallium|uranium|rare_earth)/.test(id)) return /diamond/.test(id) ? 'crystal' : 'mineral';
  if (/(forest|tree|bio_raw|seed|wood)/.test(id)) return 'organic';
  if (/(lease|fund|contract|quota|capacity)/.test(id)) return 'crate';
  return 'crate';
}

function escapeAttribute(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]);
}

function clampSize(value) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.max(1, Math.min(96, Math.round(number))) : 20;
}

export function renderResourceIcon(itemId, { size = 20, className = '', label = '' } = {}) {
  const id = String(itemId || '').toLowerCase();
  if (!/^[a-z0-9_]+$/.test(id)) return '';
  const seed = hash(id);
  const [bright, dark, light] = PALETTES[seed % PALETTES.length];
  const shape = ART[kindFor(id)].replaceAll('{light}', light).replaceAll('{dark}', dark);
  const gradientId = `item-art-${id}`;
  const accent = seed % 2
    ? '<path d="m18 3 .7 1.7L20.5 5l-1.8.6L18 7.5l-.7-1.9-1.8-.6 1.8-.3z" fill="#fff" opacity=".9"/>'
    : '<circle cx="18" cy="5" r="1" fill="#fff" opacity=".9"/>';
  const title = label ? `<title>${escapeAttribute(label)}</title>` : '';
  const accessible = label
    ? `role="img" aria-label="${escapeAttribute(label)}"`
    : 'aria-hidden="true"';
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${clampSize(size)}" height="${clampSize(size)}" viewBox="0 0 24 24" class="${escapeAttribute(className)} item-art" data-item="${id}" ${accessible}><defs><linearGradient id="${gradientId}" x1="0" y1="0" x2="1" y2="1"><stop stop-color="${bright}"/><stop offset="1" stop-color="${dark}"/></linearGradient></defs>${title}<rect x="1" y="1" width="22" height="22" rx="7" fill="url(#${gradientId})"/><path d="M4 17c3-3 6-3 9 0s5 3 8 0v4H4z" fill="#fff" opacity=".11"/>${accent}<g>${shape}</g></svg>`;
}
