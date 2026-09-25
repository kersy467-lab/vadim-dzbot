/**
 * Maintenance Banner Module for Natbirzha
 * Displays a prominent technical break banner for regular players when maintenance mode is active.
 * Automatically hidden for admins and state creators.
 */

export function updateMaintenanceBanner(isMaintenanceActive, isCreatorOrAdmin) {
  const root = document.getElementById('maintenance-banner-root');
  if (!root) return;

  const shouldShow = Boolean(isMaintenanceActive) && !Boolean(isCreatorOrAdmin);

  if (shouldShow) {
    root.innerHTML = `
      <div id="natbirzha-maint-banner" class="p-3 rounded-2xl bg-gradient-to-r from-amber-500/20 via-orange-500/20 to-amber-500/20 border-2 border-amber-500/70 shadow-lg shadow-amber-500/10 flex items-center gap-3">
        <div class="text-2xl flex-shrink-0 animate-bounce">⚠️</div>
        <div class="flex-1 min-w-0">
          <div class="text-xs font-black uppercase tracking-wider text-amber-400 flex items-center gap-1.5">
            <span>Технический перерыв</span>
            <span class="inline-block w-2 h-2 rounded-full bg-amber-400 animate-ping"></span>
          </div>
          <div class="text-[11px] text-amber-200/90 leading-tight mt-0.5">
            На сервере ведутся технические работы. Некоторые функции могут быть временно ограничены или обновляться.
          </div>
        </div>
      </div>
    `;
    root.classList.remove('hidden');
  } else {
    root.innerHTML = '';
    root.classList.add('hidden');
  }
}
