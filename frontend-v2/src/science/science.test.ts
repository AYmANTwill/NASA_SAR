import { describe, expect, it } from "vitest";
import type { Measurement } from "@/api/contract";
import { measurementParts, measurementState } from "./measurement";
import { stripGeometry } from "./strip";

const m = (value: number, uncertainty: number, sigma = 1): Measurement => ({ value, uncertainty, unit: "Mw", sigma });

describe("measurementState", () => {
  it("a draft's value without uncertainty is a placeholder, never a 0", () => {
    expect(measurementState(m(0, 0), "draft")).toBe("placeholder");
  });
  it("outside a draft, uncertainty 0 is an exact value", () => {
    expect(measurementState(m(1234, 0), "final")).toBe("exact");
    expect(measurementState(m(1234, 0), null)).toBe("exact");
  });
  it("a value with its uncertainty is measured, draft or not", () => {
    expect(measurementState(m(7.6, 0.1), "draft")).toBe("measured");
    expect(measurementState(m(7.6, 0.1), "final")).toBe("measured");
  });
});

describe("measurementParts", () => {
  it("prints the API's numbers in the page language", () => {
    expect(measurementParts(m(7.6, 0.1), "fr")).toEqual({ value: "7,6", uncertainty: "0,1", sigma: null });
  });
  it("names the σ multiple when it is not 1σ", () => {
    expect(measurementParts(m(7.6, 0.2, 2), "en").sigma).toBe("2");
  });
});

describe("stripGeometry", () => {
  it("keeps both marks and their 2σ bars inside the strip", () => {
    const g = stripGeometry(m(7.6, 0.1), m(7.7, 0.1), 300);
    for (const mark of [g.nisar, g.reference]) {
      expect(mark.sigma2[0]).toBeGreaterThanOrEqual(12 - 1e-9);
      expect(mark.sigma2[1]).toBeLessThanOrEqual(288 + 1e-9);
    }
    expect(g.nisar.x).toBeLessThan(g.reference.x);
  });
  it("uses each measurement's own σ (uncertainty / sigma)", () => {
    const g = stripGeometry(m(0, 2, 2), m(0, 1, 1), 300);
    expect(g.nisar.sigma1[1] - g.nisar.x).toBeCloseTo(g.reference.sigma1[1] - g.reference.x);
  });
  it("does not break when both values and uncertainties are equal", () => {
    const g = stripGeometry(m(5, 0), m(5, 0), 300);
    expect(Number.isFinite(g.nisar.x)).toBe(true);
  });
});
