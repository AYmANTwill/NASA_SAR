import type { ApiClient } from "@/api/client";
import { AgentStep, ApiErrorBody, DemoBundle, type Answer } from "@/api/contract";
import { ApiError, parseWith } from "@/api/errors";
import { prefersReducedMotion } from "@/i18n/format";
import { normalizeQuestion, schemaFor, type Snapshot } from "./snapshot";

/** Pause between replayed agent steps, so the live panel reads as it does online (none with reduced motion). */
const STEP_PAUSE_MS = 180;

function demoError(code: string, endpoint: string): ApiError {
  // Interface templates (src/i18n/templates): the explanation is in the page language.
  return new ApiError(code, { template: `demo.${code}`, params: {} }, 0, endpoint);
}

function aborted(): DOMException {
  return new DOMException("aborted", "AbortError");
}

/** Waits between steps; honours an abort at any time, including one that already happened. */
function pause(signal?: AbortSignal): Promise<void> {
  if (signal?.aborted) return Promise.reject(aborted());
  if (prefersReducedMotion()) return Promise.resolve();
  return new Promise<void>((resolve, reject) => {
    const onAbort = () => {
      clearTimeout(timer);
      reject(aborted());
    };
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, STEP_PAUSE_MS);
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

/**
 * The offline demo's API: answers from a snapshot of the live backend
 * (scripts/snapshot.ts). Every response is validated with the same schemas as
 * the snapshot gate (schemaFor), like the http client does. Nothing is
 * invented: a question or a page outside the snapshot gets an explicit "not in
 * the offline demo" error.
 */
export function createReplayClient(snapshot: Snapshot): ApiClient {
  function get<T>(path: string): Promise<T> {
    const endpoint = `GET ${path}`;
    try {
      const recorded = snapshot.responses[path];
      if (!recorded) throw demoError("not_in_demo", endpoint);
      if (recorded.status >= 400) {
        const body = parseWith(ApiErrorBody, recorded.body, endpoint);
        throw new ApiError(body.code, body.message, recorded.status, endpoint);
      }
      const schema = schemaFor(path);
      if (!schema) throw demoError("not_in_demo", endpoint);
      return Promise.resolve(parseWith(schema, recorded.body, endpoint) as T);
    } catch (error) {
      return Promise.reject(error);
    }
  }

  const questions = new Map<string, string>();
  const bundle = DemoBundle.safeParse(snapshot.responses["/demo"]?.body);
  if (bundle.success) for (const entry of bundle.data.entries) for (const q of entry.questions) questions.set(normalizeQuestion(q.text), entry.answer_id);

  const answerPath = (id: string) => `/answers/${encodeURIComponent(id)}`;

  return {
    health: () => get("/health"),
    cases: () => get("/cases"),
    caseStudy: (id) => get(`/cases/${id}`),
    answer: (id) => get(answerPath(id)),
    library: () => get("/library"),
    demo: () => get("/demo"),
    discoveries: (region) => get(`/discoveries?region=${encodeURIComponent(region)}`),
    lbandProof: () => get("/proofs/lband-vs-cband"),
    watches: () => get("/watches"),
    notifications: () => get("/notifications"),
    createWatch: () => Promise.reject(demoError("read_only", "POST /watches")),
    deleteWatch: () => Promise.reject(demoError("read_only", "DELETE /watches")),
    checkWatches: () => Promise.reject(demoError("read_only", "POST /watches/check")),
    simulateAlert: () => Promise.reject(demoError("read_only", "POST /watches/simulate")),

    async ask(request, onStep, signal) {
      if (signal?.aborted) throw aborted();
      const id = questions.get(normalizeQuestion(request.question));
      if (!id) throw demoError("not_in_demo", "POST /ask");
      const answer = await get<Answer>(answerPath(id));
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
