import { useLayoutEffect } from "react";
import { I18nextProvider, useTranslation } from "react-i18next";
import { Link, Navigate, useParams, useRoutes, type RouteObject } from "react-router-dom";
import { applyDocumentLang, i18nFor, isLang, preferredLang, type Lang } from "@/i18n";
import { StatusPage } from "@/features/status/StatusPage";
import { AppShell } from "./AppShell";
import { useDocumentTitle } from "./useDocumentTitle";
import "./pages.css";

/** The URL is the only source of the language: it picks the i18n instance and <html lang dir>. */
function LangLayout() {
  const { lang } = useParams();
  // "/foo/…" is not a language: the shell speaks the visitor's language and LangGate shows "not found".
  const current: Lang = isLang(lang) ? lang : preferredLang();

  useLayoutEffect(() => applyDocumentLang(current), [current]);

  return (
    <I18nextProvider i18n={i18nFor[current]}>
      <AppShell lang={current} />
    </I18nextProvider>
  );
}

function Pending({ titleKey }: { titleKey: string }) {
  const { t } = useTranslation();
  const title = t(titleKey);
  useDocumentTitle(title);
  return (
    <section className="page">
      <h1>{title}</h1>
      <p className="page-lede">{t("pending.body")}</p>
    </section>
  );
}

export function NotFound() {
  const { t, i18n: instance } = useTranslation();
  useDocumentTitle(t("notFound.title"));
  return (
    <section className="page">
      <h1>{t("notFound.title")}</h1>
      <p className="page-lede">{t("notFound.body")}</p>
      <p>
        <Link to={`/${instance.language}/`}>{t("notFound.back")}</Link>
      </p>
    </section>
  );
}

function RootRedirect() {
  return <Navigate to={`/${preferredLang()}/`} replace />;
}

function LangGate({ children }: { children: React.ReactNode }) {
  const { lang } = useParams();
  return isLang(lang) ? <>{children}</> : <NotFound />;
}

export const routes: RouteObject[] = [
  { path: "/", element: <RootRedirect /> },
  {
    path: "/:lang",
    element: <LangLayout />,
    children: [
      { index: true, element: <LangGate><Pending titleKey="nav.cases" /></LangGate> },
      { path: "ask", element: <LangGate><Pending titleKey="nav.ask" /></LangGate> },
      { path: "library", element: <LangGate><Pending titleKey="nav.library" /></LangGate> },
      { path: "watches", element: <LangGate><Pending titleKey="nav.watches" /></LangGate> },
      { path: "status", element: <LangGate><StatusPage /></LangGate> },
      { path: "*", element: <NotFound /> },
    ],
  },
];

/** Plain (non-data) router: data loading is TanStack Query's job, not the router's. */
export function AppRoutes() {
  return useRoutes(routes);
}
