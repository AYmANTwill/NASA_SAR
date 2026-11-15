import { readdirSync, existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { createHash } from "node:crypto";
import type { Plugin, ResolvedConfig } from "vite";

/** The app shell is cached only in production; API writes are never intercepted or queued. */
export function offlinePlugin(): Plugin {
  let config: ResolvedConfig;
  return { name: "nisar-offline-shell", apply: "build", configResolved(value) { config = value; }, generateBundle(_options, bundle) {
    const files = Object.keys(bundle);
    function publicFiles(folder: string, prefix = "") {
      if (!existsSync(folder)) return;
      for (const entry of readdirSync(folder, { withFileTypes: true })) {
        const relative = prefix + entry.name;
        if (entry.isDirectory()) publicFiles(join(folder, entry.name), relative + "/"); else files.push(relative);
      }
    }
    if (config.publicDir) publicFiles(config.publicDir);
    // Demo/rehearsal use a separate public directory but keep the same installable shell.
    for (const name of ["manifest.webmanifest", "icon.svg"]) {
      if (!files.includes(name)) {
        this.emitFile({ type: "asset", fileName: name, source: readFileSync(join(config.root, "public", name)) });
        files.push(name);
      }
    }
    const revision = createHash("sha256").update("validated-images-v1|" + files.join("|")).digest("hex").slice(0, 12);
    const urls = [...new Set(["index.html", ...files])].map((name) => config.base + name);
    const source = `
const CACHE = 'nisar-v2-shell-${revision}';
const PRECACHE = ${JSON.stringify(urls)};
self.addEventListener('install', event => { event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(PRECACHE)).then(() => self.skipWaiting())); });
self.addEventListener('activate', event => { event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('nisar-v2-shell-') && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim())); });
self.addEventListener('fetch', event => {
  const request = event.request, url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(fetch(request).then(response => {
      // JSON lives only in the contract-validated client cache. The worker stores images.
      if (response.ok && (response.headers.get('Content-Type') || '').startsWith('image/')) {
        const copy = response.clone(), headers = new Headers(copy.headers); headers.set('X-Nisar-Saved-At', String(Date.now()));
        event.waitUntil(caches.open(CACHE).then(cache => cache.put(request, new Response(copy.body, {status:copy.status, headers}))));
      }
      return response;
    }).catch(async () => {
      const saved = await caches.match(request, {ignoreVary:true});
      const bundled = PRECACHE.includes(url.pathname);
      if (!saved || (!bundled && Date.now() - Number(saved.headers.get('X-Nisar-Saved-At') || 0) > 7*24*60*60*1000)) return new Response('', {status:503, headers:{'X-Nisar-Offline':'1'}});
      const headers = new Headers(saved.headers); headers.set('X-Nisar-Cached','1');
      return new Response(saved.body, {status:saved.status, headers});
    }));
    return;
  }
  if (request.mode === 'navigate') {
    event.respondWith(fetch(request).catch(() => caches.match('${config.base}index.html', {ignoreVary:true}))); return;
  }
  // Same-origin immutable shell files are identical for module and preload requests (Vary: Origin).
  event.respondWith(caches.match(request, {ignoreVary:true}).then(saved => saved || fetch(request)));
});`;
    this.emitFile({ type: "asset", fileName: "sw.js", source });
  } };
}
