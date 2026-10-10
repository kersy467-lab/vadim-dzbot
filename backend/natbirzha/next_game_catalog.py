"""Seven parent corporations and a balanced, reachable multi-stage factory graph."""

from typing import Any

# A recipe is (output, quantity, input resources, operating cost per cycle).
RECIPES: dict[str, tuple[str, float, dict[str, float], float]] = {
    "ore_mining": ("iron_ore", 12, {"energy": 3, "water": 1}, 30),
    "rare_metals": ("rare_earths", 4, {"energy": 6, "water": 2}, 50),
    "agriculture": ("grain", 12, {"water": 2, "energy": 1}, 25),
    "animal_husbandry": ("meat", 8, {"feed": 4, "water": 3}, 35),
    "water_forest": ("clean_water", 20, {"energy": 2}, 25),
    "forestry": ("wood_raw", 12, {"energy": 2, "water": 1}, 25),
    "food_beverages": ("beer", 8, {"grain": 5, "hops": 1, "clean_water": 2, "energy": 2}, 45),
    "thermal": ("energy", 16, {"coal": 2, "water": 1}, 30),
    "renewables": ("energy", 9, {}, 25),
    "nuclear": ("energy", 48, {"uranium_raw": 1, "water": 1}, 75),
    "power_grid": ("grid_quota", 24, {"energy": 3}, 25),
    "oil": ("oil_crude", 10, {"energy": 2, "water": 1}, 35),
    "gas": ("gas_natural", 10, {"energy": 2, "water": 1}, 30),
    "refining": ("fuel_diesel", 20, {"oil_crude": 3, "energy": 3}, 55),
    "petrochemistry": ("plastics", 6, {"oil_crude": 4, "energy": 3, "water": 1}, 60),
    "ferrous": ("steel", 6, {"iron_ore": 5, "coal": 3, "energy": 2}, 65),
    "nonferrous": ("copper", 5, {"copper_ore": 4, "energy": 3}, 60),
    "construction_materials": ("cement", 10, {"minerals": 4, "energy": 3, "water": 2}, 40),
    "advanced_alloys": ("superalloy", 3, {"nickel_concentrate": 2, "steel": 1, "energy": 4}, 90),
    "construction": ("construction_capacity", 10, {"metal_structures": 2, "cement": 2, "energy": 2}, 75),
    "logistics": ("logistics_capacity", 7, {"fuel_diesel": 2, "energy": 1}, 45),
    "warehousing": ("logistics_capacity", 5, {"steel": 1, "energy": 1}, 50),
    "rail_ports": ("logistics_capacity", 12, {"steel": 2, "fuel_diesel": 2, "energy": 2}, 85),
    "electronics": ("components", 5, {"copper": 1, "steel": 1, "energy": 3, "water": 1}, 90),
    "ai_compute": ("ai_compute", 20, {"energy": 5, "water": 3}, 100),
    "automation": ("automation_systems", 2, {"components": 1, "energy": 3}, 110),
    "semiconductors": ("electronics", 4, {"components": 2, "ai_compute": 5, "energy": 4, "water": 2}, 130),
    "retail": ("payment_services", 12, {"energy": 1}, 25),
    "corporate": ("credit_services", 8, {"construction_capacity": 1, "energy": 1}, 45),
    "investment": ("investment_services", 5, {"components": 1, "energy": 2}, 60),
    "digital_bank": ("payment_services", 20, {"components": 1, "ai_compute": 2, "energy": 2}, 55),
    "atm_network": ("payment_services", 100, {"electrical_equipment": 1, "energy": 2}, 70),
    "corporate_accounts": ("payment_services", 150, {"components": 2, "energy": 2}, 100),
    "branch_network": ("credit_services", 40, {"machinery": 1, "energy": 3}, 150),
    "clearing_house": ("investment_services", 30, {"electronics": 1, "energy": 3}, 200),
    "asset_management": ("investment_services", 22, {"components": 2, "energy": 2}, 180),
    "merchant_acquiring": ("payment_services", 120, {"electrical_equipment": 1, "components": 1, "energy": 2}, 120),
    "fertilizer_processing": ("fertilizer", 10, {"gas_natural": 2, "water": 2, "energy": 3}, 35),
    "food_processing": ("food", 18, {"flour": 8, "clean_water": 2, "energy": 2}, 55),
    "biofuel": ("synthetic_fuel", 3, {"bio_raw": 5, "energy": 4, "water": 2}, 130),
    "paper_mill": ("paper", 10, {"cellulose": 3, "clean_water": 2, "energy": 3}, 90),
    "engineered_wood": ("engineered_wood", 5, {"lumber": 4, "energy": 4, "plastics": 1}, 100),
    "gas_processing": ("lng", 8, {"gas_natural": 3, "energy": 3, "water": 1}, 100),
    "gas_chemistry": ("fertilizer", 10, {"gas_natural": 3, "water": 2, "energy": 2}, 100),
    "gas_power": ("energy", 40, {"gas_natural": 3, "water": 1}, 40),
    "aluminum_smelt": ("aluminum", 6, {"bauxite": 3, "energy": 4}, 90),
    "battery_cells": ("batteries", 5, {"lithium_pure": 3, "copper": 1, "energy": 5, "water": 2}, 220),
    "machinery": ("machinery", 5, {"steel": 3, "components": 2, "energy": 3}, 220),
    "pharmaceuticals": ("pharmaceuticals", 2, {"basic_chem": 2, "water": 3, "energy": 2}, 250),
    "servers": ("servers", 3, {"components": 3, "electronics": 2, "energy": 5}, 350),
    "cloud_compute": ("cloud_compute", 4, {"servers": 1, "energy": 6, "water": 3}, 450),
    "robotics": ("robots", 4, {"machinery": 2, "components": 2, "electronics": 1, "energy": 4}, 500),
    "aerospace": ("aerospace_system", 2, {"titanium_alloy": 2, "advanced_composite": 2, "electronics": 1, "energy": 6}, 800),
    "uranium_enrichment": ("uranium_enriched", 3, {"uranium_raw": 2, "energy": 4, "water": 2}, 130),
    "lithium_refining": ("lithium_pure", 7, {"lithium_raw": 5, "energy": 5, "water": 3}, 180),
    "precision_parts": ("precision_parts", 5, {"steel": 2, "components": 2, "energy": 4}, 210),
    "industrial_gases": ("industrial_gases", 5, {"basic_chem": 2, "water": 2, "energy": 2}, 170),
    "plastic_molding": ("plastics", 10, {"oil_crude": 6, "energy": 4, "water": 1}, 170),
}

