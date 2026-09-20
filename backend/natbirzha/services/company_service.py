from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.natbirzha.config import nat_settings, get_game_now, get_game_today, normalize_dt
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.models.inventory import NatInventory, get_item_base_price
from backend.natbirzha.models.military import NatArmy
from backend.natbirzha.models.combat import NatArmyUnit
from backend.db.models import User
from backend.natbirzha.services.access_control import is_creator_user, get_creator_tg_ids
from backend.natbirzha.services.building_catalog import get_building_spec

from backend.natbirzha.services.company_constants import (
    VALID_SPECIALIZATIONS,
    SPECIALIZATION_ALIASES,
    STARTER_FACTORIES,
    STARTER_INVENTORIES,
)


class CompanyService:
    @staticmethod
    async def get_starting_grant(session: AsyncSession, user_id: int) -> tuple[float, int]:
        """Return the one-time cash/PVC grant for a known Telegram user.

        Legacy imports and isolated tests can create a company before the
        school-bot User record exists; those still receive the ordinary start.
        """
        user = await session.get(User, user_id)
        if not user:
            res = await session.execute(select(User).where(User.tg_id == user_id))
            user = res.scalar_one_or_none()
        if user_id in get_creator_tg_ids() or (user and (is_creator_user(user) or user.tg_id in get_creator_tg_ids())):
            return float(nat_settings.CREATOR_STARTING_CASH), int(getattr(nat_settings, "CREATOR_STARTING_PVC", 500))
        if user and bool(user.is_tester):
            return float(nat_settings.STARTING_CASH), int(nat_settings.TESTER_STARTING_PVC)
        return float(nat_settings.STARTING_CASH), 0

    @staticmethod
    async def create_company(
        session: AsyncSession,
        user_id: int,
        name: str,
        specialization: str,
        ticker: Optional[str] = None,
        commit: bool = True
    ) -> NatCompany:
        spec = SPECIALIZATION_ALIASES.get(specialization.lower(), specialization)
        if spec not in VALID_SPECIALIZATIONS:
            raise ValueError(f"Invalid specialization: {specialization}")

        clean_name = name.strip()
        if len(clean_name) < 2 or len(clean_name) > 64:
            raise ValueError("Company name must be between 2 and 64 characters.")

        clean_ticker = "".join(c for c in (ticker or "").strip() if c.isalnum()).upper()[:5] or None

        existing = await session.execute(select(NatCompany).where(NatCompany.user_id == user_id))
        if existing.scalar_one_or_none():
            raise ValueError("User already owns a company.")

        now = get_game_now()
        starting_cash, starting_pvc = await CompanyService.get_starting_grant(session, user_id)

        company = NatCompany(
            user_id=user_id,
            name=clean_name,
            specialization=spec,
            custom_ticker=clean_ticker,
            level=1,
            xp=0,
            cash=starting_cash,
            pvc_balance=starting_pvc,
            nat_balance=starting_pvc,
            territory_tiles=nat_settings.STARTING_TERRITORY_TILES,
            max_territory=20,
            is_bankrupt=False,
            created_at=now,
            updated_at=now
        )
        session.add(company)
        await session.flush()

        # Build initial starter factory
        if spec not in STARTER_FACTORIES:
            raise ValueError(f"Unknown specialization: {specialization}")
        b_type = STARTER_FACTORIES[spec]
        building = get_building_spec(b_type) or {}
        starter_factory = NatFactory(
            company_id=company.id,
            building_type=b_type,
            specialization=spec,
            level=1,
            efficiency=1.0,
            is_active=True,
            workers=int(building.get("workers_required", 10)),
            automation_level=0,
            technology_level=0,
            current_recipe=None,
            cycle_started_at=None,
            cycle_ready_at=None,
            last_produced_at=now,
            created_at=now
        )
        session.add(starter_factory)

        # Starter utilities and raw resources keep every specialization playable from minute one.
        starter_items = STARTER_INVENTORIES.get(spec, {"water": 100.0, "grid_quota": 100.0})
        for item_id, quantity in starter_items.items():
            session.add(NatInventory(
                company_id=company.id, item_id=item_id, quantity=quantity,
                reserved_quantity=0.0, avg_cost_basis=0.0
            ))


        # Initialize base army garrison
        army = NatArmy(
            company_id=company.id,
            infantry=10,
            tanks=0,
            drones=0,
            air_defense=0,
            army_strength=100,
            updated_at=now
        )
        session.add(army)
        session.add(NatArmyUnit(
            company_id=company.id,
            unit_type="infantry",
            quantity=10,
            level=1,
            readiness=10000,
            experience=0,
            updated_at=now,
        ))

        if commit:
            await session.commit()
            await session.refresh(company)
        else:
            await session.flush()
        return company

    @staticmethod
    async def get_by_owner_id(session: AsyncSession, user_id: int) -> Optional[NatCompany]:
        """Find company by internal User.id or Telegram tg_id."""
        res = await session.execute(
            select(NatCompany).where(NatCompany.user_id == user_id).with_for_update()
        )
        comp = res.scalar_one_or_none()
        if comp:
            return comp
        from backend.db.models import User
        user_res = await session.execute(select(User).where(User.tg_id == user_id))
        user = user_res.scalar_one_or_none()
        if user:
            res = await session.execute(select(NatCompany).where(NatCompany.user_id == user.id))
            return res.scalar_one_or_none()
        return None

    @staticmethod
    async def calculate_nav(session: AsyncSession, company: NatCompany) -> float:
        """Alias for calculate_audited_nav."""
        return await CompanyService.calculate_audited_nav(session, company)

    @staticmethod
    async def calculate_audited_nav(session: AsyncSession, company: NatCompany) -> float:
        """Calculates Net Asset Value: Cash + Land + Factories + Inventory."""
        total_nav = float(company.cash)
        # Land valuation: 10,000 cash per tile
        total_nav += company.territory_tiles * 10000.0

        # Factories valuation: 25,000 cash per level
        fac_res = await session.execute(select(NatFactory).where(NatFactory.company_id == company.id))
        factories = fac_res.scalars().all()
        for f in factories:
            total_nav += f.level * 25000.0

        # Inventory valuation at base price
        inv_res = await session.execute(select(NatInventory).where(NatInventory.company_id == company.id))
        inventory = inv_res.scalars().all()
        for it in inventory:
            if it.quantity > 0:
                try:
                    total_nav += it.quantity * get_item_base_price(it.item_id)
                except ValueError:
                    pass

        return round(total_nav, 2)

    @staticmethod
    async def change_specialization(
        session: AsyncSession,
        company: NatCompany,
        new_specialization: str,
        commit: bool = True
    ) -> Dict[str, Any]:
        """Respec specialization with 7-day cooldown and 25% NAV fee."""
        if new_specialization not in VALID_SPECIALIZATIONS:
            raise ValueError("Invalid specialization.")
        locked = (await session.execute(
            select(NatCompany).where(NatCompany.id == company.id).with_for_update()
        )).scalar_one_or_none()
        if not locked:
            raise ValueError("Company not found.")
        company = locked
        if new_specialization == company.specialization:
            raise ValueError("Company already has this specialization.")

        now = normalize_dt(get_game_now())
        if company.last_respec_at:
            last_respec = normalize_dt(company.last_respec_at)
            elapsed = (now - last_respec).total_seconds() / 86400
            if elapsed < nat_settings.RESPEC_COOLDOWN_DAYS:
                remaining = round(nat_settings.RESPEC_COOLDOWN_DAYS - elapsed, 1)
                raise ValueError(f"Respec cooldown active. Wait {remaining} days.")

        nav = await CompanyService.calculate_audited_nav(session, company)
        fee = round(nav * nat_settings.RESPEC_COST_PCT, 2)
        if company.cash < fee:
            raise ValueError(f"Insufficient cash for respec fee. Needed: {fee}, Available: {company.cash}")

        company.cash -= fee
        company.specialization = new_specialization
        company.last_respec_at = now

        # Immediately update all existing factories: old factories drop to 10%
        fac_res = await session.execute(select(NatFactory).where(NatFactory.company_id == company.id))
        for f in fac_res.scalars().all():
            if f.specialization == new_specialization:
                f.efficiency = 1.0
            else:
                f.efficiency = nat_settings.FOREIGN_SPEC_EFFICIENCY

        if commit:
            await session.commit()
        else:
            await session.flush()
        return {"success": True, "new_specialization": new_specialization, "fee_paid": fee}

    @staticmethod
    async def buy_foreign_license(
        session: AsyncSession,
        company: NatCompany,
        target_spec: str,
        commit: bool = True
    ) -> Dict[str, Any]:
        """NAT currency sink: Purchase secondary industry foreign license (up to 12% eff)."""
        if target_spec not in VALID_SPECIALIZATIONS:
            raise ValueError("Invalid target specialization.")
        locked = (await session.execute(
            select(NatCompany).where(NatCompany.id == company.id).with_for_update()
        )).scalar_one_or_none()
        if not locked:
            raise ValueError("Company not found.")
        company = locked
        if target_spec == company.specialization:
            raise ValueError("Cannot license own primary specialization.")
        if company.licensed_foreign_spec == target_spec:
            raise ValueError(f"Company already holds license for {target_spec}.")

        cost = nat_settings.FOREIGN_LICENSE_COST_NAT
        if company.nat_balance < cost:
            raise ValueError(f"Insufficient NAT balance. Required: {cost} NAT, Available: {company.nat_balance} NAT.")

        company.nat_balance -= cost
        company.licensed_foreign_spec = target_spec

        # Boost matching foreign factories to licensed cap (12%)
        fac_res = await session.execute(select(NatFactory).where(NatFactory.company_id == company.id))
        for f in fac_res.scalars().all():
            if f.specialization == target_spec:
                f.efficiency = nat_settings.FOREIGN_LICENSED_MAX

        if commit:
            await session.commit()
        else:
            await session.flush()
        return {
            "success": True,
            "licensed_foreign_spec": target_spec,
            "cost_paid_nat": cost,
            "remaining_nat_balance": company.nat_balance
        }

    @classmethod
    async def reset_company_for_user(cls, session: AsyncSession, user_id: int, commit: bool = True) -> bool:
        """Completely reset and remove all company assets for a user so they can restart."""
        from sqlalchemy import delete, or_, update
        from backend.natbirzha.models import (
            NatAlliance, NatAllianceMember, NatArmy, NatArmyUnit, NatBattle,
            NatBattleSnapshot, NatBondListing, NatBondSettlement, NatContract,
            NatDailyFinancials, NatDividend, NatDividendPayment, NatInstrumentPosition,
            NatInstrumentTrade, NatLoan, NatMarketOrder, NatMarketRestriction,
            NatMarketTrade, NatMarketWarning, NatMilitaryRatingEvent,
            NatMilitaryUpgrade, NatPremiumLedgerEntry, NatPremiumLicense,
            NatPveVictory, NatPvpCooldown, NatRestructuring, NatStateBondHolding,
            NatStock, NatStockHolding, NatStockOrder, NatTournamentParticipant,
        )

        res = await session.execute(select(NatCompany).where(NatCompany.user_id == user_id))
        comp = res.scalar_one_or_none()
        if not comp:
            return False

        cid = comp.id

        # Delete explicit dependants instead of trusting database cascades. This
        # keeps resets complete on SQLite test/dev deployments where foreign-key
        # enforcement may have been disabled in an older database connection.
        battle_ids = select(NatBattle.id).where(or_(
            NatBattle.attacker_company_id == cid,
            NatBattle.defender_company_id == cid,
        ))
        await session.execute(delete(NatPvpCooldown).where(or_(
            NatPvpCooldown.attacker_company_id == cid,
            NatPvpCooldown.defender_company_id == cid,
            NatPvpCooldown.battle_id.in_(battle_ids),
        )))
        await session.execute(delete(NatMilitaryRatingEvent).where(or_(
            NatMilitaryRatingEvent.company_id == cid,
            NatMilitaryRatingEvent.battle_id.in_(battle_ids),
        )))
        await session.execute(delete(NatPveVictory).where(or_(
            NatPveVictory.company_id == cid,
            NatPveVictory.battle_id.in_(battle_ids),
        )))
        await session.execute(delete(NatBattleSnapshot).where(or_(
            NatBattleSnapshot.company_id == cid,
            NatBattleSnapshot.battle_id.in_(battle_ids),
        )))
        await session.execute(delete(NatBattle).where(NatBattle.id.in_(battle_ids)))
        await session.execute(delete(NatArmyUnit).where(NatArmyUnit.company_id == cid))

        stock_ids = select(NatStock.id).where(NatStock.company_id == cid)
        await session.execute(delete(NatDividendPayment).where(or_(
            NatDividendPayment.stock_id.in_(stock_ids),
            NatDividendPayment.holder_company_id == cid,
        )))
        await session.execute(delete(NatDividend).where(NatDividend.stock_id.in_(stock_ids)))
        await session.execute(delete(NatStockOrder).where(or_(
            NatStockOrder.stock_id.in_(stock_ids), NatStockOrder.trader_company_id == cid
        )))
        await session.execute(delete(NatStockHolding).where(or_(
            NatStockHolding.stock_id.in_(stock_ids), NatStockHolding.holder_company_id == cid
        )))

        await session.execute(delete(NatBondListing).where(or_(
            NatBondListing.seller_company_id == cid, NatBondListing.buyer_company_id == cid
        )))
        await session.execute(delete(NatBondSettlement).where(NatBondSettlement.company_id == cid))
        await session.execute(delete(NatStateBondHolding).where(NatStateBondHolding.company_id == cid))
        await session.execute(delete(NatInstrumentTrade).where(NatInstrumentTrade.company_id == cid))
        await session.execute(delete(NatInstrumentPosition).where(NatInstrumentPosition.company_id == cid))
        await session.execute(delete(NatMilitaryUpgrade).where(NatMilitaryUpgrade.company_id == cid))
        await session.execute(delete(NatPremiumLicense).where(NatPremiumLicense.company_id == cid))
        await session.execute(delete(NatPremiumLedgerEntry).where(NatPremiumLedgerEntry.company_id == cid))

        await session.execute(delete(NatMarketTrade).where(or_(
            NatMarketTrade.buyer_company_id == cid, NatMarketTrade.seller_company_id == cid
        )))
        await session.execute(delete(NatLoan).where(NatLoan.company_id == cid))
        await session.execute(update(NatContract).where(
            NatContract.issuer_company_id == cid
        ).values(issuer_company_id=None))
        await session.execute(update(NatContract).where(
            NatContract.target_company_id == cid
        ).values(target_company_id=None))
        await session.execute(delete(NatMarketRestriction).where(NatMarketRestriction.company_id == cid))
        await session.execute(delete(NatMarketWarning).where(NatMarketWarning.company_id == cid))

        alliance_ids = select(NatAlliance.id).where(NatAlliance.leader_company_id == cid)
        await session.execute(delete(NatAllianceMember).where(or_(
            NatAllianceMember.company_id == cid,
            NatAllianceMember.alliance_id.in_(alliance_ids),
        )))
        await session.execute(delete(NatAlliance).where(NatAlliance.id.in_(alliance_ids)))
        await session.execute(delete(NatFactory).where(NatFactory.company_id == cid))
        await session.execute(delete(NatInventory).where(NatInventory.company_id == cid))
        await session.execute(delete(NatMarketOrder).where(NatMarketOrder.company_id == cid))
        await session.execute(delete(NatStock).where(NatStock.company_id == cid))
        await session.execute(delete(NatArmy).where(NatArmy.company_id == cid))
        await session.execute(delete(NatTournamentParticipant).where(NatTournamentParticipant.company_id == cid))
        await session.execute(delete(NatAllianceMember).where(NatAllianceMember.company_id == cid))
        await session.execute(delete(NatDailyFinancials).where(NatDailyFinancials.company_id == cid))
        await session.execute(delete(NatRestructuring).where(NatRestructuring.company_id == cid))
        await session.execute(delete(NatCompany).where(NatCompany.id == cid))
        if commit:
            await session.commit()
        else:
            await session.flush()
        return True


__all__ = [
    "CompanyService",
    "VALID_SPECIALIZATIONS",
    "SPECIALIZATION_ALIASES",
    "STARTER_FACTORIES",
    "STARTER_INVENTORIES",
]
