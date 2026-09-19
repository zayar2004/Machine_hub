/* Theme toggle */
(function () {
  'use strict';
  const KEY = 'mh_theme';
  const DEFAULT = 'dark';

  function getStored() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }

  function apply(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    document.querySelectorAll('[data-theme-toggle]').forEach(el => {
      el.innerHTML = theme === 'dark'
        ? '<svg class="icon"><use href="#i-sun"/></svg>'
        : '<svg class="icon"><use href="#i-moon"/></svg>';
    });
  }

  function toggle() {
    const cur = document.documentElement.getAttribute('data-theme') || DEFAULT;
    const next = cur === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem(KEY, next); } catch (e) {}
    apply(next);
  }

  apply(getStored() || DEFAULT);

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-theme-toggle]').forEach(el => {
      el.addEventListener('click', toggle);
    });
  });
})();
