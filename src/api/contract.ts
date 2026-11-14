/**
 * NISAR Pulse API contract (v2).
 *
 * Single source of truth for the frontend. Every response is validated with
 * these schemas before it reaches a component; a mismatch is surfaced as a
 * ContractError, never silently patched. docs/API_CONTRACT.md mirrors this
 * file for the FastAPI team (Pydantic models should match field for field).
 *
 * Rules encoded here:
 * - every measurement carries an uncertainty (Measurement.uncertainty is required);
 * - confidence and watch level are computed by the backend, never by the UI;
 * - prose is never free text from the LLM: it is a template id + parameters
 *   (TemplatedText) so numbers always come from code and can be rendered in FR/AR/EN;
 * - every answer ends with at least one "what the radar cannot tell here" item.
 */
import { z } from "zod";

export const LANGS = ["fr", "ar", "en"] as const;
export const Lang = z.enum(LANGS);
export type Lang = z.infer<typeof Lang>;

export const Unit = z.enum(["mm", "cm", "m", "mm/yr", "cm/yr", "mm/yr2", "m3/m3", "dB", "ha", "km2", "percent", "coherence", "km"]);
export type Unit = z.infer<typeof Unit>;

const isoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "expected YYYY-MM-DD");
const isoDateTime = z.string().datetime({ offset: true });

/** A physical quantity with its 1-sigma (or declared sigma) uncertainty. */
export const Measurement = z.object({
  value: z.number().finite(),
  uncertainty: z.number().finite().nonnegative(),
  unit: Unit,
  /** How many standard deviations `uncertainty` represents (1 = ±1σ). */
  sigma: z.number().positive().default(1),
});
export type Measurement = z.infer<typeof Measurement>;

export const TemplateParam = z.union([
  z.string(),
  z.number().finite(),
  Measurement,
  z.object({ date: isoDate }),
  /** Reference to a catalog term translated by the frontend, e.g. "recipe.slow_motion", "level.orange". */
  z.object({ term: z.string() }),
  /** A proper noun given by the backend in each language (place names). */
  z.object({ localized: z.object({ fr: z.string(), ar: z.string(), en: z.string() }).partial() }),
]);
export type TemplateParam = z.infer<typeof TemplateParam>;

/**
 * Localizable prose. `template` is a key of the frontend template catalog
 * (src/i18n/locales/*.json → "tpl"). `text` is an optional per-language
 * fallback used only when the template is unknown to this frontend build.
 */
export const TemplatedText = z.object({
  template: z.string().min(1),
  params: z.record(TemplateParam).default({}),
  text: z.object({ fr: z.string(), ar: z.string(), en: z.string() }).partial().optional(),
});
export type TemplatedText = z.infer<typeof TemplatedText>;

export const Bounds = z.tuple([z.number(), z.number(), z.number(), z.number()]); // [west, south, east, north]
export type Bounds = z.infer<typeof Bounds>;

export const Location = z.object({
  lat: z.number().min(-90).max(90),
  lon: z.number().min(-180).max(180),
  name: z.string().nullable(),
  name_i18n: z.object({ fr: z.string(), ar: z.string(), en: z.string() }).partial().optional(),
  bbox: Bounds.nullable().optional(),
});
export type Location = z.infer<typeof Location>;

export const Confidence = z.enum(["high", "medium", "low"]);
export type Confidence = z.infer<typeof Confidence>;

export const WatchLevel = z.enum(["yellow", "orange", "red"]);
export type WatchLevel = z.infer<typeof WatchLevel>;

export const Recipe = z.enum([
  "sudden_motion",
  "slow_motion",
  "damage",
  "flood",
  "deforestation",
  "soil_moisture",
  "large_displacement",
  "surface_change",
]);
export type Recipe = z.infer<typeof Recipe>;

export const Product = z.enum(["GUNW", "GCOV", "GOFF", "SME2"]);
export type Product = z.infer<typeof Product>;

// ---------------------------------------------------------------- agent steps

