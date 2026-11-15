/** Synthetic scenarios copied from frontend's UI fixtures. TESTS ONLY: never a live fallback. */
import type { Discoveries, LbandProof, Measurement, TemplateParam, TemplatedText, Unit } from "@/api/contract";
const m = (value: number, uncertainty: number, unit: Unit): Measurement => ({ value, uncertainty, unit, sigma: 1 });
const tpl = (template: string, params: Record<string, TemplateParam> = {}): TemplatedText => ({ template, params, text: { en: "Synthetic test fixture", fr: "Scénario synthétique de test", ar: "بيانات اصطناعية للاختبار" } });
export const proofScenario: LbandProof = {
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

export const discoveryScenario: Discoveries = {
 region: "MA", region_name: { fr: "Maroc", en: "Morocco", ar: "المغرب" }, generated_at: "2026-11-10T06:00:00Z",
 period: {start: "2026-06-17", end: "2026-11-03"}, noise_floor: m(3, 0.5, "mm/yr"), threshold_factor: 3,
 zones: [
{ id: "z-khouribga", rank: 2, location: { lat: 32.88, lon: -6.91, name: "Bassin de Khouribga", name_i18n: { fr: "Bassin de Khouribga", ar: "حوض خريبكة", en: "Khouribga basin" }, bbox: null }, kind: "mine", velocity: m(-52, 7, "mm/yr"), vertical: null, east_west: null, snr: 17.3, exposure: { buildings: 12, roads_km: 3, dams: 0, mines: 1 }, exposure_score: 0.34, confidence: "medium", manually_checked: true, answer_id: null },
{ id: "z-fes-north", rank: 3, location: { lat: 34.07, lon: -4.98, name: "Fès, quartiers nord", name_i18n: { fr: "Fès, quartiers nord", ar: "فاس، الأحياء الشمالية", en: "Fès, northern districts" }, bbox: null }, kind: "urban", velocity: m(-14, 3, "mm/yr"), vertical: m(-13, 3, "mm/yr"), east_west: m(2, 4, "mm/yr"), snr: 4.7, exposure: { buildings: 5320, roads_km: 48, dams: 0, mines: 0 }, exposure_score: 0.88, confidence: "medium", manually_checked: false, answer_id: null },
] };
