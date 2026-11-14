import { describe, expect, it } from "vitest";
import { formatDate, formatNumber } from "./format";

describe("formatNumber", () => {
  it("uses each language's decimal separator and Western digits in Arabic", () => {
    expect(formatNumber(7.7, "fr")).toBe("7,7");
    expect(formatNumber(7.7, "en")).toBe("7.7");
    expect(formatNumber(7.7, "ar")).toMatch(/^7[.,٫]7$/);
    expect(formatNumber(7.7, "ar")).not.toMatch(/[٠-٩]/);
  });

  it("does not round away the API's digits", () => {
    expect(formatNumber(0.0123, "en")).toBe("0.0123");
    expect(formatNumber(12345.5, "en")).toBe("12,345.5");
  });
});

describe("formatDate", () => {
  it("prints the UTC time of an exact event", () => {
    expect(formatDate("2026-10-09T17:56:06Z", "en")).toBe("9 Oct 2026, 17:56 UTC");
  });

  it("does not invent a time for a day-precision event", () => {
    expect(formatDate("2026-10-10T00:00:00Z", "en")).toBe("10 Oct 2026");
    expect(formatDate("2026-10-10", "fr")).toMatch(/^10 oct\.? 2026$/);
  });

  it("returns an unparseable value unchanged rather than guessing", () => {
    expect(formatDate("not a date", "fr")).toBe("not a date");
  });
});
