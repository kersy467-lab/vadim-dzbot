import { renderResourceIcon } from './resource_icons.mjs';

const ICON_PATHS = Object.freeze({
  overview: '<path d="M3 10.5 12 3l9 7.5v9a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 19.5z"/><path d="M9 21v-7h6v7"/>',
  factory: '<path d="M3 21V9l6 3V8l6 4V5h3l3 3v13z"/><path d="M7 17h2m3 0h2m3 0h2"/>',
  upgrade: '<path d="M12 20V4m-6 6 6-6 6 6"/><path d="M5 20h14"/>',
  market: '<path d="M3 20V5m0 15h18"/><path d="m6 16 4-5 3 2 5-7"/><path d="M16 6h2v2"/>',
  military: '<path d="m14 4 6 6m-9 3 6 6M4 20l7-7m2-9 7 7M4 4l7 7"/>',
  leaderboard: '<path d="M4 20h16M6 17V9h4v8m4 0V4h4v13"/><path d="M4 6h2m12 0h2"/>',
  state: '<path d="M3 10h18M5 10v9m4-9v9m6-9v9m4-9v9M3 21h18M12 3 3 8h18z"/>',
  energy: '<path d="m13 2-9 12h7l-1 8 10-13h-7z"/>',
  water: '<path d="M12 3s-7 7.2-7 11a7 7 0 0 0 14 0c0-3.8-7-11-7-11z"/><path d="M9 15a3 3 0 0 0 3 3"/>',
  mining: '<path d="m3 19 6-10 4 5 3-4 5 9z"/><path d="M3 19h18M5 6l4 3 3-5 4 6"/>',
  agriculture: '<path d="M12 21v-9m0 0C5 12 4 7 4 4c5 0 8 2 8 8zm0-2c0-4 3-7 8-7 0 5-2 8-8 8"/><path d="M7 21h10"/>',
  oil: '<path d="M12 3c-2 3-5 6-5 10a5 5 0 0 0 10 0c0-4-3-7-5-10z"/><path d="M9 15c.3 1.2 1.2 2 2.5 2"/>',
  metallurgy: '<path d="M5 20 8 4h8l3 16z"/><path d="M8 9h8m-9 5h10m-10 4h11"/>',
  construction: '<path d="M3 21h18M6 21V9h12v12M4 9l8-6 8 6"/><path d="M9 13h2m2 0h2m-6 4h2m2 0h2"/>',
  chemistry: '<path d="M9 3h6m-5 0v7l-5 8a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-8V3"/><path d="M7 16h10"/>',
  technology: '<rect x="4" y="4" width="16" height="13" rx="2"/><path d="M8 21h8m-4-4v4m-5-13h10m-10 4h6"/>',
  ai: '<path d="M9 3a3 3 0 0 0-3 3v1a3 3 0 0 0-2 3v4a3 3 0 0 0 2 3v1a3 3 0 0 0 3 3h6a3 3 0 0 0 3-3v-1a3 3 0 0 0 2-3v-4a3 3 0 0 0-2-3V6a3 3 0 0 0-3-3z"/><path d="M9 10h.01M15 10h.01M9 15c2 2 4 2 6 0m-3-5v3"/>',
  logistics: '<path d="M3 7h11v10H3zM14 10h4l3 3v4h-7z"/><circle cx="7" cy="19" r="2"/><circle cx="18" cy="19" r="2"/>',
  brewing: '<path d="M7 4h8v3h3v13H6V7h1zM7 10h8m-6 4h4"/><path d="M18 10h2v6h-2"/>',
  money: '<circle cx="12" cy="12" r="9"/><path d="M15 8.5c-.6-.8-1.6-1.2-3-1.2-1.7 0-2.8.8-2.8 2s1 1.8 2.8 2.2 2.8 1 2.8 2.3-1.1 2.2-2.8 2.2c-1.4 0-2.5-.5-3.2-1.4M12 5.5v13"/>',
  stock: '<path d="M4 19V5m0 14h16"/><path d="m7 15 3-4 3 2 5-7m-2 0h2v2"/>',
  shield: '<path d="M12 3 20 6v5c0 5-3.4 8.4-8 10-4.6-1.6-8-5-8-10V6z"/><path d="m9 12 2 2 4-4"/>',
  warning: '<path d="M12 3 2.8 19a1.4 1.4 0 0 0 1.2 2h16a1.4 1.4 0 0 0 1.2-2z"/><path d="M12 9v5m0 3h.01"/>',
  lock: '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2"/>',
  resource: '<path d="m12 3 9 5-9 5-9-5z"/><path d="m3 12 9 5 9-5m-18 5 9 5 9-5"/>',
  'arrow-left': '<path d="M19 12H5m7 7-7-7 7-7"/>',
  'arrow-right': '<path d="M5 12h14m-7-7 7 7-7 7"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  search: '<circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 5 5"/>',
  plus: '<path d="M12 5v14m-7-7h14"/>',
  minus: '<path d="M5 12h14"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  closeCircle: '<circle cx="12" cy="12" r="9"/><path d="m9 9 6 6m0-6-6 6"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="m19 13 2 1-2 4-2-1a7 7 0 0 1-2 1l-.3 2h-5L9 18a7 7 0 0 1-2-1l-2 1-2-4 2-1a7 7 0 0 1 0-2l-2-1 2-4 2 1a7 7 0 0 1 2-1l.3-2h5L15 6a7 7 0 0 1 2 1l2-1 2 4-2 1a7 7 0 0 1 0 2z"/>',
  handshake: '<path d="m3 12 4-4 4 2 3-2 7 4-5 7-4-2-3 2z"/><path d="m7 8 3-3 5 1 3 2m-9 6 3 3"/>',
  building: '<path d="M4 21V4h11v17m0-10h5v10M8 8h3m-3 4h3m-3 4h3m8 0h.01"/><path d="M2 21h20"/>',
  people: '<circle cx="9" cy="8" r="3"/><path d="M3 20v-1a6 6 0 0 1 12 0v1zm13-9a3 3 0 1 0 0-6m1 9a5 5 0 0 1 4 5"/>',
  document: '<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5m-9 4h5m-5 4h5"/>',
  hospital: '<path d="M4 21V5h16v16M2 21h20M8 9h8m-4-4v8m-4 4h2m4 0h2"/>',
  repair: '<path d="M14 6a5 5 0 0 0-6 6l-5 5 4 4 5-5a5 5 0 0 0 6-6l-3 3-4-4z"/>',
  trophy: '<path d="M8 21h8m-4-4v4M7 4h10v5a5 5 0 0 1-10 0z"/><path d="M7 6H4v2a4 4 0 0 0 4 4m9-6h3v2a4 4 0 0 1-4 4"/>',
  heart: '<path d="M20.8 8.8c0 5.2-8.8 11-8.8 11s-8.8-5.8-8.8-11a4.8 4.8 0 0 1 8.8-2.5 4.8 4.8 0 0 1 8.8 2.5z"/>',
  rebirth: '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M5.5 9A7 7 0 0 1 18 6l2 2M4 16l2 2a7 7 0 0 0 12.5-3"/>',
  refresh: '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M5.5 9A7 7 0 0 1 18 6l2 2M4 16l2 2a7 7 0 0 0 12.5-3"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.6 2.6 0 1 1 4.4 1.9c-1.2 1-1.9 1.4-1.9 3.1m0 3h.01"/>',
  filter: '<path d="M4 6h16M7 12h10m-7 6h4"/>',
  coin: '<circle cx="12" cy="12" r="9"/><path d="M8 9h8m-7 3h6m-5 3h6m-4-9v12"/>',
  chart: '<path d="M4 20V4m0 16h17"/><rect x="7" y="12" width="3" height="5" rx=".5"/><rect x="12" y="8" width="3" height="9" rx=".5"/><rect x="17" y="5" width="3" height="12" rx=".5"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18m0-18a14 14 0 0 0 0 18"/>',
  land: '<path d="m3 7 6-3 6 3 6-3v13l-6 3-6-3-6 3z"/><path d="M9 4v13m6-10v13"/>',
  armor: '<path d="M5 4h14l2 4-2 12H5L3 8z"/><path d="M8 4v5h8V4m-4 5v11"/>',
  cpu: '<rect x="5" y="5" width="14" height="14" rx="2"/><path d="M9 9h6v6H9zM9 2v3m6-3v3M9 19v3m6-3v3M2 9h3m-3 6h3m14-6h3m-3 6h3"/>',
  dataCenter: '<path d="M4 4h16v5H4zm0 7h16v5H4zm0 7h16v2H4z"/><path d="M7 6.5h.01m3-.01h7M7 13.5h.01m3-.01h7m-10 6h.01"/>',
  wind: '<path d="M12 13v8m0-8L5 5m7 8 8-5"/><circle cx="12" cy="13" r="2"/><path d="M5 5a2 2 0 1 1 3-2M20 8a2 2 0 1 1 2 3M12 21a2 2 0 1 0 3 1"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  battery: '<rect x="3" y="7" width="17" height="10" rx="2"/><path d="M23 10v4M7 10h3v4H7zm5 0h3v4h-3z"/>',
  book: '<path d="M4 4h12a3 3 0 0 1 3 3v13H7a3 3 0 0 1-3-3z"/><path d="M4 17a3 3 0 0 1 3-3h12M8 8h7m-7 3h7"/>',
  gift: '<rect x="3" y="8" width="18" height="13" rx="2"/><path d="M2 8h20v4H2zm10 0v13m0-13H7a2 2 0 1 1 2-2c0 2 3 2 3 2zm0 0h5a2 2 0 1 0-2-2c0 2-3 2-3 2z"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5m0-8h.01"/>',
  play: '<path d="m8 5 12 7-12 7z"/>',
  pause: '<path d="M8 5h3v14H8zm5 0h3v14h-3z"/>',
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  cloud: '<path d="M7 18h10a4 4 0 0 0 .4-8A6 6 0 0 0 6 9a4.5 4.5 0 0 0 1 9z"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18m0-18a14 14 0 0 0 0 18"/>',
  tree: '<path d="m12 3 6 7h-3l5 6h-6v5h-4v-5H4l5-6H6z"/>',
  medal: '<circle cx="12" cy="8" r="5"/><path d="m8 12-2 9 6-3 6 3-2-9"/>',
  star: '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9z"/>',
  scale: '<path d="M12 4v16m-7 0h14M5 7h14M7 7l-4 7h8L7 7zm10 0-4 7h8l-4-7z"/>',
  'status-dot': '<circle cx="12" cy="12" r="7" fill="currentColor" stroke="none"/>',
});

