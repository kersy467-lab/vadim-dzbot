"""Public NATBIRZHA service exports loaded lazily.

Keeping this package initializer side-effect free lets pure catalog/rule tests import
individual services without creating a database engine at import time.
"""

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    "get_strict_natbirzha_user": ("auth_service", "get_strict_natbirzha_user"),
    "get_current_company": ("auth_service", "get_current_company"),
    "validate_strict_telegram_init_data": ("auth_service", "validate_strict_telegram_init_data"),
    "validate_test_init_data": ("auth_service", "validate_test_init_data"),
    "CompanyService": ("company_service", "CompanyService"),
    "RECIPES": ("recipes", "RECIPES"),
    "validate_recipe_dag": ("recipes", "validate_recipe_dag"),
    "ProductionTickEngine": ("production_service", "ProductionTickEngine"),
    "NPCReserveService": ("npc_service", "NPCReserveService"),
    "MarketService": ("market_service", "MarketService"),
    "StockService": ("stock_service", "StockService"),
    "ValuationStrategy": ("stock_service", "ValuationStrategy"),
    "DefaultWeightedValuationStrategy": ("stock_service", "DefaultWeightedValuationStrategy"),
    "DividendService": ("dividend_service", "DividendService"),
    "BankruptcyService": ("bankruptcy_service", "BankruptcyService"),
    "MilitaryService": ("military_service", "MilitaryService"),
    "IdempotencyService": ("idempotency_service", "IdempotencyService"),
    "UpgradeService": ("upgrade_service", "UpgradeService"),
    "StateBondService": ("state_bond_service", "StateBondService"),
    "StateTreasuryService": ("state_treasury_service", "StateTreasuryService"),
    "ArmySnapshot": ("combat_resolver", "ArmySnapshot"),
    "BattleResult": ("combat_resolver", "BattleResult"),
    "PremiumModifiers": ("combat_resolver", "PremiumModifiers"),
    "resolve_battle": ("combat_resolver", "resolve_battle"),
    "PremiumService": ("premium_service", "PremiumService"),
    "ArmyService": ("army_service", "ArmyService"),
    "PveService": ("pve_service", "PveService"),
    "RatingService": ("rating_service", "RatingService"),
    "TournamentService": ("tournament_service", "TournamentService"),
    "PremiumUpgradeService": ("premium_upgrade_service", "PremiumUpgradeService"),
    "EventBroadcaster": ("event_broadcaster", "EventBroadcaster"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attr_name = target
    value = getattr(import_module(f"backend.natbirzha.services.{module_name}"), attr_name)
    globals()[name] = value
    return value
