import { useCallback } from "react";
import { useTranslation } from "react-i18next";
import type { Lang, Localized, Measurement, TemplateParam, TemplatedText } from "@/api/contract";
import { formatDate, formatNumber } from "./format";
import { isLang } from "./index";

export function useLang(): Lang {
  const { i18n } = useTranslation();
  return isLang(i18n.language) ? i18n.language : "fr";
}

const LRI = "⁦";
const PDI = "⁩";

function isMeasurement(p: TemplateParam): p is Measurement {
  return typeof p === "object" && "value" in p && "uncertainty" in p;
}

/**
 * Text helpers bound to the page language.
 *
 * `text()` renders the API's prose (TemplatedText). A template id known to this
 * interface (src/i18n/templates, ids such as "step.classify") is rendered from
 * the catalogue with the API's parameters, numbers formatted here but never
 * computed. Otherwise the backend's own text in the page language is used (the
 * backend writes "backend.*" texts in FR, EN and AR). If neither exists, an
 * explicit marker is shown: never another language, never a guess.
 */
export function useText() {
  const { t, i18n } = useTranslation();
  const lang = useLang();

  const param = useCallback(
    (p: TemplateParam): string => {
      if (typeof p === "string") return p;
      if (typeof p === "number") return LRI + formatNumber(p, lang) + PDI;
      if (isMeasurement(p)) {
        const unit = t(`unit.${p.unit}`);
        const number = p.uncertainty === 0 ? formatNumber(p.value, lang) : `${formatNumber(p.value, lang)} ± ${formatNumber(p.uncertainty, lang)}`;
        return `${LRI}${number}${PDI}${unit ? ` ${unit}` : ""}`;
      }
      if ("date" in p) return formatDate(p.date, lang);
      if ("term" in p) return t(p.term, { ns: "term", keySeparator: false, nsSeparator: false, defaultValue: p.term });
      return p.localized[lang] ?? p.localized.fr ?? p.localized.en ?? "";
    },
    [lang, t],
  );

  const text = useCallback(
    (tt: TemplatedText): string => {
      const values: Record<string, unknown> = {};
      for (const [key, value] of Object.entries(tt.params)) values[key] = key === "count" && typeof value === "number" ? value : param(value);
      const options = { ns: "tpl", keySeparator: false as const, nsSeparator: false as const, ...values };
      if (i18n.exists(tt.template, options)) return t(tt.template, options) as string;
      return tt.text?.[lang] ?? t("errors.untranslated", { id: tt.template });
    },
    [i18n, lang, param, t],
  );

  const localized = useCallback((value: Localized) => value[lang], [lang]);

  return { t, lang, text, localized, param };
}
