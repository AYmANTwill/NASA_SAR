import { describe, expect, it } from "vitest";
import { recorded, recordedFetch, recordedText } from "@/test/recorded";
import { createHttpClient } from "./client";
import type { AgentStep } from "./contract";
import { ApiError, ContractError, OfflineError } from "./errors";
import { parseSseBlock, readSse } from "./sse";

const BASE = "http://test/api";

function streamOf(text: string, chunkSize = 7): ReadableStream<Uint8Array> {
  const bytes = new TextEncoder().encode(text);
  let offset = 0;
  return new ReadableStream({
    pull(controller) {
      if (offset >= bytes.length) return controller.close();
      controller.enqueue(bytes.slice(offset, offset + chunkSize));
      offset += chunkSize;
    },
  });
}

describe("http client", () => {
  it("returns validated data", async () => {
    const { fetcher } = recordedFetch({ [`${BASE}/cases`]: recorded("cases.json") });
    const cases = await createHttpClient(BASE, fetcher).cases();
    expect(cases.map((c) => c.id)).toEqual((recorded("cases.json").body as { id: string }[]).map((c) => c.id));
  });

  it("rejects a response that breaks the contract, whole", async () => {
    const broken = structuredClone(recorded("case-panama-2026.json"));
    (broken.body as { limits: unknown[] }).limits = [];
    const { fetcher } = recordedFetch({ [`${BASE}/cases/panama-2026`]: broken });
    const error = await createHttpClient(BASE, fetcher).caseStudy("panama-2026").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ContractError);
    expect((error as ContractError).endpoint).toBe("GET /cases/panama-2026");
    expect((error as ContractError).issues.some((i) => i.path.join(".") === "limits")).toBe(true);
  });

  it("turns an error body into an ApiError with the backend's text", async () => {
    const { fetcher } = recordedFetch({ [`${BASE}/cases/no-such-case`]: recorded("case-404.json") });
    const error = await createHttpClient(BASE, fetcher).caseStudy("no-such-case").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe("case_not_found");
    expect((error as ApiError).status).toBe(404);
    expect((error as ApiError).body?.text?.ar).toBeTruthy();
  });

  it("an unreachable server is an OfflineError", async () => {
    const { fetcher } = recordedFetch({});
    await expect(createHttpClient(BASE, fetcher).health()).rejects.toBeInstanceOf(OfflineError);
  });

  it("an error status without a contract body still fails explicitly", async () => {
    const { fetcher } = recordedFetch({ [`${BASE}/health`]: () => new Response("<html>bad gateway</html>", { status: 502 }) });
    const error = await createHttpClient(BASE, fetcher).health().catch((e: unknown) => e);
    expect((error as ApiError).code).toBe("http_502");
  });
});

describe("/ask stream", () => {
  const sse = recordedText("ask-asni-en.sse");

  it("parses every step as it arrives, then the answer", async () => {
    const { fetcher } = recordedFetch({ [`${BASE}/ask`]: () => new Response(streamOf(sse), { status: 200 }) });
    const steps: AgentStep[] = [];
    const answer = await createHttpClient(BASE, fetcher).ask({ question: "q", lang: "en", location: null }, (s) => steps.push(s));
    expect(steps.length).toBe((sse.match(/^event: step$/gm) ?? []).length);
    expect(answer.limits.length).toBeGreaterThan(0);
  });

  it("an error event becomes an ApiError", async () => {
    const body = `event: error\ndata: ${JSON.stringify(recorded("case-404.json").body)}\n\n`;
    const { fetcher } = recordedFetch({ [`${BASE}/ask`]: () => new Response(streamOf(body), { status: 200 }) });
    await expect(createHttpClient(BASE, fetcher).ask({ question: "q", lang: "fr", location: null }, () => {})).rejects.toBeInstanceOf(ApiError);
  });

  it("a stream that ends without an answer is an explicit error", async () => {
    const steps = sse.split("event: answer")[0] ?? "";
    const { fetcher } = recordedFetch({ [`${BASE}/ask`]: () => new Response(streamOf(steps), { status: 200 }) });
    const error = await createHttpClient(BASE, fetcher).ask({ question: "q", lang: "fr", location: null }, () => {}).catch((e: unknown) => e);
    expect((error as ApiError).code).toBe("stream_ended_without_answer");
  });

  it("an invalid step is a ContractError, not skipped", async () => {
    const body = `event: step\ndata: {"id": 1}\n\n`;
    const { fetcher } = recordedFetch({ [`${BASE}/ask`]: () => new Response(streamOf(body), { status: 200 }) });
    await expect(createHttpClient(BASE, fetcher).ask({ question: "q", lang: "fr", location: null }, () => {})).rejects.toBeInstanceOf(ContractError);
  });
});

describe("SSE reader", () => {
  it("handles CRLF, comments, multi-line data and chunk boundaries", async () => {
    const text = ": keep-alive\r\nevent: step\r\ndata: {\"a\":\r\ndata: 1}\r\n\r\nevent: answer\ndata: x";
    const messages = [];
    for await (const m of readSse(streamOf(text, 3))) messages.push(m);
    expect(messages).toEqual([
      { event: "step", data: '{"a":\n1}' },
      { event: "answer", data: "x" },
    ]);
  });

  it("ignores a block without data", () => {
    expect(parseSseBlock("event: step")).toBeNull();
  });
});
