"""Escrow returns to its owner; only the bankrupt company's assets are seized."""
from sqlalchemy import delete, select
from backend.natbirzha.models.next_game import NatNextGameFacility, NatNextGameInventory
from backend.natbirzha.models.next_game_progression import NatNextGameMerger
from backend.natbirzha.models.next_game_partnerships import NatNextGameJointProject, NatNextGameSupplyDeal
from backend.natbirzha.models.next_game_community import NatNextGameHelpRequest
from backend.natbirzha.models.next_game_bankruptcy import NatNextGameLiquidationLot
from backend.natbirzha.services.next_game_service import NextGameService as Game
from backend.natbirzha.next_game_catalog import find_next_game_branch


async def close_partnerships(session, company, current):
    from backend.natbirzha.services.next_game_partnership_service import NextGamePartnershipService
    for model, kind, first, second in (
        (NatNextGameSupplyDeal, "supply", NatNextGameSupplyDeal.buyer_company_id, NatNextGameSupplyDeal.seller_company_id),
        (NatNextGameJointProject, "projects", NatNextGameJointProject.proposer_company_id, NatNextGameJointProject.partner_company_id),
    ):
        rows = (await session.scalars(select(model).where((first == company.id) | (second == company.id),
            model.status.in_(("OPEN", "ACTIVE"))).with_for_update())).all()
        for row in rows:
            # ACTIVE joint project cancels future cycles; past outputs stay in each owner's stock.
            await NextGamePartnershipService.cancel(session, company.owner_tg_id, kind, row.id)
    await session.flush()


async def list_factories(session, company, episode, current):
    from backend.natbirzha.services.next_game_operations_effects import retire_company
    facilities = (await session.scalars(select(NatNextGameFacility).where(
        NatNextGameFacility.company_id == company.id).with_for_update())).all()
    mergers = (await session.scalars(select(NatNextGameMerger).where(
        NatNextGameMerger.company_id == company.id, NatNextGameMerger.status == "ACTIVE").with_for_update())).all()
    merged = {row.branch_id: row for row in mergers}
    count = 0
    for facility in facilities:
        sources = merged[facility.branch_id].sources_json if facility.branch_id in merged else [
            {"branch_id": facility.branch_id, "level": facility.level}]
        for source in sources:
            branch = find_next_game_branch(source["branch_id"])
            if branch is None:
                raise ValueError("Невозможно оценить предприятие отсутствующей ветки")
            level = int(source["level"])
            # Half of construction and paid level improvements becomes the fixed reserve sale price.
            price = round((float(branch["factory"]["build_cost"]) + 2500 * level * (level - 1) / 2) * .5, 2)
            session.add(NatNextGameLiquidationLot(source_company_id=company.id, bankruptcy_sequence=episode,
                branch_id=source["branch_id"], level=level, price=max(.01, price), status="OPEN", listed_at=current))
            count += 1
    for merger in mergers:
        merger.status, merger.dissolved_at = "RESET", current
    await retire_company(session, company.id)
    await session.execute(delete(NatNextGameFacility).where(NatNextGameFacility.company_id == company.id))
    for request in (await session.scalars(select(NatNextGameHelpRequest).where(
        NatNextGameHelpRequest.company_id == company.id, NatNextGameHelpRequest.status == "OPEN"))).all():
        request.status = "CLOSED"
    await session.flush()
    return count


async def seize_inventory_and_cash(session, company):
    treasury = await Game._treasury(session)
    stock = dict(treasury.inventory_json or {})
    inventory = (await session.scalars(select(NatNextGameInventory).where(
        NatNextGameInventory.company_id == company.id).with_for_update())).all()
    for row in inventory:
        stock[row.item_id] = round(float(stock.get(row.item_id, 0)) + row.quantity, 4)
        session.add(Game._ledger(company.id, "BANKRUPTCY_GOODS", 0, 0, item_id=row.item_id,
            company_quantity=-row.quantity, treasury_quantity=row.quantity))
        await session.delete(row)
    treasury.inventory_json = stock
    cash = company.cash
    treasury.cash = round(treasury.cash + cash, 8)
    company.cash = 0
    session.add(Game._ledger(company.id, "BANKRUPTCY_CASH", -cash, cash))
    await session.flush()
    return cash


async def offer_reserve_shares(session):
    from backend.natbirzha.models.next_game_equity import NatNextGameShareHolding, NatNextGameShareIssue
    from backend.natbirzha.services.next_game_rebirth_assets import reserve_company, sweep_reserve_income
    from backend.natbirzha.services.next_game_equity_service import NextGameEquityService
    reserve = await reserve_company(session)
    for holding in (await session.scalars(select(NatNextGameShareHolding).where(
        NatNextGameShareHolding.company_id == reserve.id, NatNextGameShareHolding.shares > 0))).all():
        issue = await session.get(NatNextGameShareIssue, holding.issue_id)
        if issue.status != "ACTIVE" or issue.company_id == reserve.id:
            continue
        free = holding.shares - await NextGameEquityService._reserved_shares(session, issue.id, reserve.id)
        if free > 0:
            await NextGameEquityService.create_order(session, -1, issue.id, "SELL", free,
                max(.0001, round(issue.last_price, 4)))
    await sweep_reserve_income(session)
