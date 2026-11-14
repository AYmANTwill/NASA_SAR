import { z } from "zod";
import type { ApiClient } from "@/api/client";
import { AgentStep, Answer, ApiErrorBody, CaseStudy, CaseSummary, DemoBundle, Discoveries, Health, LbandProof, LibraryEvent, Watch, WatchNotification } from "@/api/contract";
import { ApiError, parseWith } from "@/api/errors";
import { normalizeQuestion, type Snapshot } from "./snapshot";

/** Pause between replayed agent steps, so the live panel reads as it does online (none with reduced motion). */
const STEP_PAUSE_MS = 180;

function demoError(code: string, endpoint: string): ApiError {
  // Interface templates (src/i18n/templates): the explanation is in the page language.
  return new ApiError(code, { template: `demo.${code}`, params: {} }, 0, endpoint);
}

/**
 * The offline demo's API: answers from a snapshot of the live backend
 * (scripts/snapshot.ts). Every response is validated with the contract again
 * here, like the http client does. Nothing is invented: a question or a page
 * outside the snapshot gets an explicit "not in the offline demo" error.
 */
export function createReplayClient(snapshot: Snapshot): ApiClient {
  function get<T>(path: string, schema: z.ZodType<T, z.ZodTypeDef, unknown>): Promise<T> {
    const endpoint = `GET ${path}`;
    const recorded = snapshot.responses[path];
    if (!recorded) return Promise.reject(demoError("not_in_demo", endpoint));
    if (recorded.status >= 400) {
      const body = parseWith(ApiErrorBody, recorded.body, endpoint);
      return Promise.reject(new ApiError(body.code, body.message, recorded.status, endpoint));
    }
    try {
      return Promise.resolve(parseWith(schema, recorded.body, endpoint));
    } catch (error) {
      return Promise.reject(error);
    }
  }

  const questions = new Map<string, string>();
  const bundle = DemoBundle.safeParse(snapshot.responses["/demo"]?.body);
  if (bundle.success) for (const entry of bundle.data.entries) for (const q of entry.questions) questions.set(normalizeQuestion(q.text), entry.answer_id);

  const reducedMotion = () => typeof window !== "undefined" && (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false);
  const pause = (signal?: AbortSignal) =>
    new Promise<void>((resolve, reject) => {
      if (reducedMotion()) return resolve();
      const timer = setTimeout(resolve, STEP_PAUSE_MS);
      signal?.addEventListener("abort", () => {
        clearTimeout(timer);
        reject(new DOMException("aborted", "AbortError"));
      });
    });

  return {
    health: () => get("/health", Health),
    cases: () => get("/cases", z.array(CaseSummary)),
    caseStudy: (id) => get(`/cases/${id}`, CaseStudy),
    answer: (id) => get(`/answers/${encodeURIComponent(id)}`, Answer),
    library: () => get("/library", z.array(LibraryEvent)),
    demo: () => get("/demo", DemoBundle),
    discoveries: (region) => get(`/discoveries?region=${encodeURIComponent(region)}`, Discoveries),
    lbandProof: () => get("/proofs/lband-vs-cband", LbandProof),
    watches: () => get("/watches", z.array(Watch)),
    notifications: () => get("/notifications", z.array(WatchNotification)),
    createWatch: () => Promise.reject(demoError("read_only", "POST /watches")),
    deleteWatch: () => Promise.reject(demoError("read_only", "DELETE /watches")),
    checkWatches: () => Promise.reject(demoError("read_only", "POST /watches/check")),
    simulateAlert: () => Promise.reject(demoError("read_only", "POST /watches/simulate")),

    async ask(request, onStep, signal) {
      const id = questions.get(normalizeQuestion(request.question));
      if (!id) throw demoError("not_in_demo", "POST /ask");
      const answer = await get(`/answers/${encodeURIComponent(id)}`, Answer);
      for (const step of answer.steps) {
        await pause(signal);
        onStep(parseWith(AgentStep, step, "POST /ask (step)"));
      }
      await pause(signal);
      return answer;
    },
  };
}

/** The snapshot bundled into a demo build (empty in any other build). */
export function bundledSnapshot(): Snapshot | null {
  const found = import.meta.glob<Snapshot>("../../demo-data/snapshot.json", { eager: true, import: "default" });
  return Object.values(found)[0] ?? null;
}
