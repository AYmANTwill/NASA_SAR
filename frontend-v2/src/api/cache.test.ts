import { beforeEach, describe, expect, it, vi } from "vitest";
import { recorded, recordedFetch, recordedText } from "@/test/recorded";
import { createHttpClient } from "./client";
import { cacheRead, cacheWrite, questionKey } from "./cache";
import { ApiError, ContractError, OfflineError } from "./errors";

const BASE = "http://test/api";
const offline = recordedFetch({}).fetcher;
beforeEach(() => localStorage.clear());

describe("validated offline responses", () => {
  it("survives a new client instance and announces that saved data was used", async () => {
    const saved = recorded("cases.json");
    const { fetcher } = recordedFetch({ [`${BASE}/cases`]: saved });
    await createHttpClient(BASE, fetcher, localStorage).cases();
    const listener = vi.fn();
    window.addEventListener("nisar-cache-fallback", listener);
    expect(await createHttpClient(BASE, offline, localStorage).cases()).toEqual(saved.body);
    expect(listener).toHaveBeenCalledOnce();
    window.removeEventListener("nisar-cache-fallback", listener);
  });

  it("never turns a backend error into a cached success", async () => {
    cacheWrite(localStorage, BASE + "/cases", recorded("cases.json").body);
    const { fetcher } = recordedFetch({ [`${BASE}/cases`]: () => new Response("failed", { status: 500 }) });
    await expect(createHttpClient(BASE, fetcher, localStorage).cases()).rejects.toBeInstanceOf(ApiError);
  });

  it("revalidates saved responses against the current contract", async () => {
    cacheWrite(localStorage, BASE + "/cases", [{ id: "broken" }]);
    await expect(createHttpClient(BASE, offline, localStorage).cases()).rejects.toBeInstanceOf(ContractError);
  });

  it("does not report yesterday's health as a live connection", async () => {
    cacheWrite(localStorage, BASE + "/health", recorded("health.json").body);
    await expect(createHttpClient(BASE, offline, localStorage).health()).rejects.toBeInstanceOf(OfflineError);
  });

  it("expires saved data and tolerates unavailable storage", () => {
    cacheWrite(localStorage, "old", { ok: true });
    const clock = vi.spyOn(Date, "now").mockReturnValue(Date.now() + 8 * 24 * 60 * 60 * 1000);
    expect(cacheRead(localStorage, "old")).toBeUndefined();
    clock.mockRestore();
    expect(cacheRead(null, "old")).toBeUndefined();
  });

  it("replays only the same question, language and coordinates", async () => {
    const request = { question: "À Asni ?", lang: "fr" as const, location: null };
    const { fetcher } = recordedFetch({ [`${BASE}/ask`]: () => new Response(recordedText("ask-asni-en.sse")) });
    const answer = await createHttpClient(BASE, fetcher, localStorage).ask(request, () => {});
    const client = createHttpClient(BASE, offline, localStorage);
    const steps = vi.fn();
    expect(await client.ask({ ...request, question: "a ASNI" }, steps)).toEqual({ ...answer, cached: true });
    expect(steps).toHaveBeenCalledTimes(answer.steps.length);
    await expect(client.ask({ ...request, lang: "ar" }, () => {})).rejects.toBeInstanceOf(OfflineError);
    await expect(client.ask({ ...request, location: { lat: 0, lon: 0 } }, () => {})).rejects.toBeInstanceOf(OfflineError);
    expect(questionKey(request)).not.toEqual(questionKey({ ...request, location: { lat: 0, lon: 0 } }));
  });
});
