/* Live search — auto-suggest with related errors */
(function () {
  'use strict';

  let timer = null;
  let controller = null;
  const DEBOUNCE_MS = 200;

  function getContainer(input) {
    let el = document.getElementById('live-results');
    if (el) return el;

    el = document.createElement('div');
    el.id = 'live-results';
    el.style.cssText = [
      'position:absolute',
      'top:calc(100% + 6px)',
      'left:0',
      'right:0',
      'background:var(--surface)',
      'border:1.5px solid var(--border)',
      'border-radius:var(--r-lg)',
      'box-shadow:var(--sh-lg)',
      'max-height:60vh',
      'overflow-y:auto',
      'z-index:50',
      'display:none'
    ].join(';');

    input.closest('.search').appendChild(el);
    return el;
  }

  function hideResults() {
    const el = document.getElementById('live-results');
    if (el) el.style.display = 'none';
  }

  function escapeHtml(s) {
    return String(s || '').replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }

  function renderResults(data, query) {
    const el = document.getElementById('live-results');
    if (!el) return;

    const machines = data.machines || [];
    const errors = data.errors || [];
    const total = machines.length + errors.length;

    if (!query || total === 0) {
      el.innerHTML = `
        <div style="padding:14px 16px;font-size:13px;color:var(--text-3);text-align:center;">
          ${query ? 'ရှာတွေ့မှု မရှိပါ' : 'စာလုံး ရိုက်ပါ'}
        </div>`;
      el.style.display = 'block';
      return;
    }

    let html = '';

    // Machines
    if (machines.length > 0) {
      html += `<div style="padding:10px 14px 4px;font-size:10px;font-weight:700;color:var(--text-3);letter-spacing:.06em;">MACHINES</div>`;
      html += machines.slice(0, 5).map(m => {
        // Show related errors as small badges
        const errorBadges = (m.errors || []).slice(0, 3).map(e => 
          `<span style="display:inline-flex;align-items:center;gap:2px;padding:1px 5px;background:var(--warning-soft);color:var(--warning);border-radius:3px;font-size:9px;margin-right:3px;">⚠️ ${escapeHtml(e.error_code)}</span>`
        ).join('');
        const moreErrors = (m.error_count || 0) > 3 
          ? `<span style="font-size:9px;color:var(--text-3);">+${m.error_count - 3}</span>` 
          : '';

        return `
        <a href="/machine/${m.id}" class="live-item" data-code="${escapeHtml(m.machine_code)}">
          <div class="live-item-icon" style="background:var(--accent-soft);color:var(--accent);">
            <svg class="icon icon-sm"><use href="#i-package"/></svg>
          </div>
          <div class="live-item-main">
            <div class="live-item-title">${escapeHtml(m.machine_name)}</div>
            <div class="live-item-sub">
              <span style="font-family:var(--mono);">${escapeHtml(m.machine_code)}</span>
              ${m.shop_code ? ' · ' + escapeHtml(m.shop_code) : ''}
            </div>
            ${errorBadges ? `
              <div style="display:flex;flex-wrap:wrap;align-items:center;margin-top:4px;">
                ${errorBadges}${moreErrors}
              </div>
            ` : ''}
          </div>
          <button type="button" class="live-copy" data-copy="${escapeHtml(m.machine_code)}" title="Copy code">
            <svg class="icon icon-xs"><use href="#i-copy"/></svg>
          </button>
        </a>`;
      }).join('');
    }

    // Errors
    if (errors.length > 0) {
      const sep = machines.length > 0 ? 'border-top:1px solid var(--border);margin-top:4px;' : '';
      html += `<div style="padding:10px 14px 4px;font-size:10px;font-weight:700;color:var(--text-3);letter-spacing:.06em;${sep}">ERRORS</div>`;
      html += errors.slice(0, 5).map(e => {
        const mNames = (e.machines || []).slice(0, 3).map(m => 
          `<span style="display:inline-flex;align-items:center;gap:2px;padding:1px 5px;background:var(--surface-2);border-radius:3px;font-size:9px;margin-right:3px;">📦 ${escapeHtml(m.machine_name).slice(0, 18)}</span>`
        ).join('');
        const more = (e.machine_count || 0) > 3 
          ? `<span style="font-size:9px;color:var(--text-3);">+${e.machine_count - 3}</span>` 
          : '';

        return `
        <a href="/error/${e.id}" class="live-item" data-code="${escapeHtml(e.error_code)}">
          <div class="live-item-icon" style="background:var(--warning-soft);color:var(--warning);">
            <svg class="icon icon-sm"><use href="#i-alert"/></svg>
          </div>
          <div class="live-item-main">
            <div class="live-item-title">
              <strong style="color:var(--warning);">${escapeHtml(e.error_code)}</strong>
              — ${escapeHtml(e.error_name)}
            </div>
            <div class="live-item-sub" style="display:flex;flex-wrap:wrap;align-items:center;margin-top:2px;">
              ${mNames || '<span style="color:var(--text-3);">📦 —</span>'}
              ${more}
            </div>
          </div>
          <button type="button" class="live-copy" data-copy="${escapeHtml(e.error_code)}" title="Copy code">
            <svg class="icon icon-xs"><use href="#i-copy"/></svg>
          </button>
        </a>`;
      }).join('');
    }

    // See all link
    html += `
      <a href="/search?q=${encodeURIComponent(query)}"
         class="live-see-all">
        <svg class="icon icon-xs"><use href="#i-search"/></svg>
        "${escapeHtml(query)}" အားလုံး ကြည့်ပါ →
      </a>
    `;

    el.innerHTML = html;
    el.style.display = 'block';

    // Wire copy buttons
    el.querySelectorAll('.live-copy').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const text = btn.getAttribute('data-copy');
        copyText(text, btn);
      });
    });
  }

  async function copyText(text, btn) {
    try {
      await navigator.clipboard.writeText(text);
      if (window.MH && window.MH.toast) window.MH.toast('Copied: ' + text);
      if (btn) {
        btn.style.color = 'var(--success)';
        setTimeout(() => { btn.style.color = ''; }, 1200);
      }
    } catch (err) {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.cssText = 'position:fixed;opacity:0';
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand('copy');
        if (window.MH && window.MH.toast) window.MH.toast('Copied: ' + text);
      } catch (e) {}
      document.body.removeChild(ta);
    }
  }

  async function doSearch(query, type) {
    if (controller) controller.abort();
    controller = new AbortController();

    // Offline → local
    if (!navigator.onLine) {
      if (window.MH && window.MH.search && window.MH.search.searchLocal) {
        const local = await window.MH.search.searchLocal(query, type || 'all');
        renderResults({ machines: local.machines, errors: local.errors }, query);
      } else {
        renderResults({ machines: [], errors: [] }, query);
      }
      return;
    }

    try {
      const res = await fetch(
        `/api/search?q=${encodeURIComponent(query)}&type=${type || 'all'}&limit=8`,
        {
          credentials: 'same-origin',
          headers: { 'Accept': 'application/json' },
          signal: controller.signal
        }
      );
      if (!res.ok) {
        if (window.MH && window.MH.search && window.MH.search.searchLocal) {
          const local = await window.MH.search.searchLocal(query, type || 'all');
          renderResults({ machines: local.machines, errors: local.errors }, query);
        }
        return;
      }
      const data = await res.json();
      renderResults(data, query);
    } catch (err) {
      if (err.name === 'AbortError') return;
      if (window.MH && window.MH.search && window.MH.search.searchLocal) {
        const local = await window.MH.search.searchLocal(query, type || 'all');
        renderResults({ machines: local.machines, errors: local.errors }, query);
      }
    }
  }

  function init() {
    const input = document.getElementById('search-input');
    if (!input) return;

    const searchDiv = input.closest('.search');
    if (searchDiv && getComputedStyle(searchDiv).position === 'static') {
      searchDiv.style.position = 'relative';
    }

    input.addEventListener('input', (e) => {
      const q = e.target.value.trim();
      if (timer) clearTimeout(timer);
      if (q.length < 1) {
        hideResults();
        return;
      }
      timer = setTimeout(() => doSearch(q, 'all'), DEBOUNCE_MS);
    });

    input.addEventListener('focus', (e) => {
      const q = e.target.value.trim();
      if (q.length >= 1) doSearch(q, 'all');
    });

    document.addEventListener('click', (e) => {
      if (!e.target.closest('.search')) hideResults();
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') hideResults();
    });
  }

  // CSS
  const style = document.createElement('style');
  style.textContent = `
    .live-item {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 10px 14px;
      text-decoration: none;
      color: var(--text);
      transition: background var(--t);
      cursor: pointer;
    }
    .live-item:hover { background: var(--surface-2); }
    .live-item-icon {
      width: 32px; height: 32px;
      border-radius: 8px;
      display: flex; align-items: center; justify-content: center;
      flex-shrink: 0;
    }
    .live-item-main { flex: 1; min-width: 0; }
    .live-item-title {
      font-weight: 600; font-size: 13px;
      overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    .live-item-sub {
      font-size: 11px; color: var(--text-3);
      font-family: var(--mono);
      margin-top: 1px;
    }
    .live-copy {
      width: 28px; height: 28px;
      border-radius: 6px;
      background: transparent;
      border: none;
      color: var(--text-3);
      display: flex; align-items: center; justify-content: center;
      cursor: pointer;
      flex-shrink: 0;
      transition: all var(--t);
    }
    .live-copy:hover {
      background: var(--surface-3);
      color: var(--accent);
    }
    .live-see-all {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      padding: 12px;
      border-top: 1px solid var(--border);
      font-size: 12px;
      font-weight: 600;
      color: var(--accent);
      text-decoration: none;
      background: var(--surface-2);
    }
    .live-see-all:hover { background: var(--surface-3); color: var(--accent); }
  `;
  document.head.appendChild(style);

  document.addEventListener('DOMContentLoaded', init);
  console.log('[LiveSearch] loaded');
})();
