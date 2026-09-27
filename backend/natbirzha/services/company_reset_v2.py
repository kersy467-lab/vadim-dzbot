"""Explicit cleanup for NATBIRZHA company-owned rows during a user reset."""

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models import (
    NatAlliance,
    NatAllianceMember,
    NatArmy,
    NatArmyTraining,
    NatArmyUnit,
    NatBankruptcyMarketLot,
    NatBattle,
    NatBattleSnapshot,
    NatBondListing,
    NatBondSettlement,
    NatBusiness,
    NatBusinessEmployee,
    NatBusinessIncomeDaily,
    NatBusinessIncomePeriod,
    NatBusinessProject,
    NatBusinessSupplyPolicy,
    NatBusinessVehicle,
    NatCityOrderDelivery,
    NatCompany,
    NatCompanyEconomyState,
    NatCompanyProfitPeriod,
    NatContract,
    NatDailyFinancials,
    NatDividend,
    NatDividendPayment,
    NatEconomyEvent,
    NatFactory,
    NatHospitalWard,
    NatHourlyDividendAccrual,
    NatHourlyDividendPayment,
    NatHybridMerger,
    NatInstrumentPosition,
    NatInstrumentTrade,
    NatInventory,
    NatJointFactory,
    NatJointFactoryProposal,
    NatJointFactorySettlement,
    NatLoan,
    NatMarketOrder,
    NatMarketRestriction,
    NatMarketTrade,
    NatMarketWarning,
    NatMilitaryInfrastructure,
    NatMilitaryRatingEvent,
    NatMilitaryUpgrade,
    NatPremiumLedgerEntry,
    NatPremiumLicense,
    NatPveVictory,
    NatPvpCooldown,
    NatRestructuring,
    NatStateBondHolding,
    NatStateCreditLoan,
    NatStateShareDividendPayment,
    NatStateShareHolding,
    NatStock,
    NatStockHolding,
    NatStockOrder,
    NatStockPriceSnapshot,
    NatSupplyDeal,
    NatSupplyDealSettlement,
    NatTaxDaily,
    NatTaxPeriod,
    NatTournamentParticipant,
)


