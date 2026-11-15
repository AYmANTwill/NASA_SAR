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
import { WaterRasterIndex } from "./water";
import { browserStorage, cacheRead, cacheWrite, cacheRemove, questionKey, announceCached } from "./cache";
import { saveOfflineImages } from "./offline-images";

/** Everything the interface asks of the backend. Components never call fetch. */
export interface ApiClient {
  prepareOffline?(signal?: AbortSignal): Promise<void>;
  health(signal?: AbortSignal): Promise<Health>;
  cases(signal?: AbortSignal): Promise<CaseSummary[]>;
  caseStudy(id: string, signal?: AbortSignal): Promise<CaseStudy>;
  waterRasterIndex(signal?: AbortSignal): Promise<WaterRasterIndex | null>;
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
export function createHttpClient(base: string = import.meta.env.VITE_API_BASE ?? "/api", fetcher: typeof fetch = fetch, storage: Storage | null = fetcher === fetch ? browserStorage() : null): ApiClient {
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
    if (response.headers.get("X-Nisar-Offline") === "1") throw new OfflineError(endpoint);
    if (response.headers.get("X-Nisar-Cached") === "1") announceCached();
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

  const get = async <T>(path: string, schema: Schema<T>, signal?: AbortSignal): Promise<T> => {
    try {
      const data = await json("GET", path, schema, { signal });
      if (path !== "/health") cacheWrite(storage, root + path, data);
      return data;
    } catch (error) {
      if (!(error instanceof OfflineError) || path === "/health") throw error;
      const cached = cacheRead(storage, root + path);
      if (cached === undefined) throw error;
      const data = parseWith(schema, cached, `GET ${path} (saved)`);
      announceCached();
      return data;
    }
  };
  const id = encodeURIComponent;

  return {
    async prepareOffline(signal) {
      const bundle = await get("/demo", DemoBundle, signal);
      await Promise.allSettled(bundle.entries.map(async (entry) => {
        const answer = await get(`/answers/${id(entry.answer_id)}`, Answer, signal);
        if (fetcher === fetch) saveOfflineImages(answer.layers.map((layer) => layer.url), signal);
        for (const question of entry.questions) cacheWrite(storage, root + "/ask/" + questionKey({ question: question.text, lang: question.lang, location: null }), answer);
      }));
    },
    health: (signal) => get("/health", Health, signal),
    cases: (signal) => get("/cases", z.array(CaseSummary), signal),
    async caseStudy(caseId, signal) {
      const study = await get(`/cases/${id(caseId)}`, CaseStudy, signal);
      if (fetcher === fetch) saveOfflineImages(study.figures.flatMap((figure) => [figure.url, ...(figure.layer ? [figure.layer.url] : [])]), signal);
      return study;
    },
    async waterRasterIndex(signal) {
      try {
        const index = await get("/water/raster-index", WaterRasterIndex, signal);
        if (fetcher === fetch) saveOfflineImages(index.layers.map((layer) => layer.url), signal);
        return index;
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null;
        throw error;
      }
    },
    async answer(answerId, signal) {
      const answer = await get(`/answers/${id(answerId)}`, Answer, signal);
      if (fetcher === fetch) saveOfflineImages(answer.layers.map((layer) => layer.url), signal);
      return answer;
    },
    library: (signal) => get("/library", z.array(LibraryEvent), signal),
    demo: (signal) => get("/demo", DemoBundle, signal),
    discoveries: (region, signal) => get(`/discoveries?region=${id(region)}`, Discoveries, signal),
    async lbandProof(signal) {
      const proof = await get("/proofs/lband-vs-cband", LbandProof, signal);
      if (fetcher === fetch) saveOfflineImages([proof.nisar.layer.url, proof.sentinel1.layer.url], signal);
      return proof;
    },
    watches: (signal) => get("/watches", z.array(Watch), signal),
    notifications: (signal) => get("/notifications", z.array(WatchNotification), signal),
    createWatch: (answerId) =>
      json("POST", "/watches", Watch, { headers: { "Content-Type": "application/json" }, body: JSON.stringify({ answer_id: answerId }) }),
    async deleteWatch(watchId) {
      await send("DELETE", `/watches/${id(watchId)}`);
      cacheRemove(storage, root + "/watches");
      cacheRemove(storage, root + "/notifications");
    },
    async checkWatches() {
      await send("POST", "/watches/check");
    },
    async simulateAlert(watchId, level) {
      await send("POST", `/watches/${id(watchId)}/simulate?level=${id(level)}`);
    },

    async ask(request, onStep, signal) {
      const endpoint = "POST /ask";
      let response: Response;
      try { response = await send("POST", "/ask", {
        signal,
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify(request),
      }); } catch (error) {
        if (!(error instanceof OfflineError)) throw error;
        const cached = cacheRead(storage, root + "/ask/" + questionKey(request));
        if (cached === undefined) throw error;
        const answer = parseWith(Answer, cached, "POST /ask (saved)");
        announceCached();
        for (const step of answer.steps) { if (signal?.aborted) throw new DOMException("aborted", "AbortError"); onStep(step); }
        return { ...answer, cached: true };
      }
      if (!response.body) throw new ApiError("empty_stream", null, response.status, endpoint);
      for await (const message of readSse(response.body)) {
        let payload: unknown;
        try {
          payload = JSON.parse(message.data);
        } catch {
          payload = undefined;
        }
        if (message.event === "step") onStep(parseWith(AgentStep, payload, `${endpoint} (step)`));
        else if (message.event === "answer") {
          const answer = parseWith(Answer, payload, `${endpoint} (answer)`);
          cacheWrite(storage, root + "/ask/" + questionKey(request), answer);
          cacheWrite(storage, root + `/answers/${id(answer.id)}`, answer);
          if (fetcher === fetch) saveOfflineImages(answer.layers.map((layer) => layer.url), signal);
          return answer;
        }
        else if (message.event === "error") {
          const body = parseWith(ApiErrorBody, payload, `${endpoint} (error)`);
          throw new ApiError(body.code, body.message, response.status, endpoint);
        }
      }
      throw new ApiError("stream_ended_without_answer", null, response.status, endpoint);
    },
  };
}
