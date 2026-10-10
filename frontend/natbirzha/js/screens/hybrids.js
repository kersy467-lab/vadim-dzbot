import { NatAPI } from '../api.js?v=20261010_active_production_v1';
import { store } from '../state.js?v=20260927_ai_hybrids_v1';

const ALLOWED_SOURCE_STATUSES = new Set([
  'ACTIVE', 'PAUSED_MANUAL', 'PAUSED_SUPPLY', 'PAUSED_MAINTENANCE', 'PAUSED_STORAGE',
]);

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char]));
}
function formatCash(value) {
  const amount = Number(value);
  return Number.isFinite(amount) ? amount.toLocaleString('ru-RU', { maximumFractionDigits: 2 }) : '—';
}

function formatQuantity(value) {
  const amount = Number(value);
  return Number.isFinite(amount) ? amount.toLocaleString('ru-RU', { maximumFractionDigits: 3 }) : '0';
}

function makeOperationKey(companyId, action, payload) {
  const storageKey = `nat-hybrid:${companyId}:${action}:${JSON.stringify(payload)}`;
  try {
    let value = localStorage.getItem(storageKey);
    if (!value) {
      value = globalThis.crypto?.randomUUID?.()
        || `hybrid-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      localStorage.setItem(storageKey, value);
    }
    return { value, clear: () => localStorage.removeItem(storageKey) };
  } catch (_) {
    return {
      value: globalThis.crypto?.randomUUID?.()
        || `hybrid-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      clear: () => {},
    };
  }
}

function sourceOptionHtml(option, requiredStage) {
  const options = option.businesses.map((business) => {
    const allowed = ALLOWED_SOURCE_STATUSES.has(String(business.status).toUpperCase())
      && Number(business.stage) >= Number(requiredStage);
    const upgrading = String(business.status).toUpperCase() === 'UPGRADING';
    const status = upgrading
      ? `улучшается · ур. ${business.stage} → ${business.target_stage || Number(business.stage) + 1}`
      : allowed ? `ур. ${business.stage}` : `${business.status} · ур. ${business.stage}`;
    return `<option value="${Number(business.id)}" ${allowed ? '' : 'disabled'}>${escapeHtml(business.name)} · ${status}</option>`;
  }).join('');
  return `<label class="block min-w-0"><span class="mb-1 block text-[10px] font-bold text-slate-500">${escapeHtml(option.name)}</span>
    <select class="hybrid-source-select w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 px-2 py-2 text-xs" required>
      <option value="">Выберите предприятие</option>${options}
    </select></label>`;
}

function recipeCard(recipe, data) {
  const sourcesAvailable = recipe.source_options.every((source) =>
    source.businesses.some((business) =>
      ALLOWED_SOURCE_STATUSES.has(String(business.status).toUpperCase())
      && Number(business.stage) >= Number(recipe.minimum_source_stage)
    )
  );
  const resourcesAvailable = Object.entries(recipe.resource_requirements || {}).every(
    ([itemId, amount]) => Number(data.inventory?.[itemId] || 0) + 1e-9 >= Number(amount)
  );
  const enoughCash = Number(data.company_cash || 0) + 1e-9 >= Number(recipe.additional_capital_cost || 0);
  const canOpen = sourcesAvailable && resourcesAvailable && enoughCash;
  const sourceNames = recipe.source_names || recipe.source_options.map((source) => source.name);
  const upgradingSources = recipe.source_options.flatMap((source) => source.businesses
    .filter((business) => String(business.status).toUpperCase() === 'UPGRADING')
    .map((business) => `${business.name} (${business.stage} → ${business.target_stage || Number(business.stage) + 1})`));
  const resourceRows = Object.entries(recipe.resource_requirements || {}).map(([itemId, amount]) => {
    const available = Number(data.inventory?.[itemId] || 0);
    const enough = available + 1e-9 >= Number(amount);
    return `<span class="rounded-lg px-2 py-1 ${enough ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300' : 'bg-rose-50 text-rose-600 dark:bg-rose-950/40 dark:text-rose-300'}">${escapeHtml(data.resource_names?.[itemId] || itemId)} ${formatQuantity(amount)} <span class="opacity-70">/ ${formatQuantity(available)}</span></span>`;
  }).join('');
  const sourceHint = !sourcesAvailable && upgradingSources.length
    ? `Дождитесь окончания улучшения: ${upgradingSources.map(escapeHtml).join(', ')}.`
    : !sourcesAvailable
      ? `Для этого гибрида нужны: ${sourceNames.map(escapeHtml).join(' + ')}.`
      : `Пара для объединения: ${sourceNames.map(escapeHtml).join(' + ')}.`;
  return `<article class="hybrid-recipe-card glass-card rounded-2xl p-4 space-y-3" data-recipe-id="${escapeHtml(recipe.id)}">
    <header><h3 class="text-sm font-black">${escapeHtml(recipe.name)}</h3><p class="mt-1 text-[10px] text-slate-500">${escapeHtml(recipe.description)}</p></header>
    <p class="text-[10px] text-slate-500">${sourceHint}</p>
    <div class="grid grid-cols-2 gap-2">${recipe.source_options.map((option) => sourceOptionHtml(option, recipe.minimum_source_stage)).join('')}</div>
    <div class="flex flex-wrap gap-1 text-[9px]">${resourceRows}</div>
    <div class="text-[10px] text-slate-500">Дополнительное вложение: <b>${formatCash(recipe.additional_capital_cost)} cash</b> · возврат при продаже: 40% вложений гибрида.</div>
    <div class="text-[9px] text-slate-500">Ресурсы открытия списываются один раз. Гибрид дальше потребляет сырьё и выпускает товар через обычное производство.</div>
    <button type="button" class="hybrid-open-btn w-full rounded-xl bg-indigo-600 px-3 py-2.5 text-xs font-bold text-white disabled:opacity-40" ${canOpen ? '' : 'disabled'}>
      ${!sourcesAvailable ? upgradingSources.length ? 'Дождитесь завершения улучшения' : 'Не хватает предприятий из пары' : !resourcesAvailable ? 'Не хватает ресурсов для объединения' : !enoughCash ? 'Не хватает cash' : 'Объединить предприятия'}
    </button>
  </article>`;
}

