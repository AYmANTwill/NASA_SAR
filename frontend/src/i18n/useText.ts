import { useCallback, useMemo } from "react";
import { useTranslation } from "react-i18next";
import type { Lang, Measurement, TemplatedText, TemplateParam, Unit } from "@/api/contract";
import { formatDate, formatMeasurement, formatNumber, isolate } from "@/lib/format";

export function useLang(): Lang {
  const { i18n } = useTranslation();
  return (i18n.resolvedLanguage ?? i18n.language ?? "fr") as Lang;
}

function isMeasurement(p: TemplateParam): p is Measurement {
  return typeof p === "object" && "value" in p && "uncertainty" in p;
}

/**
 * Helpers bound to a language (the UI language by default): units,
 * measurements and templated backend prose. Pass `forLang` to render a
 * text in another language, e.g. the FR and AR notification previews.
 */
export function useText(forLang?: Lang) {
  const { t: tCurrent, i18n } = useTranslation();
  const current = useLang();
  const lang = forLang ?? current;
  const t = useMemo(() => (forLang ? i18n.getFixedT(forLang) : tCurrent), [forLang, i18n, tCurrent]);

  const unit = useCallback((u: Unit) => t(`unit.${u}`), [t]);

  const measurement = useCallback((m: Measurement) => formatMeasurement(m, lang, unit(m.unit)), [lang, unit]);

  const param = useCallback(
    (p: TemplateParam): string => {
      if (typeof p === "string") return p;
      if (typeof p === "number") return isolate(formatNumber(p, lang));
      if (isMeasurement(p)) return measurement(p).text;
      if ("date" in p) return formatDate(p.date, lang);
      if ("term" in p) return t(p.term, { ns: "term", keySeparator: false });
      return p.localized[lang] ?? p.localized.fr ?? p.localized.en ?? "";
    },
    [lang, measurement, t],
  );

  /** Renders backend prose; falls back to the per-language text, then to an explicit marker. */
  const text = useCallback(
    (tt: TemplatedText): string => {
      const values: Record<string, unknown> = {};
      for (const [key, value] of Object.entries(tt.params)) values[key] = key === "count" && typeof value === "number" ? value : param(value);
      const options = { ns: "tpl", keySeparator: false as const, lng: lang, ...values };
      if (i18n.exists(tt.template, options)) return t(tt.template, options) as string;
      return tt.text?.[lang] ?? t("errors.unknownTemplate", { id: tt.template });
    },
    [i18n, lang, param, t],
  );

  /** Localized place name. */
  const place = useCallback((loc: { name: string | null; name_i18n?: Partial<Record<Lang, string>> }) => loc.name_i18n?.[lang] ?? loc.name ?? "", [lang]);

  return { t, lang, unit, measurement, text, param, place };
}