CUSTOM_ITEMS: dict[str, dict[str, Any]] = {
    "payment_services": {"name": "Платёжные операции", "unit": "операц.", "base_price": 40.0},
    "credit_services": {"name": "Кредитные услуги", "unit": "операц.", "base_price": 120.0},
    "investment_services": {"name": "Инвестиционные размещения", "unit": "операц.", "base_price": 180.0},
}

# Frozen prices keep the 2.0 NPC market independent from future legacy rebalance.
NEXT_GAME_BASE_PRICES: dict[str, float] = {
    # Pin every legacy catalogue item so changing the 1.x balance cannot
    # silently alter the isolated 2.0 market.
    "grid_quota": 5.0, "energy": 10.0, "water": 2.0, "clean_water": 4.5,
    "ultrapure_water": 18.0, "well_lease": 1_000.0, "forest_fund": 800.0,
    "grain": 20.0, "bio_raw": 18.0, "hops": 55.0, "grapes": 48.0,
    "wood_raw": 25.0, "coal": 30.0, "iron_ore": 35.0, "bauxite": 40.0,
    "minerals": 22.0, "oil_crude": 50.0, "gas_natural": 45.0,
    "rare_earths": 120.0, "lithium_raw": 85.0, "cobalt_raw": 170.0,
    "copper_ore": 48.0, "silver_ore": 140.0, "gold_ore": 260.0,
    "nickel_concentrate": 95.0, "diamonds": 420.0, "sugar_raw": 36.0,
    "gallium_raw": 210.0, "uranium_raw": 200.0, "steel": 90.0,
    "aluminum": 110.0, "lumber": 55.0, "cellulose": 65.0, "food": 45.0,
    "beer": 90.0, "wine": 150.0, "aged_spirits": 320.0, "fuel_diesel": 80.0,
    "basic_chem": 70.0, "fertilizer": 50.0, "feed": 30.0, "flour": 28.0,
    "meat": 65.0, "milk": 25.0, "copper": 140.0, "rolled_metal": 120.0,
    "metal_structures": 160.0, "brick": 38.0, "cement": 52.0, "concrete": 72.0,
    "construction_capacity": 95.0, "logistics_capacity": 65.0, "gasoline": 95.0,
    "jet_fuel": 120.0, "cardboard": 45.0, "furniture": 220.0, "composite": 180.0,
    "electrolyte": 140.0, "bioreagent": 260.0, "fresh_food": 90.0,
    "dairy_goods": 120.0, "paper": 90.0, "engineered_wood": 240.0,
    "prefab_modules": 600.0, "lng": 110.0, "lubricants": 220.0,
    "pharmaceuticals": 700.0, "industrial_gases": 180.0, "plastics": 130.0,
    "catalyst": 250.0, "lithium_pure": 180.0, "uranium_enriched": 600.0,
    "components": 150.0, "machinery": 320.0, "electronics": 400.0,
    "batteries": 350.0, "auto_components": 280.0, "superalloy": 350.0,
    "nickel_metal": 180.0, "advanced_alloy": 520.0, "titanium_alloy": 780.0,
    "electrical_equipment": 360.0, "sensors": 280.0, "automation_systems": 750.0,
    "ai_compute": 112.5, "servers": 850.0, "robots": 1_200.0,
    "ai_accelerator": 2_500.0, "aerospace_system": 6_000.0,
    "agrotech_seed": 500.0, "orbital_rations": 1_200.0,
    "precision_parts": 450.0, "industrial_modules": 1_500.0,
    "orbital_alloy": 3_500.0, "synthetic_fuel": 350.0,
    "cryogenic_fuel": 1_200.0, "advanced_composite": 900.0,
    "telecom_equipment": 900.0, "cloud_compute": 1_600.0,
    "industrial_drones": 2_200.0, "quantum_modules": 5_000.0,
    "military_gear": 500.0,
}

