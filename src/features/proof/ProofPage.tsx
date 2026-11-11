import { lazy, Suspense, useId, useState } from "react";
import { CartesianGrid, ComposedChart, ErrorBar, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipProps } from "recharts";
import { ShieldQuestion } from "lucide-react";
import type { LbandProof, RasterLayer } from "@/api/contract";
import { useLbandProof } from "@/api/queries";
import { MeasurementText } from "@/components/science/MeasurementText";
import { ErrorState, Loading } from "@/components/states";
import { gradient } from "@/components/map/palettes";
import { useText } from "@/i18n/useText";
import { formatDate, formatNumber } from "@/lib/format";

const RadarMap = lazy(() => import("@/components/map/RadarMap"));
const AXIS = { fontSize: 12, fill: "var(--ink-2)" };

export default function ProofPage() {
  const { t } = useText();
  const query = useLbandProof();
  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6">
      <header className="max-w-2xl space-y-1.5">
        <h1 className="text-2xl font-semibold sm:text-3xl">{t("proof.title")}</h1>
        <p className="text-ink-2">{t("proof.intro")}</p>
      </header>
      {query.isLoading && <Loading />}
      {query.isError && <ErrorState error={query.error} onRetry={() => void query.refetch()} />}
      {query.data && <ProofBody proof={query.data} />}
    </div>
  );
}

