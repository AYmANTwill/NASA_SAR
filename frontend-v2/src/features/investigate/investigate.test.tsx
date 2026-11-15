import { fireEvent, render, screen, within } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ApiProvider } from "@/api/ApiProvider";
import { createHttpClient } from "@/api/client";
import type { AgentStep, Answer, CaseStudy, Lang, Measurement, TemplatedText } from "@/api/contract";
import { AppRoutes } from "@/app/routes";
import { i18nFor } from "@/i18n";
import { formatNumber } from "@/i18n/format";
import { useText } from "@/i18n/useText";
import { recorded, recordedFetch, recordedText } from "@/test/recorded";
import { mergeStep } from "./useAsk";

const BASE = "http://test/api";

function Text({ tt }: { tt: TemplatedText }) {
  return <p>{useText().text(tt)}</p>;
}

function renderText(lang: Lang, tt: TemplatedText) {
  const { container, unmount } = render(
    <I18nextProvider i18n={i18nFor[lang]}>
      <Text tt={tt} />
    </I18nextProvider>,
  );
  const text = container.textContent ?? "";
  unmount();
  return text;
}

describe("templated text", () => {
  it("renders an interface template with the API's term", () => {
    expect(renderText("en", { template: "step.classify", params: { recipe: { term: "recipe.damage" } } })).toBe("Question understood as: surface change");
  });

  it("uses the plural form of the language, Arabic included", () => {
    const tt = (count: number): TemplatedText => ({ template: "step.search_scenes", params: { count, start: { date: "2026-06-17" }, end: { date: "2026-10-21" } } });
    expect(renderText("en", tt(1))).toMatch(/^1 NISAR product found/);
    expect(renderText("fr", tt(3))).toMatch(/^3 produits NISAR trouvés/);
    expect(renderText("ar", tt(2))).toMatch(/منتجَين/);
  });

  it("falls back to the backend's own text for backend.* ids", () => {
    const limit = (recorded("answer-event-panama-2026.json").body as Answer).limits[0]!;
    expect(renderText("ar", limit)).toBe(limit.text!.ar);
  });

  it.each(["fr", "en", "ar"] as const)("keeps a water measurement and its uncertainty together when prose wraps (%s)", (lang) => {
    const headline = (recorded("case-bin-el-ouidane-2026.json").body as CaseStudy).headline;
    const m = headline.params.nisar as Measurement;
    expect(renderText(lang, headline)).toContain(`${formatNumber(m.value, lang)}\u00a0±\u00a0${formatNumber(m.uncertainty, lang)}`);
  });

  it("says explicitly when a text exists in no form for this language", () => {
    expect(renderText("fr", { template: "backend.unknown", params: {}, text: { en: "only English" } })).toMatch(/Texte non disponible/);
  });
});

describe("mergeStep", () => {
  it("updates a step in place when the stream sends it again", () => {
    const running = { id: "s0", status: "running" } as AgentStep;
    const done = { id: "s0", status: "done" } as AgentStep;
    const other = { id: "s1", status: "done" } as AgentStep;
    expect(mergeStep(mergeStep(mergeStep([], running), other), done)).toEqual([done, other]);
  });
});

describe("investigator page", () => {
  function renderAsk(lang: Lang, sse: string) {
    const { fetcher, calls } = recordedFetch({
      [`${BASE}/demo`]: recorded("demo.json"),
      [`${BASE}/ask`]: () => new Response(sse, { status: 200 }),
    });
    render(
      <ApiProvider client={createHttpClient(BASE, fetcher)}>
        <MemoryRouter initialEntries={[`/${lang}/ask`]}>
          <AppRoutes />
        </MemoryRouter>
      </ApiProvider>,
    );
    return calls;
  }

  it("asks a demo question and shows the answer with its limits (recorded stream)", async () => {
    const sse = recordedText("ask-asni-en.sse");
    const calls = renderAsk("en", sse);
    const demoQuestion = (recorded("demo.json").body as { entries: { questions: { text: string; lang: string }[] }[] }).entries[0]!.questions.find((q) => q.lang === "en")!.text;
    fireEvent.click(await screen.findByRole("button", { name: demoQuestion }));
    const answer = JSON.parse(sse.split("event: answer\ndata: ")[1]!.split("\n")[0]!) as Answer;
    const limits = await screen.findByRole("region", { name: "What the radar cannot tell here" });
    for (const l of answer.limits) expect(limits.textContent).toContain(l.text?.en ?? "");
    expect(screen.getByText(answer.verdict.text!.en!)).toBeTruthy();
    expect(calls).toContain(`POST ${BASE}/ask`);
  });

  it("an error event is shown with the backend's text, in Arabic", async () => {
    const body = { code: "no_location", message: { template: "backend.error.no_location", params: {}, text: { ar: "لا يوجد موقع" } } };
    renderAsk("ar", `event: step\ndata: ${JSON.stringify((recorded("answer-event-panama-2026.json").body as Answer).steps[0])}\n\nevent: error\ndata: ${JSON.stringify(body)}\n\n`);
    fireEvent.change(await screen.findByRole("textbox"), { target: { value: "سؤال" } });
    fireEvent.click(screen.getByRole("button", { name: "ابدأ التحقيق" }));
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("لا يوجد موقع")).toBeTruthy();
  });
});
