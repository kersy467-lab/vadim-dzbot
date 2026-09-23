/**
 * Natbirzha Auth & Telegram Identity Helper
 * Resolves Telegram WebApp initData, user ID, or stable browser guest identity.
 */

const GUEST_ID_STORAGE_KEY = 'natbirzha_guest_id';
const TELEGRAM_INIT_DATA_STORAGE_KEY = 'natbirzha_telegram_init_data';
let inMemoryGuestId = '';

export function generateUUID() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function getTelegramInitData() {
  const tg = typeof window !== 'undefined' ? window.Telegram?.WebApp : null;
  if (tg?.initData && typeof tg.initData === 'string' && tg.initData.length > 0) {
    try {
      if (typeof sessionStorage !== 'undefined') sessionStorage.setItem(TELEGRAM_INIT_DATA_STORAGE_KEY, tg.initData);
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(TELEGRAM_INIT_DATA_STORAGE_KEY, tg.initData);
        localStorage.setItem('tg_init_data', tg.initData);
      }
    } catch (_) {}
    return tg.initData;
  }
  try {
    const searchParams = typeof window !== 'undefined' ? new URLSearchParams(window.location?.search || '') : null;
    const searchData = searchParams?.get('tgWebAppData');
    if (searchData && typeof searchData === 'string' && searchData.length > 0 && searchData.includes('hash=')) {
      try {
        if (typeof sessionStorage !== 'undefined') sessionStorage.setItem(TELEGRAM_INIT_DATA_STORAGE_KEY, searchData);
        if (typeof localStorage !== 'undefined') {
          localStorage.setItem(TELEGRAM_INIT_DATA_STORAGE_KEY, searchData);
          localStorage.setItem('tg_init_data', searchData);
        }
      } catch (_) {}
      return searchData;
    }
    const hash = typeof window !== 'undefined' ? window.location?.hash?.slice(1) : '';
    if (hash) {
      const hashParams = new URLSearchParams(hash);
      const hashData = hashParams.get('tgWebAppData');
      if (hashData && typeof hashData === 'string' && hashData.length > 0 && hashData.includes('hash=')) {
        try {
          if (typeof sessionStorage !== 'undefined') sessionStorage.setItem(TELEGRAM_INIT_DATA_STORAGE_KEY, hashData);
          if (typeof localStorage !== 'undefined') {
            localStorage.setItem(TELEGRAM_INIT_DATA_STORAGE_KEY, hashData);
            localStorage.setItem('tg_init_data', hashData);
          }
        } catch (_) {}
        return hashData;
      }
    }
  } catch (_) {}
  try {
    if (typeof sessionStorage !== 'undefined') {
      const carried = sessionStorage.getItem(TELEGRAM_INIT_DATA_STORAGE_KEY);
      if (carried && typeof carried === 'string' && carried.includes('hash=')) return carried;
    }
  } catch (_) {}
  try {
    if (typeof localStorage !== 'undefined') {
      const stored = localStorage.getItem(TELEGRAM_INIT_DATA_STORAGE_KEY) || localStorage.getItem('tg_init_data');
      if (stored && typeof stored === 'string' && stored.includes('hash=')) return stored;
    }
  } catch (_) {}
  return '';
}

export function clearStaleInitData() {
  const tg = typeof window !== 'undefined' ? window.Telegram?.WebApp : null;
  if (tg?.initData && tg.initData.length > 0) return;
  try {
    if (typeof sessionStorage !== 'undefined') {
      sessionStorage.removeItem(TELEGRAM_INIT_DATA_STORAGE_KEY);
    }
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem(TELEGRAM_INIT_DATA_STORAGE_KEY);
      localStorage.removeItem('tg_init_data');
    }
  } catch (_) {}
}

export function getTelegramUserId() {
  try {
    const u = window.Telegram?.WebApp?.initDataUnsafe?.user;
    if (u && u.id) {
      const sid = String(u.id);
      localStorage.setItem('cached_tg_uid', sid);
      return sid;
    }
  } catch (_) {}
  try {
    const sParams = new URLSearchParams(window.location?.search || '');
    const fromSearch = sParams.get('tg_user_id') || sParams.get('uid') || sParams.get('user_id');
    if (fromSearch) {
      localStorage.setItem('cached_tg_uid', String(fromSearch));
      return String(fromSearch);
    }
  } catch (_) {}
  try {
    const h = window.location?.hash || '';
    if (h) {
      const m = h.match(/(?:tg_user_id|uid|user_id)=([0-9]+)/);
      if (m && m[1]) {
        localStorage.setItem('cached_tg_uid', m[1]);
        return m[1];
      }
    }
  } catch (_) {}
  try {
    const cached = localStorage.getItem('cached_tg_uid');
    if (cached && /^[0-9]+$/.test(cached)) return cached;
  } catch (_) {}
  return null;
}

export function getAuthHeader() {
  const headers = {};
  const initData = getTelegramInitData();
  if (initData && typeof initData === 'string' && initData.length > 0) {
    headers['X-Telegram-Init-Data'] = initData;
  }

  const tgUid = getTelegramUserId();
  if (tgUid) {
    headers['X-Telegram-User-Id'] = tgUid;
  }

  if (!initData && !tgUid) {
    let guestId = inMemoryGuestId;
    try {
      const storage = typeof localStorage !== 'undefined' ? localStorage : sessionStorage;
      const stored = storage?.getItem(GUEST_ID_STORAGE_KEY);
      if (/^[A-Za-z0-9_-]{16,128}$/.test(stored || '')) guestId = stored;
      if (!guestId) {
        guestId = generateUUID();
        storage?.setItem(GUEST_ID_STORAGE_KEY, guestId);
      }
    } catch (_) {
      guestId = guestId || generateUUID();
    }
    inMemoryGuestId = guestId;
    headers['X-Natbirzha-Guest-Id'] = guestId;
  }
  return headers;
}
