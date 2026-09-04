/* Keeps the app shell available when the connection is poor. Pages are always
   fetched fresh when possible; static files are cached. */
var CACHE = 'where-v1';
var SHELL = ['/static/css/main.css', '/static/js/main.js', '/static/fonts/manrope.woff2', '/static/icons/icon.svg'];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(SHELL).catch(function () {}); }).then(function () { return self.skipWaiting(); }));
});
self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});
self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;
  var url = new URL(req.url);
  if (url.pathname.startsWith('/static/') || url.pathname.startsWith('/photos/')) {
    // Serve from cache straight away, refresh the copy in the background.
    e.respondWith(caches.open(CACHE).then(function (c) {
      return c.match(req).then(function (hit) {
        var refresh = fetch(req).then(function (res) { if (res.ok) c.put(req, res.clone()); return res; });
        return hit || refresh;
      });
    }));
    return;
  }
  e.respondWith(fetch(req).catch(function () { return caches.match(req); }));
});
