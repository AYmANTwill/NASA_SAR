import { useText } from "@/i18n/useText";
import { daysUntil } from "@/lib/dates";
import { formatNumber } from "@/lib/format";

/**
 * Orbit clock: the ring is the interval between the last pass and the next one
 * (both from the API, so the repeat cycle is never assumed); the satellite sits
 * where today falls in that interval. On mount it flies from the last pass to today.
 */
export function OrbitClock({ lastPass, nextPass }: { lastPass: string; nextPass: string }) {
  const { t, lang } = useText();
  const cycle = daysUntil(nextPass) - daysUntil(lastPass);
  if (!(cycle > 0)) return null;
  const elapsed = Math.min(cycle, Math.max(0, -daysUntil(lastPass)));
  const angle = (elapsed / cycle) * 360;
  const r = 26;
  const circ = 2 * Math.PI * r;

  return (
    <svg
      viewBox="0 0 64 64"
      className="orbit-clock size-16 shrink-0"
      role="img"
      aria-label={t("watch.orbit", { elapsed: formatNumber(elapsed, lang, 0), cycle: formatNumber(cycle, lang, 0) })}
      style={{ ["--orbit-angle" as string]: `${angle}deg`, ["--orbit-dash" as string]: `${(elapsed / cycle) * circ}` }}
    >
      <circle cx="32" cy="32" r={r} fill="none" stroke="var(--line)" strokeWidth="3" />
      <circle
        cx="32"
        cy="32"
        r={r}
        fill="none"
        stroke="var(--accent)"
        strokeWidth="3"
        strokeLinecap="round"
        strokeDasharray={`${(elapsed / cycle) * circ} ${circ}`}
        transform="rotate(-90 32 32)"
        className="orbit-arc"
      />
      {/* next pass: tick at the top */}
      <path d="M32 2 V10" stroke="var(--ink)" strokeWidth="2" strokeLinecap="round" />
      {/* Earth */}
      <circle cx="32" cy="32" r="9" fill="var(--accent-soft)" stroke="var(--line-strong)" />
      <g className="orbit-sat" style={{ transformOrigin: "32px 32px" }}>
        <circle cx="32" cy={32 - r} r="4.5" fill="var(--ink)" stroke="#fff" strokeWidth="1.5" />
      </g>
    </svg>
  );
}
