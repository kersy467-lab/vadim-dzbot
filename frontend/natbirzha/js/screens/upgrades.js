import { NatAPI } from '../api.js';
import { store } from '../state.js';
import { getBuildingName, getSpecializationName } from '../localization.js';

const LABELS = {
  workers: '👷 Работники',
  automation: '🤖 Автоматизация',
  technology: '🧠 Технологии',
  level: '⬆️ Уровень завода',
};

export async function renderUpgrades(container, showToast) {
  try {
    const summary = await NatAPI.getEmpireSummary();
    const businesses = Array.isArray(summary?.businesses) ? summary.businesses : [];
    if (businesses.length) {
      const availableBusinesses = businesses.filter((business) =>
        business.next_upgrade && !business.contract_expired && business.status !== 'UPGRADING'
      );
      const wrapper = document.createElement('div');
      wrapper.className = 'space-y-4 max-w-md mx-auto p-4 pb-24';
      wrapper.innerHTML = `<div><h2 class="text-xl font-black">Прокачка предприятий</h2><p class="text-xs text-slate-500">Улучшения карьерных предприятий компании</p></div>${availableBusinesses.length ? `<div class="glass-card rounded-2xl p-3 space-y-2"><button id="upgrade-all-businesses" type="button" class="w-full rounded-xl bg-indigo-600 text-white py-2.5 text-xs font-bold">Прокачать всё (${availableBusinesses.length})</button><p class="text-[10px] text-slate-500">Если общей суммы не хватит, ни одно улучшение не запустится.</p></div>` : ''}`;
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
      return;
    }
  } catch (error) {
    console.warn('Could not refresh V2 businesses for upgrades:', error);
  }

  let factories = store.factories || [];
  try {
    const data = await NatAPI.getProductionStatus();
    if (Array.isArray(data?.factories)) {
      factories = data.factories;
      store.updateCompany({ factories });
    }
  } catch (error) {
    console.warn('Could not refresh factories for upgrades:', error);
  }

  const mastery = store.company?.mastery;
  container.innerHTML = `<div class="space-y-4 max-w-md mx-auto p-4 pb-24">
    <div>
      <h2 class="text-xl font-black">Прокачка производств</h2>
      <p class="text-xs text-slate-500">Цена, требования и эффект приходят только с сервера</p>
    </div>
    ${mastery && Number(store.company?.level || 0) >= 60 ? masteryPanel(mastery) : ''}
    <div class="space-y-3">
      ${factories.map(factoryCard).join('') || `<div class="glass-card rounded-2xl p-6 text-center text-sm text-slate-500 space-y-3"><p>Сначала постройте предприятие в каталоге.</p><button class="upgrade-help-btn rounded-xl bg-blue-600 px-3 py-2 text-xs font-bold text-white">Как начать прокачку</button></div>`}
    </div>
  </div>`;

  container.querySelectorAll('.mastery-btn').forEach(btn => btn.addEventListener('click', async () => {
    if (btn.disabled) return;
    btn.disabled = true;
    try {
      await NatAPI.unlockMastery(btn.dataset.branch);
      const refreshed = await NatAPI.getMyCompany();
      store.setCompany(refreshed);
      showToast('Узел мастерства открыт', 'success');
      await renderUpgrades(container, showToast);
    } catch (error) {
      showToast(error.message, 'error');
      btn.disabled = false;
    }
  }));

  container.querySelectorAll('.upgrade-btn').forEach(btn => btn.addEventListener('click', async () => {
    if (btn.disabled) return;
    btn.disabled = true;
    try {
      const result = await NatAPI.upgradeFactory(Number(btn.dataset.factoryId), btn.dataset.type);
      showToast(`Улучшение применено. Списано ${Math.round(result.cost_paid).toLocaleString('ru-RU')} cash`, 'success');
      const refreshed = await NatAPI.getMyCompany();
      store.setCompany(refreshed);
      await renderUpgrades(container, showToast);
    } catch (error) {
      showToast(error.message, 'error');
      btn.disabled = false;
    }
  }));

  container.querySelectorAll('.upgrade-help-btn').forEach(btn => btn.addEventListener('click', () => {
    window.NatApp?.navigateTo('help');
  }));
}

