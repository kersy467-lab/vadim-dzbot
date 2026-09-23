"""Atomic inventory consumption shared by business opening and upgrades."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.inventory import CANONICAL_ITEMS, NatInventory


async def consume_business_resources(
    session: AsyncSession, company_id: int, requirements: dict[str, float]
) -> None:
    locked: dict[str, NatInventory] = {}
    missing: list[str] = []
    for item_id, raw_quantity in requirements.items():
        quantity = max(0.0, float(raw_quantity))
        if quantity <= 0:
            continue
        inventory = await session.scalar(
            select(NatInventory)
            .where(NatInventory.company_id == company_id, NatInventory.item_id == item_id)
            .with_for_update()
        )
        if inventory is None or float(inventory.available_quantity) + 1e-9 < quantity:
            missing.append(item_id)
        else:
            locked[item_id] = inventory
    if missing:
        names = [CANONICAL_ITEMS.get(item_id, {}).get("name", "Неизвестный ресурс") for item_id in missing]
        raise ValueError("Не хватает ресурсов: " + ", ".join(names))
    for item_id, inventory in locked.items():
        inventory.quantity = round(
            max(0.0, float(inventory.quantity) - float(requirements[item_id])), 6
        )


__all__ = ["consume_business_resources"]
