const tg = window.Telegram?.WebApp;

if (tg) {
  tg.ready();
  tg.expand();
  // Enable closing confirmation
  if (tg.enableClosingConfirmation) {
    tg.enableClosingConfirmation();
  }
}

/**
 * Ждёт инициализации Telegram WebApp SDK до 1500 мс.
 * Нужно вызывать перед первым getTelegramUserId(),
 * чтобы избежать ситуации когда SDK ещё не загружен (async script).
 */
function waitForTelegramWebApp(timeoutMs = 1500) {
  return new Promise((resolve) => {
    if (window.Telegram?.WebApp?.initDataUnsafe?.user) {
      return resolve();
    }
    const start = Date.now();
    const check = () => {
      if (window.Telegram?.WebApp?.initDataUnsafe?.user || Date.now() - start >= timeoutMs) {
        resolve();
      } else {
        setTimeout(check, 50);
      }
    };
    setTimeout(check, 50);
  });
}
window.waitForTelegramWebApp = waitForTelegramWebApp;


// Haptic feedback helper
const haptic = {
  impact: (style = "light") => {
    if (tg?.HapticFeedback) {
      tg.HapticFeedback.impactOccurred(style);
    }
  },
  notification: (type = "success") => {
    if (tg?.HapticFeedback) {
      tg.HapticFeedback.notificationOccurred(type);
    }
  },
  selection: () => {
    if (tg?.HapticFeedback) {
      tg.HapticFeedback.selectionChanged();
    }
  }
};
