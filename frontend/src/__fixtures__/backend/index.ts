/**
 * REAL backend answers, recorded on 14 November 2026 from the team's FastAPI
 * backend (branch feat/frontend-adapter, `/api/answers/event-*` and `/api/demo`),
 * computed on real NISAR products (branch results/real-data-checks).
 *
 * Two adjustments, both documented:
 * - `layers` are emptied: the PNG rasters are rendered from the HDF5 products,
 *   which are not shipped with the frontend. No image is shown rather than a fake one.
 * - recipe "damage" → "surface_change": the backend adapter sent surface change
 *   as "damage" only until the frontend enum had "surface_change" (their request 1).
 * Every value, verdict, step and limit is otherwise exactly as the backend returned it.
 */
import type { Answer, DemoBundle } from "@/api/contract";
import alWahda from "./event-al-wahda-surroundings";
import benGuerir from "./event-ben-guerir-mine";
import gharb from "./event-gharb-soil-moisture";
import haouzFlood from "./event-haouz-flood-2026-10-10";
import haouzSoil from "./event-haouz-soil-moisture";
import demo from "./demo";

export const RECORDED_ON = "2026-11-14";

/** Raw recordings, before parsing (the contract test parses them with zod). */
export const recordedRaw: unknown[] = [haouzFlood, haouzSoil, gharb, benGuerir, alWahda];

export function prepareRecorded(raw: unknown): Answer {
  const a = structuredClone(raw) as Answer & { recipe: string };
  a.layers = [];
  if (a.recipe === "damage") a.recipe = "surface_change";
  return a as Answer;
}

export const recordedAnswers: Answer[] = recordedRaw.map(prepareRecorded);

const ids = new Set(recordedAnswers.map((a) => a.id));
export const recordedDemoEntries: DemoBundle["entries"] = (demo as DemoBundle).entries.filter((e) => ids.has(e.answer_id));

/** Recorded real answers all carry the backend's "event-" id prefix. */
export const isRecordedAnswerId = (id: string) => id.startsWith("event-");
