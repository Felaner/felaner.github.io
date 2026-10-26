// Офлайн-режим: вики открывается без сети после первого визита.
// Страница — сначала из сети (чтобы видеть обновления), без сети — из кэша.
// Скрипты и данные с версией в адресе (?v=…) — из кэша; при новой версии старые копии удаляются.
// Картинки и шрифты кэшируются по мере просмотра.
const CACHE = "br-wiki-v1";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", ev => {
  ev.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

async function put(req, resp) {
  if (!resp || !resp.ok || resp.type === "opaqueredirect") return resp;
  const cache = await caches.open(CACHE);
  const url = new URL(req.url);
  // Тот же файл другой версии больше не нужен.
  if (url.searchParams.has("v")) {
    for (const k of await cache.keys()) {
      const ku = new URL(k.url);
      if (ku.origin === url.origin && ku.pathname === url.pathname && ku.search !== url.search) cache.delete(k);
    }
  }
  cache.put(req, resp.clone());
  return resp;
}

async function cacheFirst(req) {
  const hit = await caches.match(req);
  if (hit) return hit;
  return put(req, await fetch(req));
}

async function networkFirst(req) {
  try {
    return await put(req, await fetch(req));
  } catch {
    return (await caches.match(req)) || (await caches.match("./")) || Response.error();
  }
}

self.addEventListener("fetch", ev => {
  const req = ev.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  const fonts = /fonts\.(googleapis|gstatic)\.com$/.test(url.hostname);
  if (url.origin !== self.location.origin && !fonts) return;
  if (req.mode === "navigate" || url.pathname.endsWith(".html") || url.pathname.endsWith("/")) {
    ev.respondWith(networkFirst(req));
  } else {
    ev.respondWith(cacheFirst(req));
  }
});
