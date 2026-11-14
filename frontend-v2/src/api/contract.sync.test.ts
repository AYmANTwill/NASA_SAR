import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * frontend-v2 keeps copies of the team's sources of truth. They must not drift:
 * run `npm run sync:contract` when this test fails.
 * Only line endings are normalised (git may check files out with CRLF on Windows).
 * Vitest runs from frontend-v2/.
 */
const read = (path: string) => readFileSync(join(process.cwd(), path), "utf8").replace(/\r\n/g, "\n");

function expectIdentical(sourcePath: string, copyPath: string) {
  const source = read(sourcePath);
  const copy = read(copyPath);
  if (copy !== source) {
    const a = source.split("\n");
    const b = copy.split("\n");
    const line = a.findIndex((text, i) => text !== b[i]);
    throw new Error(
      `${copyPath} differs from ${sourcePath} from line ${line + 1}:\n` +
        `  source: ${a[line] ?? "<end of file>"}\n  copy:   ${b[line] ?? "<end of file>"}\n` +
        "Run `npm run sync:contract`.",
    );
  }
  expect(copy).toBe(source);
}

describe("shared sources of truth", () => {
  it("API contract is identical to frontend/src/api/contract.ts", () => {
    expectIdentical("../frontend/src/api/contract.ts", "src/api/contract.ts");
  });

  it("map palettes are identical to backend/palettes.json", () => {
    expectIdentical("../backend/palettes.json", "src/design/palettes.json");
  });
});
