import { Link } from "react-router-dom";
import type { Answer, Bounds, Confidence } from "@/api/contract";
import { MapPanel } from "@/components/map/MapPanel";
import { MeasurementView } from "@/components/science/MeasurementView";
import { SeriesChart } from "@/components/science/SeriesChart";
import { formatDate, formatNumber } from "@/i18n/format";
import { useText } from "@/i18n/useText";
import { StepList } from "./StepList";
import "@/features/cases/CaseView.css";
import "./investigate.css";

/** Half-size of the frame drawn around a point when the answer has neither a bbox nor a layer (display only). */
const POINT_FRAME_DEG = 1.5;

/** The area the map frames: the API's bbox, else its layers' bounds, else a small box around its point. */
export function answerFrame(answer: Answer): Bounds {
  if (answer.location.bbox) return answer.location.bbox;
  if (answer.layers.length > 0) {
    const b = answer.layers.map((l) => l.bounds);
    return [Math.min(...b.map((x) => x[0])), Math.min(...b.map((x) => x[1])), Math.max(...b.map((x) => x[2])), Math.max(...b.map((x) => x[3]))];
  }
  const { lat, lon } = answer.location;
  return [lon - POINT_FRAME_DEG, lat - POINT_FRAME_DEG, lon + POINT_FRAME_DEG, lat + POINT_FRAME_DEG];
}

function ConfidenceMark({ confidence }: { confidence: Confidence }) {
  const { t } = useText();
  const filled = { low: 1, medium: 2, high: 3 }[confidence];
  return (
    <span className="confidence">
      <svg className="confidence-icon" viewBox="0 0 24 12" aria-hidden="true" focusable="false">
        {[0, 1, 2].map((i) => (
          <rect key={i} x={i * 8 + 1} y={1} width={6} height={10} className={i < filled ? "on" : "off"} />
        ))}
      </svg>
      {t("answer.confidence", { level: t(`confidenceLevel.${confidence}`) })}
    </span>
  );
}

