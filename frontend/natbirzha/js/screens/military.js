import { NatAPI } from '../api.js?v=20260925_deals_v6';
import { store } from '../state.js?v=20260925_deals_v6';
import { getItemInfo } from '../items.js?v=20260925_deals_v6';
import { renderTournamentSection } from './military_tournament.js?v=20260925_deals_v6';

const UNITS = [
  { id: 'infantry', name: 'Пехота', icon: '🪖', role: 'Удерживает захваченную землю', cost: '50 cash' },
  { id: 'border_guards', name: 'Пограничники', icon: '🚧', role: 'Оборона и снижение наземных потерь', cost: '100 cash + снаряжение' },
  { id: 'tanks', name: 'Бронетехника', icon: '🛡️', role: 'Контрит пехоту и пограничников', cost: '1 000 cash + сталь' },
  { id: 'drones', name: 'БПЛА', icon: '🛰️', role: 'Разведка и точность', cost: '500 cash + электроника' },
  { id: 'aircraft', name: 'Авиация', icon: '✈️', role: 'Удар по бронетехнике и земле', cost: '5 000 cash + материалы' },
  { id: 'air_defense', name: 'ПВО', icon: '🎯', role: 'Контрит авиацию и дорогие системы', cost: '1 500 cash + материалы' },
];

const INFRA_NAMES = {
  command_center: ['Командный центр', '🎖️'], barracks: ['Казармы', '🏕️'],
  armor_base: ['Бронебаза', '🛡️'], airbase: ['Авиабаза', '✈️'],
  air_defense: ['Центр ПВО', '🎯'], logistics: ['Военная логистика', '🚛'],
  intelligence: ['Разведцентр', '🛰️'],
};

const COMBAT_LABELS = {
  infantry: 'Пехота', border_guards: 'Пограничники', tanks: 'Бронетехника', drones: 'БПЛА',
  aircraft: 'Авиация', air_defense: 'ПВО', electronic_warfare: 'РЭБ', readiness: 'Боеготовность',
};
const PVC_OPERATION_LABELS = {
  purchase: 'Покупка', spend: 'Списание', grant: 'Начисление', reward: 'Награда', refund: 'Возврат',
  license_purchase: 'Покупка лицензии', tournament_reward: 'Награда турнира', creator_grant: 'Начисление Государства',
};

const combatLabel = (value) => COMBAT_LABELS[value] || 'Военная система';
const pvcOperationLabel = (value) => PVC_OPERATION_LABELS[value] || 'Операция PVC';

const SECTIONS = [
  ['army', 'Армия'],
  ['borders', 'PvE-границы'],
  ['tournament', 'Турнир'],
  ['history', 'История'],
  ['alliance', 'Альянс'],
  ['premium', 'PVC'],
];

const esc = (value) => String(value ?? '').replace(/[&<>'"]/g, ch => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
}[ch]));
const number = (value) => Number(value || 0).toLocaleString('ru-RU');

function timeLeft(value) {
  if (!value) return 'нет таймера';
  const seconds = Math.max(0, Math.floor((new Date(value).getTime() - Date.now()) / 1000));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return seconds <= 0 ? 'завершено' : `${hours} ч ${minutes} мин`;
}

function unavailableReason(reason) {
  return {
    company_level: 'Нужен более высокий уровень компании',
    prerequisite: 'Сначала захватите предыдущую корпорацию',
    force_composition: 'Состав армии не соответствует требованиям этого тира',
    insufficient_force_composition: 'Состав армии не соответствует требованиям этого тира',
    already_conquered: 'Территория уже захвачена',
    cooldown: 'Повторная атака пока на кулдауне',
  }[reason] || 'Цель сейчас недоступна';
}

