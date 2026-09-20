import random
from typing import Any

def execute_boss_turn(room: Any) -> None:
    """Босс бьет героев строго по очереди (по кругу) с сокрушительным уроном."""
    hero_keys = ["host", "player_2", "player_3"]
    alive_heroes = [
        k for k in hero_keys
        if room.players[k].get("name") and room.players[k]["name"] != "Свободный слот" and not room.players[k].get("is_dead")
    ]
    if not alive_heroes:
        room.status = "finished"
        room.winner = "boss"
        return

    skill = random.choice(room.boss["skills"])
    skill_mult = float(skill.get("mult", 1.0))
    dmg_base = random.randint(room.boss["atk_min"], room.boss["atk_max"]) * skill_mult

    # Tier scaling: from Tier 1 (Golem) up to Tier 15 (Enigma Cosmic)
    BOSS_TIERS = {
        "golem": 1, "lich": 2, "tormentor": 3, "dragon": 4, "roshan": 5,
        "tidehunter": 6, "sf_boss": 7, "necrophos": 8, "invoker_boss": 9, "chaos_knight": 10,
        "dark_tormentor": 11, "doom": 12, "primal_beast": 13, "phantom_roshan": 14, "enigma": 15
    }
    b_id = str(room.boss.get("id", "roshan")).lower()
    b_tier = 5
    for k, v in BOSS_TIERS.items():
        if k in b_id:
            b_tier = v
            break

    tier_hp_pct = (0.08 + (b_tier * 0.020)) * skill_mult

    # Выбираем цель строго по очереди
    target_role = alive_heroes[room.boss_target_index % len(alive_heroes)]
    target_hero_num = (room.boss_target_index % len(alive_heroes)) + 1
    room.boss_target_index = (room.boss_target_index + 1) % len(alive_heroes)

    is_aoe = ("обоим" in skill.get("text", "").lower() or "всем" in skill.get("text", "").lower())
    target_keys = alive_heroes if is_aoe else [target_role]

    for tk in target_keys:
        hero = room.players[tk]
        h_max = max(100, int(hero.get("hp_max", 150)))
        is_def = bool(hero.get("is_defending", False))

        threat_dmg = h_max * tier_hp_pct
        eff_def = max(0, hero["defense"] * (2 if is_def else 1))
        dr = min(0.65, (eff_def * 0.04) / (1.0 + eff_def * 0.04))

        pure_part = threat_dmg * 0.50
        phys_part = (threat_dmg * 0.50 + dmg_base) * (1.0 - dr)

        final_dmg = int(pure_part + phys_part)
        if is_def:
            final_dmg = int(final_dmg * 0.55)

        min_floor = max(int(60 * b_tier * skill_mult), int(h_max * 0.08))
        final_dmg = max(min_floor, final_dmg)

        hero["hp"] = max(0, hero["hp"] - final_dmg)

        target_note = f" (удар по очереди #{target_hero_num})" if not is_aoe else " (АОЕ по всему кругу!)"
        room.combat_log.append({
            "actor": room.boss["name"],
            "text": f"💥 {room.boss['name']} {skill['text']} и наносит {final_dmg:,} урона герою {hero['name']}{target_note}!",
            "type": "boss_attack",
            "damage": final_dmg
        })

        if hero["hp"] <= 0:
            hero["is_dead"] = True
            room.combat_log.append({
                "actor": "system",
                "text": f"💀 {hero['name']} пал в бою!",
                "type": "death"
            })

    for k in hero_keys:
        room.players[k]["is_defending"] = False

    # Boss Shield mechanic (Tormentor or 30% chance)
    if room.boss.get("id") == "tormentor" or random.randint(1, 100) <= 30:
        if not room.boss.get("shield_active"):
            room.boss["shield_active"] = True
            room.combat_log.append({
                "actor": room.boss["name"],
                "text": f"🔮 {room.boss['name']} активирует Отражающий Панцирь (отразит 50% урона)! Защищайтесь или пейте зелья!",
                "type": "info"
            })
        else:
            room.boss["shield_active"] = False

    if all(room.players[k].get("is_dead") for k in hero_keys if room.players[k].get("name") and room.players[k]["name"] != "Свободный слот"):
        room.status = "finished"
        room.winner = "boss"
        room.combat_log.append({
            "actor": "system",
            "text": "☠️ Все герои погибли. Рейд провален!",
            "type": "defeat"
        })
