const CACHE_NAME = 'rechiro-cache-v1';
const ASSETS_TO_CACHE = [
  '/',
  '/fishing/home/',
  '/fishing/',
  '/static/branding/rechiro-logo.svg',
  '/static/branding/rechiro-192.png',
  '/static/branding/rechiro-512.png',
  '/static/manifest.json'
];
const IMAGE_FALLBACK = '/static/branding/rechiro-logo.svg';

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

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') {
    return;
  }

  const isHtmlRequest = event.request.mode === 'navigate' ||
    (event.request.headers.get('accept') || '').includes('text/html');

  if (isHtmlRequest) {
    // Use network-first for HTML pages so login state and dynamic content stays fresh.
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          // Only cache successful (200) same-origin HTML responses.
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

  // Cache-first for other assets (images, CSS, JS, etc.)
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
});
