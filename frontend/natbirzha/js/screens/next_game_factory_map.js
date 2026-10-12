import { esc, number, icon } from './next_game_common.js?v=20261011_continuous_progression_v1';

export function centerFactoryMapNode(container, options, node) {
  const viewport = container.querySelector('[data-factory-map-viewport]');
  const world = viewport?.querySelector('[data-factory-map-world]');
  const position = node?.closest('.next-game-factory-map-position');
  if (!viewport || !world || !position) return;
  const scale = Number(options.mapTransform?.scale || 1);
  const nodeX = Number.parseFloat(position.style.left || '0') + 102;
  const nodeY = Number.parseFloat(position.style.top || '0') + 60;
  const width = Number(world.dataset.mapWidth || 436);
  const height = Number(world.dataset.mapHeight || 180);
  const x = viewport.clientWidth / 2 - nodeX * scale;
  const y = viewport.clientHeight / 2 - nodeY * scale;
  options.mapTransform = {
    x: Math.max(Math.min(0, viewport.clientWidth - width * scale), Math.min(0, x)),
    y: Math.max(Math.min(0, viewport.clientHeight - height * scale), Math.min(0, y)),
    scale,
  };
  world.style.transform = `translate(${options.mapTransform.x}px, ${options.mapTransform.y}px) scale(${scale})`;
  container.querySelectorAll('[data-factory-select]').forEach((button) => {
    const selected = button.dataset.factorySelect === options.selectedBranchId;
    button.classList.toggle('is-selected', selected);
    button.setAttribute('aria-pressed', String(selected));
  });
  container.querySelector('[data-factory-zoom-level]')?.replaceChildren(
    document.createTextNode(`${Math.round(scale * 100)}%`),
  );
}

export function renderFactoryMap(route, facilities, consumed, selectedBranchId) {
  const nodeWidth = 204;
  const nodeHeight = 120;
  const columnStep = 218;
  const rowStep = 154;
  const rows = Math.ceil(route.length / 2);
  const width = 436;
  const height = Math.max(180, 28 + (rows - 1) * rowStep + nodeHeight);
  const nodes = route.map(({ sector, branch }, index) => {
    const row = Math.floor(index / 2);
    const column = row % 2 === 0 ? index % 2 : 1 - (index % 2);
    const x = 14 + column * columnStep;
    const y = 14 + row * rowStep;
    const facility = facilities.get(branch.id);
    const isMerged = !facility && consumed.has(branch.id);
    const status = isMerged ? ['merged', 'В комплексе']
      : facility?.status === 'blocked' ? ['blocked', 'Нужны ресурсы']
        : facility ? ['working', 'Работает'] : ['idle', 'Не построен'];
    const recipe = facility?.recipe || branch.factory || {};
    const output = `${number(recipe.output_quantity, 3)} ${recipe.output_unit || ''} ${recipe.output_name || branch.outputs || ''}`;
    const search = `${sector.name} ${branch.name} ${recipe.facility_name || ''} ${recipe.output_name || ''}`.toLocaleLowerCase('ru-RU');
    return {
      branch, index, x, y, status,
      markup: `<button type="button" class="next-game-factory-map-node is-${status[0]} ${branch.id === selectedBranchId ? 'is-selected' : ''}" data-factory-select="${esc(branch.id)}" data-factory-search-text="${esc(search)}" aria-label="Выбрать завод ${esc(recipe.facility_name || branch.name)} · ${esc(status[1])}" aria-pressed="${branch.id === selectedBranchId}">
        <span class="next-game-factory-map-node-top"><span class="next-game-factory-map-number">${icon('factories', 18)}${String(index + 1).padStart(2, '0')}</span><span class="next-game-factory-map-state">${esc(status[1])}</span></span>
        <b>${esc(recipe.facility_name || branch.name)}</b><small>${esc(output)}</small>
      </button>`,
    };
  });
  const links = nodes.slice(0, -1).map((node, index) => {
    const next = nodes[index + 1];
    const x1 = node.x + nodeWidth / 2;
    const y1 = node.y + nodeHeight / 2;
    const x2 = next.x + nodeWidth / 2;
    const y2 = next.y + nodeHeight / 2;
    return `<path d="M ${x1} ${y1} L ${x2} ${y2}" />`;
  }).join('');
  return `<div class="next-game-factory-map-viewport" data-factory-map-viewport role="region" aria-label="Карта заводов: перетаскивайте и масштабируйте">
    <div class="next-game-factory-map-world" data-factory-map-world data-map-width="${width}" data-map-height="${height}" style="width:${width}px;height:${height}px">
      <svg class="next-game-factory-map-links" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" aria-hidden="true">${links}</svg>
      ${nodes.map((node) => `<div class="next-game-factory-map-position" style="left:${node.x}px;top:${node.y}px">${node.markup}</div>`).join('')}
    </div>
  </div>`;
}

