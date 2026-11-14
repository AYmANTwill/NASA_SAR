import type { CaseExposure, CaseStatus, CaseStudy, Figure, Finding } from "@/api/contract";
import { AgreementMark } from "@/components/science/AgreementMark";
import { ComparisonStrip, NisarGlyph, ReferenceGlyph } from "@/components/science/ComparisonStrip";
import { MeasurementView } from "@/components/science/MeasurementView";
import { useText } from "@/i18n/useText";
import { measurementState } from "@/science/measurement";

/** One finding: NISAR's value, the reference's, the strip when both are measured, the API's agreement. */
export function FindingView({ finding, status }: { finding: Finding; status: CaseStatus }) {
  const { t, localized } = useText();
  const nisarState = measurementState(finding.nisar, status);
  const reference = finding.reference;
  const source = finding.reference_source;
  const bothMeasured = nisarState !== "placeholder" && reference !== null && measurementState(reference, status) !== "placeholder";
  // A placeholder has no agreement worth showing (Panama's placeholder Mw "disagrees" with USGS, API_REQUESTS.md #1).
  const agreement = nisarState === "placeholder" && reference !== null ? "pending" : finding.agreement;

  return (
    <article className="finding" aria-labelledby={`finding-${finding.id}`}>
      <h3 id={`finding-${finding.id}`} className="finding-label">
        {localized(finding.label)}
      </h3>
      <dl className="finding-rows">
        <div className="finding-row">
          <dt>
            <NisarGlyph /> NISAR
          </dt>
          <dd>
            <MeasurementView m={finding.nisar} status={status} />
          </dd>
        </div>
        {reference && source && (
          <div className="finding-row">
            <dt>
              <ReferenceGlyph />{" "}
              <a href={source.url} target="_blank" rel="noreferrer" dir="auto">
                {source.name}
                <span className="visually-hidden"> {t("common.newTab")}</span>
              </a>
            </dt>
            <dd>
              <MeasurementView m={reference} status={status} />
            </dd>
          </div>
        )}
      </dl>
      {bothMeasured && reference && <ComparisonStrip nisar={finding.nisar} reference={reference} />}
      <p className="finding-agreement">
        <AgreementMark agreement={agreement} />
      </p>
    </article>
  );
}

export function ExposureView({ exposure, status }: { exposure: CaseExposure | null; status: CaseStatus }) {
  const { t } = useText();
  if (!exposure) return <p className="not-measured">{t("case.exposureNone")}</p>;
  const rows = [
    ["people", exposure.people],
    ["buildings", exposure.buildings],
    ["area", exposure.area_km2],
  ] as const;
  return (
    <>
      <table className="exposure">
        <tbody>
          {rows.map(([key, m]) => (
            <tr key={key}>
              <th scope="row">{t(`case.exposure.${key}`)}</th>
              <td>
                <MeasurementView m={m} status={status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="source-line">
        {t("case.source")}{" "}
        <a href={exposure.source.url} target="_blank" rel="noreferrer" dir="auto">
          {exposure.source.name}
          <span className="visually-hidden"> {t("common.newTab")}</span>
        </a>
      </p>
    </>
  );
}

export function FigureList({ figures }: { figures: Figure[] }) {
  const { t, text, localized } = useText();
  if (figures.length === 0) return <p className="not-measured">{t("case.figuresNone")}</p>;
  return (
    <div className="figure-list">
      {figures.map((f) => (
        <figure key={f.id} className="figure">
          <img src={f.url} alt={localized(f.title)} loading="lazy" />
          <figcaption>
            <strong>{localized(f.title)}</strong> {text(f.caption)}
          </figcaption>
        </figure>
      ))}
    </div>
  );
}

/** "What the radar cannot tell here": always rendered, never collapsible. */
export function LimitsView({ study }: { study: CaseStudy }) {
  const { t, text } = useText();
  return (
    <section className="ledger-section limits" aria-labelledby="limits-title">
      <h2 id="limits-title">{t("case.limits")}</h2>
      <ul>
        {study.limits.map((limit, i) => (
          <li key={i}>{text(limit)}</li>
        ))}
      </ul>
    </section>
  );
}

/** Every source the case cites, once. */
export function SourcesView({ study }: { study: CaseStudy }) {
  const { t } = useText();
  const sources = new Map<string, string>();
  for (const f of study.findings) if (f.reference_source) sources.set(f.reference_source.url, f.reference_source.name);
  if (study.exposure) sources.set(study.exposure.source.url, study.exposure.source.name);
  if (sources.size === 0) return <p className="not-measured">{t("case.sourcesNone")}</p>;
  return (
    <ul className="sources">
      {[...sources].map(([url, name]) => (
        <li key={url}>
          <a href={url} target="_blank" rel="noreferrer" dir="auto">
            {name}
            <span className="visually-hidden"> {t("common.newTab")}</span>
          </a>
        </li>
      ))}
    </ul>
  );
}