# Real cross-industry routes: each checkpoint opens two possible next factories.
NEXT_BRANCH_IDS: dict[str, tuple[str, str]] = {
    "ore_mining": ("ferrous", "construction_materials"),
    "rare_metals": ("advanced_alloys", "lithium_refining"),
    "agriculture": ("food_processing", "biofuel"),
    "animal_husbandry": ("food_beverages", "warehousing"),
    "water_forest": ("food_beverages", "agriculture"),
    "forestry": ("paper_mill", "engineered_wood"),
    "food_beverages": ("agriculture", "retail"),
    "thermal": ("power_grid", "gas_power"),
    "renewables": ("power_grid", "battery_cells"),
    "nuclear": ("power_grid", "uranium_enrichment"),
    "power_grid": ("ai_compute", "water_forest"),
    "oil": ("refining", "petrochemistry"),
    "gas": ("gas_processing", "gas_power"),
    "refining": ("logistics", "plastic_molding"),
    "petrochemistry": ("industrial_gases", "pharmaceuticals"),
    "ferrous": ("construction", "machinery"),
    "nonferrous": ("aluminum_smelt", "battery_cells"),
    "construction_materials": ("construction", "engineered_wood"),
    "advanced_alloys": ("aerospace", "precision_parts"),
    "construction": ("corporate", "warehousing"),
    "logistics": ("rail_ports", "warehousing"),
    "warehousing": ("rail_ports", "retail"),
    "rail_ports": ("logistics", "corporate"),
    "electronics": ("semiconductors", "servers"),
    "ai_compute": ("semiconductors", "digital_bank"),
    "automation": ("electronics", "robotics"),
    "semiconductors": ("ai_compute", "robotics"),
    "retail": ("digital_bank", "atm_network"),
    "corporate": ("corporate_accounts", "branch_network"),
    "investment": ("asset_management", "clearing_house"),
    "digital_bank": ("merchant_acquiring", "corporate_accounts"),
    "atm_network": ("digital_bank", "merchant_acquiring"),
    "corporate_accounts": ("corporate", "clearing_house"),
    "branch_network": ("corporate", "digital_bank"),
    "clearing_house": ("investment", "asset_management"),
    "asset_management": ("investment", "digital_bank"),
    "merchant_acquiring": ("retail", "digital_bank"),
    "fertilizer_processing": ("agriculture", "animal_husbandry"),
    "food_processing": ("food_beverages", "retail"),
    "biofuel": ("refining", "logistics"),
    "paper_mill": ("construction_materials", "warehousing"),
    "engineered_wood": ("construction", "warehousing"),
    "gas_processing": ("gas_chemistry", "gas_power"),
    "gas_chemistry": ("fertilizer_processing", "petrochemistry"),
    "gas_power": ("power_grid", "industrial_gases"),
    "aluminum_smelt": ("electronics", "construction"),
    "battery_cells": ("electronics", "ai_compute"),
    "machinery": ("automation", "construction"),
    "pharmaceuticals": ("retail", "ai_compute"),
    "servers": ("cloud_compute", "electronics"),
    "cloud_compute": ("ai_compute", "semiconductors"),
    "robotics": ("automation", "semiconductors"),
    "aerospace": ("advanced_alloys", "ai_compute"),
    "uranium_enrichment": ("nuclear", "thermal"),
    "lithium_refining": ("battery_cells", "semiconductors"),
    "precision_parts": ("machinery", "aerospace"),
    "industrial_gases": ("gas_chemistry", "semiconductors"),
    "plastic_molding": ("petrochemistry", "pharmaceuticals"),
}

