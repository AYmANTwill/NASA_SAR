/**
 * Fixtures for UI development and the offline demo.
 * - ./answers, ./build: SYNTHETIC data, not NISAR measurements.
 * - ./backend: REAL answers recorded from the team's backend (see its header).
 */
import type { DemoBundle, Discoveries, LbandProof, LibraryEvent, Watch, WatchNotification } from "@/api/contract";
import { alWahda, fixtureAnswers as syntheticAnswers, gharb, panama, rifSlope, venezuela } from "./answers";
import { recordedAnswers, recordedDemoEntries } from "./backend";
import recordedLibrary from "./backend/library";
import { day, m, term, tpl } from "./build";

export const fixtureAnswers = [...syntheticAnswers, ...recordedAnswers];

export const discoveries: Discoveries = {
  region: "MA",
  region_name: { fr: "Maroc", ar: "المغرب", en: "Morocco" },
  generated_at: "2026-11-10T06:00:00Z",
  period: { start: "2026-06-17", end: "2026-11-03" },
  noise_floor: m(3, 0.5, "mm/yr"),
  threshold_factor: 3,
  zones: [
    { id: "z-rif-slope", rank: 1, location: rifSlope.location, kind: "slope", velocity: m(-38, 5, "mm/yr"), vertical: m(-31, 4, "mm/yr"), east_west: m(-19, 5, "mm/yr"), snr: 12.7, exposure: { buildings: 214, roads_km: 6, dams: 0, mines: 0 }, exposure_score: 0.71, confidence: "medium", manually_checked: true, answer_id: rifSlope.id },
    { id: "z-khouribga", rank: 2, location: { lat: 32.88, lon: -6.91, name: "Bassin de Khouribga", name_i18n: { fr: "Bassin de Khouribga", ar: "حوض خريبكة", en: "Khouribga basin" }, bbox: null }, kind: "mine", velocity: m(-52, 7, "mm/yr"), vertical: null, east_west: null, snr: 17.3, exposure: { buildings: 12, roads_km: 3, dams: 0, mines: 1 }, exposure_score: 0.34, confidence: "medium", manually_checked: true, answer_id: null },
    { id: "z-fes-north", rank: 3, location: { lat: 34.07, lon: -4.98, name: "Fès, quartiers nord", name_i18n: { fr: "Fès, quartiers nord", ar: "فاس، الأحياء الشمالية", en: "Fès, northern districts" }, bbox: null }, kind: "urban", velocity: m(-14, 3, "mm/yr"), vertical: m(-13, 3, "mm/yr"), east_west: m(2, 4, "mm/yr"), snr: 4.7, exposure: { buildings: 5320, roads_km: 48, dams: 0, mines: 0 }, exposure_score: 0.88, confidence: "medium", manually_checked: false, answer_id: null },
    { id: "z-a2-embankment", rank: 4, location: { lat: 34.21, lon: -5.62, name: "Remblai autoroutier A2", name_i18n: { fr: "Remblai autoroutier A2", ar: "ردم الطريق السيار A2", en: "A2 motorway embankment" }, bbox: null }, kind: "infrastructure", velocity: m(-11, 3, "mm/yr"), vertical: null, east_west: null, snr: 3.7, exposure: { buildings: 0, roads_km: 2, dams: 0, mines: 0 }, exposure_score: 0.41, confidence: "low", manually_checked: false, answer_id: null },
    { id: "z-benguerir", rank: 5, location: { lat: 32.24, lon: -7.95, name: "Ben Guerir, front de mine", name_i18n: { fr: "Ben Guerir, front de mine", ar: "ابن جرير، واجهة المنجم", en: "Ben Guerir, mine front" }, bbox: null }, kind: "mine", velocity: m(-10, 3, "mm/yr"), vertical: null, east_west: null, snr: 3.3, exposure: { buildings: 4, roads_km: 1, dams: 0, mines: 1 }, exposure_score: 0.22, confidence: "low", manually_checked: false, answer_id: null },
  ],
};

export const initialWatches: Watch[] = [
  { id: "w-rif-slope", location: rifSlope.location, question: rifSlope.question, recipe: "slow_motion", created_at: "2026-09-20T10:00:00Z", level: "orange", confidence: "medium", last_pass: "2026-11-03", next_pass: "2026-11-15", track: { number: 116, direction: "ascending", frame: 20 }, answer_id: rifSlope.id },
];

export const initialNotifications: WatchNotification[] = [
  { id: "n-rif-2", watch_id: "w-rif-slope", created_at: "2026-11-03T21:10:00Z", level: "orange", previous_level: "yellow", message: tpl("notify.level_changed", { place: { localized: rifSlope.location.name_i18n ?? {} }, level: term("level.orange"), velocity: m(-38, 5, "mm/yr") }), answer_id: rifSlope.id },
  { id: "n-rif-1", watch_id: "w-rif-slope", created_at: "2026-10-10T21:05:00Z", level: "yellow", previous_level: null, message: tpl("notify.level_changed", { place: { localized: rifSlope.location.name_i18n ?? {} }, level: term("level.yellow"), velocity: m(-21, 7, "mm/yr") }), answer_id: null },
];

