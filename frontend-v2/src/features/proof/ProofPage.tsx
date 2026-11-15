import { useId } from "react";
import type { LbandProof } from "@/api/contract";
import { useLbandProof } from "@/api/queries";
import { useDocumentTitle } from "@/app/useDocumentTitle";
import { QueryView } from "@/components/QueryView";
import { MapPanel } from "@/components/map/MapPanel";
import { ComparisonStrip } from "@/components/science/ComparisonStrip";
import { MeasurementView } from "@/components/science/MeasurementView";
import { useText } from "@/i18n/useText";
import { formatDate, formatNumber } from "@/i18n/format";

export function ProofPage() {
  const { t } = useText();
  useDocumentTitle(t("nav.proof"));
  const query = useLbandProof();
  return <section className="page proof-page"><header className="cases-intro"><h1>{t("nav.proof")}</h1><p className="page-lede">{t("parity.proofIntro")}</p></header>
    <BandExplainer /><QueryView query={query}>{(proof) => <ProofBody proof={proof} />}</QueryView>
  </section>;
}

function BandExplainer() {
  const { t, lang } = useText();
  const id = useId();
  return <figure className="band-explainer"><figcaption><h2>{t("parity.whyRadar")}</h2><p>{t("parity.bandBody")}</p></figcaption>
    <svg viewBox="0 0 720 220" role="img" aria-labelledby={id} direction="ltr"><title id={id}>{t("parity.bandBody")}</title>
      <path d="M20 190H700" stroke="var(--ink-2)" strokeWidth="2" />
      {[70, 135, 200, 265, 330, 395, 460, 525, 590, 655].map((x) => <g key={x}><path d={`M${x} 110V190`} stroke="var(--coast)" strokeWidth="5" /><circle cx={x} cy="110" r="30" fill="var(--sea)" stroke="var(--coast)" /></g>)}
      <path d="M120 15L210 83L145 22" stroke="var(--ink-2)" strokeWidth="3" fill="none" strokeDasharray="5 5" />
      <path d="M450 15L550 184L480 22" stroke="var(--ink)" strokeWidth="4" fill="none" />
      <circle cx="120" cy="15" r="7" fill="var(--ink-2)" /><circle cx="450" cy="15" r="7" fill="var(--ink)" />
    </svg><div className="sensor-labels" dir="ltr"><p dir={lang === "ar" ? "rtl" : "ltr"}><bdi dir="ltr">{t("source.sentinel1")}</bdi> · {t("parity.cBand")}</p><p dir={lang === "ar" ? "rtl" : "ltr"}><bdi dir="ltr">NISAR</bdi> · {t("parity.lBand")}</p></div>
    <p className="source-line">{t("parity.schematic")}</p></figure>;
}

function ProofBody({ proof }: { proof: LbandProof }) {
  const { t, lang, text } = useText();
  return <><p className="headline">{text(proof.verdict)}</p><p>{proof.site.name_i18n?.[lang] ?? proof.site.name} · {formatDate(proof.period.start, lang)} – {formatDate(proof.period.end, lang)}</p>
    <div className="sensor-grid">{(["nisar", "sentinel1"] as const).map((sensor) => <section key={sensor} className="sensor-panel"><h2>{sensor === "nisar" ? "NISAR" : t("source.sentinel1")}</h2>
      <MeasurementView m={proof[sensor].coherence} status={null} /><MapPanel frame={proof[sensor].layer.bounds} entries={[{ layer: proof[sensor].layer }]} label={sensor === "nisar" ? "NISAR" : t("source.sentinel1")} />
    </section>)}</div>
    <section className="evidence-listing"><h2>{t("parity.forestComparison")}</h2><p className="source-line">{proof.forest_source}</p>
      <p>{t("parity.usableThreshold")} <bdi>{formatNumber(proof.usable_threshold, lang)}</bdi></p>
      {proof.bins.map((bin, i) => <article className="evidence-row forest-bin" key={i}><h3>{t("parity.forestCover")} <bdi>{formatNumber(bin.forest_cover.min, lang)} – {formatNumber(bin.forest_cover.max, lang)}</bdi> {t("unit.percent")}</h3>
        <ComparisonStrip nisar={bin.nisar} reference={bin.sentinel1} /><dl className="legend-facts"><dt>NISAR</dt><dd><MeasurementView m={bin.nisar} status={null} /></dd><dt>{t("source.sentinel1")}</dt><dd><MeasurementView m={bin.sentinel1} status={null} /></dd><dt>{t("parity.pixels")}</dt><dd><bdi>{formatNumber(bin.pixels, lang)}</bdi></dd></dl>
      </article>)}</section>
    <section className="limits"><h2>{t("case.limits")}</h2><ul>{proof.limits.map((limit, i) => <li key={i}>{text(limit)}</li>)}</ul></section>
  </>;
}
