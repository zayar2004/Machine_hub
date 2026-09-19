/* Icon sprite loader + helper */
(function () {
  'use strict';
  function loadSprite() {
    if (document.getElementById('mh-sprite')) return;
    fetch('/static/icons/sprite.svg')
      .then(r => r.text())
      .then(svg => {
        const d = document.createElement('div');
        d.id = 'mh-sprite';
        d.style.cssText = 'position:absolute;width:0;height:0;overflow:hidden;';
        d.innerHTML = svg;
        document.body.insertBefore(d, document.body.firstChild);
      })
      .catch(e => console.warn('[Icons]', e));
  }
  document.addEventListener('DOMContentLoaded', loadSprite);
  console.log('[Icons] loaded');
})();
