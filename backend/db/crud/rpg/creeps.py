from typing import Dict, Any, List

# ==============================================================================
# CREEPS & DUNGEON BOSSES (КРИПЫ И БОССЫ ПОДЗЕМЕЛЬЯ)
# ==============================================================================

NATAR_CREEPS_POOL = [
    # --- НОВЫЕ КРИПЫ ВЫСОКИХ ЭТАЖЕЙ (20, 40, 50, 80, 100, 200+) ---
    {"name": "Варлок Легиона", "icon": "🔮", "base_hp": 320, "base_atk": 38, "base_def": 8, "gold": 14, "xp": 18, "floor_min": 20},
    {"name": "Железный Голем", "icon": "🗿", "base_hp": 550, "base_atk": 42, "base_def": 24, "gold": 16, "xp": 22, "floor_min": 20},
    {"name": "Адская Гончая", "icon": "🐕", "base_hp": 260, "base_atk": 45, "base_def": 6, "gold": 12, "xp": 16, "floor_min": 20},
    {"name": "Некромант Катакомб", "icon": "💀", "base_hp": 480, "base_atk": 52, "base_def": 10, "gold": 22, "xp": 30, "floor_min": 40},
    {"name": "Теневой Ассасин", "icon": "🗡️", "base_hp": 380, "base_atk": 65, "base_def": 12, "gold": 24, "xp": 34, "floor_min": 40},
    {"name": "Костяной Страж", "icon": "🛡️", "base_hp": 650, "base_atk": 48, "base_def": 30, "gold": 26, "xp": 36, "floor_min": 40},
    {"name": "Кентавр-Завоеватель", "icon": "🐎", "base_hp": 900, "base_atk": 60, "base_def": 35, "gold": 38, "xp": 48, "floor_min": 50},
    {"name": "Инфернальный Дракон", "icon": "🐉", "base_hp": 850, "base_atk": 75, "base_def": 25, "gold": 42, "xp": 54, "floor_min": 50},
    {"name": "Пламенный Маг", "icon": "🔥", "base_hp": 720, "base_atk": 82, "base_def": 18, "gold": 40, "xp": 52, "floor_min": 50},
    {"name": "Повелитель Пустоты", "icon": "👁️", "base_hp": 1200, "base_atk": 90, "base_def": 30, "gold": 65, "xp": 85, "floor_min": 80},
    {"name": "Абиссальный Бегемот", "icon": "👹", "base_hp": 1600, "base_atk": 110, "base_def": 40, "gold": 80, "xp": 100, "floor_min": 80},
    {"name": "Вестник Разлома", "icon": "⚡", "base_hp": 1100, "base_atk": 125, "base_def": 28, "gold": 75, "xp": 95, "floor_min": 80},
    {"name": "Древний Титан Скал", "icon": "🏔️", "base_hp": 2800, "base_atk": 140, "base_def": 50, "gold": 130, "xp": 170, "floor_min": 100},
    {"name": "Архимаг Хаоса", "icon": "🧙", "base_hp": 2200, "base_atk": 160, "base_def": 35, "gold": 140, "xp": 180, "floor_min": 100},
    {"name": "Паладин Падших", "icon": "✨", "base_hp": 2500, "base_atk": 130, "base_def": 55, "gold": 135, "xp": 175, "floor_min": 100},
    {"name": "Страж Апокалипсиса", "icon": "🔥", "base_hp": 5500, "base_atk": 250, "base_def": 70, "gold": 260, "xp": 360, "floor_min": 200},
    {"name": "Астральный Призрак", "icon": "👻", "base_hp": 4800, "base_atk": 300, "base_def": 45, "gold": 290, "xp": 410, "floor_min": 200},
    {"name": "Космический Разрушитель", "icon": "🌌", "base_hp": 6200, "base_atk": 340, "base_def": 60, "gold": 320, "xp": 450, "floor_min": 200},
    {"name": "Линейный Мечник", "icon": "🗡️", "base_hp": 120, "base_atk": 12, "base_def": 3, "gold": 4, "xp": 6},
    {"name": "Линейный Стрелок", "icon": "🏹", "base_hp": 90, "base_atk": 16, "base_def": 1, "gold": 5, "xp": 7},
    {"name": "Осадная Катапульта", "icon": "🚜", "base_hp": 260, "base_atk": 24, "base_def": 6, "gold": 8, "xp": 10},
    {"name": "Супер-Мечник Тьмы", "icon": "⚔️", "base_hp": 220, "base_atk": 22, "base_def": 8, "gold": 7, "xp": 9},
    {"name": "Лесной Волк Катакомб", "icon": "🐺", "base_hp": 160, "base_atk": 20, "base_def": 4, "gold": 5, "xp": 8},
    {"name": "Кентавр-Воитель", "icon": "🐎", "base_hp": 310, "base_atk": 26, "base_def": 9, "gold": 9, "xp": 12},
    {"name": "Адский Крушитель", "icon": "🐻", "base_hp": 380, "base_atk": 30, "base_def": 10, "gold": 10, "xp": 14},
    {"name": "Сатир-Осквернитель", "icon": "🐐", "base_hp": 240, "base_atk": 28, "base_def": 6, "gold": 8, "xp": 11}
]

