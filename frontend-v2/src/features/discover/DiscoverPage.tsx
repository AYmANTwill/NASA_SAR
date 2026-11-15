import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { FormEvent } from "react";
import type { Bounds, Discoveries } from "@/api/contract";
import { ApiError } from "@/api/errors";
import { useDiscoveries, useLibrary } from "@/api/queries";
import { useDocumentTitle } from "@/app/useDocumentTitle";
import { ErrorPanel } from "@/components/ErrorPanel";
import { QueryView } from "@/components/QueryView";
import { MapPanel } from "@/components/map/MapPanel";
import { MeasurementView } from "@/components/science/MeasurementView";
import { NoiseRuler } from "@/components/science/NoiseRuler";
import { useText } from "@/i18n/useText";
import { formatDate, formatNumber } from "@/i18n/format";
import type { MapMarker } from "@/components/map/RadarMap";

const MOROCCO: Bounds = [-14, 27, -1, 37];
export function markerBounds(markers: { lon: number; lat: number }[]): Bounds {
  return markers.length ? [Math.min(...markers.map((p) => p.lon)) - 1, Math.min(...markers.map((p) => p.lat)) - 1,
    Math.max(...markers.map((p) => p.lon)) + 1, Math.max(...markers.map((p) => p.lat)) + 1] : MOROCCO;
}

export function DiscoverPage() {
  const { t, lang } = useText();
  useDocumentTitle(t("nav.discover"));
  const query = useDiscoveries("MA");
  const disabled = query.error instanceof ApiError && query.error.code === "discoveries_disabled";
  return <section className="page explore-page">
    <header className="cases-intro"><h1>{t("nav.discover")}</h1><p className="page-lede">{t("parity.discoverIntro")}</p></header>
    <QuickAsk />
    {disabled ? <><ErrorPanel error={query.error} /><ObservedPlaces /></> : <QueryView query={query}>{(data) => <Candidates data={data} />}</QueryView>}
    <p><Link className="button button-primary" to={`/${lang}/ask`}>{t("ask.submit")}</Link></p>
  </section>;
}

function QuickAsk() {
  const { t, lang } = useText();
  const navigate = useNavigate();
  const [question, setQuestion] = useState("");
  const submit = (event: FormEvent) => { event.preventDefault(); if (question.trim()) navigate(`/${lang}/ask?${new URLSearchParams({ q: question.trim(), auto: "1" })}`); };
  return <form className="quick-ask" onSubmit={submit}><input aria-label={t("ask.label")} placeholder={t("ask.placeholder")} value={question} dir="auto" onChange={(event) => setQuestion(event.target.value)} /><button className="button button-primary" disabled={!question.trim()}>{t("ask.submit")}</button></form>;
}

function ObservedPlaces() {
  const { t, lang, text } = useText();
  const library = useLibrary();
  return <QueryView query={library}>{(events) => {
    const markers: MapMarker[] = events.map((e) => ({ id: e.id, ...e.location, title: e.location.name_i18n?.[lang] ?? e.location.name ?? e.id,
      href: e.answer_id ? `/${lang}/answers/${encodeURIComponent(e.answer_id)}` : `/${lang}/library` }));
    return <div className="explore-layout"><div className="evidence-listing"><h2>{t("parity.observed")}</h2>
      {events.length === 0 && <p>{t("library.empty")}</p>}
      {[...events].sort((a, b) => b.date.localeCompare(a.date)).map((event) => <article key={event.id} className="evidence-row"><time dateTime={event.date}>{formatDate(event.date, lang)}</time>
        <h3><Link to={markers.find((m) => m.id === event.id)!.href!}>{event.location.name_i18n?.[lang] ?? event.location.name ?? event.id}</Link></h3>
        <p>{text(event.reference.summary)}</p></article>)}</div>
      <MapPanel frame={markerBounds(markers)} entries={[]} markers={markers} showArea={false} label={t("parity.observed")} emptyText={t("parity.observedHelp")} />
    </div>;
  }}</QueryView>;
}

function Candidates({ data }: { data: Discoveries }) {
  const { t, lang } = useText();
  const [sort, setSort] = useState("rank");
  const zones = [...data.zones].sort((a, b) => sort === "rank" ? a.rank - b.rank : b.exposure_score - a.exposure_score);
  const markers: MapMarker[] = zones.map((z) => ({ id: z.id, ...z.location, title: z.location.name_i18n?.[lang] ?? z.location.name ?? z.id,
    href: z.answer_id ? `/${lang}/answers/${encodeURIComponent(z.answer_id)}` : `/${lang}/ask?${new URLSearchParams({ q: t("parity.zoneQuestion"), lat: String(z.location.lat), lon: String(z.location.lon), auto: "1" })}` }));
  return <><p className="source-line">{data.region_name[lang]} · {formatDate(data.period.start, lang)} – {formatDate(data.period.end, lang)}</p>
    <p className="source-line">{t("parity.generatedAt")} <time dateTime={data.generated_at}>{formatDate(data.generated_at, lang)}</time></p>
    <p>{t("metric.noise_floor")} <MeasurementView m={data.noise_floor} status={null} /> · {t("parity.thresholdFactor")} <bdi>{formatNumber(data.threshold_factor, lang)}</bdi></p>
    <p className="case-interpretation">{t("parity.candidateNote")}</p>
    <div className="explore-layout"><div className="evidence-listing">
      <label className="control-label">{t("parity.sort")}<select value={sort} onChange={(e) => setSort(e.target.value)}><option value="rank">{t("parity.bySignal")}</option><option value="exposure">{t("case.exposureTitle")}</option></select></label>
      {zones.length === 0 && <p className="empty-panel">{t("parity.noCandidates")}</p>}
      {zones.map((z) => <article key={z.id} className="evidence-row"><p className="source-line">{t(`confidenceLevel.${z.confidence}`)} · {z.manually_checked ? t("parity.checked") : t("parity.unchecked")}</p>
        <h2><Link to={markers.find((m) => m.id === z.id)!.href!}>{z.location.name_i18n?.[lang] ?? z.location.name ?? z.id}</Link></h2>
        <p>{t(z.velocity.unit.includes("/yr") ? "metric.velocity" : "parity.displacement")} <MeasurementView m={z.velocity} status={null} /></p>
        <NoiseRuler measurement={z.velocity} noise={data.noise_floor.value * data.threshold_factor} />
        <p className="source-line">{t("parity.snr")} <bdi>{formatNumber(z.snr, lang)}</bdi></p>
        <dl className="legend-facts">{Object.entries(z.exposure).map(([key, value]) => <div className="finding-row" key={key}><dt>{t(`parity.exposure.${key}`)}</dt><dd>{value === null ? t("parity.unknown") : <bdi>{formatNumber(value, lang)}</bdi>}</dd></div>)}</dl>
        {z.vertical && <p>{t("seriesId.vertical")} <MeasurementView m={z.vertical} status={null} /></p>}
        {z.east_west && <p>{t("seriesId.east_west")} <MeasurementView m={z.east_west} status={null} /></p>}
      </article>)}</div><MapPanel frame={markerBounds(markers)} entries={[]} markers={markers} showArea={false} label={t("nav.discover")} emptyText={t("parity.candidateNote")} /></div>
  </>;
}
