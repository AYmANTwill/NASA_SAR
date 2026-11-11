import type { ReactNode } from "react";
import { CircleCheck, CircleSlash, CircleHelp, CircleX, Hourglass, MinusCircle, ShieldQuestion, TriangleAlert } from "lucide-react";
import type { Answer, Check, Evidence, Metric, Series } from "@/api/contract";
import { ConfidenceBadge } from "@/components/science/badges";
import { MeasurementText } from "@/components/science/MeasurementText";
import { NoiseRuler } from "@/components/science/NoiseRuler";
import { TimeSeriesChart } from "@/components/science/TimeSeriesChart";
import { useText } from "@/i18n/useText";
import { formatDate, formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";
import { WatchAction } from "./WatchAction";

function Section({ title, children, id }: { title: string; children: ReactNode; id: string }) {
  return (
    <section aria-labelledby={id} className="space-y-2.5 border-t border-line pt-4">
      <h3 id={id} className="text-sm font-semibold text-ink-2">
        {title}
      </h3>
      {children}
    </section>
  );
}

export function AnswerView({ answer }: { answer: Answer }) {
  const { t, text } = useText();
  const noise = answer.metrics.find((m) => m.id === "noise_floor")?.measurement ?? null;
  const shown = answer.metrics.filter((m) => m.id !== "noise_floor");
  const components = answer.series.filter((s) => s.id === "vertical" || s.id === "east_west");
  const others = answer.series.filter((s) => s.id !== "vertical" && s.id !== "east_west");

  return (
    <article aria-labelledby="verdict" className="space-y-4">
      <header className="space-y-3">
        <p className="text-xs font-medium text-muted">{t("answer.verdict")}</p>
        <h2 id="verdict" tabIndex={-1} className="outline-none text-xl leading-snug font-semibold text-balance">
          {text(answer.verdict)}
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          <ConfidenceBadge level={answer.confidence} />
          {answer.stable_in_noise && (
            <span className="inline-flex items-center gap-1.5 rounded-sm border border-ink px-2 py-0.5 text-sm font-medium">
              <CircleSlash className="size-3.5" aria-hidden />
              {t("answer.stable")}
            </span>
          )}
          <span className="text-xs text-muted">{answer.cached ? t("answer.cached") : t("answer.live")}</span>
        </div>
        {answer.stable_in_noise && <p className="text-sm text-ink-2">{t("answer.stableNote")}</p>}
      </header>

      {shown.length > 0 && (
        <Section id="metrics" title={t("answer.metrics")}>
          <dl className="grid gap-3 sm:grid-cols-2">
            {shown.map((metric) => (
              <MetricItem key={metric.id} metric={metric} noise={noise && noise.unit === metric.measurement.unit ? noise.value : null} />
            ))}
            {noise && <MetricItem metric={{ id: "noise_floor", measurement: noise }} noise={null} />}
          </dl>
        </Section>
      )}

      {components.length > 0 && (
        <Section id="components" title={t("answer.components")}>
          <SmallMultiples series={components} />
        </Section>
      )}

      {others.length > 0 && (
        <Section id="series" title={t("answer.series")}>
          {others.map((s) => (
            <TimeSeriesChart key={s.id} series={s} title={t(`series.${s.id}`)} />
          ))}
        </Section>
      )}

      {answer.indication && (
        <Section id="indication" title={t("answer.indication")}>
          <div className="flex gap-3 rounded-md border border-dashed border-ink-2 p-3">
            <Hourglass className="mt-0.5 size-4 shrink-0" aria-hidden />
            <div className="space-y-1">
              <IndicationWindow start={answer.indication.window.start} end={answer.indication.window.end} />
              <p className="text-sm text-ink-2">{text(answer.indication.caveat)}</p>
            </div>
          </div>
        </Section>
      )}

      {answer.classifier && (
        <Section id="classifier" title={t("answer.classifier")}>
          <p>
            <span className="font-medium">{t(`answer.classLabel.${answer.classifier.label}`)}</span>
          </p>
          <ClassifierScores c={answer.classifier} />
        </Section>
      )}

      <Section id="checks" title={t("answer.checks")}>
        <ul className="space-y-2">
          {answer.checks.map((c) => (
            <CheckItem key={c.id} check={c} />
          ))}
        </ul>
      </Section>

      <Section id="evidence" title={t("answer.evidence")}>
        {answer.evidence.length === 0 ? (
          <p className="text-sm text-ink-2">{t("answer.noEvidence")}</p>
        ) : (
          <ul className="space-y-2">
            {answer.evidence.map((e, i) => (
              <EvidenceItem key={e.source + i} evidence={e} />
            ))}
          </ul>
        )}
      </Section>

      <Section id="details" title={t("answer.details")}>
        <Details answer={answer} />
      </Section>

      <div className="border-t border-line pt-4">
        <WatchAction answer={answer} />
      </div>

      {/* Always last: what the radar cannot tell. */}
      <section aria-labelledby="limits" className="space-y-2 rounded-md bg-ink p-4 text-white">
        <h3 id="limits" className="flex items-center gap-2 font-semibold">
          <ShieldQuestion className="size-4" aria-hidden />
          {t("answer.limits")}
        </h3>
        <ul className="list-disc space-y-1 ps-5 text-sm text-white/90">
          {answer.limits.map((l, i) => (
            <li key={l.template + i}>{text(l)}</li>
          ))}
        </ul>
      </section>
    </article>
  );
}

function MetricItem({ metric, noise }: { metric: Metric; noise: number | null }) {
  const { t } = useText();
  const label = t(`metric.${metric.id}`);
  return (
    <div className="space-y-1 rounded-md border border-line bg-surface p-3">
      <dt className="text-xs text-ink-2">{label}</dt>
      <dd className="space-y-1.5">
        <MeasurementText m={metric.measurement} size="lg" />
        {noise != null && <NoiseRuler m={metric.measurement} threshold={noise} label={label} />}
      </dd>
    </div>
  );
}

function SmallMultiples({ series }: { series: Series[] }) {
  const { t } = useText();
  const lo = Math.min(...series.flatMap((s) => s.points.map((p) => p.lo)), ...series.map((s) => -(s.noise_floor ?? 0)));
  const hi = Math.max(...series.flatMap((s) => s.points.map((p) => p.hi)), ...series.map((s) => s.noise_floor ?? 0));
  const pad = (hi - lo || 1) * 0.1;
  return (
    <div className="grid gap-4">
      {series.map((s) => (
        <TimeSeriesChart key={s.id} series={s} title={t(`series.${s.id}`)} domain={[lo - pad, hi + pad]} height={170} />
      ))}
    </div>
  );
}

function IndicationWindow({ start, end }: { start: string; end: string }) {
  const { t, lang } = useText();
  return <p className="font-medium">{t("answer.indicationWindow", { start: formatDate(start, lang), end: formatDate(end, lang) })}</p>;
}

function ClassifierScores({ c }: { c: NonNullable<Answer["classifier"]> }) {
  const { t, lang } = useText();
  return <p className="text-sm text-ink-2">{t("answer.classifierScores", { precision: formatNumber(c.precision, lang, 2), recall: formatNumber(c.recall, lang, 2), event: c.evaluated_on })}</p>;
}

const CHECK_ICON = { pass: CircleCheck, warn: TriangleAlert, fail: CircleX, not_applicable: MinusCircle } as const;

function CheckItem({ check }: { check: Check }) {
  const { t, text } = useText();
  const Icon = CHECK_ICON[check.status];
  return (
    <li className="flex gap-2.5">
      <Icon
        className={cn("mt-0.5 size-4 shrink-0", check.status === "pass" && "text-ok", check.status === "warn" && "text-warn", check.status === "fail" && "text-fail", check.status === "not_applicable" && "text-muted")}
        aria-hidden
      />
      <div className="text-sm">
        <p>
          <span className="font-medium">{t(`check.${check.id}`)}</span> <span className="text-ink-2">· {t(`check.status.${check.status}`)}</span>
        </p>
        {check.detail && <p className="text-ink-2">{text(check.detail)}</p>}
      </div>
    </li>
  );
}

const AGREE_ICON = { agrees: CircleCheck, disagrees: CircleX, inconclusive: CircleHelp, unavailable: MinusCircle } as const;

function EvidenceItem({ evidence }: { evidence: Evidence }) {
  const { t, text, lang } = useText();
  const Icon = AGREE_ICON[evidence.agreement];
  return (
    <li className="flex gap-2.5">
      <Icon
        className={cn("mt-0.5 size-4 shrink-0", evidence.agreement === "agrees" && "text-ok", evidence.agreement === "disagrees" && "text-fail", (evidence.agreement === "inconclusive" || evidence.agreement === "unavailable") && "text-muted")}
        aria-hidden
      />
      <div className="text-sm">
        <p>
          <span className="font-medium">{t(`source.${evidence.source}`)}</span> <span className="text-ink-2">· {t(`agreement.${evidence.agreement}`)}</span>
        </p>
        <p className="text-ink-2">{text(evidence.summary)}</p>
        {evidence.retrieved_at && <p className="text-xs text-muted">{formatDate(evidence.retrieved_at, lang, "medium")}</p>}
        {evidence.url && (
          <a href={evidence.url} target="_blank" rel="noopener noreferrer" className="text-xs text-accent underline underline-offset-2">
            {evidence.url}
          </a>
        )}
      </div>
    </li>
  );
}

function Details({ answer }: { answer: Answer }) {
  const { t, lang } = useText();
  const rows: [string, ReactNode][] = [
    [t("answer.recipe"), t(`recipe.${answer.recipe}`)],
    [t("answer.product"), <bdi key="p">{answer.product}</bdi>],
    [t("answer.productStatus"), t(`answer.${answer.product_status}`)],
    [t("answer.period"), t("layer.period", { start: formatDate(answer.period.start, lang), end: formatDate(answer.period.end, lang) })],
    [t("answer.passes"), <bdi key="n" className="num">{formatNumber(answer.acquisitions.length, lang)}</bdi>],
    [
      t("answer.tracks"),
      answer.tracks.length
        ? answer.tracks
            .map((tr) => t(tr.frame != null ? "answer.trackFrame" : "answer.track", { number: tr.number, direction: t(`answer.${tr.direction}`), frame: tr.frame }))
            .join(" ; ")
        : t("common.none"),
    ],
  ];
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-ink-2">{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  );
}
