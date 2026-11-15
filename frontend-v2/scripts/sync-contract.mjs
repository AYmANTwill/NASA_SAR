// Copies the team's shared sources of truth into frontend-v2:
//   frontend/src/api/contract.ts  -> src/api/contract.ts    (API shapes, zod)
//   backend/palettes.json         -> src/design/palettes.json (canonical map palettes)
// The copies must stay identical: src/api/contract.sync.test.ts fails when they are not.
import { copyFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const pairs = [
  ["../../frontend/src/api/contract.ts", "../src/api/contract.ts"],
  ["../../backend/palettes.json", "../src/design/palettes.json"],
];

for (const [from, to] of pairs) {
  const source = fileURLToPath(new URL(from, import.meta.url));
  const target = fileURLToPath(new URL(to, import.meta.url));
  copyFileSync(source, target);
  console.log(`copied ${source}\n    -> ${target}`);
}
