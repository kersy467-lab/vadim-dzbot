export function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));
}

export function number(value, digits = 2) {
  return Number(value || 0).toLocaleString('ru-RU', { maximumFractionDigits: digits });
}

const paths = {
  overview: '<path d="M3 10 12 3l9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z"/>',
  map: '<circle cx="5" cy="5" r="2"/><circle cx="19" cy="5" r="2"/><circle cx="12" cy="19" r="2"/><path d="M7 5h10M5 7v4h7v6m7-10v4h-7"/>',
  factories: '<path d="M3 21V9l6 3V7l6 3V3h5v18zM7 17h1m4 0h1m4 0h1"/>',
  market: '<path d="M3 3v18h18M7 15l4-5 4 2 6-7"/>',
  more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
  bank: '<path d="m3 8 9-5 9 5H3zm2 3v7m7-7v7m7-7v7M3 21h18"/>',
  capital: '<path d="M4 20h16M6 16v-5m6 5V4m6 12V8"/>',
  competition: '<path d="M8 3h8v5a4 4 0 0 1-8 0zM8 5H4v3a4 4 0 0 0 5 4m7-7h4v3a4 4 0 0 1-5 4m-3 0v6m-4 3h8"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9 9a3 3 0 0 1 6 0c0 2-3 2-3 4m0 3h.01"/>',
  contracts: '<path d="M6 3h9l4 4v14H6zM14 3v5h5M9 12h7m-7 4h7"/>',
  admin: '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6zM9 12l2 2 4-5"/>',
};

export function icon(name, size = 22) {
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.factories}</svg>`;
}

export function findBranch(corporations, branchId) {
  for (const sector of corporations || []) {
    const branch = (sector.branches || []).find((item) => item.id === branchId);
    if (branch) return { sector, branch };
  }
  return null;
}

export function pathEntries(state) {
  return (state.company?.branch_path || []).map((id) => findBranch(state.corporations, id)).filter(Boolean);
}

export function bindAction(container, selector, action, refresh, showToast, message) {
  container.querySelectorAll(selector).forEach((button) => button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      await action(button);
      if (message) showToast(message, 'success');
      await refresh();
    } catch (error) {
      showToast(error.message || 'Не удалось выполнить действие', 'error');
      button.disabled = false;
    }
  }));
}
