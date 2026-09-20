const RPG_ASSETS = {
  heroes: {},
  bosses: {}
};

function loadRpgImages() {
  const heroNames = ["pudge", "juggernaut", "shadow_fiend", "leshrac", "phantom_assassin", "invoker", "wraith_king", "anti_mage"];
  for (const name of heroNames) {
    const img = new Image();
    img.src = `/static/images/heroes/${name}.png`;
    RPG_ASSETS.heroes[name] = img;
  }
  const bossNames = ["faceless_void", "terrorblade", "roshan", "butcher", "shadow_lord"];
  for (const name of bossNames) {
    const img = new Image();
    img.src = `/static/images/bosses/${name}.png`;
    RPG_ASSETS.bosses[name] = img;
  }
}
loadRpgImages();

/**
 * natarGRP — Action RPG Engine & UI for 11 «Б» Mini App
 * Features:
 *  - 7 Hero Archetypes with Primary Attribute Bonus (+1 Damage per point)
 *  - 3-Attribute System: Сила (HP, HP-regen), Ловкость (Atk-speed, Armor, Crit/Dodge), Интеллект (Mana, MP-regen, Magic Resist)
 *  - Interactive 2D Action Arena on <canvas> with Virtual Joystick, WASD controls, manual/auto-cleave, ultimate skills
 *  - Swarming creeps, damage numbers, and vacuum loot pickups (gold coins & XP gems)
 *  - Floor Bosses & Reward Chests every 10-20 waves with functional items
 *  - Labeled Gear: Slot badges (Оружие/Броня/Реликвия/Зелье), Rarity badges, and clear stat previews
 *  - Secret Shop Forge (+1..+99) & Item Market
 *  - Co-op Boss Raids & 1v1 PvP Duels
 *  - Class Leaderboard
 */

(function () {
  // Safe roundRect polyfill for mobile WebViews (Telegram on Android/iOS)
  if (typeof CanvasRenderingContext2D !== "undefined" && !CanvasRenderingContext2D.prototype.roundRect) {
    CanvasRenderingContext2D.prototype.roundRect = function (x, y, w, h, radii) {
      const r = Math.min((typeof radii === "number" ? radii : 12), w / 2, h / 2);
      this.beginPath();
      this.moveTo(x + r, y);
      this.lineTo(x + w - r, y);
      this.arcTo(x + w, y, x + w, y + r, r);
      this.lineTo(x + w, y + h - r);
      this.arcTo(x + w, y + h, x + w - r, y + h, r);
      this.lineTo(x + r, y + h);
      this.arcTo(x, y + h, x, y + h - r, r);
      this.lineTo(x, y + r);
      this.arcTo(x, y, x + r, y, r);
      this.closePath();
      return this;
    };
  }

  function safeRoundRect(ctx, x, y, w, h, r) {
    const rad = Math.min(r || 12, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + rad, y);
    ctx.lineTo(x + w - rad, y);
    ctx.arcTo(x + w, y, x + w, y + rad, rad);
    ctx.lineTo(x + w, y + h - rad);
    ctx.arcTo(x + w, y + h, x + w - rad, y + h, rad);
    ctx.lineTo(x + rad, y + h);
    ctx.arcTo(x, y + h, x, y + h - rad, rad);
    ctx.lineTo(x, y + rad);
    ctx.arcTo(x, y, x + rad, y, rad);
    ctx.closePath();
  }

  function formatCompact(num) {
    if (num == null || isNaN(num)) return "0";
    const n = Math.abs(num);
    if (n >= 1_000_000_000_000_000) return (num / 1_000_000_000_000_000).toFixed(1) + "Q";
    if (n >= 1_000_000_000_000) return (num / 1_000_000_000_000).toFixed(1) + "T";
    if (n >= 1_000_000_000) return (num / 1_000_000_000).toFixed(1) + "B";
    if (n >= 1_000_000) return (num / 1_000_000).toFixed(1) + "M";
    if (n >= 10_000) return (num / 1_000).toFixed(1) + "k";
    return num.toLocaleString ? num.toLocaleString("ru-RU") : String(num);
  }

  const RPG_STATE = {
    profile: null,
    heroesList: [],
    activeTab: "farm", // 'farm', 'hero', 'chests', 'coop', 'pvp', 'leaderboard'
    loading: false,
    errorMessage: null,
    
    // Farm Mode: 'arena' (Active 2D Combat) or 'sim' (Fast Sim / Auto)
    farmMode: "arena",
    autoFarm: false,
    autoFarmTimer: null,
    isFighting: false,
    lastBattle: null,
    combatLog: [],
    killsSession: 0,
    
    // Chest Rewards
    activeChestModal: null, // { chest_name, chest_icon, tier, gold_reward, gems_reward, item, opened: bool }
    
    // Co-op Bosses
    coopBosses: [],
    selectedBoss: "roshan",
    coopRoomId: null,
    coopRoomData: null,
    coopPolling: null,
    
    // PvP Duels
    pvpRoomId: null,
    pvpRoomData: null,
    pvpPolling: null,
    classmates: [],
    classmatesSearch: "",
    
    // Leaderboard
    leaderboard: [],
    
    // Modals
    inspectedItem: null,
    selectedItemUids: new Set(),
    isSelectionMode: false,
    forgeItem: null,
    forgeSuccessAnimation: false,
    levelUpNotification: null,
    shopModalOpen: false,
    shopLoading: false,
    shopCatalog: [],
    shopFilter: "all",
    buyingItemId: null,
    slotFilterModal: null,
    adminModalOpen: false,
    adminTestSlots: [
      { id: "main", name: "👑 Основной (Админ)", tg_id: null },
      { id: "999001", name: "🧪 Тест #1 (Чистый старт 1 ур.)", tg_id: "999001" },
      { id: "999002", name: "🧪 Тест #2 (Чистый старт 1 ур.)", tg_id: "999002" },
      { id: "999003", name: "🧪 Тест #3 (Песочница)", tg_id: "999003" },
      { id: "999004", name: "🧪 Тест #4 (Песочница)", tg_id: "999004" }
    ]
  };

  const RARITY_MAP = {
    common: { name: "Обычный", color: "border-slate-400 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300", badge: "bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300" },
    uncommon: { name: "Необычный", color: "border-emerald-500 bg-emerald-50/70 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300", badge: "bg-emerald-500/15 text-emerald-600 border border-emerald-500/30" },
    rare: { name: "Редкий", color: "border-sky-500 bg-sky-50/70 dark:bg-sky-950/40 text-sky-700 dark:text-sky-300", badge: "bg-sky-500/10 text-sky-600 border border-sky-500/20" },
    epic: { name: "Эпический", color: "border-purple-500 bg-purple-50/70 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300", badge: "bg-purple-500/10 text-purple-600 border border-purple-500/20" },
    legendary: { name: "Легендарный", color: "border-amber-500 bg-amber-50/70 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300", badge: "bg-amber-500/20 text-amber-600 font-extrabold border border-amber-500/40 shadow-sm" },
    immortal: { name: "Бессмертный", color: "border-orange-500 bg-orange-50/80 dark:bg-orange-950/50 text-orange-700 dark:text-orange-300", badge: "bg-orange-600 text-white font-black shadow-md shadow-orange-600/30" }
  };

  const FALLBACK_SHOP_CATALOG = [
  {
    "id": "shop_w_guard_sword",
    "name": "Меч Стража Катакомб",
    "icon": "🗡️",
    "type": "weapon",
    "slot": "weapon",
    "slot_name": "Оружие",
    "slot_icon": "⚔️",
    "rarity": "common",
    "price_gold": 150,
    "price_gems": 0,
    "base_min": 16,
    "base_max": 24,
    "bonus": {
      "atk": 5
    },
    "bonus_desc": "⚔️ +16..24 Урон | 🗡️ +5 Атака"
  },
  {
    "id": "shop_w_shadow_blades",
    "name": "Клинки Теней",
    "icon": "🗡️",
    "type": "weapon",
    "slot": "weapon",
    "slot_name": "Оружие",
    "slot_icon": "⚔️",
    "rarity": "rare",
    "price_gold": 450,
    "price_gems": 0,
    "base_min": 26,
    "base_max": 38,
    "bonus": {
      "crit": 20
    },
    "bonus_desc": "⚔️ +26..38 Урон | 💥 +20% Крит"
  },
  {
    "id": "shop_w_harpoon",
    "name": "Гарпун Катакомб",
    "icon": "🔱",
    "type": "weapon",
    "slot": "weapon",
    "slot_name": "Оружие",
    "slot_icon": "⚔️",
    "rarity": "rare",
    "price_gold": 550,
    "price_gems": 0,
    "base_min": 32,
    "base_max": 48,
    "bonus": {
      "double_hit": 25,
      "str": 12
    },
    "bonus_desc": "⚔️ +32..48 Урон | 🥩 +12 Сила"
  },
  {
    "id": "shop_w_storm_axe",
    "name": "Секира Бури",
    "icon": "🪓",
    "type": "weapon",
    "slot": "weapon",
    "slot_name": "Оружие",
    "slot_icon": "⚔️",
    "rarity": "epic",
    "price_gold": 1200,
    "price_gems": 0,
    "base_min": 42,
    "base_max": 60,
    "bonus": {
      "cleave": 40,
      "hp_regen": 8
    },
    "bonus_desc": "⚔️ +42..60 Урон | 🌪️ Сплэш 40% | 🩹 +8 HP/сек"
  },
  {
    "id": "shop_w_blood_reaper",
    "name": "Кровавый Жнец",
    "icon": "🔴",
    "type": "weapon",
    "slot": "weapon",
    "slot_name": "Оружие",
    "slot_icon": "⚔️",
    "rarity": "epic",
    "price_gold": 1400,
    "price_gems": 0,
    "base_min": 45,
    "base_max": 65,
    "bonus": {
      "armor_pierce": 15
    },
    "bonus_desc": "⚔️ +45..65 Урон | 🩸 -15 Брони врага"
  },
  {
    "id": "shop_w_thunder_hammer",
    "name": "Громовой Молот",
    "icon": "⚡",
    "type": "weapon",
    "slot": "weapon",
    "slot_name": "Оружие",
    "slot_icon": "⚔️",
    "rarity": "legendary",
    "price_gold": 2800,
    "price_gems": 25,
    "base_min": 44,
    "base_max": 64,
    "bonus": {
      "lightning": 45
    },
    "bonus_desc": "⚔️ +44..64 Урон | ⚡ Цепная молния"
  },
  {
    "id": "shop_a_forged_cuirass",
    "name": "Кованый Панцирь",
    "icon": "🛡️",
    "type": "armor",
    "slot": "armor",
    "slot_name": "Броня",
    "slot_icon": "🛡️",
    "rarity": "common",
    "price_gold": 140,
    "price_gems": 0,
    "base_def": 10,
    "base_hp": 40,
    "bonus": {},
    "bonus_desc": "🛡️ +10 Броня | ❤️ +40 HP"
  },
  {
    "id": "shop_a_spiked_armor",
    "name": "Шипастый Доспех",
    "icon": "🦔",
    "type": "armor",
    "slot": "armor",
    "slot_name": "Броня",
    "slot_icon": "🛡️",
    "rarity": "rare",
    "price_gold": 480,
    "price_gems": 0,
    "base_def": 14,
    "base_hp": 70,
    "bonus": {
      "reflect": 35,
      "atk": 10
    },
    "bonus_desc": "🛡️ +14 Броня | ❤️ +70 HP | 🦔 Отражение 35%"
  },
  {
    "id": "shop_a_golden_avatar",
    "name": "Золотой Аватар",
    "icon": "🟡",
    "type": "armor",
    "slot": "armor",
    "slot_name": "Броня",
    "slot_icon": "🛡️",
    "rarity": "epic",
    "price_gold": 1100,
    "price_gems": 0,
    "base_def": 18,
    "base_hp": 160,
    "bonus": {
      "magic_resist": 35,
      "str": 10
    },
    "bonus_desc": "🛡️ +18 Броня | ❤️ +160 HP | 🔮 +35% Защита от магии"
  },
  {
    "id": "shop_a_crimson_guard",
    "name": "Багровый Оплот",
    "icon": "🛡️",
    "type": "armor",
    "slot": "armor",
    "slot_name": "Броня",
    "slot_icon": "🛡️",
    "rarity": "epic",
    "price_gold": 1350,
    "price_gems": 0,
    "base_def": 22,
    "base_hp": 170,
    "bonus": {
      "block": 35
    },
    "bonus_desc": "🛡️ +22 Броня | ❤️ +170 HP | 🛡️ Блок 35 урона"
  },
  {
    "id": "shop_a_assault_cuirass",
    "name": "Кираса Штурма",
    "icon": "🛡️",
    "type": "armor",
    "slot": "armor",
    "slot_name": "Броня",
    "slot_icon": "🛡️",
    "rarity": "legendary",
    "price_gold": 2700,
    "price_gems": 25,
    "base_def": 28,
    "base_hp": 130,
    "bonus": {
      "atk_speed": 30,
      "aura_armor": 6
    },
    "bonus_desc": "🛡️ +28 Броня | ❤️ +130 HP | ⚡ +30% Скор. атаки"
  },
  {
    "id": "shop_r_energy_talisman",
    "name": "Талисман Энергии",
    "icon": "🌿",
    "type": "relic",
    "slot": "relic",
    "slot_name": "Реликвия",
    "slot_icon": "💍",
    "rarity": "common",
    "price_gold": 120,
    "price_gems": 0,
    "bonus": {
      "hp": 50,
      "mp": 40
    },
    "bonus_desc": "❤️ +50 HP | 🔮 +40 MP"
  },
  {
    "id": "shop_r_blink_dagger",
    "name": "Кинжал Мерцания",
    "icon": "🗡️",
    "type": "relic",
    "slot": "relic",
    "slot_name": "Реликвия",
    "slot_icon": "💍",
    "rarity": "rare",
    "price_gold": 500,
    "price_gems": 0,
    "bonus": {
      "crit": 15,
      "dodge": 15
    },
    "bonus_desc": "💥 +15% Крит | 💨 +15% Уворот"
  },
  {
    "id": "shop_r_eye_skadi",
    "name": "Око Вечной Мерзлоты",
    "icon": "❄️",
    "type": "relic",
    "slot": "relic",
    "slot_name": "Реликвия",
    "slot_icon": "💍",
    "rarity": "legendary",
    "price_gold": 2500,
    "price_gems": 20,
    "bonus": {
      "hp": 160,
      "mp": 100,
      "atk": 25,
      "slow": 30
    },
    "bonus_desc": "❤️ +160 HP | 🔮 +100 MP | ⚔️ +25 Урон | ❄️ Заморозка"
  },
  {
    "id": "shop_w_daedalus",
    "name": "Даэдалус (Daedalus)",
    "icon": "🏹",
    "type": "weapon",
    "slot": "weapon",
    "slot_name": "Оружие",
    "slot_icon": "⚔️",
    "rarity": "immortal",
    "price_gold": 4300,
    "price_gems": 14,
    "base_min": 85,
    "base_max": 125,
    "bonus": {
      "crit": 30,
      "crit_mult": 2.5
    },
    "bonus_desc": "⚔️ +85..125 Урон | 💥 30% Шанс крита 250%"
  },
  {
    "id": "shop_w_radiance",
    "name": "Сияние (Radiance)",
    "icon": "☀️",
    "type": "weapon",
    "slot": "weapon",
    "slot_name": "Оружие",
    "slot_icon": "⚔️",
    "rarity": "immortal",
    "price_gold": 4800,
    "price_gems": 18,
    "base_min": 70,
    "base_max": 95,
    "bonus": {
      "radiance_burn": 65,
      "miss_aura": 17
    },
    "bonus_desc": "⚔️ +70..95 Урон | 🔥 Аура: 65 маг. урона/сек | 💨 17% Промах врагов/босса"
  },
  {
    "id": "shop_a_tarasque",
    "name": "Сердце Тарраска (Heart of Tarrasque)",
    "icon": "❤️",
    "type": "armor",
    "slot": "armor",
    "slot_name": "Броня",
    "slot_icon": "🛡️",
    "rarity": "immortal",
    "price_gold": 4500,
    "price_gems": 15,
    "base_def": 25,
    "base_hp": 900,
    "bonus": {
      "str": 45,
      "pct_hp_regen": 2.5
    },
    "bonus_desc": "🛡️ +25 Броня | ❤️ +900 HP | 🥩 +45 Сила | 💖 +2.5% Макс. HP/сек в бою"
  },
  {
    "id": "shop_r_satanic",
    "name": "Сатаник (Satanic)",
    "icon": "🩸",
    "type": "relic",
    "slot": "relic",
    "slot_name": "Реликвия",
    "slot_icon": "💍",
    "rarity": "immortal",
    "price_gold": 4200,
    "price_gems": 18,
    "bonus": {
      "str": 35,
      "hp": 500,
      "lifesteal": 30
    },
    "bonus_desc": "🥩 +35 Сила | ❤️ +500 HP | 🧛 +30% Вампиризм ото всех атак"
  },
  {
    "id": "shop_a_assault_cuirass",
    "name": "Кираса Штурма (Assault Cuirass)",
    "icon": "🛡️",
    "type": "armor",
    "slot": "armor",
    "slot_name": "Броня",
    "slot_icon": "🛡️",
    "rarity": "immortal",
    "price_gold": 4600,
    "price_gems": 16,
    "base_def": 28,
    "base_hp": 300,
    "bonus": {
      "atk_speed": 35,
      "aura_armor": 10,
      "minus_armor_aura": 10
    },
    "bonus_desc": "🛡️ +28 Броня | ⚡ +35% Скор. атаки | 🛡️ Аура: +10 брони герою, -10 брони врагам/боссу"
  },
  {
    "id": "shop_w_butterfly",
    "name": "Бабочка (Butterfly)",
    "icon": "🦋",
    "type": "weapon",
    "slot": "weapon",
    "slot_name": "Оружие",
    "slot_icon": "⚔️",
    "rarity": "immortal",
    "price_gold": 4700,
    "price_gems": 16,
    "base_min": 60,
    "base_max": 85,
    "bonus": {
      "agi": 35,
      "dodge": 35,
      "atk_speed": 35
    },
    "bonus_desc": "⚔️ +60..85 Урон | 🏃 +35 Ловкость | 💨 +35% Уворот от босса и крипов | ⚡ +35% Скорость"
  },
  {
    "id": "shop_w_mkb",
    "name": "Посох Короля Обезьян (MKB)",
    "icon": "🥢",
    "type": "weapon",
    "slot": "weapon",
    "slot_name": "Оружие",
    "slot_icon": "⚔️",
    "rarity": "immortal",
    "price_gold": 4400,
    "price_gems": 14,
    "base_min": 65,
    "base_max": 90,
    "bonus": {
      "atk_speed": 35,
      "true_strike": 1,
      "pure_proc": 120
    },
    "bonus_desc": "⚔️ +65..90 Урон | ⚡ +35% Скорость | 🎯 True Strike (без промахов) | 💥 75% шанс на +120 чистого урона"
  },
  {
    "id": "shop_w_mjollnir",
    "name": "Мьёльнир (Mjollnir)",
    "icon": "⚡",
    "type": "weapon",
    "slot": "weapon",
    "slot_name": "Оружие",
    "slot_icon": "⚔️",
    "rarity": "immortal",
    "price_gold": 4600,
    "price_gems": 16,
    "base_min": 65,
    "base_max": 90,
    "bonus": {
      "atk_speed": 40,
      "lightning_proc": 220
    },
    "bonus_desc": "⚔️ +65..90 Урон | ⚡ +40% Скор. атаки | ⚡ 25% Шанс цепной молнии на 220 урона"
  },
  {
    "id": "shop_w_desolator",
    "name": "Опустошитель (Desolator)",
    "icon": "🩸",
    "type": "weapon",
    "slot": "weapon",
    "slot_name": "Оружие",
    "slot_icon": "⚔️",
    "rarity": "legendary",
    "price_gold": 3500,
    "price_gems": 8,
    "base_min": 65,
    "base_max": 90,
    "bonus": {
      "minus_armor": 10
    },
    "bonus_desc": "⚔️ +65..90 Урон | 🩸 Коррозия: -10 брони врагам и боссу при ударе"
  },
  {
    "id": "shop_r_skadi",
    "name": "Око Скади (Eye of Skadi)",
    "icon": "❄️",
    "type": "relic",
    "slot": "relic",
    "slot_name": "Реликвия",
    "slot_icon": "💍",
    "rarity": "immortal",
    "price_gold": 4600,
    "price_gems": 15,
    "bonus": {
      "all_stats": 30,
      "hp": 600,
      "mp": 600,
      "frost_slow": 40
    },
    "bonus_desc": "🌟 +30 Все характеристики | ❤️ +600 HP | 💧 +600 MP | ❄️ Ледяной удар: -40% скорости бега и атак босса"
  },
  {
    "id": "shop_a_blademail",
    "name": "Шипастый Доспех (Blade Mail)",
    "icon": "🛡️",
    "type": "armor",
    "slot": "armor",
    "slot_name": "Броня",
    "slot_icon": "🛡️",
    "rarity": "rare",
    "price_gold": 1800,
    "price_gems": 0,
    "base_def": 18,
    "base_hp": 250,
    "bonus": {
      "atk": 25,
      "reflect": 35
    },
    "bonus_desc": "🛡️ +18 Броня | ❤️ +250 HP | ⚔️ +25 Урон | 🪞 Возвратка 35% входящего урона обратно боссу/крипам"
  },
  {
    "id": "shop_a_vanguard",
    "name": "Авангард (Vanguard)",
    "icon": "🛡️",
    "type": "armor",
    "slot": "armor",
    "slot_name": "Броня",
    "slot_icon": "🛡️",
    "rarity": "rare",
    "price_gold": 1900,
    "price_gems": 0,
    "base_def": 14,
    "base_hp": 400,
    "bonus": {
      "hp_regen": 8,
      "damage_block": 80
    },
    "bonus_desc": "🛡️ +14 Броня | ❤️ +400 HP | 🩹 +8 HP/сек | 🛡️ 70% Шанс заблокировать 80 урона от ударов"
  },
  {
    "id": "shop_r_moon_shard",
    "name": "Осколок Луны (Moon Shard)",
    "icon": "🌙",
    "type": "relic",
    "slot": "relic",
    "slot_name": "Реликвия",
    "slot_icon": "💍",
    "rarity": "legendary",
    "price_gold": 3800,
    "price_gems": 12,
    "bonus": {
      "atk_speed": 60
    },
    "bonus_desc": "⚡ +60% Скорость атаки | 🌙 Ночной обзор"
  },
  {
    "id": "shop_r_octarine",
    "name": "Октариновое Ядро (Octarine Core)",
    "icon": "💎",
    "type": "relic",
    "slot": "relic",
    "slot_name": "Реликвия",
    "slot_icon": "💍",
    "rarity": "immortal",
    "price_gold": 4300,
    "price_gems": 18,
    "bonus": {
      "hp": 500,
      "mp": 700,
      "cooldown_reduct": 25,
      "spell_lifesteal": 25
    },
    "bonus_desc": "❤️ +500 HP | 💧 +700 MP | ⏱️ -25% КД скиллов | 🩸 25% Вампиризм от заклинаний"
  },
  {
    "id": "shop_w_khanda",
    "name": "Кханда (Khanda)",
    "icon": "🗡️",
    "type": "weapon",
    "slot": "weapon",
    "slot_name": "Оружие",
    "slot_icon": "⚔️",
    "rarity": "immortal",
    "price_gold": 4500,
    "price_gems": 15,
    "base_min": 60,
    "base_max": 85,
    "bonus": {
      "hp": 350,
      "mp": 300,
      "crit": 20,
      "empower_spell": 150
    },
    "bonus_desc": "⚔️ +60..85 Урон | ❤️ +350 HP | 💧 +300 MP | 💥 Скиллы наносят +150 критического физ. урона"
  },
  {
    "id": "shop_w_rapier",
    "name": "Божественная Рапира (Divine Rapier)",
    "icon": "🗡️",
    "type": "weapon",
    "slot": "weapon",
    "slot_name": "Оружие",
    "slot_icon": "⚔️",
    "rarity": "immortal",
    "price_gold": 9000,
    "price_gems": 40,
    "base_min": 500,
    "base_max": 650,
    "bonus": {
      "true_strike": 1
    },
    "bonus_desc": "⚔️ +500..650 Колоссальный урон | 🎯 True Strike — абсолютное оружие богов"
  },
  {
    "id": "shop_p_healing",
    "name": "Зелье Исцеления",
    "icon": "🧴",
    "type": "potion",
    "slot": "consumable",
    "slot_name": "Зелье",
    "slot_icon": "🧪",
    "rarity": "common",
    "price_gold": 50,
    "price_gems": 0,
    "heal_amount": 120,
    "count": 3,
    "bonus_desc": "❤️ Восстанавливает 120 HP (3 шт.)"
  },
  {
    "id": "shop_p_mana",
    "name": "Эликсир Маны",
    "icon": "🧪",
    "type": "potion",
    "slot": "consumable",
    "slot_name": "Зелье",
    "slot_icon": "🧪",
    "rarity": "common",
    "price_gold": 40,
    "price_gems": 0,
    "mp_amount": 100,
    "count": 3,
    "bonus_desc": "🔮 Восстанавливает 100 MP (3 шт.)"
  },
  {
    "id": "shop_p_cheese",
    "name": "Сыр Силы Катакомб",
    "icon": "🧀",
    "type": "potion",
    "slot": "consumable",
    "slot_name": "Зелье",
    "slot_icon": "🧪",
    "rarity": "immortal",
    "price_gold": 400,
    "price_gems": 5,
    "heal_amount": 500,
    "mp_amount": 350,
    "count": 1,
    "bonus_desc": "👑 Восстанавливает 500 HP и 350 MP!"
  }
];


  function triggerHaptic(type = "light") {
    if (window.Telegram?.WebApp?.HapticFeedback) {
      if (type === "success" || type === "warning" || type === "error") {
        window.Telegram.WebApp.HapticFeedback.notificationOccurred(type);
      } else {
        window.Telegram.WebApp.HapticFeedback.impactOccurred(type);
      }
    }
  }

  // ===========================================================================
  // INITIALIZATION & PROFILE
  // ===========================================================================

  async function initRPG() {
    try {
      RPG_STATE.loading = true;
      renderRoot();

      const [prof, heroes, shop] = await Promise.all([
        api.getRpgProfile().catch(() => null),
        api.getRpgHeroes().catch(() => []),
        api.getRpgShop().catch(() => null)
      ]);

      RPG_STATE.profile = prof;
      RPG_STATE.heroesList = heroes || [];
      if (Array.isArray(shop) && shop.length > 0) {
        RPG_STATE.shopCatalog = shop;
      } else if (!RPG_STATE.shopCatalog || RPG_STATE.shopCatalog.length === 0) {
        RPG_STATE.shopCatalog = [...FALLBACK_SHOP_CATALOG];
      }

      if (!prof || !prof.hero_class) {
        RPG_STATE.activeTab = "hero";
      }
    } catch (err) {
      console.error("Failed to init natarGRP:", err);
      RPG_STATE.errorMessage = err.message || "Ошибка загрузки natarGRP";
    } finally {
      RPG_STATE.loading = false;
      renderRoot();
      if (RPG_STATE.activeTab === "farm" && RPG_STATE.farmMode === "arena") {
        startArenaLoop();
      }
    }
  }

  async function loadProfile() {
    try {
      const prof = await api.getRpgProfile();
      RPG_STATE.profile = prof;
      renderRoot();
    } catch (e) {
      console.error("Error refreshing profile:", e);
    }
  }

  function setSubTab(tab) {
    if (RPG_STATE.activeTab === "farm" && tab !== "farm") {
      stopArenaLoop();
      if (RPG_STATE.autoFarm) toggleAutoFarm(false);
    }
    RPG_STATE.activeTab = tab;
    RPG_STATE.inspectedItem = null;
    RPG_STATE.forgeItem = null;

    if (tab === "coop") {
      loadCoopBosses();
    } else if (tab === "pvp") {
      stopArenaLoop();
      if (RPG_STATE.autoFarm) toggleAutoFarm(false);
      ARENA.player.autoAttack = false;
      loadClassmates();
    } else if (tab === "leaderboard") {
      loadLeaderboard();
    }
    renderRoot();

    if (tab === "farm" && RPG_STATE.farmMode === "arena") {
      startArenaLoop();
    }
  }

  function setFarmMode(mode) {
    RPG_STATE.farmMode = mode;
    if (mode === "arena") {
      // Cleanly reset boss and arena states when entering farm arena
      ARENA.isRaidBossBattle = false;
      ARENA.topDownMode = false;
      ARENA.isBossActive = false;
      ARENA.bossEntity = null;
      ARENA.bossArenaMode = false;
      if (ARENA.player) {
        ARENA.player.x = 65;
        ARENA.player.y = ARENA.roadY - 18;
        ARENA.player.isInvulnerable = 0;
        const stats = RPG_STATE.profile?.stats || {};
        ARENA.player.maxHp = Math.max(450, stats.hp_max || 450);
        ARENA.player.currentHp = Math.max(1, ARENA.player.currentHp || ARENA.player.maxHp);
      }

      const currentSavedWave = ((RPG_STATE.profile?.dungeon_cleared || 0) % 20) + 1;
      ARENA.waveNumber = currentSavedWave;
      ARENA.creepsNeededForWave = Math.min(32, 14 + Math.floor((ARENA.waveNumber - 1) * 1.0));
      ARENA.creepsKilledInWave = 0;
      ARENA.totalCreepsSpawned = 0;
      ARENA.creeps = [];

      if (ARENA.waveNumber === 20) {
        ARENA.waveState = "boss_intro";
        ARENA.waveTransitionTimer = 60;
        ARENA.bossArenaMode = true;
        spawnBossCreep();
      } else {
        ARENA.waveState = "fighting";
      }

      RPG_STATE._forceFullRender = true;
      renderRoot();
      RPG_STATE._forceFullRender = false;
      startArenaLoop();
    } else {
      stopArenaLoop();
      ARENA.isBossActive = false;
      ARENA.topDownMode = false;
      ARENA.bossArenaMode = false;
      ARENA.bossEntity = null;
      ARENA.isRaidBossBattle = false;
      renderRoot();
    }
  }

  // ===========================================================================
  // ADMIN DEV PANEL & TEST ACCOUNT SWITCHER (Admin only: 1053722876)
  // ===========================================================================

  function isUserAdmin() {
    if (localStorage.getItem("admin_test_tg_uid")) return true;
    if (localStorage.getItem("is_admin_verified") === "true") return true;
    const p = RPG_STATE.profile;
    if (p && (p.is_admin || String(p.tg_id) === "1053722876" || String(p.user_id) === "1053722876")) {
      localStorage.setItem("is_admin_verified", "true");
      return true;
    }
    return false;
  }

  function toggleAdminModal(open) {
    triggerHaptic("light");
    RPG_STATE.adminModalOpen = (open !== undefined) ? open : !RPG_STATE.adminModalOpen;
    if (RPG_STATE.adminModalOpen && window.RPG) {
      if (window.RPG.refreshAdminPlayers) window.RPG.refreshAdminPlayers();
      if (window.RPG.fetchAdminCatalog) window.RPG.fetchAdminCatalog();
    }
    renderRoot();
  }

  function switchAdminTestAccount(tgId) {
    if (tgId && tgId !== "main") {
      localStorage.setItem("admin_test_tg_uid", String(tgId));
    } else {
      localStorage.removeItem("admin_test_tg_uid");
    }
    RPG_STATE.adminModalOpen = false;
    window.location.reload();
  }

  function createCustomAdminTestAccount() {
    const customNum = prompt("Введите номер или ID нового тестового аккаунта (например: 999005):", "999" + Math.floor(100 + Math.random() * 899));
    if (!customNum) return;
    const cleanId = customNum.replace(/[^0-9]/g, "");
    if (!cleanId) {
      alert("ID должен состоять только из цифр!");
      return;
    }
    switchAdminTestAccount(cleanId);
  }

  async function resetCurrentTestAccount() {
    if (!confirm("Вы уверены, что хотите ПОЛНОСТЬЮ СБРОСИТЬ текущий аккаунт до 1 уровня с пустым инвентарем?")) return;
    try {
      await api.resetRpgCharacter();
      alert("Аккаунт успешно сброшен с нуля!");
      RPG_STATE.adminModalOpen = false;
      window.location.reload();
    } catch (e) {
      alert("Ошибка сброса: " + (e.message || e));
    }
  }

  // ===========================================================================
  // HERO & STAT LOGIC
  // ===========================================================================

  async function selectHero(heroClass) {
    try {
      triggerHaptic("medium");
      RPG_STATE.loading = true;
      renderRoot();
      const res = await api.selectRpgHero(heroClass);
      RPG_STATE.profile = res;
      window._cachedTalentTree = null;
      window._selectedTalentId = null;
      RPG_STATE.activeTab = "farm";
      triggerHaptic("success");
    } catch (err) {
      alert(err.message || "Не удалось выбрать героя");
    } finally {
      RPG_STATE.loading = false;
      renderRoot();
      if (RPG_STATE.farmMode === "arena") startArenaLoop();
    }
  }

  function syncArenaPlayerStats() {
    if (!ARENA.player) return;
    const stats = RPG_STATE.profile?.stats || {};
    const oldMaxHp = ARENA.player.maxHp || 450;
    const newMaxHp = Math.max(450, stats.hp_max || 450);
    const newMaxMp = Math.max(80, stats.mp_max || 80);

    if (newMaxHp > oldMaxHp) {
      ARENA.player.currentHp = Math.min(newMaxHp, (ARENA.player.currentHp || oldMaxHp) + (newMaxHp - oldMaxHp));
    } else {
      ARENA.player.currentHp = Math.min(newMaxHp, ARENA.player.currentHp || newMaxHp);
    }
    ARENA.player.maxHp = newMaxHp;
    ARENA.player.maxMp = newMaxMp;
    ARENA.player.currentMp = Math.min(newMaxMp, ARENA.player.currentMp || newMaxMp);
  }

  let isUpgradingStat = false;

  async function upgradeStat(statName, amount = 1) {
    if (isUpgradingStat) return;
    const p = RPG_STATE.profile || {};
    const points = p.stat_points || 0;
    const userGold = p.gold || 0;
    const baseAttrs = p.base_attributes || {};
    const baseVal = (statName === "str"
      ? (baseAttrs.strength ?? p.strength)
      : (statName === "agi"
        ? (baseAttrs.agility ?? p.agility)
        : (baseAttrs.intelligence ?? p.intelligence))) || 10;

    let targetCount = 1;
    let isMax = false;
    if (String(amount).toLowerCase() === "max") {
      isMax = true;
      let count = points;
      let remGold = userGold;
      let val = baseVal + points;
      while (true) {
        const cost = Math.floor(Math.pow(val, 1.35) * 6);
        if (remGold < cost) break;
        remGold -= cost;
        count++;
        val++;
        if (count >= 10000) break;
      }
      targetCount = count;
    } else {
      targetCount = Math.max(1, parseInt(amount, 10) || 1);
    }

    if (targetCount <= 0) {
      triggerHaptic("error");
      return;
    }

    isUpgradingStat = true;
    try {
      triggerHaptic("light");
      const res = await api.upgradeRpgStat(statName, { amount: isMax ? "max" : targetCount });
      if (res.profile) {
        RPG_STATE.profile = res.profile;
        syncArenaPlayerStats();
        triggerHaptic("success");
      }
    } catch (err) {
      console.warn("Upgrade stat error:", err);
      alert(err.message || "Не удалось повысить характеристику");
      await loadProfile();
    } finally {
      isUpgradingStat = false;
      renderRoot();
    }
  }

  function openItemModal(itemUid) {
    if (!RPG_STATE.profile) return;
    const inv = RPG_STATE.profile.inventory || [];
    const eq = RPG_STATE.profile.equipment || {};
    let item = inv.find((i) => i.uid === itemUid);
    if (!item) {
      if (eq.weapon?.uid === itemUid) item = eq.weapon;
      else if (eq.armor?.uid === itemUid) item = eq.armor;
      else if (eq.relic?.uid === itemUid) item = eq.relic;
      else {
        for (let i = 1; i <= 6; i++) {
          if (eq[`slot_${i}`]?.uid === itemUid) {
            item = eq[`slot_${i}`];
            break;
          }
        }
      }
    }
    if (item) {
      RPG_STATE.inspectedItem = item;
      triggerHaptic("light");
      renderRoot();
    }
  }

  function closeItemModal() {
    RPG_STATE.inspectedItem = null;
    renderRoot();
  }

  async function equipItem(itemUid, targetSlot) {
    try {
      triggerHaptic("medium");
      const res = await api.equipRpgItem(itemUid, targetSlot || RPG_STATE.slotFilterModal);
      if (res.profile) {
        RPG_STATE.profile = res.profile;
        syncArenaPlayerStats();
        RPG_STATE.inspectedItem = null;
        RPG_STATE.slotFilterModal = null;
        triggerHaptic("success");
        if (window.showToast) {
          window.showToast(res.message || "Предмет успешно экипирован!", "success");
        }
      }
    } catch (err) {
      triggerHaptic("error");
      alert(err.message || "Не удалось экипировать предмет");
    } finally {
      renderRoot();
    }
  }

  async function unequipItem(slotOrUid) {
    try {
      triggerHaptic("medium");
      const res = await api.unequipRpgItem(slotOrUid);
      if (res.profile) {
        RPG_STATE.profile = res.profile;
        syncArenaPlayerStats();
        RPG_STATE.inspectedItem = null;
        RPG_STATE.slotFilterModal = null;
        triggerHaptic("success");
        if (window.showToast) {
          window.showToast(res.message || "Предмет снят в рюкзак", "info");
        }
      }
    } catch (err) {
      triggerHaptic("error");
      alert(err.message || "Не удалось снять предмет");
    } finally {
      renderRoot();
    }
  }

  async function useConsumable(itemUid) {
    try {
      triggerHaptic("medium");
      const res = await api.useRpgItem(itemUid);
      if (res.profile) {
        RPG_STATE.profile = res.profile;
        const pot = res.potion_result || {};
        if (pot.heal_hp > 0 && ARENA.player) {
          ARENA.player.currentHp = Math.min(ARENA.player.maxHp, ARENA.player.currentHp + pot.heal_hp);
          spawnFloatingText(ARENA.player.x, ARENA.player.y - 25, `+${pot.heal_hp} HP ❤️`, "#22c55e");
        }
        if (pot.heal_mp > 0 && ARENA.player) {
          ARENA.player.currentMp = Math.min(ARENA.player.maxMp, ARENA.player.currentMp + pot.heal_mp);
          spawnFloatingText(ARENA.player.x, ARENA.player.y - 35, `+${pot.heal_mp} MP 🔮`, "#38bdf8");
        }
        if (pot.remaining_count <= 0) {
          RPG_STATE.inspectedItem = null;
        } else if (RPG_STATE.inspectedItem) {
          RPG_STATE.inspectedItem.count = pot.remaining_count;
        }
        triggerHaptic("success");
      }
    } catch (err) {
      alert(err.message || "Не удалось использовать зелье");
    } finally {
      renderRoot();
    }
  }

  async function openShopModal() {
    try {
      triggerHaptic("light");
      RPG_STATE.shopModalOpen = true;
      if (!RPG_STATE.shopCatalog || RPG_STATE.shopCatalog.length === 0) {
        RPG_STATE.shopLoading = true;
        renderRoot();
        try {
          const catalog = await api.getRpgShop();
          if (Array.isArray(catalog) && catalog.length > 0) {
            RPG_STATE.shopCatalog = catalog;
          } else {
            RPG_STATE.shopCatalog = [...FALLBACK_SHOP_CATALOG];
          }
        } catch (e) {
          console.warn("Could not fetch shop catalog, using fallback:", e);
          RPG_STATE.shopCatalog = [...FALLBACK_SHOP_CATALOG];
        } finally {
          RPG_STATE.shopLoading = false;
        }
      }
    } catch (err) {
      console.error("Failed to open shop:", err);
      if (!RPG_STATE.shopCatalog || RPG_STATE.shopCatalog.length === 0) {
        RPG_STATE.shopCatalog = [...FALLBACK_SHOP_CATALOG];
      }
    } finally {
      renderRoot();
    }
  }

  async function reloadShopCatalog() {
    try {
      triggerHaptic("light");
      RPG_STATE.shopLoading = true;
      renderRoot();
      const catalog = await api.getRpgShop();
      if (Array.isArray(catalog) && catalog.length > 0) {
        RPG_STATE.shopCatalog = catalog;
      } else {
        RPG_STATE.shopCatalog = [...FALLBACK_SHOP_CATALOG];
      }
    } catch (err) {
      console.warn("Could not reload shop catalog, using fallback:", err);
      RPG_STATE.shopCatalog = [...FALLBACK_SHOP_CATALOG];
    } finally {
      RPG_STATE.shopLoading = false;
      renderRoot();
    }
  }

  function closeShopModal() {
    RPG_STATE.shopModalOpen = false;
    renderRoot();
  }

  function setShopFilter(filter) {
    RPG_STATE.shopFilter = filter;
    renderRoot();
  }

  async function buyShopItem(itemId) {
    if (RPG_STATE.buyingItemId) return;
    try {
      RPG_STATE.buyingItemId = itemId;
      triggerHaptic("medium");
      const res = await api.buyRpgShopItem(itemId);
      if (res.profile) {
        RPG_STATE.profile = res.profile;
        triggerHaptic("success");
        if (window.showToast) {
          window.showToast(res.message || "Товар приобретен!", "success");
        } else {
          alert(res.message || "Товар успешно куплен!");
        }
      }
    } catch (err) {
      triggerHaptic("error");
      alert(err.message || "Не удалось совершить покупку");
    } finally {
      RPG_STATE.buyingItemId = null;
      renderRoot();
    }
  }

  function openSlotFilterModal(slotKey) {
    RPG_STATE.inspectedItem = null;
    RPG_STATE.slotFilterModal = slotKey;
    triggerHaptic("light");
    renderRoot();
  }

  function closeSlotFilterModal() {
    RPG_STATE.slotFilterModal = null;
    renderRoot();
  }

  function openForge(itemUid) {
    if (!RPG_STATE.profile) return;
    const inv = RPG_STATE.profile.inventory || [];
    const eq = RPG_STATE.profile.equipment || {};
    let item = inv.find((i) => i.uid === itemUid);
    if (!item) {
      if (eq.slot_1?.uid === itemUid) item = eq.slot_1;
      else if (eq.slot_2?.uid === itemUid) item = eq.slot_2;
      else if (eq.slot_3?.uid === itemUid) item = eq.slot_3;
      else if (eq.slot_4?.uid === itemUid) item = eq.slot_4;
      else if (eq.slot_5?.uid === itemUid) item = eq.slot_5;
      else if (eq.slot_6?.uid === itemUid) item = eq.slot_6;
    }
    if (item) {
      RPG_STATE.inspectedItem = null;
      RPG_STATE.forgeItem = item;
      RPG_STATE.forgeSuccessAnimation = false;
      triggerHaptic("light");
      renderRoot();
    }
  }

  function closeForgeModal() {
    RPG_STATE.forgeItem = null;
    renderRoot();
  }

  async function forgeCurrentItem() {
    if (!RPG_STATE.forgeItem) return;
    try {
      triggerHaptic("heavy");
      const res = await api.forgeRpgItem(RPG_STATE.forgeItem.uid);
      if (res.profile) {
        RPG_STATE.profile = res.profile;
        syncArenaPlayerStats();
        RPG_STATE.forgeItem = res.item || RPG_STATE.forgeItem;
        if (res.success) {
          RPG_STATE.forgeSuccessAnimation = true;
          triggerHaptic("success");
          setTimeout(() => {
            RPG_STATE.forgeSuccessAnimation = false;
            renderRoot();
          }, 1200);
        } else {
          triggerHaptic("warning");
          RPG_STATE.forgeFailMessage = res.message || "Заточка не удалась!";
          setTimeout(() => {
            RPG_STATE.forgeFailMessage = null;
            renderRoot();
          }, 2500);
        }
      }
    } catch (err) {
      triggerHaptic("error");
      alert(err.message || "Не удалось заточить предмет");
    } finally {
      renderRoot();
    }
  }

  async function sellItem(itemUid) {
    if (!confirm("Продать этот предмет за золото?")) return;
    try {
      triggerHaptic("light");
      const res = await api.sellRpgItem(itemUid);
      if (res.profile) {
        RPG_STATE.profile = res.profile;
        RPG_STATE.inspectedItem = null;
        if (RPG_STATE.selectedItemUids) RPG_STATE.selectedItemUids.delete(itemUid);
        triggerHaptic("success");
      }
    } catch (err) {
      alert(err.message || "Не удалось продать предмет");
    } finally {
      renderRoot();
    }
  }

  function getItemSellPrice(item) {
    if (!item) return 0;
    const rarity = (item.rarity || "common").toLowerCase();
    const prices = { common: 40, uncommon: 75, rare: 120, epic: 320, legendary: 850, immortal: 2500 };
    const base = prices[rarity] || 40;
    const upg = item.upgrade || item.forge_level || 0;
    return base + (upg * 35);
  }

  function getSelectedItemsTotalPrice() {
    if (!RPG_STATE.selectedItemUids || RPG_STATE.selectedItemUids.size === 0) return 0;
    const inv = RPG_STATE.profile?.inventory || [];
    let sum = 0;
    for (const it of inv) {
      if (RPG_STATE.selectedItemUids.has(it.uid)) {
        sum += getItemSellPrice(it);
      }
    }
    return sum;
  }

  function toggleItemSelectionMode(forced) {
    RPG_STATE.isSelectionMode = (forced !== undefined) ? forced : !RPG_STATE.isSelectionMode;
    if (!RPG_STATE.isSelectionMode && RPG_STATE.selectedItemUids) {
      RPG_STATE.selectedItemUids.clear();
    }
    triggerHaptic("medium");
    renderRoot();
  }

  function toggleItemSelection(itemUid) {
    if (!RPG_STATE.selectedItemUids) {
      RPG_STATE.selectedItemUids = new Set();
    }
    if (RPG_STATE.selectedItemUids.has(itemUid)) {
      RPG_STATE.selectedItemUids.delete(itemUid);
      if (RPG_STATE.selectedItemUids.size === 0) {
        // keep selection mode active for easy continued picking
      }
    } else {
      RPG_STATE.selectedItemUids.add(itemUid);
      RPG_STATE.isSelectionMode = true; // Auto-activate selection mode on first item check!
    }
    triggerHaptic("light");
    renderRoot();
  }

  function selectAllByRarity(rarity) {
    const inv = RPG_STATE.profile?.inventory || [];
    if (!RPG_STATE.selectedItemUids) {
      RPG_STATE.selectedItemUids = new Set();
    }
    RPG_STATE.isSelectionMode = true;
    for (const item of inv) {
      if (!rarity || item.rarity === rarity) {
        RPG_STATE.selectedItemUids.add(item.uid);
      }
    }
    triggerHaptic("medium");
    renderRoot();
  }

  function clearItemSelection() {
    if (RPG_STATE.selectedItemUids) {
      RPG_STATE.selectedItemUids.clear();
    }
    triggerHaptic("light");
    renderRoot();
  }

  function handleInventoryItemClick(itemUid) {
    if (RPG_STATE.isSelectionMode || (RPG_STATE.selectedItemUids && RPG_STATE.selectedItemUids.size > 0)) {
      toggleItemSelection(itemUid);
    } else {
      openItemModal(itemUid);
    }
  }

  async function sellSelectedItems() {
    const uids = Array.from(RPG_STATE.selectedItemUids || []);
    if (uids.length === 0) {
      alert("Не выбрано ни одного предмета для продажи!");
      return;
    }
    if (!confirm(`Продать выбранные ${uids.length} предметов за золото?`)) {
      return;
    }

    try {
      triggerHaptic("medium");
      const res = await api.sellMultipleRpgItems(uids);
      if (res.profile) {
        RPG_STATE.profile = res.profile;
        RPG_STATE.selectedItemUids.clear();
        RPG_STATE.isSelectionMode = false;
        triggerHaptic("success");
        if (window.showToast) {
          window.showToast(res.message || `Продано ${res.items_sold} предметов за +${res.gold_earned} 🪙!`, "success");
        } else {
          alert(res.message);
        }
      }
    } catch (err) {
      triggerHaptic("error");
      alert(err.message || "Не удалось продать предметы");
    } finally {
      renderRoot();
    }
  }

  async function resetCharacter() {
    if (!confirm("⚠️ ВНИМАНИЕ: Сбросить персонажа до 1 уровня?\n\nВсе уровни, золото и предметы будут обнулены, и начнётся чистое хардкорное приключение с 1 этажа!")) {
      return;
    }
    try {
      triggerHaptic("heavy");
      const res = await api.resetRpgCharacter();
      if (res.profile) {
        RPG_STATE.profile = res.profile;
        if (RPG_STATE.selectedItemUids) RPG_STATE.selectedItemUids.clear();
        syncArenaPlayerStats();
        retryCurrentFloor();
        triggerHaptic("success");
        if (window.showToast) {
          window.showToast("Персонаж успешно сброшен до 1 уровня!", "info");
        } else {
          alert("Персонаж успешно сброшен до 1 уровня!");
        }
      }
    } catch (err) {
      triggerHaptic("error");
      alert(err.message || "Не удалось сбросить персонажа");
    } finally {
      renderRoot();
    }
  }

  // ===========================================================================
  // CHEST SYSTEM (СУНДУКИ НАГРАДЫ)
  // ===========================================================================

  function openChestModal(chestData) {
    if (!chestData) return;
    if (RPG_STATE.activeChestModal) return; // Prevent double modal open!
    RPG_STATE.activeChestModal = { ...chestData, opened: false };
    triggerHaptic("medium");
    renderRoot();
  }

  function closeChestModal() {
    RPG_STATE.activeChestModal = null;
    RPG_STATE.lastBossChestReward = null;
    if (typeof ARENA !== "undefined" && ARENA.waveState === "boss_victory") {
      ARENA.waveState = "fighting";
    }
    if (typeof ARENA !== "undefined" && (ARENA.isRaidBossBattle || ARENA._wasRaidBossBattle)) {
      exitRaidBossBattle();
      return;
    }
    renderRoot();
    if (ARENA.autoAdvanceWaves && ARENA.waveState === "prompt") {
      confirmNextWave();
    }
  }

  async function claimChestReward() {
    if (!RPG_STATE.activeChestModal) return;
    RPG_STATE.activeChestModal.opened = true;
    triggerHaptic("success");
    renderRoot();
  }

  // ===========================================================================
  // FAST SIMULATION SLAUGHTER (БЫСТРАЯ ЗАРУБКА)
  // ===========================================================================

  async function slashWave() {
    if (RPG_STATE.isFighting) return;
    try {
      RPG_STATE.isFighting = true;
      triggerHaptic("medium");
      renderRoot();

      const res = await api.slashCreepWave();
      RPG_STATE.lastBattle = res;
      if (res.profile) {
        RPG_STATE.profile = res.profile;
      }
      if (res.victory) {
        RPG_STATE.killsSession++;
        triggerHaptic(res.is_boss ? "success" : "light");
      } else {
        triggerHaptic("error");
      }
      if (res.leveled_up) {
        showLevelUpToast(res.profile?.level || 2);
      }
      if (res.chest_reward) {
        openChestModal(res.chest_reward);
      }
      if (res.combat_log && res.combat_log.length > 0) {
        RPG_STATE.combatLog = res.combat_log;
      }
    } catch (err) {
      console.error("Slash wave error:", err);
      alert(err.message || "Ошибка боя с волной крипов");
      if (RPG_STATE.autoFarm) toggleAutoFarm(false);
    } finally {
      RPG_STATE.isFighting = false;
      renderRoot();
    }
  }

  function toggleAutoFarm(forcedState) {
    const newState = forcedState !== undefined ? forcedState : !RPG_STATE.autoFarm;
    RPG_STATE.autoFarm = newState;

    if (RPG_STATE.autoFarmTimer) {
      clearInterval(RPG_STATE.autoFarmTimer);
      RPG_STATE.autoFarmTimer = null;
    }

    if (newState) {
      triggerHaptic("medium");
      slashWave();
      RPG_STATE.autoFarmTimer = setInterval(() => {
        if (!RPG_STATE.isFighting && RPG_STATE.activeTab === "farm") {
          slashWave();
        }
      }, 2500);
    } else {
      triggerHaptic("light");
    }
    renderRoot();
  }

  function showLevelUpToast(newLevel) {
    RPG_STATE.levelUpNotification = newLevel;
    triggerHaptic("success");
    setTimeout(() => {
      RPG_STATE.levelUpNotification = null;
      renderRoot();
    }, 3500);
  }

  // ===========================================================================
  // 2D ACTION ARENA ENGINE (<canvas>) — GROW CASTLE DOTA 2 STYLE
  // Герой стоит слева на тропе, крипы из Доты бегут справа.
  // 20 волн = 1 этаж (босс на 20-й волне).
  // У каждого героя уникальная атака (дальняя/ближняя), Скилл 1 и Ультимейт.
  // ===========================================================================

  const ARENA = {
    canvas: null,
    ctx: null,
    animId: null,
    width: 360,
    height: 320,
    running: false,

    // Landscape
    roadY: 225,

    // Player Entity (STATIONARY — no movement!)
    player: {
      x: 65,
      y: 200,
      radius: 20,
      currentHp: 200,
      maxHp: 200,
      currentMp: 60,
      maxMp: 60,
      attackCooldown: 0,
      attackQueued: false,
      attackRange: 270,
      isRanged: false,
      slashAnimation: null,
      autoAttack: true,
      // Active skill timers
      fleshHeapActive: 0,      // Pudge -40% damage
      bladeDanceActive: 0,     // Juggernaut +50% attack speed
      rotActive: 0,            // Pudge rot poison
      counterspellActive: 0    // Anti-Mage shield
    },

    // Cooldowns
    skill1Cooldown: 0,
    skill1CooldownMax: 480, // default 8s
    ultCooldown: 0,
    ultCooldownMax: 900,    // default 15s

    // Projectiles & Minions
    playerProjectiles: [],
    alliedMinions: [],
    specialEffects: [],

    // Creeps (come from right only)
    creeps: [],
    creepSpawnTimer: 0,
    totalCreepsSpawned: 0,
    waveNumber: 1,
    waveMax: 20, // Boss every 20 waves
    creepsKilledInWave: 0,
    creepsNeededForWave: 5,

    // Boss
    isBossActive: false,
    bossEntity: null,
    bossPhase: 0,
    bossSpecialTimer: 0,
    bossProjectiles: [],
    bossPartyMode: (() => {
      try {
        return localStorage.getItem("rpg_boss_party_mode") || "trio";
      } catch (e) {
        return "trio";
      }
    })(),
    bossCompanions: [],
    _partyBtnBounds: null,

    // Boss Arena 2D Combat Mode (free player movement)
    bossArenaMode: false,
    moveInput: { left: false, right: false },
    dodgeCooldown: 0,
    potionCooldown: 0,
    dodgeActive: 0,      // frames remaining of dodge i-frame
    dodgeDir: 1,          // direction of dodge roll
    dangerZones: [],
    joystick: { active: false, touchId: null, baseX: 0, baseY: 0, curX: 0, curY: 0, dx: 0, dy: 0, power: 0 },
    topDownMode: false,
    dashGhosts: [],
    keysPressed: {},      // boss attack telegraphs on arena floor
    bossAttackPattern: null, // current boss attack being executed
    bossPatternTimer: 0,     // timer for current pattern phase
    bossPatternPhase: "idle", // idle | telegraph | execute | recover
    _touchMoveId: null,   // active touch for movement

    // Boss interaction windows & Polish
    blockWindowActive: false,
    blockWindowTimer: 0,
    blockWindowMax: 120,
    qteActive: false,
    qteTimer: 0,
    qteMaxTimer: 90,

    // Wave Combat & Style Engine (Hades / DMC)
    enemyProjectiles: [],
    dashGhosts: [],
    combo: { count: 0, timer: 0, step: 0, maxCombo: 0 },
    styleMeter: { score: 0, rank: "D", progress: 0, decayTimer: 0, maxRank: "D" },

    // Advanced Boss Combat Engine (Sekiro/Hollow Knight/Dota 2)
    cameraTrauma: 0,
    hitstop: 0,
    parryWindow: 0,
    shockwaves: [],
    telegraphs: [],
    physicalCoins: [],
    fallingChest: null,

    // Hero Talent Perks State
    pudgeUndyingUsed: false,
    pudgeHitCounter: 0,
    wkReincarnationUsed: false,
    sfSouls: 0,
    blinkReflexCd: 0,

    // Wave state machine
    // 'fighting' | 'wave_clear' | 'prompt' | 'boss_intro' | 'floor_clear' | 'retry_prompt'
    waveState: "fighting",
    waveTransitionTimer: 0,
    _promptBtnBounds: null,
    _promptDisableBtnBounds: null,
    autoAdvanceWaves: (() => {
      try {
        const val = localStorage.getItem("rpg_arena_auto_advance_waves");
        return val !== null ? val === "true" : true;
      } catch (e) {
        return true;
      }
    })(),

    // Effects & Pickups
    floatingTexts: [],
    pickups: [],

    // Background
    clouds: [],
    bgInit: false
  };

  // ---------------------------------------------------------------------------
  // DOTA 2 HERO SKILL CONFIGS
  // ---------------------------------------------------------------------------

  function getHeroSkillConfig() {
    const hClass = (RPG_STATE.profile?.hero_class || "pudge").toLowerCase();
    const configs = {
      invoker: {
        isRanged: true,
        attackRange: 380,
        skill1Name: "Санстрайк",
        skill1Icon: "☀️",
        skill1Cd: 420, // 7 sec
        skill1Desc: "Ослепительный луч солнца бьет с неба, нанося чистый урон и ломая щиты!",
        ultName: "Хаос Метеор (Котлета)",
        ultIcon: "☄️",
        ultCd: 840, // 14 sec
        ultDesc: "С неба обрушивается пылающий метеор («котлета»), катится по всей линии и сжигает всё на пути!"
      },
      pudge: {
        isRanged: false,
        attackRange: 270,
        skill1Name: "Защитная Плоть",
        skill1Icon: "🥩",
        skill1Cd: 840, // 14 sec
        skill1Desc: "Блокирует 40% всего входящего урона на 8 секунд!",
        ultName: "Чумная Гниль",
        ultIcon: "☣️",
        ultCd: 720, // 12 sec
        ultDesc: "Вонь на всю карту 2.5 сек, наносящая урон всем крипам!"
      },
      juggernaut: {
        isRanged: false,
        attackRange: 275,
        skill1Name: "Танец Клинка",
        skill1Icon: "💨",
        skill1Cd: 600, // 10 sec
        skill1Desc: "Увеличивает скорость атаки на +50% на 6 секунд!",
        ultName: "Омнислеш",
        ultIcon: "⚔️",
        ultCd: 900, // 15 sec
        ultDesc: "Вихрь рассекающих ударов по всей карте!"
      },
      phantom_assassin: {
        isRanged: false,
        attackRange: 270,
        skill1Name: "Кинжал Тени",
        skill1Icon: "🗡️",
        skill1Cd: 360, // 6 sec
        skill1Desc: "Бросок отравленного кинжала с критом и замедлением!",
        ultName: "Coup de Grace",
        ultIcon: "🩸",
        ultCd: 720, // 12 sec
        ultDesc: "Сокрушительный выпад с критическим уроном x5.0!"
      },
      shadow_fiend: {
        isRanged: true,
        attackRange: 360,
        skill1Name: "Тройной Койл",
        skill1Icon: "🌑",
        skill1Cd: 420, // 7 sec
        skill1Desc: "Три мощных взрыва душ в ряд перед собой!",
        ultName: "Реквием Душ",
        ultIcon: "🌪️",
        ultCd: 960, // 16 sec
        ultDesc: "Адские волны темных душ во все стороны!"
      },
      wraith_king: {
        isRanged: false,
        attackRange: 280,
        skill1Name: "Огненный Стан",
        skill1Icon: "💀",
        skill1Cd: 480, // 8 sec
        skill1Desc: "Огненный череп оглушает крипов по площади!",
        ultName: "Армия Скелетов",
        ultIcon: "👑",
        ultCd: 960, // 16 sec
        ultDesc: "Призывает отряд скелетов-воинов + 100% вампиризм!"
      },
      anti_mage: {
        isRanged: false,
        attackRange: 270,
        skill1Name: "Щит Магии",
        skill1Icon: "🛡️",
        skill1Cd: 420, // 7 sec
        skill1Desc: "Магический щит отражения + мгновенный выпад!",
        ultName: "Взрыв Маны",
        ultIcon: "💥",
        ultCd: 840, // 14 sec
        ultDesc: "Колоссальный взрыв маны по скоплению врагов!"
      },
      leshrac: {
        isRanged: true,
        attackRange: 450,
        skill1Name: "Кваканье Гения",
        skill1Icon: "🎵",
        skill1Cd: 420, // 7 sec
        skill1Desc: "3-й скилл Ларго: -60% расхода маны + эхо-реверберация урона!",
        ultName: "Рапсодия",
        ultIcon: "🐸",
        ultCd: 30, // 0.5s toggle debounce
        ultDesc: "Вкл/Выкл: длится бесконечно! Каждые 2 сек тратит ману, наносит урон всем вокруг и хилит Ларго!"
      }
    };
    return configs[hClass] || configs.pudge;
  }

  // ---------------------------------------------------------------------------
  // INITIALIZATION
  // ---------------------------------------------------------------------------

  function bindArenaCanvas(canvas) {
    if (!canvas) canvas = document.getElementById("rpg-action-canvas");
    if (!canvas) return;

    // If canvas has no rendered size yet (DOM not laid out), defer until next frame
    const earlyRect = canvas.getBoundingClientRect();
    if (earlyRect.width < 10 && canvas.clientWidth < 10) {
      requestAnimationFrame(() => bindArenaCanvas(canvas));
      return;
    }

    ARENA.canvas = canvas;
    ARENA.ctx = canvas.getContext("2d");
    if (ARENA.ctx) {
      const h = ARENA.height || 320;
      ARENA.cachedSkyGrad = ARENA.ctx.createLinearGradient(0, -24, 0, h * 0.55);
      ARENA.cachedSkyGrad.addColorStop(0, "#2563eb");
      ARENA.cachedSkyGrad.addColorStop(1, "#93c5fd");
      ARENA.cachedGroundGrad = ARENA.ctx.createLinearGradient(0, h * 0.55 - 4, 0, h + 24);
      ARENA.cachedGroundGrad.addColorStop(0, "#16a34a");
      ARENA.cachedGroundGrad.addColorStop(0.4, "#15803d");
      ARENA.cachedGroundGrad.addColorStop(1, "#14532d");
    }

    const rect = canvas.getBoundingClientRect();
    const dpr = Math.min(2, (typeof window !== "undefined" && window.devicePixelRatio && window.devicePixelRatio > 0) ? window.devicePixelRatio : 1);
    const isTopDown = !!(ARENA.topDownMode || ARENA.isRaidBossBattle);
    const clientW = canvas.clientWidth > 50 ? canvas.clientWidth : (rect.width > 50 ? rect.width : 360);
    const clientH = isTopDown ? 520 : (canvas.clientHeight > 50 ? canvas.clientHeight : (rect.height > 50 ? rect.height : 320));
    // In Top-Down Brawl mode, arena logical space is a spacious 520x720 battlefield!
    ARENA.cachedClientW = clientW;
    ARENA.cachedClientH = clientH;
    ARENA.dpr = dpr;
    ARENA.width = isTopDown ? 520 : clientW;
    ARENA.height = isTopDown ? 720 : clientH;
    canvas.width = Math.round(clientW * dpr);
    canvas.height = Math.round(clientH * dpr);
    if (ARENA.ctx) {
      ARENA.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    setupArenaListeners(canvas);
    bindVirtualJoystick();
  }

  function initArenaCanvas() {
    const canvas = document.getElementById("rpg-action-canvas");
    if (!canvas) return;
    bindArenaCanvas(canvas);

    // CRITICAL: NEVER wipe out an active Boss Battle (Raid or Dungeon)!
    if (ARENA.isRaidBossBattle || (ARENA.isBossActive && ARENA.bossEntity)) {
      if (ARENA.bossEntity && !ARENA.creeps.includes(ARENA.bossEntity)) {
        ARENA.creeps = [ARENA.bossEntity];
      }
      ARENA.isBossActive = true;
      return;
    }

    const p = RPG_STATE.profile;
    const stats = p?.stats || {};
    const skillCfg = getHeroSkillConfig();

    ARENA.player.x = 65;
    ARENA.player.y = ARENA.roadY - 18;
    ARENA.player.radius = 20;
    ARENA.player.maxHp = Math.max(450, stats.hp_max || 450);
    ARENA.player.currentHp = ARENA.player.maxHp;
    ARENA.player.maxMp = Math.max(80, stats.mp_max || 80);
    ARENA.player.currentMp = ARENA.player.maxMp;
    ARENA.player.isRanged = skillCfg.isRanged;
    ARENA.player.attackRange = skillCfg.attackRange;
    ARENA.player.fleshHeapActive = 0;
    ARENA.player.bladeDanceActive = 0;
    ARENA.player.rotActive = 0;
    ARENA.player.counterspellActive = 0;
    ARENA.player.largoRhapsodyActive = false;
    ARENA.player.largoRhapsodyTickTimer = 0;

    ARENA.skill1Cooldown = 0;
    ARENA.skill1CooldownMax = skillCfg.skill1Cd;
    ARENA.ultCooldown = 0;
    ARENA.ultCooldownMax = skillCfg.ultCd;

    ARENA.creeps = [];
    ARENA.pickups = [];
    ARENA.floatingTexts = [];
    ARENA.bossProjectiles = [];
    ARENA.playerProjectiles = [];
    ARENA.alliedMinions = [];
    ARENA.specialEffects = [];

    // Always synchronize active wave with database progress from profile
    const currentSavedWave = ((RPG_STATE.profile?.dungeon_cleared || 0) % 20) + 1;
    if (!ARENA.waveNumber || ARENA.waveNumber < 1 || ARENA.waveNumber !== currentSavedWave) {
      ARENA.waveNumber = currentSavedWave;
    }
    ARENA.waveMax = 20;
    ARENA.creepsKilledInWave = 0;
    ARENA.totalCreepsSpawned = 0;
    ARENA.creepsNeededForWave = Math.min(32, 14 + Math.floor((ARENA.waveNumber - 1) * 1.0));
    ARENA.isBossActive = false;
    ARENA.bossEntity = null;
    ARENA.bossPhase = 0;
    ARENA.bossCompanions = [];
    ARENA._partyBtnBounds = null;
    ARENA.bossArenaMode = false;
    ARENA.moveInput = { left: false, right: false };
    ARENA.dodgeCooldown = 0;
    ARENA.potionCooldown = 0;
    ARENA.dodgeActive = 0;
    ARENA.dodgeDir = 1;
    ARENA.dangerZones = [];
    ARENA.bossAttackPattern = null;
    ARENA.bossPatternTimer = 0;
    ARENA.bossPatternPhase = "idle";
    ARENA._touchMoveId = null;
    ARENA.waveState = "fighting";
    ARENA.blockWindowActive = false;
    ARENA.qteActive = false;
    ARENA.cameraTrauma = 0;
    ARENA.hitstop = 0;
    ARENA.parryWindow = 0;
    ARENA.shockwaves = [];
    ARENA.telegraphs = [];
    ARENA.physicalCoins = [];
    ARENA.fallingChest = null;
    ARENA._promptBtnBounds = null;
    ARENA.enemyProjectiles = [];
    ARENA.dashGhosts = [];
    ARENA.combo = { count: 0, timer: 0, step: 0, maxCombo: 0 };
    ARENA.styleMeter = { score: 0, rank: "D", progress: 0, decayTimer: 0, maxRank: "D" };
    ARENA.player.isDashing = false;
    ARENA.player.dashCooldown = 0;
    ARENA.player.isInvulnerable = 0;
    ARENA.player.critBuff = false;
    ARENA.player.isBlocking = 0;

    // Reset perk battle counters
    ARENA.pudgeUndyingUsed = false;
    ARENA.pudgeHitCounter = 0;
    ARENA.wkReincarnationUsed = false;
    ARENA.sfSouls = 0;
    ARENA.blinkReflexCd = 0;

    if (!ARENA.bgInit) {
      ARENA.clouds = [];
      for (let i = 0; i < 5; i++) {
        ARENA.clouds.push({
          x: Math.random() * ARENA.width,
          y: 18 + Math.random() * 45,
          speed: 0.12 + Math.random() * 0.18
        });
      }
      ARENA.bgInit = true;
    }
  }

  function hasTalentPerk(perkId) {
    const perks = RPG_STATE.profile?.stats?.perks;
    return Array.isArray(perks) && perks.includes(perkId);
  }
  window.hasTalentPerk = hasTalentPerk;


  // ===========================================================================
  // ARCHERO-STYLE TOP-DOWN JOYSTICK & STUTTER-STEP SYSTEM
  // ===========================================================================

  function playerPerformDashRoll() {
    const p = ARENA.player;
    if (ARENA.dodgeCooldown > 0) return;

    let dirX = ARENA.joystick.dx;
    let dirY = ARENA.joystick.dy;

    // If standing still, dash in current facing direction
    if (Math.abs(dirX) < 0.05 && Math.abs(dirY) < 0.05) {
      const fa = p.facingAngle !== undefined ? p.facingAngle : (p.facing === -1 ? Math.PI : 0);
      dirX = Math.cos(fa);
      dirY = Math.sin(fa);
    }
    const mag = Math.hypot(dirX, dirY) || 1;
    dirX /= mag;
    dirY /= mag;

    const dashDist = 88;
    p.x = Math.max(28, Math.min(ARENA.width - 28, p.x + dirX * dashDist));
    p.y = Math.max(38, Math.min(ARENA.height - 38, p.y + dirY * dashDist));

    p.isInvulnerable = 26; // 26 frames of invincibility (~430ms)
    ARENA.dodgeCooldown = 90; // 1.5s cooldown

    if (!ARENA.dashGhosts) ARENA.dashGhosts = [];
    const hClass = (RPG_STATE.profile?.hero_class || "pudge").toLowerCase();
    for (let g = 0; g < 4; g++) {
      ARENA.dashGhosts.push({
        x: p.x - dirX * (g * 22),
        y: p.y - dirY * (g * 22),
        radius: p.radius || 22,
        alpha: 0.65 - g * 0.14,
        heroClass: hClass
      });
    }

    spawnFloatingText(p.x, p.y - 25, "🌀 РЫВОК! (I-FRAMES)", "#38bdf8");
    triggerHaptic("heavy");
  }

  function toggleTopDownArenaMode() {
    ARENA.topDownMode = !ARENA.topDownMode;
    const canvas = document.getElementById("rpg-action-canvas");
    if (canvas) {
      bindArenaCanvas(canvas);
    }
    renderRoot();
  }

  function bindVirtualJoystick() {
    const zone = document.getElementById("rpg-virtual-joystick-zone");
    const knob = document.getElementById("rpg-joystick-knob");
    if (!zone || !knob) return;

    const maxRadius = 46;
    const deadzone = 12;

    function handleStart(clientX, clientY, touchId) {
      ARENA.joystick.active = true;
      ARENA.joystick.touchId = touchId;
      const rect = zone.getBoundingClientRect();
      ARENA.joystick.baseX = rect.left + rect.width / 2;
      ARENA.joystick.baseY = rect.top + rect.height / 2;
      handleMove(clientX, clientY);
    }

    function handleMove(clientX, clientY) {
      if (!ARENA.joystick.active) return;
      let dx = clientX - ARENA.joystick.baseX;
      let dy = clientY - ARENA.joystick.baseY;
      const dist = Math.hypot(dx, dy);

      // Clamp knob visually inside joystick boundary
      let knobX = dx;
      let knobY = dy;
      if (dist > maxRadius) {
        knobX = (dx / dist) * maxRadius;
        knobY = (dy / dist) * maxRadius;
      }
      knob.style.transform = `translate(${knobX}px, ${knobY}px)`;

      ARENA.joystick.curX = knobX;
      ARENA.joystick.curY = knobY;

      // Soft deadzone and smoothed progressive sensitivity
      if (dist < deadzone) {
        ARENA.joystick.dx = 0;
        ARENA.joystick.dy = 0;
        ARENA.joystick.power = 0;
        ARENA.player.isMoving = false;
        return;
      }

      const ratio = Math.min(1.0, (dist - deadzone) / (maxRadius - deadzone));
      const smoothPower = Math.pow(ratio, 1.35) * 0.90;
      const angle = Math.atan2(dy, dx);

      ARENA.joystick.dx = Math.cos(angle) * smoothPower;
      ARENA.joystick.dy = Math.sin(angle) * smoothPower;
      ARENA.joystick.power = smoothPower;

      if (smoothPower > 0.18) {
        ARENA.player.isMoving = true;
        ARENA.player.facingAngle = angle;
      } else {
        ARENA.player.isMoving = false;
      }
    }

    function handleEnd() {
      ARENA.joystick.active = false;
      ARENA.joystick.touchId = null;
      ARENA.joystick.dx = 0;
      ARENA.joystick.dy = 0;
      ARENA.joystick.power = 0;
      ARENA.player.isMoving = false;
      knob.style.transform = "translate(0px, 0px)";
    }

    // Pointer / Touch Events on Joystick
    zone.ontouchstart = (e) => {
      e.preventDefault();
      const t = e.changedTouches[0];
      handleStart(t.clientX, t.clientY, t.identifier);
    };

    zone.ontouchmove = (e) => {
      e.preventDefault();
      if (!ARENA.joystick.active) return;
      const t = Array.from(e.changedTouches).find(touch => touch.identifier === ARENA.joystick.touchId);
      if (t) handleMove(t.clientX, t.clientY);
    };

    zone.ontouchend = (e) => {
      e.preventDefault();
      handleEnd();
    };
    zone.ontouchcancel = (e) => {
      handleEnd();
    };

    // Desktop Mouse Fallback
    zone.onmousedown = (e) => {
      e.preventDefault();
      handleStart(e.clientX, e.clientY, "mouse");
      const onMouseMove = (ev) => handleMove(ev.clientX, ev.clientY);
      const onMouseUp = () => {
        handleEnd();
        window.removeEventListener("mousemove", onMouseMove);
        window.removeEventListener("mouseup", onMouseUp);
      };
      window.addEventListener("mousemove", onMouseMove);
      window.addEventListener("mouseup", onMouseUp);
    };
  }


  // REAL RPG DAMAGE: Hero ATK vs Boss Defense (no more %-HP cheese!)

  function applyDamageToBoss(boss, rawDmg, isCrit) {
    if (!boss || boss.hp <= 0 || isNaN(boss.hp)) return 0;
    if (rawDmg == null || isNaN(rawDmg) || rawDmg <= 0) return 0;

    const p = ARENA.player;
    const stats = RPG_STATE.profile?.stats || {};
    const eq = RPG_STATE.profile?.equipment || {};

      // Boss defense: stored on entity, or fallback by tier
    const BOSS_DEF_BY_TIER = {
      golem: 35, lich: 50, tormentor: 75, dragon: 105, pudge_boss: 140,
      faceless_void: 180, roshan: 230, tidehunter: 290, sf_boss: 370,
      necrophos: 460, terrorblade: 570, invoker_boss: 700, chaos_knight: 860,
      dark_tormentor: 1050, storm_spirit: 1300, doom: 1600, primal_beast: 1950,
      phantom_roshan: 2400, tinker_boss: 3000, enigma: 3800
    };
    let bossDefense = boss.defense !== undefined ? boss.defense : 35;
    if (!boss.defense) {
      const bId = ((boss.bossType || boss.id || boss.name) || "golem").toLowerCase();
      for (const [k, v] of Object.entries(BOSS_DEF_BY_TIER)) {
        if (bId.includes(k)) { bossDefense = v; break; }
      }
    }

    // Passive Items on Boss: Desolator & Assault Cuirass Minus Armor
    const hasDeso = Object.values(eq).some(it => it && (it.name?.includes("Desolator") || it.name?.includes("Опустошитель") || it.bonus?.minus_armor));
    const hasAC = Object.values(eq).some(it => it && (it.name?.includes("Assault") || it.name?.includes("Штурма") || it.bonus?.minus_armor_aura));
    if (hasDeso) {
      if (!boss.desoDebuff) {
        spawnFloatingText(boss.x, boss.y - 30, "🩸 -10 БРОНИ (DESOLATOR)", "#dc2626");
      }
      boss.desoDebuff = 300; // 5 seconds debuff
    }
    const totalArmorShred = (boss.desoDebuff > 0 ? 10 : 0) + (hasAC ? 10 : 0);
    const effectiveArmor = Math.max(0, bossDefense - totalArmorShred);

    // Hyperbolic armor reduction: DR = armor / (armor + 100)
    const armorDR = effectiveArmor / (effectiveArmor + 100);

    // Apply defense reduction to raw damage
    let afterArmor = Math.max(1, Math.floor(rawDmg * (1.0 - armorDR)));

    // Passive Item: MKB True Strike & Pure Bonus (+120 pure damage that ignores armor)
    const hasMkb = Object.values(eq).some(it => it && (it.name?.includes("Monkey") || it.name?.includes("Обезьян") || it.bonus?.pure_proc));
    if (hasMkb && Math.random() < 0.75) {
      afterArmor += 120;
      spawnFloatingText(boss.x, boss.y - 40, "🎯 MKB +120 ПИРС!", "#38bdf8");
    }

    // Passive Item: Mjollnir Chain Lightning (25% chance for 220 electric burst)
    const hasMjollnir = Object.values(eq).some(it => it && (it.name?.includes("Mjollnir") || it.name?.includes("Мьёльнир") || it.bonus?.lightning_proc));
    if (hasMjollnir && Math.random() < 0.25) {
      afterArmor += 220;
      spawnFloatingText(boss.x, boss.y - 35, "⚡ МЬЁЛЬНИР -220!", "#38bdf8");
      if (!ARENA.shockwaves) ARENA.shockwaves = [];
      ARENA.shockwaves.push({ x: boss.x, y: boss.y, radius: 15, maxRadius: 55, alpha: 0.9, color: "#38bdf8" });
    }

    // Passive Item: Eye of Skadi (Slows boss movement and attacks by 40%)
    const hasSkadi = Object.values(eq).some(it => it && (it.name?.includes("Skadi") || it.name?.includes("Скади") || it.bonus?.frost_slow));
    if (hasSkadi) {
      if (!boss.skadiSlow) {
        spawnFloatingText(boss.x, boss.y - 25, "❄️ СКАДИ -40% СКОРОСТЬ", "#38bdf8");
      }
      boss.skadiSlow = 240;
      boss.speed = Math.max(0.70, (boss.baseSpeed || 1.45) * 0.60);
    }

    // Stagger bonus (+50% damage when boss is staggered / poise broken)
    const staggerMult = boss.isStaggered ? 1.5 : 1.0;

    // Passive Item: Daedalus Crit Multiplier
    const hasDaedalus = Object.values(eq).some(it => it && (it.name?.includes("Daedalus") || it.name?.includes("Даэдалус") || it.bonus?.crit_mult));
    let critMult = isCrit ? (hasDaedalus ? 2.5 : 1.5) : 1.0;

    let finalDmg = Math.max(1, Math.floor(afterArmor * staggerMult * critMult));

    // Single-hit sanity cap (protects against one-shot exploits or overflow bugs, up to 50% boss max HP per hit)
    const maxSingleHit = Math.max(5000, Math.floor((boss.maxHp || 1000) * 0.50));
    finalDmg = Math.min(finalDmg, maxSingleHit);

    const curBossHp = (!isNaN(boss.hp) && boss.hp > 0) ? boss.hp : (boss.maxHp || 1000);
    boss.hp = Math.max(0, curBossHp - finalDmg);

    // Passive Item: Satanic & General Lifesteal (only heals living player)
    const lifestealPct = stats.lifesteal || 0;
    if (p && !p.isDead && typeof p.currentHp === "number" && p.currentHp > 0 && lifestealPct > 0) {
      const pMax = p.maxHp || 500;
      const rawHeal = Math.floor(finalDmg * (lifestealPct / 100));
      const heal = Math.max(1, Math.min(Math.floor(pMax * 0.05), 5000, rawHeal));
      p.currentHp = Math.min(pMax, p.currentHp + heal);
      if (ARENA.frameCount % 10 === 0) {
        spawnFloatingText(p.x, p.y - 25, `+${heal} HP 🩸`, "#22c55e");
      }
    }

    // BOSS PHASES (Epic Boss Phase Transitions):
    // Phase 2 at 66% HP: Boss Enrages, gains speed and a radial shockwave!
    const hpRatio = boss.hp / boss.maxHp;
    if (hpRatio <= 0.66 && !boss._phase2Triggered) {
      boss._phase2Triggered = true;
      boss.enrageStage = "angry";
      boss.speed = (boss.speed || 1.4) * 1.15;
      spawnFloatingText(boss.x, boss.y - 45, "🔥 БОСС ВПАДАЕТ В ЯРОСТЬ! ФАЗА 2!", "#ea580c");
      triggerHaptic("heavy");
      if (ARENA.cameraTrauma !== undefined) ARENA.cameraTrauma = 0.65;
      if (!ARENA.shockwaves) ARENA.shockwaves = [];
      ARENA.shockwaves.push({ x: boss.x, y: boss.y, radius: 10, maxRadius: 90, alpha: 1.0, color: "#ea580c" });
    }
    // Phase 3 at 33% HP: Desperation Frenzy!
    if (hpRatio <= 0.33 && !boss._phase3Triggered) {
      boss._phase3Triggered = true;
      boss.enrageStage = "enraged";
      boss.speed = (boss.speed || 1.4) * 1.20;
      spawnFloatingText(boss.x, boss.y - 45, "⚡ СМЕРТЕЛЬНАЯ ФАЗА! БОСС БЕЗУМЕН!", "#ef4444");
      triggerHaptic("heavy");
      if (ARENA.cameraTrauma !== undefined) ARENA.cameraTrauma = 0.85;
      if (!ARENA.shockwaves) ARENA.shockwaves = [];
      ARENA.shockwaves.push({ x: boss.x, y: boss.y, radius: 10, maxRadius: 120, alpha: 1.0, color: "#ef4444" });
    }

    if (boss.hp <= 0 && ARENA.isRaidBossBattle && ARENA.waveState !== "boss_victory") {
      handleRaidBossDefeat();
    }

    return finalDmg;
  }

  // UNIVERSAL SAFE DAMAGE: Routes all damage through applyDamageToBoss if target is a boss!
  function safeDamageCreep(c, rawDmg, isCrit) {
    if (!c || c.hp <= 0 || isNaN(c.hp)) return 0;
    if (rawDmg == null || isNaN(rawDmg) || rawDmg <= 0) return 0;
    if (c.isBoss) {
      return applyDamageToBoss(c, rawDmg, isCrit);
    }
    const dmg = Math.max(1, Math.floor(rawDmg));
    c.hp = Math.max(0, c.hp - dmg);
    return dmg;
  }

  function calculateBossAttackDamage(boss, baseMult = 1.0) {
    if (!boss) return 50;
    const p = ARENA.player;
    const stats = RPG_STATE.profile?.stats || {};
    const def = Math.max(0, stats.defense || 5);

    // Real boss attack: from entity, template, or tier scaling fallback
    const BOSS_TIER_ATK = {
      golem: 140, lich: 210, tormentor: 320, dragon: 500, pudge_boss: 800,
      faceless_void: 1250, roshan: 1950, tidehunter: 3000, sf_boss: 4600,
      necrophos: 7000, terrorblade: 11000, invoker_boss: 17500, chaos_knight: 26500,
      dark_tormentor: 42000, storm_spirit: 64000, doom: 98000, primal_beast: 150000,
      phantom_roshan: 230000, tinker_boss: 350000, enigma: 500000
    };
    let bossAtk = boss.atk || boss.baseAtk;
    if (!bossAtk) {
      const bId = ((boss && (boss.id || boss.bossType || boss.name)) || "golem").toLowerCase();
      for (const [k, v] of Object.entries(BOSS_TIER_ATK)) {
        if (bId.includes(k)) { bossAtk = v; break; }
      }
      bossAtk = bossAtk || 140;
    }

    // Phase Enrage multiplier (when boss is enraged/furious/angry or in God Mode)
    let enrageMult = 1.0;
    const isGod = boss.isGodMode || boss.enrageStage === "god_mode";
    if (isGod) enrageMult = 15.0;
    else if (boss.enrageStage === "enraged") enrageMult = 1.40;
    else if (boss.enrageStage === "furious") enrageMult = 1.25;
    else if (boss.enrageStage === "angry") enrageMult = 1.15;

    let rawDmg = Math.floor(bossAtk * baseMult * enrageMult);

    // Hyperbolic player defense reduction: DR = def / (def + 80), max 80%
    const dr = isGod ? 0 : Math.min(0.80, (def * 1.0) / (def + 80));
    let finalDmg = Math.max(10, Math.floor(rawDmg * (1.0 - dr)));

    if (isGod) {
      const pMax = p ? (p.maxHp || stats.hp_max || 1000) : 1000;
      finalDmg = Math.max(finalDmg, Math.floor(pMax * 0.70));
    }

    if (p && p.isBlocking && !isGod) {
      finalDmg = Math.floor(finalDmg * 0.40);
    }

    return finalDmg;
  }

  function applyDamageToPlayer(rawDmg, attackType = "normal") {
    const p = ARENA.player;
    if (!p || p.isDead || (typeof p.currentHp === "number" && p.currentHp <= 0) || (typeof p.isInvulnerable === "number" && p.isInvulnerable > 0)) return 0;

    const stats = RPG_STATE.profile?.stats || {};
    const eq = RPG_STATE.profile?.equipment || {};

    const isMagic = (attackType === "magic" || attackType === "spell" || attackType === "burn" || attackType === "poison" ||
      attackType === "beam" || attackType === "chain_frost" || attackType === "danger_zone" || attackType === "black_hole" ||
      attackType === "doom" || attackType === "sunder");

    // 1. Evasion (for physical/attack hits) & Boss MKB (20% pierce chance)
    const canEvade = !isMagic;
    const dodgeChance = Math.min(70, stats.dodge_chance || 0);
    const bossMkbProcced = canEvade && (Math.random() < 0.20);
    
    if (canEvade && !bossMkbProcced && dodgeChance > 0 && Math.random() * 100 < dodgeChance) {
      spawnFloatingText(p.x, p.y - 25, "💨 УВОРОТ!", "#38bdf8");
      triggerHaptic("light");
      // PA PERK: Blur Heal (Restores 2.5% max HP on dodge, capped)
      if (window.hasTalentPerk && window.hasTalentPerk("perk_blur_heal")) {
        const healAmt = Math.max(1, Math.min(Math.floor((p.maxHp || 500) * 0.025), 3000));
        p.currentHp = Math.min(p.maxHp || 500, (p.currentHp || 0) + healAmt);
        spawnFloatingText(p.x, p.y - 45, `💚 +${healAmt} (РАЗМЫТИЕ)`, "#10b981");
      }
      return 0;
    }

    // 2. Passive Item: Radiance Blind (17% chance boss misses attack, bypassable by MKB)
    const hasRadiance = Object.values(eq).some(it => it && (it.name?.includes("Radiance") || it.name?.includes("Сияние") || it.bonus?.miss_aura));
    if (hasRadiance && canEvade && !bossMkbProcced && Math.random() < 0.17) {
      spawnFloatingText(p.x, p.y - 25, "💨 ПРОМАХ БОССА!", "#f59e0b");
      triggerHaptic("light");
      return 0;
    }

    // Juggernaut PERK: Blade Parry (15% chance to parry boss/creep melee attack and counter-attack)
    if (window.hasTalentPerk && window.hasTalentPerk("perk_blade_parry") && canEvade && Math.random() < 0.15) {
      spawnFloatingText(p.x, p.y - 25, "⚔️ ПАРИРОВАНИЕ КЛИНКОМ!", "#f59e0b");
      triggerHaptic("medium");
      const counterDmg = Math.max(10, Math.floor((stats.attack || 50) * 1.5));
      if (ARENA.isBossActive && ARENA.bossEntity && ARENA.bossEntity.hp > 0) {
        applyDamageToBoss(ARENA.bossEntity, counterDmg, true);
        spawnFloatingText(ARENA.bossEntity.x, ARENA.bossEntity.y - 25, `💥 КОНТРАТАКА -${counterDmg}!`, "#eab308");
      } else if (ARENA.creeps && ARENA.creeps.length > 0) {
        const tgt = ARENA.creeps.find(c => c.hp > 0);
        if (tgt) {
          safeDamageCreep(tgt, counterDmg);
          spawnFloatingText(tgt.x, tgt.y - 25, `💥 КОНТРАТАКА -${counterDmg}!`, "#eab308");
        }
      }
      return 0;
    }

    let finalDmg = Math.max(1, rawDmg);

    // 3. Magic Resistance: Reducts all magic, elemental and spell damage (up to 80% cap)
    if (isMagic) {
      const mr = Math.min(80, Math.max(0, stats.magic_resist || 0));
      if (mr > 0) {
        finalDmg = Math.max(1, Math.floor(finalDmg * (1.0 - mr / 100)));
      }
    }

    // 4. Passive Item: Vanguard / Crimson Guard Damage Block (70% chance, capped at 50% on bosses)
    const damageBlock = stats.damage_block || 0;
    if (damageBlock > 0 && Math.random() < 0.70) {
      const isBossEncounter = !!(ARENA.isRaidBossBattle || ARENA.isBossActive || ARENA.bossArenaMode);
      const effectiveBlock = isBossEncounter ? Math.min(damageBlock, Math.floor(finalDmg * 0.50)) : damageBlock;
      finalDmg = Math.max(1, finalDmg - effectiveBlock);
      spawnFloatingText(p.x, p.y - 20, `🛡️ БЛОК -${effectiveBlock} (АВАНГАРД)`, "#94a3b8");
    }

    // 5. Passive Item: Blade Mail Damage Return (Reflect 35% damage back to boss)
    const reflectPct = stats.reflect || 0;
    if (reflectPct > 0) {
      const reflectDmg = Math.max(1, Math.floor(rawDmg * (reflectPct / 100)));
      if (ARENA.isRaidBossBattle && ARENA.bossEntity && ARENA.bossEntity.hp > 0) {
        applyDamageToBoss(ARENA.bossEntity, reflectDmg);
        spawnFloatingText(ARENA.bossEntity.x, ARENA.bossEntity.y - 25, `🪞 ВОЗВРАТКА -${reflectDmg}!`, "#c084fc");
      } else if (ARENA.creeps && ARENA.creeps.length > 0) {
        const targetCreep = ARENA.creeps.find(c => c.hp > 0);
        if (targetCreep) {
          safeDamageCreep(targetCreep, reflectDmg);
          spawnFloatingText(targetCreep.x, targetCreep.y - 25, `🪞 ВОЗВРАТКА -${reflectDmg}!`, "#c084fc");
        }
      }
    }

    const pMax = Math.max(100, p.maxHp || 500);
    const nowFrame = ARENA.frameCount || 0;

    // Leshrac PERK: Earth Armor (Stone skin reduces physical damage up to 30% on low HP)
    if (window.hasTalentPerk && window.hasTalentPerk("perk_earth_armor") && !isMagic) {
      const missingPct = Math.max(0, 1 - ((p.currentHp || 0) / pMax));
      const armorReductionPct = Math.min(30, Math.floor((missingPct * 100) / 3));
      if (armorReductionPct > 0) {
        finalDmg = Math.max(1, Math.floor(finalDmg * (1 - armorReductionPct / 100)));
      }
    }

    // Invoker PERK: Mana Shield (30% incoming damage absorbed by MP: 1 MP = 2 HP)
    if (window.hasTalentPerk && window.hasTalentPerk("perk_mana_shield") && (p.currentMp || 0) > 0 && finalDmg > 1) {
      const absorbTarget = Math.floor(finalDmg * 0.30);
      const neededMp = Math.ceil(absorbTarget / 2);
      const usedMp = Math.min(p.currentMp, neededMp);
      const actualAbsorbed = usedMp * 2;
      p.currentMp = Math.max(0, p.currentMp - usedMp);
      finalDmg = Math.max(1, finalDmg - actualAbsorbed);
      if (actualAbsorbed > 0 && Math.random() < 0.35) {
        spawnFloatingText(p.x, p.y - 35, `🔮 ЩИТ РАЗУМА -${actualAbsorbed}`, "#818cf8");
      }
    }

    // Anti-Mage PERK: Blink Reflex (Auto-blinks with i-frame if taking >20% max HP)
    if (window.hasTalentPerk && window.hasTalentPerk("perk_blink_reflex") && finalDmg >= pMax * 0.20 && (!ARENA.blinkReflexCd || nowFrame > ARENA.blinkReflexCd)) {
      ARENA.blinkReflexCd = nowFrame + 1200; // 20s cooldown
      p.isInvulnerable = 30; // 0.5s i-frame
      spawnFloatingText(p.x, p.y - 35, "⚡ РЕФЛЕКС СКАЧКА!", "#a855f7");
      triggerHaptic("heavy");
      return 0;
    }

    // 6. PET PHOENIX: Supernova Lethal Protection (Saves from death every 30s)
    const equippedPet = (RPG_STATE.profile?.pets || []).find(pt => pt.is_equipped);
    const petType = equippedPet ? (equippedPet.type || equippedPet.pet_id) : localStorage.getItem("rpg_active_pet");
    if (petType === "phoenix" && finalDmg >= p.currentHp && (!p._phoenixShieldFrame || (ARENA.frameCount || 0) - p._phoenixShieldFrame > 1800)) {
      p._phoenixShieldFrame = ARENA.frameCount || 0;
      p.isInvulnerable = 180; // 3 seconds of immunity
      p.currentHp = Math.max(1, Math.floor(pMax * 0.35));
      spawnFloatingText(p.x, p.y - 30, "🦅 СВЕРХНОВАЯ ЗАЩИТА!", "#f59e0b");
      triggerHaptic("heavy");
      return 0;
    }

    // 7. HEALTH GATE PROTECTION:
    // Saves player ONCE per 60s from an unexpected lethal hit if they were at high health (>60% HP)
    const bossIsGod = ARENA.bossEntity && (ARENA.bossEntity.isGodMode || ARENA.bossEntity.enrageStage === "god_mode");
    if (!bossIsGod && p.currentHp > pMax * 0.60 && finalDmg >= p.currentHp && (!p._lastHealthGateFrame || nowFrame - p._lastHealthGateFrame > 3600)) {
      p._lastHealthGateFrame = nowFrame;
      finalDmg = Math.max(1, p.currentHp - 1);
      p.currentHp = 1;
      p.isInvulnerable = 18; // Brief 0.3s window to react
      spawnFloatingText(p.x, p.y - 30, "🛡️ СПАСЕНИЕ ОТ ВАНШОТА!", "#38bdf8");
      triggerHaptic("heavy");
      return finalDmg;
    }

    p.currentHp = Math.max(0, p.currentHp - finalDmg);
    if (p.currentHp <= 0) {
      p.currentHp = 0;
      p.isDead = true;
      p.isInvulnerable = 0;
      handlePlayerArenaDeath();
    }
    return finalDmg;
  }

  function setupArenaListeners(canvas) {
    function handleCanvasTap(cx, cy, screenX, screenY) {
      if (ARENA.waveState === "boss_victory") {
        const reward = RPG_STATE.lastBossChestReward;
        ARENA.waveState = "fighting";
        ARENA.isRaidBossBattle = false;
        ARENA._wasRaidBossBattle = true;
        RPG_STATE.lastBossChestReward = null;
        if (reward) {
          openChestModal(reward);
        } else {
          exitRaidBossBattle();
        }
        return;
      }
      if (ARENA.fallingChest && ARENA.fallingChest.landed && !ARENA.fallingChest.opened) {
        const fc = ARENA.fallingChest;
        if (Math.hypot(cx - fc.x, cy - fc.y) < 65) {
          fc.opened = true;
          if (RPG_STATE.lastBossChestReward) {
            openChestModal(RPG_STATE.lastBossChestReward);
          }
          return;
        }
      }
      if (ARENA.waveState === "boss_defeat") {
        const tapX = screenX !== undefined ? screenX : cx;
        const tapY = screenY !== undefined ? screenY : cy;
        if (ARENA._bossDefeatRetryBounds) {
          const rb = ARENA._bossDefeatRetryBounds;
          if (tapX >= rb.x - 10 && tapX <= rb.x + rb.w + 10 && tapY >= rb.y - 8 && tapY <= rb.y + rb.h + 8) {
            triggerHaptic("medium");
            if (ARENA.isRaidBossBattle && ARENA.currentRaidBoss && ARENA.currentRaidBoss.id) {
              startRaidBossActionBattle(ARENA.currentRaidBoss.id);
            } else {
              retryCurrentFloor();
            }
            return;
          }
        }
        if (ARENA._bossDefeatExitBounds) {
          const eb = ARENA._bossDefeatExitBounds;
          if (tapX >= eb.x - 10 && tapX <= eb.x + eb.w + 10 && tapY >= eb.y - 8 && tapY <= eb.y + eb.h + 8) {
            triggerHaptic("medium");
            if (ARENA.isRaidBossBattle) {
              exitRaidBossBattle();
            } else {
              retryCurrentFloor();
            }
            return;
          }
        }
        return;
      }
      if (ARENA.waveState === "prompt" || ARENA.waveState === "retry_prompt") {
        if (ARENA.waveState === "retry_prompt") {
          retryCurrentFloor();
        } else {
          if (ARENA._promptDisableBtnBounds) {
            const db = ARENA._promptDisableBtnBounds;
            if (cx >= db.x && cx <= db.x + db.w && cy >= db.y && cy <= db.y + db.h) {
              if (window.RPG && window.RPG.toggleArenaWaveConfirm) {
                if (!ARENA.autoAdvanceWaves) {
                  window.RPG.toggleArenaWaveConfirm();
                } else {
                  confirmNextWave();
                }
                return;
              }
            }
          }
          confirmNextWave();
        }
        return;
      }
      if (ARENA.isBossActive && ARENA._partyBtnBounds) {
        const pb = ARENA._partyBtnBounds;
        if (cx >= pb.x && cx <= pb.x + pb.w && cy >= pb.y && cy <= pb.y + pb.h) {
          window.RPG.toggleBossPartyMode();
          return;
        }
      }
      if (ARENA.blockWindowActive) {
        playerBlock();
        return;
      }
      if (ARENA.qteActive) {
        hitQTE();
        return;
      }
      if (ARENA.waveState === "fighting") {
        if (ARENA.topDownMode || ARENA.isRaidBossBattle) {
          fireTopDownAttack({ cx, cy });
        } else {
          playerSlashAttack();
        }
      }
    }

    function getEventArenaCoords(clientX, clientY) {
      const rect = canvas.getBoundingClientRect();
      const clientW = ARENA.cachedClientW || canvas.clientWidth || (rect.width > 50 ? rect.width : 360);
      const clientH = ARENA.cachedClientH || canvas.clientHeight || (rect.height > 50 ? rect.height : 320);
      const screenX = (clientX - rect.left) * (clientW / (rect.width || clientW));
      const screenY = (clientY - rect.top) * (clientH / (rect.height || clientH));

      if (ARENA.topDownMode || ARENA.isRaidBossBattle) {
        const zoom = Math.min(clientW / 520, clientH / 720);
        const offX = (clientW - 520 * zoom) / 2;
        const offY = (clientH - 720 * zoom) / 2;
        return {
          cx: Math.max(0, Math.min(520, (clientX - rect.left - offX) / zoom)),
          cy: Math.max(0, Math.min(720, (clientY - rect.top - offY) / zoom)),
          screenX,
          screenY
        };
      }
      return {
        cx: (clientX - rect.left) * (ARENA.width / (rect.width || 360)),
        cy: (clientY - rect.top) * (ARENA.height / (rect.height || 320)),
        screenX,
        screenY
      };
    }

    canvas.onclick = (e) => {
      const { cx, cy, screenX, screenY } = getEventArenaCoords(e.clientX, e.clientY);
      handleCanvasTap(cx, cy, screenX, screenY);
    };

    canvas.ontouchstart = (e) => {
      e.preventDefault();
      const touch = e.changedTouches[0];
      const { cx, cy, screenX, screenY } = getEventArenaCoords(touch.clientX, touch.clientY);
      handleCanvasTap(cx, cy, screenX, screenY);
    };

    // Boss arena movement: touchmove for continuous direction
    canvas.ontouchmove = (e) => {
      e.preventDefault();
      // No manual movement in 2D side-scroller anymore!
    };

    canvas.ontouchend = (e) => {
      e.preventDefault();
      if (ARENA.bossArenaMode) {
        const touch = Array.from(e.changedTouches).find(t => t.identifier === ARENA._touchMoveId);
        if (touch) {
          ARENA.moveInput.left = false;
          ARENA.moveInput.right = false;
          ARENA._touchMoveId = null;
        }
      }
    };

    window.onkeyup = (e) => {
      const k = e.key.toLowerCase();
      if (ARENA.keysPressed) {
        delete ARENA.keysPressed[k];
        if (ARENA.topDownMode || ARENA.isRaidBossBattle) {
          let kx = 0, ky = 0;
          if (ARENA.keysPressed["w"] || ARENA.keysPressed["arrowup"]) ky -= 1;
          if (ARENA.keysPressed["s"] || ARENA.keysPressed["arrowdown"]) ky += 1;
          if (ARENA.keysPressed["a"] || ARENA.keysPressed["arrowleft"]) kx -= 1;
          if (ARENA.keysPressed["d"] || ARENA.keysPressed["arrowright"]) kx += 1;
          const kmag = Math.hypot(kx, ky);
          if (kmag > 0) {
            ARENA.joystick.dx = kx / kmag;
            ARENA.joystick.dy = ky / kmag;
            ARENA.player.isMoving = true;
            ARENA.player.facingAngle = Math.atan2(ky, kx);
          } else {
            ARENA.joystick.dx = 0;
            ARENA.joystick.dy = 0;
            ARENA.player.isMoving = false;
          }
        }
      }
      if (!ARENA.bossArenaMode) return;
      if (k === "a" || k === "arrowleft") ARENA.moveInput.left = false;
      if (k === "d" || k === "arrowright") ARENA.moveInput.right = false;
    };

    window.onkeydown = (e) => {
      if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.isContentEditable)) return;
      if (RPG_STATE.activeTab !== "farm" || RPG_STATE.farmMode !== "arena") return;
      const k = e.key.toLowerCase();

      // WASD / Arrow keys for Top-Down free movement
      if (ARENA.topDownMode || ARENA.isRaidBossBattle) {
        if (!ARENA.keysPressed) ARENA.keysPressed = {};
        if (["w", "arrowup", "s", "arrowdown", "a", "arrowleft", "d", "arrowright"].includes(k)) {
          ARENA.keysPressed[k] = true;
          let kx = 0, ky = 0;
          if (ARENA.keysPressed["w"] || ARENA.keysPressed["arrowup"]) ky -= 1;
          if (ARENA.keysPressed["s"] || ARENA.keysPressed["arrowdown"]) ky += 1;
          if (ARENA.keysPressed["a"] || ARENA.keysPressed["arrowleft"]) kx -= 1;
          if (ARENA.keysPressed["d"] || ARENA.keysPressed["arrowright"]) kx += 1;

          const kmag = Math.hypot(kx, ky);
          if (kmag > 0) {
            ARENA.joystick.dx = kx / kmag;
            ARENA.joystick.dy = ky / kmag;
            ARENA.joystick.power = 1.0;
            ARENA.player.isMoving = true;
            ARENA.player.facingAngle = Math.atan2(ky, kx);
          } else {
            ARENA.joystick.dx = 0;
            ARENA.joystick.dy = 0;
            ARENA.player.isMoving = false;
          }
          e.preventDefault();
          return;
        }
        if (k === "shift" || k === "c") {
          playerPerformDashRoll();
          e.preventDefault();
          return;
        }
      }
      // Boss Arena Movement (A/D or Arrows)
      if (ARENA.bossArenaMode) {
        if (k === "a" || k === "arrowleft") { ARENA.moveInput.left = true; e.preventDefault(); return; }
        if (k === "d" || k === "arrowright") { ARENA.moveInput.right = true; e.preventDefault(); return; }
        if (k === "shift" || k === "c") { playerBossArenaDodge(); e.preventDefault(); return; }
      }
      if (k === " " || k === "spacebar" || k === "enter") {
        e.preventDefault();
        if (ARENA.waveState === "prompt") {
          confirmNextWave();
        } else if (ARENA.waveState === "retry_prompt") {
          retryCurrentFloor();
        } else if (ARENA.waveState === "boss_defeat") {
          if (ARENA.currentRaidBoss && ARENA.currentRaidBoss.id) {
            startRaidBossActionBattle(ARENA.currentRaidBoss.id);
          } else {
            exitRaidBossBattle();
          }
        } else if (ARENA.blockWindowActive) {
          playerBlock();
        } else if (ARENA.qteActive) {
          hitQTE();
        } else {
          playerSlashAttack();
        }
      } else if (k === "e") {
        castPlayerSkill1();
      } else if (k === "q") {
        castPlayerUltimate();
      } else if (k === "f") {
        usePlayerPotion();
      } else if (k === "r" || k === "1") {
        useActiveItemAction(0);
      } else if (k === "t" || k === "2") {
        useActiveItemAction(1);
      } else if (k === "shift" || k === "c") {
        playerPerformDash();
      } else if (k === "b") {
        playerBlock();
      }
    };
  }

  function startArenaLoop() {
    stopArenaLoop();
    if (ARENA.startLoopTimeout) {
      cancelAnimationFrame(ARENA.startLoopTimeout);
      clearTimeout(ARENA.startLoopTimeout);
      ARENA.startLoopTimeout = null;
    }
    const canvas = document.getElementById("rpg-action-canvas");
    if (canvas) {
      const r = canvas.getBoundingClientRect();
      const hasSize = (r.width > 50) || (canvas.clientWidth > 50);
      if (!hasSize) {
        // Canvas not laid out yet — retry on next frame
        ARENA.startLoopTimeout = requestAnimationFrame(() => startArenaLoop());
        return;
      }
      const isBossFightActive = !!((ARENA.isRaidBossBattle || ARENA.isBossActive) && ARENA.bossEntity);
      if (!isBossFightActive) {
        initArenaCanvas();
      } else if (!ARENA.ctx || ARENA.canvas !== canvas) {
        bindArenaCanvas(canvas);
      }
    }
    ARENA.running = true;
    function loop() {
      if (!ARENA.running) return;
      try {
        updateArena();
        renderArena();
      } catch (err) {
        console.error("Arena animation frame error:", err);
      }
      if (ARENA.running) {
        ARENA.animId = requestAnimationFrame(loop);
      }
    }
    ARENA.animId = requestAnimationFrame(loop);
  }

  function stopArenaLoop() {
    ARENA.running = false;
    if (ARENA.animId) {
      cancelAnimationFrame(ARENA.animId);
      ARENA.animId = null;
    }
    if (ARENA.startLoopTimeout) {
      cancelAnimationFrame(ARENA.startLoopTimeout);
      clearTimeout(ARENA.startLoopTimeout);
      ARENA.startLoopTimeout = null;
    }
  }

  // ---------------------------------------------------------------------------
  // MAIN GAME LOOP UPDATE
  // ---------------------------------------------------------------------------


  function updateArena() {
    ARENA.frameCount = (ARENA.frameCount || 0) + 1;
    const p = ARENA.player;

    // Hitstop freeze (Sekiro/Hollow Knight impact pause)
    if (ARENA.hitstop > 0) {
      ARENA.hitstop--;
      updateFloatingTexts();
      return;
    }

    // Decrement parry & block timers
    if (ARENA.parryWindow > 0) ARENA.parryWindow--;
    if (ARENA.player.blockTimer > 0) {
      ARENA.player.blockTimer--;
      if (ARENA.player.blockTimer <= 0) ARENA.player.isBlocking = false;
    }

    // Always update physical loot coins & falling legendary chest
    updatePhysicalCoins();
    updateFallingChest();
    updatePetLogic();

    // Sync DOM action buttons smoothly (cooldowns & block alert)
    if (ARENA.frameCount % 6 === 0) {
      const s1El = document.getElementById("rpg-cd-skill1");
      if (s1El) {
        const s1Sec = ARENA.skill1Cooldown > 0 ? Math.ceil(ARENA.skill1Cooldown / 60) : 0;
        const txt = s1Sec > 0 ? `${s1Sec}с` : "Скилл 1";
        if (s1El.textContent !== txt) s1El.textContent = txt;
        const btn1 = document.getElementById("rpg-btn-skill1");
        if (btn1) btn1.style.opacity = s1Sec > 0 ? "0.6" : "1";
      }
      const potEl = document.getElementById("rpg-cd-potion");
      if (potEl) {
        const potSec = ARENA.potionCooldown > 0 ? Math.ceil(ARENA.potionCooldown / 60) : 0;
        const txt = potSec > 0 ? `${potSec}с` : "";
        if (potEl.textContent !== txt) potEl.textContent = txt;
        const btnPot = document.getElementById("rpg-btn-potion");
        if (btnPot) btnPot.style.opacity = potSec > 0 ? "0.6" : "1";
      }
      const ultEl = document.getElementById("rpg-cd-ult");
      if (ultEl) {
        let txt = "Ульта";
        const hClass = (RPG_STATE.profile?.hero_class || "").toLowerCase();
        if (hClass === "leshrac") {
          if (p.largoRhapsodyActive) {
            txt = "ВЫКЛ";
          } else {
            const ultSec = ARENA.ultCooldown > 0 ? Math.ceil(ARENA.ultCooldown / 60) : 0;
            txt = ultSec > 0 ? `${ultSec}с` : "ВКЛ";
          }
        } else {
          const ultSec = ARENA.ultCooldown > 0 ? Math.ceil(ARENA.ultCooldown / 60) : 0;
          txt = ultSec > 0 ? `${ultSec}с` : "Ульта";
        }
        if (ultEl.textContent !== txt) ultEl.textContent = txt;
        const btnUlt = document.getElementById("rpg-btn-ult");
        if (btnUlt) {
          if (hClass === "leshrac" && p.largoRhapsodyActive) {
            btnUlt.style.opacity = "1";
            btnUlt.style.borderColor = "#22c55e";
          } else {
            const ultSec = ARENA.ultCooldown > 0 ? Math.ceil(ARENA.ultCooldown / 60) : 0;
            btnUlt.style.opacity = ultSec > 0 ? "0.6" : "1";
            btnUlt.style.borderColor = "";
          }
        }
      }

      // Sync Active Item Cooldowns
      const activeItems = getEquippedActiveItems();
      activeItems.forEach((act, idx) => {
        const cdEl = document.getElementById(`rpg-cd-item-${idx}`);
        const btnEl = document.getElementById(`rpg-btn-item-${idx}`);
        const cdFrames = ARENA.itemCooldowns?.[act.key] || 0;
        const cdSec = cdFrames > 0 ? Math.ceil(cdFrames / 60) : 0;
        const hotkey = idx === 0 ? "R" : idx === 1 ? "T" : `${idx + 1}`;
        if (cdEl) {
          const txt = cdSec > 0 ? `КД ${cdSec}с` : `[${hotkey}] Готов ⚡`;
          if (cdEl.textContent !== txt) cdEl.textContent = txt;
        }
        if (btnEl) {
          btnEl.style.opacity = cdSec > 0 ? "0.6" : "1";
        }
      });
      const blockBtn = document.getElementById("rpg-btn-block");
      if (blockBtn) {
        if (ARENA.blockWindowActive) {
          blockBtn.className = "w-11 h-11 rounded-2xl bg-blue-500 border-2 border-white animate-bounce shadow-blue-500/50 text-white font-black text-sm flex flex-col items-center justify-center shadow-lg active:scale-90 transition-all";
        } else {
          blockBtn.className = "w-11 h-11 rounded-2xl bg-slate-800/90 border border-slate-600 text-white font-black text-sm flex flex-col items-center justify-center shadow-lg active:scale-90 transition-all";
        }
      }
    }
    // Non-fighting state handling
    if (ARENA.waveState !== "fighting") {
      if (ARENA.waveState === "wave_clear" || ARENA.waveState === "boss_intro") {
        ARENA.waveTransitionTimer--;
        if (ARENA.waveTransitionTimer <= 0) {
          if (ARENA.waveState === "wave_clear") {
            if (ARENA.autoAdvanceWaves && !RPG_STATE.activeChestModal) {
              ARENA.waveState = "prompt";
              confirmNextWave();
            } else {
              ARENA.waveState = "prompt";
            }
          } else {
            ARENA.waveState = "fighting";
          }
        }
      }
      updatePickups();
      updateFloatingTexts();
      updateClouds();
      return;
    }

    const stats = RPG_STATE.profile?.stats || {};

    // =========================================================================
    // TOP-DOWN ARCHERO-STYLE UPDATE LOOP
    // =========================================================================
    if (ARENA.topDownMode || ARENA.isRaidBossBattle) {
      // 0. Update player status effects (Stun, Freeze, Slow, DoTs)
      if (p.stunTimer > 0) p.stunTimer--;
      if (p.freezeTimer > 0) p.freezeTimer--;
      const isImmobilized = (p.stunTimer > 0) || (p.freezeTimer > 0) || p.isFrozenInTime;

      // 1. Dynamic walking speed (slowed if slowTimer active)
      let moveSpeed = 3.35 * (1.0 + Math.min(0.25, (stats.agility || 10) * 0.002));
      if (p.slowTimer > 0) {
        p.slowTimer--;
        moveSpeed *= (p.slowRatio || 0.45);
      }

      if (!isImmobilized && ARENA.player.isMoving && (Math.abs(ARENA.joystick.dx) > 0.06 || Math.abs(ARENA.joystick.dy) > 0.06)) {
        p.x += ARENA.joystick.dx * moveSpeed;
        p.y += ARENA.joystick.dy * moveSpeed;
        p.x = Math.max(30, Math.min(490, p.x));
        p.y = Math.max(40, Math.min(680, p.y));
      }

      // Continuous Auto-Fire (Run & Gun) — blocked when stunned or frozen!
      const target = (ARENA.bossEntity && ARENA.bossEntity.hp > 0) ? ARENA.bossEntity : (ARENA.creeps.find(c => c.hp > 0) || null);
      if (target && target.hp > 0 && !isImmobilized) {
        // Hero faces the boss in combat
        const toTargetAngle = Math.atan2(target.y - p.y, target.x - p.x);
        p.facingAngle = toTargetAngle;
        p.facing = target.x >= p.x ? 1 : -1;
        p.shootCooldown = (p.shootCooldown || 0) - 1;

        if (p.shootCooldown <= 0) {
          if (p.blindTimer > 0) {
            p.blindTimer--;
            if (Math.random() < 0.65) {
              p.shootCooldown = 26;
              spawnFloatingText(p.x, p.y - 20, "🔴 ПРОМАХ (ОСЛЕПЛЕНИЕ)!", "#ef4444");
            } else {
              fireTopDownAttack(null);
            }
          } else {
            fireTopDownAttack(null);
          }
        }
      }

      // Burn DoT ticking
      if (p.burnTimer > 0) {
        p.burnTimer--;
        if (ARENA.frameCount % 24 === 0) {
          const bDmg = Math.max(10, p.burnDmg || Math.floor(calculateBossAttackDamage(ARENA.bossEntity, 0.16)));
          applyDamageToPlayer(bDmg, "burn");
          spawnFloatingText(p.x, p.y - 20, `🔥 ОЖОГ -${bDmg}`, "#f97316");
          if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
        }
      }
      // Poison DoT ticking
      if (p.poisonTimer > 0) {
        p.poisonTimer--;
        if (ARENA.frameCount % 24 === 0) {
          const psDmg = Math.max(10, p.poisonDmg || Math.floor(calculateBossAttackDamage(ARENA.bossEntity, 0.16)));
          applyDamageToPlayer(psDmg, "poison");
          spawnFloatingText(p.x, p.y - 20, `☣️ ЯД -${psDmg}`, "#84cc16");
          if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
        }
      }
      if (p.silenceTimer > 0) p.silenceTimer--;

      // 2. Dash Cooldown & Invulnerability
      if (ARENA.dodgeCooldown > 0) ARENA.dodgeCooldown--;
      if (p.isInvulnerable > 0) p.isInvulnerable--;

      // 3. Update Top-Down Projectiles with Magnetic Tracking (Never misses moving boss!)
      for (let pi = ARENA.playerProjectiles.length - 1; pi >= 0; pi--) {
        const proj = ARENA.playerProjectiles[pi];
        if (proj.type === "topdown_shot") {
          // Magnetic guidance towards target so shots curve slightly and hit reliably!
          if (proj.target && proj.target.hp > 0) {
            const idealAng = Math.atan2(proj.target.y - proj.y, proj.target.x - proj.x);
            const curAng = Math.atan2(proj.vy, proj.vx);
            let dAng = idealAng - curAng;
            while (dAng < -Math.PI) dAng += Math.PI * 2;
            while (dAng > Math.PI) dAng -= Math.PI * 2;
            const steer = curAng + dAng * 0.38;
            proj.vx = Math.cos(steer) * proj.speed;
            proj.vy = Math.sin(steer) * proj.speed;
          }

          proj.x += proj.vx;
          proj.y += proj.vy;
          proj.distTraveled += proj.speed;

          // Generous hit check against boss (+20px buffer ensures zero whiffs)
          const boss = ARENA.bossEntity;
          if (boss && boss.hp > 0 && Math.hypot(proj.x - boss.x, proj.y - boss.y) < (boss.radius + proj.radius + 20)) {
            const actualDmg = applyDamageToBoss(boss, proj.dmg, proj.isCrit);
            if (boss.poise !== undefined) boss.poise = Math.max(0, boss.poise - (proj.isCrit ? 15 : 8));
            spawnFloatingText(boss.x + (Math.random() * 24 - 12), boss.y - 20, `${proj.isCrit ? "💥 КРИТ! " : ""}-${actualDmg}`, proj.isCrit ? "#ef4444" : "#facc15");
            triggerHaptic(proj.isCrit ? "heavy" : "light");
            ARENA.playerProjectiles.splice(pi, 1);
            continue;
          }

          // Check hit against other creeps
          let hitCreep = false;
          for (const c of ARENA.creeps) {
            if (c !== boss && c.hp > 0 && Math.hypot(proj.x - c.x, proj.y - c.y) < (c.radius + proj.radius + 12)) {
              if (c.isBoss) {
                applyDamageToBoss(c, proj.dmg, proj.isCrit);
              } else {
                safeDamageCreep(c, proj.dmg, false);
              }
              spawnFloatingText(c.x, c.y - 15, `-${proj.dmg}`, "#facc15");
              hitCreep = true;
              break;
            }
          }
          if (hitCreep || proj.distTraveled > proj.maxDist || proj.x < -40 || proj.x > ARENA.width + 40 || proj.y < -40 || proj.y > ARENA.height + 40) {
            ARENA.playerProjectiles.splice(pi, 1);
          }
        }
      }

      // 4. EPIC BOSS ENCOUNTER AI (Dynamic Chase, Signature Abilities & Ultimates)
      const boss = ARENA.bossEntity;
      if (boss && boss.hp > 0) {
        if (typeof updateCustomBossAI === "function") {
          updateCustomBossAI(boss, p, ARENA);
        }
        if (boss.state === "telegraph_melee") {
          boss.stateTimer--;
          if (boss.stateTimer <= 0) {
            boss.state = "melee_smash";
            boss.stateTimer = 22;
            ARENA.cameraTrauma = Math.min(1.0, (ARENA.cameraTrauma || 0) + 0.35);
            triggerHaptic("heavy");
            spawnFloatingText(boss.x, boss.y - 30, "💥 УДАР!", "#ef4444");

            // Damage player if in range (anti-one-shot protected!)
            if (Math.hypot(p.x - boss.x, p.y - boss.y) < (boss.radius + p.radius + 20) && !p.isInvulnerable) {
              const rawDmg = calculateBossAttackDamage(boss, 1.0);
              const actualDmg = applyDamageToPlayer(rawDmg, "melee");
              spawnFloatingText(p.x, p.y - 20, `💥 -${actualDmg}`, "#ef4444");
              if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
            }
            // Damage companions if in range
            for (const comp of (ARENA.bossCompanions || [])) {
              if (comp.hp > 0 && Math.hypot(comp.x - boss.x, comp.y - boss.y) < (boss.radius + 32)) {
                comp.hp = Math.max(0, comp.hp - calculateBossAttackDamage(boss, 0.8));
              }
            }
          }
        }
        else if (boss.state === "melee_smash") {
          boss.stateTimer--;
          if (boss.stateTimer <= 0) boss.state = "chase";
        }
        else if (boss.state === "telegraph_charge") {
          boss.stateTimer--;
          if (boss.stateTimer <= 0) {
            boss.state = "charging";
            boss.stateTimer = 90; // Slower rush duration
          }
        }
        else if (boss.state === "charging") {
          boss.stateTimer--;
          boss.x += boss.chargeVx;
          boss.y += boss.chargeVy;

          // Charge speed trail
          if (ARENA.frameCount % 4 === 0 && ARENA.dashGhosts) {
            ARENA.dashGhosts.push({
              x: boss.x,
              y: boss.y,
              radius: boss.radius,
              alpha: 0.4,
              color: "#ef4444"
            });
          }

          // Hit player during charge!
          if (Math.hypot(p.x - boss.x, p.y - boss.y) < (boss.radius + p.radius + 10) && !p.isInvulnerable) {
            const rawDmg = calculateBossAttackDamage(boss, 1.35);
            const actualDmg = applyDamageToPlayer(rawDmg, "charge");
            // Gentle knockback player away
            p.x += Math.cos(boss.chargeAngle) * 20;
            p.y += Math.sin(boss.chargeAngle) * 20;
            spawnFloatingText(p.x, p.y - 25, `💥 ТАРАН! -${actualDmg}`, "#ef4444");
            ARENA.cameraTrauma = 0.4;
            triggerHaptic("heavy");
            if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
          }

          // Hit arena wall -> STUNNED for 1.5 seconds! (Reward player for baiting charge into wall)
          if (boss.x <= 32 || boss.x >= ARENA.width - 32 || boss.y <= 40 || boss.y >= ARENA.height - 40) {
            boss.state = "stunned";
            boss.stateTimer = 90; // ~1.5s stun
            ARENA.cameraTrauma = 0.5;
            triggerHaptic("heavy");
            spawnFloatingText(boss.x, boss.y - 35, "💫 БОСС ВРЕЗАЛСЯ В СТЕНУ! ОШЕЛОМЛЕН!", "#facc15");
          } else if (boss.stateTimer <= 0) {
            boss.state = "chase";
          }
        }
        else if (boss.state === "stunned") {
          boss.stateTimer--;
          if (boss.stateTimer <= 0) boss.state = "chase";
        }
        else if (boss.state === "barrage") {
          boss.stateTimer--;
          if (boss.stateTimer <= 0) boss.state = "chase";
        }

        // Clamp boss inside 520x720 arena
        boss.x = Math.max(35, Math.min(485, boss.x));
        boss.y = Math.max(45, Math.min(675, boss.y));

        // Direct contact damage if player touches boss while standing
        if (Math.hypot(p.x - boss.x, p.y - boss.y) < (boss.radius + p.radius) && !p.isInvulnerable) {
          if ((ARENA.frameCount % 25) === 0) {
            const rawDmg = calculateBossAttackDamage(boss, 0.65);
            const actualDmg = applyDamageToPlayer(rawDmg, "contact");
            spawnFloatingText(p.x, p.y - 20, `💥 -${actualDmg}`, "#ef4444");
            triggerHaptic("medium");
            if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
          }
        }
      }

      // Update Boss Projectiles (Floating Rockets & Ability Missiles)
      for (let bpi = ARENA.bossProjectiles.length - 1; bpi >= 0; bpi--) {
        const bp = ARENA.bossProjectiles[bpi];
        bp.x += (bp.vx || 0);
        bp.y += (bp.vy || 0);
        bp.timer = (bp.timer || 240) - 1;

        // Hit player (anti-one-shot protected!)
        if (Math.hypot(p.x - bp.x, p.y - bp.y) < (p.radius + bp.radius) && !p.isInvulnerable) {
          const rawDmg = bp.dmg || calculateBossAttackDamage(ARENA.bossEntity, 0.85);
          const actualDmg = applyDamageToPlayer(rawDmg, bp.label || "projectile");
          const lbl = bp.label ? `${bp.label} ` : "💥 СНАРЯД ";
          spawnFloatingText(p.x, p.y - 20, `${lbl}-${actualDmg}`, bp.color || "#ef4444");
          triggerHaptic("heavy");
          ARENA.cameraTrauma = Math.min(1.0, (ARENA.cameraTrauma || 0) + 0.25);
          if (typeof applyStatusEffectToPlayer === "function") {
            applyStatusEffectToPlayer(bp);
          }
          ARENA.bossProjectiles.splice(bpi, 1);
          if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
          continue;
        }

        // Hit companions
        for (const comp of (ARENA.bossCompanions || [])) {
          if (comp.hp > 0 && Math.hypot(comp.x - bp.x, comp.y - bp.y) < (comp.radius + bp.radius)) {
            comp.hp = Math.max(0, comp.hp - (bp.dmg || 40));
            ARENA.bossProjectiles.splice(bpi, 1);
            break;
          }
        }

        // Out of bounds or expired
        if (bp.timer <= 0 || bp.x < 0 || bp.x > ARENA.width || bp.y < 0 || bp.y > ARENA.height) {
          ARENA.bossProjectiles.splice(bpi, 1);
        }
      }

      // 5. Update Dash Ghost Trails
      if (ARENA.dashGhosts) {
        for (let gi = ARENA.dashGhosts.length - 1; gi >= 0; gi--) {
          const g = ARENA.dashGhosts[gi];
          g.alpha -= 0.045;
          if (g.alpha <= 0) ARENA.dashGhosts.splice(gi, 1);
        }
      }
    }

    // ===== BOSS ARENA: Side-Scroller Movement (Only when NOT in Top-Down mode!) =====
    if (ARENA.bossArenaMode && !ARENA.topDownMode && !ARENA.isRaidBossBattle) {
      const moveSpeed = 3.2;
      if (ARENA.dodgeActive > 0) {
        // Dodge roll: fast movement + i-frame
        ARENA.dodgeActive--;
        p.x += ARENA.dodgeDir * 7.5;
        p.isInvulnerable = 1;
        // Spawn after-images
        if (ARENA.dodgeActive % 3 === 0 && ARENA.dashGhosts) {
          ARENA.dashGhosts.push({ x: p.x, y: p.y, radius: p.radius, alpha: 0.45, heroClass: (RPG_STATE.profile?.hero_class || "pudge").toLowerCase() });
        }
        if (ARENA.dodgeActive <= 0) {
          p.isInvulnerable = 0;
        }
      } else {
        if (ARENA.moveInput.left) { p.x -= moveSpeed; p.facing = -1; }
        if (ARENA.moveInput.right) { p.x += moveSpeed; p.facing = 1; }
      }
      // Clamp to arena bounds
      p.x = Math.max(25, Math.min(ARENA.width - 25, p.x));
      // Dodge cooldown
      if (ARENA.dodgeCooldown > 0) ARENA.dodgeCooldown--;
    }

    // Update danger zones (Global: Top-Down, Raid Bosses, Dungeon Waves, Side-Scroller)
    if (ARENA.dangerZones && ARENA.dangerZones.length > 0) {
      for (let dz = ARENA.dangerZones.length - 1; dz >= 0; dz--) {
        const zone = ARENA.dangerZones[dz];
        zone.timer--;
        if (zone.timer <= 0) {
          if (zone.phase === "telegraph") {
            zone.phase = "active";
            zone.timer = zone.activeFrames || 14;
          } else {
            ARENA.dangerZones.splice(dz, 1);
            continue;
          }
        }
        // Active damage zone collision
        if (zone.phase === "active") {
          let inZone = false;
          if (zone.type === "rect") {
            inZone = p.x > zone.x && p.x < zone.x + zone.w && p.y > zone.y - 30 && p.y < zone.y + zone.h + 30;
          } else if (zone.type === "circle") {
            inZone = Math.hypot(p.x - zone.cx, p.y - zone.cy) < zone.r + p.radius;
          } else if (zone.type === "line") {
            const l2 = (zone.x2 - zone.x1) * (zone.x2 - zone.x1) + (zone.y2 - zone.y1) * (zone.y2 - zone.y1);
            let d = 9999;
            if (l2 === 0) {
              d = Math.hypot(p.x - zone.x1, p.y - zone.y1);
            } else {
              let t = ((p.x - zone.x1) * (zone.x2 - zone.x1) + (p.y - zone.y1) * (zone.y2 - zone.y1)) / l2;
              t = Math.max(0, Math.min(1, t));
              d = Math.hypot(p.x - (zone.x1 + t * (zone.x2 - zone.x1)), p.y - (zone.y1 + t * (zone.y2 - zone.y1)));
            }
            inZone = d < ((zone.width || 34) / 2) + p.radius;
          } else if (zone.type === "cone") {
            const d = Math.hypot(p.x - (zone.cx || zone.x), p.y - (zone.cy || zone.y));
            if (d <= (zone.range || zone.length || 180) + p.radius) {
              let diff = Math.atan2(p.y - (zone.cy || zone.y), p.x - (zone.cx || zone.x)) - (zone.angle || 0);
              while (diff > Math.PI) diff -= Math.PI * 2;
              while (diff < -Math.PI) diff += Math.PI * 2;
              if (Math.abs(diff) <= ((zone.spread || 0.8) / 2)) inZone = true;
            }
          }

          if (inZone && !p.isInvulnerable) {
            let shouldHit = false;
            if (zone.isDot) {
              zone.lastHitFrame = zone.lastHitFrame || 0;
              if (ARENA.frameCount - zone.lastHitFrame >= 20) {
                zone.lastHitFrame = ARENA.frameCount;
                shouldHit = true;
              }
            } else if (!zone.hitPlayer) {
              zone.hitPlayer = true;
              shouldHit = true;
            }

            if (shouldHit) {
              const rawDmg = Math.floor(zone.damage || calculateBossAttackDamage(ARENA.bossEntity, 1.0));
              const actualDmg = applyDamageToPlayer(rawDmg, zone.label || "danger_zone");
              const lbl = zone.label ? `${zone.label} ` : "";
              spawnFloatingText(p.x, p.y - 25, `${lbl}-${actualDmg}`, zone.color || "#ef4444");
              ARENA.cameraTrauma = Math.min(1.0, (ARENA.cameraTrauma || 0) + 0.35);
              triggerHaptic("heavy");

              // Apply CC & Status effects to Player
              if (typeof applyStatusEffectToPlayer === "function") {
                if (zone.effect) applyStatusEffectToPlayer(zone.effect);
                if (zone.stun) applyStatusEffectToPlayer({ stun: zone.stun });
                if (zone.slow || zone.slowEffect) applyStatusEffectToPlayer({ slow: true, slowDuration: zone.slowDuration || 90, slowRatio: zone.slowRatio || zone.slowEffect || 0.45 });
                if (zone.silence) applyStatusEffectToPlayer({ silence: zone.silence });
                if (zone.burn) applyStatusEffectToPlayer({ burn: true, burnDuration: zone.burnDuration, burnDmg: zone.burnDmg });
                if (zone.poison) applyStatusEffectToPlayer({ poison: true, poisonDuration: zone.poisonDuration, poisonDmg: zone.poisonDmg });
                if (zone.blind) applyStatusEffectToPlayer({ blind: true, blindDuration: zone.blindDuration });
              }

              if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
            }
          }
        }
      }
    }


    // Passive Regen
    p.currentHp = Math.min(p.maxHp, p.currentHp + (stats.hp_regen || 1) / 60);
    p.currentMp = Math.min(p.maxMp, p.currentMp + (stats.mp_regen || 1) / 60);

    // Passive Items Update (Radiance, Heart of Tarrasque)
    if (ARENA.frameCount % 30 === 0) {
      const eq = RPG_STATE.profile?.equipment || {};
      const hasRadiance = Object.values(eq).some(it => it && (it.name?.includes("Radiance") || it.name?.includes("Сияние") || it.bonus?.radiance_burn));
      if (hasRadiance) {
        const radDmg = Math.floor((stats.max_atk || 30) * 0.45 + 65);
        if (ARENA.isRaidBossBattle && ARENA.bossEntity && ARENA.bossEntity.hp > 0) {
          const rd = applyDamageToBoss(ARENA.bossEntity, radDmg);
          spawnFloatingText(ARENA.bossEntity.x, ARENA.bossEntity.y - 18, `🔥 РАДИАНС -${rd}`, "#ea580c");
        } else {
          for (const c of ARENA.creeps) {
            if (c.isBoss) {
              const rd = applyDamageToBoss(c, radDmg);
              spawnFloatingText(c.x, c.y - 18, `🔥 РАДИАНС -${rd}`, "#ea580c");
            } else {
              c.hp -= radDmg;
              spawnFloatingText(c.x, c.y - 18, `🔥 РАДИАНС -${radDmg}`, "#ea580c");
            }
          }
        }
      }
      if (ARENA.frameCount % 60 === 0) {
        const hasTarrasque = Object.values(eq).some(it => it && (it.name?.includes("Tarrasque") || it.name?.includes("Тарраск") || it.bonus?.pct_hp_regen));
        if (hasTarrasque) {
          const heal = Math.min(Math.floor(p.maxHp * 0.015), 6000);
          p.currentHp = Math.min(p.maxHp, p.currentHp + heal);
          spawnFloatingText(p.x, p.y - 30, `+${heal} HP (ТАРАСКА) ❤️`, "#22c55e");
        }
      }
    }

    // Cooldown timers
    if (p.attackCooldown > 0) {
      p.attackCooldown--;
      if (p.attackCooldown <= 0 && p.attackQueued) {
        p.attackQueued = false;
        playerSlashAttack();
      }
    }
    if (ARENA.skill1Cooldown > 0) ARENA.skill1Cooldown--;
    if (ARENA.ultCooldown > 0) ARENA.ultCooldown--;
    if (ARENA.potionCooldown > 0) ARENA.potionCooldown--;

    // Decrement item cooldowns
    if (ARENA.itemCooldowns) {
      for (const k in ARENA.itemCooldowns) {
        if (ARENA.itemCooldowns[k] > 0) ARENA.itemCooldowns[k]--;
      }
    }
    // Active item buff timers
    if (ARENA.player.bkbActive > 0) ARENA.player.bkbActive--;
    if (ARENA.player.satanicActive > 0) ARENA.player.satanicActive--;
    if (ARENA.player.eulActive > 0) ARENA.player.eulActive--;
    if (p.slashAnimation) {
      p.slashAnimation.timer--;
      if (p.slashAnimation.timer <= 0) p.slashAnimation = null;
    }

    // Active buffs/effects timers
    if (p.fleshHeapActive > 0) p.fleshHeapActive--;
    if (p.bladeDanceActive > 0) p.bladeDanceActive--;
    if (p.counterspellActive > 0) p.counterspellActive--;
    if (p.croakTimer > 0) p.croakTimer--;

    // Largo Amphibian Rhapsody: переключаемая стойка (ВКЛ / ВЫКЛ, длится бесконечно пока есть мана).
    // Каждые 0.5 секунды (30 кадров) тратит ману, хилит Ларго и наносит AoE-урон вокруг!
    if (p.largoRhapsodyActive) {
      const rhapsodyInterval = (window.hasTalentPerk && window.hasTalentPerk("perk_pulse_storm")) ? 15 : 30;
      if (!p.largoRhapsodyTickTimer || p.largoRhapsodyTickTimer <= 0) {
        p.largoRhapsodyTickTimer = rhapsodyInterval;
      }
      p.largoRhapsodyTickTimer--;

      if (p.largoRhapsodyTickTimer <= 0) {
        p.largoRhapsodyTickTimer = rhapsodyInterval;

        // Расход маны за тик: 5 MP (или -60% при активном Кваканье Гения -> 2 MP!)
        let tickCost = 5;
        if (p.croakTimer > 0) {
          tickCost = Math.floor(tickCost * 0.4); // 2 MP
        }

        // Проверка: хватает ли маны на очередной такт
        if (p.currentMp < tickCost) {
          p.largoRhapsodyActive = false;
          spawnFloatingText(p.x, p.y - 30, "Мана закончилась! Рапсодия выключена", "#94a3b8");
          triggerHaptic("error");
        } else {
          p.currentMp -= tickCost;
          spawnFloatingText(p.x, p.y - 48, `⚡ -${tickCost} MP`, "#38bdf8");

          let ultMult = p.largoRhapsodyDmgMult || 1.0;
          if (p.edictTimer > 0) {
            ultMult += 2.5; // +250% урон от ульты пока активен 1 скилл
          }
          const spellAmp = (stats.spell_amp !== undefined ? stats.spell_amp : ((p.maxMp || 100) * 0.2));

          // 1. Исцеление Ларго (разделено на 4 для тика 0.5с): сбалансировано
          const healAmt = Math.max(12, Math.min(Math.floor(p.maxHp * 0.01), 6000) + Math.min(4000, Math.floor((stats.int || 20) * 0.25)));
          p.currentHp = Math.min(p.maxHp, p.currentHp + healAmt);
          spawnFloatingText(p.x, p.y - 30, `💚 +${healAmt} ХП (РАПСОДИЯ)`, "#22c55e");

          // 2. Гармоническая визуальная волна
          if (!ARENA.specialEffects) ARENA.specialEffects = [];
          ARENA.specialEffects.push({
            type: "rhapsody_beat",
            x: p.x,
            y: p.y,
            radius: 25,
            maxRadius: 280,
            timer: 28,
            maxTimer: 28,
            color: "#22c55e"
          });
          ARENA.cameraTrauma = Math.min(1.0, (ARENA.cameraTrauma || 0) + 0.25);
          triggerHaptic("medium");

          // 3. AoE-урон всем врагам вокруг в радиусе 280px (или линии в 2D) (разделено на 4)
          const pulseDmg = Math.floor(((stats.max_atk || 30) * 0.7 + spellAmp * 0.25) * ultMult);
          if (ARENA.topDownMode || ARENA.isRaidBossBattle) {
            if (ARENA.bossEntity && ARENA.bossEntity.hp > 0) {
              const dist = Math.hypot(ARENA.bossEntity.x - p.x, ARENA.bossEntity.y - p.y);
              if (dist <= 280) {
                const actualDmg = applyDamageToBoss(ARENA.bossEntity, pulseDmg);
                spawnFloatingText(ARENA.bossEntity.x, ARENA.bossEntity.y - 25, `🐸 -${actualDmg} РАПСОДИЯ`, "#a855f7");
              }
            }
            for (const c of ARENA.creeps) {
              const dist = Math.hypot(c.x - p.x, c.y - p.y);
              if (dist <= 280) {
                if (c.isBoss) {
                  applyDamageToBoss(c, pulseDmg);
                } else {
                  c.hp -= pulseDmg;
                }
                spawnFloatingText(c.x, c.y - 15, `🐸 -${pulseDmg}`, "#a855f7");
              }
            }
          } else {
            for (const c of ARENA.creeps) {
              if (Math.abs(c.x - p.x) <= 320) {
                safeDamageCreep(c, pulseDmg, false);
                spawnFloatingText(c.x, c.y - 15, `🐸 -${pulseDmg} РАПСОДИЯ`, "#a855f7");
              }
            }
          }
        }
      }
    }

    // Pudge Rot effect: ticks every 15 frames while active
    if (p.rotActive > 0) {
      p.rotActive--;
      if (p.rotActive % 15 === 0) {
        const rotDmg = Math.floor((stats.max_atk || 25) * 0.9 * (p.rotDmgMult || 1.0));
        for (const c of ARENA.creeps) {
          if (c.isBoss) {
            const rd = applyDamageToBoss(c, rotDmg);
            spawnFloatingText(c.x, c.y - 12, `☣️ -${rd}`, "#22c55e");
          } else {
            c.hp -= rotDmg;
            spawnFloatingText(c.x, c.y - 12, `☣️ -${rotDmg}`, "#22c55e");
          }
        }
      }
    }

    // Special effects animation timers & top-down ability controllers
    for (let i = ARENA.specialEffects.length - 1; i >= 0; i--) {
      const fx = ARENA.specialEffects[i];
      fx.timer--;

      // Invoker Top-Down Chaos Meteor Flight & Impact
      if (fx.type === "topdown_meteor") {
        const prog = 1 - (fx.timer / (fx.maxTimer || 50));
        if (prog < 0.65) {
          const flightProg = prog / 0.65;
          fx.x = fx.startX + (fx.targetX - fx.startX) * flightProg;
          fx.y = fx.startY + (fx.targetY - fx.startY) * flightProg;
        } else {
          fx.x = fx.targetX;
          fx.y = fx.targetY;
          if (!fx.impactDone) {
            fx.impactDone = true;
            ARENA.cameraTrauma = Math.min(1.0, (ARENA.cameraTrauma || 0) + 0.75);
            triggerHaptic("heavy");
            if (!ARENA.shockwaves) ARENA.shockwaves = [];
            ARENA.shockwaves.push({ x: fx.x, y: fx.y, radius: 10, maxRadius: 110, alpha: 1.0, speed: 6, color: "#ea580c" });
            spawnFloatingText(fx.x, fx.y - 45, "💥 БАБАХ! МЕТЕОР ПРИЗЕМЛИЛСЯ!", "#ea580c");
            if (ARENA.bossEntity && ARENA.bossEntity.hp > 0) {
              ARENA.bossEntity.poise = Math.max(0, (ARENA.bossEntity.poise || 300) - 100);
            }
          }
        }
      }

      // Juggernaut Top-Down Omnislash Slashes
      if (fx.type === "topdown_omnislash" && fx.timer % 6 === 0 && fx.slashes > 0) {
        fx.slashes--;
        const boss = ARENA.bossEntity;
        if (boss && boss.hp > 0) {
          const slashDmg = Math.max(10, Math.floor((fx.dmg || 100) / 8));
          const ang = Math.random() * Math.PI * 2;
          if (!fx.slashArcs) fx.slashArcs = [];
          fx.slashArcs.push({ x: boss.x + Math.cos(ang) * 18, y: boss.y + Math.sin(ang) * 18, angle: ang });
          spawnFloatingText(boss.x + (Math.random() * 32 - 16), boss.y - 25, `⚔️ -${slashDmg}`, "#facc15");
          triggerHaptic("medium");
        }
      }

      // PA Dagger Throw
      if (fx.type === "dagger_throw") {
        const dProg = 1 - (fx.timer / (fx.maxTimer || 20));
        fx.x = fx.fromX + (fx.toX - fx.fromX) * dProg;
        fx.y = fx.fromY + (fx.toY - fx.fromY) * dProg;
        if (fx.timer === 1) {
          ARENA.specialEffects.push({ type: "slash_burst", x: fx.toX, y: fx.toY, timer: 16, maxTimer: 16, color: "#f43f5e" });
        }
      }

      // Wraith King Wraithfire Skull
      if (fx.type === "wraithfire") {
        const wProg = 1 - (fx.timer / (fx.maxTimer || 26));
        fx.x = fx.fromX + (fx.toX - fx.fromX) * wProg;
        fx.y = fx.fromY + (fx.toY - fx.fromY) * wProg;
      }

      // Pudge Meat Hook
      if (fx.type === "meat_hook") {
        const hookProg = Math.sin((1 - (fx.timer / (fx.maxTimer || 24))) * Math.PI);
        fx.curX = fx.fromX + (fx.toX - fx.fromX) * hookProg;
        fx.curY = fx.fromY + (fx.toY - fx.fromY) * hookProg;
      }

      // Legacy Omnislash (Side-Scroller waves)
      if (fx.type === "omnislash" && fx.timer % 7 === 0 && fx.slashes > 0) {
        fx.slashes--;
        if (ARENA.creeps.length > 0) {
          const target = ARENA.creeps[Math.floor(Math.random() * ARENA.creeps.length)];
          let dmg = Math.floor((stats.max_atk || 30) * 2.2 * (fx.mult || 1.0));
          if (target.archetype === "defender") {
            target.shieldBrokenTimer = 240;
            target.state = "stagger";
            target.staggerTimer = 80;
            target.stateTimer = 80;
            spawnFloatingText(target.x, target.y - 25, "💥 GUARD BREAK ОМНИСЛЕШЕМ!", "#facc15");
          }
          if (target.isBoss) {
            dmg = applyDamageToBoss(target, dmg, true);
          } else {
            safeDamageCreep(target, dmg, false);
          }
          spawnFloatingText(target.x, target.y - 20, `⚔️ КРИТ! -${dmg}`, "#facc15");
          triggerHaptic("heavy");
        }
      }
      if (fx.timer <= 0) ARENA.specialEffects.splice(i, 1);
    }

    // Boss block-window timer
    if (ARENA.blockWindowActive) {
      ARENA.blockWindowTimer--;
      if (ARENA.blockWindowTimer <= 0) {
        ARENA.blockWindowActive = false;
        let dmg = Math.floor((ARENA.bossEntity?.atk || 30) * 2);
        if (p.fleshHeapActive > 0) dmg = Math.floor(dmg * 0.6);
        p.currentHp = Math.max(0, p.currentHp - dmg);
        spawnFloatingText(p.x, p.y - 25, `💥 -${dmg} ПРОПУЩЕН!`, "#ef4444");
        triggerHaptic("error");
        if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
      }
    }

    // QTE timer
    if (ARENA.qteActive) {
      ARENA.qteTimer--;
      if (ARENA.qteTimer <= 0) ARENA.qteActive = false;
    }

    // Auto-attack (Side-Scroller waves only; Top-Down mode handles 360 targeting independently)
    if (!ARENA.topDownMode && !ARENA.isRaidBossBattle && p.autoAttack && p.attackCooldown <= 0) {
      let nearest = null;
      let nearestDist = Math.max(320, p.attackRange + 50);
      for (const c of ARENA.creeps) {
        const d = c.x - p.x;
        if (d > 0 && d < nearestDist) {
          nearest = c;
          nearestDist = d;
        }
      }
      if (nearest) {
        playerSlashAttack();
      }
    }

    // Update Telegraphs (Ground warnings)
    if (ARENA.telegraphs) {
      for (let i = ARENA.telegraphs.length - 1; i >= 0; i--) {
        const tg = ARENA.telegraphs[i];
        tg.timer--;
        if (tg.timer <= 0) {
          ARENA.telegraphs.splice(i, 1);
        }
      }
    }

    // Update Shockwaves (Radial expanding rings)
    if (ARENA.shockwaves) {
      for (let i = ARENA.shockwaves.length - 1; i >= 0; i--) {
        const sw = ARENA.shockwaves[i];
        sw.radius += sw.speed;

        const waveFrontX = sw.x - sw.radius;
        if (!sw.hitPlayer && Math.abs(waveFrontX - p.x) < 22) {
          // Check Perfect Parry
          if (ARENA.parryWindow > 0) {
            sw.hitPlayer = true;
            triggerPerfectParry();
          } else if (p.counterspellActive > 0 || p.isBlocking) {
            sw.hitPlayer = true;
            const blkDmg = Math.max(5, Math.floor(sw.damage * 0.3));
            p.currentHp = Math.max(0, p.currentHp - blkDmg);
            spawnFloatingText(p.x, p.y - 25, `🛡️ БЛОК -${blkDmg}`, "#38bdf8");
            triggerHaptic("medium");
          } else {
            sw.hitPlayer = true;
            const effDef = stats.defense || 6;
            const floor = RPG_STATE.profile?.dungeon_floor || 1;
            const dr = Math.min(0.82, (effDef * 0.05) / (1 + effDef * 0.05 + floor * 0.4));
            let finalDmg = Math.max(Math.floor(sw.damage * 0.2), Math.floor(sw.damage * (1 - dr)));
            if (p.fleshHeapActive > 0) finalDmg = Math.floor(finalDmg * 0.6);
            p.currentHp = Math.max(0, p.currentHp - finalDmg);
            ARENA.cameraTrauma = Math.min(1.0, ARENA.cameraTrauma + 0.45);
            spawnFloatingText(p.x, p.y - 25, `💥 -${finalDmg} УДАРНАЯ ВОЛНА!`, "#ef4444");
            triggerHaptic("error");
            if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
          }
        }

        if (sw.radius > sw.maxRadius) {
          ARENA.shockwaves.splice(i, 1);
        }
      }
    }

    // Guarantee Raid Boss remains in creeps array during boss fight!
    if (ARENA.isRaidBossBattle && ARENA.bossEntity) {
      ARENA.isBossActive = true;
      if (!ARENA.creeps.includes(ARENA.bossEntity)) {
        ARENA.creeps = [ARENA.bossEntity];
      }
    }

    // Creep Spawning (waves 1 to 19 only, NEVER during a Raid Boss Battle!)
    ARENA.creepSpawnTimer++;
    if (!ARENA.isRaidBossBattle && !ARENA.isBossActive && ARENA.creepSpawnTimer % 45 === 0 &&
        ARENA.totalCreepsSpawned < ARENA.creepsNeededForWave && ARENA.creeps.length < 14) {
      spawnArenaCreep();
    }

    // Deadlock safeguard: if wave is fighting, no creeps exist, and all wave creeps are considered spawned
    if (!ARENA.isRaidBossBattle && !ARENA.isBossActive && ARENA.waveState === "fighting" && ARENA.creeps.length === 0 && ARENA.totalCreepsSpawned >= ARENA.creepsNeededForWave) {
      if (ARENA.creepsKilledInWave >= ARENA.creepsNeededForWave) {
        if (typeof advanceArenaWave === "function") advanceArenaWave();
      } else {
        ARENA.totalCreepsSpawned = ARENA.creepsKilledInWave;
        if (typeof spawnArenaCreep === "function") spawnArenaCreep();
      }
    }

    // Boss phase logic & companion squad updates
    if (ARENA.isBossActive && ARENA.bossEntity) {
      updateBossPhase();
      updateBossCompanions();
    }

    // Boss Projectiles (Side-Scroller Waves only — Top-Down mode has its own dedicated 360 projectile loop!)
    if (!ARENA.topDownMode && !ARENA.isRaidBossBattle) {
      for (let i = ARENA.bossProjectiles.length - 1; i >= 0; i--) {
        const proj = ARENA.bossProjectiles[i];
        proj.x -= proj.speed;
      if (proj.x < p.x + 65 && !proj.warned) {
        proj.warned = true;
        ARENA.blockWindowActive = true;
        ARENA.blockWindowTimer = ARENA.blockWindowMax;
        triggerHaptic("warning");
      }
      if (proj.x < p.x - 20) {
        ARENA.bossProjectiles.splice(i, 1);
      }
    }

    // Player Projectiles
    for (let i = ARENA.playerProjectiles.length - 1; i >= 0; i--) {
      const proj = ARENA.playerProjectiles[i];

      // Companion Dagger (Phantom Assassin / Anti-Mage squad companion)
      if (proj.type === "companion_dagger") {
        proj.x += proj.speed;
        const boss = ARENA.bossEntity;
        if (boss && Math.abs(proj.x - boss.x) < 25) {
          const dmgTaken = applyDamageToBoss(boss, proj.dmg, proj.isCrit);
          if (boss.poise !== undefined) boss.poise = Math.max(0, boss.poise - (proj.isCrit ? 12 : 6));
          if (proj.isCrit) {
            spawnFloatingText(boss.x - 10 + Math.random() * 20, boss.y - 25 - Math.random() * 15, `💥 КРИТ! -${proj.dmg}`, "#ef4444");
            triggerHaptic("heavy");
          } else {
            spawnFloatingText(boss.x - 10 + Math.random() * 20, boss.y - 20 - Math.random() * 12, `🗡️ КИНЖАЛ -${proj.dmg}`, "#38bdf8");
          }
          if (ARENA.combo) {
            ARENA.combo.count++;
            ARENA.combo.timer = 120;
          }
          ARENA.playerProjectiles.splice(i, 1);
          continue;
        }
        if (proj.x > ARENA.width + 40) {
          ARENA.playerProjectiles.splice(i, 1);
          continue;
        }
      }

      // Wind Blade / Cleave Wave (Melee heroes cutting wave that slices through ranged creeps)
      if (proj.type === "wind_blade") {
        proj.x += proj.speed;
        for (const c of ARENA.creeps) {
          if (!proj.hitCreepIds) proj.hitCreepIds = new Set();
          const creepKey = c.id || c.uid || c.name; // Stable key! Never hit the same creep twice in one projectile!
          if (!proj.hitCreepIds.has(creepKey) && Math.abs(c.x - proj.x) < (c.radius + proj.radius)) {
            proj.hitCreepIds.add(creepKey);
            let finalDmg = proj.dmg;
            if (c.archetype === "defender") {
              c.shieldHits = (c.shieldHits || 0) + 1;
              if (c.shieldHits >= 3 || proj.isHeavy) {
                c.shieldBrokenTimer = 240;
                c.state = "stagger";
                c.staggerTimer = 80;
                c.stateTimer = 80;
                spawnFloatingText(c.x, c.y - 25, "💥 GUARD BREAK! (+100% УРОНА)", "#facc15");
                finalDmg = Math.floor(finalDmg * 1.5);
              } else if (c.shieldBrokenTimer <= 0) {
                finalDmg = Math.max(8, Math.floor(finalDmg * 0.5));
                spawnFloatingText(c.x, c.y - 20, `🛡️ БЛОК (-50%) [${3 - c.shieldHits} уд.]`, "#94a3b8");
              }
            }

            if (c.isBoss) {
              finalDmg = applyDamageToBoss(c, finalDmg, proj.isCrit);
            } else {
              safeDamageCreep(c, finalDmg, false);
            }
            spawnFloatingText(c.x, c.y - 18, `${proj.isCrit ? "⚡ КРИТ! " : ""}-${finalDmg}`, proj.isCrit ? "#f59e0b" : "#facc15");
          }
        }
        if (proj.x > ARENA.width + 40) {
          ARENA.playerProjectiles.splice(i, 1);
        }
        continue;
      }

      // Chaos Meteor («Котлета» Инвокера, падающая с неба и катящаяся по линии)
      if (proj.type === "meteor") {
        if (proj.falling) {
          proj.x += proj.vx;
          proj.y += proj.vy;
          proj.angle += 0.2;

          // Impact on ground!
          if (proj.y >= proj.targetY) {
            proj.y = proj.targetY;
            proj.falling = false;
            ARENA.cameraTrauma = Math.min(1.0, ARENA.cameraTrauma + 0.65);
            ARENA.hitstop = 8;
            triggerHaptic("heavy");

            // Ground impact shockwave & crater
            if (!ARENA.shockwaves) ARENA.shockwaves = [];
            ARENA.shockwaves.push({
              x: proj.x,
              y: proj.y + 12,
              radius: 12,
              maxRadius: 85,
              alpha: 1.0,
              color: "#ea580c"
            });
            spawnFloatingText(proj.x, proj.y - 35, "💥 БАБАХ! МЕТЕОР ПРИЗЕМЛИЛСЯ!", "#f97316");

            // Massive impact damage in landing zone
            for (const c of ARENA.creeps) {
              if (Math.abs(c.x - proj.x) < 85) {
                safeDamageCreep(c, Math.floor(proj.dmg * 0.8), false);
                c.x += 45; // knockback
                if (c.isBoss) {
                  c.poise = Math.max(0, (c.poise !== undefined ? c.poise : 300) - 80);
                  if (c.poise <= 0 && !c.isStaggered) {
                    c.isStaggered = true;
                    c.staggerTimer = 210;
                    ARENA.hitstop = 12;
                    ARENA.cameraTrauma = 0.8;
                    spawnFloatingText(c.x, c.y - 35, "💫 ОШЕЛОМЛЕН МЕТЕОРОМ!", "#facc15");
                  }
                }
                if (c.archetype === "defender") {
                  c.shieldBrokenTimer = 240;
                  c.state = "stagger";
                  c.staggerTimer = 90;
                  c.stateTimer = 90;
                  spawnFloatingText(c.x, c.y - 25, "💥 GUARD BREAK МЕТЕОРОМ!", "#facc15");
                }
              }
            }
          }
        } else {
          // Rolling along the lane
          proj.x += proj.speed;
          proj.angle += 0.15;

          // Leaves burning magma trail
          if (!proj.burnTrail) proj.burnTrail = [];
          if ((ARENA.frameCount || 0) % 5 === 0) {
            proj.burnTrail.push({
              x: proj.x - 16,
              y: proj.y + 12,
              timer: 130
            });
          }

          // Damage creeps in its path
          for (const c of ARENA.creeps) {
            if (!proj.hitCreepIds) proj.hitCreepIds = new Set();
            const creepKey = c.id || c.uid || c.name; // Stable key!
            if (!proj.hitCreepIds.has(creepKey) && Math.abs(c.x - proj.x) < (c.radius + proj.radius)) {
              proj.hitCreepIds.add(creepKey);
              let finalDmg = proj.dmg;
              if (c.isBoss) {
                c.poise = Math.max(0, (c.poise !== undefined ? c.poise : 300) - 45);
                if (c.poise <= 0 && !c.isStaggered) {
                  c.isStaggered = true;
                  c.staggerTimer = 210;
                  ARENA.hitstop = 10;
                  ARENA.cameraTrauma = 0.7;
                  spawnFloatingText(c.x, c.y - 35, "💫 ОШЕЛОМЛЕН МЕТЕОРОМ!", "#facc15");
                }
                finalDmg = applyDamageToBoss(c, finalDmg, true);
              } else {
                safeDamageCreep(c, finalDmg, false);
                c.x += 40; // knockback
              }
              if (c.archetype === "defender") {
                c.shieldBrokenTimer = 240;
                c.state = "stagger";
                c.staggerTimer = 90;
                c.stateTimer = 90;
                spawnFloatingText(c.x, c.y - 25, "💥 GUARD BREAK МЕТЕОРОМ!", "#facc15");
              }
              spawnFloatingText(c.x, c.y - 20, `☄️ -${finalDmg} ОЖОГ!`, "#ea580c");
            }
          }
        }

        // Update ground burn trail
        if (proj.burnTrail) {
          for (let b = proj.burnTrail.length - 1; b >= 0; b--) {
            proj.burnTrail[b].timer--;
            // Ticking burn damage on creeps walking over magma
            if (proj.burnTrail[b].timer % 18 === 0) {
              const tx = proj.burnTrail[b].x;
              for (const c of ARENA.creeps) {
                if (Math.abs(c.x - tx) < 32) {
                  const tick = Math.max(10, Math.floor(proj.dmg * 0.12));
                  safeDamageCreep(c, tick, false);
                  spawnFloatingText(c.x, c.y - 12, `🔥 -${tick}`, "#f97316");
                }
              }
            }
            if (proj.burnTrail[b].timer <= 0) proj.burnTrail.splice(b, 1);
          }
        }

        if (proj.x > ARENA.width + 60 && (!proj.burnTrail || proj.burnTrail.length === 0)) {
          ARENA.playerProjectiles.splice(i, 1);
        }
        continue;
      }

      // Targeted magic orb or dagger
      proj.x += proj.speed;
      let hit = false;
      for (const c of ARENA.creeps) {
        if (Math.abs(c.x - proj.x) < c.radius + 10) {
          let finalDmg = proj.dmg;
          if (c.isBoss) {
            if (c.tormentorShield) {
              const reflectDmg = Math.max(4, Math.floor(finalDmg * 0.5));
              p.currentHp = Math.max(0, p.currentHp - reflectDmg);
              spawnFloatingText(p.x, p.y - 22, `🪞 ОТРАЖЕНИЕ -${reflectDmg}!`, "#c084fc");
              if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
            }
            if (c.isStaggered) {
              finalDmg = Math.floor(finalDmg * 2.5);
            } else {
              c.poise = Math.max(0, (c.poise !== undefined ? c.poise : 300) - (proj.isCrit ? 35 : 18));
              if (c.poise <= 0) {
                c.isStaggered = true;
                c.staggerTimer = 210;
                ARENA.hitstop = 10;
                ARENA.cameraTrauma = 0.7;
                spawnFloatingText(c.x, c.y - 35, "💫 ОШЕЛОМЛЕН! (+150% УРОНА)", "#facc15");
                triggerHaptic("heavy");
              }
            }

            // MAGIC ATTACK: Bypasses heavy physical defense armor!
            if (proj.isMagic) {
              const magicDr = 0.12;
              finalDmg = Math.max(12, Math.floor(finalDmg * (1 - magicDr)));
            } else {
              const bDef = c.defense || 14;
              const dr = (bDef * 0.05) / (1 + bDef * 0.05);
              finalDmg = Math.max(6, Math.floor(finalDmg * (1 - dr)));
            }
            finalDmg = applyDamageToBoss(c, finalDmg, proj.isCrit);
          } else {
            safeDamageCreep(c, finalDmg, false);
          }

          if (c.archetype === "defender" && proj.isMagic) {
            c.shieldHits = (c.shieldHits || 0) + 1;
            if (c.shieldHits >= 3 || proj.isHeavy) {
              c.shieldBrokenTimer = 240;
              c.state = "stagger";
              c.staggerTimer = 80;
              c.stateTimer = 80;
              spawnFloatingText(c.x, c.y - 25, "💥 GUARD BREAK МАГИЕЙ!", "#38bdf8");
            }
          }
          const col = proj.isMagic ? (proj.isCrit ? "#c084fc" : "#38bdf8") : (proj.isCrit ? "#facc15" : "#f87171");
          const prefix = proj.isMagic ? (proj.isCrit ? "🔮 МАГ КРИТ! " : "✨ МАГ ") : (proj.isCrit ? "💥 КРИТ! " : "");
          const txt = (c.isBoss && c.isStaggered) ? `💥 STAGGER! -${finalDmg}` : `${prefix}-${finalDmg}`;
          spawnFloatingText(c.x, c.y - 18, txt, col);
          if (proj.slow) c.speed = Math.max(0.5, c.speed * 0.5);
          hit = true;
          triggerHaptic("light");
          break;
        }
      }
      if (hit || proj.x > ARENA.width + 40) {
        ARENA.playerProjectiles.splice(i, 1);
      }
    }

    // Allied Minions (Wraith King skeletons)
    for (let i = ARENA.alliedMinions.length - 1; i >= 0; i--) {
      const m = ARENA.alliedMinions[i];
      if (ARENA.topDownMode || ARENA.isRaidBossBattle) {
        const boss = ARENA.bossEntity;
        if (boss && boss.hp > 0) {
          const ang = Math.atan2(boss.y - m.y, boss.x - m.x);
          const dist = Math.hypot(boss.x - m.x, boss.y - m.y);
          if (dist > boss.radius + m.radius + 6) {
            m.x += Math.cos(ang) * (m.speed || 2.6);
            m.y += Math.sin(ang) * (m.speed || 2.6);
          } else {
            m.attackCd = (m.attackCd || 0) - 1;
            if (m.attackCd <= 0) {
              m.attackCd = 35;
              const dmg = applyDamageToBoss(boss, m.atk || 25, false);
              spawnFloatingText(boss.x + (Math.random() * 20 - 10), boss.y - 20, `💀 -${dmg}`, "#10b981");
            }
          }
        }
      } else {
        m.x += m.speed;
        // Attack nearest creep
        for (const c of ARENA.creeps) {
          if (c.x - m.x < 30 && c.x > m.x) {
            safeDamageCreep(c, m.atk, false);
            spawnFloatingText(c.x, c.y - 15, `☠️ -${m.atk}`, "#e2e8f0");
            m.hp -= c.atk;
            break;
          }
        }
      }
      if (m.hp <= 0 || m.x > ARENA.width + 50 || m.x < -50 || m.y < -50 || m.y > ARENA.height + 50) {
        ARENA.alliedMinions.splice(i, 1);
      }
    }

    // Update Player Dash & Timers
    if (p.dashCooldown > 0) p.dashCooldown--;
    if (p.isInvulnerable > 0) p.isInvulnerable--;
    if (p.dashTimer > 0) {
      p.dashTimer--;
      if (p.dashTimer <= 0) p.isDashing = false;
    }
    if (ARENA.combo && ARENA.combo.timer > 0) {
      ARENA.combo.timer--;
      if (ARENA.combo.timer <= 0) {
        ARENA.combo.count = 0;
        ARENA.combo.step = 0;
      }
    }
    if (ARENA.styleMeter) {
      if (ARENA.styleMeter.decayTimer > 0) {
        ARENA.styleMeter.decayTimer--;
      } else if (ARENA.styleMeter.score > 0) {
        ARENA.styleMeter.score = Math.max(0, ARENA.styleMeter.score - 3);
        addStylePoints(0, "decay");
      }
    }
    // Dash Ghosts decay
    if (ARENA.dashGhosts) {
      for (let g = ARENA.dashGhosts.length - 1; g >= 0; g--) {
        ARENA.dashGhosts[g].alpha -= 0.05;
        if (ARENA.dashGhosts[g].alpha <= 0) ARENA.dashGhosts.splice(g, 1);
      }
    }

    // Witch-Time Slow Motion Timer
    if (ARENA.sloMoTimer > 0) {
      ARENA.sloMoTimer--;
      if (ARENA.sloMoTimer <= 0) {
        ARENA.timeScale = 1.0;
      }
    }

    // Update Enemy Projectiles (Ranged Mages, Archers, Catapults & Reflected Bolts)
    if (ARENA.enemyProjectiles) {
      for (let j = ARENA.enemyProjectiles.length - 1; j >= 0; j--) {
        const proj = ARENA.enemyProjectiles[j];

        if (proj.reflected) {
          // Reflected bolt flying towards enemies!
          proj.x -= proj.speed; // speed is negative, moves right
          let hitCreep = false;
          for (const c of ARENA.creeps) {
            if (Math.abs(c.x - proj.x) < c.radius + 14) {
              safeDamageCreep(c, proj.dmg, false);
              spawnFloatingText(c.x, c.y - 24, `💥 ОТРАЖЕН! -${proj.dmg}`, "#facc15");
              ARENA.hitstop = 4;
              hitCreep = true;
              break;
            }
          }
          if (hitCreep || proj.x > ARENA.width + 60) {
            ARENA.enemyProjectiles.splice(j, 1);
          }
        } else {
          // Hostile projectile flying towards player
          proj.x -= proj.speed;

          if (Math.abs(proj.x - p.x) < 22) {
            if (p.isInvulnerable > 0) {
              spawnFloatingText(p.x, p.y - 20, "УВОРОТ! (I-FRAMES)", "#38bdf8");
              ARENA.enemyProjectiles.splice(j, 1);
            } else if (ARENA.parryWindow > 0) {
              proj.reflected = true;
              proj.speed = -Math.abs(proj.speed || 3.5) * 2.0;
              proj.dmg = Math.floor((proj.dmg || 20) * 2.5);
              proj.color = "#facc15";
              addStylePoints(300, "DEFLECT");
              spawnFloatingText(p.x + 15, p.y - 28, "🪞 ОТРАЖЕНО!", "#facc15");
              triggerHaptic("heavy");
            } else if (p.isBlocking || p.counterspellActive > 0) {
              const bDmg = Math.max(3, Math.floor(proj.dmg * 0.25));
              p.currentHp = Math.max(0, p.currentHp - bDmg);
              spawnFloatingText(p.x, p.y - 20, `🛡️ БЛОК -${bDmg}`, "#38bdf8");
              triggerHaptic("medium");
              ARENA.enemyProjectiles.splice(j, 1);
            } else {
              const def = Math.max(0, stats.defense || 5);
              const floor = RPG_STATE.profile?.dungeon_floor || 1;
              const armorDr = Math.min(0.82, (def * 0.05) / (1.0 + def * 0.05 + floor * 0.4));
              let rawDmg = Math.max(Math.floor(proj.dmg * 0.15), Math.floor(proj.dmg * (1.0 - armorDr)));
              if (p.pipeShield && p.pipeShield > 0) {
                const absorbed = Math.min(p.pipeShield, rawDmg);
                p.pipeShield -= absorbed;
                rawDmg -= absorbed;
                spawnFloatingText(p.x, p.y - 30, `🛡️ ПАЙП -${absorbed}`, "#a855f7");
              }
              if (p.fleshHeapActive > 0) rawDmg = Math.floor(rawDmg * 0.6);
              if (p.crimsonActive > 0) rawDmg = Math.max(4, rawDmg - (p.crimsonBlock || 85));
              const takenDmg = applyDamageToPlayer(rawDmg, proj.isMagic ? "magic" : "projectile");
              if (takenDmg > 0) {
                if (p.blademailActive > 0) {
                  spawnFloatingText(p.x, p.y - 25, `🪞 ВОЗВРАТКА -${takenDmg}`, "#facc15");
                }
                spawnFloatingText(p.x + 10, p.y - 20, `💥 -${takenDmg}`, "#ef4444");
                triggerHaptic("light");
                if (ARENA.styleMeter) ARENA.styleMeter.score = Math.max(0, ARENA.styleMeter.score - 120);
              }
              ARENA.enemyProjectiles.splice(j, 1);
              if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
            }
          } else if (proj.x < -20) {
            ARENA.enemyProjectiles.splice(j, 1);
          }
        }
      }
    }
    } // End of Side-Scroller Projectiles Guard

    // Check Captain Presence for Squad Buffs
    const activeCaptain = ARENA.creeps.find(c => c.archetype === "captain" || c.isCaptain);

    // Update Creeps — Tactical FSM (Approach, Telegraph, Attack, Recovery, Panic)
    for (let i = ARENA.creeps.length - 1; i >= 0; i--) {
      const c = ARENA.creeps[i];

      // 1. Creep Death Check FIRST!
      if (c.hp <= 0) {
        if (c.archetype === "captain" || c.isCaptain) {
          addStylePoints(220, "CAPTAIN DOWN");
          for (const remaining of ARENA.creeps) {
            if (remaining !== c && !remaining.isBoss) {
              remaining.state = "panic";
              remaining.stateTimer = 150; // 2.5s panic
              spawnFloatingText(remaining.x, remaining.y - 25, "😱 ПАНИКА ОТРЯДА!", "#38bdf8");
            }
          }
        }
        ARENA.creeps.splice(i, 1);
        handleCreepDeath(c);
        continue;
      }

      // Recovery of broken shield
      if (c.shieldBrokenTimer > 0) c.shieldBrokenTimer--;

      // Captain aura check
      c.hasCaptainBuff = !!(activeCaptain && activeCaptain !== c && Math.abs(activeCaptain.x - c.x) < 80);

      // Stagger / Stun state (checks both staggerTimer and stateTimer to prevent infinite loop)
      if (c.state === "stagger" || (c.staggerTimer && c.staggerTimer > 0) || (c.stateTimer && c.stateTimer > 0 && c.state === "stagger")) {
        if (c.staggerTimer > 0) c.staggerTimer--;
        if (c.stateTimer > 0) c.stateTimer--;
        if ((!c.staggerTimer || c.staggerTimer <= 0) && (!c.stateTimer || c.stateTimer <= 0)) {
          c.state = "approach";
          c.staggerTimer = 0;
          c.stateTimer = 0;
        }
        continue;
      }

      // Squad Panic State (triggers when Captain dies)
      if (c.state === "panic") {
        c.x += 1.4; // Run backwards away from player
        c.stateTimer--;
        if (c.stateTimer <= 0) c.state = "approach";
        continue;
      }

      // Tactical Distance & FSM
      const targetDist = c.range || 38;

      if (c.isBoss) {
        // Boss movement & attacks are fully driven by updateBossPhase roaming FSM!
      } else if (c.x > p.x + targetDist) {
        c.state = "approach";
        const spd = c.speed * (c.hasCaptainBuff ? 1.3 : 1.0);
        c.x -= spd;
      } else {
        // In Attack Range!
        c.attackCooldown = (c.attackCooldown || 0) + 1;

        if (c.state !== "telegraph" && c.attackCooldown >= (c.hasCaptainBuff ? 32 : 45)) {
          c.state = "telegraph";
          c.stateTimer = 22; // 22 frames telegraph warning
        }

        if (c.state === "telegraph") {
          c.stateTimer--;
          if (c.stateTimer <= 0) {
            // EXECUTE ATTACK!
            c.state = "recovery";
            c.attackCooldown = 0;

            if (c.range && c.range > 100) {
              // Ranged Caster / Archer / Catapult fires projectile!
              if (!ARENA.enemyProjectiles) ARENA.enemyProjectiles = [];
              const isRadiant = (c.archetype || "").includes("radiant");
              const isCatapult = c.archetype === "catapult";
              ARENA.enemyProjectiles.push({
                x: c.x - 14,
                y: c.y - 4,
                speed: isCatapult ? 3.0 : 3.8,
                dmg: c.atk,
                color: isCatapult ? "#f97316" : (isRadiant ? "#38bdf8" : "#c084fc"),
                isBossFireball: isCatapult,
                reflected: false
              });
            } else {
              // Melee Strike on Player!
              if (p.isInvulnerable > 0) {
                spawnFloatingText(p.x, p.y - 20, "УВОРОТ! (I-FRAMES)", "#38bdf8");
              } else {
                const isDodge = Math.random() * 100 < (stats.dodge_chance || 10);
                if (isDodge) {
                  spawnFloatingText(p.x, p.y - 20, "УВОРОТ!", "#38bdf8");
                } else if (ARENA.parryWindow > 0) {
                  c.state = "stagger";
                  c.staggerTimer = 110;
                  c.attackCooldown = -30;
                  c.x += 40;
                  ARENA.hitstop = 8;
                  ARENA.cameraTrauma = Math.min(1.0, ARENA.cameraTrauma + 0.3);
                  addStylePoints(260, "PERFECT PARRY");
                  spawnFloatingText(c.x, c.y - 25, "💫 ПАРИРОВАНО! (+150% УРОНА)", "#facc15");
                  triggerHaptic("heavy");
                } else if (p.isBlocking || p.counterspellActive > 0) {
                  const bDmg = Math.max(2, Math.floor(c.atk * 0.25));
                  p.currentHp = Math.max(0, p.currentHp - bDmg);
                  spawnFloatingText(p.x, p.y - 20, `🛡️ БЛОК -${bDmg}`, "#38bdf8");
                  triggerHaptic("medium");
                  if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
                } else {
                  const def = Math.max(0, stats.defense || 5);
                  const floor = RPG_STATE.profile?.dungeon_floor || 1;
                  // Diminishing returns formula with floor scaling and 82% hard-cap (prevents 99.9% godmode)
                  const armorDr = Math.min(0.82, (def * 0.05) / (1.0 + def * 0.05 + floor * 0.4));
                  let rawDmg = Math.max(Math.floor(c.atk * 0.15), Math.floor(c.atk * 0.85 * (1.0 - armorDr)));
                  if (c.pureDamage) rawDmg = Math.floor(c.atk * 0.85); // Pure damage ignores armor!
                  if (p.fleshHeapActive > 0) rawDmg = Math.floor(rawDmg * 0.6);
                  if (p.crimsonActive > 0) rawDmg = Math.max(4, rawDmg - (p.crimsonBlock || 85));
                  const takenDmg = applyDamageToPlayer(rawDmg, c.pureDamage ? "pure" : (c.isMagic ? "magic" : "melee"));
                  if (takenDmg > 0) {
                    if (p.blademailActive > 0) {
                      safeDamageCreep(c, takenDmg, false);
                      spawnFloatingText(c.x, c.y - 30, `🪞 ВОЗВРАТКА -${takenDmg}`, "#facc15");
                    }
                    spawnFloatingText(p.x + 10, p.y - 15 - Math.random() * 15, `-${takenDmg}`, "#ef4444");
                    triggerHaptic("light");
                    if (ARENA.styleMeter) ARENA.styleMeter.score = Math.max(0, ARENA.styleMeter.score - 80);
                  }
                  if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
                }
              }
            }
          }
        }
      }

      // Creep Death Check
      if (c.hp <= 0) {
        if (c.archetype === "captain" || c.isCaptain) {
          addStylePoints(220, "CAPTAIN DOWN");
          for (const remaining of ARENA.creeps) {
            if (remaining !== c && !remaining.isBoss) {
              remaining.state = "panic";
              remaining.stateTimer = 150; // 2.5s panic
              spawnFloatingText(remaining.x, remaining.y - 25, "😱 ПАНИКА ОТРЯДА!", "#38bdf8");
            }
          }
        }
        ARENA.creeps.splice(i, 1);
        handleCreepDeath(c);
      }
    }

    updatePickups();
    updateFloatingTexts();
    updateClouds();
  }

  function updatePickups() {
    const p = ARENA.player;
    if (!ARENA.pickups) return;
    for (let i = ARENA.pickups.length - 1; i >= 0; i--) {
      const it = ARENA.pickups[i];
      it.x -= 3.5;
      it.y -= 0.4;
      if (it.x < p.x + 30) {
        ARENA.pickups.splice(i, 1);
        if (it.type === "gold") {
          const g = it.value || 10;
          if (RPG_STATE.profile) RPG_STATE.profile.gold = (RPG_STATE.profile.gold || 0) + g;
          spawnFloatingText(p.x + 20, p.y - 25, `+${g} 🪙`, "#facc15");
        } else if (it.type === "xp") {
          const x = it.value || 15;
          if (RPG_STATE.profile) {
            RPG_STATE.profile.xp = (RPG_STATE.profile.xp || 0) + x;
            checkLevelUpInArena();
          }
          spawnFloatingText(p.x + 20, p.y - 35, `+${x} XP`, "#38bdf8");
        } else if (it.type === "loot") {
          spawnFloatingText(p.x + 20, p.y - 35, "🎁 ТРОФЕЙНЫЙ СУНДУК!", "#a855f7");
          triggerHaptic("heavy");
          api.openRpgChest(RPG_STATE.profile?.dungeon_cleared || 10)
            .then((res) => {
              if (res.profile) RPG_STATE.profile = res.profile;
              openChestModal(res);
            })
            .catch((err) => console.warn("Loot chest drop error:", err));
        }
        triggerHaptic("light");
      }
    }
  }

  function updatePhysicalCoins() {
    if (!ARENA.physicalCoins || ARENA.physicalCoins.length === 0) return;
    const p = ARENA.player;
    const gravity = 0.38;

    for (let i = ARENA.physicalCoins.length - 1; i >= 0; i--) {
      const c = ARENA.physicalCoins[i];
      c.age++;

      if (c.age > c.magnetDelay) {
        const dx = p.x - c.x;
        const dy = (p.y - 8) - c.y;
        const dist = Math.hypot(dx, dy);
        if (dist < 22) {
          c.collected = true;
          ARENA.physicalCoins.splice(i, 1);
          triggerHaptic("light");
          if (c.type === "gem") {
            if (RPG_STATE.profile) RPG_STATE.profile.gems = (RPG_STATE.profile.gems || 0) + 1;
            spawnFloatingText(p.x, p.y - 20, "+1 💎", "#38bdf8");
          } else {
            if (RPG_STATE.profile) RPG_STATE.profile.gold = (RPG_STATE.profile.gold || 0) + 15;
            spawnFloatingText(p.x, p.y - 20, "+15 🪙", "#facc15");
          }
          continue;
        }
        const pullSpeed = Math.min(12, 2.5 + (c.age - c.magnetDelay) * 0.28);
        c.x += (dx / dist) * pullSpeed;
        c.y += (dy / dist) * pullSpeed;
        c.z = Math.max(0, c.z - 0.45);
      } else {
        c.x += c.vx;
        c.y += c.vy;
        c.z += c.vz;
        c.vz -= gravity;

        if (c.z <= 0) {
          c.z = 0;
          c.vz = -c.vz * 0.52;
          c.vx *= 0.75;
          c.vy *= 0.75;
          c.bounces++;
        }
      }
    }
  }

  function updateFallingChest() {
    const fc = ARENA.fallingChest;
    if (!fc) return;

    if (!fc.landed) {
      fc.vy += 0.45;
      fc.y += fc.vy;
      if (fc.y >= fc.targetY) {
        fc.y = fc.targetY;
        fc.landed = true;
        ARENA.cameraTrauma = 0.75;
        triggerHaptic("heavy");
        ARENA.specialEffects.push({
          type: "stomp_ring",
          x: fc.x,
          y: fc.targetY + 14,
          radius: 12,
          maxRadius: 60,
          timer: 25
        });
      }
    } else {
      fc.beamAlpha = Math.min(0.85, fc.beamAlpha + 0.03);
      fc.rayAngle += 0.02;

      if (Math.random() < 0.45) {
        fc.sparkles.push({
          x: fc.x + (Math.random() * 36 - 18),
          y: fc.y + 10,
          vy: -1.2 - Math.random() * 1.8,
          alpha: 1,
          size: 2 + Math.random() * 3
        });
      }
      for (let j = fc.sparkles.length - 1; j >= 0; j--) {
        const s = fc.sparkles[j];
        s.y += s.vy;
        s.alpha -= 0.025;
        if (s.alpha <= 0) fc.sparkles.splice(j, 1);
      }
    }
  }

  function spawnLootExplosion(originX, originY, bossTmpl) {
    bossTmpl = bossTmpl || {};
    const count = 36;
    ARENA.physicalCoins = ARENA.physicalCoins || [];
    for (let i = 0; i < count; i++) {
      const isGem = (i % 3 === 0);
      const angle = (Math.PI * 2 * i) / count + (Math.random() - 0.5) * 0.5;
      const speed = 2.5 + Math.random() * 5.5;
      ARENA.physicalCoins.push({
        x: originX,
        y: originY,
        z: 15 + Math.random() * 10,
        vx: Math.cos(angle) * speed,
        vy: (Math.random() - 0.5) * 2.2,
        vz: 4.5 + Math.random() * 6.5,
        type: isGem ? "gem" : "gold",
        icon: isGem ? "💎" : "🪙",
        size: isGem ? 14 : 16,
        bounces: 0,
        age: 0,
        magnetDelay: 45 + Math.floor(Math.random() * 25),
        collected: false
      });
    }

    ARENA.fallingChest = {
      x: Math.min(ARENA.width - 70, Math.max(130, originX)),
      y: -60,
      targetY: ARENA.roadY - 22,
      vy: 1.2,
      landed: false,
      beamAlpha: 0,
      rayAngle: 0,
      opened: false,
      sparkles: []
    };
  }

  function updateFloatingTexts() {
    for (let i = ARENA.floatingTexts.length - 1; i >= 0; i--) {
      const ft = ARENA.floatingTexts[i];
      ft.y -= 0.8;
      ft.opacity -= 0.02;
      if (ft.opacity <= 0) ARENA.floatingTexts.splice(i, 1);
    }
  }

  function updateClouds() {
    for (const cloud of ARENA.clouds) {
      cloud.x -= cloud.speed;
      if (cloud.x < -40) cloud.x = ARENA.width + 40;
    }
  }

  // ---------------------------------------------------------------------------
  // BOSS ARENA: DODGE ROLL
  // ---------------------------------------------------------------------------

  function playerBossArenaDodge() {
    if (!ARENA.bossArenaMode) return;
    if (ARENA.dodgeCooldown > 0 || ARENA.dodgeActive > 0) return;
    const p = ARENA.player;
    // Determine dodge direction: away from boss or toward movement input
    if (ARENA.moveInput.left) {
      ARENA.dodgeDir = -1;
    } else if (ARENA.moveInput.right) {
      ARENA.dodgeDir = 1;
    } else {
      // Default: away from boss
      const boss = ARENA.bossEntity;
      ARENA.dodgeDir = boss && boss.x > p.x ? -1 : 1;
    }
    ARENA.dodgeActive = 12; // ~0.2s of i-frame roll
    ARENA.dodgeCooldown = 48; // ~0.8s cooldown
    if (!ARENA.dashGhosts) ARENA.dashGhosts = [];
    triggerHaptic("medium");
    spawnFloatingText(p.x, p.y - 20, "УВОРОТ!", "#38bdf8");
  }

  // ---------------------------------------------------------------------------
  // BOSS PHASE LOGIC & COMBAT FSM (Poise, Telegraphs, Shockwaves, Stagger)
  // ---------------------------------------------------------------------------

  function updateBossPhase() {
    // In Top-Down 360° Brawl Arena, boss AI and movement are handled EXCLUSIVELY by the Top-Down State Machine!
    // NEVER allow legacy side-scrolling phase shifts, teleports, leap gravity, or horizontal rushes to run!
    if (ARENA.topDownMode || ARENA.isRaidBossBattle) return;

    const boss = ARENA.bossEntity;
    if (!boss || boss.hp <= 0) return;

    const p = ARENA.player;
    if (boss.poise === undefined) {
      boss.poise = 300;
      boss.maxPoise = 300;
      boss.defense = boss.defense || 14;
    }

    // 1. Stagger Recovery
    if (boss.isStaggered) {
      boss.staggerTimer--;
      boss.jumpY = 0;
      boss.jumpVY = 0;
      if (boss.staggerTimer <= 0) {
        boss.isStaggered = false;
        boss.poise = boss.maxPoise;
        boss.actionState = "roam";
        boss.actionTimer = 0;
        spawnFloatingText(boss.x, boss.y - 30, "😤 БОСС ВОССТАНОВИЛСЯ!", "#f97316");
      }
      return; // Stunned boss cannot move or act!
    }

    const hpPct = boss.hp / boss.maxHp;

    // 2. God Mode check (5 minutes / 300 seconds)
    boss.battleStartTime = boss.battleStartTime || Date.now();
    const elapsedMs = Date.now() - boss.battleStartTime;
    boss.enrageTimer = (boss.enrageTimer || 0) + 1;
    if (elapsedMs >= 300000 || boss.enrageTimer >= 18000) {
      if (!boss.isGodMode) {
        boss.isGodMode = true;
        boss.enraged = true;
        boss.enrageStage = "god_mode";
        boss.speed = Math.max(3.0, (boss.speed || 0.85) * 3.5);
        ARENA.cameraTrauma = 1.0;
        ARENA.hitstop = 15;
        spawnFloatingText(boss.x, boss.y - 45, "⚡⚡ РЕЖИМ БОГА: БЕРСЕРК! ⚡⚡", "#ef4444");
        triggerHaptic("heavy");
      }
      const regenPerSec = Math.max(500, Math.floor((boss.maxHp || 10000) * 0.05));
      const regenPerFrame = Math.max(1, Math.floor(regenPerSec / 60));
      boss.hp = Math.min(boss.maxHp, boss.hp + regenPerFrame);
      if (ARENA.frameCount % 60 === 0) {
        spawnFloatingText(boss.x, boss.y - 30, `✨ +${Math.round(regenPerSec)} РЕГЕН БОГА`, "#22c55e");
      }
    } else if (hpPct <= 0.35 && !boss.enraged) {
      boss.enraged = true;
      boss.speed = Math.min(1.4, (boss.speed || 0.85) * 1.45);
      boss.atk = Math.floor(boss.atk * 1.35);
      ARENA.cameraTrauma = 0.95;
      ARENA.hitstop = 10;
      spawnFloatingText(boss.x, boss.y - 45, "🔥 ЯРОСТЬ БОССА (ENRAGE)! 🔥", "#ef4444");
      triggerHaptic("heavy");
    }

    // 3. Tormentor Reflective Shield
    const bId = (boss.bossType || boss.name || "").toLowerCase();
    const isTormentor = bId.includes("tormentor") || bId.includes("терзатель");
    if (isTormentor || (hpPct < 0.65 && hpPct > 0.30)) {
      boss.tormentorTimer = (boss.tormentorTimer || 0) + 1;
      if (!boss.tormentorShield && boss.tormentorTimer % 240 === 0) {
        boss.tormentorShield = true;
        boss.tormentorShieldTimer = 180; // 3 seconds
        spawnFloatingText(boss.x, boss.y - 35, "🔮 ОТРАЖАЮЩИЙ ПАНЦИРЬ!", "#c084fc");
        triggerHaptic("warning");
      }
    }
    if (boss.tormentorShield) {
      boss.tormentorShieldTimer--;
      if (boss.tormentorShieldTimer <= 0) {
        boss.tormentorShield = false;
        spawnFloatingText(boss.x, boss.y - 35, "✨ ПАНЦИРЬ СПАЛ!", "#a855f7");
      }
    }

    // 4. Boss Roaming & Action State Machine (Roam, Leap, Charge, Recoil, Teleport)
    boss.actionState = boss.actionState || "roam";
    boss.moveDir = boss.moveDir || -1;
    boss.decisionTimer = (boss.decisionTimer || 110) - 1;

    // A. LEAP WINDUP -> PREPARING JUMP
    if (boss.actionState === "leap_windup") {
      boss.actionTimer--;
      boss.x += (Math.random() - 0.5) * 2;
      if (boss.actionTimer <= 0) {
        boss.actionState = "leap";
        boss.jumpVY = -12.5;
        boss.targetX = p.x + 45;
        triggerHaptic("medium");
      }
      return;
    }

    // B. LEAP AIRBORNE
    if (boss.actionState === "leap") {
      boss.jumpY = (boss.jumpY || 0) + boss.jumpVY;
      boss.jumpVY += 0.82; // Gravity
      boss.x += (boss.targetX - boss.x) * 0.08;

      if (boss.jumpY >= 0) {
        // Crash landing
        boss.jumpY = 0;
        boss.jumpVY = 0;
        ARENA.cameraTrauma = 0.85;
        triggerHaptic("heavy");

        ARENA.specialEffects.push({
          type: "stomp_ring",
          x: boss.x,
          y: ARENA.roadY - 14,
          radius: 12,
          maxRadius: 75,
          timer: 24
        });

        ARENA.shockwaves.push({
          x: boss.x,
          y: ARENA.roadY - 14,
          radius: 15,
          maxRadius: ARENA.width + 60,
          speed: boss.enraged ? 6.5 : 4.8,
          damage: Math.floor(boss.atk * 1.35),
          hitPlayer: false
        });

        spawnFloatingText(boss.x, boss.y - 35, "💥 СОКРУШИТЕЛЬНЫЙ УДАР!", "#ef4444");

        if (Math.abs(boss.x - p.x) < 55) {
          if (ARENA.parryWindow > 0) {
            boss.isStaggered = true;
            boss.staggerTimer = 110;
            boss.actionState = "roam";
            spawnFloatingText(boss.x, boss.y - 25, "💫 ПАРИРОВАНО! (+150% УРОНА)", "#facc15");
            return;
          }
          if (!p.isInvulnerable && !p.isBlocking) {
            const rawDmg = calculateBossAttackDamage(boss, 0.95);
            const actualDmg = applyDamageToPlayer(rawDmg, "melee");
            spawnFloatingText(p.x, p.y - 25, `-${actualDmg}`, "#ef4444");
            if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
          }
        }

        boss.actionState = "recoil";
        boss.actionTimer = 40;
      }
      return;
    }

    // C. CHARGE WINDUP
    if (boss.actionState === "charge_windup") {
      boss.actionTimer--;
      boss.x += (Math.random() - 0.5) * 1.5;
      if (boss.actionTimer <= 0) {
        boss.actionState = "charging";
        boss.actionTimer = 35;
        triggerHaptic("heavy");
        spawnFloatingText(boss.x - 20, boss.y - 25, "💨 ТАРАННЫЙ РЫВОК!", "#f97316");
      }
      return;
    }

    // D. CHARGING
    if (boss.actionState === "charging") {
      boss.x -= 4.8;
      if (ARENA.specialEffects && Math.random() < 0.4) {
        ARENA.specialEffects.push({
          type: "blink_poof",
          x: boss.x + boss.radius,
          y: ARENA.roadY - 10,
          timer: 12
        });
      }

      if (boss.x <= p.x + 42 || boss.actionTimer-- <= 0) {
        if (boss.x <= p.x + 48 && !p.isInvulnerable && !p.isBlocking && ARENA.parryWindow <= 0) {
          const rawDmg = calculateBossAttackDamage(boss, 1.35);
          const actualDmg = applyDamageToPlayer(rawDmg, "charge");
          spawnFloatingText(p.x, p.y - 20, `💥 ТАРАН -${actualDmg}`, "#ef4444");
          ARENA.cameraTrauma = 0.5;
          if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
        }
        boss.actionState = "recoil";
        boss.actionTimer = 45;
      }
      return;
    }

    // E. RECOIL
    if (boss.actionState === "recoil") {
      boss.actionTimer--;
      if (boss.x < ARENA.width - 90) {
        boss.x += 1.6;
      }
      if (boss.actionTimer <= 0) {
        boss.actionState = "roam";
        boss.moveDir = -1;
      }
      return;
    }

    // F. ROAM (Active Arena Traversal)
    if (boss.actionState === "roam") {
      const minX = p.x + 48;
      const maxX = ARENA.width - 45;

      if (boss.x <= minX) {
        boss.x = minX;
        boss.attackCooldown = (boss.attackCooldown || 0) + 1;
        if (boss.attackCooldown >= 35) {
          boss.attackCooldown = 0;
          if (!p.isInvulnerable && !p.isBlocking && ARENA.parryWindow <= 0) {
            const rawDmg = calculateBossAttackDamage(boss, 0.85);
            const actualDmg = applyDamageToPlayer(rawDmg, "roam");
            spawnFloatingText(p.x, p.y - 20, `💥 -${actualDmg}`, "#ef4444");
            triggerHaptic("light");
            if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
          }
          if (Math.random() < 0.45) boss.moveDir = 1;
        }
      } else if (boss.x >= maxX) {
        boss.moveDir = -1;
      }

      if (boss.x > minX || boss.moveDir === 1) {
        const spd = (boss.speed || 0.85) * (boss.enraged ? 1.4 : 1.0);
        boss.x += boss.moveDir * spd;
      }

      // Special Move Decision
      if (boss.decisionTimer <= 0) {
        boss.decisionTimer = boss.enraged ? (80 + Math.floor(Math.random() * 50)) : (130 + Math.floor(Math.random() * 70));

        const roll = Math.random();
        const isCasterBoss = isTormentor || bId.includes("лич") || bId.includes("archlich");

        if (isCasterBoss && roll < 0.25) {
          // Phase Shift / Teleport
          const newX = boss.x > 180 ? (p.x + 55) : (ARENA.width - 65);
          ARENA.specialEffects.push({ type: "blink_poof", x: boss.x, y: boss.y, timer: 18 });
          boss.x = newX;
          ARENA.specialEffects.push({ type: "blink_poof", x: boss.x, y: boss.y, timer: 18 });
          spawnFloatingText(boss.x, boss.y - 35, "🌀 ФАЗОВЫЙ СДВИГ!", "#c084fc");
          triggerHaptic("medium");
        } else if (roll < 0.48) {
          // Attack 1: Ground Slam / Quake (Danger Circle at player pos)
          const targetX = Math.max(35, Math.min(ARENA.width - 35, p.x));
          if (!ARENA.dangerZones) ARENA.dangerZones = [];
          ARENA.dangerZones.push({
            type: "circle",
            cx: targetX,
            cy: ARENA.roadY - 8,
            r: 46,
            timer: 48,
            maxTimer: 48,
            phase: "telegraph",
            activeFrames: 14,
            damage: Math.floor(boss.atk * 1.35),
            hitPlayer: false
          });
          spawnFloatingText(boss.x, boss.y - 35, "⚠️ РАЗЛОМ ЗЕМЛИ!", "#ef4444");
          triggerHaptic("warning");
        } else if (roll < 0.74) {
          // Attack 2: Cleave / Melee Swipe (Wide red rectangle in front of boss)
          const swipeW = 100;
          const swipeX = boss.x > p.x ? (boss.x - swipeW) : boss.x;
          if (!ARENA.dangerZones) ARENA.dangerZones = [];
          ARENA.dangerZones.push({
            type: "rect",
            x: swipeX,
            y: ARENA.roadY - 26,
            w: swipeW,
            h: 38,
            timer: 42,
            maxTimer: 42,
            phase: "telegraph",
            activeFrames: 12,
            damage: Math.floor(boss.atk * 1.25),
            hitPlayer: false
          });
          spawnFloatingText(boss.x, boss.y - 35, "⚠️ СОКРУШИТЕЛЬНЫЙ ВЗМАХ!", "#f97316");
          triggerHaptic("warning");
        } else if (roll < 0.88) {
          // Attack 3: Leap Airborne (Drop danger circle where boss will land)
          boss.actionState = "leap_windup";
          boss.actionTimer = 26;
          const landX = Math.max(45, Math.min(ARENA.width - 45, p.x + 25));
          if (!ARENA.dangerZones) ARENA.dangerZones = [];
          ARENA.dangerZones.push({
            type: "circle",
            cx: landX,
            cy: ARENA.roadY - 8,
            r: 52,
            timer: 45,
            maxTimer: 45,
            phase: "telegraph",
            activeFrames: 14,
            damage: Math.floor(boss.atk * 1.5),
            hitPlayer: false
          });
          spawnFloatingText(boss.x, boss.y - 35, "⚠️ ПРЫЖОК ОЗЕМЬ!", "#ef4444");
          triggerHaptic("warning");
        } else {
          // Attack 4: Charging Ram
          boss.actionState = "charge_windup";
          boss.actionTimer = 30;
          if (!ARENA.dangerZones) ARENA.dangerZones = [];
          ARENA.dangerZones.push({
            type: "rect",
            x: 0,
            y: ARENA.roadY - 22,
            w: boss.x,
            h: 32,
            timer: 36,
            maxTimer: 36,
            phase: "telegraph",
            activeFrames: 24,
            damage: Math.floor(boss.atk * 1.1),
            hitPlayer: false
          });
          spawnFloatingText(boss.x, boss.y - 35, "⚠️ ЗАМАХ ДЛЯ РЫВКА!", "#f97316");
          triggerHaptic("warning");
        }
      }
    }

    // 5. Periodic Projectile Fireball
    boss.projectileTimer = (boss.projectileTimer || 0) + 1;
    const pInterval = boss.enraged ? 120 : 180;
    if (boss.projectileTimer % pInterval === 0 && boss.actionState !== "leap") {
      ARENA.bossProjectiles.push({
        x: boss.x - 20,
        y: boss.y - 6,
        speed: boss.enraged ? 4.2 : 2.8,
        damage: Math.floor(boss.atk * 1.1),
        warned: false
      });
      spawnFloatingText(boss.x - 15, boss.y - 20, "🔥", "#f97316");
    }
  }

  // ---------------------------------------------------------------------------
  // TRIO SQUAD COMPANIONS & PARTY CONTROLS
  // ---------------------------------------------------------------------------

  function initBossCompanions() {
    const p = ARENA.player;
    const hClass = (RPG_STATE.profile?.hero_class || "pudge").toLowerCase();

    let c1Class = "juggernaut";
    let c1Name = "Юрнеро";
    let c2Class = "pa";
    let c2Name = "Мортред";

    if (hClass.includes("juggernaut")) {
      c1Class = "wk";
      c1Name = "Остарион";
    }
    if (hClass.includes("pa")) {
      c2Class = "am";
      c2Name = "Магина";
    }

    ARENA.bossCompanions = [
      {
        id: "comp1",
        name: c1Name,
        heroClass: c1Class,
        x: p.x + 26,
        baseX: p.x + 26,
        y: p.y - 20,
        baseY: p.y - 20,
        radius: 17,
        attackCooldown: 25,
        attackPeriod: 46,
        slashAnimation: null
      },
      {
        id: "comp2",
        name: c2Name,
        heroClass: c2Class,
        x: p.x + 22,
        baseX: p.x + 22,
        y: p.y + 20,
        baseY: p.y + 20,
        radius: 17,
        attackCooldown: 48,
        attackPeriod: 60,
        slashAnimation: null
      }
    ];
  }

  function updateBossCompanions() {
    if (!ARENA.isBossActive || (ARENA.bossPartyMode || "trio") !== "trio") {
      ARENA.bossCompanions = [];
      return;
    }

    if (!ARENA.bossCompanions || ARENA.bossCompanions.length === 0) {
      initBossCompanions();
    }

    const boss = ARENA.bossEntity;
    if (!boss || boss.hp <= 0) return;

    const p = ARENA.player;
    const stats = RPG_STATE.profile?.stats || {};
    const baseAtk = Math.max(30, Math.floor(((stats.min_atk || 30) + (stats.max_atk || 50)) / 2));

    for (let ci = 0; ci < ARENA.bossCompanions.length; ci++) {
      const comp = ARENA.bossCompanions[ci];
      if (comp.slashAnimation) {
        comp.slashAnimation.timer--;
        if (comp.slashAnimation.timer <= 0) comp.slashAnimation = null;
      }

      // TOP-DOWN 3-HERO SQUAD MOVEMENT & FORMATION
      if (ARENA.topDownMode || ARENA.isRaidBossBattle) {
        // Formation: Companion 1 to the left flank, Companion 2 to the right flank
        const offsetX = ci === 0 ? -34 : 34;
        const offsetY = 14;
        const targetX = Math.max(28, Math.min(ARENA.width - 28, p.x + offsetX));
        const targetY = Math.max(38, Math.min(ARENA.height - 38, p.y + offsetY));

        // Smooth follower lerp so friends run right alongside player!
        comp.x += (targetX - comp.x) * 0.14;
        comp.y += (targetY - comp.y) * 0.14;
        comp.facing = boss.x >= comp.x ? 1 : -1;
      }

      comp.attackCooldown = (comp.attackCooldown || 0) - 1;
      if (comp.attackCooldown <= 0) {
        comp.attackCooldown = (comp.attackPeriod || 45) + Math.floor(Math.random() * 15);

        if (comp.heroClass === "juggernaut" || comp.heroClass === "wk") {
          // Warrior Companion Slash
          comp.slashAnimation = { radius: 28, timer: 12, isMagic: false };
          const dmg = applyDamageToBoss(boss, Math.floor(baseAtk * 0.38));
          if (boss.poise !== undefined) boss.poise = Math.max(0, boss.poise - 5);
          spawnFloatingText(boss.x - 12 + Math.random() * 24, boss.y - 20 - Math.random() * 10, `⚔️ ${comp.name} -${dmg}`, "#fbbf24");
        } else {
          // Ranger / Assassin Companion Projectile
          const isCrit = Math.random() < 0.30;
          const dmg = Math.floor(baseAtk * (isCrit ? 0.75 : 0.35));
          const pAngle = Math.atan2(boss.y - comp.y, boss.x - comp.x);
          ARENA.playerProjectiles.push({
            type: "topdown_shot",
            x: comp.x + Math.cos(pAngle) * 12,
            y: comp.y + Math.sin(pAngle) * 12,
            vx: Math.cos(pAngle) * 8.5,
            vy: Math.sin(pAngle) * 8.5,
            speed: 8.5,
            target: boss,
            dmg: dmg,
            isCrit: isCrit,
            radius: 5.0,
            color: isCrit ? "#f59e0b" : "#38bdf8",
            distTraveled: 0,
            maxDist: 850
          });
        }
      }
    }
  }

  function toggleBossPartyMode() {
    const cur = ARENA.bossPartyMode || "trio";
    const next = cur === "trio" ? "solo" : "trio";
    ARENA.bossPartyMode = next;
    try {
      localStorage.setItem("rpg_boss_party_mode", next);
    } catch (e) {}

    if (next === "trio") {
      initBossCompanions();
      spawnFloatingText(ARENA.player.x + 30, ARENA.player.y - 45, "👥 ОТРЯД: 3 ГЕРОЯ В БОЮ!", "#10b981");
    } else {
      ARENA.bossCompanions = [];
      spawnFloatingText(ARENA.player.x + 30, ARENA.player.y - 45, "👤 РЕЖИМ: СОЛО ДУЭЛЬ!", "#c084fc");
    }
    triggerHaptic("medium");
  }

  function spawnBossMinions() {
    const floor = RPG_STATE.profile?.dungeon_floor || 1;
    const scale = 1.0 + floor * 0.15;
    for (let i = 0; i < 4; i++) {
      ARENA.creeps.push({
        name: "Миньон Рошана",
        icon: "👻",
        team: "dire",
        badgeBg: "#4a044e",
        badgeBorder: "#c084fc",
        x: ARENA.width + 30 + i * 50,
        y: ARENA.roadY - 15 + (Math.random() * 20 - 10),
        radius: 13,
        speed: 1.8,
        hp: Math.floor(45 * scale),
        maxHp: Math.floor(45 * scale),
        atk: Math.floor(9 * scale),
        isBoss: false,
        isMinion: true,
        attackCooldown: 0
      });
    }
  }

  // ===========================================================================
  // COMBAT ENGINE HELPERS: STYLE METER, DASH & DEFLECTION
  // ===========================================================================

  function addStylePoints(pts, reason) {
    if (!ARENA.styleMeter) ARENA.styleMeter = { score: 0, rank: "D", progress: 0, decayTimer: 0, maxRank: "D" };
    const sm = ARENA.styleMeter;
    sm.score += pts;
    sm.decayTimer = 120; // 2 seconds before decay begins

    const thresholds = [
      { rank: "D", min: 0, max: 300 },
      { rank: "C", min: 300, max: 750 },
      { rank: "B", min: 750, max: 1400 },
      { rank: "A", min: 1400, max: 2200 },
      { rank: "S", min: 2200, max: 3200 },
      { rank: "SS", min: 3200, max: 4500 },
      { rank: "SSS", min: 4500, max: 99999 }
    ];

    let currentRank = "D";
    let progress = 0;
    for (let i = 0; i < thresholds.length; i++) {
      const t = thresholds[i];
      if (sm.score >= t.min) {
        currentRank = t.rank;
        if (t.max === 99999) {
          progress = 1.0;
        } else {
          progress = (sm.score - t.min) / (t.max - t.min);
        }
      }
    }

    if (currentRank !== sm.rank) {
      sm.rank = currentRank;
      triggerHaptic("heavy");
      if (currentRank === "S" || currentRank === "SS" || currentRank === "SSS") {
        spawnFloatingText(ARENA.player.x + 10, ARENA.player.y - 38, `🔥 STYLE RANK [${currentRank}]!`, "#f43f5e");
      }
    }
    sm.progress = progress;
  }

  function playerPerformDash() {
    const p = ARENA.player;
    if (p.dashCooldown > 0) return;

    p.dashCooldown = 32;
    p.isInvulnerable = 14;
    p.isDashing = true;
    p.dashTimer = 10;

    // Check for Perfect Dodge (Witch-Time)
    let perfectDodge = false;
    if (ARENA.enemyProjectiles) {
      for (const proj of ARENA.enemyProjectiles) {
        if (!proj.reflected && Math.abs(proj.x - p.x) < 65) {
          perfectDodge = true;
          break;
        }
      }
    }
    if (!perfectDodge && ARENA.bossProjectiles) {
      for (const bp of ARENA.bossProjectiles) {
        if (Math.abs(bp.x - p.x) < 65) {
          perfectDodge = true;
          break;
        }
      }
    }
    if (!perfectDodge && ARENA.creeps) {
      for (const c of ARENA.creeps) {
        if (c.state === "telegraph" && Math.abs(c.x - p.x) < 55) {
          perfectDodge = true;
          break;
        }
      }
    }

    if (perfectDodge) {
      ARENA.timeScale = 0.2;
      ARENA.sloMoTimer = 26;
      p.critBuff = true;
      ARENA.cameraTrauma = Math.min(1.0, ARENA.cameraTrauma + 0.35);
      addStylePoints(260, "PERFECT DODGE");
      spawnFloatingText(p.x + 15, p.y - 30, "⚡ PERFECT DODGE! (WITCH-TIME)", "#38bdf8");
      triggerHaptic("heavy");
    } else {
      triggerHaptic("light");
    }

    // Spawn 3 Ghost Afterimages
    if (!ARENA.dashGhosts) ARENA.dashGhosts = [];
    const heroClass = (RPG_STATE.profile?.hero_class || "pudge").toLowerCase();
    for (let g = 0; g < 3; g++) {
      ARENA.dashGhosts.push({
        x: p.x - (g * 14),
        y: p.y,
        radius: p.radius,
        heroClass: heroClass,
        alpha: 0.65 - (g * 0.18),
        decay: 0.05
      });
    }
  }

  function playerBlock() {
    const p = ARENA.player;
    ARENA.parryWindow = 16; // 16 frames perfect parry window
    ARENA.player.isBlocking = true;
    ARENA.player.blockTimer = 22;

    ARENA.specialEffects.push({
      type: "block_flash",
      x: p.x + 10,
      y: p.y,
      radius: 38,
      timer: 15
    });

    // DEFLECT ENEMY PROJECTILES (Reflect magic bolts and arrows back at enemies!)
    let deflectedAny = false;
    if (ARENA.enemyProjectiles) {
      for (const proj of ARENA.enemyProjectiles) {
        if (!proj.reflected && Math.abs(proj.x - p.x) < 65) {
          proj.reflected = true;
          proj.speed = -Math.abs(proj.speed || 3.5) * 2.0; // Fly right towards enemies at high speed
          proj.dmg = Math.floor((proj.dmg || 22) * 2.5);  // 2.5x critical reflection damage
          proj.color = "#facc15";
          ARENA.hitstop = 8;
          ARENA.cameraTrauma = Math.min(1.0, ARENA.cameraTrauma + 0.35);
          addStylePoints(300, "DEFLECT");
          spawnFloatingText(p.x + 15, p.y - 28, "🪞 ОТРАЖЕНИЕ! (2.5x УРОН)", "#facc15");
          triggerHaptic("heavy");
          deflectedAny = true;
          break;
        }
      }
    }

    if (ARENA.blockWindowActive) {
      triggerPerfectParry();
      ARENA.blockWindowActive = false;
    } else if (!deflectedAny) {
      // Active Melee Parry on attacking creeps
      let parriedMelee = false;
      if (ARENA.creeps) {
        for (const c of ARENA.creeps) {
          if (!c.isBoss && Math.abs(c.x - p.x) < 55 && (c.state === "telegraph" || c.attackCooldown > 0)) {
            c.state = "stagger";
            c.staggerTimer = 110;
            c.attackCooldown = 0;
            ARENA.hitstop = 10;
            ARENA.cameraTrauma = Math.min(1.0, ARENA.cameraTrauma + 0.35);
            addStylePoints(220, "PARRY");
            spawnFloatingText(c.x, c.y - 25, "⚡ ПАРИРОВАНИЕ! СТАН!", "#facc15");
            triggerHaptic("heavy");
            parriedMelee = true;
            break;
          }
        }
      }
      if (!parriedMelee) {
        spawnFloatingText(p.x + 15, p.y - 25, "🛡️ БЛОК / ПАРИРОВАНИЕ!", "#38bdf8");
        triggerHaptic("medium");
      }
    }
  }

  function triggerPerfectParry() {
    const boss = ARENA.bossEntity;
    ARENA.hitstop = 12; // 12-frame hitstop freeze
    ARENA.cameraTrauma = 0.8;
    ARENA.bossProjectiles = [];
    ARENA.shockwaves = [];
    triggerHaptic("heavy");

    if (boss) {
      const parryDmg = Math.floor((ARENA.player.attackRange || 25) * 2.2);
      boss.poise = Math.max(0, (boss.poise || 300) - 80);
      parryDmg = applyDamageToBoss(boss, parryDmg, true);
      spawnFloatingText(boss.x, boss.y - 30, `⚡ PERFECT PARRY! -${parryDmg} ⚡`, "#facc15");

      if (boss.poise <= 0 && !boss.isStaggered) {
        boss.isStaggered = true;
        boss.staggerTimer = 210;
        spawnFloatingText(boss.x, boss.y - 45, "💫 ОШЕЛОМЛЕН! (+150% УРОНА)", "#facc15");
      }

      if (boss.hp <= 0) {
        const idx = ARENA.creeps.indexOf(boss);
        if (idx !== -1) ARENA.creeps.splice(idx, 1);
        handleCreepDeath(boss);
      }
    }
  }

  function hitQTE() {
    if (!ARENA.qteActive) return;
    ARENA.qteActive = false;
    if (ARENA.bossEntity) {
      const stats = RPG_STATE.profile?.stats || {};
      const megaDmg = Math.floor((stats.max_atk || 30) * 5.0);
      const qDmg = applyDamageToBoss(ARENA.bossEntity, megaDmg, true);
      spawnFloatingText(ARENA.bossEntity.x, ARENA.bossEntity.y - 25, `⚡ МЕГА КРИТ! -${qDmg}`, "#facc15");
      triggerHaptic("heavy");
      if (ARENA.bossEntity.hp <= 0) {
        const idx = ARENA.creeps.indexOf(ARENA.bossEntity);
        if (idx !== -1) ARENA.creeps.splice(idx, 1);
        handleCreepDeath(ARENA.bossEntity);
      }
    }
  }

  // ---------------------------------------------------------------------------
  // DOTA 2 CREEP SPAWNING (Waves 1-19)
  // ---------------------------------------------------------------------------

  function spawnArenaCreep() {
    const floor = RPG_STATE.profile?.dungeon_floor || 1;
    const wave = ARENA.waveNumber || 1;
    // Balanced Exponential Scaling: HP scales with 1.28^floor, ATK scales with 1.23^floor
    const scaleHp = Math.pow(1.18, Math.max(0, floor - 1)) * (1.0 + (wave - 1) * 0.05);
    const scaleAtk = Math.pow(1.15, Math.max(0, floor - 1)) * (1.0 + (wave - 1) * 0.04);

    let pool = [];
    // Dynamic Creep Hierarchy based on Dungeon Floor
    if (floor >= 200) {
      pool = [
        { name: "Страж Апокалипсиса", archetype: "apocalypse_doomguard", radius: 24, speed: 0.75, baseHp: 5500, baseAtk: 250, range: 48, pureDamage: true },
        { name: "Астральный Призрак", archetype: "astral_phantom", radius: 18, speed: 1.15, baseHp: 4800, baseAtk: 300, range: 42, pureDamage: true },
        { name: "Космический Разрушитель", archetype: "cosmic_annihilator", radius: 22, speed: 0.70, baseHp: 6200, baseAtk: 340, range: 190 }
      ];
    } else if (floor >= 100) {
      pool = [
        { name: "Древний Титан Скал", archetype: "ancient_titan", radius: 24, speed: 0.50, baseHp: 2800, baseAtk: 140, range: 48, earthquake: true },
        { name: "Архимаг Хаоса", archetype: "chaos_harbinger", radius: 17, speed: 0.75, baseHp: 2200, baseAtk: 160, range: 190 },
        { name: "Паладин Падших", archetype: "fallen_paladin", radius: 19, speed: 0.80, baseHp: 2500, baseAtk: 130, range: 44 },
        { name: "Повелитель Пустоты", archetype: "void_terror", radius: 19, speed: 0.70, baseHp: 1200, baseAtk: 90, range: 180 }
      ];
    } else if (floor >= 80) {
      pool = [
        { name: "Повелитель Пустоты", archetype: "void_terror", radius: 19, speed: 0.70, baseHp: 1200, baseAtk: 90, range: 180, timeDilation: true },
        { name: "Абиссальный Бегемот", archetype: "abyssal_behemoth", radius: 22, speed: 0.65, baseHp: 1600, baseAtk: 110, range: 46 },
        { name: "Вестник Разлома", archetype: "rift_stalker", radius: 16, speed: 1.20, baseHp: 1100, baseAtk: 125, range: 40 },
        { name: "Кентавр-Завоеватель", archetype: "centaur_conqueror", radius: 20, speed: 0.75, baseHp: 900, baseAtk: 60, range: 44, retaliate: 25 }
      ];
    } else if (floor >= 50) {
      pool = [
        { name: "Кентавр-Завоеватель", archetype: "centaur_conqueror", radius: 20, speed: 0.75, baseHp: 900, baseAtk: 60, range: 44, retaliate: 25 },
        { name: "Инфернальный Дракон", archetype: "drake", radius: 20, speed: 0.85, baseHp: 850, baseAtk: 75, range: 180, fireBreath: true },
        { name: "Пламенный Маг", archetype: "pyro_magus", radius: 15, speed: 0.75, baseHp: 720, baseAtk: 82, range: 185 },
        { name: "Некромант Катакомб", archetype: "necromancer", radius: 16, speed: 0.70, baseHp: 480, baseAtk: 52, range: 175, canSummon: true }
      ];
    } else if (floor >= 40) {
      pool = [
        { name: "Некромант Катакомб", archetype: "necromancer", radius: 16, speed: 0.70, baseHp: 480, baseAtk: 52, range: 175, canSummon: true },
        { name: "Теневой Ассасин", archetype: "assassin", radius: 15, speed: 1.25, baseHp: 380, baseAtk: 65, range: 38, critChance: 35 },
        { name: "Костяной Страж", archetype: "bone_guardian", radius: 18, speed: 0.65, baseHp: 650, baseAtk: 48, range: 44 },
        { name: "Варлок Легиона", archetype: "warlock", radius: 16, speed: 0.72, baseHp: 320, baseAtk: 38, range: 180 }
      ];
    } else if (floor >= 20) {
      pool = [
        { name: "Варлок Легиона", archetype: "warlock", radius: 16, speed: 0.72, baseHp: 320, baseAtk: 38, range: 180 },
        { name: "Железный Голем", archetype: "irongolem", radius: 20, speed: 0.55, baseHp: 550, baseAtk: 42, range: 42, physResist: 0.5 },
        { name: "Адская Гончая", archetype: "hound", radius: 14, speed: 1.35, baseHp: 260, baseAtk: 45, range: 36 },
        { name: "Броне-Защитник", archetype: "defender", radius: 17, speed: 0.7, baseHp: 260, baseAtk: 24, range: 44 }
      ];
    } else if (wave <= 3) {
      pool = [
        { name: "Мечник Света", archetype: "melee_radiant", radius: 15, speed: 0.85, baseHp: 135, baseAtk: 12, range: 38 },
        { name: "Вурдалак Тьмы", archetype: "melee_dire", radius: 15, speed: 0.88, baseHp: 145, baseAtk: 14, range: 38 }
      ];
    } else if (wave <= 7) {
      pool = [
        { name: "Мечник Света", archetype: "melee_radiant", radius: 15, speed: 0.85, baseHp: 140, baseAtk: 13, range: 38 },
        { name: "Вурдалак Тьмы", archetype: "melee_dire", radius: 15, speed: 0.88, baseHp: 150, baseAtk: 14, range: 38 },
        { name: "Маг Света", archetype: "ranged_radiant", radius: 14, speed: 0.78, baseHp: 95, baseAtk: 16, range: 170 },
        { name: "Колдун Тьмы", archetype: "ranged_dire", radius: 14, speed: 0.78, baseHp: 100, baseAtk: 18, range: 175 }
      ];
    } else if (wave <= 12) {
      pool = [
        { name: "Броне-Защитник", archetype: "defender", radius: 17, speed: 0.68, baseHp: 230, baseAtk: 14, range: 44 },
        { name: "Вурдалак Тьмы", archetype: "melee_dire", radius: 15, speed: 0.9, baseHp: 160, baseAtk: 16, range: 38 },
        { name: "Колдун Тьмы", archetype: "ranged_dire", radius: 14, speed: 0.8, baseHp: 110, baseAtk: 20, range: 175 },
        { name: "Осадная Катапульта", archetype: "catapult", radius: 18, speed: 0.45, baseHp: 300, baseAtk: 26, range: 195 }
      ];
    } else {
      const hasCaptain = ARENA.creeps.some(c => c.archetype === "captain");
      if (!hasCaptain && Math.random() < 0.35) {
        pool = [
          { name: "ЭЛИТНЫЙ КАПИТАН", archetype: "captain", radius: 19, speed: 0.75, baseHp: 380, baseAtk: 26, range: 42, isCaptain: true }
        ];
      } else {
        pool = [
          { name: "Броне-Защитник", archetype: "defender", radius: 17, speed: 0.7, baseHp: 260, baseAtk: 16, range: 44 },
          { name: "Колдун Тьмы", archetype: "ranged_dire", radius: 14, speed: 0.82, baseHp: 125, baseAtk: 22, range: 175 },
          { name: "Вурдалак Тьмы", archetype: "melee_dire", radius: 15, speed: 0.92, baseHp: 180, baseAtk: 18, range: 38 },
          { name: "Осадная Катапульта", archetype: "catapult", radius: 18, speed: 0.46, baseHp: 340, baseAtk: 28, range: 195 }
        ];
      }
    }

    const t = pool[Math.floor(Math.random() * pool.length)];

    ARENA.creeps.push({
      name: t.name,
      archetype: t.archetype,
      team: t.archetype.includes("radiant") ? "radiant" : (t.archetype.includes("dire") ? "dire" : "neutral"),
      x: ARENA.width + 22 + Math.random() * 35,
      y: ARENA.roadY - 16 + (Math.random() * 20 - 10),
      radius: t.radius,
      speed: t.speed + (wave - 1) * 0.01,
      hp: Math.floor(t.baseHp * scaleHp),
      maxHp: Math.floor(t.baseHp * scaleHp),
      atk: Math.floor(t.baseAtk * scaleAtk),
      physResist: t.physResist || 0,
      retaliate: t.retaliate || 0,
      critChance: t.critChance || 0,
      canSummon: !!t.canSummon,
      fireBreath: !!t.fireBreath,
      timeDilation: !!t.timeDilation,
      earthquake: !!t.earthquake,
      pureDamage: !!t.pureDamage,
      range: t.range || 38,
      state: "approach",
      stateTimer: 0,
      shieldActive: t.archetype === "defender",
      shieldBrokenTimer: 0,
      isCaptain: !!t.isCaptain,
      isBoss: false,
      isMinion: false,
      attackCooldown: 0
    });
    ARENA.totalCreepsSpawned++;
  }

  function updatePetLogic() {
    const p = ARENA.player;
    if (!p) return;

    // Detect equipped pet from profile or fallback to localStorage
    const equippedPet = (RPG_STATE.profile?.pets || []).find(pt => pt.is_equipped);
    const petId = equippedPet ? (equippedPet.type || equippedPet.pet_id) : (localStorage.getItem("rpg_active_pet") || null);
    if (!petId) {
      ARENA.pet = null;
      return;
    }

    const petStars = equippedPet ? (equippedPet.stars || 1) : 1;
    const starMult = 1.0 + (petStars - 1) * 0.15;

    if (!ARENA.pet) {
      ARENA.pet = { x: p.x - 25, y: p.y - 25, timer: 0 };
    }
    const pet = ARENA.pet;
    pet.type = petId;
    pet.stars = petStars;

    // Smooth trailing physics behind the player
    const targetX = p.x - (p.facing === "left" ? -32 : 32);
    const targetY = p.y - 26 + Math.sin((ARENA.frameCount || 0) * 0.08) * 6;
    pet.x += (targetX - pet.x) * 0.12;
    pet.y += (targetY - pet.y) * 0.12;

    pet.timer = (pet.timer || 0) + 1;

    const stats = RPG_STATE.profile?.stats || {};
    const playerAtk = Math.max(50, stats.max_atk || 50);
    const playerMaxHp = Math.max(100, p.maxHp || 500);

    // Target for pet attacks (boss or first alive creep)
    const target = (ARENA.bossEntity && ARENA.bossEntity.hp > 0) ? ARENA.bossEntity : (ARENA.creeps && ARENA.creeps.find(c => c.hp > 0));

    // 1. DRAGON (🔥 Дыхание Богатства: огненный снаряд каждые 6с)
    if (petId === "dragon") {
      if (pet.timer >= 360) {
        pet.timer = 0;
        if (target && target.hp > 0) {
          const dmg = Math.floor((playerAtk * 2.5 + 1200) * starMult);
          if (ARENA.playerProjectiles) {
            ARENA.playerProjectiles.push({
              x: pet.x, y: pet.y,
              vx: (target.x - pet.x) * 0.09,
              vy: (target.y - pet.y) * 0.09,
              speed: 8.5,
              target: target,
              dmg: dmg,
              color: "#f97316",
              radius: 9,
              isMagic: true,
              isCrit: true,
              isPetShot: true
            });
          }
          spawnFloatingText(pet.x, pet.y - 14, "🔥 ДЫХАНИЕ ДРАКОНА!", "#f97316");
          triggerHaptic("medium");
        }
      }
    }
    // 2. FAIRY (🧚 Пыльца Свободы: лечит HP & MP, очищает дебаффы каждые 10с)
    else if (petId === "fairy") {
      if (pet.timer >= 600) {
        pet.timer = 0;
        p.stunTimer = 0;
        p.freezeTimer = 0;
        p.slowTimer = 0;
        const healHp = Math.min(Math.floor(playerMaxHp * 0.08 * starMult), 8000 * starMult);
        const healMp = Math.floor((p.maxMp || 100) * 0.25);
        p.currentHp = Math.min(playerMaxHp, (p.currentHp || playerMaxHp) + healHp);
        p.currentMp = Math.min(p.maxMp || 100, (p.currentMp || p.maxMp || 100) + healMp);
        spawnFloatingText(p.x, p.y - 20, `🧚 ПЫЛЬЦА СВОБОДЫ! +${healHp} HP`, "#22c55e");
        triggerHaptic("light");
      }
    }
    // 3. WOLF (🐺 Кровавый Укус: наносит урон и вешает кровотечение каждые 5с)
    else if (petId === "wolf") {
      if (pet.timer >= 300) {
        pet.timer = 0;
        if (target && target.hp > 0) {
          const dmg = Math.floor((playerAtk * 1.8 + 800) * starMult);
          safeDamageCreep(target, dmg, true);
          spawnFloatingText(target.x, target.y - 25, `🐺 УКУС ВОЛКА -${dmg}!`, "#ef4444");
          if (ARENA.specialEffects) {
            ARENA.specialEffects.push({ x: target.x, y: target.y, radius: 25, color: "#dc2626", life: 20 });
          }
          triggerHaptic("medium");
        }
      }
    }
    // 4. SLIME (💧 Капля Исцеления: лечит HP каждые 12с)
    else if (petId === "slime") {
      if (pet.timer >= 720) {
        pet.timer = 0;
        const heal = Math.min(Math.floor(playerMaxHp * 0.07 * starMult), 6000 * starMult);
        p.currentHp = Math.min(playerMaxHp, (p.currentHp || playerMaxHp) + heal);
        spawnFloatingText(p.x, p.y - 22, `💧 КАПЛЯ ЖИЗНИ +${heal} HP`, "#38bdf8");
        triggerHaptic("light");
      }
    }
    // 5. DONKEY (🫏 Курьерская Доставка: усиливает урон на +35% на 4с каждые 7с)
    else if (petId === "donkey") {
      if (pet.timer >= 420) {
        pet.timer = 0;
        p.donkeyBuffTimer = 240; // 4 seconds
        spawnFloatingText(p.x, p.y - 20, "🫏 КУРЬЕР! +35% УРОНА", "#eab308");
        triggerHaptic("medium");
      }
    }
    // 6. PHOENIX (🦅 Пылающий Феникс: атакует огненным снарядом каждые 5с)
    else if (petId === "phoenix") {
      if (pet.timer >= 300) {
        pet.timer = 0;
        if (target && target.hp > 0) {
          const dmg = Math.floor((playerAtk * 2.2 + 2000) * starMult);
          if (ARENA.playerProjectiles) {
            ARENA.playerProjectiles.push({
              x: pet.x, y: pet.y,
              vx: (target.x - pet.x) * 0.10,
              vy: (target.y - pet.y) * 0.10,
              speed: 9,
              target: target,
              dmg: dmg,
              color: "#fbbf24",
              radius: 10,
              isMagic: true,
              isCrit: true,
              isPetShot: true
            });
          }
          spawnFloatingText(pet.x, pet.y - 14, "🦅 ПЛАМЯ ФЕНИКСА!", "#f59e0b");
          triggerHaptic("medium");
        }
      }
    }
  }



// ============================================================================
// 04_boss_abilities_early.js — Signature Attacks & Ultimates for Bosses 1–10
// (Golem, Lich, Tormentor, Dragon, Pudge, Void, Roshan, Tidehunter, SF, Necro)
// ============================================================================

function executeBossAbilityEarly(boss, p, bId, abilityType, ARENA) {
  const pAng = Math.atan2(p.y - boss.y, p.x - boss.x);
  const dist = Math.hypot(p.x - boss.x, p.y - boss.y);

  // 1. GOLEM: Fissure (Разлом) or Tectonic Seismic Slam (Сейсмовзрыв)
  if (bId.includes("golem") || bId.includes("голем")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "🌋 ТЕКТОНИЧЕСКИЙ СЕЙСМОВЗРЫВ!", "#f97316");
      triggerHaptic("heavy");
      ARENA.cameraTrauma = 0.8;
      for (let ring = 1; ring <= 3; ring++) {
        ARENA.dangerZones.push({
          type: "circle", cx: boss.x, cy: boss.y, r: ring * 65,
          timer: ring * 18, phase: "telegraph", activeFrames: 14,
          damage: calculateBossAttackDamage(boss, 1.4),
          stun: 60, color: "#f97316", label: "🌋 СЕЙСМОВЗРЫВ (СТАН!)"
        });
      }
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "🪨 РАЗЛОМ ЗЕМЛИ!", "#facc15");
      const fx = boss.x + Math.cos(pAng) * 160;
      const fy = boss.y + Math.sin(pAng) * 160;
      ARENA.dangerZones.push({
        type: "line", x1: boss.x, y1: boss.y, x2: fx, y2: fy, width: 36,
        timer: 35, phase: "telegraph", activeFrames: 12,
        damage: calculateBossAttackDamage(boss, 0.95),
        slow: true, slowDuration: 90, slowRatio: 0.4,
        color: "#ca8a04", label: "🪨 РАЗЛОМ (ЗАМЕДЛЕНИЕ)"
      });
    }
    return true;
  }

  // 2. LICH: Frost Nova (Ледяной взрыв) or Chain Frost (Цепной Мороз)
  if (bId.includes("lich") || bId.includes("лич")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "❄️ ЦЕПНОЙ МОРОЗ (CHAIN FROST)!", "#38bdf8");
      triggerHaptic("heavy");
      ARENA.bossProjectiles.push({
        x: boss.x, y: boss.y,
        vx: Math.cos(pAng) * 3.6, vy: Math.sin(pAng) * 3.6,
        radius: 12, color: "#38bdf8", timer: 320,
        bouncesLeft: 5, isChainFrost: true,
        dmg: calculateBossAttackDamage(boss, 1.6),
        stun: 35, slow: true, slowDuration: 120, slowRatio: 0.3,
        label: "❄️ ЦЕПНОЙ МОРОЗ (СТАН)"
      });
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "🧊 FROST NOVA!", "#0284c7");
      ARENA.dangerZones.push({
        type: "circle", cx: p.x, cy: p.y, r: 52,
        timer: 30, phase: "telegraph", activeFrames: 15,
        damage: calculateBossAttackDamage(boss, 0.9),
        slow: true, slowDuration: 100, slowRatio: 0.35,
        color: "#0284c7", label: "🧊 NOVA (ЗАМЕДЛЕНИЕ)"
      });
    }
    return true;
  }

  // 3. TORMENTOR: Needle Spread or Reflective Barrier + Resonance Beam
  if (bId.includes("tormentor") && !bId.includes("dark_tormentor")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "🔮 РЕЗОНАНСНЫЙ ЛАЗЕР БЕЗДНЫ!", "#e879f9");
      boss.shieldActive = 180;
      triggerHaptic("heavy");
      ARENA.bossTelegraphs.push({
        type: "rotating_beam", cx: boss.x, cy: boss.y,
        angle: 0, rotSpeed: 0.045, length: 320, timer: 220,
        damage: calculateBossAttackDamage(boss, 3.2), color: "#c084fc",
        burn: true, burnDuration: 120, burnDmg: Math.floor((boss.atk || 320) * 0.8)
      });
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "✨ ОСКОЛОЧНЫЙ ЗАЛП!", "#c084fc");
      for (let n = 0; n < 8; n++) {
        const ang = (n * Math.PI) / 4;
        ARENA.bossProjectiles.push({
          x: boss.x + Math.cos(ang) * 20, y: boss.y + Math.sin(ang) * 20,
          vx: Math.cos(ang) * 3.2, vy: Math.sin(ang) * 3.2,
          radius: 7, color: "#e879f9", timer: 180,
          dmg: calculateBossAttackDamage(boss, 0.75),
          slow: true, slowDuration: 60, slowRatio: 0.6,
          label: "✨ ОСКОЛОК"
        });
      }
    }
    return true;
  }

  // 4. DRAGON: Fire Breath Cone or Inferno Cataclysm
  if (bId.includes("dragon") || bId.includes("дракон")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "🌋 КАТАКЛИЗМ ИНФЕРНО!", "#ef4444");
      triggerHaptic("heavy");
      ARENA.cameraTrauma = 0.9;
      for (let m = 0; m < 5; m++) {
        const mx = 60 + Math.random() * (ARENA.width - 120);
        const my = 60 + Math.random() * (ARENA.height - 120);
        ARENA.dangerZones.push({
          type: "circle", cx: mx, cy: my, r: 48,
          timer: 25 + m * 14, phase: "telegraph", activeFrames: 16,
          damage: calculateBossAttackDamage(boss, 1.25),
          stun: 45, burn: true, burnDuration: 150, burnDmg: Math.floor(boss.atk * 0.22),
          color: "#ea580c", label: "🌋 МЕТЕОР (СТАН & ОЖОГ)"
        });
      }
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "🔥 ОГНЕННОЕ ДЫХАНИЕ!", "#f97316");
      ARENA.dangerZones.push({
        type: "cone", cx: boss.x, cy: boss.y, angle: pAng, spread: 0.6, range: 170,
        timer: 32, phase: "telegraph", activeFrames: 24,
        damage: calculateBossAttackDamage(boss, 0.85),
        burn: true, burnDuration: 120, burnDmg: Math.floor(boss.atk * 0.18),
        color: "#ef4444", label: "🔥 ПЛАМЯ (ОЖОГ)"
      });
    }
    return true;
  }

  // 5. PUDGE: Meat Hook (Мясницкий крюк) or Dismember (Расчленение)
  if (bId.includes("pudge") || bId.includes("мясник")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "🩸 РАСЧЛЕНЕНИЕ (DISMEMBER)!", "#dc2626");
      triggerHaptic("heavy");
      ARENA.dangerZones.push({
        type: "circle", cx: boss.x, cy: boss.y, r: 85,
        timer: 15, phase: "telegraph", activeFrames: 60, isDot: true,
        damage: calculateBossAttackDamage(boss, 0.35),
        poison: true, poisonDuration: 60, slow: true, slowDuration: 60, slowRatio: 0.35,
        color: "#84cc16", label: "🩸 РАСЧЛЕНЕНИЕ (ЯД & ЗАМЕДЛЕНИЕ)"
      });
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "🪝 МЯСНИЦКИЙ КРЮК!", "#78716c");
      triggerHaptic("medium");
      ARENA.bossProjectiles.push({
        x: boss.x, y: boss.y,
        vx: Math.cos(pAng) * 5.4, vy: Math.sin(pAng) * 5.4,
        radius: 10, color: "#a8a29e", timer: 120, isMeatHook: true,
        originX: boss.x, originY: boss.y,
        dmg: calculateBossAttackDamage(boss, 1.1),
        stun: 60, label: "🪝 ХУК (СТАН!)"
      });
    }
    return true;
  }

  // 6. FACELESS VOID: Time Walk or Chronosphere (Хроносфера)
  if (bId.includes("faceless_void") || bId.includes("хроно")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "⏳ ХРОНОСФЕРА (ОСТАНОВКА ВРЕМЕНИ)!", "#a855f7");
      triggerHaptic("heavy");
      ARENA.cameraTrauma = 1.0;
      ARENA.bossTelegraphs.push({
        type: "chronosphere", cx: p.x, cy: p.y, r: 105,
        timer: 140, color: "rgba(168, 85, 247, 0.45)"
      });
      boss.x = p.x + 25;
      boss.y = p.y - 25;
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "⌛ TIME WALK + BASH!", "#c084fc");
      boss.x = p.x - Math.cos(pAng) * 45;
      boss.y = p.y - Math.sin(pAng) * 45;
      ARENA.dangerZones.push({
        type: "circle", cx: boss.x, cy: boss.y, r: 55,
        timer: 24, phase: "telegraph", activeFrames: 10,
        damage: calculateBossAttackDamage(boss, 1.2),
        stun: 60, color: "#c084fc", label: "⌛ BASH (СТАН 1с!)"
      });
    }
    return true;
  }

  // 7. ROSHAN: Ground Slam or Roar of Chaos (Рёв Ярости)
  if (bId.includes("roshan") && !bId.includes("phantom")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "🐲 РЁВ ЯРОСТИ РОШАНА!", "#ef4444");
      triggerHaptic("heavy");
      ARENA.cameraTrauma = 1.0;
      if (typeof applyStatusEffectToPlayer === "function") {
        applyStatusEffectToPlayer({ knockback: true, knockbackAngle: pAng, knockbackDist: 70 });
      }
      for (let rc = 0; rc < 4; rc++) {
        ARENA.dangerZones.push({
          type: "circle", cx: p.x + (Math.random() * 80 - 40), cy: p.y + (Math.random() * 80 - 40), r: 44,
          timer: 20 + rc * 12, phase: "telegraph", activeFrames: 14,
          damage: calculateBossAttackDamage(boss, 1.1),
          stun: 55, color: "#b45309", label: "⚠️ ОБВАЛ (СТАН!)"
        });
      }
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "💥 РОШАН-СЛЭМ!", "#ea580c");
      ARENA.dangerZones.push({
        type: "circle", cx: boss.x, cy: boss.y, r: 75,
        timer: 32, phase: "telegraph", activeFrames: 12,
        damage: calculateBossAttackDamage(boss, 0.95),
        slow: true, slowDuration: 120, slowRatio: 0.3,
        color: "#ea580c", label: "💥 СЛЭМ (ЗАМЕДЛЕНИЕ)"
      });
    }
    return true;
  }

  // 8. TIDEHUNTER: Gush or Ravage (Сокрушительный Раваж)
  if (bId.includes("tidehunter") || bId.includes("левиафан")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "🐙 СОКРУШИТЕЛЬНЫЙ РАВАЖ (RAVAGE)!", "#10b981");
      triggerHaptic("heavy");
      ARENA.cameraTrauma = 1.0;
      for (let tr = 1; tr <= 4; tr++) {
        ARENA.dangerZones.push({
          type: "circle", cx: boss.x, cy: boss.y, r: tr * 68,
          timer: tr * 14, phase: "telegraph", activeFrames: 16,
          damage: calculateBossAttackDamage(boss, 1.35),
          stun: 90, color: "#059669", label: "🐙 РАВАЖ (ОГЛУШЕНИЕ 1.5с!)"
        });
      }
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "🌊 ВОДЯНАЯ СТРУЯ (GUSH)!", "#34d399");
      ARENA.bossProjectiles.push({
        x: boss.x, y: boss.y,
        vx: Math.cos(pAng) * 4.2, vy: Math.sin(pAng) * 4.2,
        radius: 12, color: "#10b981", timer: 140,
        dmg: calculateBossAttackDamage(boss, 0.85),
        slow: true, slowDuration: 120, slowRatio: 0.35,
        label: "🌊 GUSH (ЗАМЕДЛЕНИЕ)"
      });
    }
    return true;
  }

  // 9. SHADOW FIEND: Shadowraze Trio or Requiem of Souls (Реквием Душ)
  if (bId.includes("sf_boss") || bId.includes("nevermore")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "💀 РЕКВИЕМ ДУШ (REQUIEM OF SOULS)!", "#dc2626");
      triggerHaptic("heavy");
      ARENA.cameraTrauma = 1.0;
      for (let s = 0; s < 16; s++) {
        const sAng = (s * Math.PI * 2) / 16;
        ARENA.bossProjectiles.push({
          x: boss.x, y: boss.y,
          vx: Math.cos(sAng) * 3.4, vy: Math.sin(sAng) * 3.4,
          radius: 9, color: "#ef4444", timer: 180,
          dmg: calculateBossAttackDamage(boss, 1.2),
          silence: 120, slow: true, slowDuration: 120, slowRatio: 0.35,
          label: "💀 РЕКВИЕМ (САЙЛЕНС 2с!)"
        });
      }
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "🔥 ТРОЙНОЙ SHADOWRAZE!", "#f87171");
      const dists = [60, 115, 175];
      dists.forEach((d, idx) => {
        const cx = boss.x + Math.cos(pAng) * d;
        const cy = boss.y + Math.sin(pAng) * d;
        ARENA.dangerZones.push({
          type: "circle", cx, cy, r: 42,
          timer: 18 + idx * 12, phase: "telegraph", activeFrames: 12,
          damage: calculateBossAttackDamage(boss, 0.95),
          slow: true, slowDuration: 60, slowRatio: 0.5,
          color: "#b91c1c", label: `🔥 КОИЛ #${idx + 1}`
        });
      });
    }
    return true;
  }

  // 10. NECROPHOS: Death Pulse or Reaper's Scythe (Коса Смерти)
  if (bId.includes("necrophos") || bId.includes("чумной")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "☠️ КОСА СМЕРТИ (REAPER'S SCYTHE)!", "#84cc16");
      triggerHaptic("heavy");
      const missingPct = Math.max(0, 1.0 - (p.currentHp / (p.maxHp || 400)));
      const scytheDmg = calculateBossAttackDamage(boss, 1.2 + missingPct * 1.8);
      ARENA.dangerZones.push({
        type: "circle", cx: p.x, cy: p.y, r: 60,
        timer: 45, phase: "telegraph", activeFrames: 15,
        damage: scytheDmg, stun: 75,
        color: "#65a30d", label: "💀 КОСА СМЕРТИ (КАЗНЬ!)"
      });
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "💚 ПУЛЬСАЦИЯ СМЕРТИ!", "#a3e635");
      for (let dp = 0; dp < 8; dp++) {
        const dpAng = (dp * Math.PI) / 4;
        ARENA.bossProjectiles.push({
          x: boss.x, y: boss.y,
          vx: Math.cos(dpAng) * 2.8, vy: Math.sin(dpAng) * 2.8,
          radius: 8, color: "#84cc16", timer: 160,
          dmg: calculateBossAttackDamage(boss, 0.75),
          poison: true, poisonDuration: 90,
          label: "💚 ПУЛЬС СМЕРТИ (ЯД)"
        });
      }
    }
    return true;
  }

  return false;
}

// ============================================================================
// 04_boss_abilities_late.js — Signature Attacks & Ultimates for Bosses 11–20
// (Terrorblade, Invoker, CK, Dark Tormentor, Storm, Doom, Primal Beast, Phantom Roshan, Tinker, Enigma)
// ============================================================================

function executeBossAbilityLate(boss, p, bId, abilityType, ARENA) {
  const pAng = Math.atan2(p.y - boss.y, p.x - boss.x);

  // 11. TERRORBLADE: Conjure Image or Sunder (Разрыв Души)
  if (bId.includes("terrorblade") || bId.includes("демон бездны")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "😈 РАЗРЫВ ДУШИ (SUNDER)!", "#a855f7");
      triggerHaptic("heavy");
      const curHp = (p && typeof p.currentHp === "number" && !isNaN(p.currentHp) && p.currentHp > 0) ? p.currentHp : 0;
      const siphonDmg = Math.max(0, Math.floor(curHp * 0.25));
      if (siphonDmg > 0) {
        applyDamageToPlayer(siphonDmg, "sunder");
        const curBossHp = (typeof boss.hp === "number" && !isNaN(boss.hp) && boss.hp > 0) ? boss.hp : boss.maxHp;
        const healAmt = Math.min(boss.maxHp * 0.08, siphonDmg * 10);
        boss.hp = Math.min(boss.maxHp, curBossHp + healAmt);
        spawnFloatingText(p.x, p.y - 25, `🩸 SUNDER -${siphonDmg}`, "#a855f7");
      }
      if (typeof applyStatusEffectToPlayer === "function") {
        applyStatusEffectToPlayer({ slow: true, slowDuration: 90, slowRatio: 0.4 });
      }
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "👥 ИЛЛЮЗИЯ ТЬМЫ!", "#7c3aed");
      for (let im = 0; im < 2; im++) {
        const iAng = pAng + (im === 0 ? -0.4 : 0.4);
        ARENA.bossProjectiles.push({
          x: boss.x, y: boss.y,
          vx: Math.cos(iAng) * 3.8, vy: Math.sin(iAng) * 3.8,
          radius: 9, color: "#8b5cf6", timer: 150,
          dmg: calculateBossAttackDamage(boss, 0.7),
          slow: true, slowDuration: 60, slowRatio: 0.5,
          label: "👥 ТЕНЕВОЙ БОЛТ"
        });
      }
    }
    return true;
  }

  // 12. INVOKER: Chaos Meteor or Sun Strike (Солнечный Удар)
  if (bId.includes("invoker_boss") || bId.includes("инвокер")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "☀️ СОЛНЕЧНЫЙ УДАР (SUN STRIKE)!", "#facc15");
      triggerHaptic("heavy");
      ARENA.dangerZones.push({
        type: "circle", cx: p.x, cy: p.y, r: 55,
        timer: 48, phase: "telegraph", activeFrames: 14,
        damage: calculateBossAttackDamage(boss, 2.0),
        burn: true, burnDuration: 120, burnDmg: Math.floor(boss.atk * 0.28),
        color: "#facc15", label: "☀️ SUN STRIKE (ОЖОГ)"
      });
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "☄️ МЕТЕОР ХАОСА!", "#f97316");
      const mx = boss.x + Math.cos(pAng) * 220;
      const my = boss.y + Math.sin(pAng) * 220;
      ARENA.dangerZones.push({
        type: "line", x1: boss.x, y1: boss.y, x2: mx, y2: my, width: 48,
        timer: 36, phase: "telegraph", activeFrames: 24,
        damage: calculateBossAttackDamage(boss, 1.25),
        burn: true, burnDuration: 150, burnDmg: Math.floor(boss.atk * 0.22),
        slow: true, slowDuration: 90, slowRatio: 0.4,
        color: "#ea580c", label: "☄️ МЕТЕОР (ОЖОГ & ЗАМЕДЛЕНИЕ)"
      });
    }
    return true;
  }

  // 13. CHAOS KNIGHT: Chaos Bolt or Phantasm (Фантазм)
  if (bId.includes("chaos_knight") || bId.includes("всадник хаоса")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "🐎 ФАНТАЗМ ХАОСА (PHANTASM)!", "#f59e0b");
      triggerHaptic("heavy");
      for (let c = -1; c <= 1; c++) {
        const cAng = pAng + c * 0.35;
        ARENA.bossProjectiles.push({
          x: boss.x, y: boss.y,
          vx: Math.cos(cAng) * 4.4, vy: Math.sin(cAng) * 4.4,
          radius: 14, color: "#f59e0b", timer: 140,
          dmg: calculateBossAttackDamage(boss, 1.15),
          slow: true, slowDuration: 75, slowRatio: 0.45,
          label: "🐎 ФАНТАЗМ"
        });
      }
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "⚡ CHAOS BOLT!", "#ef4444");
      const randDmgMult = 0.6 + Math.random() * 0.8;
      const randStun = Math.floor(45 + Math.random() * 55);
      ARENA.bossProjectiles.push({
        x: boss.x, y: boss.y,
        vx: Math.cos(pAng) * 4.8, vy: Math.sin(pAng) * 4.8,
        radius: 11, color: "#ef4444", timer: 140,
        dmg: calculateBossAttackDamage(boss, randDmgMult),
        stun: randStun, label: `⚡ CHAOS BOLT (СТАН ${Math.round(randStun/60*10)/10}с!)`
      });
    }
    return true;
  }

  // 14. DARK TORMENTOR: Void Needles or Singularity Pulse (Пульс Сингулярности)
  if (bId.includes("dark_tormentor") || bId.includes("тёмный терзатель")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "🌌 ПУЛЬС СИНГУЛЯРНОСТИ!", "#c084fc");
      triggerHaptic("heavy");
      ARENA.cameraTrauma = 0.9;
      p.x = p.x * 0.6 + boss.x * 0.4;
      p.y = p.y * 0.6 + boss.y * 0.4;
      ARENA.dangerZones.push({
        type: "circle", cx: boss.x, cy: boss.y, r: 120,
        timer: 36, phase: "telegraph", activeFrames: 18,
        damage: calculateBossAttackDamage(boss, 1.65),
        stun: 75, color: "#9333ea", label: "🌌 СИНГУЛЯРНОСТЬ (СТАН!)"
      });
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "✨ ШТОРМ ИГЛ БЕЗДНЫ!", "#e9d5ff");
      for (let n = 0; n < 12; n++) {
        const nAng = (n * Math.PI * 2) / 12;
        ARENA.bossProjectiles.push({
          x: boss.x, y: boss.y,
          vx: Math.cos(nAng) * 3.6, vy: Math.sin(nAng) * 3.6,
          radius: 8, color: "#c084fc", timer: 160,
          dmg: calculateBossAttackDamage(boss, 0.8),
          silence: 60, label: "✨ ИГЛА (САЙЛЕНС 1с)"
        });
      }
    }
    return true;
  }

  // 15. STORM SPIRIT: Static Remnant or Ball Lightning (Шаровая Молния)
  if (bId.includes("storm_spirit") || bId.includes("громовой")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "⚡ ШАРОВАЯ МОЛНИЯ (BALL LIGHTNING)!", "#38bdf8");
      triggerHaptic("heavy");
      ARENA.cameraTrauma = 0.8;
      const targetX = p.x + Math.cos(pAng) * 80;
      const targetY = p.y + Math.sin(pAng) * 80;
      ARENA.dangerZones.push({
        type: "line", x1: boss.x, y1: boss.y, x2: targetX, y2: targetY, width: 44,
        timer: 20, phase: "telegraph", activeFrames: 10,
        damage: calculateBossAttackDamage(boss, 1.5),
        stun: 60, color: "#38bdf8", label: "⚡ ШАРОВАЯ МОЛНИЯ (СТАН 1с!)"
      });
      boss.x = Math.max(40, Math.min(ARENA.width - 40, targetX));
      boss.y = Math.max(40, Math.min(ARENA.height - 40, targetY));
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "⚡ ЭЛЕКТРО-РЕЗЕРВ (STATIC REMNANT)!", "#facc15");
      ARENA.dangerZones.push({
        type: "circle", cx: boss.x, cy: boss.y, r: 60,
        timer: 15, phase: "telegraph", activeFrames: 120,
        damage: calculateBossAttackDamage(boss, 0.95),
        slow: true, slowDuration: 90, slowRatio: 0.35,
        color: "#facc15", label: "⚡ РЕМНАНТ (ШОК)"
      });
    }
    return true;
  }

  // 16. DOOM: Scorched Earth or DOOM (Печать Рока)
  if (bId.includes("doom") || bId.includes("вестник")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "🔥 ПЕЧАТЬ РОКА (DOOM)!", "#dc2626");
      triggerHaptic("heavy");
      ARENA.cameraTrauma = 1.0;
      p.doomDebuffTimer = 240;
      if (typeof applyStatusEffectToPlayer === "function") {
        applyStatusEffectToPlayer({ silence: 240 });
      }
      ARENA.dangerZones.push({
        type: "circle", cx: p.x, cy: p.y, r: 65,
        timer: 24, phase: "telegraph", activeFrames: 14,
        damage: calculateBossAttackDamage(boss, 1.4),
        silence: 240, color: "#7f1d1d", label: "🔥 DOOM (САЙЛЕНС 4с & УРОН!)"
      });
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "🌋 ВЫЖЖЕННАЯ ЗЕМЛЯ (SCORCHED EARTH)!", "#f97316");
      ARENA.dangerZones.push({
        type: "circle", cx: boss.x, cy: boss.y, r: 95,
        timer: 15, phase: "telegraph", activeFrames: 90, isDot: true,
        damage: calculateBossAttackDamage(boss, 0.4),
        burn: true, burnDuration: 90, burnDmg: Math.floor(boss.atk * 0.18),
        color: "#ea580c", label: "🌋 ПЛАМЯ АДА (ОЖОГ)"
      });
    }
    return true;
  }

  // 17. PRIMAL BEAST: Onslaught Rush or Pulverize (Вбивание в Землю)
  if (bId.includes("primal_beast") || bId.includes("первобытный")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "🦣 ВБИВАНИЕ В ЗЕМЛЮ (PULVERIZE)!", "#b45309");
      triggerHaptic("heavy");
      ARENA.cameraTrauma = 1.0;
      for (let pw = 0; pw < 3; pw++) {
        ARENA.dangerZones.push({
          type: "circle", cx: boss.x, cy: boss.y, r: 70 + pw * 30,
          timer: 18 + pw * 16, phase: "telegraph", activeFrames: 14,
          damage: calculateBossAttackDamage(boss, 1.25),
          stun: 65, color: "#92400e", label: "🦣 ВБИВАНИЕ (СТАН 1с!)"
        });
      }
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "💨 НЕИСТОВЫЙ РАЗБЕГ (ONSLAUGHT)!", "#f59e0b");
      boss.state = "telegraph_charge";
      boss.stateTimer = 45;
      boss.chargeAngle = pAng;
      boss.chargeVx = Math.cos(pAng) * 4.8;
      boss.chargeVy = Math.sin(pAng) * 4.8;
    }
    return true;
  }

  // 18. PHANTOM ROSHAN: Astral Slam or Astral Tear (Астральный Разрыв)
  if (bId.includes("phantom_roshan") || bId.includes("призрачный рошан")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "👻 АСТРАЛЬНЫЙ РАЗРЫВ ХАОСА!", "#34d399");
      triggerHaptic("heavy");
      ARENA.cameraTrauma = 1.0;
      for (let as = 0; as < 8; as++) {
        const asAng = (as * Math.PI * 2) / 8;
        ARENA.bossProjectiles.push({
          x: boss.x, y: boss.y,
          vx: Math.cos(asAng) * 3.8, vy: Math.sin(asAng) * 3.8,
          radius: 12, color: "#10b981", timer: 180,
          dmg: calculateBossAttackDamage(boss, 1.3),
          silence: 90, slow: true, slowDuration: 90, slowRatio: 0.4,
          label: "👻 АСТРАЛ (САЙЛЕНС 1.5с)"
        });
      }
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "💥 АСТРАЛЬНЫЙ SLAM!", "#6ee7b7");
      ARENA.dangerZones.push({
        type: "circle", cx: boss.x, cy: boss.y, r: 85,
        timer: 28, phase: "telegraph", activeFrames: 16,
        damage: calculateBossAttackDamage(boss, 1.1),
        slow: true, slowDuration: 120, slowRatio: 0.3,
        color: "#059669", label: "👻 АСТРАЛЬНЫЙ СЛЭМ"
      });
    }
    return true;
  }

  // 19. TINKER: Laser Beam or March of the Machines (Марш Роботов)
  if (bId.includes("tinker_boss") || bId.includes("архиинженер")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "🤖 МАРШ РОБОТОВ (MARCH OF MACHINES)!", "#facc15");
      triggerHaptic("heavy");
      for (let bot = 0; bot < 12; bot++) {
        const bx = 40 + (bot * (ARENA.width - 80)) / 11;
        ARENA.bossProjectiles.push({
          x: bx, y: 15,
          vx: (Math.random() - 0.5) * 1.2, vy: 2.2 + Math.random() * 0.8,
          radius: 7, color: "#eab308", timer: 240, isSpiderBot: true,
          dmg: calculateBossAttackDamage(boss, 0.45),
          slow: true, slowDuration: 45, slowRatio: 0.5,
          label: "🤖 РОБОТ-ПАУК"
        });
      }
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "🔴 ОСЛЕПЛЯЮЩИЙ ЛАЗЕР!", "#ef4444");
      ARENA.dangerZones.push({
        type: "line", x1: boss.x, y1: boss.y,
        x2: boss.x + Math.cos(pAng) * 260, y2: boss.y + Math.sin(pAng) * 260,
        width: 32, timer: 30, phase: "telegraph", activeFrames: 18,
        damage: calculateBossAttackDamage(boss, 1.2),
        blind: true, blindDuration: 150,
        color: "#ef4444", label: "🔴 ЛАЗЕР (ОСЛЕПЛЕНИЕ 2.5с!)"
      });
    }
    return true;
  }

  // 20. ENIGMA: Midnight Pulse or BLACK HOLE (Чёрная Дыра)
  if (bId.includes("enigma") || bId.includes("пожиратель миров")) {
    if (abilityType === "ultimate") {
      spawnFloatingText(boss.x, boss.y - 35, "🌌 ЧЁРНАЯ ДЫРА (BLACK HOLE)!", "#6366f1");
      triggerHaptic("heavy");
      ARENA.cameraTrauma = 1.0;
      ARENA.bossTelegraphs.push({
        type: "black_hole", cx: ARENA.width / 2, cy: ARENA.height / 2,
        r: 125, timer: 180, color: "#1e1b4b",
        dmg: calculateBossAttackDamage(boss, 0.45)
      });
    } else {
      spawnFloatingText(boss.x, boss.y - 30, "💜 ПУЛЬС ПОЛУНОЧИ (MIDNIGHT PULSE)!", "#818cf8");
      ARENA.dangerZones.push({
        type: "circle", cx: p.x, cy: p.y, r: 90,
        timer: 20, phase: "telegraph", activeFrames: 90, isDot: true,
        damage: calculateBossAttackDamage(boss, 0.4),
        slow: true, slowDuration: 60, slowRatio: 0.4,
        color: "#4338ca", label: "💜 MIDNIGHT PULSE"
      });
    }
    return true;
  }

  return false;
}

// ============================================================================
// 04_boss_ai_core.js — Boss AI Dispatcher, Ability Rotation & Ultimate Gauge
// ============================================================================

function updateCustomBossAI(boss, p, ARENA) {
  if (!boss || boss.hp <= 0) return;

  // Initialize timers if missing
  if (boss.skillCooldown == null) boss.skillCooldown = 180; // ~3s initial grace
  if (boss.ultimateMeter == null) boss.ultimateMeter = 0;
  if (boss.meleeCooldown == null) boss.meleeCooldown = 60;
  if (!ARENA.bossTelegraphs) ARENA.bossTelegraphs = [];

  const bId = (boss.bossType || boss.boss_id || boss.id || boss.name || "").toLowerCase();

  // Enrage Stages based on Timer or HP (5-minute hard cap = God Mode)
  boss.battleStartTime = boss.battleStartTime || Date.now();
  boss.enrageTimer = (boss.enrageTimer || 0) + 1;
  const elapsedMs = Date.now() - boss.battleStartTime;
  const isGodMode = elapsedMs >= 300000 || boss.enrageTimer >= 18000;

  if (isGodMode) {
    if (!boss.isGodMode) {
      boss.isGodMode = true;
      triggerHaptic("heavy");
      if (ARENA.cameraTrauma !== undefined) ARENA.cameraTrauma = 1.0;
      spawnFloatingText(boss.x, boss.y - 45, "⚡⚡ РЕЖИМ БОГА! ⚡⚡", "#ef4444");
    }
    boss.enrageStage = "god_mode";
    // 5% max HP regen per sec
    const regenPerSec = Math.max(500, Math.floor((boss.maxHp || 10000) * 0.05));
    const regenPerFrame = Math.max(1, Math.floor(regenPerSec / 60));
    boss.hp = Math.min(boss.maxHp, boss.hp + regenPerFrame);
    if (ARENA.frameCount % 60 === 0) {
      spawnFloatingText(boss.x, boss.y - 30, `✨ +${Math.round(regenPerSec)} РЕГЕН БОГА`, "#22c55e");
    }
  } else {
    const hpPct = boss.hp / (boss.maxHp || 1);
    if (boss.enrageTimer > 5400 || hpPct <= 0.15) {
      boss.enrageStage = "enraged";
    } else if (boss.enrageTimer > 3600 || hpPct <= 0.40) {
      boss.enrageStage = "furious";
    } else if (boss.enrageTimer > 1800 || hpPct <= 0.70) {
      boss.enrageStage = "angry";
    }
  }

  const bSpeedMult = boss.isGodMode ? 3.5 : (boss.enrageStage === "enraged" ? 1.3 : boss.enrageStage === "furious" ? 1.18 : boss.enrageStage === "angry" ? 1.08 : 1.0);

  // Decrement cooldowns & charge Ultimate meter
  const cdReduction = boss.isGodMode ? 3 : 1;
  boss.skillCooldown = Math.max(0, boss.skillCooldown - cdReduction);
  boss.meleeCooldown = Math.max(0, boss.meleeCooldown - cdReduction);
  boss.chargeCooldown = Math.max(0, (boss.chargeCooldown || 0) - cdReduction);
  
  let ultChargeRate = boss.isGodMode ? 0.8 : (boss.enrageStage === "enraged" ? 0.14 : 0.08);
  if (bId.includes("faceless_void") || bId.includes("хроно")) {
    if (!boss.isGodMode) ultChargeRate *= 0.25; // Massive nerf to Chronosphere cooldown (4x longer, ~1.5 - 2 mins)
  }
  boss.ultimateMeter = Math.min(100, (boss.ultimateMeter || 0) + ultChargeRate);

  // Find nearest target (player or active companion)
  let closestTarget = p;
  let minDist = Math.hypot(p.x - boss.x, p.y - boss.y);
  for (const comp of (ARENA.bossCompanions || [])) {
    if (comp.hp > 0) {
      const d = Math.hypot(comp.x - boss.x, comp.y - boss.y);
      if (d < minDist) { minDist = d; closestTarget = comp; }
    }
  }

  // Handle Doom debuff on player
  if (p.doomDebuffTimer > 0) {
    p.doomDebuffTimer--;
    if (ARENA.frameCount % 30 === 0) {
      const dDmg = Math.max(8, Math.floor((p.maxHp || 400) * 0.035));
      applyDamageToPlayer(dDmg, "doom");
      spawnFloatingText(p.x, p.y - 20, `🔥 DOOM -${dDmg}`, "#dc2626");
    }
  }

  // Update Special Boss Telegraphs (Black Hole & Chronosphere)
  for (let bti = ARENA.bossTelegraphs.length - 1; bti >= 0; bti--) {
    const bt = ARENA.bossTelegraphs[bti];
    bt.timer--;

    // 1. BLACK HOLE PULL
    if (bt.type === "black_hole") {
      const dHole = Math.hypot(p.x - bt.cx, p.y - bt.cy);
      if (dHole < bt.r + 65) {
        // Gravitational vortex pull towards center
        const pPullAng = Math.atan2(bt.cy - p.y, bt.cx - p.x);
        p.x += Math.cos(pPullAng) * 3.4;
        p.y += Math.sin(pPullAng) * 3.4;
        applyStatusEffectToPlayer({ silence: 25, slow: true, slowDuration: 25, slowRatio: 0.3 });
        if (ARENA.frameCount % 20 === 0) {
          const bhDmg = Math.floor(bt.dmg || calculateBossAttackDamage(boss, 0.45));
          applyDamageToPlayer(bhDmg, "black_hole");
          spawnFloatingText(p.x, p.y - 20, `🌌 ЧЁРНАЯ ДЫРА -${bhDmg}`, "#6366f1");
          ARENA.cameraTrauma = 0.4;
          triggerHaptic("heavy");
        }
      }
    }
    // 2. CHRONOSPHERE TIME FREEZE
    else if (bt.type === "chronosphere") {
      const dChrono = Math.hypot(p.x - bt.cx, p.y - bt.cy);
      if (dChrono < bt.r) {
        p.isFrozenInTime = true;
        applyStatusEffectToPlayer({ stun: 12 });
      } else {
        p.isFrozenInTime = false;
      }
    }
    // 3. ROTATING RESONANCE BEAM (Ancient Tormentor Laser)
    else if (bt.type === "rotating_beam") {
      bt.angle += bt.rotSpeed;
      const bx2 = bt.cx + Math.cos(bt.angle) * bt.length;
      const by2 = bt.cy + Math.sin(bt.angle) * bt.length;
      const lineDist = distToSegment(p.x, p.y, bt.cx, bt.cy, bx2, by2);
      if (lineDist < p.radius + 16 && (ARENA.frameCount % 12 === 0)) {
        const baseBeamDmg = Math.floor(bt.damage || calculateBossAttackDamage(boss, 3.2));
        const pctMelt = Math.floor((p.maxHp || 1000) * 0.08); // 8% HP melt per tick
        const bmDmg = baseBeamDmg + pctMelt;
        applyDamageToPlayer(bmDmg, "beam");
        spawnFloatingText(p.x, p.y - 20, `🔮 СМЕРТЕЛЬНЫЙ ЛАЗЕР -${bmDmg}!`, "#e879f9");
        triggerHaptic("heavy");
        if (ARENA.cameraTrauma !== undefined) ARENA.cameraTrauma = Math.min(1.0, (ARENA.cameraTrauma || 0) + 0.35);
        applyStatusEffectToPlayer({ burn: true, burnDuration: 90, burnDmg: Math.floor((boss.atk || 320) * 0.6) });
      }
    }

    if (bt.timer <= 0) {
      if (bt.type === "chronosphere") p.isFrozenInTime = false;
      ARENA.bossTelegraphs.splice(bti, 1);
    }
  }

  // BOSS STATE MACHINE
  if (boss.state === "chase" || !boss.state) {
    boss.state = "chase";

    // Dynamic Pursuit
    const bAng = Math.atan2(closestTarget.y - boss.y, closestTarget.x - boss.x);
    const moveSpd = (boss.speed || 1.45) * bSpeedMult;
    boss.x += Math.cos(bAng) * moveSpd;
    boss.y += Math.sin(bAng) * moveSpd;
    boss.facing = Math.cos(bAng) >= 0 ? 1 : -1;

    // 1. Trigger Signature ULTIMATE if meter is full (100%)
    if (boss.ultimateMeter >= 100) {
      boss.ultimateMeter = 0;
      boss.skillCooldown = 160;
      let casted = false;
      if (typeof executeBossAbilityEarly === "function") {
        casted = executeBossAbilityEarly(boss, p, bId, "ultimate", ARENA);
      }
      if (!casted && typeof executeBossAbilityLate === "function") {
        casted = executeBossAbilityLate(boss, p, bId, "ultimate", ARENA);
      }
      return;
    }

    // 2. Trigger Signature Normal Ability (every ~4-6 seconds)
    if (boss.skillCooldown <= 0 && minDist > 60) {
      boss.skillCooldown = 260;
      let casted = false;
      if (typeof executeBossAbilityEarly === "function") {
        casted = executeBossAbilityEarly(boss, p, bId, "normal", ARENA);
      }
      if (!casted && typeof executeBossAbilityLate === "function") {
        casted = executeBossAbilityLate(boss, p, bId, "normal", ARENA);
      }
      if (casted) return;
    }

    // 3. Trigger Melee Strike if close
    if (minDist < (boss.radius + p.radius + 24) && boss.meleeCooldown <= 0) {
      boss.state = "telegraph_melee";
      boss.stateTimer = 45;
      boss.meleeCooldown = 90;
      spawnFloatingText(boss.x, boss.y - 30, "⚠️ ЗАМАХ!", "#f59e0b");
    }
  } else if (boss.state === "telegraph_melee") {
    boss.stateTimer--;
    if (boss.stateTimer <= 0) {
      boss.state = "chase";
      ARENA.cameraTrauma = 0.45;
      triggerHaptic("heavy");
      if (Math.hypot(p.x - boss.x, p.y - boss.y) < (boss.radius + p.radius + 28) && !p.isInvulnerable) {
        const rawDmg = calculateBossAttackDamage(boss, 1.25);
        const actualDmg = applyDamageToPlayer(rawDmg, "melee");
        spawnFloatingText(p.x, p.y - 25, `💥 УДАР -${actualDmg}`, "#ef4444");
        applyStatusEffectToPlayer({ stun: 30 });
        if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
      }
    }
  }

  // Contact damage check
  if (Math.hypot(p.x - boss.x, p.y - boss.y) < (boss.radius + p.radius) && !p.isInvulnerable) {
    if ((ARENA.frameCount % 25) === 0) {
      const rawDmg = calculateBossAttackDamage(boss, 0.65);
      const actualDmg = applyDamageToPlayer(rawDmg, "contact");
      spawnFloatingText(p.x, p.y - 20, `💥 -${actualDmg}`, "#ef4444");
      triggerHaptic("medium");
      if (p.currentHp <= 0) { handlePlayerArenaDeath(); }
    }
  }

  // Handle Chain Frost bounces and Meat Hook pulling
  updateSpecialProjectiles(ARENA, boss, p);
}

function applyStatusEffectToPlayer(effect) {
  if (!effect) return;
  const p = ARENA.player;
  if (!p || p.isInvulnerable) return;

  // BKB (Black King Bar) magic immunity blocks all debuffs!
  if (p.bkbActive > 0) {
    if (ARENA.frameCount % 30 === 0) spawnFloatingText(p.x, p.y - 30, "🛡️ БКБ (ИММУНИТЕТ)!", "#facc15");
    return;
  }

  // 1. STUN
  const stunFrames = effect.stun || (effect.isStun ? (effect.stunDuration || 60) : 0);
  if (stunFrames > 0) {
    if (!p.stunTimer || p.stunTimer < stunFrames) {
      p.stunTimer = stunFrames;
      spawnFloatingText(p.x, p.y - 32, "💫 ОГЛУШЕНИЕ!", "#facc15");
      triggerHaptic("heavy");
    }
  }

  // 2. SLOW
  if (effect.slow || effect.slowEffect) {
    const sDur = effect.slowDuration || 90;
    const sRatio = effect.slowRatio || effect.slowEffect || 0.45;
    if (!p.slowTimer || p.slowTimer < sDur) {
      p.slowTimer = sDur;
      p.slowRatio = sRatio;
      spawnFloatingText(p.x, p.y - 26, "❄️ ЗАМЕДЛЕНИЕ!", "#38bdf8");
      triggerHaptic("light");
    }
  }

  // 3. SILENCE / DOOM
  const silFrames = effect.silence || effect.silenceDuration || 0;
  if (silFrames > 0) {
    if (!p.silenceTimer || p.silenceTimer < silFrames) {
      p.silenceTimer = silFrames;
      spawnFloatingText(p.x, p.y - 32, "🔇 БЕЗМОЛВИЕ!", "#c084fc");
      triggerHaptic("medium");
    }
  }

  // 4. BURN DoT
  if (effect.burn) {
    p.burnTimer = effect.burnDuration || 120;
    p.burnDmg = effect.burnDmg || Math.max(10, Math.floor(calculateBossAttackDamage(ARENA.bossEntity, 0.16)));
    spawnFloatingText(p.x, p.y - 22, "🔥 ОЖОГ!", "#f97316");
  }

  // 5. POISON DoT
  if (effect.poison) {
    p.poisonTimer = effect.poisonDuration || 120;
    p.poisonDmg = effect.poisonDmg || Math.max(10, Math.floor(calculateBossAttackDamage(ARENA.bossEntity, 0.16)));
    spawnFloatingText(p.x, p.y - 22, "☣️ ОТРАВЛЕНИЕ!", "#84cc16");
  }

  // 6. BLIND
  if (effect.blind) {
    p.blindTimer = effect.blindDuration || 120;
    spawnFloatingText(p.x, p.y - 30, "🔴 ОСЛЕПЛЕНИЕ!", "#ef4444");
  }

  // 7. KNOCKBACK
  if (effect.knockback && effect.knockbackAngle != null) {
    const kbDist = effect.knockbackDist || 35;
    p.x = Math.max(30, Math.min(490, p.x + Math.cos(effect.knockbackAngle) * kbDist));
    p.y = Math.max(40, Math.min(680, p.y + Math.sin(effect.knockbackAngle) * kbDist));
  }
}

function updateSpecialProjectiles(ARENA, boss, p) {
  for (let pi = ARENA.bossProjectiles.length - 1; pi >= 0; pi--) {
    const proj = ARENA.bossProjectiles[pi];

    // Chain Frost Bouncing & Impact
    if (proj.isChainFrost) {
      if (proj.x <= 20 || proj.x >= ARENA.width - 20) { proj.vx *= -1; proj.bouncesLeft--; }
      if (proj.y <= 25 || proj.y >= ARENA.height - 25) { proj.vy *= -1; proj.bouncesLeft--; }
      if (Math.hypot(p.x - proj.x, p.y - proj.y) < (p.radius + proj.radius + 6) && !p.isInvulnerable) {
        const cDmg = applyDamageToPlayer(proj.dmg || calculateBossAttackDamage(boss, 1.5), "chain_frost");
        spawnFloatingText(p.x, p.y - 25, `❄️ ЦЕПНОЙ МОРОЗ -${cDmg}`, "#38bdf8");
        applyStatusEffectToPlayer({ stun: 35, slow: true, slowDuration: 120, slowRatio: 0.35 });
        proj.bouncesLeft--;
        proj.vx = -proj.vx;
        proj.vy = -proj.vy;
      }
      if (proj.bouncesLeft <= 0) { ARENA.bossProjectiles.splice(pi, 1); continue; }
    }

    // Pudge Meat Hook Drag & Stun
    if (proj.isMeatHook) {
      if (Math.hypot(p.x - proj.x, p.y - proj.y) < (p.radius + proj.radius + 8)) {
        p.x = Math.max(30, Math.min(490, boss.x + Math.cos(Math.atan2(p.y - boss.y, p.x - boss.x)) * (boss.radius + 18)));
        p.y = Math.max(40, Math.min(680, boss.y + Math.sin(Math.atan2(p.y - boss.y, p.x - boss.x)) * (boss.radius + 18)));
        const hookDmg = applyDamageToPlayer(proj.dmg || calculateBossAttackDamage(boss, 1.25), "meat_hook");
        spawnFloatingText(p.x, p.y - 25, `🪝 ПРИТЯНУТ ХУКОМ -${hookDmg}!`, "#ef4444");
        applyStatusEffectToPlayer({ stun: 60 });
        triggerHaptic("heavy");
        ARENA.bossProjectiles.splice(pi, 1);
        continue;
      }
    }
  }
}

function distToSegment(px, py, x1, y1, x2, y2) {
  const l2 = (x2 - x1) * (x2 - x1) + (y2 - y1) * (y2 - y1);
  if (l2 === 0) return Math.hypot(px - x1, py - y1);
  let t = ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / l2;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(px - (x1 + t * (x2 - x1)), py - (y1 + t * (y2 - y1)));
}

  function spawnBossCreep() {
    const floor = RPG_STATE.profile?.dungeon_floor || 1;
    
    // Scale identically to creeps but x15 stronger
    const scaleHp = Math.pow(1.18, Math.max(0, floor - 1)) * (1.0 + 19 * 0.05); // wave 20 multiplier
    const scaleAtk = Math.pow(1.15, Math.max(0, floor - 1)) * (1.0 + 19 * 0.04);
    
    // Base creep stats for floor 20 is around 260 HP, 16 ATK. We multiply by 15!
    const baseHp = 260 * 15;
    const baseAtk = 16 * 8; // x8 ATK so it doesn't one-shot instantly but still hurts

    const bossTypes = [
      { id: "golem", name: "Древний Гранитный Голем", icon: "🗿", badgeBg: "#334155", badgeBorder: "#94a3b8" },
      { id: "lich", name: "Архилич Некрополя", icon: "☠️", badgeBg: "#18181b", badgeBorder: "#e4e4e7" },
      { id: "tormentor", name: "Древний Терзатель", icon: "🔮", badgeBg: "#4a044e", badgeBorder: "#c084fc" },
      { id: "dragon", name: "Дракон Инферно", icon: "🌋", badgeBg: "#7c2d12", badgeBorder: "#ea580c" },
      { id: "pudge_boss", name: "Мясник из Чрева", icon: "🪝", badgeBg: "#064e3b", badgeBorder: "#34d399" },
      { id: "faceless_void", name: "Хроно-Владыка", icon: "⏳", badgeBg: "#312e81", badgeBorder: "#818cf8" },
      { id: "roshan", name: "Рошан", icon: "🐲", badgeBg: "#7f1d1d", badgeBorder: "#facc15" }
    ];
    const bt = bossTypes[Math.min(bossTypes.length - 1, Math.max(0, floor - 1))];

    const stats = RPG_STATE.profile?.stats || {};
    const playerAtk = Math.max(30, Math.floor(((stats.min_atk || 30) + (stats.max_atk || 50)) / 2));
    const playerHp = Math.max(400, stats.hp_max || 400);

    const calculatedHp = Math.floor(baseHp * scaleHp);
    const calculatedAtk = Math.floor(baseAtk * scaleAtk);
    const calculatedDef = Math.floor(35 * Math.pow(1.10, Math.max(0, floor - 1)));

    const boss = {
      name: bt.name + (floor > 1 ? ` [Этаж ${floor}]` : ""),
      icon: bt.icon,
      team: "boss",
      badgeBg: bt.badgeBg,
      badgeBorder: bt.badgeBorder,
      x: (ARENA.width || 360) / 2,
      y: 95,
      radius: 30, // Scaled down for comfortable arena space
      speed: 0.65, // Active, menacing movement speed
      hp: calculatedHp,
      maxHp: calculatedHp,
      atk: calculatedAtk,
      defense: calculatedDef,
      isBoss: true,
      isMinion: false,
      shielded: false,
      attackCooldown: 0,
      state: "chase",
      stateTimer: 0,
      meleeCooldown: 60,
      chargeCooldown: 220,
      barrageCooldown: 140,
      chargeAngle: 0,
      chargeVx: 0,
      chargeVy: 0,
      facing: 1,
      enrageTimer: 0,
      battleStartTime: Date.now(),
      enrageStage: "normal",
      poise: 800,
      maxPoise: 800,
      isStaggered: false,
      staggerTimer: 0,
      bossType: (bt.name.toLowerCase().includes("терзатель") || bt.name.toLowerCase().includes("tormentor")) ? "tormentor" :
                (bt.name.toLowerCase().includes("лич") || bt.name.toLowerCase().includes("archlich")) ? "lich" :
                (bt.name.toLowerCase().includes("дракон") || bt.name.toLowerCase().includes("dragon")) ? "dragon" : "roshan"
    };

    ARENA.bossEntity = boss;
    ARENA.isBossActive = true;
    ARENA.bossPhase = 1;
    ARENA.topDownMode = true;
    ARENA.bossArenaMode = true;
    ARENA.width = 520;
    ARENA.height = 720;
    boss.x = 260;
    boss.y = 140;
    boss.radius = 32;
    ARENA.player.x = 260;
    ARENA.player.y = 620;
    ARENA.player.isMoving = false;
    ARENA.dashGhosts = [];

    ARENA.bossSpecialTimer = 0;
    ARENA.bossProjectiles = [];
    ARENA.creeps = [boss];

    if ((ARENA.bossPartyMode || "trio") === "trio") {
      initBossCompanions();
    }

    // Force full render of DOM to expand canvas to h-[520px] and activate boss controls
    RPG_STATE._forceFullRender = true;
    renderRoot();
    RPG_STATE._forceFullRender = false;

    const canvas = document.getElementById("rpg-action-canvas");
    if (canvas) {
      bindArenaCanvas(canvas);
      ARENA.width = 520;
      ARENA.height = 720;
      boss.x = 260;
      boss.y = 140;
      ARENA.player.x = 260;
      ARENA.player.y = 620;
    }
  }

  // ---------------------------------------------------------------------------
  // PLAYER ATTACK (MELEE & RANGED)
  // ---------------------------------------------------------------------------

  function fireTopDownAttack(targetPoint) {
    const p = ARENA.player;
    if (ARENA.waveState !== "fighting") return;
    if (p.shootCooldown && p.shootCooldown > 0) return;
    const stats = RPG_STATE.profile?.stats || {};
    const boss = (ARENA.bossEntity && ARENA.bossEntity.hp > 0) ? ARENA.bossEntity : (ARENA.creeps.find(c => c.hp > 0) || null);

    let fireAngle = p.facingAngle !== undefined ? p.facingAngle : -Math.PI / 2;
    let explicitTarget = boss;

    if (targetPoint && targetPoint.cx !== undefined) {
      fireAngle = Math.atan2(targetPoint.cy - p.y, targetPoint.cx - p.x);
      if (boss) {
        const toBoss = Math.atan2(boss.y - p.y, boss.x - p.x);
        let diff = Math.abs(toBoss - fireAngle);
        while (diff > Math.PI) diff = Math.PI * 2 - diff;
        if (diff < 1.1) explicitTarget = boss;
      }
    } else if (boss) {
      fireAngle = Math.atan2(boss.y - p.y, boss.x - p.x);
      explicitTarget = boss;
    }

    p.facingAngle = fireAngle;
    p.facing = Math.cos(fireAngle) >= 0 ? 1 : -1;

    const isCrit = Math.random() * 100 < (stats.crit_chance || 15);
    let baseDmg = Math.floor(((stats.min_atk || 25) + (stats.max_atk || 35)) * 0.7);
    if (p.donkeyBuffTimer && p.donkeyBuffTimer > 0) baseDmg = Math.floor(baseDmg * 1.35);
    const finalDmg = isCrit ? Math.floor(baseDmg * 2.2) : baseDmg;

    if (!ARENA.playerProjectiles) ARENA.playerProjectiles = [];
    ARENA.playerProjectiles.push({
      x: p.x + Math.cos(fireAngle) * 14,
      y: p.y + Math.sin(fireAngle) * 14,
      vx: Math.cos(fireAngle) * 10.5,
      vy: Math.sin(fireAngle) * 10.5,
      speed: 10.5,
      target: explicitTarget,
      dmg: finalDmg,
      type: "topdown_shot",
      isCrit: isCrit,
      radius: 6.5,
      color: isCrit ? "#f59e0b" : "#38bdf8",
      distTraveled: 0,
      maxDist: 850
    });

    const atkSpeed = Math.max(0.5, stats.attack_speed || 1.0);
    p.shootCooldown = Math.max(5, Math.round(60 / atkSpeed));
    triggerHaptic(isCrit ? "medium" : "light");
  }

  let _lastSlashAttackTime = 0;
  function playerSlashAttack() {
    const now = Date.now();
    if (now - _lastSlashAttackTime < 50) return;
    _lastSlashAttackTime = now;

    const p = ARENA.player;
    if (ARENA.topDownMode || ARENA.isRaidBossBattle) {
      fireTopDownAttack(null);
      return;
    }
    if (p.attackCooldown > 0) {
      if (p.attackCooldown <= 8) {
        p.attackQueued = true;
      }
      return;
    }
    const stats = RPG_STATE.profile?.stats || {};

    // 3-HIT COMBO CHAIN (Light 1 -> Light 2 -> Heavy Finisher)
    if (!ARENA.combo) ARENA.combo = { count: 0, timer: 0, step: 0, maxCombo: 0 };
    if (ARENA.combo.timer > 0) {
      ARENA.combo.step = (ARENA.combo.step + 1) % 3;
    } else {
      ARENA.combo.step = 0;
    }
    ARENA.combo.count++;
    ARENA.combo.timer = 135; // ~2.25s generous combo window for comfortable manual chaining
    ARENA.combo.maxCombo = Math.max(ARENA.combo.maxCombo, ARENA.combo.count);

    let stepMult = 2.4;
    let cdFrames = 38;
    let isHeavyFinisher = false;

    // Slower, tactile and weighty attack rate: ~1.2 to 1.6 attacks/sec (humanly clickable and readable)
    if (ARENA.combo.step === 0) {
      stepMult = 2.4;
      cdFrames = 38; // ~0.63s at 60 FPS (~1.58 atk/sec)
      addStylePoints(30, "LIGHT 1");
    } else if (ARENA.combo.step === 1) {
      stepMult = 3.2;
      cdFrames = 40; // ~0.67s at 60 FPS (~1.50 atk/sec)
      addStylePoints(55, "LIGHT 2");
    } else {
      stepMult = 5.8;
      cdFrames = 58; // ~0.97s at 60 FPS (~1.03 atk/sec heavy smash)
      isHeavyFinisher = true;
      addStylePoints(145, "HEAVY FINISHER");
    }

    let speedRate = Math.max(0.7, stats.attack_speed || 1.0);
    if (p.bladeDanceActive > 0) speedRate *= 1.5; // +50% attack speed buff

    // Attack speed formula directly scaled by stats.attack_speed
    p.attackCooldown = Math.max(8, Math.round(cdFrames / speedRate));
    triggerHaptic(isHeavyFinisher ? "heavy" : "medium");

    let isCrit = Math.random() * 100 < (stats.crit_chance || 15);
    if (p.critBuff) {
      isCrit = true;
      p.critBuff = false;
    }

    let baseDmg = Math.floor((stats.min_atk || 20) + Math.random() * ((stats.max_atk || 30) - (stats.min_atk || 20)));
    let dmg = Math.floor(baseDmg * stepMult);
    if (p.donkeyBuffTimer && p.donkeyBuffTimer > 0) dmg = Math.floor(dmg * 1.35);

    // PA PERK: Mega Coup (20% chance for x10 mega crit)
    if (isCrit) {
      if (window.hasTalentPerk && window.hasTalentPerk("perk_mega_coup") && Math.random() < 0.20) {
        dmg = Math.floor(dmg * 10.0);
        spawnFloatingText(p.x, p.y - 45, "💥 СВЕРХКРИТ x10!", "#dc2626");
        triggerHaptic("heavy");
      } else {
        dmg = Math.floor(dmg * 2.2);
      }
      // WK PERK: Vampiric Crit (Critical hits restore 100% of damage dealt)
      if (window.hasTalentPerk && window.hasTalentPerk("perk_vampiric_crit")) {
        const vampAmt = Math.min((p.maxHp || 500) - (p.currentHp || 0), dmg);
        if (vampAmt > 0) {
          p.currentHp = Math.min(p.maxHp || 500, (p.currentHp || 0) + vampAmt);
          spawnFloatingText(p.x, p.y - 30, `💚 +${vampAmt} (ВАМПИРИЗМ)`, "#22c55e");
        }
      }
    }

    // PUDGE PERK: Flesh Dismember (Every 4th attack deal x2 dmg + stun target)
    let isPudgeDismember = false;
    if (window.hasTalentPerk && window.hasTalentPerk("perk_flesh_dismember")) {
      ARENA.pudgeHitCounter = (ARENA.pudgeHitCounter || 0) + 1;
      if (ARENA.pudgeHitCounter >= 4) {
        ARENA.pudgeHitCounter = 0;
        isPudgeDismember = true;
        dmg = Math.floor(dmg * 2.0);
        spawnFloatingText(p.x, p.y - 35, "🥩 РАСЧЛЕНЕНИЕ x2!", "#ef4444");
      }
    }

    // SF PERK: Necromastery Soul Stacks (+3% damage per soul, up to 15 stacks)
    if (window.hasTalentPerk && window.hasTalentPerk("perk_necromastery_stacks") && (ARENA.sfSouls || 0) > 0) {
      dmg = Math.floor(dmg * (1.0 + ARENA.sfSouls * 0.03));
    }

    // ANTI-MAGE PERK: Mana Burn (+15% damage + target attack debuff)
    let isManaBurn = false;
    if (window.hasTalentPerk && window.hasTalentPerk("perk_mana_burn")) {
      isManaBurn = true;
      dmg = Math.floor(dmg * 1.15);
    }

    // RANGED HERO (Invoker, Shadow Fiend) — fires flying magic orb projectile
    if (p.isRanged) {
      const hClass = (RPG_STATE.profile?.hero_class || "").toLowerCase();
      const isMage = hClass === "invoker" || hClass === "mage";
      const orbCol = hClass === "shadow_fiend" ? "#c084fc" : "#38bdf8";

      // Mana empowerment for basic attacks: higher mana grants bonus magic damage!
      const spellAmpPct = (stats.spell_amp !== undefined ? stats.spell_amp : ((p.maxMp || 100) * 0.2));
      const manaMultiplier = 1.0 + ((spellAmpPct / 100) * (isMage ? 0.6 : 0.25));
      const orbDmg = Math.floor(dmg * manaMultiplier);

      ARENA.playerProjectiles.push({
        type: "magic_orb",
        x: p.x + 20,
        y: p.y - 4,
        speed: 8.8,
        dmg: orbDmg,
        isCrit: isCrit,
        isHeavy: isHeavyFinisher,
        color: orbCol,
        isMagic: true, // Tags basic attack as MAGIC DAMAGE!
        isMage: isMage
      });

      p.slashAnimation = { radius: 35, timer: 14, isMagic: true, step: ARENA.combo.step };
      return;
    }

    // MELEE HERO (Pudge, Juggernaut, PA, WK, AM) — cleave attack + wind blade wave!
    p.slashAnimation = {
      radius: isHeavyFinisher ? 85 : 65,
      timer: isHeavyFinisher ? 22 : 15,
      isMagic: false,
      step: ARENA.combo.step
    };

    if (isHeavyFinisher) {
      ARENA.cameraTrauma = Math.min(1.0, ARENA.cameraTrauma + 0.25);
    }

    // Unleash Crescent Wind Blade Projectile in player facing direction
    const pFacing = (p.facing !== undefined) ? p.facing : 1;
    if (!ARENA.playerProjectiles) ARENA.playerProjectiles = [];
    ARENA.playerProjectiles.push({
      type: "wind_blade",
      x: p.x + pFacing * 35,
      y: p.y - 6,
      speed: 10.0 * pFacing,
      dmg: Math.floor(dmg * 0.9),
      isCrit: isCrit,
      isHeavy: isHeavyFinisher,
      color: isHeavyFinisher ? "#f59e0b" : "#facc15",
      radius: isHeavyFinisher ? 28 : 20,
      hitCreepIds: new Set()
    });

    // Check direct melee hit against all creeps (direction-aware + close-quarters 360 body check)
    for (const c of ARENA.creeps) {
      // In Top-Down / Boss Fight mode, melee hit MUST be within true 2D distance!
      if (ARENA.topDownMode || ARENA.isRaidBossBattle) {
        const dist2d = Math.hypot(c.x - p.x, c.y - p.y);
        if (dist2d > (p.radius + c.radius + (isHeavyFinisher ? 50 : 32))) {
          continue; // Too far away in 2D top-down arena!
        }
      } else {
        const dx = c.x - p.x;
        const inFront = (pFacing === 1 && dx > -20 && dx < (p.attackRange + (isHeavyFinisher ? 40 : 15))) ||
                       (pFacing === -1 && dx < 20 && -dx < (p.attackRange + (isHeavyFinisher ? 40 : 15))) ||
                       (Math.abs(dx) < 45);
        if (!inFront) continue;
      }
      if (true) {
        let finalDmg = dmg;

        // Shielded Defender Guard Break Mechanics
        if (c.archetype === "defender") {
          c.shieldHits = (c.shieldHits || 0) + 1;
          if (c.shieldBrokenTimer <= 0) {
            if (isHeavyFinisher || c.shieldHits >= 3) {
              c.shieldBrokenTimer = 240;
              c.state = "stagger";
              c.staggerTimer = 80;
              c.stateTimer = 80;
              c.x += 35;
              ARENA.hitstop = 10;
              ARENA.cameraTrauma = Math.min(1.0, ARENA.cameraTrauma + 0.35);
              spawnFloatingText(c.x, c.y - 25, "💥 GUARD BREAK! (+100% УРОНА)", "#facc15");
              addStylePoints(160, "GUARD BREAK");
              triggerHaptic("heavy");
              finalDmg = Math.floor(finalDmg * 1.5);
            } else {
              finalDmg = Math.max(8, Math.floor(finalDmg * 0.5));
              spawnFloatingText(c.x, c.y - 20, `🛡️ БЛОК (-50%) [${3 - c.shieldHits} уд.]`, "#94a3b8");
              triggerHaptic("light");
            }
          }
        }

        // Check Item Passives: Desolator, Skadi, Battle Fury
        const eq = RPG_STATE.profile?.equipment || {};
        const hasBF = Object.values(eq).some(it => it && (it.name?.includes("Battle Fury") || it.name?.includes("Боевой Топор") || it.bonus?.cleave));
        const hasDeso = Object.values(eq).some(it => it && (it.name?.includes("Desolator") || it.name?.includes("Опустошитель") || it.bonus?.minus_armor));
        const hasSkadi = Object.values(eq).some(it => it && (it.name?.includes("Skadi") || it.name?.includes("Скади") || it.bonus?.frost_slow));

        if (hasDeso) {
          finalDmg = Math.floor(finalDmg * 1.24);
          if (!c.desoDebuff) {
            c.desoDebuff = 300;
            spawnFloatingText(c.x, c.y - 32, "🩸 -8 БРОНИ", "#dc2626");
          }
        }
        if (hasSkadi) {
          c.speed = Math.max(0.3, (c.speed || 0.8) * 0.55);
          spawnFloatingText(c.x, c.y - 32, "❄️ СКАДИ", "#38bdf8");
        }
        if (hasBF) {
          const cleaveDmg = Math.floor(finalDmg * 0.65);
          for (const other of ARENA.creeps) {
            if (other !== c && Math.abs(other.x - c.x) < 95) {
              safeDamageCreep(other, cleaveDmg, false);
              spawnFloatingText(other.x, other.y - 20, `🪓 КЛИВ -${cleaveDmg}`, "#f97316");
            }
          }
        }

        if (c.isBoss) {
          if (c.tormentorShield) {
            const reflectDmg = Math.max(5, Math.floor(finalDmg * 0.5));
            p.currentHp = Math.max(0, p.currentHp - reflectDmg);
            spawnFloatingText(p.x, p.y - 25, `🪞 ОТРАЖЕНИЕ -${reflectDmg}!`, "#c084fc");
            if (p.currentHp <= 0) { handlePlayerArenaDeath(); return; }
          }
          if (c.isStaggered) {
            finalDmg = Math.floor(finalDmg * 2.5);
          } else {
            const poiseDmg = isCrit ? 28 : (isHeavyFinisher ? 35 : 14);
            c.poise = Math.max(0, (c.poise !== undefined ? c.poise : 300) - poiseDmg);
            if (c.poise <= 0) {
              c.isStaggered = true;
              c.staggerTimer = 210;
              ARENA.cameraTrauma = 0.7;
              ARENA.hitstop = 10;
              spawnFloatingText(c.x, c.y - 35, "💫 ОШЕЛОМЛЕН! (+150% УРОНА)", "#facc15");
              triggerHaptic("heavy");
            }
          }
          const bDef = c.defense || 14;
          const dr = (bDef * 0.05) / (1 + bDef * 0.05);
          finalDmg = Math.max(8, Math.floor(finalDmg * (1 - dr)));
          finalDmg = applyDamageToBoss(c, finalDmg, isCrit);
        } else {
          if (isHeavyFinisher && c.archetype !== "defender") {
            c.x += 30;
          }
          safeDamageCreep(c, finalDmg, false);
        }

        if (isPudgeDismember) {
          c.stunTimer = 72;
          spawnFloatingText(c.x, c.y - 35, "🥩 ОГЛУШЕНИЕ!", "#ef4444");
        }
        if (isManaBurn) {
          c.atkDebuffTimer = 180;
          c.atkDebuff = 0.15;
          spawnFloatingText(c.x, c.y - 25, "⚡ ВЫЖИГАНИЕ!", "#38bdf8");
        }

        // Lifesteal on creeps (boss lifesteal is handled safely in applyDamageToBoss)
        if (!c.isBoss && stats.lifesteal > 0) {
          const pMax = p.maxHp || 500;
          const rawHeal = Math.floor(finalDmg * (stats.lifesteal / 100));
          const heal = Math.max(1, Math.min(Math.floor(pMax * 0.05), 5000, rawHeal));
          p.currentHp = Math.min(pMax, p.currentHp + heal);
        }

        const col = (c.isBoss && c.isStaggered) ? "#fbbf24" : (isCrit ? "#facc15" : (isHeavyFinisher ? "#f97316" : "#f87171"));
        const prefix = isHeavyFinisher ? "💥 СЛЭМ! " : (isCrit ? "⚡ КРИТ! " : "");
        const txt = (c.isBoss && c.isStaggered) ? `💥 STAGGER! -${finalDmg}` : `${prefix}-${finalDmg}`;
        spawnFloatingText(c.x, c.y - 15 - Math.random() * 10, txt, col);
      }
    }
  }

  // ---------------------------------------------------------------------------
  // SKILL 1 (SPECIFIC FOR EACH DOTA HERO)
  // ---------------------------------------------------------------------------

  function castPlayerSkill1() {
    const p = ARENA.player;
    const stats = RPG_STATE.profile?.stats || {};
    const skillCfg = getHeroSkillConfig();
    const hClass = (RPG_STATE.profile?.hero_class || "pudge").toLowerCase();
    let cost = 20;
    if (p.croakTimer > 0) {
      cost = Math.floor(cost * 0.4); // 3-й скилл Ларго: -60% расхода маны!
    }

    if (p.isFrozenInTime || (p.stunTimer && p.stunTimer > 0)) {
      spawnFloatingText(p.x, p.y - 25, "💫 ОГЛУШЕНИЕ!", "#facc15");
      triggerHaptic("error");
      return;
    }
    if ((p.silenceTimer && p.silenceTimer > 0) || (p.doomDebuffTimer && p.doomDebuffTimer > 0)) {
      spawnFloatingText(p.x, p.y - 25, "🔇 БЕЗМОЛВИЕ (СКИЛЛЫ ЗАБЛОКИРОВАНЫ)!", "#c084fc");
      triggerHaptic("error");
      return;
    }

    if (ARENA.skill1Cooldown > 0) {
      const sec = Math.ceil(ARENA.skill1Cooldown / 60);
      spawnFloatingText(p.x, p.y - 25, `${skillCfg.skill1Name}: КД ${sec}с`, "#94a3b8");
      triggerHaptic("error");
      return;
    }
    if (p.currentMp < cost) {
      spawnFloatingText(p.x, p.y - 25, `Мало маны (нужно ${cost} MP)!`, "#94a3b8");
      triggerHaptic("error");
      return;
    }

    p.currentMp -= cost;
    const cdReduct1 = 1.0 - ((RPG_STATE.profile?.talents?.cooldown || 0) * 0.06);
    ARENA.skill1Cooldown = Math.floor(skillCfg.skill1Cd * cdReduct1);
    triggerHaptic("heavy");

    // TOP-DOWN 360° BOSS TARGETING FOR ALL SKILLS
    if (ARENA.topDownMode || ARENA.isRaidBossBattle) {
      const boss = ARENA.bossEntity;
      if (boss && boss.hp > 0) {
        const toBossAngle = Math.atan2(boss.y - p.y, boss.x - p.x);

        if (hClass === "invoker") {
          // Sunstrike: drops blazing solar burst directly on boss!
          ARENA.specialEffects.push({ type: "sunstrike", x: boss.x, y: boss.y, radius: 90, timer: 36, maxTimer: 36 });
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 3.8));
          spawnFloatingText(boss.x, boss.y - 35, `☀️ САНСТРАЙК! -${dmg}`, "#facc15");
          ARENA.cameraTrauma = 0.5;
          return;
        } else if (hClass === "phantom_assassin") {
          // Stifling Dagger: spinning shadowy dagger flies at boss with neon critical sparks!
          const dmg = Math.floor((stats.max_atk || 30) * 3.4);
          ARENA.specialEffects.push({
            type: "dagger_throw",
            fromX: p.x,
            fromY: p.y,
            toX: boss.x,
            toY: boss.y,
            x: p.x,
            y: p.y,
            angle: toBossAngle,
            timer: 20,
            maxTimer: 20,
            dmg: dmg
          });
          const actualDmg = applyDamageToBoss(boss, dmg, true);
          spawnFloatingText(boss.x, boss.y - 30, `🗡️ КИНЖАЛ ТЕНИ! -${actualDmg}`, "#f43f5e");
          ARENA.cameraTrauma = 0.35;
          return;
        } else if (hClass === "shadow_fiend") {
          // Triple Shadowraze: 3 erupting dark soul pillars erupt along line towards boss!
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 2.6));
          for (let r = 1; r <= 3; r++) {
            const rx = p.x + Math.cos(toBossAngle) * (r * 68);
            const ry = p.y + Math.sin(toBossAngle) * (r * 68);
            ARENA.specialEffects.push({ type: "shadowraze", x: rx, y: ry, radius: 46, timer: 32, maxTimer: 32 });
          }
          spawnFloatingText(boss.x, boss.y - 30, `🌑 КОЙЛЫ ТЕМНОТЫ! -${dmg}`, "#c084fc");
          ARENA.cameraTrauma = 0.45;
          return;
        } else if (hClass === "pudge") {
          // Meat Hook: iron chain with sharp hook shoots directly at boss!
          p.fleshHeapActive = 480;
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 2.8));
          ARENA.specialEffects.push({
            type: "meat_hook",
            fromX: p.x,
            fromY: p.y,
            toX: boss.x,
            toY: boss.y,
            timer: 24,
            maxTimer: 24,
            dmg: dmg
          });
          spawnFloatingText(boss.x, boss.y - 30, `🥩 МЯСНОЙ КРЮК! -${dmg}`, "#ef4444");
          ARENA.cameraTrauma = 0.5;
          return;
        } else if (hClass === "juggernaut") {
          // Blade Fury: swirling golden whirlwind vortex around Juggernaut!
          p.bladeDanceActive = 360;
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 3.0));
          ARENA.specialEffects.push({
            type: "blade_fury",
            x: p.x,
            y: p.y,
            radius: 52,
            timer: 45,
            maxTimer: 45,
            dmg: dmg
          });
          spawnFloatingText(boss.x, boss.y - 30, `💨 ВИХРЬ КЛИНКОВ! -${dmg}`, "#f59e0b");
          ARENA.cameraTrauma = 0.4;
          return;
        } else if (hClass === "wraith_king") {
          // Wraithfire Blast: flaming green ghost skull missile screaming at boss!
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 2.8));
          boss.poise = Math.max(0, (boss.poise || 400) - 80);
          ARENA.specialEffects.push({
            type: "wraithfire",
            fromX: p.x,
            fromY: p.y,
            toX: boss.x,
            toY: boss.y,
            timer: 26,
            maxTimer: 26,
            dmg: dmg
          });
          spawnFloatingText(boss.x, boss.y - 30, `💀 ПРИЗРАЧНЫЙ СТАН! -${dmg}`, "#10b981");
          ARENA.cameraTrauma = 0.45;
          return;
        } else if (hClass === "anti_mage") {
          // Blink Strike: poof at origin, instant dash, and dual mana slash behind boss!
          ARENA.specialEffects.push({ type: "blink_poof", x: p.x, y: p.y, timer: 18, maxTimer: 18 });
          p.x = Math.max(40, Math.min(480, boss.x - Math.cos(toBossAngle) * 50));
          p.y = Math.max(50, Math.min(670, boss.y - Math.sin(toBossAngle) * 50));
          p.counterspellActive = 240;
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 3.2));
          ARENA.specialEffects.push({ type: "mana_slash", x: boss.x, y: boss.y, timer: 24, maxTimer: 24, dmg: dmg });
          spawnFloatingText(boss.x, boss.y - 30, `⚡ ВЫПАД ИЗ ТЕНИ! -${dmg}`, "#38bdf8");
          ARENA.cameraTrauma = 0.5;
          return;
        } else if (hClass === "leshrac") {
          // Croak of Genius (3-й скилл Ларго): -60% расхода маны + эхо-урон + восстановление маны
          p.croakTimer = 480; // 8 sec
          p.currentMp = Math.min(p.maxMp, p.currentMp + 45);
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 3.4));
          boss.stunTimer = Math.max(boss.stunTimer || 0, 60); // 1.0s ministun
          ARENA.specialEffects.push({
            type: "croak_blast",
            x: boss.x,
            y: boss.y,
            radius: 85,
            timer: 30,
            maxTimer: 30,
            color: "#a855f7"
          });
          ARENA.cameraTrauma = 0.5;
          spawnFloatingText(p.x, p.y - 35, "🎵 КВАКАНЬЕ ГЕНИЯ! (+45 MP, ЭХО)", "#c084fc");
          spawnFloatingText(boss.x, boss.y - 30, `🎶 РЕХО-УРОН! -${dmg}`, "#facc15");
          return;
        }
      }
    }

    // 1. INVOKER: Sun Strike (Солнечный луч с неба с чистым уроном)
    if (hClass === "invoker") {
      let targetX = ARENA.width * 0.54;
      if (ARENA.creeps.length > 0) {
        let maxHpCreep = ARENA.creeps[0];
        for (const c of ARENA.creeps) {
          if (c.hp > maxHpCreep.hp) maxHpCreep = c;
        }
        targetX = maxHpCreep.x;
      }

      const strikeY = ARENA.roadY - 12;
      const radius = 110;
      const spellAmpPct = (stats.spell_amp !== undefined ? stats.spell_amp : ((p.maxMp || 100) * 0.2));
      const manaBonus = 1.0 + (spellAmpPct / 100) + (p.currentMp ? (p.currentMp / p.maxMp) * 0.25 : 0);
      const dmg = Math.floor((stats.max_atk || 30) * 3.6 * manaBonus);

      ARENA.specialEffects.push({
        type: "sunstrike",
        x: targetX,
        y: strikeY,
        radius: radius,
        timer: 42,
        maxTimer: 42
      });
      ARENA.cameraTrauma = Math.min(1.0, ARENA.cameraTrauma + 0.35);
      ARENA.hitstop = 4;
      spawnFloatingText(targetX, strikeY - 48, "☀️ САНСТРАЙК! (ЧИСТЫЙ УРОН)", "#facc15");

      for (const c of ARENA.creeps) {
        if (Math.abs(c.x - targetX) < radius) {
          if (c.archetype === "defender") {
            c.shieldBrokenTimer = 240;
            c.state = "stagger";
            c.staggerTimer = 85;
            c.stateTimer = 85;
            spawnFloatingText(c.x, c.y - 25, "💥 GUARD BREAK САНСТРАЙКОМ!", "#facc15");
          }
          safeDamageCreep(c, dmg, false);
          c.attackCooldown = -60; // stunned by intense solar burst
          spawnFloatingText(c.x, c.y - 20, `☀️ -${dmg} ЧИСТЫЙ!`, "#facc15");
        }
      }
      return;
    }

    // 2. PUDGE: Flesh Heap (-40% damage for 8 sec)
    if (hClass === "pudge") {
      p.fleshHeapActive = 480; // 8 sec
      spawnFloatingText(p.x + 20, p.y - 35, "🥩 ЗАЩИТНАЯ ПЛОТЬ (-40% урона)!", "#ef4444");
      return;
    }

    // 3. JUGGERNAUT: Blade Dance (+50% attack speed for 6 sec)
    if (hClass === "juggernaut") {
      p.bladeDanceActive = 360; // 6 sec
      spawnFloatingText(p.x + 20, p.y - 35, "💨 ТАНЕЦ КЛИНКА (+50% ск. атаки)!", "#f59e0b");
      return;
    }

    // 4. PHANTOM ASSASSIN: Stifling Dagger
    if (hClass === "phantom_assassin") {
      let target = null;
      let maxDist = 0;
      for (const c of ARENA.creeps) {
        if (c.x > maxDist) { maxDist = c.x; target = c; }
      }
      const daggerDmg = Math.floor((stats.max_atk || 30) * 3.2);
      ARENA.playerProjectiles.push({
        type: "dagger",
        x: p.x + 25,
        y: p.y - 5,
        speed: 12,
        dmg: daggerDmg,
        isCrit: true,
        slow: true,
        icon: "🗡️",
        color: "#f43f5e"
      });
      spawnFloatingText(p.x + 20, p.y - 35, "🗡️ КИНЖАЛ ТЕНИ!", "#f43f5e");
      return;
    }

    // 5. SHADOW FIEND: Triple Shadowraze
    if (hClass === "shadow_fiend") {
      const razes = [p.x + 90, p.x + 180, p.x + 270];
      const dmg = Math.floor((stats.max_atk || 30) * 2.2);
      for (const rx of razes) {
        ARENA.specialEffects.push({ type: "shadowraze", x: rx, y: ARENA.roadY - 15, radius: 50, timer: 30 });
        for (const c of ARENA.creeps) {
          if (Math.abs(c.x - rx) < 55) {
            safeDamageCreep(c, dmg, false);
            spawnFloatingText(c.x, c.y - 20, `🌑 -${dmg}`, "#c084fc");
          }
        }
      }
      spawnFloatingText(p.x + 30, p.y - 40, "🌑 ТРОЙНОЙ КОЙЛ!", "#a855f7");
      return;
    }

    // 6. WRAITH KING: Wraithfire Blast
    if (hClass === "wraith_king") {
      const dmg = Math.floor((stats.max_atk || 30) * 2.4);
      ARENA.playerProjectiles.push({
        type: "dagger",
        x: p.x + 25,
        y: p.y - 5,
        speed: 9,
        dmg: dmg,
        isCrit: false,
        slow: true,
        icon: "💀",
        color: "#10b981"
      });
      spawnFloatingText(p.x + 20, p.y - 35, "💀 ПРИЗРАЧНЫЙ СТАН!", "#10b981");
      return;
    }

    // 7. ANTI-MAGE: Counterspell Shield
    if (hClass === "anti_mage") {
      p.counterspellActive = 240; // 4 sec
      spawnFloatingText(p.x + 20, p.y - 35, "🛡️ ЩИТ МАГИИ!", "#38bdf8");
      // Blink strike nearest creep
      if (ARENA.creeps.length > 0) {
        const c = ARENA.creeps[0];
        const dmg = Math.floor((stats.max_atk || 30) * 2.5);
        safeDamageCreep(c, dmg, false);
        spawnFloatingText(c.x, c.y - 20, `⚡ ВЫПАД! -${dmg}`, "#a855f7");
      }
      return;
    }

    // 8. LARGO: Diabolic Edict (Магическое эхо)
    if (hClass === "leshrac") {
      p.edictTimer = 180; // 3 sec (60 fps * 3)
      p.edictDmgMult = 0.55;
      
      ARENA.specialEffects.push({
        type: "edict_aura",
        x: p.x,
        y: p.y,
        radius: 200,
        timer: 180,
        maxTimer: 180,
        color: "#c084fc"
      });
      ARENA.cameraTrauma = Math.min(1.0, ARENA.cameraTrauma + 0.3);
      spawnFloatingText(p.x, p.y - 35, "🎵 МАГИЧЕСКОЕ ЭХО!", "#c084fc");


      for (const c of ARENA.creeps) {
        if (Math.abs(c.x - targetX) < radius) {
          if (c.archetype === "defender") {
            c.shieldBrokenTimer = 240;
            c.state = "stagger";
            c.staggerTimer = 90;
            c.stateTimer = 90;
          }
          safeDamageCreep(c, dmg, false);
          c.attackCooldown = -60; // 1s ministun
          spawnFloatingText(c.x, c.y - 20, `🎶 -${dmg} РЕХО!`, "#facc15");
        }
      }
      return;
    }
  }

  // ---------------------------------------------------------------------------
  // ULTIMATE ABILITY (SPECIFIC FOR EACH DOTA HERO)
  // ---------------------------------------------------------------------------

  function castPlayerUltimate() {
    const p = ARENA.player;
    const stats = RPG_STATE.profile?.stats || {};
    const skillCfg = getHeroSkillConfig();
    const hClass = (RPG_STATE.profile?.hero_class || "pudge").toLowerCase();
    let cost = 35;
    if (p.croakTimer > 0) {
      cost = Math.floor(cost * 0.4); // 3-й скилл Ларго: -60% расхода маны!
    }

    if (p.isFrozenInTime || (p.stunTimer && p.stunTimer > 0)) {
      spawnFloatingText(p.x, p.y - 25, "💫 ОГЛУШЕНИЕ!", "#facc15");
      triggerHaptic("error");
      return;
    }
    if ((p.silenceTimer && p.silenceTimer > 0) || (p.doomDebuffTimer && p.doomDebuffTimer > 0)) {
      spawnFloatingText(p.x, p.y - 25, "🔇 БЕЗМОЛВИЕ (УЛЬТА ЗАБЛОКИРОВАНА)!", "#c084fc");
      triggerHaptic("error");
      return;
    }

    // LARGO TOGGLE ULTIMATE: AMPHIBIAN RHAPSODY (ВКЛ / ВЫКЛ)
    if (hClass === "leshrac") {
      if (p.largoRhapsodyActive) {
        // Выключение ульты
        p.largoRhapsodyActive = false;
        ARENA.ultCooldown = 30; // 0.5с защита от двойного клика
        spawnFloatingText(p.x, p.y - 35, "🛑 РАПСОДИЯ ВЫКЛЮЧЕНА", "#94a3b8");
        triggerHaptic("light");
        const ultEl = document.getElementById("rpg-cd-ult");
        if (ultEl) ultEl.textContent = "ВКЛ";
        return;
      } else {
        // Включение ульты
        if (ARENA.ultCooldown > 0) {
          const sec = Math.ceil(ARENA.ultCooldown / 60);
          spawnFloatingText(p.x, p.y - 25, `КД ${sec}с`, "#94a3b8");
          triggerHaptic("error");
          return;
        }
        let tickMpCost = 5;
        if (p.croakTimer > 0) tickMpCost = Math.floor(tickMpCost * 0.4);
        if (p.currentMp < tickMpCost) {
          spawnFloatingText(p.x, p.y - 25, `Мало маны (нужно ${tickMpCost} MP)!`, "#94a3b8");
          triggerHaptic("error");
          return;
        }

        p.largoRhapsodyActive = true;
        p.largoRhapsodyTickTimer = 30; // 0.5 сек между тактами
        p.largoRhapsodyDmgMult = 1.0 + ((stats.ult_boost || 0) / 100.0);
        ARENA.ultCooldown = 30; // 0.5с перезарядка на переключение

        // Мгновенный первый такт при включении
        p.currentMp -= tickMpCost;
        spawnFloatingText(p.x, p.y - 48, `⚡ -${tickMpCost} MP`, "#38bdf8");

        const ultMult = p.largoRhapsodyDmgMult;
        const spellAmp = (stats.spell_amp !== undefined ? stats.spell_amp : ((p.maxMp || 100) * 0.2));
        const healAmt = Math.max(12, Math.min(Math.floor(p.maxHp * 0.01), 6000) + Math.min(4000, Math.floor((stats.int || 20) * 0.25)));
        p.currentHp = Math.min(p.maxHp, p.currentHp + healAmt);
        spawnFloatingText(p.x, p.y - 30, `💚 +${healAmt} ХП (РАПСОДИЯ)`, "#22c55e");

        if (!ARENA.specialEffects) ARENA.specialEffects = [];
        ARENA.specialEffects.push({
          type: "rhapsody_beat",
          x: p.x,
          y: p.y,
          radius: 25,
          maxRadius: 280,
          timer: 28,
          maxTimer: 28,
          color: "#22c55e"
        });
        ARENA.cameraTrauma = Math.min(1.0, (ARENA.cameraTrauma || 0) + 0.3);
        triggerHaptic("heavy");

        const pulseDmg = Math.floor(((stats.max_atk || 30) * 0.7 + spellAmp * 0.25) * ultMult);
        if (ARENA.topDownMode || ARENA.isRaidBossBattle) {
          if (ARENA.bossEntity && ARENA.bossEntity.hp > 0) {
            const dist = Math.hypot(ARENA.bossEntity.x - p.x, ARENA.bossEntity.y - p.y);
            if (dist <= 280) {
              const actualDmg = applyDamageToBoss(ARENA.bossEntity, pulseDmg);
              spawnFloatingText(ARENA.bossEntity.x, ARENA.bossEntity.y - 25, `🐸 -${actualDmg} РАПСОДИЯ`, "#a855f7");
            }
          }
          for (const c of ARENA.creeps) {
            const dist = Math.hypot(c.x - p.x, c.y - p.y);
            if (dist <= 280) {
              if (c.isBoss) {
                applyDamageToBoss(c, pulseDmg);
              } else {
                c.hp -= pulseDmg;
              }
              spawnFloatingText(c.x, c.y - 15, `🐸 -${pulseDmg}`, "#a855f7");
            }
          }
        } else {
          for (const c of ARENA.creeps) {
            if (Math.abs(c.x - p.x) <= 320) {
              safeDamageCreep(c, pulseDmg, false);
              spawnFloatingText(c.x, c.y - 15, `🐸 -${pulseDmg} РАПСОДИЯ`, "#a855f7");
            }
          }
        }

        spawnFloatingText(p.x, p.y - 65, "🐸 РАПСОДИЯ ВКЛ (Каждые 0.5с: хил, урон, -MP)", "#22c55e");
        const ultEl = document.getElementById("rpg-cd-ult");
        if (ultEl) ultEl.textContent = "ВЫКЛ";
        return;
      }
    }

    if (ARENA.ultCooldown > 0) {
      const sec = Math.ceil(ARENA.ultCooldown / 60);
      spawnFloatingText(p.x, p.y - 25, `Ульта: КД ${sec}с`, "#94a3b8");
      triggerHaptic("error");
      return;
    }
    if (p.currentMp < cost) {
      spawnFloatingText(p.x, p.y - 25, `Мало маны (нужно ${cost} MP)!`, "#94a3b8");
      triggerHaptic("error");
      return;
    }

    p.currentMp -= cost;
    const ultCdReduct = Math.min(60, stats.ult_cd_reduct || 0);
    ARENA.ultCooldown = Math.max(60, Math.floor(skillCfg.ultCd * (1.0 - ultCdReduct / 100.0)));
    triggerHaptic("heavy");

    const ultMultiplier = 1.0 + ((stats.ult_boost || 0) / 100.0);

    // TOP-DOWN 360° BOSS ULTIMATES
    if (ARENA.topDownMode || ARENA.isRaidBossBattle) {
      const boss = ARENA.bossEntity;
      if (boss && boss.hp > 0) {
        if (hClass === "invoker") {
          // Chaos Meteor (Котлета) falls from sky directly on boss with massive fiery explosion!
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 5.5 * ultMultiplier));
          ARENA.specialEffects.push({
            type: "topdown_meteor",
            startX: Math.max(30, Math.min(480, boss.x - 90)),
            startY: -70,
            targetX: boss.x,
            targetY: boss.y,
            x: Math.max(30, Math.min(480, boss.x - 90)),
            y: -70,
            radius: 36,
            timer: 50,
            maxTimer: 50,
            dmg: dmg
          });
          ARENA.cameraTrauma = 0.85;
          triggerHaptic("heavy");
          spawnFloatingText(boss.x, boss.y - 45, `☄️ ХАОС МЕТЕОР! -${dmg}`, "#ea580c");
          if (window.hasTalentPerk && window.hasTalentPerk("perk_double_cataclysm")) {
            setTimeout(() => {
              if (boss && boss.hp > 0) {
                const dmg2 = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 4.0 * ultMultiplier));
                ARENA.specialEffects.push({
                  type: "topdown_meteor",
                  startX: Math.max(30, Math.min(480, boss.x + 60)),
                  startY: -70,
                  targetX: boss.x,
                  targetY: boss.y,
                  x: Math.max(30, Math.min(480, boss.x + 60)),
                  y: -70,
                  radius: 30,
                  timer: 40,
                  maxTimer: 40,
                  dmg: dmg2
                });
                spawnFloatingText(boss.x, boss.y - 60, `☄️ ВТОРОЙ МЕТЕОР! -${dmg2}`, "#f97316");
              }
            }, 350);
          }
          return;
        } else if (hClass === "juggernaut") {
          // Omnislash: rapid slashing combo around the boss!
          if (window.hasTalentPerk && window.hasTalentPerk("perk_omnislash_invuln")) {
            p.isInvulnerable = 55;
          }
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 6.0 * ultMultiplier));
          ARENA.specialEffects.push({
            type: "topdown_omnislash",
            x: boss.x,
            y: boss.y,
            timer: 52,
            maxTimer: 52,
            slashes: 8,
            dmg: dmg
          });
          ARENA.cameraTrauma = 0.9;
          triggerHaptic("heavy");
          spawnFloatingText(boss.x, boss.y - 45, `⚔️ ОМНИСЛЕШ ПО БОССУ! -${dmg}`, "#facc15");
          return;
        } else if (hClass === "phantom_assassin") {
          // Coup de Grace: blood critical strike!
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 6.5 * ultMultiplier));
          ARENA.specialEffects.push({
            type: "coup_de_grace",
            x: boss.x,
            y: boss.y,
            timer: 35,
            maxTimer: 35,
            dmg: dmg
          });
          ARENA.cameraTrauma = 1.0;
          triggerHaptic("heavy");
          spawnFloatingText(boss.x, boss.y - 45, `🩸 COUP DE GRACE x6.5! -${dmg}`, "#dc2626");
          return;
        } else if (hClass === "shadow_fiend") {
          // Requiem of Souls: blast of souls across the arena!
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 5.8 * ultMultiplier));
          ARENA.specialEffects.push({
            type: "requiem_of_souls",
            x: p.x,
            y: p.y,
            timer: 45,
            maxTimer: 45,
            dmg: dmg
          });
          if (window.hasTalentPerk && window.hasTalentPerk("perk_requiem_fear")) {
            boss.fearTimer = 150; // 2.5s
            spawnFloatingText(boss.x, boss.y - 65, "😱 СТРАХ (2.5с)!", "#a855f7");
          }
          ARENA.cameraTrauma = 0.85;
          triggerHaptic("heavy");
          spawnFloatingText(boss.x, boss.y - 45, `🌪️ РЕКВИЕМ ДУШ! -${dmg}`, "#a855f7");
          return;
        } else if (hClass === "wraith_king") {
          // Skeleton Army: massive critical strike + summon skeletons
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 5.2 * ultMultiplier));
          p.currentHp = Math.min(p.maxHp, p.currentHp + Math.floor(dmg * 0.4));
          ARENA.specialEffects.push({
            type: "wk_skeletons",
            x: p.x,
            y: p.y,
            bossX: boss.x,
            bossY: boss.y,
            timer: 180,
            maxTimer: 180
          });
          if (!ARENA.alliedMinions) ARENA.alliedMinions = [];
          for (let s = 0; s < 3; s++) {
            ARENA.alliedMinions.push({
              x: p.x + (s - 1) * 28,
              y: p.y + 20,
              radius: 12,
              hp: 150,
              maxHp: 150,
              atk: Math.floor((stats.max_atk || 30) * 0.9),
              speed: 2.8,
              heroClass: "wraith_king",
              name: "Скелет"
            });
          }
          spawnFloatingText(boss.x, boss.y - 45, `👑 АРМИЯ СКЕЛЕТОВ! -${dmg}`, "#10b981");
          return;
        } else if (hClass === "pudge") {
          // Rot & Dismember: toxic miasma & meat cleaver chops
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 4.8 * ultMultiplier));
          p.rotActive = 180;
          ARENA.specialEffects.push({
            type: "pudge_dismember",
            fromX: p.x,
            fromY: p.y,
            x: boss.x,
            y: boss.y,
            timer: 45,
            maxTimer: 45,
            dmg: dmg
          });
          spawnFloatingText(boss.x, boss.y - 45, `☣️ ЧУМНАЯ ГНИЛЬ! -${dmg}`, "#22c55e");
          return;
        } else if (hClass === "anti_mage") {
          // Mana Void: Arcane implosion on boss!
          const dmg = applyDamageToBoss(boss, Math.floor((stats.max_atk || 30) * 5.6 * ultMultiplier));
          ARENA.specialEffects.push({
            type: "mana_void",
            x: boss.x,
            y: boss.y,
            timer: 40,
            maxTimer: 40,
            dmg: dmg
          });
          ARENA.cameraTrauma = 0.9;
          spawnFloatingText(boss.x, boss.y - 45, `💥 ВЗРЫВ МАНЫ! -${dmg}`, "#38bdf8");
          return;
        }
      }
    }

    // 1. INVOKER: Chaos Meteor («Котлета» Инвокера, падающая с неба и катящаяся по всей линии)
    if (hClass === "invoker") {
      const spellAmpPct = (stats.spell_amp !== undefined ? stats.spell_amp : ((p.maxMp || 100) * 0.2));
      const manaBonus = 1.0 + (spellAmpPct / 100) + (p.currentMp ? (p.currentMp / p.maxMp) * 0.3 : 0);
      const meteorDmg = Math.floor((stats.max_atk || 30) * 3.2 * manaBonus * ultMultiplier);
      if (!ARENA.playerProjectiles) ARENA.playerProjectiles = [];

      ARENA.playerProjectiles.push({
        type: "meteor",
        x: p.x + 15,
        y: -50,
        targetY: ARENA.roadY - 16,
        vx: 2.0,
        vy: 9.5,
        falling: true,
        speed: 5.2,
        radius: 36,
        angle: 0,
        dmg: meteorDmg,
        hitCreepIds: new Set(),
        burnTrail: []
      });

      spawnFloatingText(p.x + 40, p.y - 45, `☄️ ХАОС МЕТЕОР ПАДАЕТ С НЕБА!${stats.ult_boost ? ` (+${stats.ult_boost}% Ульта)` : ""}`, "#ea580c");
      triggerHaptic("heavy");
      if (window.hasTalentPerk && window.hasTalentPerk("perk_double_cataclysm")) {
        setTimeout(() => {
          if (!ARENA.playerProjectiles) ARENA.playerProjectiles = [];
          ARENA.playerProjectiles.push({
            type: "meteor",
            x: p.x + 55,
            y: -50,
            targetY: ARENA.roadY - 16,
            vx: 2.2,
            vy: 9.5,
            falling: true,
            speed: 5.2,
            radius: 30,
            angle: 0,
            dmg: Math.floor(meteorDmg * 0.75),
            hitCreepIds: new Set(),
            burnTrail: []
          });
          spawnFloatingText(p.x + 60, p.y - 45, "☄️ ВТОРОЙ МЕТЕОР!", "#f97316");
        }, 350);
      }
      return;
    }

    // 2. PUDGE: Rot (Choking Poison Cloud for 2.5s across the whole map)
    if (hClass === "pudge") {
      p.rotActive = 150; // 2.5 sec
      p.rotDmgMult = ultMultiplier;
      ARENA.specialEffects.push({ type: "rot", timer: 150, maxTimer: 150 });
      spawnFloatingText(p.x + 30, p.y - 45, `☣️ ЧУМНАЯ ГНИЛЬ!${stats.ult_boost ? ` (+${stats.ult_boost}% Ульта)` : ""}`, "#22c55e");
      return;
    }

    // 3. JUGGERNAUT: Omnislash (8 golden slashing strikes across the field)
    if (hClass === "juggernaut") {
      if (window.hasTalentPerk && window.hasTalentPerk("perk_omnislash_invuln")) {
        p.isInvulnerable = 65;
      }
      ARENA.specialEffects.push({ type: "omnislash", slashes: 8, timer: 65, currentSlash: 0, mult: ultMultiplier });
      spawnFloatingText(p.x + 30, p.y - 45, `⚔️ ОМНИСЛЕШ ПО ВСЕЙ КАРТЕ!${stats.ult_boost ? ` (+${stats.ult_boost}% Ульта)` : ""}`, "#facc15");
      return;
    }

    // 4. PHANTOM ASSASSIN: Coup de Grace (Screen Blood Flash + x5.5 Crit)
    if (hClass === "phantom_assassin") {
      ARENA.specialEffects.push({ type: "blood_flash", timer: 20 });
      const critDmg = Math.floor((stats.max_atk || 30) * 5.5 * ultMultiplier);
      for (const c of ARENA.creeps) {
        if (c.archetype === "defender") {
          c.shieldBrokenTimer = 240;
          c.state = "stagger";
          c.staggerTimer = 80;
          c.stateTimer = 80;
        }
        safeDamageCreep(c, critDmg, false);
        spawnFloatingText(c.x, c.y - 25, `🩸 КРИТ x5.5! -${critDmg}`, "#dc2626");
      }
      spawnFloatingText(p.x + 30, p.y - 45, `🩸 COUP DE GRACE!${stats.ult_boost ? ` (+${stats.ult_boost}% Ульта)` : ""}`, "#dc2626");
      return;
    }

    // 5. SHADOW FIEND: Requiem of Souls (Waves of souls across all lanes)
    if (hClass === "shadow_fiend") {
      const dmg = Math.floor((stats.max_atk || 30) * 4.5 * ultMultiplier);
      for (let i = 0; i < 8; i++) {
        ARENA.playerProjectiles.push({
          type: "dagger",
          x: p.x + 20,
          y: p.y - 25 + i * 8,
          speed: 6.5 + i * 0.5,
          dmg: dmg,
          icon: "🌑",
          color: "#c084fc"
        });
      }
      if (window.hasTalentPerk && window.hasTalentPerk("perk_requiem_fear")) {
        for (const c of ARENA.creeps) {
          c.fearTimer = 150;
          c.speed = -1.0;
        }
        spawnFloatingText(p.x + 30, p.y - 65, "😱 СТРАХ НА ВСЕХ!", "#a855f7");
      }
      spawnFloatingText(p.x + 30, p.y - 45, `🌪️ РЕКВИЕМ ДУШ!${stats.ult_boost ? ` (+${stats.ult_boost}% Ульта)` : ""}`, "#a855f7");
      return;
    }

    // 6. WRAITH KING: Vampiric Skeleton Army (Summons 3 skeletons + full lifesteal)
    if (hClass === "wraith_king") {
      for (let i = 0; i < 3; i++) {
        ARENA.alliedMinions.push({
          x: p.x + 30 + i * 20,
          y: ARENA.roadY - 14 + (i * 12 - 12),
          speed: 2.2,
          hp: Math.floor(90 * ultMultiplier),
          maxHp: Math.floor(90 * ultMultiplier),
          atk: Math.floor((stats.max_atk || 25) * 1.4 * ultMultiplier),
          radius: 14,
          icon: "☠️"
        });
      }
      p.currentHp = Math.min(p.maxHp, p.currentHp + Math.floor(p.maxHp * 0.5 * ultMultiplier));
      spawnFloatingText(p.x + 30, p.y - 45, `👑 АРМИЯ СКЕЛЕТОВ + ИСЦЕЛЕНИЕ!${stats.ult_boost ? ` (+${stats.ult_boost}% Ульта)` : ""}`, "#10b981");
      return;
    }

    // 7. ANTI-MAGE: Mana Void
    if (hClass === "anti_mage") {
      const dmg = Math.floor((stats.max_atk || 30) * 4.8 * ultMultiplier);
      const targetX = ARENA.width * 0.6;
      ARENA.specialEffects.push({ type: "lightning", x: targetX, y: ARENA.roadY - 15, radius: 130, timer: 30 });
      for (const c of ARENA.creeps) {
        if (c.archetype === "defender") {
          c.shieldBrokenTimer = 240;
          c.state = "stagger";
          c.staggerTimer = 80;
          c.stateTimer = 80;
        }
        safeDamageCreep(c, dmg, false);
        spawnFloatingText(c.x, c.y - 20, `💥 ВЗРЫВ МАНЫ! -${dmg}`, "#8b5cf6");
      }
      spawnFloatingText(p.x + 30, p.y - 45, `💥 ВЗРЫВ МАНЫ (MANA VOID)!${stats.ult_boost ? ` (+${stats.ult_boost}% Ульта)` : ""}`, "#8b5cf6");
      return;
    }
  }


  // ===========================================================================
  // ACTIVE ITEMS SYSTEM (Refresher Orb, Dagon, Blink, BKB, Eul, Shiva, Satanic)
  // ===========================================================================

  const ACTIVE_ITEM_DEFINITIONS = {
    refresher: {
      match: (it) => it && (it.name?.toLowerCase().includes("refresher") || it.name?.toLowerCase().includes("обновлен") || it.bonus?.refresh),
      name: "Сфера Обновления (Refresher Orb)",
      shortName: "Рефрешер",
      icon: "🟢",
      cdFrames: 1500, // 25s
      cdSec: 25,
      mpCost: 40,
      description: "Мгновенно сбрасывает время перезарядки всех скиллов!",
      execute: (p, stats) => {
        ARENA.skill1Cooldown = 0;
        ARENA.ultCooldown = 0;
        p.attackCooldown = 0;
        if (p.dashCooldown) p.dashCooldown = 0;
        if (p.isBlocking) p.isBlocking = 0;
        
        // Reset any other active items except refresher itself
        if (ARENA.itemCooldowns) {
          for (const k in ARENA.itemCooldowns) {
            if (k !== "refresher") ARENA.itemCooldowns[k] = 0;
          }
        }

        // Sync DOM immediately
        const s1El = document.getElementById("rpg-cd-skill1");
        if (s1El) s1El.textContent = "Скилл 1";
        const btn1 = document.getElementById("rpg-btn-skill1");
        if (btn1) btn1.style.opacity = "1";

        const ultEl = document.getElementById("rpg-cd-ult");
        if (ultEl) ultEl.textContent = "Ульта";
        const btnUlt = document.getElementById("rpg-btn-ult");
        if (btnUlt) btnUlt.style.opacity = "1";

        // Green energy burst expanding from hero
        ARENA.specialEffects.push({
          type: "refresher_burst",
          x: p.x,
          y: p.y,
          radius: 10,
          maxRadius: 75,
          timer: 35
        });

        spawnFloatingText(p.x + 30, p.y - 45, "🟢 РЕФРЕШЕР! ВСЕ СКИЛЛЫ ГОТОВЫ! ⚡", "#22c55e");
        triggerHaptic("heavy");
        return true;
      }
    },
    dagon: {
      match: (it) => it && (it.name?.toLowerCase().includes("dagon") || it.name?.toLowerCase().includes("дагон") || it.bonus?.burst_magic),
      name: "Дагон (Dagon)",
      shortName: "Дагон",
      icon: "⚡",
      cdFrames: 720, // 12s
      cdSec: 12,
      mpCost: 25,
      description: "Мощный разряд молнии в ближайшего врага",
      execute: (p, stats, item) => {
        const baseBurst = item?.bonus?.burst_magic || 150;
        const spellAmp = stats.spell_amp || 0;
        const totalInt = stats.total_intelligence || (stats.gear_int || 0) + (p.intelligence || 10);
        const dmg = Math.floor(baseBurst * (1 + spellAmp / 100) * (1 + totalInt / 80));

        let target = null;
        let minX = 9999;
        for (const c of ARENA.creeps) {
          if (c.hp > 0 && c.x < minX) {
            minX = c.x;
            target = c;
          }
        }
        if (!target && ARENA.bossEntity && ARENA.bossEntity.hp > 0) {
          target = ARENA.bossEntity;
        }
        if (!target) {
          spawnFloatingText(p.x, p.y - 25, "Нет целей в радиусе!", "#94a3b8");
          return false;
        }

        safeDamageCreep(target, dmg, false);
        ARENA.specialEffects.push({
          type: "dagon_beam",
          fromX: p.x + 20,
          fromY: p.y - 12,
          toX: target.x,
          toY: target.y,
          timer: 18,
          color: "#ef4444"
        });

        spawnFloatingText(target.x, target.y - 30, `⚡ ДАГОН! -${dmg.toLocaleString()}`, "#ef4444");
        triggerHaptic("heavy");
        return true;
      }
    },
    blink: {
      match: (it) => it && (it.name?.toLowerCase().includes("blink") || it.name?.toLowerCase().includes("скачка") || it.bonus?.blink),
      name: "Кинжал Скачка (Blink Dagger)",
      shortName: "Блинк",
      icon: "🗡️",
      cdFrames: 480, // 8s
      cdSec: 8,
      mpCost: 0,
      description: "Мгновенный скачок со станом врагов вокруг",
      execute: (p, stats) => {
        ARENA.specialEffects.push({
          type: "blink_poof",
          x: p.x,
          y: p.y,
          timer: 20
        });
        for (const c of ARENA.creeps) {
          if (Math.abs(c.x - (p.x + 80)) < 70) {
            c.state = "stagger";
            c.staggerTimer = 90;
            safeDamageCreep(c, Math.floor((stats.max_atk || 30) * 1.5), false);
          }
        }
        spawnFloatingText(p.x + 30, p.y - 35, "🗡️ БЛИНК!", "#38bdf8");
        triggerHaptic("medium");
        return true;
      }
    },
    bkb: {
      match: (it) => it && (it.name?.toLowerCase().includes("black king bar") || it.name?.toLowerCase().includes("королевский бар") || it.bonus?.magic_immune),
      name: "Черный Королевский Бар (BKB)",
      shortName: "БКБ",
      icon: "🟡",
      cdFrames: 1500, // 25s
      cdSec: 25,
      mpCost: 0,
      description: "Золотой Аватар: 6 секунд полной неуязвимости!",
      execute: (p) => {
        p.bkbActive = 360; // 6s
        spawnFloatingText(p.x + 30, p.y - 45, "🟡 БКБ! 100% НЕУЯЗВИМОСТЬ 6 СЕК! 👑", "#eab308");
        triggerHaptic("heavy");
        return true;
      }
    },
    satanic: {
      match: (it) => it && (it.name?.toLowerCase().includes("satanic") || it.name?.toLowerCase().includes("сатаник")),
      name: "Сатаник (Satanic)",
      shortName: "Сатаник",
      icon: "🩸",
      cdFrames: 1500, // 25s
      cdSec: 25,
      mpCost: 0,
      description: "Нечестивая Ярость: 100% вампиризм на 6 секунд",
      execute: (p) => {
        p.satanicActive = 360; // 6s
        spawnFloatingText(p.x + 30, p.y - 45, "🩸 САТАНИК! 100% ВАМПИРИЗМ! 🧛", "#dc2626");
        triggerHaptic("heavy");
        return true;
      }
    },
    eul: {
      match: (it) => it && (it.name?.toLowerCase().includes("eul") || it.name?.toLowerCase().includes("эул") || it.bonus?.tornado),
      name: "Скипетр Эула (Eul's Scepter)",
      shortName: "Эул",
      icon: "🌪️",
      cdFrames: 840, // 14s
      cdSec: 14,
      mpCost: 25,
      description: "Торнадо: неуязвимость на 2.5 секунды",
      execute: (p) => {
        p.eulActive = 150; // 2.5s
        spawnFloatingText(p.x + 30, p.y - 45, "🌪️ ЭУЛ! В ТОРНАДО! 💨", "#06b6d4");
        triggerHaptic("medium");
        return true;
      }
    },
    shiva: {
      match: (it) => it && (it.name?.toLowerCase().includes("shiva") || it.name?.toLowerCase().includes("шива")),
      name: "Шива (Shiva's Guard)",
      shortName: "Шива",
      icon: "❄️",
      cdFrames: 960, // 16s
      cdSec: 16,
      mpCost: 35,
      description: "Арктический взрыв: заморозка и урон по всей арене",
      execute: (p, stats) => {
        const dmg = Math.floor((stats.max_atk || 30) * 2.6 * (1 + (stats.spell_amp || 0) / 100));
        ARENA.specialEffects.push({
          type: "shiva_blast",
          x: p.x,
          y: p.y,
          radius: 20,
          maxRadius: 280,
          timer: 45
        });
        for (const c of ARENA.creeps) {
          safeDamageCreep(c, dmg, false);
          c.state = "stagger";
          c.staggerTimer = 180;
          spawnFloatingText(c.x, c.y - 25, `❄️ -${dmg}`, "#38bdf8");
        }
        spawnFloatingText(p.x + 30, p.y - 45, "❄️ ШИВА! АРКТИЧЕСКИЙ ВЗРЫВ!", "#38bdf8");
        triggerHaptic("heavy");
        return true;
      }
    },
    meteor: {
      match: (it) => it && (it.name?.toLowerCase().includes("meteor") || it.name?.toLowerCase().includes("метеор") || it.name?.toLowerCase().includes("fallen sky")),
      name: "Метеоритный Молот (Meteor Hammer)",
      shortName: "Метеор",
      icon: "☄️",
      cdFrames: 1080, // 18s
      cdSec: 18,
      mpCost: 45,
      description: "Призывает сокрушительный метеорит со станом",
      execute: (p, stats) => {
        const meteorDmg = Math.floor((stats.max_atk || 30) * 4.2 * (1 + (stats.spell_amp || 0) / 100));
        ARENA.playerProjectiles.push({
          type: "meteor",
          x: p.x + 15,
          y: -50,
          targetY: ARENA.roadY - 16,
          vx: 2.0,
          vy: 9.5,
          falling: true,
          speed: 5.2,
          radius: 38,
          angle: 0,
          dmg: meteorDmg,
          hitCreepIds: new Set(),
          burnTrail: []
        });
        spawnFloatingText(p.x + 30, p.y - 45, "☄️ ПАДЕНИЕ МЕТЕОРА!", "#ea580c");
        triggerHaptic("heavy");
        return true;
      }
    },
    ethereal: {
      match: (it) => it && (it.name?.toLowerCase().includes("ethereal") || it.name?.toLowerCase().includes("эфирн")),
      name: "Эфирный Клинок (Ethereal Blade)",
      shortName: "Эзернал",
      icon: "🪄",
      cdFrames: 840, // 14s
      cdSec: 14,
      mpCost: 35,
      description: "Астральный выстрел: урон от Интеллекта",
      execute: (p, stats) => {
        const target = ARENA.creeps[0] || ARENA.bossEntity;
        if (!target) return false;
        const totalInt = stats.total_intelligence || (stats.gear_int || 0) + (p.intelligence || 10);
        const dmg = Math.floor(totalInt * 2.8 * (1 + (stats.spell_amp || 0) / 100) + 200);
        safeDamageCreep(target, dmg, false);
        spawnFloatingText(target.x, target.y - 30, `🪄 ЭФИРНЫЙ ВЗРЫВ! -${dmg}`, "#22c55e");
        triggerHaptic("heavy");
        return true;
      }
    },
    manta: {
      match: (it) => it && (it.name?.toLowerCase().includes("manta") || it.name?.toLowerCase().includes("манта")),
      name: "Манта Стайл (Manta Style)",
      shortName: "Манта",
      icon: "👥",
      cdFrames: 1200, // 20s
      cdSec: 20,
      mpCost: 30,
      description: "Создает 2 иллюзии героя в бою на 7 секунд",
      execute: (p) => {
        p.mantaIllusionsTimer = 420; // 7 sec
        spawnFloatingText(p.x + 30, p.y - 45, "👥 МАНТА! ИЛЛЮЗИИ В БОЮ!", "#38bdf8");
        triggerHaptic("heavy");
        return true;
      }
    },
    abyssal: {
      match: (it) => it && (it.name?.toLowerCase().includes("abyssal") || it.name?.toLowerCase().includes("бездн") || it.bonus?.abyssal_stun),
      name: "Клинок Бездны (Abyssal Blade)",
      shortName: "Абиссал",
      icon: "🗡️",
      cdFrames: 720, // 12s
      cdSec: 12,
      mpCost: 35,
      description: "Оглушает цель на 2.5с сокрушительным ударом",
      execute: (p, stats) => {
        let target = ARENA.creeps[0] || ARENA.bossEntity;
        if (!target) return false;
        const stunDmg = Math.floor((stats.max_atk || 40) * 3.2);
        safeDamageCreep(target, stunDmg, false);
        target.state = "stagger";
        target.staggerTimer = 150;
        target.stateTimer = 150;
        ARENA.cameraTrauma = 0.8;
        ARENA.hitstop = 10;
        spawnFloatingText(target.x, target.y - 30, `⚡ АБИССАЛ СТАН! -${stunDmg}`, "#facc15");
        triggerHaptic("heavy");
        return true;
      }
    },
    hex: {
      match: (it) => it && (it.name?.toLowerCase().includes("hex") || it.name?.toLowerCase().includes("вайс") || it.name?.toLowerCase().includes("хекс") || it.bonus?.hex),
      name: "Хекс (Scythe of Vyse)",
      shortName: "Хекс",
      icon: "🐑",
      cdFrames: 900, // 15s
      cdSec: 15,
      mpCost: 50,
      description: "Превращает врага в безобидную свинку на 3.5 секунды",
      execute: (p) => {
        let target = ARENA.creeps[0] || ARENA.bossEntity;
        if (!target) return false;
        target.state = "stagger";
        target.staggerTimer = 210; // 3.5s
        target.stateTimer = 210;
        spawnFloatingText(target.x, target.y - 30, "🐑 ХЕКС! ПРЕВРАЩЕНИЕ В СВИНКУ!", "#a855f7");
        triggerHaptic("heavy");
        return true;
      }
    },
    bloodthorn: {
      match: (it) => it && (it.name?.toLowerCase().includes("bloodthorn") || it.name?.toLowerCase().includes("шип") || it.bonus?.bloodthorn_silence),
      name: "Кровавый Шип (Bloodthorn)",
      shortName: "Бладторн",
      icon: "🌹",
      cdFrames: 840, // 14s
      cdSec: 14,
      mpCost: 40,
      description: "Безмолвие цели + 100% критические удары на 4.5с",
      execute: (p) => {
        p.bloodthornActive = 270;
        spawnFloatingText(p.x + 30, p.y - 45, "🌹 БЛАДТОРН! 100% КРИТЫ! 🩸", "#ef4444");
        triggerHaptic("heavy");
        return true;
      }
    },
    gleipnir: {
      match: (it) => it && (it.name?.toLowerCase().includes("gleipnir") || it.name?.toLowerCase().includes("глейпнир") || it.bonus?.gleipnir_root),
      name: "Глейпнир (Gleipnir)",
      shortName: "Глейпнир",
      icon: "⛓️",
      cdFrames: 960, // 16s
      cdSec: 16,
      mpCost: 45,
      description: "Оцепенение всех врагов на арене на 2.5с + молнии",
      execute: (p, stats) => {
        const dmg = Math.floor((stats.max_atk || 30) * 2.2);
        for (const c of ARENA.creeps) {
          c.state = "stagger";
          c.staggerTimer = 150;
          safeDamageCreep(c, dmg, false);
          spawnFloatingText(c.x, c.y - 20, `⛓️ КОРНИ! -${dmg}`, "#38bdf8");
        }
        spawnFloatingText(p.x + 30, p.y - 45, "⛓️ ГЛЕЙПНИР! ВСЯ АРЕНА СКОВАНА!", "#38bdf8");
        triggerHaptic("heavy");
        return true;
      }
    },
    blademail: {
      match: (it) => it && (it.name?.toLowerCase().includes("blade mail") || it.name?.toLowerCase().includes("возврат") || it.name?.toLowerCase().includes("шипаст") || it.bonus?.active_blademail),
      name: "Возвратка (Blade Mail)",
      shortName: "БМ",
      icon: "🛡️",
      cdFrames: 720, // 12s
      cdSec: 12,
      mpCost: 20,
      description: "Возвращает 100% урона обратно всем атакующим на 4.5с",
      execute: (p) => {
        p.blademailActive = 270;
        spawnFloatingText(p.x + 30, p.y - 45, "🛡️ БЛЕЙДМЕЙЛ АКТИВИРОВАН! 🪞", "#facc15");
        triggerHaptic("heavy");
        return true;
      }
    },
    crimson: {
      match: (it) => it && (it.name?.toLowerCase().includes("crimson") || it.name?.toLowerCase().includes("багров") || it.bonus?.active_crimson),
      name: "Багровая Защита (Crimson Guard)",
      shortName: "Кримсон",
      icon: "🔴",
      cdFrames: 1200, // 20s
      cdSec: 20,
      mpCost: 35,
      description: "Купол защиты: блокирует 85 урона от каждого удара на 8с",
      execute: (p) => {
        p.crimsonActive = 480;
        p.crimsonBlock = 85;
        spawnFloatingText(p.x + 30, p.y - 45, "🔴 КРИМСОН ГВАРД! БРОНЕКУПОЛ!", "#dc2626");
        triggerHaptic("heavy");
        return true;
      }
    },
    pipe: {
      match: (it) => it && (it.name?.toLowerCase().includes("pipe") || it.name?.toLowerCase().includes("трубк") || it.bonus?.active_pipe),
      name: "Трубка Прозрения (Pipe of Insight)",
      shortName: "Пайп",
      icon: "📯",
      cdFrames: 1080, // 18s
      cdSec: 18,
      mpCost: 40,
      description: "Магический барьер на 650 урона от снарядов и заклинаний",
      execute: (p) => {
        p.pipeShield = 650;
        spawnFloatingText(p.x + 30, p.y - 45, "📯 ПАЙП! МАГИЧЕСКИЙ ЩИТ 650!", "#a855f7");
        triggerHaptic("heavy");
        return true;
      }
    },
    armlet: {
      match: (it) => it && (it.name?.toLowerCase().includes("armlet") || it.name?.toLowerCase().includes("арматур") || it.bonus?.unholy_strength),
      name: "Арматура (Armlet of Mordiggian)",
      shortName: "Армлет",
      icon: "🧤",
      cdFrames: 120, // 2s toggle
      cdSec: 2,
      mpCost: 0,
      description: "Нечестивая сила: +40 Сила, +65 Урон, +15 Броня",
      execute: (p) => {
        p.armletActive = !p.armletActive;
        if (p.armletActive) {
          spawnFloatingText(p.x + 30, p.y - 45, "😈 АРМЛЕТ ВКЛ! +СИЛА И УРОН!", "#ef4444");
        } else {
          spawnFloatingText(p.x + 30, p.y - 45, "💤 АРМЛЕТ ВЫКЛЮЧЕН", "#94a3b8");
        }
        triggerHaptic("medium");
        return true;
      }
    },
    hurricane: {
      match: (it) => it && (it.name?.toLowerCase().includes("hurricane") || it.name?.toLowerCase().includes("force staff") || it.name?.toLowerCase().includes("ураган") || it.bonus?.active_pike),
      name: "Пика Урагана (Hurricane Pike)",
      shortName: "Пика",
      icon: "🔱",
      cdFrames: 720, // 12s
      cdSec: 12,
      mpCost: 30,
      description: "Отталкивает врагов назад на 130px",
      execute: (p) => {
        for (const c of ARENA.creeps) {
          c.x += 130;
          c.state = "stagger";
          c.staggerTimer = 60;
        }
        spawnFloatingText(p.x + 30, p.y - 45, "💨 ПИКА! ОТТАЛКИВАНИЕ ВРАГОВ!", "#38bdf8");
        triggerHaptic("heavy");
        return true;
      }
    },
    silver_edge: {
      match: (it) => it && (it.name?.toLowerCase().includes("silver") || it.name?.toLowerCase().includes("серебрян") || it.name?.toLowerCase().includes("shadow blade") || it.bonus?.active_invis),
      name: "Серебряный Клинок (Silver Edge)",
      shortName: "Сильвер",
      icon: "🗡️",
      cdFrames: 840, // 14s
      cdSec: 14,
      mpCost: 35,
      description: "Уход в невидимость: следующий удар наносит 250% урона",
      execute: (p) => {
        p.shadowWalk = 300; // 5s
        spawnFloatingText(p.x + 30, p.y - 45, "👻 ТЕНЕВОЙ ШАГ! СЛЕДУЮЩИЙ УДАР 250%!", "#94a3b8");
        triggerHaptic("heavy");
        return true;
      }
    },
  };

  function getEquippedActiveItems() {
    const eq = RPG_STATE.profile?.equipment || {};
    const result = [];
    const seenKeys = new Set();
    for (const slot of ["relic", "weapon", "armor"]) {
      const it = eq[slot];
      if (!it) continue;
      for (const [key, def] of Object.entries(ACTIVE_ITEM_DEFINITIONS)) {
        if (!seenKeys.has(key) && def.match(it)) {
          seenKeys.add(key);
          result.push({ slot, key, item: it, def });
          break;
        }
      }
    }
    return result;
  }

  function useActiveItemAction(idx = 0) {
    const activeItems = getEquippedActiveItems();
    if (!activeItems || !activeItems[idx]) {
      spawnFloatingText(ARENA.player.x, ARENA.player.y - 25, "Нет активного предмета!", "#94a3b8");
      triggerHaptic("error");
      return;
    }

    const act = activeItems[idx];
    if (!ARENA.itemCooldowns) ARENA.itemCooldowns = {};

    const currentCd = ARENA.itemCooldowns[act.key] || 0;
    if (currentCd > 0) {
      const sec = Math.ceil(currentCd / 60);
      spawnFloatingText(ARENA.player.x, ARENA.player.y - 25, `${act.def.shortName}: КД ${sec}с`, "#94a3b8");
      triggerHaptic("error");
      return;
    }

    const p = ARENA.player;
    if (p.isFrozenInTime || (p.stunTimer && p.stunTimer > 0)) {
      spawnFloatingText(p.x, p.y - 25, "💫 ОГЛУШЕНИЕ!", "#facc15");
      triggerHaptic("error");
      return;
    }
    if (p.doomDebuffTimer && p.doomDebuffTimer > 0 && act.key !== "bkb") {
      spawnFloatingText(p.x, p.y - 25, "🔥 DOOM (ПРЕДМЕТЫ ЗАБЛОКИРОВАНЫ)!", "#dc2626");
      triggerHaptic("error");
      return;
    }

    const stats = RPG_STATE.profile?.stats || {};
    const cost = act.def.mpCost || 0;

    if (cost > 0 && p.currentMp < cost) {
      spawnFloatingText(p.x, p.y - 25, `Нужно ${cost} MP!`, "#94a3b8");
      triggerHaptic("error");
      return;
    }

    if (cost > 0) {
      p.currentMp -= cost;
    }

    const ok = act.def.execute(p, stats, act.item);
    if (ok !== false) {
      ARENA.itemCooldowns[act.key] = act.def.cdFrames;
      const cdEl = document.getElementById(`rpg-cd-item-${idx}`);
      if (cdEl) cdEl.textContent = `${act.def.cdSec}с`;
      const btnEl = document.getElementById(`rpg-btn-item-${idx}`);
      if (btnEl) btnEl.style.opacity = "0.6";
    }
  }

  function usePlayerPotion() {
    const p = ARENA.player;
    if (!p || p.isDead) return;

    if (ARENA.potionCooldown > 0) {
      triggerHaptic("light");
      return;
    }

    const stats = RPG_STATE.profile?.stats || {};
    const flatBonus = stats.flask_heal_flat || 0;
    const pctBonus = stats.flask_heal_pct || 0;
    const heal = Math.max(120, Math.floor(120 + flatBonus + (p.maxHp * pctBonus)));

    if (p.currentHp >= p.maxHp && (!stats.flask_mana || p.currentMp >= p.maxMp)) {
      spawnFloatingText(p.x, p.y - 25, "Здоровье полно!", "#94a3b8");
      return;
    }

    p.currentHp = Math.min(p.maxHp, p.currentHp + heal);
    spawnFloatingText(p.x, p.y - 25, `+${heal} HP 🧪`, "#22c55e");

    if (stats.flask_mana && stats.flask_mana > 0) {
      p.currentMp = Math.min(p.maxMp, p.currentMp + stats.flask_mana);
      spawnFloatingText(p.x, p.y - 42, `+${stats.flask_mana} MP 🔮`, "#38bdf8");
    }

    if (window.hasTalentPerk && window.hasTalentPerk("perk_divine_flask")) {
      p.stunTimer = 0;
      p.freezeTimer = 0;
      p.slowTimer = 0;
      p.speedBuffTimer = 180;
      spawnFloatingText(p.x, p.y - 58, "🌟 ОЧИЩЕНИЕ И УСКОРЕНИЕ!", "#facc15");
    }

    const cdReduct = stats.flask_cd_reduct || 0;
    ARENA.potionCooldown = Math.max(120, 360 - cdReduct);
    triggerHaptic("success");
  }

  // ---------------------------------------------------------------------------
  // WAVE PROGRESSION & DEATH HANDLING
  // ---------------------------------------------------------------------------

  function handleCreepDeath(c) {
    ARENA.pickups.push({
      type: "gold",
      x: c.x + (Math.random() * 12 - 6),
      y: c.y + (Math.random() * 12 - 6),
      value: c.isBoss ? 150 : (c.isMinion ? 3 : 10)
    });
    ARENA.pickups.push({
      type: "xp",
      x: c.x + (Math.random() * 12 - 6),
      y: c.y + (Math.random() * 12 - 6),
      value: c.isBoss ? 80 : (c.isMinion ? 2 : 4)
    });

    // Chest drops strictly from Bosses (Wave 10 mini-boss and Wave 20 floor boss)
    if (!c.isMinion && c.isBoss) {
      ARENA.pickups.push({
        type: "loot",
        x: c.x,
        y: c.y,
        value: 1
      });
    }

    if (c.isBoss) {
      handleBossDefeat();
      return;
    }

    if (!c.isMinion) {
      ARENA.creepsKilledInWave++;
      // SF PERK: Necromastery Soul Stacks (+3% dmg per soul, up to 15 stacks)
      if (window.hasTalentPerk && window.hasTalentPerk("perk_necromastery_stacks")) {
        ARENA.sfSouls = Math.min(15, (ARENA.sfSouls || 0) + 1);
        spawnFloatingText(ARENA.player.x, ARENA.player.y - 40, `👻 ДУША (${ARENA.sfSouls}/15)`, "#a855f7");
      }
      if (ARENA.creepsKilledInWave >= ARENA.creepsNeededForWave) {
        advanceArenaWave();
      }
    }
  }

  async function advanceArenaWave() {
    ARENA.waveState = "wave_clear";
    ARENA.waveTransitionTimer = ARENA.autoAdvanceWaves ? 45 : 70;
    spawnFloatingText(ARENA.width / 2, 90, `✅ ВОЛНА ${ARENA.waveNumber}/${ARENA.waveMax} ЗАЧИЩЕНА!`, "#22c55e");
    triggerHaptic("medium");

    // Sync accumulated wave, gold and XP to backend database immediately!
    try {
      const currentFloor = RPG_STATE.profile?.dungeon_floor || 1;
      const totalWaveCleared = (currentFloor - 1) * 20 + ARENA.waveNumber;
      const floorMult = 1.0 + (currentFloor - 1) * 0.10;
      const baseGold = Math.floor((10 + ARENA.waveNumber * 2) * floorMult);
      const baseXp = Math.floor((15 + ARENA.waveNumber * 3) * (1.0 + (currentFloor - 1) * 0.20));

      // DMC Style Meter Reward Multiplier (D..SSS)
      const rank = ARENA.styleMeter?.rank || "D";
      const styleMultipliers = { D: 1.0, C: 1.15, B: 1.30, A: 1.50, S: 1.70, SS: 1.95, SSS: 2.30 };
      const mult = styleMultipliers[rank] || 1.0;
      const goldGain = Math.floor(baseGold * mult);
      const xpGain = Math.floor(baseXp * mult);
      const bonusGold = goldGain - baseGold;

      if (bonusGold > 0) {
        spawnFloatingText(ARENA.width / 2, 115, `🔥 СТИЛЬ [${rank}]: +${bonusGold} 🪙 БОНУС!`, "#facc15");
      }

      const res = await api.slashCreepWave({
        wave_cleared: totalWaveCleared,
        earned_gold: goldGain,
        earned_xp: xpGain,
        style_rank: rank,
        combo_max: ARENA.combo?.maxCombo || 0
      });
      if (res.profile) {
        RPG_STATE.profile = res.profile;
      }
      if (res.leveled_up) {
        showLevelUpToast(res.profile?.level || 2);
      }
      if (res.chest_reward && (ARENA.waveNumber === 10 || ARENA.waveNumber === 20)) {
        openChestModal(res.chest_reward);
      }
    } catch (e) {
      console.warn("Wave sync warning:", e);
    }
  }

  function confirmNextWave() {
    if (ARENA.waveState !== "prompt") return;

    ARENA.waveNumber++;
    ARENA.creepsKilledInWave = 0;
    ARENA.totalCreepsSpawned = 0;
    ARENA.creeps = [];
    ARENA.pickups = [];
    ARENA.bossProjectiles = [];
    ARENA.playerProjectiles = [];

    // Boss on wave 20!
    if (ARENA.waveNumber === ARENA.waveMax) {
      // Wave 20: BOSS FIGHT! Switch to 2D Boss Arena Combat!
      ARENA.waveState = "boss_intro";
      ARENA.waveTransitionTimer = 120;
      ARENA.bossArenaMode = true;
      ARENA.moveInput = { left: false, right: false };
      ARENA.dodgeCooldown = 0;
      ARENA.dodgeActive = 0;
      ARENA.dangerZones = [];
      ARENA.bossPatternPhase = "idle";
      ARENA.bossPatternTimer = 0;
      spawnBossCreep();
      triggerHaptic("heavy");
    } else if (ARENA.waveNumber > ARENA.waveMax) {
      // Completed all 20 waves and killed the boss!
      handleFloorCleared();
    } else {
      ARENA.creepsNeededForWave = Math.min(32, 14 + Math.floor((ARENA.waveNumber - 1) * 1.0));
      ARENA.waveState = "fighting";
      triggerHaptic("medium");
    }
  }

  function retryCurrentFloor() {
    // Restart from wave 1 on death
    const stats = RPG_STATE.profile?.stats || {};
    ARENA.player.maxHp = Math.max(450, stats.hp_max || 450);
    ARENA.player.currentHp = ARENA.player.maxHp;
    ARENA.player.maxMp = Math.max(80, stats.mp_max || 80);
    ARENA.player.currentMp = ARENA.player.maxMp;
    ARENA.waveNumber = 1;
    ARENA.creepsKilledInWave = 0;
    ARENA.totalCreepsSpawned = 0;
    ARENA.creepsNeededForWave = 10;
    ARENA.creeps = [];
    ARENA.pickups = [];
    ARENA.bossProjectiles = [];
    ARENA.playerProjectiles = [];
    ARENA.alliedMinions = [];
    ARENA.specialEffects = [];
    ARENA.isBossActive = false;
    ARENA.topDownMode = false;
    ARENA.isRaidBossBattle = false;
    ARENA.bossEntity = null;
    ARENA.bossPhase = 0;
    ARENA.blockWindowActive = false;
    ARENA.qteActive = false;
    ARENA.bossArenaMode = false;
    ARENA.moveInput = { left: false, right: false };
    ARENA.dangerZones = [];
    ARENA.player.x = 65;
    ARENA.player.y = ARENA.roadY - 18;
    ARENA.player.isInvulnerable = 0;
    ARENA.player.isDead = false;
    ARENA.waveState = "fighting";

    // Re-render DOM to collapse canvas back to 320px and hide boss controls
    RPG_STATE._forceFullRender = true;
    renderRoot();
    RPG_STATE._forceFullRender = false;

    const canvas = document.getElementById("rpg-action-canvas");
    if (canvas) {
      bindArenaCanvas(canvas);
    }
    triggerHaptic("medium");
  }

  async function handleFloorCleared() {
    if (ARENA.player.currentHp <= 0 || ARENA.waveState === "retry_prompt") {
      return;
    }
    ARENA.waveState = "floor_clear";
    triggerHaptic("success");
    const currentFloor = RPG_STATE.profile?.dungeon_floor || 1;
    spawnFloatingText(ARENA.width / 2, 100, `👑 ЭТАЖ ${currentFloor} ЗАЧИЩЕН!`, "#22c55e");

    try {
      const totalFloorCleared = currentFloor * 20;
      const goldGain = Math.floor(250 + currentFloor * 80 + Math.min(1500, Math.pow(currentFloor, 1.25) * 12));
      const xpGain = Math.floor(200 + currentFloor * 60 + Math.pow(currentFloor, 1.15) * 10);
      const res = await api.slashCreepWave({
        wave_cleared: totalFloorCleared,
        earned_gold: goldGain,
        earned_xp: xpGain
      });
      if (res.profile) RPG_STATE.profile = res.profile;
      if (res.chest_reward) {
        RPG_STATE.lastBossChestReward = res.chest_reward;
        openChestModal(res.chest_reward);
      }
      if (res.leveled_up) showLevelUpToast(res.profile?.level || 2);
    } catch (e) {
      console.error("Failed to sync floor clear:", e);
    }

    setTimeout(() => {
      retryCurrentFloor();
      ARENA.waveNumber = 0;
      if (ARENA.autoAdvanceWaves && !RPG_STATE.activeChestModal) {
        ARENA.waveState = "prompt";
        confirmNextWave();
      } else {
        ARENA.waveState = "prompt";
      }
    }, 4500); // 4.5s to enjoy loot explosion & falling chest
  }

  async function handleRaidBossDefeat() {
    ARENA.waveState = "boss_victory";
    ARENA.hitstop = 15;
    ARENA.cameraTrauma = 1.0;
    triggerHaptic("success");
    const bossTmpl = ARENA.currentRaidBoss || { name: "Рейд-Босс", id: "golem", gold: 600, xp: 400 };
    spawnFloatingText(ARENA.width / 2, 80, `👑 ${bossTmpl.name} ПОВЕРЖЕН! 🏆`, "#eab308");

    spawnLootExplosion(ARENA.bossEntity?.x || ARENA.width * 0.7, ARENA.roadY - 20, bossTmpl);

    try {
      const res = await api.slashCreepWave({
        is_raid_boss: true,
        boss_id: bossTmpl.id,
        earned_gold: bossTmpl.gold || 600,
        earned_xp: bossTmpl.xp || 400
      });
      if (res.profile) RPG_STATE.profile = res.profile;
      if (res.chest_reward) {
        RPG_STATE.lastBossChestReward = res.chest_reward;
      }
      if (res.leveled_up) showLevelUpToast(res.profile?.level || 2);
    } catch (e) {
      console.warn("Could not sync raid boss defeat:", e);
    }
  }

  function handleBossDefeat() {
    if (ARENA.player.currentHp <= 0 || ARENA.waveState === "retry_prompt") {
      return;
    }
    ARENA.hitstop = 15;
    ARENA.cameraTrauma = 1.0;
    triggerHaptic("heavy");

    // Disable Boss Arena Mode — restore player position
    ARENA.bossArenaMode = false;
    ARENA.topDownMode = false;
    ARENA.moveInput = { left: false, right: false };
    ARENA.dangerZones = [];
    ARENA.player.x = 65; // Reset to default stationary position
    ARENA.player.y = ARENA.roadY - 18;
    ARENA.player.isInvulnerable = 0;

    if (ARENA.isRaidBossBattle) {
      handleRaidBossDefeat();
      return;
    }
    spawnLootExplosion(ARENA.bossEntity?.x || ARENA.width * 0.7, ARENA.roadY - 20, { name: "Босс этажа", gold: 350, xp: 250 });
    ARENA.isBossActive = false;
    ARENA.bossEntity = null;
    ARENA.bossPhase = 0;
    ARENA.blockWindowActive = false;
    ARENA.qteActive = false;
    ARENA.bossProjectiles = [];
    handleFloorCleared();
  }


  function exitRaidBossBattle() {
    ARENA.isRaidBossBattle = false;
    ARENA.topDownMode = false;
    ARENA.bossEntity = null;
    ARENA.isBossActive = false;
    ARENA.bossProjectiles = [];
    ARENA.creeps = [];
    ARENA.dangerZones = [];
    ARENA.waveState = "fighting";
    RPG_STATE.lastBossChestReward = null;

    // Reset farm wave state so farm is ready and creeps spawn properly
    const currentSavedWave = ((RPG_STATE.profile?.dungeon_cleared || 0) % 20) + 1;
    ARENA.waveNumber = currentSavedWave;
    ARENA.totalCreepsSpawned = 0;
    ARENA.creepsKilledInWave = 0;
    ARENA.creepsNeededForWave = Math.min(32, 14 + Math.floor((ARENA.waveNumber - 1) * 1.0));
    ARENA.creepSpawnTimer = 0;
    if (ARENA.player) {
      ARENA.player.x = 65;
      ARENA.player.y = ARENA.roadY - 18;
      ARENA.player.isInvulnerable = 0;
    }

    const returnTab = ARENA._originTab || "coop";
    ARENA._originTab = null;
    setSubTab(returnTab);
    if (returnTab === "farm") {
      if (typeof spawnArenaCreep === "function") spawnArenaCreep();
    }
  }

  function startRaidBossActionBattle(bossId) {
    stopCoopPolling();
    stopArenaLoop();
    if (ARENA.startLoopTimeout) {
      clearTimeout(ARENA.startLoopTimeout);
      ARENA.startLoopTimeout = null;
    }

    ARENA._originTab = (RPG_STATE.activeTab && RPG_STATE.activeTab !== "farm") ? RPG_STATE.activeTab : "coop";
    ARENA._wasRaidBossBattle = true;

    RPG_STATE.coopRoomId = null;
    RPG_STATE.coopRoomData = null;

    const bossTmpls = {
      golem: { id: "golem", name: "Древний Гранитный Голем", icon: "🗿", baseHp: 75000, baseAtk: 416, defense: 35, scale: 1.35, gold: 800, xp: 600, desc: "[75 ТЫС. ХП] Каменный колосс глубин" },
      lich: { id: "lich", name: "Архилич Некрополя", icon: "☠️", baseHp: 225000, baseAtk: 1250, defense: 50, scale: 1.30, gold: 1500, xp: 1200, desc: "[225 ТЫС. ХП] Владыка темных заклятий" },
      tormentor: { id: "tormentor", name: "Древний Терзатель (Tormentor)", icon: "🔮", baseHp: 700000, baseAtk: 3888, defense: 75, scale: 1.30, gold: 2800, xp: 2200, desc: "[700 ТЫС. ХП] Отражает 35% урона" },
      dragon: { id: "dragon", name: "Дракон Инферно", icon: "🌋", baseHp: 2200000, baseAtk: 12222, defense: 105, scale: 1.50, gold: 4500, xp: 3500, desc: "[2.2 МЛН ХП] Огнедышащий титан" },
      pudge_boss: { id: "pudge_boss", name: "Мясник из Чрева (Pudge)", icon: "🪝", baseHp: 7500000, baseAtk: 41666, defense: 140, scale: 1.40, gold: 7500, xp: 5500, desc: "[7.5 МЛН ХП] Хук цепью, вонь гнили и пожирание" },
      faceless_void: { id: "faceless_void", name: "Хроно-Владыка (Faceless Void)", icon: "⏳", baseHp: 25000000, baseAtk: 138888, defense: 180, scale: 1.35, gold: 12000, xp: 8500, desc: "[25 МЛН ХП] Остановка времени и баши" },
      roshan: { id: "roshan", name: "Рошан (Roshan)", icon: "🐲", baseHp: 85000000, baseAtk: 472222, defense: 230, scale: 1.45, gold: 18000, xp: 13000, desc: "[85 МЛН ХП] Хозяин Ямы, дропает Рапиру и Сыр" },
      tidehunter: { id: "tidehunter", name: "Левиафан Бездны (Tidehunter)", icon: "🐙", baseHp: 300000000, baseAtk: 1666666, defense: 290, scale: 1.40, gold: 25000, xp: 18000, desc: "[300 МЛН ХП] Владыка пучин с якорным ударом и Раважем" },
      sf_boss: { id: "sf_boss", name: "Архидемон Nevermore", icon: "💀", baseHp: 1000000000, baseAtk: 5555555, defense: 370, scale: 1.35, gold: 35000, xp: 25000, desc: "[1 МИЛЛИАРД ХП] Пожиратель душ с черными коилами и Реквиемом" },
      necrophos: { id: "necrophos", name: "Чумной Владыка (Necrophos)", icon: "🧟", baseHp: 3500000000, baseAtk: 19444444, defense: 460, scale: 1.30, gold: 48000, xp: 34000, desc: "[3.5 МЛРД ХП] Аура мора истощает HP, Коса Смерти рубит" },
      terrorblade: { id: "terrorblade", name: "Демон Бездны (Terrorblade)", icon: "😈", baseHp: 12000000000, baseAtk: 66666666, defense: 570, scale: 1.40, gold: 65000, xp: 45000, desc: "[12 МЛРД ХП] Метаморфоза Тьмы и разрыв души Sunder" },
      invoker_boss: { id: "invoker_boss", name: "Демиург Арсенала (Invoker)", icon: "🧙‍♂️", baseHp: 42000000000, baseAtk: 233333333, defense: 700, scale: 1.25, gold: 85000, xp: 60000, desc: "[42 МЛРД ХП] Повелитель стихий, хаос-метеоров и ЭМИ" },
      chaos_knight: { id: "chaos_knight", name: "Всадник Хаоса (Chaos Knight)", icon: "🐎", baseHp: 150000000000, baseAtk: 833333333, defense: 860, scale: 1.45, gold: 110000, xp: 78000, desc: "[150 МЛРД ХП] Фантомы параллельных миров и криты" },
      dark_tormentor: { id: "dark_tormentor", name: "Тёмный Терзатель Бездны", icon: "💎", baseHp: 550000000000, baseAtk: 3055555555, defense: 1050, scale: 1.40, gold: 140000, xp: 100000, desc: "[550 МЛРД ХП] Отражает 50% урона и стреляет шипами тьмы" },
      storm_spirit: { id: "storm_spirit", name: "Громовой Дух (Storm Spirit)", icon: "⚡", baseHp: 2000000000000, baseAtk: 11111111111, defense: 1300, scale: 1.35, gold: 180000, xp: 125000, desc: "[2 ТРИЛЛИОНА ХП] Молниеносные перелеты через арену и ремнанты" },
      doom: { id: "doom", name: "Вестник Апокалипсиса (Lord Doom)", icon: "👹", baseHp: 7500000000000, baseAtk: 41666666666, defense: 1600, scale: 1.45, gold: 230000, xp: 160000, desc: "[7.5 ТРИЛЛИОНОВ ХП] Владыка Преисподней с роком и пламенем" },
      primal_beast: { id: "primal_beast", name: "Первобытный Титан (Primal Beast)", icon: "🦣", baseHp: 28000000000000, baseAtk: 155555555555, defense: 1950, scale: 1.60, gold: 290000, xp: 200000, desc: "[28 ТРИЛЛИОНОВ ХП] Сокрушитель материков с диким топотом" },
      phantom_roshan: { id: "phantom_roshan", name: "Призрачный Рошан Хаоса", icon: "👻", baseHp: 100000000000000, baseAtk: 555555555555, defense: 2400, scale: 1.55, gold: 360000, xp: 250000, desc: "[100 ТРИЛЛИОНОВ ХП] Восставший призрак Рошана с астральным Slam" },
      tinker_boss: { id: "tinker_boss", name: "Архиинженер (Omega Tinker)", icon: "🤖", baseHp: 350000000000000, baseAtk: 1944444444444, defense: 3000, scale: 1.45, gold: 450000, xp: 320000, desc: "[350 ТРИЛЛИОНОВ ХП] Ослепляющий лазер, микроракеты и марш роботов" },
      enigma: { id: "enigma", name: "Пожиратель Миров (Enigma Cosmic)", icon: "🌌", baseHp: 1200000000000000, baseAtk: 6666666666666, defense: 3800, scale: 1.35, gold: 600000, xp: 420000, desc: "[1.2 КВАДРИЛЛИОНА ХП!] Битва на века! Схлопывает пространство в Черную Дыру" }
    };

    const b = bossTmpls[bossId] || bossTmpls.golem;
    RPG_STATE.activeTab = "farm";
    RPG_STATE.farmMode = "arena";
    ARENA.isRaidBossBattle = true;
    ARENA.topDownMode = true;
    ARENA.currentRaidBoss = b;

    const stats = RPG_STATE.profile?.stats || {};
    const playerAtk = Math.max(30, Math.floor(((stats.min_atk || 30) + (stats.max_atk || 50)) / 2));
    const playerHp = Math.max(400, stats.hp_max || 400);

    const finalHp = b.baseHp;

    // 1. CREATE BOSS ENTITY (Slow, heavy, deliberate boss pacing)
    const raidBoss = {
      id: `raid_${b.id}_${Date.now()}`,
      name: b.name,
      icon: b.icon,
      x: 180,
      y: 95,
      radius: Math.floor(30 * (b.scale || 1.15)),
      speed: 1.45, // Fast, aggressive boss movement
      hp: finalHp,
      maxHp: finalHp,
      atk: b.baseAtk || 140,
      defense: b.defense !== undefined ? b.defense : 35,
      isBoss: true,
      isRaidBoss: true,
      bossType: b.id,
      isMinion: false,
      shielded: false,
      attackCooldown: 0,
      poise: 1600,
      maxPoise: 1600,
      state: "chase",
      stateTimer: 0,
      meleeCooldown: 40, // 0.65s initial wait
      chargeCooldown: 120, // 2s initial wait before first charge
      barrageCooldown: 80, // 1.3s initial wait before first barrage
      chargeAngle: 0,
      chargeVx: 0,
      chargeVy: 0,
      facing: 1,
      enrageTimer: 0,
      battleStartTime: Date.now(),
      enrageStage: "normal",
      jumpY: 0,
      jumpVY: 0
    };

    ARENA.bossEntity = raidBoss;
    ARENA.isBossActive = true;
    ARENA.bossPhase = 1;
    ARENA.creeps = [raidBoss]; // ONLY THE BOSS! NO CREEPS!
    ARENA.waveNumber = 20;
    ARENA.totalCreepsSpawned = 999;
    ARENA.creepsNeededForWave = 1;
    ARENA.creepsKilledInWave = 0;

    ARENA.playerProjectiles = [];
    ARENA.bossProjectiles = [];
    ARENA.dangerZones = [];
    ARENA.specialEffects = [];
    ARENA.floatingTexts = [];
    ARENA.dashGhosts = [];
    ARENA.waveState = "fighting";
    ARENA.bossArenaMode = true;
    ARENA.moveInput = { left: false, right: false };
    ARENA.dodgeCooldown = 0;
    ARENA.dodgeActive = 0;

    syncArenaPlayerStats();
    ARENA.player.currentHp = ARENA.player.maxHp;
    ARENA.player.currentMp = ARENA.player.maxMp;
    ARENA.player.isMoving = false;
    ARENA.player.isInvulnerable = 0;
    ARENA.player.isDead = false;
    ARENA.player.shootCooldown = 0;
    ARENA.player.facingAngle = -Math.PI / 2;
    ARENA.player.facing = 1;
    // 520 x 720 Spacious Arena Spawns
    ARENA.width = 520;
    ARENA.height = 720;
    ARENA.player.x = 260;
    ARENA.player.y = 620;
    ARENA.player.radius = 14;

    raidBoss.x = 260;
    raidBoss.y = 140;
    raidBoss.radius = 32;

    if ((ARENA.bossPartyMode || "trio") === "trio") {
      initBossCompanions();
      if (ARENA.bossCompanions[0]) {
        ARENA.bossCompanions[0].x = 220;
        ARENA.bossCompanions[0].y = 636;
        ARENA.bossCompanions[0].radius = 13;
      }
      if (ARENA.bossCompanions[1]) {
        ARENA.bossCompanions[1].x = 300;
        ARENA.bossCompanions[1].y = 636;
        ARENA.bossCompanions[1].radius = 13;
      }
    }

    // 2. Force full render of the DOM to show the Boss Fight header!
    RPG_STATE._forceFullRender = true;
    renderRoot();
    RPG_STATE._forceFullRender = false;

    const canvas = document.getElementById("rpg-action-canvas");
    if (canvas) {
      bindArenaCanvas(canvas);
      ARENA.width = 520;
      ARENA.height = 720;
      raidBoss.x = 260;
      raidBoss.y = 140;
      ARENA.player.x = 260;
      ARENA.player.y = 620;
    }

    // 3. Start unified, authoritative arena loop
    startArenaLoop();

    spawnFloatingText(ARENA.width / 2, 75, `👑 БОЙ С БОССОМ: ${b.name}! 👑`, "#ef4444");
    triggerHaptic("heavy");
  }

  function handlePlayerArenaDeath() {
    // AEGIS OF THE IMMORTAL RESURRECTION PASSIVE
    const relic = RPG_STATE.profile?.equipment?.relic;
    const isAegis = relic && (String(relic.name || "").toLowerCase().includes("aegis") || String(relic.name || "").toLowerCase().includes("эгида") || relic.icon === "🛡️" || relic.icon === "🥚");
    if (isAegis && !ARENA.aegisUsed && ARENA.player) {
      ARENA.aegisUsed = true;
      const pMax = ARENA.player.maxHp || 500;
      ARENA.player.currentHp = Math.floor(pMax * 0.65);
      ARENA.player.isInvulnerable = 60;
      spawnFloatingText(ARENA.player.x, ARENA.player.y - 35, "✨ ВОСКРЕШЕНИЕ ЭГИДОЙ! (+65% HP)", "#facc15");
      triggerHaptic("heavy");
      return;
    }

    // WRAITH KING PERK: Reincarnation (Revives with 75% HP + 50% slow on enemies)
    if (window.hasTalentPerk && window.hasTalentPerk("perk_reincarnation") && !ARENA.wkReincarnationUsed && ARENA.player) {
      ARENA.wkReincarnationUsed = true;
      const pMax = ARENA.player.maxHp || 500;
      ARENA.player.currentHp = Math.floor(pMax * 0.75);
      ARENA.player.isInvulnerable = 90;
      ARENA.player.isDead = false;
      spawnFloatingText(ARENA.player.x, ARENA.player.y - 35, "👑 ПЕРЕРОЖДЕНИЕ КОРОЛЯ! (+75% HP)", "#22c55e");
      triggerHaptic("heavy");
      if (ARENA.creeps) {
        ARENA.creeps.forEach(c => {
          c.slowTimer = 240;
          c.speed = Math.max(0.4, (c.baseSpeed || c.speed || 1.5) * 0.5);
        });
      }
      return;
    }

    // PUDGE PERK: Undying Meat (Survives with 35% HP + 2s invuln + poison explosion)
    if (window.hasTalentPerk && window.hasTalentPerk("perk_undying_meat") && !ARENA.pudgeUndyingUsed && ARENA.player) {
      ARENA.pudgeUndyingUsed = true;
      const pMax = ARENA.player.maxHp || 500;
      ARENA.player.currentHp = Math.floor(pMax * 0.35);
      ARENA.player.isInvulnerable = 120;
      ARENA.player.isDead = false;
      spawnFloatingText(ARENA.player.x, ARENA.player.y - 35, "🥩 БЕССМЕРТНАЯ ТУША! (ВЗРЫВ ЯДА)", "#84cc16");
      triggerHaptic("heavy");
      const poisonBurst = Math.max(50, Math.floor((RPG_STATE.profile?.stats?.attack || 50) * 3));
      if (ARENA.isBossActive && ARENA.bossEntity && ARENA.bossEntity.hp > 0) {
        applyDamageToBoss(ARENA.bossEntity, poisonBurst, true);
        spawnFloatingText(ARENA.bossEntity.x, ARENA.bossEntity.y - 25, `☣️ ВЗРЫВ ЯДА -${poisonBurst}!`, "#84cc16");
      }
      if (ARENA.creeps) {
        ARENA.creeps.forEach(c => {
          if (c.hp > 0) {
            safeDamageCreep(c, poisonBurst);
            spawnFloatingText(c.x, c.y - 20, `☣️ -${poisonBurst}`, "#84cc16");
          }
        });
      }
      return;
    }

    if (ARENA.player) {
      ARENA.player.currentHp = 0;
      ARENA.player.isInvulnerable = 0;
      ARENA.player.isDead = true;
    }

    if (ARENA.isRaidBossBattle) {
      ARENA.waveState = "boss_defeat";
      triggerHaptic("error");
      spawnFloatingText(ARENA.width / 2, 95, "💀 ВАШ ГЕРОЙ ПАЛ В РЕЙДЕ!", "#ef4444");
      ARENA.playerProjectiles = [];
      ARENA.bossProjectiles = [];
      if (ARENA.bossEntity) {
        ARENA.bossEntity.state = "idle";
        ARENA.bossEntity.stateTimer = 999999;
      }
      return;
    }

    ARENA.waveState = "retry_prompt"; // NEVER floor_clear!
    triggerHaptic("error");
    spawnFloatingText(ARENA.width / 2, 100, "💀 ВАШ ГЕРОЙ ПАЛ!", "#ef4444");

    setTimeout(() => {
      const stats = RPG_STATE.profile?.stats || {};
      ARENA.player.maxHp = Math.max(450, stats.hp_max || 450);
      ARENA.player.currentHp = ARENA.player.maxHp;
      ARENA.player.isDead = false;
      ARENA.player.maxMp = Math.max(80, stats.mp_max || 80);
      ARENA.player.currentMp = ARENA.player.maxMp;
      ARENA.creeps = [];
      ARENA.pickups = [];
      ARENA.bossProjectiles = [];
      ARENA.playerProjectiles = [];
      ARENA.alliedMinions = [];
      ARENA.specialEffects = [];
      ARENA.isBossActive = false;
      ARENA.topDownMode = false;
      ARENA.bossArenaMode = false;
      ARENA.bossEntity = null;
      ARENA.bossPhase = 0;
      ARENA.blockWindowActive = false;
      ARENA.qteActive = false;
      ARENA.creepsKilledInWave = 0;
      ARENA.totalCreepsSpawned = 0;
      ARENA.waveNumber = 1;
      ARENA.player.x = 65;
      ARENA.player.y = ARENA.roadY - 18;
      ARENA.waveState = "retry_prompt";
    }, 1200);
  }

  function checkLevelUpInArena() {
    const p = RPG_STATE.profile;
    if (!p) return;
    const needed = 120 + ((p.level || 1) - 1) * 160;
    if (p.xp >= needed) {
      p.xp -= needed;
      p.level = (p.level || 1) + 1;
      p.stat_points = (p.stat_points || 0) + 1;
      if (p.level % 5 === 0) p.talent_points = (p.talent_points || 0) + 1;
      showLevelUpToast(p.level);
      spawnFloatingText(ARENA.player.x + 30, ARENA.player.y - 45, `🎉 УРОВЕНЬ ${p.level}! (+1 очко)`, "#facc15");
    }
  }

  function spawnFloatingText(x, y, text, color = "#ffffff") {
    if (!ARENA.floatingTexts) ARENA.floatingTexts = [];
    if (ARENA.floatingTexts.length >= 24) {
      ARENA.floatingTexts.shift(); // Drop oldest text to avoid canvas lag
    }
    ARENA.floatingTexts.push({ x, y, text, color, opacity: 1.0 });
  }

// ============================================================================
// 06_boss_models_early.js — Procedural Vector Models for Bosses 1–6
// (Golem, Lich, Tormentor, Dragon, Pudge, Faceless Void)
// ============================================================================

function drawBossModelEarly(ctx, b, bId, time) {
  const facing = b.facing || 1;
  let assetName = null;
  if (bId.includes("faceless") || bId.includes("войд")) assetName = "faceless_void";

  if (assetName && typeof RPG_ASSETS !== "undefined" && RPG_ASSETS.bosses[assetName]) {
    const bossAsset = RPG_ASSETS.bosses[assetName];
    if (bossAsset && bossAsset.complete && bossAsset.naturalWidth > 0) {
      ctx.save();
      if (facing === -1) {
        ctx.scale(-1, 1);
      }
      const size = b.radius * 6.0;
      ctx.drawImage(bossAsset, -size / 2, -size / 1.1, size, size);
      ctx.restore();
      return true;
    }
  }

  // 1. GOLEM (Древний Гранитный Голем)
  if (bId.includes("golem") || bId.includes("голем")) {
    ctx.save();
    // Massive rocky torso
    ctx.fillStyle = "#44403c";
    ctx.strokeStyle = "#78716c";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.roundRect(-24, -28, 48, 44, 8);
    ctx.fill();
    ctx.stroke();

    // Magma / Moss Glowing Cracks
    ctx.strokeStyle = "#f97316";
    ctx.lineWidth = 2;
    ctx.shadowColor = "#ea580c";
    ctx.shadowBlur = 8;
    ctx.beginPath();
    ctx.moveTo(-16, -18); ctx.lineTo(-4, -6); ctx.lineTo(12, -14);
    ctx.moveTo(-8, 2); ctx.lineTo(6, 12);
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Heavy Stone Fists
    ctx.fillStyle = "#292524";
    ctx.strokeStyle = "#a8a29e";
    ctx.lineWidth = 2.5;
    const fOff = Math.sin(time * 0.15) * 4;
    ctx.beginPath();
    ctx.arc(-28 * facing, 2 + fOff, 13, 0, Math.PI * 2);
    ctx.arc(28 * facing, -2 - fOff, 13, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Glowing Amber Golem Eye Ridge
    ctx.fillStyle = "#fbbf24";
    ctx.shadowColor = "#f59e0b";
    ctx.shadowBlur = 10;
    ctx.fillRect(-10 * facing, -22, 14 * facing, 4);
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  // 2. LICH (Архилич Некрополя)
  if (bId.includes("lich") || bId.includes("лич")) {
    const floatBob = Math.sin(time * 0.12) * 4;
    ctx.save();
    ctx.translate(0, floatBob);

    // Dark Frost Robes
    ctx.fillStyle = "#0f172a";
    ctx.strokeStyle = "#0284c7";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.moveTo(0, -26);
    ctx.lineTo(18, 20); ctx.lineTo(10, 24); ctx.lineTo(0, 19); ctx.lineTo(-10, 24); ctx.lineTo(-18, 20);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // Skeletal Skull Face
    ctx.fillStyle = "#e2e8f0";
    ctx.beginPath();
    ctx.arc(0, -22, 10, 0, Math.PI * 2);
    ctx.fill();

    // Golden Lich Crown with Ice Jewels
    ctx.fillStyle = "#facc15";
    ctx.beginPath();
    ctx.moveTo(-9, -28); ctx.lineTo(-5, -36); ctx.lineTo(0, -29); ctx.lineTo(5, -36); ctx.lineTo(9, -28);
    ctx.closePath();
    ctx.fill();

    // Glowing Cyan Frost Eyes
    ctx.fillStyle = "#38bdf8";
    ctx.shadowColor = "#38bdf8";
    ctx.shadowBlur = 10;
    ctx.fillRect(-5, -23, 3, 2.5);
    ctx.fillRect(2, -23, 3, 2.5);

    // Orbiting Frost Phylactery Spheres
    for (let s = 0; s < 3; s++) {
      const oAng = time * 0.08 + s * 2.09;
      const ox = Math.cos(oAng) * 26;
      const oy = Math.sin(oAng) * 14 - 10;
      ctx.fillStyle = "#0284c7";
      ctx.shadowColor = "#38bdf8";
      ctx.shadowBlur = 12;
      ctx.beginPath();
      ctx.arc(ox, oy, 5, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  // 3. TORMENTOR (Древний Терзатель)
  if (bId.includes("tormentor") && !bId.includes("dark_tormentor")) {
    const rot = time * 0.035;
    ctx.save();
    ctx.rotate(rot);
    ctx.fillStyle = "#581c87";
    ctx.strokeStyle = "#e879f9";
    ctx.lineWidth = 3;
    ctx.shadowColor = "#c084fc";
    ctx.shadowBlur = 16;
    ctx.beginPath();
    ctx.moveTo(0, -28); ctx.lineTo(24, 0); ctx.lineTo(0, 28); ctx.lineTo(-24, 0);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // Inner Glowing Core
    ctx.fillStyle = "#f5d0fe";
    ctx.beginPath();
    ctx.moveTo(0, -14); ctx.lineTo(13, 0); ctx.lineTo(0, 14); ctx.lineTo(-13, 0);
    ctx.closePath();
    ctx.fill();
    ctx.restore();

    // 4 Orbiting Shard Needles
    for (let s = 0; s < 4; s++) {
      const sAng = -rot * 1.8 + s * 1.57;
      const sx = Math.cos(sAng) * 36;
      const sy = Math.sin(sAng) * 22;
      ctx.fillStyle = "#d8b4fe";
      ctx.beginPath();
      ctx.moveTo(sx, sy - 7); ctx.lineTo(sx + 5, sy); ctx.lineTo(sx, sy + 7); ctx.lineTo(sx - 5, sy);
      ctx.closePath();
      ctx.fill();
    }
    return true;
  }

  // 4. DRAGON (Дракон Инферно)
  if (bId.includes("dragon") || bId.includes("дракон")) {
    const wingFlap = Math.sin(time * 0.2) * 12;
    ctx.save();
    // Huge Draconic Wings
    ctx.fillStyle = "#7f1d1d";
    ctx.strokeStyle = "#ef4444";
    ctx.lineWidth = 2.5;
    // Left wing
    ctx.beginPath();
    ctx.moveTo(-10, -8);
    ctx.quadraticCurveTo(-38, -32 + wingFlap, -48, -4 + wingFlap);
    ctx.lineTo(-24, 8);
    ctx.closePath();
    ctx.fill(); ctx.stroke();
    // Right wing
    ctx.beginPath();
    ctx.moveTo(10, -8);
    ctx.quadraticCurveTo(38, -32 - wingFlap, 48, -4 - wingFlap);
    ctx.lineTo(24, 8);
    ctx.closePath();
    ctx.fill(); ctx.stroke();

    // Armored Scaled Body
    ctx.fillStyle = "#991b1b";
    ctx.strokeStyle = "#f87171";
    ctx.beginPath();
    ctx.ellipse(0, 4, 18, 22, 0, 0, Math.PI * 2);
    ctx.fill(); ctx.stroke();

    // Horned Dragon Head
    ctx.fillStyle = "#b91c1c";
    ctx.beginPath();
    ctx.moveTo(-10 * facing, -16);
    ctx.lineTo(16 * facing, -24);
    ctx.lineTo(10 * facing, -8);
    ctx.closePath();
    ctx.fill();
    // Swept-back Horns
    ctx.strokeStyle = "#facc15";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(-6 * facing, -22); ctx.quadraticCurveTo(-18 * facing, -34, -26 * facing, -30);
    ctx.stroke();

    // Glowing Lava Breath Throat
    ctx.fillStyle = "#fbbf24";
    ctx.shadowColor = "#f97316"; ctx.shadowBlur = 12;
    ctx.beginPath();
    ctx.arc(12 * facing, -16, 4.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  // 5. PUDGE (Мясник из Чрева)
  if (bId.includes("pudge") || bId.includes("мясник")) {
    ctx.save();
    // Rotund Stitched Abomination Body
    ctx.fillStyle = "#57534e";
    ctx.strokeStyle = "#1c1917";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.ellipse(0, 4, 25, 26, 0, 0, Math.PI * 2);
    ctx.fill(); ctx.stroke();

    // Stitched Grotesque Flesh Seams
    ctx.strokeStyle = "#a8a29e";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(-12, -10); ctx.lineTo(-4, 14);
    ctx.moveTo(8, -6); ctx.lineTo(14, 16);
    ctx.stroke();

    // Bloody Butcher Apron
    ctx.fillStyle = "#7f1d1d";
    ctx.beginPath();
    ctx.moveTo(-14, -8); ctx.lineTo(14, -8); ctx.lineTo(10, 20); ctx.lineTo(-10, 20);
    ctx.closePath();
    ctx.fill();

    // Right Hand: Heavy Butcher Cleaver
    ctx.fillStyle = "#e2e8f0";
    ctx.strokeStyle = "#991b1b";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.rect(20 * facing, -12, 10 * facing, 22);
    ctx.fill(); ctx.stroke();

    // Left Hand: Rusted Chain Meat Hook
    ctx.strokeStyle = "#78716c";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(-22 * facing, 2);
    ctx.lineTo(-32 * facing, -4);
    ctx.arc(-32 * facing, 4, 8, -Math.PI / 2, Math.PI / 2);
    ctx.stroke();

    // Monstrous Jaws & Glowing Bile Eyes
    ctx.fillStyle = "#dc2626";
    ctx.fillRect(-8 * facing, -20, 5 * facing, 5);
    ctx.fillStyle = "#84cc16";
    ctx.shadowColor = "#84cc16"; ctx.shadowBlur = 8;
    ctx.fillRect(-10 * facing, -26, 4 * facing, 3);
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  // 6. FACELESS VOID (Хроно-Владыка)
  if (bId.includes("faceless_void") || bId.includes("хроно")) {
    ctx.save();
    // Time-Warped Violet Humanoid Body
    ctx.fillStyle = "#581c87";
    ctx.strokeStyle = "#a855f7";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.roundRect(-14, -18, 28, 36, 6);
    ctx.fill(); ctx.stroke();

    // Smooth Horned Alien Head (No Face!)
    ctx.fillStyle = "#3b0764";
    ctx.beginPath();
    ctx.moveTo(-12, -22); ctx.quadraticCurveTo(0, -42, 12, -22);
    ctx.closePath();
    ctx.fill(); ctx.stroke();

    // Curved Head Ridge / Horn
    ctx.strokeStyle = "#c084fc";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(0, -36); ctx.quadraticCurveTo(8 * facing, -48, 14 * facing, -44);
    ctx.stroke();

    // Glowing Mace of Aeons (Timelock Hammer)
    const maceBob = Math.sin(time * 0.18) * 3;
    ctx.fillStyle = "#c084fc";
    ctx.strokeStyle = "#f3e8ff";
    ctx.lineWidth = 2;
    ctx.shadowColor = "#a855f7"; ctx.shadowBlur = 12;
    ctx.beginPath();
    ctx.roundRect(16 * facing, -16 + maceBob, 12, 14, 4);
    ctx.fill(); ctx.stroke();
    ctx.shadowBlur = 0;

    // Mace Handle
    ctx.strokeStyle = "#94a3b8";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.moveTo(22 * facing, 0 + maceBob); ctx.lineTo(22 * facing, 18 + maceBob);
    ctx.stroke();
    ctx.restore();
    return true;
  }

  return false;
}

// ============================================================================
// 06_boss_models_late.js — Procedural Vector Models for Bosses 14–20
// (Dark Tormentor, Storm Spirit, Doom, Primal Beast, Phantom Roshan, Tinker, Enigma)
// ============================================================================

function drawBossModelLate(ctx, b, bId, time) {
  const facing = b.facing || 1;

  // 14. DARK TORMENTOR (Тёмный Терзатель Бездны)
  if (bId.includes("dark_tormentor") || bId.includes("тёмный терзатель")) {
    const rot = time * 0.04;
    ctx.save();
    ctx.rotate(-rot);
    ctx.fillStyle = "#1e1b4b";
    ctx.strokeStyle = "#c084fc";
    ctx.lineWidth = 3.5;
    ctx.shadowColor = "#7c3aed"; ctx.shadowBlur = 18;
    ctx.beginPath();
    ctx.moveTo(0, -32); ctx.lineTo(26, 0); ctx.lineTo(0, 32); ctx.lineTo(-26, 0);
    ctx.closePath();
    ctx.fill(); ctx.stroke();
    // Inner Singularity Eye
    ctx.fillStyle = "#a855f7";
    ctx.beginPath();
    ctx.arc(0, 0, 10, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    // 6 Orbiting Void Needles
    for (let s = 0; s < 6; s++) {
      const sAng = rot * 2.2 + s * (Math.PI / 3);
      const sx = Math.cos(sAng) * 40;
      const sy = Math.sin(sAng) * 24;
      ctx.fillStyle = "#e9d5ff";
      ctx.fillRect(sx - 3, sy - 3, 6, 6);
    }
    return true;
  }

  // 15. STORM SPIRIT (Громовой Дух)
  if (bId.includes("storm_spirit") || bId.includes("громовой дух")) {
    const sBob = Math.sin(time * 0.22) * 4;
    ctx.save();
    ctx.translate(0, sBob);
    // Jovial Electric Djinn Body
    ctx.fillStyle = "#0284c7";
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 3;
    ctx.shadowColor = "#38bdf8"; ctx.shadowBlur = 14;
    ctx.beginPath();
    ctx.ellipse(0, 2, 22, 24, 0, 0, Math.PI * 2);
    ctx.fill(); ctx.stroke();

    // Silken Vest
    ctx.fillStyle = "#dc2626";
    ctx.beginPath();
    ctx.moveTo(-10, -12); ctx.lineTo(10, -12); ctx.lineTo(6, 14); ctx.lineTo(-6, 14);
    ctx.closePath();
    ctx.fill();

    // Whimsical Topknot / Mustache & Crackling Eyes
    ctx.fillStyle = "#0369a1";
    ctx.beginPath();
    ctx.arc(0, -20, 9, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#facc15";
    ctx.fillRect(-5 * facing, -21, 3 * facing, 2.5);
    ctx.fillRect(2 * facing, -21, 3 * facing, 2.5);

    // Electric Sparks Trailing
    ctx.strokeStyle = "#facc15";
    ctx.lineWidth = 2;
    for (let sp = 0; sp < 4; sp++) {
      const spAng = time * 0.2 + sp * 1.57;
      const spx = Math.cos(spAng) * 26;
      const spy = Math.sin(spAng) * 18;
      ctx.beginPath();
      ctx.moveTo(spx, spy); ctx.lineTo(spx + 6, spy - 6); ctx.lineTo(spx + 2, spy - 10);
      ctx.stroke();
    }
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  // 16. DOOM (Вестник Апокалипсиса / Lord Doom)
  if (bId.includes("doom") || bId.includes("вестник")) {
    ctx.save();
    // Massive Crimson Demon Torso
    ctx.fillStyle = "#7f1d1d";
    ctx.strokeStyle = "#ef4444";
    ctx.lineWidth = 3.5;
    ctx.beginPath();
    ctx.roundRect(-18, -22, 36, 42, 6);
    ctx.fill(); ctx.stroke();

    // Leathery Demonic Wings
    ctx.fillStyle = "#450a0a";
    ctx.beginPath();
    ctx.moveTo(-16 * facing, -12); ctx.lineTo(-44 * facing, -38); ctx.lineTo(-30 * facing, 8);
    ctx.moveTo(16 * facing, -12); ctx.lineTo(44 * facing, -38); ctx.lineTo(30 * facing, 8);
    ctx.fill();

    // Curved Horned Helm & Flaming Eyes
    ctx.fillStyle = "#18181b";
    ctx.beginPath();
    ctx.moveTo(-10 * facing, -22); ctx.lineTo(10 * facing, -22); ctx.lineTo(0, -38);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = "#f59e0b";
    ctx.lineWidth = 3;
    ctx.stroke();

    // Giant Flaming Sword of Doom
    const swBob = Math.sin(time * 0.18) * 3;
    ctx.fillStyle = "#fbbf24";
    ctx.strokeStyle = "#dc2626";
    ctx.lineWidth = 2.5;
    ctx.shadowColor = "#f97316"; ctx.shadowBlur = 14;
    ctx.beginPath();
    ctx.rect(22 * facing, -34 + swBob, 6, 44);
    ctx.fill(); ctx.stroke();
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  // 17. PRIMAL BEAST (Первобытный Титан)
  if (bId.includes("primal_beast") || bId.includes("первобытный")) {
    ctx.save();
    // Colossal Quad-Legged Beast Body
    ctx.fillStyle = "#78350f";
    ctx.strokeStyle = "#d97706";
    ctx.lineWidth = 3.5;
    ctx.beginPath();
    ctx.ellipse(0, 4, 32, 25, 0, 0, Math.PI * 2);
    ctx.fill(); ctx.stroke();

    // Stone Carapace Plates
    ctx.fillStyle = "#451a03";
    for (let p = -2; p <= 2; p++) {
      ctx.fillRect(p * 10 - 4, -14, 8, 10);
    }

    // Heavy Horned Battering Snout
    ctx.fillStyle = "#92400e";
    ctx.beginPath();
    ctx.moveTo(16 * facing, -8); ctx.lineTo(34 * facing, 4); ctx.lineTo(18 * facing, 16);
    ctx.closePath();
    ctx.fill();

    // Massive Curved Forward Horns
    ctx.strokeStyle = "#fbbf24";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(22 * facing, -6); ctx.quadraticCurveTo(38 * facing, -24, 46 * facing, -8);
    ctx.stroke();
    ctx.restore();
    return true;
  }

  // 18. PHANTOM ROSHAN (Призрачный Рошан Хаоса)
  if (bId.includes("phantom_roshan") || bId.includes("призрачный рошан")) {
    const fBob = Math.sin(time * 0.14) * 4;
    ctx.save();
    ctx.translate(0, fBob);
    // Ethereal Translucent Ghost Body
    ctx.fillStyle = "rgba(6, 78, 59, 0.85)";
    ctx.strokeStyle = "#34d399";
    ctx.lineWidth = 3;
    ctx.shadowColor = "#10b981"; ctx.shadowBlur = 22;
    ctx.beginPath();
    ctx.ellipse(0, 0, 30, 26, 0, 0, Math.PI * 2);
    ctx.fill(); ctx.stroke();

    // Spectral Energy Cracks
    ctx.strokeStyle = "#6ee7b7";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.moveTo(-14, -8); ctx.lineTo(-2, 4); ctx.lineTo(16, -6);
    ctx.moveTo(-8, 8); ctx.lineTo(8, 14);
    ctx.stroke();

    // Spectral Horns & Eyes
    ctx.strokeStyle = "#a7f3d0";
    ctx.lineWidth = 3.5;
    ctx.beginPath();
    ctx.moveTo(-16 * facing, -16); ctx.quadraticCurveTo(-30 * facing, -34, -16 * facing, -38);
    ctx.stroke();
    ctx.fillStyle = "#67e8f9";
    ctx.shadowColor = "#67e8f9"; ctx.shadowBlur = 12;
    ctx.fillRect(-14 * facing, -10, 6 * facing, 4);
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  // 19. TINKER (Архиинженер / Omega Tinker)
  if (bId.includes("tinker_boss") || bId.includes("архиинженер")) {
    ctx.save();
    // Steampunk Combat Mech Cockpit
    ctx.fillStyle = "#334155";
    ctx.strokeStyle = "#facc15";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.roundRect(-22, -22, 44, 40, 8);
    ctx.fill(); ctx.stroke();

    // Mechanical Goggles Cockpit Viewport
    ctx.fillStyle = "#0284c7";
    ctx.shadowColor = "#38bdf8"; ctx.shadowBlur = 10;
    ctx.beginPath();
    ctx.arc(0, -6, 11, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;

    // Dual Rocket Pods on Shoulders
    ctx.fillStyle = "#dc2626";
    ctx.fillRect(-30, -28, 10, 16);
    ctx.fillRect(20, -28, 10, 16);
    ctx.fillStyle = "#facc15";
    ctx.fillRect(-28, -32, 6, 4);
    ctx.fillRect(22, -32, 6, 4);

    // High-Tech Laser Emitter Arm
    ctx.strokeStyle = "#94a3b8";
    ctx.lineWidth = 3.5;
    ctx.beginPath();
    ctx.moveTo(18 * facing, 6); ctx.lineTo(34 * facing, 6);
    ctx.stroke();
    ctx.fillStyle = "#ef4444";
    ctx.shadowColor = "#ef4444"; ctx.shadowBlur = 8;
    ctx.fillRect(32 * facing, 3, 5 * facing, 6);
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  // 20. ENIGMA (Пожиратель Миров / Enigma Cosmic)
  if (bId.includes("enigma") || bId.includes("пожиратель миров")) {
    const eSpin = time * 0.04;
    ctx.save();
    // Cosmic Nebula Void Entity
    ctx.fillStyle = "#1e1b4b";
    ctx.strokeStyle = "#818cf8";
    ctx.lineWidth = 3;
    ctx.shadowColor = "#6366f1"; ctx.shadowBlur = 24;
    ctx.beginPath();
    ctx.ellipse(0, 0, 26, 30, 0, 0, Math.PI * 2);
    ctx.fill(); ctx.stroke();

    // Swirling Central Singularity in Chest
    ctx.fillStyle = "#020617";
    ctx.beginPath();
    ctx.arc(0, 0, 12, 0, Math.PI * 2);
    ctx.fill();

    // Orbiting Cosmic Asteroid Fragments
    for (let a = 0; a < 5; a++) {
      const aAng = eSpin + a * 1.25;
      const ax = Math.cos(aAng) * 36;
      const ay = Math.sin(aAng) * 22;
      ctx.fillStyle = "#c7d2fe";
      ctx.beginPath();
      ctx.arc(ax, ay, 3, 0, Math.PI * 2);
      ctx.fill();
    }

    // Glowing Star Eyes
    ctx.fillStyle = "#ffffff";
    ctx.shadowColor = "#ffffff"; ctx.shadowBlur = 12;
    ctx.fillRect(-6 * facing, -16, 3 * facing, 3);
    ctx.fillRect(3 * facing, -16, 3 * facing, 3);
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  return false;
}

// ============================================================================
// 06_boss_models_mid.js — Procedural Vector Models for Bosses 7–13
// (Roshan, Tidehunter, SF, Necrophos, Terrorblade, Invoker, Chaos Knight)
// ============================================================================

function drawBossModelMid(ctx, b, bId, time) {
  const facing = b.facing || 1;
  let assetName = null;
  if (bId.includes("roshan") && !bId.includes("phantom")) assetName = "roshan";
  if (bId.includes("terrorblade") || bId.includes("террорблейд")) assetName = "terrorblade";

  if (assetName && typeof RPG_ASSETS !== "undefined" && RPG_ASSETS.bosses[assetName]) {
    const bossAsset = RPG_ASSETS.bosses[assetName];
    if (bossAsset && bossAsset.complete && bossAsset.naturalWidth > 0) {
      ctx.save();
      if (facing === -1) {
        ctx.scale(-1, 1);
      }
      const size = b.radius * 6.0;
      ctx.drawImage(bossAsset, -size / 2, -size / 1.1, size, size);
      ctx.restore();
      return true;
    }
  }

  // 7. ROSHAN (Рошан Свирепый)
  if (bId.includes("roshan") && !bId.includes("phantom")) {
    ctx.save();
    // Hulking Pit Beast Body
    ctx.fillStyle = "#451a03";
    ctx.strokeStyle = "#92400e";
    ctx.lineWidth = 3.5;
    ctx.beginPath();
    ctx.ellipse(0, 2, 28, 26, 0, 0, Math.PI * 2);
    ctx.fill(); ctx.stroke();

    // Spiky Rock Carapace on Back
    ctx.fillStyle = "#292524";
    ctx.beginPath();
    ctx.moveTo(-16, -12); ctx.lineTo(-24, -22); ctx.lineTo(-8, -18);
    ctx.lineTo(0, -26); ctx.lineTo(8, -18); ctx.lineTo(24, -22); ctx.lineTo(16, -12);
    ctx.closePath();
    ctx.fill();

    // Massive Curved Demon Horns
    ctx.strokeStyle = "#ea580c";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(-12 * facing, -18); ctx.quadraticCurveTo(-28 * facing, -38, -14 * facing, -42);
    ctx.moveTo(12 * facing, -18); ctx.quadraticCurveTo(28 * facing, -38, 14 * facing, -42);
    ctx.stroke();

    // Glowing Molten Eyes & Maw
    ctx.fillStyle = "#facc15";
    ctx.shadowColor = "#ea580c"; ctx.shadowBlur = 12;
    ctx.fillRect(-8 * facing, -18, 4 * facing, 3);
    ctx.fillRect(4 * facing, -18, 4 * facing, 3);
    ctx.fillStyle = "#ef4444";
    ctx.beginPath();
    ctx.moveTo(-6 * facing, -8); ctx.lineTo(6 * facing, -8); ctx.lineTo(0, 2);
    ctx.closePath();
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  // 8. TIDEHUNTER (Левиафан Бездны)
  if (bId.includes("tidehunter") || bId.includes("левиафан")) {
    ctx.save();
    // Colossal Amphibious Green Body
    ctx.fillStyle = "#064e3b";
    ctx.strokeStyle = "#10b981";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.ellipse(0, 2, 27, 25, 0, 0, Math.PI * 2);
    ctx.fill(); ctx.stroke();

    // Fish-Scale Ridges & Fins
    ctx.fillStyle = "#047857";
    ctx.beginPath();
    ctx.moveTo(-18 * facing, -14); ctx.lineTo(-26 * facing, -20); ctx.lineTo(-14 * facing, -6);
    ctx.moveTo(18 * facing, -14); ctx.lineTo(26 * facing, -20); ctx.lineTo(14 * facing, -6);
    ctx.fill();

    // Giant Rusted Heavy Anchor in Arm
    const aBob = Math.sin(time * 0.16) * 3;
    ctx.strokeStyle = "#78716c";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(22 * facing, -18 + aBob); ctx.lineTo(22 * facing, 16 + aBob);
    ctx.arc(22 * facing, 10 + aBob, 10, 0, Math.PI);
    ctx.stroke();

    // Fierce Yellow Sea-Beast Eyes
    ctx.fillStyle = "#fef08a";
    ctx.shadowColor = "#34d399"; ctx.shadowBlur = 8;
    ctx.fillRect(-8 * facing, -14, 4 * facing, 4);
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  // 9. SHADOW FIEND (Архидемон Nevermore)
  if (bId.includes("sf_boss") || bId.includes("nevermore")) {
    const sBob = Math.sin(time * 0.2) * 3;
    ctx.save();
    ctx.translate(0, sBob);

    // Swirling Shadow Pitch-Black Smoldering Body
    ctx.fillStyle = "#09090b";
    ctx.strokeStyle = "#dc2626";
    ctx.lineWidth = 2.5;
    ctx.shadowColor = "#b91c1c"; ctx.shadowBlur = 14;
    ctx.beginPath();
    ctx.moveTo(0, -26);
    ctx.quadraticCurveTo(20, -10, 14, 16);
    ctx.quadraticCurveTo(0, 26, -14, 16);
    ctx.quadraticCurveTo(-20, -10, 0, -26);
    ctx.closePath();
    ctx.fill(); ctx.stroke();

    // Glowing Crimson Ribcage
    ctx.strokeStyle = "#f87171";
    ctx.lineWidth = 2;
    for (let r = 0; r < 4; r++) {
      ctx.beginPath();
      ctx.moveTo(-10, -12 + r * 6); ctx.lineTo(10, -12 + r * 6);
      ctx.stroke();
    }

    // Fiery Horns & Demon Blade Hands
    ctx.strokeStyle = "#ef4444";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(-10 * facing, -24); ctx.lineTo(-18 * facing, -36);
    ctx.moveTo(10 * facing, -24); ctx.lineTo(18 * facing, -36);
    // Blade Arms
    ctx.moveTo(-18 * facing, 2); ctx.lineTo(-32 * facing, 14);
    ctx.moveTo(18 * facing, 2); ctx.lineTo(32 * facing, 14);
    ctx.stroke();
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  // 10. NECROPHOS (Чумной Владыка)
  if (bId.includes("necrophos") || bId.includes("чумной")) {
    const pBob = Math.sin(time * 0.12) * 3;
    ctx.save();
    ctx.translate(0, pBob);

    // Rotten Plague Robes
    ctx.fillStyle = "#14532d";
    ctx.strokeStyle = "#84cc16";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, -24); ctx.lineTo(16, 20); ctx.lineTo(-16, 20);
    ctx.closePath();
    ctx.fill(); ctx.stroke();

    // Pale Skull Head with Mitre Crown
    ctx.fillStyle = "#f1f5f9";
    ctx.beginPath();
    ctx.arc(0, -20, 8, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#166534";
    ctx.beginPath();
    ctx.moveTo(-6, -26); ctx.lineTo(0, -36); ctx.lineTo(6, -26);
    ctx.closePath();
    ctx.fill();

    // Venomous Curved Scythe
    ctx.strokeStyle = "#65a30d";
    ctx.lineWidth = 3.5;
    ctx.beginPath();
    ctx.moveTo(14 * facing, -32); ctx.lineTo(14 * facing, 22);
    ctx.quadraticCurveTo(28 * facing, -38, 36 * facing, -22);
    ctx.stroke();

    // Swirling Plague Particles
    for (let p = 0; p < 4; p++) {
      const pAng = time * 0.1 + p * 1.57;
      const px = Math.cos(pAng) * 22;
      const py = Math.sin(pAng) * 12;
      ctx.fillStyle = "#a3e635";
      ctx.fillRect(px, py, 2.5, 2.5);
    }
    ctx.restore();
    return true;
  }

  // 11. TERRORBLADE (Демон Бездны)
  if (bId.includes("terrorblade") || bId.includes("демон бездны")) {
    ctx.save();
    // Fractured Obsidian Torso
    ctx.fillStyle = "#18181b";
    ctx.strokeStyle = "#7c3aed";
    ctx.lineWidth = 2.5;
    ctx.shadowColor = "#8b5cf6"; ctx.shadowBlur = 12;
    ctx.beginPath();
    ctx.roundRect(-14, -20, 28, 38, 4);
    ctx.fill(); ctx.stroke();

    // Dual Arc Curved Crescent Blades
    ctx.strokeStyle = "#a78bfa";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(-22 * facing, -2, 14, -Math.PI / 2, Math.PI / 2);
    ctx.arc(22 * facing, -2, 14, Math.PI / 2, -Math.PI / 2);
    ctx.stroke();

    // Demon Wings
    ctx.fillStyle = "rgba(109, 40, 217, 0.75)";
    ctx.beginPath();
    ctx.moveTo(-12 * facing, -12); ctx.lineTo(-34 * facing, -30); ctx.lineTo(-24 * facing, 2);
    ctx.moveTo(12 * facing, -12); ctx.lineTo(34 * facing, -30); ctx.lineTo(24 * facing, 2);
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  // 12. INVOKER (Демиург Арсенала)
  if (bId.includes("invoker_boss") || bId.includes("инвокер") || bId.includes("арсенал")) {
    const iBob = Math.sin(time * 0.14) * 3;
    ctx.save();
    ctx.translate(0, iBob);

    // Regal Cape & Armor
    ctx.fillStyle = "#7c2d12";
    ctx.strokeStyle = "#facc15";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, -24); ctx.lineTo(16, 20); ctx.lineTo(-16, 20);
    ctx.closePath();
    ctx.fill(); ctx.stroke();

    // High Upturned Regal Mantle Collar
    ctx.fillStyle = "#facc15";
    ctx.beginPath();
    ctx.moveTo(-10, -22); ctx.lineTo(-18, -34); ctx.lineTo(-6, -26);
    ctx.moveTo(10, -22); ctx.lineTo(18, -34); ctx.lineTo(6, -26);
    ctx.fill();

    // Majestic Blond Hair & Glowing Eyes
    ctx.fillStyle = "#fef08a";
    ctx.beginPath();
    ctx.arc(0, -22, 8, 0, Math.PI * 2);
    ctx.fill();

    // 3 Orbiting Mystic Spheres: Quas (Blue), Wex (Purple), Exort (Orange)
    const orbs = [
      { c: "#38bdf8", angOff: 0 },
      { c: "#c084fc", angOff: 2.09 },
      { c: "#f97316", angOff: 4.18 }
    ];
    for (const o of orbs) {
      const oAng = time * 0.08 + o.angOff;
      const ox = Math.cos(oAng) * 26;
      const oy = Math.sin(oAng) * 14 - 14;
      ctx.fillStyle = o.c;
      ctx.shadowColor = o.c; ctx.shadowBlur = 10;
      ctx.beginPath();
      ctx.arc(ox, oy, 5, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.shadowBlur = 0;
    ctx.restore();
    return true;
  }

  // 13. CHAOS KNIGHT (Всадник Хаоса)
  if (bId.includes("chaos_knight") || bId.includes("всадник хаоса")) {
    ctx.save();
    // Armored Warhorse Torso
    ctx.fillStyle = "#1e1b4b";
    ctx.strokeStyle = "#f59e0b";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.ellipse(0, 4, 24, 18, 0, 0, Math.PI * 2);
    ctx.fill(); ctx.stroke();

    // Flaming Mane & Hooves
    ctx.fillStyle = "#ef4444";
    ctx.beginPath();
    ctx.moveTo(12 * facing, -6); ctx.lineTo(24 * facing, -18); ctx.lineTo(18 * facing, -2);
    ctx.fill();

    // Armored Helm with Spiked Horns
    ctx.fillStyle = "#0f172a";
    ctx.beginPath();
    ctx.moveTo(-6 * facing, -18); ctx.lineTo(6 * facing, -18); ctx.lineTo(0, -32);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = "#f59e0b";
    ctx.lineWidth = 2;
    ctx.stroke();

    // Spiked Chaos Flail in Arm
    const fSpin = time * 0.16;
    const fx = -20 * facing + Math.cos(fSpin) * 12;
    const fy = -4 + Math.sin(fSpin) * 12;
    ctx.strokeStyle = "#d97706";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(-16 * facing, 2); ctx.lineTo(fx, fy);
    ctx.stroke();
    ctx.fillStyle = "#ef4444";
    ctx.beginPath();
    ctx.arc(fx, fy, 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
    return true;
  }

  return false;
}

  function drawProceduralHero(ctx, p, heroClass, time = (ARENA.frameCount || 0), isAttacking, comboStep) {
    time = (time != null ? time : (ARENA.frameCount || 0));
    const hClass = (heroClass || "pudge").toLowerCase();
    const bob = Math.sin(time * 0.14) * 2;
    const facing = (p && p.facing !== undefined) ? p.facing : 1;

    ctx.save();
    ctx.translate(p.x, p.y + bob);
    if (facing === -1) {
      ctx.scale(-1, 1);
    }

    // 1. Soft Oval Ground Shadow
    ctx.fillStyle = "rgba(0, 0, 0, 0.38)";
    ctx.beginPath();
    ctx.ellipse(0, p.radius + 3 - bob, p.radius * 0.95, 5, 0, 0, Math.PI * 2);
    ctx.fill();

    // Invulnerability / Dash Ghost Aura
    if (p.isInvulnerable > 0) {
      ctx.strokeStyle = "rgba(56, 189, 248, 0.85)";
      ctx.lineWidth = 2.5;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.arc(0, 0, p.radius + 6, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Crit Buff Glow
    if (p.critBuff) {
      ctx.fillStyle = "rgba(250, 204, 21, 0.25)";
      ctx.beginPath();
      ctx.arc(0, 0, p.radius + 8, 0, Math.PI * 2);
      ctx.fill();
    }

    if (typeof RPG_ASSETS !== "undefined" && RPG_ASSETS.heroes[hClass]) {
      const heroAsset = RPG_ASSETS.heroes[hClass];
      if (heroAsset && heroAsset.complete && heroAsset.naturalWidth > 0) {
        const size = p.radius * 5.0; // adjust scale
        ctx.drawImage(heroAsset, -size / 2, -size / 1.1, size, size);
        ctx.restore();
        return;
      }
    }

    // Class-specific Procedural Vector Geometry
    if (hClass.includes("pudge")) {
      // --- PUDGE (Мясник) ---
      // Rot gas wisps
      if (p.rotActive > 0 || (time % 20 < 10)) {
        ctx.fillStyle = "rgba(34, 197, 94, 0.22)";
        for (let i = 0; i < 3; i++) {
          const rx = Math.sin(time * 0.1 + i * 2) * 16;
          const ry = -18 - (time * 0.4 + i * 8) % 18;
          ctx.beginPath();
          ctx.arc(rx, ry, 5 + i, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      // Big round body (decaying greenish flesh)
      ctx.fillStyle = "#3d4b35";
      ctx.beginPath();
      ctx.ellipse(0, 2, 17, 18, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#1e2619";
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Stitches across belly
      ctx.strokeStyle = "#141c10";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(-6, -4); ctx.lineTo(4, 8);
      ctx.moveTo(-7, 2); ctx.lineTo(-1, -2);
      ctx.moveTo(0, 7); ctx.lineTo(6, 3);
      ctx.stroke();

      // Blood-stained butcher apron
      ctx.fillStyle = "#7f1d1d";
      ctx.beginPath();
      ctx.moveTo(-8, -4);
      ctx.lineTo(8, -4);
      ctx.lineTo(10, 16);
      ctx.lineTo(-10, 16);
      ctx.closePath();
      ctx.fill();

      // Apron blood splatters
      ctx.fillStyle = "#450a0a";
      ctx.beginPath();
      ctx.arc(-2, 4, 3, 0, Math.PI * 2);
      ctx.arc(4, 10, 2.5, 0, Math.PI * 2);
      ctx.fill();

      // Head
      ctx.fillStyle = "#4a5940";
      ctx.beginPath();
      ctx.arc(2, -13, 9, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // Glowing yellow sinister eye
      ctx.fillStyle = "#facc15";
      ctx.shadowColor = "#facc15";
      ctx.shadowBlur = 6;
      ctx.beginPath();
      ctx.arc(5, -14, 2, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

      // Heavy Iron Cleaver (in right hand)
      const cleaverAngle = isAttacking ? (comboStep === 2 ? 1.4 : 0.8) : 0.15;
      ctx.save();
      ctx.translate(8, 2);
      ctx.rotate(cleaverAngle);
      // Cleaver blade
      ctx.fillStyle = "#1e293b";
      ctx.strokeStyle = "#94a3b8";
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.rect(0, -18, 14, 12);
      ctx.fill();
      ctx.stroke();
      // Sharp cutting edge
      ctx.fillStyle = "#e2e8f0";
      ctx.fillRect(12, -18, 2.5, 12);
      // Wooden handle
      ctx.fillStyle = "#78350f";
      ctx.fillRect(-2, -6, 4, 10);
      ctx.restore();

      // Hook chain (left hand)
      ctx.strokeStyle = "#64748b";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(-10, 4);
      ctx.quadraticCurveTo(-16, 12, -12, 16);
      ctx.stroke();
      // Hook curve
      ctx.strokeStyle = "#cbd5e1";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.arc(-13, 17, 4, 0, Math.PI * 1.5, false);
      ctx.stroke();

    } else if (hClass.includes("juggernaut")) {
      // --- JUGGERNAUT (Юрнеро) ---
      // Flowing red/orange samurai hakama
      ctx.fillStyle = "#b91c1c";
      ctx.beginPath();
      ctx.moveTo(-8, 0);
      ctx.lineTo(8, 0);
      ctx.lineTo(11, 17);
      ctx.lineTo(-11, 17);
      ctx.closePath();
      ctx.fill();

      // Gold obi sash
      ctx.fillStyle = "#f59e0b";
      ctx.fillRect(-9, 0, 18, 4);

      // Emerald green vest
      ctx.fillStyle = "#047857";
      ctx.beginPath();
      ctx.moveTo(-7, -10);
      ctx.lineTo(7, -10);
      ctx.lineTo(8, 0);
      ctx.lineTo(-8, 0);
      ctx.closePath();
      ctx.fill();

      // White demon ancestral mask
      ctx.fillStyle = "#fef3c7";
      ctx.strokeStyle = "#d97706";
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.ellipse(3, -12, 7.5, 8.5, 0.1, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // Red mask warpaint stripes
      ctx.strokeStyle = "#dc2626";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(1, -16); ctx.lineTo(1, -8);
      ctx.moveTo(5, -16); ctx.lineTo(5, -8);
      ctx.stroke();

      // Glowing amber eye slits
      ctx.fillStyle = "#f59e0b";
      ctx.shadowColor = "#f59e0b";
      ctx.shadowBlur = 6;
      ctx.fillRect(4, -13, 3, 1.5);
      ctx.shadowBlur = 0;

      // Fluttering samurai ponytail
      const hairWave = Math.sin(time * 0.2) * 3;
      ctx.strokeStyle = "#18181b";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(-4, -14);
      ctx.quadraticCurveTo(-12, -18 + hairWave, -16, -12 + hairWave);
      ctx.stroke();

      // Curved Katana with glowing edge
      const swordSwing = isAttacking ? (comboStep === 2 ? 1.6 : 0.9) : -0.3;
      ctx.save();
      ctx.translate(6, -2);
      ctx.rotate(swordSwing);
      // Tsuba guard
      ctx.fillStyle = "#d97706";
      ctx.fillRect(-2, -2, 4, 4);
      // Blade
      ctx.strokeStyle = "#f8fafc";
      ctx.lineWidth = 2;
      ctx.shadowColor = "#f59e0b";
      ctx.shadowBlur = 8;
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.quadraticCurveTo(10, -18, 16, -26);
      ctx.stroke();
      ctx.shadowBlur = 0;
      // Katana hilt
      ctx.fillStyle = "#451a03";
      ctx.fillRect(-2, 2, 4, 9);
      ctx.restore();

    } else if (hClass.includes("invoker")) {
      // --- INVOKER (Карл) ---
      // Levitation float
      const lev = Math.sin(time * 0.1) * 3;
      ctx.translate(0, -lev);

      // Royal crimson cape with high standing collar
      ctx.fillStyle = "#881337";
      ctx.beginPath();
      ctx.moveTo(-9, -15);
      ctx.lineTo(4, -15);
      ctx.lineTo(8, 17);
      ctx.lineTo(-14, 18);
      ctx.closePath();
      ctx.fill();
      // Gold embroidery border
      ctx.strokeStyle = "#facc15";
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Royal purple & gold robes
      ctx.fillStyle = "#581c87";
      ctx.beginPath();
      ctx.moveTo(-6, -7);
      ctx.lineTo(6, -7);
      ctx.lineTo(8, 15);
      ctx.lineTo(-6, 15);
      ctx.closePath();
      ctx.fill();

      // Head & blonde hair
      ctx.fillStyle = "#fed7aa";
      ctx.beginPath();
      ctx.arc(1, -12, 7, 0, Math.PI * 2);
      ctx.fill();
      // Flowing platinum blonde hair
      ctx.fillStyle = "#fef08a";
      ctx.beginPath();
      ctx.moveTo(-6, -14);
      ctx.quadraticCurveTo(-11, -8, -13, 2);
      ctx.lineTo(-4, -10);
      ctx.closePath();
      ctx.fill();

      // Glowing arcane eyes
      ctx.fillStyle = "#e0e7ff";
      ctx.shadowColor = "#818cf8";
      ctx.shadowBlur = 6;
      ctx.fillRect(3, -13, 2.5, 2);
      ctx.shadowBlur = 0;

      // Arcane Crystal Staff
      ctx.save();
      ctx.translate(9, -2);
      ctx.strokeStyle = "#eab308";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(0, 15); ctx.lineTo(0, -20);
      ctx.stroke();
      // Floating crystal at staff head
      ctx.fillStyle = "#38bdf8";
      ctx.shadowColor = "#38bdf8";
      ctx.shadowBlur = 10;
      ctx.beginPath();
      ctx.moveTo(0, -28); ctx.lineTo(4, -22); ctx.lineTo(0, -16); ctx.lineTo(-4, -22);
      ctx.closePath();
      ctx.fill();
      ctx.shadowBlur = 0;
      ctx.restore();

      // 3 REVOLVING ELEMENTAL ORBS IN 3D ORBIT (Quas, Wex, Exort)
      const orbitR = 21;
      const orbs = [
        { name: "Quas", color: "#38bdf8", glow: "#0284c7", angle: time * 0.05 },
        { name: "Wex", color: "#c084fc", glow: "#9333ea", angle: time * 0.05 + 2.094 },
        { name: "Exort", color: "#f97316", glow: "#ea580c", angle: time * 0.05 + 4.188 }
      ];
      for (const orb of orbs) {
        const ox = Math.cos(orb.angle) * orbitR;
        const oy = Math.sin(orb.angle) * (orbitR * 0.42) - 8;
        ctx.fillStyle = orb.color;
        ctx.shadowColor = orb.glow;
        ctx.shadowBlur = 9;
        ctx.beginPath();
        ctx.arc(ox, oy, 4.5, 0, Math.PI * 2);
        ctx.fill();
        // Bright core
        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.arc(ox - 1, oy - 1, 1.8, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;
      }

    } else if (hClass.includes("phantom") || hClass.includes("pa")) {
      // --- PHANTOM ASSASSIN (Мортред) ---
      // Shadow cloak dissolving into mist
      ctx.fillStyle = "rgba(15, 23, 42, 0.9)";
      ctx.beginPath();
      ctx.moveTo(-6, -10);
      ctx.lineTo(6, -10);
      ctx.lineTo(9, 16);
      ctx.lineTo(-12, 16);
      ctx.closePath();
      ctx.fill();

      // Cyan misty trail motes
      ctx.fillStyle = "rgba(34, 211, 238, 0.45)";
      for (let i = 0; i < 3; i++) {
        const mx = -10 - (time * 0.6 + i * 5) % 12;
        const my = 8 + Math.sin(time * 0.2 + i) * 6;
        ctx.beginPath();
        ctx.arc(mx, my, 2.5, 0, Math.PI * 2);
        ctx.fill();
      }

      // Torso / armor
      ctx.fillStyle = "#0e7490";
      ctx.beginPath();
      ctx.moveTo(-5, -6); ctx.lineTo(5, -6); ctx.lineTo(6, 6); ctx.lineTo(-5, 6);
      ctx.closePath();
      ctx.fill();

      // Assassin Cowl / Hood
      ctx.fillStyle = "#0f172a";
      ctx.beginPath();
      ctx.arc(2, -12, 8, 0, Math.PI * 2);
      ctx.fill();
      ctx.beginPath();
      ctx.moveTo(-6, -12); ctx.lineTo(8, -12); ctx.lineTo(4, -3);
      ctx.closePath();
      ctx.fill();

      // Glowing Cyan Assassin Slit Eyes
      ctx.fillStyle = "#22d3ee";
      ctx.shadowColor = "#22d3ee";
      ctx.shadowBlur = 9;
      ctx.fillRect(4, -13, 3, 1.5);
      ctx.shadowBlur = 0;

      // Dual Phantom Daggers with Cyan Poison
      const dagAngle = isAttacking ? 1.2 : 0.2;
      ctx.save();
      ctx.translate(7, 2);
      ctx.rotate(dagAngle);
      // Dagger 1
      ctx.strokeStyle = "#22d3ee";
      ctx.lineWidth = 2.5;
      ctx.shadowColor = "#22d3ee";
      ctx.shadowBlur = 7;
      ctx.beginPath();
      ctx.moveTo(0, 0); ctx.lineTo(12, -10); ctx.lineTo(15, -9);
      ctx.stroke();
      ctx.shadowBlur = 0;
      // Dagger 2
      ctx.strokeStyle = "#67e8f9";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(-2, 4); ctx.lineTo(8, -4);
      ctx.stroke();
      ctx.restore();

    } else if (hClass.includes("shadow_fiend") || hClass.includes("sf")) {
      // --- SHADOW FIEND (Невермор) ---
      // Swirling Demonic Shadow Vortex Base (no feet)
      const swirl = Math.sin(time * 0.25) * 4;
      ctx.fillStyle = "#09090b";
      ctx.beginPath();
      ctx.moveTo(-10, 0);
      ctx.quadraticCurveTo(swirl, 16, 2, 22);
      ctx.quadraticCurveTo(-swirl, 16, 10, 0);
      ctx.closePath();
      ctx.fill();

      // Demon Spire Shoulders
      ctx.fillStyle = "#18181b";
      ctx.beginPath();
      ctx.moveTo(-16, -14); ctx.lineTo(-6, -4); ctx.lineTo(0, -6);
      ctx.lineTo(6, -4); ctx.lineTo(16, -14); ctx.lineTo(8, 2); ctx.lineTo(-8, 2);
      ctx.closePath();
      ctx.fill();

      // Roaring Soul-Furnace Chest Core
      const pulse = 1 + Math.sin(time * 0.2) * 0.25;
      ctx.fillStyle = "#ea580c";
      ctx.shadowColor = "#f97316";
      ctx.shadowBlur = 12 * pulse;
      ctx.beginPath();
      ctx.arc(0, -3, 6 * pulse, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#fef08a";
      ctx.beginPath();
      ctx.arc(0, -3, 3, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

      // Horned Demon Head
      ctx.fillStyle = "#09090b";
      ctx.beginPath();
      ctx.arc(1, -14, 7, 0, Math.PI * 2);
      ctx.fill();
      // Curved ram horns
      ctx.strokeStyle = "#450a0a";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.moveTo(-4, -16); ctx.quadraticCurveTo(-11, -24, -8, -26);
      ctx.moveTo(6, -16); ctx.quadraticCurveTo(13, -24, 10, -26);
      ctx.stroke();

      // Glowing Crimson Eyes & Fangs
      ctx.fillStyle = "#ef4444";
      ctx.shadowColor = "#ef4444";
      ctx.shadowBlur = 8;
      ctx.fillRect(2, -15, 3, 1.8);
      ctx.fillRect(1, -11, 4, 1.2);
      ctx.shadowBlur = 0;

      // Soul Fire Hands
      ctx.fillStyle = "#f97316";
      ctx.shadowColor = "#f97316";
      ctx.shadowBlur = 8;
      ctx.beginPath();
      ctx.arc(12, 0, 4, 0, Math.PI * 2);
      ctx.arc(-12, 0, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

    } else if (hClass.includes("wraith_king") || hClass.includes("wk")) {
      // --- WRAITH KING (Остарион) ---
      // Tattered emerald mantle
      ctx.fillStyle = "#064e3b";
      ctx.beginPath();
      ctx.moveTo(-9, -10); ctx.lineTo(7, -10); ctx.lineTo(10, 18); ctx.lineTo(-13, 18);
      ctx.closePath();
      ctx.fill();

      // Spectral Green Plate Armor
      ctx.fillStyle = "#065f46";
      ctx.strokeStyle = "#10b981";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.rect(-8, -6, 16, 16);
      ctx.fill();
      ctx.stroke();

      // Skeletal Skull Face
      ctx.fillStyle = "#e2e8f0";
      ctx.beginPath();
      ctx.arc(1, -12, 7.5, 0, Math.PI * 2);
      ctx.fill();

      // Blazing Emerald Soul Fire in Eye Sockets
      ctx.fillStyle = "#10b981";
      ctx.shadowColor = "#10b981";
      ctx.shadowBlur = 10;
      ctx.beginPath();
      ctx.arc(3, -13, 2.2, 0, Math.PI * 2);
      ctx.arc(-1, -13, 2.2, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

      // Spiked Golden Bone Crown
      ctx.fillStyle = "#eab308";
      ctx.strokeStyle = "#ca8a04";
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(-7, -17);
      ctx.lineTo(-5, -23);
      ctx.lineTo(-2, -18);
      ctx.lineTo(1, -26);
      ctx.lineTo(4, -18);
      ctx.lineTo(7, -23);
      ctx.lineTo(9, -17);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();

      // Colossal Runic Zweihander Broadsword
      const swordSwing = isAttacking ? 1.4 : 0.2;
      ctx.save();
      ctx.translate(9, 2);
      ctx.rotate(swordSwing);
      // Giant blade with green soul edge
      ctx.fillStyle = "#1e293b";
      ctx.strokeStyle = "#10b981";
      ctx.lineWidth = 2;
      ctx.shadowColor = "#10b981";
      ctx.shadowBlur = 9;
      ctx.beginPath();
      ctx.moveTo(-3, 0); ctx.lineTo(3, 0); ctx.lineTo(4, -28); ctx.lineTo(0, -33); ctx.lineTo(-4, -28);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.shadowBlur = 0;
      // Skull crossguard
      ctx.fillStyle = "#eab308";
      ctx.fillRect(-7, 0, 14, 3.5);
      // Hilt
      ctx.fillStyle = "#451a03";
      ctx.fillRect(-1.5, 3.5, 3, 9);
      ctx.restore();

    } else if (hClass.includes("anti_mage") || hClass.includes("am")) {
      // --- ANTI-MAGE (Магина) ---
      // Indigo monk pants
      ctx.fillStyle = "#312e81";
      ctx.beginPath();
      ctx.moveTo(-7, 0); ctx.lineTo(7, 0); ctx.lineTo(9, 17); ctx.lineTo(-9, 17);
      ctx.closePath();
      ctx.fill();

      // Gold sash belt
      ctx.fillStyle = "#f59e0b";
      ctx.fillRect(-8, 0, 16, 3.5);

      // Muscular torso with purple mana burn tattoos
      ctx.fillStyle = "#fed7aa";
      ctx.beginPath();
      ctx.rect(-6, -9, 12, 9);
      ctx.fill();
      // Glowing purple tattoos
      ctx.strokeStyle = "#c084fc";
      ctx.lineWidth = 1.5;
      ctx.shadowColor = "#a855f7";
      ctx.shadowBlur = 6;
      ctx.beginPath();
      ctx.moveTo(-4, -7); ctx.lineTo(-1, -3); ctx.lineTo(3, -7);
      ctx.stroke();
      ctx.shadowBlur = 0;

      // Monk head
      ctx.fillStyle = "#fed7aa";
      ctx.beginPath();
      ctx.arc(0, -13, 7, 0, Math.PI * 2);
      ctx.fill();

      // Purple Monk Blindfold
      ctx.fillStyle = "#6b21a8";
      ctx.fillRect(-6, -15, 13, 4.5);
      ctx.fillStyle = "#e9d5ff";
      ctx.fillRect(-2, -14, 5, 2);

      // Twin Crescent Mana Glaives in both hands
      const glaiveSwing = isAttacking ? 1.3 : 0.1;
      ctx.save();
      ctx.translate(6, 0);
      ctx.rotate(glaiveSwing);
      // Front Glaive
      ctx.strokeStyle = "#c084fc";
      ctx.lineWidth = 3;
      ctx.shadowColor = "#9333ea";
      ctx.shadowBlur = 9;
      ctx.beginPath();
      ctx.arc(2, -4, 11, -Math.PI * 0.4, Math.PI * 0.6, false);
      ctx.stroke();
      ctx.shadowBlur = 0;
      // Handle
      ctx.fillStyle = "#e2e8f0";
      ctx.fillRect(0, -7, 4, 6);
      ctx.restore();

      // Back Glaive
      ctx.save();
      ctx.translate(-7, 2);
      ctx.rotate(-glaiveSwing * 0.8);
      ctx.strokeStyle = "#a855f7";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.arc(-2, -4, 9, -Math.PI * 0.5, Math.PI * 0.5, true);
      ctx.stroke();
      ctx.restore();

    } else {
      // --- DEFAULT WARRIOR / HERO FALLBACK ---
      ctx.fillStyle = "#1e293b";
      ctx.beginPath(); ctx.arc(0, 0, 14, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = "#facc15"; ctx.lineWidth = 2; ctx.stroke();
      ctx.fillStyle = "#facc15";
      ctx.fillRect(4, -10, 4, 20);
    }

    ctx.restore();
  }

  // ===========================================================================
  // PROCEDURAL CREEP & MONSTER SPRITE RENDERER
  // ===========================================================================

  function drawProceduralCreep(ctx, c, time = (ARENA.frameCount || 0)) {
    time = (time != null ? time : (ARENA.frameCount || 0));
    const bob = Math.sin(time * 0.16 + c.x * 0.05) * 1.8;
    const type = (c.archetype || c.team || "melee").toLowerCase();

    ctx.save();
    ctx.translate(c.x, c.y + bob + (c.jumpY || 0));

    // Ground Shadow (pinned to road floor even if boss is leaping high in the air)
    const shadowScale = c.isBoss ? Math.max(0.35, 1.0 - Math.abs(c.jumpY || 0) / 95) : 1.0;
    ctx.fillStyle = `rgba(0, 0, 0, ${0.32 * shadowScale})`;
    ctx.beginPath();
    ctx.ellipse(0, c.radius + 2 - bob - (c.jumpY || 0), (c.radius * 0.9) * shadowScale, 4.5 * shadowScale, 0, 0, Math.PI * 2);
    ctx.fill();

    // God Mode Aura
    if (c.isGodMode || c.enrageStage === "god_mode") {
      const pulse = 1 + Math.sin(time * 0.25) * 0.15;
      ctx.strokeStyle = "rgba(239, 68, 68, 0.85)";
      ctx.lineWidth = 3;
      ctx.shadowColor = "#ef4444";
      ctx.shadowBlur = 14;
      ctx.beginPath();
      ctx.arc(0, 0, (c.radius + 8) * pulse, 0, Math.PI * 2);
      ctx.stroke();
      ctx.shadowBlur = 0;
    }

    // Stagger / Stun indicator stars
    if (c.state === "stagger" || c.isStaggered) {
      ctx.fillStyle = "#facc15";
      ctx.shadowColor = "#facc15";
      ctx.shadowBlur = 6;
      for (let s = 0; s < 3; s++) {
        const starAng = time * 0.15 + s * 2.09;
        const sx = Math.cos(starAng) * (c.radius + 6);
        const sy = Math.sin(starAng) * 4 - c.radius - 8;
        ctx.beginPath();
        ctx.arc(sx, sy, 2.5, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.shadowBlur = 0;
    }

    // Panic sweat drops
    if (c.state === "panic") {
      ctx.fillStyle = "#38bdf8";
      for (let w = 0; w < 2; w++) {
        const px = (w === 0 ? -6 : 6);
        const py = -c.radius - 10 + (time * 0.3 + w * 4) % 10;
        ctx.beginPath();
        ctx.arc(px, py, 2, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Captain Aura on Ground
    if (type === "captain" || c.isCaptain) {
      const auraPulse = 1 + Math.sin(time * 0.1) * 0.12;
      ctx.strokeStyle = "rgba(250, 204, 21, 0.65)";
      ctx.lineWidth = 2.5;
      ctx.setLineDash([6, 6]);
      ctx.beginPath();
      ctx.ellipse(0, c.radius + 2 - bob, 48 * auraPulse, 16 * auraPulse, 0, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Captain Buff Ring on Minions
    if (c.hasCaptainBuff) {
      ctx.strokeStyle = "rgba(234, 179, 8, 0.4)";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(0, 0, c.radius + 4, 0, Math.PI * 2);
      ctx.stroke();
    }

    // ARCHETYPE RENDERING:
    if (c.isBoss) {
      // --- EPIC BOSS SPRITES (Proportional scaling) ---
      const bScale = (c.radius || 44) / 28;
      ctx.save();
      ctx.scale(bScale, bScale);

      const bId = (c.bossType || c.boss_id || c.id || c.name || "").toLowerCase();
      let drawn = false;

      if (typeof RPG_ASSETS !== "undefined") {
        let assetKey = null;
        if (bId.includes("roshan") || bId.includes("рошан") || bId.includes("огненный демон")) assetKey = "roshan";
        else if (bId.includes("terrorblade") || bId.includes("террорблейд") || bId.includes("демон бездны")) assetKey = "terrorblade";
        else if (bId.includes("void") || bId.includes("хроно") || bId.includes("faceless") || bId.includes("хроно-владыка")) assetKey = "faceless_void";
        else if (bId.includes("мясник") || bId.includes("butcher")) assetKey = "butcher";
        else if (bId.includes("повелитель теней") || bId.includes("shadow")) assetKey = "shadow_lord";

        if (assetKey && RPG_ASSETS.bosses && RPG_ASSETS.bosses[assetKey]) {
          const bossAsset = RPG_ASSETS.bosses[assetKey];
          if (bossAsset && bossAsset.complete && bossAsset.naturalWidth > 0) {
            const size = 110; 
            ctx.drawImage(bossAsset, -size / 2, -size / 1.1, size, size);
            drawn = true;
          }
        }
      }

      if (!drawn && typeof drawBossModelEarly === "function") drawn = drawBossModelEarly(ctx, c, bId, time);
      if (!drawn && typeof drawBossModelMid === "function") drawn = drawBossModelMid(ctx, c, bId, time);
      if (!drawn && typeof drawBossModelLate === "function") drawn = drawBossModelLate(ctx, c, bId, time);

      if (!drawn) {
        // Fallback Colossus Brute
        ctx.fillStyle = "#334155";
        ctx.strokeStyle = "#ea580c";
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.ellipse(0, 0, 26, 22, 0, 0, Math.PI * 2);
        ctx.fill(); ctx.stroke();
        ctx.strokeStyle = "#f97316";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(-12, -8); ctx.lineTo(-2, 4); ctx.lineTo(14, -6);
        ctx.stroke();
      }
      ctx.restore();

    } else if (type.includes("defender")) {
      // --- SHIELDED DEFENDER (Пехотинец со щитом) ---
      // Heavy plate body
      ctx.fillStyle = "#334155";
      ctx.beginPath();
      ctx.rect(-8, -12, 16, 22);
      ctx.fill();
      // Helmet with narrow slit
      ctx.fillStyle = "#1e293b";
      ctx.beginPath();
      ctx.arc(0, -14, 8, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#facc15";
      ctx.fillRect(-4, -15, 6, 1.8);

      // Giant Tower Heater Shield (Facing Left towards player)
      const shieldBroken = c.shieldBrokenTimer > 0;
      ctx.save();
      ctx.translate(-10, 0);
      if (shieldBroken) {
        ctx.rotate(-0.4);
        ctx.strokeStyle = "#ef4444";
      } else {
        ctx.strokeStyle = "#38bdf8";
      }
      // Shield Face
      ctx.fillStyle = shieldBroken ? "#475569" : "#1e293b";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(0, -18);
      ctx.lineTo(-10, -16);
      ctx.lineTo(-10, 10);
      ctx.lineTo(0, 18);
      ctx.lineTo(6, 10);
      ctx.lineTo(6, -16);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();

      // Shield Cross / Crest
      ctx.fillStyle = shieldBroken ? "#991b1b" : "#eab308";
      ctx.fillRect(-6, -6, 8, 3);
      ctx.fillRect(-4, -10, 4, 11);

      // Guard Shield Sheen
      if (!shieldBroken) {
        ctx.fillStyle = "rgba(56, 189, 248, 0.25)";
        ctx.shadowColor = "#38bdf8";
        ctx.shadowBlur = 8;
        ctx.beginPath();
        ctx.arc(-5, 0, 14, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;
      }
      ctx.restore();

      // Spear behind shield
      ctx.strokeStyle = "#94a3b8";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(-16, -4); ctx.lineTo(12, -4);
      ctx.stroke();

    } else if (type.includes("ranged") || type.includes("mage") || type.includes("маг")) {
      // --- RANGED MAGE / ARCHER ---
      const isRadiant = type.includes("radiant") || type.includes("свет");
      // Robes
      ctx.fillStyle = isRadiant ? "#15803d" : "#581c87";
      ctx.beginPath();
      ctx.moveTo(-6, -10); ctx.lineTo(6, -10); ctx.lineTo(9, 15); ctx.lineTo(-9, 15);
      ctx.closePath();
      ctx.fill();

      // Pointed Hood
      ctx.fillStyle = isRadiant ? "#166534" : "#3b0764";
      ctx.beginPath();
      ctx.moveTo(-8, -8); ctx.lineTo(8, -8); ctx.lineTo(0, -22);
      ctx.closePath();
      ctx.fill();

      // Glowing Eyes in hood darkness
      ctx.fillStyle = isRadiant ? "#38bdf8" : "#f43f5e";
      ctx.shadowColor = ctx.fillStyle;
      ctx.shadowBlur = 6;
      ctx.fillRect(-4, -12, 2.5, 1.8);
      ctx.shadowBlur = 0;

      // Wooden Staff with Pulsing Magic Orb
      ctx.save();
      ctx.translate(-9, -2);
      ctx.strokeStyle = "#78350f";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(0, 16); ctx.lineTo(0, -18);
      ctx.stroke();

      // Pulsing magic orb at tip
      const orbPulse = 1 + Math.sin(time * 0.2) * 0.2;
      ctx.fillStyle = isRadiant ? "#38bdf8" : "#c084fc";
      ctx.shadowColor = ctx.fillStyle;
      ctx.shadowBlur = 10 * orbPulse;
      ctx.beginPath();
      ctx.arc(0, -22, 4.5 * orbPulse, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
      ctx.restore();

    } else if (type.includes("catapult") || type.includes("катапульта")) {
      // --- SIEGE CATAPULT ---
      // Heavy timber cart chassis
      ctx.fillStyle = "#78350f";
      ctx.fillRect(-14, -6, 28, 12);

      // Spiked wheels with spokes
      ctx.strokeStyle = "#451a03";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.arc(-8, 8, 6.5, 0, Math.PI * 2);
      ctx.arc(8, 8, 6.5, 0, Math.PI * 2);
      ctx.stroke();

      // Throwing arm with counterweight
      ctx.strokeStyle = "#92400e";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(8, -4); ctx.lineTo(-14, -18);
      ctx.stroke();

      // Flaming rock in bucket
      ctx.fillStyle = "#ea580c";
      ctx.shadowColor = "#f97316"; ctx.shadowBlur = 8;
      ctx.beginPath();
      ctx.arc(-15, -19, 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

        } else if (type.includes("warlock")) {
      // --- WARLOCK: Horned purple cowl, flaming obsidian staff, burning magma eye ---
      ctx.fillStyle = "#3b0764";
      ctx.beginPath();
      ctx.arc(0, -2, c.radius, 0, Math.PI * 2);
      ctx.fill();
      // Horns
      ctx.fillStyle = "#18181b";
      ctx.beginPath();
      ctx.moveTo(-c.radius * 0.6, -c.radius * 0.7);
      ctx.lineTo(-c.radius * 1.1, -c.radius * 1.4);
      ctx.lineTo(-c.radius * 0.3, -c.radius);
      ctx.moveTo(c.radius * 0.6, -c.radius * 0.7);
      ctx.lineTo(c.radius * 1.1, -c.radius * 1.4);
      ctx.lineTo(c.radius * 0.3, -c.radius);
      ctx.fill();
      // Flaming Eye
      ctx.fillStyle = "#ea580c";
      ctx.beginPath();
      ctx.arc(-3, -2, 3, 0, Math.PI * 2);
      ctx.arc(3, -2, 3, 0, Math.PI * 2);
      ctx.fill();
    } else if (type.includes("irongolem")) {
      // --- IRONCLAD GOLEM: Heavy gunmetal cubic plating with glowing magma core ---
      ctx.fillStyle = "#1e293b";
      ctx.fillRect(-c.radius * 0.9, -c.radius * 0.9, c.radius * 1.8, c.radius * 1.8);
      ctx.fillStyle = "#f97316";
      ctx.beginPath();
      ctx.arc(0, 0, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#475569";
      ctx.lineWidth = 2.5;
      ctx.strokeRect(-c.radius * 0.9, -c.radius * 0.9, c.radius * 1.8, c.radius * 1.8);
    } else if (type.includes("hound")) {
      // --- INFERNAL HOUND: Low feral quadruped, flame teeth ---
      ctx.fillStyle = "#450a0a";
      ctx.beginPath();
      ctx.ellipse(0, 0, c.radius * 1.2, c.radius * 0.7, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#dc2626";
      ctx.beginPath();
      ctx.arc(-c.radius * 0.8, -2, 3, 0, Math.PI * 2);
      ctx.fill();
    } else if (type.includes("necromancer")) {
      // --- NECROMANCER: Emerald bone skull mask ---
      ctx.fillStyle = "#022c22";
      ctx.beginPath();
      ctx.arc(0, -2, c.radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#10b981";
      ctx.beginPath();
      ctx.arc(-3, -3, 2.5, 0, Math.PI * 2);
      ctx.arc(3, -3, 2.5, 0, Math.PI * 2);
      ctx.fill();
    } else if (type.includes("assassin")) {
      // --- SHADOW BLADE ASSASSIN: Dark ninja with glowing violet daggers ---
      ctx.fillStyle = "#0f172a";
      ctx.beginPath();
      ctx.arc(0, -3, c.radius * 0.85, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#c084fc";
      ctx.fillRect(-c.radius - 4, -1, 6, 2);
      ctx.fillRect(c.radius - 2, -1, 6, 2);
    } else if (type.includes("centaur_conqueror")) {
      // --- CENTAUR CONQUEROR: Golden plate, battleaxe ---
      ctx.fillStyle = "#78350f";
      ctx.beginPath();
      ctx.ellipse(0, 2, c.radius * 1.2, c.radius * 0.8, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#facc15";
      ctx.fillRect(-c.radius * 0.5, -c.radius - 2, c.radius, 8);
    } else if (type.includes("drake")) {
      // --- INFERNAL DRAKE: Wings and fiery snout ---
      ctx.fillStyle = "#9a3412";
      ctx.beginPath();
      ctx.arc(0, -4, c.radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#ea580c";
      ctx.beginPath();
      ctx.moveTo(-c.radius * 1.2, -6);
      ctx.lineTo(-c.radius * 0.3, -c.radius);
      ctx.lineTo(-c.radius * 0.3, 0);
      ctx.moveTo(c.radius * 1.2, -6);
      ctx.lineTo(c.radius * 0.3, -c.radius);
      ctx.lineTo(c.radius * 0.3, 0);
      ctx.fill();
    } else if (type.includes("void_terror")) {
      // --- VOID TERROR: Cosmic dark eye with violet rings ---
      ctx.fillStyle = "#1e1b4b";
      ctx.beginPath();
      ctx.arc(0, 0, c.radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#818cf8";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.ellipse(0, 0, c.radius + 5, c.radius * 0.4, time * 0.05, 0, Math.PI * 2);
      ctx.stroke();
    } else if (type.includes("ancient_titan")) {
      // --- ANCIENT EARTH TITAN: Giant granite colossus with cyan runes ---
      ctx.fillStyle = "#334155";
      ctx.beginPath();
      ctx.arc(0, 0, c.radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#38bdf8";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.moveTo(-c.radius * 0.5, 0);
      ctx.lineTo(0, -c.radius * 0.6);
      ctx.lineTo(c.radius * 0.5, 0);
      ctx.stroke();
    } else if (type.includes("apocalypse_doomguard")) {
      // --- APOCALYPSE DOOMGUARD: Towering winged demon lord ---
      ctx.fillStyle = "#7f1d1d";
      ctx.beginPath();
      ctx.arc(0, -4, c.radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#dc2626";
      ctx.beginPath();
      ctx.moveTo(-c.radius * 1.4, -c.radius);
      ctx.lineTo(-c.radius * 0.4, 0);
      ctx.lineTo(-c.radius * 0.4, -c.radius * 0.5);
      ctx.moveTo(c.radius * 1.4, -c.radius);
      ctx.lineTo(c.radius * 0.4, 0);
      ctx.lineTo(c.radius * 0.4, -c.radius * 0.5);
      ctx.fill();
    } else if (type.includes("astral_phantom")) {
      // --- ASTRAL PHANTOM: Cyan translucent luminous ghost ---
      ctx.fillStyle = "rgba(56, 189, 248, 0.75)";
      ctx.beginPath();
      ctx.arc(0, -2, c.radius, 0, Math.PI * 2);
      ctx.fill();
    } else if (type.includes("captain") || c.isCaptain) {
      // --- ELITE CAPTAIN ---
      // Golden armor
      ctx.fillStyle = "#b45309";
      ctx.strokeStyle = "#facc15";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.rect(-9, -10, 18, 20);
      ctx.fill(); ctx.stroke();

      // Winged Helmet
      ctx.fillStyle = "#1e293b";
      ctx.beginPath();
      ctx.arc(0, -14, 8, 0, Math.PI * 2);
      ctx.fill();
      // Wings on helm
      ctx.fillStyle = "#facc15";
      ctx.beginPath();
      ctx.moveTo(-6, -16); ctx.lineTo(-15, -24); ctx.lineTo(-6, -20);
      ctx.moveTo(6, -16); ctx.lineTo(15, -24); ctx.lineTo(6, -20);
      ctx.fill();

      // Royal standard / war banner on back
      ctx.strokeStyle = "#78350f"; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(6, 10); ctx.lineTo(6, -30); ctx.stroke();
      ctx.fillStyle = "#dc2626";
      ctx.beginPath();
      ctx.moveTo(6, -30); ctx.lineTo(24, -24); ctx.lineTo(6, -18);
      ctx.closePath();
      ctx.fill();

      // Dual swords
      ctx.strokeStyle = "#f8fafc";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(-4, 0); ctx.lineTo(-18, -8);
      ctx.moveTo(2, 4); ctx.lineTo(-14, 14);
      ctx.stroke();

    } else {
      // --- MELEE GRUNTS (Radiant / Dire) ---
      const isDire = type.includes("dire") || type.includes("тьма");
      if (isDire) {
        // Dire Ghoul / Fiend
        ctx.fillStyle = "#450a0a";
        ctx.beginPath();
        ctx.ellipse(0, 0, 11, 14, -0.2, 0, Math.PI * 2);
        ctx.fill();
        // Spiked black iron shoulder
        ctx.fillStyle = "#18181b";
        ctx.beginPath();
        ctx.moveTo(2, -12); ctx.lineTo(10, -20); ctx.lineTo(6, -8);
        ctx.closePath();
        ctx.fill();
        // Burning red eye
        ctx.fillStyle = "#ef4444";
        ctx.shadowColor = "#ef4444"; ctx.shadowBlur = 6;
        ctx.fillRect(-7, -8, 3, 2);
        ctx.shadowBlur = 0;
        // Dual jagged rusted axes
        ctx.strokeStyle = "#94a3b8"; ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(-2, 0); ctx.lineTo(-15, -6);
        ctx.stroke();
      } else {
        // Radiant Swordsman
        ctx.fillStyle = "#166534";
        ctx.beginPath();
        ctx.ellipse(0, 0, 11, 13, 0.1, 0, Math.PI * 2);
        ctx.fill();
        // Round oak shield
        ctx.fillStyle = "#78350f"; ctx.strokeStyle = "#d97706"; ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(-7, 2, 7.5, 0, Math.PI * 2);
        ctx.fill(); ctx.stroke();
        // Short iron sword
        ctx.strokeStyle = "#cbd5e1"; ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(2, 0); ctx.lineTo(12, -12);
        ctx.stroke();
      }
    }

    // Telegraph indicator (danger icon / raised weapon flash)
    if (c.state === "telegraph") {
      ctx.strokeStyle = "#ef4444";
      ctx.lineWidth = 2;
      ctx.shadowColor = "#ef4444";
      ctx.shadowBlur = 9;
      ctx.beginPath();
      ctx.arc(0, 0, c.radius + 5, 0, Math.PI * 2);
      ctx.stroke();
      ctx.shadowBlur = 0;
    }

    ctx.restore();
  }

  // ===========================================================================
  // PROCEDURAL ALLIED MINION (WK Skeleton)
  // ===========================================================================

  function drawProceduralMinion(ctx, m, time = (ARENA.frameCount || 0)) {
    time = (time != null ? time : (ARENA.frameCount || 0));
    const bob = Math.sin(time * 0.2 + m.x * 0.1) * 1.5;
    ctx.save();
    ctx.translate(m.x, m.y + bob);

    // Shadow
    ctx.fillStyle = "rgba(0,0,0,0.28)";
    ctx.beginPath();
    ctx.ellipse(0, m.radius + 2, m.radius * 0.8, 3.5, 0, 0, Math.PI * 2);
    ctx.fill();

    // Ivory ribcage
    ctx.strokeStyle = "#e2e8f0";
    ctx.lineWidth = 1.8;
    ctx.beginPath();
    ctx.moveTo(0, -6); ctx.lineTo(0, 6);
    ctx.moveTo(-5, -3); ctx.lineTo(5, -3);
    ctx.moveTo(-4, 0); ctx.lineTo(4, 0);
    ctx.moveTo(-3, 3); ctx.lineTo(3, 3);
    ctx.stroke();

    // Skull
    ctx.fillStyle = "#f8fafc";
    ctx.beginPath();
    ctx.arc(0, -10, 5.5, 0, Math.PI * 2);
    ctx.fill();

    // Glowing turquoise eyes
    ctx.fillStyle = "#2dd4bf";
    ctx.shadowColor = "#2dd4bf";
    ctx.shadowBlur = 6;
    ctx.fillRect(-2, -11, 1.6, 1.6);
    ctx.fillRect(1, -11, 1.6, 1.6);
    ctx.shadowBlur = 0;

    // Rusted blade
    ctx.strokeStyle = "#94a3b8";
    ctx.lineWidth = 1.8;
    ctx.beginPath();
    ctx.moveTo(4, 0); ctx.lineTo(14, -6);
    ctx.stroke();

    ctx.restore();
  }

  // ===========================================================================
  // PROCEDURAL PICKUPS: COINS, GEMS, CHESTS
  // ===========================================================================

  function drawProceduralCoin(ctx, x, y, radius, time = (ARENA.frameCount || 0)) {
    time = (time != null ? time : (ARENA.frameCount || 0));
    ctx.save();
    ctx.translate(x, y);

    // Beveled 3D Gold Rim
    ctx.fillStyle = "#b45309";
    ctx.beginPath();
    ctx.arc(0, 0, radius, 0, Math.PI * 2);
    ctx.fill();

    // Inner Radiant Gold Face
    ctx.fillStyle = "#facc15";
    ctx.beginPath();
    ctx.arc(0, 0, radius * 0.82, 0, Math.PI * 2);
    ctx.fill();

    // Embossed center star / crest
    ctx.fillStyle = "#eab308";
    ctx.beginPath();
    ctx.moveTo(0, -radius * 0.5);
    ctx.lineTo(radius * 0.35, 0);
    ctx.lineTo(0, radius * 0.5);
    ctx.lineTo(-radius * 0.35, 0);
    ctx.closePath();
    ctx.fill();

    // Rotating specular sparkle glint
    const glintAng = time * 0.08;
    const gx = Math.cos(glintAng) * (radius * 0.45);
    const gy = Math.sin(glintAng) * (radius * 0.45);
    ctx.fillStyle = "#ffffff";
    ctx.beginPath();
    ctx.arc(gx, gy, radius * 0.22, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
  }

  function drawProceduralGem(ctx, x, y, radius, colorHex, time = (ARENA.frameCount || 0)) {
    time = (time != null ? time : (ARENA.frameCount || 0));
    ctx.save();
    ctx.translate(x, y);
    const col = colorHex || "#38bdf8";

    // Glowing faceted diamond polygon
    ctx.fillStyle = col;
    ctx.shadowColor = col;
    ctx.shadowBlur = 8;
    ctx.beginPath();
    ctx.moveTo(0, -radius);
    ctx.lineTo(radius * 0.85, -radius * 0.35);
    ctx.lineTo(0, radius);
    ctx.lineTo(-radius * 0.85, -radius * 0.35);
    ctx.closePath();
    ctx.fill();
    ctx.shadowBlur = 0;

    // Specular facet
    ctx.fillStyle = "rgba(255, 255, 255, 0.65)";
    ctx.beginPath();
    ctx.moveTo(0, -radius);
    ctx.lineTo(radius * 0.4, -radius * 0.35);
    ctx.lineTo(0, 0);
    ctx.closePath();
    ctx.fill();

    ctx.restore();
  }

  function drawProceduralChest(ctx, x, y, time = (ARENA.frameCount || 0), isLanded, isOpened) {
    time = (time != null ? time : (ARENA.frameCount || 0));
    ctx.save();
    ctx.translate(x, y);

    // God Ray Light Pillar when landed
    if (isLanded) {
      const rayAlpha = 0.22 + Math.sin(time * 0.06) * 0.08;
      const grad = ctx.createLinearGradient(0, 0, 0, -220);
      grad.addColorStop(0, `rgba(250, 204, 21, ${rayAlpha * 1.5})`);
      grad.addColorStop(1, "rgba(250, 204, 21, 0)");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.moveTo(-24, 0); ctx.lineTo(24, 0); ctx.lineTo(38, -220); ctx.lineTo(-38, -220);
      ctx.closePath();
      ctx.fill();
    }

    // Shadow
    ctx.fillStyle = "rgba(0,0,0,0.4)";
    ctx.beginPath();
    ctx.ellipse(0, 12, 22, 6, 0, 0, Math.PI * 2);
    ctx.fill();

    // Wooden Chest Base
    ctx.fillStyle = "#78350f";
    ctx.strokeStyle = "#b45309";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.roundRect(-16, -6, 32, 20, 3);
    ctx.fill();
    ctx.stroke();

    // Iron Banding & Corner Brackets
    ctx.fillStyle = "#eab308";
    ctx.fillRect(-16, -6, 4, 20);
    ctx.fillRect(12, -6, 4, 20);
    ctx.fillRect(-2, -6, 4, 20);

    // Lid (Closed or Tilted Open)
    if (isOpened) {
      ctx.save();
      ctx.translate(-16, -6);
      ctx.rotate(-0.8);
      ctx.fillStyle = "#92400e";
      ctx.strokeStyle = "#facc15";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.roundRect(0, -10, 34, 10, 3);
      ctx.fill(); ctx.stroke();
      ctx.restore();

      // Golden Treasure Rays pouring from open chest
      ctx.fillStyle = "rgba(250, 204, 21, 0.45)";
      ctx.shadowColor = "#facc15"; ctx.shadowBlur = 12;
      ctx.beginPath();
      ctx.arc(0, -4, 8, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
    } else {
      ctx.fillStyle = "#92400e";
      ctx.strokeStyle = "#eab308";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.roundRect(-17, -15, 34, 11, [4, 4, 0, 0]);
      ctx.fill(); ctx.stroke();

      // Brass Keyhole Lock
      ctx.fillStyle = "#facc15";
      ctx.beginPath();
      ctx.arc(0, -4, 3.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#1e293b";
      ctx.fillRect(-1, -4, 2, 4);
    }

    ctx.restore();
  }

  // ===========================================================================
  // PROCEDURAL ENVIRONMENT: TREES & CLOUDS
  // ===========================================================================

  function drawProceduralTree(ctx, x, y, time = (ARENA.frameCount || 0)) {
    time = (time != null ? time : (ARENA.frameCount || 0));
    ctx.save();
    ctx.translate(x, y);

    // Gnarled Trunk
    ctx.fillStyle = "#5c3a21";
    ctx.beginPath();
    ctx.moveTo(-5, 0); ctx.lineTo(-3, -22); ctx.lineTo(3, -22); ctx.lineTo(6, 0);
    ctx.closePath();
    ctx.fill();

    // Ambient Leaf Sway
    const sway = Math.sin(time * 0.04 + x * 0.1) * 2;

    // Multi-tiered Lush Foliage Canopies
    ctx.fillStyle = "#166534";
    ctx.beginPath();
    ctx.arc(sway, -34, 16, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = "#15803d";
    ctx.beginPath();
    ctx.arc(-8 + sway * 0.8, -26, 12, 0, Math.PI * 2);
    ctx.arc(8 + sway * 0.8, -26, 12, 0, Math.PI * 2);
    ctx.fill();

    // Sunlit Top Leaf Highlights
    ctx.fillStyle = "#22c55e";
    ctx.beginPath();
    ctx.arc(sway, -40, 8, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
  }

  function drawProceduralCloud(ctx, cloud) {
    ctx.save();
    ctx.fillStyle = "rgba(255, 255, 255, 0.42)";
    ctx.beginPath();
    ctx.arc(cloud.x, cloud.y, 14, 0, Math.PI * 2);
    ctx.arc(cloud.x + 12, cloud.y - 5, 17, 0, Math.PI * 2);
    ctx.arc(cloud.x + 26, cloud.y, 13, 0, Math.PI * 2);
    ctx.arc(cloud.x + 14, cloud.y + 4, 12, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  // ===========================================================================
  // DEVIL MAY CRY STYLE METER HUD (D, C, B, A, S, SS, SSS)
  // ===========================================================================

  function drawStyleMeterHUD(ctx, styleMeter, combo, customW) {
    if (!styleMeter) return;
    const rank = styleMeter.rank || "D";
    const w = customW || ARENA.width || 360;
    const x = Math.round(w / 2);
    const y = 30;

    const rankColors = {
      D: { text: "#94a3b8", glow: "#64748b" },
      C: { text: "#06b6d4", glow: "#0891b2" },
      B: { text: "#10b981", glow: "#059669" },
      A: { text: "#f59e0b", glow: "#d97706" },
      S: { text: "#f97316", glow: "#ea580c" },
      SS: { text: "#ef4444", glow: "#dc2626" },
      SSS: { text: "#f43f5e", glow: "#e11d48" }
    };
    const cfg = rankColors[rank] || rankColors.D;

    ctx.save();
    // Glass HUD Backplate
    ctx.fillStyle = "rgba(15, 23, 42, 0.78)";
    ctx.strokeStyle = cfg.text;
    ctx.lineWidth = 1.5;
    ctx.shadowColor = cfg.glow;
    ctx.shadowBlur = 8;
    ctx.beginPath();
    safeRoundRect(ctx, x - 38, y - 17, 76, 34, 8);
    ctx.fill();
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Glowing Rank Letter
    ctx.font = "900 22px 'Impact', sans-serif";
    ctx.fillStyle = cfg.text;
    ctx.shadowColor = cfg.glow;
    ctx.shadowBlur = 10;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(rank, x - 16, y);
    ctx.shadowBlur = 0;

    // Style Meter Progress Bar
    const prog = Math.max(0, Math.min(1, styleMeter.progress || 0));
    ctx.fillStyle = "rgba(0,0,0,0.6)";
    ctx.fillRect(x - 4, y - 5, 36, 4);
    ctx.fillStyle = cfg.text;
    ctx.fillRect(x - 4, y - 5, 36 * prog, 4);

    // Combo Counter (if active)
    if (combo && combo.count > 1) {
      ctx.font = "italic 800 8.5px sans-serif";
      ctx.fillStyle = "#facc15";
      ctx.fillText(`${combo.count} COMBO!`, x + 14, y + 6);
    } else {
      ctx.font = "bold 7px sans-serif";
      ctx.fillStyle = "#94a3b8";
      ctx.fillText("STYLE", x + 14, y + 6);
    }

    ctx.restore();
  }

  // ===========================================================================
  // PROCEDURAL PROJECTILES (NO EMOJIS)
  // ===========================================================================

  function drawProceduralProjectile(ctx, proj, time = (ARENA.frameCount || 0)) {
    time = (time != null ? time : (ARENA.frameCount || 0));
    ctx.save();
    ctx.translate(proj.x, proj.y);

    if (proj.type === "meteor") {
      // --- INVOKER CHAOS METEOR (Пылающая «Котлета») ---
      const r = proj.radius || 34;

      // 1. Draw Burn Trail behind in local coords
      if (proj.burnTrail) {
        for (const tr of proj.burnTrail) {
          const relX = tr.x - proj.x;
          const relY = tr.y - proj.y;
          const trAlpha = Math.min(1.0, tr.timer / 80);
          ctx.fillStyle = `rgba(234, 88, 12, ${0.45 * trAlpha})`;
          ctx.beginPath();
          ctx.ellipse(relX, relY, 20, 6, 0, 0, Math.PI * 2);
          ctx.fill();
          // Inner ember
          ctx.fillStyle = `rgba(254, 240, 138, ${0.7 * trAlpha})`;
          ctx.beginPath();
          ctx.arc(relX + (Math.sin(tr.timer * 0.3) * 6), relY - 2, 2.5, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      ctx.rotate(proj.angle || (time * 0.12));

      // 2. Fiery Magma Aura / Outer Blaze
      ctx.fillStyle = "rgba(234, 88, 12, 0.45)";
      ctx.shadowColor = "#f97316";
      ctx.shadowBlur = 24;
      ctx.beginPath();
      ctx.arc(0, 0, r + 7, 0, Math.PI * 2);
      ctx.fill();

      // 3. Molten Volcanic Rock Body (Charred dark obsidian stone)
      ctx.fillStyle = "#1c1917";
      ctx.beginPath();
      ctx.arc(0, 0, r, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

      // 4. Glowing Magma Veins & Lava Cracks
      ctx.strokeStyle = "#f97316";
      ctx.lineWidth = 3.5;
      ctx.beginPath();
      ctx.moveTo(-r * 0.7, -r * 0.3);
      ctx.lineTo(-r * 0.2, 0);
      ctx.lineTo(r * 0.3, -r * 0.4);
      ctx.lineTo(r * 0.8, -r * 0.1);
      ctx.moveTo(-r * 0.3, r * 0.5);
      ctx.lineTo(0, r * 0.2);
      ctx.lineTo(r * 0.4, r * 0.6);
      ctx.stroke();

      // White-hot inner crack lines
      ctx.strokeStyle = "#fef08a";
      ctx.lineWidth = 1.6;
      ctx.beginPath();
      ctx.moveTo(-r * 0.2, 0);
      ctx.lineTo(r * 0.3, -r * 0.4);
      ctx.stroke();

      // Molten craters
      ctx.fillStyle = "#ea580c";
      ctx.beginPath();
      ctx.arc(-r * 0.35, -r * 0.2, 5, 0, Math.PI * 2);
      ctx.arc(r * 0.2, r * 0.3, 5.5, 0, Math.PI * 2);
      ctx.arc(-r * 0.1, r * 0.45, 4, 0, Math.PI * 2);
      ctx.fill();

      // White-hot crater centers
      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.arc(-r * 0.35, -r * 0.2, 2, 0, Math.PI * 2);
      ctx.arc(r * 0.2, r * 0.3, 2.2, 0, Math.PI * 2);
      ctx.fill();

    } else if (proj.type === "wind_blade") {
      // Crescent Wind Blade / Cleave Wave
      const col = proj.color || "#facc15";
      const rad = proj.radius || 20;
      ctx.shadowColor = col;
      ctx.shadowBlur = proj.isHeavy ? 16 : 10;
      ctx.strokeStyle = col;
      ctx.lineWidth = proj.isHeavy ? 5 : 3.5;
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.arc(0, 0, rad, -Math.PI * 0.45, Math.PI * 0.45);
      ctx.stroke();

      // Bright inner core
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 1.8;
      ctx.beginPath();
      ctx.arc(0, 0, rad - 2, -Math.PI * 0.35, Math.PI * 0.35);
      ctx.stroke();

      // Trailing wind sparks
      ctx.fillStyle = col;
      ctx.beginPath();
      ctx.arc(-rad * 0.4, -rad * 0.3, 2, 0, Math.PI * 2);
      ctx.arc(-rad * 0.4, rad * 0.3, 2, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

    } else if (proj.type === "dagger" || proj.type === "companion_dagger") {
      // Throwing Dagger (PA / Squad Companion)
      ctx.rotate(Math.atan2(proj.vy || 0, proj.vx || 1) || 0);
      const isCrit = !!proj.isCrit;
      // Trail
      ctx.strokeStyle = isCrit ? "rgba(239, 68, 68, 0.65)" : "rgba(34, 211, 238, 0.5)";
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.moveTo(-16, 0); ctx.lineTo(0, 0);
      ctx.stroke();

      // Steel blade
      ctx.fillStyle = "#e2e8f0";
      ctx.strokeStyle = "#22d3ee";
      ctx.lineWidth = 1.5;
      ctx.shadowColor = "#22d3ee";
      ctx.shadowBlur = 8;
      ctx.beginPath();
      ctx.moveTo(8, 0); ctx.lineTo(-4, -4); ctx.lineTo(-4, 4);
      ctx.closePath();
      ctx.fill(); ctx.stroke();
      ctx.shadowBlur = 0;

    } else if (proj.isBossFireball || proj.type === "fireball") {
      // Blazing Boss Fireball
      ctx.fillStyle = "#f97316";
      ctx.shadowColor = "#ea580c";
      ctx.shadowBlur = 14;
      ctx.beginPath();
      ctx.arc(0, 0, 8, 0, Math.PI * 2);
      ctx.fill();
      // White hot core
      ctx.fillStyle = "#fef08a";
      ctx.beginPath();
      ctx.arc(0, 0, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

      // Trailing flame wisps
      ctx.fillStyle = "rgba(234, 88, 12, 0.6)";
      for (let f = 0; f < 3; f++) {
        const fx = 8 + (time * 0.5 + f * 4) % 12;
        const fy = Math.sin(time * 0.3 + f) * 3;
        ctx.beginPath();
        ctx.arc(fx, fy, 3.5 - f * 0.8, 0, Math.PI * 2);
        ctx.fill();
      }

    } else if (proj.type === "topdown_shot") {
      const ang = Math.atan2(proj.vy || 0, proj.vx || 1);
      ctx.rotate(ang);
      const col = proj.color || (proj.isCrit ? "#f59e0b" : "#38bdf8");
      ctx.fillStyle = col;
      ctx.shadowColor = col;
      ctx.shadowBlur = proj.isCrit ? 16 : 10;
      ctx.beginPath();
      ctx.ellipse(0, 0, (proj.radius || 6) * 1.5, (proj.radius || 6) * 0.85, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.ellipse(2, 0, (proj.radius || 6) * 0.75, (proj.radius || 6) * 0.45, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
      ctx.fillStyle = col;
      ctx.beginPath();
      ctx.arc(-8, 0, 3, 0, Math.PI * 2);
      ctx.arc(-14, 0, 1.8, 0, Math.PI * 2);
      ctx.fill();
    } else if (proj.reflected) {
      // REFLECTED RADIANT GOLDEN BOLT
      ctx.fillStyle = "#facc15";
      ctx.shadowColor = "#facc15";
      ctx.shadowBlur = 16;
      ctx.beginPath();
      ctx.arc(0, 0, 7.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.arc(0, 0, 3.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

      // Speed streak
      ctx.strokeStyle = "rgba(250, 204, 21, 0.75)";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(-16, 0); ctx.lineTo(0, 0);
      ctx.stroke();

    } else {
      // General Magic Bolt (Player or Enemy Caster)
      const col = proj.color || "#38bdf8";
      ctx.fillStyle = col;
      ctx.shadowColor = col;
      ctx.shadowBlur = 10;
      ctx.beginPath();
      ctx.arc(0, 0, 5.5, 0, Math.PI * 2);
      ctx.fill();
      // Bright center
      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.arc(0, 0, 2.2, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

      // Sparkle tail
      const dir = (proj.speed && proj.speed < 0) ? -1 : 1;
      ctx.fillStyle = col;
      ctx.beginPath();
      ctx.arc(-dir * 7, 0, 3, 0, Math.PI * 2);
      ctx.arc(-dir * 12, 0, 1.8, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.restore();
  }


    function renderGrandBossHUD(ctx, w, h, boss, time) {
    if (!boss) return;

    const bannerX = 8;
    const bannerY = 56; // Опустили вниз, чтобы не перекрывалось кнопками (было 7)
    const bannerW = w - 16;
    const bannerH = 48;

    // Background Ornate Slate Box
    ctx.save();
    ctx.fillStyle = "rgba(15, 23, 42, 0.94)";
    ctx.beginPath();
    safeRoundRect(ctx, bannerX, bannerY, bannerW, bannerH, 12);
    ctx.fill();

      const isGod = boss.isGodMode || boss.enrageStage === "god_mode";
    ctx.strokeStyle = isGod ? "#ef4444" : (boss.enraged ? "#f97316" : (boss.isStaggered ? "#ec4899" : "#f59e0b"));
    ctx.lineWidth = isGod ? 2.5 : 1.8;
    ctx.beginPath();
    safeRoundRect(ctx, bannerX, bannerY, bannerW, bannerH, 12);
    ctx.stroke();

    // 1. Top Row: Title & Party Mode Toggle
    ctx.font = "bold 10px sans-serif";
    ctx.fillStyle = isGod ? "#ef4444" : (boss.enraged ? "#f87171" : "#facc15");
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    let enrageLabel = "";
    const elapsedSec = Math.floor((Date.now() - (boss.battleStartTime || Date.now())) / 1000);
    const remSec = Math.max(0, 300 - elapsedSec);
    const remM = Math.floor(remSec / 60);
    const remS = remSec % 60;
    const timerStr = `${remM}:${remS < 10 ? "0" : ""}${remS}`;

    if (isGod) {
      enrageLabel = "💀 РЕЖИМ БОГА!";
    } else if (boss.enrageStage === "enraged" || boss.enraged) {
      enrageLabel = `🔥 БЕЗУМИЕ (${timerStr})`;
    } else if (boss.enrageStage === "furious") {
      enrageLabel = `⚡ ЯРОСТЬ (${timerStr})`;
    } else if (boss.enrageStage === "angry") {
      enrageLabel = `😡 ЗЛОЙ (${timerStr})`;
    } else {
      enrageLabel = `⏱️ ${timerStr}`;
    }
    const bossTitle = `👑 ${boss.name || "БОСС"} • ${enrageLabel}`;
    ctx.fillText(bossTitle.length > 28 ? bossTitle.slice(0, 27) + "…" : bossTitle, bannerX + 10, bannerY + 11);

    // Party Button on Canvas HUD
    const btnW = 86;
    const btnH = 18;
    const btnX = bannerX + bannerW - btnW - 6;
    const btnY = bannerY + 3;
    const isTrio = (ARENA.bossPartyMode || "trio") === "trio";

    ctx.fillStyle = isTrio ? "rgba(16, 185, 129, 0.25)" : "rgba(168, 85, 247, 0.25)";
    ctx.beginPath();
    safeRoundRect(ctx, btnX, btnY, btnW, btnH, 6);
    ctx.fill();

    ctx.strokeStyle = isTrio ? "#10b981" : "#a855f7";
    ctx.lineWidth = 1;
    ctx.beginPath();
    safeRoundRect(ctx, btnX, btnY, btnW, btnH, 6);
    ctx.stroke();

    ctx.font = "bold 9px sans-serif";
    ctx.fillStyle = isTrio ? "#6ee7b7" : "#d8b4fe";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(isTrio ? "👥 Отряд: 3" : "👤 Бой: Соло", btnX + btnW / 2, btnY + btnH / 2);
    ARENA._partyBtnBounds = { x: btnX, y: btnY, w: btnW, h: btnH };

    // 2. Main Boss HP Bar
    const hpBarX = bannerX + 10;
    const hpBarY = bannerY + 22;
    const hpBarW = bannerW - 20;
    const hpBarH = 12;
    const hpPct = Math.max(0, Math.min(1, boss.hp / boss.maxHp));

    ctx.fillStyle = "rgba(0, 0, 0, 0.75)";
    ctx.beginPath();
    safeRoundRect(ctx, hpBarX, hpBarY, hpBarW, hpBarH, 4);
    ctx.fill();

    // HP Fill Gradient
    const hpGrad = ctx.createLinearGradient(hpBarX, 0, hpBarX + hpBarW, 0);
    if (isGod) {
      hpGrad.addColorStop(0, "#7f1d1d");
      hpGrad.addColorStop(0.5, "#ef4444");
      hpGrad.addColorStop(1, "#b91c1c");
    } else if (boss.enraged) {
      hpGrad.addColorStop(0, "#ea580c");
      hpGrad.addColorStop(1, "#dc2626");
    } else {
      hpGrad.addColorStop(0, "#dc2626");
      hpGrad.addColorStop(1, "#b91c1c");
    }
    ctx.fillStyle = hpGrad;
    ctx.beginPath();
    safeRoundRect(ctx, hpBarX, hpBarY, hpBarW * hpPct, hpBarH, 4);
    ctx.fill();

    // HP Text
    ctx.font = "bold 8.5px sans-serif";
    ctx.fillStyle = "#ffffff";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.shadowColor = "#000000";
    ctx.shadowBlur = 4;
    ctx.fillText(`${formatCompact(boss.hp)} / ${formatCompact(boss.maxHp)} (${Math.ceil(hpPct * 100)}%)`, hpBarX + hpBarW / 2, hpBarY + hpBarH / 2);
    ctx.shadowBlur = 0;

    // 3. Poise / Stagger Bar & Badges
    const poiseBarX = hpBarX;
    const poiseBarY = hpBarY + hpBarH + 3;
    const poiseBarW = hpBarW - 100;
    const poiseBarH = 5;
    const poiseVal = boss.poise !== undefined ? boss.poise : 300;
    const poiseMax = boss.maxPoise || 300;
    const poisePct = Math.max(0, Math.min(1, poiseVal / poiseMax));

    ctx.fillStyle = "rgba(0, 0, 0, 0.65)";
    ctx.beginPath();
    safeRoundRect(ctx, poiseBarX, poiseBarY, poiseBarW, poiseBarH, 2.5);
    ctx.fill();

    ctx.fillStyle = boss.isStaggered ? "#ec4899" : "#f59e0b";
    ctx.beginPath();
    safeRoundRect(ctx, poiseBarX, poiseBarY, poiseBarW * (boss.isStaggered ? 1.0 : poisePct), poiseBarH, 2.5);
    ctx.fill();

    // Poise / Stagger Label
    ctx.font = "bold 7px sans-serif";
    ctx.fillStyle = boss.isStaggered ? "#f472b6" : "#fde68a";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillText(boss.isStaggered ? "💫 ОШЕЛОМЛЕН (+150%)!" : `⚡ БАЛАНС ${Math.ceil(poiseVal)}/${poiseMax}`, poiseBarX + 4, poiseBarY + poiseBarH / 2);

    // Badges on the right of poise bar
    let badgeX = poiseBarX + poiseBarW + 6;
    if (isGod) {
      ctx.fillStyle = "#ef4444";
      ctx.font = "bold 7.5px sans-serif";
      ctx.fillText("⚡ БОГ", badgeX, poiseBarY + poiseBarH / 2);
      badgeX += 34;
    } else if (boss.enraged) {
      ctx.fillStyle = "#ef4444";
      ctx.font = "bold 7.5px sans-serif";
      ctx.fillText("🔥 ЯРОСТЬ", badgeX, poiseBarY + poiseBarH / 2);
      badgeX += 46;
    }
    if (boss.tormentorShield) {
      ctx.fillStyle = "#c084fc";
      ctx.font = "bold 7.5px sans-serif";
      ctx.fillText("🔮 ЩИТ", badgeX, poiseBarY + poiseBarH / 2);
    }

    ctx.restore();
  }


  function renderArena() {
    const canvas = document.getElementById("rpg-action-canvas");
    if (!canvas) return;

    const isTopDown = !!(ARENA.topDownMode || ARENA.isRaidBossBattle);
    const expectedClientH = isTopDown ? 520 : 320;
    const curClientW = canvas.clientWidth;

    if (ARENA.canvas !== canvas || !ARENA.ctx ||
        (curClientW > 50 && Math.abs(curClientW - (ARENA.cachedClientW || 0)) > 2) ||
        (ARENA.cachedClientH !== expectedClientH)) {
      bindArenaCanvas(canvas);
    }

    const ctx = ARENA.ctx;
    if (!ctx) return;
    const clientW = ARENA.cachedClientW || (canvas.clientWidth > 50 ? canvas.clientWidth : 360);
    const clientH = ARENA.cachedClientH || (isTopDown ? 520 : 320);
    const w = ARENA.width || clientW || 360;
    const h = ARENA.height || clientH || 320;
    const time = ARENA.frameCount || 0;

    // Camera Trauma Shake (Subtle, crisp impact feel without violent earthquake)
    let shakeX = 0, shakeY = 0;
    if (ARENA.cameraTrauma > 0) {
      ARENA.cameraTrauma = Math.max(0, ARENA.cameraTrauma - 0.08);
      const shake = Math.pow(ARENA.cameraTrauma, 2) * 3.5;
      shakeX = (Math.random() * 2 - 1) * shake;
      shakeY = (Math.random() * 2 - 1) * shake;
    }
    ctx.save();
    ctx.translate(shakeX, shakeY);

    // Camera Zoom-Out in Top-Down mode: scale 520x720 arena to fit screen (zoom ~0.69)
    if (ARENA.topDownMode || ARENA.isRaidBossBattle) {
      const zoom = Math.min(clientW / 520, clientH / 720);
      const offX = (clientW - 520 * zoom) / 2;
      const offY = (clientH - 720 * zoom) / 2;

      ctx.translate(offX, offY);
      ctx.scale(zoom, zoom);

      // Deep Obsidian Floor filling 520x720 arena
      ctx.fillStyle = "#09090b";
      ctx.fillRect(-60, -60, 520 + 120, 720 + 120);

      // 2. Tactical Tile Grid (Batched single path stroke for 60 FPS performance)
      ctx.strokeStyle = "rgba(71, 85, 105, 0.20)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let tx = 0; tx <= 520; tx += 44) {
        ctx.moveTo(tx, 0); ctx.lineTo(tx, 720);
      }
      for (let ty = 0; ty <= 720; ty += 44) {
        ctx.moveTo(0, ty); ctx.lineTo(520, ty);
      }
      ctx.stroke();

      // 3. Glowing Perimeter Hazard Walls
      ctx.strokeStyle = "rgba(234, 179, 8, 0.50)";
      ctx.lineWidth = 4;
      ctx.strokeRect(16, 16, 488, 688);

      // Inner danger border
      ctx.strokeStyle = "rgba(239, 68, 68, 0.35)";
      ctx.lineWidth = 2;
      ctx.setLineDash([14, 8]);
      ctx.strokeRect(24, 24, 472, 672);
      ctx.setLineDash([]);

      // 4. Central Magical Battle Circle
      ctx.strokeStyle = "rgba(234, 179, 8, 0.38)";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.arc(260, 360, 95, 0, Math.PI * 2);
      ctx.stroke();

      // Outer Rune Octagon
      ctx.setLineDash([10, 6]);
      ctx.strokeStyle = "rgba(168, 85, 247, 0.38)";
      ctx.beginPath();
      ctx.arc(260, 360, 150, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);

      // 5. 4 Corner Tactical Pillars (Cover Obstacles)
      const pillars = [
        { x: 70, y: 90 },
        { x: 450, y: 90 },
        { x: 70, y: 630 },
        { x: 450, y: 630 }
      ];
      for (const pil of pillars) {
        ctx.fillStyle = "rgba(0,0,0,0.45)";
        ctx.beginPath();
        ctx.ellipse(pil.x, pil.y + 10, 16, 8, 0, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = "#1e293b";
        ctx.strokeStyle = "#64748b";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(pil.x, pil.y, 13, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = "#38bdf8";
        ctx.beginPath();
        ctx.arc(pil.x, pil.y, 4, 0, Math.PI * 2);
        ctx.fill();
      }

      // 6. Boss Charge Telegraph Beam (Bright pulsing warning beam with moving chevrons)
      const bObj = ARENA.bossEntity;
      if (bObj && bObj.state === "telegraph_charge") {
        ctx.save();
        const cAng = bObj.chargeAngle || 0;
        const beamL = 440;
        const cos = Math.cos(cAng);
        const sin = Math.sin(cAng);
        const nx = -sin * 24;
        const ny = cos * 24;

        const pulse = 0.28 + Math.sin((ARENA.frameCount || 0) * 0.18) * 0.12;
        ctx.fillStyle = `rgba(239, 68, 68, ${pulse})`;
        ctx.strokeStyle = "#ef4444";
        ctx.lineWidth = 3;
        ctx.setLineDash([12, 6]);
        ctx.beginPath();
        ctx.moveTo(bObj.x + nx, bObj.y + ny);
        ctx.lineTo(bObj.x + nx + cos * beamL, bObj.y + ny + sin * beamL);
        ctx.lineTo(bObj.x - nx + cos * beamL, bObj.y - ny + sin * beamL);
        ctx.lineTo(bObj.x - nx, bObj.y - ny);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        ctx.setLineDash([]);

        // Animated moving chevron markers along the charge beam
        const animOffset = ((ARENA.frameCount || 0) * 2) % 40;
        ctx.fillStyle = "#fef08a";
        for (let st = 35 + animOffset; st < beamL; st += 40) {
          ctx.beginPath();
          ctx.arc(bObj.x + cos * st, bObj.y + sin * st, 4.5, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.restore();
      }

      // Melee Smash Telegraph Circle (Expanding pulsing red hazard zone)
      if (bObj && bObj.state === "telegraph_melee") {
        ctx.save();
        const pulse = 0.32 + Math.sin((ARENA.frameCount || 0) * 0.2) * 0.15;
        ctx.fillStyle = `rgba(239, 68, 68, ${pulse})`;
        ctx.strokeStyle = "#ef4444";
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(bObj.x, bObj.y, 65, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        ctx.restore();
      }
    } else {
      // CLASSIC SIDE-SCROLLING ROAD (Only when NOT in Top-Down / Boss Fight!)
      if (ARENA.bossArenaMode) {
        if (!ARENA.cachedBossSkyGrad) {
          ARENA.cachedBossSkyGrad = ctx.createLinearGradient(0, -24, 0, h * 0.55);
          ARENA.cachedBossSkyGrad.addColorStop(0, "#450a0a");
          ARENA.cachedBossSkyGrad.addColorStop(0.4, "#1c1917");
          ARENA.cachedBossSkyGrad.addColorStop(1, "#292524");
        }
        ctx.fillStyle = ARENA.cachedBossSkyGrad;
      } else {
        ctx.fillStyle = ARENA.cachedSkyGrad || "#3b82f6";
      }
      ctx.fillRect(-24, -24, w + 48, h * 0.55 + 24);

      // Clouds
      if (ARENA.bossArenaMode) {
        ctx.fillStyle = "rgba(249, 115, 22, 0.6)";
        for (let e = 0; e < 12; e++) {
          const ex = (e * 31 + time * 1.2) % (w + 20);
          const ey = (e * 23 + time * 0.8) % (h * 0.7);
          ctx.beginPath();
          ctx.arc(ex, ey, (e % 3) + 1, 0, Math.PI * 2);
          ctx.fill();
        }
      } else {
        for (const cloud of (ARENA.clouds || [])) {
          drawProceduralCloud(ctx, cloud);
        }
      }

      // Distant Hills
      ctx.fillStyle = ARENA.bossArenaMode ? "#1c1917" : "#22c55e";
      ctx.beginPath();
      ctx.moveTo(-24, h * 0.55);
      ctx.quadraticCurveTo(60, h * 0.42, 120, h * 0.52);
      ctx.quadraticCurveTo(180, h * 0.40, 240, h * 0.50);
      ctx.quadraticCurveTo(310, h * 0.43, w + 24, h * 0.50);
      ctx.lineTo(w + 24, h * 0.58);
      ctx.lineTo(-24, h * 0.58);
      ctx.closePath();
      ctx.fill();

      // Ground
      if (ARENA.bossArenaMode) {
        if (!ARENA.cachedBossGroundGrad) {
          ARENA.cachedBossGroundGrad = ctx.createLinearGradient(0, h * 0.55 - 4, 0, h + 24);
          ARENA.cachedBossGroundGrad.addColorStop(0, "#1c1917");
          ARENA.cachedBossGroundGrad.addColorStop(0.4, "#292524");
          ARENA.cachedBossGroundGrad.addColorStop(1, "#0c0a09");
        }
        ctx.fillStyle = ARENA.cachedBossGroundGrad;
      } else {
        ctx.fillStyle = ARENA.cachedGroundGrad || "#15803d";
      }
      ctx.fillRect(-24, h * 0.55 - 4, w + 48, h * 0.45 + 32);

      // Grass blades
      ctx.fillStyle = "#4ade80";
      for (let gx = 15; gx < w; gx += 40) {
        const gy = ARENA.roadY + 32 + (gx * 13 % 17);
        ctx.beginPath();
        ctx.moveTo(gx, gy);
        ctx.lineTo(gx - 3, gy - 6);
        ctx.lineTo(gx + 1, gy - 4);
        ctx.lineTo(gx + 4, gy - 7);
        ctx.lineTo(gx + 6, gy);
        ctx.closePath();
        ctx.fill();
      }

      // Trail
      ctx.fillStyle = "#927050";
      ctx.beginPath();
      ctx.moveTo(0, ARENA.roadY - 14);
      for (let px = 0; px <= w; px += 20) {
        ctx.lineTo(px, ARENA.roadY - 14 + Math.sin(px * 0.03) * 3);
      }
      ctx.lineTo(w, ARENA.roadY + 30);
      for (let px = w; px >= 0; px -= 20) {
        ctx.lineTo(px, ARENA.roadY + 30 + Math.sin(px * 0.04) * 2);
      }
      ctx.closePath();
      ctx.fill();

      // Light strip
      ctx.fillStyle = "#b89570";
      ctx.fillRect(0, ARENA.roadY - 2, w, 20);

      // Pebbles
      ctx.fillStyle = "#6e5238";
      const pebbles = [30, 85, 145, 210, 275, 335];
      for (const px of pebbles) {
        const py = ARENA.roadY + 6 + (px * 7 % 11);
        ctx.beginPath();
        ctx.arc(px, py, 2.5, 0, Math.PI * 2);
        ctx.fill();
      }

      // Trees
      for (const tr of [{ x: 15 }, { x: 100 }, { x: 210 }, { x: 320 }]) {
        drawProceduralTree(ctx, tr.x, ARENA.roadY - 14, time);
      }
    }

    // ---- 6.0 BOSS ARENA DANGER ZONES (Visual Telegraphs & Impact Flashes) ----
    if (ARENA.dangerZones && ARENA.dangerZones.length > 0) {
      for (const dz of ARENA.dangerZones) {
        ctx.save();
        const maxT = dz.maxTimer || 45;
        const progress = Math.min(1, Math.max(0, 1 - (dz.timer / maxT)));
        const pulse = 0.5 + Math.sin(time * 0.25) * 0.35;

        if (dz.phase === "telegraph") {
          // Warning red zone with warning border & fill
          if (dz.type === "rect") {
            ctx.fillStyle = `rgba(239, 68, 68, ${0.22 + progress * 0.32})`;
            ctx.fillRect(dz.x, dz.y, dz.w, dz.h);
            ctx.strokeStyle = `rgba(248, 113, 113, ${0.7 + pulse * 0.3})`;
            ctx.lineWidth = 2.5;
            ctx.setLineDash([6, 4]);
            ctx.strokeRect(dz.x, dz.y, dz.w, dz.h);
            // Red progress bar at bottom of rectangle
            ctx.fillStyle = "rgba(220, 38, 38, 0.75)";
            ctx.fillRect(dz.x, dz.y + dz.h - 4, dz.w * progress, 4);
          } else if (dz.type === "circle") {
            ctx.beginPath();
            ctx.arc(dz.cx, dz.cy, dz.r, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(239, 68, 68, ${0.22 + progress * 0.32})`;
            ctx.fill();
            ctx.strokeStyle = `rgba(248, 113, 113, ${0.7 + pulse * 0.3})`;
            ctx.lineWidth = 2.5;
            ctx.setLineDash([6, 4]);
            ctx.stroke();
            // Expanding inner red circle indicator
            ctx.beginPath();
            ctx.arc(dz.cx, dz.cy, dz.r * progress, 0, Math.PI * 2);
            ctx.fillStyle = "rgba(220, 38, 38, 0.4)";
            ctx.fill();
          } else if (dz.type === "line") {
            ctx.strokeStyle = dz.color || "#ef4444";
            ctx.lineWidth = dz.width || 24;
            ctx.beginPath();
            ctx.moveTo(dz.x1, dz.y1);
            ctx.lineTo(dz.x2, dz.y2);
            ctx.stroke();
          } else if (dz.type === "cone") {
            ctx.fillStyle = dz.color ? `${dz.color}44` : "rgba(239, 68, 68, 0.35)";
            ctx.beginPath();
            ctx.moveTo(dz.cx, dz.cy);
            ctx.arc(dz.cx, dz.cy, dz.range || 150, dz.angle - dz.spread / 2, dz.angle + dz.spread / 2);
            ctx.closePath();
            ctx.fill();
          }
          // Warning Exclamation Marker
          ctx.font = "bold 13px sans-serif";
          ctx.fillStyle = "#facc15";
          ctx.textAlign = "center";
          const tx = dz.type === "rect" ? (dz.x + dz.w / 2) : (dz.type === "line" ? ((dz.x1 + dz.x2) / 2) : dz.cx);
          const ty = dz.type === "rect" ? (dz.y + dz.h / 2 + 5) : (dz.type === "line" ? ((dz.y1 + dz.y2) / 2) : (dz.cy + 5));
          ctx.fillText(dz.label || "⚠️", tx, ty);
        } else if (dz.phase === "active") {
          // Impact detonation flash!
          ctx.shadowColor = dz.color || "#ef4444";
          ctx.shadowBlur = 18;
          if (dz.type === "rect") {
            ctx.fillStyle = "rgba(254, 202, 202, 0.85)";
            ctx.fillRect(dz.x, dz.y, dz.w, dz.h);
            ctx.strokeStyle = "#ffffff";
            ctx.lineWidth = 3;
            ctx.strokeRect(dz.x, dz.y, dz.w, dz.h);
          } else if (dz.type === "circle") {
            ctx.beginPath();
            ctx.arc(dz.cx, dz.cy, dz.r, 0, Math.PI * 2);
            ctx.fillStyle = "rgba(254, 202, 202, 0.85)";
            ctx.fill();
            ctx.strokeStyle = "#ffffff";
            ctx.lineWidth = 3;
            ctx.stroke();
          } else if (dz.type === "line") {
            ctx.strokeStyle = "#ffffff";
            ctx.lineWidth = (dz.width || 24) + 6;
            ctx.beginPath();
            ctx.moveTo(dz.x1, dz.y1);
            ctx.lineTo(dz.x2, dz.y2);
            ctx.stroke();
          } else if (dz.type === "cone") {
            ctx.fillStyle = "rgba(254, 202, 202, 0.85)";
            ctx.beginPath();
            ctx.moveTo(dz.cx, dz.cy);
            ctx.arc(dz.cx, dz.cy, dz.range || 150, dz.angle - dz.spread / 2, dz.angle + dz.spread / 2);
            ctx.closePath();
            ctx.fill();
          }
          ctx.shadowBlur = 0;
        }
        ctx.restore();
      }
    }

    if (typeof renderSpecialBossTelegraphs === "function") {
      renderSpecialBossTelegraphs(ctx, ARENA, time);
    }

    // ---- 6. PICKUPS & TELEGRAPHS & SHOCKWAVES ----
    // Ground Telegraphs (Boss ground attacks)
    if (ARENA.telegraphs && ARENA.telegraphs.length > 0) {
      for (const tg of ARENA.telegraphs) {
        const progress = Math.min(1, 1 - (tg.timer / tg.maxTimer));
        ctx.save();
        ctx.strokeStyle = "rgba(239, 68, 68, 0.85)";
        ctx.lineWidth = 2.5;
        ctx.setLineDash([5, 4]);
        ctx.beginPath();
        ctx.arc(tg.x, tg.y, tg.radius, 0, Math.PI * 2);
        ctx.stroke();
        ctx.fillStyle = `rgba(239, 68, 68, ${0.15 + progress * 0.35})`;
        ctx.beginPath();
        ctx.arc(tg.x, tg.y, tg.radius * progress, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }
    }

    // Radial Expanding Shockwaves
    if (ARENA.shockwaves && ARENA.shockwaves.length > 0) {
      for (const sw of ARENA.shockwaves) {
        ctx.save();
        ctx.beginPath();
        ctx.arc(sw.x, sw.y, sw.radius, 0, Math.PI * 2);
        ctx.strokeStyle = "rgba(249, 115, 22, 0.95)";
        ctx.lineWidth = 4;
        ctx.shadowColor = "#f97316";
        ctx.shadowBlur = 12;
        ctx.stroke();
        ctx.restore();
      }
    }

    // Standard Pickups
    for (const it of ARENA.pickups) {
      if (it.type === "gold") {
        drawProceduralCoin(ctx, it.x, it.y, 6.5, time);
      } else if (it.type === "loot") {
        drawProceduralChest(ctx, it.x, it.y, time, false, false);
      } else {
        drawProceduralGem(ctx, it.x, it.y, 6.5, "#38bdf8", time);
      }
    }

    // Bouncing Physical Coins & Gems (Loot Explosion)
    if (ARENA.physicalCoins && ARENA.physicalCoins.length > 0) {
      for (const c of ARENA.physicalCoins) {
        ctx.save();
        const drawY = c.y - c.z;
        ctx.beginPath();
        ctx.ellipse(c.x, c.y + 4, 5, 2.5, 0, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(0, 0, 0, 0.35)";
        ctx.fill();
        ctx.font = `${c.size}px 'Segoe UI Emoji', 'Apple Color Emoji', sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        if (c.type === "gem") {
          drawProceduralGem(ctx, c.x, drawY, 6, c.color || "#38bdf8", time);
        } else {
          drawProceduralCoin(ctx, c.x, drawY, 6.5, time);
        }
        ctx.restore();
      }
    }

    // Falling Legendary Chest & Pillar of Light
    if (ARENA.fallingChest) {
      const fc = ARENA.fallingChest;
      ctx.save();
      if (fc.landed && fc.beamAlpha > 0) {
        const grad = ctx.createLinearGradient(fc.x, 0, fc.x, fc.targetY);
        grad.addColorStop(0, "rgba(253, 224, 71, 0)");
        grad.addColorStop(0.3, `rgba(250, 204, 21, ${fc.beamAlpha * 0.35})`);
        grad.addColorStop(1, `rgba(245, 158, 11, ${fc.beamAlpha * 0.85})`);
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.moveTo(fc.x - 22, 0);
        ctx.lineTo(fc.x + 22, 0);
        ctx.lineTo(fc.x + 34, fc.targetY + 12);
        ctx.lineTo(fc.x - 34, fc.targetY + 12);
        ctx.closePath();
        ctx.fill();

        // Rotating rays
        ctx.save();
        ctx.translate(fc.x, fc.targetY);
        ctx.rotate(fc.rayAngle);
        ctx.strokeStyle = `rgba(253, 224, 71, ${fc.beamAlpha * 0.4})`;
        ctx.lineWidth = 1.5;
        for (let r = 0; r < 8; r++) {
          ctx.beginPath();
          ctx.moveTo(0, 0);
          const ra = (r * Math.PI) / 4;
          ctx.lineTo(Math.cos(ra) * 45, Math.sin(ra) * 45);
          ctx.stroke();
        }
        ctx.restore();

        for (const sp of fc.sparkles) {
          ctx.fillStyle = `rgba(255, 255, 255, ${sp.alpha})`;
          ctx.beginPath();
          ctx.arc(sp.x, sp.y, sp.size, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      drawProceduralChest(ctx, fc.x, fc.y, time, fc.landed, fc.opened);

      if (fc.landed) {
        ctx.font = "bold 9.5px sans-serif";
        ctx.fillStyle = "#fef08a";
        ctx.shadowColor = "#000000";
        ctx.shadowBlur = 4;
        ctx.fillText("НАЖМИТЕ, ЧТОБЫ ОТКРЫТЬ!", fc.x, fc.targetY + 22);
      }
      ctx.restore();
    }

    // ---- 7. ALLIED MINIONS (WK Skeletons) ----
    for (const m of ARENA.alliedMinions) {
      ctx.fillStyle = "#1e293b";
      ctx.beginPath();
      ctx.arc(m.x, m.y, m.radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#10b981";
      ctx.lineWidth = 2;
      ctx.stroke();
      drawProceduralMinion(ctx, m, time);
    }

    // ---- 8. DOTA CREEPS & BOSSES (SOLID TOKEN SPRITES) ----
    for (const c of ARENA.creeps) {
      // Ground Shadow
      ctx.fillStyle = "rgba(0,0,0,0.3)";
      ctx.beginPath();
      ctx.ellipse(c.x, c.y + c.radius * 0.8, c.radius * 0.9, c.radius * 0.35, 0, 0, Math.PI * 2);
      ctx.fill();

      // Boss shield glow
      if (c.isBoss && c.shielded) {
        ctx.strokeStyle = "rgba(168, 85, 247, 0.8)";
        ctx.lineWidth = 3.5;
        ctx.beginPath();
        ctx.arc(c.x, c.y, c.radius + 12, 0, Math.PI * 2);
        ctx.stroke();
        ctx.fillStyle = "rgba(168, 85, 247, 0.15)";
        ctx.beginPath();
        ctx.arc(c.x, c.y, c.radius + 12, 0, Math.PI * 2);
        ctx.fill();
      }

      // PROCEDURAL VECTOR CREEP / BOSS SPRITE (ZERO EMOJIS)
      drawProceduralCreep(ctx, c, time);

      // CREEP NAME TAG
      ctx.font = c.isBoss ? "bold 9.5px sans-serif" : "bold 7.5px sans-serif";
      ctx.fillStyle = c.isBoss ? "#facc15" : "#ffffff";
      ctx.fillText(c.name, c.x, c.y - c.radius - (c.isBoss ? 16 : 10));

      // HP BAR
      const barW = c.radius * 2.2;
      const barH = c.isBoss ? 6 : 4;
      const hpPct = Math.max(0, Math.min(1, c.hp / c.maxHp));
      ctx.fillStyle = "rgba(0,0,0,0.65)";
      ctx.fillRect(c.x - barW / 2, c.y - c.radius - 6, barW, barH);
      ctx.fillStyle = c.isBoss ? "#ef4444" : (c.team === "radiant" ? "#22c55e" : "#f97316");
      ctx.fillRect(c.x - barW / 2, c.y - c.radius - 6, barW * hpPct, barH);

      // BOSS POISE (STAGGER) BAR & TORMENTOR SHIELD
      if (c.isBoss) {
        const poiseBarW = barW;
        const poiseH = 3;
        const pPct = Math.max(0, Math.min(1, (c.poise !== undefined ? c.poise : 300) / (c.maxPoise || 300)));
        ctx.fillStyle = "rgba(15, 23, 42, 0.85)";
        ctx.fillRect(c.x - poiseBarW / 2, c.y - c.radius - 11, poiseBarW, poiseH);
        ctx.fillStyle = c.isStaggered ? "#ec4899" : "#fbbf24";
        ctx.fillRect(c.x - poiseBarW / 2, c.y - c.radius - 11, poiseBarW * pPct, poiseH);

        // Stagger / Stunned / Enrage badge & visual indicators
        if (c.state === "stunned") {
          ctx.font = "bold 10px sans-serif";
          ctx.fillStyle = "#facc15";
          ctx.fillText("💫 В СТЕНЕ! ОШЕЛОМЛЕН! БЕЙ!", c.x, c.y - c.radius - 20);
          // Rotating stars over boss head
          const stAngle = (ARENA.frameCount || 0) * 0.08;
          for (let s = 0; s < 3; s++) {
            const a = stAngle + (s * Math.PI * 2) / 3;
            const sx = c.x + Math.cos(a) * (c.radius * 0.75);
            const sy = c.y - c.radius * 0.9 + Math.sin(a) * 5;
            ctx.fillStyle = "#facc15";
            ctx.beginPath();
            ctx.arc(sx, sy, 4, 0, Math.PI * 2);
            ctx.fill();
          }
        } else if (c.state === "telegraph_charge") {
          ctx.font = "bold 10px sans-serif";
          ctx.fillStyle = "#ef4444";
          ctx.fillText("⚠️ ТАРАН (УЙДИ С ЛИНИИ!)", c.x, c.y - c.radius - 20);
        } else if (c.state === "telegraph_melee") {
          ctx.font = "bold 10px sans-serif";
          ctx.fillStyle = "#f97316";
          ctx.fillText("⚠️ ЗАМАХ (ОТОЙДИ!)", c.x, c.y - c.radius - 20);
        } else if (c.isStaggered) {
          ctx.font = "bold 8.5px sans-serif";
          ctx.fillStyle = "#fbbf24";
          ctx.fillText("💫 STAGGER (+150%)", c.x, c.y - c.radius - 18);
        } else if (c.enraged) {
          ctx.font = "bold 8.5px sans-serif";
          ctx.fillStyle = "#ef4444";
          ctx.fillText("🔥 ENRAGE!", c.x, c.y - c.radius - 18);
        }

        // Tormentor Reflective Shield Ring
        if (c.tormentorShield) {
          ctx.save();
          ctx.strokeStyle = "rgba(192, 132, 252, 0.95)";
          ctx.lineWidth = 3.5;
          ctx.setLineDash([6, 3]);
          ctx.beginPath();
          ctx.arc(c.x, c.y, c.radius + 14, 0, Math.PI * 2);
          ctx.stroke();
          ctx.fillStyle = "rgba(168, 85, 247, 0.18)";
          ctx.fill();
          ctx.restore();
        }
      }
    }

    // ---- 8.5 SQUAD COMPANIONS (TRIO SQUAD MODE) ----
    if (ARENA.isBossActive && (ARENA.bossPartyMode || "trio") === "trio" && ARENA.bossCompanions) {
      for (const comp of ARENA.bossCompanions) {
        // Shadow
        ctx.fillStyle = "rgba(0, 0, 0, 0.35)";
        ctx.beginPath();
        ctx.ellipse(comp.x, comp.y + comp.radius + 2, 16, 5, 0, 0, Math.PI * 2);
        ctx.fill();

        // Procedural Hero Sprite
        drawProceduralHero(ctx, comp, comp.heroClass, time, !!comp.slashAnimation, 0);

        // Name tag
        ctx.font = "bold 7.5px sans-serif";
        ctx.fillStyle = "#38bdf8";
        ctx.textAlign = "center";
        ctx.fillText(comp.name, comp.x, comp.y - comp.radius - 6);

        // Slash Arc
        if (comp.slashAnimation) {
          const csa = comp.slashAnimation;
          ctx.save();
          ctx.translate(comp.x + 18, comp.y);
          ctx.strokeStyle = "rgba(251, 191, 36, 0.9)";
          ctx.lineWidth = 3;
          ctx.beginPath();
          ctx.arc(0, 0, csa.radius, -Math.PI * 0.35, Math.PI * 0.35);
          ctx.stroke();
          ctx.restore();
        }
      }
    }

    // ---- 9. HERO (STATIONARY TOKEN, LEFT SIDE) ----
    const p = ARENA.player;
    const heroProfile = RPG_STATE.profile || {};

    // Hero Platform / Shadow
    ctx.fillStyle = "rgba(250, 204, 21, 0.2)";
    ctx.beginPath();
    ctx.ellipse(p.x, p.y + p.radius + 2, 24, 8, 0, 0, Math.PI * 2);
    ctx.fill();

    // Pudge Flesh Heap Spiked Shield Aura
    if (p.fleshHeapActive > 0) {
      ctx.strokeStyle = "rgba(239, 68, 68, 0.7)";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.radius + 8, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Juggernaut Blade Dance Whirlwind
    if (p.bladeDanceActive > 0) {
      ctx.strokeStyle = "rgba(245, 158, 11, 0.8)";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.radius + 9, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Anti-Mage Counterspell Shield
    if (p.counterspellActive > 0) {
      ctx.strokeStyle = "rgba(56, 189, 248, 0.85)";
      ctx.lineWidth = 3.5;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.radius + 10, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Largo Croak of Genius Echo Aura
    if (p.croakTimer > 0) {
      const pulse = Math.sin((ARENA.frameCount || 0) * 0.25) * 3;
      ctx.strokeStyle = "rgba(192, 132, 252, 0.85)";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.radius + 9 + pulse, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Largo Amphibian Rhapsody Aura (активна пока включена ульта)
    if (p.largoRhapsodyActive || p.largoRhapsodyTimer > 0) {
      const spin = (ARENA.frameCount || 0) * 0.08;
      const pulse = Math.sin((ARENA.frameCount || 0) * 0.15) * 4;
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.strokeStyle = "rgba(34, 197, 94, 0.85)";
      ctx.lineWidth = 3;
      ctx.setLineDash([8, 6]);
      ctx.beginPath();
      ctx.arc(0, 0, p.radius + 16 + pulse, spin, spin + Math.PI * 2);
      ctx.stroke();

      // Golden harmonic outer ring
      ctx.strokeStyle = "rgba(250, 204, 21, 0.6)";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.arc(0, 0, p.radius + 22 - pulse * 0.5, -spin * 1.5, -spin * 1.5 + Math.PI * 2);
      ctx.stroke();
      ctx.restore();

      // Spawns soft floating musical notes around Largo
      if ((ARENA.frameCount || 0) % 45 === 0) {
        spawnFloatingText(p.x + (Math.random() - 0.5) * 30, p.y - 15, "🎶", "#4ade80");
      }
    }

    // --- VISUAL PLAYER STATUS EFFECTS (STUN, SLOW, SILENCE, DOOM, DOTs) ---
    if (p.slowTimer > 0) {
      ctx.save();
      ctx.strokeStyle = "rgba(56, 189, 248, 0.85)";
      ctx.lineWidth = 2.5;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.radius + 7, time * 0.003, time * 0.003 + Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    }
    if (p.burnTimer > 0) {
      ctx.save();
      ctx.fillStyle = "rgba(249, 115, 22, 0.35)";
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.radius + 5 + Math.sin(time * 0.01) * 3, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }
    if (p.poisonTimer > 0) {
      ctx.save();
      ctx.fillStyle = "rgba(132, 204, 22, 0.35)";
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.radius + 4 + Math.cos(time * 0.01) * 3, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }
    if (p.stunTimer > 0 || p.isFrozenInTime) {
      ctx.save();
      for (let s = 0; s < 3; s++) {
        const sAng = (time * 0.006) + (s * Math.PI * 2 / 3);
        const sx = p.x + Math.cos(sAng) * (p.radius + 6);
        const sy = p.y - p.radius - 28 + Math.sin(sAng) * 4;
        ctx.fillStyle = "#facc15";
        ctx.beginPath();
        ctx.arc(sx, sy, 3.5, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.font = "bold 9px sans-serif";
      ctx.fillStyle = "#facc15";
      ctx.textAlign = "center";
      ctx.fillText(p.isFrozenInTime ? "⏳ СТОП-ВРЕМЯ" : "💫 СТАН", p.x, p.y - p.radius - 32);
      ctx.restore();
    }
    if (p.silenceTimer > 0 || p.doomDebuffTimer > 0) {
      ctx.save();
      ctx.font = "bold 9px sans-serif";
      ctx.fillStyle = p.doomDebuffTimer > 0 ? "#ef4444" : "#c084fc";
      ctx.textAlign = "center";
      ctx.fillText(p.doomDebuffTimer > 0 ? "🔥 DOOM" : "🔇 САЙЛЕНС", p.x, p.y - p.radius - 32);
      ctx.restore();
    }
    if (p.blindTimer > 0) {
      ctx.save();
      ctx.font = "bold 8.5px sans-serif";
      ctx.fillStyle = "#ef4444";
      ctx.textAlign = "center";
      ctx.fillText("🔴 ОСЛЕПЛЕНИЕ", p.x, p.y - p.radius - 22);
      ctx.restore();
    }

    // RENDER DASH GHOST AFTERIMAGES BEHIND PLAYER
    if (ARENA.dashGhosts) {
      for (const ghost of ARENA.dashGhosts) {
        ctx.save();
        ctx.globalAlpha = ghost.alpha;
        drawProceduralHero(ctx, ghost, ghost.heroClass, time, false, 0);
        ctx.restore();
      }
    }

    // PROCEDURAL VECTOR HERO SPRITE (ZERO EMOJIS)
    const hClass = (heroProfile.hero_class || heroProfile.class_id || RPG_STATE.profile?.hero_class || "pudge").toLowerCase();
    drawProceduralHero(ctx, p, hClass, time, !!p.slashAnimation, ARENA.combo ? ARENA.combo.step : 0);

    // HERO NAME
    ctx.font = "bold 8.5px sans-serif";
    ctx.fillStyle = "#facc15";
    ctx.fillText(heroProfile.class_name ? heroProfile.class_name.split(" ")[0] : "Герой", p.x, p.y - p.radius - 22);

    // HERO HP & MP BARS
    const pHpPct = Math.max(0, Math.min(1, p.currentHp / p.maxHp));
    const pMpPct = Math.max(0, Math.min(1, p.currentMp / p.maxMp));
    const pBarW = 54;
    ctx.fillStyle = "rgba(0,0,0,0.65)";
    ctx.fillRect(p.x - pBarW / 2, p.y - p.radius - 15, pBarW, 5);
    ctx.fillStyle = "#22c55e";
    ctx.fillRect(p.x - pBarW / 2, p.y - p.radius - 15, pBarW * pHpPct, 5);
    ctx.fillStyle = "rgba(0,0,0,0.65)";
    ctx.fillRect(p.x - pBarW / 2, p.y - p.radius - 9, pBarW, 4);
    ctx.fillStyle = "#38bdf8";
    ctx.fillRect(p.x - pBarW / 2, p.y - p.radius - 9, pBarW * pMpPct, 4);

    // Melee Slash Arc
    if (p.slashAnimation) {
      const sa = p.slashAnimation;
      ctx.save();
      ctx.translate(p.x + 24, p.y);
      ctx.strokeStyle = sa.isMagic ? "rgba(56, 189, 248, 0.9)" : "rgba(250, 204, 21, 0.9)";
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.arc(0, 0, sa.radius, -Math.PI * 0.4, Math.PI * 0.4);
      ctx.stroke();
      ctx.restore();
    }

    // ---- 9.1 ACTIVE BATTLE PET (FAMILIAR) ----
    if (ARENA.pet) {
      ctx.save();
      const pet = ARENA.pet;
      const petIcons = {
        slime: "💧",
        fairy: "🧚",
        wolf: "🐺",
        dragon: "🐉",
        donkey: "🫏",
        phoenix: "🦅"
      };
      const petIcon = petIcons[pet.type] || "🐾";
      const petGlow = {
        slime: "rgba(56, 189, 248, 0.35)",
        fairy: "rgba(34, 197, 94, 0.35)",
        wolf: "rgba(239, 68, 68, 0.35)",
        dragon: "rgba(249, 115, 22, 0.35)",
        donkey: "rgba(234, 179, 8, 0.35)",
        phoenix: "rgba(245, 158, 11, 0.45)"
      };
      // Gentle floating shadow/glow
      ctx.fillStyle = petGlow[pet.type] || "rgba(249, 115, 22, 0.25)";
      ctx.beginPath();
      ctx.arc(pet.x, pet.y + 12, 11, 0, Math.PI * 2);
      ctx.fill();

      ctx.font = "20px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(petIcon, pet.x, pet.y);
      ctx.restore();
    }

    // ---- 10. PLAYER PROJECTILES (Snowball, Magic Orbs, Daggers) ----
    for (const proj of ARENA.playerProjectiles) {
      drawProceduralProjectile(ctx, proj, time);
    }

    // ---- 11. SPECIAL EFFECTS (Lightning, Rot, Omnislash, Active Items) ----
    for (const fx of ARENA.specialEffects) {
      if (fx.type === "refresher_burst") {
        ctx.save();
        const progress = 1 - (fx.timer / 35);
        const curRadius = fx.radius + (fx.maxRadius - fx.radius) * progress;
        const alpha = Math.max(0, fx.timer / 35);
        ctx.shadowColor = "#22c55e";
        ctx.shadowBlur = 25;
        ctx.strokeStyle = `rgba(34, 197, 94, ${alpha * 0.9})`;
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.ellipse(fx.x, fx.y, curRadius, curRadius * 0.45, 0, 0, Math.PI * 2);
        ctx.stroke();

        ctx.fillStyle = `rgba(74, 222, 128, ${alpha * 0.25})`;
        ctx.fill();
        ctx.shadowBlur = 0;

        for (let s = 0; s < 6; s++) {
          const spX = fx.x + Math.sin(progress * 10 + s * 1.2) * (curRadius * 0.8);
          const spY = fx.y - (progress * 60 + s * 8);
          ctx.fillStyle = `rgba(187, 247, 208, ${alpha})`;
          ctx.beginPath();
          ctx.arc(spX, spY, 2.5, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.restore();
      } else if (fx.type === "dagon_beam") {
        ctx.save();
        const alpha = Math.max(0, fx.timer / 18);
        ctx.shadowColor = fx.color || "#ef4444";
        ctx.shadowBlur = 20;
        ctx.strokeStyle = `rgba(239, 68, 68, ${alpha})`;
        ctx.lineWidth = 4.5;
        ctx.beginPath();
        ctx.moveTo(fx.fromX, fx.fromY);
        const midX = (fx.fromX + fx.toX) / 2;
        const midY = (fx.fromY + fx.toY) / 2 + (Math.random() - 0.5) * 16;
        ctx.lineTo(midX, midY);
        ctx.lineTo(fx.toX, fx.toY);
        ctx.stroke();
        ctx.strokeStyle = `rgba(255, 255, 255, ${alpha * 0.9})`;
        ctx.lineWidth = 2;
        ctx.stroke();
        ctx.restore();
      } else if (fx.type === "shiva_blast") {
        ctx.save();
        const progress = 1 - (fx.timer / 45);
        const curRadius = fx.radius + (fx.maxRadius - fx.radius) * progress;
        const alpha = Math.max(0, fx.timer / 45);
        ctx.shadowColor = "#38bdf8";
        ctx.shadowBlur = 25;
        ctx.strokeStyle = `rgba(56, 189, 248, ${alpha * 0.85})`;
        ctx.lineWidth = 5;
        ctx.beginPath();
        ctx.ellipse(fx.x, fx.y, curRadius, curRadius * 0.4, 0, 0, Math.PI * 2);
        ctx.stroke();
        ctx.fillStyle = `rgba(186, 230, 253, ${alpha * 0.15})`;
        ctx.fill();
        ctx.restore();
      } else if (fx.type === "blink_poof") {
        ctx.save();
        const alpha = Math.max(0, fx.timer / 20);
        ctx.shadowColor = "#38bdf8";
        ctx.shadowBlur = 15;
        ctx.fillStyle = `rgba(56, 189, 248, ${alpha * 0.4})`;
        ctx.beginPath();
        ctx.arc(fx.x, fx.y, 25 * (1 - alpha * 0.5), 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }
      if (fx.type === "sunstrike") {
        // --- INVOKER SUN STRIKE (Солнечный луч с неба) ---
        ctx.save();
        const progress = 1 - (fx.timer / (fx.maxTimer || 42));
        const alpha = fx.timer < 10 ? (fx.timer / 10) : (progress < 0.2 ? progress / 0.2 : 1.0);

        // 1. Vertical Sun Beam from top of sky to ground
        const beamGrad = ctx.createLinearGradient(fx.x - 26, 0, fx.x + 26, 0);
        beamGrad.addColorStop(0, "rgba(250, 204, 21, 0)");
        beamGrad.addColorStop(0.3, `rgba(250, 204, 21, ${0.45 * alpha})`);
        beamGrad.addColorStop(0.5, `rgba(255, 255, 255, ${0.95 * alpha})`);
        beamGrad.addColorStop(0.7, `rgba(250, 204, 21, ${0.45 * alpha})`);
        beamGrad.addColorStop(1, "rgba(250, 204, 21, 0)");

        ctx.fillStyle = beamGrad;
        ctx.fillRect(fx.x - 28, 0, 56, fx.y + 12);

        // Core laser white line
        ctx.strokeStyle = `rgba(255, 255, 255, ${alpha})`;
        ctx.lineWidth = 4.5;
        ctx.beginPath();
        ctx.moveTo(fx.x, 0);
        ctx.lineTo(fx.x, fx.y + 12);
        ctx.stroke();

        // 2. Expanding Radiant Solar Rings on Ground
        ctx.shadowColor = "#facc15";
        ctx.shadowBlur = 20;
        ctx.strokeStyle = `rgba(251, 191, 36, ${0.9 * alpha})`;
        ctx.lineWidth = 3.5;
        ctx.beginPath();
        ctx.ellipse(fx.x, fx.y + 2, fx.radius * progress, (fx.radius * 0.4) * progress, 0, 0, Math.PI * 2);
        ctx.stroke();

        // Inner glowing disc
        ctx.fillStyle = `rgba(254, 240, 138, ${0.35 * alpha})`;
        ctx.beginPath();
        ctx.ellipse(fx.x, fx.y + 2, (fx.radius * 0.6) * progress, (fx.radius * 0.25) * progress, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;

        // Rising solar rays / sparkles
        for (let s = 0; s < 5; s++) {
          const spX = fx.x + Math.sin(fx.timer * 0.3 + s * 1.5) * (fx.radius * 0.7);
          const spY = fx.y - ((fx.timer * 4 + s * 18) % 80);
          ctx.fillStyle = `rgba(254, 240, 138, ${0.8 * alpha})`;
          ctx.beginPath();
          ctx.arc(spX, spY, 2.5, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.restore();

      } else if (fx.type === "lightning") {
        // Vertical Lightning Bolt
        ctx.save();
        ctx.strokeStyle = "rgba(186, 230, 253, 0.95)";
        ctx.lineWidth = 6;
        ctx.beginPath();
        ctx.moveTo(fx.x, 0);
        ctx.lineTo(fx.x - 8, fx.y * 0.4);
        ctx.lineTo(fx.x + 8, fx.y * 0.7);
        ctx.lineTo(fx.x, fx.y);
        ctx.stroke();

        ctx.strokeStyle = "rgba(56, 189, 248, 0.7)";
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(fx.x, fx.y, fx.radius * (1 - fx.timer / 35), 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
      } else if (fx.type === "rot") {
        // Poison Rot Cloud across entire map
        ctx.fillStyle = "rgba(34, 197, 94, 0.22)";
        ctx.fillRect(0, 0, w, h);
      } else if (fx.type === "blood_flash") {
        ctx.fillStyle = "rgba(220, 38, 38, 0.25)";
        ctx.fillRect(0, 0, w, h);
      } else if (fx.type === "omnislash") {
        ctx.strokeStyle = "rgba(250, 204, 21, 0.9)";
        ctx.lineWidth = 3.5;
        ctx.beginPath();
        const randX = 60 + Math.sin((ARENA.frameCount || 0) * 1.5 + fx.timer) * 120 + 100;
        const randY = ARENA.roadY - 30 + Math.cos((ARENA.frameCount || 0) * 2.1 + fx.timer) * 35;
        ctx.moveTo(randX - 25, randY - 20);
        ctx.lineTo(randX + 25, randY + 20);
        ctx.stroke();
      } else if (fx.type === "croak_blast") {
        // --- LARGO CROAK OF GENIUS (Музыкальная звуковая волна) ---
        ctx.save();
        const prog = 1 - (fx.timer / (fx.maxTimer || 35));
        const alpha = Math.max(0, fx.timer / (fx.maxTimer || 35));
        ctx.shadowColor = "#c084fc";
        ctx.shadowBlur = 20;
        ctx.strokeStyle = `rgba(192, 132, 252, ${alpha * 0.9})`;
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.ellipse(fx.x, fx.y, fx.radius * prog, (fx.radius * 0.45) * prog, 0, 0, Math.PI * 2);
        ctx.stroke();

        // Musical note symbols floating up
        const notes = ["🎵", "🎶", "🐸", "✨"];
        for (let s = 0; s < 3; s++) {
          const nX = fx.x + Math.sin(prog * 8 + s * 2) * (fx.radius * 0.6 * prog);
          const nY = fx.y - (prog * 50 + s * 12);
          ctx.font = "16px sans-serif";
          ctx.fillText(notes[s % notes.length], nX - 8, nY);
        }
        ctx.restore();
      } else if (fx.type === "rhapsody_beat") {
        // --- LARGO AMPHIBIAN RHAPSODY BEAT (Каждую секунду: зеленое исцеление + золотой урон) ---
        ctx.save();
        const prog = 1 - (fx.timer / (fx.maxTimer || 35));
        const alpha = Math.max(0, fx.timer / (fx.maxTimer || 35));
        
        // Healing green inner ring
        ctx.shadowColor = "#22c55e";
        ctx.shadowBlur = 25;
        ctx.strokeStyle = `rgba(34, 197, 94, ${alpha * 0.9})`;
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.ellipse(fx.x, fx.y, (fx.radius * 0.6) * prog, (fx.radius * 0.3) * prog, 0, 0, Math.PI * 2);
        ctx.stroke();

        // Golden shockwave outer ring
        ctx.shadowColor = "#facc15";
        ctx.shadowBlur = 20;
        ctx.strokeStyle = `rgba(250, 204, 21, ${alpha * 0.85})`;
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.ellipse(fx.x, fx.y, fx.radius * prog, (fx.radius * 0.45) * prog, 0, 0, Math.PI * 2);
        ctx.stroke();

        // Floating musical notes
        const notes = ["🎵", "🎶", "💚", "✨", "🐸"];
        for (let s = 0; s < 4; s++) {
          const ang = (s * Math.PI / 2) + prog * 2;
          const nX = fx.x + Math.cos(ang) * (fx.radius * 0.7 * prog);
          const nY = fx.y + Math.sin(ang) * (fx.radius * 0.35 * prog) - (prog * 30);
          ctx.font = "15px sans-serif";
          ctx.fillText(notes[s % notes.length], nX - 7, nY);
        }
        ctx.restore();
      } else if (fx.type === "rhapsody_aura") {
        // --- LARGO CONTINUOUS AURA ---
        const p = ARENA.player;
        if (p && p.largoRhapsodyTimer > 0) {
          ctx.save();
          const ang = ((ARENA.frameCount || 0) * 0.06) % (Math.PI * 2);
          ctx.strokeStyle = "rgba(34, 197, 94, 0.45)";
          ctx.lineWidth = 2.5;
          ctx.setLineDash([10, 8]);
          ctx.beginPath();
          ctx.ellipse(p.x, p.y + 4, 180, 80, ang, 0, Math.PI * 2);
          ctx.stroke();
          ctx.restore();
        }
      } else if (fx.type === "topdown_meteor") {
        // --- INVOKER CHAOS METEOR (Падающая огненная "котлета") ---
        ctx.save();
        const prog = 1 - (fx.timer / (fx.maxTimer || 50));
        if (prog < 0.65) {
          // Flight phase: flaming asteroid hurtles from sky with trailing embers
          const ang = Math.atan2(fx.targetY - fx.startY, fx.targetX - fx.startX);
          const cos = Math.cos(ang);
          const sin = Math.sin(ang);

          // Fiery tail
          const tailLen = 65;
          const grad = ctx.createLinearGradient(fx.x - cos * tailLen, fx.y - sin * tailLen, fx.x, fx.y);
          grad.addColorStop(0, "rgba(234, 88, 12, 0)");
          grad.addColorStop(0.5, "rgba(249, 115, 22, 0.7)");
          grad.addColorStop(1, "rgba(254, 240, 138, 0.95)");
          ctx.strokeStyle = grad;
          ctx.lineWidth = 20;
          ctx.lineCap = "round";
          ctx.beginPath();
          ctx.moveTo(fx.x - cos * tailLen, fx.y - sin * tailLen);
          ctx.lineTo(fx.x, fx.y);
          ctx.stroke();

          // Core burning fireball
          ctx.fillStyle = "#f97316";
          ctx.beginPath();
          ctx.arc(fx.x, fx.y, 22, 0, Math.PI * 2);
          ctx.fill();

          ctx.fillStyle = "#fef08a";
          ctx.beginPath();
          ctx.arc(fx.x, fx.y, 14, 0, Math.PI * 2);
          ctx.fill();

          // Fiery spark particles flying backwards
          for (let s = 0; s < 4; s++) {
            const spDist = 15 + ((fx.timer * 7 + s * 16) % 55);
            const spX = fx.x - cos * spDist + (Math.sin(s * 2 + fx.timer) * 8);
            const spY = fx.y - sin * spDist + (Math.cos(s * 2 + fx.timer) * 8);
            ctx.fillStyle = s % 2 === 0 ? "#ea580c" : "#fef08a";
            ctx.beginPath();
            ctx.arc(spX, spY, 3, 0, Math.PI * 2);
            ctx.fill();
          }
        } else {
          // Impact & crater explosion phase
          const impactProg = (prog - 0.65) / 0.35;
          const alpha = 1 - impactProg;

          // Scorched crater on the ground
          ctx.fillStyle = `rgba(12, 10, 9, ${0.75 * alpha})`;
          ctx.beginPath();
          ctx.ellipse(fx.targetX, fx.targetY + 8, 48, 22, 0, 0, Math.PI * 2);
          ctx.fill();

          // Expanding explosion fireball
          const expR = 24 + impactProg * 65;
          const expGrad = ctx.createRadialGradient(fx.targetX, fx.targetY, 6, fx.targetX, fx.targetY, expR);
          expGrad.addColorStop(0, `rgba(254, 240, 138, ${0.9 * alpha})`);
          expGrad.addColorStop(0.4, `rgba(249, 115, 22, ${0.8 * alpha})`);
          expGrad.addColorStop(0.8, `rgba(220, 38, 38, ${0.6 * alpha})`);
          expGrad.addColorStop(1, "rgba(220, 38, 38, 0)");
          ctx.fillStyle = expGrad;
          ctx.beginPath();
          ctx.arc(fx.targetX, fx.targetY, expR, 0, Math.PI * 2);
          ctx.fill();

          // Expanding shockwave ring
          ctx.strokeStyle = `rgba(251, 146, 60, ${0.85 * alpha})`;
          ctx.lineWidth = 3.5;
          ctx.beginPath();
          ctx.arc(fx.targetX, fx.targetY, expR * 1.15, 0, Math.PI * 2);
          ctx.stroke();
        }
        ctx.restore();

      } else if (fx.type === "blade_fury") {
        // --- JUGGERNAUT BLADE FURY / BLADE DANCE (Золотой вихрь клинков) ---
        ctx.save();
        const spinAng = (ARENA.frameCount || 0) * 0.35;
        const bAlpha = fx.timer < 10 ? fx.timer / 10 : 0.85;
        ctx.translate(fx.x, fx.y);

        // Golden spinning energy ring
        ctx.strokeStyle = `rgba(245, 158, 11, ${0.75 * bAlpha})`;
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(0, 0, fx.radius || 48, 0, Math.PI * 2);
        ctx.stroke();

        // 4 curved crescent blades swirling
        for (let b = 0; b < 4; b++) {
          const ba = spinAng + (b * Math.PI) / 2;
          ctx.save();
          ctx.rotate(ba);
          ctx.strokeStyle = `rgba(254, 240, 138, ${0.95 * bAlpha})`;
          ctx.lineWidth = 3.5;
          ctx.beginPath();
          ctx.arc(0, 0, (fx.radius || 48) - 4, 0, Math.PI * 0.45);
          ctx.stroke();
          ctx.restore();
        }
        ctx.restore();

      } else if (fx.type === "topdown_omnislash") {
        // --- JUGGERNAUT OMNISLASH (Молниеносные золотые удары по боссу) ---
        ctx.save();
        const boss = ARENA.bossEntity;
        const cx = boss ? boss.x : fx.x;
        const cy = boss ? boss.y : fx.y;

        // Render recorded slash trails
        if (fx.slashArcs) {
          for (let s = 0; s < fx.slashArcs.length; s++) {
            const arc = fx.slashArcs[s];
            const cos = Math.cos(arc.angle);
            const sin = Math.sin(arc.angle);
            const len = 42;

            ctx.strokeStyle = "rgba(250, 204, 21, 0.9)";
            ctx.lineWidth = 4;
            ctx.beginPath();
            ctx.moveTo(arc.x - cos * len, arc.y - sin * len);
            ctx.lineTo(arc.x + cos * len, arc.y + sin * len);
            ctx.stroke();

            ctx.strokeStyle = "rgba(255, 255, 255, 0.95)";
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(arc.x - cos * len, arc.y - sin * len);
            ctx.lineTo(arc.x + cos * len, arc.y + sin * len);
            ctx.stroke();
          }
        }

        // Central slash impact glow
        ctx.strokeStyle = "rgba(245, 158, 11, 0.8)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(cx, cy, 38, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();

      } else if (fx.type === "dagger_throw") {
        // --- PHANTOM ASSASSIN STIFLING DAGGER (Летящий теневой кинжал) ---
        ctx.save();
        ctx.translate(fx.x, fx.y);
        ctx.rotate(fx.angle !== undefined ? fx.angle : 0);

        // Neon cyan/crimson blur trail
        ctx.strokeStyle = "rgba(244, 63, 94, 0.65)";
        ctx.lineWidth = 5;
        ctx.beginPath();
        ctx.moveTo(-22, 0);
        ctx.lineTo(0, 0);
        ctx.stroke();

        // Dagger blade
        ctx.fillStyle = "#ffffff";
        ctx.beginPath();
        ctx.moveTo(12, 0);
        ctx.lineTo(-6, -4);
        ctx.lineTo(-2, 0);
        ctx.lineTo(-6, 4);
        ctx.closePath();
        ctx.fill();

        // Glowing crimson tip
        ctx.fillStyle = "#f43f5e";
        ctx.beginPath();
        ctx.arc(12, 0, 3.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();

      } else if (fx.type === "slash_burst") {
        // --- PA COUP DE GRACE CRITICAL SPARK BURST ---
        ctx.save();
        const prog = 1 - (fx.timer / (fx.maxTimer || 16));
        const alpha = 1 - prog;
        const rad = 10 + prog * 28;
        ctx.strokeStyle = `rgba(244, 63, 94, ${alpha})`;
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(fx.x, fx.y, rad, 0, Math.PI * 2);
        ctx.stroke();

        ctx.strokeStyle = `rgba(255, 255, 255, ${alpha * 0.9})`;
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.moveTo(fx.x - rad, fx.y - rad);
        ctx.lineTo(fx.x + rad, fx.y + rad);
        ctx.moveTo(fx.x + rad, fx.y - rad);
        ctx.lineTo(fx.x - rad, fx.y + rad);
        ctx.stroke();
        ctx.restore();

      } else if (fx.type === "coup_de_grace") {
        // --- PHANTOM ASSASSIN COUP DE GRACE (Кровавый разрез босса x6.5) ---
        ctx.save();
        const prog = 1 - (fx.timer / (fx.maxTimer || 35));
        const alpha = 1 - prog;

        // Giant crimson diagonal slash across boss
        ctx.strokeStyle = `rgba(220, 38, 38, ${0.95 * alpha})`;
        ctx.lineWidth = 6;
        ctx.beginPath();
        ctx.moveTo(fx.x - 55, fx.y - 45);
        ctx.lineTo(fx.x + 55, fx.y + 45);
        ctx.stroke();

        ctx.strokeStyle = `rgba(254, 202, 202, ${0.9 * alpha})`;
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.moveTo(fx.x - 55, fx.y - 45);
        ctx.lineTo(fx.x + 55, fx.y + 45);
        ctx.stroke();

        // Blood droplets spray
        for (let d = 0; d < 8; d++) {
          const dropX = fx.x + Math.sin(d * 1.3) * (20 + prog * 45);
          const dropY = fx.y + Math.cos(d * 1.3) * (15 + prog * 35);
          ctx.fillStyle = `rgba(185, 28, 28, ${alpha})`;
          ctx.beginPath();
          ctx.arc(dropX, dropY, 3, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.restore();

      } else if (fx.type === "shadowraze") {
        // --- SHADOW FIEND SHADOWRAZE (Инфернальный темный столб душ) ---
        ctx.save();
        const prog = 1 - (fx.timer / (fx.maxTimer || 32));
        const alpha = fx.timer < 8 ? fx.timer / 8 : (prog < 0.25 ? prog / 0.25 : 1 - (prog - 0.25) / 0.75);

        // Ground dark runic circle
        ctx.fillStyle = `rgba(88, 28, 135, ${0.4 * alpha})`;
        ctx.beginPath();
        ctx.ellipse(fx.x, fx.y + 8, (fx.radius || 46) * prog, ((fx.radius || 46) * 0.45) * prog, 0, 0, Math.PI * 2);
        ctx.fill();

        // Vertical erupting soul pillar
        const pillarH = 75 * prog;
        const grad = ctx.createLinearGradient(fx.x, fx.y + 8, fx.x, fx.y + 8 - pillarH);
        grad.addColorStop(0, `rgba(168, 85, 247, ${0.85 * alpha})`);
        grad.addColorStop(0.5, `rgba(107, 33, 168, ${0.75 * alpha})`);
        grad.addColorStop(1, `rgba(30, 27, 75, ${0.2 * alpha})`);
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.ellipse(fx.x, fx.y + 8 - pillarH / 2, 24 * (1 - prog * 0.3), pillarH / 2, 0, 0, Math.PI * 2);
        ctx.fill();

        // Soul fire core
        ctx.strokeStyle = `rgba(233, 213, 255, ${0.9 * alpha})`;
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.moveTo(fx.x, fx.y + 8);
        ctx.lineTo(fx.x, fx.y + 8 - pillarH);
        ctx.stroke();
        ctx.restore();

      } else if (fx.type === "requiem_of_souls") {
        // --- SHADOW FIEND REQUIEM OF SOULS (Расширяющееся кольцо из 12 духов) ---
        ctx.save();
        const prog = 1 - (fx.timer / (fx.maxTimer || 45));
        const alpha = 1 - prog;
        const ringRadius = 25 + prog * 180;

        // Expanding dark mist ring
        ctx.strokeStyle = `rgba(168, 85, 247, ${0.65 * alpha})`;
        ctx.lineWidth = 3.5;
        ctx.beginPath();
        ctx.arc(fx.x, fx.y, ringRadius, 0, Math.PI * 2);
        ctx.stroke();

        // 12 flying dark souls in 360 degrees
        for (let s = 0; s < 12; s++) {
          const sa = (s * Math.PI * 2) / 12 + (prog * 0.5);
          const sx = fx.x + Math.cos(sa) * ringRadius;
          const sy = fx.y + Math.sin(sa) * ringRadius;

          // Soul head
          ctx.fillStyle = `rgba(192, 132, 252, ${0.95 * alpha})`;
          ctx.beginPath();
          ctx.arc(sx, sy, 5, 0, Math.PI * 2);
          ctx.fill();

          // Soul tail directed towards center
          ctx.strokeStyle = `rgba(126, 34, 206, ${0.7 * alpha})`;
          ctx.lineWidth = 3;
          ctx.beginPath();
          ctx.moveTo(sx, sy);
          ctx.lineTo(sx - Math.cos(sa) * 16, sy - Math.sin(sa) * 16);
          ctx.stroke();
        }
        ctx.restore();

      } else if (fx.type === "meat_hook") {
        // --- PUDGE MEAT HOOK (Железная цепь с зазубренным крюком к боссу) ---
        ctx.save();
        const hx = fx.curX !== undefined ? fx.curX : fx.toX;
        const hy = fx.curY !== undefined ? fx.curY : fx.toY;
        const ang = Math.atan2(hy - fx.fromY, hx - fx.fromX);
        const dist = Math.hypot(hx - fx.fromX, hy - fx.fromY);
        const linkCount = Math.max(3, Math.floor(dist / 14));

        // Chain links
        ctx.strokeStyle = "#94a3b8";
        ctx.lineWidth = 3.5;
        for (let l = 0; l <= linkCount; l++) {
          const lx = fx.fromX + Math.cos(ang) * (l * 14);
          const ly = fx.fromY + Math.sin(ang) * (l * 14);
          ctx.beginPath();
          ctx.ellipse(lx, ly, 6, 3, ang, 0, Math.PI * 2);
          ctx.stroke();
        }

        // Curved Meat Hook Head
        ctx.translate(hx, hy);
        ctx.rotate(ang);
        ctx.fillStyle = "#cbd5e1";
        ctx.beginPath();
        ctx.moveTo(0, -6);
        ctx.lineTo(16, 0);
        ctx.lineTo(8, 12);
        ctx.lineTo(4, 8);
        ctx.lineTo(8, 0);
        ctx.closePath();
        ctx.fill();

        ctx.strokeStyle = "#ef4444";
        ctx.lineWidth = 2;
        ctx.stroke();
        ctx.restore();

      } else if (fx.type === "pudge_dismember") {
        // --- PUDGE DISMEMBER & ROT (Ядовитое облако и удары тесаком) ---
        ctx.save();
        const prog = 1 - (fx.timer / (fx.maxTimer || 45));
        const alpha = 1 - prog;

        // Toxic Green Poison Miasma
        ctx.fillStyle = `rgba(34, 197, 94, ${0.32 * alpha})`;
        ctx.beginPath();
        ctx.arc(fx.x, fx.y, 55, 0, Math.PI * 2);
        ctx.fill();

        // Poison bubbling particles
        for (let b = 0; b < 6; b++) {
          const bx = fx.x + Math.sin(b * 1.5 + fx.timer * 0.4) * 35;
          const by = fx.y + Math.cos(b * 1.5 + fx.timer * 0.4) * 35;
          ctx.fillStyle = `rgba(134, 239, 172, ${0.85 * alpha})`;
          ctx.beginPath();
          ctx.arc(bx, by, 4, 0, Math.PI * 2);
          ctx.fill();
        }

        // Red butcher cleaver slashes on boss
        ctx.strokeStyle = `rgba(239, 68, 68, ${0.9 * alpha})`;
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.moveTo(fx.x - 25, fx.y - 20);
        ctx.lineTo(fx.x + 25, fx.y + 20);
        ctx.stroke();
        ctx.restore();

      } else if (fx.type === "wraithfire") {
        // --- WRAITH KING WRAITHFIRE BLAST (Призрачный пылающий череп) ---
        ctx.save();
        ctx.translate(fx.x, fx.y);

        // Spectral green flame trail
        ctx.strokeStyle = "rgba(16, 185, 129, 0.75)";
        ctx.lineWidth = 6;
        ctx.beginPath();
        ctx.arc(0, 0, 14, 0, Math.PI * 2);
        ctx.stroke();

        // Glowing green skull orb
        ctx.fillStyle = "#10b981";
        ctx.beginPath();
        ctx.arc(0, 0, 10, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = "#a7f3d0";
        ctx.beginPath();
        ctx.arc(0, 0, 6, 0, Math.PI * 2);
        ctx.fill();

        // Eye sockets
        ctx.fillStyle = "#064e3b";
        ctx.beginPath();
        ctx.arc(-3, -2, 1.8, 0, Math.PI * 2);
        ctx.arc(3, -2, 1.8, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();

      } else if (fx.type === "wk_skeletons") {
        // --- WRAITH KING SKELETON SUMMON AURA ---
        ctx.save();
        const alpha = Math.min(1.0, fx.timer / 30);
        ctx.strokeStyle = `rgba(16, 185, 129, ${0.65 * alpha})`;
        ctx.lineWidth = 2.5;
        ctx.setLineDash([8, 4]);
        ctx.beginPath();
        ctx.arc(fx.x, fx.y, 42, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.restore();

      } else if (fx.type === "mana_slash") {
        // --- ANTI-MAGE DUAL MANA BLADE STRIKE ---
        ctx.save();
        const prog = 1 - (fx.timer / (fx.maxTimer || 24));
        const alpha = 1 - prog;

        ctx.strokeStyle = `rgba(56, 189, 248, ${0.95 * alpha})`;
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.moveTo(fx.x - 30, fx.y - 25);
        ctx.lineTo(fx.x + 30, fx.y + 25);
        ctx.moveTo(fx.x + 30, fx.y - 25);
        ctx.lineTo(fx.x - 30, fx.y + 25);
        ctx.stroke();

        ctx.strokeStyle = `rgba(255, 255, 255, ${0.9 * alpha})`;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(fx.x - 30, fx.y - 25);
        ctx.lineTo(fx.x + 30, fx.y + 25);
        ctx.moveTo(fx.x + 30, fx.y - 25);
        ctx.lineTo(fx.x - 30, fx.y + 25);
        ctx.stroke();
        ctx.restore();

      } else if (fx.type === "mana_void") {
        // --- ANTI-MAGE MANA VOID (Коллапсирующая сфера маны и взрыв) ---
        ctx.save();
        const prog = 1 - (fx.timer / (fx.maxTimer || 40));

        if (prog < 0.5) {
          // Implosion phase: void sphere condenses inward
          const imploseR = 60 * (1 - prog * 1.5);
          ctx.fillStyle = `rgba(147, 51, 234, ${0.5 + prog})`;
          ctx.beginPath();
          ctx.arc(fx.x, fx.y, Math.max(6, imploseR), 0, Math.PI * 2);
          ctx.fill();

          ctx.strokeStyle = "#38bdf8";
          ctx.lineWidth = 3;
          ctx.beginPath();
          ctx.arc(fx.x, fx.y, Math.max(10, imploseR + 10), 0, Math.PI * 2);
          ctx.stroke();
        } else {
          // Detonation phase: massive electric shockwave explosion
          const expProg = (prog - 0.5) / 0.5;
          const expRad = 15 + expProg * 90;
          ctx.strokeStyle = `rgba(56, 189, 248, ${0.9 * (1 - expProg)})`;
          ctx.lineWidth = 4;
          ctx.beginPath();
          ctx.arc(fx.x, fx.y, expRad, 0, Math.PI * 2);
          ctx.stroke();

          ctx.strokeStyle = `rgba(168, 85, 247, ${0.8 * (1 - expProg)})`;
          ctx.lineWidth = 2.5;
          ctx.beginPath();
          ctx.arc(fx.x, fx.y, expRad * 0.75, 0, Math.PI * 2);
          ctx.stroke();
        }
        ctx.restore();

      } else if (fx.type === "croak_blast") {
        // --- LARGO CROAK OF GENIUS (Акустическая волна кваканья) ---
        ctx.save();
        const prog = 1 - (fx.timer / (fx.maxTimer || 30));
        const alpha = Math.max(0, 1 - prog);
        const curR = 15 + prog * (fx.radius || 85);
        ctx.strokeStyle = `rgba(168, 85, 247, ${0.9 * alpha})`;
        ctx.lineWidth = 4;
        ctx.beginPath();
        ctx.arc(fx.x, fx.y, curR, 0, Math.PI * 2);
        ctx.stroke();

        ctx.strokeStyle = `rgba(216, 180, 254, ${0.7 * alpha})`;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(fx.x, fx.y, curR * 0.7, 0, Math.PI * 2);
        ctx.stroke();

        for (let n = 0; n < 3; n++) {
          const noteAngle = (n * Math.PI * 2 / 3) + prog * 2;
          const nx = fx.x + Math.cos(noteAngle) * curR * 0.8;
          const ny = fx.y + Math.sin(noteAngle) * curR * 0.8;
          ctx.fillStyle = `rgba(250, 204, 21, ${alpha})`;
          ctx.font = "bold 14px sans-serif";
          ctx.fillText("🎵", nx - 6, ny);
        }
        ctx.restore();

      } else if (fx.type === "rhapsody_beat") {
        // --- LARGO AMPHIBIAN RHAPSODY BEAT (Гармонический взрыв хила и урона) ---
        ctx.save();
        const prog = 1 - (fx.timer / (fx.maxTimer || 25));
        const alpha = Math.max(0, 1 - prog);
        const curR = fx.radius + (fx.maxRadius - fx.radius) * prog;

        // Emerald healing pulse
        ctx.strokeStyle = `rgba(34, 197, 94, ${0.85 * alpha})`;
        ctx.lineWidth = 4.5;
        ctx.beginPath();
        ctx.arc(fx.x, fx.y, curR, 0, Math.PI * 2);
        ctx.stroke();

        // Golden harmonic ring
        ctx.strokeStyle = `rgba(250, 204, 21, ${0.75 * alpha})`;
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.arc(fx.x, fx.y, curR * 0.85, 0, Math.PI * 2);
        ctx.stroke();

        // Central harmonic soft glow
        ctx.fillStyle = `rgba(74, 222, 128, ${0.2 * alpha})`;
        ctx.beginPath();
        ctx.arc(fx.x, fx.y, curR * 0.4, 0, Math.PI * 2);
        ctx.fill();

        ctx.restore();
      }
    }

    // ---- 12. BOSS & ENEMY PROJECTILES ----
    for (const proj of ARENA.bossProjectiles) {
      if (proj.isMeatHook) {
        ctx.save();
        ctx.fillStyle = "#78716c";
        ctx.strokeStyle = "#e2e8f0";
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.arc(proj.x, proj.y, proj.radius || 10, 0, Math.PI * 2);
        ctx.fill(); ctx.stroke();
        ctx.restore();
      } else if (proj.isSpiderBot) {
        ctx.save();
        ctx.fillStyle = "#eab308";
        ctx.fillRect(proj.x - 5, proj.y - 4, 10, 8);
        ctx.strokeStyle = "#713f12";
        ctx.lineWidth = 1.5;
        ctx.strokeRect(proj.x - 5, proj.y - 4, 10, 8);
        ctx.restore();
      } else {
        drawProceduralProjectile(ctx, { x: proj.x, y: proj.y, color: proj.color, radius: proj.radius, isBossFireball: true }, time);
      }
    }
    if (ARENA.enemyProjectiles) {
      for (const proj of ARENA.enemyProjectiles) {
        drawProceduralProjectile(ctx, proj, time);
      }
    }

    // ---- 13. FLOATING TEXTS ----
    for (const ft of ARENA.floatingTexts) {
      ctx.save();
      ctx.globalAlpha = Math.max(0, ft.opacity);
      ctx.font = "bold 12px sans-serif";
      ctx.fillStyle = ft.color;
      ctx.textAlign = "center";
      ctx.fillText(ft.text, ft.x, ft.y);
      ctx.restore();
    }

    // Close Camera Trauma translate so Top HUD & Overlays remain rock-solid in screen space
    ctx.restore();

    // ---- 14. TOP HUD (Grand Boss Banner on Boss Wave or Raid Battle) ----
    if (ARENA.isRaidBossBattle || (ARENA.isBossActive && ARENA.bossEntity)) {
      const bTarget = ARENA.bossEntity || ARENA.currentRaidBoss;
      if (bTarget) renderGrandBossHUD(ctx, clientW, clientH, bTarget, time);
    } else {
      ctx.fillStyle = "rgba(15, 23, 42, 0.88)";
      ctx.beginPath();
      safeRoundRect(ctx, 10, 56, clientW - 20, 28, 12); // Moved down from 8 to 56
      ctx.fill();

      ctx.font = "bold 11px sans-serif";
      ctx.fillStyle = "#facc15";
      ctx.textAlign = "left";
      ctx.fillText(`Этаж ${RPG_STATE.profile?.dungeon_floor || 1} • Волна ${ARENA.waveNumber}/${ARENA.waveMax}`, 18, 74); // 26 -> 74

      ctx.textAlign = "right";
      ctx.fillStyle = "#94a3b8";
      const killLabel = ARENA.isRaidBossBattle
        ? `👑 РЕЙД-БОСС: ${ARENA.bossEntity?.name || "БОСС"}`
        : `Убито: ${ARENA.creepsKilledInWave}/${ARENA.creepsNeededForWave}`;
      ctx.fillText(killLabel, w - 18, 74); // 26 -> 74
    }

    // Skill 1 & Ult CD in HUD
    let cdHudY = h - 22;
    if (ARENA.skill1Cooldown > 0) {
      const sPct = ARENA.skill1Cooldown / ARENA.skill1CooldownMax;
      ctx.fillStyle = "rgba(0,0,0,0.5)";
      ctx.fillRect(10, cdHudY, 52, 9);
      ctx.fillStyle = "#38bdf8";
      ctx.fillRect(10, cdHudY, 52 * (1 - sPct), 9);
      ctx.font = "bold 7.5px sans-serif";
      ctx.fillStyle = "#e0f2fe";
      ctx.textAlign = "left";
      ctx.fillText(`Скилл ${Math.ceil(ARENA.skill1Cooldown / 60)}с`, 12, cdHudY + 7);
      cdHudY -= 11;
    }
    if (ARENA.ultCooldown > 0) {
      const ultPct = ARENA.ultCooldown / ARENA.ultCooldownMax;
      ctx.fillStyle = "rgba(0,0,0,0.5)";
      ctx.fillRect(10, cdHudY, 52, 9);
      ctx.fillStyle = "#a855f7";
      ctx.fillRect(10, cdHudY, 52 * (1 - ultPct), 9);
      ctx.font = "bold 7.5px sans-serif";
      ctx.fillStyle = "#e9d5ff";
      ctx.textAlign = "left";
      ctx.fillText(`Ульта ${Math.ceil(ARENA.ultCooldown / 60)}с`, 12, cdHudY + 7);
    }

    // ---- 15. BLOCK WINDOW (Boss special) ----
    if (ARENA.blockWindowActive) {
      const bPct = ARENA.blockWindowTimer / ARENA.blockWindowMax;
      const pulse = 0.7 + Math.sin(Date.now() / 100) * 0.3;
      ctx.save();
      ctx.fillStyle = "rgba(0,0,0,0.55)";
      ctx.fillRect(w / 2 - 75, h / 2 - 35, 150, 65);
      ctx.strokeStyle = `rgba(59, 130, 246, ${pulse})`;
      ctx.lineWidth = 3;
      ctx.strokeRect(w / 2 - 75, h / 2 - 35, 150, 65);

      ctx.font = "bold 20px sans-serif";
      ctx.fillStyle = "#3b82f6";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("🛡️ БЛОК!", w / 2, h / 2 - 10);

      ctx.fillStyle = "rgba(0,0,0,0.5)";
      ctx.fillRect(w / 2 - 55, h / 2 + 14, 110, 7);
      ctx.fillStyle = "#3b82f6";
      ctx.fillRect(w / 2 - 55, h / 2 + 14, 110 * bPct, 7);
      ctx.restore();
    }

    // ---- 16. QTE WINDOW (Boss rage) ----
    if (ARENA.qteActive) {
      const qPct = ARENA.qteTimer / ARENA.qteMaxTimer;
      const pulse = 0.7 + Math.sin(Date.now() / 80) * 0.3;
      ctx.save();
      ctx.fillStyle = "rgba(0,0,0,0.55)";
      ctx.fillRect(w / 2 - 85, h / 2 - 38, 170, 72);
      ctx.strokeStyle = `rgba(250, 204, 21, ${pulse})`;
      ctx.lineWidth = 3;
      ctx.strokeRect(w / 2 - 85, h / 2 - 38, 170, 72);

      ctx.font = "bold 22px sans-serif";
      ctx.fillStyle = "#facc15";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("⚡ МЕГА-УДАР!", w / 2, h / 2 - 8);

      ctx.fillStyle = "rgba(0,0,0,0.5)";
      ctx.fillRect(w / 2 - 65, h / 2 + 18, 130, 7);
      ctx.fillStyle = "#facc15";
      ctx.fillRect(w / 2 - 65, h / 2 + 18, 130 * qPct, 7);
      ctx.restore();
    }

    // ---- 17. WAVE PROMPT OVERLAY ----
    if (ARENA.waveState === "prompt") {
      ctx.save();
      ctx.fillStyle = "rgba(0,0,0,0.65)";
      ctx.fillRect(0, 0, w, h);

      const cardW = 270, cardH = 152;
      const cx = w / 2 - cardW / 2, cy = h / 2 - cardH / 2;

      ctx.fillStyle = "rgba(15, 23, 42, 0.95)";
      ctx.beginPath();
      safeRoundRect(ctx, cx, cy, cardW, cardH, 16);
      ctx.fill();
      ctx.strokeStyle = "#facc15";
      ctx.lineWidth = 2;
      ctx.beginPath();
      safeRoundRect(ctx, cx, cy, cardW, cardH, 16);
      ctx.stroke();

      ctx.font = "bold 15px sans-serif";
      ctx.fillStyle = "#facc15";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";

      const nextW = ARENA.waveNumber + 1;
      const isBossNext = nextW === ARENA.waveMax;
      if (ARENA.waveNumber === 0) {
        const flr = RPG_STATE.profile?.dungeon_floor || 1;
        ctx.fillText(`🏰 Новый этаж ${flr}!`, w / 2, cy + 24);
        ctx.font = "12px sans-serif";
        ctx.fillStyle = "#94a3b8";
        ctx.fillText(`Следующая: Волна 1/${ARENA.waveMax}`, w / 2, cy + 46);
      } else {
        ctx.fillText(`✅ Волна ${ARENA.waveNumber}/${ARENA.waveMax} зачищена!`, w / 2, cy + 24);
        ctx.font = "12px sans-serif";
        ctx.fillStyle = isBossNext ? "#ef4444" : "#94a3b8";
        ctx.fillText(isBossNext ? "⚠️ Следующая: БОСС ЭТАЖА!" : `Следующая: Волна ${nextW}/${ARENA.waveMax}`, w / 2, cy + 46);
      }

      // Main action button
      const btnX = w / 2 - 95, btnY = cy + 68, btnW = 190, btnH = 34;
      ctx.fillStyle = "#facc15";
      ctx.beginPath();
      safeRoundRect(ctx, btnX, btnY, btnW, btnH, 10);
      ctx.fill();

      ctx.font = "bold 13px sans-serif";
      ctx.fillStyle = "#0f172a";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("▶ Перейти дальше", w / 2, btnY + btnH / 2);

      // Disable confirmation button right on overlay
      const optBtnX = w / 2 - 95, optBtnY = cy + 110, optBtnW = 190, optBtnH = 28;
      ctx.fillStyle = "rgba(30, 41, 59, 0.95)";
      ctx.beginPath();
      safeRoundRect(ctx, optBtnX, optBtnY, optBtnW, optBtnH, 8);
      ctx.fill();
      ctx.strokeStyle = "rgba(148, 163, 184, 0.35)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      safeRoundRect(ctx, optBtnX, optBtnY, optBtnW, optBtnH, 8);
      ctx.stroke();

      ctx.font = "bold 10px sans-serif";
      ctx.fillStyle = "#38bdf8";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("⏭️ Отключить подтверждение", w / 2, optBtnY + optBtnH / 2);

      ctx.restore();
      ARENA._promptBtnBounds = { x: btnX, y: btnY, w: btnW, h: btnH };
      ARENA._promptDisableBtnBounds = { x: optBtnX, y: optBtnY, w: optBtnW, h: optBtnH };
    }

    // ---- 18. RETRY PROMPT OVERLAY (On Death — NEVER auto clear!) ----
    if (ARENA.waveState === "retry_prompt") {
      ctx.save();
      ctx.fillStyle = "rgba(0,0,0,0.7)";
      ctx.fillRect(0, 0, w, h);

      const cardW = 270, cardH = 135;
      const cx = w / 2 - cardW / 2, cy = h / 2 - cardH / 2;

      ctx.fillStyle = "rgba(15, 23, 42, 0.95)";
      ctx.beginPath();
      safeRoundRect(ctx, cx, cy, cardW, cardH, 16);
      ctx.fill();
      ctx.strokeStyle = "#ef4444";
      ctx.lineWidth = 2;
      ctx.beginPath();
      safeRoundRect(ctx, cx, cy, cardW, cardH, 16);
      ctx.stroke();

      ctx.font = "bold 16px sans-serif";
      ctx.fillStyle = "#ef4444";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("💀 ВАШ ГЕРОЙ ПАЛ!", w / 2, cy + 28);

      ctx.font = "11.5px sans-serif";
      ctx.fillStyle = "#94a3b8";
      ctx.fillText("Этаж не зачищен! Начните заново с 1-й волны.", w / 2, cy + 52);

      const btnX = w / 2 - 95, btnY = cy + 78, btnW = 190, btnH = 38;
      ctx.fillStyle = "#ef4444";
      ctx.beginPath();
      safeRoundRect(ctx, btnX, btnY, btnW, btnH, 12);
      ctx.fill();

      ctx.font = "bold 13px sans-serif";
      ctx.fillStyle = "#ffffff";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("🔄 Начать заново (1-я волна)", w / 2, btnY + btnH / 2);

      ctx.restore();
      ARENA._promptBtnBounds = { x: btnX, y: btnY, w: btnW, h: btnH };
    }

    // ---- 18b. BOSS DEFEAT OVERLAY (On Raid Boss Defeat / Player Death) ----
    if (ARENA.waveState === "boss_defeat") {
      ctx.save();
      ctx.fillStyle = "rgba(0,0,0,0.85)";
      ctx.fillRect(0, 0, clientW, clientH);

      const cardW = Math.min(300, clientW - 32);
      const cardH = 185;
      const cx = (clientW - cardW) / 2;
      const cy = (clientH - cardH) / 2;

      ctx.fillStyle = "rgba(15, 23, 42, 0.96)";
      ctx.beginPath();
      safeRoundRect(ctx, cx, cy, cardW, cardH, 16);
      ctx.fill();
      ctx.strokeStyle = "#ef4444";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      safeRoundRect(ctx, cx, cy, cardW, cardH, 16);
      ctx.stroke();

      ctx.font = "bold 15px sans-serif";
      ctx.fillStyle = "#ef4444";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("💀 ВЫ ПОГИБЛИ В БИТВЕ С БОССОМ!", clientW / 2, cy + 26);

      const bEntity = ARENA.bossEntity;
      const hpPct = bEntity && bEntity.maxHp ? Math.max(0, Math.min(100, Math.round((bEntity.hp / bEntity.maxHp) * 100))) : 0;
      const remHp = bEntity ? formatCompact(bEntity.hp) : "0";
      const totalHp = bEntity ? formatCompact(bEntity.maxHp) : "0";
      ctx.font = "11.5px sans-serif";
      ctx.fillStyle = "#e2e8f0";
      ctx.fillText(`У босса осталось: ${hpPct}% HP (${remHp} / ${totalHp})`, clientW / 2, cy + 52);
      ctx.font = "10px sans-serif";
      ctx.fillStyle = "#94a3b8";
      ctx.fillText("Прокачайте героя, подберите билд и повторите!", clientW / 2, cy + 70);

      // Button 1: Попробовать снова
      const btnW = Math.min(230, cardW - 32);
      const btnH = 34;
      const btnX = (clientW - btnW) / 2;
      const btnY = cy + 96;
      ctx.fillStyle = "#ef4444";
      ctx.beginPath();
      safeRoundRect(ctx, btnX, btnY, btnW, btnH, 10);
      ctx.fill();
      ctx.font = "bold 12px sans-serif";
      ctx.fillStyle = "#ffffff";
      ctx.fillText("🔄 Попробовать снова", clientW / 2, btnY + btnH / 2);

      // Button 2: В лобби боссов / Начать с волны 1
      const exitBtnW = btnW;
      const exitBtnH = 30;
      const exitBtnX = btnX;
      const exitBtnY = cy + 138;
      ctx.fillStyle = "#334155";
      ctx.beginPath();
      safeRoundRect(ctx, exitBtnX, exitBtnY, exitBtnW, exitBtnH, 8);
      ctx.fill();
      ctx.font = "bold 11px sans-serif";
      ctx.fillStyle = "#cbd5e1";
      const exitLabel = ARENA.isRaidBossBattle ? "🚪 В лобби боссов" : "🏠 Начать с волны 1";
      ctx.fillText(exitLabel, clientW / 2, exitBtnY + exitBtnH / 2);

      ctx.restore();
      ARENA._bossDefeatRetryBounds = { x: btnX, y: btnY, w: btnW, h: btnH };
      ARENA._bossDefeatExitBounds = { x: exitBtnX, y: exitBtnY, w: exitBtnW, h: exitBtnH };
    }

    // ---- 19. FLOOR CLEAR OVERLAY ----
    if (ARENA.waveState === "floor_clear") {
      ctx.save();
      ctx.fillStyle = "rgba(0,0,0,0.6)";
      ctx.fillRect(0, 0, w, h);
      ctx.font = "bold 22px sans-serif";
      ctx.fillStyle = "#22c55e";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("👑 ЭТАЖ 20/20 ЗАЧИЩЕН!", w / 2, h / 2 - 10);
      ctx.font = "12px sans-serif";
      ctx.fillStyle = "#94a3b8";
      ctx.fillText("Награды начислены! Следующий этаж ждёт...", w / 2, h / 2 + 20);
      ctx.restore();
    }

    // ---- 20. BOSS INTRO OVERLAY ----
    if (ARENA.waveState === "boss_intro") {
      const pulse = 0.4 + Math.sin(Date.now() / 200) * 0.2;
      ctx.save();
      ctx.fillStyle = `rgba(0,0,0,${pulse})`;
      ctx.fillRect(0, 0, w, h);
      ctx.font = "bold 24px sans-serif";
      ctx.fillStyle = "#ef4444";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("⚠️ БОСС ЭТАЖА! (Волна 20/20) ⚠️", w / 2, h / 2 - 15);
      if (ARENA.bossEntity) {
        ctx.font = "bold 16px sans-serif";
        ctx.fillStyle = "#facc15";
        ctx.fillText(ARENA.bossEntity.name, w / 2, h / 2 + 15);
      }
      ctx.restore();
    }

    // ---- 21. BOSS VICTORY SHOWCASE OVERLAY ----
    if (ARENA.waveState === "boss_victory") {
      if (!ARENA.isRaidBossBattle && !RPG_STATE.lastBossChestReward) {
        ARENA.waveState = "fighting";
        return;
      }
      ctx.save();
      ctx.fillStyle = "rgba(0, 0, 0, 0.80)";
      ctx.fillRect(0, 0, clientW, clientH);

      const cardW = Math.min(310, clientW - 32);
      const cardH = 175;
      const cx = (clientW - cardW) / 2;
      const cy = (clientH - cardH) / 2;

      ctx.fillStyle = "rgba(15, 23, 42, 0.96)";
      ctx.beginPath();
      safeRoundRect(ctx, cx, cy, cardW, cardH, 16);
      ctx.fill();
      ctx.strokeStyle = "#facc15";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      safeRoundRect(ctx, cx, cy, cardW, cardH, 16);
      ctx.stroke();

      ctx.font = "bold 16px sans-serif";
      ctx.fillStyle = "#facc15";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("👑 РЕЙД-БОСС ПОВЕРЖЕН! 🏆", clientW / 2, cy + 30);

      ctx.font = "11.5px sans-serif";
      ctx.fillStyle = "#e2e8f0";
      ctx.fillText("Великая победа! Награда ждёт вас!", clientW / 2, cy + 58);

      const btnW = Math.min(230, cardW - 32);
      const btnH = 38;
      const btnX = (clientW - btnW) / 2;
      const btnY = cy + 102;
      ctx.fillStyle = "#eab308";
      ctx.beginPath();
      safeRoundRect(ctx, btnX, btnY, btnW, btnH, 12);
      ctx.fill();

      ctx.font = "bold 13px sans-serif";
      ctx.fillStyle = "#0f172a";
      ctx.fillText("🎁 ЗАБРАТЬ НАГРАДУ", clientW / 2, btnY + btnH / 2);
      ctx.restore();
      ARENA._promptBtnBounds = { x: btnX, y: btnY, w: btnW, h: btnH };
    }

    // DMC STYLE METER HUD (D, C, B, A, S, SS, SSS) — perfectly centered in screen space
    drawStyleMeterHUD(ctx, ARENA.styleMeter, ARENA.combo, w);

    // ---- 22. BOSS ARENA MOBILE MOVEMENT HINTS (Subtle translucent touch guides) ----
    if (ARENA.bossArenaMode && ARENA.waveState === "fighting") {
      ctx.save();
      const hintY = h - 14;
      ctx.font = "bold 9.5px sans-serif";
      // Left touch zone guide
      ctx.fillStyle = ARENA.moveInput.left ? "rgba(56, 189, 248, 0.9)" : "rgba(255, 255, 255, 0.35)";
      ctx.textAlign = "left";
      ctx.fillText("◀ БЕГ ВЛЕВО", 14, hintY);
      // Right touch zone guide
      ctx.fillStyle = ARENA.moveInput.right ? "rgba(56, 189, 248, 0.9)" : "rgba(255, 255, 255, 0.35)";
      ctx.textAlign = "right";
      ctx.fillText("БЕГ ВПРАВО ▶", w - 14, hintY);
      // Center tap hint
      ctx.fillStyle = "rgba(250, 204, 21, 0.4)";
      ctx.textAlign = "center";
      ctx.fillText("⚔️ ТАП / КНОПКИ — АТАКА", w / 2, hintY);
      ctx.restore();
    }
  }


  // ===========================================================================
  // MULTIPLAYER DUELS & CO-OP (PvP & BOSSES)
  // ===========================================================================

  async function loadCoopBosses() {
    try {
      const bosses = await api.getCoopBosses();
      RPG_STATE.coopBosses = bosses || [];
      renderRoot();
    } catch (e) {
      console.error("Failed to load co-op bosses:", e);
    }
  }

  async function createCoopRaid(bossId, isSolo = false) {
    try {
      triggerHaptic("medium");
      RPG_STATE.selectedBoss = bossId;
      const myName = RPG_STATE.profile?.user_name || "Герой";
      const oppLabel = isSolo ? "Соло-рейд" : "Босс-Рейд";
      const room = await api.inviteGame(0, myName, "rpg_coop", "white", oppLabel, bossId, isSolo, RPG_STATE.profile);
      RPG_STATE.coopRoomId = room.room_id;
      RPG_STATE.coopRoomData = room;
      startCoopPolling();
      renderRoot();
    } catch (err) {
      alert(err.message || "Не удалось создать рейд");
    }
  }

  function startCoopPolling() {
    stopCoopPolling();
    RPG_STATE.coopPolling = setInterval(async () => {
      if (!RPG_STATE.coopRoomId) return;
      try {
        const updated = await api.getGameRoom(RPG_STATE.coopRoomId);
        RPG_STATE.coopRoomData = updated;
        renderRoot();
      } catch (e) {
        if (e && (e.status === 404 || (e.message && (e.message.includes("404") || e.message.includes("не найден"))))) {
          console.warn("[Coop] Room no longer exists (404), stopping polling");
          stopCoopPolling();
          RPG_STATE.coopRoomId = null;
          RPG_STATE.coopRoomData = null;
          renderRoot();
        }
      }
    }, 1500);
  }

  function stopCoopPolling() {
    if (RPG_STATE.coopPolling) {
      clearInterval(RPG_STATE.coopPolling);
      RPG_STATE.coopPolling = null;
    }
  }

  async function sendCoopAction(actionType) {
    if (!RPG_STATE.coopRoomId) return;
    try {
      triggerHaptic(actionType === "skill" ? "heavy" : "medium");
      const bossToken = document.getElementById("coop-boss-token");
      if (bossToken) {
        bossToken.style.transform = "scale(0.88) rotate(-4deg)";
        setTimeout(() => {
          if (bossToken) bossToken.style.transform = "scale(1.08) rotate(4deg)";
          setTimeout(() => {
            if (bossToken) bossToken.style.transform = "none";
          }, 150);
        }, 100);
      }
      const updated = await api.sendGameMove(RPG_STATE.coopRoomId, { action: actionType });
      RPG_STATE.coopRoomData = updated;
      renderRoot();
    } catch (err) {
      alert(err.message || "Ошибка хода в рейде");
    }
  }

  async function addCoopBot() {
    if (!RPG_STATE.coopRoomId) return;
    try {
      triggerHaptic("medium");
      const updated = await api.addCoopBot(RPG_STATE.coopRoomId);
      RPG_STATE.coopRoomData = updated;
      renderRoot();
    } catch (err) {
      alert(err.message || "Не удалось добавить бота");
    }
  }

  function leaveCoopRoom() {
    stopCoopPolling();
    RPG_STATE.coopRoomId = null;
    RPG_STATE.coopRoomData = null;
    renderRoot();
  }

  async function joinCoopRoom(targetRoomId) {
    const input = document.getElementById("coop-room-code-input");
    const roomId = targetRoomId || input?.value?.trim();
    if (!roomId) {
      alert("Введите код комнаты рейда");
      return;
    }
    try {
      triggerHaptic("medium");
      const myName = RPG_STATE.profile?.user_name || "Герой";
      const room = await api.joinGameRoom(roomId, myName);
      RPG_STATE.coopRoomId = room.room_id || roomId;
      RPG_STATE.coopRoomData = room;
      startCoopPolling();
      renderRoot();
    } catch (err) {
      alert(err.message || "Не удалось подключиться к рейду");
    }
  }

  async function loadClassmates() {
    try {
      const res = await api.getClassmates();
      RPG_STATE.classmates = res || [];
      renderRoot();
    } catch (e) {
      console.error("Failed to load classmates:", e);
    }
  }

  async function challengeClassmate(tgId, classmateName) {
    try {
      triggerHaptic("medium");
      const myName = RPG_STATE.profile?.user_name || "Дуэлянт";
      const room = await api.inviteGame(tgId, myName, "rpg_duel", "white", classmateName);
      RPG_STATE.pvpRoomId = room.room_id;
      RPG_STATE.pvpRoomData = room;
      startPvPPolling();
      renderRoot();
    } catch (err) {
      alert(err.message || "Не удалось вызвать на дуэль");
    }
  }

  function startPvPPolling() {
    stopPvPPolling();
    RPG_STATE.pvpPolling = setInterval(async () => {
      if (!RPG_STATE.pvpRoomId) return;
      try {
        const updated = await api.getGameRoom(RPG_STATE.pvpRoomId);
        RPG_STATE.pvpRoomData = updated;
        renderRoot();
      } catch (e) {
        if (e && (e.status === 404 || (e.message && (e.message.includes("404") || e.message.includes("не найден"))))) {
          console.warn("[PvP] Room no longer exists (404), stopping polling");
          stopPvPPolling();
          RPG_STATE.pvpRoomId = null;
          RPG_STATE.pvpRoomData = null;
          renderRoot();
        }
      }
    }, 1500);
  }

  function stopPvPPolling() {
    if (RPG_STATE.pvpPolling) {
      clearInterval(RPG_STATE.pvpPolling);
      RPG_STATE.pvpPolling = null;
    }
  }

  async function sendPvPAction(actionType) {
    if (!RPG_STATE.pvpRoomId) return;
    try {
      triggerHaptic("light");
      const updated = await api.sendGameMove(RPG_STATE.pvpRoomId, { action: actionType });
      RPG_STATE.pvpRoomData = updated;
      renderRoot();
    } catch (err) {
      alert(err.message || "Ошибка хода в дуэли");
    }
  }

  function leavePvPRoom() {
    stopPvPPolling();
    RPG_STATE.pvpRoomId = null;
    RPG_STATE.pvpRoomData = null;
    renderRoot();
  }

  async function loadLeaderboard() {
    try {
      const list = await api.getRpgLeaderboard();
      RPG_STATE.leaderboard = list || [];
      renderRoot();
    } catch (e) {
      console.error("Failed to load leaderboard:", e);
    }
  }

  // ===========================================================================
  // RENDERING ROOT & SUBTABS
  // ===========================================================================



// ============================================================================
// 07_boss_telegraphs.js — Rendering Unique Boss Visual Telegraphs & Ultimates
// (Black Hole, Chronosphere, Resonance Laser, Chains, and Special VFX)
// ============================================================================

function renderSpecialBossTelegraphs(ctx, ARENA, time) {
  if (!ARENA.bossTelegraphs) return;

  for (const bt of ARENA.bossTelegraphs) {
    ctx.save();

    // 1. BLACK HOLE (Чёрная Дыра Энигмы)
    if (bt.type === "black_hole") {
      const bhPulse = 1 + Math.sin(time * 0.1) * 0.05;
      const r = bt.r * bhPulse;

      // Outer Gravitational Accretion Disk
      const grad = ctx.createRadialGradient(bt.cx, bt.cy, r * 0.2, bt.cx, bt.cy, r);
      grad.addColorStop(0, "rgba(2, 6, 23, 0.95)");
      grad.addColorStop(0.45, "rgba(88, 28, 135, 0.75)");
      grad.addColorStop(0.85, "rgba(99, 102, 241, 0.4)");
      grad.addColorStop(1, "rgba(99, 102, 241, 0)");

      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(bt.cx, bt.cy, r, 0, Math.PI * 2);
      ctx.fill();

      // Swirling Event Horizon Rings
      ctx.strokeStyle = "rgba(168, 85, 247, 0.6)";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(bt.cx, bt.cy, r * 0.65, time * 0.08, time * 0.08 + Math.PI * 1.5);
      ctx.stroke();

      // Pure Void Center
      ctx.fillStyle = "#000000";
      ctx.beginPath();
      ctx.arc(bt.cx, bt.cy, r * 0.35, 0, Math.PI * 2);
      ctx.fill();

      // Infalling Star Matter
      for (let s = 0; s < 6; s++) {
        const sAng = -time * 0.12 + s * 1.05;
        const sDist = r * (0.4 + ((time * 0.02 + s * 0.15) % 0.55));
        ctx.fillStyle = "#e0e7ff";
        ctx.beginPath();
        ctx.arc(bt.cx + Math.cos(sAng) * sDist, bt.cy + Math.sin(sAng) * sDist, 2.5, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // 2. CHRONOSPHERE (Хроносфера Войда)
    else if (bt.type === "chronosphere") {
      const r = bt.r;
      // Translucent Violet Sphere
      ctx.fillStyle = "rgba(88, 28, 135, 0.35)";
      ctx.beginPath();
      ctx.arc(bt.cx, bt.cy, r, 0, Math.PI * 2);
      ctx.fill();

      // Glowing Temporal Grid Outline
      ctx.strokeStyle = "#c084fc";
      ctx.lineWidth = 3;
      ctx.shadowColor = "#a855f7";
      ctx.shadowBlur = 14;
      ctx.beginPath();
      ctx.arc(bt.cx, bt.cy, r, 0, Math.PI * 2);
      ctx.stroke();

      // Floating Clock Hour Hand in Center
      ctx.strokeStyle = "#f3e8ff";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.moveTo(bt.cx, bt.cy);
      ctx.lineTo(bt.cx + Math.cos(time * 0.04) * (r * 0.6), bt.cy + Math.sin(time * 0.04) * (r * 0.6));
      ctx.stroke();
      ctx.shadowBlur = 0;
    }

    // 3. ROTATING RESONANCE BEAM (Терзатель)
    else if (bt.type === "rotating_beam") {
      const bx2 = bt.cx + Math.cos(bt.angle) * bt.length;
      const by2 = bt.cy + Math.sin(bt.angle) * bt.length;

      ctx.strokeStyle = bt.color || "#e879f9";
      ctx.lineWidth = 8;
      ctx.shadowColor = "#c084fc";
      ctx.shadowBlur = 16;
      ctx.beginPath();
      ctx.moveTo(bt.cx, bt.cy);
      ctx.lineTo(bx2, by2);
      ctx.stroke();

      // Inner Core White Beam
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(bt.cx, bt.cy);
      ctx.lineTo(bx2, by2);
      ctx.stroke();
      ctx.shadowBlur = 0;
    }

    ctx.restore();
  }

  // Draw Pudge Hook Chains if projectile is Meat Hook
  for (const proj of (ARENA.bossProjectiles || [])) {
    if (proj.isMeatHook && proj.originX != null) {
      ctx.save();
      ctx.strokeStyle = "#78716c";
      ctx.lineWidth = 2.5;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(proj.originX, proj.originY);
      ctx.lineTo(proj.x, proj.y);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();
    }
  }
}

  function renderRoot() {
    const container = document.getElementById("rpg-root");
    if (!container) return;

    if (RPG_STATE.errorMessage) {
      container.innerHTML = `
        <div class="py-16 text-center space-y-3 px-4">
          <div class="text-4xl">вљ пёЏ</div>
          <h3 class="text-base font-bold text-red-500">РљСЂРёС‚РёС‡РµСЃРєР°СЏ РѕС€РёР±РєР°</h3>
          <p class="text-xs font-mono bg-slate-900 text-slate-300 p-3 rounded-xl border border-slate-700 text-left overflow-auto">${RPG_STATE.errorMessage}</p>
        </div>
      `;
      return;
    }

    if (RPG_STATE.loading && !RPG_STATE.profile) {
      container.innerHTML = `
        <div class="py-16 text-center space-y-3">
          <div class="inline-block w-8 h-8 border-4 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
          <p class="text-sm font-bold text-slate-500">Загрузка natarGRP...</p>
        </div>
      `;
      return;
    }

    if (!RPG_STATE.profile || !RPG_STATE.profile.hero_class) {
      container.innerHTML = renderHeroSelectHTML();
      return;
    }

    // Fast-path: If user is actively in the Action Arena and canvas already exists,
    // DO NOT destroy the canvas DOM node! Update header and modals smoothly.
    const existingCanvas = document.getElementById("rpg-action-canvas");
    const viewContainer = document.getElementById("rpg-view-container");

    const isBossFightState = !!(ARENA.isRaidBossBattle || (ARENA.isBossActive && ARENA.topDownMode));
    const bossFightStateChanged = RPG_STATE._lastRenderedBossFight !== isBossFightState;
    RPG_STATE._lastRenderedBossFight = isBossFightState;

    if (!RPG_STATE._forceFullRender && !bossFightStateChanged && existingCanvas && viewContainer && RPG_STATE.activeTab === "farm" && RPG_STATE.farmMode === "arena") {
      const topNav = document.getElementById("rpg-top-nav");
      if (topNav) {
        topNav.outerHTML = renderTopNavBarHTML();
      }
      const toastEl = document.getElementById("rpg-toast-container");
      if (toastEl) {
        toastEl.innerHTML = RPG_STATE.levelUpNotification
          ? `<div class="p-3 rounded-2xl bg-gradient-to-r from-amber-500 to-yellow-400 text-slate-950 font-black text-center text-xs shadow-lg animate-bounce">
              🎉 НОВЫЙ УРОВЕНЬ ${RPG_STATE.levelUpNotification}! Получено +1 очко характеристик!
            </div>`
          : "";
      }
      const modalsEl = document.getElementById("rpg-modals-container");
      if (modalsEl) {
        const existingAdmin = document.getElementById("rpg-admin-modal-backdrop");
        const shouldShowAdmin = isUserAdmin() && RPG_STATE.adminModalOpen;
        if (!shouldShowAdmin && existingAdmin) {
          existingAdmin.remove();
        }
        modalsEl.innerHTML = `
          ${RPG_STATE.inspectedItem ? renderItemModalHTML(RPG_STATE.inspectedItem) : ""}
          ${RPG_STATE.forgeItem ? renderForgeModalHTML(RPG_STATE.forgeItem) : ""}
          ${RPG_STATE.activeChestModal ? renderChestModalHTML(RPG_STATE.activeChestModal) : ""}
          ${RPG_STATE.shopModalOpen ? renderShopModalHTML() : ""}
          ${RPG_STATE.slotFilterModal ? renderSlotFilterModalHTML(RPG_STATE.slotFilterModal) : ""}
          ${(shouldShowAdmin && !existingAdmin) ? renderAdminModalHTML() : ""}
        `;
        if (shouldShowAdmin && existingAdmin && !modalsEl.contains(existingAdmin)) {
          modalsEl.appendChild(existingAdmin);
        }
      }
      if (ARENA.canvas !== existingCanvas || !ARENA.ctx) {
        bindArenaCanvas(existingCanvas);
      }
      if (!ARENA.running) {
        startArenaLoop();
      }
      return;
    }

    // Full render when switching tabs or initial load
    container.innerHTML = `
      <div class="space-y-3.5 pb-8">
        <!-- Level Up Toast Notification Container -->
        <div id="rpg-toast-container">
          ${
            RPG_STATE.levelUpNotification
              ? `
            <div class="p-3 rounded-2xl bg-gradient-to-r from-amber-500 to-yellow-400 text-slate-950 font-black text-center text-xs shadow-lg animate-bounce">
              🎉 НОВЫЙ УРОВЕНЬ ${RPG_STATE.levelUpNotification}! Получено +1 очко характеристик!
            </div>
          `
              : ""
          }
        </div>

        <!-- Top Navigation -->
        ${renderTopNavBarHTML()}

        <!-- Active Subtab View -->
        <div id="rpg-view-container">
          ${renderCurrentViewHTML()}
        </div>
      </div>

      <!-- Modals Container -->
      <div id="rpg-modals-container">
        <!-- Item Inspection Modal -->
        ${RPG_STATE.inspectedItem ? renderItemModalHTML(RPG_STATE.inspectedItem) : ""}

        <!-- Forge Modal -->
        ${RPG_STATE.forgeItem ? renderForgeModalHTML(RPG_STATE.forgeItem) : ""}

        <!-- Chest Opening Modal -->
        ${RPG_STATE.activeChestModal ? renderChestModalHTML(RPG_STATE.activeChestModal) : ""}

        <!-- Shop Modal -->
        ${RPG_STATE.shopModalOpen ? renderShopModalHTML() : ""}

        <!-- Slot Quick Equip Modal -->
        ${RPG_STATE.slotFilterModal ? renderSlotFilterModalHTML(RPG_STATE.slotFilterModal) : ""}

        <!-- Admin Dev Modal -->
        ${(isUserAdmin() && RPG_STATE.adminModalOpen) ? renderAdminModalHTML() : ""}
      </div>

      <!-- Admin Floating Pill Badge (Bottom-left) -->
      ${isUserAdmin() ? renderAdminFloatingBadgeHTML() : ""}
    `;

    if (RPG_STATE.activeTab === "farm" && RPG_STATE.farmMode === "arena") {
      const c = document.getElementById("rpg-action-canvas");
      if (c) {
        bindArenaCanvas(c);
        requestAnimationFrame(() => {
          const freshC = document.getElementById("rpg-action-canvas");
          if (freshC) bindArenaCanvas(freshC);
        });
        if (!ARENA.running) {
          startArenaLoop();
        }
      }
    }
  }

  function renderTopNavBarHTML() {
    const p = RPG_STATE.profile || {};
    const tabs = [
      { id: "farm", name: "Фарм", icon: "⚔️" },
      { id: "hero", name: "Герой", icon: p.class_icon || "🛡️" },
      { id: "talents", name: "Таланты", icon: "🧬" },
      { id: "coop", name: "Боссы", icon: "🐉" }
    ];

    const xp = p.xp !== undefined ? p.xp : (p.experience || 0);
    const xpNeeded = p.xp_needed !== undefined ? p.xp_needed : (p.experience_to_next || 100);
    const xpPct = Math.min(100, Math.max(0, Math.round((xp / xpNeeded) * 100)));

    return `
      <div id="rpg-top-nav" class="space-y-2">
        <!-- Character Summary Card -->
        <div class="p-3.5 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-800 to-amber-950 text-white shadow-md border border-amber-500/30 space-y-2">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2.5">
              <div class="w-10 h-10 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-2xl shadow-inner">
                ${p.class_avatar || p.class_icon || "🛡️"}
              </div>
              <div>
                <div class="flex items-center gap-1.5">
                  <span class="text-xs font-black tracking-wide">${p.class_name || "Герой"}</span>
                  <span class="text-[10px] px-1.5 py-0.2 rounded-md bg-amber-500 text-slate-950 font-black">Ур. ${p.level || 1}</span>
                </div>
                <div class="flex items-center gap-2 text-[11px] text-amber-200/90 font-medium">
                  <span>🪙 <b>${(p.gold || 0).toLocaleString()}</b></span>
                  <span>💎 <b>${p.gems || 0}</b></span>
                  <span>🔥 <b>${p.dungeon_floor || 1}</b> эт.</span>
                  ${(p.stat_points || 0) > 0 ? `<span class="px-1.5 rounded bg-emerald-500 text-white font-extrabold text-[9px] animate-pulse">+${p.stat_points} очк</span>` : ""}
                </div>
              </div>
            </div>

            <div class="text-right flex items-center gap-1.5">
              <button onclick="window.RPG.openShopModal()" class="px-2.5 py-1.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 active:scale-95 text-white font-black text-[11px] shadow-sm flex items-center gap-1">
                <span>🏪</span>
                <span>Лавка</span>
              </button>
              <button onclick="window.RPG.openForge()" class="px-2.5 py-1.5 rounded-xl bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 active:scale-95 text-slate-950 font-black text-[11px] shadow-sm flex items-center gap-1">
                <span>⚒️</span>
                <span>Кузница</span>
              </button>
            </div>
          </div>

          <!-- Mini XP Bar in Header -->
          <div class="w-full h-1.5 rounded-full bg-slate-700/80 overflow-hidden">
            <div class="h-full bg-gradient-to-r from-amber-400 to-yellow-300 transition-all duration-300" style="width: ${xpPct}%"></div>
          </div>
        </div>

        <!-- Navigation Subtabs -->
        <div class="grid grid-cols-4 gap-1 p-1 rounded-2xl bg-slate-200/80 dark:bg-slate-800/90 text-[11px] font-bold">
          ${tabs
            .map(
              (t) => `
            <button onclick="window.RPG.setSubTab('${t.id}')" class="py-2 rounded-xl transition-all flex flex-col items-center justify-center gap-0.5 ${
                RPG_STATE.activeTab === t.id
                  ? "bg-white dark:bg-slate-700 text-amber-600 dark:text-amber-400 shadow-sm"
                  : "text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200"
              }">
              <span class="text-sm">${t.icon}</span>
              <span class="text-[10px] leading-tight">${t.name}</span>
            </button>
          `
            )
            .join("")}
        </div>
      </div>
    `;
  }

  function renderCurrentViewHTML() {
    switch (RPG_STATE.activeTab) {
      case "farm":
        return renderFarmTabHTML();
      case "hero":
        return renderHeroProfileHTML();
      case "talents":
        if (window._talentsTabAutoLoad) setTimeout(_talentsTabAutoLoad, 0);
        return renderTalentsTab();
      case "coop":
        return renderCoopRaidsHTML();
      case "pvp":
        return renderPvPDuelsHTML();
      case "leaderboard":
        return renderLeaderboardHTML();
      default:
        return renderFarmTabHTML();
    }
  }

  // ===========================================================================
  // 1. HERO PROFILE & 3-ATTRIBUTE SYSTEM HTML
  // ===========================================================================

  function renderHeroProfileHTML() {
    const p = RPG_STATE.profile || {};
    const stats = p.stats || {};
    const eq = p.equipment || {};
    const inv = p.inventory || [];
    const points = p.stat_points || 0;

    const baseStr = (p.base_attributes && p.base_attributes.strength) || p.strength || 10;
    const gearStr = (p.gear_attributes && p.gear_attributes.strength) || stats.gear_str || 0;
    const totalStr = (p.total_attributes && p.total_attributes.strength) || (baseStr + gearStr);

    const baseAgi = (p.base_attributes && p.base_attributes.agility) || p.agility || 10;
    const gearAgi = (p.gear_attributes && p.gear_attributes.agility) || stats.gear_agi || 0;
    const totalAgi = (p.total_attributes && p.total_attributes.agility) || (baseAgi + gearAgi);

    const baseInt = (p.base_attributes && p.base_attributes.intelligence) || p.intelligence || 10;
    const gearInt = (p.gear_attributes && p.gear_attributes.intelligence) || stats.gear_int || 0;
    const totalInt = (p.total_attributes && p.total_attributes.intelligence) || (baseInt + gearInt);

    const xp = p.xp !== undefined ? p.xp : (p.experience || 0);
    const xpNeeded = p.xp_needed !== undefined ? p.xp_needed : (p.experience_to_next || 100);
    const xpPct = Math.min(100, Math.max(0, Math.round((xp / xpNeeded) * 100)));
    const primaryAttr = p.primary_attr || stats.primary_attr || "Сила";
    const userGold = p.gold || 0;

    function calcCost(currentVal, count) {
      let total = 0;
      let pts = points;
      let val = currentVal;
      for (let i = 0; i < count; i++) {
        if (pts > 0) {
          pts--;
        } else {
          total += Math.floor(Math.pow(val, 1.35) * 6);
        }
        val++;
      }
      return total;
    }

    function calcMax(currentVal) {
      let count = 0;
      let pts = points;
      let remGold = userGold;
      let val = currentVal;
      while (pts > 0) {
        pts--;
        count++;
        val++;
      }
      while (true) {
        const cost = Math.floor(Math.pow(val, 1.35) * 6);
        if (remGold < cost) break;
        remGold -= cost;
        count++;
        val++;
        if (count >= 10000) break;
      }
      return count;
    }

    function formatShort(num) {
      if (!num || num <= 0) return "0";
      if (num >= 1e9) return (num / 1e9).toFixed(1) + "B";
      if (num >= 1e6) return (num / 1e6).toFixed(1) + "M";
      if (num >= 1e3) return Math.round(num / 1e3) + "k";
      return num.toLocaleString();
    }

    function renderStatUpgradeButtons(statKey, baseVal, themeGradient) {
      const cost1 = calcCost(baseVal, 1);
      const cost10 = calcCost(baseVal, 10);
      const cost100 = calcCost(baseVal, 100);
      const maxCount = calcMax(baseVal);

      const can1 = !isUpgradingStat && (cost1 <= userGold || points > 0);
      const can10 = !isUpgradingStat && (cost10 <= userGold || points >= 10);
      const can100 = !isUpgradingStat && (cost100 <= userGold || points >= 100);
      const canMax = !isUpgradingStat && (maxCount > 0);

      const disabledCls = "bg-slate-100 dark:bg-slate-800/80 text-slate-400 dark:text-slate-500 opacity-50 cursor-not-allowed";
      const btnBase = "py-2 px-1 rounded-xl flex flex-col items-center justify-center transition-all select-none";

      const getSubLabel = (count, cost) => {
        if (points >= count) return `✨ ${count}`;
        return `${formatShort(cost)} 🪙`;
      };

      return `
        <div class="grid grid-cols-4 gap-1.5 pt-2 border-t border-slate-200/50 dark:border-slate-700/50">
          <button ${!can1 ? "disabled" : ""} onclick="window.RPG.upgradeStat('${statKey}', 1)" title="+1 уровень" class="${btnBase} ${can1 ? (points > 0 ? "bg-gradient-to-r from-emerald-600 to-green-500 text-white shadow-sm ring-1 ring-emerald-400/40 active:scale-95" : themeGradient + " active:scale-95") : disabledCls}">
            <span class="text-xs font-black leading-tight">+1</span>
            <span class="text-[9px] font-bold opacity-90 truncate max-w-full">${points > 0 ? "✨ 1" : `${formatShort(cost1)} 🪙`}</span>
          </button>

          <button ${!can10 ? "disabled" : ""} onclick="window.RPG.upgradeStat('${statKey}', 10)" title="+10 уровней" class="${btnBase} ${can10 ? themeGradient + " active:scale-95" : disabledCls}">
            <span class="text-xs font-black leading-tight">+10</span>
            <span class="text-[9px] font-bold opacity-90 truncate max-w-full">${getSubLabel(10, cost10)}</span>
          </button>

          <button ${!can100 ? "disabled" : ""} onclick="window.RPG.upgradeStat('${statKey}', 100)" title="+100 уровней" class="${btnBase} ${can100 ? themeGradient + " active:scale-95" : disabledCls}">
            <span class="text-xs font-black leading-tight">+100</span>
            <span class="text-[9px] font-bold opacity-90 truncate max-w-full">${getSubLabel(100, cost100)}</span>
          </button>

          <button ${!canMax ? "disabled" : ""} onclick="window.RPG.upgradeStat('${statKey}', 'max')" title="+Максимум на сколько хватает монет" class="${btnBase} ${canMax ? "bg-gradient-to-r from-amber-500 to-yellow-500 text-slate-950 font-black shadow-sm ring-1 ring-amber-400/50 active:scale-95" : disabledCls}">
            <span class="text-xs font-black leading-tight">+МАКС</span>
            <span class="text-[9px] font-bold opacity-90 truncate max-w-full">${maxCount > 0 ? `+${maxCount}` : "0"}</span>
          </button>
        </div>
      `;
    }

    return `
      <div class="space-y-4">
        <!-- Level & EXP progress -->
        <div class="theme-card p-3.5 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm space-y-2">
          <div class="flex items-center justify-between text-xs font-bold">
            <span class="text-slate-500 dark:text-slate-400">Прогресс уровня</span>
            <span class="text-amber-600 dark:text-amber-400 font-extrabold">${xp} / ${xpNeeded} XP (${xpPct}%)</span>
          </div>
          <div class="w-full h-2.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
            <div class="h-full bg-gradient-to-r from-amber-500 to-yellow-400 transition-all duration-300" style="width: ${xpPct}%"></div>
          </div>
          <div class="flex items-center justify-between text-xs font-bold mt-2 pt-2 border-t border-slate-200/50 dark:border-slate-700/50">
            <span class="text-slate-500 dark:text-slate-400">Уровень героя:</span>
            <span class="text-amber-600 dark:text-amber-400 font-black text-sm">${p.level || 1} ур.</span>
          </div>
          <div class="flex items-center justify-between text-[11px] pt-1.5 border-t border-purple-500/20">
            <span class="text-slate-400">Доступно очков характеристик:</span>
            <span class="text-amber-400 font-black">${points} очк.</span>
          </div>
          <div class="flex items-center justify-between text-[11px] pt-1.5 border-t border-purple-500/20">
            <span class="text-slate-400">Доступно очков талантов:</span>
            <span class="text-emerald-400 font-black">${p.talent_points || 0} очк.</span>
          </div>
        </div>

        <!-- REBIRTH & TALENTS SUMMARY CARD -->
        <div class="theme-card p-3.5 rounded-2xl bg-gradient-to-r from-purple-950/40 via-slate-900 to-indigo-950/40 border border-purple-500/30 shadow-sm space-y-2.5">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="text-xl">🧬</span>
              <div>
                <div class="text-xs font-black text-purple-300">Перерождение и Таланты</div>
                <div class="text-[10px] text-slate-400">Ранг: <b class="text-white">${p.rebirths || 0}</b> (+${(p.rebirths || 0) * 10}% ко всем статам)</div>
              </div>
            </div>
            <button onclick="window.RPG.setSubTab('talents')" class="px-3 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-500 active:scale-95 text-white font-black text-[11px] shadow-sm flex items-center gap-1">
              <span>Открыть</span>
              <span>⚡</span>
            </button>
          </div>
          <div class="flex items-center justify-between text-[11px] pt-1.5 border-t border-purple-500/20">
            <span class="text-slate-400">Доступно очков талантов:</span>
            <span class="text-emerald-400 font-black">${p.talent_points || 0} очк.</span>
          </div>
        </div>

        <!-- 3 ATTRIBUTES SYSTEM (СИЛА, ЛОВКОСТЬ, ИНТЕЛЛЕКТ) -->
        <div class="theme-card p-3.5 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm space-y-3">
          <div class="flex items-center justify-between">
            <h3 class="text-xs font-black uppercase tracking-wider text-slate-700 dark:text-slate-200 flex items-center gap-1.5">
              <span>📊</span> Характеристики
            </h3>
            ${
              points > 0
                ? `<span class="px-2 py-0.5 rounded-lg bg-emerald-500 text-white font-extrabold text-[10px] animate-pulse">✨ Свободных очков: ${points}</span>`
                : `<span class="text-[10px] text-slate-400 font-medium">Прокачка за золото</span>`
            }
          </div>

          <div class="flex items-center justify-between p-2.5 rounded-xl bg-slate-100 dark:bg-slate-900/60 text-xs font-bold border border-slate-200/60 dark:border-slate-700/60">
            <span class="text-slate-500 dark:text-slate-400">Ваше золото для прокачки:</span>
            <span class="text-amber-500 font-black">🪙 ${(p.gold || 0).toLocaleString()}</span>
          </div>

          <div class="space-y-2">
            <!-- 1. STRENGTH (СИЛА) -->
            <div class="p-3 rounded-2xl bg-slate-50 dark:bg-slate-900/50 border ${primaryAttr === "Сила" ? "border-red-500/50 shadow-sm bg-red-50/20" : "border-slate-200/60 dark:border-slate-700/60"} flex flex-col gap-2">
              <div class="flex items-center justify-between">
                <div class="space-y-0.5">
                  <div class="flex items-center gap-1.5 flex-wrap">
                    <span class="text-xs font-black text-red-500">🥩 Сила: ${baseStr}${gearStr > 0 ? ` <span class="text-amber-500 font-extrabold">(+${gearStr})</span>` : ""}${gearStr > 0 ? ` <span class="text-slate-800 dark:text-slate-100 font-black">= ${totalStr}</span>` : ""}</span>
                    ${primaryAttr === "Сила" ? `<span class="px-1.5 py-0.2 rounded bg-red-500/10 text-red-600 border border-red-500/30 text-[9px] font-black">ОСНОВНОЙ (+1 Урон)</span>` : ""}
                  </div>
                  <span class="block text-[10px] text-slate-400">+22 HP за очко | +0.35 HP/сек регенерация</span>
                </div>
              </div>
              ${renderStatUpgradeButtons('str', baseStr, 'bg-gradient-to-r from-red-600 to-rose-600 text-white hover:from-red-500 hover:to-rose-500 shadow-sm shadow-red-500/20')}
            </div>

            <!-- 2. AGILITY (ЛОВКОСТЬ) -->
            <div class="p-3 rounded-2xl bg-slate-50 dark:bg-slate-900/50 border ${primaryAttr === "Ловкость" ? "border-emerald-500/50 shadow-sm bg-emerald-50/20" : "border-slate-200/60 dark:border-slate-700/60"} flex flex-col gap-2">
              <div class="flex items-center justify-between">
                <div class="space-y-0.5">
                  <div class="flex items-center gap-1.5 flex-wrap">
                    <span class="text-xs font-black text-emerald-500">🗡️ Ловкость: ${baseAgi}${gearAgi > 0 ? ` <span class="text-amber-500 font-extrabold">(+${gearAgi})</span>` : ""}${gearAgi > 0 ? ` <span class="text-slate-800 dark:text-slate-100 font-black">= ${totalAgi}</span>` : ""}</span>
                    ${primaryAttr === "Ловкость" ? `<span class="px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-600 border border-emerald-500/30 text-[9px] font-black">ОСНОВНОЙ (+1 Урон)</span>` : ""}
                  </div>
                  <span class="block text-[10px] text-slate-400">+2.5% Скор. атаки | +0.4 Брони | Крит & Уворот</span>
                </div>
              </div>
              ${renderStatUpgradeButtons('agi', baseAgi, 'bg-gradient-to-r from-emerald-600 to-teal-600 text-white hover:from-emerald-500 hover:to-teal-500 shadow-sm shadow-emerald-500/20')}
            </div>

            <!-- 3. INTELLIGENCE (ИНТЕЛЛЕКТ) -->
            <div class="p-3 rounded-2xl bg-slate-50 dark:bg-slate-900/50 border ${primaryAttr === "Интеллект" ? "border-sky-500/50 shadow-sm bg-sky-50/20" : "border-slate-200/60 dark:border-slate-700/60"} flex flex-col gap-2">
              <div class="flex items-center justify-between">
                <div class="space-y-0.5">
                  <div class="flex items-center gap-1.5 flex-wrap">
                    <span class="text-xs font-black text-sky-500">🧙 Интеллект: ${baseInt}${gearInt > 0 ? ` <span class="text-amber-500 font-extrabold">(+${gearInt})</span>` : ""}${gearInt > 0 ? ` <span class="text-slate-800 dark:text-slate-100 font-black">= ${totalInt}</span>` : ""}</span>
                    ${primaryAttr === "Интеллект" ? `<span class="px-1.5 py-0.2 rounded bg-sky-500/10 text-sky-600 border border-sky-500/30 text-[9px] font-black">ОСНОВНОЙ (+1 Урон)</span>` : ""}
                  </div>
                  <span class="block text-[10px] text-slate-400">+14 Маны за очко | +0.25 MP/сек | +0.4% Сопр. магии</span>
                </div>
              </div>
              ${renderStatUpgradeButtons('int', baseInt, 'bg-gradient-to-r from-sky-600 to-blue-600 text-white hover:from-sky-500 hover:to-blue-500 shadow-sm shadow-sky-500/20')}
            </div>
          </div>

          <!-- Combat Summary Badges -->
          <div class="pt-2 border-t border-slate-100 dark:border-slate-700/80 grid grid-cols-3 gap-1.5 text-center">
            <div class="p-1.5 rounded-lg bg-slate-100 dark:bg-slate-700/40">
              <span class="block text-[9px] font-bold text-slate-400 uppercase">HP</span>
              <span class="text-xs font-black text-emerald-600 dark:text-emerald-400">${stats.hp_max || 180} <span class="text-[9px] text-slate-400">(+${stats.hp_regen || 0}/с)</span></span>
            </div>
            <div class="p-1.5 rounded-lg bg-slate-100 dark:bg-slate-700/40">
              <span class="block text-[9px] font-bold text-slate-400 uppercase">Мана</span>
              <span class="text-xs font-black text-sky-600 dark:text-sky-400">${stats.mp_max || 60} <span class="text-[9px] text-slate-400">(+${stats.mp_regen || 0}/с)</span></span>
            </div>
            <div class="p-1.5 rounded-lg bg-slate-100 dark:bg-slate-700/40">
              <span class="block text-[9px] font-bold text-slate-400 uppercase">Урон</span>
              <span class="text-xs font-black text-red-600 dark:text-red-400">${stats.min_atk || 16}-${stats.max_atk || 24}</span>
            </div>
            <div class="p-1.5 rounded-lg bg-slate-100 dark:bg-slate-700/40">
              <span class="block text-[9px] font-bold text-slate-400 uppercase">Броня</span>
              <span class="text-xs font-black text-sky-600 dark:text-sky-400">${stats.defense || 5}</span>
            </div>
            <div class="p-1.5 rounded-lg bg-slate-100 dark:bg-slate-700/40">
              <span class="block text-[9px] font-bold text-slate-400 uppercase">Скор. атаки</span>
              <span class="text-xs font-black text-amber-600 dark:text-amber-400">${stats.attack_speed || 1.0} уд/с</span>
            </div>
            <div class="p-1.5 rounded-lg bg-slate-100 dark:bg-slate-700/40">
              <span class="block text-[9px] font-bold text-slate-400 uppercase">Сопр. магии</span>
              <span class="text-xs font-black text-purple-600 dark:text-purple-400">${stats.magic_resist || 0}%</span>
            </div>
            <div class="p-1.5 rounded-lg bg-slate-100 dark:bg-slate-700/40">
              <span class="block text-[9px] font-bold text-slate-400 uppercase">Сила Магии ✨</span>
              <span class="text-xs font-black text-amber-500">+${stats.spell_amp || Math.round((stats.mp_max || 60) * 0.2)}%</span>
            </div>
            <div class="p-1.5 rounded-lg bg-slate-100 dark:bg-slate-700/40">
              <span class="block text-[9px] font-bold text-slate-400 uppercase">Крит</span>
              <span class="text-xs font-black text-amber-600 dark:text-amber-400">${stats.crit_chance || 5}%</span>
            </div>
            <div class="p-1.5 rounded-lg bg-slate-100 dark:bg-slate-700/40">
              <span class="block text-[9px] font-bold text-slate-400 uppercase">Уворот</span>
              <span class="text-xs font-black text-violet-600 dark:text-violet-400">${stats.dodge_chance || 5}%</span>
            </div>
            <div class="p-1.5 rounded-lg bg-slate-100 dark:bg-slate-700/40">
              <span class="block text-[9px] font-bold text-slate-400 uppercase">Вампиризм</span>
              <span class="text-xs font-black text-rose-600 dark:text-rose-400">${stats.lifesteal || 0}%</span>
            </div>
            ${stats.ult_boost > 0 ? `
            <div class="p-1.5 rounded-lg bg-purple-500/10 border border-purple-500/30">
              <span class="block text-[9px] font-bold text-purple-400 uppercase">Урон Ульты 💥</span>
              <span class="text-xs font-black text-purple-500">+${stats.ult_boost}%</span>
            </div>
            ` : ""}
            ${stats.ult_cd_reduct > 0 ? `
            <div class="p-1.5 rounded-lg bg-sky-500/10 border border-sky-500/30">
              <span class="block text-[9px] font-bold text-sky-400 uppercase">КД Ульты ⏱️</span>
              <span class="text-xs font-black text-sky-400">-${stats.ult_cd_reduct}%</span>
            </div>
            ` : ""}
          </div>
        </div>

        <!-- Equipped Gear Slots (3 slots) -->
        <div class="theme-card p-3.5 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm space-y-2.5">
          <h3 class="text-xs font-black uppercase tracking-wider text-slate-700 dark:text-slate-200 flex items-center gap-1.5">
            <span>🛡️</span> Экипировка
          </h3>

          <div class="grid grid-cols-3 gap-2">
            ${[1,2,3,4,5,6].map(i => renderEquippedSlotHTML('slot_'+i, 'Слот '+i, '🎒', eq['slot_'+i] || (i===1 ? eq.weapon : i===2 ? eq.armor : i===3 ? eq.relic : null))).join('')}
          </div>
        </div>

        <!-- Inventory Card -->
        <div class="theme-card p-3.5 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm space-y-3">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="text-base">🎒</span>
              <h3 class="text-xs font-black uppercase tracking-wider text-slate-700 dark:text-slate-200">
                Инвентарь
              </h3>
              <span class="text-[10px] font-bold text-slate-400">(${inv.length} / 60)</span>
            </div>

            <!-- Toggle Selection Mode Button -->
            ${inv.length > 0 ? `
              <button onclick="window.RPG.toggleItemSelectionMode()" class="px-2.5 py-1 rounded-xl text-xs font-black transition-all flex items-center gap-1.5 ${
                RPG_STATE.isSelectionMode
                  ? 'bg-rose-500 text-white shadow-md'
                  : 'bg-amber-500/15 text-amber-500 border border-amber-500/40 hover:bg-amber-500/25'
              }">
                <span>${RPG_STATE.isSelectionMode ? "✕ Отмена" : "☑️ Выбрать для продажи"}</span>
              </button>
            ` : ""}
          </div>

          <!-- Quick Bulk Select Filters -->
          ${inv.length > 0 ? `
            <div class="p-2 rounded-xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200/60 dark:border-slate-700/60 flex items-center justify-between gap-1 flex-wrap text-[10.5px]">
              <span class="text-slate-400 font-bold">Выбрать:</span>
              <div class="flex items-center gap-1 flex-wrap font-extrabold">
                <button onclick="window.RPG.selectAllByRarity('common')" class="px-2 py-0.5 rounded-lg bg-slate-200 dark:bg-slate-700 hover:bg-slate-300 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-200">
                  ⬜ Серые
                </button>
                <button onclick="window.RPG.selectAllByRarity('uncommon')" class="px-2 py-0.5 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-500 border border-emerald-500/30">
                  🟩 Зеленые
                </button>
                <button onclick="window.RPG.selectAllByRarity('rare')" class="px-2 py-0.5 rounded-lg bg-sky-500/15 hover:bg-sky-500/25 text-sky-500 border border-sky-500/30">
                  🟦 Синие
                </button>
                <button onclick="window.RPG.selectAllByRarity()" class="px-2 py-0.5 rounded-lg bg-amber-500/15 hover:bg-amber-500/25 text-amber-500 border border-amber-500/30">
                  ✨ Выбрать всё
                </button>
                ${(RPG_STATE.selectedItemUids && RPG_STATE.selectedItemUids.size > 0) ? `
                  <button onclick="window.RPG.clearItemSelection()" class="px-2 py-0.5 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 text-rose-500 border border-rose-500/30">
                    Сброс (${RPG_STATE.selectedItemUids.size})
                  </button>
                ` : ""}
              </div>
            </div>
          ` : ""}

          ${
            inv.length === 0
              ? `
            <div class="py-6 text-center text-slate-400 text-xs">
              Инвентарь пуст. Зачищайте этажи, чтобы получать наградные сундуки!
            </div>
          `
              : `
            <div class="grid grid-cols-3 sm:grid-cols-4 gap-2">
              ${inv.map((item) => renderInventoryItemTileHTML(item)).join("")}
            </div>
          `
          }

          <!-- Floating Bulk Sell Action Bar -->
          ${(RPG_STATE.selectedItemUids && RPG_STATE.selectedItemUids.size > 0) ? `
            <div class="sticky bottom-16 z-30 p-3.5 rounded-2xl bg-gradient-to-r from-amber-500/25 via-yellow-500/20 to-amber-500/25 border-2 border-amber-500 flex items-center justify-between gap-3 shadow-xl backdrop-blur-md animate-scale-up">
              <div>
                <div class="flex items-center gap-1.5">
                  <span class="text-xs font-black text-amber-500 dark:text-amber-400">
                    Выбрано: ${RPG_STATE.selectedItemUids.size} шт.
                  </span>
                </div>
                <span class="text-[11px] font-black text-emerald-600 dark:text-emerald-400 block">
                  Вы получите: +${getSelectedItemsTotalPrice()} 🪙
                </span>
              </div>
              <div class="flex items-center gap-1.5">
                <button onclick="window.RPG.clearItemSelection()" class="px-2.5 py-2 rounded-xl bg-slate-800 text-slate-300 font-bold text-xs hover:bg-slate-700">
                  ✕
                </button>
                <button onclick="window.RPG.sellSelectedItems()" class="px-4 py-2 rounded-xl bg-gradient-to-r from-amber-500 to-yellow-400 hover:from-amber-400 active:scale-95 text-slate-950 font-black text-xs shadow-md flex items-center gap-1">
                  <span>💰</span>
                  <span>Продать за +${getSelectedItemsTotalPrice()} 🪙</span>
                </button>
              </div>
            </div>
          ` : ""}
        </div>

        <!-- Shop Banner in Hero Tab -->
        <div class="p-3 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-800 to-emerald-950 border border-emerald-500/30 text-white flex items-center justify-between shadow-sm">
          <div class="flex items-center gap-2.5">
            <span class="text-2xl">🏪</span>
            <div>
              <span class="text-xs font-black block text-emerald-400">Лавка Снаряжения</span>
              <span class="text-[10px] text-slate-300">Покупка оружия, брони, реликвий и зелий</span>
            </div>
          </div>
          <button onclick="window.RPG.openShopModal()" class="px-3 py-1.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 active:scale-95 text-slate-950 font-black text-xs shadow-md">
            В лавку →
          </button>
        </div>

        <!-- Switch Hero & Hardcore Reset Buttons -->
        <div class="text-center pt-2 space-y-2">
          <button onclick="window.RPG.openHeroPicker()" class="text-xs font-bold text-slate-400 hover:text-amber-500 transition-colors block mx-auto">
            Сменить героя natarGRP 🔄
          </button>
          <button onclick="window.RPG.resetCharacter()" class="text-[11px] font-bold text-rose-500/80 hover:text-rose-400 transition-colors block mx-auto underline">
            Сбросить персонажа (Хардкорный старт с 1 ур.) ⚠️
          </button>
        </div>
      </div>
    `;
  }

  function renderEquippedSlotHTML(slotKey, label, defaultIcon, item) {
    if (!item) {
      return `
        <div onclick="window.RPG.openSlotFilterModal('${slotKey}')" class="cursor-pointer p-2.5 rounded-2xl border-2 border-dashed border-slate-300 dark:border-slate-700 hover:border-amber-500 text-center space-y-1 transition-all active:scale-95">
          <span class="text-2xl opacity-40">${defaultIcon}</span>
          <span class="block text-[10px] font-bold text-slate-400">${label}</span>
          <span class="block text-[9px] text-amber-500 font-bold">+ Надеть</span>
        </div>
      `;
    }

    const rInfo = RARITY_MAP[item.rarity] || RARITY_MAP.common;
    const forgeTag = item.forge_level > 0 ? `+${item.forge_level}` : "";

    return `
      <div onclick="window.RPG.openItemModal('${item.uid}')" class="cursor-pointer p-2.5 rounded-2xl border-2 ${rInfo.color} text-center space-y-1 hover:scale-105 transition-transform relative group">
        <div class="relative inline-block">
          <span class="text-2xl">${item.icon || defaultIcon}</span>
          ${
            forgeTag
              ? `<span class="absolute -top-1 -right-2 px-1 rounded-md bg-amber-500 text-slate-950 font-black text-[9px] shadow-sm">${forgeTag}</span>`
              : ""
          }
        </div>
        <span class="block text-[10.5px] font-black truncate">${item.name}</span>
        <div class="flex items-center justify-center gap-1 flex-wrap">
          <span class="text-[9px] font-extrabold px-1.5 py-0.2 rounded-md ${rInfo.badge}">${rInfo.name}</span>
          ${(() => {
            const activeDef = Object.values(ACTIVE_ITEM_DEFINITIONS).find(d => d.match(item));
            return activeDef ? `<span class="text-[8px] font-black px-1 py-0.2 rounded bg-amber-500/20 text-amber-400 border border-amber-500/40 animate-pulse">⚡ [${activeDef.shortName}]</span>` : "";
          })()}
        </div>
        <button onclick="event.stopPropagation(); window.RPG.openSlotFilterModal('${slotKey}')" class="w-full mt-1 py-0.5 rounded-lg bg-slate-800/80 hover:bg-amber-500 text-slate-300 hover:text-slate-950 text-[9px] font-bold border border-slate-700 hover:border-amber-400 flex items-center justify-center gap-1 transition-colors">
          <span>🔄</span>
          <span>Сменить</span>
        </button>
      </div>
    `;
  }

  function renderInventoryItemTileHTML(item) {
    const rInfo = RARITY_MAP[item.rarity] || RARITY_MAP.common;
    const isSelected = RPG_STATE.selectedItemUids && RPG_STATE.selectedItemUids.has(item.uid);
    const forgeTag = (item.forge_level || item.upgrade) > 0 ? `+${item.forge_level || item.upgrade}` : "";
    const slotBadge = item.slot_name || (item.slot === "weapon" ? "Оружие" : item.slot === "armor" ? "Броня" : item.slot === "relic" ? "Реликвия" : "Зелье");
    const isPotion = item.slot === "consumable" || item.type === "potion";
    const p = RPG_STATE.profile || {};
    const eq = p.equipment || {};
    const targetSlot = (item.slot || item.type || "").toLowerCase();
    const isEquippable = ["weapon", "armor", "relic"].includes(targetSlot) || targetSlot.startsWith("slot_");
    const currEquipped = isEquippable ? (eq[targetSlot] || eq[item.slot] || eq[item.type]) : null;
    const sellPrice = getItemSellPrice(item);

    let actionBtnHTML = "";
    if (!RPG_STATE.isSelectionMode) {
      if (isPotion) {
        actionBtnHTML = `
          <button onclick="event.stopPropagation(); window.RPG.useConsumable('${item.uid}')" class="w-full mt-1.5 py-1 rounded-xl bg-emerald-600 hover:bg-emerald-500 active:scale-95 text-white font-black text-[9.5px] shadow-sm flex items-center justify-center gap-1 transition-all">
            <span>🧪</span>
            <span>Пить ${item.count > 1 ? `(${item.count})` : ""}</span>
          </button>
        `;
      } else if (isEquippable) {
        if (currEquipped) {
          actionBtnHTML = `
            <button onclick="event.stopPropagation(); window.RPG.equipItem('${item.uid}')" class="w-full mt-1.5 py-1 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 active:scale-95 text-white font-black text-[9.5px] shadow-sm flex items-center justify-center gap-1 transition-all">
              <span>🔄</span>
              <span>Сменить</span>
            </button>
          `;
        } else {
          actionBtnHTML = `
            <button onclick="event.stopPropagation(); window.RPG.equipItem('${item.uid}')" class="w-full mt-1.5 py-1 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 active:scale-95 text-white font-black text-[9.5px] shadow-sm flex items-center justify-center gap-1 transition-all">
              <span>⚔️</span>
              <span>Надеть</span>
            </button>
          `;
        }
      }
    } else {
      actionBtnHTML = `
        <div class="w-full mt-1 py-1 text-center font-black text-[10px] rounded-lg ${isSelected ? 'bg-amber-500 text-slate-950' : 'bg-slate-100 dark:bg-slate-700 text-slate-400'}">
          ${isSelected ? `✓ ВЫБРАНО (+${sellPrice} 🪙)` : `+${sellPrice} 🪙`}
        </div>
      `;
    }

    return `
      <div onclick="window.RPG.handleInventoryItemClick('${item.uid}')" class="cursor-pointer p-2.5 rounded-2xl border-2 ${isSelected ? 'border-amber-400 ring-3 ring-amber-400/60 scale-102 bg-amber-500/15 shadow-md shadow-amber-500/20' : rInfo.color} flex flex-col justify-between hover:scale-102 active:scale-98 transition-all relative space-y-1 bg-white/70 dark:bg-slate-800/80 shadow-xs">
        <!-- Multi-select Checkbox Badge -->
        <button onclick="event.stopPropagation(); window.RPG.toggleItemSelection('${item.uid}')" class="absolute top-1.5 left-1.5 w-6 h-6 rounded-lg flex items-center justify-center text-xs font-black border transition-all z-10 ${isSelected ? 'bg-amber-500 border-amber-300 text-slate-950 shadow-md scale-110' : 'bg-slate-900/80 border-slate-600 text-slate-400 hover:border-amber-400 hover:text-white'}">
          ${isSelected ? "✓" : "○"}
        </button>
        <div class="flex items-center justify-between">
          <span class="text-[8.5px] font-extrabold px-1.5 py-0.2 rounded bg-black/20 ml-6">${slotBadge}</span>
          <div class="flex items-center gap-1">
            ${(() => {
              const activeDef = Object.values(ACTIVE_ITEM_DEFINITIONS).find(d => d.match(item));
              return activeDef ? `<span class="px-1 rounded bg-amber-500/20 text-amber-400 text-[8px] font-black border border-amber-500/30">⚡ АКТИВКА</span>` : "";
            })()}
            ${forgeTag ? `<span class="px-1.5 rounded-md bg-amber-500 text-slate-950 font-black text-[8.5px] shadow-sm">${forgeTag}</span>` : ""}
          </div>
        </div>
        <div class="text-center py-1">
          <span class="text-2xl block">${item.icon || "📦"}</span>
          <span class="block text-[10.5px] font-black truncate mt-0.5">${item.name}</span>
        </div>
        <div class="text-center min-h-[14px]">
          <span class="text-[8.5px] text-slate-500 dark:text-slate-400 line-clamp-2 block leading-tight">${item.bonus_desc || ""}</span>
        </div>
        ${actionBtnHTML}
      </div>
    `;
  }

  // ===========================================================================
  // 2. FARM TAB (2D ACTION ARENA OR FAST SIM)
  // ===========================================================================

  function renderFarmTabHTML() {
    const p = RPG_STATE.profile || {};
    const floor = p.dungeon_floor || 1;
    const isArena = RPG_STATE.farmMode === "arena";
    const isRaidBoss = !!ARENA.isRaidBossBattle;
    const isDungeonBoss = !!(ARENA.isBossActive && ARENA.topDownMode);
    const bossObj = ARENA.bossEntity || ARENA.currentRaidBoss || {};

    if (isRaidBoss) {
      return `
        <div class="space-y-3.5">
          <!-- Brawl Boss Fight Header -->
          <div class="p-3.5 rounded-2xl bg-gradient-to-r from-red-950 via-purple-950 to-amber-950 text-white border-2 border-red-500/50 shadow-xl flex items-center justify-between">
            <div class="flex items-center gap-3">
              <span class="text-3xl animate-bounce">👑</span>
              <div>
                <div class="flex items-center gap-2">
                  <h3 class="text-sm font-black tracking-wide uppercase text-amber-400">
                    БОЙ С БОССОМ: ${bossObj.name || "БОСС"}
                  </h3>
                  <span class="text-[9px] px-2 py-0.5 rounded-full bg-red-600 text-white font-extrabold uppercase shadow-sm">BRAWL 2D</span>
                </div>
                <p class="text-[11px] text-purple-200 font-medium">
                  Джойстик — беги в 360°, уворачивайся от тарана и ракет! Отпусти — автострельба!
                </p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <button onclick="window.RPG.toggleBossPartyMode()" class="px-2.5 py-1.5 rounded-xl bg-slate-800/90 hover:bg-slate-700 active:scale-95 text-white font-bold text-xs border border-slate-600 flex items-center gap-1 shadow-md">
                <span>${(ARENA.bossPartyMode || "trio") === "trio" ? "👥 3 Игрока" : "👤 1 Игрок"}</span>
              </button>
              <button onclick="window.RPG.exitRaidBossBattle()" class="px-3 py-1.5 rounded-xl bg-slate-800/90 hover:bg-slate-700 active:scale-95 text-slate-300 font-bold text-xs border border-slate-600 flex items-center gap-1 shadow-md">
                <span>✕ В лобби</span>
              </button>
            </div>
          </div>

          ${renderActionArenaHTML()}
        </div>
      `;
    }

    return `
      <div class="space-y-3.5">
        <!-- Floor Header & Mode Switcher -->
        <div class="p-3.5 rounded-2xl bg-gradient-to-r from-red-950 via-slate-900 to-amber-950 text-white border border-red-500/30 shadow-md flex items-center justify-between">
          <div>
            <div class="flex items-center gap-2">
              <span class="text-base">⚔️</span>
              <h3 class="text-sm font-black tracking-wide uppercase">
                Этаж ${floor} Катакомб
              </h3>
            </div>
            <p class="text-[11px] text-amber-200/80 font-medium">
              ${isArena ? (isDungeonBoss ? `👑 Бой с боссом: ${bossObj.name || "Босс этажа"}!` : "Защита тропы! Крипы бегут справа — руби и отбивай боссов!") : "Автоматическое месилово крипов"}
            </p>
          </div>

          <!-- Mode Toggle Buttons -->
          <div class="flex items-center p-1 rounded-xl bg-slate-800/80 border border-slate-700 text-[10px] font-bold">
            <button onclick="window.RPG.setFarmMode('arena')" class="px-2.5 py-1 rounded-lg transition-all ${
              isArena ? "bg-amber-500 text-slate-950 font-black" : "text-slate-400 hover:text-white"
            }">
              🎮 Арена
            </button>
            <button onclick="window.RPG.setFarmMode('sim')" class="px-2.5 py-1 rounded-lg transition-all ${
              !isArena ? "bg-amber-500 text-slate-950 font-black" : "text-slate-400 hover:text-white"
            }">
              ⚡ Авто
            </button>
          </div>
        </div>

        ${isArena ? renderActionArenaHTML() : renderFastSimHTML()}
      </div>
    `;
  }

  function renderActionArenaHTML() {
    const p = RPG_STATE.profile || {};
    const stats = p.stats || {};
    const cfg = getHeroSkillConfig();
    const isBossFight = !!(ARENA.isRaidBossBattle || (ARENA.isBossActive && ARENA.topDownMode));
    const s1CdSec = ARENA.skill1Cooldown > 0 ? Math.ceil(ARENA.skill1Cooldown / 60) : 0;
    const ultCdSec = ARENA.ultCooldown > 0 ? Math.ceil(ARENA.ultCooldown / 60) : 0;

    return `
      <div class="space-y-2">
                <!-- Canvas Arena Element -->
        <div class="relative w-full rounded-3xl overflow-hidden border-2 border-amber-500/40 shadow-2xl bg-slate-950">
          <canvas id="rpg-action-canvas" class="w-full ${isBossFight ? 'h-[520px]' : 'h-[320px]'} block cursor-crosshair"></canvas>

          ${ARENA.isRaidBossBattle ? `
          <div class="absolute top-3 left-3 z-20 flex items-center gap-1.5">
            <button onclick="window.RPG.exitRaidBossBattle()"
              class="h-7 px-2.5 rounded-full bg-slate-900/90 border border-slate-700 text-slate-300 font-bold text-[10px] flex items-center gap-1.5 shadow-lg active:scale-95 transition-all">
              <span>✕ В лобби боссов</span>
            </button>
          </div>
          ` : ""}

          <!-- Virtual Touch Joystick (Active only during boss battles) -->
          ${isBossFight ? `<div id="rpg-virtual-joystick-zone"
               class="absolute bottom-3 left-3 w-24 h-24 flex items-center justify-center pointer-events-auto z-30 select-none touch-none">
            <div id="rpg-joystick-base" class="relative w-20 h-20 rounded-full border-2 border-amber-400/50 bg-slate-900/80 shadow-2xl flex items-center justify-center backdrop-blur-md ring-2 ring-amber-500/20">
              <span class="absolute top-1 text-[9px] text-amber-300/50">▲</span>
              <span class="absolute bottom-1 text-[9px] text-amber-300/50">▼</span>
              <span class="absolute left-1.5 text-[9px] text-amber-300/50">◀</span>
              <span class="absolute right-1.5 text-[9px] text-amber-300/50">▶</span>
              <div id="rpg-joystick-knob" class="w-8 h-8 rounded-full bg-gradient-to-tr from-amber-500 to-yellow-300 shadow-xl border-2 border-white pointer-events-none flex items-center justify-center">
                <span class="text-xs font-black text-slate-950">🕹️</span>
              </div>
            </div>
          </div>` : ""}

          <!-- Active Items (above joystick) -->
          <div class="absolute bottom-28 left-3 z-20 flex flex-col gap-2">
            <button id="rpg-btn-potion" ontouchstart="event.preventDefault(); window.RPG.usePotionAction()" onmousedown="event.preventDefault(); window.RPG.usePotionAction()" onclick="window.RPG.usePotionAction()" title="Зелье / Сыр [F / 1]" class="w-10 h-10 rounded-2xl bg-emerald-600/95 border-2 border-emerald-300 text-white font-bold text-lg flex items-center justify-center shadow-lg active:scale-90 transition-transform relative">
              <span>🧪</span>
              <span id="rpg-cd-potion" class="text-[8px] font-black absolute bottom-0.5 pointer-events-none drop-shadow"></span>
            </button>
            ${(window.RPG.getEquippedActiveItems ? window.RPG.getEquippedActiveItems() : []).map((act, idx) => {
              const cdSec = act.currentCd > 0 ? Math.ceil(act.currentCd / 60) : 0;
              return `
              <button id="rpg-btn-item-${idx}" ontouchstart="event.preventDefault(); window.RPG.useActiveItemAction(${idx})" onmousedown="event.preventDefault(); window.RPG.useActiveItemAction(${idx})" onclick="window.RPG.useActiveItemAction(${idx})" title="${act.name}" class="w-10 h-10 rounded-2xl ${cdSec > 0 ? 'bg-slate-800/80 border border-slate-700 opacity-60' : 'bg-indigo-600/95 border-2 border-indigo-300'} text-white font-bold text-lg flex flex-col items-center justify-center shadow-lg active:scale-90 transition-transform relative">
                <span class="text-base">${act.def.icon || '✨'}</span>
                <span id="rpg-cd-item-${idx}" class="text-[8px] font-bold absolute bottom-0.5">${cdSec > 0 ? cdSec + 'с' : ''}</span>
              </button>`;
            }).join('')}
          </div>

          <!-- Right Action Buttons (Attack, Dash / Roll, Skill 1, Ultimate) -->
          <div class="absolute bottom-3 right-3 flex flex-col gap-1.5 z-20">
            <!-- Top row: Skill 1 + Ultimate -->
            <div class="flex items-center gap-1.5">
              <!-- Hero Skill 1 Button [E] -->
              <button id="rpg-btn-skill1" ontouchstart="event.preventDefault(); window.RPG.castSkill1Action()" onmousedown="event.preventDefault(); window.RPG.castSkill1Action()" onclick="window.RPG.castSkill1Action()" title="${cfg.skill1Name} [E]" class="w-11 h-11 rounded-2xl ${s1CdSec > 0 ? 'bg-slate-800/80 border border-slate-700 opacity-60' : 'bg-gradient-to-r from-blue-600 to-cyan-600 border-2 border-cyan-400'} text-white font-black text-sm flex flex-col items-center justify-center shadow-lg active:scale-90 transition-transform">
                <span class="text-base">${cfg.skill1Icon || '⚡'}</span>
                <span id="rpg-cd-skill1" class="text-[8px] font-bold">${s1CdSec > 0 ? `${s1CdSec}с` : 'Скилл'}</span>
              </button>

              <!-- Hero Ultimate Skill Button [Q] -->
              <button id="rpg-btn-ult" ontouchstart="event.preventDefault(); window.RPG.castUltimateAction()" onmousedown="event.preventDefault(); window.RPG.castUltimateAction()" onclick="window.RPG.castUltimateAction()" title="${cfg.ultName} [Q]" class="w-11 h-11 rounded-2xl ${ultCdSec > 0 ? 'bg-slate-800/80 border border-slate-700 opacity-60' : 'bg-gradient-to-r from-purple-600 to-indigo-600 border-2 border-purple-400'} text-white font-black text-sm flex flex-col items-center justify-center shadow-lg active:scale-90 transition-transform">
                <span class="text-base">${cfg.ultIcon || '🌟'}</span>
                <span id="rpg-cd-ult" class="text-[8px] font-bold">${ultCdSec > 0 ? `${ultCdSec}с` : 'Ульта'}</span>
              </button>
            </div>

            <!-- Bottom row: Attack + Dash (Dash only visible during boss fight) -->
            <div class="flex items-center gap-1.5">
              <!-- Attack / Shoot Button [Space / Click] -->
              <button id="rpg-btn-attack" ontouchstart="event.preventDefault(); window.RPG.playerSlashAttackAction()" onclick="window.RPG.playerSlashAttackAction()" title="Атака [Пробел / Клик]"
                class="w-11 h-11 rounded-2xl bg-gradient-to-r from-red-600 via-rose-600 to-amber-500 border-2 border-amber-300 text-white font-black text-xs flex flex-col items-center justify-center shadow-lg shadow-red-600/40 active:scale-90 transition-transform">
                <span class="text-base leading-none">⚔️</span>
                <span class="text-[8px] font-bold mt-0.5">АТАК</span>
              </button>

              ${isBossFight ? `
              <!-- Dash / Roll Button (Boss battle only) -->
              <button ontouchstart="event.preventDefault(); window.RPG.playerDashRollAction()" onmousedown="event.preventDefault(); window.RPG.playerDashRollAction()" onclick="window.RPG.playerDashRollAction()" title="Рывок / Кувырок [Shift / C]"
                class="w-11 h-11 rounded-2xl ${ARENA.dodgeCooldown > 0 ? 'bg-slate-800/80 border border-slate-700 opacity-60' : 'bg-gradient-to-r from-sky-500 to-cyan-500 border-2 border-sky-300 shadow-sky-500/40'} text-white font-black text-sm flex flex-col items-center justify-center shadow-lg active:scale-90 transition-all">
                <span class="text-base">🌀</span>
                <span class="text-[8px] leading-tight font-bold">${ARENA.dodgeCooldown > 0 ? Math.ceil(ARENA.dodgeCooldown / 60) + 'с' : 'Рывок'}</span>
              </button>
              ` : ""}
            </div>
          </div>
        </div>

        <!-- Controls Guide Toolbar -->
        <div class="p-2.5 rounded-2xl bg-slate-100 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 text-[10.5px] text-slate-500 dark:text-slate-400 flex flex-wrap items-center justify-between gap-2">
          <div class="flex items-center gap-1.5">
            <span>${isBossFight ? '🕹️ <b>Бой с боссом</b>: джойстик — перемещение, [⚔️ Атака] — огонь, [🌀 Рывок] — уворот!' : '⚔️ <b>Фарм волн</b>: [⚔️ Атака] / Авто-бой — зачистка крипов, сбор золота и лута!'}</span>
          </div>
          <div class="flex items-center gap-2">
            <!-- Auto-Attack ON / OFF Toggle Button (Wave/Dungeon/Arena) -->
            <button id="rpg-auto-attack-btn" onclick="window.RPG.toggleArenaAutoAttack()" class="px-2.5 py-1 rounded-xl text-xs font-black transition-all ${ARENA.player.autoAttack ? 'bg-amber-500/20 text-amber-500 border border-amber-500/40 shadow-sm' : 'bg-slate-200 dark:bg-slate-700 text-slate-500'}" title="Включить или выключить автоматический удар">
              Авто-удар: ${ARENA.player.autoAttack ? "ВКЛ ⚔️" : "ВЫКЛ ✋"}
            </button>
            <button id="rpg-wave-confirm-btn" onclick="window.RPG.toggleArenaWaveConfirm()" class="px-2.5 py-1 rounded-xl text-xs font-black transition-all ${ARENA.autoAdvanceWaves ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-sm' : 'bg-slate-200 dark:bg-slate-700 text-slate-500'}" title="${ARENA.autoAdvanceWaves ? 'Подтверждение волн отключено' : 'Подтверждение волн включено'}">
              Авто-волны: ${ARENA.autoAdvanceWaves ? "ВКЛ ⏩" : "ВЫКЛ ⏸️"}
            </button>
          </div>
        </div>
      </div>
    `;
  }

  function renderFastSimHTML() {
    const p = RPG_STATE.profile || {};
    const stats = p.stats || {};
    const battle = RPG_STATE.lastBattle;

    return `
      <div class="space-y-3.5">
        <!-- Arena Display -->
        <div class="theme-card p-4 rounded-3xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm space-y-4">
          <!-- Floor & Wave Synchronized Status -->
          <div class="flex items-center justify-between px-3 py-2 rounded-2xl bg-slate-100 dark:bg-slate-900/60 border border-slate-200/60 dark:border-slate-700/60 text-xs font-bold text-slate-600 dark:text-slate-300">
            <span>⚔️ Этаж ${p.dungeon_floor || 1} • Волна <b class="text-amber-500">${((p.dungeon_cleared || 0) % 20) + 1} / 20</b></span>
            <span class="ml-3">🐉 Боссов убито: <b class="text-emerald-400">${p.boss_kills || 0}</b></span>
            <span>🏆 Зачищено всего: <b class="text-emerald-500">${p.dungeon_cleared || 0} волн</b></span>
          </div>

          <div class="flex items-center justify-between gap-3">
            <!-- Hero Side -->
            <div class="flex-1 text-center space-y-1.5 p-3 rounded-2xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200/60 dark:border-slate-700/60">
              <div class="text-3xl">${p.class_avatar || p.class_icon || "🛡️"}</div>
              <div class="text-xs font-black truncate">${p.user_name || p.class_name}</div>
              <div class="space-y-1">
                ${(() => {
                  const hMax = battle?.hero_hp_max || stats.hp_max || 180;
                  const hCur = battle?.hero_hp_left !== undefined ? battle.hero_hp_left : hMax;
                  const hPct = Math.max(0, Math.min(100, Math.round((hCur / hMax) * 100)));
                  return `
                    <div class="flex justify-between text-[10px] font-bold text-slate-500 dark:text-slate-400">
                      <span>HP</span>
                      <span class="${hCur <= 0 ? 'text-rose-500 font-black' : ''}">${hCur.toLocaleString()} / ${hMax.toLocaleString()}</span>
                    </div>
                    <div class="w-full h-2 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                      <div class="h-full ${hCur <= 0 ? 'bg-rose-500' : 'bg-emerald-500'} transition-all duration-300" style="width: ${hPct}%"></div>
                    </div>
                  `;
                })()}
              </div>
            </div>

            <!-- VS Badge -->
            <div class="flex flex-col items-center justify-center">
              <span class="text-xs font-black px-2.5 py-1 rounded-xl bg-red-500/10 text-red-600 border border-red-500/30">VS</span>
            </div>

            <!-- Enemy Side -->
            <div class="flex-1 text-center space-y-1.5 p-3 rounded-2xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200/60 dark:border-slate-700/60">
              <div class="text-3xl">${battle?.enemy_icon || "👾"}</div>
              <div class="text-xs font-black truncate">${battle?.enemy_name || "Пачка крипов"}</div>
              <div class="space-y-1">
                ${(() => {
                  const eMax = battle?.enemy_hp_max || 100;
                  const eCur = battle?.enemy_hp_left !== undefined ? battle.enemy_hp_left : (battle?.victory ? 0 : eMax);
                  const ePct = Math.max(0, Math.min(100, Math.round((eCur / eMax) * 100)));
                  return `
                    <div class="flex justify-between text-[10px] font-bold text-slate-500 dark:text-slate-400">
                      <span>HP Врагов</span>
                      <span>${eCur <= 0 ? '💀 0 (Повержен)' : `${eCur.toLocaleString()} (${ePct}%)`}</span>
                    </div>
                    <div class="w-full h-2 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
                      <div class="h-full bg-red-500 transition-all duration-300" style="width: ${ePct}%"></div>
                    </div>
                  `;
                })()}
              </div>
            </div>
          </div>

          <!-- Streak & Victory banner if just fought -->
          ${
            battle
              ? `
            <div class="p-3 rounded-2xl ${
              battle.victory
                ? "bg-gradient-to-r from-amber-500/10 via-emerald-500/10 to-amber-500/10 border border-emerald-500/30 text-emerald-700 dark:text-emerald-300"
                : battle.is_draw
                  ? "bg-gradient-to-r from-amber-500/10 to-orange-500/10 border border-amber-500/40 text-amber-700 dark:text-amber-300"
                  : "bg-red-500/10 border border-red-500/30 text-red-600"
            } text-center space-y-1">
              <div class="text-xs font-black tracking-wide">
                ${
                  battle.victory
                    ? (battle.streak_title || "ВОЛНА ЗАЧИЩЕНА! 🏆")
                    : battle.is_draw
                      ? `⏳ НИЧЬЯ (ТАЙМАУТ ${battle.rounds_fought || 400} РАУНДОВ)!`
                      : "💀 ВАШ ГЕРОЙ ПАЛ В БОЮ!"
                }
              </div>
              ${battle.description ? `<div class="text-[10.5px] font-medium opacity-90">${battle.description}</div>` : ""}
              ${
                battle.victory
                  ? `
                <div class="flex items-center justify-center gap-3 text-[11px] font-bold">
                  <span>+${battle.gold_earned} 🪙</span>
                  <span>+${battle.xp_earned} XP</span>
                  ${battle.crits_count > 0 ? `<span>🔥 ${battle.crits_count} критов</span>` : ""}
                  ${battle.rounds_fought ? `<span>⏱️ ${battle.rounds_fought} раундов</span>` : ""}
                </div>
              `
                  : ""
              }
            </div>
          `
              : ""
          }

          <!-- Action Controls -->
          <div class="grid grid-cols-2 gap-2">
            <button onclick="window.RPG.slashWave()" ${RPG_STATE.isFighting ? "disabled" : ""} class="py-3 px-4 rounded-2xl bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 active:scale-95 text-white font-black text-sm shadow-md shadow-red-600/20 flex items-center justify-center gap-2 transition-all ${
              RPG_STATE.isFighting ? "opacity-60 cursor-not-allowed" : ""
            }">
              <span>⚔️</span>
              <span>${RPG_STATE.isFighting ? "Месилово..." : "Зарубить волну"}</span>
            </button>

            <button onclick="window.RPG.toggleAutoFarm()" class="py-3 px-4 rounded-2xl ${
              RPG_STATE.autoFarm
                ? "bg-amber-500 text-slate-950 font-black animate-pulse"
                : "bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200 font-bold hover:bg-slate-300"
            } active:scale-95 text-sm shadow-sm flex items-center justify-center gap-2 transition-all">
              <span>⚡</span>
              <span>${RPG_STATE.autoFarm ? "Стоп авто-фарм" : "Авто-месилово"}</span>
            </button>
          </div>
        </div>

        <!-- Combat Feed / Log -->
        <div class="theme-card p-3.5 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm space-y-2">
          <div class="flex items-center justify-between text-xs font-black uppercase text-slate-500 dark:text-slate-400">
            <span>📜 Лог сражения</span>
            <span>Сессия: ${RPG_STATE.killsSession} волн</span>
          </div>

          <div class="p-2.5 rounded-xl bg-slate-100 dark:bg-slate-900/60 max-h-36 overflow-y-auto space-y-1 font-mono text-[11px]">
            ${
              RPG_STATE.combatLog.length === 0
                ? `<div class="text-slate-400 text-center py-2">Нажмите «Зарубить волну» для фарма золота и опыта!</div>`
                : RPG_STATE.combatLog.map((line) => `<div class="leading-tight text-slate-700 dark:text-slate-300">${line}</div>`).join("")
            }
          </div>
        </div>
      </div>
    `;
  }

  // ===========================================================================
  // 3. CO-OP BOSS RAIDS HTML
  // ===========================================================================

  function renderCoopRaidsHTML() {
    if (RPG_STATE.coopRoomId && RPG_STATE.coopRoomData) {
      return renderActiveCoopBattleHTML();
    }

        const TAG_MAP = {
      golem: { tag: "Начальный", color: "border-stone-500/60 bg-stone-500/5" },
      lich: { tag: "Нежить", color: "border-cyan-500/60 bg-cyan-500/5" },
      tormentor: { tag: "Магический", color: "border-purple-500/60 bg-purple-500/5" },
      dragon: { tag: "Рейдовый", color: "border-rose-500/60 bg-rose-500/5" },
      pudge_boss: { tag: "Мясник", color: "border-emerald-600/60 bg-emerald-600/5" },
      faceless_void: { tag: "Хронос", color: "border-purple-600/60 bg-purple-600/5" },
      roshan: { tag: "Хозяин Ямы", color: "border-amber-500/60 bg-amber-500/5" },
      tidehunter: { tag: "Сверх-Ранг", color: "border-teal-500/60 bg-teal-500/5" },
      sf_boss: { tag: "Сверх-Ранг", color: "border-red-600/60 bg-red-600/5" },
      necrophos: { tag: "Сверх-Ранг", color: "border-emerald-600/60 bg-emerald-600/5" },
      terrorblade: { tag: "Сверх-Ранг", color: "border-violet-700/60 bg-violet-700/5" },
      invoker_boss: { tag: "Сверх-Ранг", color: "border-yellow-500/60 bg-yellow-500/5" },
      chaos_knight: { tag: "Сверх-Ранг", color: "border-amber-600/60 bg-amber-600/5" },
      dark_tormentor: { tag: "Сверх-Ранг", color: "border-purple-700/60 bg-purple-700/5" },
      storm_spirit: { tag: "Сверх-Ранг", color: "border-sky-500/60 bg-sky-500/5" },
      doom: { tag: "Сверх-Ранг", color: "border-orange-600/60 bg-orange-600/5" },
      primal_beast: { tag: "Сверх-Ранг", color: "border-red-700/60 bg-red-700/5" },
      phantom_roshan: { tag: "Сверх-Ранг", color: "border-cyan-400/60 bg-cyan-400/5" },
      tinker_boss: { tag: "Сверх-Босс", color: "border-yellow-600/60 bg-yellow-600/5" },
      enigma: { tag: "Финальный Босс", color: "border-indigo-600/60 bg-indigo-600/5" }
    };

    const bosses = (RPG_STATE.coopBosses && RPG_STATE.coopBosses.length > 0)
      ? RPG_STATE.coopBosses.map(b => ({
          id: b.id,
          name: b.name,
          icon: b.icon || "🗿",
          hp: b.hp_display ? `${b.hp_display} HP` : `${formatCompact(b.max_hp || b.hp)} HP`,
          desc: b.desc || "Могущественный рейд-босс",
          tag: (TAG_MAP[b.id] || {}).tag || "Рейдовый",
          color: (TAG_MAP[b.id] || {}).color || "border-purple-500/60 bg-purple-500/5"
        }))
      : [
          { id: "golem", name: "Древний Гранитный Голем", icon: "🗿", hp: "75,000 HP", desc: "[75k HP] Гигант из древнего гранита с тяжелыми разломами земли.", tag: "Начальный", color: "border-stone-500/60 bg-stone-500/5" },
          { id: "lich", name: "Архилич Некрополя", icon: "☠️", hp: "225,000 HP", desc: "[225k HP] Владыка темных заклятий, ледяных сфер и телепортации.", tag: "Нежить", color: "border-cyan-500/60 bg-cyan-500/5" },
          { id: "tormentor", name: "Древний Терзатель", icon: "🔮", hp: "700,000 HP", desc: "[700k HP] Отражает входящий урон кристальным панцирем. Дропает Shard!", tag: "Магический", color: "border-purple-500/60 bg-purple-500/5" },
          { id: "dragon", name: "Дракон Инферно", icon: "🌋", hp: "2.2M HP", desc: "[2.2M HP] Испепеляет арену потоками лавы и огненными взмахами крыльев.", tag: "Рейдовый", color: "border-rose-500/60 bg-rose-500/5" },
          { id: "pudge_boss", name: "Мясник из Чрева (Pudge)", icon: "🪝", hp: "7.5M HP", desc: "[7.5M HP] Тесак, ржавый крюк цепью и отравляющая вонь гнили.", tag: "Мясник", color: "border-emerald-600/60 bg-emerald-600/5" },
          { id: "faceless_void", name: "Хроно-Владыка (Faceless Void)", icon: "⏳", hp: "25M HP", desc: "[25M HP] Повелитель времени, двойные баши и купол Хроносферы.", tag: "Хронос", color: "border-purple-600/60 bg-purple-600/5" },
          { id: "roshan", name: "Рошан Свирепый (Roshan)", icon: "🐲", hp: "85M HP", desc: "[85M HP] КУЛЬТОВЫЙ ХОЗЯИН ЯМЫ! Дропает Aegis of the Immortal, Сыр и Divine Rapier!", tag: "Хозяин Ямы", color: "border-amber-500/60 bg-amber-500/5" },
          { id: "tidehunter", name: "Левиафан Бездны (Tidehunter)", icon: "🐙", hp: "300M HP", desc: "[300M HP] Владыка пучин. Чешуя Кракена гасит урон, Раваж сносит арену.", tag: "Сверх-Ранг", color: "border-teal-500/60 bg-teal-500/5" },
          { id: "sf_boss", name: "Архидемон Nevermore", icon: "💀", hp: "1B HP", desc: "[1 МИЛЛИАРД HP] Собирает легион душ. Тройные коилы и Реквием Душ!", tag: "Сверх-Ранг", color: "border-red-600/60 bg-red-600/5" },
          { id: "necrophos", name: "Чумной Владыка (Necrophos)", icon: "🧟", hp: "3.5B HP", desc: "[3.5 МИЛЛИАРДА HP] Аура чумы истощает здоровье, Коса Смерти рубит наповал!", tag: "Сверх-Ранг", color: "border-emerald-600/60 bg-emerald-600/5" },
          { id: "terrorblade", name: "Демон Бездны (Terrorblade)", icon: "😈", hp: "12B HP", desc: "[12 МИЛЛИАРДОВ HP] Метаморфоза в крылатого демона и разрыв души Sunder!", tag: "Сверх-Ранг", color: "border-violet-700/60 bg-violet-700/5" },
          { id: "invoker_boss", name: "Демиург Арсенала (Invoker)", icon: "🧙‍♂️", hp: "42B HP", desc: "[42 МИЛЛИАРДА HP] Повелитель всех стихий. Обрушивает хаос-метеоры!", tag: "Сверх-Ранг", color: "border-yellow-500/60 bg-yellow-500/5" },
          { id: "chaos_knight", name: "Всадник Хаоса (Chaos Knight)", icon: "🐎", hp: "150B HP", desc: "[150 МИЛЛИАРДОВ HP] Призывает фантомы и пробивает непредсказуемыми критами!", tag: "Сверх-Ранг", color: "border-amber-600/60 bg-amber-600/5" },
          { id: "dark_tormentor", name: "Тёмный Терзатель Бездны", icon: "💎", hp: "550B HP", desc: "[550 МИЛЛИАРДОВ HP] Мутировавший Терзатель Тьмы с отражением урона!", tag: "Сверх-Ранг", color: "border-purple-700/60 bg-purple-700/5" },
          { id: "storm_spirit", name: "Громовой Дух (Storm Spirit)", icon: "⚡", hp: "2T HP", desc: "[2 ТРИЛЛИОНА HP] Молниеносные перелеты через всю арену и статические мины!", tag: "Сверх-Ранг", color: "border-sky-500/60 bg-sky-500/5" },
          { id: "doom", name: "Вестник Апокалипсиса (Lord Doom)", icon: "👹", hp: "7.5T HP", desc: "[7.5 ТРИЛЛИОНОВ HP] Владыка преисподней с чистым уроном и роком!", tag: "Сверх-Ранг", color: "border-orange-600/60 bg-orange-600/5" },
          { id: "primal_beast", name: "Первобытный Титан (Primal Beast)", icon: "🦣", hp: "28T HP", desc: "[28 ТРИЛЛИОНОВ HP] Неукротимый сокрушитель материков с яростным топотом!", tag: "Сверх-Ранг", color: "border-red-700/60 bg-red-700/5" },
          { id: "phantom_roshan", name: "Призрачный Рошан Хаоса", icon: "👻", hp: "100T HP", desc: "[100 ТРИЛЛИОНОВ HP] Восставший из Бездны призрак Рошана с астральным Slam!", tag: "Сверх-Ранг", color: "border-cyan-400/60 bg-cyan-400/5" },
          { id: "tinker_boss", name: "Архиинженер (Omega Tinker)", icon: "🤖", hp: "350T HP", desc: "[350 ТРИЛЛИОНОВ HP] Лазер, шквал ракет и марш сотен боевых роботов!", tag: "Сверх-Босс", color: "border-yellow-600/60 bg-yellow-600/5" },
          { id: "enigma", name: "Пожиратель Миров (Enigma Cosmic)", icon: "🌌", hp: "1.2Q HP", desc: "[1.2 КВАДРИЛЛИОНА HP!] Битва на века! Схлопывает арену в Черную Дыру!", tag: "Финальный Босс", color: "border-indigo-600/60 bg-indigo-600/5" }
        ];

    return `
      <div class="space-y-3.5">
        <div class="p-3.5 rounded-2xl bg-gradient-to-r from-purple-950 via-slate-900 to-amber-950 text-white border border-purple-500/30 shadow-md">
          <div class="flex items-center gap-2">
            <span class="text-xl">🐉</span>
            <div>
              <h3 class="text-sm font-black tracking-wide uppercase">Совместные Рейды на Боссов (до 3 игроков)</h3>
              <p class="text-[11px] text-purple-200/80">Идите на босса втроем! Герои стоят по кругу, а босс в центре бьет всех по очереди. Награды сохраняются в профиль.</p>
            </div>
          </div>
        </div>

        <!-- Join Room by Code -->
        <div class="p-3 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 flex items-center gap-2 shadow-sm">
          <input id="coop-room-code-input" type="text" placeholder="Код рейда (напр. 1234)" class="flex-1 px-3 py-2 text-xs rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 font-mono text-slate-800 dark:text-slate-200 uppercase outline-none focus:border-purple-500" />
          <button onclick="window.RPG.joinCoopRoom()" class="px-4 py-2 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 active:scale-95 text-white font-black text-xs shadow-sm flex items-center gap-1">
            <span>Войти</span>
          </button>
        </div>

        <!-- Boss Picker -->
        <div class="space-y-2.5">
          ${bosses
            .map(
              (b) => `
            <div class="p-3.5 rounded-2xl border-2 ${b.color} bg-white dark:bg-slate-800 shadow-sm space-y-2.5 transition-all">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2.5">
                  <span class="text-3xl">${b.icon}</span>
                  <div>
                    <h4 class="text-xs font-black text-slate-800 dark:text-white">${b.name}</h4>
                    <span class="text-[10px] font-bold text-red-500">${b.hp}</span>
                  </div>
                </div>
                <span class="text-[10px] font-extrabold px-2 py-0.5 rounded-md bg-purple-500/20 text-purple-600 dark:text-purple-400">${b.tag}</span>
              </div>

              <p class="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed font-normal">${b.desc}</p>

              <div class="space-y-1.5 pt-1">
                <button onclick="window.RPG.startRaidBossActionBattle('${b.id}')" class="w-full py-2.5 rounded-xl bg-gradient-to-r from-red-600 via-rose-600 to-amber-600 hover:from-red-500 hover:to-amber-500 active:scale-95 text-white font-black text-xs shadow-lg shadow-red-600/30 flex items-center justify-center gap-2 border border-red-400/40">
                  <span>⚔️</span>
                  <span>В бой на Арену (Экшен 60 FPS)</span>
                </button>
                <div class="grid grid-cols-2 gap-1.5">
                  <button onclick="window.RPG.startRaidBossActionBattle('${b.id}')" class="py-2 rounded-xl bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 active:scale-95 text-white font-black text-[11px] shadow-sm flex items-center justify-center gap-1 border border-red-400/40">
                    <span>⚔️</span>
                    <span>2D Дуэль 1v1</span>
                  </button>
                  <button onclick="window.RPG.createCoopRaid('${b.id}', false)" class="py-2 rounded-xl bg-gradient-to-r from-purple-700 to-indigo-700 hover:from-purple-600 active:scale-95 text-white font-bold text-[11px] shadow-sm flex items-center justify-center gap-1">
                    <span>👥</span>
                    <span>Кооп (3 чел)</span>
                  </button>
                </div>
              </div>
            </div>
          `
            )
            .join("")}
        </div>
      </div>
    `;
  }

  function renderCoopHeroCard(hero, role, label, isCurrentTurn, isBossTarget) {
    if (!hero || !hero.name || hero.name === "Свободный слот") {
      return `
        <div class="w-24 sm:w-28 p-2 rounded-2xl border-2 border-dashed border-slate-300 dark:border-slate-700/80 bg-slate-100/50 dark:bg-slate-900/40 text-center space-y-1 shadow-sm">
          <span class="text-lg opacity-40">➕</span>
          <div class="text-[9.5px] font-bold text-slate-400">${label}</div>
          <button onclick="window.RPG.addCoopBot()" class="px-2 py-0.5 rounded-lg bg-purple-600 hover:bg-purple-500 active:scale-95 text-white font-black text-[8px] shadow-xs">
            🤖 Бот
          </button>
        </div>
      `;
    }

    const hpPct = Math.max(0, Math.min(100, Math.round((hero.hp / (hero.hp_max || 1)) * 100)));
    const mpPct = Math.max(0, Math.min(100, Math.round((hero.mp / (hero.mp_max || 1)) * 100)));
    const isDead = hero.is_dead || hero.hp <= 0;

    let borderClass = "border-slate-200 dark:border-slate-700";
    if (isDead) {
      borderClass = "border-rose-900/60 opacity-50 grayscale";
    } else if (isCurrentTurn) {
      borderClass = "border-amber-400 ring-2 ring-amber-400/80 shadow-lg shadow-amber-500/20";
    } else if (isBossTarget) {
      borderClass = "border-red-500 ring-2 ring-red-500/80 shadow-lg shadow-red-500/20 animate-pulse";
    }

    return `
      <div class="w-24 sm:w-28 p-1.5 rounded-2xl bg-white/95 dark:bg-slate-800/95 border-2 ${borderClass} transition-all space-y-1 text-center shadow-md relative">
        ${isCurrentTurn ? `<span class="absolute -top-2 left-1/2 -translate-x-1/2 px-1.5 py-0.2 rounded-md bg-amber-500 text-slate-950 font-black text-[7.5px] shadow-sm animate-pulse whitespace-nowrap">⚡ ХОД</span>` : ""}
        ${isBossTarget && !isDead ? `<span class="absolute -bottom-2 left-1/2 -translate-x-1/2 px-1.5 py-0.2 rounded-md bg-red-600 text-white font-black text-[7.5px] shadow-sm whitespace-nowrap">🎯 ЦЕЛЬ</span>` : ""}
        ${hero.is_defending ? `<span class="absolute -top-1.5 right-1 text-[10px]">🛡️</span>` : ""}

        <div class="flex items-center justify-center">
          <span class="text-xl">${isDead ? "💀" : (hero.class_icon || "🛡️")}</span>
        </div>
        <div class="text-[9.5px] font-black truncate text-slate-900 dark:text-white px-0.5">${hero.name}</div>
        
        <!-- HP -->
        <div class="space-y-0.5">
          <div class="w-full h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
            <div class="h-full ${hpPct > 35 ? 'bg-emerald-500' : 'bg-red-500'} transition-all duration-300" style="width: ${hpPct}%"></div>
          </div>
          <div class="text-[8px] font-bold text-slate-500 dark:text-slate-400 leading-none">${hero.hp}/${hero.hp_max}</div>
        </div>

        <!-- MP -->
        <div class="w-full h-1 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
          <div class="h-full bg-sky-400 transition-all duration-300" style="width: ${mpPct}%"></div>
        </div>
      </div>
    `;
  }

  function renderActiveCoopBattleHTML() {
    const r = RPG_STATE.coopRoomData;
    const boss = r.boss || {};
    const p1 = r.players?.host || {};
    const p2 = r.players?.player_2 || r.players?.opponent || {};
    const p3 = r.players?.player_3 || {};
    const yourRole = r.your_role;
    const isYourTurn = r.is_your_turn;
    const bossTarget = r.boss_target;

    const bossHpPct = Math.max(0, Math.min(100, Math.round((boss.hp / (boss.hp_max || 1)) * 100)));
    const targetName = bossTarget === "host" ? p1.name : bossTarget === "player_2" || bossTarget === "opponent" ? p2.name : bossTarget === "player_3" ? p3.name : "";

    return `
      <div class="space-y-3.5">
        <!-- Header Status -->
        <div class="p-3 rounded-2xl bg-slate-900 text-white flex items-center justify-between border ${r.is_solo ? 'border-rose-500/40' : 'border-purple-500/40'}">
          <div class="flex items-center gap-2">
            <span class="text-xl">${boss.icon || "🐉"}</span>
            <div>
              <h4 class="text-xs font-black">${boss.name || "Босс"} ${r.is_solo ? '<span class="text-[9px] px-1.5 py-0.2 rounded bg-rose-600 text-white font-extrabold ml-1">СОЛО 1v1</span>' : ''}</h4>
              <span class="text-[10px] text-slate-400">
                ${r.status === "waiting" ? (r.is_solo ? "Готов к бою 1v1" : "Ожидание героев (до 3 игроков)") : r.status === "playing" ? (r.is_solo ? "Идет дуэль 1 на 1!" : "Идет круговой бой!") : "Рейд завершен"}
              </span>
            </div>
          </div>
          <div class="flex items-center gap-1.5">
            <button onclick="window.RPG.startRaidBossActionBattle('${boss.id || 'golem'}')" class="px-2.5 py-1 rounded-lg bg-gradient-to-r from-red-600 to-amber-600 hover:from-red-500 text-white text-[10px] font-black shadow-sm flex items-center gap-1">
              <span>⚔️</span>
              <span>На Арену</span>
            </button>
            <button onclick="navigator.clipboard && navigator.clipboard.writeText('${r.room_id}'); alert('Код комнаты скопирован: ${r.room_id}');" class="px-2 py-1 rounded-lg bg-purple-900/60 border border-purple-500/40 text-[10px] font-bold text-purple-200">
              #${r.room_id} 📋
            </button>
            <button onclick="window.RPG.leaveCoopRoom()" class="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-bold text-slate-300">
              ✕
            </button>
          </div>
        </div>

        <!-- Boss Big Bar -->
        <div class="theme-card p-3 rounded-2xl bg-white dark:bg-slate-800 border ${boss.shield_active ? "border-purple-500/80 shadow-md shadow-purple-900/30" : "border-slate-200 dark:border-slate-700"} space-y-1.5 transition-all">
          <div class="flex items-center justify-between text-xs font-black">
            <span class="text-red-600 dark:text-red-400 flex items-center gap-1.5">
              <span>${boss.icon || "🐲"}</span>
              <span>${boss.name}</span>
              ${boss.shield_active ? `<span class="px-2 py-0.5 rounded-full bg-purple-900/80 text-purple-200 border border-purple-400 text-[10px] font-black animate-pulse flex items-center gap-1"><span>🔮</span><span>ЩИТ 50%</span></span>` : ""}
            </span>
            <span class="text-[11px]">${boss.hp} / ${boss.hp_max} HP (${bossHpPct}%)</span>
          </div>
          <div class="w-full h-3 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">
            <div class="h-full bg-gradient-to-r from-red-600 to-rose-500 transition-all duration-300" style="width: ${bossHpPct}%"></div>
          </div>
        </div>

        <!-- 2D ACTION ARENA FAST-LAUNCH BANNER -->
        <div class="p-3.5 rounded-2xl bg-gradient-to-r from-red-600 via-rose-600 to-amber-600 text-white shadow-xl shadow-red-950/60 border-2 border-amber-400 flex items-center justify-between gap-3 animate-pulse">
          <div class="flex items-center gap-2.5">
            <span class="text-2xl">⚔️</span>
            <div>
              <span class="text-xs font-black block">НАСТОЯЩИЙ 2D ЭКШЕН-БОЙ НА АРЕНЕ!</span>
              <span class="text-[10px] text-amber-100">Свободное движение героя, увороты, удары и скиллы в 60 FPS</span>
            </div>
          </div>
          <button onclick="window.RPG.startRaidBossActionBattle('${boss.id || 'golem'}')" class="px-4 py-2.5 rounded-xl bg-amber-400 hover:bg-amber-300 active:scale-95 text-slate-950 font-black text-xs shadow-lg whitespace-nowrap">
            В БОЙ 2D ⚡
          </button>
        </div>

        <!-- ARENA DISPLAY: 1v1 SHOWDOWN OR 3-HERO CIRCULAR -->
        ${
          r.is_solo
            ? `
          <div class="theme-card p-4 rounded-3xl bg-gradient-to-b from-slate-900 via-rose-950/30 to-slate-950 border-2 border-rose-500/40 shadow-2xl space-y-3 relative overflow-hidden">
            <div class="text-[10px] font-black uppercase text-center text-rose-400 tracking-wider flex items-center justify-center gap-1.5">
              <span>🗡️</span>
              <span>СОЛО-РЕЙД: ДУЭЛЬ 1 НА 1</span>
            </div>

            <!-- Big Action Arena Button -->
            <button onclick="window.RPG.startRaidBossActionBattle('${boss.id || 'golem'}')" class="w-full py-3 rounded-2xl bg-gradient-to-r from-red-600 via-rose-600 to-amber-600 text-white font-black text-xs shadow-lg active:scale-95 flex items-center justify-center gap-2 border-2 border-amber-400/60">
              <span class="text-base">⚔️</span>
              <span>ВЫЙТИ В 2D БОЙ НА АРЕНУ (РЕАЛЬНОЕ ВРЕМЯ)</span>
            </button>

            <div class="flex items-center justify-around py-3">
              <!-- Solo Hero Card -->
              <div class="flex flex-col items-center">
                <span class="text-[9px] font-extrabold text-slate-400 mb-1">ТВОЙ ГЕРОЙ</span>
                ${renderCoopHeroCard(p1, "host", "Герой", (r.turn === "host"), (bossTarget === "host"))}
              </div>

              <!-- VS Badge -->
              <div class="flex flex-col items-center justify-center px-2">
                <span class="text-3xl font-black text-rose-500 animate-pulse tracking-widest">VS</span>
                <span class="text-[8px] font-extrabold text-rose-300 uppercase px-2 py-0.5 rounded-full bg-rose-900/60 border border-rose-500/40 mt-1">1 на 1</span>
              </div>

              <!-- Boss Card -->
              <div class="flex flex-col items-center">
                <span class="text-[9px] font-extrabold text-red-400 mb-1">РЕЙД БОСС</span>
                <div class="w-24 sm:w-28 p-2 rounded-2xl bg-gradient-to-b from-slate-900 to-red-950/90 border-2 border-red-500/70 shadow-lg text-center space-y-1 relative">
                  <div class="text-2xl animate-bounce">${boss.icon || "🐉"}</div>
                  <div class="text-[9.5px] font-black text-red-300 truncate px-0.5">${boss.name.split(" ")[0]}</div>
                  <div class="space-y-0.5">
                    <div class="w-full h-1.5 rounded-full bg-slate-700 overflow-hidden">
                      <div class="h-full bg-red-500 transition-all duration-300" style="width: ${bossHpPct}%"></div>
                    </div>
                    <div class="text-[8px] font-bold text-amber-300">${boss.hp} / ${boss.hp_max}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        `
            : `
          <!-- CIRCULAR ARENA: 3 HEROES AROUND CENTRAL BOSS -->
          <div class="theme-card p-3.5 rounded-3xl bg-radial from-slate-900 via-purple-950/30 to-slate-950 border-2 border-purple-500/30 shadow-2xl space-y-2 relative overflow-hidden">
            <div class="text-[10px] font-black uppercase text-center text-purple-300 tracking-wider flex items-center justify-center gap-1.5">
              <span>⭕</span>
              <span>Круговая Арена Рейда (Босс в центре)</span>
            </div>

            <!-- Circular Battle Arena Layout -->
            <div class="relative w-full max-w-[320px] mx-auto min-h-[290px] flex flex-col justify-between items-center py-1">
              <!-- Decorative circle track -->
              <div class="absolute inset-4 rounded-full border border-dashed border-purple-500/25 pointer-events-none"></div>

              <!-- Position 1: Player 1 (Top / North) -->
              <div class="z-10">
                ${renderCoopHeroCard(p1, "host", "Игрок 1", (r.turn === "host"), (bossTarget === "host"))}
              </div>

              <!-- Position Center: RAID BOSS -->
              <div id="coop-boss-token" class="z-20 my-1 text-center p-3 rounded-full bg-gradient-to-b from-slate-900 to-red-950/90 border-2 border-red-500/70 shadow-2xl shadow-red-900/60 relative transition-transform duration-200">
                <span class="text-4xl block animate-pulse">${boss.icon || "🐉"}</span>
                <div class="text-[10px] font-black text-red-400 truncate max-w-[80px] mx-auto">${boss.name.split(" ")[0]}</div>
                <div class="text-[9px] font-extrabold text-amber-300">${boss.hp} HP</div>
                ${targetName ? `
                  <div class="text-[7.5px] px-1.5 py-0.2 rounded-full bg-red-600 text-white font-black mt-0.5 whitespace-nowrap shadow-sm">
                    🎯 Очередь: ${targetName}
                  </div>
                ` : ""}
              </div>

              <!-- Position 2 & 3: Player 2 (Left) & Player 3 (Right) -->
              <div class="z-10 w-full flex items-center justify-between px-1">
                <div>
                  ${renderCoopHeroCard(p2, "player_2", "Игрок 2", (r.turn === "player_2" || r.turn === "opponent"), (bossTarget === "player_2" || bossTarget === "opponent"))}
                </div>
                <div>
                  ${renderCoopHeroCard(p3, "player_3", "Игрок 3", (r.turn === "player_3"), (bossTarget === "player_3"))}
                </div>
              </div>
            </div>
          </div>
        `
        }

        <!-- Actions -->
        ${
          r.status === "playing"
            ? (() => {
                const myRole = r.your_role;
                const myHero = myRole === "host" ? p1 : (myRole === "player_2" || myRole === "opponent") ? p2 : p3;
                const skillCd = myHero?.skill_cooldown || 0;
                const canSkill = isYourTurn && skillCd === 0;

                return `
          <div class="theme-card p-3 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 space-y-2">
            <div class="text-xs font-black text-center ${isYourTurn ? "text-amber-500 animate-pulse" : "text-slate-400"}">
              ${isYourTurn ? "🔥 ВАШ ХОД! Выберите действие:" : `⏳ Ход: ${r.turn === "host" ? p1.name : r.turn === "player_2" || r.turn === "opponent" ? p2.name : p3.name}, ждем...`}
            </div>
            <div class="grid grid-cols-4 gap-1.5">
              <button onclick="window.RPG.sendCoopAction('attack')" ${!isYourTurn ? "disabled" : ""} class="py-2.5 rounded-xl bg-gradient-to-r from-red-600 to-rose-600 active:scale-95 text-white font-bold text-xs flex flex-col items-center justify-center gap-0.5 ${!isYourTurn ? "opacity-40 cursor-not-allowed" : "shadow-md shadow-red-600/20"}">
                <span>⚔️</span>
                <span>Атака</span>
              </button>
              <button onclick="window.RPG.sendCoopAction('skill')" ${!canSkill ? "disabled" : ""} class="py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 active:scale-95 text-white font-bold text-xs flex flex-col items-center justify-center gap-0.5 ${!canSkill ? "opacity-40 cursor-not-allowed" : "shadow-md shadow-purple-600/20"}">
                <span>⚡</span>
                <span>${skillCd > 0 ? `КД (${skillCd})` : "Скилл"}</span>
              </button>
              <button onclick="window.RPG.sendCoopAction('defend')" ${!isYourTurn ? "disabled" : ""} class="py-2.5 rounded-xl bg-gradient-to-r from-sky-600 to-blue-600 active:scale-95 text-white font-bold text-xs flex flex-col items-center justify-center gap-0.5 ${!isYourTurn ? "opacity-40 cursor-not-allowed" : "shadow-md shadow-sky-600/20"} ${boss.shield_active ? "ring-2 ring-sky-300 animate-pulse" : ""}">
                <span>🛡️</span>
                <span>Блок</span>
              </button>
              <button onclick="window.RPG.sendCoopAction('potion')" ${!isYourTurn ? "disabled" : ""} class="py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 active:scale-95 text-white font-bold text-xs flex flex-col items-center justify-center gap-0.5 ${!isYourTurn ? "opacity-40 cursor-not-allowed" : "shadow-md shadow-emerald-600/20"}">
                <span>🧪</span>
                <span>Зелье</span>
              </button>
            </div>
            ${boss.shield_active ? `
              <div class="p-2.5 rounded-xl bg-gradient-to-r from-purple-950/90 via-slate-900 to-purple-950/90 border-2 border-purple-500/80 text-center animate-pulse space-y-0.5 shadow-lg shadow-purple-950/40">
                <div class="text-[11px] font-black text-purple-300 flex items-center justify-center gap-1.5">
                  <span>🔮</span>
                  <span>ОТРАЖАЮЩИЙ ЩИТ БОССА АКТИВЕН!</span>
                  <span>🔮</span>
                </div>
                <p class="text-[10px] text-purple-200">Любая атака отразит 50% урона обратно в героя! Используйте Блок 🛡️ или Зелье 🧪!</p>
              </div>
            ` : ""}
          </div>
        `;
              })()
            : r.status === "finished" && r.winner === "heroes"
            ? `
          <div class="theme-card p-4 rounded-3xl bg-gradient-to-b from-amber-950/40 via-slate-900 to-slate-950 border-2 border-amber-500/80 shadow-2xl space-y-3.5 text-center animate-scale-up">
            <div class="text-4xl animate-bounce">🏆</div>
            <div>
              <h3 class="text-base font-black text-amber-400">ВЕЛИКАЯ ПОБЕДА НАД РЕЙД-БОССОМ!</h3>
              <p class="text-xs text-slate-300 font-medium">${boss.name || "Босс"} пал под натиском героев!</p>
            </div>

            ${r.victory_rewards?.item ? `
              <div class="p-3 rounded-2xl bg-slate-800/90 border border-amber-500/50 space-y-1.5 text-center">
                <span class="text-3xl block">${r.victory_rewards.item.icon || "🎁"}</span>
                <h4 class="text-xs font-black text-amber-300">${r.victory_rewards.item.name}</h4>
                <div class="text-[10px] font-extrabold text-amber-400">${r.victory_rewards.item.bonus_desc || ""}</div>
                <div class="text-[9px] text-emerald-400 font-bold">✨ Легендарный дроп добавлен в инвентарь!</div>
              </div>
            ` : ""}

            <div class="flex items-center justify-around p-2 rounded-xl bg-slate-800/60 text-xs font-black text-amber-300">
              <span>+${r.victory_rewards?.gold_earned || boss.gold_reward || 1200} 🪙</span>
              <span>+${r.victory_rewards?.xp_earned || boss.xp_reward || 850} ✨</span>
              <span>+${r.victory_rewards?.gems_earned || 35} 💎</span>
            </div>

            <div class="flex items-center gap-2">
              <button onclick="window.RPG.fetchProfile(); RPG_STATE.activeTab = 'inventory'; renderRoot();" class="flex-1 py-3 rounded-2xl bg-gradient-to-r from-amber-500 to-yellow-400 text-slate-950 font-black text-xs shadow-lg shadow-amber-500/20 active:scale-95">
                ОТКРЫТЬ РЮКЗАК 🎒
              </button>
              <button onclick="window.RPG.leaveCoopRoom()" class="flex-1 py-3 rounded-2xl bg-slate-800 hover:bg-slate-700 text-white font-black text-xs active:scale-95">
                В ЛОББИ РЕЙДА ⚔️
              </button>
            </div>
          </div>
        ` : r.status === "finished" && r.winner === "boss" ? `
          <div class="theme-card p-4 rounded-3xl bg-slate-900 border-2 border-rose-600/70 shadow-2xl space-y-3 text-center animate-scale-up">
            <div class="text-4xl">💀</div>
            <h3 class="text-base font-black text-rose-500">РЕЙД ПРОВАЛЕН</h3>
            <p class="text-xs text-slate-300">Все герои пали в неравном бою. Улучшите экипировку и попробуйте снова!</p>
            <button onclick="window.RPG.leaveCoopRoom()" class="w-full py-3 rounded-2xl bg-rose-600 hover:bg-rose-500 text-white font-black text-xs shadow-lg active:scale-95">
              ВЕРНУТЬСЯ В ЛОББИ ⚔️
            </button>
          </div>
        ` : ""
        }

        <!-- Co-op Combat Feed / Log -->
        <div class="theme-card p-3 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 space-y-1.5">
          <div class="flex items-center justify-between text-xs font-black uppercase text-slate-500 dark:text-slate-400">
            <span>📜 Лог рейда (Босс бьет по кругу)</span>
            <span class="text-amber-500 text-[10px]">Круг целей</span>
          </div>

          <div class="p-2.5 rounded-xl bg-slate-100 dark:bg-slate-900/60 max-h-32 overflow-y-auto space-y-1 font-mono text-[10.5px]">
            ${
              !r.combat_log || r.combat_log.length === 0
                ? `<div class="text-slate-400 text-center py-2">Рейд начался! Атакуйте босса по очереди.</div>`
                : r.combat_log.map((entry) => {
                    const txt = typeof entry === "string" ? entry : (entry.text || "");
                    const isBoss = typeof entry === "object" && entry.type === "boss_attack";
                    const isVictory = typeof entry === "object" && entry.type === "victory";
                    const isDefeat = typeof entry === "object" && entry.type === "defeat";
                    const colorClass = isVictory ? "text-emerald-500 font-bold" : isDefeat ? "text-rose-500 font-bold" : isBoss ? "text-red-400" : "text-slate-700 dark:text-slate-300";
                    return `<div class="leading-tight ${colorClass}">${txt}</div>`;
                  }).join("")
            }
          </div>
        </div>
      </div>
    `;
  }

  // ===========================================================================
  // 4. PVP DUELS & LEADERBOARD HTML
  // ===========================================================================

  function renderPvPDuelsHTML() {
    if (RPG_STATE.pvpRoomId && RPG_STATE.pvpRoomData) {
      return renderActivePvPDuelHTML();
    }

    const p = RPG_STATE.profile || {};
    const classmates = RPG_STATE.classmates || [];

    return `
      <div class="space-y-3.5">
        <div class="p-3.5 rounded-2xl bg-gradient-to-r from-red-950 via-slate-900 to-amber-950 text-white border border-red-500/30 shadow-md">
          <div class="flex items-center justify-between">
            <div>
              <h3 class="text-sm font-black tracking-wide uppercase">1v1 Дуэли Одноклассников</h3>
              <p class="text-[11px] text-red-200/80">Сразитесь экипировкой с одноклассником! Рейтинг: <b>${p.pvp_rating || 1000}</b></p>
            </div>
            <span class="text-2xl">🥊</span>
          </div>
        </div>

        <div class="space-y-2">
          <h4 class="text-xs font-black uppercase text-slate-500">Одноклассники в сети:</h4>
          ${
            classmates.length === 0
              ? `<div class="p-4 text-center text-xs text-slate-400 theme-card rounded-2xl">Одноклассники не найдены. Поделитесь ботом!</div>`
              : classmates
                  .map(
                    (c) => `
              <div class="p-3 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 flex items-center justify-between shadow-sm">
                <div class="flex items-center gap-2.5">
                  <div class="w-8 h-8 rounded-xl bg-amber-500/10 text-amber-600 font-black text-xs flex items-center justify-center">
                    ${c.name ? c.name[0] : "👤"}
                  </div>
                  <div>
                    <span class="text-xs font-bold text-slate-800 dark:text-white block">${c.name}</span>
                    <span class="text-[10px] text-slate-400">Рейтинг: 1000</span>
                  </div>
                </div>
                <button onclick="window.RPG.challengeClassmate(${c.tg_id}, '${c.name}')" class="px-3 py-1.5 rounded-xl bg-red-600 hover:bg-red-500 active:scale-95 text-white font-bold text-xs shadow-sm">
                  Вызвать ⚔️
                </button>
              </div>
            `
                  )
                  .join("")}
        </div>
      </div>
    `;
  }

  function renderActivePvPDuelHTML() {
    const r = RPG_STATE.pvpRoomData;
    const host = r.players?.host || {};
    const opp = r.players?.opponent || {};
    const isYourTurn = r.is_your_turn;

    return `
      <div class="space-y-3.5">
        <div class="p-3 rounded-2xl bg-slate-900 text-white flex items-center justify-between border border-red-500/40">
          <h4 class="text-xs font-black">1v1 Дуэль</h4>
          <button onclick="window.RPG.leavePvPRoom()" class="px-2.5 py-1 rounded-lg bg-slate-800 text-xs font-bold text-slate-300">
            Сдаться
          </button>
        </div>

        <div class="grid grid-cols-2 gap-2">
          <!-- Player 1 -->
          <div class="p-3 rounded-2xl bg-white dark:bg-slate-800 border ${r.turn === "host" ? "border-amber-500 shadow-md" : "border-slate-200 dark:border-slate-700"} text-center space-y-1">
            <span class="text-3xl">${host.class_icon || "🗡️"}</span>
            <div class="text-xs font-black truncate">${host.name}</div>
            <div class="text-xs font-extrabold text-emerald-500">${host.hp} HP</div>
          </div>

          <!-- Player 2 -->
          <div class="p-3 rounded-2xl bg-white dark:bg-slate-800 border ${r.turn === "opponent" ? "border-amber-500 shadow-md" : "border-slate-200 dark:border-slate-700"} text-center space-y-1">
            <span class="text-3xl">${opp.class_icon || "🛡️"}</span>
            <div class="text-xs font-black truncate">${opp.name}</div>
            <div class="text-xs font-extrabold text-emerald-500">${opp.hp} HP</div>
          </div>
        </div>

        ${
          r.status === "playing"
            ? `
          <div class="theme-card p-3 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 space-y-2">
            <div class="text-xs font-black text-center ${isYourTurn ? "text-amber-500 animate-pulse" : "text-slate-400"}">
              ${isYourTurn ? "ВАШ ХОД!" : "Ход соперника..."}
            </div>
            <div class="grid grid-cols-3 gap-2">
              <button onclick="window.RPG.sendPvPAction('attack')" ${!isYourTurn ? "disabled" : ""} class="py-2.5 rounded-xl bg-red-600 active:scale-95 text-white font-bold text-xs flex flex-col items-center justify-center gap-0.5 ${!isYourTurn ? "opacity-40" : ""}">
                <span>⚔️</span>
                <span>Удар</span>
              </button>
              <button onclick="window.RPG.sendPvPAction('skill')" ${!isYourTurn ? "disabled" : ""} class="py-2.5 rounded-xl bg-purple-600 active:scale-95 text-white font-bold text-xs flex flex-col items-center justify-center gap-0.5 ${!isYourTurn ? "opacity-40" : ""}">
                <span>⚡</span>
                <span>Скилл</span>
              </button>
              <button onclick="window.RPG.sendPvPAction('defend')" ${!isYourTurn ? "disabled" : ""} class="py-2.5 rounded-xl bg-sky-600 active:scale-95 text-white font-bold text-xs flex flex-col items-center justify-center gap-0.5 ${!isYourTurn ? "opacity-40" : ""}">
                <span>🛡️</span>
                <span>Щит</span>
              </button>
            </div>
          </div>
        `
            : ""
        }
      </div>
    `;
  }

  function renderLeaderboardHTML() {
    const list = RPG_STATE.leaderboard || [];

    return `
      <div class="space-y-3.5">
        <div class="p-3.5 rounded-2xl bg-gradient-to-r from-amber-600 to-yellow-500 text-slate-950 shadow-md flex items-center justify-between">
          <div>
            <h3 class="text-sm font-black tracking-wide uppercase">Рейтинг natarGRP 11 «Б»</h3>
            <p class="text-[11px] font-bold opacity-90">Сильнейшие воины класса</p>
          </div>
          <span class="text-2xl">🏆</span>
        </div>

        <div class="space-y-1.5">
          ${
            list.length === 0
              ? `<div class="p-6 text-center text-xs text-slate-400 theme-card rounded-2xl">Рейтинг пока пуст. Будьте первым!</div>`
              : list
                  .map(
                    (p, idx) => `
              <div class="p-2.5 rounded-2xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 flex items-center justify-between shadow-sm">
                <div class="flex items-center gap-2.5">
                  <span class="w-6 text-center font-black text-xs ${idx === 0 ? "text-amber-500 text-sm" : idx === 1 ? "text-slate-400" : idx === 2 ? "text-amber-700" : "text-slate-400"}">
                    ${idx === 0 ? "🥇" : idx === 1 ? "🥈" : idx === 2 ? "🥉" : `#${idx + 1}`}
                  </span>
                  <div class="text-xl">${p.class_avatar || p.class_icon || "🛡️"}</div>
                  <div>
                    <span class="text-xs font-bold text-slate-800 dark:text-white block truncate">${p.name || "Воин"}</span>
                    <span class="text-[10px] text-slate-400">${p.class_name || ""} • Ур. ${p.level}</span>
                  </div>
                </div>
                <div class="text-right">
                  <span class="text-xs font-black text-amber-500 block">${p.pvp_rating || 1000} 🏆</span>
                  <span class="text-[9.5px] text-slate-400">${p.dungeon_floor || 1} этаж</span>
                </div>
              </div>
            `
                  )
                  .join("")}
        </div>
      </div>
    `;
  }

  // ===========================================================================
  // MODALS: ITEM INSPECT, FORGE & REWARD CHEST
  // ===========================================================================

  function renderItemModalHTML(item) {
    const rInfo = RARITY_MAP[item.rarity] || RARITY_MAP.common;
    const forgeTag = item.forge_level > 0 ? `+${item.forge_level}` : "";
    const slotName = item.slot_name || (item.slot === "weapon" ? "Оружие" : item.slot === "armor" ? "Броня" : item.slot === "relic" ? "Реликвия" : "Зелье");

    const p = RPG_STATE.profile || {};
    const eq = p.equipment || {};
    const isEquipped = Object.values(eq).some(it => it && it.uid === item.uid);

    let deltaHTML = "";
    if (!isEquipped && ["weapon", "armor", "relic"].includes(item.slot)) {
      const curr = eq[item.slot];
      if (!curr) {
        deltaHTML = `
          <div class="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-[10.5px] font-bold text-emerald-600 dark:text-emerald-400 text-center">
            ✨ Слот пуст: надев предмет, вы получите полный бонус!
          </div>
        `;
      } else {
        const deltas = [];
        if (item.slot === "weapon") {
          const itemMin = item.min_atk || item.base_min || 0;
          const itemMax = item.max_atk || item.base_max || 0;
          const currMin = curr.min_atk || curr.base_min || 0;
          const currMax = curr.max_atk || curr.base_max || 0;
          const dMin = itemMin - currMin;
          const dMax = itemMax - currMax;
          if (dMin !== 0 || dMax !== 0) {
            const sign = dMax >= 0 ? "+" : "";
            const col = dMax >= 0 ? "text-emerald-500" : "text-rose-500";
            deltas.push(`<span class="${col} font-bold">${dMax >= 0 ? "▲" : "▼"} ${sign}${dMin}..${sign}${dMax} Урон</span>`);
          }
        } else if (item.slot === "armor") {
          const itemDef = item.defense || item.base_def || 0;
          const itemHp = item.hp_bonus || item.base_hp || 0;
          const currDef = curr.defense || curr.base_def || 0;
          const currHp = curr.hp_bonus || curr.base_hp || 0;
          const dDef = itemDef - currDef;
          const dHp = itemHp - currHp;
          if (dDef !== 0) {
            const sign = dDef >= 0 ? "+" : "";
            const col = dDef >= 0 ? "text-emerald-500" : "text-rose-500";
            deltas.push(`<span class="${col} font-bold">${dDef >= 0 ? "▲" : "▼"} ${sign}${dDef} Броня</span>`);
          }
          if (dHp !== 0) {
            const sign = dHp >= 0 ? "+" : "";
            const col = dHp >= 0 ? "text-emerald-500" : "text-rose-500";
            deltas.push(`<span class="${col} font-bold">${dHp >= 0 ? "▲" : "▼"} ${sign}${dHp} HP</span>`);
          }
        }
        if (deltas.length > 0) {
          deltaHTML = `
            <div class="p-2 rounded-xl bg-slate-100 dark:bg-slate-800 text-[10.5px] text-center border border-slate-200 dark:border-slate-700">
              <span class="text-slate-400 block text-[9.5px]">Сравнение с надетым [${curr.name}]:</span>
              <div class="flex items-center justify-center gap-2 mt-0.5">${deltas.join(" | ")}</div>
            </div>
          `;
        }
      }
    }

    const isConsumable = item.slot === "consumable" || item.type === "potion";

    return `
      <div class="fixed inset-0 z-50 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4">
        <div class="w-full max-w-sm rounded-3xl bg-white dark:bg-slate-900 border-2 ${rInfo.color} p-5 space-y-4 shadow-2xl animate-scale-up">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-1.5">
              <span class="text-[10px] font-extrabold px-2 py-0.5 rounded-lg ${rInfo.badge}">${rInfo.name}</span>
              <span class="text-[10px] font-black px-2 py-0.5 rounded-lg bg-black/20 text-slate-600 dark:text-slate-300">[${slotName}]</span>
              ${isEquipped ? `<span class="text-[9.5px] font-black px-1.5 py-0.5 rounded-md bg-emerald-500 text-white">НАДЕТО</span>` : ""}
            </div>
            <button onclick="window.RPG.closeItemModal()" class="w-7 h-7 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-400 hover:text-white flex items-center justify-center text-xs">
              ✕
            </button>
          </div>

          <div class="text-center space-y-2">
            <div class="relative inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-b from-slate-800 to-slate-900 border-2 border-amber-500/40 shadow-lg shadow-amber-500/10">
              <span class="text-4xl leading-none">${item.icon || "📦"}</span>
              ${forgeTag ? `<span class="absolute -top-1 -right-2 px-1.5 rounded-md bg-amber-500 text-slate-950 font-black text-xs shadow-sm">${forgeTag}</span>` : ""}
            </div>
            <h3 class="text-sm font-black text-slate-900 dark:text-white">${item.name}</h3>
            <p class="text-xs font-bold text-amber-500">${item.bonus_desc || ""}</p>
            ${(() => {
              const matchedDef = Object.values(ACTIVE_ITEM_DEFINITIONS).find(d => d.match(item));
              if (!matchedDef) return "";
              return `
                <div class="p-2 rounded-xl bg-gradient-to-r from-emerald-500/20 via-teal-500/20 to-emerald-500/20 border border-emerald-500/40 text-[10.5px] font-bold text-emerald-400 text-center space-y-0.5">
                  <div class="flex items-center justify-center gap-1 text-emerald-300 font-black uppercase text-[10px]">
                    <span>⚡</span> <span>АКТИВНЫЙ ПРЕДМЕТ</span>
                  </div>
                  <span>${matchedDef.description}</span>
                  <div class="text-[9px] text-amber-300 font-extrabold mt-1">
                    ${isEquipped ? '✅ Экипирован: кнопка активна на боевом экране [Клавиша: R / 1 или тап]' : '💡 Наденьте в слот, чтобы применять способность кнопкой в бою!'}
                  </div>
                </div>
              `;
            })()}
          </div>

          ${deltaHTML}

          <div class="space-y-2 pt-2 border-t border-slate-100 dark:border-slate-800">
            ${
              isEquipped
                ? `
              <button onclick="window.RPG.openSlotFilterModal('${Object.keys(eq).find(k => eq[k]?.uid === item.uid) || item.slot || 'slot_1'}')" class="w-full py-2.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 active:scale-95 text-white font-black text-xs shadow-md flex items-center justify-center gap-1.5">
                <span>🔄</span>
                <span>Сменить на другой предмет (${slotName})</span>
              </button>
              <button onclick="window.RPG.unequipItem('${item.uid}')" class="w-full py-2.5 rounded-xl bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 active:scale-95 text-white font-black text-xs shadow-md flex items-center justify-center gap-1.5">
                <span>🎒</span>
                <span>Снять в рюкзак</span>
              </button>
            `
                : !isConsumable
                  ? `
              <button onclick="window.RPG.equipItem('${item.uid}')" class="w-full py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 active:scale-95 text-white font-black text-xs shadow-md flex items-center justify-center gap-1.5">
                <span>⚔️</span>
                <span>${eq[item.slot || item.type] ? `Сменить [${eq[item.slot || item.type].name}] ➔ [${item.name}]` : "Надеть в слот снаряжения"}</span>
              </button>
            `
                  : `
              <button onclick="window.RPG.useConsumable('${item.uid}')" class="w-full py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 active:scale-95 text-white font-black text-xs shadow-md flex items-center justify-center gap-1.5">
                <span>🧪</span>
                <span>Использовать ${item.count ? `(${item.count} шт.)` : ""}</span>
              </button>
            `
            }

            ${
              !isConsumable
                ? `
              <button onclick="window.RPG.openForge('${item.uid}')" class="w-full py-2.5 rounded-xl bg-gradient-to-r from-amber-600 to-yellow-500 hover:from-amber-500 hover:to-yellow-400 active:scale-95 text-slate-950 font-black text-xs shadow-md">
                Заточить в Кузнице (+1..+99) ⚒️
              </button>
            `
                : ""
            }

            ${
              isEquipped
                ? `
              <button onclick="window.RPG.sellItem('${item.uid}')" class="w-full py-2.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-500 active:scale-95 font-bold text-xs flex items-center justify-center gap-1.5 transition-all">
                <span>💰</span>
                <span>Снять и продать (+${getItemSellPrice(item)} 🪙)</span>
              </button>
            `
                : `
              <button onclick="window.RPG.toggleItemSelection('${item.uid}'); window.RPG.closeItemModal();" class="w-full py-2.5 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-500 font-black text-xs flex items-center justify-center gap-1.5">
                <span>☑️</span>
                <span>Выбрать для продажи (+${getItemSellPrice(item)} 🪙)</span>
              </button>
              <button onclick="window.RPG.sellItem('${item.uid}')" class="w-full py-2 rounded-xl bg-slate-100 dark:bg-slate-800 text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/30 font-bold text-xs">
                Продать этот предмет (+${getItemSellPrice(item)} 🪙)
              </button>
            `
            }
          </div>
        </div>
      </div>
    `;
  }

  function renderForgeModalHTML(item) {
    const p = RPG_STATE.profile || {};
    const userGold = p.gold || 0;
    const userGems = p.gems || 0;
    const currentUpg = item.upgrade || item.forge_level || 0;
    const targetUpg = currentUpg + 1;
    const isMax = currentUpg >= 100;

    let rate = 1.0;
    let goldCost = targetUpg * 350;
    let gemsCost = 0;

    if (targetUpg <= 3) {
      rate = 1.0;
      goldCost = targetUpg * 350;
      gemsCost = 0;
    } else if (targetUpg <= 6) {
      rate = 0.98;
      goldCost = targetUpg * 800;
      gemsCost = 2;
    } else if (targetUpg <= 9) {
      rate = 0.90;
      goldCost = targetUpg * 2000;
      gemsCost = 6;
    } else if (targetUpg <= 12) {
      rate = 0.75;
      goldCost = targetUpg * 5500;
      gemsCost = 15;
    } else if (targetUpg <= 15) {
      rate = 0.60;
      goldCost = targetUpg * 15000;
      gemsCost = 45;
    } else {
      rate = 0.50;
      goldCost = targetUpg * 25000;
      gemsCost = 45 + (targetUpg - 15) * 2;
    }

    const successPct = isMax ? 0 : Math.round(rate * 100);
    const canAffordGold = userGold >= goldCost;
    const canAffordGems = userGems >= gemsCost;
    const canAfford = canAffordGold && canAffordGems && !isMax;

    let chanceColor = "text-emerald-400";
    if (successPct <= 25) chanceColor = "text-rose-400";
    else if (successPct <= 45) chanceColor = "text-orange-400";
    else if (successPct <= 65) chanceColor = "text-yellow-400";

    // Collect all forgeable equipment & inventory items
    const eq = p.equipment || {};
    const inv = p.inventory || [];
    const allForgeable = [
      ...(eq.slot_1 ? [{ ...eq.slot_1, locLabel: "Слот 1" }] : []),
      ...(eq.slot_2 ? [{ ...eq.slot_2, locLabel: "Слот 2" }] : []),
      ...(eq.slot_3 ? [{ ...eq.slot_3, locLabel: "Слот 3" }] : []),
      ...(eq.slot_4 ? [{ ...eq.slot_4, locLabel: "Слот 4" }] : []),
      ...(eq.slot_5 ? [{ ...eq.slot_5, locLabel: "Слот 5" }] : []),
      ...(eq.slot_6 ? [{ ...eq.slot_6, locLabel: "Слот 6" }] : []),
      ...inv.filter((i) => {
        const itype = (i.type || "").toLowerCase();
        const islot = (i.slot || "").toLowerCase();
        return itype !== "consumable" && islot !== "consumable" && itype !== "potion";
      }).map((i) => ({ ...i, locLabel: "Рюкзак" }))
    ];

    // Compute preview stat deltas (+15% per level)
    let previewStats = "";
    const itemT = (item.type || item.slot || "").toLowerCase();
    if (itemT === "weapon") {
      const curMin = item.min_atk || item.base_min || 16;
      const curMax = item.max_atk || item.base_max || 24;
      const nextMin = Math.floor(curMin * 1.15) + 2;
      const nextMax = Math.floor(curMax * 1.15) + 4;
      previewStats = `
        <div class="p-2 rounded-xl bg-slate-800/80 border border-amber-500/30 text-[11px] font-bold text-amber-300">
          ⚔️ Урон: ${curMin}..${curMax} ➔ <span class="text-emerald-400 font-extrabold">${nextMin}..${nextMax}</span> (+15%)
        </div>
      `;
    } else if (itemT === "armor") {
      const curDef = item.defense || item.base_def || 10;
      const curHp = item.hp_bonus || item.base_hp || 40;
      const nextDef = Math.floor(curDef * 1.15) + 2;
      const nextHp = Math.floor(curHp * 1.15) + 20;
      previewStats = `
        <div class="p-2 rounded-xl bg-slate-800/80 border border-amber-500/30 text-[11px] font-bold text-amber-300">
          🛡️ Броня: ${curDef} ➔ <span class="text-emerald-400 font-extrabold">${nextDef}</span> | ❤️ HP: +${curHp} ➔ <span class="text-emerald-400 font-extrabold">+${nextHp}</span>
        </div>
      `;
    } else {
      previewStats = `
        <div class="p-2 rounded-xl bg-slate-800/80 border border-amber-500/30 text-[11px] font-bold text-amber-300">
          ✨ Все параметры реликвии увеличатся на <span class="text-emerald-400 font-extrabold">+15%</span>!
        </div>
      `;
    }

    return `
      <div class="fixed inset-0 z-50 bg-black/80 backdrop-blur-xs flex items-center justify-center p-4">
        <div class="w-full max-w-sm rounded-3xl bg-slate-900 border-2 border-amber-500/60 p-5 space-y-3.5 shadow-2xl text-white animate-scale-up">
          <div class="flex items-center justify-between">
            <h3 class="text-xs font-black uppercase text-amber-400 flex items-center gap-1.5">
              <span>⚒️</span> Кузница Заточки (+0..+100)
            </h3>
            <button onclick="window.RPG.closeForgeModal()" class="w-7 h-7 rounded-full bg-slate-800 text-slate-400 hover:text-white flex items-center justify-center text-xs">
              ✕
            </button>
          </div>

          ${
            RPG_STATE.forgeSuccessAnimation
              ? `<div class="p-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 text-white font-black text-xs text-center shadow-lg animate-bounce flex items-center justify-center gap-1.5">
                  <span>🔥</span> ЗАТОЧКА УСПЕШНА! Уровень +${currentUpg}! <span>✨</span>
                </div>`
              : (RPG_STATE.forgeFailMessage
                  ? `<div class="p-2.5 rounded-xl bg-gradient-to-r from-rose-700 to-red-600 text-white font-black text-xs text-center shadow-lg flex items-center justify-center gap-1.5">
                      <span>💥</span> ${RPG_STATE.forgeFailMessage}
                    </div>`
                  : "")
          }

          <div class="text-center space-y-2 py-1">
            <div class="text-4xl ${RPG_STATE.forgeSuccessAnimation ? "animate-bounce" : ""}">${item.icon || "⚔️"}</div>
            <h4 class="text-sm font-black">${item.name} <span class="text-amber-400 font-extrabold">+${currentUpg}</span></h4>
            ${
              item.bonus_desc
                ? `
              <div class="p-2 rounded-xl bg-slate-800/60 border border-slate-700 text-xs font-bold text-slate-300">
                ${item.bonus_desc}
              </div>
            `
                : ""
            }
            ${previewStats}
            <div class="space-y-0.5 pt-1">
              <span class="text-xs ${chanceColor} block font-black">
                ${isMax ? "МАКСИМАЛЬНЫЙ УРОВЕНЬ (+100)" : `Шанс успеха: ${successPct}%`}
              </span>
              <span class="text-[9.5px] text-emerald-400 block font-medium">
                🛡️ Безопасность: при неудаче предмет НЕ сломается и не сбросит уровень!
              </span>
            </div>
          </div>

          <!-- Quick Item Selector Chips -->
          ${
            allForgeable.length > 1
              ? `
            <div class="space-y-1">
              <span class="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Другие предметы:</span>
              <div class="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none">
                ${allForgeable
                  .map(
                    (it) => `
                  <button onclick="window.RPG.openForge('${it.uid}')" class="px-2 py-1 rounded-lg text-[10.5px] font-bold whitespace-nowrap flex items-center gap-1 border transition-all ${
                      it.uid === item.uid
                        ? "bg-amber-500/20 border-amber-400 text-amber-300"
                        : "bg-slate-800 border-slate-700 text-slate-400 hover:text-white"
                    }">
                    <span>${it.icon || "🗡️"}</span>
                    <span>${it.name.split(" ")[0]}</span>
                    <span class="text-amber-400 text-[9px] font-black">${(it.upgrade || it.forge_level) ? `+${it.upgrade || it.forge_level}` : ""}</span>
                  </button>
                `
                  )
                  .join("")}
              </div>
            </div>
          `
              : ""
          }

          <div class="p-2.5 rounded-xl bg-slate-800/50 border border-slate-700 flex items-center justify-between text-xs font-bold">
            <span class="text-slate-400">Стоимость заточки:</span>
            <div class="flex items-center gap-2">
              <span class="${canAffordGold ? "text-amber-400 font-black" : "text-red-400 font-black"}">🪙 ${goldCost.toLocaleString()}</span>
              ${gemsCost > 0 ? `<span class="${canAffordGems ? "text-cyan-400 font-black" : "text-red-400 font-black"}">💎 ${gemsCost}</span>` : ""}
            </div>
          </div>

          <div class="space-y-2">
            <button onclick="window.RPG.forgeCurrentItem()" ${!canAfford ? "disabled" : ""} class="w-full py-3 rounded-xl bg-gradient-to-r from-amber-500 to-yellow-400 hover:from-amber-400 active:scale-95 text-slate-950 font-black text-xs shadow-md ${
              !canAfford ? "opacity-40 cursor-not-allowed" : ""
            }">
              ${isMax ? "Максимальный уровень заточки (+100)" : (canAfford ? `Заточить до +${targetUpg} (${successPct}% шанс) 🔥` : (!canAffordGold ? `Не хватает золота (нужно 🪙 ${goldCost})` : `Не хватает кристаллов (нужно 💎 ${gemsCost})`))}
            </button>
          </div>
        </div>
      </div>
    `;
  }


  function renderChestModalHTML(chest) {
    const item = chest.item || {};
    const rInfo = RARITY_MAP[item.rarity] || RARITY_MAP.common;
    const isOpened = chest.opened;

    return `
      <div class="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
        <div class="w-full max-w-sm rounded-3xl bg-slate-900 border-2 border-amber-500 p-6 space-y-4 shadow-2xl text-white text-center animate-scale-up">
          <div class="text-5xl ${!isOpened ? "animate-bounce" : "scale-110 transition-transform"}">
            ${!isOpened ? (chest.chest_icon || "🎁") : "✨"}
          </div>

          <h3 class="text-base font-black text-amber-400">${chest.chest_name || "Наградной Сундук"}</h3>

          ${
            !isOpened
              ? `
            <p class="text-xs text-slate-300 font-medium">Поздравляем с зачисткой этажа! Внутри гарантированный функциональный артефакт и сокровища.</p>
            <button onclick="window.RPG.claimChestReward()" class="w-full py-3.5 rounded-2xl bg-gradient-to-r from-amber-500 via-yellow-400 to-amber-500 active:scale-95 text-slate-950 font-black text-sm shadow-xl shadow-amber-500/30">
              ОТКРЫТЬ СУНДУК 🎁
            </button>
          `
              : `
            <div class="p-4 rounded-2xl border-2 ${rInfo.color} space-y-2 bg-slate-800/80">
              <span class="text-4xl block">${item.icon || "⚔️"}</span>
              <h4 class="text-sm font-black">${item.name}</h4>
              <div class="flex items-center justify-center gap-1.5">
                <span class="text-[10px] font-extrabold px-2 py-0.5 rounded-md ${rInfo.badge}">${rInfo.name}</span>
                <span class="text-[10px] font-black px-2 py-0.5 rounded-md bg-black/30">[${item.slot_name || "Снаряжение"}]</span>
              </div>
              <p class="text-xs text-amber-400 font-bold">${item.bonus_desc || ""}</p>
            </div>

            <div class="flex items-center justify-center gap-4 text-xs font-extrabold text-amber-300">
              <span>+${chest.gold_reward || 200} 🪙</span>
              <span>+${chest.gems_reward || 10} 💎</span>
            </div>

            <button onclick="window.RPG.closeChestModal()" class="w-full py-3 rounded-2xl bg-emerald-600 hover:bg-emerald-500 active:scale-95 text-white font-black text-xs shadow-md">
              Забрать награду в инвентарь 🎒
            </button>
          `
          }
        </div>
      </div>
    `;
  }

  function renderShopModalHTML() {
    const p = RPG_STATE.profile || {};
    const catalog = RPG_STATE.shopCatalog || [];
    const filter = RPG_STATE.shopFilter || "all";
    const userGold = p.gold || 0;
    const userGems = p.gems || 0;

    const filterTabs = [
      { id: "all", label: "Все товары" },
      { id: "mage", label: "Магия 🔮" },
      { id: "agi", label: "Ловкость 🏹" },
      { id: "str", label: "Сила 💪" },
      { id: "weapon", label: "Оружие ⚔️" },
      { id: "armor", label: "Броня 🛡️" },
      { id: "relic", label: "Реликвии 💍" },
      { id: "potion", label: "Зелья 🧪" }
    ];

    const filteredItems = catalog.filter((it) => {
      if (filter === "all") return true;
      if (filter === "mage") {
        const desc = ((it.bonus_desc || "") + " " + (it.name || "")).toLowerCase();
        return (it.int && it.int > 0) || (it.spell_amp && it.spell_amp > 0) || (it.ult_boost && it.ult_boost > 0) || (it.ult_cd && it.ult_cd > 0) || (it.cooldown_reduct && it.cooldown_reduct > 0) || desc.includes("интеллект") || desc.includes("маг") || desc.includes("заклинаний") || desc.includes("мана") || desc.includes("ульт");
      }
      if (filter === "agi") {
        const desc = ((it.bonus_desc || "") + " " + (it.name || "")).toLowerCase();
        return (it.agi && it.agi > 0) || (it.atk_speed && it.atk_speed > 0) || (it.dodge && it.dodge > 0) || desc.includes("ловкост") || desc.includes("скор. атаки") || desc.includes("уворот");
      }
      if (filter === "str") {
        const desc = ((it.bonus_desc || "") + " " + (it.name || "")).toLowerCase();
        return (it.str && it.str > 0) || (it.hp && it.hp > 0) || (it.hp_regen && it.hp_regen > 0) || desc.includes("сила") || desc.includes("жизни") || desc.includes("регенерац");
      }
      if (filter === "weapon") return it.slot === "weapon" || it.type === "weapon";
      if (filter === "armor") return it.slot === "armor" || it.type === "armor";
      if (filter === "relic") return it.slot === "relic" || it.type === "relic";
      if (filter === "potion") return it.slot === "consumable" || it.type === "potion";
      return true;
    });

    return `
      <div class="fixed inset-0 z-50 bg-black/75 backdrop-blur-xs flex items-center justify-center p-3 sm:p-4">
        <div class="w-full max-w-lg max-h-[88vh] flex flex-col rounded-3xl bg-slate-900 border-2 border-emerald-500/60 p-4 sm:p-5 space-y-3 shadow-2xl text-white animate-scale-up">
          <!-- Header -->
          <div class="flex items-center justify-between border-b border-slate-800 pb-2">
            <div class="flex items-center gap-2">
              <span class="text-2xl">🏪</span>
              <div>
                <h3 class="text-sm font-black uppercase text-emerald-400">Тайная Лавка Снаряжения</h3>
                <div class="flex items-center gap-2 text-[11px] font-bold text-amber-300">
                  <span>🪙 ${(userGold).toLocaleString()}</span>
                  <span>💎 ${userGems}</span>
                </div>
              </div>
            </div>
            <button onclick="window.RPG.closeShopModal()" class="w-7 h-7 rounded-full bg-slate-800 text-slate-400 hover:text-white flex items-center justify-center text-xs">
              ✕
            </button>
          </div>

          <!-- Category Filters -->
          <div class="flex items-center gap-1 overflow-x-auto pb-1 text-[10.5px] font-bold">
            ${filterTabs
              .map(
                (t) => `
              <button onclick="window.RPG.setShopFilter('${t.id}')" class="px-2.5 py-1 rounded-xl whitespace-nowrap transition-all ${
                  filter === t.id
                    ? "bg-emerald-500 text-slate-950 font-black shadow-sm"
                    : "bg-slate-800 text-slate-400 hover:text-white"
                }">
                ${t.label}
              </button>
            `
              )
              .join("")}
          </div>

          <!-- Catalog List -->
          <div class="flex-1 overflow-y-auto space-y-2 pr-1 custom-scrollbar">
            ${
              RPG_STATE.shopLoading
                ? `
                <div class="py-14 text-center text-slate-400 text-xs flex flex-col items-center justify-center gap-3">
                  <div class="w-8 h-8 border-3 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
                  <span class="font-bold text-slate-300">Загрузка товаров лавки... 🏪</span>
                </div>
              `
                : filteredItems.length === 0
                ? `
                <div class="py-10 text-center text-slate-400 text-xs space-y-3">
                  <span class="text-3xl block">📦</span>
                  <p>В этой категории товары отсутствуют или обновляются.</p>
                  <button onclick="window.RPG.reloadShopCatalog()" class="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-amber-400 font-black text-xs border border-slate-700">
                    🔄 Обновить ассортимент
                  </button>
                </div>
              `
                : filteredItems
                    .map((item) => {
                      const rInfo = RARITY_MAP[item.rarity] || RARITY_MAP.common;
                      const costGold = item.price_gold || 0;
                      const costGems = item.price_gems || 0;
                      const canAfford = userGold >= costGold && userGems >= costGems;
                      const isBuying = RPG_STATE.buyingItemId === item.id;
                      const slotBadge = item.slot_name || (item.slot === "weapon" ? "Оружие" : item.slot === "armor" ? "Броня" : item.slot === "relic" ? "Реликвия" : "Зелье");

                      return `
                        <div class="p-3 rounded-2xl bg-slate-800/70 border border-slate-700/80 flex items-center justify-between gap-3 hover:border-emerald-500/40 transition-colors">
                          <div class="flex items-center gap-3 min-w-0">
                            <div class="w-10 h-10 rounded-xl bg-slate-900 border border-slate-700 flex items-center justify-center text-2xl shrink-0">
                              ${item.icon || "📦"}
                            </div>
                            <div class="min-w-0">
                              <div class="flex items-center gap-1.5 flex-wrap">
                                <span class="text-xs font-black truncate">${item.name}</span>
                                <span class="text-[9px] font-extrabold px-1.5 py-0.2 rounded-md ${rInfo.badge}">${rInfo.name}</span>
                                <span class="text-[9px] font-bold px-1 rounded bg-black/30 text-slate-300">[${slotBadge}]</span>
                              </div>
                              <p class="text-[10px] text-amber-300/90 font-medium line-clamp-2 leading-tight mt-0.5">${item.bonus_desc || ""}</p>
                            </div>
                          </div>

                          <div class="shrink-0 text-right space-y-1">
                            <div class="text-[11px] font-extrabold flex items-center justify-end gap-1.5">
                              ${costGold > 0 ? `<span class="${userGold >= costGold ? 'text-amber-400' : 'text-rose-400'}">${costGold} 🪙</span>` : ""}
                              ${costGems > 0 ? `<span class="${userGems >= costGems ? 'text-cyan-400' : 'text-rose-400'}">${costGems} 💎</span>` : ""}
                            </div>
                            <button onclick="window.RPG.buyShopItem('${item.id}')" ${!canAfford || isBuying ? "disabled" : ""} class="px-3 py-1.5 rounded-xl text-xs font-black transition-all active:scale-95 ${
                              canAfford && !isBuying
                                ? "bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 text-slate-950 shadow-md shadow-emerald-500/20"
                                : "bg-slate-700 text-slate-400 opacity-50 cursor-not-allowed"
                            }">
                              ${isBuying ? "Покупка..." : "Купить"}
                            </button>
                          </div>
                        </div>
                      `;
                    })
                    .join("")
            }
          </div>
        </div>
      </div>
    `;
  }

  function renderSlotFilterModalHTML(slotKey) {
    const p = RPG_STATE.profile || {};
    const inv = p.inventory || [];
    const eq = p.equipment || {};
    const sKey = (slotKey || "").toLowerCase();
    const currEquipped = eq[sKey] || eq[slotKey];
    const slotRu = sKey.startsWith("slot_") ? "Слот " + sKey.split("_")[1] : sKey;
    const matchingItems = inv.filter((it) => {
      const islot = (it.slot || it.type || "").toLowerCase();
      return islot === "weapon" || islot === "armor" || islot === "relic" || islot.startsWith("slot_");
    });

    return `
      <div class="fixed inset-0 z-50 bg-black/75 backdrop-blur-xs flex items-center justify-center p-4">
        <div class="w-full max-w-sm max-h-[85vh] flex flex-col rounded-3xl bg-white dark:bg-slate-900 border-2 border-amber-500/60 p-5 space-y-3 shadow-2xl animate-scale-up text-slate-900 dark:text-white">
          <div class="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
            <h3 class="text-xs font-black uppercase tracking-wider text-amber-500 flex items-center gap-1.5">
              <span>🛡️</span> Выбор снаряжения: ${slotRu}
            </h3>
            <button onclick="window.RPG.closeSlotFilterModal()" class="w-7 h-7 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-400 hover:text-white flex items-center justify-center text-xs">
              ✕
            </button>
          </div>

          ${
            currEquipped
              ? `
            <!-- Currently Equipped Item Banner -->
            <div class="p-3 rounded-2xl bg-amber-500/10 border border-amber-500/40 space-y-1.5 shrink-0">
              <div class="flex items-center justify-between text-[10px] font-black text-amber-500 dark:text-amber-400 uppercase">
                <span>🛡️ Сейчас надето:</span>
                <button onclick="window.RPG.unequipItem('${slotKey}')" class="text-rose-500 hover:text-rose-400 font-bold underline text-[9.5px]">
                  Снять в рюкзак
                </button>
              </div>
              <div class="flex items-center gap-2.5">
                <span class="text-2xl">${currEquipped.icon || "🗡️"}</span>
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-1">
                    <span class="text-xs font-black truncate">${currEquipped.name}</span>
                    ${(currEquipped.forge_level || currEquipped.upgrade) ? `<span class="px-1 rounded bg-amber-500 text-slate-950 font-black text-[8px]">+${currEquipped.forge_level || currEquipped.upgrade}</span>` : ""}
                  </div>
                  <span class="text-[10px] text-slate-500 dark:text-slate-400 truncate block">${currEquipped.bonus_desc || ""}</span>
                </div>
              </div>
            </div>
          `
              : ""
          }

          <div class="flex-1 overflow-y-auto space-y-2 pr-1 custom-scrollbar">
            ${
              matchingItems.length === 0
                ? `
              <div class="py-6 text-center space-y-3">
                <span class="text-3xl block">🎒</span>
                <p class="text-xs text-slate-400">В вашем рюкзаке пока нет других предметов типа <b>${slotRu}</b>.</p>
                <button onclick="window.RPG.closeSlotFilterModal(); window.RPG.openShopModal(); window.RPG.setShopFilter('${slotKey}');" class="px-4 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 active:scale-95 text-white font-black text-xs shadow-md">
                  Купить ${slotRu} в Лавке Снаряжения 🏪
                </button>
              </div>
            `
                : matchingItems
                    .map((item) => {
                      const rInfo = RARITY_MAP[item.rarity] || RARITY_MAP.common;
                      const forgeTag = (item.forge_level || item.upgrade) > 0 ? `+${item.forge_level || item.upgrade}` : "";
                      return `
                        <div class="p-3 rounded-2xl border-2 ${rInfo.color} flex items-center justify-between gap-2 bg-slate-50 dark:bg-slate-800/60">
                          <div class="flex items-center gap-2.5 min-w-0">
                            <span class="text-2xl shrink-0">${item.icon || "📦"}</span>
                            <div class="min-w-0">
                              <div class="flex items-center gap-1">
                                <span class="text-xs font-black truncate">${item.name}</span>
                                ${forgeTag ? `<span class="px-1 rounded bg-amber-500 text-slate-950 font-black text-[8px]">${forgeTag}</span>` : ""}
                              </div>
                              <span class="text-[10px] text-slate-500 dark:text-slate-400 truncate block">${item.bonus_desc || ""}</span>
                            </div>
                          </div>
                          <button onclick="window.RPG.equipItem('${item.uid}', '${slotKey}')" class="px-3.5 py-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-black text-xs shrink-0 shadow-sm flex items-center gap-1">
                            <span>⚔️</span>
                            <span>${currEquipped ? "Сменить" : "Надеть"}</span>
                          </button>
                        </div>
                      `;
                    })
                    .join("")
            }
          </div>
        </div>
      </div>
    `;
  }

  function renderHeroSelectHTML() {
    const heroes = RPG_STATE.heroesList || [];

    return `
      <div class="space-y-4 py-2">
        <div class="text-center space-y-1">
          <h2 class="text-base font-black text-slate-900 dark:text-white tracking-tight flex items-center justify-center gap-1.5">
            <span>⚔️</span> Выберите героя natarGRP
          </h2>
          <p class="text-xs text-slate-400">У каждого героя уникальный основной атрибут (+1 Урон за очко) и коронный скилл!</p>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          ${heroes
            .map(
              (h) => `
            <div class="p-3.5 rounded-2xl bg-white dark:bg-slate-800 border-2 border-slate-200 dark:border-slate-700 hover:border-amber-500 transition-all space-y-2.5 shadow-sm">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2.5">
                  <span class="text-3xl">${h.avatar || h.icon}</span>
                  <div>
                    <h3 class="text-xs font-black text-slate-900 dark:text-white">${h.name}</h3>
                    <span class="text-[10px] font-extrabold px-1.5 py-0.2 rounded-md ${
                      h.attr === "Сила" ? "bg-red-500/10 text-red-600" : h.attr === "Ловкость" ? "bg-emerald-500/10 text-emerald-600" : "bg-sky-500/10 text-sky-600"
                    }">
                      Основной: ${h.attr}
                    </span>
                  </div>
                </div>
              </div>

              <p class="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed font-normal">${h.desc}</p>

              <div class="p-2 rounded-xl bg-slate-50 dark:bg-slate-900/60 text-[10.5px] font-bold text-amber-600 dark:text-amber-400">
                ⚡ ${h.skill?.name}: ${h.skill?.desc}
              </div>

              <button onclick="window.RPG.selectHero('${h.id}')" class="w-full py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-yellow-400 hover:from-amber-400 active:scale-95 text-slate-950 font-black text-xs shadow-md">
                Выбрать героя ⚔️
              </button>
            </div>
          `
            )
            .join("")}
        </div>
      </div>
    `;
  }

  // ===========================================================================
  // PUBLIC API EXPOSURE
  // ===========================================================================


// ============================================================
// 10_talents_tree.js — Интерактивное Визуальное Древо Талантов (Skill Tree)
// 3 ветки (ATK, TANK, UTIL) × 5 тиров с SVG связями и плашкой прокачки
// ============================================================

window._selectedTalentId = window._selectedTalentId || null;
window._talentTreeFilter = window._talentTreeFilter || "all";

const TREE_BRANCH_THEMES = {
  atk: {
    label: "🗡️ Атака",
    colX: 45,
    activeStroke: "#ef4444",
    glowColor: "rgba(239, 68, 68, 0.6)",
    nodeBought: "bg-red-950 border-red-500 shadow-red-500/50 shadow-md",
    nodeAvail: "bg-slate-900 border-red-500/80 shadow-red-500/30 animate-pulse",
    textColor: "text-red-400"
  },
  tank: {
    label: "🛡️ Выживание",
    colX: 135,
    activeStroke: "#3b82f6",
    glowColor: "rgba(59, 130, 246, 0.6)",
    nodeBought: "bg-blue-950 border-blue-500 shadow-blue-500/50 shadow-md",
    nodeAvail: "bg-slate-900 border-blue-500/80 shadow-blue-500/30 animate-pulse",
    textColor: "text-blue-400"
  },
  util: {
    label: "✨ Утилита",
    colX: 225,
    activeStroke: "#a855f7",
    glowColor: "rgba(168, 85, 247, 0.6)",
    nodeBought: "bg-purple-950 border-purple-500 shadow-purple-500/50 shadow-md",
    nodeAvail: "bg-slate-900 border-purple-500/80 shadow-purple-500/30 animate-pulse",
    textColor: "text-purple-400"
  },
  flask: {
    label: "🧪 Фляга",
    colX: 315,
    activeStroke: "#10b981",
    glowColor: "rgba(16, 185, 129, 0.6)",
    nodeBought: "bg-emerald-950 border-emerald-500 shadow-emerald-500/50 shadow-md",
    nodeAvail: "bg-slate-900 border-emerald-500/80 shadow-emerald-500/30 animate-pulse",
    textColor: "text-emerald-400"
  }
};

const TIER_Y = {
  1: 385,
  2: 305,
  3: 225,
  4: 145,
  5: 60
};

const ROOT_POS = { x: 180, y: 465 };

function renderVisualTalentTree(p, treeData) {
  if (!treeData) {
    return `
      <div class="text-center text-slate-500 text-sm py-12 bg-slate-900/60 rounded-3xl border border-slate-800">
        <div class="text-3xl mb-2 animate-bounce">🌳</div>
        Связывание с астральным древом...
        <br><button onclick="loadTalentTreeUI()" class="mt-4 px-4 py-2 bg-gradient-to-r from-amber-500 to-yellow-500 rounded-xl text-slate-950 font-black text-xs shadow-lg shadow-amber-500/20 active:scale-95">Загрузить Древо</button>
      </div>`;
  }

  const branches = treeData.branches || {};
  const charLvl = p.level || 1;
  const effectiveProgress = charLvl;
  const talentPts = (treeData && treeData.talent_points !== undefined) ? treeData.talent_points : (p.talent_points || 0);
  const filter = window._talentTreeFilter;

  // Flatten nodes for fast lookup
  const nodeMap = {};
  for (const bKey in branches) {
    for (const n of branches[bKey]) {
      nodeMap[n.id] = { ...n, branchKey: bKey };
    }
  }

  // Selected Node (default to first available or first tier if none chosen)
  let selectedNode = nodeMap[window._selectedTalentId];
  if (!selectedNode) {
    const allNodes = Object.values(nodeMap);
    selectedNode = allNodes.find(n => n.can_buy && !n.is_bought) || allNodes.find(n => n.is_bought) || allNodes[0];
  }

  let html = `
    <div class="relative bg-slate-950/90 rounded-3xl border border-slate-800/80 shadow-2xl overflow-hidden p-3 select-none">
      <!-- Background Constellation Ambient Glow -->
      <div class="absolute inset-0 pointer-events-none bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-900/20 via-slate-950/40 to-slate-950/90"></div>

      <!-- Tree Header / Filter Tabs -->
      <div class="relative z-10 flex items-center justify-between gap-1 mb-2 pb-2 border-b border-slate-800/60">
        <div class="flex items-center gap-1 overflow-x-auto no-scrollbar py-0.5">
          <button onclick="setTalentTreeFilterUI('all')" class="px-2 py-1 rounded-xl text-[10px] font-black transition-all ${filter === 'all' ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20' : 'bg-slate-900 text-slate-400 border border-slate-800'}">🌲 Все</button>
          <button onclick="setTalentTreeFilterUI('atk')" class="px-2 py-1 rounded-xl text-[10px] font-black transition-all ${filter === 'atk' ? 'bg-red-600 text-white shadow-md shadow-red-600/30' : 'bg-slate-900 text-red-300 border border-slate-800'}">🗡️ Атака</button>
          <button onclick="setTalentTreeFilterUI('tank')" class="px-2 py-1 rounded-xl text-[10px] font-black transition-all ${filter === 'tank' ? 'bg-blue-600 text-white shadow-md shadow-blue-600/30' : 'bg-slate-900 text-blue-300 border border-slate-800'}">🛡️ Выжив.</button>
          <button onclick="setTalentTreeFilterUI('util')" class="px-2 py-1 rounded-xl text-[10px] font-black transition-all ${filter === 'util' ? 'bg-purple-600 text-white shadow-md shadow-purple-600/30' : 'bg-slate-900 text-purple-300 border border-slate-800'}">✨ Утил.</button>
          <button onclick="setTalentTreeFilterUI('flask')" class="px-2 py-1 rounded-xl text-[10px] font-black transition-all ${filter === 'flask' ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/30' : 'bg-slate-900 text-emerald-300 border border-slate-800'}">🧪 Фляга</button>
        </div>
        <div class="text-[10.5px] font-bold text-amber-400 shrink-0">
          ⭐ <span class="text-white">${talentPts}</span> очк.
        </div>
      </div>

      <!-- Main Visual Tree Canvas (360x510 SVG + Positioned HTML Nodes) -->
      <div class="relative w-full max-w-[360px] mx-auto h-[510px]">
        <!-- SVG Connecting Energy Branches -->
        <svg class="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 360 510">`;

  // Draw root lines to T1
  const bKeys = ["atk", "tank", "util", "flask"];
  for (const bKey of bKeys) {
    if (filter !== "all" && filter !== bKey) continue;
    const theme = TREE_BRANCH_THEMES[bKey];
    const t1Node = (branches[bKey] || []).find(n => n.tier === 1);
    const isT1Bought = t1Node && t1Node.is_bought;
    const isT1Avail = t1Node && !t1Node.is_bought && effectiveProgress >= (t1Node.unlock_level != null ? t1Node.unlock_level : 1);

    const strokeColor = isT1Bought ? theme.activeStroke : (isT1Avail ? "#eab308" : "#334155");
    const strokeW = isT1Bought ? 3.5 : (isT1Avail ? 2.5 : 1.5);
    const dash = isT1Bought ? "" : "stroke-dasharray='4,4'";
    const opacity = isT1Bought ? 0.95 : (isT1Avail ? 0.75 : 0.35);

    html += `<line x1="${ROOT_POS.x}" y1="${ROOT_POS.y}" x2="${theme.colX}" y2="${TIER_Y[1]}" stroke="${strokeColor}" stroke-width="${strokeW}" ${dash} opacity="${opacity}" stroke-linecap="round" />`;

    // Draw lines between tiers (T1->T2, T2->T3, T3->T4, T4->T5)
    for (let t = 1; t <= 4; t++) {
      const parentNode = (branches[bKey] || []).find(n => n.tier === t);
      const childNode = (branches[bKey] || []).find(n => n.tier === t + 1);
      const isParentBought = parentNode && parentNode.is_bought;
      const isChildBought = childNode && childNode.is_bought;
      const isChildAvail = childNode && !childNode.is_bought && isParentBought && effectiveProgress >= (childNode.unlock_level != null ? childNode.unlock_level : childNode.tier * 5);

      let lineCol = "#334155";
      let lw = 1.5;
      let lDash = "stroke-dasharray='4,4'";
      let lOp = 0.35;

      if (isChildBought) {
        lineCol = theme.activeStroke;
        lw = 3.5;
        lDash = "";
        lOp = 0.95;
      } else if (isParentBought || isChildAvail) {
        lineCol = theme.activeStroke;
        lw = 2.5;
        lDash = "stroke-dasharray='6,3'";
        lOp = 0.75;
      }

      html += `<line x1="${theme.colX}" y1="${TIER_Y[t]}" x2="${theme.colX}" y2="${TIER_Y[t + 1]}" stroke="${lineCol}" stroke-width="${lw}" ${lDash} opacity="${lOp}" stroke-linecap="round" />`;
    }
  }

  html += `</svg>`;

  // 1. HERO CORE ROOT NODE at bottom
  html += `
    <div style="left: ${ROOT_POS.x - 26}px; top: ${ROOT_POS.y - 26}px;" class="absolute w-[52px] h-[52px] rounded-full bg-gradient-to-tr from-amber-600 via-yellow-500 to-amber-300 border-2 border-yellow-200 shadow-xl shadow-amber-500/40 flex flex-col items-center justify-center text-slate-950 font-black z-10 animate-pulse cursor-pointer">
      <span class="text-base leading-none">👑</span>
      <span class="text-[9px] font-black leading-none mt-0.5">Ур.${charLvl}</span>
    </div>`;

  // 2. TALENT NODES
  for (const bKey of bKeys) {
    if (filter !== "all" && filter !== bKey) continue;
    const theme = TREE_BRANCH_THEMES[bKey];
    const nodes = branches[bKey] || [];

    for (const node of nodes) {
      const isSelected = selectedNode && selectedNode.id === node.id;
      const isPerk = node.desc && node.desc.includes("[ПЕРК]");
      const y = TIER_Y[node.tier] || 250;
      const x = theme.colX;
      const size = isPerk ? 54 : 46;
      const halfSize = size / 2;

      let borderStyle = "";
      let bgStyle = "";
      let badgeHtml = "";

      const isNodeLvlMet = effectiveProgress >= (node.unlock_level != null ? node.unlock_level : (node.tier === 1 ? 1 : node.tier * 5));
      const nodeReq = node.req ? nodeMap[node.req] : null;
      const isNodeReqMet = !node.req || (nodeReq && nodeReq.is_bought);
      const isNodeAvail = !node.is_bought && isNodeLvlMet && isNodeReqMet;

      if (node.is_bought) {
        bgStyle = isPerk ? "bg-gradient-to-br from-emerald-950 to-slate-900 border-emerald-400 shadow-lg shadow-emerald-500/30" : "bg-emerald-950/90 border-emerald-500 shadow-md shadow-emerald-500/20";
        borderStyle = "border-2";
        badgeHtml = `<span class="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-emerald-500 text-slate-950 flex items-center justify-center text-[9px] font-black shadow">✓</span>`;
      } else if (isNodeAvail) {
        bgStyle = isPerk ? "bg-gradient-to-br from-amber-950 via-slate-900 to-amber-900 border-amber-400 shadow-xl shadow-amber-500/40 animate-pulse" : `${theme.nodeAvail} border-2`;
        borderStyle = isPerk ? "border-2" : "border-2";
        badgeHtml = `<span class="absolute -top-1 -right-1 px-1 py-0.2 rounded-full bg-amber-500 text-slate-950 text-[8px] font-black shadow">${node.cost || 1}⭐</span>`;
      } else {
        bgStyle = "bg-slate-900/70 border-slate-800 text-slate-600 opacity-60";
        borderStyle = "border";
        badgeHtml = `<span class="absolute -top-1 -right-1 text-[10px]">🔒</span>`;
      }

      if (isSelected) {
        bgStyle += " ring-2 ring-white ring-offset-2 ring-offset-slate-950 scale-110 z-20";
      }

      html += `
        <div style="left: ${x - halfSize}px; top: ${y - halfSize}px; width: ${size}px; height: ${size}px;"
             onclick="selectTalentNodeUI('${node.id}')"
             class="absolute rounded-2xl ${borderStyle} ${bgStyle} flex flex-col items-center justify-center cursor-pointer transition-all active:scale-95 group z-10">
          ${badgeHtml}
          <span class="${isPerk ? 'text-2xl' : 'text-xl'} leading-none filter drop-shadow">${node.icon}</span>
          <span class="text-[8px] font-black ${node.is_bought ? 'text-emerald-300' : (isNodeAvail ? 'text-amber-300' : 'text-slate-500')} leading-none mt-1">Т${node.tier}</span>
        </div>`;
    }
  }

  html += `</div>`; // End Canvas

  // 3. SELECTED TALENT INTERACTIVE DETAILS CARD (BOTTOM SHEET)
  if (selectedNode) {
    const isPerk = selectedNode.desc && selectedNode.desc.includes("[ПЕРК]");
    const theme = TREE_BRANCH_THEMES[selectedNode.branchKey] || TREE_BRANCH_THEMES.atk;
    const unlockLvl = selectedNode.unlock_level != null ? selectedNode.unlock_level : (selectedNode.tier === 1 ? 1 : selectedNode.tier * 5);
    const isLvlMet = effectiveProgress >= unlockLvl;
    const reqNode = selectedNode.req ? nodeMap[selectedNode.req] : null;
    const isReqMet = !selectedNode.req || (reqNode && reqNode.is_bought);
    const cost = selectedNode.cost || 1;
    const hasEnoughPts = talentPts >= cost;

    let buyBtnHtml = "";
    if (selectedNode.is_bought) {
      buyBtnHtml = `<div class="px-4 py-2.5 rounded-xl bg-emerald-900/60 border border-emerald-500/40 text-emerald-300 text-xs font-black flex items-center justify-center gap-1.5 shadow-sm">✓ ТАЛАНТ УЖЕ ИЗУЧЕН</div>`;
    } else if (!isLvlMet) {
      buyBtnHtml = `<div class="px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-500 text-xs font-bold flex items-center justify-center gap-1">🔒 Требуется ${unlockLvl} уровень (у вас: ${charLvl})</div>`;
    } else if (!isReqMet) {
      buyBtnHtml = `<div class="px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-400 text-xs font-bold flex items-center justify-center gap-1">⛓️ Сначала изучите предыдущий талант ветки (${reqNode ? reqNode.name : 'Т' + (selectedNode.tier - 1)})</div>`;
    } else if (!hasEnoughPts) {
      buyBtnHtml = `<div class="px-4 py-2.5 rounded-xl bg-amber-950/40 border border-amber-500/30 text-amber-400 text-xs font-bold flex items-center justify-center gap-1">⭐ Не хватает очков талантов (нужно: ${cost}, у вас: ${talentPts})</div>`;
    } else {
      buyBtnHtml = `
        <button onclick="buyTalentNodeUI('${selectedNode.id}')" class="w-full py-3 rounded-2xl bg-gradient-to-r from-amber-500 via-yellow-400 to-amber-500 active:scale-95 text-slate-950 font-black text-xs shadow-lg shadow-amber-500/30 flex items-center justify-center gap-2">
          <span>⚡ ИЗУЧИТЬ ТАЛАНТ</span>
          <span class="px-2 py-0.5 rounded bg-black/20 text-slate-950 text-[11px] font-extrabold">${cost} ⭐</span>
        </button>`;
    }

    html += `
      <div class="relative z-10 mt-3 p-4 rounded-2xl bg-slate-900/90 border-2 ${isPerk ? 'border-amber-400/80 shadow-amber-500/20 shadow-xl' : 'border-slate-700/80 shadow-lg'} animate-scale-up">
        <div class="flex items-start justify-between gap-2 mb-2">
          <div class="flex items-center gap-3">
            <div class="w-12 h-12 rounded-2xl ${selectedNode.is_bought ? 'bg-emerald-950 border-emerald-500' : 'bg-slate-950 border-slate-700'} border flex items-center justify-center text-3xl shrink-0 shadow-inner">
              ${selectedNode.icon}
            </div>
            <div>
              <div class="flex items-center gap-1.5 flex-wrap">
                <h4 class="font-black text-sm text-white">${selectedNode.name}</h4>
                <span class="text-[9px] font-black px-1.5 py-0.5 rounded ${theme.textColor} bg-slate-950 border border-slate-800">Т${selectedNode.tier}</span>
                ${isPerk ? '<span class="text-[8.5px] font-black px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/60 animate-pulse">✨ ПЕРК</span>' : ''}
              </div>
              <div class="text-[10px] text-slate-400 mt-0.5 font-medium">${theme.label} • Доступно с ${unlockLvl} ур. / этажа</div>
            </div>
          </div>
        </div>
        <p class="text-xs text-slate-200 bg-slate-950/60 p-2.5 rounded-xl border border-slate-800/80 mb-3 leading-relaxed">
          ${selectedNode.desc}
        </p>
        ${buyBtnHtml}
      </div>`;
  }

  html += `</div>`; // End container
  return html;
}

window.selectTalentNodeUI = function(nodeId) {
  window._selectedTalentId = nodeId;
  if (window.triggerHaptic) triggerHaptic("light");
  renderRoot();
};

window.setTalentTreeFilterUI = function(filter) {
  window._talentTreeFilter = filter;
  if (window.triggerHaptic) triggerHaptic("light");
  renderRoot();
};

// ============================================================
// 10_talents_ui.js — Дерево Талантов и Алтарь Вознесения natarGRP
// ============================================================

window._cachedTalentTree = window._cachedTalentTree || null;

function renderTalentsTab() {
  const p = RPG_STATE.profile;
  if (!p) return `<div class="p-4 text-center text-white/50">Загрузка...</div>`;

  const currentHero = (p.hero_class || "").toLowerCase();
  if (window._cachedTalentTree && (window._cachedTalentTree.hero_class || "").toLowerCase() !== currentHero) {
    window._cachedTalentTree = null;
    window._selectedTalentId = null;
    if (window._talentsTabAutoLoad) setTimeout(window._talentsTabAutoLoad, 0);
  }

  const rebirths = (p.rebirth_info && p.rebirth_info.rank) || p.rebirths || 0;
  const maxRank = (p.rebirth_info && p.rebirth_info.max_rank) || 40;
  const isMaxRank = rebirths >= maxRank;
  const rebirthMult = (p.rebirth_info && p.rebirth_info.multiplier) || 1.0;
  const essence = (p.rebirth_info && p.rebirth_info.essence) || p.rebirth_essence || 0;
  const charLvl = p.level || 1;
  const talentPts = (window._cachedTalentTree && window._cachedTalentTree.talent_points !== undefined)
    ? window._cachedTalentTree.talent_points
    : (p.talent_points || 0);

  const reqLvl = (p.rebirth_info && p.rebirth_info.next_min_level) || (rebirths === 0 ? 30 : (rebirths === 1 ? 40 : (rebirths === 2 ? 45 : 50)));
  const canAscend = !isMaxRank && charLvl >= reqLvl;

  let html = `<div class="p-3 bg-slate-900 min-h-screen text-slate-200 space-y-4">`;

  // === 1. REBIRTH BANNER (АЛТАРЬ ВОЗНЕСЕНИЯ) ===
  html += `
    <div class="bg-gradient-to-r from-purple-950/90 via-slate-800 to-indigo-950/90 p-4 rounded-3xl border border-purple-500/40 shadow-xl relative overflow-hidden">
      <div class="relative z-10 flex justify-between items-center gap-3">
        <div>
          <div class="flex items-center gap-1.5">
            <h2 class="text-base font-black text-white drop-shadow-md">🌟 Алтарь Вознесения</h2>
            <span class="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/30 text-purple-300 font-extrabold border border-purple-400/30">Ранг ${rebirths}</span>
          </div>
          <div class="text-xs text-amber-300 mt-1 font-bold">
            Множитель: <span class="text-white">x${rebirthMult.toFixed(2)}</span> | ✨ Эссенция: <span class="text-white">${essence}</span>
          </div>
          <div class="text-[10.5px] text-slate-400 mt-0.5">
            ${isMaxRank
              ? `<span class="text-amber-400 font-extrabold">👑 Достигнут абсолютный предел Вознесения (Ранг ${maxRank})!</span>`
              : `Требуется: <span class="${canAscend ? 'text-emerald-400 font-bold' : 'text-amber-300 font-bold'}">${reqLvl} ур. героя</span> (текущий: ${charLvl})`
            }
          </div>
        </div>
        <div class="shrink-0">
          ${isMaxRank
            ? `<button disabled class="px-3 py-2 bg-slate-800/90 rounded-2xl font-bold text-[10px] text-amber-400 border border-amber-500/40 cursor-not-allowed">МАКС. РАНГ (${maxRank})</button>`
            : (canAscend
                ? `<button onclick="doRebirthUI()" class="px-3.5 py-2.5 bg-gradient-to-r from-purple-500 via-indigo-500 to-purple-600 rounded-2xl font-black text-xs text-white shadow-lg shadow-purple-500/40 active:scale-95 animate-pulse">ВОЗНЕСЕНИЕ 🌟</button>`
                : `<button disabled class="px-3 py-2 bg-slate-800/90 rounded-2xl font-bold text-[10px] text-slate-500 border border-slate-700/80 cursor-not-allowed">С ${reqLvl} ур.</button>`
              )
          }
        </div>
      </div>
    </div>`;

  // === 2. TALENT TREE HEADER ===
  html += `
    <div class="flex items-center justify-between px-1">
      <div>
        <h3 class="text-sm font-black text-amber-400 flex items-center gap-1.5">
          <span>⚔️</span> Древо Навыков (${p.class_name || "Герой"})
        </h3>
        <p class="text-[10.5px] text-slate-400">Интерактивное древо развития — выберите узел для прокачки</p>
      </div>
      <div class="flex items-center gap-1.5">
        <span class="text-xs font-black px-2.5 py-1 rounded-xl bg-slate-800 border border-slate-700 text-amber-300">Ур. ${charLvl}</span>
        <span class="text-xs font-black px-2.5 py-1 rounded-xl ${talentPts > 0 ? 'bg-emerald-900/60 border-emerald-500/50 text-emerald-300 animate-pulse' : 'bg-slate-800 border-slate-700 text-slate-400'} border">⭐ ${talentPts} очк.</span>
      </div>
    </div>`;

  // === 3. VISUAL TALENT TREE GRAPH ===
  html += renderVisualTalentTree(p, window._cachedTalentTree);

  // === 4. PETS SECTION ===
  html += renderPetsSection(p);

  html += `</div>`;
  return html;
}

function renderPetsSection(p) {
  const petDict = {
    "fairy":   { icon: "🧚", name: "Лесная Фея",          desc: "Снимает станы, +35% скорости бега" },
    "wolf":    { icon: "🐺", name: "Призрачный Волк",      desc: "Кровотечение 400 ед./сек" },
    "dragon":  { icon: "🐉", name: "Золотой Дракон",       desc: "Конус огня 1200 урона, +50% золота" },
    "phoenix": { icon: "🦅", name: "Пылающий Феникс",      desc: "Щит неуязвимости при смертельном ударе" },
    "slime":   { icon: "💧", name: "Капельный Слайм",      desc: "Лечит на 10% HP каждые 12с" },
    "donkey":  { icon: "🫏", name: "Ослик-Курьер Доты",    desc: "Носит рюкзак на 6 предметов, +40% к урону группы" },
  };

  let html = `
    <div class="space-y-2 pt-2 pb-20">
      <div class="flex items-center justify-between px-1">
        <div>
          <h3 class="text-sm font-black text-amber-400 flex items-center gap-1.5"><span>🐾</span> Боевые Питомцы</h3>
          <p class="text-[10px] text-slate-400">Летающий спутник атакует врагов и усиливает героя</p>
        </div>
        <button onclick="hatchPetUI()" class="px-3 py-1.5 rounded-xl bg-gradient-to-r from-amber-500 to-yellow-400 active:scale-95 text-slate-950 font-black text-[11px] shadow-sm">🥚 ИНКУБАТОР (50 💎)</button>
      </div>
      <div class="space-y-1.5">`;

  const pets = p.pets || [];
  if (pets.length === 0) {
    html += `<div class="text-center text-slate-500 text-xs py-4 bg-slate-800/40 rounded-2xl border border-slate-800">У вас пока нет питомцев. Откройте яйцо в Инкубаторе!</div>`;
  }

  for (const pet of pets) {
    const pData = petDict[pet.type || pet.pet_id] || { icon: "🐾", name: pet.name || "Питомец", desc: "Боевой спутник" };
    const isSel = pet.is_equipped;
    html += `
      <div class="bg-slate-800/80 rounded-2xl p-3 border ${isSel ? 'border-amber-400 shadow-md shadow-amber-500/10' : 'border-slate-700/80'} flex items-center justify-between gap-3">
        <div class="flex items-center gap-3">
          <div class="w-11 h-11 rounded-xl bg-slate-900 border border-slate-700 flex items-center justify-center text-2xl shadow-inner relative">
            ${pData.icon}
            <div class="absolute -bottom-1 -right-1 bg-amber-500 text-slate-900 text-[9px] font-black px-1 rounded border border-amber-300">${pet.stars || 1}⭐</div>
          </div>
          <div>
            <div class="font-bold text-xs text-white">${pData.name}</div>
            <div class="text-[10px] text-slate-400 mt-0.5 leading-tight">${pData.desc}</div>
            <button onclick="upgradePetUI('${pet.uid}')" class="text-[10px] text-amber-400 underline mt-0.5 block font-semibold">Синтез 3-в-1 (нужно 3 шт, 10 💎)</button>
          </div>
        </div>
        <button onclick="equipPetUI('${pet.uid}')" class="px-3 py-1.5 rounded-xl text-xs font-black transition-all shrink-0 ${isSel ? 'bg-amber-500 text-slate-950 shadow-md' : 'bg-slate-700 hover:bg-slate-600 text-slate-200'}">
          ${isSel ? 'НАДЕТ' : 'ВЗЯТЬ'}
        </button>
      </div>`;
  }

  html += `</div></div>`;
  return html;
}

// === EVENT HANDLERS ===

window.loadTalentTreeUI = async function() {
  try {
    const data = await api.getTalentTree();
    window._cachedTalentTree = data;
    renderRoot();
  } catch (e) {
    alert("Ошибка загрузки дерева талантов: " + (e.message || e));
  }
};

window.buyTalentNodeUI = async function(nodeId) {
  try {
    if (window.triggerHaptic) triggerHaptic("medium");
    const res = await api.buyTalentNode(nodeId);
    if (res && res.profile) {
      RPG_STATE.profile = res.profile;
      if (window.syncArenaPlayerStats) syncArenaPlayerStats();
      window._cachedTalentTree = await api.getTalentTree();
      if (window.triggerHaptic) triggerHaptic("success");
      renderRoot();
    }
  } catch (err) {
    if (window.triggerHaptic) triggerHaptic("error");
    alert(err.message || "Ошибка покупки таланта");
  }
};

window.doRebirthUI = async function() {
  if (!confirm("Совершить Вознесение? Уровень сбросится до 1, но вы сохраните все предметы, заточку, питомцев и получите постоянный множитель статов!")) return;
  try {
    if (window.triggerHaptic) triggerHaptic("heavy");
    const res = await api.doRebirth();
    if (res.profile) {
      RPG_STATE.profile = res.profile;
      if (typeof ARENA !== "undefined") {
        ARENA.waveNumber = 1;
        ARENA.totalCreepsSpawned = 0;
        ARENA.creepsKilledInWave = 0;
        ARENA.creeps = [];
      }
      if (window.syncArenaPlayerStats) syncArenaPlayerStats();
      if (window.triggerHaptic) triggerHaptic("success");
      window._cachedTalentTree = null;
      renderRoot();
    }
  } catch(e) { alert(e.message || "Ошибка перерождения"); }
};

window.hatchPetUI = async function() {
  try {
    if (window.triggerHaptic) triggerHaptic("medium");
    const res = await api.hatchPetCrate();
    if (res.profile) {
      RPG_STATE.profile = res.profile;
      if (window.triggerHaptic) triggerHaptic("success");
      alert("Выпал питомец: " + (res.pet_cfg ? res.pet_cfg.name : "Новый питомец!"));
      renderRoot();
    }
  } catch(e) { alert(e.message || "Ошибка открытия яйца"); }
};

window.equipPetUI = async function(petUid) {
  try {
    if (window.triggerHaptic) triggerHaptic("light");
    const res = await api.equipPet(petUid);
    if (res.profile) {
      RPG_STATE.profile = res.profile;
      if (window.syncArenaPlayerStats) syncArenaPlayerStats();
      const eqPet = (res.profile.pets || []).find(p => p.is_equipped);
      if (eqPet) localStorage.setItem("rpg_active_pet", eqPet.type || eqPet.pet_id);
      else localStorage.removeItem("rpg_active_pet");
      renderRoot();
    }
  } catch(e) { alert(e.message || "Ошибка экипировки"); }
};

window.selectPetUI = window.equipPetUI;

window.upgradePetUI = async function(petUid) {
  try {
    if (window.triggerHaptic) triggerHaptic("medium");
    const res = await api.upgradePet(petUid);
    if (res.profile) {
      RPG_STATE.profile = res.profile;
      if (window.syncArenaPlayerStats) syncArenaPlayerStats();
      if (window.triggerHaptic) triggerHaptic("success");
      alert("Питомец успешно улучшен!");
      renderRoot();
    }
  } catch(e) { alert(e.message || "Ошибка улучшения питомца"); }
};

window.upgradeTalentUI = async function(talentId) {
  try {
    if (window.triggerHaptic) triggerHaptic("light");
    const res = await api.upgradeTalent(talentId);
    if (res.profile) {
      RPG_STATE.profile = res.profile;
      if (window.syncArenaPlayerStats) syncArenaPlayerStats();
      renderRoot();
    }
  } catch(e) { alert(e.message || "Ошибка улучшения таланта"); }
};

// Auto-load talent tree data when tab opens
window._talentsTabAutoLoad = function() {
  const currentHero = (RPG_STATE.profile?.hero_class || "").toLowerCase();
  if ((!window._cachedTalentTree || (window._cachedTalentTree.hero_class || "").toLowerCase() !== currentHero) && RPG_STATE.profile) {
    api.getTalentTree().then(data => {
      window._cachedTalentTree = data;
      renderRoot();
    }).catch(() => {});
  }
};

// ============================================================
// 11_admin_catalog_data.js — Встроенный каталог предметов RPG
// 148 предметов для мгновенной доступности без задержек сети
// ============================================================
window._DEFAULT_RPG_CATALOG = [
  {"name": "Железная Ветка (Iron Branch)", "icon": "🌿", "rarity": "common", "slot": "relic"},
  {"name": "Перчатки Силы (Gauntlets of Strength)", "icon": "🥊", "rarity": "common", "slot": "relic"},
  {"name": "Тапочки Ловкости (Slippers of Agility)", "icon": "🥿", "rarity": "common", "slot": "relic"},
  {"name": "Мантия Интеллекта (Mantle of Intelligence)", "icon": "📜", "rarity": "common", "slot": "relic"},
  {"name": "Венец Благородства (Circlet)", "icon": "👑", "rarity": "common", "slot": "relic"},
  {"name": "Топорик Лесоруба (Quelling Blade)", "icon": "🪓", "rarity": "common", "slot": "weapon"},
  {"name": "Прочный Щиток (Stout Shield)", "icon": "🛡️", "rarity": "common", "slot": "armor"},
  {"name": "Кольцо Защиты (Ring of Protection)", "icon": "💍", "rarity": "common", "slot": "armor"},
  {"name": "Волшебная Палочка (Magic Stick)", "icon": "🪄", "rarity": "common", "slot": "relic"},
  {"name": "Камень Порчи (Blight Stone)", "icon": "🪨", "rarity": "common", "slot": "weapon"},
  {"name": "Шнурок Ветра (Wind Lace)", "icon": "👟", "rarity": "common", "slot": "armor"},
  {"name": "Капли Дождя (Infused Raindrops)", "icon": "💧", "rarity": "common", "slot": "relic"},
  {"name": "Ржавый Кинжал Новичка", "icon": "🗡️", "rarity": "common", "slot": "weapon"},
  {"name": "Тканевая Куртка Ополченца", "icon": "🥋", "rarity": "common", "slot": "armor"},
  {"name": "Кольцо Регенерации (Ring of Regen)", "icon": "💚", "rarity": "common", "slot": "relic"},
  {"name": "Дубовый Боевой Посох", "icon": "🪵", "rarity": "common", "slot": "weapon"},
  {"name": "Клинки Атаки (Blades of Attack)", "icon": "⚔️", "rarity": "uncommon", "slot": "weapon"},
  {"name": "Кольчуга (Chainmail)", "icon": "🦺", "rarity": "uncommon", "slot": "armor"},
  {"name": "Шлем Железной Воли (Helm of Iron Will)", "icon": "🪖", "rarity": "uncommon", "slot": "armor"},
  {"name": "Маска Смерти (Morbid Mask)", "icon": "🎭", "rarity": "uncommon", "slot": "relic"},
  {"name": "Сапоги Скорости (Boots of Speed)", "icon": "👢", "rarity": "uncommon", "slot": "armor"},
  {"name": "Фазовые Сапоги (Phase Boots)", "icon": "👢", "rarity": "uncommon", "slot": "armor"},
  {"name": "Сапоги Мощи (Power Treads)", "icon": "🥾", "rarity": "uncommon", "slot": "armor"},
  {"name": "Сфера Коррозии (Orb of Corrosion)", "icon": "🧪", "rarity": "uncommon", "slot": "weapon"},
  {"name": "Клинок Сокола (Falcon Blade)", "icon": "🪶", "rarity": "uncommon", "slot": "weapon"},
  {"name": "Авангард (Vanguard)", "icon": "🛡️", "rarity": "uncommon", "slot": "armor"},
  {"name": "Урна Теней (Urn of Shadows)", "icon": "🏺", "rarity": "uncommon", "slot": "relic"},
  {"name": "Медальон Мужества (Medallion of Courage)", "icon": "🏅", "rarity": "uncommon", "slot": "armor"},
  {"name": "Корона Императора (Crown)", "icon": "👑", "rarity": "uncommon", "slot": "relic"},
  {"name": "Пояс Великана (Belt of Strength)", "icon": "🥋", "rarity": "uncommon", "slot": "armor"},
  {"name": "Сапоги Эльфийской Ловкости (Boots of Elvenskin)", "icon": "🥿", "rarity": "uncommon", "slot": "armor"},
  {"name": "Мантия Мага (Robe of the Magi)", "icon": "👘", "rarity": "uncommon", "slot": "armor"},
  {"name": "Палаш (Broadsword)", "icon": "🗡️", "rarity": "rare", "slot": "weapon"},
  {"name": "Клеймор (Claymore)", "icon": "🗡️", "rarity": "rare", "slot": "weapon"},
  {"name": "Мифриловый Молот (Mithril Hammer)", "icon": "🔨", "rarity": "rare", "slot": "weapon"},
  {"name": "Латный Доспех (Platemail)", "icon": "🛡️", "rarity": "rare", "slot": "armor"},
  {"name": "Кристалис (Crystalys)", "icon": "💎", "rarity": "rare", "slot": "weapon"},
  {"name": "Крушитель Черепов (Skull Basher)", "icon": "🔨", "rarity": "rare", "slot": "weapon"},
  {"name": "Теневой Клинок (Shadow Blade)", "icon": "🗡️", "rarity": "rare", "slot": "weapon"},
  {"name": "Яша (Yasha)", "icon": "🗡️", "rarity": "rare", "slot": "weapon"},
  {"name": "Саша (Sange)", "icon": "🗡️", "rarity": "rare", "slot": "weapon"},
  {"name": "Кайя (Kaya)", "icon": "🪄", "rarity": "rare", "slot": "weapon"},
  {"name": "Молния (Maelstrom)", "icon": "⚡", "rarity": "rare", "slot": "weapon"},
  {"name": "Клинок Очищения (Diffusal Blade)", "icon": "🗡️", "rarity": "rare", "slot": "weapon"},
  {"name": "Пика Дракона (Dragon Lance)", "icon": "🔱", "rarity": "rare", "slot": "weapon"},
  {"name": "Возвратный Доспех (Blade Mail)", "icon": "🛡️", "rarity": "rare", "slot": "armor"},
  {"name": "Аганимный Осколок (Aghanim Shard)", "icon": "🔷", "rarity": "rare", "slot": "relic"},
  {"name": "Саша и Яша (Sange and Yasha)", "icon": "⚔️", "rarity": "rare", "slot": "weapon"},
  {"name": "Боевой Топор (Battle Fury)", "icon": "🪓", "rarity": "epic", "slot": "weapon"},
  {"name": "Дедал (Daedalus)", "icon": "🏹", "rarity": "epic", "slot": "weapon"},
  {"name": "Бабочка (Butterfly)", "icon": "🦋", "rarity": "epic", "slot": "weapon"},
  {"name": "Обезьяний Посох (Monkey King Bar)", "icon": "🐒", "rarity": "epic", "slot": "weapon"},
  {"name": "Сияние (Radiance)", "icon": "☀️", "rarity": "epic", "slot": "weapon"},
  {"name": "Опустошитель (Desolator)", "icon": "🔴", "rarity": "epic", "slot": "weapon"},
  {"name": "Сатаник (Satanic)", "icon": "🩸", "rarity": "epic", "slot": "relic"},
  {"name": "Сердце Тарраска (Heart of Tarrasque)", "icon": "❤️", "rarity": "epic", "slot": "armor"},
  {"name": "Кираса Штурма (Assault Cuirass)", "icon": "🛡️", "rarity": "epic", "slot": "armor"},
  {"name": "Черный Королевский Бар (Black King Bar)", "icon": "🟡", "rarity": "epic", "slot": "relic"},
  {"name": "Страж Шивы (Shiva Guard)", "icon": "❄️", "rarity": "epic", "slot": "armor"},
  {"name": "Око Скади (Eye of Skadi)", "icon": "👁️", "rarity": "epic", "slot": "relic"},
  {"name": "Кровавый Шип (Bloodthorn)", "icon": "🌹", "rarity": "epic", "slot": "weapon"},
  {"name": "Мьёльнир (Mjollnir)", "icon": "⚡", "rarity": "epic", "slot": "weapon"},
  {"name": "Коса Вайса (Scythe of Vyse)", "icon": "🐏", "rarity": "epic", "slot": "relic"},
  {"name": "Абиссальный Клинок (Abyssal Blade)", "icon": "🗡️", "rarity": "epic", "slot": "weapon"},
  {"name": "Божественная Рапира (Divine Rapier)", "icon": "🗡️", "rarity": "immortal", "slot": "weapon"},
  {"name": "Эгида Бессмертия (Aegis of the Immortal)", "icon": "🛡️", "rarity": "immortal", "slot": "relic"},
  {"name": "Сыр Рошана (Cheese)", "icon": "🧀", "rarity": "immortal", "slot": "consumable"},
  {"name": "Благословение Аганима (Aghanim Blessing)", "icon": "🔮", "rarity": "immortal", "slot": "relic"},
  {"name": "Сфера Обновления (Refresher Orb)", "icon": "🟢", "rarity": "immortal", "slot": "relic"},
  {"name": "Апекс (Apex)", "icon": "🔺", "rarity": "immortal", "slot": "relic"},
  {"name": "Падшие Небеса (Fallen Sky)", "icon": "☄️", "rarity": "immortal", "slot": "weapon"},
  {"name": "Зеркальный Щит (Mirror Shield)", "icon": "🪞", "rarity": "immortal", "slot": "armor"},
  {"name": "Гигантское Кольцо (Giant Ring)", "icon": "💍", "rarity": "immortal", "slot": "armor"},
  {"name": "Стигийский Дезолятор (Stygian Desolator)", "icon": "🩸", "rarity": "immortal", "slot": "weapon"},
  {"name": "Око Вечности (Eye of Eternity)", "icon": "👁️", "rarity": "immortal", "slot": "relic"},
  {"name": "Дубовый Посох (Oak Staff)", "icon": "🦯", "rarity": "common", "slot": "weapon"},
  {"name": "Ржавый Кинжал (Rusty Dagger)", "icon": "🗡️", "rarity": "common", "slot": "weapon"},
  {"name": "Деревянный Баклер (Wooden Buckler)", "icon": "🛡️", "rarity": "common", "slot": "armor"},
  {"name": "Треснувший Опал (Cracked Opal)", "icon": "💎", "rarity": "common", "slot": "relic"},
  {"name": "Кольцо Базилиуса (Ring of Basilius)", "icon": "💍", "rarity": "common", "slot": "relic"},
  {"name": "Топорик Лесоруба (Woodcutter Hatchet)", "icon": "🪓", "rarity": "common", "slot": "weapon"},
  {"name": "Повязка Ученика (Apprentice Band)", "icon": "🎗️", "rarity": "common", "slot": "armor"},
  {"name": "Шнурок Проворства (Lace of Haste)", "icon": "🎗️", "rarity": "common", "slot": "relic"},
  {"name": "Брейсер Защитника (Bracer)", "icon": "🥊", "rarity": "uncommon", "slot": "relic"},
  {"name": "Врейс Бенд (Wraith Band)", "icon": "💍", "rarity": "uncommon", "slot": "relic"},
  {"name": "Нулл Талисман (Null Talisman)", "icon": "📿", "rarity": "uncommon", "slot": "relic"},
  {"name": "Кольцо Души (Soul Ring)", "icon": "💍", "rarity": "uncommon", "slot": "relic"},
  {"name": "Капля Жизни (Tear of Life)", "icon": "💧", "rarity": "uncommon", "slot": "relic"},
  {"name": "Плащ Мудрости (Cloak of Wisdom)", "icon": "🧥", "rarity": "uncommon", "slot": "armor"},
  {"name": "Кинжал Тени (Shadow Dagger)", "icon": "🗡️", "rarity": "uncommon", "slot": "weapon"},
  {"name": "Кольцо Аквилы (Ring of Aquila)", "icon": "💍", "rarity": "uncommon", "slot": "relic"},
  {"name": "Барабаны Войны (Drum of Endurance)", "icon": "🥁", "rarity": "rare", "slot": "relic"},
  {"name": "Владимир (Vladmir Offering)", "icon": "🦇", "rarity": "rare", "slot": "relic"},
  {"name": "Солар Крест (Solar Crest)", "icon": "☀️", "rarity": "rare", "slot": "armor"},
  {"name": "Линза Эфира (Aether Lens)", "icon": "🔍", "rarity": "rare", "slot": "relic"},
  {"name": "Плащ Мерцания (Glimmer Cape)", "icon": "🧥", "rarity": "rare", "slot": "armor"},
  {"name": "Эхо Сабля (Echo Sabre)", "icon": "⚔️", "rarity": "rare", "slot": "weapon"},
  {"name": "Метеор Хаммер (Meteor Hammer)", "icon": "☄️", "rarity": "rare", "slot": "weapon"},
  {"name": "Меч Гарпуна (Harpoon Blade)", "icon": "🔱", "rarity": "rare", "slot": "weapon"},
  {"name": "Крикун Глейпнир (Gleipnir)", "icon": "⚡", "rarity": "epic", "slot": "weapon"},
  {"name": "Кримсон Гард (Crimson Guard)", "icon": "🛡️", "rarity": "epic", "slot": "armor"},
  {"name": "Трубка Прозрения (Pipe of Insight)", "icon": "🪈", "rarity": "epic", "slot": "armor"},
  {"name": "Эон Диск (Aeon Disk)", "icon": "📀", "rarity": "epic", "slot": "armor"},
  {"name": "Винд Вейкер (Wind Waker)", "icon": "🌪️", "rarity": "epic", "slot": "relic"},
  {"name": "Брошь Призрака (Revenant Brooch)", "icon": "👻", "rarity": "epic", "slot": "relic"},
  {"name": "Октарин Ядро (Octarine Core)", "icon": "🔮", "rarity": "epic", "slot": "relic"},
  {"name": "Сфера Линкена (Linken Sphere)", "icon": "🌐", "rarity": "epic", "slot": "relic"},
  {"name": "Книга Мертвых (Book of the Dead)", "icon": "📖", "rarity": "immortal", "slot": "relic"},
  {"name": "Пиратская Шляпа (Pirate Hat)", "icon": "🏴‍☠️", "rarity": "immortal", "slot": "armor"},
  {"name": "Сапоги Силы (Force Boots)", "icon": "👢", "rarity": "immortal", "slot": "armor"},
  {"name": "Камень Провидца (Seer Stone)", "icon": "🔮", "rarity": "immortal", "slot": "relic"},
  {"name": "Экс Махина (Ex Machina)", "icon": "⚙️", "rarity": "immortal", "slot": "armor"},
  {"name": "Посох Чародея (Staff of Wizardry)", "icon": "🪄", "rarity": "uncommon", "slot": "weapon"},
  {"name": "Клинок Ловкости (Blade of Alacrity)", "icon": "🗡️", "rarity": "uncommon", "slot": "weapon"},
  {"name": "Дагон I (Dagon I)", "icon": "⚡", "rarity": "rare", "slot": "relic"},
  {"name": "Скипетр Эула (Eul's Scepter)", "icon": "🌪️", "rarity": "rare", "slot": "relic"},
  {"name": "Мистический Посох (Mystic Staff)", "icon": "🧙", "rarity": "rare", "slot": "weapon"},
  {"name": "Орлиный Рог (Eaglehorn)", "icon": "🏹", "rarity": "rare", "slot": "weapon"},
  {"name": "Ботинки Путешествий (Boots of Travel)", "icon": "👟", "rarity": "rare", "slot": "relic"},
  {"name": "Дагон III (Dagon III)", "icon": "⚡", "rarity": "epic", "slot": "relic"},
  {"name": "Дагон V (Dagon V)", "icon": "⚡", "rarity": "epic", "slot": "relic"},
  {"name": "Эфирный Клинок (Ethereal Blade)", "icon": "🪄", "rarity": "epic", "slot": "weapon"},
  {"name": "Кайя и Саша (Kaya and Sange)", "icon": "⚔️", "rarity": "epic", "slot": "weapon"},
  {"name": "Яша и Кайя (Yasha and Kaya)", "icon": "⚔️", "rarity": "epic", "slot": "weapon"},
  {"name": "Манта Стайл (Manta Style)", "icon": "👥", "rarity": "epic", "slot": "weapon"},
  {"name": "Серебряный Кортик (Silver Edge)", "icon": "🗡️", "rarity": "epic", "slot": "weapon"},
  {"name": "Ураганная Пика (Hurricane Pike)", "icon": "🔱", "rarity": "epic", "slot": "weapon"},
  {"name": "Сфера Линки (Linken's Sphere)", "icon": "🌐", "rarity": "immortal", "slot": "relic"},
  {"name": "Клинок Бездны (Abyssal Blade)", "icon": "🗡️", "rarity": "immortal", "slot": "weapon"},
  {"name": "Коса Вайса (Scythe of Vyse / Хекс)", "icon": "🐑", "rarity": "immortal", "slot": "relic"},
  {"name": "Глейпнир (Gleipnir)", "icon": "⛓️", "rarity": "immortal", "slot": "relic"},
  {"name": "Шипастый Доспех (Blade Mail)", "icon": "🛡️", "rarity": "rare", "slot": "armor"},
  {"name": "Багровая Защита (Crimson Guard)", "icon": "🔴", "rarity": "epic", "slot": "armor"},
  {"name": "Арматура Мордиггиана (Armlet)", "icon": "🧤", "rarity": "rare", "slot": "armor"},
  {"name": "Пика Урагана (Hurricane Pike)", "icon": "🔱", "rarity": "epic", "slot": "weapon"},
  {"name": "Серебряный Клинок (Silver Edge)", "icon": "🗡️", "rarity": "immortal", "slot": "weapon"},
  {"name": "Даэдалус (Daedalus)", "icon": "🏹", "rarity": "immortal", "slot": "weapon"},
  {"name": "Посох Короля Обезьян (Monkey King Bar)", "icon": "🥢", "rarity": "immortal", "slot": "weapon"},
  {"name": "Сердце Тарраски (Heart of Tarrasque)", "icon": "❤️", "rarity": "immortal", "slot": "armor"},
  {"name": "Кровавый Камень (Bloodstone)", "icon": "🩸", "rarity": "immortal", "slot": "relic"},
  {"name": "Осколок Аганима (Aghanim Shard)", "icon": "🔷", "rarity": "rare", "slot": "relic"},
  {"name": "Октариновое Ядро (Octarine Core)", "icon": "💎", "rarity": "epic", "slot": "relic"},
  {"name": "Страж Шивы (Shiva's Guard)", "icon": "❄️", "rarity": "epic", "slot": "armor"},
  {"name": "Диффуза (Diffusal Blade)", "icon": "🗡️", "rarity": "rare", "slot": "weapon"},
  {"name": "Кованая Кираса Стража", "icon": "🛡️", "rarity": "rare", "slot": "armor"},
  {"name": "Кинжал Скачка (Blink Dagger)", "icon": "🗡️", "rarity": "rare", "slot": "relic"},
  {"name": "Кханда (Khanda)", "icon": "🗡️", "rarity": "immortal", "slot": "weapon"},
  {"name": "Осколок Луны (Moon Shard)", "icon": "🌙", "rarity": "legendary", "slot": "relic"},
];

// ============================================================
// 11_admin_panel.js — Админ-Панель управления RPG
// Чит-коды: золото, уровень, предметы из каталога и сброс игроков
// ============================================================

window.RPG = window.RPG || {};
window._adminPlayersList = window._adminPlayersList || null;
window._adminCatalogItems = window._adminCatalogItems || (typeof window._DEFAULT_RPG_CATALOG !== "undefined" ? window._DEFAULT_RPG_CATALOG : []);
window._adminSelectedTarget = window._adminSelectedTarget || "";
window._adminSubTab = window._adminSubTab || "actions"; // "actions" | "slots"
window._fetchingAdminPlayers = false;
window._fetchingAdminCatalog = false;

function showAdminNotice(msg) {
  if (window.Telegram?.WebApp?.showAlert) {
    try { window.Telegram.WebApp.showAlert(msg); return; } catch (_) {}
  }
  alert(msg);
}

function getDefaultAdminPlayers() {
  const p = window.RPG_STATE?.profile;
  const uid = p?.user_id || 1, tg = p?.tg_id || 1053722876, name = p?.user_name || "Я (Администратор)", lvl = p?.level || 1, gold = p?.gold || 0;
  return [
    { user_id: uid, tg_id: tg, name: name, level: lvl, gold: gold, hero_icon: "👑" },
    { user_id: 1, tg_id: 7755842535, name: "Не Вадим", level: 28, gold: 1645000, hero_icon: "🦌" },
    { user_id: 5, tg_id: 1440393642, name: "Михаил Исайкин", level: 43, gold: 373000, hero_icon: "🔮" },
    { user_id: 24, tg_id: 6926859962, name: "Макар", level: 35, gold: 104000, hero_icon: "🔮" },
    { user_id: 17, tg_id: 5181261098, name: "Глеб", level: 21, gold: 146000, hero_icon: "🔮" },
    { user_id: 4, tg_id: 1053722876, name: "notariuspiva", level: 18, gold: 4236000, hero_icon: "🪝" },
  ];
}

function updateAdminModalDOM() {
  const backdrop = document.getElementById("rpg-admin-modal-backdrop");
  if (backdrop && RPG_STATE.adminModalOpen) {
    backdrop.outerHTML = renderAdminModalHTML();
  } else {
    renderRoot();
  }
}

function renderAdminFloatingBadgeHTML() {
  const activeTestSlot = localStorage.getItem("admin_test_tg_uid");
  const currentSlotLabel = activeTestSlot ? `🧪 #${activeTestSlot}` : `👑 Админ`;
  return `<div id="rpg-admin-floating-btn" class="fixed bottom-20 left-2.5 z-40">
    <button onclick="window.RPG.toggleAdminModal(true)" title="Админ-Панель"
      class="px-2.5 py-1.5 rounded-2xl bg-gradient-to-r from-amber-500 via-yellow-400 to-amber-500 text-slate-950 font-black text-[10px] shadow-2xl border-2 border-amber-300 flex items-center gap-1.5 active:scale-95 animate-pulse">
      <span class="text-xs">🛠️</span><span>${currentSlotLabel}</span>
    </button>
  </div>`;
}

function renderAdminModalHTML() {
  const activeTestSlot = localStorage.getItem("admin_test_tg_uid");
  const currentSlotLabel = activeTestSlot ? `🧪 #${activeTestSlot}` : `👑 Админ`;
  const players = (window._adminPlayersList && window._adminPlayersList.length > 0) ? window._adminPlayersList : getDefaultAdminPlayers();
  const catalog = (window._adminCatalogItems && window._adminCatalogItems.length > 0) ? window._adminCatalogItems : (window._DEFAULT_RPG_CATALOG || []);

  return `<div id="rpg-admin-modal-backdrop" class="fixed inset-0 z-50 bg-slate-950/85 backdrop-blur-md flex items-center justify-center p-3">
    <div class="w-full max-w-md max-h-[92vh] flex flex-col rounded-3xl bg-slate-900 border-2 border-amber-400/90 shadow-2xl text-white animate-scale-up overflow-hidden">
      <div class="p-3.5 border-b border-slate-700/80 flex items-center justify-between bg-slate-800/60 shrink-0">
        <div class="flex items-center gap-2">
          <span class="text-2xl">🛠️</span>
          <div>
            <h3 class="text-xs font-black text-amber-400 uppercase tracking-wider">Админ-Панель natarGRP</h3>
            <span class="text-[9px] text-slate-400">Управление игроками, чит-коды и тестирование</span>
          </div>
        </div>
        <button onclick="window.RPG.toggleAdminModal(false)" class="w-7 h-7 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 flex items-center justify-center font-bold text-xs">✕</button>
      </div>
      <div class="flex border-b border-slate-700/80 bg-slate-950/40 p-1 gap-1 shrink-0">
        <button onclick="window.RPG.setAdminSubTab('actions')" class="flex-1 py-1.5 text-center text-xs font-black rounded-xl transition-all ${window._adminSubTab === 'actions' ? 'bg-amber-500 text-slate-950 shadow-md' : 'text-slate-400 hover:text-white'}">⚡ Чит-Меню & Действия</button>
        <button onclick="window.RPG.setAdminSubTab('slots')" class="flex-1 py-1.5 text-center text-xs font-black rounded-xl transition-all ${window._adminSubTab === 'slots' ? 'bg-amber-500 text-slate-950 shadow-md' : 'text-slate-400 hover:text-white'}">🧪 Тест-Слоты (${currentSlotLabel})</button>
      </div>
      <div class="p-3.5 overflow-y-auto space-y-3 flex-1 text-xs">
        ${window._adminSubTab === "actions" ? renderAdminActionsTabHTML(players, catalog) : renderAdminSlotsTabHTML(activeTestSlot)}
      </div>
    </div>
  </div>`;
}

function renderAdminActionsTabHTML(players, catalog) {
  return `
    <div class="p-2.5 rounded-2xl bg-slate-800/80 border border-slate-700 space-y-2">
      <div class="flex items-center justify-between">
        <span class="text-[10px] font-black uppercase text-amber-400 tracking-wider">🎯 Целевой Игрок (${players.length} чел.):</span>
        <button onclick="window.RPG.refreshAdminPlayers()" class="text-[10px] text-sky-400 hover:underline flex items-center gap-1 font-bold"><span>🔄</span> Обновить</button>
      </div>
      <select id="admin-target-select" onchange="window._adminSelectedTarget = this.value; updateAdminModalDOM();" class="w-full bg-slate-950 border border-slate-600 rounded-xl px-2.5 py-1.5 text-xs text-amber-200 font-bold focus:outline-none">
        <option value="" ${!window._adminSelectedTarget ? 'selected' : ''}>👤 Текущий аккаунт (Я)</option>
        ${players.map(p => `<option value="${p.tg_id || p.user_id}" ${window._adminSelectedTarget == (p.tg_id || p.user_id) ? 'selected' : ''}>${p.hero_icon || '👤'} ${p.name} ${p.level > 0 ? `[Ур. ${p.level} | 🪙 ${p.gold >= 1000 ? Math.round(p.gold/1000)+'k' : p.gold}]` : '[Новичок]'} (ID: ${p.tg_id || p.user_id})</option>`).join('')}
      </select>
      <div class="flex items-center gap-2">
        <input type="text" id="admin-custom-target-input" placeholder="Или введите TG ID / User ID / @username" value="${window._adminSelectedTarget || ''}" onchange="window._adminSelectedTarget = this.value.trim()" class="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-2.5 py-1 text-[11px] text-slate-300 placeholder-slate-500">
        <button onclick="window.RPG.applyAdminCustomTarget()" class="px-2.5 py-1 bg-slate-700 hover:bg-slate-600 text-white rounded-xl text-[10px] font-bold">Выбрать</button>
      </div>
    </div>
    <div class="p-2.5 rounded-2xl bg-slate-800/80 border border-slate-700 space-y-2">
      <span class="text-[10px] font-black uppercase text-amber-400 tracking-wider flex items-center gap-1"><span>🪙</span> Выдать Золото</span>
      <div class="grid grid-cols-4 gap-1.5">
        ${[[50000, '+50k'], [250000, '+250k'], [1000000, '+1M'], [10000000, '+10M']].map(([a, l]) => `<button onclick="window.RPG.adminGiveGold(${a})" class="py-1 bg-amber-500/20 border border-amber-500/50 rounded-xl font-black text-amber-300 text-[11px] active:scale-95">${l}</button>`).join('')}
      </div>
      <div class="flex gap-2">
        <input type="number" id="admin-gold-custom-input" placeholder="Своя сумма золота" class="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-2.5 py-1 text-xs text-white">
        <button onclick="window.RPG.adminGiveGoldCustom()" class="px-3 py-1 bg-gradient-to-r from-amber-500 to-yellow-500 text-slate-950 rounded-xl font-black text-xs active:scale-95">Выдать</button>
      </div>
    </div>
    <div class="p-2.5 rounded-2xl bg-slate-800/80 border border-slate-700 space-y-2">
      <span class="text-[10px] font-black uppercase text-emerald-400 tracking-wider flex items-center gap-1"><span>💎</span> Выдать Кристаллы</span>
      <div class="grid grid-cols-4 gap-1.5">
        ${[[50, '+50 💎'], [250, '+250 💎'], [1000, '+1k 💎'], [10000, '+10k 💎']].map(([a, l]) => `<button onclick="window.RPG.adminGiveGems(${a})" class="py-1 bg-emerald-500/20 border border-emerald-500/50 rounded-xl font-black text-emerald-300 text-[11px] active:scale-95">${l}</button>`).join('')}
      </div>
      <div class="flex gap-2">
        <input type="number" id="admin-gems-custom-input" placeholder="Своя сумма кристаллов" class="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-2.5 py-1 text-xs text-white">
        <button onclick="window.RPG.adminGiveGemsCustom()" class="px-3 py-1 bg-gradient-to-r from-emerald-500 to-teal-500 text-slate-950 rounded-xl font-black text-xs active:scale-95">Выдать</button>
      </div>
    </div>
    <div class="p-2.5 rounded-2xl bg-slate-800/80 border border-slate-700 space-y-2">
      <span class="text-[10px] font-black uppercase text-sky-400 tracking-wider flex items-center gap-1"><span>🆙</span> Изменить Уровень Героя (1..50)</span>
      <div class="grid grid-cols-4 gap-1.5">
        ${[[1, 'Ур. 1'], [15, 'Ур. 15'], [30, 'Ур. 30'], [50, 'Ур. 50 (MAX)']].map(([l, lbl]) => `<button onclick="window.RPG.adminSetLevel(${l})" class="py-1 bg-sky-500/20 border border-sky-500/50 rounded-xl font-black text-sky-300 text-[11px] active:scale-95">${lbl}</button>`).join('')}
      </div>
      <div class="flex gap-2">
        <input type="number" id="admin-level-custom-input" min="1" max="50" placeholder="Уровень 1..50" class="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-2.5 py-1 text-xs text-white">
        <button onclick="window.RPG.adminSetLevelCustom()" class="px-3 py-1 bg-gradient-to-r from-sky-500 to-blue-600 text-white rounded-xl font-black text-xs active:scale-95">Установить</button>
      </div>
    </div>
    <div class="p-2.5 rounded-2xl bg-slate-800/80 border border-slate-700 space-y-2">
      <div class="flex items-center justify-between">
        <span class="text-[10px] font-black uppercase text-purple-400 tracking-wider flex items-center gap-1">
          <span>🎁</span> Выдать Предмет из Каталога (${catalog.length} предм.)
        </span>
        <button onclick="window.RPG.fetchAdminCatalog()" class="text-[10px] text-purple-300 hover:underline font-bold">🔄 Обновить</button>
      </div>
      <div>
        <label class="text-[9px] text-slate-400 block mb-0.5">Выберите предмет из игры:</label>
        <select id="admin-catalog-item-select" onchange="window.RPG.onAdminCatalogItemChange(this.value)" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-2 py-1.5 text-xs text-amber-300 font-bold focus:outline-none focus:border-purple-400">
          <option value="">🎲 [Случайный предмет под выбранную редкость]</option>
          ${catalog.map(it => `<option value="${it.name}">${it.icon || '📦'} ${it.name} (${it.rarity || 'common'})</option>`).join('')}
        </select>
      </div>
      <div class="grid grid-cols-2 gap-2">
        <div>
          <label class="text-[9px] text-slate-400 block mb-0.5">Редкость:</label>
          <select id="admin-item-rarity-select" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-2 py-1 text-xs text-purple-300 font-bold">
            <option value="common">⚪ Обычный</option><option value="uncommon">🟢 Необычный</option><option value="rare">🔵 Редкий</option>
            <option value="epic">🟣 Эпический</option><option value="legendary" selected>🟠 Легендарный</option><option value="mythic">🔴 Мифический</option><option value="immortal">💖 Бессмертный</option>
          </select>
        </div>
        <div>
          <label class="text-[9px] text-slate-400 block mb-0.5">Уровень (1..50):</label>
          <input type="number" id="admin-item-level-input" value="10" min="1" max="50" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-2 py-1 text-xs text-white">
        </div>
      </div>
      <button onclick="window.RPG.adminGiveItemSubmit()" class="w-full py-2 bg-gradient-to-r from-purple-600 via-indigo-600 to-purple-700 text-white rounded-xl font-black text-xs shadow-lg shadow-purple-600/30 active:scale-95">✨ Выдать Выбранный Предмет в Инвентарь</button>
    </div>
    <div class="p-2.5 rounded-2xl bg-rose-950/40 border border-rose-600/50 space-y-1.5">
      <span class="text-[10px] font-black uppercase text-rose-400 tracking-wider flex items-center gap-1"><span>⚠️</span> Опасная Зона: Сброс</span>
      <p class="text-[10px] text-rose-300/80 leading-tight">Полностью обнуляет выбранного игрока до 1 уровня, очищает экипировку и инвентарь до стартовых.</p>
      <button onclick="window.RPG.adminResetPlayerSubmit()" class="w-full py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-xl font-black text-xs shadow-lg shadow-rose-600/30 active:scale-95 flex items-center justify-center gap-1">
        <span>🔄</span><span>Обнулить Прогресс Выбранного Игрока</span>
      </button>
    </div>`;
}

function renderAdminSlotsTabHTML(activeTestSlot) {
  return `
    <div class="p-2.5 rounded-xl bg-slate-800/80 border border-slate-700 flex items-center justify-between text-xs">
      <span class="text-slate-400 font-bold text-[11px]">Активный аккаунт:</span>
      <span class="font-black text-amber-300">${activeTestSlot ? `🧪 #${activeTestSlot}` : '👑 Основной Админ'}</span>
    </div>
    <div class="space-y-1.5">
      <span class="text-[10px] font-black uppercase text-slate-400 tracking-wider block">Быстрые слоты:</span>
      ${RPG_STATE.adminTestSlots.map(s => {
        const isCur = (!activeTestSlot && s.id === 'main') || (activeTestSlot === s.tg_id);
        return `<button onclick="window.RPG.switchAdminTestAccount('${s.id}')" class="w-full p-2 rounded-xl text-left text-xs font-black flex items-center justify-between border transition-all ${isCur ? 'bg-amber-500/20 border-amber-400 text-amber-300 shadow-md' : 'bg-slate-800/60 border-slate-700/60 text-slate-300 hover:bg-slate-700'}">
          <span>${s.name}</span>
          <span class="text-[9px] px-1.5 py-0.5 rounded ${isCur ? 'bg-amber-400 text-slate-950 font-extrabold' : 'bg-slate-700 text-slate-400'}">${isCur ? 'АКТИВЕН' : 'Войти →'}</span>
        </button>`;
      }).join('')}
    </div>
    <div class="pt-2 space-y-2">
      <button onclick="window.RPG.createCustomAdminTestAccount()" class="w-full py-2 rounded-xl bg-gradient-to-r from-sky-600 to-cyan-600 text-white font-black text-xs shadow-md active:scale-95 flex items-center justify-center gap-1.5">
        <span>➕</span><span>Создать аккаунт с кастомным ID</span>
      </button>
      ${activeTestSlot ? `<button onclick="window.RPG.switchAdminTestAccount('main')" class="w-full py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-amber-400 font-black text-xs shadow-sm active:scale-95 flex items-center justify-center gap-1.5">
        <span>👑</span><span>Вернуться на Основной Аккаунт</span>
      </button>` : ''}
    </div>`;
}

// === ADMIN ACTIONS CONTROLLER ===
window.RPG = window.RPG || {};
window.RPG.setAdminSubTab = function(tab) {
  window._adminSubTab = tab;
  if (tab === "actions") {
    if (!window._adminPlayersList) window.RPG.refreshAdminPlayers();
    if (!window._adminCatalogItems) window.RPG.fetchAdminCatalog();
  }
  updateAdminModalDOM();
};

window.RPG.applyAdminCustomTarget = function() {
  const inp = document.getElementById("admin-custom-target-input");
  if (inp && inp.value) {
    window._adminSelectedTarget = inp.value.trim();
    alert(`Целевой игрок выбран: ${window._adminSelectedTarget}`);
    updateAdminModalDOM();
  }
};

window.RPG.refreshAdminPlayers = async function() {
  if (window._fetchingAdminPlayers) return;
  window._fetchingAdminPlayers = true;
  try {
    const apiObj = window.api || (typeof api !== "undefined" ? api : null);
    let res = null;
    if (apiObj?.getAdminRpgPlayers) { try { res = await apiObj.getAdminRpgPlayers(); } catch (err) { console.warn(err); } }
    if (!res) { try { res = await fetch("/api/rpg/admin/players").then(r => r.json()); } catch (err) { console.warn(err); } }
    if (res?.players?.length > 0) { window._adminPlayersList = res.players; updateAdminModalDOM(); }
  } catch (e) { console.warn("Failed to fetch admin players:", e); }
  finally { window._fetchingAdminPlayers = false; }
};

window.RPG.fetchAdminCatalog = async function() {
  if (!window._adminCatalogItems || window._adminCatalogItems.length === 0) window._adminCatalogItems = window._DEFAULT_RPG_CATALOG || [];
  if (window._fetchingAdminCatalog) return;
  window._fetchingAdminCatalog = true;
  try {
    const apiObj = window.api || (typeof api !== "undefined" ? api : null);
    let res = null;
    if (apiObj?.getAdminItemsCatalog) { try { res = await apiObj.getAdminItemsCatalog(); } catch (err) { console.warn(err); } }
    if (!res) { try { res = await fetch("/api/rpg/admin/items_catalog").then(r => r.json()); } catch (err) { console.warn(err); } }
    if (res?.items?.length > 0) { window._adminCatalogItems = res.items; updateAdminModalDOM(); }
  } catch (e) { console.warn("Failed to fetch admin items catalog:", e); }
  finally { window._fetchingAdminCatalog = false; }
};

window.RPG.onAdminCatalogItemChange = function(itemName) {
  if (!itemName) return;
  const catalog = window._adminCatalogItems || [];
  const found = catalog.find(it => it.name === itemName);
  if (found && found.rarity) {
    const sel = document.getElementById("admin-item-rarity-select");
    if (sel) sel.value = found.rarity;
  }
};

function applyAdminProfileUpdate(res, target) {
  if (!res || !res.profile) return;
  const p = res.profile;
  const curUid = String(RPG_STATE.profile?.user_id || "");
  const curTg = String(RPG_STATE.profile?.tg_id || localStorage.getItem("admin_test_tg_uid") || localStorage.getItem("cached_tg_uid") || "");
  const tgtStr = target ? String(target).trim() : "";
  const isMe = !tgtStr || tgtStr === curUid || tgtStr === curTg || String(p.user_id) === curUid || (p.tg_id && String(p.tg_id) === curTg);

  if (isMe) {
    RPG_STATE.profile = p;
    if (typeof syncArenaPlayerStats === "function") syncArenaPlayerStats();
    const topNav = document.getElementById("rpg-top-nav");
    if (topNav && typeof renderTopNavBarHTML === "function") topNav.outerHTML = renderTopNavBarHTML();
    const viewContainer = document.getElementById("rpg-view-container");
    if (viewContainer && RPG_STATE.activeTab === "hero" && typeof renderHeroViewHTML === "function") viewContainer.innerHTML = renderHeroViewHTML();
  }
  if (window._adminPlayersList && window._adminPlayersList.length > 0) {
    const pItem = window._adminPlayersList.find(x => String(x.tg_id) === tgtStr || String(x.user_id) === tgtStr || (isMe && (String(x.user_id) === curUid || String(x.tg_id) === curTg)));
    if (pItem) {
      if (p.gold !== undefined) pItem.gold = p.gold;
      if (p.gems !== undefined) pItem.gems = p.gems;
      if (p.level !== undefined) pItem.level = p.level;
    }
  }
}

window.RPG.adminGiveGold = async function(amount) {
  try {
    const target = window._adminSelectedTarget || null;
    const apiObj = window.api || (typeof api !== "undefined" ? api : null);
    const res = await apiObj.adminGiveGold({ target, amount });
    applyAdminProfileUpdate(res, target);
    showAdminNotice(res.message || "Золото успешно выдано!");
    window.RPG.refreshAdminPlayers();
    updateAdminModalDOM();
  } catch (e) {
    showAdminNotice(e.message || "Ошибка выдачи золота");
  }
};

window.RPG.adminGiveGoldCustom = function() {
  const val = parseInt(document.getElementById("admin-gold-custom-input")?.value || 0, 10);
  if (!val) return showAdminNotice("Введите корректную сумму золота");
  window.RPG.adminGiveGold(val);
};

window.RPG.adminGiveGems = async function(amount) {
  try {
    const target = window._adminSelectedTarget || null;
    const apiObj = window.api || (typeof api !== "undefined" ? api : null);
    const res = await apiObj.adminGiveGems({ target, amount });
    applyAdminProfileUpdate(res, target);
    showAdminNotice(res.message || "Кристаллы успешно выданы!");
    window.RPG.refreshAdminPlayers();
    updateAdminModalDOM();
  } catch (e) {
    showAdminNotice(e.message || "Ошибка выдачи кристаллов");
  }
};

window.RPG.adminGiveGemsCustom = function() {
  const val = parseInt(document.getElementById("admin-gems-custom-input")?.value || 0, 10);
  if (!val) return showAdminNotice("Введите корректную сумму кристаллов");
  window.RPG.adminGiveGems(val);
};

window.RPG.adminSetLevel = async function(lvl) {
  try {
    const target = window._adminSelectedTarget || null;
    const apiObj = window.api || (typeof api !== "undefined" ? api : null);
    const res = await apiObj.adminSetLevel({ target, level: lvl });
    applyAdminProfileUpdate(res, target);
    showAdminNotice(res.message || `Уровень успешно изменен на ${lvl}!`);
    window.RPG.refreshAdminPlayers();
    updateAdminModalDOM();
  } catch (e) {
    showAdminNotice(e.message || "Ошибка изменения уровня");
  }
};

window.RPG.adminSetLevelCustom = function() {
  const val = parseInt(document.getElementById("admin-level-custom-input")?.value || 0, 10);
  if (!val || val < 1 || val > 50) return showAdminNotice("Введите уровень от 1 до 50");
  window.RPG.adminSetLevel(val);
};

window.RPG.adminGiveItemSubmit = async function() {
  try {
    const target = window._adminSelectedTarget || null;
    const rarity = document.getElementById("admin-item-rarity-select")?.value || "legendary";
    const lvl = parseInt(document.getElementById("admin-item-level-input")?.value || "10", 10);
    const itemName = document.getElementById("admin-catalog-item-select")?.value || null;
    const apiObj = window.api || (typeof api !== "undefined" ? api : null);
    const res = await apiObj.adminGiveItem({ target, rarity, level: lvl, item_name: itemName });
    applyAdminProfileUpdate(res, target);
    showAdminNotice(res.message || "Предмет успешно выдан в инвентарь!");
    updateAdminModalDOM();
  } catch (e) {
    showAdminNotice(e.message || "Ошибка выдачи предмета");
  }
};

window.RPG.adminResetPlayerSubmit = async function() {
  const targetLabel = window._adminSelectedTarget ? `игрока [${window._adminSelectedTarget}]` : "ТЕКУЩЕГО аккаунта";
  const ok = confirm(`ВНИМАНИЕ! Вы уверены, что хотите ПОЛНОСТЬЮ ОБНУЛИТЬ прогресс ${targetLabel} до 1 уровня?\nЭто действие необратимо!`);
  if (!ok) return;

  try {
    const target = window._adminSelectedTarget || null;
    const apiObj = window.api || (typeof api !== "undefined" ? api : null);
    const res = await apiObj.adminResetPlayer({ target });
    applyAdminProfileUpdate(res, target);
    showAdminNotice(res.message || "Прогресс игрока успешно сброшен!");
    window.RPG.refreshAdminPlayers();
    updateAdminModalDOM();
  } catch (e) {
    showAdminNotice(e.message || "Ошибка сброса игрока");
  }
};

// Immediate pre-fetch in background on script initialization
setTimeout(() => {
  if (window.RPG) {
    if (window.RPG.fetchAdminCatalog) window.RPG.fetchAdminCatalog();
    if (window.RPG.refreshAdminPlayers) window.RPG.refreshAdminPlayers();
  }
}, 300);

  window.RPG = {
    init: initRPG,
    setSubTab: setSubTab,
    setFarmMode: setFarmMode,
    loadProfile: loadProfile,
    selectHero: selectHero,
    openHeroPicker: () => {
      if (RPG_STATE.profile) RPG_STATE.profile.hero_class = null;
      renderRoot();
    },
    upgradeStat: upgradeStat,
    openItemModal: openItemModal,
    closeItemModal: closeItemModal,
    equipItem: equipItem,
    unequipItem: unequipItem,
    useConsumable: useConsumable,
    openShopModal: openShopModal,
    closeShopModal: closeShopModal,
    reloadShopCatalog: reloadShopCatalog,
    setShopFilter: setShopFilter,
    buyShopItem: buyShopItem,
    openSlotFilterModal: openSlotFilterModal,
    closeSlotFilterModal: closeSlotFilterModal,
    openForge: (uid) => {
      if (uid && typeof uid === 'string') {
        openForge(uid);
      } else {
        const p = RPG_STATE.profile;
        const eq = p?.equipment || {};
        const firstItem = eq.slot_1 || eq.slot_2 || eq.slot_3 || eq.slot_4 || eq.slot_5 || eq.slot_6;
        if (firstItem) openForge(firstItem.uid);
        else alert("Сначала наденьте предмет или выберите его из инвентаря!");
      }
    },
    closeForgeModal: closeForgeModal,
    forgeCurrentItem: forgeCurrentItem,
    sellItem: sellItem,
    toggleItemSelection: toggleItemSelection,
    toggleItemSelectionMode: toggleItemSelectionMode,
    handleInventoryItemClick: handleInventoryItemClick,
    selectAllByRarity: selectAllByRarity,
    clearItemSelection: clearItemSelection,
    sellSelectedItems: sellSelectedItems,
    resetCharacter: resetCharacter,
    slashWave: slashWave,
    toggleAutoFarm: toggleAutoFarm,
    toggleBossPartyMode: toggleBossPartyMode,
    bossArenaDodgeAction: playerBossArenaDodge,
    // Admin Dev Panel
    toggleAdminModal: toggleAdminModal,
    switchAdminTestAccount: switchAdminTestAccount,
    createCustomAdminTestAccount: createCustomAdminTestAccount,
    resetCurrentTestAccount: resetCurrentTestAccount,
    // Chest Modal
    claimChestReward: claimChestReward,
    closeChestModal: closeChestModal,
    // Arena Controls
    playerSlashAttackAction: playerSlashAttack,
    castSkill1Action: castPlayerSkill1,
    castUltimateAction: castPlayerUltimate,
    useActiveItemAction: useActiveItemAction,
    getEquippedActiveItems: getEquippedActiveItems,
    usePotionAction: usePlayerPotion,
    playerDashAction: () => playerPerformDash(),
    playerBlockAction: playerBlock,
    hitQTEAction: hitQTE,
    confirmNextWaveAction: confirmNextWave,
    retryCurrentFloorAction: retryCurrentFloor,
    toggleArenaAutoAttack: () => {
      ARENA.player.autoAttack = !ARENA.player.autoAttack;
      const btn = document.getElementById("rpg-auto-attack-btn");
      if (btn) {
        btn.innerText = `Авто-удар: ${ARENA.player.autoAttack ? "ВКЛ" : "ВЫКЛ"}`;
        if (ARENA.player.autoAttack) {
          btn.className = "px-2.5 py-1 rounded-xl text-xs font-black transition-all bg-amber-500/20 text-amber-500 border border-amber-500/40";
        } else {
          btn.className = "px-2.5 py-1 rounded-xl text-xs font-black transition-all bg-slate-200 dark:bg-slate-700 text-slate-500";
        }
      }
      triggerHaptic("light");
    },
    playerDashRollAction: () => {
      playerPerformDashRoll();
    },
    toggleTopDownArenaMode: () => {
      toggleTopDownArenaMode();
    },
    toggleArenaWaveConfirm: () => {
      ARENA.autoAdvanceWaves = !ARENA.autoAdvanceWaves;
      try {
        localStorage.setItem("rpg_arena_auto_advance_waves", ARENA.autoAdvanceWaves ? "true" : "false");
      } catch (e) {}
      const btn = document.getElementById("rpg-wave-confirm-btn");
      if (btn) {
        btn.innerText = `Подтверждение волн: ${ARENA.autoAdvanceWaves ? "ВЫКЛ ⏩" : "ВКЛ ⏸️"}`;
        if (ARENA.autoAdvanceWaves) {
          btn.className = "px-2.5 py-1 rounded-xl text-xs font-black transition-all bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-sm";
          btn.title = "Подтверждение волн отключено: переход к следующей волне происходит автоматически";
        } else {
          btn.className = "px-2.5 py-1 rounded-xl text-xs font-black transition-all bg-slate-200 dark:bg-slate-700 text-slate-500";
          btn.title = "Подтверждение волн включено: требуется нажимать продолжить";
        }
      }
      triggerHaptic("light");
      if (ARENA.autoAdvanceWaves && ARENA.waveState === "prompt" && !RPG_STATE.activeChestModal) {
        confirmNextWave();
      }
    },
    // Co-op
    loadCoopBosses: loadCoopBosses,
    createCoopRaid: createCoopRaid,
    joinCoopRoom: joinCoopRoom,
    sendCoopAction: sendCoopAction,
    leaveCoopRoom: leaveCoopRoom,
    addCoopBot: addCoopBot,
    startRaidBossActionBattle: startRaidBossActionBattle,
    exitRaidBossBattle: exitRaidBossBattle,
    // PvP
    loadClassmates: loadClassmates,
    challengeClassmate: challengeClassmate,
    sendPvPAction: sendPvPAction,
    leavePvPRoom: leavePvPRoom,
    renderRoot: renderRoot
  };
})();
