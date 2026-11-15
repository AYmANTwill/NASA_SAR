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

/**
 * The summaries have no map extent (API_REQUESTS.md #2), so each card also
 * reads its case; a case that fails its contract shows its own error.
 */
function CaseGrid({ list }: { list: CaseSummary[] }) {
  const details = useCaseStudies(list.map((c) => c.id));
  return (
    <ol className="case-grid">
      {list.map((summary, i) => (
        <li key={summary.id}>
          <CaseCard summary={summary} detail={details[i]} />
        </li>
      ))}
    </ol>
  );
}

function CaseCard({ summary, detail }: { summary: CaseSummary; detail: UseQueryResult<CaseStudy> | undefined }) {
  const { t, lang, text, localized } = useText();
  const study = detail?.data;

  return (
    <article className="case-card" aria-labelledby={`case-${summary.id}`}>
      <div className="case-card-map">{study ? <LocatorMap bbox={study.location.bbox} point={study.location} /> : null}</div>
      <div className="case-card-body">
        <p className="case-card-meta">
          <span>{t(`caseKind.${summary.kind}`)}</span>
          <time dateTime={summary.date}>{formatDate(summary.date, lang)}</time>
        </p>
        <h2 id={`case-${summary.id}`} className="case-card-title">
          <Link to={`/${lang}/cases/${summary.id}`}>{localized(summary.title)}</Link>
        </h2>
        {study && <p className="case-card-place">{localized(study.location.place)}</p>}
        {study && <p className="case-card-headline">{text(study.headline)}</p>}
        {detail?.isError && <ErrorPanel error={detail.error} onRetry={() => void detail.refetch()} />}
        <p className="case-card-status">
          <StatusTag status={summary.status} />
        </p>
      </div>
    </article>
  );
}
