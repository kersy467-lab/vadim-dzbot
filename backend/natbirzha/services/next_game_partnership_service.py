"""Offers, acceptance and cancellation for independent corporate partnerships."""
from datetime import timedelta
from math import isfinite
from sqlalchemy import func, or_, select
from backend.natbirzha.models.next_game import NatNextGameCompany, NatNextGameFacility
from backend.natbirzha.models.next_game_partnerships import NatNextGameSupplyDeal as Supply, NatNextGameJointProject as Project
from backend.natbirzha.next_game_catalog import find_next_game_branch, get_next_game_items
from backend.natbirzha.services.next_game_service import NextGameService as Game
from backend.natbirzha.services.next_game_service.common import _utcnow
from backend.natbirzha.services.next_game_market_service import NextGameMarketService as Market
from backend.natbirzha.services.next_game_partnership_settlement import refund_supply, settle_all, supply_batch


def amount(value, label, maximum=100_000, digits=4):
    raw = float(value)
    if not isfinite(raw) or raw <= 0 or raw > maximum or abs(raw - round(raw, digits)) > 1e-8:
        raise ValueError(f"{label}: положительное число до {maximum:g}, максимум {digits} знака")
    return round(raw, digits)


async def parties(session, owner_tg_id, counterparty_id):
    await Market.lock_orderbook(session)
    company = await Game._owned_company(session, owner_tg_id)
    counterparty = await session.scalar(select(NatNextGameCompany).where(
        NatNextGameCompany.id == int(counterparty_id)).with_for_update())
    if not counterparty or counterparty.owner_tg_id <= 0 or counterparty.id == company.id:
        raise ValueError("Выберите другую компанию тестового мира")
    return company, counterparty


async def project_count(session, company_id):
    return await session.scalar(select(func.count(Project.id)).where(Project.status == "ACTIVE", or_(
        Project.proposer_company_id == company_id, Project.partner_company_id == company_id))) or 0


async def create_supply(session, owner_tg_id, counterparty_id, item_id, quantity,
                        unit_price, rate_per_hour, duration_hours, now=None):
    quantity = amount(quantity, "Количество")
    price = amount(unit_price, "Цена", maximum=1_000_000)
    rate = amount(rate_per_hour, "Скорость поставки")
    duration = int(duration_hours)
    if duration != duration_hours or not 1 <= duration <= 720:
        raise ValueError("Срок поставки: от 1 до 720 целых часов")
    if item_id not in get_next_game_items():
        raise ValueError("Товар не существует в тестовой экономике")
    buyer, seller = await parties(session, owner_tg_id, counterparty_id)
    escrow = round(quantity * price, 2)
    if escrow <= 0 or escrow > 10_000_000 or buyer.cash + 1e-8 < escrow:
        raise ValueError("Недостаточно cash для полного резерва договора (лимит 10 млн)")
    buyer.cash = round(buyer.cash - escrow, 8)
    row = Supply(buyer_company_id=buyer.id, seller_company_id=seller.id, item_id=item_id,
                 quantity=quantity, unit_price=price, rate_per_hour=rate, duration_hours=duration,
                 escrow_cash=escrow, delivered=0, status="OPEN", offered_at=now or _utcnow())
    session.add(row)
    await session.flush()
    session.add(Game._ledger(buyer.id, "SUPPLY_ESCROW", -escrow, escrow, metadata={"deal_id": row.id}))
    await session.flush()
    return {"success": True, "id": row.id, "kind": "supply"}


async def create_project(session, owner_tg_id, counterparty_id, branch_id, now=None):
    proposer, partner = await parties(session, owner_tg_id, counterparty_id)
    branch = find_next_game_branch(branch_id)
    built = await session.scalar(select(NatNextGameFacility.id).where(
        NatNextGameFacility.company_id == proposer.id, NatNextGameFacility.branch_id == branch_id))
    if not branch or (branch_id not in (proposer.branch_path or []) and not built):
        raise ValueError("Сначала откройте чертёж этого производства")
    if await project_count(session, proposer.id) >= 2 or await project_count(session, partner.id) >= 2:
        raise ValueError("Не более двух активных совместных заводов у каждой компании")
    from backend.natbirzha.services.next_game_operations_effects import production_slots, used_production_slots
    if await used_production_slots(session, proposer.id) >= await production_slots(session, proposer.id):
        raise ValueError("Расширьте производственную площадку для совместного предприятия")
    cost = round(float(branch["factory"]["build_cost"]), 2)
    half = round(cost / 2, 2)
    if proposer.cash + 1e-8 < half:
        raise ValueError("Недостаточно cash для вашей половины строительства")
    proposer.cash = round(proposer.cash - half, 8)
    row = Project(proposer_company_id=proposer.id, partner_company_id=partner.id, branch_id=branch_id,
                  recipe_json=dict(branch["factory"]), build_cost=cost, escrow_cash=half,
                  status="OPEN", cycles_completed=0, offered_at=now or _utcnow())
    session.add(row)
    await session.flush()
    session.add(Game._ledger(proposer.id, "JOINT_ESCROW", -half, half, metadata={"project_id": row.id}))
    await session.flush()
    return {"success": True, "id": row.id, "kind": "projects"}


async def related_row(session, owner_tg_id, kind, id):
    await Market.lock_orderbook(session)
    company = await Game._owned_company(session, owner_tg_id)
    model = Supply if kind == "supply" else Project if kind == "projects" else None
    if model is None:
        raise ValueError("Неизвестный тип договора")
    row = await session.scalar(select(model).where(model.id == int(id)).with_for_update())
    ids = (row.buyer_company_id, row.seller_company_id) if row and kind == "supply" else (
        row.proposer_company_id, row.partner_company_id) if row else ()
    if company.id not in ids:
        raise ValueError("Договор вашей компании не найден")
    return company, row, ids