START_BRANCH_IDS: dict[str, frozenset[str]] = {
    "resources": frozenset({"ore_mining", "rare_metals", "forestry"}),
    "energy": frozenset({"thermal", "renewables", "nuclear"}),
    "oilgas": frozenset({"oil", "gas"}),
    "materials": frozenset({"ferrous", "nonferrous", "construction_materials", "advanced_alloys"}),
    "infrastructure": frozenset({"construction"}),
    "technology": frozenset({"electronics", "ai_compute", "automation", "semiconductors"}),
    "bank": frozenset({"retail", "corporate", "investment"}),
}

CORPORATIONS = (
    ("resources", "Ресурсная корпорация", "mining", "Сырьё, вода, лес и продовольствие.", (
        ("ore_mining", "Руды и уголь", "Руда и уголь", ("Обогащение руды", "Кокс и сплавы")),
        ("rare_metals", "Редкие металлы", "Редкоземельные металлы и концентраты", ("Литиевые соли", "Высокочистые металлы")),
        ("agriculture", "Растениеводство", "Зерно и агросырьё", ("Пищевые ингредиенты", "Биотопливо")),
        ("animal_husbandry", "Животноводство", "Мясо, молоко и комбикорм", ("Молочная переработка", "Холодные склады")),
        ("water_forest", "Водоснабжение", "Очищенная промышленная вода", ("Сверхчистая вода", "Водная сеть")),
        ("forestry", "Лес и целлюлоза", "Древесина и лесоматериалы", ("Бумага и картон", "Инженерная древесина")),
        ("food_beverages", "Пищевое производство", "Пиво и продукты из агросырья", ("Пивоварение", "Пищевая переработка")),
        ("food_processing", "Переработка продуктов", "Мука превращается в готовую еду", ("Пищевое производство", "Розничный банк")),
        ("fertilizer_processing", "Минеральные удобрения", "Газ и энергия превращаются в удобрения", ("Растениеводство", "Переработка продуктов")),
        ("biofuel", "Биотопливо", "Переработка растительного сырья в топливо", ("Переработка", "Транспортная сеть")),
        ("paper_mill", "Целлюлозно-бумажный комбинат", "Целлюлоза превращается в бумагу", ("Стройматериалы", "Складские комплексы")),
        ("engineered_wood", "Инженерная древесина", "Лесоматериалы для крупной стройки", ("Промышленное строительство", "Складские комплексы")),
    )),
    ("energy", "Энергетическая корпорация", "energy", "Генерация, накопители и сети.", (
        ("thermal", "Тепловая генерация", "Электроэнергия из угля и газа", ("Пиковые станции", "Улавливание выбросов")),
        ("renewables", "Возобновляемая энергия", "Ветер, солнце и гидроэнергетика", ("Накопители", "Умная сеть")),
        ("nuclear", "Атомная энергетика", "Базовая генерация для крупных потребителей", ("Топливный цикл", "Малые реакторы")),
        ("power_grid", "Энергосети", "Передача энергии и сетевые квоты", ("Магистральные сети", "Распределённые накопители")),
        ("gas_power", "Газовая генерация", "Маневренная электростанция на природном газе", ("Энергосети", "Промышленные газы")),
    )),
    ("oilgas", "Нефтегазовая корпорация", "oil", "Добыча топлива и глубокая переработка.", (
        ("oil", "Нефтяная добыча", "Сырая нефть", ("Нефтехимия", "Синтетическое топливо")),
        ("gas", "Газовая добыча", "Природный газ", ("Газопереработка", "Газовая генерация")),
        ("refining", "Переработка", "Дизель и нефтепродукты", ("Полимеры", "Катализаторы и удобрения")),
        ("petrochemistry", "Нефтехимия", "Полимеры и промышленные реагенты", ("Спецпластики", "Фармацевтика")),
        ("gas_processing", "Газопереработка", "СПГ и подготовка газа", ("Газовая химия", "Газовая генерация")),
        ("gas_chemistry", "Газовая химия", "Удобрения и химическое сырьё из газа", ("Удобрения", "Нефтехимия")),
        ("plastic_molding", "Полимерные изделия", "Глубокая переработка полимеров", ("Нефтехимия", "Фармацевтика")),
        ("industrial_gases", "Промышленные газы", "Газы для электроники и медицины", ("Газовая химия", "Полупроводники")),
        ("pharmaceuticals", "Фармацевтика", "Высокотехнологичные медицинские продукты", ("Розничный банк", "ИИ и вычисления")),
    )),
    ("materials", "Корпорация материалов", "metallurgy", "Металлы и материалы для заводов.", (
        ("ferrous", "Чёрная металлургия", "Сталь и чугун", ("Конструкционная сталь", "Спецсплавы")),
        ("nonferrous", "Цветные металлы", "Медь и цветные концентраты", ("Высокочистая медь", "Аккумуляторные металлы")),
        ("construction_materials", "Стройматериалы", "Цемент и инженерные материалы", ("Изоляция", "Керамика")),
        ("advanced_alloys", "Специальные сплавы", "Жаропрочные материалы", ("Аэрокосмические системы", "Точные детали")),
        ("aluminum_smelt", "Алюминиевый завод", "Лёгкие конструкционные металлы", ("Электроника", "Промышленное строительство")),
        ("battery_cells", "Аккумуляторные ячейки", "Батареи из лития и меди", ("Электроника", "ИИ и вычисления")),
        ("machinery", "Машиностроение", "Станки и промышленное оборудование", ("ПО и автоматизация", "Промышленное строительство")),
        ("aerospace", "Аэрокосмические системы", "Сложные сплавы и точная электроника", ("Специальные сплавы", "ИИ и вычисления")),
        ("uranium_enrichment", "Обогащение урана", "Топливо для атомной энергетики", ("Атомная энергетика", "Тепловая генерация")),
        ("lithium_refining", "Переработка лития", "Высокочистый литий для аккумуляторов", ("Аккумуляторные ячейки", "Полупроводники")),
        ("precision_parts", "Точные детали", "Детали для машин и авиации", ("Машиностроение", "Аэрокосмические системы")),
    )),
    ("infrastructure", "Инфраструктурная корпорация", "construction", "Стройка, хранение и доставка грузов.", (
        ("construction", "Промышленное строительство", "Здания, линии и площадки", ("Модернизация заводов", "Городская инфраструктура")),
        ("logistics", "Транспортная сеть", "Автопарк и маршруты", ("Морские порты", "Скоростные перевозки")),
        ("warehousing", "Складские комплексы", "Хранение и управление потоками", ("Холодные цепи", "Автоматизированные терминалы")),
        ("rail_ports", "Железная дорога и порты", "Магистральные перевозки грузов", ("Контейнерные хабы", "Трансграничные коридоры")),
    )),
    ("technology", "Технологическая корпорация", "technology", "Электроника, вычисления и автоматизация.", (
        ("electronics", "Электроника", "Компоненты и серверное оборудование", ("Микрочипы", "Серверные стойки")),
        ("ai_compute", "ИИ и вычисления", "Дата-центры и обучение моделей", ("Суперкомпьютеры", "Облачные вычисления")),
        ("automation", "ПО и автоматизация", "Промышленное управление", ("Робототехника", "Промышленный ИИ")),
        ("semiconductors", "Полупроводники", "Чипы и вычислительные модули", ("Ускорители ИИ", "Квантовые модули")),
        ("servers", "Серверные стойки", "Оборудование для дата-центров", ("Облачные вычисления", "Электроника")),
        ("cloud_compute", "Облачные вычисления", "Масштабируемые вычислительные платформы", ("ИИ и вычисления", "Полупроводники")),
        ("robotics", "Робототехника", "Промышленные роботы и автоматизация", ("ПО и автоматизация", "Полупроводники")),
    )),
    ("bank", "Банковская корпорация", "money", "Счета, платежи, кредитование и инвестиции.", (
        ("retail", "Розничный банк", "Счета, вклады и обслуживание клиентов", ("Цифровые платежи", "Сеть банкоматов")),
        ("corporate", "Корпоративный банк", "Кредитование предприятий", ("Расчётные счета", "Региональные отделения")),
        ("investment", "Инвестиционный банк", "Размещение капитала и управление активами", ("Управление активами", "Межбанковский клиринг")),
        ("digital_bank", "Цифровой банк", "Дистанционные платежи и расчёты", ("Эквайринг торговых сетей", "Расчётные счета")),
        ("atm_network", "Сеть банкоматов", "Наличные и платежи в регионах", ("Цифровые платежи", "Эквайринг торговых сетей")),
        ("corporate_accounts", "Расчётные счета", "Расчётное обслуживание компаний", ("Корпоративное кредитование", "Межбанковский клиринг")),
        ("branch_network", "Региональные отделения", "Физическая сеть обслуживания клиентов", ("Корпоративное кредитование", "Цифровые платежи")),
        ("clearing_house", "Межбанковский клиринг", "Расчёты между банками и крупными сетями", ("Инвестиционный банк", "Управление активами")),
        ("asset_management", "Управление активами", "Управление капиталом клиентов", ("Инвестиционный банк", "Цифровой банк")),
        ("merchant_acquiring", "Эквайринг торговых сетей", "Обработка платежей магазинов и сервисов", ("Розничный банк", "Цифровой банк")),
    )),
)


