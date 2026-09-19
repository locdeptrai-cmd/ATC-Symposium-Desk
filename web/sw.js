var CACHE = "atc-symposium-desk-v38";
var ASSETS = [
  "./",
  "./index.html",
  "./glossary.html",
  "./recordings.html",
  "./finetune.html",
  "./briefs.html",
  "./cai-dat.html",
  "./css/app.css",
  "./js/creator-lock.js",
  "./js/glossary.js",
  "./js/library-data.js",
  "./js/library.js",
  "./data/library.sqlite",
  "./data/library.json",
  "./js/topics.js",
  "./js/lexicon.js",
  "./js/dict-en-vi.js",
  "./js/mt-bridge.js",
  "./js/translate.js",
  "./js/replies.js",
  "./js/speech-repair.js",
  "./js/speech.js",
  "./js/app.js",
  "./js/glossary-ui.js",
  "./js/glossary-editor.js",
  "./js/recordings.js",
  "./js/finetune.js",
  "./js/pwa.js",
  "./manifest.json",
  "./icons/icon.jpg",
  "./icons/icon-180.png",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/icon-maskable-512.png"
];

function precache() {
  return caches.open(CACHE).then(function (cache) {
    return Promise.all(
      ASSETS.map(function (url) {
        return cache.add(url);
      })
    );
  });
}

self.addEventListener("install", function (event) {
  event.waitUntil(precache().then(function () {
    return self.skipWaiting();
  }));
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches
      .keys()
      .then(function (keys) {
        return Promise.all(
          keys
            .filter(function (k) {
              return k.indexOf("atc-symposium-desk-") === 0 && k !== CACHE;
            })
            .map(function (k) {
              return caches.delete(k);
            })
        );
      })
      .then(function () {
        return self.clients.claim();
      })
  );
});

self.addEventListener("fetch", function (event) {
  var req = event.request;
  if (req.method !== "GET") return;
  var url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.indexOf("/api/") === 0) return;
  if (url.pathname.indexOf("/certs/") >= 0) return;
  if (url.pathname.indexOf("/SIGNATURE.txt") >= 0) return;

  event.respondWith(
    caches.match(req, { ignoreSearch: true }).then(function (hit) {
      if (hit) return hit;
      return fetch(req)
        .then(function (res) {
          if (res && res.ok && res.type === "basic") {
            var copy = res.clone();
            caches.open(CACHE).then(function (cache) {
              cache.put(req, copy);
            });
          }
          return res;
        })
        .catch(function () {
          if (req.mode === "navigate") {
            return caches.match("./index.html");
          }
          var fallback = url.pathname.split("/").pop();
          if (fallback) {
            return caches.match("./" + fallback);
          }
          return caches.match("./index.html");
        });
    })
  );
});
