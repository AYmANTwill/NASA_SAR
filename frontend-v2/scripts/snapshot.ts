/**
 * Records the live backend for the offline demo (run with the backend up):
 *   npm run snapshot                       (backend on http://127.0.0.1:8000)
 *   API=http://host:port/api npm run snapshot
 *
 * Writes demo-data/snapshot.json (every response the demo path needs, as sent)
 * and demo-data/public/api/... (the figure and map-layer images). Every
 * response is checked against the contract; a mismatch stops the snapshot.
 * Nothing is edited: what the backend sent is what the demo replays.
 */
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import type { CaseStudy, CaseSummary, DemoBundle, LibraryEvent } from "@/api/contract";
import { draftCases, validateSnapshot, type Snapshot } from "@/demo/snapshot";

const API = (process.env.API ?? "http://127.0.0.1:8000/api").replace(/\/$/, "");
const ORIGIN = new URL(API).origin;
const OUT = join(process.cwd(), "demo-data");

const snapshot: Snapshot = { generated_at: new Date().toISOString(), source: API, responses: {}, files: [] };

async function record<T>(path: string): Promise<T> {
  const response = await fetch(API + path);
  const body: unknown = await response.json().catch(() => null);
  snapshot.responses[path] = { status: response.status, body };
  console.log(`${response.status}  ${path}`);
  return body as T;
}

/** Copies an image the API refers to (an /api/... URL) next to the demo build. */
async function copyFile(url: string): Promise<void> {
  if (!url.startsWith("/api/")) {
    console.warn(`skipped ${url}: not an /api/ URL`);
    return;
  }
  if (snapshot.files.includes(url)) return;
  const response = await fetch(ORIGIN + url);
  if (!response.ok) throw new Error(`${url}: ${response.status}`);
  const target = join(OUT, "public", url.split("?")[0]!);
  mkdirSync(dirname(target), { recursive: true });
  writeFileSync(target, Buffer.from(await response.arrayBuffer()));
  snapshot.files.push(url);
  console.log(`file ${url}`);
}

rmSync(OUT, { recursive: true, force: true });
mkdirSync(OUT, { recursive: true });

await record("/health");
const cases = await record<CaseSummary[]>("/cases");
for (const summary of cases) {
  const study = await record<CaseStudy>(`/cases/${summary.id}`);
  if (summary.thumbnail_url) await copyFile(summary.thumbnail_url);
  for (const figure of study.figures ?? []) {
    await copyFile(figure.url);
    if (figure.layer) await copyFile(figure.layer.url);
  }
}

const library = await record<LibraryEvent[]>("/library");
const demo = await record<DemoBundle>("/demo");
const answerIds = new Set([...library.flatMap((e) => (e.answer_id ? [e.answer_id] : [])), ...demo.entries.map((e) => e.answer_id)]);
for (const id of answerIds) {
  const answer = await record<{ layers?: { url: string }[] }>(`/answers/${encodeURIComponent(id)}`);
  for (const layer of answer.layers ?? []) await copyFile(layer.url);
}

await record("/discoveries?region=morocco");
await record("/proofs/lband-vs-cband");
await record("/watches");
await record("/notifications");

const problems = validateSnapshot(snapshot);
if (problems.length > 0) {
  for (const p of problems) console.error(`contract: ${p.path}: ${p.problem}`);
  console.error(`\n${problems.length} contract problem(s): the snapshot is not written.`);
  process.exit(1);
}

writeFileSync(join(OUT, "snapshot.json"), JSON.stringify(snapshot, null, 1) + "\n");
const drafts = draftCases(snapshot);
console.log(`\nsnapshot written: ${Object.keys(snapshot.responses).length} responses, ${snapshot.files.length} files`);
if (drafts.length > 0) console.warn(`draft cases (a demo build will refuse them): ${drafts.join(", ")}`);
