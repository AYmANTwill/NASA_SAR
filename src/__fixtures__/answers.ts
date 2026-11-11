/** SYNTHETIC answers for UI development. Not NISAR measurements. */
import type { Answer, Earthquake } from "@/api/contract";
import { day, m, passes, series, step, term, tpl } from "./build";

const R = "/__fixtures__/rasters/";
const since = day("2026-06-17");

// ------------------------------------------------------------------ Panama
const panamaDates = passes("2026-06-21", "2026-11-06");
const panamaQuake = panamaDates.findIndex((d) => d > "2026-10-09");
const aftershocks: Earthquake[] = Array.from({ length: 14 }, (_, i) => ({
  id: `fx-as-${i + 1}`,
  lat: 7.42 + Math.sin(i * 2.1) * 0.32,
  lon: -80.32 + Math.cos(i * 1.3) * 0.48,
  depth_km: 10 + ((i * 7) % 25),
  magnitude: { value: Math.round((4 + ((i * 37) % 21) / 10) * 10) / 10, uncertainty: null, type: "mb" },
  time: new Date(Date.parse("2026-10-09T06:10:00Z") + (i + 1) * 9.5 * 3_600_000).toISOString(),
  role: "aftershock",
  url: null,
}));

export const panama: Answer = {
  id: "fx-panama-2026-10-09",
  created_at: "2026-11-10T18:00:00Z",
  question: "Où le sol a-t-il bougé après le séisme du 9 octobre ?",
  lang: "fr",
  location: { lat: 7.45, lon: -80.3, name: "Panama, péninsule d'Azuero", name_i18n: { fr: "Panama, péninsule d'Azuero", ar: "بنما، شبه جزيرة أزويرو", en: "Panama, Azuero peninsula" }, bbox: [-81.3, 6.7, -79.3, 8.3] },
  recipe: "sudden_motion",
  product: "GUNW",
  product_status: "provisional",
  period: { start: "2026-10-03", end: "2026-10-15" },
  acquisitions: panamaDates,
  tracks: [{ number: 41, direction: "ascending", frame: 22 }],
  verdict: tpl("verdict.sudden_motion", { max: m(46, 3, "cm"), date: day("2026-10-09") }),
  confidence: "high",
  stable_in_noise: false,
  metrics: [
    { id: "los_displacement_max", measurement: m(46, 3, "cm") },
    { id: "coherence_loss_area", measurement: m(310, 40, "km2") },
    { id: "noise_floor", measurement: m(1.2, 0.2, "cm") },
    { id: "masked_fraction", measurement: m(14, 2, "percent") },
  ],
  series: [
    {
      id: "los",
      unit: "cm",
      noise_floor: 1.2,
      points: series(panamaDates, (i) => (i >= panamaQuake ? 44 : 0), (i) => (i >= panamaQuake ? 3 : 1.1), 1, 0.7),
    },
  ],
  checks: [
    { id: "noise_floor", status: "pass", measurement: m(1.2, 0.2, "cm"), detail: tpl("check.noise_floor", { noise: m(1.2, 0.2, "cm") }) },
    { id: "coherence_mask", status: "warn", measurement: m(14, 2, "percent"), detail: tpl("check.coherence_mask", { fraction: m(14, 2, "percent"), threshold: 0.3 }) },
    { id: "ionosphere", status: "pass", measurement: null, detail: tpl("check.ionosphere.applied") },
    { id: "unwrapping", status: "warn", measurement: null, detail: tpl("check.unwrapping.jumps", { count: 3 }) },
  ],
  evidence: [
    { source: "usgs", agreement: "agrees", summary: tpl("evidence.usgs.mainshock", { mag: 7.7, date: day("2026-10-09"), count: aftershocks.length }), url: null, retrieved_at: "2026-11-10T17:40:00Z" },
    { source: "osm", agreement: "inconclusive", summary: tpl("evidence.osm.exposure", { buildings: 18400, roads: 920 }), url: null, retrieved_at: "2026-11-10T17:41:00Z" },
  ],
  layers: [
    { id: "panama-disp", kind: "displacement", url: R + "panama-displacement.png", bounds: [-81.3, 6.7, -79.3, 8.3], unit: "cm", min: -50, max: 50, palette: "diverging_displacement", sign_convention: "positive_toward_satellite", period: { start: "2026-10-03", end: "2026-10-15" }, source: "NISAR GUNW" },
    { id: "panama-coh", kind: "coherence_loss", url: R + "panama-coherence-loss.png", bounds: [-81.3, 6.7, -79.3, 8.3], unit: "coherence", min: 0, max: 1, palette: "sequential_coherence_loss", sign_convention: null, period: { start: "2026-10-03", end: "2026-10-15" }, source: "NISAR GUNW" },
  ],
  earthquakes: [
    { id: "fx-main", lat: 7.38, lon: -80.41, depth_km: 22, magnitude: { value: 7.7, uncertainty: null, type: "Mww" }, time: "2026-10-09T06:10:00Z", role: "mainshock", url: null },
    ...aftershocks,
  ],
  limits: [tpl("limit.los_only"), tpl("limit.decorrelation"), tpl("limit.no_prediction")],
  indication: null,
  classifier: null,
  next_pass: "2026-11-18",
  cached: true,
  steps: [
    step("s1", "cache", "atlas.lookup", 60, tpl("step.cache"), { answer: "fx-panama-2026-10-09" }),
    step("s2", "classify", "agent.classify", 180, tpl("step.classify", { recipe: term("recipe.sudden_motion") })),
    step("s3", "search_scenes", "asf_search", 240, tpl("step.search_scenes", { count: 2, start: day("2026-10-03"), end: day("2026-10-15") }), { platform: "NISAR", product: "GUNW", track: 41 }),
    step("s4", "compute", "recipe.sudden_motion", 320, tpl("step.compute.unwrap"), { wavelength_m: 0.24, sign: "toward_satellite" }),
    step("s5", "uncertainty_checks", "checks.run", 140, tpl("step.checks", { passed: 2, total: 4 })),
    step("s6", "cross_evidence", "evidence.usgs", 210, tpl("step.evidence", { count: 2 }), { min_magnitude: 4 }),
    step("s7", "verdict", "agent.verdict", 90, tpl("step.verdict")),
  ],
};

