import { useMemo } from "react";
import { Link } from "react-router-dom";
import { ExternalLink, MessageSquareText, ShieldQuestion } from "lucide-react";
import type { CaseStudy, Measurement } from "@/api/contract";
import { useCaseStudy } from "@/api/queries";
import { MapSlot } from "@/components/map/MapSlot";
import type { MapMarker } from "@/components/map/RadarMap";
import { MeasurementText } from "@/components/science/MeasurementText";
import { ErrorState, Loading } from "@/components/states";
import { Button } from "@/components/ui/button";
import { useText } from "@/i18n/useText";
import { formatDate } from "@/lib/format";
import { BackToCases, KIND_ICON, localized } from "./CasesPage";
import { AgreementBadge, DraftBanner, PendingAgreementBadge } from "./parts";

const DAY = 86_400_000;
const dayOf = (at: string) => Date.parse(at.length === 10 ? at + "T00:00:00Z" : at);

export function CaseView({ id }: { id: string }) {
  const query = useCaseStudy(id);
  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6">
      <BackToCases />
      {query.isLoading && <Loading />}
      {query.isError && <ErrorState error={query.error} onRetry={() => void query.refetch()} />}
      {query.data && <CaseBody c={query.data} />}
    </div>
  );
}

function CaseBody({ c }: { c: CaseStudy }) {
  const { t, lang, text } = useText();
  const Icon = KIND_ICON[c.kind];
  const layers = useMemo(() => c.figures.flatMap((f) => (f.layer ? [f.layer] : [])), [c.figures]);
  const markers: MapMarker[] = useMemo(() => [{ id: c.id, lat: c.location.lat, lon: c.location.lon, label: "", title: localized(c.location.place, lang), active: true }], [c, lang]);

  return (
    <article className="space-y-6" aria-labelledby="case-title">
      {c.status === "draft" && <DraftBanner />}

      {/* 1. Headline */}
      <header className="space-y-2">
        <p className="flex flex-wrap items-center gap-2 text-sm text-ink-2">
          <Icon className="size-4 text-accent" aria-hidden />
          {t(`cases.kind.${c.kind}`)} · <time dateTime={c.date}>{formatDate(c.date, lang)}</time> · {localized(c.location.place, lang)}
        </p>
        <h1 id="case-title" className="text-2xl font-semibold text-balance sm:text-3xl">
          {localized(c.title, lang)}
        </h1>
        <p className="max-w-3xl text-lg text-balance">{text(c.headline)}</p>
      </header>

      {/* 2. Timeline */}
      {c.timeline.length > 0 && <Timeline items={c.timeline} />}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        {/* 3. Map */}
        <section aria-label={t("cases.map")} className="relative h-[52vh] min-h-72 overflow-hidden rounded-md border border-line">
          <MapSlot
            className="absolute inset-0"
            ariaLabel={`${t("cases.map")} · ${localized(c.location.place, lang)}`}
            bounds={c.location.bbox}
            layers={layers}
            markers={layers.length ? [] : markers}
            motion={layers.length ? { kind: "pass", key: c.id, direction: "ascending" } : null}
          />
        </section>

        <div className="space-y-6">
          {/* 4. Findings */}
          <Findings c={c} />
          {/* 5. Exposure */}
          {c.exposure && <Exposure exposure={c.exposure} />}
        </div>
      </div>

      {/* Figures that are not map layers */}
      {c.figures.some((f) => f.kind !== "map" && f.url) && (
        <section aria-labelledby="case-figures" className="space-y-3">
          <h2 id="case-figures" className="font-semibold">{t("cases.figures")}</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {c.figures
              .filter((f) => f.kind !== "map" && f.url)
              .map((f) => (
                <figure key={f.id} className="space-y-2 rounded-md border border-line bg-surface p-3">
                  <img src={f.url!} alt={localized(f.title, lang)} className="w-full rounded-sm" />
                  <figcaption className="text-sm text-ink-2">{text(f.caption)}</figcaption>
                </figure>
              ))}
          </div>
        </section>
      )}

      {/* 6. Limits, always visible */}
      <section aria-labelledby="case-limits" className="space-y-2 rounded-md bg-ink p-4 text-white">
        <h2 id="case-limits" className="flex items-center gap-2 font-semibold">
          <ShieldQuestion className="size-4" aria-hidden />
          {t("answer.limits")}
        </h2>
        <ul className="list-disc space-y-1 ps-5 text-sm text-white/90">
          {c.limits.map((l, i) => (
            <li key={l.template + i}>{text(l)}</li>
          ))}
        </ul>
      </section>

      {/* 7. Agent answers */}
      {c.answer_ids.length > 0 && (
        <section aria-labelledby="case-answers" className="space-y-2">
          <h2 id="case-answers" className="font-semibold">{t("cases.answers")}</h2>
          <div className="flex flex-wrap gap-2">
            {c.answer_ids.map((id) => (
              <Button key={id} asChild variant="outline" size="sm">
                <Link to={`/investigate/${encodeURIComponent(id)}`}>
                  <MessageSquareText className="size-4" aria-hidden />
                  {t("cases.openAnswer")}
                </Link>
              </Button>
            ))}
          </div>
        </section>
      )}
    </article>
  );
}

