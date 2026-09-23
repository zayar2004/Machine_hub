/* Machine Hub — Service Worker v7 (offline-first) */
const VERSION = 'mh-v29';
const STATIC = VERSION + '-static';
const RUNTIME = VERSION + '-runtime';
const PHOTOS = VERSION + '-photos';
const SHELL = VERSION + '-shell';

// Precache static assets + app shell
const PRECACHE = [
  '/static/css/user.css',
  '/static/js/icons.js',
  '/static/js/theme.js',
  '/static/js/menu.js',
  '/static/js/db.js',
  '/static/js/sync.js',
  '/static/js/offline-search.js',
  '/static/js/live-search.js',
  '/static/js/smart-back.js',
  '/static/js/recent.js',
  '/static/js/favorites.js',
  '/static/js/install.js',
  '/static/js/pull-refresh.js',
  '/static/icons/sprite.svg',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
];

// App shell pages — precache for offline
const SHELL_PAGES = [
  '/offline',
  '/static/manifest.json',
];
// NOTE: Auth-required pages (/, /favorites, /recent, /history)
// are cached dynamically via staleWhileRevalidateHTML after login.
// They can't be precached at install time (no session).

self.addEventListener('install', (e) => {
  e.waitUntil(
    Promise.all([
      caches.open(STATIC).then(c => c.addAll(PRECACHE).catch(() => {})),
      caches.open(SHELL).then(c => c.addAll(SHELL_PAGES).catch(() => {})),
    ])
  );
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => !k.startsWith(VERSION)).map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  if (req.method !== 'GET') return;

  // Static assets: cache-first
  if (url.pathname.startsWith('/static/')) {
    e.respondWith(cacheFirst(req, STATIC));
    return;
  }

  // Photos: cache-first
  if (url.pathname.startsWith('/uploads/') || url.pathname.startsWith('/admin/uploads/')) {
    e.respondWith(cacheFirst(req, PHOTOS));
    return;
  }

  // Admin + Auth + health: NEVER cache
  if (
    url.pathname.startsWith('/admin') ||
    url.pathname.startsWith('/auth') ||
    url.pathname.startsWith('/health')
  ) {
    e.respondWith(
      fetch(req).catch(() =>
        new Response(
          '<!DOCTYPE html><html><head><meta charset="utf-8"><title>Offline</title></head><body style="font-family:system-ui;background:#09090b;color:#fafafa;padding:24px;"><h1>📡 Offline</h1><p>Admin pages need internet.</p></body></html>',
          { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
        )
      )
    );
    return;
  }

  // API: cache-first with background update (offline-first)
  if (url.pathname.startsWith('/api/')) {
    e.respondWith(staleWhileRevalidate(req, RUNTIME));
    return;
  }

  // HTML navigation: cache-first → network → offline page (offline-first)
  if (req.mode === 'navigate' || (req.headers.get('accept') || '').includes('text/html')) {
    e.respondWith(staleWhileRevalidateHTML(req));
    return;
  }
});

async function cacheFirst(req, cacheName) {
  const c = await caches.open(cacheName);
  const hit = await c.match(req);
  if (hit) return hit;
  try {
    const res = await fetch(req);
    if (res.ok) c.put(req, res.clone());
    return res;
  } catch (e) {
    return new Response('', { status: 504 });
  }
}

async function staleWhileRevalidate(req, cacheName) {
  // CACHE-FIRST: return cached immediately, update in background
  const c = await caches.open(cacheName);
  const hit = await c.match(req);

  if (hit) {
    // Background revalidate (non-blocking)
    fetch(req).then(res => {
      if (res && res.ok) c.put(req, res.clone());
    }).catch(() => {});
    return hit;
  }

  // Cache miss — network
  try {
    const res = await fetch(req);
    if (res.ok) c.put(req, res.clone());
    return res;
  } catch (e) {
    return new Response(
      JSON.stringify({ error: 'offline' }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    );
  }
}

async function staleWhileRevalidateHTML(req) {
  // CACHE-FIRST for HTML — offline-first navigation
  const c = await caches.open(SHELL);
  const hit = await c.match(req);

  if (hit) {
    // Background revalidate (non-blocking)
    fetch(req).then(res => {
      if (res && res.ok) c.put(req, res.clone());
    }).catch(() => {});
    return hit;
  }

  // Cache miss — network
  try {
    const res = await fetch(req);
    if (res.ok) c.put(req, res.clone());
    return res;
  } catch (e) {
    // Fallback chain: / → /offline → inline
    const root = await c.match('/');
    if (root) return root;
    const offline = await c.match('/offline');
    if (offline) return offline;
    return new Response(
      '<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Offline</title><style>body{font-family:system-ui;background:#09090b;color:#fafafa;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;padding:24px;text-align:center}h1{font-size:20px;margin-bottom:12px;font-weight:700}p{color:#a1a1aa;font-size:14px}</style></head><body><div><h1>📡 Offline</h1><p>Internet ပြန်ရလာရင် ပြန် ကြည့်ပါ။</p></div></body></html>',
      { status: 200, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
    );
  }
}
