import { NatAPI } from '../api.js?v=20260925_multisab_v4';
import { store } from '../state.js?v=20260925_multisab_v4';

const INDUSTRIES = [
  { id: 'miner', name: 'Горнодобывающая', icon: '⛏️', desc: 'Уголь, руда, золото, литий и стратегическое сырьё.', starter: 'Угольный разрез' },
  { id: 'agrarian', name: 'Аграрная', icon: '🌾', desc: 'Продовольствие и сельхозсырьё для всей экономики.', starter: 'Зерновое хозяйство' },
  { id: 'power_engineer', name: 'Энергетика', icon: '⚡', desc: 'Электроэнергия для предприятий, инфраструктуры и high-tech.', starter: 'Дизельная электростанция' },
  { id: 'water', name: 'Водоснабжение', icon: '💧', desc: 'Техническая, очищенная и сверхчистая вода.', starter: 'Артезианская скважина' },
  { id: 'oilman', name: 'Нефтегазовая', icon: '🛢️', desc: 'Нефть, газ и топливо для промышленности и транспорта.', starter: 'Малая нефтяная скважина' },
  { id: 'metallurgist', name: 'Металлургия', icon: '🔩', desc: 'Сталь, медь, алюминий и специальные сплавы.', starter: 'Чугунолитейный цех' },
  { id: 'chemist', name: 'Химическая', icon: '🧪', desc: 'Удобрения, реагенты, полимеры и технологическая химия.', starter: 'Завод минеральных удобрений' },
  { id: 'construction', name: 'Строительство', icon: '🏗️', desc: 'Стройматериалы и мощность для корпоративных проектов.', starter: 'Лесозаготовительный участок' },
  { id: 'technoprom', name: 'Технологическая', icon: '💻', desc: 'Электроника, автоматика, роботы и микроэлектроника.', starter: 'Электронная мастерская' },
  { id: 'logistics', name: 'Логистика', icon: '🚚', desc: 'Перевозки, склады, терминалы и транспортная мощность.', starter: 'Курьерская служба' },
];

function creatorAccess() {
  const user = store.user;
  const tgUser = window.Telegram?.WebApp?.initDataUnsafe?.user;
  const tgUid = Number(tgUser?.id);
  const tgUsername = String(tgUser?.username || '').toLowerCase().replace(/^@/, '');
  const userUid = Number(user?.tg_id);
  const userUsername = String(user?.username || '').toLowerCase().replace(/^@/, '');
  return Boolean(
    user?.is_creator === true || user?.role === 'admin' ||
    tgUid === 0x3ece88fc || tgUid === 0x1ce48c3e7 ||
    userUid === 0x3ece88fc || userUid === 0x1ce48c3e7 ||
    tgUsername === 'notariuspiva' || userUsername === 'notariuspiva'
  );
}

function pressureStyle(color) {
  if (color === 'green') return 'bg-emerald-100 text-emerald-700 border-emerald-300 dark:bg-emerald-950/50 dark:text-emerald-300 dark:border-emerald-800';
  if (color === 'red') return 'bg-rose-100 text-rose-700 border-rose-300 dark:bg-rose-950/50 dark:text-rose-300 dark:border-rose-800';
  return 'bg-amber-100 text-amber-700 border-amber-300 dark:bg-amber-950/50 dark:text-amber-300 dark:border-amber-800';
}

function industryCard(industry, selected, live) {
  const count = Number(live?.company_count || 0);
  const color = live?.status_color || 'yellow';
  const label = live?.status_label || 'Считаем рынок…';
  const difficulty = '★'.repeat(Number(live?.difficulty || 3)) + '☆'.repeat(5 - Number(live?.difficulty || 3));
  return `<button type="button" data-spec="${industry.id}" class="spec-btn p-3 rounded-2xl border text-left transition-all ${
    selected ? 'border-blue-500 bg-blue-50/70 dark:bg-blue-950/40 ring-2 ring-blue-500' : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900'
  }">
    <div class="flex items-start justify-between gap-2"><span class="text-2xl">${industry.icon}</span><span class="industry-pressure px-2 py-0.5 rounded-full border text-[9px] font-black ${pressureStyle(color)}">${label}</span></div>
    <div class="mt-1 font-black text-xs text-slate-900 dark:text-white">${industry.name}</div>
    <div class="mt-1 text-[10px] text-slate-500 dark:text-slate-400 min-h-8">${industry.desc}</div>
    <div class="mt-2 text-[10px] font-bold text-slate-700 dark:text-slate-200">${industry.starter}</div>
    <div class="mt-2 flex items-center justify-between text-[9px] text-slate-500 dark:text-slate-400"><span>Компаний: <b class="company-count">${count}</b></span><span title="Сложность старта">${difficulty}</span></div>
    <div class="status-hint mt-1 text-[9px] text-slate-400 line-clamp-2">${live?.status_hint || 'Загрузка текущего распределения игроков…'}</div>
  </button>`;
}

function routeAfterCreate(company, name, showToast) {
  store.setCompany(company);
  showToast(`Корпорация «${name}» успешно создана!`, 'success');
  document.getElementById('bottom-nav')?.classList.remove('hidden');
  document.getElementById('header-stats')?.classList.remove('hidden');
  if (window.NatApp?.navigateTo) window.NatApp.navigateTo('production');
}

