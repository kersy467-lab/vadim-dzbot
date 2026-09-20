import random
from typing import Optional, Dict, Any

BOTS = [
    {"name": "Свен (Бот-Рыцарь)", "class_name": "Рыцарь", "class_icon": "🛡️", "hp": 190, "mp": 50, "min_atk": 18, "max_atk": 26, "defense": 10},
    {"name": "Лина (Бот-Маг)", "class_name": "Маг", "class_icon": "🔮", "hp": 130, "mp": 90, "min_atk": 22, "max_atk": 32, "defense": 6},
    {"name": "Тракса (Бот-Лучник)", "class_name": "Следопыт", "class_icon": "🏹", "hp": 140, "mp": 60, "min_atk": 20, "max_atk": 28, "defense": 7}
]

def make_default_hero(tg_id: Optional[int], name: str, icon: str, cname: str, hp: int, mp: int, min_a: int, max_a: int, df: int) -> Dict[str, Any]:
    return {
        "tg_id": tg_id,
        "name": name,
        "class_name": cname,
        "class_icon": icon,
        "hp": hp,
        "hp_max": hp,
        "mp": mp,
        "mp_max": mp,
        "min_atk": min_a,
        "max_atk": max_a,
        "defense": df,
        "crit_chance": 10,
        "dodge_chance": 5,
        "skill": {"name": "Удар ярости", "icon": "💥", "mp_cost": 15},
        "is_defending": False,
        "potions": 2,
        "is_dead": False,
        "skill_cooldown": 0
    }

def add_bot_ally_to_room(room: Any) -> tuple[bool, str]:
    target_slot = None
    if room.players["player_2"]["name"] == "Свободный слот":
        target_slot = "player_2"
    elif room.players["player_3"]["name"] == "Свободный слот":
        target_slot = "player_3"
    if not target_slot:
        return False, "Все 3 слота в рейде уже заняты!"

    existing_names = [room.players[k].get("name") for k in ["host", "player_2", "player_3"]]
    available_bots = [bot for bot in BOTS if bot["name"] not in existing_names]
    b = random.choice(available_bots) if available_bots else random.choice(BOTS)
    host = room.players.get("host", {})
    b_hp = host.get("hp_max", b["hp"])
    b_mp = host.get("mp_max", b["mp"])
    b_min_atk = host.get("min_atk", b["min_atk"])
    b_max_atk = host.get("max_atk", b["max_atk"])
    b_def = host.get("defense", b["defense"])

    room.players[target_slot].update({
        "tg_id": -random.randint(100, 999),
        "name": b["name"],
        "class_name": b["class_name"],
        "class_icon": b["class_icon"],
        "hp": b_hp,
        "hp_max": b_hp,
        "mp": b_mp,
        "mp_max": b_mp,
        "min_atk": b_min_atk,
        "max_atk": b_max_atk,
        "defense": b_def,
        "is_bot": True,
        "is_dead": False
    })
    room.combat_log.append({
        "actor": "system",
        "text": f"🤝 Союзник {b['name']} вступил в рейд на помощь!",
        "type": "info"
    })
    return True, f"Союзник {b['name']} добавлен в рейд!"
