/* Offline search — IndexedDB fallback with machine join */
(function () {
  'use strict';

  function normalize(s) {
    return (s || '').toString().trim().toLowerCase();
  }

  function getField(item, field) {
    return normalize(item[field]);
  }

  function matchWords(item, words) {
    const haystack = [
      item.machine_code, item.machine_name, item.description,
      item.error_code, item.error_name, item.error_fix, item.explanation,
    ].map(f => normalize(f)).join(' ');
    return words.every(w => haystack.includes(w));
  }

  // Tokenize machine code/name into keywords (>= 3 chars)
  function machineTokens(m) {
    const text = (m.machine_code || '') + ' ' + (m.machine_name || '');
    return text.toLowerCase().split(/[\s_\-./]+/).filter(t => t.length >= 3);
  }

  // Check if error's machine_name pattern overlaps with any machine token
  function errorMatchesMachine(e, m) {
    const pattern = (e.machine_pattern || e.machine_name || '').toLowerCase();
    if (!pattern) return false;
    const tokens = machineTokens(m);
    return tokens.some(tok => pattern.includes(tok));
  }

  // ---------- Enrich errors with machine names ----------

  async function enrichErrors(errors) {
    if (!errors || !errors.length) return errors;

    // Load all machine_errors from IndexedDB (if we have it) OR
    // build from error → machine relationship
    // IndexedDB stores machines and errors but not the join table.
    // Solution: error_images and machine_errors are synced via API.
    // For now, use the machines list + the error's own 'machines' field
    // (which sync API includes).

    return errors;
  }

  // ---------- Search ----------

  async function searchLocal(q, type) {
    if (!window.MH || !window.MH.db) return { machines: [], errors: [] };

    const query = normalize(q);
    if (!query) return { machines: [], errors: [] };

    const words = query.split(/\s+/).filter(w => w.length > 0);
    const result = { machines: [], errors: [] };

    const allMachines = await window.MH.db.getAll('machines');
    const allErrors = await window.MH.db.getAll('errors');
    const machineById = {};
    allMachines.forEach(m => { machineById[m.id] = m; });

    const userShopId = await window.MH.db.getMeta('user_shop_id', null);

    // Helper: enrich error with machine info
    // Matches via BOTH: (1) M2M linkage (e.machine_ids), (2) error.machine_name pattern
    function enrichError(e) {
      const seen = new Set();
      let machines = [];

      // 1) M2M linkage
      if (e.machine_ids && Array.isArray(e.machine_ids)) {
        e.machine_ids.forEach(id => {
          const m = machineById[id];
          if (m && !seen.has(m.id)) {
            seen.add(m.id);
            machines.push(m);
          }
        });
      }

      // 2) Auto-pair via error.machine_name pattern
      const pattern = (e.machine_pattern || e.machine_name || '').toLowerCase();
      if (pattern) {
        allMachines.forEach(m => {
          if (seen.has(m.id)) return;
          if (errorMatchesMachine(e, m)) {
            seen.add(m.id);
            machines.push(m);
          }
        });
      }

      // 3) Shop-scope filter (non-admin)
      if (userShopId) {
        machines = machines.filter(m => m.shop_id === userShopId);
      }

      return {
        ...e,
        machines: machines,
        machine_count: machines.length,
      };
    }

    // Helper: enrich machine with related errors
    function enrichMachine(m) {
      const relatedErrors = allErrors
        .filter(e => e.machine_ids && e.machine_ids.includes(m.id))
        .slice(0, 5)
        .map(e => ({
          id: e.id,
          error_code: e.error_code,
          error_name: e.error_name,
          category: e.category || 'ERROR',
        }));
      return {
        ...m,
        errors: relatedErrors,
        error_count: relatedErrors.length,
      };
    }

    if (type === 'all' || type === 'machine') {
      const matched = allMachines.filter(m => matchWords(m, words));
      result.machines = matched.slice(0, 50).map(enrichMachine);

      // Collect related error IDs from matched machines (M2M + pattern)
      const relatedErrorIds = new Set();
      matched.forEach(m => {
        allErrors.forEach(e => {
          const m2mMatch = e.machine_ids && e.machine_ids.includes(m.id);
          const patternMatch = (typeof errorMatchesMachine === 'function') && errorMatchesMachine(e, m);
          if (m2mMatch || patternMatch) relatedErrorIds.add(e.id);
        });
      });

      // Include related errors in results
      if (relatedErrorIds.size > 0) {
        result._relatedErrorIds = Array.from(relatedErrorIds);
      }
    }

    if (type === 'all' || type === 'error') {
      const filtered = allErrors.filter(e => matchWords(e, words));
      result.errors = filtered.slice(0, 50).map(enrichError);
    }

    // If machine search — include related errors (deduped)
    if (result._relatedErrorIds && result._relatedErrorIds.length > 0) {
      const existingIds = new Set(result.errors.map(e => e.id));
      const extraIds = result._relatedErrorIds.filter(id => !existingIds.has(id));
      if (extraIds.length > 0) {
        const extra = allErrors
          .filter(e => extraIds.includes(e.id))
          .slice(0, 50)
          .map(enrichError);
        result.errors = result.errors.concat(extra);
      }
    }

    delete result._relatedErrorIds;
    return result;
  }

  async function search(q, type = 'all') {
    if (!navigator.onLine) {
      return { source: 'local', ...(await searchLocal(q, type)) };
    }

    try {
      const res = await fetch(
        `/api/search?q=${encodeURIComponent(q)}&type=${type}`,
        { credentials: 'same-origin', headers: { 'Accept': 'application/json' } }
      );
      if (!res.ok) throw new Error('server ' + res.status);
      const data = await res.json();
      return { source: 'server', ...data };
    } catch (err) {
      console.warn('[Search] server failed, fallback local:', err);
      return { source: 'local', ...(await searchLocal(q, type)) };
    }
  }

  window.MH = window.MH || {};
  window.MH.search = { search, searchLocal };

  console.log('[Search] Offline search loaded');
})();
