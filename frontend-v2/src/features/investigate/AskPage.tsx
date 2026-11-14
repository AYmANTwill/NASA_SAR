import { useQuery } from "@tanstack/react-query";
import { useId, useState, type FormEvent } from "react";
import { useApi } from "@/api/ApiProvider";
import type { Bounds } from "@/api/contract";
import { useDocumentTitle } from "@/app/useDocumentTitle";
import { ErrorPanel } from "@/components/ErrorPanel";
import { MapPanel } from "@/components/map/MapPanel";
import { formatNumber } from "@/i18n/format";
import { useText } from "@/i18n/useText";
import { AnswerView } from "./AnswerView";
import { StepList } from "./StepList";
import { useAsk } from "./useAsk";
import "./investigate.css";

/** The whole Earth: the picker starts with no place assumed. */
const WORLD: Bounds = [-180, -70, 180, 75];

type Point = { lat: number; lon: number };

export function AskPage() {
  const { t, lang } = useText();
  useDocumentTitle(t("nav.ask"));
  const api = useApi();
  const demo = useQuery({ queryKey: ["demo"], queryFn: ({ signal }) => api.demo(signal) });
  const { state, ask } = useAsk();
  const [question, setQuestion] = useState("");
  const [point, setPoint] = useState<Point | null>(null);
  const fieldId = useId();

  const suggestions = demo.data?.entries.flatMap((e) => e.questions.filter((q) => q.lang === lang).map((q) => q.text)) ?? [];
  const running = state.phase === "running";

  function submit(text: string, event?: FormEvent) {
    event?.preventDefault();
    const q = text.trim();
    if (!q || running) return;
    setQuestion(q);
    void ask({ question: q, lang, location: point });
  }

  return (
    <div className="case-view">
      <header className="cases-intro">
        <h1>{t("nav.ask")}</h1>
        <p className="page-lede">{t("ask.lede")}</p>
      </header>

      <div className="ask-layout">
        <form className="ask-form" onSubmit={(e) => submit(question, e)}>
          <label htmlFor={fieldId} className="ask-label">
            {t("ask.label")}
          </label>
          <textarea
            id={fieldId}
            className="ask-input"
            rows={3}
            dir="auto"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) submit(question, e);
            }}
            placeholder={t("ask.placeholder")}
          />
          <p className="ask-point" aria-live="polite">
            {point ? (
              <>
                {t("ask.pointChosen")}{" "}
                <bdi dir="ltr">
                  {formatNumber(Number(point.lat.toFixed(3)), lang)}, {formatNumber(Number(point.lon.toFixed(3)), lang)}
                </bdi>{" "}
                <button type="button" className="link-button" onClick={() => setPoint(null)}>
                  {t("ask.clearPoint")}
                </button>
              </>
            ) : (
              t("ask.noPoint")
            )}
          </p>
          <p>
            <button type="submit" className="button button-primary" disabled={running || question.trim() === ""}>
              {running ? t("ask.running") : t("ask.submit")}
            </button>
          </p>
          {suggestions.length > 0 && (
            <div className="ask-suggestions">
              <p className="ask-label">{t("ask.examples")}</p>
              <ul>
                {suggestions.map((s) => (
                  <li key={s}>
                    <button type="button" className="suggestion" dir="auto" disabled={running} onClick={() => submit(s)}>
                      {s}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </form>

        <MapPanel
          frame={WORLD}
          point={point ?? undefined}
          entries={[]}
          showArea={false}
          onPick={setPoint}
          label={t("ask.mapLabel")}
          emptyText={t("ask.mapHelp")}
        />
      </div>

      {state.phase !== "idle" && (
        <section className="ask-result" aria-labelledby="result-title" aria-busy={running}>
          <h2 id="result-title" className="visually-hidden">
            {t("ask.result")}
          </h2>
          {state.phase !== "done" && (
            <div className="ask-steps">
              <h3>{t("answer.steps")}</h3>
              <StepList steps={state.steps} live={running} />
              {running && <p className="loading">{t("ask.running")}</p>}
            </div>
          )}
          {state.phase === "failed" && <ErrorPanel error={state.error} />}
          {state.phase === "done" && <AnswerView answer={state.answer} />}
        </section>
      )}
    </div>
  );
}
