export function formatNumber(value: number, locale = "en", digits = 0) {
  return new Intl.NumberFormat(locale, {
    maximumFractionDigits: digits,
  }).format(value);
}
export function formatDate(date: string, locale = "en", short = false) {
  return new Date(date + "T12:00:00Z").toLocaleDateString(locale, {
    month: "short",
    day: "2-digit",
    ...(!short ? { year: "numeric" } : {}),
  });
}
export const reducedMotion = () =>
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;
