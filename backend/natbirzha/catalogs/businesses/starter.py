"""Tier-one cash and resource businesses for a new tycoon company."""

from .schema import business_spec


STARTER_BUSINESSES = {
    "retail_chain": business_spec(
        business_id="retail_chain", name="Торговая сеть", tier=1, mechanic="cash_income",
        specialization="retail", max_stage=20, open_cost=8_000, base_income_per_hour=220,
        base_maintenance_per_hour=18, income_growth=1.155, upgrade_cost_growth=1.27,
        upgrade_time_curve="starter", milestones={
            5: {"label": "Районная сеть", "income_multiplier": 1.08},
            10: {"label": "Городская сеть", "income_multiplier": 1.10},
            15: {"label": "Региональный ритейл", "income_multiplier": 1.12},
            20: {"label": "Федеральная сеть", "income_multiplier": 1.15},
        },
    ),
    "agroholding": business_spec(
        business_id="agroholding", name="Агрохолдинг", tier=1, mechanic="resource_production",
        specialization="agrarian", max_stage=30, open_cost=10_000, base_income_per_hour=0,
        base_maintenance_per_hour=14, income_growth=1.13, upgrade_cost_growth=1.25,
        upgrade_time_curve="starter", inputs_per_hour={"water": 0.5, "energy": 0.25},
        outputs_per_hour={"grain": 5.0}, milestones={
            10: {"label": "Животноводческая линия", "output_multiplier": 1.15},
            20: {"label": "Переработка урожая", "output_multiplier": 1.18},
            30: {"label": "Агропромышленный кластер", "output_multiplier": 1.22},
        },
    ),
    "energy_company": business_spec(
        business_id="energy_company", name="Энергокомпания", tier=1, mechanic="resource_production",
        specialization="power_engineer", max_stage=30, open_cost=12_000, base_income_per_hour=0,
        base_maintenance_per_hour=20, income_growth=1.12, upgrade_cost_growth=1.24,
        upgrade_time_curve="starter", inputs_per_hour={"coal": 0.35}, outputs_per_hour={"energy": 8.0},
        milestones={
            10: {"label": "Гибридная генерация", "output_multiplier": 1.12},
            20: {"label": "Региональная сеть", "output_multiplier": 1.16},
            30: {"label": "Энергетический кластер", "output_multiplier": 1.20},
        },
    ),
    "water_utility": business_spec(
        business_id="water_utility", name="Водоканал", tier=1, mechanic="resource_production",
        specialization="infrastructure", max_stage=25, open_cost=9_000, base_income_per_hour=0,
        base_maintenance_per_hour=12, income_growth=1.13, upgrade_cost_growth=1.24,
        upgrade_time_curve="starter", outputs_per_hour={"water": 12.0}, milestones={
            8: {"label": "Городская сеть", "output_multiplier": 1.10},
            16: {"label": "Очистные сооружения", "output_multiplier": 1.14},
            25: {"label": "Региональный водоканал", "output_multiplier": 1.18},
        },
    ),
}
