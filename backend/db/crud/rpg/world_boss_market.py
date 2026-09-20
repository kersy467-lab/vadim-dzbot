"""
natarGRP World Boss (World Titan Roshan 50M HP) & P2P Marketplace.
Conforms to Specification 3.0.0-ULTIMATE (Volume IX, 9.3 & 9.4).
"""
import time
import uuid
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import select

from backend.db.models import RPGCharacter

# --- 9.3. Мировой Рошан (World Titan Roshan — 50 000 000 HP) ---
DEFAULT_WORLD_BOSS_HP = 50_000_000

_WORLD_BOSS_STATE: Dict[str, Any] = {
    "boss_id": "world_roshan",
    "name": "Мировой Титан Рошан",
    "max_hp": DEFAULT_WORLD_BOSS_HP,
    "current_hp": DEFAULT_WORLD_BOSS_HP,
    "total_damage_dealt": 0,
    "is_defeated": False,
    "claimed_milestones": [],  # [25, 50, 75, 100]
    "participants": {},  # user_id -> {"user_name": str, "total_damage": int, "attacks_count": int}
}

MILESTONE_REWARDS: Dict[int, Dict[str, Any]] = {
    25: {"gold": 5000, "gems": 50, "desc": "Рубеж 25% пройден!"},
    50: {"gold": 10000, "gems": 100, "desc": "Рубеж 50% пройден!"},
    75: {"gold": 15000, "gems": 150, "desc": "Рубеж 75% пройден!"},
    100: {"gold": 25000, "gems": 250, "chest": "immortal_chest", "desc": "Мировой Титан повержен!"},
}


def get_world_boss_status() -> Dict[str, Any]:
    """Returns current state, HP percentage, and top 10 damage dealers."""
    max_hp = _WORLD_BOSS_STATE["max_hp"]
    curr_hp = max(0, _WORLD_BOSS_STATE["current_hp"])
    hp_pct = round((curr_hp / max_hp) * 100, 2) if max_hp > 0 else 0.0

    sorted_participants = sorted(
        _WORLD_BOSS_STATE["participants"].values(),
        key=lambda p: p["total_damage"],
        reverse=True
    )

    return {
        "boss_id": _WORLD_BOSS_STATE["boss_id"],
        "name": _WORLD_BOSS_STATE["name"],
        "max_hp": max_hp,
        "current_hp": curr_hp,
        "hp_pct": hp_pct,
        "total_damage_dealt": _WORLD_BOSS_STATE["total_damage_dealt"],
        "is_defeated": _WORLD_BOSS_STATE["is_defeated"],
        "claimed_milestones": list(_WORLD_BOSS_STATE["claimed_milestones"]),
        "leaderboard": sorted_participants[:10],
        "total_participants": len(_WORLD_BOSS_STATE["participants"])
    }


def record_world_boss_attack(user_id: int, user_name: str, damage: int) -> Dict[str, Any]:
    """
    Applies player's attack damage to World Roshan, updates leaderboard and checks milestones.
    """
    if _WORLD_BOSS_STATE["is_defeated"] or _WORLD_BOSS_STATE["current_hp"] <= 0:
        return {
            "success": False,
            "message": "Мировой Титан уже повержен! Ожидайте следующего рейда.",
            "boss_status": get_world_boss_status()
        }

    actual_dmg = min(max(1, damage), _WORLD_BOSS_STATE["current_hp"])
    _WORLD_BOSS_STATE["current_hp"] -= actual_dmg
    _WORLD_BOSS_STATE["total_damage_dealt"] += actual_dmg

    # Leaderboard update
    parts = _WORLD_BOSS_STATE["participants"]
    if user_id not in parts:
        parts[user_id] = {
            "user_id": user_id,
            "user_name": user_name,
            "total_damage": 0,
            "attacks_count": 0
        }
    parts[user_id]["total_damage"] += actual_dmg
    parts[user_id]["attacks_count"] += 1
    parts[user_id]["user_name"] = user_name

    # Check Milestones (25%, 50%, 75%, 100%)
    max_hp = _WORLD_BOSS_STATE["max_hp"]
    dmg_done = _WORLD_BOSS_STATE["total_damage_dealt"]
    newly_unlocked_milestones = []

    for pct in [25, 50, 75, 100]:
        needed_dmg = int(max_hp * (pct / 100.0))
        if dmg_done >= needed_dmg and pct not in _WORLD_BOSS_STATE["claimed_milestones"]:
            _WORLD_BOSS_STATE["claimed_milestones"].append(pct)
            newly_unlocked_milestones.append({
                "milestone_pct": pct,
                "reward": MILESTONE_REWARDS[pct]
            })

    if _WORLD_BOSS_STATE["current_hp"] <= 0:
        _WORLD_BOSS_STATE["is_defeated"] = True

    return {
        "success": True,
        "damage_dealt": actual_dmg,
        "newly_unlocked_milestones": newly_unlocked_milestones,
        "boss_status": get_world_boss_status()
    }


def reset_world_boss(new_max_hp: int = DEFAULT_WORLD_BOSS_HP) -> Dict[str, Any]:
    """Resets World Titan Roshan for testing or new raid cycle."""
    _WORLD_BOSS_STATE["max_hp"] = new_max_hp
    _WORLD_BOSS_STATE["current_hp"] = new_max_hp
    _WORLD_BOSS_STATE["total_damage_dealt"] = 0
    _WORLD_BOSS_STATE["is_defeated"] = False
    _WORLD_BOSS_STATE["claimed_milestones"] = []
    _WORLD_BOSS_STATE["participants"] = {}
    return get_world_boss_status()


