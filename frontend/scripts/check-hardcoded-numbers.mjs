// Fails if UI code or UI strings contain a hard-coded number shown to users.
// Every displayed number must come from the API. Allowed: proper names that
// contain digits (Sentinel-1, A2…), {{placeholders}}, and fixtures/tests.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(fileURLToPath(import.meta.url), "..", "..");
const ALLOWED_NAMES = /\b(Sentinel-[12]|SME2|A2|L3|ALOS-2|v\d+)\b/g;
const problems = [];

function walk(dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) {
      if (["__fixtures__", "ui", "node_modules"].includes(name)) continue;
      walk(path);
    } else if (/\.tsx$/.test(name) && !/\.test\./.test(name)) checkTsx(path);
  }
}

function checkTsx(path) {
  const src = readFileSync(path, "utf8");
  const lines = src.split("\n");
  lines.forEach((line, i) => {
    // JSX text between tags: >  text with 3 digits  <
    for (const m of line.matchAll(/>([^<>{}]*)</g)) {
      if (/[&|=?:()]/.test(m[1])) continue; // code, not text
      const text = m[1].replace(ALLOWED_NAMES, "");
      if (/\d/.test(text)) problems.push(`${relative(root, path)}:${i + 1} JSX text "${m[1].trim()}"`);
    }
    // User-facing string attributes
    for (const m of line.matchAll(/\b(aria-label|title|placeholder|alt)="([^"]*)"/g)) {
      if (/\d/.test(m[2].replace(ALLOWED_NAMES, ""))) problems.push(`${relative(root, path)}:${i + 1} ${m[1]}="${m[2]}"`);
    }
  });
}

function checkLocale(file) {
  const json = JSON.parse(readFileSync(join(root, "src/i18n/locales", file), "utf8"));
  const visit = (obj, path) => {
    for (const [k, v] of Object.entries(obj)) {
      const p = path ? `${path}.${k}` : k;
      if (typeof v === "object") visit(v, p);
      else {
        const stripped = String(v).replace(/\{\{[^}]+\}\}/g, "").replace(ALLOWED_NAMES, "").replace(/\bNISAR\b/g, "");
        if (/\d/.test(stripped)) problems.push(`locales/${file} ${p}: "${v}"`);
      }
    }
  };
  visit(json, "");
}

walk(join(root, "src"));
for (const f of ["fr.json", "ar.json", "en.json"]) checkLocale(f);

if (problems.length) {
  console.error(`Hard-coded numbers found (${problems.length}):\n` + problems.join("\n"));
  process.exit(1);
}
console.log("No hard-coded user-facing numbers in src/ (fixtures and shadcn primitives excluded).");
