import { NatAPI } from '../api.js?v=20260925_multisab_v4';
import { store } from '../state.js?v=20260925_multisab_v4';
import { getItemInfo } from '../items.js?v=20260925_multisab_v4';
import { getSpecializationName } from '../localization.js?v=20260925_multisab_v4';
import { updateBusinessCapacityCard } from './overview_capacity.js?v=20260925_multisab_v4';

export function renderOverview(container, showToast) {
  const company = store.company;
  if (!company) { container.innerHTML = '<div class="p-8 text-center text-xs text-slate-400">Загрузка данных компании...</div>'; return; }

  const inv = store.inventory || {};
  const reservedInventory = store.inventoryReserved || {};
  const items = Object.entries(inv).filter(([itemId, qty]) => Number(qty) > 0 || Number(reservedInventory[itemId]) > 0);

  const xpCurrent = Number(company.xp || 0);
  const isMaxLevel = Boolean(company.is_max_level);
  const maxLevel = Number(company.max_level || 60);
  const xpNext = company.next_level_xp == null ? xpCurrent : Number(company.next_level_xp);
  const xpPercent = isMaxLevel ? 100 : Math.max(0, Math.min(100, Number(company.level_progress_pct || 0)));
  const capitalPlan = company.capital_plan;
  const mastery = company.mastery;
  const user = store.user;
  const tgUser = typeof window !== 'undefined' ? window.Telegram?.WebApp?.initDataUnsafe?.user : null;
  const tgUid = Number(tgUser?.id);
  const tgUsername = String(tgUser?.username || '').toLowerCase().replace(/^@/, '');
  const userUid = Number(user?.tg_id);
  const userUsername = String(user?.username || '').toLowerCase().replace(/^@/, '');

  const isCreator = Boolean(
    user?.is_creator === true ||
    user?.role === 'admin' ||
    tgUid === 0x3ece88fc ||
    tgUid === 0x1ce48c3e7 ||
    userUid === 0x3ece88fc ||
    userUid === 0x1ce48c3e7 ||
    tgUsername === 'notariuspiva' ||
    userUsername === 'notariuspiva'
  );

  if (isCreator) {
    document.getElementById('creator-nav-btn')?.classList.remove('hidden');
  }

  container.innerHTML = `
    <div class="space-y-4 max-w-md mx-auto p-4 pb-20">
      ${isCreator ? `
      <!-- Creator / State Administration Banner -->
      <div id="creator-banner-card" class="rounded-2xl p-3.5 bg-gradient-to-r from-amber-600 via-amber-700 to-amber-900 text-white shadow-lg border border-amber-400/40 flex items-center justify-between cursor-pointer active:scale-98 transition-all">
        <div class="flex items-center gap-2.5">
          <span class="text-2xl">👑</span>
          <div>
            <div class="text-xs font-black uppercase tracking-wide flex items-center gap-1.5">
              <span>Панель Государства</span>
              <span class="px-1.5 py-0.5 rounded bg-amber-400 text-slate-950 text-[9px] font-black">ADMIN</span>
            </div>
            <div class="text-[10px] text-amber-200 font-medium">Казна, модерация, сброс всех аккаунтов</div>
          </div>
        </div>
        <button class="px-3 py-1.5 rounded-xl bg-amber-400 text-slate-950 font-black text-xs shadow-md shrink-0">
          Войти ➔
        </button>
      </div>` : ''}
      <!-- Corporate Header Card -->
      <div class="glass-card rounded-2xl p-4 shadow-sm relative overflow-hidden">
        <div class="flex items-start justify-between">
          <div>
            <div class="flex items-center gap-2">
              <span class="px-2 py-0.5 rounded-lg bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 font-mono font-bold text-xs tracking-wider">
                [${company.ticker}]
              </span>
              <span class="text-xs font-semibold text-slate-500 dark:text-slate-400">
                ${getSpecializationName(company.specialization)}
              </span>
            </div>
            <h2 class="text-lg font-black text-slate-900 dark:text-white mt-1">
              ${company.name}
            </h2>
            <button id="rename-company-btn" class="mt-1 text-[10px] font-bold text-blue-600 dark:text-blue-300">✏️ Сменить название · 10 000 cash</button>
          </div>
          <div class="text-right">
            <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold ${
              company.is_public
                ? 'bg-amber-100 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border border-amber-300 dark:border-amber-700'
                : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'
            }">
              ${company.is_public ? '🏛️ ПАО (IPO)' : '🔒 Частная'}
            </span>
          </div>
        </div>

        <!-- Level & XP Bar -->
        <div class="mt-4 pt-3 border-t border-slate-200/60 dark:border-slate-800">
          <div class="flex justify-between text-xs font-semibold mb-1">
            <span class="text-slate-600 dark:text-slate-300">Уровень ${company.level || 1} / ${maxLevel} · эпоха ${company.era || 1}</span>
            <span class="text-slate-400 font-mono">${isMaxLevel ? `${xpCurrent} XP` : `${xpCurrent} / ${xpNext} XP`}</span>
          </div>
          <div class="w-full h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
            <div class="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full transition-all duration-500" style="width: ${xpPercent}%"></div>
          </div>
          <div class="mt-1 text-[10px] text-slate-400">${isMaxLevel ? 'Основная шкала 1–60 завершена — дальше открывается мастерство.' : `До следующего уровня: ${Number(company.xp_to_next || 0)} XP. Производите товары, торгуйте и побеждайте в PvE.`}</div>
          ${isMaxLevel && mastery ? `
            <div class="mastery-progress mt-3 rounded-xl p-2.5">
              <div class="flex items-center justify-between text-[11px] font-bold">
                <span>✨ Мастерство корпорации · ранг ${Number(mastery.rank || 0)}</span>
                <span class="font-mono">${Number(mastery.xp || 0).toLocaleString('ru-RU')} XP</span>
              </div>
              <div class="mt-1.5 h-1.5 overflow-hidden rounded-full bg-white/60 dark:bg-black/20"><div class="h-full rounded-full bg-gradient-to-r from-rose-500 to-violet-500" style="width: ${Math.max(0, Math.min(100, Number(mastery.progress_pct || 0)))}%"></div></div>
              <div class="mt-1 text-[10px] opacity-80">До ранга ${Number(mastery.rank || 0) + 1}: ${Number(mastery.xp_to_next || 0).toLocaleString('ru-RU')} XP · шкала без лимита</div>
            </div>
          ` : ''}
        </div>
      </div>

      <!-- Financial Balance Stats Grid -->
      <div class="grid grid-cols-2 gap-3">
        <div class="glass-card rounded-2xl p-4 shadow-sm">
          <div class="text-xs font-bold uppercase tracking-wider text-slate-400">Счёт компании</div>
          <div class="text-xl font-black text-emerald-600 dark:text-emerald-400 mt-1 font-mono">
            ${Number(company.cash || 0).toLocaleString('ru-RU', { maximumFractionDigits: 2 })}
          </div>
          <div class="text-[11px] text-slate-400 mt-0.5">cash (ликвидность)</div>
        </div>

        <div class="glass-card rounded-2xl p-4 shadow-sm">
          <div class="text-xs font-bold uppercase tracking-wider text-slate-400">Оценка NAV</div>
          <div class="text-xl font-black text-blue-600 dark:text-blue-400 mt-1 font-mono">
            ${Number(store.nav || company.cash || 0).toLocaleString('ru-RU', { maximumFractionDigits: 2 })}
          </div>
          <div class="text-[11px] text-slate-400 mt-0.5">активы + склады + кеш</div>
        </div>
      </div>

      ${capitalPlan?.recommended ? `
        <div class="capital-plan-card rounded-2xl p-4 shadow-sm border">
          <div class="flex items-start gap-3">
            <span class="text-2xl">🏛️</span>
            <div class="min-w-0 flex-1">
              <div class="text-sm font-black text-slate-900 dark:text-white">${capitalPlan.title}</div>
              <p class="mt-1 text-[11px] leading-relaxed text-slate-600 dark:text-slate-200">${capitalPlan.message}</p>
              <div class="mt-2 text-[10px] font-semibold text-rose-700 dark:text-rose-200">Не хватает: ${Number(capitalPlan.cash_shortfall || 0).toLocaleString('ru-RU')} cash · дивиденды от ${Number(capitalPlan.min_dividend_pct || 5)}%</div>
              <div class="mt-3 grid grid-cols-2 gap-2">
                <button id="capital-plan-ipo-btn" class="rounded-xl bg-indigo-600 px-3 py-2 text-xs font-bold text-white">${capitalPlan.action?.label || 'Сравнить IPO'}</button>
                ${Number(company.level || 0) >= Number(capitalPlan.debt_option?.available_from_level || 18) ? `<button id="capital-plan-loan-btn" class="rounded-xl bg-amber-500 px-3 py-2 text-xs font-bold text-slate-950">💳 Кредит</button>` : `<button disabled class="rounded-xl bg-slate-200 dark:bg-slate-800 px-3 py-2 text-[10px] font-bold opacity-60">Кредит с ур. ${Number(capitalPlan.debt_option?.available_from_level || 18)}</button>`}
              </div>
              <div class="mt-1.5 text-[10px] text-slate-500 dark:text-slate-300">${capitalPlan.alternative || ''}</div>
            </div>
          </div>
        </div>
      ` : ''}

      <!-- Energy & Infrastructure Status -->
      <div class="glass-card rounded-2xl p-4 shadow-sm">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="text-lg">⚡</span>
            <div>
              <div class="text-xs font-bold text-slate-800 dark:text-white">Муниципальная энергосеть</div>
              <div class="text-[11px] text-slate-400">Стартовая utility-квота хранится на складе; фоновые бесплатные циклы отключены</div>
            </div>
          </div>
          <span class="text-xs font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/50 px-2 py-1 rounded-lg">
            В норме
          </span>
        </div>
      </div>

      <!-- Warehouse / Inventory -->
      <div class="glass-card rounded-2xl p-4 shadow-sm space-y-3">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="text-base">📦</span>
            <h3 class="text-sm font-bold text-slate-900 dark:text-white">Складские запасы</h3>
          </div>
          <span class="text-xs text-slate-400 font-mono">${items.length} поз.</span>
        </div>

        ${items.length === 0 ? `
          <div class="text-center py-6 text-slate-400 text-xs">
            Склад пуст. Закупайте сырьё на бирже или у NPC для запуска производства.
          </div>
        ` : `
          <div class="grid grid-cols-2 gap-2">
            ${items.map(([itemId, qty]) => {
              const info = getItemInfo(itemId);
              const reservedQty = Number(reservedInventory[itemId] || 0);
              return `
              <div class="resource-pill p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200/60 dark:border-slate-700/60 flex items-center justify-between">
                <div class="flex items-center gap-2 min-w-0 pr-1">
                  <span class="text-base shrink-0">${info.icon}</span>
                  <div class="min-w-0">
                    <div class="text-xs font-bold text-slate-800 dark:text-white leading-tight truncate">${info.name}</div>
                    <div class="text-[10px] text-slate-400 font-mono">${info.unit}</div>
                  </div>
                </div>
                <div class="text-right shrink-0">
                  <div class="text-sm font-black font-mono text-slate-900 dark:text-white">
                    ${Number(qty).toLocaleString('ru-RU')}
                  </div>
                  <div class="text-[9px] text-slate-400">доступно</div>
                  ${reservedQty > 0 ? `<div class="text-[9px] text-amber-600 dark:text-amber-400">В заявках: ${reservedQty.toLocaleString('ru-RU')} ${info.unit}</div>` : ''}
                </div>
              </div>
            `;}).join('')}
          </div>
        `}
      </div>

      <!-- Business Capacity -->
      <div class="glass-card rounded-2xl p-4 shadow-sm" id="business-capacity-card">
        <div class="flex items-center justify-between gap-3">
          <div class="flex items-center gap-2 min-w-0">
            <span class="text-base">🏭</span>
            <div class="min-w-0">
              <div class="text-xs font-bold text-slate-800 dark:text-white">Мощности предприятий</div>
              <div class="text-[11px] text-slate-400" id="business-capacity-summary">Загружаем данные о слотах…</div>
            </div>
          </div>
          <button id="expand-capacity-btn" class="shrink-0 px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs active:scale-95 transition-all">
            ＋ Добавить
          </button>
        </div>
      </div>

      <!-- Actions: Respec & Refresh -->
      <div class="pt-2 flex items-center justify-center gap-2">
        <button id="help-btn" class="px-3 py-2 rounded-xl text-xs font-bold text-blue-700 dark:text-blue-300 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 hover:bg-blue-100 transition-colors">❓ Как играть</button>
        <button
          id="respec-btn"
          class="px-3 py-2 rounded-xl text-xs font-bold text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 hover:bg-amber-100 transition-colors"
        >
          🔄 Сменить отрасль
        </button>
        ${Number(company.level || 0) >= 14 ? `<button id="loans-btn" class="px-3 py-2 rounded-xl text-xs font-bold text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800">💳 Долги</button>` : ''}
        <button
          id="refresh-btn"
          class="px-3 py-2 rounded-xl text-xs font-bold text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors"
        >
          ⚡ Обновить NAV
        </button>
      </div>
    </div>
  `;

  void updateBusinessCapacityCard(container);
  container.querySelector('#rename-company-btn')?.addEventListener('click', async (event) => {
    const newName = prompt('Новое название компании (стоимость смены — 10 000 cash):', company.name)?.trim();
    if (!newName || newName === company.name) return;
    if (!confirm(`Сменить название на «${newName}» за 10 000 cash?`)) return;
    const button = event.currentTarget;
    button.disabled = true;
    try {
      const result = await NatAPI.renameCompany(newName);
      const refreshed = await NatAPI.getMyCompany();
      store.setCompany(refreshed);
      showToast(`Название изменено на «${result.name || newName}»`, 'success');
      renderOverview(container, showToast);
    } catch (err) {
      showToast(err.message, 'error');
      button.disabled = false;
    }
  });
  container.querySelector('#help-btn')?.addEventListener('click', () => window.NatApp?.navigateTo('help'));
  container.querySelector('#capital-plan-ipo-btn')?.addEventListener('click', () => window.NatApp?.navigateTo('market'));
  container.querySelector('#capital-plan-loan-btn')?.addEventListener('click', async () => {
    try {
      const status = await NatAPI.getLoans();
      const quote = status.quote || {};
      if (!quote.eligible) {
        showToast(`Кредит пока недоступен. Требуется уровень ${quote.required_level || 18}`, 'error');
        return;
      }
      const suggested = Math.min(Number(capitalPlan.cash_shortfall || quote.max_principal || 0), Number(quote.max_principal || 0));
      const raw = prompt(`Сумма кредита (${Number(quote.min_principal || 0).toLocaleString('ru-RU')}–${Number(quote.max_principal || 0).toLocaleString('ru-RU')} cash). Ставка ${Number(quote.daily_interest_pct || 0)}%/день, срок ${Number(quote.term_days || 14)} дней.`, Math.round(suggested));
      if (!raw) return;
      const amount = Number(raw);
      const result = await NatAPI.borrow(amount);
      showToast(`Получено ${Number(result.cash_received || 0).toLocaleString('ru-RU')} cash. Долг нужно погасить в срок.`, 'success');
      const refreshed = await NatAPI.getMyCompany();
      store.setCompany(refreshed);
      renderOverview(container, showToast);
    } catch (err) {
      showToast(err.message, 'error');
    }
  });

  container.querySelector('#loans-btn')?.addEventListener('click', async () => {
    try {
      const status = await NatAPI.getLoans();
      const open = (status.loans || []).filter(loan => ['ACTIVE', 'DEFAULTED'].includes(loan.status));
      if (!open.length) {
        const q = status.quote || {};
        showToast(q.eligible
          ? `Долгов нет. Доступный лимит: ${Number(q.max_principal || 0).toLocaleString('ru-RU')} cash под ${Number(q.daily_interest_pct || 0)}%/день.`
          : 'Долгов нет; новый кредит сейчас недоступен.', 'info');
        return;
      }
      const loan = open[0];
      const raw = prompt(`Долг #${loan.id}: ${Number(loan.remaining_debt).toLocaleString('ru-RU')} cash · ${loan.daily_interest_pct}%/день · срок ${loan.due_date}. Сколько погасить?`, Math.ceil(Number(loan.remaining_debt)));
      if (!raw) return;
      const result = await NatAPI.repayLoan(loan.id, Number(raw));
      showToast(`Погашено ${Number(result.paid).toLocaleString('ru-RU')} cash. Остаток долга ${Number(result.loan.remaining_debt).toLocaleString('ru-RU')}.`, 'success');
      const refreshed = await NatAPI.getMyCompany();
      store.setCompany(refreshed);
      renderOverview(container, showToast);
    } catch (err) { showToast(err.message, 'error'); }
  });

  // Attach refresh handler
  const refreshBtn = container.querySelector('#refresh-btn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', async () => {
      try {
        refreshBtn.innerText = 'Обновление...';
        const refreshed = await NatAPI.getMyCompany();
        store.setCompany(refreshed);
        renderOverview(container, showToast);
        showToast('Данные актуализированы', 'info');
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        refreshBtn.innerText = '⚡ Обновить NAV';
      }
    });
  }

  // Attach respec handler
  const respecBtn = container.querySelector('#respec-btn');
  if (respecBtn) {
    respecBtn.addEventListener('click', async () => {
      const specs = ['metallurgist', 'power_engineer', 'oilman', 'agrarian', 'chemist', 'technoprom', 'miner', 'forester'];
      const specPrompt = prompt(
        `Выберите новую специализацию:\n${specs.join(', ')}`,
        company.specialization
      );
      if (!specPrompt || specPrompt === company.specialization) return;
      const targetSpec = specPrompt.trim().toLowerCase();
      if (!specs.includes(targetSpec)) {
        showToast('Неизвестная специализация!', 'error');
        return;
      }
      try {
        respecBtn.disabled = true;
        respecBtn.innerText = 'Смена...';
        await NatAPI.respecCompany(targetSpec);
        showToast('Отрасль компании успешно изменена!', 'success');
        const refreshed = await NatAPI.getMyCompany();
        store.setCompany(refreshed);
        renderOverview(container, showToast);
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        respecBtn.disabled = false;
        respecBtn.innerText = '🔄 Сменить отрасль';
      }
    });
  }

  const expandBtn = container.querySelector('#expand-capacity-btn');
  if (expandBtn) {
    expandBtn.addEventListener('click', async () => {
      try {
        expandBtn.disabled = true;
        expandBtn.innerText = 'Запускаем...';
        const result = await NatAPI.expandBusinessCapacity();
        showToast(`Слот ${result.target_capacity} откроется через ${result.duration_hours} ч.`, 'success');
        const refreshed = await NatAPI.getMyCompany();
        store.setCompany(refreshed);
        renderOverview(container, showToast);
      } catch (err) {
        showToast(err.message || 'Не удалось расширить мощности', 'error');
      } finally {
        if (expandBtn.isConnected) {
          expandBtn.disabled = false;
          expandBtn.innerText = '＋ Добавить';
        }
      }
    });
  }

  const creatorBanner = container.querySelector('#creator-banner-card');
  if (creatorBanner) {
    creatorBanner.addEventListener('click', () => {
      if (window.NatApp?.navigateTo) {
        window.NatApp.navigateTo('creator');
      }
    });
  }
}
