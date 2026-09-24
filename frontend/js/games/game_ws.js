/**
 * game_ws.js — универсальный WebSocket-клиент для игровых комнат.
 * Подключается к /ws/room/{roomId}/{userId}, получает push-state от сервера.
 * Автоматически реконнектится с экспоненциальным backoff (1s → 2s → 4s → 8s).
 * При 3 неудачных попытках переключается в режим HTTP-поллинга (через ETag).
 * Вызывается игровыми модулями вместо setInterval для getGameRoom.
 *
 * API:
 *   const conn = window.GameWS.connect(roomId, userId, onState, onClose?)
 *   conn.disconnect()
 *   conn.isWsMode()        // true = WS, false = HTTP polling fallback
 */
(function () {
  'use strict';

  const WS_MAX_RETRIES = 3;       // после этого — fallback на HTTP
  const WS_PING_INTERVAL = 25000; // ms, heartbeat
  const POLL_INTERVAL_MS = 2500;  // интервал HTTP fallback

  function buildWsUrl(roomId, userId) {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    return `${proto}://${location.host}/api/ws/room/${roomId}/${userId}`;
  }

  /**
   * Создаёт управляемое WS-соединение.
   * @param {string} roomId
   * @param {string|number} userId  tg_id пользователя
   * @param {function} onState      вызывается с payload комнаты при каждом обновлении
   * @param {function} [onClose]    вызывается при финальном закрытии (после всех ретраев)
   * @returns {{disconnect: function, isWsMode: function}}
   */
  function connect(roomId, userId, onState, onClose) {
    let ws = null;
    let retries = 0;
    let pingTimer = null;
    let pollTimer = null;
    let closed = false;
    let useWs = true; // false = упали в HTTP polling

    function clearTimers() {
      if (pingTimer) { clearInterval(pingTimer); pingTimer = null; }
      if (pollTimer) { clearTimeout(pollTimer); pollTimer = null; }
    }

    // ── HTTP polling fallback ────────────────────────────────────────────────
    function startHttpFallback() {
      if (closed) return;
      useWs = false;
      console.info(`[GameWS] room=${roomId} WS failed, falling back to HTTP polling`);
      const uid = String(userId);

      async function poll() {
        if (closed) return;
        if (typeof document !== 'undefined' && document.hidden) {
          pollTimer = setTimeout(poll, POLL_INTERVAL_MS);
          return;
        }
        try {
          const data = await (window.api?.getGameRoom(roomId));
          if (data) onState(data);
        } catch (_) {}
        if (!closed) pollTimer = setTimeout(poll, POLL_INTERVAL_MS);
      }
      poll();
    }

    // ── WebSocket ────────────────────────────────────────────────────────────
    function openWs() {
      if (closed) return;
      const url = buildWsUrl(roomId, userId);
      ws = new WebSocket(url);

      ws.addEventListener('open', () => {
        retries = 0;
        pingTimer = setInterval(() => {
          if (ws && ws.readyState === WebSocket.OPEN) ws.send('ping');
        }, WS_PING_INTERVAL);
      });

      ws.addEventListener('message', (ev) => {
        if (ev.data === 'pong') return;
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === 'state' && msg.payload) {
            // Сбрасываем ETag-кэш: WS-данные всегда свежие
            if (window.api?.clearGameRoomEtag) window.api.clearGameRoomEtag(roomId);
            onState(msg.payload);
          } else if (msg.type === 'error') {
            console.warn('[GameWS] server error:', msg.message);
          }
        } catch (_) {}
      });

      ws.addEventListener('close', (ev) => {
        clearTimers();
        if (closed) return;
        if (ev.code === 4004) {
          // Room not found — не реконнектимся
          if (onClose) onClose();
          return;
        }
        retries++;
        if (retries > WS_MAX_RETRIES) {
          startHttpFallback();
          return;
        }
        const delay = Math.min(1000 * Math.pow(2, retries - 1), 8000);
        console.info(`[GameWS] room=${roomId} reconnect #${retries} in ${delay}ms`);
        setTimeout(openWs, delay);
      });

      ws.addEventListener('error', () => {
        // 'close' событие последует автоматически
      });
    }

    // Если вкладка скрыта — не открываем WS (откроем при фокусе)
    if (typeof document !== 'undefined' && document.hidden) {
      // Ждём фокуса, затем пробуем WS
      const onVisible = () => {
        document.removeEventListener('visibilitychange', onVisible);
        if (!closed) openWs();
      };
      document.addEventListener('visibilitychange', onVisible);
    } else {
      openWs();
    }

    // Реконнект при возврате во вкладку (только если уже WS-режим)
    function onVisChange() {
      if (closed || !useWs) return;
      if (!document.hidden && (!ws || ws.readyState === WebSocket.CLOSED)) {
        openWs();
      }
    }
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', onVisChange);
    }

    return {
      disconnect() {
        closed = true;
        clearTimers();
        if (typeof document !== 'undefined') {
          document.removeEventListener('visibilitychange', onVisChange);
        }
        if (ws) { try { ws.close(); } catch (_) {} ws = null; }
      },
      isWsMode() { return useWs; },
    };
  }

  window.GameWS = { connect };
})();