export const StepKind = z.enum([
  "classify",
  "select_recipe",
  "search_scenes",
  "download",
  "compute",
  "uncertainty_checks",
  "cross_evidence",
  "verdict",
  "cache",
]);
export type StepKind = z.infer<typeof StepKind>;

export const StepStatus = z.enum(["pending", "running", "done", "failed", "skipped"]);
export type StepStatus = z.infer<typeof StepStatus>;

export const AgentStep = z.object({
  id: z.string(),
  kind: StepKind,
  /** Tool or recipe name as called by the agent, e.g. "asf_search", "recipe.slow_motion". */
  tool: z.string(),
  status: StepStatus,
  params: z.record(z.union([z.string(), z.number(), z.boolean(), z.null()])).default({}),
  started_at: isoDateTime,
  duration_ms: z.number().nonnegative().nullable(),
  summary: TemplatedText.nullable(),
  error: TemplatedText.nullable(),
});
export type AgentStep = z.infer<typeof AgentStep>;

// ---------------------------------------------------------------- answer parts

export const SeriesPoint = z.object({
  date: isoDate,
  value: z.number().finite(),
  lo: z.number().finite(),
  hi: z.number().finite(),
});
export type SeriesPoint = z.infer<typeof SeriesPoint>;

export const SeriesId = z.enum(["los", "vertical", "east_west", "soil_moisture", "backscatter", "coherence"]);
export type SeriesId = z.infer<typeof SeriesId>;

export const Series = z.object({
  id: SeriesId,
  unit: Unit,
  points: z.array(SeriesPoint).min(1),
  /** lo/hi are value ∓ sigma·σ. */
  sigma: z.number().positive().default(1),
  /** ± noise floor drawn as a reference band around zero, same unit. */
  noise_floor: z.number().nonnegative().nullable(),
});
export type Series = z.infer<typeof Series>;

export const MetricId = z.enum([
  "los_displacement_max",
  "velocity",
  "vertical_velocity",
  "east_west_velocity",
  "acceleration",
  "vertical_displacement",
  "east_west_displacement",
  "coherence_loss_area",
  "flooded_area",
  "flood_duration",
  "forest_loss",
  "soil_moisture",
  "soil_moisture_anomaly",
  "offset_max",
  "masked_fraction",
  "noise_floor",
]);
export type MetricId = z.infer<typeof MetricId>;

export const Metric = z.object({ id: MetricId, measurement: Measurement });
export type Metric = z.infer<typeof Metric>;

export const CheckId = z.enum(["noise_floor", "coherence_mask", "ionosphere", "unwrapping"]);
export type CheckId = z.infer<typeof CheckId>;

export const Check = z.object({
  id: CheckId,
  status: z.enum(["pass", "warn", "fail", "not_applicable"]),
  measurement: Measurement.nullable(),
  detail: TemplatedText.nullable(),
});
export type Check = z.infer<typeof Check>;

export const EvidenceSource = z.enum(["usgs", "open_meteo", "firms", "copernicus_gfm", "osm", "sentinel1", "sentinel2", "nasa", "gdacs"]);
export type EvidenceSource = z.infer<typeof EvidenceSource>;

export const Agreement = z.enum(["agrees", "disagrees", "inconclusive", "unavailable"]);
export type Agreement = z.infer<typeof Agreement>;

export const Evidence = z.object({
  source: EvidenceSource,
  agreement: Agreement,
  summary: TemplatedText,
  url: z.string().url().nullable(),
  retrieved_at: isoDateTime.nullable(),
});
export type Evidence = z.infer<typeof Evidence>;

export const Palette = z.enum(["diverging_displacement", "sequential_coherence", "sequential_coherence_loss", "sequential_moisture"]);
export type Palette = z.infer<typeof Palette>;

export const SignConvention = z.enum(["positive_toward_satellite", "positive_away_from_satellite", "positive_up", "positive_east"]);
export type SignConvention = z.infer<typeof SignConvention>;

