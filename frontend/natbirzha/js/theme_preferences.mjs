const STORAGE_KEY = 'natbirzha-theme';

export const DEFAULT_THEME = 'ivory';
export const THEMES = Object.freeze([
  Object.freeze({ id: 'ivory', label: 'Айвори и шалфей', scheme: 'light' }),
  Object.freeze({ id: 'midnight', label: 'Ночная биржа', scheme: 'dark' }),
  Object.freeze({ id: 'pearl', label: 'Жемчуг и сталь', scheme: 'light' }),
]);

const THEME_IDS = new Set(THEMES.map(({ id }) => id));

export function normalizeThemeId(value) {
  const id = String(value ?? '').trim().toLowerCase();
  return THEME_IDS.has(id) ? id : DEFAULT_THEME;
}

function safeStorage(storage) {
  if (storage) return storage;
  try { return globalThis.localStorage; } catch (_) { return null; }
}

export function readThemePreference(storage) {
  try {
    return normalizeThemeId(safeStorage(storage)?.getItem(STORAGE_KEY));
  } catch (_) {
    return DEFAULT_THEME;
  }
}

export function writeThemePreference(value, storage) {
  const id = normalizeThemeId(value);
  try { safeStorage(storage)?.setItem(STORAGE_KEY, id); } catch (_) {}
  return id;
}

export function applyTheme(root, value) {
  const id = normalizeThemeId(value);
  if (!root) return id;
  const theme = THEMES.find(({ id: candidate }) => candidate === id);
  if (root.dataset) root.dataset.theme = id;
  else root.setAttribute?.('data-theme', id);
  if (root.style) root.style.colorScheme = theme?.scheme || 'light';
  return id;
}

export function initThemePicker({ documentRef, storage } = {}) {
  let doc = documentRef;
  if (!doc) {
    try { doc = globalThis.document; } catch (_) { return DEFAULT_THEME; }
  }
  if (!doc?.documentElement) return DEFAULT_THEME;

  const selected = readThemePreference(storage);
  applyTheme(doc.documentElement, selected);
  const picker = doc.getElementById?.('theme-select');
  if (picker) {
    picker.value = selected;
    picker.addEventListener('change', () => {
      const next = writeThemePreference(picker.value, storage);
      picker.value = next;
      applyTheme(doc.documentElement, next);
    });
  }
  return selected;
}

if (typeof document !== 'undefined') initThemePicker();