NATAR_FLOOR_BOSSES = [
    {"name": "Мясник Катакомб", "icon": "🪝", "base_hp": 180000, "base_atk": 65, "base_def": 25, "gold": 220, "xp": 260},
    {"name": "Повелитель Теней", "icon": "💀", "base_hp": 260000, "base_atk": 80, "base_def": 30, "gold": 260, "xp": 310},
    {"name": "Древний Терзатель", "icon": "🔮", "base_hp": 380000, "base_atk": 98, "base_def": 35, "gold": 320, "xp": 380},
    {"name": "Дракон Инферно", "icon": "🐉", "base_hp": 540000, "base_atk": 120, "base_def": 42, "gold": 390, "xp": 460},
    {"name": "Огненный Демон", "icon": "🐲", "base_hp": 750000, "base_atk": 150, "base_def": 50, "gold": 480, "xp": 560},
    {"name": "Король Кракенов", "icon": "🐙", "base_hp": 1000000, "base_atk": 180, "base_def": 58, "gold": 580, "xp": 680},
    {"name": "Тёмный Жнец", "icon": "💀", "base_hp": 1300000, "base_atk": 220, "base_def": 65, "gold": 700, "xp": 820},
    {"name": "Высший Некромант", "icon": "🧟", "base_hp": 1700000, "base_atk": 260, "base_def": 72, "gold": 840, "xp": 980},
    {"name": "Архимаг Хаоса", "icon": "🧙‍♂️", "base_hp": 2200000, "base_atk": 310, "base_def": 80, "gold": 1000, "xp": 1180},
    {"name": "Тёмный Рыцарь", "icon": "🐎", "base_hp": 2800000, "base_atk": 365, "base_def": 90, "gold": 1200, "xp": 1400},
    {"name": "Тёмный Терзатель Бездны", "icon": "💎", "base_hp": 3500000, "base_atk": 425, "base_def": 100, "gold": 1450, "xp": 1680},
    {"name": "Владыка Преисподней", "icon": "👹", "base_hp": 4300000, "base_atk": 490, "base_def": 112, "gold": 1750, "xp": 2000},
    {"name": "Древний Бегемот", "icon": "🦣", "base_hp": 5200000, "base_atk": 560, "base_def": 125, "gold": 2100, "xp": 2400},
    {"name": "Призрачный Дракон", "icon": "👻", "base_hp": 6300000, "base_atk": 640, "base_def": 140, "gold": 2500, "xp": 2850},
    {"name": "Космический Ужас", "icon": "🌌", "base_hp": 7800000, "base_atk": 740, "base_def": 160, "gold": 3000, "xp": 3400}
]

# Backwards compat aliases
DOTA_CREEPS_POOL = NATAR_CREEPS_POOL
DOTA_FLOOR_BOSSES = NATAR_FLOOR_BOSSES

# ==============================================================================
# 6.2. КАТАЛОГ КРИПОВ DOTA 2 (GDD 3.0.0-ULTIMATE, ТОМ VI)
# ==============================================================================