/** Event → NISAR passes → product, with the real interval between consecutive dates. */
function Timeline({ items }: { items: CaseStudy["timeline"] }) {
  const { t, lang } = useText();
  const sorted = [...items].sort((a, b) => dayOf(a.at) - dayOf(b.at));
  return (
    <section aria-labelledby="case-timeline" className="space-y-3">
      <h2 id="case-timeline" className="font-semibold">{t("cases.timeline")}</h2>
      <ol className="case-timeline relative grid gap-4 sm:grid-flow-col sm:auto-cols-fr">
        {sorted.map((item, i) => {
          const days = i > 0 ? Math.round((dayOf(item.at) - dayOf(sorted[i - 1].at)) / DAY) : null;
          return (
            <li key={item.at + i} className="case-step relative flex gap-3 sm:flex-col sm:gap-2" style={{ animationDelay: `${i * 220}ms` }}>
              <span aria-hidden className="relative z-10 mt-1 size-3 shrink-0 rounded-full border-2 border-accent bg-surface sm:mt-0" />
              <div className="space-y-0.5">
                <p className="font-medium">{localized(item.label, lang)}</p>
                <p className="text-sm text-ink-2">
                  <time dateTime={item.at}>{item.at.length === 10 ? formatDate(item.at, lang) : formatDate(item.at.slice(0, 10), lang)}</time>
                  {days != null && <> · {days === 0 ? t("cases.sameDay") : t("cases.after", { count: days })}</>}
                </p>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function Findings({ c }: { c: CaseStudy }) {
  const { t, lang } = useText();
  return (
    <section aria-labelledby="case-findings" className="space-y-2">
      <h2 id="case-findings" className="font-semibold">{t("cases.findings")}</h2>
      {c.findings.length === 0 ? (
        <p className="rounded-md border border-dashed border-line-strong bg-surface p-4 text-ink-2">{t("cases.noFindings")}</p>
      ) : (
        <div className="overflow-x-auto rounded-md border border-line bg-surface">
          <table className="w-full text-sm">
            <thead className="bg-surface-2 text-xs text-ink-2">
              <tr>
                <th scope="col" className="px-3 py-2 text-start font-medium">{t("cases.what")}</th>
                <th scope="col" className="px-3 py-2 text-start font-medium">{t("cases.nisar")}</th>
                <th scope="col" className="px-3 py-2 text-start font-medium">{t("cases.reference")}</th>
                <th scope="col" className="px-3 py-2 text-start font-medium">{t("cases.agreementCol")}</th>
              </tr>
            </thead>
            <tbody>
              {c.findings.map((f) => (
                <tr key={f.id} className="border-t border-line align-top">
                  <th scope="row" className="px-3 py-2 text-start font-medium">{localized(f.label, lang)}</th>
                  <td className="px-3 py-2">
                    {/* A NISAR value without uncertainty is a draft placeholder (a final case requires one): never shown as a measurement. */}
                    {f.nisar.uncertainty > 0 ? <MeasurementText m={f.nisar} /> : <span className="text-ink-2">{t("cases.notMeasuredYet")}</span>}
                  </td>
                  <td className="px-3 py-2">
                    {f.reference ? <MeasurementText m={f.reference} /> : <span className="text-ink-2">{t("cases.notMeasured")}</span>}
                    {f.reference_source && (
                      <span className="block text-xs text-ink-2">
                        {f.reference_source.url ? (
                          <a href={f.reference_source.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 underline underline-offset-2 hover:text-ink">
                            {f.reference_source.name}
                            <ExternalLink className="size-3" aria-hidden />
                          </a>
                        ) : (
                          f.reference_source.name
                        )}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2">{f.nisar.uncertainty > 0 ? <AgreementBadge value={f.agreement} /> : <PendingAgreementBadge />}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function Exposure({ exposure }: { exposure: NonNullable<CaseStudy["exposure"]> }) {
  const { t } = useText();
  const rows: [string, Measurement | null][] = [
    [t("cases.people"), exposure.people],
    [t("cases.buildings"), exposure.buildings],
    [t("cases.area"), exposure.area_km2],
  ];
  return (
    <section aria-labelledby="case-exposure" className="space-y-2 rounded-md border border-line bg-surface p-4">
      <h2 id="case-exposure" className="font-semibold">{t("cases.exposure")}</h2>
      <dl className="grid grid-cols-3 gap-3">
        {rows.map(([label, m]) => (
          <div key={label}>
            <dt className="text-xs text-ink-2">{label}</dt>
            <dd>{m ? <MeasurementText m={m} /> : <span className="text-ink-2">{t("cases.notMeasured")}</span>}</dd>
          </div>
        ))}
      </dl>
      <p className="text-xs text-ink-2">
        <a href={exposure.source.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 underline underline-offset-2 hover:text-ink">
          {t("cases.exposureSource", { source: exposure.source.name })}
          <ExternalLink className="size-3" aria-hidden />
        </a>
      </p>
    </section>
  );
}
