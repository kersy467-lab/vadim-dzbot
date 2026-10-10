"""Constants shared by the isolated NATBIRZHA 2.0 economy."""
from datetime import datetime, timezone

TREASURY_START_CASH = 100_000_000.0
TREASURY_START_STOCK = 10_000.0
STARTING_COMPANY_CASH = 10_000.0
MAX_TRADE_QUANTITY = 10_000.0
MAX_INVENTORY_PER_ITEM = 100_000.0
MAX_CATCH_UP_CYCLES = 100
MAX_FACILITY_LEVEL = 10
FACILITY_UPGRADE_BASE_COST = 2_500.0
FACILITY_OUTPUT_PER_LEVEL = 0.25
XP_PER_CYCLE = 200
XP_PER_LEVEL = 1_000
BUY_MARKUP = 1.20
SELL_MARKDOWN = 0.80
MAX_BANK_LOAN = 50_000.0
MIN_BANK_LOAN = 1_000.0
BANK_LOAN_DAILY_RATE = 0.01
MAX_BANK_LOAN_DAYS = 30
MIN_BANK_DEPOSIT = 1_000.0
MAX_BANK_DEPOSIT = 1_000_000_000.0
BANK_DEPOSIT_DAILY_RATE = 0.0025
MAX_BANK_DEPOSIT_DAYS = 30


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def facility_upgrade_cost(current_level: int) -> float:
    return round(FACILITY_UPGRADE_BASE_COST * int(current_level), 2)


def facility_output_multiplier(level: int) -> float:
    return round(1 + max(0, int(level) - 1) * FACILITY_OUTPUT_PER_LEVEL, 4)


def facility_recipe_at_level(recipe: dict, level: int) -> dict:
    multiplier = facility_output_multiplier(level)
    return {**recipe, "output_quantity": round(float(recipe["output_quantity"]) * multiplier, 4)}


__all__ = [name for name in globals() if name.isupper()] + [
    "_utcnow", "facility_upgrade_cost", "facility_output_multiplier", "facility_recipe_at_level",
]
