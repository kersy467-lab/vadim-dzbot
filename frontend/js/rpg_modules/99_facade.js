  window.RPG = {
    init: initRPG,
    setSubTab: setSubTab,
    setFarmMode: setFarmMode,
    loadProfile: loadProfile,
    selectHero: selectHero,
    openHeroPicker: () => {
      if (RPG_STATE.profile) RPG_STATE.profile.hero_class = null;
      renderRoot();
    },
    upgradeStat: upgradeStat,
    openItemModal: openItemModal,
    closeItemModal: closeItemModal,
    equipItem: equipItem,
    unequipItem: unequipItem,
    useConsumable: useConsumable,
    openShopModal: openShopModal,
    closeShopModal: closeShopModal,
    reloadShopCatalog: reloadShopCatalog,
    setShopFilter: setShopFilter,
    buyShopItem: buyShopItem,
    openSlotFilterModal: openSlotFilterModal,
    closeSlotFilterModal: closeSlotFilterModal,
    openForge: (uid) => {
      if (uid && typeof uid === 'string') {
        openForge(uid);
      } else {
        const p = RPG_STATE.profile;
        const eq = p?.equipment || {};
        const firstItem = eq.slot_1 || eq.slot_2 || eq.slot_3 || eq.slot_4 || eq.slot_5 || eq.slot_6;
        if (firstItem) openForge(firstItem.uid);
        else alert("Сначала наденьте предмет или выберите его из инвентаря!");
      }
    },
    closeForgeModal: closeForgeModal,
    forgeCurrentItem: forgeCurrentItem,
    sellItem: sellItem,
    toggleItemSelection: toggleItemSelection,
    toggleItemSelectionMode: toggleItemSelectionMode,
    handleInventoryItemClick: handleInventoryItemClick,
    selectAllByRarity: selectAllByRarity,
    clearItemSelection: clearItemSelection,
    sellSelectedItems: sellSelectedItems,
    resetCharacter: resetCharacter,
    slashWave: slashWave,
    toggleAutoFarm: toggleAutoFarm,
    toggleBossPartyMode: toggleBossPartyMode,
    bossArenaDodgeAction: playerBossArenaDodge,
    // Admin Dev Panel
    toggleAdminModal: toggleAdminModal,
    switchAdminTestAccount: switchAdminTestAccount,
    createCustomAdminTestAccount: createCustomAdminTestAccount,
    resetCurrentTestAccount: resetCurrentTestAccount,
    // Chest Modal
    claimChestReward: claimChestReward,
    closeChestModal: closeChestModal,
    // Arena Controls
    playerSlashAttackAction: playerSlashAttack,
    castSkill1Action: castPlayerSkill1,
    castUltimateAction: castPlayerUltimate,
    useActiveItemAction: useActiveItemAction,
    getEquippedActiveItems: getEquippedActiveItems,
    usePotionAction: usePlayerPotion,
    playerDashAction: () => playerPerformDash(),
    playerBlockAction: playerBlock,
    hitQTEAction: hitQTE,
    confirmNextWaveAction: confirmNextWave,
    retryCurrentFloorAction: retryCurrentFloor,
    toggleArenaAutoAttack: () => {
      ARENA.player.autoAttack = !ARENA.player.autoAttack;
      const btn = document.getElementById("rpg-auto-attack-btn");
      if (btn) {
        btn.innerText = `Авто-удар: ${ARENA.player.autoAttack ? "ВКЛ" : "ВЫКЛ"}`;
        if (ARENA.player.autoAttack) {
          btn.className = "px-2.5 py-1 rounded-xl text-xs font-black transition-all bg-amber-500/20 text-amber-500 border border-amber-500/40";
        } else {
          btn.className = "px-2.5 py-1 rounded-xl text-xs font-black transition-all bg-slate-200 dark:bg-slate-700 text-slate-500";
        }
      }
      triggerHaptic("light");
    },
    playerDashRollAction: () => {
      playerPerformDashRoll();
    },
    toggleTopDownArenaMode: () => {
      toggleTopDownArenaMode();
    },
    toggleArenaWaveConfirm: () => {
      ARENA.autoAdvanceWaves = !ARENA.autoAdvanceWaves;
      try {
        localStorage.setItem("rpg_arena_auto_advance_waves", ARENA.autoAdvanceWaves ? "true" : "false");
      } catch (e) {}
      const btn = document.getElementById("rpg-wave-confirm-btn");
      if (btn) {
        btn.innerText = `Подтверждение волн: ${ARENA.autoAdvanceWaves ? "ВЫКЛ ⏩" : "ВКЛ ⏸️"}`;
        if (ARENA.autoAdvanceWaves) {
          btn.className = "px-2.5 py-1 rounded-xl text-xs font-black transition-all bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-sm";
          btn.title = "Подтверждение волн отключено: переход к следующей волне происходит автоматически";
        } else {
          btn.className = "px-2.5 py-1 rounded-xl text-xs font-black transition-all bg-slate-200 dark:bg-slate-700 text-slate-500";
          btn.title = "Подтверждение волн включено: требуется нажимать продолжить";
        }
      }
      triggerHaptic("light");
      if (ARENA.autoAdvanceWaves && ARENA.waveState === "prompt" && !RPG_STATE.activeChestModal) {
        confirmNextWave();
      }
    },
    // Co-op
    loadCoopBosses: loadCoopBosses,
    createCoopRaid: createCoopRaid,
    joinCoopRoom: joinCoopRoom,
    sendCoopAction: sendCoopAction,
    leaveCoopRoom: leaveCoopRoom,
    addCoopBot: addCoopBot,
    startRaidBossActionBattle: startRaidBossActionBattle,
    exitRaidBossBattle: exitRaidBossBattle,
    // PvP
    loadClassmates: loadClassmates,
    challengeClassmate: challengeClassmate,
    sendPvPAction: sendPvPAction,
    leavePvPRoom: leavePvPRoom,
    renderRoot: renderRoot
  };
})();
