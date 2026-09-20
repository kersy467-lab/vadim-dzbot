const API_BASE = "";

function getTelegramInitData() {
  if (window.Telegram?.WebApp?.initData) {
    return window.Telegram.WebApp.initData;
  }
  try {
    const hash = window.location.hash.slice(1);
    if (hash) {
      const params = new URLSearchParams(hash);
      const fromHash = params.get("tgWebAppData");
      if (fromHash) return fromHash;
    }
  } catch (e) {}
  return "";
}

function getTelegramUser() {
  if (window.Telegram?.WebApp?.initDataUnsafe?.user) {
    return window.Telegram.WebApp.initDataUnsafe.user;
  }
  try {
    const raw = getTelegramInitData();
    if (raw) {
      const params = new URLSearchParams(raw);
      const uStr = params.get("user");
      if (uStr) return JSON.parse(uStr);
    }
  } catch (e) {}
  return null;
}

function getTelegramUserId() {
  // 0. Admin Test Account override for bug hunting
  try {
    const adminOverride = localStorage.getItem("admin_test_tg_uid");
    if (adminOverride && /^[0-9]+$/.test(adminOverride)) {
      return String(adminOverride);
    }
  } catch (e) {}
  // 1. window.Telegram.WebApp.initDataUnsafe.user.id
  try {
    const tgUser = getTelegramUser();
    if (tgUser && tgUser.id) {
      const sid = String(tgUser.id);
      localStorage.setItem("cached_tg_uid", sid);
      return sid;
    }
  } catch (e) {}

  // 2. URL search parameters (?tg_user_id=, ?uid=, ?user_id=)
  try {
    const sParams = new URLSearchParams(window.location.search);
    const fromSearch = sParams.get("tg_user_id") || sParams.get("uid") || sParams.get("user_id");
    if (fromSearch) {
      localStorage.setItem("cached_tg_uid", String(fromSearch));
      return String(fromSearch);
    }
  } catch (e) {}

  // 3. URL hash parameters (#tg_user_id=, #uid=, or encoded in #tgWebAppData)
  try {
    const h = window.location.hash;
    if (h) {
      // Check direct param
      const mDirect = h.match(/(?:tg_user_id|uid|user_id)=([0-9]+)/);
      if (mDirect && mDirect[1]) {
        localStorage.setItem("cached_tg_uid", mDirect[1]);
        return mDirect[1];
      }
      // Check encoded user JSON in tgWebAppData
      const mJson = h.match(/(?:(?:%2522|%22|")id(?:%2522|%22|")\s*(?:%253A|%3A|:)\s*)([0-9]+)/);
      if (mJson && mJson[1]) {
        localStorage.setItem("cached_tg_uid", mJson[1]);
        return mJson[1];
      }
    }
  } catch (e) {}

  // 4. Cached from previous authenticated session
  try {
    const cached = localStorage.getItem("cached_tg_uid");
    if (cached && /^[0-9]+$/.test(cached)) return cached;
  } catch (e) {}

  return null;
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function apiRequestWithRetry(endpoint, options = {}, retries = 3, delayMs = 3000) {
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      return await apiRequest(endpoint, options);
    } catch (err) {
      const isLast = attempt === retries;
      // Не повторять 401/403 — это не сетевые ошибки
      if (err.status === 401 || err.status === 403 || isLast) throw err;
      console.warn(`[retry] attempt ${attempt}/${retries} failed for ${endpoint}, retrying in ${delayMs}ms...`, err.message);
      await sleep(delayMs);
    }
  }
}

