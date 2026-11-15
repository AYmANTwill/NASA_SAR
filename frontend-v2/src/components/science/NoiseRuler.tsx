import type { Measurement } from "@/api/contract";
import { useText } from "@/i18n/useText";

/** Geometry only: no new measured number or detection is derived from this picture. */
export function NoiseRuler({ measurement, noise }: { measurement: Measurement; noise: number }) {
  const { t } = useText();
  const sigma = measurement.uncertainty / measurement.sigma;
  const extent = Math.max(Math.abs(measurement.value) + sigma, Math.abs(noise));
  const x = (value: number) => extent ? 160 + value / extent * 148 : 160;
  return <svg className="noise-ruler" viewBox="0 0 320 36" role="img" aria-label={t("parity.noiseRuler")}>
    <rect x={x(-Math.abs(noise))} y="5" width={x(Math.abs(noise)) - x(-Math.abs(noise))} height="26" fill="var(--sea)" />
    <path d="M8 18H312 M160 5V31" stroke="var(--coast)" />
    <path d={`M${x(measurement.value - measurement.uncertainty / measurement.sigma)} 18H${x(measurement.value + measurement.uncertainty / measurement.sigma)}`} stroke="var(--ink)" strokeWidth="3" />
    <circle cx={x(measurement.value)} cy="18" r="5" fill="var(--ink)" />
  </svg>;
}
