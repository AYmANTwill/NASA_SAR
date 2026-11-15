import { z } from "zod";
import {
  AgentStep,
  Answer,
  ApiErrorBody,
  CaseStudy,
  CaseSummary,
  DemoBundle,
  Discoveries,
  Health,
  LbandProof,
  LibraryEvent,
  Watch,
  WatchNotification,
  type AskRequest,
  type WatchLevel,
} from "./contract";
import { ApiError, OfflineError, parseWith } from "./errors";
import { readSse } from "./sse";

/** Everything the interface asks of the backend. Components never call fetch. */
export interface ApiClient {
  health(signal?: AbortSignal): Promise<Health>;
  cases(signal?: AbortSignal): Promise<CaseSummary[]>;
  caseStudy(id: string, signal?: AbortSignal): Promise<CaseStudy>;
  ask(request: AskRequest, onStep: (step: AgentStep) => void, signal?: AbortSignal): Promise<Answer>;
  answer(id: string, signal?: AbortSignal): Promise<Answer>;
  library(signal?: AbortSignal): Promise<LibraryEvent[]>;
  demo(signal?: AbortSignal): Promise<DemoBundle>;
  discoveries(region: string, signal?: AbortSignal): Promise<Discoveries>;
  lbandProof(signal?: AbortSignal): Promise<LbandProof>;
  watches(signal?: AbortSignal): Promise<Watch[]>;
  createWatch(answerId: string): Promise<Watch>;
  deleteWatch(id: string): Promise<void>;
  notifications(signal?: AbortSignal): Promise<WatchNotification[]>;
  /**
   * Actions whose response has no schema in the contract (API_REQUESTS.md #7): their body is
   * never read or shown. The interface re-reads the watches and notifications instead, which are validated.
   */
  checkWatches(): Promise<void>;
  simulateAlert(watchId: string, level: WatchLevel): Promise<void>;
}

type Schema<T> = z.ZodType<T, z.ZodTypeDef, unknown>;

/** Talks to the FastAPI backend under /api (same origin; Vite proxies it in development). */
export function createHttpClient(base: string = import.meta.env.VITE_API_BASE ?? "/api", fetcher: typeof fetch = fetch): ApiClient {
  const root = base.replace(/\/$/, "");

  async function send(method: string, path: string, init: RequestInit = {}): Promise<Response> {
    const endpoint = `${method} ${path}`;
    let response: Response;
    try {
      response = await fetcher(root + path, { ...init, method, headers: { Accept: "application/json", ...init.headers } });
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") throw error;
      throw new OfflineError(endpoint);
    }
    if (!response.ok) {
      const body: unknown = await response.json().catch(() => null);
      const parsed = ApiErrorBody.safeParse(body);
      throw parsed.success
        ? new ApiError(parsed.data.code, parsed.data.message, response.status, endpoint)
        : new ApiError(`http_${response.status}`, null, response.status, endpoint);
    }
    return response;
  }

  async function json<T>(method: string, path: string, schema: Schema<T>, init?: RequestInit): Promise<T> {
    const response = await send(method, path, init);
    let data: unknown;
    try {
      data = await response.json();
    } catch {
      throw parseWith(schema, undefined, `${method} ${path}`);
    }
    return parseWith(schema, data, `${method} ${path}`);
  }

  const get = <T>(path: string, schema: Schema<T>, signal?: AbortSignal) => json("GET", path, schema, { signal });
  const id = encodeURIComponent;

  return {
    health: (signal) => get("/health", Health, signal),
    cases: (signal) => get("/cases", z.array(CaseSummary), signal),
    caseStudy: (caseId, signal) => get(`/cases/${id(caseId)}`, CaseStudy, signal),
    answer: (answerId, signal) => get(`/answers/${id(answerId)}`, Answer, signal),
    library: (signal) => get("/library", z.array(LibraryEvent), signal),
    demo: (signal) => get("/demo", DemoBundle, signal),
    discoveries: (region, signal) => get(`/discoveries?region=${id(region)}`, Discoveries, signal),
    lbandProof: (signal) => get("/proofs/lband-vs-cband", LbandProof, signal),
    watches: (signal) => get("/watches", z.array(Watch), signal),
    notifications: (signal) => get("/notifications", z.array(WatchNotification), signal),
    createWatch: (answerId) =>
      json("POST", "/watches", Watch, { headers: { "Content-Type": "application/json" }, body: JSON.stringify({ answer_id: answerId }) }),
    async deleteWatch(watchId) {
      await send("DELETE", `/watches/${id(watchId)}`);
    },
    async checkWatches() {
      await send("POST", "/watches/check");
    },
    async simulateAlert(watchId, level) {
      await send("POST", `/watches/${id(watchId)}/simulate?level=${id(level)}`);
    },

    async ask(request, onStep, signal) {
      const endpoint = "POST /ask";
      const response = await send("POST", "/ask", {
        signal,
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify(request),
      });
      if (!response.body) throw new ApiError("empty_stream", null, response.status, endpoint);
      for await (const message of readSse(response.body)) {
        let payload: unknown;
        try {
          payload = JSON.parse(message.data);
        } catch {
          payload = undefined;
        }
        if (message.event === "step") onStep(parseWith(AgentStep, payload, `${endpoint} (step)`));
        else if (message.event === "answer") return parseWith(Answer, payload, `${endpoint} (answer)`);
        else if (message.event === "error") {
          const body = parseWith(ApiErrorBody, payload, `${endpoint} (error)`);
          throw new ApiError(body.code, body.message, response.status, endpoint);
        }
      }
      throw new ApiError("stream_ended_without_answer", null, response.status, endpoint);
    },
  };
}
