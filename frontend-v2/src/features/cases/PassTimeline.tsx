import { useState } from "react";
import type { CaseStudy } from "@/api/contract";
import { formatDate } from "@/i18n/format";
import { useText } from "@/i18n/useText";
import "./PassTimeline.css";

/**
 * The case's timeline under the map: one mark per item at its date (event,
 * NISAR acquisitions, ASF publication dates), and the same items as a list,
 * which is what screen readers get. Items are not typed by the API yet
 * (API_REQUESTS.md #3), so they share one row. Time runs left to right, like
 * the map and the charts. Mark positions are layout only; only the API's dates
 * are written.
 */
export function PassTimeline({ study }: { study: CaseStudy }) {
  const { t, lang, localized } = useText();
  const [hover, setHover] = useState<number | null>(null);
  const items = study.timeline;

  if (items.length === 0) {
    return (
      <section className="pass-timeline" aria-labelledby="timeline-title">
        <h2 id="timeline-title">{t("case.timeline")}</h2>
        <p className="not-measured">{t("case.timelineNone")}</p>
      </section>
    );
  }

  const times = items.map((item) => Date.parse(item.at));
  const first = Math.min(...times);
  const last = Math.max(...times);
  const position = (time: number) => (last === first ? 50 : 4 + ((time - first) / (last - first)) * 92);

  return (
    <section className="pass-timeline" aria-labelledby="timeline-title">
      <h2 id="timeline-title">{t("case.timeline")}</h2>
      <div className="pt-axis" aria-hidden="true">
        {times.map((time, i) => (
          <span key={i} className={`pt-mark${hover === i ? " is-active" : ""}`} style={{ left: `${position(time)}%` }} />
        ))}
      </div>
      <ol className="pt-list">
        {items.map((item, i) => (
          <li key={i} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
            <time dateTime={item.at}>{formatDate(item.at, lang)}</time>
            <span>{localized(item.label)}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
