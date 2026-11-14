import { z } from "zod";
import { ApiError, OfflineError, parseWith, type ApiClient } from "./client";
import {
  AgentStep,
  Answer,
  ApiErrorBody,
  CaseStudy,
  CaseSummary,
  DemoBundle,
  Discoveries,
  LbandProof,
  LibraryEvent,
  Watch,
  WatchNotification,
  type AskRequest,
} from "./contract";
import { readSse } from "./sse";

/** Talks to the FastAPI backend. Base URL defaults to same-origin /api (Vite proxies it in dev). */
export function createHttpClient(base = import.meta.env.VITE_API_BASE ?? "/api"): ApiClient {
  const root = base.replace(/\/$/, "");

  async function request(path: string, init?: RequestInit): Promise<Response> {
    let response: Response;
    try {
      response = await fetch(root + path, { ...init, headers: { Accept: "application/json", ...init?.headers } });
    } catch (error) {
      if ((error as Error).name === "AbortError") throw error;
      throw new OfflineError(path);
    }
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      const parsed = ApiErrorBody.safeParse(body);
      throw new ApiError(parsed.success ? parsed.data.code : "http_" + response.status, parsed.success ? parsed.data.message : null, response.status);
    }
    return response;
  }

  async function getJson<T>(path: string, schema: z.ZodType<T, z.ZodTypeDef, unknown>, signal?: AbortSignal): Promise<T> {
    const response = await request(path, { signal });
    return parseWith(schema, await response.json(), "GET " + path);
  }

  return {
    mode: "http",

    async ask(req: AskRequest, onStep, signal) {
      const response = await request("/ask", {
        method: "POST",
        signal,
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify(req),
      });
      if (!response.body) throw new ApiError("empty_stream", null, response.status);
      for await (const message of readSse(response.body)) {
        const payload: unknown = JSON.parse(message.data);
        if (message.event === "step") onStep(parseWith(AgentStep, payload, "SSE step"));
        else if (message.event === "answer") return parseWith(Answer, payload, "SSE answer");
        else if (message.event === "error") {
          const body = parseWith(ApiErrorBody, payload, "SSE error");
          throw new ApiError(body.code, body.message, response.status);
        }
      }
      throw new ApiError("stream_ended_without_answer", null, response.status);
    },

    answer: (id, signal) => getJson(`/answers/${encodeURIComponent(id)}`, Answer, signal),
    discoveries: (region, signal) => getJson(`/discoveries?region=${encodeURIComponent(region)}`, Discoveries, signal),
    watches: (signal) => getJson("/watches", z.array(Watch), signal),
    async createWatch(answerId) {
      const response = await request("/watches", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answer_id: answerId }),
      });
      return parseWith(Watch, await response.json(), "POST /watches");
    },
    async deleteWatch(id) {
      await request(`/watches/${encodeURIComponent(id)}`, { method: "DELETE" });
    },
    notifications: (signal) => getJson("/notifications", z.array(WatchNotification), signal),
    library: (signal) => getJson("/library", z.array(LibraryEvent), signal),
    lbandProof: (signal) => getJson("/proofs/lband-vs-cband", LbandProof, signal),
    demoBundle: (signal) => getJson("/demo", DemoBundle, signal),
    cases: (signal) => getJson("/cases", z.array(CaseSummary), signal),
    caseStudy: (id, signal) => getJson(`/cases/${encodeURIComponent(id)}`, CaseStudy, signal),
  };
}