async def respond(session, owner_tg_id, kind, id, accept, now=None):
    company, row, ids = await related_row(session, owner_tg_id, kind, id)
    if company.id != ids[1]:
        raise ValueError("Принимать предложение может только указанная компания-партнёр")
    if not accept:
        return await cancel(session, owner_tg_id, kind, id)
    if row.status == "ACTIVE":
        return {"success": True, "id": row.id, "status": row.status}
    if row.status != "OPEN":
        raise ValueError("Предложение уже закрыто")
    current = now or _utcnow()
    if kind == "supply":
        row.accepted_at = current
        row.ends_at = current + timedelta(hours=row.duration_hours)
    else:
        proposer = await session.get(NatNextGameCompany, ids[0])
        if await project_count(session, company.id) >= 2 or await project_count(session, proposer.id) >= 2:
            raise ValueError("Лимит: два активных совместных завода на компанию")
        from backend.natbirzha.services.next_game_operations_effects import production_slots, used_production_slots
        # The proposer's OPEN offer already occupies one place; partner starts reserving now.
        if (await used_production_slots(session, company.id) >= await production_slots(session, company.id)
                or await used_production_slots(session, proposer.id) > await production_slots(session, proposer.id)):
            raise ValueError("У участника заняты производственные места; расширьте площадку")
        partner_cost = round(row.build_cost - row.escrow_cash, 2)
        if company.cash + 1e-8 < partner_cost:
            raise ValueError("Недостаточно cash для половины строительства")
        treasury = await Game._treasury(session)
        company.cash = round(company.cash - partner_cost, 8)
        treasury.cash = round(treasury.cash + row.build_cost, 8)
        # The proposer was debited at offer time; record the reserved contribution
        # without charging them again when the escrow reaches the treasury.
        session.add(Game._ledger(proposer.id, "JOINT_BUILD", 0, 0, metadata={
            "project_id": row.id, "cash_from_escrow": row.escrow_cash,
            "treasury_construction_total": row.build_cost,
        }))
        session.add(Game._ledger(company.id, "JOINT_BUILD", -partner_cost, partner_cost, metadata={"project_id": row.id}))
        row.escrow_cash = 0
        row.accepted_at = current
        row.next_cycle_at = current + timedelta(seconds=int(row.recipe_json["cycle_seconds"]))
    row.status = "ACTIVE"
    await session.flush()
    return {"success": True, "id": row.id, "status": row.status}


async def cancel(session, owner_tg_id, kind, id):
    _, row, ids = await related_row(session, owner_tg_id, kind, id)
    if row.status in {"CANCELLED", "COMPLETED", "EXPIRED"}:
        return {"success": True, "id": row.id, "status": row.status}
    if kind == "supply":
        await refund_supply(session, row, "CANCELLED")
    else:
        if row.status == "OPEN" and row.escrow_cash:
            proposer = await session.get(NatNextGameCompany, ids[0])
            proposer.cash = round(proposer.cash + row.escrow_cash, 8)
            session.add(Game._ledger(proposer.id, "JOINT_REFUND", row.escrow_cash, -row.escrow_cash, metadata={"project_id": row.id}))
            row.escrow_cash = 0
        row.status = "CANCELLED"
    await session.flush()
    return {"success": True, "id": row.id, "status": row.status}


async def snapshot(session, owner_tg_id, now=None):
    await settle_all(session, now=now)
    company = await Game._owned_company(session, owner_tg_id)
    companies = (await session.scalars(select(NatNextGameCompany).where(NatNextGameCompany.owner_tg_id > 0).order_by(NatNextGameCompany.id).limit(200))).all()
    names = {row.id: row.name for row in companies}
    items = get_next_game_items()
    supplies = (await session.scalars(select(Supply).where(or_(Supply.buyer_company_id == company.id,
        Supply.seller_company_id == company.id)).order_by(Supply.id.desc()).limit(60))).all()
    projects = (await session.scalars(select(Project).where(or_(Project.proposer_company_id == company.id,
        Project.partner_company_id == company.id)).order_by(Project.id.desc()).limit(60))).all()
    def payload(row, kind):
        ids = (row.buyer_company_id, row.seller_company_id) if kind == "supply" else (row.proposer_company_id, row.partner_company_id)
        result = {column.name: getattr(row, column.name) for column in row.__table__.columns if column.name != "recipe_json"}
        result = {key: value.isoformat() if hasattr(value, "isoformat") else value for key, value in result.items()}
        result.update(kind=kind, initiator_name=names.get(ids[0], f"Компания #{ids[0]}"),
                      partner_name=names.get(ids[1], f"Компания #{ids[1]}"), can_accept=row.status == "OPEN" and company.id == ids[1])
        if kind == "supply":
            result.update(item_name=items.get(row.item_id, {}).get("name", row.item_id), batch=supply_batch(row))
        else:
            result["recipe"] = row.recipe_json
        return result
    return {"company_id": company.id, "cash": company.cash,
            "companies": [{"id": row.id, "name": row.name} for row in companies if row.id != company.id],
            "items": [{"id": id, **item} for id, item in items.items()],
            "blueprints": [{"id": id, **find_next_game_branch(id)} for id in (company.branch_path or []) if find_next_game_branch(id)],
            "supplies": [payload(row, "supply") for row in supplies],
            "projects": [payload(row, "projects") for row in projects],
            "active_projects": await project_count(session, company.id)}


class NextGamePartnershipService:
    create_supply = staticmethod(create_supply)
    create_project = staticmethod(create_project)
    respond = staticmethod(respond)
    cancel = staticmethod(cancel)
    snapshot = staticmethod(snapshot)
    settle_all = staticmethod(settle_all)

