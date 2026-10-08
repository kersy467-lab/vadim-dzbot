"""Lazy, offline-safe production settlement for active joint factories."""

from backend.natbirzha.services.progression_service import company_production_multiplier


from datetime import datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.catalogs.businesses import get_business_spec, get_joint_factory_recipe
from backend.natbirzha.config import get_game_now, nat_settings, normalize_dt
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.joint_factories import (
    NatJointFactory,
    NatJointFactoryProposal,
    NatJointFactorySettlement,
)
from backend.natbirzha.services.idle_economy_service import IdleEconomyService
from backend.natbirzha.services.tax_service import TaxService
from backend.natbirzha.tax_rules import get_period_bounds, period_production_deadline


def _add_quantity(target: dict[str, float], item_id: str, quantity: float) -> None:
    if quantity > 0:
        target[item_id] = round(float(target.get(item_id, 0.0)) + quantity, 8)


class JointFactorySettlementService:
    """Accrue each owner's half-share of no-input/no-upkeep production."""

    @staticmethod
    async def participants_to_settle(session: AsyncSession, company_id: int) -> set[int]:
        active_rows = (await session.execute(
            select(NatJointFactory.company_a_id, NatJointFactory.company_b_id).where(
                NatJointFactory.status == "ACTIVE",
                or_(
                    NatJointFactory.company_a_id == int(company_id),
                    NatJointFactory.company_b_id == int(company_id),
                ),
            )
        )).all()
        # Lock pending build partners too: accept is a second request after the
        # proposal was committed, and must not create a pair while settlement
        # has locked only one side based on a stale active-factory query.
        pending_rows = (await session.execute(
            select(
                NatJointFactoryProposal.proposer_company_id,
                NatJointFactoryProposal.partner_company_id,
            ).where(
                NatJointFactoryProposal.status == "PENDING",
                or_(
                    NatJointFactoryProposal.proposer_company_id == int(company_id),
                    NatJointFactoryProposal.partner_company_id == int(company_id),
                ),
            )
        )).all()
        return {int(value) for row in (*active_rows, *pending_rows) for value in row}

    @classmethod
    async def settle_for_company(
        cls,
        session: AsyncSession,
        company_id: int,
        *,
        now: datetime | None = None,
    ) -> list[dict]:
        current = normalize_dt(now or get_game_now())
        participants = await cls.participants_to_settle(session, company_id)
        participant_ids = sorted({int(company_id), *participants})
        await session.execute(
            select(NatCompany.id)
            .where(NatCompany.id.in_(participant_ids))
            .order_by(NatCompany.id)
            .with_for_update()
        )
        candidates = (await session.execute(
            select(NatJointFactory.id, NatJointFactory.company_a_id, NatJointFactory.company_b_id)
            .where(
                NatJointFactory.status == "ACTIVE",
                or_(
                    NatJointFactory.company_a_id == int(company_id),
                    NatJointFactory.company_b_id == int(company_id),
                ),
            )
        )).all()
        locked_ids = set(participant_ids)
        eligible_factory_ids = [
            factory_id for factory_id, owner_a_id, owner_b_id in candidates
            if {int(owner_a_id), int(owner_b_id)} <= locked_ids
        ]
        # If a build committed after participant discovery, do not take its JV
        # row while holding only one owner. The next lazy settlement will see
        # and lock the complete pair in sorted order.
        if not eligible_factory_ids:
            return []
        factories = list((await session.execute(
            select(NatJointFactory)
            .where(NatJointFactory.id.in_(eligible_factory_ids), NatJointFactory.status == "ACTIVE")
            .order_by(NatJointFactory.id)
            .with_for_update()
        )).scalars().all())
        results = []
        for factory in factories:
            results.append(await cls._settle_locked(session, factory, current))
        return results

    @classmethod
    async def settle_factory(
        cls,
        session: AsyncSession,
        factory_id: int,
        *,
        now: datetime | None = None,
    ) -> dict:
        current = normalize_dt(now or get_game_now())
        peek = await session.get(NatJointFactory, int(factory_id))
        if peek is None:
            raise ValueError("Совместный завод не найден")
        await session.execute(
            select(NatCompany.id)
            .where(NatCompany.id.in_((peek.company_a_id, peek.company_b_id)))
            .order_by(NatCompany.id)
            .with_for_update()
        )
        factory = await session.scalar(
            select(NatJointFactory)
            .where(NatJointFactory.id == int(factory_id))
            .with_for_update()
        )
        if factory is None:
            raise ValueError("Совместный завод не найден")
        return await cls._settle_locked(session, factory, current)

    @classmethod
    async def breach_for_company(
        cls,
        session: AsyncSession,
        company_id: int,
        *,
        now: datetime | None = None,
    ) -> int:
        """Stop a partnership before bankruptcy and cancel its unaccepted offers."""
        current = normalize_dt(now or get_game_now())
        factories = list((await session.execute(
            select(NatJointFactory).where(
                NatJointFactory.status == "ACTIVE",
                or_(
                    NatJointFactory.company_a_id == int(company_id),
                    NatJointFactory.company_b_id == int(company_id),
                ),
            ).order_by(NatJointFactory.id).with_for_update()
        )).scalars().all())
        for factory in factories:
            factory.status = "BREACHED"
            factory.closed_at = current
            factory.last_settled_at = current
        pending = list((await session.execute(select(NatJointFactoryProposal).where(
            NatJointFactoryProposal.status == "PENDING",
            or_(
                NatJointFactoryProposal.proposer_company_id == int(company_id),
                NatJointFactoryProposal.partner_company_id == int(company_id),
            ),
        ).with_for_update())).scalars().all())
        for proposal in pending:
            proposal.status = "CANCELLED"
            proposal.responded_at = current
        await session.flush()
        return len(factories)

    @staticmethod
    async def preserve_partner_stock_on_reset(session: AsyncSession, company_id: int) -> None:
        """Move each surviving partner's unclaimed share out before a reset deletes a JV."""
        factories = list((await session.execute(
            select(NatJointFactory).where(
                or_(
                    NatJointFactory.company_a_id == int(company_id),
                    NatJointFactory.company_b_id == int(company_id),
                ),
            ).order_by(NatJointFactory.id).with_for_update()
        )).scalars().all())
        for factory in factories:
            if int(factory.company_a_id) == int(company_id):
                partner_id, partner_stock = factory.company_b_id, dict(factory.stock_b_json or {})
            else:
                partner_id, partner_stock = factory.company_a_id, dict(factory.stock_a_json or {})
            for item_id, quantity in partner_stock.items():
                quantity = max(0.0, float(quantity))
                if quantity <= 0:
                    continue
                inventory = await session.scalar(select(NatInventory).where(
                    NatInventory.company_id == partner_id,
                    NatInventory.item_id == item_id,
                ).with_for_update())
                if inventory is None:
                    session.add(NatInventory(
                        company_id=partner_id,
                        item_id=item_id,
                        quantity=quantity,
                        reserved_quantity=0.0,
                        avg_cost_basis=0.0,
                    ))
                    continue
                old_quantity = max(0.0, float(inventory.quantity))
                new_quantity = old_quantity + quantity
                inventory.avg_cost_basis = round(
                    old_quantity * float(inventory.avg_cost_basis) / max(new_quantity, 1e-9), 6
                )
                inventory.quantity = round(new_quantity, 8)
        await session.flush()

    @classmethod
    async def _settle_locked(
        cls,
        session: AsyncSession,
        factory: NatJointFactory,
        current: datetime,
    ) -> dict:
        if factory.status != "ACTIVE":
            return {"factory_id": factory.id, "settled_hours": 0.0, "status": factory.status}
        companies = list((await session.execute(
            select(NatCompany)
            .where(NatCompany.id.in_((factory.company_a_id, factory.company_b_id)))
            .order_by(NatCompany.id)
            .with_for_update()
        )).scalars().all())
        by_id = {company.id: company for company in companies}
        company_a = by_id.get(factory.company_a_id)
        company_b = by_id.get(factory.company_b_id)
        if company_a is None or company_b is None or company_a.is_bankrupt or company_b.is_bankrupt:
            factory.status = "BREACHED"
            factory.closed_at = current
            factory.last_settled_at = current
            await session.flush()
            return {"factory_id": factory.id, "settled_hours": 0.0, "status": "BREACHED"}

        recipe = get_joint_factory_recipe(factory.recipe_id)
        if recipe is None:
            factory.status = "BREACHED"
            factory.closed_at = current
            factory.last_settled_at = current
            await session.flush()
            return {"factory_id": factory.id, "settled_hours": 0.0, "status": "BREACHED"}

        started = normalize_dt(factory.last_settled_at) or current
        if current <= started:
            return {"factory_id": factory.id, "settled_hours": 0.0, "status": "ACTIVE"}

        cap_hours = min(
            IdleEconomyService.offline_cap_hours(company_a),
            IdleEconomyService.offline_cap_hours(company_b),
        )
        planned_end = min(current, started + timedelta(hours=max(1, int(cap_hours))))
        for company in (company_a, company_b):
            tax = await TaxService.summary(session, company.id, now=current)
            unpaid_period = tax.get("oldest_unpaid_date")
            if unpaid_period:
                deadline = TaxService.production_deadline(datetime.fromisoformat(unpaid_period))
            else:
                business_rows = (await session.execute(select(
                    NatBusiness.business_type, NatBusiness.last_settled_at
                ).where(NatBusiness.company_id == company.id))).all()
                business_cursors = [
                    normalize_dt(cursor)
                    for business_type, cursor in business_rows
                    if (get_business_spec(business_type) or {}).get("legacy_hidden") is not True
                ]
                oldest_cursor = min(
                    (cursor for cursor in business_cursors if cursor is not None),
                    default=started,
                )
                _, period_end = get_period_bounds(oldest_cursor)
                deadline = period_production_deadline(period_end)
            planned_end = min(planned_end, deadline)

        level = recipe["levels"][max(1, min(4, int(factory.level))) - 1]
        stock_a = dict(factory.stock_a_json or {})
        stock_b = dict(factory.stock_b_json or {})
        rate_by_item = {
            item_id: float(rate)
            for item_id, rate in level["outputs_per_hour"].items()
            if float(rate) > 0
        }
        bonus_a = company_production_multiplier(company_a)
        bonus_b = company_production_multiplier(company_b)
        maximum_stock = max(0.0, float(nat_settings.INVENTORY_MAX_QUANTITY_PER_ITEM))
        allowed_hours = max(0.0, (planned_end - started).total_seconds() / 3600)
        for item_id, rate in rate_by_item.items():
            owner_rate = rate / 2
            if owner_rate <= 0:
                continue
            allowed_hours = min(
                allowed_hours,
                max(0.0, maximum_stock - float(stock_a.get(item_id, 0.0))) / (owner_rate * bonus_a),
                max(0.0, maximum_stock - float(stock_b.get(item_id, 0.0))) / (owner_rate * bonus_b),
            )

        produced: dict[str, float] = {}
        for item_id, rate in rate_by_item.items():
            quantity_a = round(rate * allowed_hours * bonus_a / 2, 8)
            quantity_b = round(rate * allowed_hours * bonus_b / 2, 8)
            produced[item_id] = round(quantity_a + quantity_b, 8)
            _add_quantity(stock_a, item_id, quantity_a)
            _add_quantity(stock_b, item_id, quantity_b)

        end = started + timedelta(hours=allowed_hours)
        if allowed_hours > 1e-9:
            session.add(NatJointFactorySettlement(
                factory_id=factory.id,
                period_start=started,
                period_end=end,
                quantity_by_item_json=produced,
            ))
        total_produced = dict(factory.total_produced_json or {})
        for item_id, quantity in produced.items():
            _add_quantity(total_produced, item_id, quantity)
        factory.stock_a_json = stock_a
        factory.stock_b_json = stock_b
        factory.total_produced_json = total_produced
        # Offline-cap, tax-deadline and full-buffer time is skipped, never paid
        # back later, matching ordinary idle-factory settlement semantics.
        factory.last_settled_at = current
        await session.flush()
        return {
            "factory_id": factory.id,
            "settled_hours": round(allowed_hours, 6),
            "produced": produced,
            "status": factory.status,
        }


__all__ = ["JointFactorySettlementService"]
