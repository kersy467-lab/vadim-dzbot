/**
 * durak.js — Главный фасад и координатор игры «Дурак» для Mini App 11 «Б».
 * Объединяет модули durak_cards.js, durak_menu.js и durak_game.js.
 * Экспортирует window.DURAK = { init, destroy }
 */
(function () {
  'use strict';

  let _roomId = null;
  let _userId = null;
  let _state = null;
  let _selectedCard = null;
  let _container = null;
  let _selectedStake = 0;
  let _userCoins = 0;
  let _pendingRoomId = null;

  function getUserId() {
    if (_userId) return _userId;
    if (window.currentUser && window.currentUser.tg_id) return window.currentUser.tg_id;
    try {
      if (typeof window !== "undefined" && window.location && window.location.search) {
        const params = new URLSearchParams(window.location.search);
        return parseInt(params.get('user_id') || params.get('uid') || '0', 10);
      }
    } catch (e) {}
    return 0;
  }

  function apiBase() {
    try {
      if (typeof window !== "undefined" && window.location && window.location.origin) {
        return window.location.origin;
      }
    } catch (e) {}
    return '';
  }

  function showAlert(msg) {
    if (typeof alert !== "undefined") {
      alert(msg);
    } else {
      console.warn(msg);
    }
  }

  async function apiPost(path, body = {}) {
    const uid = getUserId();
    const resp = await fetch(`${apiBase()}${path}?user_id=${uid}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...body, user_id: uid }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }
    return resp.json();
  }

  async function apiGet(path) {
    const uid = getUserId();
    const resp = await fetch(`${apiBase()}${path}?user_id=${uid}`);
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }
    return resp.json();
  }

  async function refreshUserCoins() {
    try {
      const me = await apiGet('/api/me');
      if (me && typeof me.coins !== 'undefined') {
        _userCoins = Number(me.coins || 0);
        if (window.currentUser) window.currentUser.coins = _userCoins;
      }
    } catch (e) {
      if (window.currentUser && typeof window.currentUser.coins !== 'undefined') {
        _userCoins = Number(window.currentUser.coins || 0);
      }
    }
    return _userCoins;
  }

  function getContext() {
    return {
      getUserId,
      getUserCoins: () => _userCoins,
      getSelectedStake: () => _selectedStake,
      setSelectedStake: (v) => { _selectedStake = v; },
      getRoomId: () => _roomId,
      getState: () => _state,
      setState: (st) => { _state = st; },
      getSelectedCard: () => _selectedCard,
      setSelectedCard: (c) => { _selectedCard = c; },
      refreshUserCoins,
      apiPost,
      apiGet,
      startBotGame,
      createOnlineRoom,
      joinRoom,
      leaveCurrentRoom,
      exitToMenu
    };
  }

  async function leaveCurrentRoom() {
    if (_roomId) {
      const rId = _roomId;
      _roomId = null;
      try {
        await apiPost('/api/durak/leave', { room_id: rId });
      } catch (e) {
        console.warn('leave room error', e);
      }
    }
  }

  async function exitToMenu() {
    if (window.DURAK_GAME && typeof window.DURAK_GAME.disconnectWS === 'function') {
      window.DURAK_GAME.disconnectWS();
    }
    await leaveCurrentRoom();
    _state = null;
    _selectedCard = null;
    await refreshUserCoins();
    if (_container && window.DURAK_MENU && typeof window.DURAK_MENU.showMenu === 'function') {
      window.DURAK_MENU.showMenu(_container, getContext());
    }
  }

  async function startBotGame() {
    _userId = getUserId();
    try {
      const res = await apiPost('/api/durak/new', {
        mode: 'bot',
        players_count: 2,
        stake: _selectedStake
      });
      _roomId = res.room_id;
      _state = res.state;
      window.DURAK_GAME.connectWS(
        _roomId,
        _userId,
        (st) => { _state = st; window.DURAK_GAME.renderGame(_container, getContext()); },
        null,
        () => exitToMenu()
      );
      window.DURAK_GAME.renderGame(_container, getContext());
    } catch (e) {
      showAlert(`Ошибка: ${e.message}`);
    }
  }

  async function createOnlineRoom(playersCount, stake) {
    _userId = getUserId();
    try {
      const res = await apiPost('/api/durak/new', {
        mode: 'online',
        players_count: playersCount,
        stake: stake
      });
      _roomId = res.room_id;
      const onCancelRoom = async () => {
        await exitToMenu();
      };
      window.DURAK_GAME.connectWS(
        _roomId,
        _userId,
        (st) => { _state = st; window.DURAK_GAME.renderGame(_container, getContext()); },
        (players, stkW) => {
          window.DURAK_MENU.renderWaiting(_container, _roomId, players, stkW || stake, onCancelRoom, true);
        },
        async () => {
          await exitToMenu();
        }
      );
      window.DURAK_MENU.renderWaiting(_container, _roomId, res.players, stake, onCancelRoom, true);
    } catch (e) {
      showAlert(`Ошибка: ${e.message}`);
    }
  }

  async function joinRoom(roomId) {
    _userId = getUserId();
    _roomId = roomId;
    try {
      const res = await apiPost('/api/durak/join', { room_id: roomId });
      const onLeaveRoom = async () => {
        await exitToMenu();
      };
      window.DURAK_GAME.connectWS(
        _roomId,
        _userId,
        (st) => { _state = st; window.DURAK_GAME.renderGame(_container, getContext()); },
        (players, stkW) => {
          window.DURAK_MENU.renderWaiting(_container, _roomId, players, stkW || res.stake || 0, onLeaveRoom, false);
        },
        async () => {
          await exitToMenu();
        }
      );
      if (res.status === 'started') {
        _state = res.state;
        window.DURAK_GAME.renderGame(_container, getContext());
      } else {
        window.DURAK_MENU.renderWaiting(_container, _roomId, res.players, res.stake || 0, onLeaveRoom, false);
      }
    } catch (e) {
      showAlert(`Ошибка: ${e.message}`);
    }
  }

  async function init(container) {
    _container = container;
    _roomId = null;
    _state = null;
    _selectedCard = null;
    _userId = getUserId();
    if (window.DURAK_CARDS && typeof window.DURAK_CARDS.injectCSS === 'function') {
      window.DURAK_CARDS.injectCSS();
    }
    await refreshUserCoins();
    if (_pendingRoomId) {
      const pending = _pendingRoomId;
      _pendingRoomId = null;
      await joinRoom(pending);
      return;
    }
    if (window.DURAK_MENU && typeof window.DURAK_MENU.showMenu === 'function') {
      window.DURAK_MENU.showMenu(_container, getContext());
    }
  }

  function joinRoomPublic(roomId) {
    if (!_container) {
      _pendingRoomId = roomId;
      const el = document.getElementById('durak-root');
      if (el) init(el);
      return;
    }
    return joinRoom(roomId);
  }

  function destroy() {
    if (window.DURAK_GAME && typeof window.DURAK_GAME.disconnectWS === 'function') {
      window.DURAK_GAME.disconnectWS();
    }
    if (_roomId) {
      leaveCurrentRoom();
    }
    _roomId = null;
    _state = null;
    _selectedCard = null;
    _container = null;
    _pendingRoomId = null;
  }

  window.DURAK = { init, destroy, joinRoom: joinRoomPublic };
})();
