import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { useApi } from "@/api/ApiProvider";
import type { AgentStep, Answer, AskRequest } from "@/api/contract";

export type AskState =
  | { phase: "idle" }
  | { phase: "running"; steps: AgentStep[] }
  | { phase: "done"; steps: AgentStep[]; answer: Answer }
  | { phase: "failed"; steps: AgentStep[]; error: unknown };

/** A step is updated in place when the stream sends it again with a new status (same id). */
export function mergeStep(steps: AgentStep[], step: AgentStep): AgentStep[] {
  const index = steps.findIndex((s) => s.id === step.id);
  if (index === -1) return [...steps, step];
  const next = steps.slice();
  next[index] = step;
  return next;
}

/** POST /api/ask as a live stream: steps appear as the backend sends them, then the answer. */
export function useAsk() {
  const api = useApi();
  const queries = useQueryClient();
  const [state, setState] = useState<AskState>({ phase: "idle" });
  const controller = useRef<AbortController | null>(null);

  useEffect(() => () => controller.current?.abort(), []);

  const ask = useCallback(
    async (request: AskRequest) => {
      controller.current?.abort();
      const current = new AbortController();
      controller.current = current;
      let steps: AgentStep[] = [];
      setState({ phase: "running", steps });
      try {
        const answer = await api.ask(
          request,
          (step) => {
            steps = mergeStep(steps, step);
            if (!current.signal.aborted) setState({ phase: "running", steps });
          },
          current.signal,
        );
        if (current.signal.aborted) return;
        queries.setQueryData(["answer", answer.id], answer);
        setState({ phase: "done", steps, answer });
      } catch (error) {
        if (current.signal.aborted) return;
        setState({ phase: "failed", steps, error });
      }
    },
    [api, queries],
  );

  const reset = useCallback(() => {
    controller.current?.abort();
    setState({ phase: "idle" });
  }, []);

  return { state, ask, reset };
}
