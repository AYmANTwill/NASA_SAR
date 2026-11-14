import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * frontend-v2 keeps a copy of the team's contract (frontend/src/api/contract.ts).
 * The copy must not drift: run `npm run sync:contract` when this test fails.
 * Only line endings are normalised (git may check files out with CRLF on Windows).
 */
const read = (relative: string) =>
  readFileSync(fileURLToPath(new URL(relative, import.meta.url)), "utf8").replace(/\r\n/g, "\n");

describe("API contract copy", () => {
  it("is identical to frontend/src/api/contract.ts", () => {
    const source = read("../../../frontend/src/api/contract.ts");
    const copy = read("./contract.ts");
    if (copy !== source) {
      const a = source.split("\n");
      const b = copy.split("\n");
      const line = a.findIndex((text, i) => text !== b[i]);
      throw new Error(
        `contract.ts differs from frontend/src/api/contract.ts from line ${line + 1}:\n` +
          `  frontend:    ${a[line] ?? "<end of file>"}\n  frontend-v2: ${b[line] ?? "<end of file>"}\n` +
          "Run `npm run sync:contract`.",
      );
    }
    expect(copy).toBe(source);
  });
});
