"""Lifecycle actions for proposals, construction, upgrades and production claims."""

from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.catalogs.businesses import INDUSTRIES, JOINT_FACTORY_RECIPES, get_joint_factory_recipe
from backend.natbirzha.config import get_game_now, nat_settings, normalize_dt
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import CANONICAL_ITEMS, NatInventory
from backend.natbirzha.models.joint_factories import NatJointFactory, NatJointFactoryProposal
from backend.natbirzha.services.inventory_capacity_service import InventoryCapacityService
from backend.natbirzha.services.joint_factory_settlement_service import JointFactorySettlementService


class JointFactoryService:
    """A company may own one active joint factory in a dedicated slot."""

    @staticmethod
    async def _locked_companies(
        session: AsyncSession,
        ids: tuple[int, int],
        *,
        allow_bankrupt: bool = False,
    ) -> dict[int, NatCompany]:
        rows = (await session.execute(
            select(NatCompany).where(NatCompany.id.in_(ids)).order_by(NatCompany.id).with_for_update()
        )).scalars().all()
        companies = {row.id: row for row in rows}
        if len(companies) != 2:
            raise ValueError("Одна из компаний больше не существует")
        if not allow_bankrupt and any(company.is_bankrupt for company in companies.values()):
            raise ValueError("Банкротная компания не может участвовать в совместном заводе")
        return companies

    @staticmethod
    def _recipe(recipe_id: str, *, allow_legacy: bool = False) -> dict[str, Any]:
        key = (recipe_id or "").strip().lower()
        recipe = JOINT_FACTORY_RECIPES.get(key)
        if recipe is None and allow_legacy:
            recipe = get_joint_factory_recipe(key)
        if recipe is None:
            raise ValueError("Неизвестный рецепт совместного завода")
        return recipe

    @classmethod
    async def _assert_slots_free(cls, session: AsyncSession, ids: tuple[int, int]) -> None:
        active = await session.scalar(select(func.count(NatJointFactory.id)).where(
            NatJointFactory.status == "ACTIVE",
            or_(NatJointFactory.company_a_id.in_(ids), NatJointFactory.company_b_id.in_(ids)),
        ))
        if active:
            raise ValueError("Отдельный слот совместного завода уже занят у одной из компаний")

    @classmethod
    async def partners(cls, session: AsyncSession, company: NatCompany) -> list[dict]:
        if company.is_bankrupt:
            return []
        own_busy = await session.scalar(select(func.count(NatJointFactory.id)).where(
            NatJointFactory.status == "ACTIVE",
            or_(NatJointFactory.company_a_id == company.id, NatJointFactory.company_b_id == company.id),
        ))
        own_pending = await session.scalar(select(func.count(NatJointFactoryProposal.id)).where(
            NatJointFactoryProposal.status == "PENDING",
            or_(NatJointFactoryProposal.proposer_company_id == company.id,
                NatJointFactoryProposal.partner_company_id == company.id),
        ))
        if own_busy or own_pending:
            return []
        companies = (await session.execute(select(NatCompany).where(
            NatCompany.id != company.id,
            NatCompany.is_bankrupt.is_(False),
            NatCompany.specialization.in_(tuple(INDUSTRIES)),
        ).order_by(NatCompany.name, NatCompany.id))).scalars().all()
        result = []
        for partner in companies:
            recipe = next((row for row in JOINT_FACTORY_RECIPES.values()
                           if set(row["specializations"]) == {company.specialization, partner.specialization}), None)
            if recipe is None:
                continue
            busy = await session.scalar(select(func.count(NatJointFactory.id)).where(
                NatJointFactory.status == "ACTIVE",
                or_(NatJointFactory.company_a_id == partner.id, NatJointFactory.company_b_id == partner.id),
            ))
            pending = await session.scalar(select(func.count(NatJointFactoryProposal.id)).where(
                NatJointFactoryProposal.status == "PENDING",
                or_(NatJointFactoryProposal.proposer_company_id == partner.id,
                    NatJointFactoryProposal.partner_company_id == partner.id),
            ))
            if busy or pending:
                continue
            result.append({
                "company_id": partner.id,
                "company_name": partner.name,
                "specialization": partner.specialization,
                "level": int(partner.level),
                "recipe_id": recipe["id"],
                "recipe_name": " × ".join(INDUSTRIES[key]["name"] for key in recipe["specializations"]),
                "partner_resource": recipe["output_items"][partner.specialization],
            })
        return result

    @classmethod
    async def create_build_proposal(cls, session, proposer_id: int, partner_id: int, recipe_id: str, *, now=None) -> dict:
        if int(proposer_id) == int(partner_id):
            raise ValueError("Нельзя строить совместный завод со своей компанией")
        recipe = cls._recipe(recipe_id)
        companies = await cls._locked_companies(session, (proposer_id, partner_id))
        proposer, partner = companies[proposer_id], companies[partner_id]
        if {proposer.specialization, partner.specialization} != set(recipe["specializations"]):
            raise ValueError("Отрасли компаний не соответствуют выбранному проекту")
        await cls._assert_slots_free(session, (proposer.id, partner.id))
        pending = await session.scalar(select(func.count(NatJointFactoryProposal.id)).where(
            NatJointFactoryProposal.status == "PENDING",
            or_(NatJointFactoryProposal.proposer_company_id.in_((proposer.id, partner.id)),
                NatJointFactoryProposal.partner_company_id.in_((proposer.id, partner.id))),
        ))
        if pending:
            raise ValueError("Сначала обработайте уже отправленное предложение о совместном заводе")
        proposal = NatJointFactoryProposal(
            proposer_company_id=proposer.id, partner_company_id=partner.id,
            recipe_id=recipe["id"], operation="BUILD", target_level=1, status="PENDING",
            created_at=normalize_dt(now or get_game_now()),
        )
        session.add(proposal)
        await session.flush()
        return {"success": True, "proposal_id": proposal.id, "status": proposal.status}

    @classmethod
    async def create_upgrade_proposal(cls, session, company_id: int, factory_id: int, *, now=None) -> dict:
        factory = await session.scalar(select(NatJointFactory).where(NatJointFactory.id == int(factory_id)))
        if factory is None or factory.status != "ACTIVE":
            raise ValueError("Активный совместный завод не найден")
        ids = (factory.company_a_id, factory.company_b_id)
        await cls._locked_companies(session, ids)
        factory = await session.scalar(select(NatJointFactory).where(
            NatJointFactory.id == int(factory_id)
        ).with_for_update().execution_options(populate_existing=True))
        if factory is None or factory.status != "ACTIVE":
            raise ValueError("Активный совместный завод не найден")
        if int(company_id) not in ids:
            raise ValueError("Этот завод не принадлежит вашей компании")
        if int(factory.level) >= 4:
            raise ValueError("Совместный завод уже достиг максимального уровня")
        pending = await session.scalar(select(func.count(NatJointFactoryProposal.id)).where(
            NatJointFactoryProposal.factory_id == factory.id,
            NatJointFactoryProposal.status == "PENDING",
        ))
        if pending:
            raise ValueError("Для этого завода уже ожидается решение по предложению")
        partner_id = factory.company_b_id if company_id == factory.company_a_id else factory.company_a_id
        proposal = NatJointFactoryProposal(
            proposer_company_id=int(company_id), partner_company_id=partner_id,
            recipe_id=factory.recipe_id, operation="UPGRADE", factory_id=factory.id,
            target_level=int(factory.level) + 1, status="PENDING",
            created_at=normalize_dt(now or get_game_now()),
        )
        session.add(proposal)
        await session.flush()
        return {
            "success": True, "proposal_id": proposal.id, "status": proposal.status,
            "target_level": proposal.target_level,
            "contributions": cls._recipe(factory.recipe_id, allow_legacy=True)["levels"][proposal.target_level - 1]["contributions"],
        }

    @classmethod
    async def _apply_contributions(cls, session, companies, recipe, target_level: int) -> tuple[float, float]:
        contributions = recipe["levels"][target_level - 1]["contributions"]
        cash_due: dict[int, float] = {}
        requirements: list[tuple[int, str, float]] = []
        for company in companies.values():
            terms = contributions[company.specialization]
            cash_due[company.id] = round(float(terms["cash"]), 2)
            requirements.extend((company.id, item, float(quantity))
                                for item, quantity in terms["resources"].items())
        for company_id, amount in cash_due.items():
            if float(companies[company_id].cash) + 1e-9 < amount:
                raise ValueError(f"{companies[company_id].name}: недостаточно cash для взноса ({amount:.2f})")
        locked: dict[tuple[int, str], NatInventory] = {}
        for company_id, item_id, quantity in sorted(requirements):
            row = await session.scalar(select(NatInventory).where(
                NatInventory.company_id == company_id, NatInventory.item_id == item_id
            ).with_for_update())
            if row is None or row.available_quantity + 1e-9 < quantity:
                available = float(row.available_quantity) if row else 0.0
                raise ValueError(f"{companies[company_id].name}: нужно {quantity:.3f} {item_id}, доступно {available:.3f}")
            locked[(company_id, item_id)] = row
        for company_id, amount in cash_due.items():
            companies[company_id].cash = round(float(companies[company_id].cash) - amount, 2)
        resource_value = 0.0
        for company_id, item_id, quantity in requirements:
            row = locked[(company_id, item_id)]
            row.quantity = round(max(0.0, float(row.quantity) - quantity), 8)
            resource_value += quantity * float(CANONICAL_ITEMS[item_id]["base_price"])
        return round(sum(cash_due.values()), 2), round(resource_value, 2)

    @classmethod
    async def accept_proposal(cls, session, company_id: int, proposal_id: int, *, now=None) -> dict:
        peek = await session.get(NatJointFactoryProposal, int(proposal_id))
        if peek is None:
            raise ValueError("Предложение не найдено")
        ids = (peek.proposer_company_id, peek.partner_company_id)
        companies = await cls._locked_companies(session, ids)
        proposal = await session.scalar(select(NatJointFactoryProposal).where(
            NatJointFactoryProposal.id == int(proposal_id)
        ).with_for_update())
        if proposal is None or proposal.status != "PENDING":
            raise ValueError("Это предложение уже обработано")
        if proposal.partner_company_id != int(company_id):
            raise ValueError("Принять предложение может только компания-получатель")
        recipe = cls._recipe(proposal.recipe_id, allow_legacy=proposal.operation == "UPGRADE")
        current = normalize_dt(now or get_game_now())
        if proposal.operation == "BUILD":
            await cls._assert_slots_free(session, ids)
            cash, resources = await cls._apply_contributions(session, companies, recipe, 1)
            owner_by_industry = {row.specialization: row.id for row in companies.values()}
            factory = NatJointFactory(
                recipe_id=recipe["id"],
                company_a_id=owner_by_industry[recipe["specializations"][0]],
                company_b_id=owner_by_industry[recipe["specializations"][1]],
                level=1, status="ACTIVE", stock_a_json={}, stock_b_json={},
                total_produced_json={}, claimed_a_json={}, claimed_b_json={},
                total_cash_contributed=cash, total_resource_contributed=resources,
                last_settled_at=current, created_at=current,
            )
            session.add(factory)
            await session.flush()
            proposal.factory_id = factory.id
        else:
            factory = await session.scalar(select(NatJointFactory).where(
                NatJointFactory.id == proposal.factory_id
            ).with_for_update())
            if factory is None or factory.status != "ACTIVE" or {
                factory.company_a_id, factory.company_b_id
            } != set(ids):
                raise ValueError("Совместный завод больше нельзя улучшить")
            if int(factory.level) + 1 != int(proposal.target_level):
                raise ValueError("Уровень завода изменился; отправьте новое предложение")
            await JointFactorySettlementService._settle_locked(session, factory, current)
            if factory.status != "ACTIVE":
                raise ValueError("Завод нельзя улучшить после прекращения работы")
            cash, resources = await cls._apply_contributions(session, companies, recipe, proposal.target_level)
            factory.level = int(proposal.target_level)
            factory.total_cash_contributed = round(float(factory.total_cash_contributed) + cash, 2)
            factory.total_resource_contributed = round(float(factory.total_resource_contributed) + resources, 2)
        proposal.status = "ACCEPTED"
        proposal.responded_at = current
        await session.flush()
        return {
            "success": True, "proposal_id": proposal.id, "factory_id": factory.id,
            "operation": proposal.operation, "level": int(factory.level), "status": proposal.status,
            "cash_contributed": cash, "resource_value_contributed": resources,
            "slot": "Совместный завод · отдельная мощность",
        }

    @classmethod
    async def reject_proposal(cls, session, company_id: int, proposal_id: int, *, now=None) -> dict:
        proposal = await session.scalar(select(NatJointFactoryProposal).where(
            NatJointFactoryProposal.id == int(proposal_id)
        ).with_for_update())
        if proposal is None or proposal.status != "PENDING":
            raise ValueError("Это предложение уже обработано")
        if proposal.partner_company_id != int(company_id):
            raise ValueError("Отклонить предложение может только компания-получатель")
        proposal.status = "REJECTED"
        proposal.responded_at = normalize_dt(now or get_game_now())
        await session.flush()
        return {"success": True, "proposal_id": proposal.id, "status": proposal.status}

    @classmethod
    async def cancel_proposal(cls, session, company_id: int, proposal_id: int, *, now=None) -> dict:
        proposal = await session.scalar(select(NatJointFactoryProposal).where(
            NatJointFactoryProposal.id == int(proposal_id)
        ).with_for_update())
        if proposal is None or proposal.status != "PENDING":
            raise ValueError("Это предложение уже обработано")
        if proposal.proposer_company_id != int(company_id):
            raise ValueError("Отменить предложение может только его автор")
        proposal.status = "CANCELLED"
        proposal.responded_at = normalize_dt(now or get_game_now())
        await session.flush()
        return {"success": True, "proposal_id": proposal.id, "status": proposal.status}

    @classmethod
    async def claim_output(cls, session, company_id: int, factory_id: int, *, now=None) -> dict:
        peek = await session.get(NatJointFactory, int(factory_id))
        if peek is None:
            raise ValueError("Совместный завод не найден")
        companies = await cls._locked_companies(
            session, (peek.company_a_id, peek.company_b_id), allow_bankrupt=True
        )
        if companies.get(int(company_id)) is None or companies[int(company_id)].is_bankrupt:
            raise ValueError("Банкротная компания не может забрать продукцию")
        factory = await session.scalar(select(NatJointFactory).where(
            NatJointFactory.id == int(factory_id)
        ).with_for_update())
        if factory is None or int(company_id) not in (factory.company_a_id, factory.company_b_id):
            raise ValueError("Этот завод не принадлежит вашей компании")
        if factory.status not in {"ACTIVE", "BREACHED"}:
            raise ValueError("На закрытом заводе нет доступной продукции")
        if factory.status == "ACTIVE":
            await JointFactorySettlementService._settle_locked(
                session, factory, normalize_dt(now or get_game_now())
            )
        owner_a = int(company_id) == factory.company_a_id
        stock_key = "stock_a_json" if owner_a else "stock_b_json"
        claimed_key = "claimed_a_json" if owner_a else "claimed_b_json"
        stock, claimed = dict(getattr(factory, stock_key) or {}), dict(getattr(factory, claimed_key) or {})
        businesses = list((await session.execute(select(NatBusiness).where(
            NatBusiness.company_id == int(company_id)
        ))).scalars().all())
        capacity = InventoryCapacityService.capacity_by_item(companies[int(company_id)], businesses)
        moved: dict[str, float] = {}
        for item_id, joint_quantity in sorted(stock.items()):
            inventory = await session.scalar(select(NatInventory).where(
                NatInventory.company_id == int(company_id), NatInventory.item_id == item_id
            ).with_for_update())
            if inventory is None:
                inventory = NatInventory(company_id=int(company_id), item_id=item_id, quantity=0.0)
                session.add(inventory)
                await session.flush()
            cap = max(float(nat_settings.INVENTORY_MAX_QUANTITY_PER_ITEM), float(capacity.get(item_id, 0)))
            free = max(0.0, cap - float(inventory.quantity))
            quantity = round(min(max(0.0, float(joint_quantity)), free), 8)
            if quantity <= 1e-9:
                continue
            old_quantity = float(inventory.quantity)
            inventory.quantity = round(old_quantity + quantity, 8)
            inventory.avg_cost_basis = round(
                old_quantity * float(inventory.avg_cost_basis) / max(inventory.quantity, 1e-9), 6
            )
            stock[item_id] = round(max(0.0, float(joint_quantity) - quantity), 8)
            claimed[item_id] = round(float(claimed.get(item_id, 0.0)) + quantity, 8)
            moved[item_id] = quantity
        setattr(factory, stock_key, stock)
        setattr(factory, claimed_key, claimed)
        await session.flush()
        return {"success": True, "factory_id": factory.id, "claimed": moved, "remaining_stock": stock}


__all__ = ["JointFactoryService"]
