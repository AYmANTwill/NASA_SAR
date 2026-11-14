// Gate of the release demo build: the offline demo must replay exported, final cases only.
// Fails when no export exists or when any exported case is still a draft.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const file = join(dirname(fileURLToPath(import.meta.url)), "..", "src", "__fixtures__", "cases-export.ts");
const src = readFileSync(file, "utf8");
const json = src.slice(src.indexOf("=") + 1, src.indexOf(";\nexport default")).trim();
const data = json === "null" ? null : JSON.parse(json);

if (!data) {
  console.error("No exported cases: run `node scripts/export-cases.mjs` with the API running.");
  process.exit(1);
}
const drafts = data.studies.filter((c) => c.status !== "final").map((c) => c.id);
if (drafts.length) {
  console.error(`Demo build refused: draft cases ${drafts.join(", ")}.`);
  process.exit(1);
}
console.log(`${data.studies.length} final cases: the demo can ship.`);
