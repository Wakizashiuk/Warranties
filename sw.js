// Offline support: keeps the app itself available without a connection.
// Your warranty data is never cached here; it lives on the device and in your private repo.
const CACHE = 'hw-app-v3';
const SHELL = ['./index.html', './manifest.webmanifest', './icon.svg', './icon-192.png', './icon-512.png', './icon-180.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

async function fromNetwork(url, ms) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try {
    let res = await fetch(url, { cache: 'no-store', signal: ctrl.signal });
    // A redirected response can't be used for a page load, so copy it into a plain one.
    if (res.redirected) res = new Response(await res.blob(), { status: res.status, statusText: res.statusText, headers: res.headers });
    return res;
  } finally { clearTimeout(timer); }
}

self.addEventListener('fetch', e => {
  const req = e.request;
  const url = new URL(req.url);
  // Only handle this app's own files. GitHub API calls always go straight to the network.
  if (req.method !== 'GET' || url.origin !== self.location.origin) return;

  if (req.mode === 'navigate') {
    // Opening the app: try the network for up to 4 seconds, otherwise use the saved copy.
    e.respondWith((async () => {
      try {
        const res = await fromNetwork(new URL('./index.html', self.registration.scope).href, 4000);
        if (res.ok) { const c = await caches.open(CACHE); await c.put('./index.html', res.clone()); return res; }
        throw new Error('HTTP ' + res.status);
      } catch (err) {
        const cached = await caches.match('./index.html');
        return cached || fetch(req);
      }
    })());
    return;
  }

  // Icons, manifest and so on: saved copy first, refreshed in the background.
  e.respondWith((async () => {
    const cached = await caches.match(req, { ignoreSearch: true });
    const net = fetch(req).then(res => { if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); } return res; }).catch(() => null);
    return cached || (await net) || Response.error();
  })());
});
