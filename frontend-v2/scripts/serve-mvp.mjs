// Standalone, local-only static server. Copy beside the compiled index.html; no npm install required.
import { createServer } from "node:http";
import { createReadStream, realpathSync, statSync, existsSync } from "node:fs";
import { dirname, extname, resolve, sep, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = realpathSync(process.argv[2] ?? dirname(fileURLToPath(import.meta.url)));
const port = Number(process.env.PORT ?? 4312);
const types = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif", ".svg": "image/svg+xml", ".woff": "font/woff", ".woff2": "font/woff2", ".webmanifest": "application/manifest+json" };
createServer((request, response) => {
  if (!["GET", "HEAD"].includes(request.method ?? "")) { response.writeHead(405).end(); return; }
  let pathname;
  try { pathname = decodeURIComponent(new URL(request.url, "http://localhost").pathname); }
  catch { response.writeHead(400).end(); return; }
  let file = resolve(root, "." + pathname);
  if (file !== root && !file.startsWith(root + sep)) { response.writeHead(403).end(); return; }
  if (!existsSync(file) || !statSync(file).isFile()) {
    if (pathname.startsWith("/api/") || extname(pathname)) { response.writeHead(404).end(); return; }
    file = join(root, "index.html");
  }
  if (!realpathSync(file).startsWith(root + sep)) { response.writeHead(403).end(); return; }
  response.writeHead(200, { "Content-Type": types[extname(file)] ?? "application/octet-stream", "Content-Length": statSync(file).size, "Cache-Control": "no-cache" });
  if (request.method === "HEAD") response.end();
  else createReadStream(file).on("error", () => response.destroy()).pipe(response);
}).listen(port, "127.0.0.1", () => { console.log(`MVP: http://127.0.0.1:${port}/fr/ — Ctrl+C to stop`); });