// ------------------------------------------------------------------ Venezuela (plan B)
const vzDates = passes("2026-06-13", "2026-07-31");
export const venezuela: Answer = {
  ...panama,
  id: "fx-venezuela-2026-06-24",
  question: "Où le sol a-t-il bougé après les séismes du 24 juin au Venezuela ?",
  location: { lat: 10.45, lon: -66.9, name: "Venezuela, côte centrale", name_i18n: { fr: "Venezuela, côte centrale", ar: "فنزويلا، الساحل الأوسط", en: "Venezuela, central coast" }, bbox: [-67.8, 9.8, -66.0, 11.1] },
  period: { start: "2026-06-18", end: "2026-06-30" },
  acquisitions: vzDates,
  tracks: [{ number: 66, direction: "descending", frame: 31 }],
  verdict: tpl("verdict.sudden_motion", { max: m(24, 2, "cm"), date: day("2026-06-24") }),
  metrics: [
    { id: "los_displacement_max", measurement: m(24, 2, "cm") },
    { id: "coherence_loss_area", measurement: m(120, 25, "km2") },
    { id: "noise_floor", measurement: m(0.9, 0.2, "cm") },
    { id: "masked_fraction", measurement: m(9, 2, "percent") },
  ],
  series: [{ id: "los", unit: "cm", noise_floor: 0.9, points: series(vzDates, (i) => (vzDates[i] > "2026-06-24" ? 23 : 0), (i) => (vzDates[i] > "2026-06-24" ? 2 : 0.9), 4, 0.5) }],
  evidence: [
    { source: "nasa", agreement: "agrees", summary: tpl("evidence.nasa.map"), url: null, retrieved_at: "2026-11-09T10:00:00Z" },
    { source: "usgs", agreement: "agrees", summary: tpl("evidence.usgs.mainshock", { mag: 7.5, date: day("2026-06-24"), count: 6 }), url: null, retrieved_at: "2026-11-09T10:00:00Z" },
  ],
  layers: [
    { id: "vz-disp", kind: "displacement", url: R + "venezuela-displacement.png", bounds: [-67.8, 9.8, -66.0, 11.1], unit: "cm", min: -30, max: 30, palette: "diverging_displacement", sign_convention: "positive_toward_satellite", period: { start: "2026-06-18", end: "2026-06-30" }, source: "NISAR GUNW" },
  ],
  earthquakes: [
    { id: "fx-vz-main", lat: 10.5, lon: -66.85, depth_km: 15, magnitude: { value: 7.5, uncertainty: null, type: "Mww" }, time: "2026-06-24T02:30:00Z", role: "mainshock", url: null },
  ],
  next_pass: null,
};