DOTA_BESTIARY_CATALOG: Dict[str, Dict[str, Any]] = {
    "melee_creep": {
        "id": "melee_creep",
        "name": "Линейный Мечник (Melee Creep)",
        "role": "melee",
        "icon": "🗡️",
        "hp": 280,
        "attack": 24,
        "armor": 2,
        "speed": 160,
        "attack_range": 60,
        "attack_cooldown": 1.0,
        "behavior": "boids_swarm",
        "desc": "Бежит толпой на ближайшего игрока по алгоритму стаи Boids."
    },
    "ranged_creep": {
        "id": "ranged_creep",
        "name": "Линейный Маг (Ranged Creep)",
        "role": "ranged",
        "icon": "🔮",
        "hp": 180,
        "attack": 36,
        "armor": 0,
        "speed": 140,
        "attack_range": 320,
        "attack_cooldown": 1.2,
        "behavior": "kite_ranged",
        "projectile_speed": 400,
        "desc": "Держит дистанцию 320px, стреляет пулями магии."
    },
    "mega_creep": {
        "id": "mega_creep",
        "name": "Мега-крип (Mega Creep)",
        "role": "heavy",
        "icon": "⚔️",
        "hp": 1400,
        "attack": 95,
        "armor": 14,
        "speed": 150,
        "attack_range": 70,
        "attack_cooldown": 1.1,
        "micro_stun_immune": True,
        "desc": "Невосприимчив к легкому микро-стану, наносит сокрушительный урон."
    },
    "centaur_conqueror": {
        "id": "centaur_conqueror",
        "name": "Нейтральный Кентавр-Завоеватель",
        "role": "neutral_bruiser",
        "icon": "🐎",
        "hp": 950,
        "attack": 55,
        "armor": 8,
        "speed": 155,
        "attack_range": 80,
        "attack_cooldown": 1.2,
        "ability": {
            "id": "war_stomp",
            "name": "War Stomp",
            "radius": 160,
            "damage": 120,
            "stun_duration": 1.5,
            "cooldown": 8.0,
            "trigger_distance": 160
        },
        "desc": "При сближении игрока топает копытом (War Stomp R=160px), станит на 1.5с."
    },
    "alpha_wolf": {
        "id": "alpha_wolf",
        "name": "Нейтральный Альфа-Волк",
        "role": "neutral_support",
        "icon": "🐺",
        "hp": 600,
        "attack": 40,
        "armor": 5,
        "speed": 170,
        "attack_range": 70,
        "attack_cooldown": 1.0,
        "aura": {
            "id": "pack_leader",
            "name": "Pack Leader (Вожак стаи)",
            "damage_bonus_pct": 30.0,
            "radius": 450,
            "desc": "Излучает ауру +30% урона всем союзным крипам в комнате."
        },
        "desc": "Излучает ауру +30% урона всем крипам в комнате."
    },
    "satyr_tormenter": {
        "id": "satyr_tormenter",
        "name": "Нейтральный Сатир-Истязатель",
        "role": "neutral_caster",
        "icon": "🐐",
        "hp": 800,
        "attack": 45,
        "armor": 6,
        "speed": 135,
        "attack_range": 200,
        "attack_cooldown": 1.3,
        "ability": {
            "id": "shockwave",
            "name": "Shockwave (Ударная волна)",
            "damage": 260,
            "range": 800,
            "width": 100,
            "cooldown": 10.0,
            "desc": "Выпускает гигантскую красную волну через весь зал на 260 урона."
        },
        "desc": "Выпускает гигантскую красную волну (Shockwave) через весь зал на 260 урона."
    },
    "mud_golem": {
        "id": "mud_golem",
        "name": "Грязевой Голем",
        "role": "neutral_splitter",
        "icon": "🗿",
        "hp": 700,
        "attack": 35,
        "armor": 10,
        "speed": 130,
        "attack_range": 70,
        "attack_cooldown": 1.2,
        "on_death": {
            "action": "split_into_shards",
            "count": 2,
            "spawn_creep_id": "shard_golem"
        },
        "desc": "При смерти взрывается и распадается на 2 маленьких големов, бросающих камни со станом."
    },
    "shard_golem": {
        "id": "shard_golem",
        "name": "Малый Грязевой Голем",
        "role": "neutral_minion",
        "icon": "🪨",
        "hp": 250,
        "attack": 20,
        "armor": 4,
        "speed": 145,
        "attack_range": 240,
        "attack_cooldown": 1.0,
        "ability": {
            "id": "hurl_boulder",
            "name": "Hurl Boulder (Бросок камня)",
            "damage": 60,
            "stun_duration": 0.6,
            "cooldown": 6.0
        },
        "desc": "Осколок грязевого голема. Бросает камни с микро-станом."
    }
}