async def delete_company_complete_state(session: AsyncSession, cid: int) -> None:
    """Delete all company dependants in topological order without relying on DB cascades."""
    reset_factory_ids = select(NatFactory.id).where(NatFactory.company_id == cid)
    reset_business_ids = select(NatBusiness.id).where(NatBusiness.company_id == cid)
    reset_stock_ids = select(NatStock.id).where(NatStock.company_id == cid)
    reset_joint_factory_ids = select(NatJointFactory.id).where(or_(
        NatJointFactory.company_a_id == cid,
        NatJointFactory.company_b_id == cid,
    ))

    # 1. City orders & bankruptcy marketplace
    await session.execute(update(NatCityOrderDelivery).where(
        NatCityOrderDelivery.company_id == cid
    ).values(company_id=None))

    await session.execute(update(NatBankruptcyMarketLot).where(
        NatBankruptcyMarketLot.status == "ACTIVE",
        or_(
            NatBankruptcyMarketLot.former_company_id == cid,
            (NatBankruptcyMarketLot.asset_kind == "FACTORY") & NatBankruptcyMarketLot.asset_id.in_(reset_factory_ids),
            (NatBankruptcyMarketLot.asset_kind == "BUSINESS") & NatBankruptcyMarketLot.asset_id.in_(reset_business_ids),
            (NatBankruptcyMarketLot.asset_kind == "STOCK") & NatBankruptcyMarketLot.asset_id.in_(reset_stock_ids),
            (NatBankruptcyMarketLot.asset_kind == "JOINT_GOODS") & NatBankruptcyMarketLot.asset_id.in_(reset_joint_factory_ids),
        ),
    ).values(status="CANCELLED"))
    await session.execute(update(NatBankruptcyMarketLot).where(
        NatBankruptcyMarketLot.former_company_id == cid
    ).values(former_company_id=None))
    await session.execute(update(NatBankruptcyMarketLot).where(
        NatBankruptcyMarketLot.buyer_company_id == cid
    ).values(buyer_company_id=None))

    # 2. Economy metrics telemetry
    await session.execute(update(NatEconomyEvent).where(
        NatEconomyEvent.company_id == cid
    ).values(company_id=None))

    # 3. Combat, ratings, PvP cooldowns & military units
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
    await session.execute(delete(NatHospitalWard).where(NatHospitalWard.company_id == cid))
    await session.execute(delete(NatArmyTraining).where(NatArmyTraining.company_id == cid))
    await session.execute(delete(NatMilitaryInfrastructure).where(NatMilitaryInfrastructure.company_id == cid))
    await session.execute(delete(NatMilitaryUpgrade).where(NatMilitaryUpgrade.company_id == cid))
    await session.execute(delete(NatTournamentParticipant).where(NatTournamentParticipant.company_id == cid))
    await session.execute(delete(NatArmy).where(NatArmy.company_id == cid))

    # 4. State share dividends and holdings
    await session.execute(delete(NatStateShareDividendPayment).where(NatStateShareDividendPayment.company_id == cid))
    await session.execute(delete(NatStateShareHolding).where(NatStateShareHolding.company_id == cid))

    # 5. Financial bonds, reference instruments, premium ledger and loans
    await session.execute(delete(NatBondListing).where(or_(
        NatBondListing.seller_company_id == cid, NatBondListing.buyer_company_id == cid
    )))
    await session.execute(delete(NatBondSettlement).where(NatBondSettlement.company_id == cid))
    await session.execute(delete(NatStateBondHolding).where(NatStateBondHolding.company_id == cid))
    await session.execute(delete(NatInstrumentTrade).where(NatInstrumentTrade.company_id == cid))
    await session.execute(delete(NatInstrumentPosition).where(NatInstrumentPosition.company_id == cid))
    await session.execute(delete(NatPremiumLicense).where(NatPremiumLicense.company_id == cid))
    await session.execute(delete(NatPremiumLedgerEntry).where(NatPremiumLedgerEntry.company_id == cid))
    await session.execute(delete(NatMarketTrade).where(or_(
        NatMarketTrade.buyer_company_id == cid, NatMarketTrade.seller_company_id == cid
    )))
    await session.execute(delete(NatLoan).where(NatLoan.company_id == cid))
    await session.execute(delete(NatStateCreditLoan).where(NatStateCreditLoan.company_id == cid))

    # 6. Bilateral supply deals and settlement references
    deal_ids = select(NatSupplyDeal.id).where(or_(
        NatSupplyDeal.buyer_company_id == cid,
        NatSupplyDeal.supplier_company_id == cid,
    ))
    await session.execute(delete(NatSupplyDealSettlement).where(
        NatSupplyDealSettlement.deal_id.in_(deal_ids)
    ))
    await session.execute(update(NatSupplyDealSettlement).where(
        NatSupplyDealSettlement.business_id.in_(reset_business_ids)
    ).values(business_id=None))
    await session.execute(delete(NatSupplyDeal).where(NatSupplyDeal.id.in_(deal_ids)))

    # 7. Joint factories
    await session.execute(delete(NatJointFactorySettlement).where(
        NatJointFactorySettlement.factory_id.in_(reset_joint_factory_ids)
    ))
    await session.execute(delete(NatJointFactoryProposal).where(or_(
        NatJointFactoryProposal.proposer_company_id == cid,
        NatJointFactoryProposal.partner_company_id == cid,
        NatJointFactoryProposal.factory_id.in_(reset_joint_factory_ids),
    )))
    await session.execute(delete(NatJointFactory).where(NatJointFactory.id.in_(reset_joint_factory_ids)))

    # 8. Contracts, market warnings, market restrictions and alliances
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

    # 9. Hybrid mergers, business assets and tycoon businesses
    await session.execute(delete(NatHybridMerger).where(or_(
        NatHybridMerger.company_id == cid,
        NatHybridMerger.source_business_a_id.in_(reset_business_ids),
        NatHybridMerger.source_business_b_id.in_(reset_business_ids),
        NatHybridMerger.hybrid_business_id.in_(reset_business_ids),
    )))
    await session.execute(delete(NatBusinessSupplyPolicy).where(NatBusinessSupplyPolicy.business_id.in_(reset_business_ids)))
    await session.execute(delete(NatBusinessVehicle).where(NatBusinessVehicle.business_id.in_(reset_business_ids)))
    await session.execute(delete(NatBusinessEmployee).where(NatBusinessEmployee.business_id.in_(reset_business_ids)))
    await session.execute(delete(NatBusinessProject).where(NatBusinessProject.business_id.in_(reset_business_ids)))
    await session.execute(delete(NatBusinessIncomeDaily).where(NatBusinessIncomeDaily.business_id.in_(reset_business_ids)))
    await session.execute(delete(NatBusinessIncomePeriod).where(NatBusinessIncomePeriod.business_id.in_(reset_business_ids)))
    await session.execute(delete(NatBusiness).where(NatBusiness.company_id == cid))

    # 10. Taxes and economy cache
    await session.execute(delete(NatCompanyProfitPeriod).where(NatCompanyProfitPeriod.company_id == cid))
    await session.execute(delete(NatTaxDaily).where(NatTaxDaily.company_id == cid))
    await session.execute(delete(NatTaxPeriod).where(NatTaxPeriod.company_id == cid))
    await session.execute(delete(NatCompanyEconomyState).where(NatCompanyEconomyState.company_id == cid))

    # 11. Stocks, orderbook, snapshots and dividends
    hourly_accrual_ids = select(NatHourlyDividendAccrual.id).where(
        NatHourlyDividendAccrual.stock_id.in_(reset_stock_ids)
    )
    await session.execute(delete(NatHourlyDividendPayment).where(or_(
        NatHourlyDividendPayment.stock_id.in_(reset_stock_ids),
        NatHourlyDividendPayment.holder_company_id == cid,
        NatHourlyDividendPayment.accrual_id.in_(hourly_accrual_ids),
    )))
    await session.execute(delete(NatHourlyDividendAccrual).where(
        NatHourlyDividendAccrual.stock_id.in_(reset_stock_ids)
    ))
    await session.execute(delete(NatDividendPayment).where(or_(
        NatDividendPayment.stock_id.in_(reset_stock_ids),
        NatDividendPayment.holder_company_id == cid,
    )))
    await session.execute(delete(NatDividend).where(NatDividend.stock_id.in_(reset_stock_ids)))
    await session.execute(delete(NatStockOrder).where(or_(
        NatStockOrder.stock_id.in_(reset_stock_ids), NatStockOrder.trader_company_id == cid
    )))
    await session.execute(delete(NatStockHolding).where(or_(
        NatStockHolding.stock_id.in_(reset_stock_ids), NatStockHolding.holder_company_id == cid
    )))
    await session.execute(delete(NatStockPriceSnapshot).where(
        NatStockPriceSnapshot.stock_id.in_(reset_stock_ids)
    ))
    await session.execute(delete(NatStock).where(NatStock.company_id == cid))

    # 12. Starter factories, inventory, market orders, restructuring and core company record
    await session.execute(delete(NatFactory).where(NatFactory.company_id == cid))
    await session.execute(delete(NatInventory).where(NatInventory.company_id == cid))
    await session.execute(delete(NatMarketOrder).where(NatMarketOrder.company_id == cid))
    await session.execute(delete(NatDailyFinancials).where(NatDailyFinancials.company_id == cid))
    await session.execute(delete(NatRestructuring).where(NatRestructuring.company_id == cid))
    await session.execute(delete(NatCompany).where(NatCompany.id == cid))