// ------------------------------------------------------------------ Al Wahda (stable in noise)
const wahdaDates = passes("2026-06-17", "2026-11-03");
export const alWahda: Answer = {
  id: "fx-alwahda-since-june",
  created_at: "2026-11-10T18:05:00Z",
  question: "Le barrage Al Wahda se déforme-t-il depuis juin ?",
  lang: "fr",
  location: { lat: 34.64, lon: -5.17, name: "Barrage Al Wahda", name_i18n: { fr: "Barrage Al Wahda", ar: "سد الوحدة", en: "Al Wahda dam" }, bbox: [-5.35, 34.52, -4.98, 34.76] },
  recipe: "slow_motion",
  product: "GUNW",
  product_status: "provisional",
  period: { start: "2026-06-17", end: "2026-11-03" },
  acquisitions: wahdaDates,
  tracks: [{ number: 116, direction: "ascending", frame: 19 }],
  verdict: tpl("verdict.stable_in_noise", { noise: m(2.6, 0.4, "mm"), since }),
  confidence: "low",
  stable_in_noise: true,
  metrics: [
    { id: "velocity", measurement: m(-1.1, 2.4, "mm/yr") },
    { id: "noise_floor", measurement: m(2.8, 0.4, "mm/yr") },
    { id: "masked_fraction", measurement: m(6, 1, "percent") },
  ],
  series: [{ id: "los", unit: "mm", noise_floor: 2.6, points: series(wahdaDates, () => 0, () => 2.2, 2, 1.1) }],
  checks: [
    { id: "noise_floor", status: "pass", measurement: m(2.6, 0.4, "mm"), detail: tpl("check.noise_floor", { noise: m(2.6, 0.4, "mm") }) },
    { id: "coherence_mask", status: "pass", measurement: m(6, 1, "percent"), detail: tpl("check.coherence_mask", { fraction: m(6, 1, "percent"), threshold: 0.3 }) },
    { id: "ionosphere", status: "warn", measurement: null, detail: tpl("check.ionosphere.missing") },
    { id: "unwrapping", status: "pass", measurement: null, detail: tpl("check.unwrapping.ok") },
  ],
  evidence: [
    { source: "open_meteo", agreement: "inconclusive", summary: tpl("evidence.open_meteo.rain", { rain: m(41, 6, "mm"), days: 30 }), url: null, retrieved_at: "2026-11-10T17:50:00Z" },
    { source: "usgs", agreement: "unavailable", summary: tpl("evidence.usgs.none", { radius: 100 }), url: null, retrieved_at: "2026-11-10T17:50:00Z" },
  ],
  layers: [
    { id: "wahda-vel", kind: "velocity", url: R + "alwahda-velocity.png", bounds: [-5.35, 34.52, -4.98, 34.76], unit: "mm/yr", min: -20, max: 20, palette: "diverging_displacement", sign_convention: "positive_toward_satellite", period: { start: "2026-06-17", end: "2026-11-03" }, source: "NISAR GUNW stack" },
  ],
  earthquakes: [],
  limits: [tpl("limit.dam_structure"), tpl("limit.short_history", { since }), tpl("limit.los_only")],
  indication: null,
  classifier: null,
  next_pass: "2026-11-15",
  cached: true,
  steps: [
    step("w1", "cache", "atlas.lookup", 40, tpl("step.cache"), { track: 116, frame: 19 }),
    step("w2", "classify", "agent.classify", 150, tpl("step.classify", { recipe: term("recipe.slow_motion") })),
    step("w3", "compute", "recipe.slow_motion", 110, tpl("step.compute.stack", { count: wahdaDates.length - 1 }), { method: "SBAS", reference: "stable_area" }),
    step("w4", "uncertainty_checks", "checks.run", 80, tpl("step.checks", { passed: 3, total: 4 })),
    step("w5", "cross_evidence", "evidence.open_meteo", 120, tpl("step.evidence", { count: 2 })),
    step("w6", "verdict", "agent.verdict", 60, tpl("step.verdict")),
  ],
};

