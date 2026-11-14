/**
 * DRAFT case studies, until the backend serves /api/cases (contract: docs/CASE_CONTRACT.md).
 * Every one is `status: "draft"` and shown under a "DRAFT, example values" banner.
 * No new number is invented here: values are taken from the existing fixtures
 * (synthetic for Panama and Venezuela, real recorded answer for Al Haouz);
 * where nothing exists (ionosphere + GPS), findings stay empty ("not measured yet").
 */
import type { Answer, CaseStudy, CaseSummary, Localized, TemplatedText } from "@/api/contract";
import { panama, venezuela } from "./answers";
import { recordedAnswers } from "./backend";

const metric = (a: Answer, id: string) => a.metrics.find((x) => x.id === id)?.measurement;
const prose = (key: string, fr: string, en: string, ar: string): TemplatedText => ({ template: `backend.case.${key}`, params: {}, text: { fr, en, ar } });
const loc = (a: Answer, place: Localized): CaseStudy["location"] => ({
  lat: a.location.lat,
  lon: a.location.lon,
  bbox: a.location.bbox ?? [a.location.lon - 0.15, a.location.lat - 0.15, a.location.lon + 0.15, a.location.lat + 0.15],
  place,
});
const placeOf = (a: Answer): Localized => ({ fr: a.location.name_i18n?.fr ?? a.location.name ?? "", en: a.location.name_i18n?.en ?? a.location.name ?? "", ar: a.location.name_i18n?.ar ?? a.location.name ?? "" });

const haouz = recordedAnswers.find((a) => a.id === "event-haouz-flood-2026-10-10")!;

const panamaCase: CaseStudy = {
  id: "panama-2026",
  kind: "earthquake",
  status: "draft",
  title: { fr: "Séisme du Panama, 9 octobre 2026", en: "Panama earthquake, 9 October 2026", ar: "زلزال بنما، 9 أكتوبر 2026" },
  date: "2026-10-09",
  location: loc(panama, placeOf(panama)),
  headline: prose("panama.headline", "Le sol a bougé en ligne de visée sur la péninsule d'Azuero entre les deux passages qui encadrent le séisme.", "The ground moved along the line of sight on the Azuero peninsula between the two passes around the earthquake.", "تحرّكت الأرض في خط الرؤية في شبه جزيرة أزويرو بين المرورين المحيطين بالزلزال."),
  findings: [
    { id: "los_max", label: { fr: "Déplacement maximal en ligne de visée", en: "Maximum line-of-sight displacement", ar: "أقصى إزاحة في خط الرؤية" }, nisar: metric(panama, "los_displacement_max")!, reference: null, reference_source: null, agreement: "no_reference" },
    { id: "coh_loss", label: { fr: "Surface ayant perdu la cohérence", en: "Area that lost coherence", ar: "المساحة التي فقدت التماسك" }, nisar: metric(panama, "coherence_loss_area")!, reference: null, reference_source: null, agreement: "no_reference" },
  ],
  figures: panama.layers.map((layer) => ({ id: `fig-${layer.id}`, kind: "map" as const, title: { fr: layer.source, en: layer.source, ar: layer.source }, url: null, caption: prose("panama.fig", "Carte NISAR de l'événement.", "NISAR map of the event.", "خريطة NISAR للحدث."), layer })),
  exposure: null,
  timeline: [
    { label: { fr: "Dernier passage NISAR avant", en: "Last NISAR pass before", ar: "آخر مرور لـ NISAR قبل" }, at: panama.period.start },
    { label: { fr: "Séisme", en: "Earthquake", ar: "الزلزال" }, at: "2026-10-09" },
    { label: { fr: "Premier passage NISAR après", en: "First NISAR pass after", ar: "أول مرور لـ NISAR بعد" }, at: panama.period.end },
  ],
  answer_ids: [panama.id],
  limits: panama.limits,
};

