import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { LANGS, type Lang } from "@/api/contract";
import ar from "./locales/ar.json";
import en from "./locales/en.json";
import fr from "./locales/fr.json";
import tplAr from "./templates/ar.json";
import tplEn from "./templates/en.json";
import tplFr from "./templates/fr.json";

export { LANGS, type Lang };

export const DEFAULT_LANG: Lang = "fr";

export const DIR: Record<Lang, "ltr" | "rtl"> = { fr: "ltr", en: "ltr", ar: "rtl" };

/** Each language is named in its own language in the switcher. */
export const LANG_NAMES: Record<Lang, string> = { fr: "Français", en: "English", ar: "العربية" };

export function isLang(value: string | undefined): value is Lang {
  return value !== undefined && (LANGS as readonly string[]).includes(value);
}

/** The language a visitor gets at "/": the first browser preference we support. */
export function preferredLang(languages: readonly string[] = navigator.languages ?? []): Lang {
  for (const tag of languages) {
    const base = tag.toLowerCase().split("-")[0];
    if (isLang(base)) return base;
  }
  return DEFAULT_LANG;
}

/** The URL is the single source of the language; this keeps <html lang dir> in step with it. */
export function applyDocumentLang(lang: Lang): void {
  document.documentElement.lang = lang;
  document.documentElement.dir = DIR[lang];
}

/** The language segment of a path ("/ar/cases/x" → "ar"), or null. */
export function langFromPath(pathname: string): Lang | null {
  const first = pathname.split("/")[1];
  return isLang(first) ? first : null;
}

/** The same page in another language: only the first path segment changes. */
export function pathInLang(pathname: string, lang: Lang): string {
  const rest = langFromPath(pathname) ? pathname.split("/").slice(2).join("/") : "";
  return `/${lang}/${rest}`;
}

void i18n.use(initReactI18next).init({
  // "tpl" and "term" hold the API's template ids (keys with dots, read with keySeparator: false).
  resources: {
    fr: { translation: fr, ...tplFr },
    en: { translation: en, ...tplEn },
    ar: { translation: ar, ...tplAr },
  },
  ns: ["translation", "tpl", "term"],
  defaultNS: "translation",
  lng: DEFAULT_LANG,
  fallbackLng: false,
  supportedLngs: [...LANGS],
  interpolation: { escapeValue: false },
  returnNull: false,
  initImmediate: false,
});

/**
 * One fixed instance per language. The page under /ar/ renders with the Arabic
 * instance from its first frame: no global language switch, no flash of
 * another language, and two languages can be rendered side by side.
 */
export const i18nFor: Record<Lang, typeof i18n> = {
  fr: i18n.cloneInstance({ lng: "fr", initImmediate: false }),
  en: i18n.cloneInstance({ lng: "en", initImmediate: false }),
  ar: i18n.cloneInstance({ lng: "ar", initImmediate: false }),
};

export default i18n;
