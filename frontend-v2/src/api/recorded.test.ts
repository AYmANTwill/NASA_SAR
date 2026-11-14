import { describe, expect, it } from "vitest";
import { z } from "zod";
import { recorded, recordedNames } from "@/test/recorded";
import { Answer, ApiErrorBody, CaseStudy, CaseSummary, DemoBundle, Health, LibraryEvent } from "./contract";

/**
 * The real backend's responses (recorded by scripts/record-fixtures.mjs) must
 * pass the contract as they are. If one fails here, the interface would show
 * an error panel for it: report it in API_REQUESTS.md, never patch the data.
 */
describe("recorded backend responses pass the contract", () => {
  it("health", () => expect(Health.safeParse(recorded("health.json").body).success).toBe(true));
  it("case list", () => expect(z.array(CaseSummary).safeParse(recorded("cases.json").body).success).toBe(true));
  it("library", () => expect(z.array(LibraryEvent).safeParse(recorded("library.json").body).success).toBe(true));
  it("demo bundle", () => expect(DemoBundle.safeParse(recorded("demo.json").body).success).toBe(true));

  it.each(recordedNames("case-").filter((n) => n !== "case-404.json"))("%s", (name) => {
    const result = CaseStudy.safeParse(recorded(name).body);
    expect(result.success, result.success ? "" : JSON.stringify(result.error.issues)).toBe(true);
  });

  it.each(recordedNames("answer-"))("%s", (name) => {
    const result = Answer.safeParse(recorded(name).body);
    expect(result.success, result.success ? "" : JSON.stringify(result.error.issues)).toBe(true);
  });

  it.each(["case-404.json", "discoveries.json", "lband-proof.json"])("error body %s", (name) => {
    const r = recorded(name);
    expect(r.status).toBeGreaterThanOrEqual(400);
    expect(ApiErrorBody.safeParse(r.body).success).toBe(true);
  });
});
