import { getNextGameItemArtwork } from './next_game_item_art.mjs?v=20261010_next_game_item_art_v1';

const PALETTES = {
  energy: ['#f2c14e', '#976600', '#fff0a8'],
  water: ['#2496c8', '#155477', '#d8f1ff'],
  organic: ['#78a867', '#3f7048', '#e1f1d4'],
  mineral: ['#a29a6c', '#625d3b', '#f0e8bd'],
  metal: ['#84969d', '#46575f', '#e1eaed'],
  building: ['#c3925e', '#795434', '#f4dfbf'],
  chemistry: ['#5d9d91', '#315d56', '#d8f0e8'],
  barrel: ['#847766', '#514638', '#eee0c4'],
  crudeOil: ['#737d7e', '#354044', '#d8c98f'],
  diesel: ['#d89a22', '#805214', '#ffd36a'],
  technology: ['#708eb8', '#405f8b', '#dce9ff'],
  server: ['#677f8c', '#394e59', '#dce7eb'],
  transport: ['#6b9e91', '#385f56', '#def0e5'],
  beverage: ['#bb7a3f', '#70461f', '#ffe2b1'],
  beer: ['#e0a91f', '#8a5311', '#ffe6a0'],
  food: ['#98a94e', '#5e6d31', '#eff4c4'],
  shield: ['#6d8290', '#3c4f5b', '#e3edf2'],
  crystal: ['#7892bd', '#455e8b', '#e2edff'],
  crate: ['#b58d58', '#765638', '#f4e2be'],
};

const ART = {
  energy: '<path d="m14 2-8 11h5l-1 9 8-12h-5z" fill="{light}" stroke="{dark}" stroke-width="1.1" stroke-linejoin="round"/>',
  water: '<path d="M12 3C10 6 6 10 6 14a6 6 0 0 0 12 0c0-4-4-8-6-11Z" fill="{light}" stroke="{dark}" stroke-width="1.1"/><path d="M8.5 15c.5 1.5 1.7 2.5 3.5 2.5" fill="none" stroke="{dark}" stroke-width="1.2" stroke-linecap="round"/>',
  crudeOil: '<path d="M7.3 5.4h9.4l1.2 13c-2.5 1.8-9.3 1.8-11.8 0z" fill="#202629" stroke="#101517" stroke-width="1.1"/><ellipse cx="12" cy="5.4" rx="4.7" ry="1.4" fill="#4c5759" stroke="#101517" stroke-width="1.1"/><path d="M7.8 8c2.3 1.1 6.1 1.1 8.4 0m-8 7.3c2.2 1 5.5 1 7.8 0" fill="none" stroke="#9ba4a1" stroke-width="1.1"/><path d="M10.7 10.5c-.65 1-1.3 1.6-1.3 2.4a1.6 1.6 0 0 0 3.2 0c0-.8-.65-1.4-1.3-2.4z" fill="#d8c98f"/>',
  diesel: '<path d="M7 9h10l1 11H6L7 9z" fill="#edb833" stroke="#805214" stroke-width="1.1" stroke-linejoin="round"/><path d="M9 8V6a3 3 0 0 1 6 0v2" fill="none" stroke="#805214" stroke-width="1.5" stroke-linecap="round"/><path d="M15 9V7h3l1 2M8 12h8m-8 3h8" fill="none" stroke="#fff1b1" stroke-width="1.1" stroke-linecap="round"/>',
  beer: '<path d="M6 8h11v12H6z" fill="#f0bb37" stroke="#7b4c0c" stroke-width="1.1" stroke-linejoin="round"/><path d="M17 10h2a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2" fill="none" stroke="#7b4c0c" stroke-width="1.4"/><path d="M6 9c0-1.2 1-2 2-2 .3-1.4 1.4-2.2 2.7-1.7.8-1.3 2.8-1.3 3.6 0 1.5-.4 2.7.5 2.7 1.7v2H6z" fill="#fff7dd" stroke="#c58a20" stroke-width=".8" stroke-linejoin="round"/><path d="M9 12v5m4-5v5" stroke="#fff0b8" stroke-width="1.2" stroke-linecap="round"/>',
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

function kindFor(id) {
  if (/^(energy|grid_quota)$/.test(id)) return 'energy';
  if (/(water)/.test(id)) return 'water';
  if (/^(oil|oil_crude|crude_oil)$/.test(id)) return 'crudeOil';
  if (/(fuel_diesel|diesel)/.test(id)) return 'diesel';
  if (/^beer$/.test(id)) return 'beer';
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
  const special = getNextGameItemArtwork(id);
  const kind = kindFor(id);
  const [bright, dark, light] = special?.palette || PALETTES[kind];
  const shape = (special?.art || ART[kind]).replaceAll('{light}', light).replaceAll('{dark}', dark);
  const gradientId = `item-art-${id}`;
  const title = label ? `<title>${escapeAttribute(label)}</title>` : '';
  const accessible = label
    ? `role="img" aria-label="${escapeAttribute(label)}"`
    : 'aria-hidden="true"';
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${clampSize(size)}" height="${clampSize(size)}" viewBox="0 0 24 24" class="${escapeAttribute(className)} item-art" data-item="${id}" ${accessible}><defs><linearGradient id="${gradientId}" x1="0" y1="0" x2="1" y2="1"><stop stop-color="${bright}"/><stop offset="1" stop-color="${dark}"/></linearGradient></defs>${title}<rect x="1" y="1" width="22" height="22" rx="7" fill="url(#${gradientId})"/><path d="M4 17c3-3 6-3 9 0s5 3 8 0v4H4z" fill="#fff" opacity=".11"/><g>${shape}</g></svg>`;
}
