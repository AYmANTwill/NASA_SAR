import { describe, expect, it } from "vitest";
import { z } from "zod";
import * as fx from "@/__fixtures__";
import { Answer, ApiErrorBody, DemoBundle, Discoveries, LbandProof, LibraryEvent, Watch, WatchNotification } from "./contract";
import { recordedRaw } from "@/__fixtures__/backend";
import { matchDemoQuestion, normalizeQuestion } from "./match";
import { parseBlock } from "./sse";

describe("fixtures respect the API contract", () => {
  it.each(fx.fixtureAnswers.map((a) => [a.id, a]))("answer %s", (_, answer) => {
    const parsed = Answer.safeParse(answer);
    expect(parsed.success, JSON.stringify(parsed.error?.issues)).toBe(true);
  });
  it("discoveries, watches, notifications, library, proof, demo bundle", () => {
    expect(Discoveries.safeParse(fx.discoveries).success).toBe(true);
    expect(z.array(Watch).safeParse(fx.initialWatches).success).toBe(true);
    expect(z.array(WatchNotification).safeParse(fx.initialNotifications).success).toBe(true);
    expect(z.array(LibraryEvent).safeParse(fx.library).success).toBe(true);
    expect(LbandProof.safeParse(fx.lbandProof).success).toBe(true);
    expect(DemoBundle.safeParse(fx.demoBundle).success).toBe(true);
  });
  it("every demo bundle entry points to an existing answer", () => {
    const ids = new Set(fx.fixtureAnswers.map((a) => a.id));
    for (const e of fx.demoBundle.entries) expect(ids.has(e.answer_id)).toBe(true);
  });
});

describe("contract rules", () => {
  it("rejects an answer without 'what the radar cannot tell'", () => {
    expect(Answer.safeParse({ ...fx.fixtureAnswers[0], limits: [] }).success).toBe(false);
  });
  it("rejects a measurement without uncertainty", () => {
    const broken = structuredClone(fx.fixtureAnswers[0]) as unknown as { metrics: { measurement: Record<string, unknown> }[] };
    delete broken.metrics[0].measurement.uncertainty;
    expect(Answer.safeParse(broken).success).toBe(false);
  });
  it("rejects a confidence level the backend did not define", () => {
    expect(Answer.safeParse({ ...fx.fixtureAnswers[0], confidence: "very_high" }).success).toBe(false);
  });
});

describe("demo question matching", () => {
  it("normalizes accents, Arabic diacritics and punctuation", () => {
    expect(normalizeQuestion("Où le sol a-t-il bougé ?")).toBe("ou le sol a t il bouge");
    expect(normalizeQuestion("سدّ الوحدة؟")).toBe("سد الوحدة");
  });
  it("finds exact and close questions in FR, AR and EN", () => {
    expect(matchDemoQuestion(fx.demoBundle, "le barrage al wahda se deforme-t-il depuis juin")).toBe("fx-alwahda-since-june");
    expect(matchDemoQuestion(fx.demoBundle, "هل يتشوه سد الوحدة منذ يونيو؟")).toBe("fx-alwahda-since-june");
    expect(matchDemoQuestion(fx.demoBundle, "Where did the ground move after the 9 October earthquake")).toBe("fx-panama-2026-10-09");
  });
  it("does not invent a match for an unrelated question", () => {
    expect(matchDemoQuestion(fx.demoBundle, "Quel temps fera-t-il demain à Paris ?")).toBeNull();
  });
});

describe("real backend recordings (14/11)", () => {
  it.each(recordedRaw.map((r) => [(r as { id: string }).id, r]))("raw %s passes the contract as recorded", (_, raw) => {
    const parsed = Answer.safeParse(raw);
    expect(parsed.success, JSON.stringify(parsed.error?.issues)).toBe(true);
  });
  it("discoveries_disabled and not_available bodies parse as API errors", () => {
    const body = { code: "discoveries_disabled", message: { template: "backend.error.discoveries_disabled", params: {}, text: { fr: "x", en: "x", ar: "x" } } };
    expect(ApiErrorBody.safeParse(body).success).toBe(true);
  });
});

describe("SSE parser", () => {
  it("reads event and multi-line data", () => {
    expect(parseBlock("event: step\ndata: {\"a\":\ndata: 1}")).toEqual({ event: "step", data: '{"a":\n1}' });
    expect(parseBlock(": keep-alive")).toBeNull();
  });
});
