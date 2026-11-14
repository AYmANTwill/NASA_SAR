// Copies the team's API contract (frontend/src/api/contract.ts) into frontend-v2.
// The copy must stay identical: src/api/contract.sync.test.ts fails when it is not.
import { copyFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const source = fileURLToPath(new URL("../../frontend/src/api/contract.ts", import.meta.url));
const target = fileURLToPath(new URL("../src/api/contract.ts", import.meta.url));

copyFileSync(source, target);
console.log(`copied ${source}\n    -> ${target}`);
