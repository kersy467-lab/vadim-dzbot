const CHECK_INTERVAL_MS = 60_000;
const dismissedCompanies = new Set();

let activeOverlay = null;
let monitorTimer = null;

function dismissedKey(companyId) {
  return `natbirzha:bankruptcy-dismissed:${companyId}`;
}

function isDismissed(companyId) {
  if (dismissedCompanies.has(String(companyId))) return true;
  try {
    return window.localStorage.getItem(dismissedKey(companyId)) === '1';
  } catch (_) {
    return false;
  }
}

function markDismissed(companyId) {
  dismissedCompanies.add(String(companyId));
  try {
    window.localStorage.setItem(dismissedKey(companyId), '1');
  } catch (_) {}
}

function clearDismissed(companyId) {
  dismissedCompanies.delete(String(companyId));
  try {
    window.localStorage.removeItem(dismissedKey(companyId));
  } catch (_) {}
}

function closeOverlay() {
  if (!activeOverlay) return;
  activeOverlay.remove();
  activeOverlay = null;
  document.body.style.overflow = '';
}

function createOverlay({ companyId, companyName, status, api, store, showToast, onRestart }) {
  const overlay = document.createElement('section');
  overlay.className = 'fixed inset-0 z-[100000] grid place-items-center overflow-y-auto bg-[#f5f5ee] p-5 text-slate-900';
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');
  overlay.setAttribute('aria-labelledby', 'bankruptcy-title');
  overlay.dataset.companyId = String(companyId);
  overlay.innerHTML = `
    <div class="w-full max-w-md overflow-hidden rounded-[2rem] border border-emerald-950/10 bg-white shadow-2xl">
      <div class="bg-gradient-to-br from-emerald-950 via-emerald-900 to-emerald-700 px-6 py-8 text-center text-white">
        <div class="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-2xl border border-white/20 bg-white/10 text-4xl font-black" aria-hidden="true">!</div>
        <p class="text-xs font-bold uppercase tracking-[0.24em] text-emerald-100">НАТБИРЖА · решение по компании</p>
        <h1 id="bankruptcy-title" class="mt-3 text-3xl font-black tracking-tight">ВЫ БАНКРОТ</h1>
        <p class="bankruptcy-company mt-2 text-sm font-semibold text-emerald-50"></p>
      </div>
      <div class="space-y-4 p-5 sm:p-6">
        <p class="bankruptcy-description text-center text-sm leading-6 text-slate-600"></p>
        <button type="button" class="bankruptcy-restart w-full rounded-2xl bg-emerald-800 px-4 py-4 text-left text-white shadow-lg transition hover:bg-emerald-900 disabled:cursor-wait disabled:opacity-60">
          <span class="block text-base font-black">Начать заново</span>
          <span class="bankruptcy-grant mt-1 block text-xs font-semibold text-emerald-100">+100 000 cash на новый баланс</span>
        </button>
        <button type="button" class="bankruptcy-continue w-full rounded-2xl border border-emerald-900/15 bg-[#f0f4ed] px-4 py-4 text-left text-emerald-950 transition hover:bg-[#e6eee4]">
          <span class="block text-base font-black">Продолжить</span>
          <span class="bankruptcy-continue-note mt-1 block text-xs leading-5 text-slate-600"></span>
        </button>
        <p class="bankruptcy-error min-h-5 text-center text-xs font-semibold text-rose-700" role="status" aria-live="polite"></p>
      </div>
    </div>`;

  overlay.querySelector('.bankruptcy-company').textContent = companyName || 'Ваша компания';
  overlay.querySelector('.bankruptcy-description').textContent = status.assets_liquidated
    ? 'Имущество уже списано по процедуре банкротства. Выберите: продолжить с тем, что осталось, или начать новую компанию.'
    : 'Для компании начата процедура реструктуризации. Выберите, продолжать её или начать заново.';
  overlay.querySelector('.bankruptcy-continue-note').textContent = status.assets_liquidated
    ? 'Имущество уже вычтено — продолжите с оставшимися активами.'
    : 'Продолжите игру с текущими условиями реструктуризации.';

  const restartButton = overlay.querySelector('.bankruptcy-restart');
  const continueButton = overlay.querySelector('.bankruptcy-continue');
  const errorNode = overlay.querySelector('.bankruptcy-error');

  continueButton.addEventListener('click', () => {
    markDismissed(companyId);
    closeOverlay();
  });

  restartButton.addEventListener('click', async () => {
    restartButton.disabled = true;
    continueButton.disabled = true;
    restartButton.querySelector('.bankruptcy-grant').textContent = 'Создаём новую компанию…';
    errorNode.textContent = '';
    try {
      const result = await api.restartBankruptCompany();
      let freshCompany = null;
      try {
        freshCompany = await api.getMyCompany();
      } catch (_) {}
      const company = freshCompany || result.company;
      if (!company?.id && !company?.company_id) {
        throw new Error('Компания создана, но не удалось загрузить её данные. Обновите игру.');
      }
      store.setCompany(company);
      clearDismissed(companyId);
      closeOverlay();
      await onRestart?.(company);
      showToast?.(`Новая компания создана. На баланс добавлено ${Number(result.cash_grant || 100_000).toLocaleString('ru-RU')} cash.`, 'success');
    } catch (error) {
      errorNode.textContent = error?.message || 'Не удалось начать заново. Попробуйте ещё раз.';
      restartButton.disabled = false;
      continueButton.disabled = false;
      restartButton.querySelector('.bankruptcy-grant').textContent = '+100 000 cash на новый баланс';
      showToast?.(errorNode.textContent, 'error');
    }
  });

  document.body.style.overflow = 'hidden';
  document.body.appendChild(overlay);
  return overlay;
}

async function checkBankruptcy({ api, store, showToast, onRestart }) {
  if (!store.hasCompany()) return;
  const company = store.company;
  const companyId = company?.id || company?.company_id;
  if (!companyId) return;

  try {
    const status = await api.getBankruptcyStatus();
    if (!status?.is_bankrupt) {
      clearDismissed(companyId);
      if (activeOverlay?.dataset.companyId === String(companyId)) closeOverlay();
      return;
    }
    if (isDismissed(companyId) || activeOverlay?.dataset.companyId === String(companyId)) return;
    activeOverlay = createOverlay({
      companyId,
      companyName: company.name,
      status,
      api,
      store,
      showToast,
      onRestart,
    });
  } catch (_) {
    // A status check must never block the game if the bankruptcy service is unavailable.
  }
}

export async function startBankruptcyMonitor(options) {
  if (monitorTimer) window.clearInterval(monitorTimer);
  await checkBankruptcy(options);
  monitorTimer = window.setInterval(() => {
    if (document.visibilityState === 'visible') void checkBankruptcy(options);
  }, CHECK_INTERVAL_MS);
}
