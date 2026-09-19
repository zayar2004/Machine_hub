/* Smart Back button — real app behavior */
(function () {
  'use strict';

  function isSameHost(url) {
    try {
      const u = new URL(url, window.location.origin);
      return u.host === window.location.host;
    } catch (e) {
      return false;
    }
  }

  function isAuthPage(url) {
    return url.includes('/auth/login') || 
           url.includes('/auth/register') ||
           url.includes('/auth/logout');
  }

  function shouldGoBack() {
    // No history → go home
    if (window.history.length <= 1) return false;

    // No referrer → go home
    if (!document.referrer) return false;

    // External referrer → go home
    if (!isSameHost(document.referrer)) return false;

    // Referrer was login/register → go home (not back to login)
    if (isAuthPage(document.referrer)) return false;

    // Same page referrer (refresh) → go home
    if (document.referrer === window.location.href) return false;

    return true;
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-smart-back]').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        if (shouldGoBack()) {
          e.preventDefault();
          window.history.back();
        }
        // else: default href (Home)
      });
    });
  });

  console.log('[SmartBack] loaded');
})();
