import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import { LANGS, type Lang } from "@/api/contract";
import { formatNumber } from "@/lib/format";
import ar from "./locales/ar.json";
import en from "./locales/en.json";
import fr from "./locales/fr.json";

type Locale = typeof fr;

/** tpl and term hold keys containing dots, so they live in flat namespaces. */
function split(resource: Locale) {
  const { tpl, term, ...translation } = resource;
  return { translation, tpl, term };
}

const STORAGE_KEY = "nisar-pulse-lang";

export const DIR: Record<Lang, "ltr" | "rtl"> = { fr: "ltr", en: "ltr", ar: "rtl" };

function initialLang(): Lang {
  try {
    const fromUrl = new URLSearchParams(window.location.search).get("lang");
    if (fromUrl && (LANGS as readonly string[]).includes(fromUrl)) return fromUrl as Lang;
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored && (LANGS as readonly string[]).includes(stored)) return stored as Lang;
  } catch {
    /* storage unavailable */
  }
  return "fr";
}

function applyDocument(lang: Lang) {
  document.documentElement.lang = lang;
  document.documentElement.dir = DIR[lang];
}

void i18n.use(initReactI18next).init({
  resources: { fr: split(fr), ar: split(ar as Locale), en: split(en as Locale) },
  lng: initialLang(),
  fallbackLng: "fr",
  supportedLngs: [...LANGS],
  ns: ["translation", "tpl", "term"],
  defaultNS: "translation",
  interpolation: { escapeValue: false },
  returnNull: false,
});

i18n.services.formatter?.add("number", (value: unknown, lng: string | undefined) =>
  typeof value === "number" ? formatNumber(value, (lng as Lang) ?? "fr", 0) : String(value),
);

applyDocument(i18n.language as Lang);
i18n.on("languageChanged", (lng) => {
  applyDocument(lng as Lang);
  try {
    window.localStorage.setItem(STORAGE_KEY, lng);
  } catch {
    /* storage unavailable */
  }
});

export default i18n;
