import time
import random
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class RPGPvPRoom:
    """Пошаговая онлайн-дуэль между двумя одноклассниками со статами их персонажей."""
    def __init__(
        self,
        room_id: str,
        host_tg_id: int,
        host_name: str,
        opponent_tg_id: Optional[int] = None,
        opponent_name: Optional[str] = None,
        hero_data: Optional[Dict[str, Any]] = None
    ):
        self.room_id = room_id
        self.game_type = "rpg_duel"
        self.host_tg_id = host_tg_id
        self.host_name = host_name
        self.opponent_tg_id = opponent_tg_id
        self.opponent_name = opponent_name or "Соперник"

        self.status = "waiting"  # waiting, playing, finished, rejected, canceled
        self.turn = "host"       # "host" or "opponent"
        self.winner = None       # "host", "opponent", "draw"
        self.rematch_requested_by = None
        self.combat_log: List[Dict[str, Any]] = []

        self.players = {
            "host": {
                "tg_id": host_tg_id,
                "name": host_name,
                "class_name": "Герой",
                "class_icon": "🛡️",
                "level": 1,
                "hp": 120,
                "hp_max": 120,
                "mp": 50,
                "mp_max": 50,
                "min_atk": 12,
                "max_atk": 18,
                "defense": 8,
                "crit_chance": 10,
                "dodge_chance": 5,
                "skill": {"name": "Спецудар", "icon": "💥", "mp_cost": 15},
                "is_defending": False,
                "potions": 2,
                "loaded": False
            },
            "opponent": {
                "tg_id": opponent_tg_id,
                "name": opponent_name or "Соперник",
                "class_name": "Герой",
                "class_icon": "🔮",
                "level": 1,
                "hp": 120,
                "hp_max": 120,
                "mp": 50,
                "mp_max": 50,
                "min_atk": 12,
                "max_atk": 18,
                "defense": 8,
                "crit_chance": 10,
                "dodge_chance": 5,
                "skill": {"name": "Спецудар", "icon": "💥", "mp_cost": 15},
                "is_defending": False,
                "potions": 2,
                "loaded": False
            }
        }
        if hero_data:
            self.sync_character_data("host", hero_data)

        self.created_at = time.time()
        self.last_activity = time.time()

    def set_opponent(self, user_tg_id: int, user_name: str, hero_data: Optional[Dict[str, Any]] = None):
        self.opponent_tg_id = user_tg_id
        if user_name:
            self.opponent_name = user_name
        self.players["opponent"]["tg_id"] = user_tg_id
        self.players["opponent"]["name"] = user_name or "Соперник"
        if hero_data:
            self.sync_character_data("opponent", hero_data)

    def sync_character_data(self, role: str, profile_dict: Dict[str, Any]):
        """Injects loaded RPGCharacter stats into the active duel room."""
        if role not in self.players or not profile_dict:
            return
        p = self.players[role]
        stats = profile_dict.get("stats", {})
        p["name"] = profile_dict.get("user_name") or p["name"]
        p["class_name"] = profile_dict.get("class_name", "Герой")
        p["class_icon"] = profile_dict.get("class_icon", "🛡️")
        p["level"] = profile_dict.get("level", 1)
        p["hp_max"] = max(50, stats.get("hp_max", 120))
        p["hp"] = p["hp_max"]
        p["mp_max"] = max(20, stats.get("mp_max", 50))
        p["mp"] = p["mp_max"]
        p["min_atk"] = stats.get("min_atk", 10)
        p["max_atk"] = stats.get("max_atk", 16)
        p["defense"] = stats.get("defense", 6)
        p["crit_chance"] = stats.get("crit_chance", 10)
        p["dodge_chance"] = stats.get("dodge_chance", 5)
        p["skill"] = stats.get("skill", {"name": "Удар", "icon": "💥", "mp_cost": 15})
        p["loaded"] = True

    def get_player_role(self, user_tg_id: int) -> Optional[str]:
        if user_tg_id == self.host_tg_id:
            return "host"
        if self.opponent_tg_id and user_tg_id == self.opponent_tg_id:
            return "opponent"
        return None

    def make_move(self, user_tg_id: int, action_data: Any) -> tuple[bool, str]:
        self.last_activity = time.time()
        if self.status != "playing":
            return False, "Дуэль не активна"

        role = self.get_player_role(user_tg_id)
        if not role:
            return False, "Вы не участник этой дуэли"

        if self.turn != role:
            return False, "Сейчас ход соперника"

        target_role = "opponent" if role == "host" else "host"
        attacker = self.players[role]
        defender = self.players[target_role]

        action = "attack"
        if isinstance(action_data, dict):
            action = action_data.get("action", "attack")
        elif isinstance(action_data, str):
            action = action_data

        attacker["is_defending"] = False

        if action == "defend":
            attacker["is_defending"] = True
            attacker["mp"] = min(attacker["mp_max"], attacker["mp"] + 12)
            self.combat_log.append({
                "actor": attacker["name"],
                "text": f"🛡️ {attacker['name']} встает в защитную стойку (-50% урона) и восстанавливает +12 MP!",
                "type": "defend"
            })
            self.turn = target_role
            return True, "Защитная стойка принята"

        if action == "potion":
            if attacker["potions"] <= 0:
                return False, "Зелья здоровья закончились!"
            attacker["potions"] -= 1
            heal = int(attacker["hp_max"] * 0.45)
            attacker["hp"] = min(attacker["hp_max"], attacker["hp"] + heal)
            self.combat_log.append({
                "actor": attacker["name"],
                "text": f"🧪 {attacker['name']} выпивает зелье и восстанавливает +{heal} HP!",
                "type": "heal"
            })
            self.turn = target_role
            return True, "Зелье выпито"

        # Check Dodge
        dodge_roll = random.randint(1, 100)
        if dodge_roll <= defender["dodge_chance"] and not defender["is_defending"]:
            self.combat_log.append({
                "actor": defender["name"],
                "text": f"💨 {defender['name']} ловко уворачивается от атаки {attacker['name']}!",
                "type": "dodge"
            })
            self.turn = target_role
            return True, "Соперник увернулся"

        is_skill = (action == "skill")
        base_dmg = random.randint(attacker["min_atk"], attacker["max_atk"])

        if is_skill:
            skill_cost = attacker["skill"].get("mp_cost", 15)
            if attacker["mp"] < skill_cost:
                return False, f"Недостаточно маны для спецудара! Нужно {skill_cost} MP."
            attacker["mp"] -= skill_cost
            base_dmg = int(base_dmg * 1.8)

        # Crit check
        is_crit = (random.randint(1, 100) <= attacker["crit_chance"])
        if is_crit:
            base_dmg = int(base_dmg * 1.6)

        # Hyperbolic defense reduction (Dota 2 / WC3 formula)
        eff_def = max(0, defender["defense"] * (2 if defender["is_defending"] else 1))
        dr = (eff_def * 0.05) / (1.0 + eff_def * 0.05)
        final_dmg = max(5, int(base_dmg * (1.0 - dr)))

        defender["hp"] = max(0, defender["hp"] - final_dmg)

        skill_icon = attacker["skill"].get("icon", "💥") if is_skill else "⚔️"
        crit_str = " 🔥 КРИТИЧЕСКИЙ УДАР!" if is_crit else ""
        def_str = " (соперник в блоке)" if defender["is_defending"] else ""
        act_name = attacker["skill"].get("name", "Спецудар") if is_skill else "обычную атаку"

        self.combat_log.append({
            "actor": attacker["name"],
            "text": f"{skill_icon} {attacker['name']} применяет {act_name} и наносит {final_dmg} урона{crit_str}{def_str}!",
            "type": "attack",
            "damage": final_dmg
        })

        if defender["hp"] <= 0:
            self.status = "finished"
            self.winner = role
            self.combat_log.append({
                "actor": "system",
                "text": f"🏆 {attacker['name']} одерживает победу в дуэли над {defender['name']}!",
                "type": "victory"
            })
        else:
            self.turn = target_role

        return True, "Ход выполнен"

    def request_rematch(self, user_tg_id: int) -> tuple[bool, str]:
        self.last_activity = time.time()
        role = self.get_player_role(user_tg_id)
        if not role:
            return False, "Вы не участник дуэли"

        if self.rematch_requested_by is None:
            self.rematch_requested_by = role
            return True, "Запрос на реванш отправлен"
        elif self.rematch_requested_by != role:
            self.rematch_requested_by = None
            self.status = "playing"
            self.winner = None
            self.turn = "host"
            for p in self.players.values():
                p["hp"] = p["hp_max"]
                p["mp"] = p["mp_max"]
                p["potions"] = 2
                p["is_defending"] = False
            self.combat_log.append({
                "actor": "system",
                "text": "⚔️ Реванш принят! Бой начался заново!",
                "type": "start"
            })
            return True, "Реванш начался"
        return True, "Ожидание подтверждения реванша"

    def resign(self, user_tg_id: int) -> tuple[bool, str]:
        role = self.get_player_role(user_tg_id)
        if not role or self.status != "playing":
            return False, "Нельзя сдаться"
        winner_role = "opponent" if role == "host" else "host"
        self.status = "finished"
        self.winner = winner_role
        self.combat_log.append({
            "actor": "system",
            "text": f"🏳️ {self.players[role]['name']} сдается в дуэли!",
            "type": "victory"
        })
        return True, "Вы сдались в дуэли"

    def to_dict(self, viewer_tg_id: Optional[int] = None) -> Dict[str, Any]:
        viewer_role = self.get_player_role(viewer_tg_id) if viewer_tg_id else None
        return {
            "room_id": self.room_id,
            "game_type": "rpg_duel",
            "status": self.status,
            "turn": self.turn,
            "winner": self.winner,
            "host_name": self.host_name,
            "opponent_name": self.opponent_name,
            "players": self.players,
            "combat_log": self.combat_log[-12:],
            "rematch_requested_by": self.rematch_requested_by,
            "your_role": viewer_role,
            "is_your_turn": (self.status == "playing" and self.turn == viewer_role)
        }
