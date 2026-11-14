import { useMemo } from "react";
import { useText } from "@/i18n/useText";
import { formatNumber } from "@/lib/format";
import { C_BAND_CM, L_BAND_CM } from "@/lib/physics";

type P = [number, number];

/** A sine wave following a polyline, with the given wavelength (px) and amplitude. */
function sineAlong(points: P[], wavelength: number, amplitude: number): string {
  const out: string[] = [];
  let travelled = 0;
  for (let i = 0; i < points.length - 1; i++) {
    const [x0, y0] = points[i];
    const [x1, y1] = points[i + 1];
    const len = Math.hypot(x1 - x0, y1 - y0);
    const ux = (x1 - x0) / len, uy = (y1 - y0) / len;
    const nx = -uy, ny = ux;
    for (let d = 0; d <= len; d += 1.5) {
      const a = amplitude * Math.sin(((travelled + d) / wavelength) * Math.PI * 2);
      out.push(`${(x0 + ux * d + nx * a).toFixed(1)},${(y0 + uy * d + ny * a).toFixed(1)}`);
    }
    travelled += len;
  }
  return "M" + out.join(" L");
}

const TREES = [40, 92, 150, 205, 262, 318, 372, 430, 486, 540, 596];

/**
 * Why L-band: the drawing is to scale in wavelength (λC / λL from the
 * instruments' frequencies). The C-band wave (Sentinel-1) scatters back from
 * the foliage; the L-band wave (NISAR), about four times longer, passes
 * through it and returns from the ground. Schematic, not a measurement.
 */
export function BandExplainer() {
  const { t, lang } = useText();
  const L = 46;
  const Cpx = (L * C_BAND_CM) / L_BAND_CM;
  const canopyTop = 150, ground = 262;
  const paths = useMemo(
    () => ({
      // Monostatic radar: the echo returns to the satellite that sent the pulse.
      c: sineAlong([[150, 20], [235, canopyTop], [166, 22]], Cpx, 5),
      l: sineAlong([[390, 20], [470, ground], [408, 22]], L, 7),
    }),
    [Cpx],
  );

  return (
    <figure className="space-y-3 rounded-md border border-line bg-surface p-4">
      <figcaption className="space-y-1">
        <span className="block font-semibold">{t("proof.why.title")}</span>
        <span className="block text-sm text-ink-2">{t("proof.why.body")}</span>
      </figcaption>
      <svg viewBox="0 0 640 300" role="img" aria-label={t("proof.why.alt")} className="band-explainer mx-auto block max-h-72 w-full" direction="ltr">
        <defs>
          <linearGradient id="sky" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="var(--surface-2)" />
            <stop offset="1" stopColor="var(--surface)" />
          </linearGradient>
        </defs>
        <rect width="640" height="300" fill="url(#sky)" />
        {/* ground */}
        <path d={`M0 ${ground} H640 V300 H0 Z`} fill="#c9b99a" />
        <path d={`M0 ${ground} H640`} stroke="#8a7a5c" strokeWidth="2" />
        {/* canopy: trunks and crowns */}
        {TREES.map((x, i) => (
          <g key={x}>
            <rect x={x - 3} y={canopyTop + 20} width="6" height={ground - canopyTop - 20} fill="#6b5a3e" />
            <ellipse cx={x} cy={canopyTop + 14 + (i % 2) * 6} rx="30" ry="20" fill="#3f7a4a" opacity="0.9" />
            <ellipse cx={x + 10} cy={canopyTop + 4 + (i % 3) * 4} rx="20" ry="15" fill="#4f8f58" opacity="0.9" />
          </g>
        ))}
        {/* satellites */}
        <g fill="var(--ink)">
          <circle cx="150" cy="14" r="6" />
          <rect x="132" y="11" width="36" height="5" />
          <circle cx="400" cy="14" r="6" />
          <rect x="382" y="11" width="36" height="5" />
        </g>
        {/* waves: faint full path + a travelling packet */}
        <path d={paths.c} fill="none" stroke="var(--series-2)" strokeWidth="1.25" opacity="0.35" />
        <path d={paths.c} fill="none" stroke="var(--series-2)" strokeWidth="2.5" pathLength={100} className="wave-packet" />
        <path d={paths.l} fill="none" stroke="var(--series-1)" strokeWidth="1.25" opacity="0.35" />
        <path d={paths.l} fill="none" stroke="var(--series-1)" strokeWidth="2.5" pathLength={100} className="wave-packet wave-packet-l" />
        {/* scattering points */}
        <circle cx="235" cy={canopyTop} r="5" fill="none" stroke="var(--series-2)" strokeWidth="2" className="wave-hit" />
        <circle cx="470" cy={ground} r="5" fill="none" stroke="var(--series-1)" strokeWidth="2" className="wave-hit wave-hit-l" />
      </svg>
      <ul className="grid gap-2 text-sm sm:grid-cols-2">
        <li className="flex items-start gap-2">
          <span aria-hidden className="mt-1.5 inline-block h-0.5 w-5 shrink-0 bg-[var(--series-2)]" />
          <span>{t("proof.why.c", { lambda: formatNumber(C_BAND_CM, lang, 2) })}</span>
        </li>
        <li className="flex items-start gap-2">
          <span aria-hidden className="mt-1.5 inline-block h-0.5 w-5 shrink-0 bg-[var(--series-1)]" />
          <span>{t("proof.why.l", { lambda: formatNumber(L_BAND_CM, lang, 2) })}</span>
        </li>
      </ul>
    </figure>
  );
}
