import { useState } from "react";
import type { CaseStudy } from "@/api/contract";
import { formatDate } from "@/i18n/format";
import { useText } from "@/i18n/useText";
import "./PassTimeline.css";

/**
 * The case's timeline under the map: one mark per item at its date (event,
 * NISAR acquisitions, ASF publication dates), and the same items as a list,
 * which is what screen readers get. Optional kinds separate the tracks;
 * dates without a kind keep their own unclassified track. Time runs left to right, like
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
  const kinds = ["event", "acquisition", "publication", "unspecified"] as const;
  const tracks = kinds.filter((kind) => items.some((item) => (item.kind ?? "unspecified") === kind));

  return (
    <section className="pass-timeline" aria-labelledby="timeline-title">
      <h2 id="timeline-title">{t("case.timeline")}</h2>
      <div className="pt-tracks" aria-hidden="true">
        {tracks.map((kind) => (
          <div key={kind} className="pt-track" data-kind={kind}>
            <span className="pt-track-label">{t(`timelineKind.${kind}`)}</span>
            <div className="pt-axis">
              {items.map((item, i) => (item.kind ?? "unspecified") === kind && (
                <span key={i} className={`pt-mark${hover === i ? " is-active" : ""}`} style={{ left: `${position(times[i]!)}%` }} />
              ))}
            </div>
          </div>
        ))}
      </div>
      <ol className="pt-list" tabIndex={0} aria-labelledby="timeline-title">
        {items.map((item, i) => (
          <li key={i} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
            <time dateTime={item.at}>{formatDate(item.at, lang)}</time>
            <span>
              {item.kind && <span className="pt-item-kind">{t(`timelineKind.${item.kind}`)} · </span>}
              {localized(item.label)}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