async def delete_v2_company_state(session: AsyncSession, company_id: int) -> None:
    """Backward-compatible wrapper for V2 business/tax cleanup."""
    reset_business_ids = select(NatBusiness.id).where(NatBusiness.company_id == company_id)

    await session.execute(delete(NatHybridMerger).where(or_(
        NatHybridMerger.company_id == company_id,
        NatHybridMerger.source_business_a_id.in_(reset_business_ids),
        NatHybridMerger.source_business_b_id.in_(reset_business_ids),
        NatHybridMerger.hybrid_business_id.in_(reset_business_ids),
    )))
    await session.execute(delete(NatBusinessSupplyPolicy).where(NatBusinessSupplyPolicy.business_id.in_(reset_business_ids)))
    await session.execute(delete(NatBusinessVehicle).where(NatBusinessVehicle.business_id.in_(reset_business_ids)))
    await session.execute(delete(NatBusinessEmployee).where(NatBusinessEmployee.business_id.in_(reset_business_ids)))
    await session.execute(delete(NatBusinessProject).where(NatBusinessProject.business_id.in_(reset_business_ids)))
    await session.execute(delete(NatBusinessIncomeDaily).where(NatBusinessIncomeDaily.business_id.in_(reset_business_ids)))
    await session.execute(delete(NatBusinessIncomePeriod).where(NatBusinessIncomePeriod.business_id.in_(reset_business_ids)))
    await session.execute(delete(NatBusiness).where(NatBusiness.company_id == company_id))

    await session.execute(delete(NatCompanyProfitPeriod).where(NatCompanyProfitPeriod.company_id == company_id))
    await session.execute(delete(NatCompanyEconomyState).where(NatCompanyEconomyState.company_id == company_id))
    await session.execute(delete(NatTaxDaily).where(NatTaxDaily.company_id == company_id))
    await session.execute(delete(NatTaxPeriod).where(NatTaxPeriod.company_id == company_id))
    await session.execute(delete(NatMilitaryInfrastructure).where(NatMilitaryInfrastructure.company_id == company_id))
    await session.execute(delete(NatArmyTraining).where(NatArmyTraining.company_id == company_id))


__all__ = ["delete_company_complete_state", "delete_v2_company_state"]
