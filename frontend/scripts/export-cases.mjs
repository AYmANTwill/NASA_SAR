// Exports the case studies from the running API for the offline demo build.
//   node scripts/export-cases.mjs [--api http://127.0.0.1:8000/api]
// Writes src/__fixtures__/cases-export.ts (responses verbatim, only /api URLs rewritten)
// and downloads every figure and layer image into public/__fixtures__/cases/.
// Values are never edited: the demo replays exactly what the API served.
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const argApi = process.argv.indexOf("--api");
const api = (argApi > 0 ? process.argv[argApi + 1] : process.env.NISAR_API ?? "http://127.0.0.1:8000/api").replace(/\/$/, "");
const origin = new URL(api).origin;

async function getJson(path) {
  const res = await fetch(api + path);
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return res.json();
}

/** Downloads an /api/... asset and returns its offline URL. */
async function localize(url) {
  if (!url || !url.startsWith("/api/")) return url;
  const rel = url.slice("/api/".length).split("?")[0];
  const res = await fetch(origin + url);
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  const file = join(root, "public", "__fixtures__", "cases", rel);
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, Buffer.from(await res.arrayBuffer()));
  return `/__fixtures__/cases/${rel}`;
}

const summaries = await getJson("/cases");
const studies = [];
for (const s of summaries) {
  const c = await getJson(`/cases/${encodeURIComponent(s.id)}`);
  for (const f of c.figures ?? []) {
    f.url = await localize(f.url);
    if (f.layer) f.layer.url = await localize(f.layer.url);
  }
  studies.push(c);
}
for (const s of summaries) s.thumbnail_url = await localize(s.thumbnail_url);

const drafts = studies.filter((c) => c.status !== "final").map((c) => c.id);
const out = join(root, "src", "__fixtures__", "cases-export.ts");
writeFileSync(
  out,
  `// Exported from ${api} on ${new Date().toISOString()} by scripts/export-cases.mjs. Do not edit by hand.\n` +
    `const data: { summaries: unknown[]; studies: unknown[] } | null = ${JSON.stringify({ summaries, studies }, null, 1)};\n` +
    `export default data;\n`,
);
console.log(`${studies.length} cases exported to ${out}`);
if (drafts.length) console.log(`Still draft (the release demo build will refuse them): ${drafts.join(", ")}`);
