/**
 * Records the live backend for the offline demo (run with the backend up):
 *   npm run snapshot                       (backend on http://127.0.0.1:8000)
 *   API=http://host:port/api npm run snapshot
 *
 * Writes demo-data/snapshot.json (every response the demo path needs, as sent)
 * and demo-data/public/api/... (the figure and map-layer images). Every
 * response is checked against the contract; on any problem the previous
 * snapshot is kept untouched. Nothing is edited: what the backend sent is
 * what the demo replays.
 */
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { draftCases, validateSnapshot, type Snapshot } from "@/demo/snapshot";

const API = (process.env.API ?? "http://127.0.0.1:8000/api").replace(/\/$/, "");
const ORIGIN = new URL(API).origin;
const TMP = join(process.cwd(), "demo-data.tmp");

const snapshot: Snapshot = { generated_at: new Date().toISOString(), source: API, responses: {}, files: [] };

function fail(message: string): never {
  rmSync(TMP, { recursive: true, force: true });
  console.error(`\n${message}\nThe previous snapshot (if any) is kept unchanged.`);
  process.exit(1);
}

async function record(path: string, optional = false): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(API + path);
  } catch {
    fail(`${path}: the backend does not answer at ${API}.`);
  }
  const body: unknown = await response.json().catch(() => null);
  if (optional && response.status === 404) {
    console.log(`404  ${path} (optional, omitted)`);
    return null;
  }
  snapshot.responses[path] = { status: response.status, body };
  console.log(`${response.status}  ${path}`);
  return response.ok ? body : null;
}

const list = <T>(value: unknown): T[] => (Array.isArray(value) ? (value as T[]) : []);

/** Copies an image the API refers to (an /api/... URL) next to the demo build. */
async function copyFile(url: string): Promise<void> {
  if (!url.startsWith("/api/")) {
    console.warn(`skipped ${url}: not an /api/ URL`);
    return;
  }
  if (snapshot.files.includes(url)) return;
  const response = await fetch(ORIGIN + url).catch(() => null);
  if (!response?.ok) fail(`${url}: ${response ? response.status : "no answer"}: an image the demo shows could not be copied.`);
  const target = join(TMP, "public", url.split("?")[0]!);
  mkdirSync(dirname(target), { recursive: true });
  writeFileSync(target, Buffer.from(await response.arrayBuffer()));
  snapshot.files.push(url);
  console.log(`file ${url}`);
}

rmSync(TMP, { recursive: true, force: true });
mkdirSync(TMP, { recursive: true });

await record("/health");
const answerIds = new Set<string>();
const summaries = list<{ id: string; status: string; thumbnail_url: string | null }>(await record("/cases"));
const finalOnly = process.argv.includes("--final-only");
const cases = finalOnly ? summaries.filter((summary) => summary.status === "final") : summaries;
if (finalOnly) {
  if (!cases.length) fail("No final case is available for the jury demo.");
  snapshot.responses["/cases"] = { ...snapshot.responses["/cases"]!, body: cases };
  console.log(`final cases only; omitted drafts: ${summaries.filter((summary) => summary.status !== "final").map((summary) => summary.id).join(", ")}`);
}
for (const summary of cases) {
  const study = (await record(`/cases/${summary.id}`)) as { figures?: { url: string; layer?: { url: string } }[]; answer_ids?: string[] } | null;
  if (summary.thumbnail_url) await copyFile(summary.thumbnail_url);
  for (const figure of study?.figures ?? []) {
    await copyFile(figure.url);
    if (figure.layer) await copyFile(figure.layer.url);
  }
  for (const id of study?.answer_ids ?? []) answerIds.add(id);
}

if (cases.some((c) => c.id === "bin-el-ouidane-2026")) {
  const water = await record("/water/raster-index", true) as { layers?: { url: string }[] } | null;
  for (const image of water?.layers ?? []) await copyFile(image.url);
}

for (const e of list<{ answer_id: string | null }>(await record("/library"))) if (e.answer_id) answerIds.add(e.answer_id);
const demo = (await record("/demo")) as { entries?: { answer_id: string }[] } | null;
for (const e of demo?.entries ?? []) answerIds.add(e.answer_id);
for (const w of list<{ answer_id: string | null }>(await record("/watches"))) if (w.answer_id) answerIds.add(w.answer_id);
for (const n of list<{ answer_id: string | null }>(await record("/notifications"))) if (n.answer_id) answerIds.add(n.answer_id);

// Every answer the recorded pages link to: cases, library, demonstration questions, watches and alerts.
for (const id of answerIds) {
  const answer = (await record(`/answers/${encodeURIComponent(id)}`)) as { layers?: { url: string }[] } | null;
  for (const layer of answer?.layers ?? []) await copyFile(layer.url);
}

await record("/discoveries?region=MA");
await record("/proofs/lband-vs-cband");

const problems = validateSnapshot(snapshot);
if (problems.length > 0) {
  for (const p of problems) console.error(`contract: ${p.path}: ${p.problem}`);
  fail(`${problems.length} problem(s): the snapshot is not written.`);
}

writeFileSync(join(TMP, "snapshot.json"), JSON.stringify(snapshot, null, 1) + "\n");
// install-snapshot.mjs runs after Vite releases its Windows directory watchers.

const drafts = draftCases(snapshot);
console.log(`\nsnapshot validated: ${Object.keys(snapshot.responses).length} responses, ${snapshot.files.length} files`);
if (drafts.length > 0) console.warn(`draft cases (a demo build will refuse them): ${drafts.join(", ")}`);