export const RasterLayer = z.object({
  id: z.string(),
  kind: z.enum(["displacement", "velocity", "coherence", "coherence_loss", "soil_moisture", "backscatter_change", "offset"]),
  /** North-up RGBA PNG rendered with `palette` between min and max. */
  url: z.string(),
  bounds: Bounds,
  unit: Unit,
  min: z.number().finite(),
  max: z.number().finite(),
  palette: Palette,
  sign_convention: SignConvention.nullable(),
  period: z.object({ start: isoDate, end: isoDate }).nullable(),
  source: z.string(),
});
export type RasterLayer = z.infer<typeof RasterLayer>;

export const Earthquake = z.object({
  id: z.string(),
  lat: z.number(),
  lon: z.number(),
  depth_km: z.number().nullable(),
  magnitude: z.object({ value: z.number(), uncertainty: z.number().nonnegative().nullable(), type: z.string() }),
  time: isoDateTime,
  role: z.enum(["mainshock", "aftershock"]),
  url: z.string().url().nullable(),
});
export type Earthquake = z.infer<typeof Earthquake>;

export const Indication = z.object({
  method: z.literal("inverse_velocity"),
  window: z.object({ start: isoDate, end: isoDate }),
  caveat: TemplatedText,
});
export type Indication = z.infer<typeof Indication>;

export const ClassifierResult = z.object({
  label: z.enum(["flooded", "burned", "vegetation_loss", "stable"]),
  beta: z.literal(true),
  precision: z.number().min(0).max(1),
  recall: z.number().min(0).max(1),
  evaluated_on: z.string(),
});
export type ClassifierResult = z.infer<typeof ClassifierResult>;

export const Track = z.object({ number: z.number().int(), direction: z.enum(["ascending", "descending"]), frame: z.number().int().nullable() });
export type Track = z.infer<typeof Track>;

export const Answer = z.object({
  id: z.string(),
  created_at: isoDateTime,
  question: z.string(),
  lang: Lang,
  location: Location,
  recipe: Recipe,
  product: Product,
  product_status: z.enum(["provisional", "validated"]),
  period: z.object({ start: isoDate, end: isoDate }),
  acquisitions: z.array(isoDate),
  tracks: z.array(Track),
  verdict: TemplatedText,
  confidence: Confidence,
  /** True when the signal does not exceed the noise floor: a valid, first-class answer. */
  stable_in_noise: z.boolean(),
  metrics: z.array(Metric),
  series: z.array(Series),
  checks: z.array(Check),
  evidence: z.array(Evidence),
  layers: z.array(RasterLayer),
  earthquakes: z.array(Earthquake),
  limits: z.array(TemplatedText).min(1, "every answer must state what the radar cannot tell"),
  indication: Indication.nullable(),
  classifier: ClassifierResult.nullable(),
  next_pass: isoDate.nullable(),
  cached: z.boolean(),
  steps: z.array(AgentStep),
});
export type Answer = z.infer<typeof Answer>;

// ---------------------------------------------------------------- endpoints

export const AskRequest = z.object({
  question: z.string().min(1),
  lang: Lang,
  location: z.object({ lat: z.number(), lon: z.number() }).nullable(),
});
export type AskRequest = z.infer<typeof AskRequest>;

export const ApiErrorBody = z.object({ code: z.string(), message: TemplatedText });
export type ApiErrorBody = z.infer<typeof ApiErrorBody>;

export const Exposure = z.object({
  buildings: z.number().int().nonnegative().nullable(),
  roads_km: z.number().nonnegative().nullable(),
  dams: z.number().int().nonnegative().nullable(),
  mines: z.number().int().nonnegative().nullable(),
});
export type Exposure = z.infer<typeof Exposure>;

