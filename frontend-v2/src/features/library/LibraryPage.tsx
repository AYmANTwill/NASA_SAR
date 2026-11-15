import { Link } from "react-router-dom";
import type { LibraryEvent } from "@/api/contract";
import { useLibrary } from "@/api/queries";
import { useDocumentTitle } from "@/app/useDocumentTitle";
import { QueryView } from "@/components/QueryView";
import { ComparisonStrip, NisarGlyph, ReferenceGlyph } from "@/components/science/ComparisonStrip";
import { MeasurementView } from "@/components/science/MeasurementView";
import { formatDate, formatNumber } from "@/i18n/format";
import { useText } from "@/i18n/useText";
import { measurementState } from "@/science/measurement";
import "@/features/cases/CaseView.css";
import "@/features/cases/CasesPage.css";
import "@/features/investigate/investigate.css";
import "./LibraryPage.css";

export function LibraryPage() {
  const { t } = useText();
  useDocumentTitle(t("nav.library"));
  const library = useLibrary();
  return (
    <section className="page">
      <header className="cases-intro">
        <h1>{t("nav.library")}</h1>
        <p className="page-lede">{t("library.lede")}</p>
      </header>
      <QueryView query={library}>
        {(events) =>
          events.length === 0 ? (
            <p className="not-measured">{t("library.empty")}</p>
          ) : (
            <ol className="library-list">
              {events.map((event) => (
                <li key={event.id}>
                  <LibraryCard event={event} />
                </li>
              ))}
            </ol>
          )
        }
      </QueryView>
    </section>
  );
}

function LibraryCard({ event }: { event: LibraryEvent }) {
  const { t, lang, text } = useText();
  const name = event.location.name_i18n?.[lang] ?? event.location.name ?? event.id;
  const ref = event.reference;
  const comparison = ref.comparison;
  const both = comparison && measurementState(comparison.nisar, null) === "measured" && measurementState(comparison.reference, null) === "measured";

  return (
    <article className="library-card" aria-labelledby={`event-${event.id}`}>
      <p className="case-card-meta">
        <span>{t(`libraryKind.${event.kind}`)}</span>
        <time dateTime={event.date}>{formatDate(event.date, lang)}</time>
        {event.magnitude && (
          <span>
            <bdi dir="ltr">
              {event.magnitude.type} {formatNumber(event.magnitude.value, lang)}
            </bdi>{" "}
            <span className="measure-note">{t("measure.noSigma")}</span>
          </span>
        )}
      </p>
      <h2 id={`event-${event.id}`} className="case-card-title">
        {event.answer_id ? <Link to={`/${lang}/answers/${encodeURIComponent(event.answer_id)}`}>{name}</Link> : name}
      </h2>
      <div className="library-reference">
        <p className="evidence-head">
          <strong>{t(`source.${ref.source}`)}</strong>
          <span className="evidence-agreement">{t(`evidenceAgreement.${ref.agreement}`)}</span>
        </p>
        <p>{text(ref.summary)}</p>
        {comparison && (
          <div className="finding">
            <p className="finding-label">{t(`metric.${comparison.metric}`)}</p>
            <dl className="finding-rows">
              <div className="finding-row">
                <dt>
                  <NisarGlyph /> NISAR
                </dt>
                <dd>
                  <MeasurementView m={comparison.nisar} status={null} />
                </dd>
              </div>
              <div className="finding-row">
                <dt>
                  <ReferenceGlyph /> {t(`source.${ref.source}`)}
                </dt>
                <dd>
                  <MeasurementView m={comparison.reference} status={null} />
                </dd>
              </div>
            </dl>
            {both && <ComparisonStrip nisar={comparison.nisar} reference={comparison.reference} />}
          </div>
        )}
        {ref.url && (
          <a href={ref.url} target="_blank" rel="noreferrer">
            {t("answer.openSource")}
            <span className="visually-hidden"> {t("common.newTab")}</span>
          </a>
        )}
      </div>
      {!event.answer_id && <p className="not-measured">{t("library.noAnswer")}</p>}
    </article>
  );
}
