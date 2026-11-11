import { lazy, Suspense, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Building2, CircleCheckBig, Pickaxe, Route, Waves } from "lucide-react";
import type { Discoveries, Zone } from "@/api/contract";
import { useDiscoveries } from "@/api/queries";
import { ConfidenceBadge } from "@/components/science/badges";
import { MeasurementText } from "@/components/science/MeasurementText";
import { NoiseRuler } from "@/components/science/NoiseRuler";
import { EmptyState, ErrorState, Loading } from "@/components/states";
import { useText } from "@/i18n/useText";
import { formatDate, formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";
import { AskBox } from "@/features/investigate/AskBox";
import type { MapMarker } from "@/components/map/RadarMap";

const RadarMap = lazy(() => import("@/components/map/RadarMap"));

type Sort = "velocity" | "exposure";

export default function DiscoverPage() {
  const { t } = useText();
  const query = useDiscoveries("MA");
  const navigate = useNavigate();

  return (
    <div className="mx-auto w-full max-w-[1600px] px-4 py-6">
      <div className="mb-6 max-w-2xl">
        <AskBox
          location={null}
          onClearLocation={() => undefined}
          running={false}
          compact
          onAsk={(q) => navigate(`/investigate?q=${encodeURIComponent(q)}&auto=1`)}
          onCancel={() => undefined}
        />
      </div>
      {query.isLoading && <Loading />}
      {query.isError && <ErrorState error={query.error} onRetry={() => void query.refetch()} />}
      {query.data && <DiscoverBody data={query.data} />}
      {!query.isLoading && !query.data && !query.isError && <p className="sr-only">{t("common.none")}</p>}
    </div>
  );
}

function DiscoverBody({ data }: { data: Discoveries }) {
  const { t, lang, measurement, place } = useText();
  const navigate = useNavigate();
  const [sort, setSort] = useState<Sort>("velocity");
  const threshold = data.noise_floor.value * data.threshold_factor;

  const zones = useMemo(() => {
    const list = [...data.zones];
    if (sort === "velocity") list.sort((a, b) => a.rank - b.rank);
    else list.sort((a, b) => b.exposure_score - a.exposure_score);
    return list;
  }, [data.zones, sort]);

  const extent = Math.max(threshold, ...data.zones.map((z) => Math.abs(z.velocity.value) + z.velocity.uncertainty)) * 1.1;
  const zoneHref = (z: Zone) =>
    z.answer_id ? `/investigate/${encodeURIComponent(z.answer_id)}` : `/investigate?q=${encodeURIComponent(t("ask.zoneQuestion"))}&lat=${z.location.lat}&lon=${z.location.lon}&auto=1`;

  const markers: MapMarker[] = useMemo(
    () =>
      data.zones.map((z) => ({
        id: z.id,
        lat: z.location.lat,
        lon: z.location.lon,
        label: formatNumber(z.rank, lang),
        title: `${t("discover.rank", { rank: z.rank })} · ${place(z.location)}`,
        onSelect: () => navigate(zoneHref(z)),
      })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [data.zones, lang],
  );

  const regionBounds: [number, number, number, number] = useMemo(() => {
    const lons = data.zones.map((z) => z.location.lon), lats = data.zones.map((z) => z.location.lat);
    return [Math.min(...lons) - 1, Math.min(...lats) - 0.8, Math.max(...lons) + 1, Math.max(...lats) + 0.8];
  }, [data.zones]);

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
      <section aria-labelledby="discover-title" className="space-y-4">
        <header className="space-y-1.5">
          <h1 id="discover-title" className="text-2xl font-semibold text-balance sm:text-3xl">
            {t("discover.title", { region: data.region_name[lang] })}
          </h1>
          <p className="max-w-2xl text-ink-2">
            {t("discover.subtitle", {
              factor: formatNumber(data.threshold_factor, lang),
              noise: measurement(data.noise_floor).text,
              start: formatDate(data.period.start, lang),
              end: formatDate(data.period.end, lang),
            })}
          </p>
          <p className="text-xs text-muted">{t("discover.generated", { date: formatDate(data.generated_at, lang) })}</p>
        </header>

        {data.zones.length > 0 && (
          <div className="flex items-center gap-2 text-sm" role="group" aria-label={t("discover.sortBy")}>
            <span className="text-ink-2">{t("discover.sortBy")}</span>
            {(["velocity", "exposure"] as const).map((s) => (
              <button
                key={s}
                type="button"
                aria-pressed={sort === s}
                onClick={() => setSort(s)}
                className={cn("rounded-sm border px-2.5 py-1", sort === s ? "border-ink bg-ink text-white" : "border-line-strong bg-surface hover:bg-surface-2")}
              >
                {t(s === "velocity" ? "discover.sortVelocity" : "discover.sortExposure")}
              </button>
            ))}
          </div>
        )}

        {data.zones.length === 0 ? (
          <EmptyState icon={<CircleCheckBig className="mt-0.5 size-5 shrink-0 text-ok" aria-hidden />}>
            <p>{t("discover.empty", { factor: formatNumber(data.threshold_factor, lang) })}</p>
          </EmptyState>
        ) : (
          <ol aria-label={t("discover.list")} className="space-y-3">
            {zones.map((z) => (
              <ZoneRow key={z.id} zone={z} threshold={threshold} extent={extent} href={zoneHref(z)} />
            ))}
          </ol>
        )}
      </section>

      <div className="relative h-[60vh] min-h-80 overflow-hidden rounded-md border border-line sticky-below-chrome">
        <Suspense fallback={<div className="absolute inset-0 bg-[#d9e3e9]" />}>
          <RadarMap className="absolute inset-0" ariaLabel={t("map.zones")} bounds={regionBounds} markers={markers} legend={false} />
        </Suspense>
      </div>
    </div>
  );
}

function ZoneRow({ zone, threshold, extent, href }: { zone: Zone; threshold: number; extent: number; href: string }) {
  const { t, lang, place } = useText();
  const e = zone.exposure;
  const exposure = [
    e.buildings != null && e.buildings > 0 && { icon: Building2, text: t("exposure.buildings", { count: e.buildings }) },
    e.roads_km != null && e.roads_km > 0 && { icon: Route, text: t("exposure.roads", { value: formatNumber(e.roads_km, lang) }) },
    e.dams != null && e.dams > 0 && { icon: Waves, text: t("exposure.dams", { count: e.dams }) },
    e.mines != null && e.mines > 0 && { icon: Pickaxe, text: t("exposure.mines", { count: e.mines }) },
  ].filter(Boolean) as { icon: typeof Building2; text: string }[];

  return (
    <li className="group relative rounded-md border border-line bg-surface p-4 transition-colors focus-within:border-accent hover:border-line-strong">
      <div className="flex items-start gap-3">
        <span className="num grid size-8 shrink-0 place-items-center rounded-full border-2 border-accent text-sm font-semibold text-accent" aria-hidden>
          {formatNumber(zone.rank, lang)}
        </span>
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h2 className="text-base font-semibold">
              <Link to={href} className="after:absolute after:inset-0 focus-visible:outline-none">
                <span className="sr-only">{t("discover.rank", { rank: zone.rank })} : </span>
                {place(zone.location)}
              </Link>
            </h2>
            <span className="text-sm text-ink-2">{t(`zoneKind.${zone.kind}`)}</span>
            <span className="ms-auto">
              <ConfidenceBadge level={zone.confidence} withLabel={false} />
            </span>
          </div>

          <div className="grid gap-1 sm:grid-cols-[minmax(0,14rem)_1fr] sm:items-center sm:gap-4">
            <div className="text-sm">
              <span className="text-ink-2">{t("discover.velocity")} </span>
              <MeasurementText m={zone.velocity} />
            </div>
            <div className="flex items-center gap-3">
              <div className="flex-1">
                <NoiseRuler m={zone.velocity} threshold={threshold} extent={extent} label={t("discover.ruler")} />
              </div>
              <bdi className="num shrink-0 text-xs text-ink-2">{t("discover.snr", { value: formatNumber(zone.snr, lang, 1) })}</bdi>
            </div>
          </div>

          {(zone.vertical || zone.east_west) && (
            <p className="flex flex-wrap gap-x-4 text-sm">
              {zone.vertical && (
                <span>
                  <span className="text-ink-2">{t("series.vertical")} </span>
                  <MeasurementText m={zone.vertical} />
                </span>
              )}
              {zone.east_west && (
                <span>
                  <span className="text-ink-2">{t("series.east_west")} </span>
                  <MeasurementText m={zone.east_west} />
                </span>
              )}
            </p>
          )}

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-2">
            <span className="sr-only">{t("exposure.label")} : </span>
            {exposure.length ? (
              exposure.map(({ icon: Icon, text }) => (
                <span key={text} className="inline-flex items-center gap-1">
                  <Icon className="size-3.5" aria-hidden />
                  {text}
                </span>
              ))
            ) : (
              <span>{t("exposure.unknown")}</span>
            )}
            <span className="ms-auto">{zone.manually_checked ? t("discover.checked") : t("discover.unchecked")}</span>
          </div>
        </div>
      </div>
    </li>
  );
}
