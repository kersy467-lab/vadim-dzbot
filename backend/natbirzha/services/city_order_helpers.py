"""Small value and response helpers shared by city-order handlers."""

import hashlib
import json
from decimal import Decimal, ROUND_DOWN

from backend.natbirzha.catalogs.businesses import INDUSTRIES
from backend.natbirzha.config import game_dt_iso
from backend.natbirzha.models.city_orders import NatCityOrder
from backend.natbirzha.models.inventory import CANONICAL_ITEMS


QUANTITY_QUANTUM = Decimal("0.000001")


def quantity(value: Decimal) -> Decimal:
    return max(Decimal(0), value.quantize(QUANTITY_QUANTUM, rounding=ROUND_DOWN))


def request_hash(order_id: int, amount: Decimal) -> str:
    payload = json.dumps(
        {"order_id": int(order_id), "quantity": str(amount)},
        sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def serialize_order(order: NatCityOrder) -> dict:
    item = CANONICAL_ITEMS.get(order.item_id, {})
    return {
        "id": order.id,
        "scheduled_slot": game_dt_iso(order.scheduled_slot),
        "industry": order.industry,
        "industry_name": INDUSTRIES.get(order.industry, {}).get("name", order.industry),
        "item_id": order.item_id,
        "item_name": item.get("name", order.item_id),
        "unit": item.get("unit", "шт."),
        "quantity": float(order.quantity),
        "remaining_quantity": float(order.remaining_quantity),
        "unit_price": float(order.unit_price),
        "reserved_cash": float(order.reserved_cash),
        "paid_cash": float(order.paid_cash),
        "status": order.status,
        "issued_at": game_dt_iso(order.issued_at),
        "expires_at": game_dt_iso(order.expires_at),
        "closed_at": game_dt_iso(order.closed_at) if order.closed_at else None,
    }


__all__ = ["quantity", "request_hash", "serialize_order"]
