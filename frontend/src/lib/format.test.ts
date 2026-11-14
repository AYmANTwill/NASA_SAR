import { describe, expect, it } from "vitest";
import { decimalsFor, formatMeasurement, niceTicks } from "./format";

describe("decimalsFor", () => {
  it("keeps one significant figure of the uncertainty", () => {
    expect(decimalsFor(3, 46)).toBe(0);
    expect(decimalsFor(0.4, 2.6)).toBe(1);
    expect(decimalsFor(0.04, 0.36)).toBe(2);
  });
  it("keeps two significant figures when the uncertainty starts with 1", () => {
    expect(decimalsFor(1.2, 10)).toBe(1);
    expect(decimalsFor(0.15, 0.5)).toBe(2);
  });
});

describe("formatMeasurement", () => {
  it("rounds the value to the uncertainty and never drops the ±", () => {
    const f = formatMeasurement({ value: -38.27, uncertainty: 5, unit: "mm/yr", sigma: 1 }, "en", "mm/yr");
    expect(f.value).toBe("−38");
    expect(f.uncertainty).toBe("5");
    expect(f.text).toContain("±");
    expect(f.text.endsWith("mm/yr")).toBe(true);
  });
  it("uses Western digits and a comma decimal in Moroccan Arabic", () => {
    const f = formatMeasurement({ value: 2.6, uncertainty: 0.4, unit: "mm", sigma: 1 }, "ar", "مم");
    expect(f.value).toBe("2,6");
  });
  it("isolates the numeric run left-to-right, not the unit", () => {
    const f = formatMeasurement({ value: 1, uncertainty: 0.5, unit: "mm", sigma: 1 }, "ar", "مم");
    expect(f.text.startsWith("⁦")).toBe(true);
    expect(f.text.indexOf("⁩")).toBeLessThan(f.text.indexOf("مم"));
  });
});

describe("niceTicks", () => {
  it("returns round, evenly spaced ticks covering the range", () => {
    const { domain, ticks } = niceTicks(-27.3, 6.2);
    expect(domain[0]).toBeLessThanOrEqual(-27.3);
    expect(domain[1]).toBeGreaterThanOrEqual(6.2);
    const steps = new Set(ticks.slice(1).map((v, i) => +(v - ticks[i]).toFixed(6)));
    expect(steps.size).toBe(1);
  });
  it("does not print ± 0 when no uncertainty is provided", () => {
    const f = formatMeasurement({ value: 37.9, uncertainty: 0, unit: "mm", sigma: 1 }, "fr", "mm");
    expect(f.text).not.toContain("±");
    expect(f.text).toContain("37,9");
  });
});
