import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useDemo } from "@/demo/DemoContext";
import { LANGS, LANG_NAMES, pathInLang, type Lang } from "@/i18n";
import { formatDate } from "@/i18n/format";
import { PageBoundary } from "@/components/PageBoundary";
import "./AppShell.css";

const SECTIONS = [
  { to: "", key: "nav.cases", end: true },
  { to: "discover", key: "nav.discover", end: false },
  { to: "ask", key: "nav.ask", end: false },
  { to: "library", key: "nav.library", end: false },
  { to: "watches", key: "nav.watches", end: false },
  { to: "proof", key: "nav.proof", end: false },
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
  const demo = useDemo();
  const [menu, setMenu] = useState(false);
  const [presentation, setPresentation] = useState(false);
  const [savedData, setSavedData] = useState(false);
  useEffect(() => { const update = () => setSavedData(true); window.addEventListener("nisar-cache-fallback", update); return () => window.removeEventListener("nisar-cache-fallback", update); }, []);
  useEffect(() => {
    const toggle = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() !== "p" || event.ctrlKey || event.metaKey || event.altKey || (event.target instanceof HTMLElement && event.target.closest("input, textarea, select, [contenteditable=true]"))) return;
      setPresentation((value) => !value);
    };
    window.addEventListener("keydown", toggle);
    return () => window.removeEventListener("keydown", toggle);
  }, []);
  useEffect(() => setMenu(false), [pathname]);

  return (
    <div className={`app-workspace${presentation ? " is-presenting" : ""}`}>
      <a className="skip-link" href="#main">
        {t("shell.skip")}
      </a>
      <header className={`shell-header${menu ? " menu-open" : ""}`}>
        <Link className="shell-brand" to={`/${lang}/`} lang="en" dir="ltr">
          <svg viewBox="0 0 40 40" width="38" height="38" aria-hidden="true"><circle cx="20" cy="20" r="16" fill="none" stroke="currentColor" /><ellipse cx="20" cy="20" rx="8" ry="17" fill="none" stroke="currentColor" transform="rotate(45 20 20)" /><circle cx="20" cy="20" r="3" fill="currentColor" /></svg>
          <span>{t("app.name")}</span>
        </Link>
        <button type="button" className="menu-toggle" aria-expanded={menu} aria-controls="workspace-navigation" onClick={() => setMenu((value) => !value)}>{t("parity.menu")}</button>
        <nav id="workspace-navigation" className="shell-nav" aria-label={t("shell.navLabel")}>
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
        <p className="shell-purpose">{t("app.tagline")}</p>
        <button type="button" className="presentation-toggle" onClick={() => setPresentation(true)}>{t("parity.presentation")}</button>
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
      <div className="shell-content">
      {presentation && <button className="button presentation-exit" type="button" onClick={() => setPresentation(false)}>{t("parity.exitPresentation")}</button>}
      {demo && (
        <p className={`shell-demo shell-demo-${demo.kind}`} role="note">
          {t(`demo.banner.${demo.kind}`, { date: formatDate(demo.generatedAt, lang) })}
        </p>
      )}
      {!online && !demo && (
        <p className="shell-offline" role="status">
          {t("shell.offline")}
        </p>
      )}
      {online && savedData && !demo && <p className="shell-offline" role="status">{t("parity.cachedData")}</p>}
      <main id="main" className="shell-main" tabIndex={-1}>
        <PageBoundary key={pathname}><Outlet /></PageBoundary>
      </main>
      <footer className="shell-footer">{t("app.tagline")}</footer>
      </div>
    </div>
  );
}
