import time
import random
import logging
from typing import Optional, Dict, Any, List
from backend.api.rpg_bosses import RAID_BOSSES
from backend.api.rpg_coop_boss_turn import execute_boss_turn
from backend.api.rpg_coop_helpers import make_default_hero, add_bot_ally_to_room

logger = logging.getLogger(__name__)

class RPGCoopBossRoom:
    """Совместный рейд (соло 1v1 или группа до 3 одноклассников) против Рейдового Босса."""
    def __init__(
        self,
        room_id: str,
        host_tg_id: int,
        host_name: str,
        opponent_tg_id: Optional[int] = None,
        opponent_name: Optional[str] = None,
        boss_id: str = "roshan",
        is_solo: bool = False,
        hero_data: Optional[Dict[str, Any]] = None
    ):
        self.room_id = room_id
        self.game_type = "rpg_coop"
        self.host_tg_id = host_tg_id
        self.host_name = host_name
        self.is_solo = is_solo

        boss_tmpl = RAID_BOSSES.get(boss_id, RAID_BOSSES["roshan"])
        boss_max_hp = boss_tmpl["max_hp"]
        boss_atk_min = boss_tmpl["atk_min"]
        boss_atk_max = boss_tmpl["atk_max"]

        if is_solo:
            boss_max_hp = max(200, int(boss_max_hp * 0.45))
            boss_atk_min = max(8, int(boss_atk_min * 0.8))
            boss_atk_max = max(14, int(boss_atk_max * 0.8))

        self.boss = {
            "id": boss_tmpl["id"], "name": boss_tmpl["name"], "icon": boss_tmpl["icon"],
            "desc": boss_tmpl["desc"], "hp": boss_max_hp, "hp_max": boss_max_hp,
            "atk_min": boss_atk_min, "atk_max": boss_atk_max, "defense": boss_tmpl["defense"],
            "gold_reward": boss_tmpl["gold_reward"], "xp_reward": boss_tmpl["xp_reward"],
            "skills": boss_tmpl["skills"], "shield_active": False, "enraged": False, "phase": 1
        }
        self.victory_rewards = None
        actual_opp_id = opponent_tg_id if (not is_solo and opponent_tg_id and opponent_tg_id > 0) else None
        self.opponent_tg_id = actual_opp_id
        self.opponent_name = opponent_name if actual_opp_id else None

        self.status = "playing"
        self.turn = "host"
        self.winner = None
        self.combat_log: List[Dict[str, Any]] = []
        self.boss_target_index: int = 0

        p1 = make_default_hero(host_tg_id, host_name, "🛡️", "Рыцарь", 150, 50, 15, 22, 8)
        p2 = make_default_hero(actual_opp_id, opponent_name if actual_opp_id else "Свободный слот", "🔮", "Маг", 120, 80, 18, 26, 5)
        p3 = make_default_hero(None, "Свободный слот", "🏹", "Следопыт", 130, 60, 16, 24, 6)

        self.players = {"host": p1, "player_2": p2, "player_3": p3, "opponent": p2}
        if hero_data:
            self.sync_character_data("host", hero_data)

        self.created_at = time.time()
        self.last_activity = time.time()

    def add_bot_ally(self) -> tuple[bool, str]:
        return add_bot_ally_to_room(self)

    def add_coop_player(self, user_tg_id: int, user_name: str) -> tuple[bool, str]:
        self.last_activity = time.time()
        if user_tg_id == self.host_tg_id:
            return True, "Вы создатель рейда"

        if self.players["player_2"]["tg_id"] == user_tg_id or self.players["player_3"]["tg_id"] == user_tg_id:
            self.status = "playing"
            return True, "Успешное подключение"

        for slot, slot_num in [("player_2", 2), ("player_3", 3)]:
            if self.players[slot]["tg_id"] is None or self.players[slot]["tg_id"] <= 0:
                self.players[slot]["tg_id"] = user_tg_id
                self.players[slot]["name"] = user_name or f"Игрок {slot_num}"
                if slot == "player_2":
                    self.opponent_tg_id = user_tg_id
                    self.opponent_name = self.players[slot]["name"]
                self.status = "playing"
                return True, f"Подключен как Игрок {slot_num}"

        return False, "В рейде уже максимум 3 игрока"

    def sync_character_data(self, role: str, profile_dict: Dict[str, Any]):
        if role not in self.players or not profile_dict:
            return
        p = self.players[role]
        stats = profile_dict.get("stats", {})
        p["name"] = profile_dict.get("user_name") or p["name"]
        p["class_name"] = profile_dict.get("class_name", "Герой")
        p["class_icon"] = profile_dict.get("class_icon", "🛡️")
        p["hp_max"] = max(50, stats.get("hp_max", 130))
        p["hp"] = p["hp_max"]
        p["mp_max"] = max(20, stats.get("mp_max", 50))
        p["mp"] = p["mp_max"]
        p["min_atk"] = stats.get("min_atk", 12)
        p["max_atk"] = stats.get("max_atk", 18)
        p["defense"] = stats.get("defense", 6)
        p["crit_chance"] = stats.get("crit_chance", 10)
        p["dodge_chance"] = stats.get("dodge_chance", 5)
        p["skill"] = stats.get("skill", {"name": "Удар", "icon": "💥", "mp_cost": 15})

    def get_player_role(self, user_tg_id: Optional[int]) -> Optional[str]:
        if user_tg_id is None or user_tg_id == 0 or user_tg_id == self.host_tg_id:
            return "host"
        if self.players["player_2"].get("tg_id") == user_tg_id or (self.opponent_tg_id and user_tg_id == self.opponent_tg_id):
            return "player_2"
        if self.players["player_3"].get("tg_id") == user_tg_id:
            return "player_3"
        return "host"

    def boss_turn(self):
        execute_boss_turn(self)

    def make_move(self, user_tg_id: int, action_data: Any) -> tuple[bool, str]:
        self.last_activity = time.time()
        if self.status != "playing":
            return False, "Рейд не активен"

        raw_role = self.get_player_role(user_tg_id)
        if not raw_role:
            return False, "Вы не участник этого рейда"

        role = "player_2" if raw_role == "opponent" else raw_role
        turn_canon = "player_2" if self.turn == "opponent" else self.turn
        if turn_canon != role:
            return False, "Сейчас ход другого героя"

        hero = self.players[role]
        hero["is_defending"] = False
        action = action_data.get("action", "attack") if isinstance(action_data, dict) else (action_data or "attack")

        if action == "potion":
            if hero["potions"] <= 0:
                return False, "Зелья здоровья закончились!"
            hero["potions"] -= 1
            heal = int(hero["hp_max"] * 0.5)
            hero["hp"] = min(hero["hp_max"], hero["hp"] + heal)
            if hero.get("skill_cooldown", 0) > 0:
                hero["skill_cooldown"] -= 1
            self.combat_log.append({"actor": hero["name"], "text": f"🧪 {hero['name']} пьет зелье (+{heal} HP)!", "type": "heal"})
        elif action == "defend":
            hero["is_defending"] = True
            hero["mp"] = min(hero["mp_max"], hero["mp"] + 15)
            if hero.get("skill_cooldown", 0) > 0:
                hero["skill_cooldown"] -= 1
            self.combat_log.append({"actor": hero["name"], "text": f"🛡️ {hero['name']} встает в защиту (+15 MP)!", "type": "defend"})
        else:
            is_skill = (action == "skill")
            if is_skill:
                if hero.get("skill_cooldown", 0) > 0:
                    return False, f"Скилл перезаряжается! Осталось ходов: {hero['skill_cooldown']}"
                cost = hero["skill"].get("mp_cost", 15)
                if hero["mp"] < cost:
                    return False, f"Недостаточно маны! Нужно {cost} MP."
                hero["mp"] -= cost
                hero["skill_cooldown"] = 2
            elif hero.get("skill_cooldown", 0) > 0:
                hero["skill_cooldown"] -= 1

            base_dmg = random.randint(hero["min_atk"], hero["max_atk"])
            if is_skill:
                base_dmg = int(base_dmg * 2.0)
                if "исцеления" in hero["skill"].get("name", "").lower():
                    for k in ["host", "player_2", "player_3"]:
                        if self.players[k].get("tg_id"):
                            self.players[k]["hp"] = min(self.players[k]["hp_max"], self.players[k]["hp"] + 50)
                    self.combat_log.append({"actor": hero["name"], "text": "✨ Исцеление +50 HP всей команде!", "type": "heal"})

            is_crit = (random.randint(1, 100) <= hero["crit_chance"])
            if is_crit:
                base_dmg = int(base_dmg * 1.6)

            b_def = max(0, self.boss.get("defense", 10))
            dr = (b_def * 0.05) / (1.0 + b_def * 0.05)
            final_dmg = max(5, int(base_dmg * (1.0 - dr)))
            self.boss["hp"] = max(0, self.boss["hp"] - final_dmg)

            icon = hero["skill"].get("icon", "💥") if is_skill else "⚔️"
            crit_s = " 🔥 КРИТ!" if is_crit else ""
            self.combat_log.append({"actor": hero["name"], "text": f"{icon} {hero['name']} наносит {final_dmg} урона по {self.boss['name']}{crit_s}!", "type": "attack", "damage": final_dmg})

            if self.boss.get("shield_active") and final_dmg > 0:
                refl = max(6, int(final_dmg * 0.5))
                hero["hp"] = max(0, hero["hp"] - refl)
                self.combat_log.append({"actor": self.boss["name"], "text": f"🪞 Отражающий щит вернул {refl} урона в {hero['name']}!", "type": "boss_attack", "damage": refl})
                if hero["hp"] <= 0:
                    hero["is_dead"] = True
                    self.combat_log.append({"actor": "system", "text": f"💀 {hero['name']} погиб от отражения!", "type": "death"})

            if self.boss["hp"] > 0 and self.boss["hp"] <= int(self.boss["hp_max"] * 0.35) and not self.boss.get("enraged"):
                self.boss["enraged"] = True
                self.boss["atk_min"] = int(self.boss["atk_min"] * 1.4)
                self.boss["atk_max"] = int(self.boss["atk_max"] * 1.4)
                self.boss["phase"] = 3
                self.combat_log.append({"actor": self.boss["name"], "text": f"🔥 {self.boss['name']} ВПАДАЕТ В ЯРОСТЬ! +40% урона!", "type": "warning"})

        if self.boss["hp"] <= 0:
            self.status = "finished"
            self.winner = "heroes"
            self.combat_log.append({"actor": "system", "text": f"🎉 ПОБЕДА! Босс {self.boss['name']} повержен!", "type": "victory"})
            return True, "Босс повержен!"

        hero_keys = ["host", "player_2", "player_3"]
        active = [k for k in hero_keys if self.players[k].get("name") and self.players[k]["name"] != "Свободный слот" and not self.players[k].get("is_dead")]
        if not active:
            self.status = "finished"
            self.winner = "boss"
            return True, "Все герои погибли"

        if self.is_solo or len(active) <= 1:
            self.boss_turn()
            self.turn = "host"
            return True, "Действие выполнено"

        try:
            curr_idx = active.index(role)
        except ValueError:
            curr_idx = -1

        if curr_idx + 1 < len(active):
            self.turn = active[curr_idx + 1]
        else:
            self.boss_turn()
            rem = [k for k in hero_keys if self.players[k].get("name") and self.players[k]["name"] != "Свободный слот" and not self.players[k].get("is_dead")]
            self.turn = rem[0] if rem else "host"

        while self.turn != "host" and self.players.get(self.turn, {}).get("is_bot") and self.status == "playing":
            bot = self.players[self.turn]
            bdmg = random.randint(bot["min_atk"], bot["max_atk"])
            self.boss["hp"] = max(0, self.boss["hp"] - bdmg)
            self.combat_log.append({"actor": bot["name"], "text": f"⚔️ {bot['name']} бьет босса на {bdmg} урона!", "type": "attack", "damage": bdmg})
            if self.boss["hp"] <= 0:
                self.status = "finished"
                self.winner = "heroes"
                self.combat_log.append({"actor": "system", "text": f"🎉 ПОБЕДА! Босс {self.boss['name']} повержен!", "type": "victory"})
                break
            try:
                b_idx = active.index(self.turn)
            except ValueError:
                b_idx = -1
            if b_idx + 1 < len(active):
                self.turn = active[b_idx + 1]
            else:
                self.boss_turn()
                rem = [k for k in hero_keys if self.players[k].get("name") and self.players[k]["name"] != "Свободный слот" and not self.players[k].get("is_dead")]
                self.turn = rem[0] if rem else "host"

        return True, "Действие выполнено"

    def to_dict(self, viewer_tg_id: Optional[int] = None) -> Dict[str, Any]:
        hero_keys = ["host", "player_2", "player_3"]
        alive = [k for k in hero_keys if self.players[k].get("name") and self.players[k]["name"] != "Свободный слот" and not self.players[k].get("is_dead")]
        next_target = alive[self.boss_target_index % len(alive)] if alive else "host"
        viewer_role = self.get_player_role(viewer_tg_id) or "host"
        turn_canon = "player_2" if self.turn == "opponent" else self.turn
        viewer_canon = "player_2" if viewer_role == "opponent" else viewer_role
        is_your_turn = (self.status == "playing" and (turn_canon == viewer_canon or self.is_solo or viewer_canon == "host"))

        return {
            "room_id": self.room_id, "game_type": "rpg_coop", "status": self.status,
            "turn": self.turn, "winner": self.winner, "boss": self.boss, "boss_target": next_target,
            "max_players": 3,
            "player_count": len([k for k in hero_keys if self.players[k].get("name") and self.players[k]["name"] != "Свободный слот"]),
            "players": self.players,
            "coop_heroes": [self.players[k] for k in hero_keys if self.players[k].get("name") and self.players[k]["name"] != "Свободный слот"],
            "combat_log": self.combat_log[-12:], "your_role": viewer_role, "is_your_turn": is_your_turn,
            "is_solo": self.is_solo, "victory_rewards": getattr(self, "victory_rewards", None)
        }