export function bindFactoryMap(container, options) {
  const viewport = container.querySelector('[data-factory-map-viewport]');
  const world = viewport?.querySelector('[data-factory-map-world]');
  if (!viewport || !world) return;
  const width = Number(world.dataset.mapWidth || 500);
  const height = Number(world.dataset.mapHeight || 180);
  const minScale = 0.42;
  const maxScale = 1.6;
  if (!options.mapTransform) {
    options.mapTransform = {
      x: 0, y: 0,
      scale: Math.min(1, Math.max(minScale, (viewport.clientWidth - 18) / width)),
    };
  }
  const apply = () => {
    const transform = options.mapTransform;
    transform.scale = Math.min(maxScale, Math.max(minScale, Number(transform.scale) || 1));
    transform.x = Math.max(Math.min(0, viewport.clientWidth - width * transform.scale),
      Math.min(0, Number(transform.x) || 0));
    transform.y = Math.max(Math.min(0, viewport.clientHeight - height * transform.scale),
      Math.min(0, Number(transform.y) || 0));
    world.style.transform = `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`;
    container.querySelector('[data-factory-zoom-level]')?.replaceChildren(
      document.createTextNode(`${Math.round(transform.scale * 100)}%`),
    );
  };
  const zoomAt = (x, y, scale) => {
    const transform = options.mapTransform;
    const nextScale = Math.min(maxScale, Math.max(minScale, scale));
    const mapX = (x - transform.x) / transform.scale;
    const mapY = (y - transform.y) / transform.scale;
    options.mapTransform = { x: x - mapX * nextScale, y: y - mapY * nextScale, scale: nextScale };
    apply();
  };
  apply();
  container.querySelector('[data-factory-zoom-in]')?.addEventListener('click', () => {
    zoomAt(viewport.clientWidth / 2, viewport.clientHeight / 2, options.mapTransform.scale * 1.18);
  });
  container.querySelector('[data-factory-zoom-out]')?.addEventListener('click', () => {
    zoomAt(viewport.clientWidth / 2, viewport.clientHeight / 2, options.mapTransform.scale / 1.18);
  });
  container.querySelector('[data-factory-map-fit]')?.addEventListener('click', () => {
    options.mapTransform = {
      x: 0, y: 0,
      scale: Math.min(1, Math.max(minScale, (viewport.clientWidth - 18) / width)),
    };
    apply();
  });

  const pointers = new Map();
  const capturedPointers = new Set();
  let pan = null;
  let pinch = null;
  let moved = false;
  const localPoint = (event) => {
    const rect = viewport.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  };
  const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
  const midpoint = (a, b) => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 });
  viewport.addEventListener('pointerdown', (event) => {
    if (event.pointerType === 'mouse' && event.button !== 0) return;
    pointers.set(event.pointerId, localPoint(event));
    moved = false;
    if (pointers.size === 1) {
      const point = pointers.get(event.pointerId);
      pan = { id: event.pointerId, point, transform: { ...options.mapTransform } };
      pinch = null;
    } else if (pointers.size === 2) {
      const [first, second] = [...pointers.values()];
      const center = midpoint(first, second);
      pinch = {
        distance: Math.max(1, distance(first, second)), center,
        scale: options.mapTransform.scale,
        mapX: (center.x - options.mapTransform.x) / options.mapTransform.scale,
        mapY: (center.y - options.mapTransform.y) / options.mapTransform.scale,
      };
      pan = null;
    }
  });
  viewport.addEventListener('pointermove', (event) => {
    if (!pointers.has(event.pointerId)) return;
    pointers.set(event.pointerId, localPoint(event));
    if (pointers.size >= 2 && pinch) {
      if (!capturedPointers.has(event.pointerId)) {
        viewport.setPointerCapture(event.pointerId);
        capturedPointers.add(event.pointerId);
      }
      const [first, second] = [...pointers.values()];
      const center = midpoint(first, second);
      const scale = Math.min(maxScale, Math.max(minScale,
        pinch.scale * distance(first, second) / pinch.distance));
      options.mapTransform = {
        x: center.x - pinch.mapX * scale,
        y: center.y - pinch.mapY * scale,
        scale,
      };
      moved = true;
      apply();
    } else if (pointers.size === 1 && pan?.id === event.pointerId) {
      const point = pointers.get(event.pointerId);
      const dx = point.x - pan.point.x;
      const dy = point.y - pan.point.y;
      if (Math.hypot(dx, dy) > 4) {
        moved = true;
        if (!capturedPointers.has(event.pointerId)) {
          viewport.setPointerCapture(event.pointerId);
          capturedPointers.add(event.pointerId);
        }
      }
      if (moved) {
        options.mapTransform = {
          ...pan.transform,
          x: pan.transform.x + dx,
          y: pan.transform.y + dy,
        };
        apply();
      }
    }
  });
  const finishPointer = (event) => {
    if (moved) options.suppressFactoryMapClickUntil = Date.now() + 350;
    pointers.delete(event.pointerId);
    capturedPointers.delete(event.pointerId);
    if (pointers.size === 1) {
      const [id, point] = [...pointers.entries()][0];
      pan = { id, point, transform: { ...options.mapTransform } };
      pinch = null;
    } else {
      pan = null;
      pinch = null;
    }
  };
  viewport.addEventListener('pointerup', finishPointer);
  viewport.addEventListener('pointercancel', finishPointer);
  viewport.addEventListener('wheel', (event) => {
    event.preventDefault();
    const point = localPoint(event);
    zoomAt(point.x, point.y, options.mapTransform.scale * (event.deltaY < 0 ? 1.12 : 1 / 1.12));
  }, { passive: false });
}
