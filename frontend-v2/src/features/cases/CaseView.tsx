import { Link, useParams } from "react-router-dom";
import type { CaseStudy } from "@/api/contract";
import { useCaseStudy } from "@/api/queries";
import { useDocumentTitle } from "@/app/useDocumentTitle";
import { MapPanel, type MapEntry } from "@/components/map/MapPanel";
import { QueryView } from "@/components/QueryView";
import { StatusTag } from "@/components/StatusTag";
import { formatDate } from "@/i18n/format";
import { useText } from "@/i18n/useText";
import { ExposureView, FigureList, FindingView, LimitsView, SourcesView } from "./ledger";
import { PassTimeline } from "./PassTimeline";
import "./CaseView.css";

export function CaseView() {
  const { id = "" } = useParams();
  const { t, lang } = useText();
  const query = useCaseStudy(id);
  useDocumentTitle(t("nav.cases"));

  return (
    <div className="case-view">
      <p className="case-back">
        <Link to={`/${lang}/`}>{t("case.back")}</Link>
      </p>
      <QueryView query={query}>{(study) => <CaseBody study={study} />}</QueryView>
    </div>
  );
}

function CaseBody({ study }: { study: CaseStudy }) {
  const { t, lang, text, localized } = useText();
  const draft = study.status === "draft";
  useDocumentTitle(`${draft ? `[${t("caseStatus.draft")}] ` : ""}${localized(study.title)}`);
  // Figures with a raster layer go on the map; the others (charts, images) stay in the ledger.
  const mapEntries: MapEntry[] = study.figures.flatMap((f) => (f.layer ? [{ layer: f.layer, title: f.title, caption: f.caption }] : []));
  const otherFigures = study.figures.filter((f) => !f.layer);

  return (
    <article className="case" aria-labelledby="case-title">
      {draft && (
        <p className="draft-band" role="note">
          <strong>{t("caseStatus.draft")}</strong> {t("case.draftBand")}
        </p>
      )}

      <header className="case-header">
        <p className="case-meta">
          <span>{t(`caseKind.${study.kind}`)}</span>
          <time dateTime={study.date}>{formatDate(study.date, lang)}</time>
          <span>{localized(study.location.place)}</span>
        </p>
        <h1 id="case-title">{localized(study.title)}</h1>
        <StatusTag status={study.status} />
      </header>

      <div className="case-layout">
        <div className="case-map-column">
          <MapPanel frame={study.location.bbox} point={study.location} entries={mapEntries} label={t("case.mapLabel", { place: localized(study.location.place) })} />
          <PassTimeline study={study} />
        </div>

        <div className="ledger">
          <p className="headline">{text(study.headline)}</p>

          <section className="ledger-section" aria-labelledby="findings-title">
            <h2 id="findings-title">{t("case.findings")}</h2>
            {study.findings.length === 0 ? (
              <p className="not-measured">{t("case.findingsNone")}</p>
            ) : (
              study.findings.map((f) => <FindingView key={f.id} finding={f} status={study.status} />)
            )}
          </section>

          <section className="ledger-section" aria-labelledby="exposure-title">
            <h2 id="exposure-title">{t("case.exposureTitle")}</h2>
            <ExposureView exposure={study.exposure} status={study.status} />
          </section>

          <section className="ledger-section" aria-labelledby="figures-title">
            <h2 id="figures-title">{t("case.figures")}</h2>
            <FigureList figures={otherFigures} />
          </section>

          <LimitsView study={study} />

          <section className="ledger-section" aria-labelledby="sources-title">
            <h2 id="sources-title">{t("case.sources")}</h2>
            <SourcesView study={study} />
          </section>
        </div>
      </div>
    </article>
  );
}
