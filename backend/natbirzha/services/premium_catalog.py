"""Premium licenses available for Pivocoins (PVC)."""

from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class PremiumLicenseSpec:
    code: str
    title: str
    description: str
    price_pvc: int
    duration_hours: int
    permitted_buildings: tuple[str, ...]
    permitted_recipes: tuple[str, ...]
    permitted_upgrades: tuple[str, ...]

    def as_dict(self) -> dict:
        return asdict(self)


PREMIUM_LICENSES: Mapping[str, PremiumLicenseSpec] = MappingProxyType(
    {
        "rare_mining": PremiumLicenseSpec(
            code="rare_mining",
            title="Контракт на редкую добычу",
            description="Для покупки нужны 32-й уровень компании, 6 единиц территории и свободная мощность. На 72 часа выдаёт бесплатный литиевый карьер в разделе «Предприятия». После окончания карьер останавливается, но сохраняет уровень и улучшения до продления контракта. Также открывает классические редкие производства.",
            price_pvc=120,
            duration_hours=72,
            permitted_buildings=("lithium_mine", "rare_earth_mine"),
            permitted_recipes=("mine_lithium", "mine_rare_earths"),
            permitted_upgrades=("rare_resource_extraction",),
        ),
        "advanced_defense": PremiumLicenseSpec(
            code="advanced_defense",
            title="Лицензия передовых вооружений",
            description="Открывает отдельную позднюю ветку военных технологий на 48 часов.",
            price_pvc=180,
            duration_hours=48,
            permitted_buildings=("advanced_defense_plant",),
            permitted_recipes=("smart_air_defense", "long_range_drones"),
            permitted_upgrades=("advanced_air_defense", "precision_recon"),
        ),
    }
)


def serialize_license_catalog() -> list[dict]:
    return [spec.as_dict() for spec in PREMIUM_LICENSES.values()]


@dataclass(frozen=True)
class MilitaryUpgradeSpec:
    code: str
    title: str
    description: str
    required_license: str
    max_level: int
    resource_cost: Mapping[str, float]
    modifier: str
    modifier_per_level: float
    countered_by: tuple[str, ...]

    def as_dict(self) -> dict:
        value = asdict(self)
        value["resource_cost"] = dict(self.resource_cost)
        return value


MILITARY_UPGRADES: Mapping[str, MilitaryUpgradeSpec] = MappingProxyType(
    {
        "electronic_warfare": MilitaryUpgradeSpec(
            code="electronic_warfare",
            title="Радиоэлектронная борьба",
            description="Подавляет разведывательное преимущество противника.",
            required_license="advanced_defense",
            max_level=3,
            resource_cost=MappingProxyType({"rare_earths": 4, "gallium_raw": 2, "electronics": 4}),
            modifier="electronic_warfare",
            modifier_per_level=0.04,
            countered_by=("drones", "readiness"),
        ),
        "active_protection": MilitaryUpgradeSpec(
            code="active_protection",
            title="Активная защита бронетехники",
            description="Снижает потери танков, но не защищает от превосходства авиации.",
            required_license="advanced_defense",
            max_level=3,
            resource_cost=MappingProxyType({"lithium_raw": 4, "cobalt_raw": 3, "steel": 5}),
            modifier="active_protection",
            modifier_per_level=0.05,
            countered_by=("aircraft",),
        ),
        "precision_guidance": MilitaryUpgradeSpec(
            code="precision_guidance",
            title="Точное наведение",
            description="Повышает эффективность авиации в пределах серверного cap.",
            required_license="advanced_defense",
            max_level=3,
            resource_cost=MappingProxyType({"rare_earths": 4, "gallium_raw": 3, "electronics": 3}),
            modifier="air",
            modifier_per_level=0.04,
            countered_by=("air_defense",),
        ),
        "autonomous_strike_drones": MilitaryUpgradeSpec(
            code="autonomous_strike_drones",
            title="Автономные ударные БПЛА",
            description="Усиливает разведывательную фазу и точность состава.",
            required_license="advanced_defense",
            max_level=3,
            resource_cost=MappingProxyType({"lithium_raw": 4, "cobalt_raw": 2, "electronics": 5}),
            modifier="recon",
            modifier_per_level=0.04,
            countered_by=("electronic_warfare", "air_defense"),
        ),
    }
)


def serialize_upgrade_catalog() -> list[dict]:
    return [spec.as_dict() for spec in MILITARY_UPGRADES.values()]
