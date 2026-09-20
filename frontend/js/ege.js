/**
 * ege.js — Главный координирующий модуль тренажера ЕГЭ для Mini App.
 * Объединяет модули из /static/js/ege/:
 * - ege_core.js (навигация по предметам и заданиям)
 * - ege_math18.js (Задание 18: Параметры)
 * - ege_paronyms.js (Задание 5: Паронимы)
 * - ege_stress.js (Задание 4: Ударения)
 */
(function () {
  'use strict';

  window.EGE = Object.assign(
    {},
    window.EGE_CORE || {},
    window.EGE_STRESS || {},
    window.EGE_PARONYMS || {},
    window.EGE_MATH18 || {}
  );

  // Unified public API
  window.EGE.init = function() {
    if (window.EGE_CORE && typeof window.EGE_CORE.initEge === 'function') {
      window.EGE_CORE.initEge();
    }
  };

  window.EGE.renderEge = function() {
    if (window.EGE_CORE && typeof window.EGE_CORE.renderEge === 'function') {
      window.EGE_CORE.renderEge();
    }
  };
})();
