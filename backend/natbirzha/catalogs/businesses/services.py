"""Business types with unique future mechanics beyond simple production."""

from .schema import business_spec


SERVICE_BUSINESSES = {
    "logistics_company": business_spec(
        business_id="logistics_company", name="Логистическая компания", tier=2, mechanic="fleet",
        specialization="logistics", max_stage=30, open_cost=30_000, base_income_per_hour=90,
        base_maintenance_per_hour=25, income_growth=1.13, upgrade_cost_growth=1.25,
        upgrade_time_curve="service", milestones={10: {"label": "Региональные рейсы", "fleet_slots": 4}},
    ),
    "construction_company": business_spec(
        business_id="construction_company", name="Строительная компания", tier=2, mechanic="projects",
        specialization="construction", max_stage=30, open_cost=40_000, base_income_per_hour=60,
        base_maintenance_per_hour=30, income_growth=1.12, upgrade_cost_growth=1.24,
        upgrade_time_curve="service", milestones={10: {"label": "Инфраструктурные проекты", "project_slots": 2}},
    ),
    "it_company": business_spec(
        business_id="it_company", name="IT-компания", tier=3, mechanic="employees_projects",
        specialization="it", max_stage=35, open_cost=100_000, base_income_per_hour=130,
        base_maintenance_per_hour=45, income_growth=1.11, upgrade_cost_growth=1.23,
        upgrade_time_curve="service", milestones={12: {"label": "Продуктовая команда", "employee_slots": 6}},
    ),
    "bank_business": business_spec(
        business_id="bank_business", name="Коммерческий банк", tier=4, mechanic="vault_rates",
        specialization="finance", max_stage=35, open_cost=250_000, base_income_per_hour=110,
        base_maintenance_per_hour=55, income_growth=1.10, upgrade_cost_growth=1.22,
        upgrade_time_curve="advanced", milestones={15: {"label": "Кредитный портфель", "vault_multiplier": 1.2}},
    ),
    "real_estate_company": business_spec(
        business_id="real_estate_company", name="Девелоперская компания", tier=4, mechanic="property_portfolio",
        specialization="real_estate", max_stage=35, open_cost=300_000, base_income_per_hour=120,
        base_maintenance_per_hour=40, income_growth=1.10, upgrade_cost_growth=1.22,
        upgrade_time_curve="advanced", milestones={15: {"label": "Арендный портфель", "property_slots": 3}},
    ),
}
