import type { Measurement } from "@/api/contract";

/**
 * Geometry of the comparison strip: where the NISAR and reference marks and
 * their uncertainty bars sit on a shared number line. Pixel positions only:
 * the strip has no tick labels, so no number computed here is ever displayed.
 * Bars are ±1σ (solid) and ±2σ (light), from each measurement's own
 * uncertainty / sigma, as the API sent them.
 */
export interface StripMark {
  x: number;
  sigma1: [number, number];
  sigma2: [number, number];
}

export interface StripGeometry {
  nisar: StripMark;
  reference: StripMark;
}

export function stripGeometry(nisar: Measurement, reference: Measurement, width: number, pad = 12): StripGeometry {
  const s1 = (m: Measurement) => m.uncertainty / m.sigma;
  const lo = Math.min(nisar.value - 2 * s1(nisar), reference.value - 2 * s1(reference));
  const hi = Math.max(nisar.value + 2 * s1(nisar), reference.value + 2 * s1(reference));
  const span = hi - lo || Math.abs(hi) || 1;
  const x = (v: number) => pad + ((v - lo) / span) * (width - 2 * pad);
  const mark = (m: Measurement): StripMark => ({
    x: x(m.value),
    sigma1: [x(m.value - s1(m)), x(m.value + s1(m))],
    sigma2: [x(m.value - 2 * s1(m)), x(m.value + 2 * s1(m))],
  });
  return { nisar: mark(nisar), reference: mark(reference) };
}
