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
import { existsSync, mkdirSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { draftCases, validateSnapshot, type Snapshot } from "@/demo/snapshot";

const API = (process.env.API ?? "http://127.0.0.1:8000/api").replace(/\/$/, "");
const ORIGIN = new URL(API).origin;
const OUT = join(process.cwd(), "demo-data");
const TMP = join(process.cwd(), "demo-data.tmp");

const snapshot: Snapshot = { generated_at: new Date().toISOString(), source: API, responses: {}, files: [] };

function fail(message: string): never {
  rmSync(TMP, { recursive: true, force: true });
  console.error(`\n${message}\nThe previous snapshot (if any) is kept unchanged.`);
  process.exit(1);
}

async function record(path: string): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(API + path);
  } catch {
    fail(`${path}: the backend does not answer at ${API}.`);
  }
  const body: unknown = await response.json().catch(() => null);
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
for (const summary of list<{ id: string; thumbnail_url: string | null }>(await record("/cases"))) {
  const study = (await record(`/cases/${summary.id}`)) as { figures?: { url: string; layer?: { url: string } }[]; answer_ids?: string[] } | null;
  if (summary.thumbnail_url) await copyFile(summary.thumbnail_url);
  for (const figure of study?.figures ?? []) {
    await copyFile(figure.url);
    if (figure.layer) await copyFile(figure.layer.url);
  }
  for (const id of study?.answer_ids ?? []) answerIds.add(id);
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

await record("/discoveries?region=morocco");
await record("/proofs/lband-vs-cband");

const problems = validateSnapshot(snapshot);
if (problems.length > 0) {
  for (const p of problems) console.error(`contract: ${p.path}: ${p.problem}`);
  fail(`${problems.length} problem(s): the snapshot is not written.`);
}

writeFileSync(join(TMP, "snapshot.json"), JSON.stringify(snapshot, null, 1) + "\n");
// Only now is the previous snapshot replaced.
if (existsSync(OUT)) rmSync(OUT, { recursive: true, force: true });
renameSync(TMP, OUT);

const drafts = draftCases(snapshot);
console.log(`\nsnapshot written: ${Object.keys(snapshot.responses).length} responses, ${snapshot.files.length} files`);
if (drafts.length > 0) console.warn(`draft cases (a demo build will refuse them): ${drafts.join(", ")}`);
