/**
 * CaseStudy contract (docs/CASE_CONTRACT.md), proposed for src/api/contract.ts of the frontend.
 * Mirrors backend/science/case_models.py field for field. Imports the existing types from ./contract.
 *
 * Once the frontend adds "Mw", "people", "count", "deg" to its Unit enum, CaseMeasurement can be replaced by
 * Measurement.
 */
import { z } from "zod";
import { Bounds, Measurement, RasterLayer, TemplatedText, Unit } from "./contract";

export const CaseUnit = z.union([Unit, z.enum(["Mw", "people", "count", "deg"])]);
export const CaseMeasurement = Measurement.extend({ unit: CaseUnit });
export type CaseMeasurement = z.infer<typeof CaseMeasurement>;

const Lang3 = z.object({ fr: z.string().min(1), en: z.string().min(1), ar: z.string().min(1) });
const isoUtc = z.string().datetime({ offset: true });
const Source = z.object({ name: z.string().min(1), url: z.string().url() });

export const CaseId = z.enum(["panama-2026", "venezuela-2026", "haouz-flood-2026", "ionosphere-gps"]);
export const CaseKind = z.enum(["earthquake", "flood", "method"]);
export const CaseStatus = z.enum(["draft", "final"]);
export const CaseAgreement = z.enum(["agree", "partial", "disagree", "no_reference"]);

/** agree if |n − r| ≤ 2·sqrt(σn² + σr²), partial if ≤ 4·sqrt(...), else disagree (1-sigma values). */
export function caseAgreement(n: CaseMeasurement, r: CaseMeasurement | null): z.infer<typeof CaseAgreement> {
  if (r === null) return "no_reference";
  const d = Math.abs(n.value - r.value);
  const s = Math.hypot(n.uncertainty / n.sigma, r.uncertainty / r.sigma);
  if (s === 0) return d === 0 ? "agree" : "disagree";
  return d <= 2 * s ? "agree" : d <= 4 * s ? "partial" : "disagree";
}

export const CaseFinding = z
  .object({
    id: z.string().min(1),
    label: Lang3,
    nisar: CaseMeasurement,
    reference: CaseMeasurement.nullable(),
    reference_source: Source.nullable(),
    agreement: CaseAgreement,
  })
  .superRefine((f, ctx) => {
    if ((f.reference === null) !== (f.reference_source === null))
      ctx.addIssue({ code: "custom", message: "reference and reference_source go together" });
    if (f.reference && f.reference.unit !== f.nisar.unit)
      ctx.addIssue({ code: "custom", message: "nisar and reference units differ" });
    else if (f.agreement !== caseAgreement(f.nisar, f.reference))
      ctx.addIssue({ code: "custom", message: `agreement ${f.agreement} does not follow the 2σ/4σ rule` });
  });
export type CaseFinding = z.infer<typeof CaseFinding>;

export const CaseFigure = z.object({
  id: z.string().min(1),
  kind: z.enum(["map", "chart", "image"]),
  title: Lang3,
  url: z.string().min(1),
  caption: TemplatedText,
  layer: RasterLayer.optional(),
});

export const CaseExposure = z.object({
  people: CaseMeasurement.extend({ unit: z.literal("people") }),
  buildings: CaseMeasurement.extend({ unit: z.literal("count") }),
  area_km2: CaseMeasurement.extend({ unit: z.literal("km2") }),
  source: Source,
});

export const CaseStudy = z.object({
  id: CaseId,
  kind: CaseKind,
  status: CaseStatus,
  title: Lang3,
  date: isoUtc,
  location: z.object({ lat: z.number().min(-90).max(90), lon: z.number().min(-180).max(180), bbox: Bounds, place: Lang3 }),
  headline: TemplatedText,
  findings: z.array(CaseFinding),
  figures: z.array(CaseFigure),
  exposure: CaseExposure.nullable(),
  timeline: z.array(z.object({ label: Lang3, at: isoUtc })),
  answer_ids: z.array(z.string()),
  limits: z.array(TemplatedText).min(1, "every case must state its limits"),
});
export type CaseStudy = z.infer<typeof CaseStudy>;

export const CaseSummary = z.object({
  id: CaseId,
  kind: CaseKind,
  title: Lang3,
  date: isoUtc,
  status: CaseStatus,
  thumbnail_url: z.string().nullable(),
});
export type CaseSummary = z.infer<typeof CaseSummary>;
