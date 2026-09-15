/**
 * A deliberately minimal, honest service worker — NOT a full pre-cached
 * PWA. It doesn't know Next.js's build output filenames in advance (they
 * change every build), so there's no install-time precache list here.
 * Instead it caches pages and static assets AS THEY'RE ACTUALLY VISITED
 * while online (a standard "runtime caching" pattern), so a page you
 * already opened today can still open again after the connection drops
 * — a page you never visited while online still can't load offline.
 * That's a real, useful improvement over "the app just fails to load
 * on refresh with no connection" without overclaiming full offline
 * coverage of the entire site.
 */

const CACHE_NAME = "nsaabodee-runtime-v1";
const STATIC_ASSET_PATTERN = /\/_next\/static\//;

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return; // never cache/interfere with writes — those go through the app's own offline queue instead
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return; // never intercept API calls to a different host

  // Hashed, immutable build assets — cache-first, they never change under the same filename.
  if (STATIC_ASSET_PATTERN.test(url.pathname)) {
    event.respondWith(
      caches.match(request).then((cached) => {
        if (cached) return cached;
        return fetch(request).then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          return response;
        });
      })
    );
    return;
  }

  // Page navigations — network-first (always prefer live data when
  // there's a connection), falling back to whatever was last cached for
  // this exact URL when there isn't.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          return response;
        })
        .catch(() => caches.match(request).then((cached) => cached || caches.match("/")))
    );
  }
});
