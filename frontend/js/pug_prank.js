// ============================================================
// frontend/js/pug_prank.js — Шуточный модуль «Глеб Мопс»
// Для удаления: просто удалить этот файл и убрать тег из index.html
// ============================================================

(function() {
  const GLEB_TG_ID = 5181261098;
  const STATIC_PUG_SRC = "/static/images/pug/pug_static.png";
  const PETTING_PUG_SRC = "/static/images/pug/pug_petting.gif";
  let isPugModeActive = false;
  let revertTimer = null;
  let audioCtx = null;

  function playBarkSound() {
    try {
      if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      }
      if (audioCtx.state === "suspended") {
        audioCtx.resume();
      }
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = "triangle";
      const now = audioCtx.currentTime;
      osc.frequency.setValueAtTime(440, now);
      osc.frequency.exponentialRampToValueAtTime(180, now + 0.14);
      gain.gain.setValueAtTime(0.25, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.15);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start(now);
      osc.stop(now + 0.15);
    } catch (e) {
      // Audio not permitted or supported, silent fallback
    }
  }

  function spawnPawParticle(x, y) {
    const el = document.createElement("div");
    el.textContent = ["🐾", "❤️", "✨", "🦴"][Math.floor(Math.random() * 4)];
    el.style.cssText = `
      position: fixed; left: ${x - 12}px; top: ${y - 12}px;
      font-size: 20px; pointer-events: none; z-index: 50;
      transition: all 0.8s ease-out; opacity: 1; transform: translateY(0) scale(1);
    `;
    document.body.appendChild(el);
    requestAnimationFrame(() => {
      el.style.transform = `translateY(-${50 + Math.random() * 40}px) scale(${1.2 + Math.random() * 0.4})`;
      el.style.opacity = "0";
    });
    setTimeout(() => el.remove(), 850);
  }

  function initPugUI() {
    if (document.getElementById("pug-prank-overlay")) return;

    document.documentElement.style.backgroundColor = "#000000";
    document.body.style.backgroundColor = "#000000";

    const header = document.querySelector("header");
    if (header) header.style.display = "none";
    const main = document.querySelector("main");
    if (main) main.style.display = "none";
    const nav = document.querySelector("nav");
    if (nav) nav.style.display = "none";

    const overlay = document.createElement("div");
    overlay.id = "pug-prank-overlay";
    overlay.style.cssText = `
      position: fixed; inset: 0;
      background: #000000; z-index: 99999;
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      user-select: none; -webkit-user-select: none;
      touch-action: manipulation; cursor: pointer;
    `;

    overlay.innerHTML = `
      <div id="pug-click-area" style="position: relative; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 380px;">
        <div id="pug-bubble" style="
          opacity: 0; transform: translateY(10px) scale(0.9);
          transition: all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
          position: absolute; top: -30px;
          background: #ffffff; color: #000000;
          font-weight: 900; font-size: 14px;
          padding: 6px 14px; border-radius: 18px;
          box-shadow: 0 4px 20px rgba(255,255,255,0.25);
          pointer-events: none; white-space: nowrap; z-index: 48;
        ">Гав! 🐾</div>
        <img id="pug-main-img" src="${STATIC_PUG_SRC}" alt="Мопс" style="
          width: 260px; max-width: 82vw; max-height: 60vh;
          object-fit: contain; filter: drop-shadow(0 0 25px rgba(255,255,255,0.06));
          transition: transform 0.15s ease;
        " />
        <p id="pug-action-hint" style="
          color: #64748b; font-size: 12px; font-weight: 700;
          margin-top: 20px; letter-spacing: 0.5px;
        ">(нажми на мопса, чтобы погладить)</p>
      </div>
    `;

    document.body.appendChild(overlay);

    const clickArea = document.getElementById("pug-click-area");
    const pugImg = document.getElementById("pug-main-img");
    const bubble = document.getElementById("pug-bubble");

    function triggerPetting(e) {
      if (e) {
        const px = e.clientX || (window.innerWidth / 2);
        const py = e.clientY || (window.innerHeight / 2);
        spawnPawParticle(px, py);
      }

      playBarkSound();

      pugImg.src = `${PETTING_PUG_SRC}?t=${Date.now()}`;
      pugImg.style.imageRendering = "pixelated";
      pugImg.style.width = "220px";
      pugImg.style.transform = "scale(1.06)";
      setTimeout(() => { if (pugImg) pugImg.style.transform = "scale(1)"; }, 150);

      const sounds = ["Гав! 🐾", "Гав-гав! ❤️", "Тяф-тяф! 🐶", "М-м-м, погладили! ✨", "Вуф! 🦴", "Ещё погладь! 🐶"];
      bubble.textContent = sounds[Math.floor(Math.random() * sounds.length)];
      bubble.style.opacity = "1";
      bubble.style.transform = "translateY(0) scale(1)";

      if (revertTimer) clearTimeout(revertTimer);
      revertTimer = setTimeout(() => {
        if (pugImg) {
          pugImg.src = STATIC_PUG_SRC;
          pugImg.style.imageRendering = "auto";
          pugImg.style.width = "260px";
        }
        if (bubble) {
          bubble.style.opacity = "0";
          bubble.style.transform = "translateY(10px) scale(0.9)";
        }
      }, 3500);
    }

    overlay.addEventListener("click", triggerPetting);
    overlay.addEventListener("touchstart", (e) => {
      triggerPetting(e.touches ? e.touches[0] : null);
    }, { passive: true });
  }

  async function checkPugMode() {
    const params = new URLSearchParams(window.location.search);
    if (params.get("pug_mode") === "1" || params.get("pug") === "1" || params.get("gleb") === "1") {
      isPugModeActive = true;
      initPugUI();
      return;
    }

    let tgId = null;
    try {
      const tgUser = window.Telegram?.WebApp?.initDataUnsafe?.user;
      if (tgUser && tgUser.id) tgId = tgUser.id;
    } catch (e) {}

    if (!tgId) {
      tgId = localStorage.getItem("cached_tg_uid") || localStorage.getItem("admin_test_tg_uid");
    }

    try {
      const url = tgId ? `/api/pug_prank/status?tg_id=${tgId}` : "/api/pug_prank/status";
      const res = await fetch(url).then(r => r.json());
      if (res && res.active) {
        isPugModeActive = true;
        initPugUI();
      }
    } catch (e) {}
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", checkPugMode);
  } else {
    checkPugMode();
  }
})();
