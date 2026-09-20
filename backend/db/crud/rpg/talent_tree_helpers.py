"""
Вспомогательные структуры, константы и функции для системы дерева талантов.
Включает логику сброса старых талантов и миграции на новую систему.
"""
from typing import Dict, Any

# Стоимость узла по тиру (в очках талантов)
TIER_COST = {1: 1, 2: 1, 3: 2, 4: 2, 5: 3}

# Уровень персонажа для открытия тира
TIER_UNLOCK_LEVEL = {1: 1, 2: 10, 3: 15, 4: 20, 5: 30}

BRANCH_LABELS = {
    "atk": {"name": "Атака", "icon": "🗡️", "color": "red"},
    "tank": {"name": "Выживание", "icon": "🛡️", "color": "blue"},
    "util": {"name": "Утилита", "icon": "✨", "color": "purple"},
    "flask": {"name": "Фляга", "icon": "🧪", "color": "emerald"},
}


def _node(branch: str, tier: int, name: str, icon: str,
          desc: str, effect: Dict[str, Any], req: str = None) -> Dict[str, Any]:
    """Вспомогательная функция для создания узла дерева."""
    node_id = f"{branch}_{tier}"
    return {
        "id": node_id,
        "branch": branch,
        "tier": tier,
        "name": name,
        "icon": icon,
        "desc": desc,
        "effect": effect,
        "cost": TIER_COST[tier],
        "req": req or (f"{branch}_{tier - 1}" if tier > 1 else None),
        "unlock_level": TIER_UNLOCK_LEVEL[tier],
    }


FLASK_BRANCH: Dict[str, Dict[str, Any]] = {
    "flask_1": _node("flask", 1, "Освежающий Глоток", "🧪",
                     "+350 к исцелению бутылочки, +5% от макс. HP",
                     {"flask_heal_flat": 350, "flask_heal_pct": 0.05}),
    "flask_2": _node("flask", 2, "Целебный Настой", "🍶",
                     "+800 к исцелению бутылочки, +10% от макс. HP, +60 MP",
                     {"flask_heal_flat": 800, "flask_heal_pct": 0.10, "flask_mana": 60}),
    "flask_3": _node("flask", 3, "Эликсир Стойкости", "🧃",
                     "+2000 к исцелению бутылочки, +15% от макс. HP, -1с перезарядки",
                     {"flask_heal_flat": 2000, "flask_heal_pct": 0.15, "flask_cd_reduct": 60}),
    "flask_4": _node("flask", 4, "Великая Алхимия", "✨",
                     "+4500 к исцелению бутылочки, +25% от макс. HP, +180 MP, -1с перезарядки",
                     {"flask_heal_flat": 4500, "flask_heal_pct": 0.25, "flask_mana": 180, "flask_cd_reduct": 60}),
    "flask_5": _node("flask", 5, "Живая Вода", "🌟",
                     "+12 000 к исцелению бутылочки, +40% от макс. HP. ✨ [ПЕРК] Снимает станы/замедления и ускоряет на 50% на 3с!",
                     {"flask_heal_flat": 12000, "flask_heal_pct": 0.40, "flask_mana": 300, "flask_cd_reduct": 60, "perk": "perk_divine_flask"}),
}


def is_node_available(node: Dict[str, Any], char_level: int,
                      purchased: Dict[str, int]) -> bool:
    """Проверяет, доступен ли узел для покупки."""
    if char_level < node["unlock_level"]:
        return False
    req = node.get("req")
    if req and not purchased.get(req, 0):
        return False
    return True


def get_hero_spent_talent_points(char: Any, hero_class: str, hero_tree_getter=None) -> int:
    """Возвращает суммарно потраченные очки талантов для конкретного героя."""
    talents = getattr(char, "talents", {}) or {}
    tree = talents.get("tree", {})
    hero_nodes = tree.get(hero_class, {})
    if not hero_nodes or not hero_tree_getter:
        return 0
    hero_tree = hero_tree_getter(hero_class)
    spent = 0
    for nid, bought in (hero_nodes or {}).items():
        if bought and nid in hero_tree:
            spent += hero_tree[nid].get("cost", 1)
    return spent


def get_hero_available_talent_points(char: Any, hero_class: str = None, hero_tree_getter=None) -> int:
    """
    Возвращает количество доступных очков талантов для текущего (или указанного) героя.
    Каждый герой имеет свой баланс очков из общего пула (level // 2), не отбирая очки у других героев.
    """
    if not hero_class:
        hero_class = str(getattr(char, "hero_class", "pudge") or "pudge").lower()
    char_level = getattr(char, "level", 1) or 1
    total_earned = char_level // 2
    spent = get_hero_spent_talent_points(char, hero_class, hero_tree_getter)
    return max(0, total_earned - spent)


def reset_old_talents_and_refund(char: Any, hero_tree_getter=None) -> bool:
    """
    Сбрасывает старые таланты Доты и старые пассивки (lifesteal/dodge/crit_mult/cooldown),
    гарантируя актуальный баланс очков для активного героя (1 очко за каждые 2 уровня за вычетом купленных узлов).
    """
    talents = dict(getattr(char, "talents", {}) or {})
    modified = False

    # 1. Возврат очков за старые 4 пассивки
    old_passives = ["lifesteal", "dodge", "crit_mult", "cooldown"]
    for key in old_passives:
        if key in talents:
            talents.pop(key, None)
            modified = True

    # 2. Удаление старых дота-талантов
    if "dota_talents" in talents:
        talents.pop("dota_talents", None)
        modified = True

    # 3. Пересчёт очков талантов по уровню персонажа для активного героя
    h_class = str(getattr(char, "hero_class", "pudge") or "pudge").lower()
    target_pts = get_hero_available_talent_points(char, h_class, hero_tree_getter)
    current_pts = getattr(char, "talent_points", 0) or 0
    if target_pts != current_pts:
        char.talent_points = target_pts
        modified = True

    if not talents.get("_talents_v2_migrated"):
        talents["_talents_v2_migrated"] = True
        modified = True

    if modified:
        char.talents = talents

    return modified