function renderManager(container, showToast, onBack, data) {
  const companyId = Number(store.company?.id || store.company?.company_id || 0);
  container.innerHTML = `<div class="space-y-4 max-w-md mx-auto p-4 pb-24">
    <button type="button" class="hybrid-back text-xs font-bold text-pink-500">← Прокачка</button>
    <header><h2 class="text-xl font-black flex items-center gap-2">${window.NatIcons.icon('handshake', 22)} Объединение предприятий</h2><p class="mt-1 text-xs text-slate-500">Каждый гибрид можно улучшить до 4-го уровня. Общего лимита гибридов на сервере нет; число зависит от свободных слотов вашей компании.</p></header>
    ${data.company_hybrids?.length ? `<section class="space-y-2"><h3 class="text-sm font-black">Ваши активные гибриды</h3>${data.company_hybrids.map((hybrid) => `<article class="glass-card rounded-2xl p-4 space-y-2"><div class="flex items-start justify-between gap-2"><div><h4 class="text-xs font-black">${escapeHtml(hybrid.name)}</h4><p class="text-[10px] text-slate-500">Ур. ${Number(hybrid.stage || 1)}/${Number(hybrid.max_stage || 4)} · источники: ${(hybrid.source_business_names || []).map(escapeHtml).join(' + ')}</p></div><span class="text-[9px] text-emerald-600">${escapeHtml(hybrid.status)}</span></div><button type="button" class="hybrid-sell-btn w-full rounded-xl border border-rose-300 px-3 py-2 text-[10px] font-bold text-rose-600" data-hybrid-id="${Number(hybrid.id)}">Продать гибрид и восстановить предприятия</button></article>`).join('')}</section>` : ''}
    <section class="space-y-2"><h3 class="text-sm font-black">Варианты объединения · ${Number(data.recipes?.length || 0)}</h3>${data.recipes?.length ? data.recipes.map((recipe) => recipeCard(recipe, data)).join('') : '<div class="glass-card rounded-xl p-4 text-xs text-slate-500">Для текущей отрасли гибридный рецепт не настроен.</div>'}</section>
  </div>`;

  container.querySelector('.hybrid-back')?.addEventListener('click', onBack);
  container.querySelectorAll('.hybrid-open-btn').forEach((button) => button.addEventListener('click', async () => {
    const card = button.closest('[data-recipe-id]');
    const sourceIds = [...card.querySelectorAll('.hybrid-source-select')].map((select) => Number(select.value));
    if (sourceIds.length !== 2 || sourceIds.some((id) => !id)) {
      showToast('Выберите оба исходных предприятия.', 'error');
      return;
    }
    const payload = {
      recipe_id: card.dataset.recipeId,
      source_business_a_id: sourceIds[0],
      source_business_b_id: sourceIds[1],
    };
    const operation = makeOperationKey(companyId, 'open', payload);
    button.disabled = true;
    try {
      const result = await NatAPI.openHybrid(payload, operation.value);
      operation.clear();
      store.setCompany(await NatAPI.getMyCompany());
      showToast(`Гибрид создан · вложено ${formatCash(result.additional_capital_invested)} cash`, 'success');
      await renderHybridManager(container, showToast, onBack);
    } catch (error) {
      showToast(error.message || 'Не удалось объединить предприятия.', 'error');
      button.disabled = false;
    }
  }));

  container.querySelectorAll('.hybrid-sell-btn').forEach((button) => button.addEventListener('click', async () => {
    const hybridId = Number(button.dataset.hybridId);
    const payload = { hybrid_id: hybridId };
    const operation = makeOperationKey(companyId, 'sell', payload);
    button.disabled = true;
    try {
      const result = await NatAPI.sellHybrid(hybridId, operation.value);
      operation.clear();
      store.setCompany(await NatAPI.getMyCompany());
      showToast(`Гибрид продан · возвращено ${formatCash(result.refund)} cash`, 'success');
      await renderHybridManager(container, showToast, onBack);
    } catch (error) {
      showToast(error.message || 'Не удалось продать гибрид.', 'error');
      button.disabled = false;
    }
  }));
}

export async function renderHybridManager(container, showToast, onBack) {
  container.innerHTML = '<div class="max-w-md mx-auto p-4 text-xs text-slate-500">Загружаем рецепты гибридов…</div>';
  try {
    const data = await NatAPI.getHybridCatalog();
    renderManager(container, showToast, onBack, data);
  } catch (error) {
    container.innerHTML = `<div class="max-w-md mx-auto p-4 space-y-3"><button type="button" class="hybrid-back text-xs font-bold text-pink-500">← Прокачка</button><div class="glass-card rounded-xl p-4 text-xs text-rose-500">${escapeHtml(error.message || 'Не удалось загрузить гибриды.')}</div></div>`;
    container.querySelector('.hybrid-back')?.addEventListener('click', onBack);
  }
}
