import { useCallback } from "react";
import { useTranslation } from "react-i18next";
import type { Lang, Localized, TemplatedText } from "@/api/contract";
import { isLang } from "./index";

export function useLang(): Lang {
  const { i18n } = useTranslation();
  return isLang(i18n.language) ? i18n.language : "fr";
}

/**
 * Backend prose. The backend writes every text in FR, EN and AR (`text`), with
 * its numbers already in it; the interface shows the page language's version.
 * If that language is missing, an explicit marker is shown: never another
 * language, never a guess. (A template catalogue in the interface is only
 * needed if the backend ever sends a template without its text.)
 */
export function useText() {
  const { t } = useTranslation();
  const lang = useLang();

  const text = useCallback(
    (tt: TemplatedText): string => tt.text?.[lang] ?? t("errors.untranslated", { id: tt.template }),
    [lang, t],
  );

  const localized = useCallback((value: Localized) => value[lang], [lang]);

  return { t, lang, text, localized };
}
