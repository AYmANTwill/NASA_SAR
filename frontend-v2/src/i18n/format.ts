import type { Lang } from "@/api/contract";

/**
 * Number and date formatting. Nothing here creates a value: numbers are printed
 * as the API sent them, with the language's separators. Arabic keeps Western
 * digits (as written in Morocco) and every number is isolated left to right.
 */
const LOCALE: Record<Lang, string> = { fr: "fr-FR", en: "en-GB", ar: "ar-MA-u-nu-latn" };

/** Enough fraction digits to print any value the API sends without rounding it away. */
const MAX_FRACTION_DIGITS = 6;

export function formatNumber(value: number, lang: Lang): string {
  return new Intl.NumberFormat(LOCALE[lang], { maximumFractionDigits: MAX_FRACTION_DIGITS, useGrouping: true }).format(value);
}

const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

/** "2026-10-09" → 9 Oct 2026; a date-time also gets its UTC time ("17:56 UTC"). */
export function formatDate(iso: string, lang: Lang): string {
  const date = new Date(DATE_ONLY.test(iso) ? `${iso}T00:00:00Z` : iso);
  if (Number.isNaN(date.getTime())) return iso;
  const day = new Intl.DateTimeFormat(LOCALE[lang], { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).format(date);
  if (DATE_ONLY.test(iso) || isMidnightUtc(iso)) return day;
  const time = new Intl.DateTimeFormat(LOCALE[lang], { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: "UTC" }).format(date);
  // In Arabic the Latin "17:56 UTC" is isolated (LRI…PDI) so the bidi algorithm cannot reorder it.
  return lang === "ar" ? `${day}، ⁦${time} UTC⁩` : `${day}, ${time} UTC`;
}

/** Day-precision events are sent as T00:00:00Z: showing "00:00" would invent a time. */
function isMidnightUtc(iso: string): boolean {
  return /T00:00(:00(\.0+)?)?(Z|\+00:00)$/.test(iso);
}
