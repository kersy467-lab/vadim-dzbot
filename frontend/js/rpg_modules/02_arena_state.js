  const ARENA = {
    canvas: null,
    ctx: null,
    animId: null,
    width: 360,
    height: 320,
    running: false,

    // Landscape
    roadY: 225,

    // Player Entity (STATIONARY — no movement!)
    player: {
      x: 65,
      y: 200,
      radius: 20,
      currentHp: 200,
      maxHp: 200,
      currentMp: 60,
      maxMp: 60,
      attackCooldown: 0,
      attackQueued: false,
      attackRange: 270,
      isRanged: false,
      slashAnimation: null,
      autoAttack: true,
      // Active skill timers
      fleshHeapActive: 0,      // Pudge -40% damage
      bladeDanceActive: 0,     // Juggernaut +50% attack speed
      rotActive: 0,            // Pudge rot poison
      counterspellActive: 0    // Anti-Mage shield
    },

    // Cooldowns
    skill1Cooldown: 0,
    skill1CooldownMax: 480, // default 8s
    ultCooldown: 0,
    ultCooldownMax: 900,    // default 15s

    // Projectiles & Minions
    playerProjectiles: [],
    alliedMinions: [],
    specialEffects: [],

    // Creeps (come from right only)
    creeps: [],
    creepSpawnTimer: 0,
    totalCreepsSpawned: 0,
    waveNumber: 1,
    waveMax: 20, // Boss every 20 waves
    creepsKilledInWave: 0,
    creepsNeededForWave: 5,

    // Boss
    isBossActive: false,
    bossEntity: null,
    bossPhase: 0,
    bossSpecialTimer: 0,
    bossProjectiles: [],
    bossPartyMode: (() => {
      try {
        return localStorage.getItem("rpg_boss_party_mode") || "trio";
      } catch (e) {
        return "trio";
      }
    })(),
    bossCompanions: [],
    _partyBtnBounds: null,

    // Boss Arena 2D Combat Mode (free player movement)
    bossArenaMode: false,
    moveInput: { left: false, right: false },
    dodgeCooldown: 0,
    potionCooldown: 0,
    dodgeActive: 0,      // frames remaining of dodge i-frame
    dodgeDir: 1,          // direction of dodge roll
    dangerZones: [],
    joystick: { active: false, touchId: null, baseX: 0, baseY: 0, curX: 0, curY: 0, dx: 0, dy: 0, power: 0 },
    topDownMode: false,
    dashGhosts: [],
    keysPressed: {},      // boss attack telegraphs on arena floor
    bossAttackPattern: null, // current boss attack being executed
    bossPatternTimer: 0,     // timer for current pattern phase
    bossPatternPhase: "idle", // idle | telegraph | execute | recover
    _touchMoveId: null,   // active touch for movement

    // Boss interaction windows & Polish
    blockWindowActive: false,
    blockWindowTimer: 0,
    blockWindowMax: 120,
    qteActive: false,
    qteTimer: 0,
    qteMaxTimer: 90,

    // Wave Combat & Style Engine (Hades / DMC)
    enemyProjectiles: [],
    dashGhosts: [],
    combo: { count: 0, timer: 0, step: 0, maxCombo: 0 },
    styleMeter: { score: 0, rank: "D", progress: 0, decayTimer: 0, maxRank: "D" },

    // Advanced Boss Combat Engine (Sekiro/Hollow Knight/Dota 2)
    cameraTrauma: 0,
    hitstop: 0,
    parryWindow: 0,
    shockwaves: [],
    telegraphs: [],
    physicalCoins: [],
    fallingChest: null,

    // Hero Talent Perks State
    pudgeUndyingUsed: false,
    pudgeHitCounter: 0,
    wkReincarnationUsed: false,
    sfSouls: 0,
    blinkReflexCd: 0,

    // Wave state machine
    // 'fighting' | 'wave_clear' | 'prompt' | 'boss_intro' | 'floor_clear' | 'retry_prompt'
    waveState: "fighting",
    waveTransitionTimer: 0,
    _promptBtnBounds: null,
    _promptDisableBtnBounds: null,
    autoAdvanceWaves: (() => {
      try {
        const val = localStorage.getItem("rpg_arena_auto_advance_waves");
        return val !== null ? val === "true" : true;
      } catch (e) {
        return true;
      }
    })(),

    // Effects & Pickups
    floatingTexts: [],
    pickups: [],

    // Background
    clouds: [],
    bgInit: false
  };

  // ---------------------------------------------------------------------------
  // DOTA 2 HERO SKILL CONFIGS
  // ---------------------------------------------------------------------------

  function getHeroSkillConfig() {
    const hClass = (RPG_STATE.profile?.hero_class || "pudge").toLowerCase();
    const configs = {
      invoker: {
        isRanged: true,
        attackRange: 380,
        skill1Name: "Санстрайк",
        skill1Icon: "☀️",
        skill1Cd: 420, // 7 sec
        skill1Desc: "Ослепительный луч солнца бьет с неба, нанося чистый урон и ломая щиты!",
        ultName: "Хаос Метеор (Котлета)",
        ultIcon: "☄️",
        ultCd: 840, // 14 sec
        ultDesc: "С неба обрушивается пылающий метеор («котлета»), катится по всей линии и сжигает всё на пути!"
      },
      pudge: {
        isRanged: false,
        attackRange: 270,
        skill1Name: "Защитная Плоть",
        skill1Icon: "🥩",
        skill1Cd: 840, // 14 sec
        skill1Desc: "Блокирует 40% всего входящего урона на 8 секунд!",
        ultName: "Чумная Гниль",
        ultIcon: "☣️",
        ultCd: 720, // 12 sec
        ultDesc: "Вонь на всю карту 2.5 сек, наносящая урон всем крипам!"
      },
      juggernaut: {
        isRanged: false,
        attackRange: 275,
        skill1Name: "Танец Клинка",
        skill1Icon: "💨",
        skill1Cd: 600, // 10 sec
        skill1Desc: "Увеличивает скорость атаки на +50% на 6 секунд!",
        ultName: "Омнислеш",
        ultIcon: "⚔️",
        ultCd: 900, // 15 sec
        ultDesc: "Вихрь рассекающих ударов по всей карте!"
      },
      phantom_assassin: {
        isRanged: false,
        attackRange: 270,
        skill1Name: "Кинжал Тени",
        skill1Icon: "🗡️",
        skill1Cd: 360, // 6 sec
        skill1Desc: "Бросок отравленного кинжала с критом и замедлением!",
        ultName: "Coup de Grace",
        ultIcon: "🩸",
        ultCd: 720, // 12 sec
        ultDesc: "Сокрушительный выпад с критическим уроном x5.0!"
      },
      shadow_fiend: {
        isRanged: true,
        attackRange: 360,
        skill1Name: "Тройной Койл",
        skill1Icon: "🌑",
        skill1Cd: 420, // 7 sec
        skill1Desc: "Три мощных взрыва душ в ряд перед собой!",
        ultName: "Реквием Душ",
        ultIcon: "🌪️",
        ultCd: 960, // 16 sec
        ultDesc: "Адские волны темных душ во все стороны!"
      },
      wraith_king: {
        isRanged: false,
        attackRange: 280,
        skill1Name: "Огненный Стан",
        skill1Icon: "💀",
        skill1Cd: 480, // 8 sec
        skill1Desc: "Огненный череп оглушает крипов по площади!",
        ultName: "Армия Скелетов",
        ultIcon: "👑",
        ultCd: 960, // 16 sec
        ultDesc: "Призывает отряд скелетов-воинов + 100% вампиризм!"
      },
      anti_mage: {
        isRanged: false,
        attackRange: 270,
        skill1Name: "Щит Магии",
        skill1Icon: "🛡️",
        skill1Cd: 420, // 7 sec
        skill1Desc: "Магический щит отражения + мгновенный выпад!",
        ultName: "Взрыв Маны",
        ultIcon: "💥",
        ultCd: 840, // 14 sec
        ultDesc: "Колоссальный взрыв маны по скоплению врагов!"
      },
      leshrac: {
        isRanged: true,
        attackRange: 450,
        skill1Name: "Кваканье Гения",
        skill1Icon: "🎵",
        skill1Cd: 420, // 7 sec
        skill1Desc: "3-й скилл Ларго: -60% расхода маны + эхо-реверберация урона!",
        ultName: "Рапсодия",
        ultIcon: "🐸",
        ultCd: 30, // 0.5s toggle debounce
        ultDesc: "Вкл/Выкл: длится бесконечно! Каждые 2 сек тратит ману, наносит урон всем вокруг и хилит Ларго!"
      }
    };
    return configs[hClass] || configs.pudge;
  }

  // ---------------------------------------------------------------------------
  // INITIALIZATION
  // ---------------------------------------------------------------------------

  function bindArenaCanvas(canvas) {
    if (!canvas) canvas = document.getElementById("rpg-action-canvas");
    if (!canvas) return;

    // If canvas has no rendered size yet (DOM not laid out), defer until next frame
    const earlyRect = canvas.getBoundingClientRect();
    if (earlyRect.width < 10 && canvas.clientWidth < 10) {
      requestAnimationFrame(() => bindArenaCanvas(canvas));
      return;
    }

    ARENA.canvas = canvas;
    ARENA.ctx = canvas.getContext("2d");
    if (ARENA.ctx) {
      const h = ARENA.height || 320;
      ARENA.cachedSkyGrad = ARENA.ctx.createLinearGradient(0, -24, 0, h * 0.55);
      ARENA.cachedSkyGrad.addColorStop(0, "#2563eb");
      ARENA.cachedSkyGrad.addColorStop(1, "#93c5fd");
      ARENA.cachedGroundGrad = ARENA.ctx.createLinearGradient(0, h * 0.55 - 4, 0, h + 24);
      ARENA.cachedGroundGrad.addColorStop(0, "#16a34a");
      ARENA.cachedGroundGrad.addColorStop(0.4, "#15803d");
      ARENA.cachedGroundGrad.addColorStop(1, "#14532d");
    }

    const rect = canvas.getBoundingClientRect();
    const dpr = Math.min(2, (typeof window !== "undefined" && window.devicePixelRatio && window.devicePixelRatio > 0) ? window.devicePixelRatio : 1);
    const isTopDown = !!(ARENA.topDownMode || ARENA.isRaidBossBattle);
    const clientW = canvas.clientWidth > 50 ? canvas.clientWidth : (rect.width > 50 ? rect.width : 360);
    const clientH = isTopDown ? 520 : (canvas.clientHeight > 50 ? canvas.clientHeight : (rect.height > 50 ? rect.height : 320));
    // In Top-Down Brawl mode, arena logical space is a spacious 520x720 battlefield!
    ARENA.cachedClientW = clientW;
    ARENA.cachedClientH = clientH;
    ARENA.dpr = dpr;
    ARENA.width = isTopDown ? 520 : clientW;
    ARENA.height = isTopDown ? 720 : clientH;
    canvas.width = Math.round(clientW * dpr);
    canvas.height = Math.round(clientH * dpr);
    if (ARENA.ctx) {
      ARENA.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    setupArenaListeners(canvas);
    bindVirtualJoystick();
  }

  function initArenaCanvas() {
    const canvas = document.getElementById("rpg-action-canvas");
    if (!canvas) return;
    bindArenaCanvas(canvas);

    // CRITICAL: NEVER wipe out an active Boss Battle (Raid or Dungeon)!
    if (ARENA.isRaidBossBattle || (ARENA.isBossActive && ARENA.bossEntity)) {
      if (ARENA.bossEntity && !ARENA.creeps.includes(ARENA.bossEntity)) {
        ARENA.creeps = [ARENA.bossEntity];
      }
      ARENA.isBossActive = true;
      return;
    }

    const p = RPG_STATE.profile;
    const stats = p?.stats || {};
    const skillCfg = getHeroSkillConfig();

    ARENA.player.x = 65;
    ARENA.player.y = ARENA.roadY - 18;
    ARENA.player.radius = 20;
    ARENA.player.maxHp = Math.max(450, stats.hp_max || 450);
    ARENA.player.currentHp = ARENA.player.maxHp;
    ARENA.player.maxMp = Math.max(80, stats.mp_max || 80);
    ARENA.player.currentMp = ARENA.player.maxMp;
    ARENA.player.isRanged = skillCfg.isRanged;
    ARENA.player.attackRange = skillCfg.attackRange;
    ARENA.player.fleshHeapActive = 0;
    ARENA.player.bladeDanceActive = 0;
    ARENA.player.rotActive = 0;
    ARENA.player.counterspellActive = 0;
    ARENA.player.largoRhapsodyActive = false;
    ARENA.player.largoRhapsodyTickTimer = 0;

    ARENA.skill1Cooldown = 0;
    ARENA.skill1CooldownMax = skillCfg.skill1Cd;
    ARENA.ultCooldown = 0;
    ARENA.ultCooldownMax = skillCfg.ultCd;

    ARENA.creeps = [];
    ARENA.pickups = [];
    ARENA.floatingTexts = [];
    ARENA.bossProjectiles = [];
    ARENA.playerProjectiles = [];
    ARENA.alliedMinions = [];
    ARENA.specialEffects = [];

    // Always synchronize active wave with database progress from profile
    const currentSavedWave = ((RPG_STATE.profile?.dungeon_cleared || 0) % 20) + 1;
    if (!ARENA.waveNumber || ARENA.waveNumber < 1 || ARENA.waveNumber !== currentSavedWave) {
      ARENA.waveNumber = currentSavedWave;
    }
    ARENA.waveMax = 20;
    ARENA.creepsKilledInWave = 0;
    ARENA.totalCreepsSpawned = 0;
    ARENA.creepsNeededForWave = Math.min(32, 14 + Math.floor((ARENA.waveNumber - 1) * 1.0));
    ARENA.isBossActive = false;
    ARENA.bossEntity = null;
    ARENA.bossPhase = 0;
    ARENA.bossCompanions = [];
    ARENA._partyBtnBounds = null;
    ARENA.bossArenaMode = false;
    ARENA.moveInput = { left: false, right: false };
    ARENA.dodgeCooldown = 0;
    ARENA.potionCooldown = 0;
    ARENA.dodgeActive = 0;
    ARENA.dodgeDir = 1;
    ARENA.dangerZones = [];
    ARENA.bossAttackPattern = null;
    ARENA.bossPatternTimer = 0;
    ARENA.bossPatternPhase = "idle";
    ARENA._touchMoveId = null;
    ARENA.waveState = "fighting";
    ARENA.blockWindowActive = false;
    ARENA.qteActive = false;
    ARENA.cameraTrauma = 0;
    ARENA.hitstop = 0;
    ARENA.parryWindow = 0;
    ARENA.shockwaves = [];
    ARENA.telegraphs = [];
    ARENA.physicalCoins = [];
    ARENA.fallingChest = null;
    ARENA._promptBtnBounds = null;
    ARENA.enemyProjectiles = [];
    ARENA.dashGhosts = [];
    ARENA.combo = { count: 0, timer: 0, step: 0, maxCombo: 0 };
    ARENA.styleMeter = { score: 0, rank: "D", progress: 0, decayTimer: 0, maxRank: "D" };
    ARENA.player.isDashing = false;
    ARENA.player.dashCooldown = 0;
    ARENA.player.isInvulnerable = 0;
    ARENA.player.critBuff = false;
    ARENA.player.isBlocking = 0;

    // Reset perk battle counters
    ARENA.pudgeUndyingUsed = false;
    ARENA.pudgeHitCounter = 0;
    ARENA.wkReincarnationUsed = false;
    ARENA.sfSouls = 0;
    ARENA.blinkReflexCd = 0;

    if (!ARENA.bgInit) {
      ARENA.clouds = [];
      for (let i = 0; i < 5; i++) {
        ARENA.clouds.push({
          x: Math.random() * ARENA.width,
          y: 18 + Math.random() * 45,
          speed: 0.12 + Math.random() * 0.18
        });
      }
      ARENA.bgInit = true;
    }
  }

  function hasTalentPerk(perkId) {
    const perks = RPG_STATE.profile?.stats?.perks;
    return Array.isArray(perks) && perks.includes(perkId);
  }
  window.hasTalentPerk = hasTalentPerk;


  // ===========================================================================
  // ARCHERO-STYLE TOP-DOWN JOYSTICK & STUTTER-STEP SYSTEM
  // ===========================================================================

  function playerPerformDashRoll() {
    const p = ARENA.player;
    if (ARENA.dodgeCooldown > 0) return;

    let dirX = ARENA.joystick.dx;
    let dirY = ARENA.joystick.dy;

    // If standing still, dash in current facing direction
    if (Math.abs(dirX) < 0.05 && Math.abs(dirY) < 0.05) {
      const fa = p.facingAngle !== undefined ? p.facingAngle : (p.facing === -1 ? Math.PI : 0);
      dirX = Math.cos(fa);
      dirY = Math.sin(fa);
    }
    const mag = Math.hypot(dirX, dirY) || 1;
    dirX /= mag;
    dirY /= mag;

    const dashDist = 88;
    p.x = Math.max(28, Math.min(ARENA.width - 28, p.x + dirX * dashDist));
    p.y = Math.max(38, Math.min(ARENA.height - 38, p.y + dirY * dashDist));

    p.isInvulnerable = 26; // 26 frames of invincibility (~430ms)
    ARENA.dodgeCooldown = 90; // 1.5s cooldown

    if (!ARENA.dashGhosts) ARENA.dashGhosts = [];
    const hClass = (RPG_STATE.profile?.hero_class || "pudge").toLowerCase();
    for (let g = 0; g < 4; g++) {
      ARENA.dashGhosts.push({
        x: p.x - dirX * (g * 22),
        y: p.y - dirY * (g * 22),
        radius: p.radius || 22,
        alpha: 0.65 - g * 0.14,
        heroClass: hClass
      });
    }

    spawnFloatingText(p.x, p.y - 25, "🌀 РЫВОК! (I-FRAMES)", "#38bdf8");
    triggerHaptic("heavy");
  }

  function toggleTopDownArenaMode() {
    ARENA.topDownMode = !ARENA.topDownMode;
    const canvas = document.getElementById("rpg-action-canvas");
    if (canvas) {
      bindArenaCanvas(canvas);
    }
    renderRoot();
  }

  function bindVirtualJoystick() {
    const zone = document.getElementById("rpg-virtual-joystick-zone");
    const knob = document.getElementById("rpg-joystick-knob");
    if (!zone || !knob) return;

    const maxRadius = 46;
    const deadzone = 12;

    function handleStart(clientX, clientY, touchId) {
      ARENA.joystick.active = true;
      ARENA.joystick.touchId = touchId;
      const rect = zone.getBoundingClientRect();
      ARENA.joystick.baseX = rect.left + rect.width / 2;
      ARENA.joystick.baseY = rect.top + rect.height / 2;
      handleMove(clientX, clientY);
    }

    function handleMove(clientX, clientY) {
      if (!ARENA.joystick.active) return;
      let dx = clientX - ARENA.joystick.baseX;
      let dy = clientY - ARENA.joystick.baseY;
      const dist = Math.hypot(dx, dy);

      // Clamp knob visually inside joystick boundary
      let knobX = dx;
      let knobY = dy;
      if (dist > maxRadius) {
        knobX = (dx / dist) * maxRadius;
        knobY = (dy / dist) * maxRadius;
      }
      knob.style.transform = `translate(${knobX}px, ${knobY}px)`;

      ARENA.joystick.curX = knobX;
      ARENA.joystick.curY = knobY;

      // Soft deadzone and smoothed progressive sensitivity
      if (dist < deadzone) {
        ARENA.joystick.dx = 0;
        ARENA.joystick.dy = 0;
        ARENA.joystick.power = 0;
        ARENA.player.isMoving = false;
        return;
      }

      const ratio = Math.min(1.0, (dist - deadzone) / (maxRadius - deadzone));
      const smoothPower = Math.pow(ratio, 1.35) * 0.90;
      const angle = Math.atan2(dy, dx);

      ARENA.joystick.dx = Math.cos(angle) * smoothPower;
      ARENA.joystick.dy = Math.sin(angle) * smoothPower;
      ARENA.joystick.power = smoothPower;

      if (smoothPower > 0.18) {
        ARENA.player.isMoving = true;
        ARENA.player.facingAngle = angle;
      } else {
        ARENA.player.isMoving = false;
      }
    }

    function handleEnd() {
      ARENA.joystick.active = false;
      ARENA.joystick.touchId = null;
      ARENA.joystick.dx = 0;
      ARENA.joystick.dy = 0;
      ARENA.joystick.power = 0;
      ARENA.player.isMoving = false;
      knob.style.transform = "translate(0px, 0px)";
    }

    // Pointer / Touch Events on Joystick
    zone.ontouchstart = (e) => {
      e.preventDefault();
      const t = e.changedTouches[0];
      handleStart(t.clientX, t.clientY, t.identifier);
    };

    zone.ontouchmove = (e) => {
      e.preventDefault();
      if (!ARENA.joystick.active) return;
      const t = Array.from(e.changedTouches).find(touch => touch.identifier === ARENA.joystick.touchId);
      if (t) handleMove(t.clientX, t.clientY);
    };

    zone.ontouchend = (e) => {
      e.preventDefault();
      handleEnd();
    };
    zone.ontouchcancel = (e) => {
      handleEnd();
    };

    // Desktop Mouse Fallback
    zone.onmousedown = (e) => {
      e.preventDefault();
      handleStart(e.clientX, e.clientY, "mouse");
      const onMouseMove = (ev) => handleMove(ev.clientX, ev.clientY);
      const onMouseUp = () => {
        handleEnd();
        window.removeEventListener("mousemove", onMouseMove);
        window.removeEventListener("mouseup", onMouseUp);
      };
      window.addEventListener("mousemove", onMouseMove);
      window.addEventListener("mouseup", onMouseUp);
    };
  }


  // REAL RPG DAMAGE: Hero ATK vs Boss Defense (no more %-HP cheese!)
