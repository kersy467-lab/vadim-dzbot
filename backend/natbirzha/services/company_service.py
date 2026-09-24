from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.natbirzha.config import nat_settings, get_game_now, get_game_today, normalize_dt
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.inventory import NatInventory, get_item_base_price
from backend.db.models import User
from backend.natbirzha.services.access_control import is_creator_user, get_creator_tg_ids

from backend.natbirzha.services.company_constants import (
    VALID_SPECIALIZATIONS,
    SPECIALIZATION_ALIASES,
    STARTER_FACTORIES,
)
from backend.natbirzha.services.company_bootstrap import bootstrap_company_state
from backend.natbirzha.services.company_reset_v2 import delete_v2_company_state


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
            return float(nat_settings.STARTING_CASH), int(getattr(nat_settings, "CREATOR_STARTING_PVC", 200))
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
            raise ValueError("Неизвестная отрасль компании")

        clean_name = name.strip()
        if len(clean_name) < 2 or len(clean_name) > 64:
            raise ValueError("Название компании должно содержать от 2 до 64 символов")

        clean_ticker = "".join(c for c in (ticker or "").strip() if c.isalnum()).upper()[:5] or None

        existing = await session.execute(select(NatCompany).where(NatCompany.user_id == user_id))
        if existing.scalar_one_or_none():
            raise ValueError("У вас уже есть компания")

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

        await bootstrap_company_state(session, company, now=now)

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

        # Tycoon V2 enterprises are real company assets too. Legacy hidden
        # aggregate rows are intentionally excluded from the new economy.
        biz_res = await session.execute(
            select(NatBusiness).where(
                NatBusiness.company_id == company.id, NatBusiness.status != "BANKRUPT"
            )
        )
        from backend.natbirzha.catalogs.businesses import get_business_spec
        for business in biz_res.scalars().all():
            spec = get_business_spec(business.business_type)
            if spec and not spec.get("legacy_hidden"):
                total_nav += max(0.0, float(business.capital_invested)) * 0.70

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
            raise ValueError("Неизвестная отрасль")
        locked = (await session.execute(
            select(NatCompany).where(NatCompany.id == company.id).with_for_update()
        )).scalar_one_or_none()
        if not locked:
            raise ValueError("Компания не найдена")
        company = locked
        if new_specialization == company.specialization:
            raise ValueError("Эта отрасль уже является основной")

        now = normalize_dt(get_game_now())
        if company.last_respec_at:
            last_respec = normalize_dt(company.last_respec_at)
            elapsed = (now - last_respec).total_seconds() / 86400
            if elapsed < nat_settings.RESPEC_COOLDOWN_DAYS:
                remaining = round(nat_settings.RESPEC_COOLDOWN_DAYS - elapsed, 1)
                raise ValueError(f"Смена отрасли на перезарядке. Подождите ещё {remaining} дн.")

        nav = await CompanyService.calculate_audited_nav(session, company)
        fee = round(nav * nat_settings.RESPEC_COST_PCT, 2)
        if company.cash < fee:
            raise ValueError(f"Недостаточно cash для смены отрасли: нужно {fee}, доступно {company.cash}")

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
            raise ValueError("Неизвестная дополнительная отрасль")
        locked = (await session.execute(
            select(NatCompany).where(NatCompany.id == company.id).with_for_update()
        )).scalar_one_or_none()
        if not locked:
            raise ValueError("Компания не найдена")
        company = locked
        if target_spec == company.specialization:
            raise ValueError("Нельзя покупать лицензию на собственную основную отрасль")
        if company.licensed_foreign_spec == target_spec:
            raise ValueError("Лицензия на эту дополнительную отрасль уже куплена")

        cost = nat_settings.FOREIGN_LICENSE_COST_NAT
        if company.nat_balance < cost:
            raise ValueError(f"Недостаточно PVC: нужно {cost}, доступно {company.nat_balance}")

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
            NatHourlyDividendAccrual, NatHourlyDividendPayment,
            NatInstrumentTrade, NatLoan, NatMarketOrder, NatMarketRestriction,
            NatMarketTrade, NatMarketWarning, NatMilitaryRatingEvent,
            NatMilitaryUpgrade, NatPremiumLedgerEntry, NatPremiumLicense,
            NatPveVictory, NatPvpCooldown, NatRestructuring, NatStateBondHolding,
            NatStock, NatStockHolding, NatStockOrder, NatTournamentParticipant,
            NatStateCreditLoan,
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
        hourly_accrual_ids = select(NatHourlyDividendAccrual.id).where(
            NatHourlyDividendAccrual.stock_id.in_(stock_ids)
        )
        await session.execute(delete(NatHourlyDividendPayment).where(or_(
            NatHourlyDividendPayment.stock_id.in_(stock_ids),
            NatHourlyDividendPayment.holder_company_id == cid,
            NatHourlyDividendPayment.accrual_id.in_(hourly_accrual_ids),
        )))
        await session.execute(delete(NatHourlyDividendAccrual).where(
            NatHourlyDividendAccrual.stock_id.in_(stock_ids)
        ))
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
        await session.execute(delete(NatStateCreditLoan).where(NatStateCreditLoan.company_id == cid))
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
        await delete_v2_company_state(session, cid)
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
