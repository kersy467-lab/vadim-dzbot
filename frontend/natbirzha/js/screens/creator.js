import { NatAPI } from '../api.js';
import { loadCreatorOverview } from './creator_overview.js';
import { loadCreatorModeration } from './creator_moderation.js';
import { loadCreatorShares } from './creator_shares.js';
import { loadCreatorPlayersTab } from './creator_players.js';
import { loadCreatorCreditTab } from './creator_credit.js';
import { declareCreatorBondBankruptcy } from './creator_bond_api.js';

let activeTab = 'overview';
const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
}[char]));

export async function renderCreator(container, showToast) {
  container.innerHTML = `
    <div class="space-y-4 max-w-md mx-auto p-4 pb-24 text-slate-100">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="text-xl font-black text-amber-400 flex items-center gap-2">
            <span>👑</span> Панель Создателя
          </h2>
          <p class="text-[11px] text-slate-400">Государственное управление и модерация рынка</p>
        </div>
        <div class="flex items-center gap-1.5">
          <button id="exit-creator-btn" class="px-2.5 py-1.5 rounded-xl bg-slate-800 border border-slate-700 hover:bg-slate-700 text-xs text-slate-300 font-bold flex items-center gap-1">
            ← В игру
          </button>
          <button id="refresh-creator-btn" class="p-2 rounded-xl bg-slate-800 border border-slate-700 hover:bg-slate-700 text-xs">
            🔄
          </button>
        </div>
      </div>

      <!-- Navigation Tabs -->
      <div class="flex gap-1 overflow-x-auto pb-1 text-xs font-bold scrollbar-none">
        <button class="creator-tab-btn px-3 py-1.5 rounded-lg whitespace-nowrap transition-all ${activeTab === 'overview' ? 'bg-amber-500 text-slate-950 shadow-md' : 'bg-slate-800/80 text-slate-300'}" data-tab="overview">🏛️ Казна</button>
        <button class="creator-tab-btn px-3 py-1.5 rounded-lg whitespace-nowrap transition-all ${activeTab === 'market' ? 'bg-amber-500 text-slate-950 shadow-md' : 'bg-slate-800/80 text-slate-300'}" data-tab="market">⚖️ Модерация</button>
        <button class="creator-tab-btn px-3 py-1.5 rounded-lg whitespace-nowrap transition-all ${activeTab === 'bonds' ? 'bg-amber-500 text-slate-950 shadow-md' : 'bg-slate-800/80 text-slate-300'}" data-tab="bonds">📜 Облигации</button>
        <button class="creator-tab-btn px-3 py-1.5 rounded-lg whitespace-nowrap transition-all ${activeTab === 'shares' ? 'bg-amber-500 text-slate-950 shadow-md' : 'bg-slate-800/80 text-slate-300'}" data-tab="shares">📈 Акции государства</button>
        <button class="creator-tab-btn px-3 py-1.5 rounded-lg whitespace-nowrap transition-all ${activeTab === 'credits' ? 'bg-amber-500 text-slate-950 shadow-md' : 'bg-slate-800/80 text-slate-300'}" data-tab="credits">🏦 Кредиты</button>
        <button class="creator-tab-btn px-3 py-1.5 rounded-lg whitespace-nowrap transition-all ${activeTab === 'tournaments' ? 'bg-amber-500 text-slate-950 shadow-md' : 'bg-slate-800/80 text-slate-300'}" data-tab="tournaments">⚔️ Турниры</button>
        <button class="creator-tab-btn px-3 py-1.5 rounded-lg whitespace-nowrap transition-all ${activeTab === 'players' ? 'bg-amber-500 text-slate-950 shadow-md' : 'bg-slate-800/80 text-slate-300'}" data-tab="players">👥 Игроки</button>
        <button class="creator-tab-btn px-3 py-1.5 rounded-lg whitespace-nowrap transition-all ${activeTab === 'premium' ? 'bg-amber-500 text-slate-950 shadow-md' : 'bg-slate-800/80 text-slate-300'}" data-tab="premium">💎 PVC</button>
        <button class="creator-tab-btn px-3 py-1.5 rounded-lg whitespace-nowrap transition-all ${activeTab === 'audit' ? 'bg-amber-500 text-slate-950 shadow-md' : 'bg-slate-800/80 text-slate-300'}" data-tab="audit">📋 Аудит</button>
      </div>

      <div id="creator-tab-content" class="space-y-3">
        <div class="glass-card rounded-2xl p-6 text-center text-xs text-slate-400">Загрузка данных...</div>
      </div>
    </div>
  `;

  // Mouse wheel → horizontal scroll on top tabs row (PC / Telegram Desktop)
  const creatorTabsRow = container.querySelector('.flex.gap-1.overflow-x-auto');
  if (creatorTabsRow) {
    creatorTabsRow.addEventListener('wheel', (e) => {
      if (e.deltaY !== 0) { e.preventDefault(); creatorTabsRow.scrollLeft += e.deltaY; }
    }, { passive: false });
  }

  // Bind tab switching
  container.querySelectorAll('.creator-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      activeTab = btn.dataset.tab;
      renderCreator(container, showToast);
    });
  });


  const refreshBtn = container.querySelector('#refresh-creator-btn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => renderCreator(container, showToast));
  }

  const exitBtn = container.querySelector('#exit-creator-btn');
  if (exitBtn) {
    exitBtn.addEventListener('click', () => {
      if (window.NatApp?.navigateTo) {
        window.NatApp.navigateTo('overview');
      }
    });
  }

  const contentArea = container.querySelector('#creator-tab-content');
  if (!contentArea) return;

  try {
    if (activeTab === 'overview') {
      await loadCreatorOverview(contentArea, showToast);
    } else if (activeTab === 'market') {
      await loadCreatorModeration(contentArea, showToast);
    } else if (activeTab === 'bonds') {
      await loadBondsTab(contentArea, showToast);
    } else if (activeTab === 'shares') {
      await loadCreatorShares(contentArea, showToast);
    } else if (activeTab === 'credits') {
      await loadCreatorCreditTab(contentArea, showToast);
    } else if (activeTab === 'tournaments') {
      await loadTournamentsTab(contentArea, showToast);
    } else if (activeTab === 'players') {
      await loadCreatorPlayersTab(contentArea, showToast);
    } else if (activeTab === 'premium') {
      await loadPremiumLedgerTab(contentArea);
    } else if (activeTab === 'audit') {
      await loadAuditTab(contentArea, showToast);
    }
  } catch (err) {
    contentArea.innerHTML = `
      <div class="glass-card rounded-2xl p-4 border border-rose-500/30 bg-rose-950/20 text-center">
        <p class="text-rose-400 text-xs font-bold">${err.message || 'Ошибка загрузки данных администратора'}</p>
      </div>
    `;
  }
}

