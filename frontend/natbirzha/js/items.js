/**
 * Natbirzha - Canonical Items Registry and Localization Dictionary
 * Maps item IDs to Russian names, emojis, and measurement units.
 */

export const ITEMS = {
  // Tier 0: Utilities & Naturals
  grid_quota: { name: 'Квота энергосети', icon: '⚡', unit: 'МВт·ч' },
  energy: { name: 'Электроэнергия', icon: '💡', unit: 'МВт·ч' },
  water: { name: 'Техническая вода', icon: '💧', unit: 'м³' },
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
  uranium_raw: { name: 'Урановая руда', icon: '☢️', unit: 'т' },

  // Tier 2: Intermediate Processing
  steel: { name: 'Конструкционная сталь', icon: '🔩', unit: 'т' },
  aluminum: { name: 'Алюминий', icon: '🪙', unit: 'т' },
  copper: { name: 'Медь первичная', icon: '🟠', unit: 'т' },
  rolled_metal: { name: 'Прокат металлический', icon: '🏗️', unit: 'т' },
  metal_structures: { name: 'Металлоконструкции', icon: '🔩', unit: 'т' },
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

  // Tier 3: Advanced & High-Tech
  plastics: { name: 'Полимеры и пластик', icon: '🧴', unit: 'т' },
  catalyst: { name: 'Катализаторы', icon: '💠', unit: 'кг' },
  lithium_pure: { name: 'Аккумуляторный литий', icon: '🔋', unit: 'кг' },
  uranium_enriched: { name: 'Обогащённый уран', icon: '⚛️', unit: 'шт.' },
  components: { name: 'Электронные компоненты', icon: '🔧', unit: 'шт.' },
  machinery: { name: 'Механические узлы', icon: '⚙️', unit: 'шт.' },
  auto_components: { name: 'Автокомпоненты', icon: '🚗', unit: 'шт.' },
  superalloy: { name: 'Жаропрочные спецсплавы', icon: '🧪', unit: 'кг' },
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
};

/**
 * Returns localized metadata for a given item ID with safe fallbacks.
 * @param {string} itemId
 * @returns {{ name: string, icon: string, unit: string }}
 */
export function getItemInfo(itemId) {
  if (!itemId) return { name: 'Неизвестно', icon: '📦', unit: 'шт.' };
  let key = String(itemId).toLowerCase().trim();
  if (ITEM_ALIASES[key]) key = ITEM_ALIASES[key];
  return ITEMS[key] || {
    name: key.replace(/_/g, ' '),
    icon: '📦',
    unit: 'шт.'
  };
}
