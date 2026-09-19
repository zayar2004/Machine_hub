/* Recent searches — IndexedDB store */
(function () {
  'use strict';

  var STORE = 'recent_searches';
  var MAX = 30;

  function openDB() {
    return new Promise(function (resolve, reject) {
      var req = indexedDB.open('machine_hub');
      req.onsuccess = function () {
        var db = req.result;
        if (db.objectStoreNames.contains(STORE)) {
          resolve(db);
          return;
        }
        // Upgrade to add store
        var newVersion = db.version + 1;
        db.close();
        var req2 = indexedDB.open('machine_hub', newVersion);
        req2.onupgradeneeded = function (e) {
          var db2 = e.target.result;
          if (!db2.objectStoreNames.contains(STORE)) {
            db2.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true });
          }
        };
        req2.onsuccess = function () { resolve(req2.result); };
        req2.onerror = function () { reject(req2.error); };
      };
      req.onerror = function () { reject(req.error); };
    });
  }

  function addRecent(query, type) {
    if (!query || !query.trim()) return Promise.resolve();
    return openDB().then(function (db) {
      var tx = db.transaction(STORE, 'readwrite');
      var store = tx.objectStore(STORE);

      return new Promise(function (resolve) {
        var r = store.getAll();
        r.onsuccess = function () {
          var all = r.result || [];
          var dup = null;
          for (var i = 0; i < all.length; i++) {
            if (all[i].query &&
                all[i].query.toLowerCase() === query.toLowerCase() &&
                all[i].type === type) {
              dup = all[i];
              break;
            }
          }
          if (dup) store.delete(dup.id);

          store.add({
            query: query.trim(),
            type: type || 'all',
            at: Date.now()
          });

          // Trim
          var r2 = store.getAll();
          r2.onsuccess = function () {
            var after = r2.result || [];
            if (after.length > MAX) {
              var sorted = after.sort(function (a, b) { return a.at - b.at; });
              var remove = sorted.slice(0, sorted.length - MAX);
              for (var j = 0; j < remove.length; j++) store.delete(remove[j].id);
            }
          };

          tx.oncomplete = function () { db.close(); resolve(); };
          tx.onerror = function () { db.close(); resolve(); };
        };
      });
    }).catch(function (e) {
      console.warn('[Recent] add failed:', e);
    });
  }

  function getRecents(limit) {
    limit = limit || 30;
    return openDB().then(function (db) {
      var tx = db.transaction(STORE, 'readonly');
      var store = tx.objectStore(STORE);
      return new Promise(function (resolve) {
        var r = store.getAll();
        r.onsuccess = function () {
          var all = r.result || [];
          db.close();
          all.sort(function (a, b) { return b.at - a.at; });
          resolve(all.slice(0, limit));
        };
        r.onerror = function () { db.close(); resolve([]); };
      });
    }).catch(function () { return []; });
  }

  function clearRecents() {
    return openDB().then(function (db) {
      var tx = db.transaction(STORE, 'readwrite');
      tx.objectStore(STORE).clear();
      return new Promise(function (resolve) {
        tx.oncomplete = function () { db.close(); resolve(true); };
        tx.onerror = function () { db.close(); resolve(false); };
      });
    }).catch(function () { return false; });
  }

  // Auto-record search
  function autoRecord() {
    try {
      var params = new URLSearchParams(location.search);
      var q = params.get('q');
      var type = params.get('type') || 'all';
      if (q && location.pathname === '/search') {
        addRecent(q, type);
      }
    } catch (e) {}
  }

  // Expose
  window.MH = window.MH || {};
  window.MH.recent = {
    add: addRecent,
    list: getRecents,
    clear: clearRecents,
    STORE: STORE,
  };

  document.addEventListener('DOMContentLoaded', autoRecord);
  console.log('[Recent] loaded');
})();