async function apiRequest(endpoint, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {})
  };

  const tgUid = getTelegramUserId();
  if (tgUid) {
    headers["X-Telegram-User-Id"] = tgUid;
    // Also attach to query parameter for maximum reliability
    const sep = endpoint.includes("?") ? "&" : "?";
    if (!endpoint.includes("tg_user_id=")) {
      endpoint = `${endpoint}${sep}tg_user_id=${tgUid}`;
    }
  }

  // Safe initData: NEVER send raw non-ASCII strings in headers to avoid WHATWG Fetch crash
  try {
    const hasAdminOverride = !!localStorage.getItem("admin_test_tg_uid");
    const rawInit = getTelegramInitData();
    if (!hasAdminOverride && rawInit && /^[\x20-\x7E]*$/.test(rawInit)) {
      headers["X-Telegram-Init-Data"] = rawInit;
    }
  } catch (e) {}




  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers
    });

    if (!response.ok) {
      let errorDetail = "";
      try {
        const err = await response.json();
        errorDetail = err.detail || err.message || "";
      } catch (e) {}

      let errMsg = errorDetail;
      if (!errMsg) {
        if (response.status === 401 || response.status === 403) {
          errMsg = "Доступ запрещен или требуется авторизация";
        } else {
          errMsg = `Ошибка сервера: ${response.status}`;
        }
      }
      const errObj = new Error(errMsg);
      errObj.status = response.status;
      throw errObj;
    }

    return await response.json();
  } catch (error) {
    console.error(`API Error on ${endpoint}:`, error);
    throw error;
  }
}