async function loadPremiumLedgerTab(el) {
  const data = await NatAPI.getCreatorPremiumLedger();
  const entries = data.entries || [];
  el.innerHTML = `
    <div class="glass-card rounded-2xl p-4 space-y-2">
      <div class="flex items-center justify-between gap-2"><div><div class="text-xs font-bold text-amber-400 uppercase">Журнал PVC</div><div class="text-[10px] text-slate-400">Неизменяемая история начислений и списаний Pivocoins.</div></div><span class="text-[10px] text-slate-500">${entries.length} операций</span></div>
      <div class="space-y-2 max-h-[31rem] overflow-y-auto">
        ${entries.map(entry => {
          const meta = entry.metadata && Object.keys(entry.metadata).length ? JSON.stringify(entry.metadata) : '—';
          const player = entry.telegram_name || entry.telegram_username || `Компания #${entry.company_id}`;
          return `<div class="rounded-xl border border-slate-800 bg-slate-900/60 p-3 text-[10px]"><div class="flex justify-between gap-3"><div><div class="font-bold text-slate-100">${escapeHtml(entry.company_name)} <span class="text-slate-500">· ${escapeHtml(player)}</span></div><div class="text-slate-400 mt-0.5">${escapeHtml(entry.reason)}</div></div><div class="font-mono font-black whitespace-nowrap ${entry.amount > 0 ? 'text-emerald-400' : 'text-rose-400'}">${entry.amount > 0 ? '+' : ''}${entry.amount} PVC</div></div><div class="mt-1 flex justify-between gap-2 text-slate-500"><span>Баланс ${entry.balance_before} → ${entry.balance_after}</span><span>${new Date(entry.created_at).toLocaleString('ru-RU')}</span></div><div class="mt-1 text-[9px] text-slate-500 break-all">${escapeHtml(meta)}</div></div>`;
        }).join('') || '<div class="py-4 text-center text-xs text-slate-500">Операций PVC пока нет.</div>'}
      </div>
    </div>
  `;
}

async function loadBondsTab(el, showToast) {
  const data = await NatAPI.getCreatorBonds();
  el.innerHTML = `
    <div class="glass-card rounded-2xl p-4 space-y-3">
      <div class="text-xs font-bold text-amber-400 uppercase">Выпуск государственных облигаций</div>
      <div class="space-y-2 text-xs">
        <input id="bond-title" placeholder="Название (напр. ОФЗ-НАТ-1)" class="w-full p-2 rounded-xl bg-slate-900 border border-slate-700 text-white" />
        <div class="grid grid-cols-2 gap-2">
          <input id="bond-vol" type="number" placeholder="Объём (шт.)" class="p-2 rounded-xl bg-slate-900 border border-slate-700 text-white" />
          <input id="bond-face" type="number" placeholder="Номинал (₽)" class="p-2 rounded-xl bg-slate-900 border border-slate-700 text-white" />
        </div>
        <div class="grid grid-cols-2 gap-2">
          <input id="bond-rate" type="number" placeholder="Купон (%)" class="p-2 rounded-xl bg-slate-900 border border-slate-700 text-white" />
          <input id="bond-days" type="number" placeholder="Срок (дней)" class="p-2 rounded-xl bg-slate-900 border border-slate-700 text-white" />
        </div>
        <input id="bond-purpose" placeholder="Цель привлечения средств" class="w-full p-2 rounded-xl bg-slate-900 border border-slate-700 text-white" />
        <button id="issue-bond-btn" class="w-full py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 font-bold text-white text-xs transition-all shadow-md">
          Выпустить облигации
        </button>
      </div>
    </div>

    <div class="glass-card rounded-2xl p-3 space-y-2">
      <div class="text-xs font-bold text-slate-300">Размещённые облигации (${data.bonds.length})</div>
      <div class="space-y-1.5">
        ${data.bonds.map(b => `
          <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-2.5 text-[11px] font-mono">
            <div class="flex justify-between font-bold text-white">
              <span>${b.title}</span>
              <span class="text-amber-400">${b.coupon_rate}% годовых</span>
            </div>
            <div class="text-[10px] text-slate-400 mt-1">
              Остаток: ${b.remaining_volume} / ${b.total_volume} шт. по ${b.face_value} ₽ · Срок: ${b.maturity_days} дн.
            </div>
            <div class="text-[9px] text-slate-500 italic mt-0.5">${b.purpose}</div>
            <div class="mt-2 flex justify-end">
              ${b.status === 'BANKRUPT'
                ? '<span class="rounded-lg bg-rose-950/50 px-2.5 py-1 text-[10px] font-bold text-rose-300">Банкротство объявлено</span>'
                : b.status === 'CLOSED'
                  ? '<span class="rounded-lg bg-slate-800 px-2.5 py-1 text-[10px] font-bold text-slate-400">Погашена</span>'
                  : `<button class="bankrupt-bond-btn rounded-lg bg-rose-700 px-2.5 py-1 text-[10px] font-bold text-white hover:bg-rose-600" data-id="${Number(b.id)}">Банкрот</button>`}
            </div>
          </div>
        `).join('')}
      </div>
    </div>
  `;

  const issueBtn = el.querySelector('#issue-bond-btn');
  if (issueBtn) {
    issueBtn.addEventListener('click', async () => {
      const title = el.querySelector('#bond-title').value.trim();
      const vol = parseInt(el.querySelector('#bond-vol').value, 10);
      const face = parseFloat(el.querySelector('#bond-face').value);
      const rate = parseFloat(el.querySelector('#bond-rate').value);
      const days = parseInt(el.querySelector('#bond-days').value, 10);
      const purpose = el.querySelector('#bond-purpose').value.trim();

      if (!title || !vol || !face || !days || !purpose) {
        return showToast('Заполните все поля эмиссии', 'error');
      }

      if (!confirm(`Выпустить ${vol} облигаций «${title}» по ${face} cash? Выпуск сам по себе не создаёт деньги.`)) return;
      try {
        await NatAPI.issueCreatorBonds({
          title, volume: vol, face_value: face, coupon_rate: rate || 0, maturity_days: days, purpose
        });
        showToast(`Облигации «${title}» выпущены. Казна пополняется только при фактической покупке.`, 'success');
        await loadBondsTab(el, showToast);
      } catch (e) {
        showToast(e.message, 'error');
      }
    });
  }

  el.querySelectorAll('.bankrupt-bond-btn').forEach(button => {
    button.addEventListener('click', async () => {
      const bond = data.bonds.find(row => Number(row.id) === Number(button.dataset.id));
      if (!bond) return;
      const confirmed = confirm(
        `Объявить выпуск «${bond.title}» банкротом? Каждый текущий держатель получит 30% номинала за облигацию, 70% основного долга будет списано. Будущие купоны и погашение прекратятся.`
      );
      if (!confirmed) return;
      button.disabled = true;
      try {
        const result = await declareCreatorBondBankruptcy(bond.id);
        showToast(
          `Банкротство объявлено: выплачено ${Number(result.compensation_paid).toLocaleString('ru-RU')} cash; списано ${Number(result.principal_written_off).toLocaleString('ru-RU')} cash.`,
          'success',
        );
        await loadBondsTab(el, showToast);
      } catch (error) {
        showToast(error.message, 'error');
        button.disabled = false;
      }
    });
  });
}

async function loadTournamentsTab(el, showToast) {
  el.innerHTML = `
    <div class="glass-card rounded-2xl p-4 space-y-3">
      <div class="text-xs font-bold text-amber-400 uppercase">Управление Турнирами 11 «Б»</div>
      <p class="text-[11px] text-slate-400">
        Обычный цикл: старт раз в 72 часа, длительность 18 часов. Здесь можно запустить отдельный турнир с собственным призовым фондом PVC.
      </p>
      <div class="grid grid-cols-3 gap-2">
        <label class="text-[10px] text-amber-300">🥇 1 место
          <input id="tourn-reward-first" type="number" inputmode="numeric" min="0" max="10000" step="1" value="150" class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-2 py-2 text-sm text-white outline-none focus:border-amber-400">
        </label>
        <label class="text-[10px] text-slate-300">🥈 2 место
          <input id="tourn-reward-second" type="number" inputmode="numeric" min="0" max="10000" step="1" value="100" class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-2 py-2 text-sm text-white outline-none focus:border-amber-400">
        </label>
        <label class="text-[10px] text-orange-300">🥉 3 место
          <input id="tourn-reward-third" type="number" inputmode="numeric" min="0" max="10000" step="1" value="70" class="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-2 py-2 text-sm text-white outline-none focus:border-amber-400">
        </label>
      </div>
      <p class="text-[10px] text-slate-500">Награды выдаются в Pivocoins (PVC). Допустимо от 0 до 10 000 PVC за место.</p>
      <button id="launch-tourn-btn" class="w-full py-3 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-black text-xs transition-all shadow-lg shadow-amber-500/20">
        ⚔️ Запустить кастомный турнир на 18 часов
      </button>
    </div>
  `;

  const btn = el.querySelector('#launch-tourn-btn');
  if (btn) {
    btn.addEventListener('click', async () => {
      const rewards = [
        Number(el.querySelector('#tourn-reward-first')?.value),
        Number(el.querySelector('#tourn-reward-second')?.value),
        Number(el.querySelector('#tourn-reward-third')?.value),
      ];
      if (!rewards.every(value => Number.isInteger(value) && value >= 0 && value <= 10000)) {
        showToast('Укажите целые призы от 0 до 10 000 PVC.', 'error');
        return;
      }
      if (!confirm(`Запустить 18-часовой турнир с наградами ${rewards[0]} / ${rewards[1]} / ${rewards[2]} PVC?`)) return;
      try {
        const res = await NatAPI.launchCreatorTournament({
          reward_first_pvc: rewards[0],
          reward_second_pvc: rewards[1],
          reward_third_pvc: rewards[2],
        });
        showToast(`Турнир №${res.number} запущен на 18 часов.`, 'success');
        btn.disabled = true;
        btn.textContent = 'Турнир запущен';
      } catch (e) {
        showToast(e.message, 'error');
      }
    });
  }
}

async function loadAuditTab(el, showToast) {
  const data = await NatAPI.getCreatorAuditLog();
  el.innerHTML = `
    <div class="glass-card rounded-2xl p-3 space-y-2">
      <div class="text-xs font-bold text-slate-300">Журнал действий Администратора (${data.logs.length})</div>
      <div class="space-y-1.5 max-h-96 overflow-y-auto">
        ${data.logs.map(l => `
          <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-2 text-[10px]">
            <div class="flex justify-between font-mono">
              <span class="text-amber-400 font-bold">${l.action}</span>
              <span class="text-slate-500">${new Date(l.created_at).toLocaleTimeString('ru-RU')}</span>
            </div>
            <div class="text-slate-300 mt-0.5">${l.details || ''}</div>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}