const venezuelaCase: CaseStudy = {
  id: "venezuela-2026",
  kind: "earthquake",
  status: "draft",
  title: { fr: "Séismes du Venezuela, 24 juin 2026", en: "Venezuela earthquakes, 24 June 2026", ar: "زلازل فنزويلا، 24 يونيو 2026" },
  date: "2026-06-24",
  location: loc(venezuela, placeOf(venezuela)),
  headline: prose("venezuela.headline", "Le déplacement mesuré par NISAR est comparé à la carte publiée par la NASA.", "The displacement measured by NISAR is compared with the map published by NASA.", "تُقارَن الإزاحة التي قاسها NISAR بالخريطة التي نشرتها ناسا."),
  findings: [
    { id: "los_max", label: { fr: "Déplacement maximal en ligne de visée", en: "Maximum line-of-sight displacement", ar: "أقصى إزاحة في خط الرؤية" }, nisar: metric(venezuela, "los_displacement_max")!, reference: null, reference_source: { name: "NASA", url: null }, agreement: "no_reference" },
  ],
  figures: venezuela.layers.map((layer) => ({ id: `fig-${layer.id}`, kind: "map" as const, title: { fr: layer.source, en: layer.source, ar: layer.source }, url: null, caption: prose("venezuela.fig", "Carte NISAR de l'événement.", "NISAR map of the event.", "خريطة NISAR للحدث."), layer })),
  exposure: null,
  timeline: [
    { label: { fr: "Dernier passage NISAR avant", en: "Last NISAR pass before", ar: "آخر مرور لـ NISAR قبل" }, at: venezuela.period.start },
    { label: { fr: "Séismes", en: "Earthquakes", ar: "الزلازل" }, at: "2026-06-24" },
    { label: { fr: "Premier passage NISAR après", en: "First NISAR pass after", ar: "أول مرور لـ NISAR بعد" }, at: venezuela.period.end },
  ],
  answer_ids: [venezuela.id],
  limits: venezuela.limits,
};

const haouzCase: CaseStudy = {
  id: "haouz-flood-2026",
  kind: "flood",
  status: "draft",
  title: { fr: "Crue éclair d'Al Haouz, 10 octobre 2026", en: "Al Haouz flash flood, 10 October 2026", ar: "سيول الحوز، 10 أكتوبر 2026" },
  date: "2026-10-10",
  location: loc(haouz, placeOf(haouz)),
  headline: haouz.verdict,
  findings: (["coherence_loss_area"] as const)
    .map((id) => metric(haouz, id))
    .filter((m) => !!m)
    .map((m) => ({ id: "coh_loss", label: { fr: "Surface ayant perdu la cohérence (rayon de 5 km)", en: "Area that lost coherence (5 km radius)", ar: "المساحة التي فقدت التماسك (نصف قطر 5 كم)" }, nisar: m!, reference: null, reference_source: null, agreement: "no_reference" as const })),
  figures: [],
  exposure: null,
  timeline: [
    { label: { fr: "Passage NISAR avant", en: "NISAR pass before", ar: "مرور NISAR قبل" }, at: haouz.period.start },
    { label: { fr: "Crue", en: "Flood", ar: "السيل" }, at: "2026-10-10" },
    { label: { fr: "Passage NISAR après", en: "NISAR pass after", ar: "مرور NISAR بعد" }, at: haouz.period.end },
  ],
  answer_ids: [haouz.id],
  limits: haouz.limits,
};

const ionoCase: CaseStudy = {
  id: "ionosphere-gps",
  kind: "method",
  status: "draft",
  title: { fr: "Ionosphère et GPS : le radar tient-il face au sol ?", en: "Ionosphere and GPS: does the radar hold against the ground truth?", ar: "الأيونوسفير وGPS: هل يصمد الرادار أمام الحقيقة الأرضية؟" },
  date: "2026-11-14",
  location: { lat: 31.6, lon: -7.98, bbox: [-9.2, 30.6, -6.8, 32.6], place: { fr: "Stations GPS du Maroc", en: "Moroccan GPS stations", ar: "محطات GPS في المغرب" } },
  headline: prose("iono.headline", "Comparaison NISAR contre GPS, sans puis avec correction ionosphérique : calcul en cours.", "NISAR versus GPS, without then with the ionospheric correction: being computed.", "مقارنة NISAR مع GPS، دون تصحيح أيونوسفيري ثم معه: الحساب جارٍ."),
  findings: [],
  figures: [],
  exposure: null,
  timeline: [],
  answer_ids: [],
  limits: [prose("iono.limit", "Tant que la validation GPS n'est pas terminée, aucune valeur n'est affichée.", "Until the GPS validation is finished, no value is shown.", "لن تُعرض أي قيمة قبل انتهاء التحقق بـ GPS.")],
};

export const caseStudies: CaseStudy[] = [panamaCase, venezuelaCase, haouzCase, ionoCase];

export const caseSummaries: CaseSummary[] = caseStudies.map((c) => ({ id: c.id, kind: c.kind, title: c.title, date: c.date, status: c.status, thumbnail_url: null }));
