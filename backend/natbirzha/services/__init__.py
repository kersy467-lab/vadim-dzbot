from backend.natbirzha.services.auth_service import (
    get_strict_natbirzha_user,
    get_current_company,
    validate_strict_telegram_init_data,
    validate_test_init_data
)
from backend.natbirzha.services.company_service import CompanyService
from backend.natbirzha.services.recipes import RECIPES, validate_recipe_dag
from backend.natbirzha.services.production_service import ProductionTickEngine
from backend.natbirzha.services.npc_service import NPCReserveService
from backend.natbirzha.services.market_service import MarketService
from backend.natbirzha.services.stock_service import (
    StockService,
    ValuationStrategy,
    DefaultWeightedValuationStrategy
)
from backend.natbirzha.services.dividend_service import DividendService
from backend.natbirzha.services.bankruptcy_service import BankruptcyService
from backend.natbirzha.services.military_service import MilitaryService
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.upgrade_service import UpgradeService
from backend.natbirzha.services.state_bond_service import StateBondService
from backend.natbirzha.services.state_treasury_service import StateTreasuryService
from backend.natbirzha.services.combat_resolver import (
    ArmySnapshot,
    BattleResult,
    PremiumModifiers,
    resolve_battle,
)
from backend.natbirzha.services.premium_service import PremiumService
from backend.natbirzha.services.army_service import ArmyService
from backend.natbirzha.services.pve_service import PveService
from backend.natbirzha.services.rating_service import RatingService
from backend.natbirzha.services.tournament_service import TournamentService
from backend.natbirzha.services.premium_upgrade_service import PremiumUpgradeService

__all__ = [
    "get_strict_natbirzha_user",
    "get_current_company",
    "validate_strict_telegram_init_data",
    "validate_test_init_data",
    "CompanyService",
    "RECIPES",
    "validate_recipe_dag",
    "ProductionTickEngine",
    "NPCReserveService",
    "MarketService",
    "StockService",
    "ValuationStrategy",
    "DefaultWeightedValuationStrategy",
    "DividendService",
    "BankruptcyService",
    "MilitaryService",
    "IdempotencyService",
    "UpgradeService",
    "StateBondService",
    "StateTreasuryService",
    "ArmySnapshot",
    "BattleResult",
    "PremiumModifiers",
    "resolve_battle",
    "PremiumService",
    "ArmyService",
    "PveService",
    "RatingService",
    "TournamentService",
    "PremiumUpgradeService",
]
