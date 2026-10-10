"""Civilian 2.0 products; all prices are fixed independently of 1.x."""
CUSTOM_ITEMS = {
    "payment_services": ("Платёжные операции", "операц.", 40),
    "credit_services": ("Кредитные услуги", "операц.", 120),
    "investment_services": ("Инвестиционные размещения", "операц.", 180),
    "district_heat": ("Теплоснабжение", "Гкал", 45),
    "reactor_fuel": ("Реакторные кассеты", "касс.", 1200),
    "storage_capacity": ("Услуги накопления энергии", "МВт·ч", 110),
    "green_hydrogen": ("Зелёный водород", "т", 180),
    "grid_services": ("Услуги балансировки сети", "контр.", 250),
    "plasma_services": ("Плазменные технологические услуги", "контр.", 600),
    "hydrogen_services": ("Водородные заправочные услуги", "контр.", 180),
    "polymer_fiber": ("Полимерные волокна", "т", 180),
    "medical_polymer": ("Медицинские полимеры", "т", 240),
    "carbon_material": ("Углеродные материалы", "т", 240),
    "diagnostics": ("Диагностические комплекты", "компл.", 600),
    "battery_pack": ("Аккумуляторные блоки", "шт.", 700),
    "habitat_module": ("Жилые автономные модули", "шт.", 6000),
    "cold_capacity": ("Услуги холодной цепи", "контр.", 150),
    "rail_capacity": ("Железнодорожные перевозки", "контр.", 200),
    "port_capacity": ("Портовые грузовые услуги", "контр.", 220),
    "air_capacity": ("Авиационные грузовые услуги", "контр.", 320),
    "warehouse_services": ("Услуги автоматизированного склада", "контр.", 250),
    "urban_services": ("Обслуживание городской инфраструктуры", "контр.", 400),
    "life_support": ("Системы жизнеобеспечения", "компл.", 1500),
    "orbital_logistics": ("Гражданская орбитальная доставка", "контр.", 4000),
    "vision_system": ("Системы машинного зрения", "компл.", 650),
    "security_services": ("Защита цифровых сетей", "контр.", 250),
    "model_services": ("Отраслевые модели ИИ", "контр.", 850),
    "engineering_services": ("Инженерные расчёты", "контр.", 1200),
    "quantum_services": ("Квантовые расчёты", "контр.", 1800),
    "insurance_services": ("Страховые услуги", "контр.", 200),
    "leasing_services": ("Лизинговые услуги", "контр.", 250),
    "settlement_services": ("Расчётные услуги", "контр.", 220),
    "risk_services": ("Услуги оценки рисков", "контр.", 280),
    "custody_services": ("Депозитарные услуги", "контр.", 230),
}
CUSTOM_ITEMS = {
    key: {"name": name, "unit": unit, "base_price": float(price)}
    for key, (name, unit, price) in CUSTOM_ITEMS.items()
}
# Rights are finite assets, not renewable factory output. Military goods are excluded.
EXCLUDED_ITEMS = frozenset({"military_gear", "well_lease", "forest_fund"})
