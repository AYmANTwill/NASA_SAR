import type { UseQueryResult } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import type { CaseStudy, CaseSummary } from "@/api/contract";
import { useCaseStudies, useCases } from "@/api/queries";
import { useDocumentTitle } from "@/app/useDocumentTitle";
import { ErrorPanel } from "@/components/ErrorPanel";
import { LocatorMap } from "@/components/map/LocatorMap";
import { QueryView } from "@/components/QueryView";
import { StatusTag } from "@/components/StatusTag";
import { formatDate } from "@/i18n/format";
import { useText } from "@/i18n/useText";
import "./CasesPage.css";

export function CasesPage() {
  const { t } = useText();
  useDocumentTitle(t("nav.cases"));
  const cases = useCases();

  return (
    <section className="page cases-page">
      <header className="cases-intro">
        <h1>{t("nav.cases")}</h1>
        <p className="page-lede">{t("cases.lede")}</p>
      </header>
      <QueryView query={cases}>
        {(list) => (
          <>
            <ReadyCase list={list} />
            {list.some((c) => c.status === "draft") && (
              <p className="cases-draft-note" role="note">
                {t("cases.draftNote")}
              </p>
            )}
            <CaseGrid list={list} />
          </>
        )}
      </QueryView>
    </section>
  );
}

function ReadyCase({ list }: { list: CaseSummary[] }) {
  const { t, lang, localized } = useText();
  const ready = list.find((study) => study.status === "final");
  return ready ? <p className="cases-ready"><Link className="button button-primary" to={`/${lang}/cases/${ready.id}`}>{t("cases.openReady")}</Link><span>{localized(ready.title)}</span></p> : null;
}

/** Older APIs need a case read for the map extent or place. Complete summaries stand alone. */
function CaseGrid({ list }: { list: CaseSummary[] }) {
  const missing = list.filter((c) => !c.bbox || !c.place);
  const details = useCaseStudies(missing.map((c) => c.id));
  const byId = new Map(missing.map((c, i) => [c.id, details[i]]));
  return (
    <ol className="case-grid">
      {list.map((summary) => (
        <li key={summary.id}>
          <CaseCard summary={summary} detail={byId.get(summary.id)} />
        </li>
      ))}
    </ol>
  );
}

function CaseCard({ summary, detail }: { summary: CaseSummary; detail: UseQueryResult<CaseStudy> | undefined }) {
  const { t, lang, text, localized } = useText();
  const study = detail?.data;
  const bbox = summary.bbox ?? study?.location.bbox;
  const place = summary.place ?? study?.location.place;

  return (
    <article className="case-card" aria-labelledby={`case-${summary.id}`}>
      <div className="case-card-map">{bbox && <LocatorMap bbox={bbox} point={study?.location} />}</div>
      <div className="case-card-body">
        <p className="case-card-meta">
          <span>{t(`caseKind.${summary.kind}`)}</span>
          <time dateTime={summary.date}>{formatDate(summary.date, lang)}</time>
        </p>
        <h2 id={`case-${summary.id}`} className="case-card-title">
          <Link to={`/${lang}/cases/${summary.id}`}>{localized(summary.title)}</Link>
        </h2>
        {place && <p className="case-card-place">{localized(place)}</p>}
        {study && <p className="case-card-headline">{text(study.headline)}</p>}
        {detail?.isError && <ErrorPanel error={detail.error} onRetry={() => void detail.refetch()} />}
        <p className="case-card-status">
          <StatusTag status={summary.status} />
        </p>
      </div>
    </article>
  );
}
