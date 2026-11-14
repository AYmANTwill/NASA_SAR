import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { LANGS, LANG_NAMES, pathInLang, type Lang } from "@/i18n";
import "./AppShell.css";

const SECTIONS = [
  { to: "", key: "nav.cases", end: true },
  { to: "ask", key: "nav.ask", end: false },
  { to: "library", key: "nav.library", end: false },
  { to: "watches", key: "nav.watches", end: false },
  { to: "status", key: "nav.status", end: false },
] as const;

/** Narrow screens show each language's own short name; the full name stays the accessible name. */
const LANG_SHORT: Record<Lang, string> = { fr: "FR", en: "EN", ar: "ع" };

function useOnline(): boolean {
  const [online, setOnline] = useState(() => navigator.onLine);
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  return online;
}

export function AppShell({ lang }: { lang: Lang }) {
  const { t } = useTranslation();
  const { pathname, search, hash } = useLocation();
  const online = useOnline();

  return (
    <>
      <a className="skip-link" href="#main">
        {t("shell.skip")}
      </a>
      <header className="shell-header">
        <Link className="shell-brand" to={`/${lang}/`} lang="en" dir="ltr">
          {t("app.name")}
        </Link>
        <nav className="shell-nav" aria-label={t("shell.navLabel")}>
          <ul>
            {SECTIONS.map((s) => (
              <li key={s.key}>
                <NavLink to={`/${lang}/${s.to}`} end={s.end}>
                  {t(s.key)}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <nav className="shell-langs" aria-label={t("shell.langLabel")}>
          <ul>
            {LANGS.map((l) => (
              <li key={l}>
                <Link
                  to={pathInLang(pathname, l) + search + hash}
                  lang={l}
                  hrefLang={l}
                  aria-current={l === lang ? "true" : undefined}
                >
                  <span className="lang-long">{LANG_NAMES[l]}</span>
                  <span className="lang-short" aria-hidden="true">
                    {LANG_SHORT[l]}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </header>
      {!online && (
        <p className="shell-offline" role="status">
          {t("shell.offline")}
        </p>
      )}
      <main id="main" className="shell-main" tabIndex={-1}>
        <Outlet />
      </main>
    </>
  );
}
