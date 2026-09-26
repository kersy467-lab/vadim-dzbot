import os
from datetime import datetime, date, time
import zoneinfo
from typing import Dict, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AliasChoices, Field

class NatbirzhaSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    GAME_TIMEZONE: str = Field(default="Asia/Yekaterinburg", description="Timezone for calendar settlements")
    ALLOW_TEST_AUTH: bool = Field(default=False, validation_alias=AliasChoices("NATBIRZHA_ALLOW_TEST_AUTH", "ALLOW_TEST_AUTH"), description="Allow signed test initData only in explicit local/test environments")
    TEST_AUTH_SECRET: str = Field(default="natbirzha_test_secret_key_2026", validation_alias=AliasChoices("NATBIRZHA_TEST_AUTH_SECRET", "TEST_AUTH_SECRET"), description="Secret for signing test initData; ignored unless ALLOW_TEST_AUTH=true")
    CREATOR_TG_IDS: str = Field(default="", validation_alias=AliasChoices("NATBIRZHA_CREATOR_TG_IDS", "CREATOR_TG_IDS"), description="Comma-separated Telegram user IDs allowed to use Creator/State controls")
    BETA_TESTERS_ONLY: bool = Field(default=False, description="Restrict Natbirzha access to beta-testers and admins only")
    SEASON_RESET_ENABLED: bool = Field(
        default=False,
        validation_alias=AliasChoices("NATBIRZHA_SEASON_RESET_ENABLED", "SEASON_RESET_ENABLED"),
        description="Explicit production switch for destructive season resets",
    )
    TYCOON_V2_ENABLED: bool = Field(
        default=True,
        validation_alias=AliasChoices("NATBIRZHA_TYCOON_V2_ENABLED", "TYCOON_V2_ENABLED"),
        description="Enable the NATBIRZHA 2.0 idle/tycoon economy after the season reset",
    )
    TYCOON_V2_OFFLINE_CASH_CAP_HOURS: int = 24
    TYCOON_V2_RESOURCE_TICK_MINUTES: int = 15
    TYCOON_V2_WORK_XP_PER_HOUR: int = 20
    TYCOON_V2_IPO_MIN_LEVEL: int = 7
    EVENTS_CHAT_ID: int = Field(
        default=-1004491945174,
        validation_alias=AliasChoices("NATBIRZHA_EVENTS_CHAT_ID", "EVENTS_CHAT_ID"),
        description="Public Telegram chat ID for broadcasting Natbirzha game events",
    )

    # Mandatory company income tax. Tax is assessed every 12 hours on positive
    # operating profit. Unpaid tax blocks production when the period closes;
    # a non-compounding +3% hourly penalty starts after each full overdue hour.
    TAX_RATE: float = 0.13
    TAX_PERIOD_HOURS: int = 12
    TAX_GRACE_HOURS: int = 0
    TAX_HOURLY_PENALTY_RATE: float = 0.03
    TAX_GRACE_DAYS: int = 3  # legacy compatibility alias
    TAX_DAILY_PENALTY_RATE: float = 0.50  # legacy compatibility alias

    # Specialization efficiency limits (strict)
    OWN_SPEC_EFFICIENCY: float = 1.00       # 100%
    FOREIGN_SPEC_EFFICIENCY: float = 0.10   # 10%
    FOREIGN_LICENSED_MAX: float = 0.12      # Max 12% with special license
    FOREIGN_LICENSE_COST_NAT: int = 50      # NAT sink: purchase foreign spec license
    RESPEC_COOLDOWN_DAYS: int = 7
    RESPEC_COST_PCT: float = 0.25

    # NPC State Reserve (Госрезерв). The State buys no more than this amount
    # per product per game day, keeping player-to-player trade economically relevant.
    NPC_BUY_FLOOR_MULT: float = 0.80        # NPC buys surplus at 80% base price
    NPC_SELL_CAP_MULT: float = 1.50         # NPC sells supplies at 150% base price
    NPC_DAILY_BUYBACK_CASH_LIMIT: float = 1_000_000.0  # Per product, per game day; 0 disables the cap
    # Premium raw materials keep a tiny explicit emergency stock so unlimited
    # NPC supply cannot bypass premium production and player-to-player trade.
    NPC_RARE_SELL_RESERVES: Dict[str, float] = {
        "lithium_raw": 2.0,
        "cobalt_raw": 1.0,
        "rare_earths": 2.0,
        "gallium_raw": 1.0,
    }

    # Alliance rules
    ALLIANCE_MAX_MEMBERS: int = 3           # Strictly maximum 3 members

    # Tournament rules
    TOURNAMENT_CYCLE_HOURS: int = 72        # 72h tournament cycle
    TOURNAMENT_DURATION_HOURS: int = 18     # PvP event window
    TOURNAMENT_SNAPSHOT_MINUTES: int = 15   # Immutable snapshot before finish
    TOURNAMENT_WINNER_PRIZE_NAT: int = 100  # 100 NAT to 1st place
    TOURNAMENT_REWARD_FIRST_PVC: int = 150
    TOURNAMENT_REWARD_SECOND_PVC: int = 100
    TOURNAMENT_REWARD_THIRD_PVC: int = 70
    PVE_WIN_COOLDOWN_HOURS: int = 2

    # IPO rules
    IPO_MIN_LEVEL: int = 7
    IPO_MIN_SHARES: int = 4000
    IPO_DEFAULT_SHARES: int = 10000
    IPO_FOUNDER_MIN_PCT: float = 0.50       # Founder retains at least 50%
    IPO_FLOAT_MAX_PCT: float = 0.50         # Public float at most 50%
    IPO_DEFAULT_FLOAT_PCT: float = 0.40
    IPO_MIN_FLOAT_PCT: float = 0.10
    IPO_SPO_COOLDOWN_DAYS: int = 14
    IPO_NAV_WEIGHT: float = 1.0
    IPO_PROFIT_PE_MULT: float = 8.0
    IPO_CASH_DISCOUNT: float = 0.85
    IPO_REQUIRE_FINANCIAL_HISTORY: bool = False  # Configurable IPO eligibility rule
    IPO_MIN_DIVIDEND_PCT: float = 5.0
    IPO_MAX_DIVIDEND_PCT: float = 100.0
    DIVIDEND_RATE_MIN_AFTER_IPO_PCT: float = 6.0
    STOCK_VALUATION_REFRESH_MINUTES: int = 10

    # Dividends
    DIVIDEND_POOL_PCT: float = 0.10         # 10% of closed daily distributable profit

    # Bankruptcy & Restructuring
    BANKRUPTCY_LIQUIDATION_POOL_PCT: float = 0.40  # 40% of audited NAV at snapshot
    BANKRUPTCY_FEE_CALENDAR_DAYS: int = 2          # Next 2 real calendar dates in GAME_TIMEZONE
    BANKRUPTCY_FEE_RATE: float = 0.30              # 30% of positive daily profit

    # Base Economic Constants
    # Every company starts with the same cash balance. Creators and testers
    # retain their separate PVC grants.
    STARTING_CASH: float = 50000.0
    CREATOR_STARTING_PVC: int = 200
    TESTER_STARTING_PVC: int = 200
    STARTING_TERRITORY_TILES: int = 4
    BASE_MUNICIPAL_ENERGY_TICK: float = 10.0       # Starter utility supply; never creates background production
    INVENTORY_MAX_QUANTITY_PER_ITEM: float = 1000000.0  # Safety cap; overflow blocks collect

    # Company progression. Six ten-level eras form the main progression track;
    # post-60 mastery is intentionally a separate system so it never rewrites
    # or resets the player's company level.
    COMPANY_MAX_LEVEL: int = 60
    COMPANY_ERA_SIZE: int = 10
    MASTERY_XP_BASE: int = 1250

    # Factory Construction Costs
    FACTORY_BASE_COSTS: Dict[str, float] = {
        "smelter": 5000.0,
        "aluminum_plant": 8000.0,
        "hydro_solar": 6000.0,
        "thermal_plant": 6000.0,
        "nuclear_plant": 25000.0,
        "oil_rig": 5500.0,
        "refinery": 7000.0,
        "chem_plant": 5500.0,
        "polymer_plant": 8500.0,
        "mine": 5000.0,
        "deep_mine": 9000.0,
        "uranium_quarry": 15000.0,
        "logging_camp": 5000.0,
        "sawmill": 6500.0,
        "farm": 5000.0,
        "food_factory": 7000.0,
        "machinery_plant": 7500.0,
        "electronics_fab": 8000.0,
        "centrifuge": 18000.0,
        "defense_plant": 30000.0,
    }

    def get_factory_cost(self, factory_type: str, existing_count: int = 0) -> float:
        base = self.FACTORY_BASE_COSTS.get(factory_type, 5000.0)
        return round(base * (1.0 + 0.15 * existing_count), 2)

nat_settings = NatbirzhaSettings()

def get_game_tz() -> zoneinfo.ZoneInfo:
    try:
        return zoneinfo.ZoneInfo(nat_settings.GAME_TIMEZONE)
    except Exception:
        return zoneinfo.ZoneInfo("UTC")

def normalize_dt(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Normalizes any datetime to offset-naive game time in GAME_TIMEZONE.
    Guarantees that datetime subtractions and comparisons never crash with
    TypeError: can't subtract/compare offset-naive and offset-aware datetimes.
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(get_game_tz()).replace(tzinfo=None)
    return dt

def get_game_now() -> datetime:
    """Returns current game timestamp normalized as offset-naive game timezone."""
    return datetime.now(get_game_tz()).replace(tzinfo=None)

def game_dt_iso(dt: Optional[datetime]) -> Optional[str]:
    """Serialize a stored game-time value with an explicit timezone offset for browsers."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=get_game_tz())
    else:
        dt = dt.astimezone(get_game_tz())
    return dt.isoformat()

def get_game_today() -> date:
    return datetime.now(get_game_tz()).date()
