import { useEffect, useState } from "react";

/**
 * Motion language of NISAR Pulse.
 * Every movement shows a real physical step (a satellite pass, a radar pulse,
 * a measurement settling against the noise). Nothing animates through
 * invented values. `prefers-reduced-motion` turns every sequence into its end state.
 */

const QUERY = "(prefers-reduced-motion: reduce)";

export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia(QUERY).matches;
}

export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(prefersReducedMotion);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia(QUERY);
    const on = () => setReduced(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return reduced;
}

export const easeInOutCubic = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);
export const easeOutCubic = (t: number) => 1 - (1 - t) ** 3;
export const clamp01 = (t: number) => Math.max(0, Math.min(1, t));

/**
 * Runs `frame(progress)` for `duration` ms on requestAnimationFrame.
 * Returns a cancel function. With reduced motion, jumps straight to the end.
 */
export function animate(duration: number, frame: (t: number) => void, done?: () => void): () => void {
  if (prefersReducedMotion() || duration <= 0) {
    frame(1);
    done?.();
    return () => undefined;
  }
  let raf = 0;
  const start = performance.now();
  const tick = (now: number) => {
    const t = clamp01((now - start) / duration);
    frame(t);
    if (t < 1) raf = requestAnimationFrame(tick);
    else done?.();
  };
  raf = requestAnimationFrame(tick);
  return () => cancelAnimationFrame(raf);
}

/**
 * NISAR flies a sun-synchronous, near-polar orbit (inclination about 98°):
 * over Morocco an ascending pass heads slightly west of north, a descending
 * pass slightly west of south. Headings in degrees clockwise from north.
 * Used only to orient the drawing of a pass, never as a measurement.
 */
export const PASS_HEADING = { ascending: -12, descending: 192 } as const;
export type PassDirection = keyof typeof PASS_HEADING;

/** Timing of the staged answer (ms). The whole sequence stays under four seconds. */
export const STAGE = {
  /** Minimum gap between two step updates while the agent works. */
  stepGap: 170,
  /** Raster revealed by the swath. */
  reveal: 1400,
  /** Ruler marker settling on the measured value. */
  ruler: 900,
  /** Time series drawn pass after pass. */
  chart: 1500,
  /** Home-page orbit pass. */
  intro: 3600,
} as const;
