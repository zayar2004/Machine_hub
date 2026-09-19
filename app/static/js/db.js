/* =========================================================
   Machine Hub — IndexedDB wrapper
   Stores: shops, machines, errors, error_images,
           repair_history, meta
   ========================================================= */
(function () {
  'use strict';

  var DB_NAME = 'machine_hub';
  var DB_VERSION = 5;  // bumped + auto-recovery for VersionError

  var STORES = {
    shops: { keyPath: 'id' },
    machines: { keyPath: 'id', indexes: ['shop_id', 'machine_code'] },
    errors: { keyPath: 'id', indexes: ['error_code'] },
    error_images: { keyPath: 'id', indexes: ['error_id'] },
    repair_history: { keyPath: 'id', indexes: ['machine_id'] },
    meta: { keyPath: 'key' },
  };

  var dbPromise = null;

  function openDB() {
    if (dbPromise) return dbPromise;

    dbPromise = new Promise(function (resolve, reject) {
      var req;
      try {
        req = indexedDB.open(DB_NAME, DB_VERSION);
      } catch (e) {
        dbPromise = null;
        reject(e);
        return;
      }

      req.onupgradeneeded = function (event) {
        var db = event.target.result;
        var oldVersion = event.oldVersion;

        for (var name in STORES) {
          if (!STORES.hasOwnProperty(name)) continue;
          var cfg = STORES[name];

          if (!db.objectStoreNames.contains(name)) {
            var store = db.createObjectStore(name, { keyPath: cfg.keyPath });
            if (cfg.indexes) {
              for (var i = 0; i < cfg.indexes.length; i++) {
                var idx = cfg.indexes[i];
                try {
                  store.createIndex(idx, idx, { unique: false });
                } catch (e) {
                  console.warn('[IDB] index exists:', idx);
                }
              }
            }
          }
        }
      };

      req.onsuccess = function () { resolve(req.result); };

      req.onerror = function () {
        var err = req.error;
        dbPromise = null;  // reset so next call can retry
        reject(err);
      };

      req.onblocked = function () {
        console.warn('[IDB] open blocked — close other tabs');
      };
    });

    return dbPromise;
  }

  // =========================================================
  // Auto-recovery: delete DB and re-open fresh
  // =========================================================
  function wipeDB() {
    return new Promise(function (resolve) {
      try {
        var req = indexedDB.deleteDatabase(DB_NAME);
        req.onsuccess = function () { resolve(true); };
        req.onerror = function () { resolve(false); };
        req.onblocked = function () {
          console.warn('[IDB] delete blocked');
          resolve(false);
        };
      } catch (e) {
        console.warn('[IDB] wipe error:', e);
        resolve(false);
      }
    });
  }

  function openDBWithRecovery() {
    return openDB().catch(function (err) {
      if (err && err.name === 'VersionError') {
        console.warn('[IDB] VersionError — wiping and retrying');
        return wipeDB().then(function () {
          dbPromise = null;
          return openDBWithRecovery();
        });
      }
      throw err;
    });
  }

  function tx(storeName, mode) {
    mode = mode || 'readonly';
    return openDB().then(function (db) {
      var t = db.transaction(storeName, mode);
      return { tx: t, store: t.objectStore(storeName) };
    });
  }

  // ---------- Generic CRUD ----------

  function putAll(storeName, items) {
    if (!items || items.length === 0) return Promise.resolve(0);
    return tx(storeName, 'readwrite').then(function (ctx) {
      return new Promise(function (resolve, reject) {
        var count = 0;
        for (var i = 0; i < items.length; i++) {
          var item = items[i];
          if (item == null || item.id == null) continue;
          try {
            ctx.store.put(item);
            count++;
          } catch (e) {
            console.warn('[IDB] put error:', e);
          }
        }
        ctx.tx.oncomplete = function () { resolve(count); };
        ctx.tx.onerror = function () { reject(ctx.tx.error); };
        ctx.tx.onabort = function () { reject(ctx.tx.error || new Error('tx aborted')); };
      });
    });
  }

  function getAll(storeName) {
    return tx(storeName, 'readonly').then(function (ctx) {
      return new Promise(function (resolve, reject) {
        var req = ctx.store.getAll();
        req.onsuccess = function () { resolve(req.result || []); };
        req.onerror = function () { reject(req.error); };
      });
    });
  }

  function get(storeName, id) {
    return tx(storeName, 'readonly').then(function (ctx) {
      return new Promise(function (resolve, reject) {
        var req = ctx.store.get(id);
        req.onsuccess = function () { resolve(req.result); };
        req.onerror = function () { reject(req.error); };
      });
    });
  }

  function getByIndex(storeName, indexName, value) {
    return tx(storeName, 'readonly').then(function (ctx) {
      var idx = ctx.store.index(indexName);
      return new Promise(function (resolve, reject) {
        var req = idx.getAll(value);
        req.onsuccess = function () { resolve(req.result || []); };
        req.onerror = function () { reject(req.error); };
      });
    });
  }

  function count(storeName) {
    return tx(storeName, 'readonly').then(function (ctx) {
      return new Promise(function (resolve, reject) {
        var req = ctx.store.count();
        req.onsuccess = function () { resolve(req.result); };
        req.onerror = function () { reject(req.error); };
      });
    });
  }

  function clearStore(storeName) {
    return tx(storeName, 'readwrite').then(function (ctx) {
      return new Promise(function (resolve, reject) {
        ctx.store.clear();
        ctx.tx.oncomplete = function () { resolve(); };
        ctx.tx.onerror = function () { reject(ctx.tx.error); };
      });
    });
  }

  function clearAll() {
    var names = Object.keys(STORES);
    var i = 0;
    function next() {
      if (i >= names.length) return Promise.resolve();
      var n = names[i++];
      return clearStore(n).then(next).catch(next);
    }
    return next();
  }

  // ---------- Meta ----------

  function setMeta(key, value) {
    return tx('meta', 'readwrite').then(function (ctx) {
      return new Promise(function (resolve, reject) {
        ctx.store.put({ key: key, value: value });
        ctx.tx.oncomplete = function () { resolve(); };
        ctx.tx.onerror = function () { reject(ctx.tx.error); };
      });
    });
  }

  function getMeta(key, defaultValue) {
    if (defaultValue === undefined) defaultValue = null;
    return get('meta', key).then(function (row) {
      return row ? row.value : defaultValue;
    });
  }

  // ---------- Expose ----------

  window.MH = window.MH || {};
  window.MH.db = {
    open: openDB,
    openWithRecovery: openDBWithRecovery,
    wipe: wipeDB,
    putAll: putAll,
    getAll: getAll,
    get: get,
    getByIndex: getByIndex,
    count: count,
    clearStore: clearStore,
    clearAll: clearAll,
    setMeta: setMeta,
    getMeta: getMeta,
    STORES: STORES,
  };

  console.log('[IDB] Wrapper loaded (v' + DB_VERSION + ')');
})();
