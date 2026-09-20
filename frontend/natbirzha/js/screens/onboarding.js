import { NatAPI } from '../api.js';
import { store } from '../state.js';

const SPECIALIZATIONS = [
  { id: 'metallurgist', name: 'Металлургия', icon: '⚙️', desc: 'Добыча руды, выплавка чугуна, стали и сплавов', starter: '🔥 Металлургический комбинат → сталь' },
  { id: 'power_engineer', name: 'Энергетика', icon: '⚡', desc: 'Угольные, газовые и АЭС, генерация МВт·ч', starter: '☀️ Солнечная электростанция → энергия' },
  { id: 'oilman', name: 'Нефтегаз', icon: '🛢️', desc: 'Бурение, сырая нефть, бензин и полимеры', starter: '🛢️ Нефтяная вышка → сырая нефть' },
  { id: 'agrarian', name: 'Агропром', icon: '🌾', desc: 'Зерно, биоэтанол, фермы и продовольствие', starter: '🌱 Зерновая ферма → зерно' },
  { id: 'chemist', name: 'Химия', icon: '🧪', desc: 'Удобрения, кислоты, реагенты и синтетика', starter: '⚗️ Химзавод → базовые реагенты' },
  { id: 'technoprom', name: 'Технопром', icon: '🔌', desc: 'Оборудование, электроника, высокие технологии', starter: '🔧 Завод компонентов → компоненты' },
  { id: 'miner', name: 'Горнодобыча', icon: '⛏️', desc: 'Уголь, руда и минералы; редкая добыча открывается отдельно', starter: '⛏️ Железный рудник → железная руда' },
  { id: 'forester', name: 'Лесопром', icon: '🌲', desc: 'Лесозаготовка, пиломатериалы и целлюлоза', starter: '🌲 Лесозаготовка → древесина' },
];

const FUTURE_SPECIALIZATIONS = [
  '🏗️ Строительство и инфраструктура',
  '🧬 Фармацевтика и биотехнологии',
  '🚚 Логистика и транспорт',
  '🚀 Аэрокосмическая промышленность',
];

