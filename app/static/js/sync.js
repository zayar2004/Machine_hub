/* =========================================================
   Machine Hub — Sync engine (safe + offline + deletes)
   ========================================================= */
(function () {
  'use strict';

  var LOCAL_VERSION_KEY = 'local_version';
  var LAST_SYNC_KEY = 'last_sync';
  var MAX_ITERATIONS = 20;
  var AUTO_SYNC_INTERVAL = 15 * 60 * 1000;  // 15 min (background check)

  var syncing = false;

  function setStatus(state, text) {
    try {
      var dot = document.getElementById('sync-dot');
      var label = document.getElementById('sync-label');
      var indicator = document.getElementById('sync-indicator');
      if (!dot || !label) return;

      dot.classList.remove('offline', 'syncing', 'error', 'synced');

      switch (state) {
        case 'offline':
          dot.classList.add('offline');
          label.textContent = 'Offline';
          break;
        case 'syncing':
          dot.classList.add('syncing');
          label.textContent = 'Syncing…';
          break;
        case 'error':
          dot.classList.add('error');
          label.textContent = 'Sync error';
          break;
        case 'synced':
          dot.classList.add('synced');
          label.textContent = 'Synced';
          break;
        default:
          dot.classList.remove('offline');
          label.textContent = 'Online';
      }
      if (indicator) indicator.title = text || '';
    } catch (e) {
      console.warn('[Sync] setStatus error:', e);
    }
  }

  function fetchVersion() {
    return fetch('/api/sync/version', {
      credentials: 'same-origin',
      headers: { 'Accept': 'application/json' }
    }).then(function (res) {
      if (!res.ok) throw new Error('version ' + res.status);
      return res.json();
    });
  }

  function fetchChanges(since) {
    return fetch('/api/sync/changes?since=' + since, {
      credentials: 'same-origin',
      headers: { 'Accept': 'application/json' }
    }).then(function (res) {
      if (!res.ok) throw new Error('changes ' + res.status);
      return res.json();
    });
  }

  function deleteRecord(storeName, id) {
    return window.MH.db.open().then(function (db) {
      return new Promise(function (resolve) {
        try {
          var tx = db.transaction(storeName, 'readwrite');
          var store = tx.objectStore(storeName);
          store.delete(id);
          tx.oncomplete = function () { resolve(true); };
          tx.onerror = function () { resolve(false); };
          tx.onabort = function () { resolve(false); };
        } catch (e) {
          resolve(false);
        }
      });
    }).catch(function () { return false; });
  }

  function syncNow(silent) {
    if (syncing) {
      console.log('[Sync] already running');
      return Promise.resolve({ skipped: true });
    }
    if (!navigator.onLine) {
      setStatus('offline', 'No network');
      return Promise.resolve({ offline: true });
    }
    if (!window.MH || !window.MH.db) {
      return Promise.resolve({ error: 'no-db' });
    }

    syncing = true;
    if (!silent) setStatus('syncing');

    var result = {
      shops: 0, machines: 0, errors: 0, error_images: 0, users: 0,
      repair_history: 0, deletes: 0,
      iterations: 0, finalVersion: 0
    };

    return fetchVersion()
      .then(function (v) {
        var serverVersion = v.server_version || 0;
        return window.MH.db.getMeta(LOCAL_VERSION_KEY, 0).then(function (localVersion) {
          return { v: v, serverVersion: serverVersion, localVersion: localVersion };
        });
      })
      .then(function (ctx) {
        var v = ctx.v;
        return Promise.all([
          window.MH.db.setMeta('entity_versions', v.entities || {}),
          window.MH.db.setMeta('user_shop_id', v.shop_id || null),
          window.MH.db.setMeta('is_admin', v.is_admin || false)
        ]).then(function () { return ctx; });
      })
      .then(function (ctx) {
        if (ctx.localVersion >= ctx.serverVersion) {
          return window.MH.db.setMeta(LAST_SYNC_KEY, Date.now()).then(function () {
            if (!silent) setStatus('synced', 'Up to date');
            result.finalVersion = ctx.localVersion;
            return result;
          });
        }

        var cursor = ctx.localVersion;
        var iterations = 0;

        function nextPage() {
          if (iterations >= MAX_ITERATIONS) {
            return Promise.resolve(result);
          }
          iterations++;
          result.iterations = iterations;

          return fetchChanges(cursor).then(function (page) {
            var changes = page.changes || {};
            var deletes = page.deletes || [];
            var entities = ['shops', 'machines', 'errors', 'error_images',
                            'users', 'repair_history'];

            // Process deletes first
            function processDeletes(i) {
              if (i >= deletes.length) return Promise.resolve();
              var d = deletes[i];
              return deleteRecord(d.entity, d.id).then(function (ok) {
                if (ok) result.deletes++;
                return processDeletes(i + 1);
              });
            }

            return processDeletes(0).then(function () {
              // Process changes
              function saveEntity(i) {
                if (i >= entities.length) return Promise.resolve();
                var entity = entities[i];
                var items = changes[entity] || [];
                if (items.length > 0) {
                  return window.MH.db.putAll(entity, items).then(function (n) {
                    result[entity] = (result[entity] || 0) + n;
                    return saveEntity(i + 1);
                  });
                }
                return saveEntity(i + 1);
              }

              return saveEntity(0).then(function () {
                cursor = page.current_version || cursor;
                if (page.has_more) {
                  return nextPage();
                }
                return result;
              });
            });
          });
        }

        return nextPage().then(function () {
          return Promise.all([
            window.MH.db.setMeta(LOCAL_VERSION_KEY, cursor),
            window.MH.db.setMeta(LAST_SYNC_KEY, Date.now())
          ]).then(function () {
            result.finalVersion = cursor;
            if (!silent) {
              var msg = 'Synced v' + cursor;
              if (result.deletes > 0) msg += ' (' + result.deletes + ' deleted)';
              setStatus('synced', msg);
            }

            // 🆕 Auto-reload on new data (dedup per version)
            try {
              var _seenKey = 'mh_reload_seen_version';
              var _seenVer = localStorage.getItem(_seenKey);
              var _ver = (cursor != null) ? String(cursor) : null;
              var _hasNew = false;

              if (result) {
                if ((result.added || 0) > 0) _hasNew = true;
                if ((result.updated || 0) > 0) _hasNew = true;
                if ((result.new_count || 0) > 0) _hasNew = true;
                if ((result.deletes || 0) > 0) _hasNew = true;
              }

              // Fallback — version changed since last reload
              if (!_hasNew && _ver && _seenVer !== _ver) {
                _hasNew = true;
              }

              if (_hasNew && _ver && _seenVer !== _ver) {
                localStorage.setItem(_seenKey, _ver);
                console.log('[Sync] New data — reload in 800ms (v' + _ver + ')');
                setTimeout(function () { location.reload(); }, 800);
              }
            } catch (e) {
              console.warn('[Sync] auto-reload failed:', e);
            }

            return result;
          });
        });
      })
      .catch(function (err) {
        console.error('[Sync] Failed:', err);

        // Auto-recovery: VersionError → wipe old IndexedDB + retry once
        if (err && err.name === 'VersionError' && !syncNow._recovering) {
          console.warn('[Sync] VersionError — wiping local DB and retrying...');
          syncNow._recovering = true;
          syncing = false;

          if (window.MH && window.MH.db && typeof window.MH.db.wipe === 'function') {
            return window.MH.db.wipe().then(function () {
              console.log('[Sync] DB wiped — retrying sync');
              syncNow._recovering = false;
              return syncNow(silent);
            });
          }
          // Fallback — reload page
          console.warn('[Sync] No wipe available — reloading page');
          setTimeout(function () { location.reload(); }, 800);
          return { error: 'version-recover-reload' };
        }

        var detail = (err && (err.name + ': ' + err.message)) || String(err);
        if (!silent) setStatus('error', detail);

        // Show toast + modal (no native alert)
        showSyncError(detail, err);

        return { error: err.message || String(err) };
      })
      .then(function (r) {
        syncing = false;
        return r;
      });
  }

  // =========================================================
  // Toast + Sync Error Modal
  // =========================================================
  var _lastErrorShown = null;

  function showToast(message, type, onClick) {
    try {
      var container = document.getElementById('mh-toast-container');
      if (!container) return;

      var toast = document.createElement('div');
      toast.className = 'mh-toast';

      var iconCls = type === 'success' ? 'mh-toast-icon-success' : 'mh-toast-icon-warn';
      var iconHref = type === 'success' ? '#i-check' : '#i-alert';
      toast.innerHTML =
        '<div class="mh-toast-icon ' + iconCls + '">' +
          '<svg class="icon icon-sm"><use href="' + iconHref + '"/></svg>' +
        '</div>' +
        '<div class="mh-toast-text"></div>';
      toast.querySelector('.mh-toast-text').textContent = message;

      if (typeof onClick === 'function') {
        toast.addEventListener('click', onClick);
      }

      container.appendChild(toast);

      setTimeout(function () {
        toast.classList.add('out');
        setTimeout(function () {
          if (toast.parentNode) toast.parentNode.removeChild(toast);
        }, 220);
      }, 4000);
    } catch (e) {
      console.warn('[Sync] showToast error:', e);
    }
  }

  function showSyncError(detail, err) {
    // Dedup: same detail → show once per session
    if (_lastErrorShown === detail) return;
    _lastErrorShown = detail;

    // Populate modal
    try {
      var msgEl = document.getElementById('sync-error-message');
      var statusEl = document.getElementById('sync-error-status');
      var localEl = document.getElementById('sync-error-local');
      var serverEl = document.getElementById('sync-error-server');
      if (msgEl) msgEl.textContent = detail || 'Unknown sync error.';

      // Try to read local version
      if (window.MH && window.MH.db && localEl) {
        window.MH.db.getMeta(LOCAL_VERSION_KEY).then(function (v) {
          localEl.textContent = v != null ? String(v) : '—';
        }).catch(function () {});
      }
      if (statusEl) statusEl.textContent = 'Sync failed';
      if (serverEl) {
        fetchVersion().then(function (info) {
          serverEl.textContent = info && info.server_version != null
            ? String(info.server_version) : '—';
        }).catch(function () {});
      }
    } catch (e) { console.warn('[Sync] modal populate error:', e); }

    // Show toast
    showToast('Sync error — tap to see details', 'warn', function () {
      openSyncErrorModal();
    });
  }

  function openSyncErrorModal() {
    var m = document.getElementById('sync-error-modal');
    if (!m) return;
    m.classList.add('open');
    m.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }

  function hideSyncError() {
    var m = document.getElementById('sync-error-modal');
    if (!m) return;
    m.classList.remove('open');
    m.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  }

  // Expose for template onclick handlers
  window.MH_Sync = window.MH_Sync || {};
  window.MH_Sync.hideSyncError = hideSyncError;
  window.MH_Sync.openSyncErrorModal = openSyncErrorModal;

  // Topbar chip → open modal
  function bindTopbarChip() {
    var indicator = document.getElementById('sync-indicator');
    if (!indicator) return;
    indicator.style.cursor = 'pointer';
    indicator.addEventListener('click', function () {
      var dot = document.getElementById('sync-dot');
      if (dot && dot.classList.contains('error')) {
        openSyncErrorModal();
      } else {
        syncNow(true);
      }
    });
  }

  // Retry button
  function bindRetryButton() {
    var btn = document.getElementById('sync-retry-btn');
    if (!btn) return;
    btn.addEventListener('click', function () {
      hideSyncError();
      _lastErrorShown = null;
      syncNow(false);
    });
  }

  function backgroundSync() {
    // Check version only — data fetch only if changed
    fetchVersion().then(function(v) {
      var localVer = parseInt(localStorage.getItem(LOCAL_VERSION_KEY) || '0', 10);
      var serverVer = (v && v.server_version) || 0;
      if (serverVer > localVer) {
        syncNow(true);  // Data changed — silent sync
      }
      // else skip — save battery/data
    }).catch(function() {
      // Silent fail
    });
  }

  function initSync() {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', function () {
        bindTopbarChip();
        bindRetryButton();
      });
    } else {
      bindTopbarChip();
      bindRetryButton();
    }

    setTimeout(function () {
      try {
        var firstSync = localStorage.getItem('mh_first_sync');
        if (!firstSync) {
          // First open — full sync (visible)
          syncNow(false);
          localStorage.setItem('mh_first_sync', '1');
        } else {
          // Already synced — background check
          backgroundSync();
        }
      } catch (e) {}
    }, 1500);

    window.addEventListener('online', function () {
      setStatus('online');
      try { syncNow(false); } catch (e) {}
    });

    window.addEventListener('offline', function () {
      setStatus('offline');
    });

    setInterval(function () {
      if (navigator.onLine) {
        try { backgroundSync(); } catch (e) {}
      }
    }, AUTO_SYNC_INTERVAL);

    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState === 'visible' && navigator.onLine) {
        try { syncNow(true); } catch (e) {}
      }
    });

    document.querySelectorAll('[data-sync-now]').forEach(function (el) {
      el.addEventListener('click', function (e) {
        e.preventDefault();
        try { syncNow(false); } catch (err) {}
      });
    });
  }

  window.MH = window.MH || {};
  window.MH.sync = {
    now: syncNow,
    setStatus: setStatus
  };

  document.addEventListener('DOMContentLoaded', initSync);
  console.log('[Sync] Engine loaded');
})();