// ------------------------------------------------------------------ Rif slope (discovery #1, accelerating)
const rifDates = passes("2026-06-17", "2026-11-03");
const accel = (i: number) => -(1.2 * i + 0.09 * i * i);
export const rifSlope: Answer = {
  id: "fx-zone-rif-slope",
  created_at: "2026-11-10T18:10:00Z",
  question: "Ce versant au-dessus du village glisse-t-il ?",
  lang: "fr",
  location: { lat: 34.54, lon: -4.64, name: "Versant de Taounate", name_i18n: { fr: "Versant de Taounate", ar: "منحدر تاونات", en: "Taounate slope" }, bbox: [-4.75, 34.47, -4.53, 34.61] },
  recipe: "slow_motion",
  product: "GUNW",
  product_status: "provisional",
  period: { start: "2026-06-17", end: "2026-11-03" },
  acquisitions: rifDates,
  tracks: [
    { number: 116, direction: "ascending", frame: 20 },
    { number: 23, direction: "descending", frame: 108 },
  ],
  verdict: tpl("verdict.slow_motion.accelerating", { velocity: m(-38, 5, "mm/yr"), since: day("2026-09-01") }),
  confidence: "medium",
  stable_in_noise: false,
  metrics: [
    { id: "vertical_velocity", measurement: m(-31, 4, "mm/yr") },
    { id: "east_west_velocity", measurement: m(-19, 5, "mm/yr") },
    { id: "acceleration", measurement: m(-24, 9, "mm/yr2") },
    { id: "noise_floor", measurement: m(3.4, 0.5, "mm/yr") },
  ],
  series: [
    { id: "vertical", unit: "mm", noise_floor: 3.1, points: series(rifDates, (i) => accel(i) * 0.8, (i) => 2.4 + i * 0.15, 5, 0.8) },
    { id: "east_west", unit: "mm", noise_floor: 3.1, points: series(rifDates, (i) => accel(i) * 0.5, (i) => 2.9 + i * 0.18, 6, 0.9) },
  ],
  checks: [
    { id: "noise_floor", status: "pass", measurement: m(3.1, 0.5, "mm"), detail: tpl("check.noise_floor", { noise: m(3.1, 0.5, "mm") }) },
    { id: "coherence_mask", status: "warn", measurement: m(22, 3, "percent"), detail: tpl("check.coherence_mask", { fraction: m(22, 3, "percent"), threshold: 0.3 }) },
    { id: "ionosphere", status: "pass", measurement: null, detail: tpl("check.ionosphere.applied") },
    { id: "unwrapping", status: "pass", measurement: null, detail: tpl("check.unwrapping.ok") },
  ],
  evidence: [
    { source: "open_meteo", agreement: "inconclusive", summary: tpl("evidence.open_meteo.rain", { rain: m(96, 12, "mm"), days: 30 }), url: null, retrieved_at: "2026-11-10T17:55:00Z" },
    { source: "osm", agreement: "inconclusive", summary: tpl("evidence.osm.exposure", { buildings: 214, roads: 6 }), url: null, retrieved_at: "2026-11-10T17:55:00Z" },
  ],
  layers: [
    { id: "rif-vel", kind: "velocity", url: R + "rif-slope-velocity.png", bounds: [-4.75, 34.47, -4.53, 34.61], unit: "mm/yr", min: -40, max: 40, palette: "diverging_displacement", sign_convention: "positive_up", period: { start: "2026-06-17", end: "2026-11-03" }, source: "NISAR GUNW asc+desc" },
  ],
  earthquakes: [],
  limits: [tpl("limit.north_south"), tpl("limit.short_history", { since }), tpl("limit.no_prediction")],
  indication: { method: "inverse_velocity", window: { start: "2027-01-10", end: "2027-04-30" }, caveat: tpl("indication.caveat", { revisit: 12 }) },
  classifier: null,
  next_pass: "2026-11-15",
  cached: true,
  steps: [
    step("r1", "cache", "atlas.lookup", 50, tpl("step.cache"), { tracks: "116A+023D" }),
    step("r2", "compute", "atlas.decompose", 130, tpl("step.compute.decompose"), { geometry: "asc+desc" }),
    step("r3", "uncertainty_checks", "checks.run", 70, tpl("step.checks", { passed: 3, total: 4 })),
    step("r4", "cross_evidence", "evidence.osm", 110, tpl("step.evidence", { count: 2 })),
    step("r5", "verdict", "agent.verdict", 60, tpl("step.verdict")),
  ],
};