function armyRequirementText(requirements = {}, missing = {}) {
  const labels = {
    ground_total: 'Наземные войска',
    border_guards: 'Пограничники',
    tanks: 'Бронетехника',
    drones: 'БПЛА',
    aircraft: 'Авиация',
    air_defense: 'ПВО',
  };
  return Object.entries(requirements).map(([unit, required]) => {
    const gap = missing?.[unit];
    return `${labels[unit] || unit}: ${number(required)}${gap ? ` (не хватает ${number(gap.missing)})` : ''}`;
  }).join(' · ');
}

export async function renderMilitary(container, showToast) {
  let activeSection = 'army';
  let army = {};
  let pveTargets = [];
  let tournamentData = { tournament: null, participants: [] };
  let tournamentTargets = [];
  let history = [];
  let tournamentHistory = [];
  let premiumData = null;
  const scouting = new Map();

  async function loadWarData() {
    const [armyRes, pveRes, tournamentRes, historyRes, tournamentHistoryRes] = await Promise.allSettled([
      NatAPI.getMilitaryStatus(),
      NatAPI.getPveTargets(),
      NatAPI.getCurrentTournament(),
      NatAPI.getBattleHistory(),
      NatAPI.getTournamentHistory(),
    ]);
    if (armyRes.status === 'fulfilled') army = armyRes.value || {};
    if (pveRes.status === 'fulfilled') pveTargets = pveRes.value?.targets || [];
    if (tournamentRes.status === 'fulfilled') tournamentData = tournamentRes.value || tournamentData;
    if (historyRes.status === 'fulfilled') history = historyRes.value?.battles || [];
    if (tournamentHistoryRes.status === 'fulfilled') tournamentHistory = tournamentHistoryRes.value?.tournaments || [];
    const tournament = tournamentData?.tournament;
    if (tournament?.id && tournament.status === 'ACTIVE') {
      try {
        tournamentTargets = (await NatAPI.getTournamentTargets(tournament.id))?.targets || [];
      } catch (_) {
        tournamentTargets = [];
      }
    } else {
      tournamentTargets = [];
    }
  }

  async function loadPremiumData() {
    const results = await Promise.allSettled([
      NatAPI.getPremiumWallet(),
      NatAPI.getPremiumLedger(),
      NatAPI.getPremiumLicenseCatalog(),
      NatAPI.getPremiumLicenses(),
      NatAPI.getPremiumUpgradeCatalog(),
      NatAPI.getPremiumUpgrades(),
      NatAPI.getIndustryUpgradeCatalog(),
      NatAPI.getIndustryUpgrade(),
    ]);
    const value = (index, fallback) => results[index].status === 'fulfilled' ? results[index].value : fallback;
    premiumData = {
      wallet: value(0, { balance: 0, currency: 'PVC' }),
      ledger: value(1, { entries: [] }),
      catalog: value(2, { licenses: [] }),
      licenses: value(3, { licenses: [] }),
      upgradeCatalog: value(4, { upgrades: [] }),
      upgrades: value(5, { upgrades: [] }),
      industryCatalog: value(6, { upgrades: [] }),
      industry: value(7, { upgrade: null }),
    };
  }

  function armySection() {
    const phases = army.phase_strengths || {};
    return `
      <div class="space-y-3">
        <div class="grid grid-cols-2 gap-2">
          ${UNITS.map(unit => {
            const readiness = Math.round(Number(army.readiness?.[unit.id] ?? 1) * 100);
            return `<div class="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
              <div class="flex items-start justify-between gap-2"><span class="text-xl">${unit.icon}</span><span class="font-mono font-black">${number(army[unit.id])}</span></div>
              <div class="text-xs font-bold mt-1">${unit.name}</div>
              <div class="text-[9px] text-slate-400 min-h-7">${unit.role}</div>
              <div class="mt-2 h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden"><div class="h-full bg-emerald-500" style="width:${Math.min(100, readiness)}%"></div></div>
              <div class="text-[9px] text-slate-400 mt-1">Готовность ${readiness}% · ур. ${army.levels?.[unit.id] || 1}</div>
            </div>`;
          }).join('')}
        </div>
        <div class="glass-card rounded-2xl p-4 space-y-2">
          <div class="flex justify-between"><span class="text-xs font-bold uppercase text-slate-400">Общая мощь</span><span class="font-mono font-black text-emerald-500">${number(army.army_strength)}</span></div>
          <div class="grid grid-cols-2 gap-2 text-[10px] font-mono">
            <span>Разведка: ${number(phases.recon)}</span><span>Авиация: ${number(phases.air)}</span>
            <span>ПВО: ${number(phases.air_defense)}</span><span>Земля: ${number(phases.ground)}</span>
          </div>
        </div>
        <div class="glass-card rounded-2xl p-4 space-y-2">
          <h3 class="text-xs font-bold uppercase text-slate-400">Снабжение одной операции</h3>
          <p class="text-[9px] text-slate-400">Перед PvE/PvP боем ресурсы списываются со склада. Военная логистика снижает расход.</p>
          <div class="grid grid-cols-3 gap-2 text-[10px]">${Object.entries(army.operation_supply || {}).map(([itemId, qty]) => `<div class="p-2 rounded-lg bg-slate-50 dark:bg-slate-800/50"><span class="block text-slate-400">${esc(getItemInfo(itemId).name)}</span><b>${number(qty)}</b></div>`).join('') || '<div class="col-span-3 text-slate-400">Армия пока не требует снабжения.</div>'}</div>
        </div>
        <div class="glass-card rounded-2xl p-4 space-y-2">
          <h3 class="text-xs font-bold uppercase text-slate-400">Военная инфраструктура</h3>
          <p class="text-[9px] text-slate-400">Объекты открывают тяжёлые войска, ускоряют подготовку и снижают расход снабжения.</p>
          <div class="grid grid-cols-2 gap-2">${Object.entries(INFRA_NAMES).map(([id, meta]) => {
            const level = Number(army.infrastructure?.levels?.[id] || 0);
            const quote = army.infrastructure?.upgrade_quotes?.[id];
            return `<div class="p-2 rounded-xl bg-slate-50 dark:bg-slate-800/50"><div class="text-xs font-bold">${meta[1]} ${meta[0]}</div><div class="text-[9px] text-slate-400">ур. ${level}/10</div><button class="upgrade-infra-btn mt-1 w-full px-2 py-1 rounded-lg bg-indigo-600 text-white text-[9px] font-bold disabled:opacity-50" data-facility="${id}" ${quote ? '' : 'disabled'}>${quote ? `${number(quote.cash)} cash` : 'MAX'}</button></div>`;
          }).join('')}</div>
        </div>
        <div class="glass-card rounded-2xl p-4 space-y-2">
          <h3 class="text-xs font-bold uppercase text-slate-400">Очередь подготовки</h3>
          ${(army.infrastructure?.training_queue || []).length ? army.infrastructure.training_queue.map(row => `<div class="flex justify-between gap-2 text-[10px] p-2 rounded-lg bg-slate-50 dark:bg-slate-800/50"><span>${UNITS.find(unit => unit.id === row.unit_type)?.name || esc(row.unit_type)} × ${number(row.quantity)}</span><b>${timeLeft(row.ready_at)}</b></div>`).join('') : '<div class="text-[10px] text-slate-400">Очередь пуста</div>'}
        </div>
        <div class="glass-card rounded-2xl p-4 space-y-2">
          <h3 class="text-xs font-bold uppercase text-slate-400">Формирование подразделений</h3>
          ${UNITS.map(unit => `<div class="flex items-center justify-between gap-2 p-2 rounded-xl bg-slate-50 dark:bg-slate-800/50">
            <div><div class="text-xs font-bold">${unit.icon} ${unit.name}</div><div class="text-[9px] text-slate-400">${unit.cost}</div></div>
            <button class="recruit-unit-btn px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-bold disabled:opacity-50" data-unit-id="${unit.id}" data-name="${unit.name}">Нанять</button>
          </div>`).join('')}
        </div>
      </div>`;
  }

  function bordersSection() {
    if (!pveTargets.length) return '<div class="glass-card rounded-2xl p-5 text-xs text-slate-400 text-center">PvE-корпорации пока не загружены</div>';
    return `<div class="space-y-3">${pveTargets.map(target => {
      const scout = scouting.get(target.code);
      const strength = scout?.strength_range || target.strength_range || {};
      const disabled = !target.available;
      const cooldownText = target.cooldown_until ? `Повторная атака: ${timeLeft(target.cooldown_until)}` : '';
      const requirementText = armyRequirementText(target.army_requirements, target.missing_army_requirements);
      const hasMissingRequirements = Object.keys(target.missing_army_requirements || {}).length > 0;
      const lossForecast = scout ? Object.entries(scout.expected_losses || {})
        .filter(([, range]) => Number(range.max || 0) > 0)
        .map(([unit, range]) => `${UNITS.find(row => row.id === unit)?.name || unit}: ${range.min}–${range.max}`)
        .join(' · ') : '';
      const riskName = { low: 'низкий', medium: 'средний', high: 'высокий', extreme: 'крайний' }[scout?.risk] || '';
      return `<div class="glass-card rounded-2xl p-4 space-y-3">
        <div class="flex justify-between gap-3"><div><div class="text-sm font-black">${esc(target.name)}</div><div class="text-[10px] text-slate-400">Тир ${target.tier} · фронтир ${Number(target.campaign_rank || 0) + 1} · ${esc(target.industry)}</div></div><span class="text-xs font-mono font-bold text-amber-500">${target.repeatable ? 'награды без земли' : `+${target.territory_reward} земли`}</span></div>
        <div class="grid grid-cols-2 gap-2 text-[10px]"><div class="p-2 rounded-lg bg-slate-50 dark:bg-slate-800/50">Сила: <b>${number(strength.min)}–${number(strength.max)}</b></div><div class="p-2 rounded-lg bg-slate-50 dark:bg-slate-800/50">Компенсация: <b>до ${number(target.cash_reward)} cash</b></div></div>
        ${requirementText ? `<div class="text-[10px] rounded-lg p-2 ${hasMissingRequirements ? 'bg-amber-50 dark:bg-amber-950/30 text-amber-700 dark:text-amber-300' : 'bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300'}"><b>Требования к армии:</b> ${esc(requirementText)}</div>` : ''}
        ${scout ? `<div class="text-[10px] rounded-lg p-2 bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300">Разведка: ${scout.accuracy === 'exact' ? 'точный состав получен' : 'оценка диапазона'} · риск: <b>${riskName}</b> · БПЛА: ${scout.scouting_drones}${lossForecast ? `<div class="mt-1 text-[9px]">Ожидаемые потери: ${lossForecast}</div>` : ''}</div>` : ''}
        ${target.conquered ? `<div class="text-[10px] text-emerald-600 dark:text-emerald-300">✓ Корпорация уже покорена. ${cooldownText}</div>` : ''}
        ${disabled ? `<div class="text-[10px] text-slate-400">${unavailableReason(target.unavailable_reason)} ${target.unavailable_reason === 'cooldown' ? cooldownText : ''}</div>` : `<div class="grid grid-cols-2 gap-2"><button class="scout-pve-btn py-2 rounded-xl bg-slate-200 dark:bg-slate-700 text-xs font-bold disabled:opacity-50" data-code="${esc(target.code)}">Разведать</button><button class="attack-pve-btn py-2 rounded-xl bg-rose-600 text-white text-xs font-bold disabled:opacity-50" data-code="${esc(target.code)}">Атаковать</button></div>`}
      </div>`;
    }).join('')}</div>`;
  }

  function historySection() {
    const battles = history.length ? `<div class="space-y-2">${history.map(battle => {
      const won = battle.winner === 'attacker';
      const losses = Object.values(battle.attacker_losses || {}).reduce((sum, value) => sum + Number(value || 0), 0);
      return `<div class="glass-card rounded-2xl p-4 border-l-4 ${won ? 'border-l-emerald-500' : 'border-l-rose-500'}"><div class="flex justify-between"><div class="text-xs font-black">${battle.mode === 'PVE' ? esc(battle.target_name) : `PvP #${battle.battle_id}`}</div><div class="text-xs font-bold ${won ? 'text-emerald-500' : 'text-rose-500'}">${won ? 'Победа' : 'Поражение'}</div></div><div class="text-[10px] text-slate-400 mt-1">Потери: ${losses} · рейтинг ${battle.rating_delta ?? battle.attacker_rating_delta ?? 0} · ${battle.resolved_at ? new Date(battle.resolved_at).toLocaleString('ru-RU') : ''}</div></div>`;
    }).join('')}</div>` : '<div class="text-xs text-slate-400 text-center py-2">История боёв пуста</div>';
    const tournaments = tournamentHistory.length ? tournamentHistory.map(tournament => {
      const mine = tournament.my_participation;
      return `<div class="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50"><div class="flex justify-between"><span class="text-xs font-black">Турнир #${tournament.tournament_number}</span><span class="text-[10px] text-slate-400">${tournament.resolved_at ? new Date(tournament.resolved_at).toLocaleDateString('ru-RU') : ''}</span></div>${mine ? `<div class="text-[10px] mt-1">Ваше место: <b>#${mine.rank}</b> · сила ${number(mine.strength)} · рейтинг ${mine.rating} · <span class="text-amber-500">+${mine.prize_pvc} PVC</span></div>` : '<div class="text-[10px] text-slate-400 mt-1">Вы не участвовали</div>'}</div>`;
    }).join('') : '<div class="text-xs text-slate-400 text-center py-2">Завершённых турниров пока нет</div>';
    return `<div class="space-y-3"><div class="glass-card rounded-2xl p-4 space-y-2"><h3 class="text-xs font-bold uppercase text-slate-400">История боёв</h3>${battles}</div><div class="glass-card rounded-2xl p-4 space-y-2"><h3 class="text-xs font-bold uppercase text-slate-400">Завершённые турниры</h3>${tournaments}</div></div>`;
  }

  function allianceSection() {
    return `<div class="glass-card rounded-2xl p-4 space-y-3"><div class="flex gap-3"><span class="text-2xl">🤝</span><div><h3 class="text-sm font-black">Военный альянс</h3><p class="text-[10px] text-slate-400">До трёх корпораций. Альянс помогает координации, но не меняет серверный результат боя.</p></div></div><button id="join-alliance-btn" class="w-full py-2 rounded-xl bg-indigo-600 text-white text-xs font-bold disabled:opacity-50">Вступить по ID</button></div>`;
  }

  function premiumSection() {
    if (!premiumData) return '<div class="glass-card rounded-2xl p-5 text-xs text-slate-400 text-center">Загрузка Pivocoins...</div>';
    const ownedLicenses = new Map((premiumData.licenses.licenses || []).map(license => [license.code, license]));
    const ownedUpgrades = new Map((premiumData.upgrades.upgrades || []).map(upgrade => [upgrade.code, upgrade]));
    const licenses = (premiumData.catalog.licenses || []).map(spec => {
      const active = ownedLicenses.get(spec.code);
      const expiry = active?.expires_at ? new Date(active.expires_at).toLocaleString('ru-RU') : null;
      const isActive = active?.status === 'ACTIVE' && Date.parse(active.expires_at) > Date.now();
      return `<div class="rounded-xl bg-slate-50 dark:bg-slate-800/50 p-3 space-y-2"><div class="flex justify-between gap-2"><div><div class="text-xs font-bold">${esc(spec.title)}</div><div class="text-[10px] text-slate-400">${esc(spec.description)}</div></div><span class="text-xs font-black text-amber-500 whitespace-nowrap">${spec.price_pvc} PVC</span></div><div class="flex items-center justify-between gap-2"><span class="text-[9px] ${isActive ? 'text-emerald-500' : 'text-slate-500'}">${isActive ? `Активна до ${expiry}` : `${spec.duration_hours} часов`}</span><button class="premium-license-btn px-3 py-1.5 rounded-lg bg-amber-500 text-slate-950 text-[10px] font-black disabled:opacity-50" data-code="${esc(spec.code)}">${isActive ? 'Продлить' : 'Купить'}</button></div></div>`;
    }).join('') || '<div class="text-xs text-slate-400">Лицензии пока не настроены.</div>';
    const upgrades = (premiumData.upgradeCatalog.upgrades || []).map(spec => {
      const own = ownedUpgrades.get(spec.code);
      const cost = Object.entries(spec.resource_cost || {}).map(([item, qty]) => `${getItemInfo(item).name}: ${qty}`).join(' · ');
      const counters = (spec.countered_by || []).map(combatLabel).join(', ');
      const capped = Number(own?.level || 0) >= Number(spec.max_level || 0);
      return `<div class="rounded-xl bg-slate-50 dark:bg-slate-800/50 p-3 space-y-1"><div class="flex justify-between gap-2"><div class="text-xs font-bold">${esc(spec.title)}</div><span class="text-[10px] text-indigo-400">ур. ${own?.level || 0}/${spec.max_level}</span></div><div class="text-[10px] text-slate-400">${esc(spec.description)}</div><div class="text-[9px] text-slate-500">Ресурсы: ${esc(cost)} · контрится: ${esc(counters)}</div><button class="premium-upgrade-btn w-full py-1.5 rounded-lg bg-indigo-600 text-white text-[10px] font-bold disabled:opacity-50" data-code="${esc(spec.code)}" ${capped ? 'disabled' : ''}>${capped ? 'Максимальный уровень' : 'Улучшить за ресурсы'}</button></div>`;
    }).join('') || '<div class="text-xs text-slate-400">Улучшения пока не настроены.</div>';
    const entries = (premiumData.ledger.entries || []).slice(0, 6).map(entry => `<div class="flex justify-between gap-2 text-[10px] py-1 border-b border-slate-800"><span class="text-slate-400">${esc(pvcOperationLabel(entry.operation_type))}</span><span class="font-mono ${entry.amount > 0 ? 'text-emerald-500' : 'text-rose-400'}">${entry.amount > 0 ? '+' : ''}${entry.amount} PVC</span></div>`).join('') || '<div class="text-[10px] text-slate-500">Операций PVC пока нет.</div>';
    return `<div class="space-y-3"><div class="glass-card rounded-2xl p-4 border border-amber-500/30 bg-amber-950/20"><div class="text-[10px] uppercase font-bold text-amber-400">Pivocoins · отдельная premium-валюта</div><div class="text-2xl font-black text-white mt-1">${number(premiumData.wallet.balance)} <span class="text-sm text-amber-400">PVC</span></div><p class="text-[10px] text-slate-400 mt-2">PVC не заменяют cash: контракты открывают редкое производство, а военные улучшения дают ситуативные преимущества.</p></div><div class="glass-card rounded-2xl p-4 space-y-2"><h3 class="text-xs font-bold uppercase text-slate-400">Лицензии и производственные контракты</h3>${licenses}</div><div class="glass-card rounded-2xl p-4 space-y-2"><h3 class="text-xs font-bold uppercase text-slate-400">Эксклюзивная военная ветка</h3>${upgrades}</div><div class="glass-card rounded-2xl p-4 space-y-1"><h3 class="text-xs font-bold uppercase text-slate-400">Последние операции PVC</h3>${entries}</div></div>`;
  }

  function renderView() {
    const section = { army: armySection, borders: bordersSection, tournament: () => renderTournamentSection({ tournamentData, tournamentTargets, army }), history: historySection, alliance: allianceSection, premium: premiumSection }[activeSection] || armySection;
    container.innerHTML = `<div class="space-y-4 max-w-md mx-auto p-4 pb-24"><div><h2 class="text-xl font-black">Война</h2><p class="text-xs text-slate-500">Армия, корпоративные границы и турнирное PvP</p></div><div class="flex gap-2 overflow-x-auto no-scrollbar pb-1">${SECTIONS.map(([id, title]) => `<button class="war-section-btn px-3 py-2 rounded-xl whitespace-nowrap text-xs font-bold ${id === activeSection ? 'bg-blue-600 text-white' : 'bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700'}" data-section="${id}">${title}</button>`).join('')}</div>${section()}</div>`;
    if (activeSection === 'premium' && premiumData?.industry?.upgrade?.available) {
      const industry = premiumData.industry.upgrade;
      const premiumBody = container.querySelector('.space-y-4.max-w-md')?.lastElementChild;
      const panel = document.createElement('div');
      panel.className = 'glass-card rounded-2xl p-4 space-y-2 border border-indigo-400/30';
      const heading = document.createElement('div');
      heading.className = 'text-xs font-bold';
      heading.textContent = industry.title + ' · ур. ' + industry.level + '/' + industry.max_level;
      const description = document.createElement('div');
      description.className = 'text-[10px] text-slate-500';
      description.textContent = industry.description
        + ' Текущий бонус: +' + industry.bonus_pct + '%.'
        + ' Максимум: +' + industry.max_bonus_pct + '%.'
        + ' ' + industry.price_schedule;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'premium-industry-upgrade-btn w-full py-2 rounded-lg bg-indigo-600 text-white text-[10px] font-bold disabled:opacity-50';
      button.textContent = industry.level >= industry.max_level
        ? 'Максимальный уровень'
        : 'Улучшить до +' + industry.next_bonus_pct + '% за ' + industry.next_level_cost + ' PVC';
      button.disabled = industry.level >= industry.max_level || Number(premiumData.wallet.balance || 0) < Number(industry.next_level_cost || 0);
      panel.append(heading, description, button);
      if (premiumBody?.firstElementChild) premiumBody.firstElementChild.after(panel);
      else premiumBody?.prepend(panel);
    }
    bindHandlers();
  }

  async function refreshAfterBattle(result) {
    showToast(result.winner === 'attacker' ? 'Победа! Результат записан в историю.' : 'Бой проигран. Армия и рейтинг обновлены.', result.winner === 'attacker' ? 'success' : 'error');
    const company = await NatAPI.getMyCompany().catch(() => null);
    if (company) store.setCompany(company);
    await loadWarData();
    renderView();
  }

  function bindHandlers() {
    const tabsRow = container.querySelector('.flex.gap-2.overflow-x-auto');
    if (tabsRow) {
      tabsRow.addEventListener('wheel', (e) => {
        if (e.deltaY !== 0) {
          e.preventDefault();
          tabsRow.scrollLeft += e.deltaY;
        }
      }, { passive: false });
    }

    container.querySelectorAll('.war-section-btn').forEach(btn => btn.addEventListener('click', async () => {
      activeSection = btn.dataset.section;
      if (activeSection === 'premium' && !premiumData) await loadPremiumData();
      renderView();
    }));

    container.querySelectorAll('.recruit-unit-btn').forEach(btn => btn.addEventListener('click', async () => {
      const count = parseInt(prompt(`Сколько единиц «${btn.dataset.name}» нанять?`, '1'), 10);
      if (!count || count <= 0) return;
      btn.disabled = true;
      try {
        const training = await NatAPI.recruitUnits(btn.dataset.unitId, count);
        army = await NatAPI.getMilitaryStatus();
        const company = await NatAPI.getMyCompany();
        store.setCompany(company);
        showToast(`Подготовка начата · ${training.duration_minutes || 1} мин`, 'success');
        renderView();
      } catch (error) { showToast(error.message, 'error'); } finally { btn.disabled = false; }
    }));
    container.querySelectorAll('.upgrade-infra-btn').forEach(btn => btn.addEventListener('click', async () => {
      btn.disabled = true;
      try {
        await NatAPI.upgradeMilitaryInfrastructure(btn.dataset.facility);
        army = await NatAPI.getMilitaryStatus();
        const company = await NatAPI.getMyCompany().catch(() => null);
        if (company) store.setCompany(company);
        showToast('Военный объект улучшен', 'success');
        renderView();
      } catch (error) { showToast(error.message, 'error'); btn.disabled = false; }
    }));
    container.querySelectorAll('.scout-pve-btn').forEach(btn => btn.addEventListener('click', async () => {
      btn.disabled = true;
      try { scouting.set(btn.dataset.code, await NatAPI.scoutPveTarget(btn.dataset.code)); renderView(); }
      catch (error) { showToast(error.message, 'error'); btn.disabled = false; }
    }));
    container.querySelectorAll('.attack-pve-btn').forEach(btn => btn.addEventListener('click', async () => {
      btn.disabled = true;
      try { await refreshAfterBattle(await NatAPI.attackPveTarget(btn.dataset.code)); }
      catch (error) { showToast(error.message, 'error'); btn.disabled = false; }
    }));
    container.querySelectorAll('.attack-pvp-btn').forEach(btn => btn.addEventListener('click', async () => {
      btn.disabled = true;
      try { await refreshAfterBattle(await NatAPI.attackTournamentTarget(tournamentData.tournament.id, btn.dataset.companyId)); }
      catch (error) { showToast(error.message, 'error'); btn.disabled = false; }
    }));
    container.querySelector('.tournament-join-btn')?.addEventListener('click', async event => {
      const button = event.currentTarget;
      button.disabled = true;
      try {
        const result = await NatAPI.joinTournament(tournamentData.tournament.id);
        showToast(result.message || 'Вы зарегистрировались в турнире', 'success');
        await loadWarData();
        renderView();
      } catch (error) { showToast(error.message, 'error'); button.disabled = false; }
    });
    container.querySelector('#join-alliance-btn')?.addEventListener('click', async event => {
      const id = parseInt(prompt('ID альянса:', '1'), 10);
      if (!id || id <= 0) return;
      event.currentTarget.disabled = true;
      try { const response = await NatAPI.joinAlliance(id); showToast(response.message || 'Вы вступили в альянс', 'success'); }
      catch (error) { showToast(error.message, 'error'); event.currentTarget.disabled = false; }
    });
    container.querySelectorAll('.premium-license-btn').forEach(btn => btn.addEventListener('click', async () => {
      btn.disabled = true;
      try {
        await NatAPI.purchasePremiumLicense(btn.dataset.code);
        await loadPremiumData();
        const company = await NatAPI.getMyCompany();
        store.setCompany(company);
        showToast('Лицензия PVC оформлена на 48 часов.', 'success');
        renderView();
      } catch (error) { showToast(error.message, 'error'); btn.disabled = false; }
    }));
    container.querySelectorAll('.premium-upgrade-btn').forEach(btn => btn.addEventListener('click', async () => {
      btn.disabled = true;
      try {
        await NatAPI.purchasePremiumUpgrade(btn.dataset.code);
        await loadPremiumData();
        showToast('Эксклюзивное улучшение применено.', 'success');
        renderView();
      } catch (error) { showToast(error.message, 'error'); btn.disabled = false; }
    }));
    container.querySelectorAll('.premium-industry-upgrade-btn').forEach(btn => btn.addEventListener('click', async () => {
      btn.disabled = true;
      try {
        const result = await NatAPI.purchaseIndustryUpgrade();
        await loadPremiumData();
        const company = await NatAPI.getMyCompany();
        store.setCompany(company);
        showToast('Отраслевой бонус повышен до ' + result.bonus_pct + '%.', 'success');
        renderView();
      } catch (error) { showToast(error.message, 'error'); btn.disabled = false; }
    }));
  }

  await loadWarData();
  renderView();
}