function ProofBody({ proof }: { proof: LbandProof }) {
  const { t, lang, text, place } = useText();
  return (
    <div className="space-y-6">
      <p className="text-lg font-medium text-balance">{text(proof.verdict)}</p>
      <p className="text-sm text-ink-2">
        {place(proof.site)} · {t("layer.period", { start: formatDate(proof.period.start, lang), end: formatDate(proof.period.end, lang) })}
      </p>

      <div className="grid gap-4 md:grid-cols-2">
        <SensorMap title={t("proof.nisar")} layer={proof.nisar.layer} mean={proof.nisar.coherence} />
        <SensorMap title={t("proof.s1")} layer={proof.sentinel1.layer} mean={proof.sentinel1.coherence} />
      </div>
      <SharedScale layer={proof.nisar.layer} />

      <ForestChart proof={proof} />

      <section aria-labelledby="proof-limits" className="space-y-2 rounded-md bg-ink p-4 text-white">
        <h2 id="proof-limits" className="flex items-center gap-2 font-semibold">
          <ShieldQuestion className="size-4" aria-hidden />
          {t("answer.limits")}
        </h2>
        <ul className="list-disc space-y-1 ps-5 text-sm text-white/90">
          {proof.limits.map((l, i) => (
            <li key={l.template + i}>{text(l)}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function SensorMap({ title, layer, mean }: { title: string; layer: RasterLayer; mean: LbandProof["nisar"]["coherence"] }) {
  const { t } = useText();
  return (
    <figure className="space-y-2">
      <figcaption className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-semibold">{title}</span>
        <span className="text-sm">
          <span className="text-ink-2">{t("proof.mean")} </span>
          <MeasurementText m={mean} />
        </span>
      </figcaption>
      <div className="relative aspect-[4/3] overflow-hidden rounded-md border border-line">
        <Suspense fallback={<div className="absolute inset-0 bg-[#d9e3e9]" />}>
          <RadarMap className="absolute inset-0" ariaLabel={`${title} · ${t("layer.kind.coherence")}`} bounds={layer.bounds} layers={[layer]} legend={false} interactive={false} />
        </Suspense>
      </div>
    </figure>
  );
}

/** One scale for both maps, so the comparison is honest. */
function SharedScale({ layer }: { layer: RasterLayer }) {
  const { t, lang } = useText();
  return (
    <div className="max-w-sm space-y-1">
      <p className="text-sm font-medium">
        {t("layer.kind.coherence")} <span className="font-normal text-muted">({t("unitName.coherence")})</span>
      </p>
      <div dir="ltr" aria-hidden className="space-y-0.5">
        <div className="h-2.5 rounded-sm ring-1 ring-black/10" style={{ background: gradient(layer.palette) }} />
        <div className="num flex justify-between text-xs text-ink-2">
          <span>{formatNumber(layer.min, lang)}</span>
          <span>{formatNumber(layer.max, lang)}</span>
        </div>
      </div>
      <p className="sr-only">{t("common.range", { from: formatNumber(layer.min, lang), to: formatNumber(layer.max, lang) })}</p>
    </div>
  );
}

interface BinRow {
  mid: number;
  label: string;
  nisar: number;
  nisarErr: number;
  s1: number;
  s1Err: number;
  pixels: number;
}

function ForestChart({ proof }: { proof: LbandProof }) {
  const { t, lang } = useText();
  const [table, setTable] = useState(false);
  const tableId = useId();
  const rows: BinRow[] = proof.bins.map((b) => ({
    mid: (b.forest_cover.min + b.forest_cover.max) / 2,
    label: t("proof.bin", { min: formatNumber(b.forest_cover.min, lang), max: formatNumber(b.forest_cover.max, lang) }),
    nisar: b.nisar.value,
    nisarErr: b.nisar.uncertainty,
    s1: b.sentinel1.value,
    s1Err: b.sentinel1.uncertainty,
    pixels: b.pixels,
  }));
  const fmt = (v: number) => formatNumber(v, lang, 2);

  return (
    <figure className="space-y-3 rounded-md border border-line bg-surface p-4">
      <figcaption className="font-semibold">{t("proof.byForest")}</figcaption>
      <div dir="ltr" className="h-72" aria-hidden={table ? true : undefined}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 8, right: 16, bottom: 18, left: 0 }} accessibilityLayer>
            <CartesianGrid vertical={false} stroke="var(--line)" />
            <XAxis
              dataKey="mid"
              type="number"
              domain={[0, 100]}
              ticks={rows.map((r) => r.mid)}
              tickFormatter={(v: number) => rows.find((r) => r.mid === v)?.label ?? ""}
              tick={AXIS}
              tickLine={false}
              axisLine={{ stroke: "var(--line-strong)" }}
              label={{ value: t("proof.forestAxis"), position: "insideBottom", offset: -12, fill: "var(--ink-2)", fontSize: 12 }}
            />
            <YAxis domain={[0, 1]} tickFormatter={(v: number) => formatNumber(v, lang, 1)} tick={AXIS} tickLine={false} axisLine={false} width={40} />
            <ReferenceLine
              y={proof.usable_threshold}
              stroke="var(--ink)"
              strokeDasharray="5 4"
              label={{ value: t("proof.threshold", { value: formatNumber(proof.usable_threshold, lang, 1) }), position: "insideTopRight", fill: "var(--ink)", fontSize: 12 }}
            />
            <Line dataKey="nisar" name={t("proof.nisar")} stroke="var(--series-1)" strokeWidth={2} dot={{ r: 4, fill: "var(--series-1)", stroke: "var(--surface)", strokeWidth: 2 }} isAnimationActive={false}>
              <ErrorBar dataKey="nisarErr" width={6} stroke="var(--series-1)" strokeWidth={1.5} direction="y" />
            </Line>
            <Line
              dataKey="s1"
              name={t("proof.s1")}
              stroke="var(--series-2)"
              strokeWidth={2}
              strokeDasharray="6 3"
              dot={{ r: 4, fill: "var(--surface)", stroke: "var(--series-2)", strokeWidth: 2 }}
              isAnimationActive={false}
            >
              <ErrorBar dataKey="s1Err" width={6} stroke="var(--series-2)" strokeWidth={1.5} direction="y" />
            </Line>
            <Tooltip content={<BinTooltip fmt={fmt} />} cursor={{ stroke: "var(--ink-2)", strokeWidth: 1 }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-ink-2">
        <li className="flex items-center gap-2">
          <svg width="22" height="10" aria-hidden>
            <line x1="0" x2="22" y1="5" y2="5" stroke="var(--series-1)" strokeWidth="2" />
            <circle cx="11" cy="5" r="3.5" fill="var(--series-1)" />
          </svg>
          {t("proof.nisar")}
        </li>
        <li className="flex items-center gap-2">
          <svg width="22" height="10" aria-hidden>
            <line x1="0" x2="22" y1="5" y2="5" stroke="var(--series-2)" strokeWidth="2" strokeDasharray="5 3" />
            <circle cx="11" cy="5" r="3.5" fill="var(--surface)" stroke="var(--series-2)" strokeWidth="2" />
          </svg>
          {t("proof.s1")}
        </li>
        <li className="text-xs">{t("chart.band", { sigma: formatNumber(proof.bins[0].nisar.sigma, lang) })}</li>
        <li className="text-xs">{t("proof.forestSource", { source: proof.forest_source })}</li>
        <li className="ms-auto">
          <button type="button" className="underline underline-offset-2 hover:text-ink" aria-expanded={table} aria-controls={tableId} onClick={() => setTable((v) => !v)}>
            {table ? t("common.hideData") : t("common.showData")}
          </button>
        </li>
      </ul>
      <div id={tableId} hidden={!table} className="overflow-x-auto rounded-sm border border-line">
        <table className="num w-full text-sm">
          <caption className="sr-only">{t("proof.byForest")}</caption>
          <thead className="bg-surface-2 text-xs text-ink-2">
            <tr>
              <th scope="col" className="px-2 py-1 text-start font-medium">{t("proof.forestAxis")}</th>
              <th scope="col" className="px-2 py-1 text-end font-medium">{t("proof.nisar")}</th>
              <th scope="col" className="px-2 py-1 text-end font-medium">{t("proof.s1")}</th>
              <th scope="col" className="px-2 py-1 text-end font-medium">{t("proof.pixelsHeader")}</th>
            </tr>
          </thead>
          <tbody>
            {proof.bins.map((b, i) => (
              <tr key={i} className="border-t border-line">
                <td className="px-2 py-1">{rows[i].label}</td>
                <td className="px-2 py-1 text-end"><MeasurementText m={b.nisar} /></td>
                <td className="px-2 py-1 text-end"><MeasurementText m={b.sentinel1} /></td>
                <td className="px-2 py-1 text-end">{formatNumber(b.pixels, lang, 0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </figure>
  );
}

function BinTooltip({ active, payload, fmt }: TooltipProps<number, string> & { fmt: (v: number) => string }) {
  const { t } = useText();
  const row = payload?.[0]?.payload as BinRow | undefined;
  if (!active || !row) return null;
  return (
    <div className="space-y-0.5 rounded-sm border border-line-strong bg-surface px-2.5 py-1.5 text-sm shadow-md">
      <div className="text-xs text-ink-2">{row.label}</div>
      <div><span className="text-ink-2">{t("proof.nisar")} </span><bdi className="num font-medium">{fmt(row.nisar)} ± {fmt(row.nisarErr)}</bdi></div>
      <div><span className="text-ink-2">{t("proof.s1")} </span><bdi className="num font-medium">{fmt(row.s1)} ± {fmt(row.s1Err)}</bdi></div>
      <div className="text-xs text-muted">{t("proof.pixels", { count: row.pixels })}</div>
    </div>
  );
}
