/**
 * Natbirzha - Canonical Items Registry and Localization Dictionary
 * Maps item IDs to Russian names, legacy glyphs, and measurement units.
 */

export const ITEMS = {
  // Tier 0: Utilities & Naturals
  grid_quota: { name: 'Квота энергосети', icon: '⚡', unit: 'МВт·ч' },
  energy: { name: 'Электроэнергия', icon: '💡', unit: 'МВт·ч' },
  ai_compute: { name: 'Вычислительная мощность ИИ', icon: '🧠', unit: 'выч. ч' },
  water: { name: 'Техническая вода', icon: '💧', unit: 'м³' },
  clean_water: { name: 'Очищенная вода', icon: '🚰', unit: 'м³' },
  ultrapure_water: { name: 'Сверхчистая технологическая вода', icon: '🔬', unit: 'м³' },
  well_lease: { name: 'Отвод скважины', icon: '📜', unit: 'шт.' },
  forest_fund: { name: 'Квота лесного фонда', icon: '🌲', unit: 'га' },

  // Tier 1: Primary Extraction
  grain: { name: 'Зерно', icon: '🌾', unit: 'т' },
  bio_raw: { name: 'Биосырьё', icon: '🌱', unit: 'т' },
  wood_raw: { name: 'Кругляк древесины', icon: '🪵', unit: 'м³' },
  coal: { name: 'Каменный уголь', icon: '🪨', unit: 'т' },
  iron_ore: { name: 'Железная руда', icon: '⛏️', unit: 'т' },
  bauxite: { name: 'Бокситы', icon: '🧱', unit: 'т' },
  minerals: { name: 'Минералы и флюс', icon: '💎', unit: 'т' },
  oil_crude: { name: 'Сырая нефть', icon: '🛢️', unit: 'барр.' },
  gas_natural: { name: 'Природный газ', icon: '🔥', unit: 'тыс. м³' },
  rare_earths: { name: 'Редкоземельные металлы', icon: '✨', unit: 'кг' },
  lithium_raw: { name: 'Неочищенный литий', icon: '🔋', unit: 'т' },
  cobalt_raw: { name: 'Кобальтовый концентрат', icon: '🔷', unit: 'кг' },
  gallium_raw: { name: 'Галлиевый концентрат', icon: '🧫', unit: 'кг' },
  uranium_raw: { name: 'Урановая руда', icon: '☢️', unit: 'т' },
  copper_ore: { name: 'Медная руда', icon: '🟠', unit: 'т' },
  silver_ore: { name: 'Серебряная руда', icon: '🥈', unit: 'кг' },
  gold_ore: { name: 'Золотая руда', icon: '🥇', unit: 'кг' },
  nickel_concentrate: { name: 'Никелевый концентрат', icon: '⚙️', unit: 'т' },
  diamonds: { name: 'Промышленные алмазы', icon: '💎', unit: 'кар.' },
  sugar_raw: { name: 'Сахарное сырьё', icon: '🍬', unit: 'т' },
  hops: { name: 'Хмель', icon: '🌿', unit: 'т' },
  grapes: { name: 'Виноград', icon: '🍇', unit: 'т' },

  // Tier 2: Intermediate Processing
  steel: { name: 'Конструкционная сталь', icon: '🔩', unit: 'т' },
  aluminum: { name: 'Алюминий', icon: '🪙', unit: 'т' },
  copper: { name: 'Медь первичная', icon: '🟠', unit: 'т' },
  rolled_metal: { name: 'Прокат металлический', icon: '🏗️', unit: 'т' },
  metal_structures: { name: 'Металлоконструкции', icon: '🔩', unit: 'т' },
  brick: { name: 'Строительный кирпич', icon: '🧱', unit: 'т' },
  cement: { name: 'Цемент', icon: '🏗️', unit: 'т' },
  concrete: { name: 'Товарный бетон', icon: '🏢', unit: 'м³' },
  construction_capacity: { name: 'Строительная мощность', icon: '👷', unit: 'ед.' },
  logistics_capacity: { name: 'Логистическая мощность', icon: '🚚', unit: 'ед.' },
  lumber: { name: 'Пиломатериалы', icon: '🪵', unit: 'м³' },
  cellulose: { name: 'Целлюлоза', icon: '📄', unit: 'т' },
  food: { name: 'Продовольственные пайки', icon: '🥫', unit: 'ящ.' },
  feed: { name: 'Комбикорм', icon: '🌽', unit: 'т' },
  flour: { name: 'Мука', icon: '🍞', unit: 'т' },
  meat: { name: 'Мясо', icon: '🥩', unit: 'т' },
  milk: { name: 'Молоко', icon: '🥛', unit: 'т' },
  fuel_diesel: { name: 'Дизельное топливо', icon: '⛽', unit: 'л' },
  gasoline: { name: 'Товарный бензин', icon: '⛽', unit: 'л' },
  jet_fuel: { name: 'Авиакеросин', icon: '✈️', unit: 'л' },
  basic_chem: { name: 'Базовые реагенты', icon: '🧪', unit: 'т' },
  fertilizer: { name: 'Удобрения', icon: '🌱', unit: 'т' },
  cardboard: { name: 'Тарный картон', icon: '📦', unit: 'т' },
  furniture: { name: 'Мебель', icon: '🪑', unit: 'шт.' },
  composite: { name: 'Древесные композиты', icon: '🧱', unit: 'т' },
  electrolyte: { name: 'Электролит', icon: '🔋', unit: 'л' },
  bioreagent: { name: 'Биореактивы', icon: '🧬', unit: 'кг' },
  fresh_food: { name: 'Свежая тепличная продукция', icon: '🍅', unit: 'ящ.' },
  dairy_goods: { name: 'Молочная продукция', icon: '🥛', unit: 'ящ.' },
  paper: { name: 'Промышленная бумага', icon: '📰', unit: 'т' },
  engineered_wood: { name: 'Инженерная древесина', icon: '🏗️', unit: 'м³' },
  prefab_modules: { name: 'Сборные модули', icon: '🏢', unit: 'шт.' },
  lng: { name: 'Сжиженный природный газ', icon: '❄️', unit: 'т' },
  lubricants: { name: 'Промышленные масла', icon: '🛢️', unit: 'т' },
  pharmaceuticals: { name: 'Фармацевтические субстанции', icon: '💊', unit: 'кг' },
  industrial_gases: { name: 'Технические газы', icon: '🧊', unit: 'балл.' },
  beer: { name: 'Пиво', icon: '🍺', unit: 'ящ.' },
  wine: { name: 'Вино', icon: '🍷', unit: 'ящ.' },
  aged_spirits: { name: 'Выдержанный коньяк', icon: '🥃', unit: 'ящ.' },

  // Tier 3: Advanced & High-Tech
  plastics: { name: 'Полимеры и пластик', icon: '🧴', unit: 'т' },
  catalyst: { name: 'Катализаторы', icon: '💠', unit: 'кг' },
  lithium_pure: { name: 'Аккумуляторный литий', icon: '🔋', unit: 'кг' },
  uranium_enriched: { name: 'Обогащённый уран', icon: '⚛️', unit: 'шт.' },
  components: { name: 'Электронные компоненты', icon: '🔧', unit: 'шт.' },
  machinery: { name: 'Механические узлы', icon: '⚙️', unit: 'шт.' },
  auto_components: { name: 'Автокомпоненты', icon: '🚗', unit: 'шт.' },
  superalloy: { name: 'Жаропрочные спецсплавы', icon: '🧪', unit: 'кг' },
  nickel_metal: { name: 'Никель первичный', icon: '⚙️', unit: 'т' },
  advanced_alloy: { name: 'Высокопрочный сплав', icon: '🛡️', unit: 'кг' },
  titanium_alloy: { name: 'Титановый сплав', icon: '🛰️', unit: 'кг' },
  electrical_equipment: { name: 'Электротехническое оборудование', icon: '⚡', unit: 'компл.' },
  sensors: { name: 'Промышленные датчики', icon: '📡', unit: 'шт.' },
  automation_systems: { name: 'Системы промышленной автоматики', icon: '🤖', unit: 'компл.' },
  electronics: { name: 'Электронные чипы', icon: '💻', unit: 'шт.' },
  batteries: { name: 'Тяговые батареи', icon: '🔋', unit: 'шт.' },
  servers: { name: 'Серверные стойки', icon: '🖥️', unit: 'шт.' },
  robots: { name: 'Промышленные роботы', icon: '🤖', unit: 'шт.' },
  ai_accelerator: { name: 'AI-ускорители', icon: '🧠', unit: 'шт.' },
  aerospace_system: { name: 'Аэрокосмические узлы', icon: '🛰️', unit: 'шт.' },
  agrotech_seed: { name: 'Агротехнологические семенные линии', icon: '🧬', unit: 'парт.' },
  orbital_rations: { name: 'Орбитальные пищевые рационы', icon: '🛰️', unit: 'компл.' },
  precision_parts: { name: 'Прецизионные детали', icon: '🧰', unit: 'компл.' },
  industrial_modules: { name: 'Тяжёлые промышленные модули', icon: '🏭', unit: 'шт.' },
  orbital_alloy: { name: 'Орбитальный сверхсплав', icon: '🚀', unit: 'кг' },
  synthetic_fuel: { name: 'Синтетическое топливо', icon: '🧪', unit: 'т' },
  cryogenic_fuel: { name: 'Криогенное ракетное топливо', icon: '🚀', unit: 'т' },
  advanced_composite: { name: 'Сверхпрочный композит', icon: '🧬', unit: 'т' },
  telecom_equipment: { name: 'Телеком-оборудование', icon: '📡', unit: 'компл.' },
  cloud_compute: { name: 'Вычислительные контракты', icon: '☁️', unit: 'контр.' },
  industrial_drones: { name: 'Промышленные беспилотники', icon: '🚁', unit: 'шт.' },
  quantum_modules: { name: 'Квантовые модули', icon: '⚛️', unit: 'шт.' },

  // Tier 4: Military
  military_gear: { name: 'Военное снаряжение', icon: '🪖', unit: 'компл.' },
};

