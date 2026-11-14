import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { CloudOff, Database, MessageSquareText } from "lucide-react";
import { API_MODE } from "@/api";
import { formatDate } from "@/lib/format";
import type { Answer, Bounds } from "@/api/contract";
import { useAnswer, useAsk } from "@/api/queries";
import { ErrorState, Loading } from "@/components/states";
import { useText } from "@/i18n/useText";
import { MapSlot } from "@/components/map/MapSlot";
import type { MapMotion } from "@/components/map/RadarMap";
import { AgentSteps } from "./AgentSteps";
import { AnswerView } from "./AnswerView";
import { AskBox } from "./AskBox";


function boundsOf(answer: Answer | undefined): Bounds | null {
  if (!answer) return null;
  if (answer.location.bbox) return answer.location.bbox;
  const b = answer.layers[0]?.bounds;
  if (b) return b;
  const d = 0.1;
  return [answer.location.lon - d, answer.location.lat - d, answer.location.lon + d, answer.location.lat + d];
}

export default function InvestigatePage() {
  const { t, lang } = useText();
  const { answerId } = useParams();
  const [search] = useSearchParams();
  const navigate = useNavigate();
  const { state, ask, reset } = useAsk();
  const stored = useAnswer(state.status === "idle" ? answerId : undefined);
  const [picked, setPicked] = useState<{ lat: number; lon: number } | null>(() => {
    const lat = Number(search.get("lat")), lon = Number(search.get("lon"));
    return search.has("lat") && Number.isFinite(lat) && Number.isFinite(lon) ? { lat, lon } : null;
  });
  const initialQuestion = search.get("q") ?? "";
  const autoAsked = useRef(false);
  const panel = useRef<HTMLDivElement>(null);

  const answer = state.status === "success" ? state.answer : state.status === "idle" ? stored.data : undefined;
  const steps = state.status === "idle" ? (answer?.steps ?? []) : state.steps;

  const run = async (question: string) => {
    const result = await ask({ question, lang, location: picked });
    if (result) navigate(`/investigate/${encodeURIComponent(result.id)}`, { replace: !!answerId });
  };

  // Zone links pass ?q=…&auto=1 to start immediately.
  useEffect(() => {
    // Deferred so StrictMode's simulated unmount (which aborts the request) cancels the timer instead.
    if (initialQuestion && search.get("auto") === "1" && !autoAsked.current) {
      const timer = setTimeout(() => {
        autoAsked.current = true;
        void run(initialQuestion);
      }, 0);
      return () => clearTimeout(timer);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Move focus to the answer when it arrives (keyboard and screen-reader users).
  useEffect(() => {
    if (state.status === "success") document.getElementById("verdict")?.focus?.();
  }, [state.status]);

  const mapAnswer = answer;
  const bounds = useMemo(() => boundsOf(mapAnswer), [mapAnswer]);
  // While the agent works, passes sweep over the point; a new answer is revealed by one pass in its flight direction.
  const motion: MapMotion =
    state.status === "running"
      ? { kind: "scan", key: state.request.question }
      : mapAnswer
        ? { kind: "pass", key: mapAnswer.id, direction: mapAnswer.tracks[0]?.direction ?? "ascending" }
        : null;

  return (
    <div className="flex flex-1 flex-col fill-below-chrome lg:flex-row lg:overflow-hidden">
      <div ref={panel} className="order-2 w-full space-y-5 overflow-y-auto border-line bg-surface px-4 py-5 lg:order-none lg:w-[30rem] lg:shrink-0 lg:border-e xl:w-[34rem]">
        <AskBox
          key={answerId ?? "new"}
          initial={state.status !== "idle" ? state.request.question : (answer?.question ?? initialQuestion)}
          location={picked}
          onClearLocation={() => setPicked(null)}
          running={state.status === "running"}
          onAsk={(q) => void run(q)}
          onCancel={reset}
          compact={!!answer}
        />

        {state.status === "idle" && !answerId && (
          <div className="flex gap-3 text-ink-2">
            <MessageSquareText className="mt-0.5 size-5 shrink-0 text-muted" aria-hidden />
            <p>{t("ask.intro")}</p>
          </div>
        )}

        {state.status === "success" && state.fromCache && (
          <p role="status" className="flex items-center gap-2 rounded-sm bg-surface-2 px-3 py-2 text-sm text-ink-2">
            <CloudOff className="size-4" aria-hidden />
            {t("steps.fromCache")}
          </p>
        )}

        {answer && API_MODE === "fixtures" && answer.id.startsWith("event-") && (
          <p role="note" className="flex items-start gap-2 rounded-sm border border-line-strong bg-accent-soft px-3 py-2 text-sm text-ink">
            <Database className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
            {t("answer.recorded", { date: formatDate(answer.created_at, lang) })}
          </p>
        )}

        {steps.length > 0 && <AgentSteps steps={steps} live={state.status === "running"} />}
        {state.status === "running" && steps.length === 0 && <Loading label={t("ask.running")} />}

        {state.status === "error" && <ErrorState error={state.error} onRetry={() => void run(state.request.question)} />}
        {state.status === "idle" && stored.isLoading && <Loading />}
        {state.status === "idle" && stored.isError && <ErrorState error={stored.error} onRetry={() => void stored.refetch()} />}

        {answer && state.status !== "running" && <AnswerView answer={answer} />}
      </div>

      <div className="relative order-1 h-[46vh] min-h-72 flex-1 lg:order-none lg:h-auto">
        <MapSlot
            className="absolute inset-0"
            ariaLabel={t("map.label")}
            bounds={bounds}
            layers={mapAnswer?.layers ?? []}
            earthquakes={mapAnswer?.earthquakes ?? []}
            picked={picked ?? (mapAnswer ? { lat: mapAnswer.location.lat, lon: mapAnswer.location.lon } : null)}
            onPick={(lat, lon) => setPicked({ lat, lon })}
            motion={motion}
          />
      </div>
    </div>
  );
}
