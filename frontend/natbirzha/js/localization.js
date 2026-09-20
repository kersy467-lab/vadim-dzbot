/**
 * Natbirzha UI Localization Dictionary
 * Human-readable Russian titles and icons for specializations and production facilities.
 */

export const SPECIALIZATIONS = {
  agrarian: 'Сельское хозяйство',
  miner: 'Горнодобыча',
  metallurgist: 'Металлургия',
  oilman: 'Нефтегаз',
  power_engineer: 'Энергетика',
  forester: 'Лесозаготовка',
  chemist: 'Химия',
  technoprom: 'Машиностроение',
};

export const BUILDINGS = {
  // 1. Энергетика (power_engineer)
  solar_plant: '☀️ Солнечная электростанция',
  hydro_plant: '🌊 ГЭС',
  thermal_power_plant: '🔥 ТЭЦ',
  thermal_plant: '🔥 ТЭЦ',
  coal_power_plant: '🔥 ТЭЦ',
  wind_farm: '💨 Ветропарк',
  nuclear_plant: '☢️ АЭС',
  fusion_plant: '⚛️ Термоядерный комплекс',
  gas_turbine_plant: '🔥 Газотурбинная станция',
  geothermal_plant: '🌋 Геотермальная станция',
  tidal_plant: '🌊 Приливная электростанция',
  fast_reactor: '⚛️ Реактор на быстрых нейтронах',
  hydro_solar: '☀️ Солнечная электростанция',

  // 2. Металлургия (metallurgist)
  iron_mine: '⛏️ Железный рудник',
  bauxite_mine: '🧱 Бокситовый рудник',
  smelter: '🔥 Металлургический комбинат',
  steel_mill: '🏭 Сталелитейный завод',
  metallurgy_smelter: '🏭 Сталелитейный завод',
  rolling_mill: '🏗️ Прокатный стан',
  superalloy_foundry: '🧪 Литейный цех спецсплавов',
  metal_structure_plant: '🔩 Завод металлоконструкций',
  aluminum_plant: '🪙 Алюминиевый завод',
  copper_smelter: '🟠 Медеплавильный комбинат',

  // 3. Нефтегаз (oilman)
  oil_rig: '🛢️ Нефтяная вышка',
  oil_refinery: '⛽ Нефтеперерабатывающий завод',
  gas_well: '🔥 Газовая скважина',
  fuel_plant: '⛽ Топливный завод',
  lng_terminal: '❄️ СПГ-терминал',
  gas_condensate_plant: '🧊 Газоперерабатывающий завод',
  deep_drilling_rig: '🛢️ Глубоководная буровая',

  // 4. Сельское хозяйство (agrarian)
  farm_grain: '🌱 Зерновая ферма',
  farm: '🌱 Зерновая ферма',
  grain_farm: '🌱 Зерновая ферма',
  feed_mill: '🌽 Комбикормовый завод',
  livestock_complex: '🐄 Животноводческий комплекс',
  food_factory: '🥫 Пищевой комбинат',
  bio_farm: '🧬 Биоферма',
  flour_mill: '🍞 Мукомольный завод',
  greenhouse_complex: '🍅 Тепличный агрокомплекс',
  dairy_plant: '🥛 Молочный комбинат',
  agrotech_lab: '🧬 Агробиотехнологический центр',
  orbital_agro_complex: '🛰️ Орбитальный агрокомплекс',

  // 5. Лесозаготовка (forester)
  sawmill: '🪵 Лесозаготовка',
  woodworking: '🪵 Деревообрабатывающий цех',
  paper_mill: '📄 ЦБК',
  furniture_factory: '🪑 Мебельная фабрика',
  cellulose_plant: '📄 Целлюлозный завод',
  wood_composite_plant: '🧱 Завод древесных плит',
  prefab_home_plant: '🏢 Комбинат деревянного домостроения',

  // 6. Химия (chemist)
  chemical_plant: '🧪 Химзавод',
  chem_plant: '🧪 Химзавод',
  fertilizer_plant: '🌱 Завод удобрений',
  plastics_factory: '🧴 Завод полимеров',
  polymer_plant: '🧴 Завод полимеров',
  battery_plant: '🔋 Аккумуляторный завод',
  pharma_plant: '💊 Фармацевтический завод',
  reagent_plant: '🧪 Завод химреагентов',
  catalyst_plant: '💠 Завод катализаторов',

  // 7. Горнодобыча (miner)
  mine: '⛏️ Железный рудник',
  coal_mine: '🪨 Угольный разрез',
  mineral_quarry: '💎 Карьер минералов',
  deep_mine: '🔋 Литиевый рудник',
  lithium_mine: '🔋 Литиевый рудник',
  uranium_mine: '☢️ Урановый карьер',
  uranium_quarry: '☢️ Урановый карьер',
  rare_earth_mine: '✨ Редкоземельный карьер',

  // 8. Машиностроение / Технопром (technoprom)
  electronics_factory: '⚡ Завод компонентов',
  machinery_plant: '⚙️ Машиностроительный завод',
  component_factory: '⚙️ Завод механических узлов',
  chip_factory: '💻 Фабрика микроэлектроники',
  chip_fab: '💻 Фабрика микроэлектроники',
  electronics_fab: '💻 Фабрика микроэлектроники',
  centrifuge: '💻 Фабрика микроэлектроники',
  auto_plant: '🚗 Автомобильный завод',
  robotics_plant: '🤖 Завод робототехники',
  server_fab: '🖥️ Серверная фабрика',
  ai_chip_fab: '🧠 Фабрика ИИ-ускорителей',
  aerospace_plant: '🛰️ Аэрокосмический завод',
  precision_lab: '🧰 Лаборатория прецизионной механики',
  supercomputer_cluster: '🖥️ Суперкомпьютерный кластер',
  quantum_foundry: '⚛️ Квантовая фабрика',
  machine_factory: '⚙️ Завод машиностроения',
  defense_plant: '⚙️ Завод машиностроения',
};

/**
 * Returns human-readable Russian specialization name.
 * @param {string} spec
 * @returns {string}
 */
export function getSpecializationName(spec) {
  if (!spec) return '';
  const key = String(spec).toLowerCase().trim();
  return SPECIALIZATIONS[key] || spec.replace(/_/g, ' ');
}

/**
 * Returns human-readable Russian building name with icon.
 * @param {string} bType
 * @returns {string}
 */
export function getBuildingName(bType) {
  if (!bType) return '';
  const key = String(bType).toLowerCase().trim();
  return BUILDINGS[key] || bType.replace(/_/g, ' ');
}
