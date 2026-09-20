"""Continuous industrial businesses that create the multiplayer commodity economy."""

from .schema import business_spec


INDUSTRY_BUSINESSES = {
    "mining_company": business_spec(
        business_id="mining_company", name="Добывающая компания", tier=2, mechanic="resource_production",
        specialization="miner", max_stage=40, open_cost=35_000, base_income_per_hour=0,
        base_maintenance_per_hour=55, income_growth=1.11, upgrade_cost_growth=1.23,
        upgrade_time_curve="industry", inputs_per_hour={"energy": 1.5, "water": 0.5},
        outputs_per_hour={"iron_ore": 6.0, "coal": 2.0}, milestones={
            10: {"label": "Медный участок", "output_multiplier": 1.12},
            25: {"label": "Бокситовый карьер", "output_multiplier": 1.16},
            40: {"label": "Глубокая добыча", "output_multiplier": 1.20},
        },
    ),
    "oil_gas_company": business_spec(
        business_id="oil_gas_company", name="Нефтегазовая компания", tier=2, mechanic="resource_production",
        specialization="oilman", max_stage=40, open_cost=45_000, base_income_per_hour=0,
        base_maintenance_per_hour=70, income_growth=1.10, upgrade_cost_growth=1.22,
        upgrade_time_curve="industry", inputs_per_hour={"energy": 1.2, "water": 0.4},
        outputs_per_hour={"oil_crude": 5.0, "gas_natural": 2.0}, milestones={
            12: {"label": "Газовый промысел", "output_multiplier": 1.12},
            28: {"label": "Нефтепереработка", "output_multiplier": 1.16},
            40: {"label": "Экспортный терминал", "output_multiplier": 1.20},
        },
    ),
    "metallurgy_combine": business_spec(
        business_id="metallurgy_combine", name="Металлургический комбинат", tier=3, mechanic="resource_production",
        specialization="metallurgist", max_stage=40, open_cost=90_000, base_income_per_hour=0,
        base_maintenance_per_hour=135, income_growth=1.10, upgrade_cost_growth=1.22,
        upgrade_time_curve="industry", inputs_per_hour={"iron_ore": 4.0, "coal": 2.0, "energy": 3.0},
        outputs_per_hour={"steel": 3.0}, upgrade_downtime_mult=0.7,
    ),
    "chemical_concern": business_spec(
        business_id="chemical_concern", name="Химический концерн", tier=3, mechanic="resource_production",
        specialization="chemist", max_stage=40, open_cost=110_000, base_income_per_hour=0,
        base_maintenance_per_hour=150, income_growth=1.09, upgrade_cost_growth=1.21,
        upgrade_time_curve="industry", inputs_per_hour={"oil_crude": 3.0, "energy": 3.0, "water": 1.0},
        outputs_per_hour={"basic_chem": 3.0, "fertilizer": 1.0}, upgrade_downtime_mult=0.7,
    ),
    "technoprom": business_spec(
        business_id="technoprom", name="Технопром", tier=3, mechanic="resource_production",
        specialization="technoprom", max_stage=40, open_cost=140_000, base_income_per_hour=0,
        base_maintenance_per_hour=180, income_growth=1.09, upgrade_cost_growth=1.21,
        upgrade_time_curve="industry", inputs_per_hour={"copper": 2.0, "plastics": 1.5, "energy": 4.0},
        outputs_per_hour={"electronics": 2.0, "components": 2.0}, upgrade_downtime_mult=0.7,
    ),
}
