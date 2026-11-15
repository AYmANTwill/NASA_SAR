import { describe, expect, it } from "vitest";
import type { Answer, CaseStudy, DemoBundle } from "@/api/contract";
import { ApiError, ContractError } from "@/api/errors";
import { recorded, recordedNames } from "@/test/recorded";
import { createReplayClient } from "./replay";
import { draftCases, normalizeQuestion, validateSnapshot, type Snapshot } from "./snapshot";

/** A snapshot built from the recorded live responses (src/test/recorded). */
function recordedSnapshot(): Snapshot {
  const responses: Snapshot["responses"] = {};
  const caseFiles = recordedNames("case").filter((n) => n !== "case-404.json");
  for (const name of [...caseFiles, ...recordedNames("answer-"), "health.json", "library.json", "demo.json", "discoveries.json", "lband-proof.json"]) {
    const r = recorded(name);
    responses[r.path] = { status: r.status, body: r.body };
  }
  return { generated_at: "2026-11-14T21:32:00Z", source: "recorded", responses, files: [] };
}

describe("snapshot gate", () => {
  it("every recorded live response passes the contract", () => {
    expect(validateSnapshot(recordedSnapshot())).toEqual([]);
  });

  it("finds the draft cases a demo build must refuse", () => {
    const snapshot = recordedSnapshot();
    const expected = Object.values(snapshot.responses)
      .filter((r) => r.status < 400 && (r.body as CaseStudy).status === "draft" && (r.body as CaseStudy).findings)
      .map((r) => (r.body as CaseStudy).id);
    expect(draftCases(snapshot)).toEqual(expected.sort());
  });

  it("a draft listed in /cases is refused even if its page failed to record", () => {
    const snapshot = recordedSnapshot();
    const listed = (snapshot.responses["/cases"]!.body as { id: string; status: string }[]).find((c) => c.status === "draft");
    if (!listed) return;
    delete snapshot.responses[`/cases/${listed.id}`];
    expect(draftCases(snapshot)).toContain(listed.id);
  });

  it("a demo page recorded as an error is a problem; an information state is not", () => {
    const snapshot = recordedSnapshot();
    const notFound = recorded("case-404.json");
    snapshot.responses["/cases/panama-2026"] = { status: notFound.status, body: notFound.body };
    const paths = validateSnapshot(snapshot).map((p) => p.path);
    expect(paths).toContain("/cases/panama-2026");
    expect(paths).not.toContain("/discoveries?region=morocco");
  });

  it("reports a response that breaks the contract", () => {
    const snapshot = recordedSnapshot();
    (snapshot.responses["/cases/panama-2026"]!.body as { limits: unknown[] }).limits = [];
    expect(validateSnapshot(snapshot).map((p) => p.path)).toContain("/cases/panama-2026");
  });
});

describe("question matching", () => {
  it("ignores case, accents, punctuation and spacing", () => {
    expect(normalizeQuestion("Le sol a-t-il changé à Asni ?")).toBe(normalizeQuestion("le sol a t il change a asni"));
  });
  it("ignores Arabic vowel marks", () => {
    expect(normalizeQuestion("هل تغيّرت الأرض؟")).toBe(normalizeQuestion("هل تغيرت الأرض"));
  });
});

describe("replay client", () => {
  const snapshot = recordedSnapshot();
  const client = createReplayClient(snapshot);
  const demo = snapshot.responses["/demo"]!.body as DemoBundle;

  it("answers a demonstration question with its recorded answer, steps first", async () => {
    const entry = demo.entries.find((e) => snapshot.responses[`/answers/${e.answer_id}`])!;
    const question = entry.questions.find((q) => q.lang === "ar")!;
    const steps: string[] = [];
    const answer = await client.ask({ question: question.text, lang: "ar", location: null }, (s) => steps.push(s.id));
    const stored = snapshot.responses[`/answers/${entry.answer_id}`]!.body as Answer;
    expect(answer.id).toBe(stored.id);
    expect(steps).toEqual(stored.steps.map((s) => s.id));
  });

  it("a question outside the snapshot is an explicit 'not in the demo', never a guess", async () => {
    const error = await client.ask({ question: "something else entirely", lang: "en", location: null }, () => {}).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe("not_in_demo");
  });

  it("replays error bodies as the backend sent them", async () => {
    const error = await client.discoveries("morocco").catch((e: unknown) => e);
    expect((error as ApiError).code).toBe("discoveries_disabled");
  });

  it("validates again at replay time", async () => {
    const broken = recordedSnapshot();
    (broken.responses["/cases/panama-2026"]!.body as { limits: unknown[] }).limits = [];
    await expect(createReplayClient(broken).caseStudy("panama-2026")).rejects.toBeInstanceOf(ContractError);
  });

  it("changes nothing: watch actions are refused with an explanation", async () => {
    const error = await client.createWatch("x").catch((e: unknown) => e);
    expect((error as ApiError).code).toBe("read_only");
  });
});
