import { NatAPI } from '../api.js?v=20261009_perf_tuning_v1';
import { store } from '../state.js?v=20260926_local_update_v1';
import { getSpecializationName } from '../localization.js?v=20261009_luxury_ui_v2';
import { registerScreenCleanup } from '../screen_lifecycle.js?v=20260928_mobile_perf_v1';
import { renderHybridManager } from './hybrids.js?v=20261009_luxury_ui_v2';

let upgradesRenderGeneration = 0;
let unregisterUpgradesCleanup = null;

export async function renderUpgrades(container, showToast) {
  const generation = ++upgradesRenderGeneration;
  unregisterUpgradesCleanup?.();
  unregisterUpgradesCleanup = registerScreenCleanup(() => {
    if (generation === upgradesRenderGeneration) upgradesRenderGeneration += 1;
    unregisterUpgradesCleanup = null;
  });
  renderUpgradeLoading(container);
  void refreshUpgradeScreen(container, showToast, generation);
}

async function refreshUpgradeScreen(container, showToast, generation) {
  const isCurrent = () => generation === upgradesRenderGeneration && container.isConnected;
  try {
    const summary = await NatAPI.getBusinessUpgradeSummary();
    if (!isCurrent()) return;
    const businesses = Array.isArray(summary?.businesses) ? summary.businesses : [];
    renderBusinessUpgrades(container, showToast, businesses);
  } catch (error) {
    if (error?.name === 'AbortError' || !isCurrent()) return;
    console.warn('Could not refresh V2 businesses for upgrades:', error);
    renderUpgradeError(container, () => renderUpgrades(container, showToast));
  }
}

function renderUpgradeLoading(container) {
  container.innerHTML = `<div class="space-y-4 max-w-md mx-auto p-4 pb-24">
    <header><h2 class="text-xl font-black">Прокачка</h2><p class="text-xs text-slate-500">Проверяем доступные улучшения…</p></header>
    <div class="glass-card rounded-2xl p-6 text-center text-sm text-slate-500">Загружаем улучшения предприятий…</div>
  </div>`;
}

function renderUpgradeError(container, retry) {
  container.innerHTML = `<div class="space-y-4 max-w-md mx-auto p-4 pb-24">
    <header><h2 class="text-xl font-black">Прокачка предприятий</h2></header>
    <div class="glass-card rounded-2xl p-5 text-center space-y-3">
      <p class="text-sm text-rose-400">Не удалось загрузить улучшения. Проверьте соединение и попробуйте ещё раз.</p>
      <button id="retry-upgrades" type="button" class="rounded-xl bg-indigo-600 px-4 py-2 text-xs font-bold text-white">Повторить</button>
    </div>
  </div>`;
  container.querySelector('#retry-upgrades')?.addEventListener('click', retry);
}

function renderBusinessUpgrades(container, showToast, businesses) {
  const availableBusinesses = businesses.filter((business) =>
    business.next_upgrade && !business.contract_expired && business.status !== 'UPGRADING'
  );
  const wrapper = document.createElement('div');
  wrapper.className = 'space-y-4 max-w-md mx-auto p-4 pb-24';
  wrapper.innerHTML = `<div class="space-y-3"><header><h2 class="text-xl font-black">Прокачка предприятий</h2><p class="text-xs text-slate-500">Улучшения карьерных предприятий компании</p></header><button id="hybrid-manager-open" type="button" class="w-full rounded-2xl border border-indigo-300/60 bg-indigo-50/60 dark:bg-indigo-950/20 p-3 text-left"><span class="block text-xs font-black">${window.NatIcons.icon('handshake', 16)} Объединение предприятий</span><span class="mt-1 block text-[10px] text-slate-500">Каждый гибрид улучшается до 4-го уровня · лимита на сервер нет</span></button></div>${availableBusinesses.length ? `<div class="glass-card rounded-2xl p-3 space-y-2"><button id="upgrade-all-businesses" type="button" class="w-full rounded-xl bg-indigo-600 text-white py-2.5 text-xs font-bold">Прокачать всё</button><p class="text-[10px] text-slate-500">Если общей суммы не хватит, ни одно улучшение не запустится.</p></div>` : ''}`;
  wrapper.querySelector('#hybrid-manager-open')?.addEventListener('click', () => {
    renderHybridManager(container, showToast, () => renderUpgrades(container, showToast));
  });
  const upgradeAllButton = wrapper.querySelector('#upgrade-all-businesses');
  upgradeAllButton?.addEventListener('click', async () => {
    upgradeAllButton.disabled = true;
    try {
      const result = await NatAPI.upgradeAllBusinesses();
      store.setCompany(await NatAPI.getMyCompany());
      if (result.started_count) {
        showToast(
          `На прокачку поставлено ${result.started_count} предприятий · списано ${Number(result.total_cost).toLocaleString('ru-RU')} cash`,
          'success',
        );
      } else {
        showToast('Нет предприятий, доступных для прокачки.', 'info');
      }
      await renderUpgrades(container, showToast);
    } catch (error) {
      showToast(error.message, 'error');
      upgradeAllButton.disabled = false;
    }
  });

  const list = document.createElement('div');
  list.className = 'space-y-3';
  if (!businesses.length) {
    list.innerHTML = '<div class="glass-card rounded-2xl p-6 text-center text-sm text-slate-500">Пока нет предприятий для улучшения. Откройте предприятие в каталоге.</div>';
  }
  for (const business of businesses) {
    const card = document.createElement('div');
    card.className = 'glass-card rounded-2xl p-4 space-y-2';
    const title = document.createElement('div');
    title.className = 'text-sm font-black';
    title.textContent = business.catalog_name || business.name || 'Предприятие';
    const level = document.createElement('div');
    level.className = 'text-[10px] text-slate-500';
    level.textContent = getSpecializationName(business.specialization) + ' · уровень ' + business.stage + '/' + business.max_stage;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'w-full rounded-xl bg-blue-600 text-white py-2 text-xs font-bold disabled:opacity-50';
    const next = business.next_upgrade;
    const upgrading = business.status === 'UPGRADING';
    button.textContent = upgrading
      ? 'Улучшение выполняется'
      : business.contract_expired
        ? 'Контракт PVC истёк'
        : next
          ? 'Улучшить до ' + next.target_stage + ' · ' + Number(next.cost).toLocaleString('ru-RU') + ' cash'
          : 'Максимальный уровень';
    button.disabled = upgrading || Boolean(business.contract_expired) || !next;
    button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        await NatAPI.upgradeBusiness(business.id);
        store.setCompany(await NatAPI.getMyCompany());
        showToast('Улучшение предприятия запущено', 'success');
        await renderUpgrades(container, showToast);
      } catch (error) {
        showToast(error.message, 'error');
        button.disabled = false;
      }
    });
    card.append(title, level, button);
    list.append(card);
  }
  wrapper.append(list);
  container.replaceChildren(wrapper);
}
