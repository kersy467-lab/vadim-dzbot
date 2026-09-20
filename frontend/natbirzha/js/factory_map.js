/**
 * Pure projection of server factories into the paged territory map.
 *
 * This module deliberately has no DOM or API dependencies.  The server owns
 * factory state; the map only decides where each returned factory is shown.
 */

export const BIOMES = [
  { id: 'grass', title: 'Зелёная равнина', pageClass: 'factory-biome-grass' },
  { id: 'desert', title: 'Пустыня', pageClass: 'factory-biome-desert' },
  { id: 'snow', title: 'Снежные горы', pageClass: 'factory-biome-snow' },
];

export function getFactoryPage(index) {
  return Math.floor(Math.max(0, Number(index) || 0) / 9) + 1;
}

export function getFactorySlot(index) {
  return Math.max(0, Number(index) || 0) % 9;
}

export function getBiomeForPage(page) {
  const normalizedPage = Math.max(1, Number(page) || 1);
  return BIOMES[(normalizedPage - 1) % BIOMES.length];
}

function explicitCoordinate(factory, key) {
  const value = Number(factory?.[key]);
  return Number.isInteger(value) ? value : null;
}

function firstFreeSlot(slots) {
  const index = slots.findIndex((factory) => factory === null);
  return index >= 0 ? index : 0;
}

export function buildFactoryPages(factories = [], maxSlots = 0) {
  const source = Array.isArray(factories) ? factories : [];
  const requestedSlots = Math.max(Number(maxSlots) || 0, source.length);
  const pagesCount = Math.max(1, Math.ceil(requestedSlots / 9));
  const pages = Array.from({ length: pagesCount }, (_, index) => ({
    page: index + 1,
    biome: getBiomeForPage(index + 1),
    slots: Array(9).fill(null),
  }));

  source.forEach((factory, index) => {
    const explicitPage = explicitCoordinate(factory, 'map_page');
    const explicitSlot = explicitCoordinate(factory, 'map_slot');
    const pageNumber = explicitPage && explicitPage > 0 ? explicitPage : getFactoryPage(index);
    while (pages.length < pageNumber) {
      const page = pages.length + 1;
      pages.push({ page, biome: getBiomeForPage(page), slots: Array(9).fill(null) });
    }

    const page = pages[pageNumber - 1];
    let slot = explicitSlot !== null && explicitSlot >= 0 && explicitSlot < 9
      ? explicitSlot
      : getFactorySlot(index);
    if (page.slots[slot] !== null) slot = firstFreeSlot(page.slots);
    page.slots[slot] = factory;
  });

  return pages;
}