const ITEM_ALIASES = {
  wheat: 'grain',
  wood: 'wood_raw',
  oil: 'oil_crude',
  gas: 'gas_natural',
  reagent: 'basic_chem',
  polymer: 'plastics',
  plastic: 'plastics',
  chips: 'electronics',
  machines: 'machinery',
  parts: 'components',
  battery: 'batteries',
  uranium: 'uranium_raw',
  lithium: 'lithium_raw',
  bio_raw_material: 'bio_raw',
  rations: 'food',
  cognac: 'aged_spirits',
  brandy: 'aged_spirits',
};

const ITEM_ICON_GROUPS = Object.freeze({
  energy: 'grid_quota energy',
  water: 'water clean_water ultrapure_water',
  ai: 'ai_compute cloud_compute ai_accelerator',
  mining: 'well_lease coal iron_ore bauxite minerals oil_crude gas_natural rare_earths lithium_raw cobalt_raw gallium_raw uranium_raw copper_ore silver_ore gold_ore nickel_concentrate diamonds lithium_pure uranium_enriched nickel_metal',
  agriculture: 'forest_fund grain bio_raw wood_raw sugar_raw hops grapes food feed flour meat milk fresh_food dairy_goods agrotech_seed orbital_rations',
  oil: 'fuel_diesel gasoline jet_fuel lng lubricants cryogenic_fuel industrial_gases',
  metallurgy: 'steel aluminum copper rolled_metal metal_structures construction_capacity superalloy advanced_alloy titanium_alloy electrical_equipment',
  construction: 'brick cement concrete lumber engineered_wood prefab_modules industrial_modules advanced_composite',
  chemistry: 'basic_chem fertilizer cellulose cardboard electrolyte bioreagent pharmaceuticals plastics catalyst batteries synthetic_fuel',
  brewing: 'beer wine aged_spirits',
  logistics: 'logistics_capacity industrial_drones',
  technology: 'components machinery auto_components sensors automation_systems electronics servers robots aerospace_system precision_parts telecom_equipment quantum_modules military_gear',
});

const ITEM_ICON_NAMES = Object.freeze(Object.fromEntries(
  Object.entries(ITEM_ICON_GROUPS).flatMap(([icon, ids]) => ids.split(' ').map((id) => [id, icon])),
));

export function getItemIconName(itemId) {
  if (!itemId) return 'resource';
  const key = String(itemId).toLowerCase().trim();
  return ITEM_ICON_NAMES[ITEM_ALIASES[key] || key] || 'resource';
}

/**
 * Returns localized metadata for a given item ID with safe fallbacks.
 * @param {string} itemId
 * @returns {{ name: string, icon: string, unit: string }}
 */
export function getItemInfo(itemId) {
  if (!itemId) return { name: 'Неизвестно', icon: 'resource', unit: 'шт.' };
  let key = String(itemId).toLowerCase().trim();
  if (ITEM_ALIASES[key]) key = ITEM_ALIASES[key];
  const item = ITEMS[key];
  return item
    ? { ...item, icon: ITEM_ICON_NAMES[key] || 'resource' }
    : { name: 'Неизвестный ресурс', icon: 'resource', unit: 'шт.' };
}
