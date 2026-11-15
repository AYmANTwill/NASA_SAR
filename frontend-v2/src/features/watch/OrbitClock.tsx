import { formatDate } from "@/i18n/format";
import { useText } from "@/i18n/useText";

export function OrbitClock({ last, next }: { last: string | null; next: string }) {
  const { t, lang } = useText();
  const start = last ? Date.parse(last) : NaN, end = Date.parse(next);
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return null;
  const elapsed = Math.min(1, Math.max(0, (Date.now() - start) / (end - start)));
  return <svg className="orbit-clock" viewBox="0 0 64 64" role="img" aria-label={`${t("watch.nextPass")} ${formatDate(next, lang)}`} direction="ltr">
    <circle cx="32" cy="32" r="25" fill="none" stroke="var(--rule)" strokeWidth="3" />
    <circle cx="32" cy="32" r="25" fill="none" stroke="var(--ink)" strokeWidth="3" strokeDasharray={`${elapsed * 2 * Math.PI * 25} ${2 * Math.PI * 25}`} transform="rotate(-90 32 32)" />
    <circle cx="32" cy="32" r="8" fill="var(--sea)" stroke="var(--coast)" />
  </svg>;
}