const ICON_ALIASES = Object.freeze({
  '🏛️': 'overview', '🏭': 'factory', '⚙️': 'settings', '🔧': 'repair', '🛠️': 'repair',
  '📊': 'market', '⚔️': 'military', '🏆': 'trophy', '👑': 'state', '🎖️': 'medal',
  '⚡': 'energy', '💡': 'energy', '🔌': 'energy', '💧': 'water', '🚰': 'water', '🌊': 'water',
  '⛏️': 'mining', '🪨': 'mining', '💎': 'mining', '🌋': 'mining', '🌾': 'agriculture',
  '🌱': 'agriculture', '🌿': 'agriculture', '🌽': 'agriculture', '🍅': 'agriculture',
  '🍇': 'agriculture', '🍞': 'agriculture', '🍬': 'agriculture', '🐄': 'agriculture',
  '🌲': 'tree', '🛢️': 'oil', '⛽': 'oil', '🔥': 'energy', '🔩': 'metallurgy', '🪙': 'coin',
  '🧪': 'chemistry', '🔬': 'chemistry', '🧫': 'chemistry', '☢️': 'chemistry', '🧬': 'chemistry',
  '🧠': 'ai', '🤖': 'ai', '👁️': 'ai', '🖥️': 'technology', '💻': 'technology', '🦾': 'technology',
  '🚚': 'logistics', '🚛': 'logistics', '🍺': 'brewing', '🍷': 'brewing', '🥃': 'brewing',
  '💰': 'money', '💵': 'money', '💶': 'money', '💸': 'money', '💳': 'money', '💱': 'money', '🏦': 'money',
  '📈': 'stock', '🛡️': 'shield', '⚠️': 'warning', '🔒': 'lock', '🔐': 'lock', '⛔': 'warning',
  '📦': 'resource', '🤝': 'handshake', '🏢': 'building', '🏙️': 'building', '👥': 'people',
  '📜': 'document', '🧾': 'document', '📄': 'document', '📰': 'document', '📋': 'document',
  '🏥': 'hospital', '⏳': 'clock', '⏱️': 'clock', '🕒': 'clock', '🔄': 'refresh',
  '❌': 'closeCircle', '✅': 'check', '➕': 'plus', '⬅️': 'arrow-left', '➡️': 'arrow-right',
  '🎁': 'gift', '🪖': 'armor', '🗺️': 'land', '🧱': 'construction', '🏗️': 'construction',
  '👷': 'construction', '🚧': 'construction', '🚀': 'upgrade', '🗃️': 'resource', '🗂️': 'document',
  '🥇': 'medal', '🥈': 'medal', '🥉': 'medal', '✨': 'star', '⭐': 'star', '🎯': 'target',
  '🌐': 'globe', '☀️': 'sun', '🌙': 'sun', '☁️': 'cloud', '❄️': 'cloud', '🧊': 'cloud',
  '⚖️': 'scale', '⚪': 'status-dot', '🟢': 'status-dot', '🔴': 'status-dot', '💨': 'wind',
  '🚨': 'warning', '🛑': 'warning', '🚫': 'closeCircle', '⏸️': 'pause', '▶️': 'play', '▶': 'play',
  '⭕': 'status-dot', '🎭': 'people', '🏕️': 'construction', '👷': 'construction', '🛰️': 'technology',
  '🚁': 'logistics', '🚗': 'logistics', '💊': 'chemistry', '💠': 'resource', '🔋': 'battery',
  '🔍': 'search', '🟠': 'status-dot', '🔷': 'resource', '🪵': 'tree', '🪑': 'building',
  '🥛': 'agriculture', '🥩': 'agriculture', '🥫': 'agriculture', '🧰': 'repair', '🧴': 'chemistry',
  '🧱': 'construction', '🪙': 'coin', 'ℹ': 'info', '✈️': 'technology', '⚛️': 'technology',
  '📡': 'technology', '💣': 'warning', '📥': 'document', '📤': 'document', '🖐️': 'people',
});

