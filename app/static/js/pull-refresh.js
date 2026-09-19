/* Pull-to-refresh — PWA mobile pattern */
(function () {
  'use strict';

  if (typeof window === 'undefined') return;

  var startY = 0;
  var currentY = 0;
  var isPulling = false;
  var THRESHOLD = 80;

  var indicator = null;

  function createIndicator() {
    if (indicator) return indicator;
    indicator = document.createElement('div');
    indicator.id = 'ptr-indicator';
    indicator.style.cssText = [
      'position:fixed',
      'top:0',
      'left:50%',
      'transform:translateX(-50%) translateY(-100%)',
      'padding:8px 16px',
      'background:var(--surface)',
      'border:1px solid var(--border)',
      'border-radius:0 0 12px 12px',
      'font-size:12px',
      'font-weight:600',
      'color:var(--text-2)',
      'transition:transform 200ms ease',
      'z-index:9999',
      'display:flex',
      'align-items:center',
      'gap:6px'
    ].join(';');
    indicator.innerHTML =
      '<svg class="icon icon-xs" style="width:14px;height:14px;"><use href="#i-refresh"/></svg>' +
      '<span>Pull to refresh</span>';
    document.body.appendChild(indicator);
    return indicator;
  }

  document.addEventListener('touchstart', function (e) {
    if (window.scrollY > 0) return;
    if (e.touches.length !== 1) return;
    startY = e.touches[0].pageY;
    isPulling = false;
  }, { passive: true });

  document.addEventListener('touchmove', function (e) {
    if (window.scrollY > 0 || startY === 0) return;
    currentY = e.touches[0].pageY;
    var diff = currentY - startY;

    if (diff > 20) {
      isPulling = true;
      var ind = createIndicator();
      var pct = Math.min(100, (diff / THRESHOLD) * 100);
      var offset = Math.min(60, diff * 0.5);
      ind.style.transform = 'translateX(-50%) translateY(' + (offset - 40) + 'px)';
      ind.style.opacity = String(Math.min(1, diff / THRESHOLD));
    }
  }, { passive: true });

  document.addEventListener('touchend', function () {
    if (!isPulling) {
      startY = 0;
      return;
    }
    var diff = currentY - startY;

    if (diff >= THRESHOLD) {
      if (indicator) {
        indicator.querySelector('span').textContent = 'Refreshing...';
        indicator.style.transform = 'translateX(-50%) translateY(0)';
      }
      setTimeout(function () {
        location.reload();
      }, 300);
    } else {
      if (indicator) {
        indicator.style.transform = 'translateX(-50%) translateY(-100%)';
      }
    }

    startY = 0;
    currentY = 0;
    isPulling = false;
  }, { passive: true });

  console.log('[PTR] Pull-to-refresh loaded');
})();
