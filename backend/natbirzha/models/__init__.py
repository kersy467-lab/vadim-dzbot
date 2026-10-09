"""
NATBIRZHA Database Models Package.
All models inherit from Base and are automatically discovered by SQLAlchemy.
"""

from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.models.next_game import NatNextGameCompany
from backend.natbirzha.models.bankruptcy_market import NatBankruptcyMarketLot
from backend.natbirzha.models.inventory import (
    CANONICAL_ITEMS,
    NatInventory,
    get_item_base_price,
    get_item_name,
    get_npc_buy_price,
    get_npc_sell_price
)
from backend.natbirzha.models.market import NatMarketOrder, NatMarketTrade
from backend.natbirzha.models.stocks import (
    NatStock,
    NatStockPriceSnapshot,
    NatStockTrade,
    NatStockHolding,
    NatStockOrder,
    NatDividend,
    NatDividendPayment,
    NatHourlyDividendAccrual,
    NatHourlyDividendPayment,
)
from backend.natbirzha.models.contracts import NatContract, NatLoan
from backend.natbirzha.models.military import NatArmy, NatTournament, NatTournamentParticipant
from backend.natbirzha.models.alliances import NatAlliance, NatAllianceMember
from backend.natbirzha.models.restructuring import NatRestructuring, NatDailyFinancials
from backend.natbirzha.models.idempotency import NatIdempotencyRecord
from backend.natbirzha.models.npc import NatNpcDailyVolume, NatNpcCompanyDailyVolume, NatStateReserveStock
from backend.natbirzha.models.premium import NatMilitaryUpgrade, NatPremiumLedgerEntry, NatPremiumLicense
from backend.natbirzha.models.season import NatSeasonResetOperation
from backend.natbirzha.models.economy_metrics import NatEconomyEvent
from backend.natbirzha.models.combat import (
    NatArmyUnit,
    NatBattle,
    NatBattleSnapshot,
    NatMilitaryRatingEvent,
    NatPveCorporation,
    NatPveVictory,
    NatPvpCooldown,
)
from backend.natbirzha.models.instruments import (
    NatInstrumentPosition,
    NatInstrumentTrade,
    NatReferenceRateSnapshot,
)
from backend.natbirzha.models.creator import (
    NatStateTreasury,
    NatCreatorAuditLog,
    NatMarketRestriction,
    NatMarketWarning,
    NatStateBond,
    NatStateBondHolding,
    NatBondSettlement,
    NatBondListing,
)
from backend.natbirzha.models.state_shares import (
    NatStateShare,
    NatStateShareHolding,
    NatStateShareOperation,
    NatStateShareDailySettlement,
    NatStateShareDividendPayment,
)
from backend.natbirzha.models.state_credit import NatStateCreditLoan
from backend.natbirzha.models.business import (
    BUSINESS_STATUSES,
    NatBusiness,
    NatBusinessIncomeDaily,
    NatBusinessIncomePeriod,
    NatCompanyEconomyState,
)
from backend.natbirzha.models.business_assets import (
    NatBusinessEmployee,
    NatBusinessProject,
    NatBusinessSupplyPolicy,
    NatBusinessVehicle,
)
from backend.natbirzha.models.military_infrastructure import (
    NatArmyTraining,
    NatMilitaryInfrastructure,
)
from backend.natbirzha.models.hospital import NatHospitalWard
from backend.natbirzha.models.tax import NatCompanyProfitPeriod, NatTaxDaily, NatTaxPeriod
from backend.natbirzha.models.sabotage import NatActiveSabotage
from backend.natbirzha.models.player_deals import NatSupplyDeal, NatSupplyDealSettlement
from backend.natbirzha.models.city_orders import (
    NatCityOrder, NatCityOrderCycleState, NatCityOrderDelivery,
)
from backend.natbirzha.models.liquidity import NatLiquiditySnapshot
from backend.natbirzha.models.hybrid_mergers import NatHybridMerger
from backend.natbirzha.models.joint_factories import (
    NatJointFactory,
    NatJointFactoryProposal,
    NatJointFactorySettlement,
)

__all__ = [
    "NatCompany",
    "NatNextGameCompany",
    "NatFactory",
    "NatBankruptcyMarketLot",
    "CANONICAL_ITEMS",
    "NatInventory",
    "get_item_base_price",
    "get_item_name",
    "get_npc_buy_price",
    "get_npc_sell_price",
    "NatMarketOrder",
    "NatMarketTrade",
    "NatStock",
    "NatStockPriceSnapshot",
    "NatStockTrade",
    "NatStockHolding",
    "NatStockOrder",
    "NatDividend",
    "NatDividendPayment",
    "NatHourlyDividendAccrual",
    "NatHourlyDividendPayment",
    "NatContract",
    "NatLoan",
    "NatArmy",
    "NatTournament",
    "NatTournamentParticipant",
    "NatAlliance",
    "NatAllianceMember",
    "NatRestructuring",
    "NatDailyFinancials",
    "NatIdempotencyRecord",
    "NatNpcDailyVolume",
    "NatNpcCompanyDailyVolume",
    "NatStateReserveStock",
    "NatPremiumLedgerEntry",
    "NatPremiumLicense",
    "NatMilitaryUpgrade",
    "NatSeasonResetOperation",
    "NatEconomyEvent",
    "NatArmyUnit",
    "NatBattle",
    "NatBattleSnapshot",
    "NatMilitaryRatingEvent",
    "NatPveCorporation",
    "NatPveVictory",
    "NatPvpCooldown",
    "NatReferenceRateSnapshot",
    "NatInstrumentPosition",
    "NatInstrumentTrade",
    "NatStateTreasury",
    "NatCreatorAuditLog",
    "NatMarketRestriction",
    "NatMarketWarning",
    "NatStateBond",
    "NatStateBondHolding",
    "NatBondSettlement",
    "NatBondListing",
    "NatStateShare",
    "NatStateShareHolding",
    "NatStateShareOperation",
    "NatStateShareDailySettlement",
    "NatStateShareDividendPayment",
    "NatStateCreditLoan",
    "BUSINESS_STATUSES",
    "NatBusiness",
    "NatBusinessIncomeDaily",
    "NatBusinessIncomePeriod",
    "NatCompanyEconomyState",
    "NatBusinessSupplyPolicy",
    "NatBusinessVehicle",
    "NatBusinessEmployee",
    "NatBusinessProject",
    "NatMilitaryInfrastructure",
    "NatArmyTraining",
    "NatHospitalWard",
    "NatTaxDaily",
    "NatTaxPeriod",
    "NatCompanyProfitPeriod",
    "NatActiveSabotage",
    "NatSupplyDeal",
    "NatSupplyDealSettlement",
    "NatCityOrder",
    "NatCityOrderCycleState",
    "NatCityOrderDelivery",
    "NatLiquiditySnapshot",
    "NatHybridMerger",
    "NatJointFactory",
    "NatJointFactoryProposal",
    "NatJointFactorySettlement",
]

from backend.natbirzha.models.rebirth import NatCompanyRebirth
from backend.natbirzha.models.company_aid import NatCompanyAidRequest, NatCompanyAidTransfer
from backend.natbirzha.models.admin_rebirth import NatAdminRebirthSchedule

__all__.extend([
    "NatCompanyRebirth", "NatCompanyAidRequest", "NatCompanyAidTransfer",
    "NatAdminRebirthSchedule",
])