const NORMALIZED_ICON_ALIASES = new Map(Object.entries(ICON_ALIASES)
  .map(([emoji, name]) => [emoji.replace(/\uFE0F/g, ''), name]));

export const ICON_NAMES = Object.freeze(Object.keys(ICON_PATHS));

function escapeAttribute(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]);
}

function clampSize(value) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.max(1, Math.min(96, Math.round(number))) : 20;
}

export function renderIcon(name, { size = 20, className = '', label = '' } = {}) {
  if (typeof name === 'string' && name.startsWith('item:')) {
    return renderResourceIcon(name.slice(5), { size, className, label });
  }
  const key = Object.hasOwn(ICON_PATHS, name) ? name : ICON_ALIASES[name];
  const path = ICON_PATHS[Object.hasOwn(ICON_PATHS, key) ? key : 'resource'];
  const safeClass = escapeAttribute(className);
  const title = label ? `<title>${escapeAttribute(label)}</title>` : '';
  const accessible = label
    ? `role="img" aria-label="${escapeAttribute(label)}"`
    : 'aria-hidden="true"';
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${clampSize(size)}" height="${clampSize(size)}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" class="${safeClass}" ${accessible}>${title}${path}</svg>`;
}

export function splitLegacyIcons(value) {
  const chars = Array.from(String(value ?? ''));
  const parts = [];
  let text = '';
  for (let index = 0; index < chars.length; index += 1) {
    if (chars[index - 1] === '\u200D' || chars[index + 1] === '\u200D') {
      text += chars[index];
      continue;
    }
    const withVariation = chars[index] + (chars[index + 1] === '\uFE0F' ? chars[index + 1] : '');
    const icon = NORMALIZED_ICON_ALIASES.get(withVariation.replace(/\uFE0F/g, ''));
    if (!icon) {
      text += chars[index];
      continue;
    }
    if (text) parts.push({ text, icon: null });
    parts.push({ text: '', icon });
    text = '';
    if (withVariation.length > chars[index].length) index += 1;
  }
  if (text || !parts.length) parts.push({ text, icon: null });
  return parts;
}

