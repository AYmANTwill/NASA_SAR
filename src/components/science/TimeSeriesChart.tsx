import { useId, useMemo, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipProps } from "recharts";
import type { Series } from "@/api/contract";
import { useText } from "@/i18n/useText";
import { decimalsFor, formatDate, formatNumber } from "@/lib/format";

interface Row {
  ts: number;
  date: string;
  value: number;
  band: [number, number];
  sigma: number;
}

interface TimeSeriesChartProps {
  series: Series;
  title: string;
  /** Shared y-domain for small multiples so panels compare honestly. */
  domain?: [number, number];
  sigma?: number;
  height?: number;
}

const AXIS = { fontSize: 12, fill: "var(--ink-2)" };

/**
 * One series per chart: line = value, band = uncertainty, grey band = noise floor,
 * every dot = a NISAR pass. A data table is always available.
 */
export function TimeSeriesChart({ series, title, domain, sigma = 1, height = 200 }: TimeSeriesChartProps) {
  const { t, lang, unit } = useText();
  const [showTable, setShowTable] = useState(false);
  const tableId = useId();
  const u = unit(series.unit) || t(`unitName.${series.unit}`, { defaultValue: "" });

  const rows: Row[] = useMemo(
    () => series.points.map((p) => ({ ts: Date.parse(p.date + "T00:00:00Z"), date: p.date, value: p.value, band: [p.lo, p.hi], sigma: (p.hi - p.lo) / 2 })),
    [series.points],
  );
  const decimals = decimalsFor(Math.min(...rows.map((r) => r.sigma).filter((s) => s > 0), Infinity), rows[0]?.value ?? 0);
  const fmt = (v: number) => formatNumber(v, lang, Number.isFinite(decimals) ? decimals : 1);

  const yDomain = useMemo<[number, number]>(() => {
    if (domain) return domain;
    const lo = Math.min(...rows.map((r) => r.band[0]), -(series.noise_floor ?? 0));
    const hi = Math.max(...rows.map((r) => r.band[1]), series.noise_floor ?? 0);
    const pad = (hi - lo || 1) * 0.12;
    return [lo - pad, hi + pad];
  }, [domain, rows, series.noise_floor]);

  return (
    <figure className="space-y-2">
      <figcaption className="flex flex-wrap items-baseline justify-between gap-x-3">
        <span className="font-medium">{title}</span>
        <span className="text-xs text-muted">{t("chart.axis", { label: t(`series.${series.id}`), unit: u })}</span>
      </figcaption>
      <div dir="ltr" style={{ height }} aria-hidden={showTable ? true : undefined}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 6, right: 8, bottom: 0, left: 0 }} accessibilityLayer>
            <CartesianGrid vertical={false} stroke="var(--line)" strokeDasharray="0" />
            <XAxis
              dataKey="ts"
              type="number"
              scale="time"
              domain={["dataMin", "dataMax"]}
              ticks={pickTicks(rows)}
              tickFormatter={(ts: number) => formatDate(new Date(ts).toISOString().slice(0, 10), lang, "short")}
              tick={AXIS}
              tickLine={false}
              axisLine={{ stroke: "var(--line-strong)" }}
            />
            <YAxis domain={yDomain} tickFormatter={fmt} tick={AXIS} tickLine={false} axisLine={false} width={46} allowDecimals />
            {series.noise_floor != null && series.noise_floor > 0 && (
              <ReferenceArea y1={-series.noise_floor} y2={series.noise_floor} fill="var(--noise-band)" fillOpacity={1} stroke="none" ifOverflow="hidden" />
            )}
            {yDomain[0] < 0 && yDomain[1] > 0 && <ReferenceLine y={0} stroke="var(--muted)" strokeWidth={1} />}
            <Area dataKey="band" type="linear" stroke="none" fill="var(--uncertainty-band)" fillOpacity={1} isAnimationActive={false} activeDot={false} />
            <Line
              dataKey="value"
              type="linear"
              stroke="var(--series-1)"
              strokeWidth={2}
              dot={{ r: 4, fill: "var(--surface)", stroke: "var(--series-1)", strokeWidth: 2 }}
              activeDot={{ r: 5, fill: "var(--series-1)", stroke: "var(--surface)", strokeWidth: 2 }}
              isAnimationActive={false}
            />
            <Tooltip content={<ChartTooltip unit={u} fmt={fmt} />} cursor={{ stroke: "var(--ink-2)", strokeWidth: 1 }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
        <li className="flex items-center gap-1.5">
          <span aria-hidden className="inline-block size-2.5 rounded-full border-2 border-[var(--series-1)] bg-surface" />
          {t("chart.pass")}
        </li>
        <li className="flex items-center gap-1.5">
          <span aria-hidden className="inline-block h-2.5 w-4 bg-[var(--uncertainty-band)]" />
          {t("chart.band", { sigma: formatNumber(sigma, lang) })}
        </li>
        {series.noise_floor != null && series.noise_floor > 0 && (
          <li className="flex items-center gap-1.5">
            <span aria-hidden className="inline-block h-2.5 w-4 bg-[var(--noise-band)] ring-1 ring-line" />
            {t("chart.noise")}
          </li>
        )}
        <li className="ms-auto">
          <button type="button" className="underline underline-offset-2 hover:text-ink" aria-expanded={showTable} aria-controls={tableId} onClick={() => setShowTable((s) => !s)}>
            {showTable ? t("common.hideData") : t("common.showData")}
          </button>
        </li>
      </ul>
      <div id={tableId} hidden={!showTable} className="max-h-56 overflow-auto rounded-sm border border-line">
        <table className="num w-full text-sm">
          <caption className="sr-only">{t("chart.caption", { label: title })}</caption>
          <thead className="sticky top-0 bg-surface-2 text-start text-xs text-ink-2">
            <tr>
              <th scope="col" className="px-2 py-1 text-start font-medium">{t("common.date")}</th>
              <th scope="col" className="px-2 py-1 text-end font-medium">{t("common.value")} ({u})</th>
              <th scope="col" className="px-2 py-1 text-end font-medium">{t("common.lower")}</th>
              <th scope="col" className="px-2 py-1 text-end font-medium">{t("common.upper")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.date} className="border-t border-line">
                <td className="px-2 py-1">{formatDate(r.date, lang, "medium")}</td>
                <td className="px-2 py-1 text-end"><bdi>{fmt(r.value)}</bdi></td>
                <td className="px-2 py-1 text-end"><bdi>{fmt(r.band[0])}</bdi></td>
                <td className="px-2 py-1 text-end"><bdi>{fmt(r.band[1])}</bdi></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </figure>
  );
}

function pickTicks(rows: Row[]): number[] {
  if (rows.length <= 5) return rows.map((r) => r.ts);
  const step = Math.ceil(rows.length / 5);
  return rows.filter((_, i) => i % step === 0).map((r) => r.ts);
}

function ChartTooltip({ active, payload, unit, fmt }: TooltipProps<number, string> & { unit: string; fmt: (v: number) => string }) {
  const { t, lang } = useText();
  const row = payload?.[0]?.payload as Row | undefined;
  if (!active || !row) return null;
  return (
    <div className="rounded-sm border border-line-strong bg-surface px-2.5 py-1.5 text-sm shadow-md">
      <div className="text-xs text-ink-2">{t("chart.pass")} · {formatDate(row.date, lang, "medium")}</div>
      <div className="num font-medium">
        <bdi>{t("chart.value", { value: fmt(row.value), uncertainty: fmt(row.sigma) })}</bdi> {unit}
      </div>
    </div>
  );
}
