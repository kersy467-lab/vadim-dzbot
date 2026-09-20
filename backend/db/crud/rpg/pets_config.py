from typing import Dict, Any

# ==============================================================================
# PETS CONFIGURATION & GACHA RATES (Volume VIII of GDD)
# ==============================================================================

MAX_PET_STARS = 5
MERGE_COST_GEMS = 10
HATCH_COST_GEMS = 50

PETS_CATALOG: Dict[str, Dict[str, Any]] = {
    "slime": {
        "id": "slime",
        "name": "Капельный Слайм",
        "icon": "💧",
        "rarity": "common",
        "base_hp_mult": 1.10,
        "base_gold_mult": 1.05,
        "base_dmg_mult": 1.05,
        "base_xp_mult": 1.05,
        "stars_scaling": 0.08,
        "skill_name": "Капля Исцеления",
        "skill_desc": "Лечит героя на 10% HP каждые 12с",
        "cooldown_base": 12.0,
    },
    "fairy": {
        "id": "fairy",
        "name": "Лесная Фея",
        "icon": "🧚",
        "rarity": "rare",
        "base_hp_mult": 1.15,
        "base_gold_mult": 1.10,
        "base_dmg_mult": 1.05,
        "base_xp_mult": 1.15,
        "stars_scaling": 0.08,
        "skill_name": "Пыльца Свободы",
        "skill_desc": "Снимает станы, дает +35% к скорости бега",
        "cooldown_base": 10.0,
    },
    "wolf": {
        "id": "wolf",
        "name": "Призрачный Волк",
        "icon": "🐺",
        "rarity": "epic",
        "base_hp_mult": 1.10,
        "base_gold_mult": 1.10,
        "base_dmg_mult": 1.25,
        "base_xp_mult": 1.15,
        "stars_scaling": 0.08,
        "skill_name": "Кровавый Укус",
        "skill_desc": "Накладывает кровотечение (400 ед./сек)",
        "cooldown_base": 8.0,
    },
    "dragon": {
        "id": "dragon",
        "name": "Золотой Дракон",
        "icon": "🐉",
        "rarity": "legendary",
        "base_hp_mult": 1.15,
        "base_gold_mult": 1.50,
        "base_dmg_mult": 1.30,
        "base_xp_mult": 1.10,
        "stars_scaling": 0.08,
        "skill_name": "Дыхание Богатства",
        "skill_desc": "Конус огня (1200 урона), +50% золота",
        "cooldown_base": 7.0,
    },
    "donkey": {
        "id": "donkey",
        "name": "Ослик-Курьер Доты",
        "icon": "🫏",
        "rarity": "mythic",
        "base_hp_mult": 1.20,
        "base_gold_mult": 1.35,
        "base_dmg_mult": 1.40,
        "base_xp_mult": 1.25,
        "stars_scaling": 0.08,
        "skill_name": "Курьерская Доставка",
        "skill_desc": "Носит дополнительный рюкзак на 6 предметов и усиливает урон группы на +40%",
        "cooldown_base": 6.0,
    },
    "phoenix": {
        "id": "phoenix",
        "name": "Пылающий Феникс",
        "icon": "🦅",
        "rarity": "immortal",
        "base_hp_mult": 1.35,
        "base_gold_mult": 1.35,
        "base_dmg_mult": 1.45,
        "base_xp_mult": 1.35,
        "stars_scaling": 0.08,
        "skill_name": "Сверхновая Защита",
        "skill_desc": "При получении смертельного урона дает щит неуязвимости на 3с",
        "cooldown_base": 30.0,
    },
}

PET_HATCH_RATES = {
    "common": 50.0,
    "rare": 30.0,
    "epic": 14.0,
    "legendary": 5.0,
    "mythic": 0.85,
    "immortal": 0.15,
}