# --- 9.4. Торговая Площадка (P2P Marketplace) ---
MARKET_FEE_PCT = 5.0  # 5% комиссия рынка

_MARKET_LISTINGS: Dict[str, Dict[str, Any]] = {}


def get_market_listings(
    rarity: Optional[str] = None,
    slot: Optional[str] = None,
    currency: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Returns active market listings with optional filtering."""
    results = []
    for item_data in _MARKET_LISTINGS.values():
        item = item_data["item"]
        if rarity and item.get("rarity") != rarity.lower():
            continue
        if slot and item.get("slot") != slot.lower():
            continue
        if currency and item_data.get("currency") != currency.lower():
            continue
        results.append(item_data)
    return results


async def list_item_for_sale(
    session: AsyncSession,
    char: RPGCharacter,
    item_uid: str,
    price: int,
    currency: str = "gold",
    user_name: str = "Торговец"
) -> Dict[str, Any]:
    """
    Puts an item from player's inventory up for sale on the P2P marketplace.
    """
    if price <= 0:
        raise ValueError("Цена должна быть строго больше 0.")
    curr_key = currency.lower().strip()
    if curr_key not in ["gold", "gems"]:
        raise ValueError("Валюта должна быть 'gold' или 'gems'.")

    inv = list(char.inventory or [])
    found_idx = next((i for i, it in enumerate(inv) if it.get("uid") == item_uid), -1)
    if found_idx == -1:
        raise ValueError("Предмет не найден в вашем инвентаре.")

    item_to_sell = inv.pop(found_idx)
    char.inventory = inv
    flag_modified(char, "inventory")

    listing_id = "mkt_" + uuid.uuid4().hex[:10]
    listing = {
        "listing_id": listing_id,
        "seller_id": char.user_id,
        "seller_name": user_name,
        "item": item_to_sell,
        "price": price,
        "currency": curr_key,
        "fee_pct": MARKET_FEE_PCT,
        "created_at": time.time()
    }
    _MARKET_LISTINGS[listing_id] = listing
    await session.commit()
    await session.refresh(char)

    return {
        "success": True,
        "listing": listing,
        "message": f"Предмет «{item_to_sell.get('name')}» выставлен на рынок за {price} {curr_key}!"
    }


async def cancel_market_listing(
    session: AsyncSession,
    char: RPGCharacter,
    listing_id: str
) -> Dict[str, Any]:
    """Cancels an active listing and returns the item to seller's inventory."""
    listing = _MARKET_LISTINGS.get(listing_id)
    if not listing:
        raise ValueError("Лот на рынке не найден.")
    if listing["seller_id"] != char.user_id:
        raise ValueError("Вы можете снять с продажи только собственный лот.")

    item = listing["item"]
    inv = list(char.inventory or [])
    inv.append(item)
    char.inventory = inv
    flag_modified(char, "inventory")

    del _MARKET_LISTINGS[listing_id]
    await session.commit()
    await session.refresh(char)

    return {
        "success": True,
        "item": item,
        "message": f"Предмет «{item.get('name')}» возвращен в инвентарь."
    }


async def buy_market_item(
    session: AsyncSession,
    buyer_char: RPGCharacter,
    listing_id: str
) -> Dict[str, Any]:
    """
    Executes a purchase: checks buyer funds, transfers item, pays seller net price (minus 5% fee).
    """
    listing = _MARKET_LISTINGS.get(listing_id)
    if not listing:
        raise ValueError("Лот на рынке не найден или уже продан.")
    if listing["seller_id"] == buyer_char.user_id:
        raise ValueError("Вы не можете купить собственный лот на рынке.")

    price = listing["price"]
    currency = listing["currency"]
    fee = int(price * (MARKET_FEE_PCT / 100.0))
    payout = price - fee

    if currency == "gold":
        if buyer_char.gold < price:
            raise ValueError(f"Не хватает золота! Требуется {price} 🪙, у вас {buyer_char.gold} 🪙.")
        buyer_char.gold -= price
    elif currency == "gems":
        if buyer_char.gems < price:
            raise ValueError(f"Не хватает кристаллов! Требуется {price} 💎, у вас {buyer_char.gems} 💎.")
        buyer_char.gems -= price

    # Add item to buyer inventory
    buyer_inv = list(buyer_char.inventory or [])
    bought_item = listing["item"]
    buyer_inv.append(bought_item)
    buyer_char.inventory = buyer_inv
    flag_modified(buyer_char, "inventory")

    # Credit seller
    seller_res = await session.execute(
        select(RPGCharacter).where(RPGCharacter.user_id == listing["seller_id"])
    )
    seller_char = seller_res.scalar_one_or_none()
    if seller_char:
        if currency == "gold":
            seller_char.gold += payout
        elif currency == "gems":
            seller_char.gems += payout

    del _MARKET_LISTINGS[listing_id]
    await session.commit()
    await session.refresh(buyer_char)

    return {
        "success": True,
        "item": bought_item,
        "price_paid": price,
        "fee_taken": fee,
        "seller_payout": payout,
        "currency": currency,
        "message": f"Успешная покупка «{bought_item.get('name')}» за {price} {currency}!"
    }
