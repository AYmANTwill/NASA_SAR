/**
 * Gate before an offline demo build (npm run build:demo):
 * - demo-data/snapshot.json exists and every response passes the contract;
 * - no case is a draft (CASE_CONTRACT.md, rule 5). A rehearsal build
 *   (npm run build:rehearsal, --allow-drafts) keeps drafts, with their DRAFT band
 *   and a REHEARSAL banner: it is for testing, never for the jury.
 */
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { draftCases, validateSnapshot, type Snapshot } from "@/demo/snapshot";

const file = join(process.cwd(), "demo-data", "snapshot.json");
if (!existsSync(file)) {
  console.error("demo-data/snapshot.json is missing: run `npm run snapshot` with the backend running.");
  process.exit(1);
}

const snapshot = JSON.parse(readFileSync(file, "utf8")) as Snapshot;
const problems = validateSnapshot(snapshot);
if (problems.length > 0) {
  for (const p of problems) console.error(`contract: ${p.path}: ${p.problem}`);
  process.exit(1);
}

const drafts = draftCases(snapshot);
const rehearsal = process.argv.includes("--allow-drafts");
if (drafts.length > 0 && !rehearsal) {
  console.error(`The demo build refuses draft cases (CASE_CONTRACT.md, rule 5): ${drafts.join(", ")}.`);
  console.error("Make them final in the backend, then run `npm run snapshot` again. For a test run, use `npm run build:rehearsal`.");
  process.exit(1);
}

console.log(`snapshot of ${snapshot.generated_at}: ${Object.keys(snapshot.responses).length} responses pass the contract` + (drafts.length ? ` (rehearsal: drafts kept: ${drafts.join(", ")})` : ", no draft"));