// ------------------------------------------------------------------ Gharb soil moisture (live question)
const gharbDates = passes("2026-06-24", "2026-10-20");
export const gharb: Answer = {
  id: "fx-gharb-sme2-2026-10-20",
  created_at: "2026-11-11T09:30:00Z",
  question: "Mes champs du Gharb sont-ils saturés ?",
  lang: "fr",
  location: { lat: 34.52, lon: -6.05, name: "Plaine du Gharb", name_i18n: { fr: "Plaine du Gharb", ar: "سهل الغرب", en: "Gharb plain" }, bbox: [-6.5, 34.2, -5.6, 34.9] },
  recipe: "soil_moisture",
  product: "SME2",
  product_status: "provisional",
  period: { start: "2026-06-24", end: "2026-10-20" },
  acquisitions: gharbDates,
  tracks: [{ number: 15, direction: "ascending", frame: null }],
  verdict: tpl("verdict.soil_moisture", { value: m(0.36, 0.04, "m3/m3"), anomaly: m(0.11, 0.05, "m3/m3") }),
  confidence: "medium",
  stable_in_noise: false,
  metrics: [
    { id: "soil_moisture", measurement: m(0.36, 0.04, "m3/m3") },
    { id: "soil_moisture_anomaly", measurement: m(0.11, 0.05, "m3/m3") },
  ],
  series: [{ id: "soil_moisture", unit: "m3/m3", noise_floor: null, points: series(gharbDates, (i) => (i < gharbDates.length - 2 ? 0.2 + i * 0.004 : 0.34 + (i - gharbDates.length + 2) * 0.02), () => 0.04, 9, 0.015) }],
  checks: [
    { id: "noise_floor", status: "not_applicable", measurement: null, detail: null },
    { id: "coherence_mask", status: "not_applicable", measurement: null, detail: null },
    { id: "ionosphere", status: "pass", measurement: null, detail: tpl("check.ionosphere.applied") },
    { id: "unwrapping", status: "not_applicable", measurement: null, detail: null },
  ],
  evidence: [{ source: "open_meteo", agreement: "agrees", summary: tpl("evidence.open_meteo.rain", { rain: m(58, 8, "mm"), days: 7 }), url: null, retrieved_at: "2026-11-11T09:29:00Z" }],
  layers: [
    { id: "gharb-sm", kind: "soil_moisture", url: R + "gharb-soil-moisture.png", bounds: [-6.5, 34.2, -5.6, 34.9], unit: "m3/m3", min: 0.05, max: 0.5, palette: "sequential_moisture", sign_convention: null, period: { start: "2026-10-20", end: "2026-10-20" }, source: "NISAR SME2 L3" },
  ],
  earthquakes: [],
  limits: [tpl("limit.soil_depth"), tpl("limit.resolution", { resolution: 200 })],
  indication: null,
  classifier: null,
  next_pass: "2026-11-13",
  cached: false,
  steps: [
    step("g1", "classify", "agent.classify", 420, tpl("step.classify", { recipe: term("recipe.soil_moisture") })),
    step("g2", "search_scenes", "asf_search", 610, tpl("step.search_scenes", { count: 1, start: day("2026-10-20"), end: day("2026-10-20") }), { platform: "NISAR", product: "SME2" }),
    step("g3", "download", "asf.download", 1200, tpl("step.download", { count: 1, size_mb: 105 }), { partial_read: true }),
    step("g4", "compute", "recipe.soil_moisture", 380, tpl("step.compute.anomaly", { count: gharbDates.length - 1 })),
    step("g5", "cross_evidence", "evidence.open_meteo", 300, tpl("step.evidence", { count: 1 })),
    step("g6", "verdict", "agent.verdict", 150, tpl("step.verdict")),
  ],
};

export const fixtureAnswers: Answer[] = [panama, venezuela, alWahda, rifSlope, gharb];
