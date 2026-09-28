"""Machine-learning and data-center career replacing the forestry branch."""

from .career import career_business


_BUSINESSES = (
    ("ai_compute_node", "Пограничный узел обработки ИИ", "🧠", 1, 12_000, 1,
     {"energy": 14, "water": 3},
     {"ai_compute": 18}, None,
     ("Первый серверный шкаф", "Охлаждение жидкостью", "Резервные вычисления", "Пул GPU", "Городской узел инференса")),
    ("ml_training_center", "Центр обучения моделей", "📚", 2, 30_000, 4,
     {"energy": 20, "water": 5, "components": 2},
     {"ai_compute": 28}, "ai_compute_node",
     ("Ферма ускорителей", "Подготовка датасетов", "Распределённое обучение", "Автооценка моделей", "Региональный ML-центр")),
    ("cloud_ai_center", "Облачный дата-центр ИИ", "🖥️", 3, 62_000, 8,
     {"energy": 32, "clean_water": 8, "servers": 0.8},
     {"ai_compute": 50, "cloud_compute": 0.2}, "ml_training_center",
     ("Модульный зал", "Оптоволоконный кластер", "Умное охлаждение", "Автоперераспределение", "Облачная вычислительная сеть")),
    ("machine_vision_lab", "Лаборатория машинного зрения", "👁️", 4, 125_000, 13,
     {"energy": 45, "clean_water": 12, "electronics": 2},
     {"ai_compute": 70, "sensors": 0.8}, "cloud_ai_center",
     ("Промышленные камеры", "Разметка потока", "Распознавание дефектов", "Цифровой двойник", "Сеть машинного зрения")),
    ("industrial_ai_park", "Промышленный парк ИИ", "🏭", 5, 245_000, 18,
     {"energy": 60, "clean_water": 15, "servers": 2, "components": 4},
     {"ai_compute": 90, "cloud_compute": 0.6}, "machine_vision_lab",
     ("Тестовый полигон", "Промышленные данные", "Обучение на производстве", "Распределённый инференс", "Парк промышленного ИИ")),
    ("autonomous_control_center", "Центр автономного управления", "🦾", 6, 475_000, 24,
     {"energy": 82, "clean_water": 22, "ai_accelerator": 0.1},
     {"ai_compute": 135, "automation_systems": 0.5}, "industrial_ai_park",
     ("Предиктивное обслуживание", "Автономная диспетчерская", "Оптимизация энергосети", "Самонастройка линий", "Автономный промкластер")),
    ("foundation_model_cluster", "Кластер фундаментальных моделей", "🧬", 7, 900_000, 30,
     {"energy": 110, "clean_water": 30, "ai_accelerator": 0.25},
     {"ai_compute": 190, "cloud_compute": 1.4}, "autonomous_control_center",
     ("Модельный корпус", "Мультимодальное обучение", "Федеративный кластер", "Самообучающаяся сеть", "Фундаментальный AI-кластер")),
    ("national_ai_supercomputer", "Национальный суперкомпьютер ИИ", "🚀", 8, 1_750_000, 38,
     {"energy": 150, "clean_water": 40, "servers": 3, "ai_accelerator": 0.5},
     {"ai_compute": 270, "automation_systems": 2.5}, "foundation_model_cluster",
     ("Экзафлопсный зал", "Тепловая рекуперация", "Квантовая связность", "Автоматический планировщик", "Национальный вычислительный центр")),
    ("sovereign_ai_cloud", "Суверенное облако автономного ИИ", "🌐", 9, 3_500_000, 46,
     {"energy": 220, "ultrapure_water": 15, "ai_accelerator": 1, "quantum_modules": 0.1},
     {"ai_compute": 400, "automation_systems": 5, "cloud_compute": 5}, "national_ai_supercomputer",
     ("Суверенный дата-центр", "Автономное энергоснабжение", "Распределённый интеллект", "ИИ-управление холдингами", "Глобальная сеть автономных систем")),
)


AI_DATA_BUSINESSES = {}
for business_id, name, icon, order, cost, level, inputs, outputs, prerequisite, milestones in _BUSINESSES:
    spec = career_business(
        business_id=business_id,
        name=name,
        icon=icon,
        specialization="ai_data",
        order=order,
        open_cost=cost,
        level_required=level,
        inputs=inputs,
        outputs=outputs,
        milestones=milestones,
        milestone_resources=("electronics", "servers", "ai_accelerator"),
        description=f"ИИ-производство: {name.lower()} обучает модели или продаёт вычислительную мощность.",
        prerequisites={prerequisite: min(50, 8 + order)} if prerequisite else None,
        territory_required=max(0, order - 1),
        starter=order == 1,
        tags=("ai", "machine-learning", "data-center", "production"),
    )
    AI_DATA_BUSINESSES[business_id] = spec


__all__ = ["AI_DATA_BUSINESSES"]
