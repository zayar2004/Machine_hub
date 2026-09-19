/* Sheet + Install + Toast + Copy */
(function () {
  'use strict';

  let deferredPrompt = null;

  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    const btn = document.getElementById('mh-install-btn');
    if (btn) btn.style.display = 'flex';
  });

  window.addEventListener('appinstalled', () => {
    deferredPrompt = null;
    const btn = document.getElementById('mh-install-btn');
    if (btn) btn.style.display = 'none';
    toast('Installed');
  });

  function isStandalone() {
    return (window.matchMedia('(display-mode: standalone)').matches) ||
           (window.navigator.standalone === true);
  }

  async function doInstall() {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      const c = await deferredPrompt.userChoice;
      if (c.outcome === 'accepted') {
        deferredPrompt = null;
        const btn = document.getElementById('mh-install-btn');
        if (btn) btn.style.display = 'none';
      }
    } else {
      toast('Chrome → Add to Home screen');
    }
  }

  function openSheet() {
    const s = document.getElementById('sheet');
    const b = document.getElementById('sheet-backdrop');
    if (!s || !b) return;
    s.classList.add('open');
    b.classList.add('open');
    document.body.style.overflow = 'hidden';
  }

  function closeSheet() {
    const s = document.getElementById('sheet');
    const b = document.getElementById('sheet-backdrop');
    if (!s || !b) return;
    s.classList.remove('open');
    b.classList.remove('open');
    document.body.style.overflow = '';
  }

  function toast(msg) {
    let el = document.getElementById('mh-toast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'mh-toast';
      el.className = 'toast';
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.classList.add('visible');
    setTimeout(() => el.classList.remove('visible'), 2000);
  }

  function wireCopy() {
    document.querySelectorAll('[data-copy]').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.preventDefault();
        const text = btn.getAttribute('data-copy');
        try {
          await navigator.clipboard.writeText(text);
          btn.classList.add('copied');
          toast('Copied: ' + text);
          setTimeout(() => btn.classList.remove('copied'), 1500);
        } catch (err) {
          const ta = document.createElement('textarea');
          ta.value = text;
          ta.style.cssText = 'position:fixed;opacity:0';
          document.body.appendChild(ta);
          ta.select();
          try {
            document.execCommand('copy');
            toast('Copied: ' + text);
          } catch (e2) {
            toast('Copy failed');
          }
          document.body.removeChild(ta);
        }
      });
    });
  }

  function wireSearchClear() {
    const i = document.getElementById('search-input');
    const c = document.getElementById('search-clear');
    if (!i || !c) return;
    function u() {
      if (i.value.length > 0) c.classList.add('visible');
      else c.classList.remove('visible');
    }
    i.addEventListener('input', u);
    c.addEventListener('click', () => { i.value = ''; i.focus(); u(); });
    u();
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-sheet-open]').forEach(el => {
      el.addEventListener('click', openSheet);
    });
    document.querySelectorAll('[data-sheet-close]').forEach(el => {
      el.addEventListener('click', closeSheet);
    });
    const b = document.getElementById('sheet-backdrop');
    if (b) b.addEventListener('click', closeSheet);
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeSheet();
    });

    const ib = document.getElementById('mh-install-btn');
    if (ib) {
      ib.addEventListener('click', (e) => { e.preventDefault(); doInstall(); });
      if (isStandalone()) ib.style.display = 'none';
      else ib.style.display = 'flex';
    }

    wireCopy();
    wireSearchClear();
  });

  window.MH = window.MH || {};
  window.MH.toast = toast;
  console.log('[Menu] loaded');
})();
