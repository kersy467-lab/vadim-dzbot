from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import (
    Integer, String, Float, DateTime,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column
from backend.db.models import Base
from backend.natbirzha.config import nat_settings

# Canonical registry of all game items (Single Source of Truth)
CANONICAL_ITEMS: Dict[str, Dict[str, Any]] = {
    # Tier 0: Utilities & Naturals
    "grid_quota": {"name": "Лимит энергосети", "category": "utility", "unit": "МВт·ч", "base_price": 5.0},
    "energy": {"name": "Электроэнергия", "category": "utility", "unit": "МВт·ч", "base_price": 10.0},
    "water": {"name": "Техническая вода", "category": "utility", "unit": "м³", "base_price": 2.0},
    "clean_water": {"name": "Очищенная вода", "category": "utility", "unit": "м³", "base_price": 4.5},
    "ultrapure_water": {"name": "Сверхчистая технологическая вода", "category": "utility", "unit": "м³", "base_price": 18.0},
    "well_lease": {"name": "Отвод скважины", "category": "asset", "unit": "шт.", "base_price": 1000.0},
    "forest_fund": {"name": "Квота лесного фонда", "category": "asset", "unit": "га", "base_price": 800.0},

    # Tier 1: Primary Extraction
    "grain": {"name": "Зерно", "category": "raw", "unit": "т", "base_price": 20.0},
    "bio_raw": {"name": "Биосырье", "category": "raw", "unit": "т", "base_price": 18.0},
    "wood_raw": {"name": "Кругляк древесины", "category": "raw", "unit": "м³", "base_price": 25.0},
    "coal": {"name": "Каменный уголь", "category": "raw", "unit": "т", "base_price": 30.0},
    "iron_ore": {"name": "Железная руда", "category": "raw", "unit": "т", "base_price": 35.0},
    "bauxite": {"name": "Бокситы", "category": "raw", "unit": "т", "base_price": 40.0},
    "minerals": {"name": "Минералы и флюс", "category": "raw", "unit": "т", "base_price": 22.0},
    "oil_crude": {"name": "Сырая нефть", "category": "raw", "unit": "барр.", "base_price": 50.0},
    "gas_natural": {"name": "Природный газ", "category": "raw", "unit": "тыс. м³", "base_price": 45.0},
    "rare_earths": {"name": "Редкоземельные металлы", "category": "raw", "unit": "кг", "base_price": 120.0},
    "lithium_raw": {"name": "Неочищенный литий", "category": "raw", "unit": "т", "base_price": 85.0},
    "cobalt_raw": {"name": "Кобальтовый концентрат", "category": "rare", "unit": "кг", "base_price": 170.0},
    "copper_ore": {"name": "Медная руда", "category": "raw", "unit": "т", "base_price": 48.0},
    "silver_ore": {"name": "Серебряная руда", "category": "rare", "unit": "кг", "base_price": 140.0},
    "gold_ore": {"name": "Золотая руда", "category": "rare", "unit": "кг", "base_price": 260.0},
    "nickel_concentrate": {"name": "Никелевый концентрат", "category": "raw", "unit": "т", "base_price": 95.0},
    "diamonds": {"name": "Промышленные алмазы", "category": "rare", "unit": "кар.", "base_price": 420.0},
    "sugar_raw": {"name": "Сахарное сырьё", "category": "raw", "unit": "т", "base_price": 36.0},
    "gallium_raw": {"name": "Галлиевый концентрат", "category": "rare", "unit": "кг", "base_price": 210.0},
    "uranium_raw": {"name": "Урановая руда", "category": "raw", "unit": "т", "base_price": 200.0},

    # Tier 2: Intermediate Processing
    "steel": {"name": "Конструкционная сталь", "category": "intermediate", "unit": "т", "base_price": 90.0},
    "aluminum": {"name": "Алюминий первичный", "category": "intermediate", "unit": "т", "base_price": 110.0},
    "lumber": {"name": "Пиломатериалы", "category": "intermediate", "unit": "м³", "base_price": 55.0},
    "cellulose": {"name": "Целлюлоза", "category": "intermediate", "unit": "т", "base_price": 65.0},
    "food": {"name": "Продовольственные пайки", "category": "intermediate", "unit": "ящ.", "base_price": 45.0},
    "fuel_diesel": {"name": "Дизельное топливо", "category": "intermediate", "unit": "л", "base_price": 1.2},
    "basic_chem": {"name": "Базовые кислоты и реагенты", "category": "intermediate", "unit": "т", "base_price": 70.0},
    "fertilizer": {"name": "Удобрения", "category": "intermediate", "unit": "т", "base_price": 50.0},
    "feed": {"name": "Комбикорм", "category": "intermediate", "unit": "т", "base_price": 30.0},
    "flour": {"name": "Мука пшеничная", "category": "intermediate", "unit": "т", "base_price": 28.0},
    "meat": {"name": "Мясо", "category": "intermediate", "unit": "т", "base_price": 65.0},
    "milk": {"name": "Молоко фермерское", "category": "intermediate", "unit": "т", "base_price": 25.0},
    "copper": {"name": "Медь первичная", "category": "intermediate", "unit": "т", "base_price": 140.0},
    "rolled_metal": {"name": "Прокат металлический", "category": "intermediate", "unit": "т", "base_price": 120.0},
    "metal_structures": {"name": "Металлоконструкции", "category": "finished", "unit": "т", "base_price": 160.0},
    "brick": {"name": "Строительный кирпич", "category": "intermediate", "unit": "т", "base_price": 38.0},
    "cement": {"name": "Цемент", "category": "intermediate", "unit": "т", "base_price": 52.0},
    "concrete": {"name": "Товарный бетон", "category": "intermediate", "unit": "м³", "base_price": 72.0},
    "construction_capacity": {"name": "Строительная мощность", "category": "service", "unit": "ед.", "base_price": 95.0},
    "logistics_capacity": {"name": "Логистическая мощность", "category": "service", "unit": "ед.", "base_price": 65.0},
    "gasoline": {"name": "Товарный бензин", "category": "finished", "unit": "л", "base_price": 1.5},
    "jet_fuel": {"name": "Авиакеросин", "category": "finished", "unit": "л", "base_price": 1.8},
    "cardboard": {"name": "Тарный картон", "category": "finished", "unit": "т", "base_price": 45.0},
    "furniture": {"name": "Мебель", "category": "finished", "unit": "шт.", "base_price": 220.0},
    "composite": {"name": "Древесные композиты", "category": "finished", "unit": "т", "base_price": 180.0},
    "electrolyte": {"name": "Электролит чистоты 99%", "category": "finished", "unit": "л", "base_price": 140.0},
    "bioreagent": {"name": "Биохимические реактивы", "category": "finished", "unit": "кг", "base_price": 260.0},
    "fresh_food": {"name": "Свежая тепличная продукция", "category": "finished", "unit": "ящ.", "base_price": 90.0},
    "dairy_goods": {"name": "Молочная продукция", "category": "finished", "unit": "ящ.", "base_price": 120.0},
    "paper": {"name": "Промышленная бумага", "category": "finished", "unit": "т", "base_price": 90.0},
    "engineered_wood": {"name": "Инженерная древесина", "category": "finished", "unit": "м³", "base_price": 240.0},
    "prefab_modules": {"name": "Сборные строительные модули", "category": "finished", "unit": "шт.", "base_price": 600.0},
    "lng": {"name": "Сжиженный природный газ", "category": "finished", "unit": "т", "base_price": 110.0},
    "lubricants": {"name": "Промышленные масла", "category": "finished", "unit": "т", "base_price": 220.0},
    "pharmaceuticals": {"name": "Фармацевтические субстанции", "category": "finished", "unit": "кг", "base_price": 700.0},
    "industrial_gases": {"name": "Технические газы высокой чистоты", "category": "finished", "unit": "балл.", "base_price": 180.0},

    # Tier 3: Advanced & High-Tech
    "plastics": {"name": "Конструкционные полимеры", "category": "finished", "unit": "т", "base_price": 130.0},
    "catalyst": {"name": "Промышленные катализаторы", "category": "finished", "unit": "кг", "base_price": 250.0},
    "lithium_pure": {"name": "Аккумуляторный литий", "category": "finished", "unit": "кг", "base_price": 180.0},
    "uranium_enriched": {"name": "Обогащенный уран (ТВЭЛ)", "category": "finished", "unit": "шт.", "base_price": 600.0},
    "components": {"name": "Электронные компоненты", "category": "intermediate", "unit": "шт.", "base_price": 150.0},
    "machinery": {"name": "Механические узлы и станки", "category": "finished", "unit": "шт.", "base_price": 320.0},
    "electronics": {"name": "Электронные чипы", "category": "finished", "unit": "шт.", "base_price": 400.0},
    "batteries": {"name": "Тяговые батареи", "category": "finished", "unit": "шт.", "base_price": 350.0},
    "auto_components": {"name": "Автокомпоненты", "category": "finished", "unit": "шт.", "base_price": 280.0},
    "superalloy": {"name": "Жаропрочные спецсплавы", "category": "finished", "unit": "кг", "base_price": 350.0},
    "nickel_metal": {"name": "Никель первичный", "category": "intermediate", "unit": "т", "base_price": 180.0},
    "advanced_alloy": {"name": "Высокопрочный сплав", "category": "finished", "unit": "кг", "base_price": 520.0},
    "titanium_alloy": {"name": "Титановый сплав", "category": "finished", "unit": "кг", "base_price": 780.0},
    "electrical_equipment": {"name": "Электротехническое оборудование", "category": "finished", "unit": "компл.", "base_price": 360.0},
    "sensors": {"name": "Промышленные датчики", "category": "finished", "unit": "шт.", "base_price": 280.0},
    "automation_systems": {"name": "Системы промышленной автоматики", "category": "hightech", "unit": "компл.", "base_price": 750.0},
    "servers": {"name": "Серверные стойки", "category": "finished", "unit": "шт.", "base_price": 850.0},
    "robots": {"name": "Промышленные роботы", "category": "finished", "unit": "шт.", "base_price": 1200.0},
    "ai_accelerator": {"name": "AI-ускорители", "category": "finished", "unit": "шт.", "base_price": 2500.0},
    "aerospace_system": {"name": "Аэрокосмические узлы", "category": "finished", "unit": "шт.", "base_price": 6000.0},
    "agrotech_seed": {"name": "Агротехнологические семенные линии", "category": "hightech", "unit": "парт.", "base_price": 500.0},
    "orbital_rations": {"name": "Орбитальные пищевые рационы", "category": "hightech", "unit": "компл.", "base_price": 1200.0},
    "precision_parts": {"name": "Прецизионные детали", "category": "hightech", "unit": "компл.", "base_price": 450.0},
    "industrial_modules": {"name": "Тяжёлые промышленные модули", "category": "hightech", "unit": "шт.", "base_price": 1500.0},
    "orbital_alloy": {"name": "Орбитальный сверхсплав", "category": "hightech", "unit": "кг", "base_price": 3500.0},
    "synthetic_fuel": {"name": "Синтетическое топливо", "category": "hightech", "unit": "т", "base_price": 350.0},
    "cryogenic_fuel": {"name": "Криогенное ракетное топливо", "category": "hightech", "unit": "т", "base_price": 1200.0},
    "advanced_composite": {"name": "Сверхпрочный композит", "category": "hightech", "unit": "т", "base_price": 900.0},
    "telecom_equipment": {"name": "Телекоммуникационное оборудование", "category": "hightech", "unit": "компл.", "base_price": 900.0},
    "cloud_compute": {"name": "Вычислительные контракты", "category": "hightech", "unit": "контр.", "base_price": 1600.0},
    "industrial_drones": {"name": "Промышленные беспилотники", "category": "hightech", "unit": "шт.", "base_price": 2200.0},
    "quantum_modules": {"name": "Квантовые вычислительные модули", "category": "hightech", "unit": "шт.", "base_price": 5000.0},

    # Tier 4: Military
    "military_gear": {"name": "Военное снаряжение ВПК", "category": "military", "unit": "компл.", "base_price": 500.0},
}

def get_item_base_price(item_id: str) -> float:
    item = CANONICAL_ITEMS.get(item_id)
    if not item:
        raise ValueError(f"Unknown canonical item: {item_id}")
    return float(item["base_price"])


def get_item_name(item_id: str) -> str:
    """Return a safe player-facing item name without leaking internal IDs."""
    item = CANONICAL_ITEMS.get(item_id)
    return str(item["name"]) if item else "Неизвестный ресурс"

def get_npc_buy_price(item_id: str) -> float:
    return round(get_item_base_price(item_id) * nat_settings.NPC_BUY_FLOOR_MULT, 2)

def get_npc_sell_price(item_id: str) -> float:
    return round(get_item_base_price(item_id) * nat_settings.NPC_SELL_CAP_MULT, 2)


class NatInventory(Base):
    __tablename__ = "nat_inventory"
    __table_args__ = (
        UniqueConstraint("company_id", "item_id", name="uq_nat_inventory_company_item"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("nat_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    quantity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    reserved_quantity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    avg_cost_basis: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    @property
    def available_quantity(self) -> float:
        return max(0.0, self.quantity - self.reserved_quantity)