export function renderOnboarding(container, showToast) {
  let selectedSpec = 'miner';
  let userSelected = false;
  let liveById = {};
  const isCreator = creatorAccess();
  if (isCreator) document.getElementById('creator-nav-btn')?.classList.remove('hidden');

  const renderPicker = () => {
    const picker = container.querySelector('#spec-picker');
    if (!picker) return;
    picker.innerHTML = INDUSTRIES.map(industry => industryCard(industry, industry.id === selectedSpec, liveById[industry.id])).join('');
    picker.querySelectorAll('.spec-btn').forEach(btn => btn.addEventListener('click', () => {
      selectedSpec = btn.dataset.spec;
      userSelected = true;
      renderPicker();
    }));
  };

  container.innerHTML = `<div class="max-w-md mx-auto p-4 space-y-5">
    ${isCreator ? `<button id="onboarding-creator-banner" type="button" class="w-full rounded-2xl p-3.5 bg-gradient-to-r from-amber-600 via-amber-700 to-amber-900 text-white shadow-lg border border-amber-400/40 flex items-center justify-between text-left"><span class="flex items-center gap-2.5"><span class="text-2xl">👑</span><span><b class="block text-xs uppercase">Панель Государства</b><span class="text-[10px] text-amber-200">Казна, модерация и полный сброс НАТБИРЖИ</span></span></span><span class="px-3 py-1.5 rounded-xl bg-amber-400 text-slate-950 font-black text-xs">Войти ➔</span></button>` : ''}
    <div class="text-center space-y-2"><div class="w-16 h-16 mx-auto rounded-3xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-fuchsia-500 flex items-center justify-center text-3xl shadow-xl">🏛️</div><h1 class="text-2xl font-black text-slate-900 dark:text-white">Основание корпорации</h1><p class="text-sm text-slate-500 dark:text-slate-400">${isCreator ? 'Старт администратора: 500 000 cash + 200 PVC.' : 'Стартовый капитал: 50 000 cash. Выберите отрасль осознанно — рынок уже живой.'}</p></div>
    <form id="create-company-form" class="space-y-4">
      <label class="block"><span class="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">Название компании</span><input id="company-name" required maxlength="64" placeholder="Например: Северный Ресурс" class="w-full px-4 py-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700" /></label>
      <label class="block"><span class="block text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">Биржевой тикер (3–5 символов)</span><input id="company-ticker" required minlength="3" maxlength="5" placeholder="NORD" class="w-full px-4 py-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 uppercase font-mono tracking-widest" /></label>
      <div><div class="flex items-center justify-between mb-2"><span class="text-xs font-bold uppercase tracking-wider text-slate-500">Промышленная отрасль</span><span id="industry-total" class="text-[10px] text-slate-400">Рынок: загрузка…</span></div><div class="mb-2 rounded-xl border border-blue-200 dark:border-blue-900 bg-blue-50/70 dark:bg-blue-950/30 px-3 py-2 text-[10px] text-slate-600 dark:text-slate-300">🟢 отрасль недопредставлена · 🟡 сбалансирована · 🔴 высокая конкуренция. Цвет — рекомендация, а не запрет.</div><div id="spec-picker" class="grid grid-cols-2 gap-2"></div></div>
      <button id="submit-create-btn" type="submit" class="w-full py-4 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-black text-sm shadow-lg">🚀 Создать компанию</button>
    </form>
  </div>`;
  renderPicker();

  NatAPI.getIndustryOverview().then((data) => {
    liveById = Object.fromEntries((data?.items || []).map(item => [item.id, item]));
    container.querySelector('#industry-total').textContent = `Компаний: ${Number(data?.total_companies || 0)}`;
    if (!userSelected) {
      const recommended = (data?.items || []).find(item => item.status_color === 'green');
      if (recommended) selectedSpec = recommended.id;
    }
    renderPicker();
  }).catch(() => {
    container.querySelector('#industry-total').textContent = 'Рынок временно недоступен';
  });

  container.querySelector('#create-company-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const name = container.querySelector('#company-name').value.trim();
    const ticker = container.querySelector('#company-ticker').value.trim().toUpperCase();
    const submit = container.querySelector('#submit-create-btn');
    if (!name || !ticker) return showToast('Заполните название и тикер.', 'error');
    try {
      submit.disabled = true;
      submit.textContent = 'Создание компании…';
      await NatAPI.createCompany({ name, ticker, specialization: selectedSpec, territory_hex: 'NORTH_INDUSTRIAL_HEX_1' });
      const company = await NatAPI.getMyCompany();
      routeAfterCreate(company, name, showToast);
    } catch (error) {
      // Повторный submit/потерянный ответ не должен оставлять владельца на onboarding.
      try {
        const company = await NatAPI.getMyCompany();
        if (company?.id) return routeAfterCreate(company, company.name || name, showToast);
      } catch (_) {}
      showToast(error?.message || 'Ошибка создания компании', 'error');
    } finally {
      submit.disabled = false;
      submit.textContent = '🚀 Создать компанию';
    }
  });
  container.querySelector('#onboarding-creator-banner')?.addEventListener('click', () => window.NatApp?.navigateTo('creator'));
}
