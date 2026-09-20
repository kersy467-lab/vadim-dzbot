from typing import Dict, Any

PART2_BUILDINGS: Dict[str, Dict[str, Any]] = {
    # ---------------- 5. ЭНЕРГЕТИК (power_engineer) ----------------
    'solar_plant': {
        'id': 'solar_plant', 'name': '☀️ Солнечная электростанция', 'specialization': 'power_engineer',
        'category': 'extraction', 'level_required': 1, 'build_cost': 25000.0,
        'workers_required': 10, 'energy_required': 0, 'cycle_duration': 60,
        'description': 'Бестопливная фотоэлектрическая генерация',
        'inputs': {'grid_quota': 1.0}, 'outputs': {'energy': 15.0},
        'recipe_id': 'generate_solar'
    },
    'hydro_plant': {
        'id': 'hydro_plant', 'name': '🌊 ГЭС', 'specialization': 'power_engineer',
        'category': 'extraction', 'level_required': 1, 'build_cost': 40000.0,
        'workers_required': 15, 'energy_required': 0, 'cycle_duration': 60,
        'description': 'Стабильная гидрогенерация на водном потоке',
        'inputs': {'water': 3.0, 'grid_quota': 1.0}, 'outputs': {'energy': 22.0},
        'recipe_id': 'generate_hydro'
    },
    'thermal_power_plant': {
        'id': 'thermal_power_plant', 'name': '🔥 ТЭЦ', 'specialization': 'power_engineer',
        'category': 'processing', 'level_required': 14, 'build_cost': 95000.0,
        'workers_required': 35, 'energy_required': 0, 'cycle_duration': 90,
        'description': 'Тепловая электростанция на угле и воде',
        'inputs': {'coal': 2.0, 'water': 2.0}, 'outputs': {'energy': 35.0},
        'recipe_id': 'generate_thermal_plant'
    },
    'wind_farm': {
        'id': 'wind_farm', 'name': '💨 Ветропарк', 'specialization': 'power_engineer',
        'category': 'extraction', 'level_required': 8, 'build_cost': 60000.0,
        'workers_required': 12, 'energy_required': 0, 'cycle_duration': 60,
        'description': 'Ветропарк с низкими эксплуатационными затратами',
        'inputs': {'grid_quota': 1.5}, 'outputs': {'energy': 20.0},
        'recipe_id': 'generate_wind'
    },
    'nuclear_plant': {
        'id': 'nuclear_plant', 'name': '☢️ Атомная электростанция', 'specialization': 'power_engineer',
        'category': 'hightech', 'level_required': 40, 'build_cost': 650000.0,
        'workers_required': 80, 'energy_required': 0, 'cycle_duration': 180,
        'description': 'Огромная мощность на обогащённом уране',
        'inputs': {'uranium_enriched': 1.0, 'water': 3.0}, 'outputs': {'energy': 150.0},
        'recipe_id': 'generate_nuclear_plant'
    },
    'fusion_plant': {
        'id': 'fusion_plant', 'name': '⚛️ Термоядерный комплекс', 'specialization': 'power_engineer',
        'category': 'endgame', 'level_required': 56, 'build_cost': 1800000.0,
        'workers_required': 100, 'energy_required': 0, 'cycle_duration': 240,
        'description': 'Эндгейм-энергетика на термоядерном синтезе',
        'inputs': {'rare_earths': 1.5, 'water': 5.0, 'grid_quota': 3.0}, 'outputs': {'energy': 400.0},
        'recipe_id': 'generate_fusion'
    },
    'gas_turbine_plant': {
        'id': 'gas_turbine_plant', 'name': '🔥 Газотурбинная станция', 'specialization': 'power_engineer',
        'category': 'processing', 'level_required': 18, 'build_cost': 135000.0,
        'workers_required': 32, 'energy_required': 0, 'cycle_duration': 105,
        'description': 'Маневренная генерация на природном газе',
        'inputs': {'gas_natural': 2.0, 'water': 1.0}, 'outputs': {'energy': 48.0},
        'recipe_id': 'generate_gas_turbine'
    },
    'geothermal_plant': {
        'id': 'geothermal_plant', 'name': '🌋 Геотермальная станция', 'specialization': 'power_engineer',
        'category': 'industry', 'level_required': 24, 'build_cost': 190000.0,
        'workers_required': 38, 'energy_required': 0, 'cycle_duration': 120,
        'description': 'Стабильная базовая генерация на глубинном тепле',
        'inputs': {'water': 4.0, 'grid_quota': 2.0}, 'outputs': {'energy': 70.0},
        'recipe_id': 'generate_geothermal'
    },
    'tidal_plant': {
        'id': 'tidal_plant', 'name': '🌊 Приливная электростанция', 'specialization': 'power_engineer',
        'category': 'industry', 'level_required': 32, 'build_cost': 310000.0,
        'workers_required': 50, 'energy_required': 0, 'cycle_duration': 150,
        'description': 'Крупная морская генерация с высокой стабильностью',
        'inputs': {'water': 6.0, 'grid_quota': 2.5}, 'outputs': {'energy': 105.0},
        'recipe_id': 'generate_tidal'
    },
    'fast_reactor': {
        'id': 'fast_reactor', 'name': '⚛️ Реактор на быстрых нейтронах', 'specialization': 'power_engineer',
        'category': 'hightech', 'level_required': 46, 'build_cost': 980000.0,
        'workers_required': 88, 'energy_required': 0, 'cycle_duration': 210,
        'description': 'Продвинутая атомная генерация на обогащённом топливе',
        'inputs': {'uranium_enriched': 1.5, 'water': 4.0}, 'outputs': {'energy': 230.0},
        'recipe_id': 'generate_fast_reactor'
    },

    # ---------------- 6. ЛЕСОПРОМЫШЛЕННИК (forester) ----------------
    'logging_camp': {
        'id': 'logging_camp', 'name': '🌲 Лесозаготовка', 'specialization': 'forester',
        'category': 'extraction', 'level_required': 1, 'build_cost': 18000.0,
        'workers_required': 20, 'energy_required': 0, 'cycle_duration': 60,
        'description': 'Заготовка деловой древесины по лесной квоте',
        'inputs': {'grid_quota': 1.0, 'water': 1.0}, 'outputs': {'wood_raw': 6.0},
        'recipe_id': 'log_timber_camp'
    },
    'sawmill': {
        'id': 'sawmill', 'name': '🪵 Лесопилка', 'specialization': 'forester',
        'category': 'processing', 'level_required': 8, 'build_cost': 45000.0,
        'workers_required': 25, 'energy_required': 3, 'cycle_duration': 90,
        'description': 'Распиловка круглого леса на обрезные пиломатериалы',
        'inputs': {'wood_raw': 4.0, 'energy': 3.0}, 'outputs': {'lumber': 3.0},
        'recipe_id': 'saw_lumber'
    },
    'pulp_mill': {
        'id': 'pulp_mill', 'name': '📄 Целлюлозный завод', 'specialization': 'forester',
        'category': 'processing', 'level_required': 14, 'build_cost': 85000.0,
        'workers_required': 30, 'energy_required': 4, 'cycle_duration': 105,
        'description': 'Варка древесной сульфатной целлюлозы',
        'inputs': {'wood_raw': 3.0, 'water': 2.0, 'energy': 4.0}, 'outputs': {'cellulose': 2.5},
        'recipe_id': 'produce_pulp'
    },
    'cardboard_factory': {
        'id': 'cardboard_factory', 'name': '📦 Картонный комбинат', 'specialization': 'forester',
        'category': 'industry', 'level_required': 26, 'build_cost': 180000.0,
        'workers_required': 35, 'energy_required': 4, 'cycle_duration': 120,
        'description': 'Производство упаковочного гофрокартона',
        'inputs': {'cellulose': 2.0, 'energy': 4.0}, 'outputs': {'cardboard': 3.0},
        'recipe_id': 'produce_cardboard'
    },
    'furniture_factory': {
        'id': 'furniture_factory', 'name': '🪑 Мебельная фабрика', 'specialization': 'forester',
        'category': 'industry', 'level_required': 36, 'build_cost': 310000.0,
        'workers_required': 45, 'energy_required': 5, 'cycle_duration': 150,
        'description': 'Сборка корпусной мебели из массива и полимеров',
        'inputs': {'lumber': 2.0, 'plastics': 1.0, 'energy': 5.0}, 'outputs': {'furniture': 2.0},
        'recipe_id': 'assemble_furniture'
    },
    'composite_factory': {
        'id': 'composite_factory', 'name': '🧱 Завод композитов', 'specialization': 'forester',
        'category': 'hightech', 'level_required': 46, 'build_cost': 610000.0,
        'workers_required': 55, 'energy_required': 6, 'cycle_duration': 180,
        'description': 'Древесно-полимерные сверхпрочные композиты',
        'inputs': {'wood_raw': 3.0, 'plastics': 2.0, 'energy': 6.0}, 'outputs': {'composite': 2.0},
        'recipe_id': 'produce_composite'
    },
    'paper_mill': {
        'id': 'paper_mill', 'name': '📰 Бумажный комбинат', 'specialization': 'forester',
        'category': 'processing', 'level_required': 20, 'build_cost': 125000.0,
        'workers_required': 34, 'energy_required': 4, 'cycle_duration': 105,
        'description': 'Промышленное производство бумаги из целлюлозы',
        'inputs': {'cellulose': 2.0, 'energy': 4.0}, 'outputs': {'paper': 3.0},
        'recipe_id': 'produce_paper'
    },
    'engineered_wood_factory': {
        'id': 'engineered_wood_factory', 'name': '🏗️ Завод инженерной древесины', 'specialization': 'forester',
        'category': 'industry', 'level_required': 32, 'build_cost': 260000.0,
        'workers_required': 46, 'energy_required': 6, 'cycle_duration': 150,
        'description': 'Клеёные и усиленные древесные конструкционные материалы',
        'inputs': {'lumber': 2.0, 'basic_chem': 1.0, 'energy': 6.0}, 'outputs': {'engineered_wood': 2.0},
        'recipe_id': 'produce_engineered_wood'
    },
    'prefab_factory': {
        'id': 'prefab_factory', 'name': '🏢 Завод сборных модулей', 'specialization': 'forester',
        'category': 'industry', 'level_required': 40, 'build_cost': 430000.0,
        'workers_required': 62, 'energy_required': 8, 'cycle_duration': 180,
        'description': 'Модульные конструкции из инженерной древесины и металла',
        'inputs': {'engineered_wood': 2.0, 'metal_structures': 1.0, 'energy': 8.0}, 'outputs': {'prefab_modules': 1.5},
        'recipe_id': 'assemble_prefab_modules'
    },
    'advanced_composite_factory': {
        'id': 'advanced_composite_factory', 'name': '🧬 Центр сверхкомпозитов', 'specialization': 'forester',
        'category': 'endgame', 'level_required': 54, 'build_cost': 1200000.0,
        'workers_required': 86, 'energy_required': 10, 'cycle_duration': 225,
        'description': 'Лёгкие сверхпрочные композиты для транспорта и космоса',
        'inputs': {'composite': 2.0, 'catalyst': 0.5, 'energy': 10.0}, 'outputs': {'advanced_composite': 1.0},
        'recipe_id': 'produce_advanced_composite'
    },

    # ---------------- 7. ХИМИК (chemist) ----------------
    'chemical_plant': {
        'id': 'chemical_plant', 'name': '⚗️ Химзавод', 'specialization': 'chemist',
        'category': 'extraction', 'level_required': 1, 'build_cost': 25000.0,
        'workers_required': 30, 'energy_required': 4, 'cycle_duration': 60,
        'description': 'Базовый синтез кислот, щелочей и реагентов',
        'inputs': {'oil_crude': 1.5, 'water': 2.0, 'energy': 4.0}, 'outputs': {'basic_chem': 3.0},
        'recipe_id': 'chem_synth_base'
    },
    'fertilizer_plant': {
        'id': 'fertilizer_plant', 'name': '🌱 Завод удобрений', 'specialization': 'chemist',
        'category': 'processing', 'level_required': 8, 'build_cost': 52000.0,
        'workers_required': 30, 'energy_required': 4, 'cycle_duration': 90,
        'description': 'Азотные и комплексные удобрения для агрокомплекса',
        'inputs': {'basic_chem': 1.5, 'water': 2.0, 'energy': 4.0}, 'outputs': {'fertilizer': 3.0},
        'recipe_id': 'chem_fertilizers'
    },
    'polymer_factory': {
        'id': 'polymer_factory', 'name': '🧴 Полимерный завод', 'specialization': 'chemist',
        'category': 'processing', 'level_required': 14, 'build_cost': 95000.0,
        'workers_required': 35, 'energy_required': 4, 'cycle_duration': 105,
        'description': 'Каталитический синтез конструкционных полимеров',
        'inputs': {'oil_crude': 2.0, 'basic_chem': 1.0, 'energy': 4.0}, 'outputs': {'plastics': 3.0},
        'recipe_id': 'chem_polymers'
    },
    'electrolyte_factory': {
        'id': 'electrolyte_factory', 'name': '🔋 Завод электролитов', 'specialization': 'chemist',
        'category': 'hightech', 'level_required': 42, 'build_cost': 520000.0,
        'workers_required': 35, 'energy_required': 5, 'cycle_duration': 120,
        'description': 'Электролиты высокой чистоты для тяговых батарей',
        'inputs': {'lithium_raw': 2.0, 'basic_chem': 1.0, 'energy': 5.0}, 'outputs': {'electrolyte': 2.0},
        'recipe_id': 'chem_electrolyte'
    },
    'biochem_factory': {
        'id': 'biochem_factory', 'name': '🧬 Биохимический комплекс', 'specialization': 'chemist',
        'category': 'industry', 'level_required': 24, 'build_cost': 180000.0,
        'workers_required': 45, 'energy_required': 6, 'cycle_duration': 150,
        'description': 'Ферментные биореактивы высокой степени очистки',
        'inputs': {'bio_raw': 3.0, 'basic_chem': 1.0, 'energy': 6.0}, 'outputs': {'bioreagent': 2.0},
        'recipe_id': 'chem_bioreagents'
    },
    'catalyst_factory': {
        'id': 'catalyst_factory', 'name': '🧪 Завод катализаторов', 'specialization': 'chemist',
        'category': 'endgame', 'level_required': 48, 'build_cost': 760000.0,
        'workers_required': 55, 'energy_required': 7, 'cycle_duration': 180,
        'description': 'Специальные промышленные катализаторы',
        'inputs': {'rare_earths': 1.0, 'basic_chem': 2.0, 'energy': 7.0}, 'outputs': {'catalyst': 1.5},
        'recipe_id': 'chem_catalysts'
    },
    'pharmaceutical_plant': {
        'id': 'pharmaceutical_plant', 'name': '💊 Фармацевтический завод', 'specialization': 'chemist',
        'category': 'industry', 'level_required': 30, 'build_cost': 250000.0,
        'workers_required': 48, 'energy_required': 6, 'cycle_duration': 150,
        'description': 'Промышленный выпуск лекарственных субстанций из биореактивов',
        'inputs': {'bioreagent': 1.0, 'basic_chem': 1.0, 'energy': 6.0}, 'outputs': {'pharmaceuticals': 2.0},
        'recipe_id': 'chem_pharmaceuticals'
    },
    'industrial_gas_plant': {
        'id': 'industrial_gas_plant', 'name': '🧊 Завод технических газов', 'specialization': 'chemist',
        'category': 'industry', 'level_required': 34, 'build_cost': 320000.0,
        'workers_required': 52, 'energy_required': 7, 'cycle_duration': 165,
        'description': 'Разделение и подготовка газов высокой чистоты для промышленности',
        'inputs': {'gas_natural': 2.0, 'water': 1.0, 'energy': 7.0}, 'outputs': {'industrial_gases': 2.5},
        'recipe_id': 'chem_industrial_gases'
    },
    'lithium_refinery': {
        'id': 'lithium_refinery', 'name': '🔋 Литиевый рафинировочный комплекс', 'specialization': 'chemist',
        'category': 'hightech', 'level_required': 46, 'build_cost': 680000.0,
        'workers_required': 64, 'energy_required': 9, 'cycle_duration': 195,
        'description': 'Глубокая очистка лития для аккумуляторной промышленности',
        'inputs': {'lithium_raw': 1.5, 'basic_chem': 1.0, 'energy': 9.0}, 'outputs': {'lithium_pure': 1.0},
        'recipe_id': 'refine_lithium'
    },
    'battery_gigafactory': {
        'id': 'battery_gigafactory', 'name': '🔋 Гигафабрика батарей', 'specialization': 'chemist',
        'category': 'endgame', 'level_required': 54, 'build_cost': 1350000.0,
        'workers_required': 90, 'energy_required': 12, 'cycle_duration': 240,
        'description': 'Тяговые батареи для транспорта, роботов и стратегических систем',
        'inputs': {'lithium_pure': 1.0, 'electrolyte': 1.0, 'aluminum': 1.0, 'energy': 12.0}, 'outputs': {'batteries': 1.5},
        'recipe_id': 'assemble_batteries'
    },

    # ---------------- 8. ТЕХНОПРОМ (technoprom) ----------------
    'component_factory': {
        'id': 'component_factory', 'name': '🔧 Завод компонентов', 'specialization': 'technoprom',
        'category': 'extraction', 'level_required': 1, 'build_cost': 30000.0,
        'workers_required': 25, 'energy_required': 3, 'cycle_duration': 60,
        'description': 'Производство медных контактов и деталей',
        'inputs': {'copper': 1.5, 'plastics': 1.0, 'energy': 3.0}, 'outputs': {'components': 3.0},
        'recipe_id': 'tech_components'
    },
    'chip_factory': {
        'id': 'chip_factory', 'name': '💻 Микроэлектронный завод', 'specialization': 'technoprom',
        'category': 'processing', 'level_required': 8, 'build_cost': 95000.0,
        'workers_required': 40, 'energy_required': 5, 'cycle_duration': 120,
        'description': 'Литография кремниевых микрочипов',
        'inputs': {'components': 2.0, 'basic_chem': 0.5, 'energy': 5.0}, 'outputs': {'electronics': 2.0},
        'recipe_id': 'tech_chips'
    },
    'server_factory': {
        'id': 'server_factory', 'name': '🖥️ Серверный комплекс', 'specialization': 'technoprom',
        'category': 'industry', 'level_required': 20, 'build_cost': 180000.0,
        'workers_required': 50, 'energy_required': 7, 'cycle_duration': 150,
        'description': 'Высокопроизводительные серверные стойки',
        'inputs': {'electronics': 2.0, 'steel': 1.5, 'energy': 7.0}, 'outputs': {'servers': 1.5},
        'recipe_id': 'tech_servers'
    },
    'robot_factory': {
        'id': 'robot_factory', 'name': '🤖 Робототехнический завод', 'specialization': 'technoprom',
        'category': 'industry', 'level_required': 32, 'build_cost': 340000.0,
        'workers_required': 60, 'energy_required': 8, 'cycle_duration': 180,
        'description': 'Промышленные манипуляторы и роботы',
        'inputs': {'electronics': 1.5, 'machinery': 1.5, 'energy': 8.0}, 'outputs': {'robots': 1.0},
        'recipe_id': 'tech_robots'
    },
    'ai_factory': {
        'id': 'ai_factory', 'name': '🧠 AI-фабрика', 'specialization': 'technoprom',
        'category': 'hightech', 'level_required': 46, 'build_cost': 820000.0,
        'workers_required': 70, 'energy_required': 10, 'cycle_duration': 210,
        'description': 'Тензорные нейроускорители для ИИ',
        'inputs': {'electronics': 2.5, 'rare_earths': 1.0, 'energy': 10.0}, 'outputs': {'ai_accelerator': 1.0},
        'recipe_id': 'tech_ai'
    },
    'aerospace_complex': {
        'id': 'aerospace_complex', 'name': '🛰️ Аэрокосмический комплекс', 'specialization': 'technoprom',
        'category': 'endgame', 'level_required': 58, 'build_cost': 2200000.0,
        'workers_required': 100, 'energy_required': 12, 'cycle_duration': 240,
        'description': 'Сборка спутников и аэрокосмических систем',
        'inputs': {'electronics': 2.0, 'superalloy': 1.0, 'machinery': 1.5, 'energy': 12.0},
        'outputs': {'aerospace_system': 1.0},
        'recipe_id': 'tech_aerospace'
    },
    'telecom_factory': {
        'id': 'telecom_factory', 'name': '📡 Завод телеком-оборудования', 'specialization': 'technoprom',
        'category': 'industry', 'level_required': 14, 'build_cost': 125000.0,
        'workers_required': 38, 'energy_required': 5, 'cycle_duration': 120,
        'description': 'Сетевое оборудование и промышленные системы связи',
        'inputs': {'electronics': 1.5, 'copper': 1.0, 'energy': 5.0}, 'outputs': {'telecom_equipment': 1.5},
        'recipe_id': 'tech_telecom'
    },
    'data_center': {
        'id': 'data_center', 'name': '🗄️ Центр обработки данных', 'specialization': 'technoprom',
        'category': 'industry', 'level_required': 26, 'build_cost': 260000.0,
        'workers_required': 44, 'energy_required': 8, 'cycle_duration': 150,
        'description': 'Вычислительные мощности для корпоративных и государственных заказов',
        'inputs': {'servers': 1.0, 'energy': 8.0}, 'outputs': {'cloud_compute': 2.0},
        'recipe_id': 'tech_cloud_compute'
    },
    'drone_factory': {
        'id': 'drone_factory', 'name': '🚁 Завод промышленных дронов', 'specialization': 'technoprom',
        'category': 'hightech', 'level_required': 38, 'build_cost': 480000.0,
        'workers_required': 62, 'energy_required': 9, 'cycle_duration': 180,
        'description': 'Автономные промышленные беспилотные платформы',
        'inputs': {'electronics': 1.0, 'machinery': 1.0, 'auto_components': 1.0, 'energy': 9.0}, 'outputs': {'industrial_drones': 1.0},
        'recipe_id': 'tech_industrial_drones'
    },
    'quantum_factory': {
        'id': 'quantum_factory', 'name': '⚛️ Квантовый технологический центр', 'specialization': 'technoprom',
        'category': 'endgame', 'level_required': 52, 'build_cost': 1500000.0,
        'workers_required': 90, 'energy_required': 12, 'cycle_duration': 240,
        'description': 'Квантовые вычислительные модули на редких материалах',
        'inputs': {'electronics': 2.0, 'gallium_raw': 0.5, 'rare_earths': 0.5, 'energy': 12.0}, 'outputs': {'quantum_modules': 0.75},
        'recipe_id': 'tech_quantum_modules'
    },
}