/** One answer of the investigator: map and evidence ledger, in the same reading order as a case. */
export function AnswerView({ answer, showSteps = true }: { answer: Answer; showSteps?: boolean }) {
  const { t, lang, text } = useText();
  const place = answer.location.name_i18n?.[lang] ?? answer.location.name ?? "";

  return (
    <article className="answer" aria-labelledby={`answer-${answer.id}`}>
      <div className="case-layout">
        <div className="case-map-column">
          <MapPanel
            frame={answerFrame(answer)}
            point={answer.location}
            entries={answer.layers.map((layer) => ({ layer }))}
            label={t("case.mapLabel", { place: place || t("answer.thePoint") })}
            // A rectangle only for an area the API gave (bbox or layers), never for the box drawn around a point.
            showArea={answer.location.bbox != null || answer.layers.length > 0}
            emptyText={t("answer.noRaster")}
          />
          {showSteps && answer.steps.length > 0 && (
            <section className="steps-panel" aria-labelledby="steps-title">
              <h2 id="steps-title">{t("answer.steps")}</h2>
              <StepList steps={answer.steps} live={false} />
            </section>
          )}
        </div>

        <div className="ledger">
          <header className="answer-head">
            <p className="answer-question" dir="auto">
              <q>{answer.question}</q>
            </p>
            {place && <p className="answer-place">{place}</p>}
          </header>
          <p id={`answer-${answer.id}`} className="headline">
            {text(answer.verdict)}
          </p>
          <p className="answer-tags">
            <ConfidenceMark confidence={answer.confidence} />
            {answer.stable_in_noise && <span className="tag">{t("answer.stableInNoise")}</span>}
            <span className="tag">{t(`productStatus.${answer.product_status}`)}</span>
          </p>

          {answer.metrics.length > 0 && (
            <section className="ledger-section" aria-labelledby="metrics-title">
              <h2 id="metrics-title">{t("answer.metrics")}</h2>
              <dl className="metric-list">
                {answer.metrics.map((m) => (
                  <div key={m.id} className="finding-row">
                    <dt>{t(`metric.${m.id}`)}</dt>
                    <dd>
                      <MeasurementView m={m.measurement} status={null} />
                    </dd>
                  </div>
                ))}
              </dl>
            </section>
          )}

          {answer.series.length > 0 && (
            <section className="ledger-section" aria-labelledby="series-title">
              <h2 id="series-title">{t("answer.series")}</h2>
              {answer.series.map((s) => (
                <SeriesChart key={s.id} series={s} />
              ))}
            </section>
          )}

          {answer.indication && (
            <section className="ledger-section" aria-labelledby="indication-title">
              <h2 id="indication-title">{t("answer.indication")}</h2>
              <p>
                {formatDate(answer.indication.window.start, lang)} → {formatDate(answer.indication.window.end, lang)}
              </p>
              <p className="measure-note">{text(answer.indication.caveat)}</p>
            </section>
          )}

          <section className="ledger-section" aria-labelledby="checks-title">
            <h2 id="checks-title">{t("answer.checks")}</h2>
            {answer.checks.length === 0 ? (
              <p className="not-measured">{t("answer.checksNone")}</p>
            ) : (
              <ul className="check-list">
                {answer.checks.map((c) => (
                  <li key={c.id} className={`check check-${c.status}`}>
                    <span className="check-status">{t(`checkStatus.${c.status}`)}</span>
                    <span className="check-name">{t(`check.${c.id}`)}</span>
                    {c.measurement && <MeasurementView m={c.measurement} status={null} />}
                    {c.detail && <span className="check-detail">{text(c.detail)}</span>}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="ledger-section" aria-labelledby="evidence-title">
            <h2 id="evidence-title">{t("answer.evidence")}</h2>
            {answer.evidence.length === 0 ? (
              <p className="not-measured">{t("answer.evidenceNone")}</p>
            ) : (
              <ul className="evidence-list">
                {answer.evidence.map((e, i) => (
                  <li key={i}>
                    <p className="evidence-head">
                      <strong>{t(`source.${e.source}`)}</strong>
                      <span className={`evidence-agreement evidence-${e.agreement}`}>{t(`evidenceAgreement.${e.agreement}`)}</span>
                    </p>
                    <p>{text(e.summary)}</p>
                    {e.url && (
                      <a href={e.url} target="_blank" rel="noreferrer">
                        {t("answer.openSource")}
                        <span className="visually-hidden"> {t("common.newTab")}</span>
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>

          {answer.earthquakes.length > 0 && (
            <section className="ledger-section" aria-labelledby="quakes-title">
              <h2 id="quakes-title">{t("answer.earthquakes")}</h2>
              <ul className="evidence-list">
                {answer.earthquakes.map((q) => (
                  <li key={q.id}>
                    <strong>
                      <bdi dir="ltr">
                        {q.magnitude.type} {formatNumber(q.magnitude.value, lang)}
                        {q.magnitude.uncertainty !== null && ` ± ${formatNumber(q.magnitude.uncertainty, lang)}`}
                      </bdi>
                    </strong>{" "}
                    {q.magnitude.uncertainty === null && <span className="measure-note">{t("measure.noSigma")} </span>}
                    {t(`quakeRole.${q.role}`)}, {formatDate(q.time, lang)}
                    {q.url && (
                      <>
                        {" "}
                        <a href={q.url} target="_blank" rel="noreferrer">
                          USGS<span className="visually-hidden"> {t("common.newTab")}</span>
                        </a>
                      </>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className="ledger-section limits" aria-labelledby={`limits-${answer.id}`}>
            <h2 id={`limits-${answer.id}`}>{t("case.limits")}</h2>
            <ul>
              {answer.limits.map((limit, i) => (
                <li key={i}>{text(limit)}</li>
              ))}
            </ul>
          </section>

          <section className="ledger-section" aria-labelledby="data-title">
            <h2 id="data-title">{t("answer.data")}</h2>
            <dl className="legend-facts">
              <dt>{t("answer.product")}</dt>
              <dd>
                NISAR {answer.product} ({t(`productStatus.${answer.product_status}`)})
              </dd>
              <dt>{t("legend.period")}</dt>
              <dd>
                {formatDate(answer.period.start, lang)} → {formatDate(answer.period.end, lang)}
              </dd>
              <dt>{t("answer.acquisitions")}</dt>
              <dd>{answer.acquisitions.length === 0 ? t("answer.none") : answer.acquisitions.map((d) => formatDate(d, lang)).join(" · ")}</dd>
              <dt>{t("answer.tracks")}</dt>
              <dd>
                {answer.tracks.length === 0
                  ? t("answer.none")
                  : answer.tracks.map((tr) => t("answer.track", { number: formatNumber(tr.number, lang), direction: t(`direction.${tr.direction}`) })).join(" · ")}
              </dd>
              {answer.next_pass && (
                <>
                  <dt>{t("answer.nextPass")}</dt>
                  <dd>{formatDate(answer.next_pass, lang)}</dd>
                </>
              )}
              <dt>{t("answer.permalink")}</dt>
              <dd>
                <Link to={`/${lang}/answers/${encodeURIComponent(answer.id)}`}>
                  <code dir="ltr">{answer.id}</code>
                </Link>
                {answer.cached && <span className="measure-note"> {t("answer.cached")}</span>}
              </dd>
            </dl>
          </section>
        </div>
      </div>
    </article>
  );
}
