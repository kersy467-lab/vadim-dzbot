"""Atomic deliveries and shared factory cycles; caller owns the transaction."""
from datetime import timedelta
from math import floor
from sqlalchemy import select
from backend.natbirzha.models.next_game import NatNextGameCompany
from backend.natbirzha.models.next_game_community import NatNextGameTransfer
from backend.natbirzha.models.next_game_partnerships import NatNextGameSupplyDeal, NatNextGameJointProject
from backend.natbirzha.services.next_game_service import NextGameService as Game
from backend.natbirzha.services.next_game_service.common import MAX_INVENTORY_PER_ITEM, MAX_CATCH_UP_CYCLES, _utcnow
from backend.natbirzha.services.next_game_market_service import NextGameMarketService as Market


async def refund_supply(session, row, status):
    buyer = await session.get(NatNextGameCompany, row.buyer_company_id)
    refund = round(row.escrow_cash, 2)
    buyer.cash = round(buyer.cash + refund, 8)
    row.escrow_cash = 0
    row.status = status
    if refund:
        session.add(Game._ledger(buyer.id, "SUPPLY_REFUND", refund, -refund, metadata={"deal_id": row.id}))


def supply_batch(row):
    return 1 if row.unit_price > 500 else 100 if row.item_id in {"water", "clean_water"} else 5


async def settle_supply(session, row, current):
    if row.status != "ACTIVE":
        return
    buyer = await session.get(NatNextGameCompany, row.buyer_company_id)
    seller = await session.get(NatNextGameCompany, row.seller_company_id)
    until = min(current, row.ends_at)
    due = min(row.quantity, max(0, (until - row.accepted_at).total_seconds()) / 3600 * row.rate_per_hour)
    pending = max(0, round(due - row.delivered, 4))
    remaining = round(row.quantity - row.delivered, 4)
    batch = supply_batch(row)
    seller_stock = await Game._inventory_row(session, seller.id, row.item_id)
    buyer_stock = await Game._inventory_row(session, buyer.id, row.item_id)
    reserved = await Market.reserved_sell_quantity(session, buyer.id, row.item_id)
    available = float(seller_stock.quantity if seller_stock else 0)
    from backend.natbirzha.services.next_game_operations_effects import warehouse_capacity
    capacity = max(0, await warehouse_capacity(session, buyer.id) - float(buyer_stock.quantity if buyer_stock else 0) - reserved)
    # Ordinary deliveries remain exact batches; a final remainder may close the deal.
    quantity = round(floor((min(pending, available, capacity) + 1e-8) / batch) * batch, 4)
    if remaining - quantity < batch and min(pending, available, capacity) + 1e-8 >= remaining:
        quantity = remaining
    quantity = min(quantity, remaining)
    row.blocked_reason = ""
    if quantity > 0:
        total_delivered = round(row.delivered + quantity, 4)
        payment = round(round(total_delivered * row.unit_price, 2) - round(row.delivered * row.unit_price, 2), 2)
        if payment > row.escrow_cash + 1e-7:
            raise ValueError("Резерв договора не покрывает поставку")
        await Game._change_inventory(session, seller.id, row.item_id, -quantity)
        await Game._change_inventory(session, buyer.id, row.item_id, quantity)
        seller.cash = round(seller.cash + payment, 8)
        row.delivered = total_delivered
        row.escrow_cash = max(0, round(row.escrow_cash - payment, 2))
        metadata = {"deal_id": row.id, "unit_price": row.unit_price}
        session.add(Game._ledger(seller.id, "SUPPLY_DELIVERY", payment, -payment, item_id=row.item_id,
                                 company_quantity=-quantity, metadata=metadata))
        session.add(Game._ledger(buyer.id, "SUPPLY_RECEIVED", 0, 0, item_id=row.item_id,
                                 company_quantity=quantity, metadata=metadata))
        session.add(NatNextGameTransfer(sender_company_id=seller.id, recipient_company_id=buyer.id,
                                       item_id=row.item_id, quantity=quantity, cash=0,
                                       reason="SUPPLY_GOODS", metadata_json=metadata))
        session.add(NatNextGameTransfer(sender_company_id=buyer.id, recipient_company_id=seller.id,
                                       cash=payment, reason="SUPPLY_PAYMENT", metadata_json=metadata))
    elif pending + 1e-8 >= min(batch, remaining):
        row.blocked_reason = "У продавца недостаточно свободного товара" if available < min(batch, remaining) else "Склад покупателя заполнен"
    if row.delivered + 1e-8 >= row.quantity:
        await refund_supply(session, row, "COMPLETED")
    elif current >= row.ends_at:
        await refund_supply(session, row, "EXPIRED")