const api = {
  getMe: () => apiRequestWithRetry("/api/me"),
  getStudents: () => apiRequest("/api/students"),
  getBells: () => apiRequest("/api/bells"),
  getSchedule: (dateStr) => apiRequest(`/api/schedule?target_date=${dateStr}`),
  getHomework: (dateStr) => apiRequest(`/api/homework?target_date=${dateStr}`),
  toggleHomework: (id) => apiRequest(`/api/homework/${id}/toggle`, { method: "POST" }),
  getDuty: () => apiRequest("/api/duty"),
  getDailyFact: () => apiRequest(`/api/facts/today?_t=${Date.now()}`),
  setUserId: (uid) => {
    if (uid) {
      localStorage.setItem("cached_tg_uid", String(uid));
    }
  },
  // Multiplayer Games
  getClassmates: () => apiRequest("/api/games/classmates"),
  createLocalGame: (gameType = "chess", hostName = "Игрок 1") =>
    apiRequest("/api/games/local", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        game_type: gameType,
        host_name: hostName
      })
    }),
  inviteGame: (opponentTgId, hostName, gameType = "tictactoe", hostColor = "white", opponentName = "", bossId = null, isSolo = false, heroData = null) =>
    apiRequest("/api/games/invite", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        opponent_tg_id: opponentTgId,
        host_name: hostName,
        opponent_name: opponentName,
        game_type: gameType,
        host_color: hostColor,
        boss_id: bossId,
        is_solo: isSolo,
        hero_data: heroData
      })
    }),
  getGameRoom: (roomId) => apiRequest(`/api/games/room/${roomId}`),
  joinGameRoom: (roomId, userName) =>
    apiRequest(`/api/games/room/${roomId}/join`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_name: userName })
    }),
  sendGameMove: (roomId, moveData) => {
    const payload = typeof moveData === "number" ? { cell: moveData } : { move: moveData };
    return apiRequest(`/api/games/room/${roomId}/move`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
  },
  addCoopBot: (roomId) =>
    apiRequest(`/api/games/room/${roomId}/bot`, {
      method: "POST"
    }),
  resignGame: (roomId) =>
    apiRequest(`/api/games/room/${roomId}/resign`, {
      method: "POST"
    }),
  rematchGame: (roomId) =>
    apiRequest(`/api/games/room/${roomId}/rematch`, {
      method: "POST"
    }),
  cancelGame: (roomId) =>
    apiRequest(`/api/games/room/${roomId}/cancel`, {
      method: "POST"
    }),
  // Dota 2 RPG Endpoints
  getRpgHeroes: () => apiRequest("/api/rpg/heroes"),
  getRpgProfile: () => apiRequest("/api/rpg/profile"),
  selectRpgHero: (heroClass) =>
    apiRequest("/api/rpg/class/select", {
      method: "POST",
      body: JSON.stringify({ hero_class: heroClass })
    }),
  upgradeRpgStat: (statName, extra = {}) => {
    const payload = (typeof extra === "object" && extra !== null)
      ? { stat: statName, ...extra }
      : { stat: statName, amount: extra };
    return apiRequest("/api/rpg/upgrade/stat", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },
  equipRpgItem: (itemUid, targetSlot) =>
    apiRequest("/api/rpg/inventory/equip", {
      method: "POST",
      body: JSON.stringify({ item_uid: itemUid, slot: targetSlot })
    }),
  unequipRpgItem: (slotOrUid) =>
    apiRequest("/api/rpg/inventory/unequip", {
      method: "POST",
      body: JSON.stringify({ slot: slotOrUid })
    }),
  useRpgItem: (itemUid) =>
    apiRequest("/api/rpg/inventory/use", {
      method: "POST",
      body: JSON.stringify({ item_uid: itemUid })
    }),
  doRebirth: () => apiRequest("/api/rpg/rebirth_system/ascend", { method: "POST" }),
  upgradeTalent: (talentId) => apiRequest("/api/rpg/talents/upgrade", {
    method: "POST",
    body: JSON.stringify({ talent_id: talentId })
  }),
  chooseDotaTalent: (tier, choice) => apiRequest("/api/rpg/talents/choose", {
    method: "POST",
    body: JSON.stringify({ tier, choice })
  }),
  getTalentTree: () => apiRequest("/api/rpg/talents/tree"),
  buyTalentNode: (nodeId) => apiRequest("/api/rpg/talents/tree/buy", {
    method: "POST",
    body: JSON.stringify({ node_id: nodeId })
  }),
  getRpgShop: () => apiRequest("/api/rpg/shop"),
  buyRpgShopItem: (itemId) =>
    apiRequest("/api/rpg/shop/buy", {
      method: "POST",
      body: JSON.stringify({ item_id: itemId })
    }),
  forgeRpgItem: (itemUid) =>
    apiRequest("/api/rpg/inventory/forge", {
      method: "POST",
      body: JSON.stringify({ item_uid: itemUid })
    }),
  hatchPetCrate: () =>
    apiRequest("/api/rpg/pets/hatch", {
      method: "POST",
      body: JSON.stringify({})
    }),
  equipPet: (petUid) =>
    apiRequest("/api/rpg/pets/equip", {
      method: "POST",
      body: JSON.stringify({ pet_uid: petUid })
    }),
  upgradePet: (petUid) =>
    apiRequest("/api/rpg/pets/upgrade", {
      method: "POST",
      body: JSON.stringify({ pet_uid: petUid })
    }),
  sellRpgItem: (itemUid) =>
    apiRequest("/api/rpg/inventory/sell", {
      method: "POST",
      body: JSON.stringify({ item_uid: itemUid })
    }),
  slashCreepWave: (payload = {}) =>
    apiRequest("/api/rpg/dungeon/wave", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  openRpgChest: (wave) =>
    apiRequest("/api/rpg/chest/open", {
      method: "POST",
      body: JSON.stringify({ wave: wave || 10 })
    }),
  getRpgLeaderboard: () => apiRequest("/api/rpg/leaderboard"),
  getCoopBosses: () => apiRequest("/api/rpg/bosses"),
  syncRpgRoom: (roomId) =>
    apiRequest(`/api/rpg/room/${roomId}/sync`, {
      method: "POST"
    }),
  sellMultipleRpgItems: (itemUids) =>
    apiRequest("/api/rpg/inventory/sell_multiple", {
      method: "POST",
      body: JSON.stringify({ item_uids: itemUids })
    }),
  resetRpgCharacter: () =>
    apiRequest("/api/rpg/reset", {
      method: "POST"
    }),
  getAdminRpgPlayers: () => apiRequest("/api/rpg/admin/players"),
  getAdminItemsCatalog: () => apiRequest("/api/rpg/admin/items_catalog"),
  adminGiveGold: (payload) =>
    apiRequest("/api/rpg/admin/give_gold", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  adminGiveGems: (payload) =>
    apiRequest("/api/rpg/admin/give_gems", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  adminSetLevel: (payload) =>
    apiRequest("/api/rpg/admin/set_level", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  adminGiveItem: (payload) =>
    apiRequest("/api/rpg/admin/give_item", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  adminResetPlayer: (payload) =>
    apiRequest("/api/rpg/admin/reset_player", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  request: apiRequest
};

window.api = api;