export function renderOnboarding(container, showToast) {
  let selectedSpec = 'metallurgist';
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
    <div class="max-w-md mx-auto p-4 space-y-6">
      ${isCreator ? `
      <!-- Creator / State Administration Banner -->
      <div id="onboarding-creator-banner" class="rounded-2xl p-3.5 bg-gradient-to-r from-amber-600 via-amber-700 to-amber-900 text-white shadow-lg border border-amber-400/40 flex items-center justify-between cursor-pointer active:scale-98 transition-all">
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
        <button type="button" class="px-3 py-1.5 rounded-xl bg-amber-400 text-slate-950 font-black text-xs shadow-md shrink-0">
          Войти ➔
        </button>
      </div>` : ''}

      <div class="text-center space-y-2">
        <div class="w-16 h-16 mx-auto rounded-3xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-amber-500 flex items-center justify-center text-white text-3xl shadow-xl shadow-indigo-500/25">
          🏛️
        </div>
        <h1 class="text-2xl font-black text-slate-900 dark:text-white">Основание Корпорации</h1>
        <p class="text-sm text-slate-500 dark:text-slate-400">
          ${isCreator ? 'Грант Создателя: 500,000 cash и 500 PVC/NAT.' : 'Зарегистрируйте предприятие на НАТБИРЖЕ и получите стартовый капитал 50,000 cash.'}
        </p>
      </div>

      <form id="create-company-form" class="space-y-4">
        <div>
          <label class="block text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400 mb-1">
            Название компании
          </label>
          <input
            type="text"
            id="company-name"
            required
            maxlength="64"
            placeholder="Например: ПАО «Северсталь»"
            class="w-full px-4 py-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label class="block text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400 mb-1">
            Биржевой тикер (3-5 букв)
          </label>
          <input
            type="text"
            id="company-ticker"
            required
            minlength="3"
            maxlength="5"
            placeholder="STEEL"
            class="w-full px-4 py-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white placeholder-slate-400 uppercase font-mono tracking-widest focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label class="block text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400 mb-2">
            Промышленная отрасль (Специализация)
          </label>
          <div class="mb-2 rounded-xl border border-emerald-300/60 bg-emerald-50/70 dark:bg-emerald-950/20 px-3 py-2 text-[11px] text-emerald-800 dark:text-emerald-300">
            <span class="font-black">Открыто с начала:</span> все 8 отраслей ниже доступны при создании компании. На карточке указан ваш стартовый завод и первый товар.
          </div>
          <div class="grid grid-cols-2 gap-2" id="spec-picker">
            ${SPECIALIZATIONS.map(s => `
              <button
                type="button"
                data-spec="${s.id}"
                class="spec-btn p-3 rounded-xl border text-left flex flex-col justify-between transition-all ${
                  s.id === selectedSpec
                    ? 'border-blue-500 bg-blue-50/50 dark:bg-blue-950/40 ring-2 ring-blue-500'
                    : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900'
                }"
              >
                <div class="text-xl mb-1">${s.icon}</div>
                <div class="font-bold text-xs text-slate-900 dark:text-white leading-tight">${s.name}</div>
                <div class="text-[10px] text-slate-500 dark:text-slate-400 mt-1 line-clamp-2">${s.desc}</div>
                <div class="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 mt-2">${s.starter}</div>
              </button>
            `).join('')}
          </div>
          <div class="mt-3">
            <div class="text-[11px] font-black uppercase tracking-wider text-slate-500 mb-2">Будущие отрасли</div>
            <div class="grid grid-cols-2 gap-2">
              ${FUTURE_SPECIALIZATIONS.map(name => `
                <button type="button" disabled class="p-3 rounded-xl border border-dashed border-slate-300 dark:border-slate-700 bg-slate-100/70 dark:bg-slate-900/50 text-left opacity-60 cursor-not-allowed">
                  <div class="text-[11px] font-bold text-slate-500 dark:text-slate-400">${name}</div>
                  <div class="text-[9px] text-slate-400 mt-1">Недоступно при старте · откроется в следующих эпохах</div>
                </button>
              `).join('')}
            </div>
          </div>
        </div>

        <button
          type="submit"
          id="submit-create-btn"
          class="w-full py-4 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-bold text-sm shadow-lg shadow-blue-500/30 hover:from-blue-700 hover:to-indigo-700 active:scale-[0.98] transition-all"
        >
          ${isCreator ? '🚀 Зарегистрировать компанию (+500,000 cash)' : '🚀 Зарегистрировать компанию (+50,000 cash)'}
        </button>
      </form>
    </div>
  `;

  // Spec selection
  const SPEC_ACTIVE_CLASS = 'spec-btn p-3 rounded-xl border text-left flex flex-col justify-between transition-all border-blue-500 bg-blue-50/50 dark:bg-blue-950/40 ring-2 ring-blue-500';
  const SPEC_INACTIVE_CLASS = 'spec-btn p-3 rounded-xl border text-left flex flex-col justify-between transition-all border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900';

  function updateSpecSelection(specId) {
    if (!specId) return;
    selectedSpec = specId;
    container.querySelectorAll('.spec-btn').forEach(b => {
      const isSelected = b.getAttribute('data-spec') === selectedSpec;
      b.className = isSelected ? SPEC_ACTIVE_CLASS : SPEC_INACTIVE_CLASS;
    });
  }

  const specPicker = container.querySelector('#spec-picker');
  if (specPicker) {
    specPicker.addEventListener('click', (e) => {
      const btn = e.target.closest('.spec-btn');
      if (btn) {
        const spec = btn.getAttribute('data-spec');
        updateSpecSelection(spec);
      }
    });
  }

  const specButtons = container.querySelectorAll('.spec-btn');
  specButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      updateSpecSelection(btn.getAttribute('data-spec'));
    });
  });

  // Form submit
  const form = container.querySelector('#create-company-form');
  const submitBtn = container.querySelector('#submit-create-btn');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const nameInput = container.querySelector('#company-name');
    const tickerInput = container.querySelector('#company-ticker');
    const name = nameInput.value.trim();
    const ticker = tickerInput.value.trim().toUpperCase();

    if (!name || !ticker) {
      showToast('Заполните все поля!', 'error');
      return;
    }

    try {
      submitBtn.disabled = true;
      submitBtn.innerText = 'Создание...';
      const company = await NatAPI.createCompany({
        name,
        ticker,
        specialization: selectedSpec,
        territory_hex: 'NORTH_INDUSTRIAL_HEX_1',
      });
      let fullCompany = company;
      try {
        fullCompany = await NatAPI.getMyCompany();
      } catch (_) {}
      store.setCompany(fullCompany);
      showToast(`Корпорация «${name}» успешно создана!`, 'success');
      document.getElementById('bottom-nav')?.classList.remove('hidden');
      document.getElementById('header-stats')?.classList.remove('hidden');
      if (typeof window !== 'undefined' && window.NatApp?.navigateTo) {
        window.NatApp.navigateTo('overview');
      } else {
        store.setTab('overview');
        if (typeof window !== 'undefined' && window.NatApp?.renderCurrentScreen) {
          window.NatApp.renderCurrentScreen();
        }
      }
    } catch (err) {
      const errMsg = String(err?.message || err || '');
      if (errMsg.includes('already owns') || errMsg.includes('уже владеет')) {
        showToast('У вас уже есть компания! Загружаем...', 'info');
        try {
          const existingComp = await NatAPI.getMyCompany();
          if (existingComp) {
            store.setCompany(existingComp);
            document.getElementById('bottom-nav')?.classList.remove('hidden');
            document.getElementById('header-stats')?.classList.remove('hidden');
            if (typeof window !== 'undefined' && window.NatApp?.navigateTo) {
              window.NatApp.navigateTo('overview');
            } else {
              store.setTab('overview');
              if (typeof window !== 'undefined' && window.NatApp?.renderCurrentScreen) {
                window.NatApp.renderCurrentScreen();
              }
            }
            return;
          }
        } catch (_) {}
      }
      showToast(errMsg || 'Ошибка создания компании', 'error');
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerText = isCreator
        ? '🚀 Зарегистрировать компанию (+500,000 cash)'
        : '🚀 Зарегистрировать компанию (+50,000 cash)';
    }
  });

  if (isCreator) {
    container.querySelector('#onboarding-creator-banner')?.addEventListener('click', () => {
      if (typeof window !== 'undefined' && window.NatApp?.navigateTo) {
        window.NatApp.navigateTo('creator');
      }
    });
  }
}
