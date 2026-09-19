/* =========================================================
   Machine Hub — Favorites (client)
   - Toggle favorite via API
   - Mark buttons on detail pages
   ========================================================= */
(function () {
  'use strict';

  async function toggle(type, id, btn) {
    if (!type || !id) return;
    const url = `/api/favorites/${type}/${id}`;
    try {
      const res = await fetch(url, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Accept': 'application/json' },
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      updateButton(btn, data.is_favorite);
      showToast(data.is_favorite ? 'Added to favorites' : 'Removed from favorites');
    } catch (err) {
      console.error('[Fav] toggle failed:', err);
      showToast('Could not update favorite');
    }
  }

  function updateButton(btn, isFav) {
    if (!btn) return;
    btn.setAttribute('data-fav', isFav ? '1' : '0');
    btn.classList.toggle('favorited', isFav);
    btn.setAttribute('aria-pressed', isFav ? 'true' : 'false');
    const icon = btn.querySelector('svg');
    if (icon) {
      icon.setAttribute('fill', isFav ? 'currentColor' : 'none');
    }
  }

  function showToast(msg) {
    let el = document.getElementById('mh-toast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'mh-toast';
      el.className = 'toast';
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.classList.add('visible');
    setTimeout(() => el.classList.remove('visible'), 1800);
  }

  async function markFavorites() {
    // Collect all [data-fav-toggle] buttons
    const buttons = Array.from(document.querySelectorAll('[data-fav-toggle]'));
    if (!buttons.length) return;

    const machineIds = [];
    const errorIds = [];

    for (const btn of buttons) {
      const type = btn.getAttribute('data-type');
      const id = btn.getAttribute('data-id');
      if (!id) continue;
      if (type === 'machine') machineIds.push(id);
      else if (type === 'error') errorIds.push(id);
    }

    const params = new URLSearchParams();
    if (machineIds.length) params.set('machine_ids', machineIds.join(','));
    if (errorIds.length) params.set('error_ids', errorIds.join(','));

    try {
      const res = await fetch(`/api/favorites/check?${params}`, {
        credentials: 'same-origin',
        headers: { 'Accept': 'application/json' },
      });
      if (!res.ok) return;
      const data = await res.json();

      for (const btn of buttons) {
        const type = btn.getAttribute('data-type');
        const id = btn.getAttribute('data-id');
        const map = type === 'machine' ? data.machines : data.errors;
        const isFav = !!map[id];
        updateButton(btn, isFav);
      }
    } catch (e) {
      console.warn('[Fav] check failed:', e);
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-fav-toggle]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const type = btn.getAttribute('data-type');
        const id = btn.getAttribute('data-id');
        toggle(type, id, btn);
      });
    });
    markFavorites();
  });

  window.MH = window.MH || {};
  window.MH.favorites = { mark: markFavorites, toggle };
  console.log('[Fav] loaded');
})();
