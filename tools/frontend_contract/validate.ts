import { readFileSync, readdirSync } from "fs";
import * as C from "./contract";
import * as K from "./case_contract";
import { z } from "zod";
const schemas: Record<string, z.ZodTypeAny> = {
  step: C.AgentStep, answer: C.Answer, error: C.ApiErrorBody, discoveries: C.Discoveries,
  watch: C.Watch, watches: z.array(C.Watch), notifications: z.array(C.WatchNotification),
  library: z.array(C.LibraryEvent), demo: C.DemoBundle, health: C.Health,
  // what the interface accepts (frontend/src/api/contract.ts)
  cases: z.array(C.CaseSummary), case: C.CaseStudy,
};
// The case rules of docs/CASE_CONTRACT.md (computed agreement, units, ISO UTC dates), checked on top.
const strict: Record<string, z.ZodTypeAny> = { cases: z.array(K.CaseSummary), case: K.CaseStudy };
// NISAR_DEMO=1: the demo build refuses any case still in "draft".
const demo = process.env.NISAR_DEMO === "1";
const issues = (e: z.ZodError) => JSON.stringify(e.issues.slice(0, 6), null, 0).slice(0, 1500);
let bad = 0, n = 0;
for (const f of readdirSync(process.argv[2])) {
  const kind = f.split("__")[0];
  const s = schemas[kind]; if (!s) continue;
  const data = JSON.parse(readFileSync(process.argv[2] + "/" + f, "utf8"));
  const r = s.safeParse(data); n++;
  if (!r.success) { bad++; console.log("FAIL", f, "(frontend contract)", issues(r.error)); continue; }
  const k = strict[kind]?.safeParse(data);
  if (k && !k.success) { bad++; console.log("FAIL", f, "(CASE_CONTRACT.md rules)", issues(k.error)); continue; }
  if (demo && (kind === "case" || kind === "cases")) {
    const drafts = (Array.isArray(data) ? data : [data]).filter((c: { status: string }) => c.status === "draft");
    if (drafts.length) { bad++; console.log("FAIL", f, "NISAR_DEMO=1 refuses draft cases:", drafts.map((c: { id: string }) => c.id).join(", ")); }
  }
}
console.log(`${n - bad}/${n} responses match the frontend contract${demo ? " (demo mode: no draft case allowed)" : ""}`);
process.exit(bad ? 1 : 0);
