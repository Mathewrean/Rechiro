const CACHE_NAME = 'rechiro-cache-v1';
const ASSETS_TO_CACHE = [
  '/',
  '/fishing/home/',
  '/fishing/',
  '/static/branding/rechiro_logo.png',
  '/static/branding/rechiro-192.png',
  '/static/branding/rechiro-512.png',
  '/static/manifest.json',
  '/static/style.css'
];
const IMAGE_FALLBACK = '/static/branding/rechiro-512.png';
const CATALOG_URL = '/fishing/api/catalog/';

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS_TO_CACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    ).then(() => self.clients.claim())
  );
});

// Catalog caching for offline access
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') {
    return;
  }

  const url = new URL(event.request.url);
  
  // Cache fish catalog for offline access
  if (url.pathname === CATALOG_URL || url.pathname.includes('/fishing/marketplace/')) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, responseClone));
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  const isHtmlRequest = event.request.mode === 'navigate' ||
    (event.request.headers.get('accept') || '').includes('text/html');

  if (isHtmlRequest) {
    // Network-first for HTML pages
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response && response.status === 200 && response.type === 'basic') {
            const responseClone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, responseClone));
          }
          return response;
        })
        .catch(() => caches.match(event.request) || caches.match(ASSETS_TO_CACHE[0]))
    );
    return;
  }

  // Cache-first for static assets (skip media files)
if (!url.pathname.startsWith('/media/')) {
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) {
        return cached;
      }
      return fetch(event.request)
        .then((response) => {
          if (!response || response.status !== 200 || response.type !== 'basic') {
            return response;
          }
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, responseClone));
          return response;
        })
        .catch(() => {
          if (event.request.destination === 'image') {
            return caches.match(IMAGE_FALLBACK);
          }
          return caches.match(ASSETS_TO_CACHE[0]);
        });
    })
  );
}
});

// Handle offline cart sync
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-cart') {
    event.waitUntil(
      self.clients.matchAll({ type: 'window' }).then((clients) => {
        clients.forEach((client) => client.postMessage({ type: 'SYNC_CART' }));
      })
    );
  }
});