def halves(value, digits=4):
    first = round(float(value) / 2, digits)
    return first, round(float(value) - first, digits)


async def project_block_reason(session, companies, recipe):
    costs = halves(recipe["operating_cost"], 2)
    inputs = {id: halves(quantity) for id, quantity in recipe["inputs"].items()}
    outputs = halves(recipe["output_quantity"])
    for index, company in enumerate(companies):
        if company.cash + 1e-8 < costs[index]:
            return f"{company.name}: недостаточно cash на половину цикла"
        for item_id, quantities in inputs.items():
            inventory = await Game._inventory_row(session, company.id, item_id)
            if float(inventory.quantity if inventory else 0) + 1e-8 < quantities[index]:
                return f"{company.name}: недостаточно сырья {item_id}"
        inventory = await Game._inventory_row(session, company.id, recipe["output_item"])
        reserved = await Market.reserved_sell_quantity(session, company.id, recipe["output_item"])
        from backend.natbirzha.services.next_game_operations_effects import warehouse_capacity
        if float(inventory.quantity if inventory else 0) + reserved + outputs[index] > await warehouse_capacity(session, company.id) + 1e-8:
            return f"{company.name}: склад заполнен"
    return None


async def settle_project(session, row, current):
    if row.status != "ACTIVE" or current < row.next_cycle_at:
        return
    companies = [await session.get(NatNextGameCompany, id) for id in (row.proposer_company_id, row.partner_company_id)]
    treasury = await Game._treasury(session)
    recipe = row.recipe_json
    interval = int(recipe["cycle_seconds"])
    due = min(MAX_CATCH_UP_CYCLES, 1 + floor((current - row.next_cycle_at).total_seconds() / interval))
    costs, outputs = halves(recipe["operating_cost"], 2), halves(recipe["output_quantity"])
    inputs = {id: halves(quantity) for id, quantity in recipe["inputs"].items()}
    for _ in range(due):
        row.blocked_reason = await project_block_reason(session, companies, recipe) or ""
        if row.blocked_reason:
            row.next_cycle_at = current + timedelta(seconds=interval)
            break
        for index, company in enumerate(companies):
            metadata = {"project_id": row.id, "branch_id": row.branch_id}
            for item_id, quantities in inputs.items():
                await Game._change_inventory(session, company.id, item_id, -quantities[index])
                session.add(Game._ledger(company.id, "JOINT_INPUT", 0, 0, item_id=item_id,
                                        company_quantity=-quantities[index], metadata=metadata))
            company.cash = round(company.cash - costs[index], 8)
            treasury.cash = round(treasury.cash + costs[index], 8)
            session.add(Game._ledger(company.id, "JOINT_OPERATING", -costs[index], costs[index], metadata=metadata))
            await Game._change_inventory(session, company.id, recipe["output_item"], outputs[index])
            session.add(Game._ledger(company.id, "JOINT_OUTPUT", 0, 0, item_id=recipe["output_item"],
                                    company_quantity=outputs[index], metadata=metadata))
        row.cycles_completed += 1
        row.next_cycle_at += timedelta(seconds=interval)


async def settle_all(session, now=None):
    await Market.lock_orderbook(session)
    current = now or _utcnow()
    # The treasury lock serializes supplies, regular production, orders and shared projects.
    supplies = (await session.scalars(select(NatNextGameSupplyDeal).where(
        NatNextGameSupplyDeal.status == "ACTIVE").order_by(NatNextGameSupplyDeal.id).with_for_update())).all()
    for row in supplies:
        await settle_supply(session, row, current)
    projects = (await session.scalars(select(NatNextGameJointProject).where(
        NatNextGameJointProject.status == "ACTIVE").order_by(NatNextGameJointProject.id).with_for_update())).all()
    for row in projects:
        await settle_project(session, row, current)
    await session.flush()

