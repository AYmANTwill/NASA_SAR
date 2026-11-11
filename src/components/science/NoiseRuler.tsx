import type { Measurement } from "@/api/contract";
import { useText } from "@/i18n/useText";
import { formatNumber, isolate } from "@/lib/format";

interface NoiseRulerProps {
  m: Measurement;
  /** Half-width of the "within noise" band, same unit as m. */
  threshold: number;
  /** Shared half-range so several rulers line up; defaults to fitting this value. */
  extent?: number;
  label: string;
}

/**
 * A number line centred on zero: shaded band = noise threshold, whisker = ±uncertainty,
 * dot = value. Shows at a glance whether a signal clears the noise.
 * Always drawn left-to-right (a number line), including in Arabic.
 */
export function NoiseRuler({ m, threshold, extent, label }: NoiseRulerProps) {
  const { t, lang, measurement, unit } = useText();
  const half = extent ?? Math.max(Math.abs(m.value) + m.uncertainty, threshold) * 1.15;
  const pos = (v: number) => 50 + (Math.max(-half, Math.min(half, v)) / half) * 48;
  const clears = Math.abs(m.value) - m.uncertainty > threshold;
  const lo = pos(m.value - m.uncertainty);
  const hi = pos(m.value + m.uncertainty);
  const desc = t("ruler.desc", { label, value: measurement(m).text, threshold: isolate(`±${formatNumber(threshold, lang)} ${unit(m.unit)}`) });

  return (
    <div dir="ltr" role="img" aria-label={desc} className="relative h-4 w-full">
      <div className="absolute inset-x-[2%] top-1/2 h-px bg-line-strong" />
      <div className="absolute inset-y-0.5 bg-[var(--noise-band)]" style={{ left: pos(-threshold) + "%", width: pos(threshold) - pos(-threshold) + "%" }} />
      <div className="absolute inset-y-0 left-1/2 w-px bg-muted" />
      <div className="absolute top-1/2 h-0.5 -translate-y-1/2 bg-ink" style={{ left: lo + "%", width: Math.max(0.5, hi - lo) + "%" }} />
      <div
        className={"absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-ink " + (clears ? "bg-accent" : "bg-surface")}
        style={{ left: pos(m.value) + "%" }}
      />
    </div>
  );
}
