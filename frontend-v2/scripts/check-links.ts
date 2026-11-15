/**
 * Calls every method of the interface's API client against the live backend,
 * through the same path the browser uses, and reports what came back:
 *   npm run check:links                         (dev server on 127.0.0.1:5310, backend behind it)
 *   BASE=http://127.0.0.1:8000/api npm run check:links   (backend directly)
 *
 * Read-only except for one watch, created on a library answer and deleted at
 * the end. The alert simulation is not called (it would write a SIMULATION
 * alert into the backend's notifications).
 */
import { createHttpClient } from "@/api/client";
import { ApiError, ContractError, INFORMATION_CODES, OfflineError } from "@/api/errors";

const BASE = process.env.BASE ?? "http://127.0.0.1:5310/api";
const api = createHttpClient(BASE);
let failures = 0;

async function check(name: string, call: () => Promise<unknown>, describe: (value: unknown) => string = () => "ok") {
  try {
    const value = await call();
    console.log(`ok    ${name.padEnd(34)} ${describe(value)}`);
    return value;
  } catch (error) {
    if (error instanceof ApiError && INFORMATION_CODES.has(error.code)) {
      console.log(`info  ${name.padEnd(34)} ${error.status} ${error.code} (shown as information)`);
      return null;
    }
    failures++;
    const why = error instanceof ContractError ? `contract: ${error.message}` : error instanceof OfflineError ? "unreachable" : String(error);
    console.log(`FAIL  ${name.padEnd(34)} ${why}`);
    return null;
  }
}

const count = (v: unknown) => (Array.isArray(v) ? `${v.length} item(s)` : "ok");

await check("health()", () => api.health(), (h) => JSON.stringify(h));
const cases = (await check("cases()", () => api.cases(), count)) as { id: string }[] | null;
for (const c of cases ?? []) {
  await check(`caseStudy(${c.id})`, () => api.caseStudy(c.id), (s) => {
    const study = s as { status: string; findings: unknown[]; figures: { url: string }[]; answer_ids: string[] };
    return `${study.status}, ${study.findings.length} finding(s), ${study.figures.length} figure(s), ${study.answer_ids.length} linked answer(s)`;
  });
}
await check("caseStudy(unknown) → 404", async () => {
  try {
    await api.caseStudy("no-such-case");
    throw new Error("expected a 404");
  } catch (e) {
    if (e instanceof ApiError && e.code === "case_not_found") return e.code;
    throw e;
  }
}, String);

const library = (await check("library()", () => api.library(), count)) as { answer_id: string | null }[] | null;
const demo = (await check("demo()", () => api.demo(), (d) => `${(d as { entries: unknown[] }).entries.length} demo question set(s)`)) as {
  entries: { answer_id: string; questions: { text: string; lang: "fr" | "en" | "ar" }[] }[];
} | null;
for (const id of new Set([...(library ?? []).flatMap((e) => (e.answer_id ? [e.answer_id] : [])), ...(demo?.entries ?? []).map((e) => e.answer_id)])) {
  await check(`answer(${id})`, () => api.answer(id), (a) => `${(a as { layers: unknown[] }).layers.length} layer(s), ${(a as { metrics: unknown[] }).metrics.length} metric(s)`);
}

for (const lang of ["fr", "en", "ar"] as const) {
  const q = demo?.entries[0]?.questions.find((x) => x.lang === lang);
  if (!q) continue;
  let steps = 0;
  await check(`ask(demo question, ${lang})`, () => api.ask({ question: q.text, lang, location: null }, () => steps++), (a) => `${steps} step(s) streamed, answer ${(a as { id: string }).id}`);
}
await check("ask(question with a picked point)", () => api.ask({ question: "Le terrain bouge-t-il ici ?", lang: "fr", location: { lat: 34.598, lon: -5.198 } }, () => {}), (a) => `answer ${(a as { id: string }).id}`);

await check("discoveries(MA)", () => api.discoveries("MA"));
await check("lbandProof()", () => api.lbandProof());
await check("watches()", () => api.watches(), count);
await check("notifications()", () => api.notifications(), count);

const target = library?.find((e) => e.answer_id)?.answer_id;
if (target) {
  const before = ((await api.watches()) as { id: string; answer_id: string | null }[]).find((w) => w.answer_id === target);
  const watch = (await check(`createWatch(${target})`, () => api.createWatch(target), (w) => `watch ${(w as { id: string }).id}, next pass ${(w as { next_pass: string }).next_pass}`)) as { id: string } | null;
  if (watch && !before) await check(`deleteWatch(${watch.id})`, () => api.deleteWatch(watch.id));
}
await check("checkWatches()", () => api.checkWatches());

console.log(failures === 0 ? "\nevery link works" : `\n${failures} link(s) failing`);
process.exit(failures === 0 ? 0 : 1);
