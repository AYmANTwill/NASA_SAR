/**
 * Helpers for SYNTHETIC fixtures. Fixtures only exercise the UI until the
 * FastAPI backend exists. No value here is a NISAR measurement; the app shows
 * a permanent "test data" banner whenever fixtures are served.
 */
import type { AgentStep, Measurement, SeriesPoint, TemplatedText, TemplateParam, Unit } from "@/api/contract";

export const m = (value: number, uncertainty: number, unit: Unit): Measurement => ({ value, uncertainty, unit, sigma: 1 });
export const tpl = (template: string, params: Record<string, TemplateParam> = {}): TemplatedText => ({ template, params });
export const term = (t: string) => ({ term: t });
export const day = (date: string) => ({ date });

/** NISAR revisit: dates every 12 days from `start` up to `end` (inclusive). */
export function passes(start: string, end: string, step = 12): string[] {
  const out: string[] = [];
  const last = Date.parse(end + "T00:00:00Z");
  for (let t = Date.parse(start + "T00:00:00Z"); t <= last; t += step * 86_400_000) out.push(new Date(t).toISOString().slice(0, 10));
  return out;
}

/** Deterministic wobble in [-1, 1]. */
const wobble = (i: number, seed: number) => Math.sin(i * 1.7 + seed * 2.3) * 0.6 + Math.sin(i * 0.61 + seed) * 0.4;

export function series(dates: string[], valueAt: (i: number) => number, sigmaAt: (i: number) => number, seed: number, jitter: number): SeriesPoint[] {
  return dates.map((date, i) => {
    const value = round(valueAt(i) + (i === 0 ? 0 : wobble(i, seed) * jitter));
    const s = round(sigmaAt(i));
    return { date, value, lo: round(value - s), hi: round(value + s) };
  });
}

const round = (x: number) => Math.round(x * 100) / 100;

let clock = Date.parse("2026-11-11T09:00:00Z");
export function step(
  id: string,
  kind: AgentStep["kind"],
  tool: string,
  duration: number,
  summary: TemplatedText | null,
  params: AgentStep["params"] = {},
): AgentStep {
  const started_at = new Date(clock).toISOString();
  clock += duration + 40;
  return { id, kind, tool, status: "done", params, started_at, duration_ms: duration, summary, error: null };
}