export const uiIcon = (name, size = 18) => renderIcon(name, { size, className: 'ui-icon' });

export function installIconHydration(doc = document, target = window) {
  function hydrateLegacyIcons(root) {
    if (!root || typeof doc.createTreeWalker !== 'function') return;
    const walker = doc.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        if (!node.nodeValue || !/\p{Extended_Pictographic}/u.test(node.nodeValue)) return NodeFilter.FILTER_REJECT;
        const parent = node.parentElement;
        if (!parent || parent.closest('script,style,textarea,input,select,option,svg,[data-preserve-emoji]')) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      },
    });
    const textNodes = [];
    while (walker.nextNode()) textNodes.push(walker.currentNode);
    for (const node of textNodes) {
      const parts = splitLegacyIcons(node.nodeValue);
      if (!parts.some((part) => part.icon)) continue;
      const fragment = doc.createDocumentFragment();
      for (const part of parts) {
        if (!part.icon) {
          fragment.append(doc.createTextNode(part.text));
          continue;
        }
        const wrapper = doc.createElement('span');
        wrapper.className = 'nat-legacy-icon';
        wrapper.setAttribute('aria-hidden', 'true');
        wrapper.innerHTML = uiIcon(part.icon, 14);
        fragment.append(wrapper);
      }
      node.replaceWith(fragment);
    }
  }

  target.NatIcons = Object.freeze({ renderIcon, icon: uiIcon, hydrateLegacyIcons });
  doc.querySelectorAll('[data-icon]').forEach((element) => {
    element.innerHTML = renderIcon(element.dataset.icon, { size: element.classList.contains('nav-icon') ? 22 : 18 });
  });
  hydrateLegacyIcons(doc.body);
  if (typeof MutationObserver !== 'undefined') {
    const iconObserver = new MutationObserver((records) => {
      for (const record of records) {
        if (record.type === 'characterData') {
          if (record.target.parentElement) hydrateLegacyIcons(record.target.parentElement);
          continue;
        }
        for (const node of record.addedNodes) {
          if (node.nodeType === Node.TEXT_NODE) hydrateLegacyIcons(node.parentElement);
          else if (node.nodeType === Node.ELEMENT_NODE) hydrateLegacyIcons(node);
        }
      }
    });
    ['#screen-container', '#toast-container', '#maintenance-banner-root', '#header-ticker']
      .map((selector) => doc.querySelector(selector))
      .filter(Boolean)
      .forEach((root) => iconObserver.observe(root, { childList: true, characterData: true, subtree: true }));
  }
  return hydrateLegacyIcons;
}
