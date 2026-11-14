// Records live backend responses as test fixtures (src/test/recorded/).
// Fixtures are never typed by hand: re-run this against the backend when it changes.
//   node scripts/record-fixtures.mjs            (backend on http://127.0.0.1:8000)
//   API=http://host:port/api node scripts/record-fixtures.mjs
import { mkdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const API = (process.env.API ?? "http://127.0.0.1:8000/api").replace(/\/$/, "");
const OUT = fileURLToPath(new URL("../src/test/recorded/", import.meta.url));
mkdirSync(OUT, { recursive: true });

async function record(name, path, init) {
  const response = await fetch(API + path, init);
  const text = await response.text();
  const body = response.headers.get("content-type")?.includes("json") ? JSON.parse(text) : text;
  writeFileSync(OUT + name, JSON.stringify({ path, status: response.status, body }, null, 1) + "\n");
  console.log(`${response.status}  ${path}  -> ${name}`);
  return body;
}

await record("health.json", "/health");
const cases = await record("cases.json", "/cases");
for (const c of cases) await record(`case-${c.id}.json`, `/cases/${c.id}`);
await record("case-404.json", "/cases/no-such-case");
const library = await record("library.json", "/library");
for (const event of library) if (event.answer_id) await record(`answer-${event.answer_id}.json`, `/answers/${event.answer_id}`);
await record("demo.json", "/demo");
await record("discoveries.json", "/discoveries?region=morocco");
await record("lband-proof.json", "/proofs/lband-vs-cband");

// /ask is a server-sent event stream: kept raw, exactly as the backend wrote it.
const ask = await fetch(API + "/ask", {
  method: "POST",
  headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
  body: JSON.stringify({ question: "Did the ground change at Asni during the flash flood of 10 October 2026?", lang: "en", location: null }),
});
writeFileSync(OUT + "ask-asni-en.sse", await ask.text());
console.log(`${ask.status}  POST /ask  -> ask-asni-en.sse`);
