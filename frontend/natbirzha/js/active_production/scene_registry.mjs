export const SCENE_FAMILIES = Object.freeze({
  resources: { name: 'Рабочий посёлок', pickup: 'Руда', station: 'Карьер', delivery: 'Вагонетка', actor: 'Рабочий', operation: 'СБОР', color: '#a9723f' },
  energy: { name: 'Дежурный диспетчер', pickup: 'Заряд', station: 'Генератор', delivery: 'Городская сеть', actor: 'Техник', operation: 'ПУЛЬТ', color: '#d6a52e' },
  oilgas: { name: 'Нефтепромысел', pickup: 'Партия топлива', station: 'Скважина', delivery: 'Резервуар', actor: 'Цистерна', operation: 'МАРШРУТ', color: '#43869a' },
  materials: { name: 'Заводской цех', pickup: 'Заготовка', station: 'Печь', delivery: 'Стеллаж', actor: 'Погрузчик', operation: 'ЦЕХ', color: '#c16d47' },
  infrastructure: { name: 'Город доставки', pickup: 'Коробки', station: 'Склад', delivery: 'Магазин', actor: 'Грузовик', operation: 'МАРШРУТ', color: '#478a72' },
  technology: { name: 'Микрофабрика', pickup: 'Плата', station: 'Сборочный стол', delivery: 'Испытательный стенд', actor: 'Робот', operation: 'СБОРКА', color: '#6176b6' },
  bank: { name: 'Финансовый квартал', pickup: 'Папка клиента', station: 'Окно банка', delivery: 'Расчётный отдел', actor: 'Курьер', operation: 'БАНК', color: '#a58a45' },
});

const variants = Object.freeze({
  resources: [['Руда', 'Карьер', 'Вагонетка'], ['Растение', 'Поле', 'Элеватор'], ['Древесина', 'Лесной участок', 'Склад брёвен'], ['Вода', 'Насосная', 'Резервуар']],
  energy: [['Топливо', 'Генератор', 'Подстанция'], ['Заряд', 'Солнечная панель', 'Аккумулятор'], ['Поток энергии', 'Турбина', 'Городская сеть'], ['Команда запуска', 'Щитовая', 'Пульт']],
  oilgas: [['Капля нефти', 'Скважина', 'Резервуар'], ['Газовый модуль', 'Насос', 'Эстакада'], ['Пустая цистерна', 'Колонна', 'Переработка'], ['Партия топлива', 'Трубопровод', 'Лаборатория']],
  materials: [['Заготовка', 'Печь', 'Стеллаж'], ['Слиток', 'Пресс', 'Охлаждение'], ['Поддон', 'Прокатный стан', 'Линия отгрузки'], ['Катушка', 'Сборочный стол', 'Склад']],
  infrastructure: [['Коробки', 'Склад', 'Магазин'], ['Стройматериалы', 'Стройка', 'Дом'], ['Паллеты', 'Сортировка', 'Терминал'], ['Контейнер', 'Погрузка', 'Порт']],
  technology: [['Плата', 'Сборочный стол', 'Испытательный стенд'], ['Сенсор', 'Серверная стойка', 'Упаковка'], ['Модуль', 'Лаборатория', 'Склад приборов'], ['Микросхема', 'Конвейер', 'Сервисный робот']],
  bank: [['Папка клиента', 'Окно банка', 'Расчётный отдел'], ['Платёж', 'Кредитный стол', 'Архив'], ['Заявка', 'Терминал', 'Касса'], ['Документ', 'Хранилище', 'Клиентский зал']],
});

function stableHash(value) {
  let hash = 2166136261;
  for (const character of String(value)) hash = Math.imul(hash ^ character.charCodeAt(0), 16777619);
  return hash >>> 0;
}

export function sceneForBranch(branchId, sectorId, serverScene = null) {
  const family = SCENE_FAMILIES[sectorId];
  if (!family || !branchId) return null;
  const seed = stableHash(branchId);
  const variant = variants[sectorId][seed % variants[sectorId].length];
  const fallback = {
    branch_id: branchId, sector_id: sectorId, scene_family: sectorId,
    scene_name: family.name, operation: family.operation, vehicle: family.actor,
    visual_pickup: variant[0], workstation: variant[1], delivery_marker: variant[2],
    microvariant: seed % 6,
  };
  if (branchId === 'ore_mining') Object.assign(fallback, {
    visual_pickup: 'Железная руда', workstation: 'Карьер', delivery_marker: 'Вагонетка', vehicle: 'Рабочий',
  });
  if (branchId === 'logistics') Object.assign(fallback, {
    visual_pickup: 'Коробки', workstation: 'Склад', delivery_marker: 'Магазин', vehicle: 'Грузовик',
  });
  if (branchId === 'ore_mining') Object.assign(fallback, {
    visual_pickup: 'Железная руда', workstation: 'Карьер', delivery_marker: 'Вагонетка', vehicle: 'Рабочий',
  });
  if (branchId === 'logistics') Object.assign(fallback, {
    visual_pickup: 'Коробки', workstation: 'Склад', delivery_marker: 'Магазин', vehicle: 'Грузовик',
  });
  return { ...fallback, ...(serverScene || {}) };
}

export function buildSceneRegistry(corporations = []) {
  const registry = new Map();
  for (const corporation of corporations || []) {
    const sectorId = corporation?.id;
    if (!SCENE_FAMILIES[sectorId]) continue;
    for (const branch of corporation.branches || []) {
      const scene = sceneForBranch(branch.id, sectorId);
      if (scene) registry.set(branch.id, { ...scene, branch_name: branch.name });
    }
  }
  return registry;
}
