// Run outside vite-node: its Windows watcher can keep demo-data.tmp open until the process exits.
import { existsSync, readFileSync, rmSync, lstatSync, cpSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const temporary = join(root, "demo-data.tmp"), output = join(root, "demo-data"), previous = join(root, "demo-data.previous");
for (const path of [temporary, output, previous]) {
  if (dirname(resolve(path)) !== root || (existsSync(path) && lstatSync(path).isSymbolicLink())) throw new Error("Snapshot path outside the package");
}
const snapshot = JSON.parse(readFileSync(join(temporary, "snapshot.json"), "utf8"));
if (!snapshot.responses?.["/cases"]) throw new Error("No validated case snapshot to install");
if (existsSync(previous)) rmSync(previous, { recursive: true, force: true });
if (existsSync(output)) cpSync(output, previous, { recursive: true });
try {
  mkdirSync(output, { recursive: true });
  cpSync(join(temporary, "public"), join(output, "public"), { recursive: true, force: true });
  // Publish the validated manifest last; directory renames fail under Windows file watchers.
  writeFileSync(join(output, "snapshot.json"), readFileSync(join(temporary, "snapshot.json")));
} catch (error) {
  if (existsSync(previous)) cpSync(previous, output, { recursive: true, force: true });
  throw error;
}
console.log(`Snapshot installed: ${Object.keys(snapshot.responses).length} responses, ${snapshot.files.length} images. Previous snapshot retained when present.`);
