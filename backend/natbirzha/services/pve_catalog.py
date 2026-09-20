"""Versioned PvE corporation catalog for corporate territory wars."""

from types import MappingProxyType
from typing import Any, Mapping


PVE_CATALOG_VERSION = "p2-v3"


# PvE is intentionally a combined-arms progression path.  Raw infantry power
# alone must never be enough to rush the entire corporate-war tree.
PVE_FORCE_REQUIREMENTS: Mapping[int, Mapping[str, int]] = MappingProxyType(
    {
        1: MappingProxyType(
            {
                "ground_total": 100,
                "border_guards": 20,
                "drones": 5,
            }
        ),
        2: MappingProxyType(
            {
                "ground_total": 240,
                "border_guards": 50,
                "tanks": 10,
                "drones": 15,
            }
        ),
        3: MappingProxyType(
            {
                "ground_total": 450,
                "border_guards": 100,
                "tanks": 25,
                "drones": 30,
                "aircraft": 3,
                "air_defense": 10,
            }
        ),
        4: MappingProxyType(
            {
                "ground_total": 1_000,
                "border_guards": 300,
                "tanks": 90,
                "drones": 75,
                "aircraft": 20,
                "air_defense": 35,
            }
        ),
    }
)


def _target(
    code: str,
    name: str,
    industry: str,
    tier: int,
    units: dict[str, int],
    *,
    prerequisite: str | None = None,
    territory: int = 1,
    cash: float = 0.0,
    xp: int = 0,
    resources: dict[str, float] | None = None,
    premium: dict[str, float] | None = None,
    min_company_level: int | None = None,
) -> Mapping[str, Any]:
    return MappingProxyType(
        {
            "code": code,
            "name": name,
            "industry": industry,
            "tier": tier,
            "min_company_level": min_company_level or tier,
            "prerequisite_code": prerequisite,
            "unit_snapshot": units,
            "premium_modifiers": premium or {},
            "territory_reward": territory,
            "cash_reward": cash,
            "xp_reward": xp,
            "resource_rewards": resources or {},
        }
    )


PVE_CORPORATIONS: tuple[Mapping[str, Any], ...] = (
    _target("local_logistics", "Локальная логистика", "logistics", 1,
            {"infantry": 180, "border_guards": 45, "drones": 10}, cash=2_500, xp=60,
            min_company_level=6,
            resources={"military_gear": 1}),
    _target("forest_contractor", "Лесной подрядчик", "forestry", 1,
            {"infantry": 210, "border_guards": 30, "drones": 15}, cash=3_000, xp=70,
            min_company_level=6,
            resources={"wood_raw": 15}),
    _target("municipal_depot", "Муниципальная база", "construction", 1,
            {"infantry": 160, "border_guards": 70, "tanks": 6, "drones": 8}, cash=3_500, xp=80,
            min_company_level=6,
            resources={"steel": 3}),
    _target("coal_combine", "Угольный комбинат", "mining", 2,
            {"infantry": 520, "border_guards": 150, "tanks": 30, "drones": 30},
            prerequisite="local_logistics", cash=7_500, xp=160, min_company_level=16, resources={"coal": 25}),
    _target("river_port", "Речной грузовой порт", "logistics", 2,
            {"infantry": 600, "border_guards": 120, "tanks": 25, "drones": 45, "air_defense": 8},
            prerequisite="forest_contractor", cash=8_000, xp=170, min_company_level=16, resources={"fuel_diesel": 30}),
    _target("steel_syndicate", "Стальной синдикат", "metallurgy", 2,
            {"infantry": 480, "border_guards": 200, "tanks": 40, "drones": 32},
            prerequisite="municipal_depot", cash=9_000, xp=180, min_company_level=16, resources={"steel": 12}),
    _target("energy_concern", "Энергетический концерн", "energy", 3,
            {"infantry": 1_000, "border_guards": 350, "tanks": 90, "drones": 90,
             "aircraft": 12, "air_defense": 35},
            prerequisite="coal_combine", territory=2, cash=18_000, xp=320, min_company_level=30,
            resources={"energy": 120}),
    _target("petrochemical_group", "Нефтехимическая группа", "oil_gas", 3,
            {"infantry": 1_100, "border_guards": 290, "tanks": 80, "drones": 70,
             "aircraft": 16, "air_defense": 30},
            prerequisite="river_port", territory=2, cash=20_000, xp=340, min_company_level=30,
            resources={"jet_fuel": 40}),
    _target("electronics_holding", "Электронный холдинг", "technology", 3,
            {"infantry": 900, "border_guards": 260, "tanks": 75, "drones": 120,
             "aircraft": 14, "air_defense": 45},
            prerequisite="steel_syndicate", territory=2, cash=22_000, xp=360, min_company_level=30,
            resources={"electronics": 8}),
    _target("continental_defense", "Континентальная оборона", "defense", 4,
            {"infantry": 2_400, "border_guards": 900, "tanks": 260, "drones": 220,
             "aircraft": 80, "air_defense": 140}, prerequisite="energy_concern",
            territory=3, cash=45_000, xp=650, min_company_level=45, resources={"military_gear": 25},
            premium={"defense": 0.05}),
    _target("aerospace_union", "Аэрокосмический союз", "aerospace", 4,
            {"infantry": 2_100, "border_guards": 700, "tanks": 220, "drones": 350,
             "aircraft": 120, "air_defense": 110}, prerequisite="petrochemical_group",
            territory=3, cash=50_000, xp=700, min_company_level=45, resources={"aerospace_system": 2},
            premium={"air": 0.08}),
    _target("quantum_industries", "Квантовые индустрии", "technology", 4,
            {"infantry": 1_950, "border_guards": 850, "tanks": 210, "drones": 420,
             "aircraft": 100, "air_defense": 170}, prerequisite="electronics_holding",
            territory=3, cash=55_000, xp=750, min_company_level=45, resources={"ai_accelerator": 2},
            premium={"recon": 0.08, "defense": 0.05}),
)

