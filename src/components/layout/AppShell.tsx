import { useEffect, useRef } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CloudOff, FlaskConical } from "lucide-react";
import { API_MODE } from "@/api";
import { LANGS, type Lang } from "@/api/contract";
import { useDemoPrefetch, useOnline } from "@/api/queries";
import { useLang } from "@/i18n/useText";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", key: "cases", end: true },
  { to: "/discover", key: "discover", end: false },
  { to: "/investigate", key: "investigate", end: false },
  { to: "/watch", key: "watch", end: false },
  { to: "/library", key: "library", end: false },
  { to: "/proof", key: "proof", end: false, soon: true },
] as const;

const LANG_SHORT: Record<Lang, string> = { fr: "FR", ar: "ع", en: "EN" };

function Logo() {
  return (
    <svg viewBox="0 0 32 32" className="size-7 shrink-0" aria-hidden>
      <circle cx="16" cy="16" r="14" fill="none" stroke="var(--accent)" strokeWidth="2" />
      <path d="M5 17h6l2.5-7 4 13 3-9 1.5 3H27" fill="none" stroke="var(--ink)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

function LangSwitch() {
  const { t, i18n } = useTranslation();
  const lang = useLang();
  return (
    <div role="group" aria-label={t("lang.label")} className="flex rounded-md border border-line-strong p-0.5">
      {LANGS.map((l) => (
        <button
          key={l}
          type="button"
          lang={l}
          aria-pressed={lang === l}
          title={t(`lang.${l}`)}
          onClick={() => void i18n.changeLanguage(l)}
          className={cn("min-w-9 rounded-[3px] px-2 py-1 text-sm font-medium", lang === l ? "bg-ink text-white" : "text-ink-2 hover:bg-surface-2")}
        >
          <span>{LANG_SHORT[l]}</span>
          <span className="sr-only"> {t(`lang.${l}`)}</span>
        </button>
      ))}
    </div>
  );
}

export default function AppShell() {
  const { t } = useTranslation();
  const online = useOnline();
  useDemoPrefetch();
  const chrome = useRef<HTMLDivElement>(null);
  // Expose the sticky chrome height so full-height screens (map) can fill the rest.
  useEffect(() => {
    const el = chrome.current;
    if (!el) return;
    const update = () => document.documentElement.style.setProperty("--header-h", el.offsetHeight + "px");
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div className="flex min-h-dvh flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:start-2 focus:top-2 focus:z-50 focus:rounded-sm focus:bg-ink focus:px-3 focus:py-2 focus:text-white">
        {t("app.skip")}
      </a>
      <div ref={chrome} className="sticky top-0 z-30">
      {API_MODE === "fixtures" && (
        <div role="note" className="flex items-center justify-center gap-2 bg-[var(--level-yellow)] px-4 py-1.5 text-center text-sm text-[var(--level-yellow-ink)]">
          <FlaskConical className="size-4 shrink-0" aria-hidden />
          {t("status.fixtures")}
        </div>
      )}
      <header className="border-b border-line bg-surface/95 backdrop-blur-sm">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2.5">
          <NavLink to="/" className="flex items-center gap-2 rounded-sm">
            <Logo />
            <span className="leading-tight">
              <span className="block font-semibold">{t("app.name")}</span>
              <span className="block text-xs text-muted">{t("app.tagline")}</span>
            </span>
          </NavLink>
          <nav aria-label={t("nav.primary")} className="order-3 -mx-1 w-full overflow-x-auto md:order-none md:w-auto">
            <ul className="flex gap-1">
              {NAV.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.end}
                    className={({ isActive }) =>
                      cn("block whitespace-nowrap rounded-sm px-2.5 py-1.5 text-sm", isActive ? "bg-accent-soft font-medium text-accent" : "text-ink-2 hover:bg-surface-2 hover:text-ink")
                    }
                  >
                    {t(`nav.${item.key}`)}
                    {"soon" in item && API_MODE === "http" && (
                      <span className="ms-1.5 rounded-sm border border-line-strong px-1 py-px text-[0.6875rem] font-normal text-ink-2">{t("nav.soon")}</span>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
          <div className="ms-auto flex items-center gap-3">
            {!online && (
              <span role="status" title={t("status.offline")} className="flex items-center gap-1.5 rounded-sm border border-line-strong px-2 py-1 text-xs text-ink-2">
                <CloudOff className="size-3.5" aria-hidden />
                {t("status.offlineShort")}
                <span className="sr-only">{t("status.offline")}</span>
              </span>
            )}
            <LangSwitch />
          </div>
        </div>
      </header>
      </div>
      <main id="main" tabIndex={-1} className="flex flex-1 flex-col outline-none">
        <Outlet />
      </main>
    </div>
  );
}
