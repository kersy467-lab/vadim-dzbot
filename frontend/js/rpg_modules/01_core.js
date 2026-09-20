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
