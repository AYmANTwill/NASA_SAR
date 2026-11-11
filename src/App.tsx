import { lazy, Suspense, useEffect, useState, useMemo, useRef } from "react";
import { MotionConfig } from "framer-motion";
import {
  Activity,
  ArrowUpRight,
  Bell,
  BookOpen,
  ChevronRight,
  CircleHelp,
  Globe2,
  Pause,
  ScanLine,
  Share2,
  X,
} from "lucide-react";
import { loadAlerts, loadCases, loadCaseSeries, isMock } from "./data/loader";
import type { Alert, CaseStudy, Sample } from "./data/types";
import { useStore } from "./store/useStore";
import { resolveSite } from "./data/layers";
import { useI18n, caseText, translate } from "./lib/i18n";
import { deriveAlerts, type Observation } from "./features/alerts/rules";
import Overlays from "./features/about/Overlays";
const MapScene = lazy(() => import("./components/MapScene"));
const Intro = lazy(() => import("./features/intro/Intro"));
const Dashboard = lazy(() => import("./features/dashboard/Dashboard"));
const Compare = lazy(() => import("./features/compare/Compare"));
export default function App() {
  const [cases, updateCases] = useState<CaseStudy[]>([]),
    [storedAlerts, updateAlerts] = useState<Alert[]>([]),
    [series, updateSeries] = useState<Sample[]>([]),
    [error, setError] = useState(""),
    [toast, setToast] = useState("");
  const state = useStore(),
    {
      caseId,
      screen,
      date,
      playing,
      speed,
      tour,
      locale,
      compare,
      set,
      selectCase,
    } = state;
  const {t}=useI18n();
  const baseCase=cases.find(c=>c.id===caseId)??cases[0];
  const current=useMemo(()=>baseCase?resolveSite(baseCase,state.siteId):undefined,[baseCase,state.siteId]);
  const [observations,setObservations]=useState<Observation[]>([]);
  const alerts=useMemo(()=>[...storedAlerts,...(isMock?deriveAlerts(cases,observations,state.thresholds):[])],[storedAlerts,cases,observations,state.thresholds]);
  const previousAlertIds=useRef<Set<string>|null>(null);
  useEffect(()=>{
    if(!isMock||!cases.length)return;
    const controller=new AbortController();
    const targets=cases.flatMap(c=>[c,...(c.sites??[]).filter(s=>s.dataPath!==c.id).map(site=>resolveSite(c,site.id))]);
    Promise.all(targets.map(async c=>({caseId:c.id,siteId:c.siteId,center:c.center,series:await loadCaseSeries(c,controller.signal)}))).then(setObservations).catch(e=>{if(e.name!=="AbortError")setError(e.message);});
    return()=>controller.abort();
  },[cases]);
  useEffect(()=>{
    if(!observations.length)return;
    const next=new Set(alerts.map(a=>a.id));
    const fresh=previousAlertIds.current?alerts.filter(a=>!previousAlertIds.current!.has(a.id)):[];
    if(fresh.length)setToast(translate("New simulated alerts",useStore.getState().locale)+" ? "+fresh.length);
    previousAlertIds.current=next;
  },[alerts,observations]);

  useEffect(() => {
    Promise.all([loadCases(), loadAlerts()])
      .then(([c, a]) => {
        updateCases(c);
        updateAlerts(a);
        const query = new URLSearchParams(location.search),
          id = query.get("case");
        if (id && c.some((v) => v.id === id)) {
          selectCase(id);
          const requestedSite=query.get("site");
          if(c.find(v=>v.id===id)?.sites?.some(s=>s.id===requestedSite))set({siteId:requestedSite});
          const index = Number(query.get("date") ?? 7);
          set({
            date: Math.max(
              0,
              Math.min(
                c.find((v) => v.id === id)!.dates.length - 1,
                Number.isFinite(index) ? index : 7,
              ),
            ),
          });
        } else if (!c.some((v) => v.id === useStore.getState().caseId))
          set({ caseId: c[0].id });
      })
      .catch((e) => setError(e.message));
  }, [selectCase, set]);
  useEffect(() => {
    if (!current) return;
    const controller = new AbortController();
    updateSeries([]);
    loadCaseSeries(current, controller.signal)
      .then(updateSeries)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => controller.abort();
  }, [current]);
  useEffect(() => {
    if (!playing || !current || screen === "intro") return;
    const timer = window.setInterval(
      () =>
        set({ date: (useStore.getState().date + 1) % current.dates.length }),
      1800 / speed,
    );
    return () => clearInterval(timer);
  }, [playing, current, speed, screen, set]);
  useEffect(() => {
    if (!tour || !cases.length) return;
    let step = 0;
    setToast("Guided tour · five signals, one changing planet");
    const timer = window.setInterval(() => {
      step++;
      if (step >= cases.length) {
        set({ tour: false, playing: false });
        setToast(translate("Tour complete. Keep exploring.",useStore.getState().locale));
        clearInterval(timer);
        return;
      }
      selectCase(cases[step].id);
      set({
        playing: true,
        layers: {
          ...useStore.getState().layers,
          gunw: [0,4,6].includes(step) ? 0.8 : 0,
          gcov: [0,4,6].includes(step) ? 0 : 0.8,
          ndvi:step===7?.65:0,
          events: step === 0 ? 1 : 0,
          fires: step === 3 ? 0.8 : 0,
          floodExtent: step === 2 ? 0.65 : 0,
        },
      });
      setToast(caseText(cases[step],"subtitle",useStore.getState().locale));
    }, 13000);
    return () => clearInterval(timer);
  }, [tour, cases, selectCase, set]);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (
        (e.target as HTMLElement).closest(
          'input,select,textarea,button,[role="dialog"]',
        ) ||
        e.ctrlKey ||
        e.metaKey ||
        e.altKey
      )
        return;
      const s = useStore.getState();
      if (e.key === "?") {
        set({ modal: "shortcuts" });
        return;
      }
      if (s.modal) return;
      if (/^[1-8]$/.test(e.key) && cases[Number(e.key) - 1])
        selectCase(cases[Number(e.key) - 1].id);
      if (e.key.toLowerCase() === "l")
        set({
          sheet: s.sheet === "layers" ? null : "layers",
          layersOpen: !s.layersOpen,
        });
      if (s.screen === "intro") return;
      if (e.code === "Space") {
        e.preventDefault();
        set({ playing: !s.playing });
      }
      if (e.key.toLowerCase() === "c") set({ compare: !s.compare });
      if (e.key === "ArrowRight")
        set({ date: Math.min((current?.dates.length ?? 8) - 1, s.date + 1) });
      if (e.key === "ArrowLeft") set({ date: Math.max(0, s.date - 1) });
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [cases, current, set, selectCase]);
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 4000);
    return () => clearTimeout(timer);
  }, [toast]);
  function exportSnapshot() {
    if (!current) return;
    const blob = new Blob(
      [
        JSON.stringify(
          {
            case: current,
            selectedAcquisition: current.dates[date],
            sample: series[date],
            layers: state.layers,
            simulated: isMock,
          },
          null,
          2,
        ),
      ],
      { type: "application/json" },
    );
    const url = URL.createObjectURL(blob),
      a = document.createElement("a");
    a.href = url;
    a.download =
      "nisar-pulse-" + current.id + "-" + current.dates[date] + ".json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    setToast(t("Analysis snapshot exported"));
  }
  async function share() {
    const url = new URL(location.href);
    url.searchParams.set("case", caseId);
    url.searchParams.set("date", String(date));
    if(state.siteId)url.searchParams.set("site",state.siteId);else url.searchParams.delete("site");
    try {
      await navigator.clipboard.writeText(url.toString());
      setToast(t("View link copied"));
    } catch {
      setToast(t("Clipboard unavailable. Use Export to save this view."));
    }
  }
  if (error && !cases.length)
    return (
      <div className="loading-screen">
        <Activity size={40} />
        <h1>{t("Unable to load the observatory")}</h1>
        <p>{error}</p>
        <button className="primary" onClick={() => location.reload()}>{t("Try again")}</button>
      </div>
    );
  if (!current)
    return (
      <div className="loading-screen">
        <span className="radar-loader" />
        <h1>NISAR Pulse</h1>
        <p>{t("Acquiring a planetary perspective…")}</p>
      </div>
    );
  return (
    <MotionConfig reducedMotion="user">
      <div
        className={"app " + screen + (compare ? " comparing" : "")}
        style={
          {
            "--accent": screen === "intro" ? "#82b9a4" : current.accentColor,
            "--accent-soft":
              (screen === "intro" ? "#82b9a4" : current.accentColor) + "18",
          } as React.CSSProperties
        }
      >
        <div className="star-field" />
        <div className="atmosphere" />
        <Suspense fallback={<div className="map-loading">{t("Preparing map…")}</div>}>
          <MapScene cases={cases} current={current} series={series} />
        </Suspense>
        <div className="map-vignette" />
        <header className="topbar">
          <button
            className="brand"
            aria-label={t("NISAR Pulse home")}
            onClick={() =>
              set({
                screen: "intro",
                playing: false,
                tour: false,
                compare: false,
              })
            }
          >
            <span className="brand-symbol">
              <Activity size={22} />
            </span>
            <span>
              NISAR <b>Pulse</b>
              <small>{t("EARTH SURFACE OBSERVATORY")}</small>
            </span>
          </button>
          {screen === "intro" ? (
            <nav className="landing-nav">
              <span className="active-nav">{t("Observatory")}</span>
              <button onClick={() => set({ modal: "about" })}>{t("The mission")}<ArrowUpRight size={12} />
              </button>
            </nav>
          ) : (
            <div className="breadcrumb">
              <button
                onClick={() =>
                  set({
                    screen: "intro",
                    playing: false,
                    tour: false,
                    compare: false,
                  })
                }
              >
                <Globe2 size={13} />{t("Globe")}</button>
              <ChevronRight size={12} />
              <span>{caseText(current,"name",locale)}</span>
            </div>
          )}
          <div className="top-actions">
            <span className="data-badge">
              <span className="live-dot" />
              {t(isMock ? "DEMO DATA" : "EXPORTED DATA")}
            </span>
            {screen === "dashboard" && (
              <>
                <button
                  className={"top-button " + (compare ? "active" : "")}
                  aria-pressed={compare}
                  onClick={() => set({ compare: !compare })}
                >
                  <ScanLine size={15} />
                  <span>{locale === "fr" ? "Comparer" : "Compare"}</span>
                </button>
                <button
                  className="icon-button notification"
                  aria-label={t("Open alerts")+" ("+alerts.length+")"}
                  onClick={() => set({ modal: "alerts" })}
                >
                  <Bell size={17} />
                  <i>{alerts.length}</i>
                </button>
                <button
                  className="icon-button desktop-only"
                  title={t("Copy view link")}
                  aria-label={t("Copy view link")}
                  onClick={share}
                >
                  <Share2 size={16} />
                </button>
                <button
                  className="top-button export-button"
                  onClick={exportSnapshot}
                >
                  <span>{t("Export")}</span>
                  <ArrowUpRight size={15} />
                </button>
              </>
            )}
            <button
              className="language"
              aria-label={t("Change language")}
              onClick={() => set({ locale: locale === "en" ? "fr" : "en" })}
            >
              {locale.toUpperCase()}
            </button>
            <button
              className="icon-button"
              aria-label={t("About the observatory")}
              onClick={() => set({ modal: "about" })}
            >
              <CircleHelp size={17} />
            </button>
          </div>
        </header>
        <Suspense
          fallback={<div className="map-loading">{t("Preparing observatory…")}</div>}
        >
          {screen === "intro" ? (
            <Intro cases={cases} />
          ) : (
            <Dashboard cases={cases} current={current} series={series} />
          )}
        </Suspense>
        {compare && screen === "dashboard" && (
          <Suspense>
            <Compare current={current} />
          </Suspense>
        )}
        {screen === "dashboard" && (
          <div className="dashboard-title">
            <span className="eyebrow">{t("SURFACE CHANGE INTELLIGENCE")}</span>
            <h1>{caseText(current,"subtitle",locale)}</h1>
            <span className="view-badge">
              <span className="live-dot" />{t("L-BAND SAR")}<i />{" "}
              {t(isMock ? "SIMULATION" : "EXPORTED OBSERVATIONS")}
            </span>
          </div>
        )}
        {tour && (
          <div className="tour-banner glass">
            <span className="live-dot" />{t("GUIDED TOUR")}{" "}
            <span>{cases.findIndex((c) => c.id === caseId) + 1} / {cases.length}</span>
            <button onClick={() => set({ tour: false, playing: false })}>
              <Pause size={13} />{t("End tour")}</button>
          </div>
        )}
        {toast && (
          <div className="toast glass" role="status">
            {toast}
            <button
              aria-label={t("Dismiss notification")}
              onClick={() => setToast("")}
            >
              <X size={14} />
            </button>
          </div>
        )}
        {error && (
          <div className="toast glass" role="alert">
            {error}
            <button onClick={() => setError("")} aria-label={t("Dismiss error")}>
              <X size={14} />
            </button>
          </div>
        )}
        <button
          className="shortcut-help"
          onClick={() => set({ modal: "shortcuts" })}
        >
          <BookOpen size={12} />
          <span>{t("Keyboard shortcuts")}</span>
          <kbd>?</kbd>
        </button>
        <Overlays cases={cases} alerts={alerts} />
      </div>
    </MotionConfig>
  );
}
