import type { Lang, Measurement } from "@/api/contract";

/** Intl locale per UI language. Moroccan Arabic uses Western digits (ar-MA → latn). */
export const LOCALE: Record<Lang, string> = { fr: "fr-FR", ar: "ar-MA-u-nu-latn", en: "en-GB" };

const FSI = "⁨";
const PDI = "⁩";

/** Isolates a run of text so digits/signs keep their order inside RTL sentences. */
export const isolate = (text: string) => FSI + text + PDI;

export function formatNumber(value: number, lang: Lang, decimals?: number): string {
  const digits = decimals ?? (Number.isInteger(value) ? 0 : Math.abs(value) < 1 ? 2 : 1);
  return new Intl.NumberFormat(LOCALE[lang], { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
}

/**
 * Decimal places so the uncertainty keeps one significant figure (two when it
 * starts with 1), and the value is rounded to the same place.
 */
export function decimalsFor(uncertainty: number, value: number): number {
  if (!(uncertainty > 0)) {
    const abs = Math.abs(value);
    return Number.isInteger(value) ? 0 : abs < 1 ? 2 : 1;
  }
  const exponent = Math.floor(Math.log10(uncertainty));
  const leading = Math.floor(uncertainty / 10 ** exponent);
  const sig = leading === 1 ? 2 : 1;
  return Math.min(4, Math.max(0, sig - 1 - exponent));
}

export interface FormattedMeasurement {
  value: string;
  uncertainty: string;
  unit: string;
  /** Full isolated string, e.g. "−38 ± 5 mm/an". */
  text: string;
}

export function formatMeasurement(m: Measurement, lang: Lang, unitLabel: string): FormattedMeasurement {
  const decimals = decimalsFor(m.uncertainty, m.value);
  const value = formatNumber(m.value, lang, decimals).replace("-", "−");
  const uncertainty = formatNumber(m.uncertainty, lang, decimals);
  const core = `${value} ± ${uncertainty}`;
  return { value, uncertainty, unit: unitLabel, text: isolate(unitLabel ? `${core} ${unitLabel}` : core) };
}

const dateFormats = {
  long: { day: "numeric", month: "long", year: "numeric" },
  short: { day: "numeric", month: "short" },
  medium: { day: "numeric", month: "short", year: "numeric" },
} satisfies Record<string, Intl.DateTimeFormatOptions>;

export function formatDate(iso: string, lang: Lang, style: keyof typeof dateFormats = "long"): string {
  const date = iso.length === 10 ? new Date(iso + "T00:00:00Z") : new Date(iso);
  return new Intl.DateTimeFormat(LOCALE[lang], { ...dateFormats[style], timeZone: "UTC" }).format(date);
}

export function formatDateTime(iso: string, lang: Lang): string {
  return new Intl.DateTimeFormat(LOCALE[lang], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC", timeZoneName: "short" }).format(new Date(iso));
}

export function formatCoord(value: number, lang: Lang): string {
  return formatNumber(value, lang, 3);
}
