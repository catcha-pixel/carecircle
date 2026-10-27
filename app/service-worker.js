// Lets CareCircle install like an app and open without internet.
// App files: network first (so you see your latest code), saved copy as a backup.
// The text reader (vendor/): saved after the first download, since it's large and never changes.
// Checking messages and pills still needs internet.

const CACHE = "carecircle-v3";
const APP_SHELL = [
  "./", "./index.html", "./styles.css", "./manifest.webmanifest", "./icons/icon-192.png",
  "./js/ocr.js", "./js/app.js", "./js/scam.js", "./js/pills.js", "./js/contacts.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== location.origin) return;

  if (url.pathname.includes("/vendor/")) {
    event.respondWith(
      caches.match(event.request).then((saved) => saved || fetch(event.request).then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        }
        return response;
      }))
    );
    return;
  }

  // API answers are never saved.
  if (url.pathname.startsWith("/check-message") || url.pathname.startsWith("/meds") || url.pathname.startsWith("/pills")) return;

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