export const library: LibraryEvent[] = [
  // Real, recorded from the backend (only events whose answer was recorded).
  ...(recordedLibrary as unknown as LibraryEvent[]).filter((e) => recordedAnswers.some((a) => a.id === e.answer_id)),
  {
    id: "lib-panama", kind: "earthquake", date: "2026-10-09", location: panama.location, magnitude: { value: 7.7, type: "Mww" }, answer_id: panama.id,
    reference: { source: "usgs", agreement: "agrees", summary: tpl("library.usgs", { mag: 7.7, date: day("2026-10-09") }), url: null, comparison: null },
  },
  {
    id: "lib-venezuela", kind: "earthquake", date: "2026-06-24", location: venezuela.location, magnitude: { value: 7.5, type: "Mww" }, answer_id: venezuela.id,
    reference: { source: "nasa", agreement: "agrees", summary: tpl("library.nasa_map"), url: null, comparison: { metric: "los_displacement_max", nisar: m(24, 2, "cm"), reference: m(22, 3, "cm") } },
  },
];

export const lbandProof: LbandProof = {
  site: { lat: 35.12, lon: -5.25, name: "Rif boisé, Chefchaouen", name_i18n: { fr: "Rif boisé, Chefchaouen", ar: "الريف المشجر، شفشاون", en: "Forested Rif, Chefchaouen" }, bbox: [-5.6, 34.9, -4.9, 35.4] },
  period: { start: "2026-10-08", end: "2026-10-20" },
  forest_source: "ESA WorldCover",
  usable_threshold: 0.3,
  nisar: {
    coherence: m(0.58, 0.04, "coherence"),
    layer: { id: "rif-coh-l", kind: "coherence", url: "/__fixtures__/rasters/rif-coherence-nisar.png", bounds: [-5.6, 34.9, -4.9, 35.4], unit: "coherence", min: 0, max: 1, palette: "sequential_coherence", sign_convention: null, period: { start: "2026-10-08", end: "2026-10-20" }, source: "NISAR GUNW (L)" },
  },
  sentinel1: {
    coherence: m(0.27, 0.05, "coherence"),
    layer: { id: "rif-coh-c", kind: "coherence", url: "/__fixtures__/rasters/rif-coherence-s1.png", bounds: [-5.6, 34.9, -4.9, 35.4], unit: "coherence", min: 0, max: 1, palette: "sequential_coherence", sign_convention: null, period: { start: "2026-10-08", end: "2026-10-20" }, source: "Sentinel-1 (C)" },
  },
  bins: [
    { forest_cover: { min: 0, max: 20 }, nisar: m(0.68, 0.04, "coherence"), sentinel1: m(0.52, 0.05, "coherence"), pixels: 41200 },
    { forest_cover: { min: 20, max: 40 }, nisar: m(0.63, 0.04, "coherence"), sentinel1: m(0.39, 0.05, "coherence"), pixels: 35800 },
    { forest_cover: { min: 40, max: 60 }, nisar: m(0.57, 0.05, "coherence"), sentinel1: m(0.28, 0.05, "coherence"), pixels: 30100 },
    { forest_cover: { min: 60, max: 80 }, nisar: m(0.51, 0.05, "coherence"), sentinel1: m(0.19, 0.04, "coherence"), pixels: 27400 },
    { forest_cover: { min: 80, max: 100 }, nisar: m(0.46, 0.06, "coherence"), sentinel1: m(0.14, 0.04, "coherence"), pixels: 19900 },
  ],
  verdict: tpl("verdict.lband_proof", { threshold: 0.3 }),
  limits: [tpl("limit.proof_single_pair"), tpl("limit.proof_baseline")],
};

export const demoBundle: DemoBundle = {
  generated_at: "2026-11-10T18:15:00Z",
  entries: [
    { answer_id: panama.id, questions: [{ text: panama.question, lang: "fr" }, { text: "Where did the ground move after the 9 October earthquake?", lang: "en" }, { text: "أين تحركت الأرض بعد زلزال 9 أكتوبر؟", lang: "ar" }] },
    { answer_id: venezuela.id, questions: [{ text: venezuela.question, lang: "fr" }, { text: "Where did the ground move after the 24 June earthquakes in Venezuela?", lang: "en" }, { text: "أين تحركت الأرض بعد زلازل 24 يونيو في فنزويلا؟", lang: "ar" }] },
    { answer_id: alWahda.id, questions: [{ text: alWahda.question, lang: "fr" }, { text: "Le barrage se déforme-t-il depuis juin ?", lang: "fr" }, { text: "Is the Al Wahda dam deforming since June?", lang: "en" }, { text: "هل يتشوه سد الوحدة منذ يونيو؟", lang: "ar" }] },
    { answer_id: rifSlope.id, questions: [{ text: rifSlope.question, lang: "fr" }, { text: "Is this slope above the village sliding?", lang: "en" }, { text: "هل ينزلق هذا المنحدر فوق القرية؟", lang: "ar" }] },
    { answer_id: gharb.id, questions: [{ text: gharb.question, lang: "fr" }, { text: "Are my fields in the Gharb saturated?", lang: "en" }, { text: "هل حقولي في الغرب مشبعة بالماء؟", lang: "ar" }] },
    ...recordedDemoEntries,
  ],
};
export { caseStudies, caseSummaries } from "./cases";
