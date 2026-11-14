import { QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, ContractError, getClient, OfflineError } from "./index";
import type { AgentStep, Answer, AskRequest, DemoBundle } from "./contract";
import { matchDemoQuestion } from "./match";
import { replaySteps } from "./replay";
import { createPacer } from "@/motion/director";
import { STAGE } from "@/motion/motion";

export const keys = {
  answer: (id: string) => ["answer", id] as const,
  discoveries: (region: string) => ["discoveries", region] as const,
  watches: ["watches"] as const,
  notifications: ["notifications"] as const,
  library: ["library"] as const,
  proof: ["proof", "lband-vs-cband"] as const,
  demo: ["demo"] as const,
};

export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 5 * 60_000,
        gcTime: 7 * 24 * 3_600_000, // keep for offline demo
        networkMode: "offlineFirst",
        // An explicit answer from the server (feature off, not computed, bad contract) is not retried.
        retry: (count, error) => !(error instanceof OfflineError || error instanceof ApiError || error instanceof ContractError) && count < 2,
        refetchOnWindowFocus: false,
      },
      mutations: { networkMode: "always" },
    },
  });
}

/** Persists the query cache to localStorage so the demo answers survive a reload without network. */
export const persister = createSyncStoragePersister({
  storage: typeof window === "undefined" ? undefined : safeStorage(),
  key: "nisar-pulse-cache-v2",
  throttleTime: 500,
});

function safeStorage(): Storage | undefined {
  try {
    const probe = "__nisar_probe__";
    window.localStorage.setItem(probe, probe);
    window.localStorage.removeItem(probe);
    return window.localStorage;
  } catch {
    return undefined;
  }
}

export const useAnswer = (id: string | undefined) =>
  useQuery({ queryKey: keys.answer(id ?? ""), enabled: !!id, queryFn: async ({ signal }) => (await getClient()).answer(id!, signal) });

export const useDiscoveries = (region = "MA") =>
  useQuery({ queryKey: keys.discoveries(region), queryFn: async ({ signal }) => (await getClient()).discoveries(region, signal) });

export const useWatches = () => useQuery({ queryKey: keys.watches, queryFn: async ({ signal }) => (await getClient()).watches(signal) });

export const useNotifications = () =>
  useQuery({ queryKey: keys.notifications, queryFn: async ({ signal }) => (await getClient()).notifications(signal) });

export const useLibrary = () => useQuery({ queryKey: keys.library, queryFn: async ({ signal }) => (await getClient()).library(signal) });

export const useLbandProof = () => useQuery({ queryKey: keys.proof, queryFn: async ({ signal }) => (await getClient()).lbandProof(signal) });

export function useCreateWatch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (answerId: string) => (await getClient()).createWatch(answerId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.watches });
      void qc.invalidateQueries({ queryKey: keys.notifications });
    },
  });
}

export function useDeleteWatch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => (await getClient()).deleteWatch(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.watches });
      void qc.invalidateQueries({ queryKey: keys.notifications });
    },
  });
}

/**
 * Downloads the demo bundle and every precomputed answer it lists, so the
 * whole demo path works later without network (served from the persisted cache).
 */
export function useDemoPrefetch() {
  const qc = useQueryClient();
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const client = await getClient();
        const bundle = await qc.fetchQuery({ queryKey: keys.demo, queryFn: ({ signal }) => client.demoBundle(signal), staleTime: 30 * 60_000 });
        for (const entry of bundle.entries) {
          if (cancelled) return;
          await qc.prefetchQuery({ queryKey: keys.answer(entry.answer_id), queryFn: ({ signal }) => client.answer(entry.answer_id, signal), staleTime: 30 * 60_000 });
        }
      } catch {
        // Offline or backend unavailable: whatever is already cached is used.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [qc]);
}

export type AskState =
  | { status: "idle"; steps: AgentStep[] }
  | { status: "running"; steps: AgentStep[]; request: AskRequest }
  | { status: "success"; steps: AgentStep[]; request: AskRequest; answer: Answer; fromCache: boolean }
  | { status: "error"; steps: AgentStep[]; request: AskRequest; error: unknown };

/** Runs a question through the agent, streaming steps; falls back to the offline demo cache. */
export function useAsk() {
  const qc = useQueryClient();
  const [state, setState] = useState<AskState>({ status: "idle", steps: [] });
  const controller = useRef<AbortController | null>(null);

  useEffect(() => () => controller.current?.abort(), []);

  const upsert = useCallback((step: AgentStep) => {
    setState((prev) => {
      const steps = [...prev.steps];
      const index = steps.findIndex((s) => s.id === step.id);
      if (index === -1) steps.push(step);
      else steps[index] = step;
      return { ...prev, steps } as AskState;
    });
  }, []);

  const ask = useCallback(
    async (request: AskRequest): Promise<Answer | null> => {
      controller.current?.abort();
      const ctrl = new AbortController();
      controller.current = ctrl;
      setState({ status: "running", steps: [], request });
      // Steps are always staged: fast (precomputed) answers are spaced so the reasoning can be followed.
      const pacer = createPacer(upsert, STAGE.stepGap, ctrl.signal);
      try {
        let answer: Answer;
        let fromCache = false;
        try {
          if (typeof navigator !== "undefined" && navigator.onLine === false) throw new OfflineError("/ask");
          answer = await (await getClient()).ask(request, pacer.push, ctrl.signal);
        } catch (error) {
          const cached = error instanceof OfflineError ? findCachedAnswer(qc, request.question) : null;
          if (!cached) throw error;
          fromCache = true;
          answer = await replaySteps(cached, pacer.push, 0, ctrl.signal);
        }
        await pacer.drained();
        if (ctrl.signal.aborted) return null;
        qc.setQueryData(keys.answer(answer.id), answer);
        setState((prev) => ({ status: "success", steps: prev.steps, request, answer, fromCache }));
        return answer;
      } catch (error) {
        if ((error as Error).name === "AbortError") return null;
        setState((prev) => ({ status: "error", steps: prev.steps, request, error }));
        return null;
      }
    },
    [qc, upsert],
  );

  const reset = useCallback(() => {
    controller.current?.abort();
    setState({ status: "idle", steps: [] });
  }, []);

  return { state, ask, reset };
}

function findCachedAnswer(qc: QueryClient, question: string): Answer | null {
  const bundle = qc.getQueryData<DemoBundle>(keys.demo);
  const id = bundle ? matchDemoQuestion(bundle, question) : null;
  return id ? (qc.getQueryData<Answer>(keys.answer(id)) ?? null) : null;
}

/** navigator.onLine plus browser events. */
export function useOnline(): boolean {
  const [online, setOnline] = useState(() => (typeof navigator === "undefined" ? true : navigator.onLine));
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);
  return online;
}
