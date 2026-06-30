const CACHE = "sindgreen-mentor-v84";
const ASSETS = [
  "/icons/icon-192.jpg",
  "/videos/moment-banner.webp",
  "/videos/moment-poster.jpg",
];
const NETWORK_FIRST = ["/", "/index.html", "/app.js", "/style.css", "/sw.js"];

function isNetworkFirst(url) {
  const path = url.pathname;
  if (NETWORK_FIRST.includes(path)) return true;
  if (path === "/app.js" || path === "/style.css") return true;
  if (path.startsWith("/app.js") || path.startsWith("/style.css")) return true;
  return false;
}

self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") self.skipWaiting();
});

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then(async (cache) => {
      for (const url of ASSETS) {
        try {
          await cache.add(url);
        } catch {
          /* ignora falhas pontuais no cache */
        }
      }
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
      .then(() => self.clients.matchAll({ type: "window" }).then((clients) => {
        clients.forEach((client) => client.postMessage({ type: "SW_ACTIVATED" }));
      }))
  );
});

self.addEventListener("push", (event) => {
  let title = "Betting Brain";
  let body = "Nova oportunidade ao vivo";
  try {
    const data = event.data ? event.data.json() : {};
    title = data.title || title;
    body = data.body || body;
  } catch {
    if (event.data) body = event.data.text();
  }
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon: "/icons/icon-192.jpg",
      badge: "/icons/icon-192.jpg",
      data: { url: "/", evKey: null },
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const data = event.notification.data || {};
  const target = data.url || "/";
  const evKey = data.evKey || null;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if ("focus" in client) {
          client.postMessage({ type: "sgm-notification", url: target, evKey });
          return client.focus();
        }
      }
      if (self.clients.openWindow) return self.clients.openWindow(target);
      return undefined;
    })
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;

  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith("/api/")) {
    event.respondWith(fetch(event.request));
    return;
  }

  if (event.request.mode === "navigate" || isNetworkFirst(url)) {
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          if (res.ok && event.request.mode === "navigate") {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put("/index.html", copy));
          }
          return res;
        })
        .catch(() =>
          caches.match("/index.html").then(
            (cached) => cached || new Response(
              "<!DOCTYPE html><html lang='pt'><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>A ligar…</title><body style='font-family:sans-serif;background:#0a2a20;color:#eee;text-align:center;padding:2rem'><h1>A ligar o servidor…</h1><p>No plano grátis o Render demora ~1 minuto a acordar.</p><p>Refresca daqui a pouco.</p><script>setTimeout(()=>location.reload(),45000)</script></body></html>",
              { status: 503, headers: { "Content-Type": "text/html; charset=utf-8" } }
            )
          )
        )
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(event.request, copy));
        }
        return res;
      });
    })
  );
});