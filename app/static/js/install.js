/* PWA Install — DISABLED (both APK + browser) */
(function () {
  'use strict';

  // APK/WebView detection — always skip in native app
  function isNativeApp() {
    try {
      if (window.Capacitor && window.Capacitor.isNativePlatform) {
        return window.Capacitor.isNativePlatform();
      }
    } catch (e) {}
    var ua = navigator.userAgent || '';
    if (/wv\)/.test(ua) && /Android/.test(ua)) return true;
    if (/MachineHub/.test(ua)) return true;
    if (/iPhone|iPad/.test(ua) && !/Safari/.test(ua)) return true;
    return false;
  }

  if (isNativeApp()) {
    console.log('[Install] Native app — skip banner');
    return;
  }

  console.log('[Install] Disabled — no PWA install banner');

  // Hide sheet install button (if present)
  try {
    var btn = document.getElementById('mh-install-btn');
    if (btn) btn.style.display = 'none';
  } catch (e) {}
})();
