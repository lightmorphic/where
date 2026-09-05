/* Keeps the app usable on a poor connection without ever pretending to be
   online. Pages always come from the server; if the server cannot be reached
   you get a page that says so, never a stale copy that looks live and then
   swallows whatever you type into it. */
var CACHE = 'where-v2';
var OFFLINE = '/offline';
var SHELL = ['/static/css/main.css', '/static/js/main.js', '/static/fonts/manrope.woff2',
             '/static/icons/icon.svg', OFFLINE];

self.addEventListener('install', function (e) {
  e.waitUntil(
    caches.open(CACHE)
      .then(function (c) { return c.addAll(SHELL).catch(function () {}); })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; })
                           .map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') { return; }   // never touch a form being submitted
  var url = new URL(req.url);
  if (url.origin !== self.location.origin) { return; }

  // Pictures and the stylesheet are safe to serve from the cache and refresh
  // behind your back: they are the same bytes every time.
  if (url.pathname.startsWith('/static/') || url.pathname.startsWith('/photos/')) {
    e.respondWith(caches.open(CACHE).then(function (c) {
      return c.match(req).then(function (hit) {
        var fresh = fetch(req).then(function (res) {
          if (res.ok) { c.put(req, res.clone()); }
          return res;
        });
        return hit || fresh;
      });
    }));
    return;
  }

  // A page. Always ask the server, because what it says may have changed and a
  // remembered copy would be a lie.
  if (req.mode === 'navigate') {
    e.respondWith(fetch(req).catch(function () {
      return caches.match(OFFLINE).then(function (hit) {
        return hit || new Response('Where cannot be reached.', {
          status: 503, headers: { 'Content-Type': 'text/plain' }
        });
      });
    }));
  }
});