export const Zone = z.object({
  id: z.string(),
  rank: z.number().int().positive(),
  location: Location,
  kind: z.enum(["dam", "mine", "urban", "slope", "infrastructure", "other"]),
  velocity: Measurement,
  vertical: Measurement.nullable(),
  east_west: Measurement.nullable(),
  /** |velocity| divided by the noise floor, computed by the backend. */
  snr: z.number().nonnegative(),
  exposure: Exposure,
  /** Backend-computed exposure score used for the "by exposure" ordering. */
  exposure_score: z.number().nonnegative(),
  confidence: Confidence,
  manually_checked: z.boolean(),
  answer_id: z.string().nullable(),
});
export type Zone = z.infer<typeof Zone>;

export const Discoveries = z.object({
  region: z.string(),
  region_name: z.object({ fr: z.string(), ar: z.string(), en: z.string() }),
  generated_at: isoDateTime,
  period: z.object({ start: isoDate, end: isoDate }),
  noise_floor: Measurement,
  threshold_factor: z.number().positive(),
  zones: z.array(Zone),
});
export type Discoveries = z.infer<typeof Discoveries>;

export const Watch = z.object({
  id: z.string(),
  location: Location,
  question: z.string(),
  recipe: Recipe,
  created_at: isoDateTime,
  level: WatchLevel.nullable(),
  confidence: Confidence.nullable(),
  last_pass: isoDate.nullable(),
  next_pass: isoDate,
  track: Track.nullable(),
  answer_id: z.string().nullable(),
});
export type Watch = z.infer<typeof Watch>;

export const WatchNotification = z.object({
  id: z.string(),
  watch_id: z.string(),
  created_at: isoDateTime,
  level: WatchLevel,
  previous_level: WatchLevel.nullable(),
  message: TemplatedText,
  answer_id: z.string().nullable(),
});
export type WatchNotification = z.infer<typeof WatchNotification>;

export const CreateWatchRequest = z.object({ answer_id: z.string() });
export type CreateWatchRequest = z.infer<typeof CreateWatchRequest>;

export const LibraryEvent = z.object({
  id: z.string(),
  kind: z.enum(["earthquake", "flood", "landslide", "volcano"]),
  date: isoDate,
  location: Location,
  magnitude: z.object({ value: z.number(), type: z.string() }).nullable(),
  answer_id: z.string().nullable(),
  reference: z.object({
    source: EvidenceSource,
    agreement: Agreement,
    summary: TemplatedText,
    url: z.string().url().nullable(),
    comparison: z
      .object({ metric: MetricId, nisar: Measurement, reference: Measurement })
      .nullable(),
  }),
});
export type LibraryEvent = z.infer<typeof LibraryEvent>;

export const CoherenceBin = z.object({
  forest_cover: z.object({ min: z.number().min(0).max(100), max: z.number().min(0).max(100) }),
  nisar: Measurement,
  sentinel1: Measurement,
  pixels: z.number().int().nonnegative(),
});
export type CoherenceBin = z.infer<typeof CoherenceBin>;

export const LbandProof = z.object({
  site: Location,
  period: z.object({ start: isoDate, end: isoDate }),
  forest_source: z.string(),
  usable_threshold: z.number().min(0).max(1),
  nisar: z.object({ layer: RasterLayer, coherence: Measurement }),
  sentinel1: z.object({ layer: RasterLayer, coherence: Measurement }),
  bins: z.array(CoherenceBin).min(1),
  verdict: TemplatedText,
  limits: z.array(TemplatedText).min(1),
});
export type LbandProof = z.infer<typeof LbandProof>;

/** Precomputed answers the client keeps for offline replay (demo mode). */
export const DemoBundle = z.object({
  generated_at: isoDateTime,
  entries: z.array(
    z.object({
      answer_id: z.string(),
      /** Questions (any language) that map to this answer, matched after normalization. */
      questions: z.array(z.object({ text: z.string().min(1), lang: Lang })).min(1),
    }),
  ),
});
export type DemoBundle = z.infer<typeof DemoBundle>;

export const Health = z.object({ status: z.literal("ok"), version: z.string(), data: z.enum(["live", "cache"]) });
export type Health = z.infer<typeof Health>;