function factoryCard(factory) {
  const upgrades = Array.isArray(factory.upgrade_options) ? factory.upgrade_options : [];
  const bType = factory.building_type || factory.factory_type;
  const bName = (factory.name && factory.name !== bType) ? factory.name : getBuildingName(bType);
  const specName = getSpecializationName(factory.specialization);
  return `<div class="glass-card rounded-2xl p-4 space-y-3" data-factory-id="${factory.id}">
    <div class="flex justify-between items-center">
      <div>
        <div class="text-sm font-black text-slate-900 dark:text-white">${bName}</div>
        <div class="text-[10px] text-slate-500">Ур. ${factory.level || 1} · ${specName}</div>
      </div>
      <span class="text-lg">⚙️</span>
    </div>
    <div class="grid grid-cols-2 gap-2">
      ${upgrades.map(u => upgradeCard(factory.id, u)).join('') || '<div class="col-span-2 text-xs text-slate-500">Сервер не вернул варианты прокачки.</div>'}
    </div>
  </div>`;
}

function upgradeCard(factoryId, u) {
  const title = LABELS[u.type] || u.type;
  const current = Number(u.current ?? u.current_level ?? 0);
  const next = Number(u.next ?? u.next_level ?? current);
  const cost = Number(u.cost || 0);
  const maxLevel = Number(u.max_level || 0);
  const automationNote = u.type === 'automation'
    ? `<div class="text-[9px] text-blue-600 dark:text-blue-300 mt-1">Автозапуск и автосбор без автопокупки сырья · ветка ${Number(u.current_level || 0)}/${maxLevel || 10}</div>`
    : '';
  const button = u.allowed
    ? `<button class="upgrade-btn w-full rounded-xl bg-blue-600 hover:bg-blue-500 text-white py-2 text-[11px] font-bold" data-factory-id="${factoryId}" data-type="${u.type}">Купить: ${cost.toLocaleString('ru-RU')} cash</button>`
    : `<div class="space-y-1"><button disabled class="upgrade-locked-btn w-full rounded-xl py-2 text-[10px] font-bold cursor-not-allowed">🔒 ${u.reason || 'Условие пока не выполнено'}</button><button class="upgrade-help-btn w-full text-[10px] font-bold text-blue-600 dark:text-blue-300">Как выполнить условие?</button></div>`;

  return `<div class="rounded-xl border border-slate-200/80 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 p-2.5 flex flex-col justify-between">
    <div>
      <div class="text-[11px] font-bold text-slate-800 dark:text-slate-100">${title}</div>
      <div class="text-[9px] text-emerald-600 dark:text-emerald-400 mt-0.5">${u.effect || ''}</div>
      ${automationNote}
      <div class="font-mono text-[10px] text-slate-500 my-1.5">${current} ➔ <span class="font-bold text-slate-800 dark:text-white">${next}</span>${maxLevel ? ` · max ${maxLevel}` : ''}</div>
    </div>
    ${button}
  </div>`;
}

function masteryPanel(mastery) {
  const branches = Object.values(mastery.branches || {});
  const available = Number(mastery.points_available || 0);
  return `<div class="mastery-progress glass-card rounded-2xl p-4 space-y-3">
    <div class="flex items-center justify-between gap-3"><div><div class="text-sm font-black">✨ Мастерство корпорации</div><div class="text-[10px] opacity-70">Ранг ${Number(mastery.rank || 0)} · эффект каждой ветки имеет предел и убывающую отдачу</div></div><div class="rounded-xl bg-white/70 dark:bg-black/20 px-2 py-1 text-xs font-black">${available} очк.</div></div>
    <div class="grid grid-cols-1 gap-2">${branches.map(branch => {
      const cost = Number(branch.next_cost || 1);
      const disabled = available < cost;
      return `<div class="rounded-xl border border-violet-200/70 dark:border-violet-800/60 p-3">
        <div class="flex justify-between gap-2"><div><div class="text-xs font-black">${branch.name}</div><div class="mt-0.5 text-[10px] opacity-70">${branch.description}</div></div><div class="text-right text-[10px] font-mono">ур. ${Number(branch.level || 0)}<br><b>${Number(branch.effect_pct || 0)}%</b> / ${Number(branch.cap_pct || 0)}%</div></div>
        <button class="mastery-btn mt-2 w-full rounded-xl px-3 py-2 text-[10px] font-bold ${disabled ? 'bg-slate-200 dark:bg-slate-800 opacity-60' : 'bg-violet-600 text-white'}" data-branch="${branch.code}" ${disabled ? 'disabled' : ''}>Открыть за ${cost} очк.</button>
      </div>`;
    }).join('')}</div>
  </div>`;
}