def get_next_game_items() -> dict[str, dict[str, Any]]:
    from backend.natbirzha.models.inventory import CANONICAL_ITEMS

    items = {
        item_id: {
            "name": row["name"], "unit": row["unit"],
            "base_price": NEXT_GAME_BASE_PRICES[item_id],
        }
        for item_id, row in CANONICAL_ITEMS.items()
    }
    return {**items, **CUSTOM_ITEMS}


def get_next_game_catalog() -> list[dict[str, Any]]:
    items = get_next_game_items()
    branch_names = {
        branch_id: branch_name
        for _sector_id, _sector_name, _icon, _description, branches in CORPORATIONS
        for branch_id, branch_name, _outputs, _future_choices in branches
    }
    catalog = []
    for sector_id, name, icon, description, branches in CORPORATIONS:
        branch_rows = []
        for branch_id, branch_name, outputs, _future_choices in branches:
            output_id, quantity, inputs, operating_cost = RECIPES[branch_id]
            recipe = {
                "facility_name": f"Завод: {branch_name}",
                "build_cost": 3_000,
                "cycle_seconds": 300,
                "output_item": output_id,
                "output_name": items[output_id]["name"],
                "output_unit": items[output_id]["unit"],
                "output_quantity": quantity,
                "inputs": dict(inputs),
                "input_items": [
                    {"item_id": item_id, "name": items[item_id]["name"],
                     "unit": items[item_id]["unit"], "quantity": amount}
                    for item_id, amount in inputs.items()
                ],
                "operating_cost": operating_cost,
            }
            branch_rows.append({
                "id": branch_id,
                "name": branch_name,
                "outputs": outputs,
                "is_starting_branch": branch_id in START_BRANCH_IDS.get(sector_id, frozenset()),
                "future_choices": [branch_names[target] for target in NEXT_BRANCH_IDS[branch_id]],
                "next_branch_ids": list(NEXT_BRANCH_IDS[branch_id]),
                "factory": recipe,
            })
        catalog.append({
            "id": sector_id, "name": name, "icon": icon,
            "description": description, "branches": branch_rows,
        })
    return catalog


def find_next_game_sector(sector_id: str) -> dict[str, Any] | None:
    return next((item for item in get_next_game_catalog() if item["id"] == sector_id), None)


def find_next_game_branch(branch_id: str) -> dict[str, Any] | None:
    return next(
        (branch for sector in get_next_game_catalog() for branch in sector["branches"]
         if branch["id"] == branch_id),
        None,
    )


__all__ = [
    "CORPORATIONS", "CUSTOM_ITEMS", "NEXT_BRANCH_IDS", "NEXT_GAME_BASE_PRICES", "RECIPES", "START_BRANCH_IDS", "find_next_game_branch",
    "find_next_game_sector", "get_next_game_catalog", "get_next_game_items",
]
