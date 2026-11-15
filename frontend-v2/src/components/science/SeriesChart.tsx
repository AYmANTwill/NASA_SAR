import type { Series } from "@/api/contract";
import { formatDate, formatNumber } from "@/i18n/format";
import { useText } from "@/i18n/useText";

const W = 560;
const H = 200;
const PAD = { left: 56, right: 12, top: 12, bottom: 28 };

/**
 * A time series as the API sent it: each point with its lo–hi band, and the
 * ± noise floor drawn around zero when the API gives one. Axis labels are
 * only API values (first and last dates, lowest lo and highest hi), so the
 * chart writes no number of its own. Time runs left to right in every
 * language. Screen readers get the same points as a table.
 */
export function SeriesChart({ series }: { series: Series }) {
  const { t, lang } = useText();
  const unit = t(`unit.${series.unit}`);
  const times = series.points.map((p) => Date.parse(`${p.date}T00:00:00Z`));
  const t0 = Math.min(...times);
  const t1 = Math.max(...times);
  const lo = Math.min(...series.points.map((p) => p.lo), series.noise_floor !== null ? -series.noise_floor : Infinity);
  const hi = Math.max(...series.points.map((p) => p.hi), series.noise_floor !== null ? series.noise_floor : -Infinity);
  const x = (time: number) => PAD.left + (t1 === t0 ? 0.5 : (time - t0) / (t1 - t0)) * (W - PAD.left - PAD.right);
  const y = (v: number) => PAD.top + (hi === lo ? 0.5 : (hi - v) / (hi - lo)) * (H - PAD.top - PAD.bottom);
  const minLo = Math.min(...series.points.map((p) => p.lo));
  const maxHi = Math.max(...series.points.map((p) => p.hi));
  const band =
    series.points.map((p, i) => `${i === 0 ? "M" : "L"}${x(times[i]!)},${y(p.hi)}`).join("") +
    series.points
      .slice()
      .reverse()
      .map((p, i) => `L${x(times[times.length - 1 - i]!)},${y(p.lo)}`)
      .join("") +
    "Z";
  const line = series.points.map((p, i) => `${i === 0 ? "M" : "L"}${x(times[i]!)},${y(p.value)}`).join("");

  return (
    <figure className="series">
      <figcaption className="series-title">
        {t(`seriesId.${series.id}`)}
        {unit && <span className="legend-unit"> ({unit})</span>}
      </figcaption>
      <svg className="series-chart" viewBox={`0 0 ${W} ${H}`} aria-hidden="true" focusable="false">
        {series.noise_floor !== null && (
          <rect className="series-noise" x={PAD.left} width={W - PAD.left - PAD.right} y={y(series.noise_floor)} height={Math.max(y(-series.noise_floor) - y(series.noise_floor), 0)} />
        )}
        <path className="series-band" d={band} />
        <path className="series-line" d={line} />
        {series.points.map((p, i) => (
          <circle key={p.date} className="series-point" cx={x(times[i]!)} cy={y(p.value)} r="2.5" />
        ))}
        <text className="series-axis" x={PAD.left - 6} y={y(maxHi)} textAnchor="end" dominantBaseline="middle">
          {formatNumber(maxHi, lang)}
        </text>
        <text className="series-axis" x={PAD.left - 6} y={y(minLo)} textAnchor="end" dominantBaseline="middle">
          {formatNumber(minLo, lang)}
        </text>
        <text className="series-axis" x={x(t0)} y={H - 8} textAnchor="start">
          {formatDate(series.points[0]!.date, lang)}
        </text>
        {t1 !== t0 && (
          <text className="series-axis" x={x(t1)} y={H - 8} textAnchor="end">
            {formatDate(series.points[series.points.length - 1]!.date, lang)}
          </text>
        )}
      </svg>
      <details className="series-table">
        <summary>{t("series.table")}</summary>
        <table>
          <thead>
            <tr>
              <th scope="col">{t("series.date")}</th>
              <th scope="col">{t("series.value")}</th>
              <th scope="col">{t("series.range", { sigma: formatNumber(series.sigma, lang) })}</th>
            </tr>
          </thead>
          <tbody>
            {series.points.map((p) => (
              <tr key={p.date}>
                <td>{formatDate(p.date, lang)}</td>
                <td>
                  <bdi dir="ltr">{formatNumber(p.value, lang)}</bdi> {unit}
                </td>
                <td>
                  <bdi dir="ltr">
                    {formatNumber(p.lo, lang)} – {formatNumber(p.hi, lang)}
                  </bdi>{" "}
                  {unit}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
