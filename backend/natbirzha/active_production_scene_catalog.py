"""Reusable active-production scene presets for every 2.0 branch."""

from __future__ import annotations

import hashlib
from functools import lru_cache

from backend.natbirzha.next_game_catalog import get_next_game_catalog

SCENE_FAMILIES = {
    "resources": {
        "name": "Рабочий посёлок", "operation": "СБОР",
        "pickups": ("Руда", "Растение", "Древесина", "Вода"),
        "workstations": ("Карьер", "Поле", "Лесной участок", "Насосная"),
        "deliveries": ("Вагонетка", "Элеватор", "Склад брёвен", "Резервуар"),
        "vehicles": ("Рабочий", "Тележка", "Вагонетка"),
    },
    "energy": {
        "name": "Дежурный диспетчер", "operation": "ПУЛЬТ",
        "pickups": ("Топливо", "Заряд", "Поток энергии", "Команда запуска"),
        "workstations": ("Генератор", "Солнечная панель", "Турбина", "Щитовая"),
        "deliveries": ("Подстанция", "Аккумулятор", "Городская сеть", "Пульт"),
        "vehicles": ("Техник", "Электрокар", "Робот"),
    },
    "oilgas": {
        "name": "Нефтепромысел", "operation": "МАРШРУТ",
        "pickups": ("Капля нефти", "Газовый модуль", "Пустая цистерна", "Партия топлива"),
        "workstations": ("Скважина", "Насос", "Колонна", "Трубопровод"),
        "deliveries": ("Резервуар", "Эстакада", "Переработка", "Лаборатория"),
        "vehicles": ("Техник", "Цистерна", "Погрузчик"),
    },
    "materials": {
        "name": "Заводской цех", "operation": "ЦЕХ",
        "pickups": ("Заготовка", "Слиток", "Поддон", "Катушка"),
        "workstations": ("Печь", "Пресс", "Прокатный стан", "Сборочный стол"),
        "deliveries": ("Стеллаж", "Охлаждение", "Линия отгрузки", "Склад"),
        "vehicles": ("Погрузчик", "Тележка", "Работник"),
    },
    "infrastructure": {
        "name": "Город доставки", "operation": "МАРШРУТ",
        "pickups": ("Коробки", "Стройматериалы", "Паллеты", "Контейнер"),
        "workstations": ("Склад", "Стройка", "Сортировка", "Погрузка"),
        "deliveries": ("Магазин", "Дом", "Терминал", "Порт"),
        "vehicles": ("Грузовик", "Погрузчик", "Электрокар"),
    },
    "technology": {
        "name": "Микрофабрика", "operation": "СБОРКА",
        "pickups": ("Плата", "Сенсор", "Модуль", "Микросхема"),
        "workstations": ("Сборочный стол", "Серверная стойка", "Лаборатория", "Конвейер"),
        "deliveries": ("Испытательный стенд", "Упаковка", "Склад приборов", "Сервисный робот"),
        "vehicles": ("Робот", "Инженер", "Тележка"),
    },
    "bank": {
        "name": "Финансовый квартал", "operation": "БАНК",
        "pickups": ("Папка клиента", "Платёж", "Заявка", "Документ"),
        "workstations": ("Окно банка", "Кредитный стол", "Терминал", "Хранилище"),
        "deliveries": ("Расчётный отдел", "Архив", "Касса", "Клиентский зал"),
        "vehicles": ("Курьер", "Сотрудник", "Робот"),
    },
}


def _variant(branch_id: str) -> int:
    return int.from_bytes(hashlib.sha256(branch_id.encode("utf-8")).digest()[:4], "big")


@lru_cache(maxsize=1)
def _branch_index() -> dict[tuple[str, str], dict]:
    return {
        (corporation["id"], branch["id"]): branch
        for corporation in get_next_game_catalog()
        for branch in corporation["branches"]
    }


def scene_for_branch(branch_id: str, sector_id: str) -> dict:
    family = SCENE_FAMILIES.get(sector_id)
    if family is None:
        raise ValueError(f"Для отрасли {sector_id!r} нет семейства активной сцены")
    branch = _branch_index().get((sector_id, branch_id))
    if branch is None:
        raise ValueError("Направление отсутствует в каталоге 2.0")
    seed = _variant(branch_id)
    scene = {
        "branch_id": branch_id,
        "sector_id": sector_id,
        "scene_family": sector_id,
        "scene_name": family["name"],
        "branch_name": branch["name"],
        "operation": family["operation"],
        "visual_pickup": family["pickups"][seed % len(family["pickups"])],
        "workstation": family["workstations"][(seed // 7) % len(family["workstations"])],
        "delivery_marker": family["deliveries"][(seed // 19) % len(family["deliveries"])],
        "vehicle": family["vehicles"][(seed // 31) % len(family["vehicles"])],
        "microvariant": seed % 6,
    }
    if branch_id == "ore_mining":
        scene.update(visual_pickup="Железная руда", workstation="Карьер", delivery_marker="Вагонетка", vehicle="Рабочий")
    elif branch_id == "logistics":
        scene.update(visual_pickup="Коробки", workstation="Склад", delivery_marker="Магазин", vehicle="Грузовик")
    return scene


def get_active_production_scene_catalog() -> dict[str, dict]:
    return {
        branch["id"]: scene_for_branch(branch["id"], corporation["id"])
        for corporation in get_next_game_catalog()
        for branch in corporation["branches"]
    }


__all__ = ["SCENE_FAMILIES", "get_active_production_scene_catalog", "scene_for_branch"]
