/* PWA Install — DISABLED (both APK + browser) */
(function () {
  'use strict';
  console.log('[Install] Disabled — no PWA install banner');

  // Intentionally do nothing:
  //   - No beforeinstallprompt handling
  //   - No install banner
  //   - No install button activation
  //   - No manual help modal

  // Hide the sheet-menu install button (if present)
  try {
    var btn = document.getElementById('mh-install-btn');
    if (btn) btn.style.display = 'none';
  } catch (e) {}
})();
