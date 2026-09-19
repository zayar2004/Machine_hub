/* Install prompt — MUST install before dismissing */
(function () {
  'use strict';

  const KEY = 'mh_install_done';
  let deferred = null;

  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferred = e;
    setTimeout(showInstallBanner, 800);
  });

  window.addEventListener('appinstalled', () => {
    try { localStorage.setItem(KEY, '1'); } catch (err) {}
    hideBanner();
    if (window.MH && window.MH.toast) {
      window.MH.toast('✓ Installed!');
    }
  });

  function isStandalone() {
    return (window.matchMedia('(display-mode: standalone)').matches) ||
           (window.navigator.standalone === true);
  }

  function isInstalled() {
    try {
      if (localStorage.getItem(KEY) === '1') return true;
    } catch (e) {}
    return isStandalone();
  }

  function showInstallBanner() {
    if (isInstalled()) return;
    if (document.getElementById('mh-install-banner')) return;

    const banner = document.createElement('div');
    banner.id = 'mh-install-banner';
    banner.style.cssText = [
      'position:fixed;bottom:0;left:0;right:0;',
      'background:var(--surface);color:var(--text);',
      'border-top:1.5px solid var(--border);',
      'padding:16px 20px;',
      'box-shadow:0 -8px 24px rgba(0,0,0,0.4);',
      'z-index:500;',
      'display:flex;flex-direction:column;gap:12px;'
    ].join('');

    banner.innerHTML = [
      '<div style="display:flex;align-items:center;gap:14px;">',
      '  <div style="width:48px;height:48px;border-radius:12px;background:linear-gradient(135deg,var(--accent),#8b5cf6);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:16px;flex-shrink:0;">MH</div>',
      '  <div style="flex:1;min-width:0;">',
      '    <div style="font-weight:700;font-size:15px;margin-bottom:2px;">Install Machine Hub</div>',
      '    <div style="font-size:12px;color:var(--text-2);line-height:1.4;">Internet မလိုဘဲ သုံးနိုင်မယ်</div>',
      '  </div>',
      '</div>',
      '<button type="button" id="mh-install-go" style="width:100%;padding:14px;border-radius:12px;background:var(--accent);color:#fff;font-weight:700;font-size:15px;border:none;cursor:pointer;">Install Now</button>',
      '<p style="font-size:11px;color:var(--text-3);text-align:center;line-height:1.5;margin:0;">Install လုပ်ပြီးမှ ဒီ banner ပျောက်ပါမယ်</p>'
    ].join('');

    document.body.appendChild(banner);

    document.getElementById('mh-install-go').addEventListener('click', async () => {
      if (deferred) {
        try {
          deferred.prompt();
          const c = await deferred.userChoice;
          if (c.outcome === 'accepted') {
            try { localStorage.setItem(KEY, '1'); } catch (e) {}
            hideBanner();
            if (window.MH && window.MH.toast) {
              window.MH.toast('✓ Installing…');
            }
          }
          deferred = null;
        } catch (err) {
          console.warn('install error', err);
        }
      } else {
        showManualInstallHelp();
      }
    });
  }

  function showManualInstallHelp() {
    if (document.getElementById('mh-install-help-modal')) return;

    const modal = document.createElement('div');
    modal.id = 'mh-install-help-modal';
    modal.style.cssText = 'position:fixed;inset:0;z-index:600;background:rgba(0,0,0,0.7);display:flex;align-items:center;justify-content:center;padding:20px;';

    modal.innerHTML = [
      '<div style="background:var(--surface);color:var(--text);border-radius:20px;max-width:400px;width:100%;padding:24px;border:1.5px solid var(--border);">',
      '  <h3 style="font-size:18px;font-weight:800;margin-bottom:8px;">Install Machine Hub</h3>',
      '  <p style="font-size:13px;color:var(--text-2);margin-bottom:20px;line-height:1.5;">Chrome က auto-install မပေးလို့ manual လုပ်ပါ:</p>',
      '  <div style="background:var(--surface-2);padding:16px;border-radius:12px;margin-bottom:16px;">',
      '    <div style="font-weight:700;font-size:13px;margin-bottom:10px;">Chrome (Android):</div>',
      '    <ol style="margin-left:20px;color:var(--text-2);font-size:13px;line-height:1.9;">',
      '      <li>Tap ⋮ (top right)</li>',
      '      <li>Tap "Add to Home screen"</li>',
      '      <li>Confirm</li>',
      '    </ol>',
      '  </div>',
      '  <button type="button" id="mh-help-close" style="width:100%;padding:12px;border-radius:10px;background:var(--accent);color:#fff;font-weight:700;font-size:14px;border:none;cursor:pointer;">Got it</button>',
      '</div>'
    ].join('');

    document.body.appendChild(modal);
    document.getElementById('mh-help-close').addEventListener('click', () => modal.remove());
  }

  function hideBanner() {
    const el = document.getElementById('mh-install-banner');
    if (el) el.remove();
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (isInstalled()) {
      try { localStorage.setItem(KEY, '1'); } catch (e) {}
    }
  });

  setTimeout(() => {
    if (!isInstalled() && !document.getElementById('mh-install-banner')) {
      if (window.location.pathname !== '/auth/login' &&
          window.location.pathname !== '/auth/register') {
        showInstallBanner();
      }
    }
  }, 3000);
})();
