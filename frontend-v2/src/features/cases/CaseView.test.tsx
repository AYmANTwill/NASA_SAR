import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { I18nextProvider } from "react-i18next";
import { describe, expect, it } from "vitest";
import { ApiProvider } from "@/api/ApiProvider";
import { createHttpClient } from "@/api/client";
import type { CaseStudy, Lang } from "@/api/contract";
import { AppRoutes } from "@/app/routes";
import { formatNumber } from "@/i18n/format";
import { i18nFor } from "@/i18n";
import { recorded, recordedFetch, type Recorded } from "@/test/recorded";
import { FindingView } from "./ledger";

const BASE = "http://test/api";

function renderCase(lang: Lang, rec: Recorded) {
  const id = (rec.body as CaseStudy).id;
  const { fetcher } = recordedFetch({ [`${BASE}/cases/${id}`]: rec });
  render(
    <ApiProvider client={createHttpClient(BASE, fetcher)}>
      <MemoryRouter initialEntries={[`/${lang}/cases/${id}`]}>
        <AppRoutes />
      </MemoryRouter>
    </ApiProvider>,
  );
}

/**
 * A final version of a recorded case, derived from the API's own values (never typed):
 * every NISAR value takes its reference's value and σ, so by the 2σ rule the agreement is "agree".
 */
function finalFrom(name: string): Recorded {
  const rec = structuredClone(recorded(name));
  const study = rec.body as CaseStudy;
  study.status = "final";
  study.findings = study.findings.filter((f) => f.reference).map((f) => ({ ...f, nisar: { ...f.reference! }, agreement: "agree" as const }));
  return rec;
}

/** Every number the API sent, formatted the way the interface prints it. */
function apiNumbers(value: unknown, lang: Lang, out = new Set<string>()): Set<string> {
  if (typeof value === "number") out.add(formatNumber(value, lang));
  else if (Array.isArray(value)) value.forEach((v) => apiNumbers(v, lang, out));
  else if (value && typeof value === "object") Object.values(value).forEach((v) => apiNumbers(v, lang, out));
  return out;
}

describe("case view, draft (recorded Panama)", () => {
  const panama = recorded("case-panama-2026.json");
  const study = panama.body as CaseStudy;

  it("shows the DRAFT band and the page title says draft", async () => {
    renderCase("fr", panama);
    expect(await screen.findByRole("note")).toHaveProperty("textContent", expect.stringContaining("Brouillon"));
    expect(document.title).toMatch(/^\[Brouillon\]/);
  });

  it("never shows a placeholder as 0, and hides its agreement", async () => {
    renderCase("en", panama);
    const mw = (await screen.findByRole("heading", { name: study.findings[0]!.label.en })).closest("article") as HTMLElement;
    expect(within(mw).getByText("not measured yet")).toBeTruthy();
    expect(within(mw).queryByText(/Disagrees/)).toBeNull();
    expect(within(mw).getByText(/Compared once the NISAR value is measured/)).toBeTruthy();
    // The USGS reference is shown with its uncertainty and its source link.
    const sourceName = study.findings[0]!.reference_source!.name;
    expect(within(mw).getByRole("link", { name: (name) => name.startsWith(sourceName) })).toHaveProperty(
      "href",
      study.findings[0]!.reference_source!.url,
    );
    const ref = study.findings[0]!.reference!;
    expect(mw.querySelector(".measure-number")?.textContent).toBe(`${formatNumber(ref.value, "en")} ± ${formatNumber(ref.uncertainty, "en")}`);
  });

  it("always shows the limits, in Arabic too", async () => {
    renderCase("ar", panama);
    const limits = await screen.findByRole("region", { name: "ما لا يستطيع الرادار قوله هنا" });
    for (const limit of study.limits) expect(limits.textContent).toContain(limit.text!.ar!);
  });
});

describe("case view, final", () => {
  it("draws the comparison strip and the API's agreement; no DRAFT band", async () => {
    renderCase("en", finalFrom("case-panama-2026.json"));
    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByRole("note")).toBeNull();
    expect(document.querySelectorAll("svg.strip").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Agrees: gap within 2σ combined/).length).toBeGreaterThan(0);
  });

  it.each(["fr", "en", "ar"] as const)("every number in a measurement comes from the API (%s)", async (lang) => {
    const rec = finalFrom("case-panama-2026.json");
    renderCase(lang, rec);
    await screen.findByRole("heading", { level: 1 });
    const allowed = apiNumbers(rec.body, lang);
    const shown = [...document.querySelectorAll(".measure-number")].flatMap((el) => (el.textContent ?? "").split("±").map((s) => s.trim()));
    expect(shown.length).toBeGreaterThan(0);
    for (const n of shown) expect(allowed, `"${n}" is not an API value`).toContain(n);
  });
});

describe("case view, linked answers", () => {
  it("links each answer the case lists, with its question and verdict", async () => {
    const rec = structuredClone(recorded("case-panama-2026.json"));
    const answer = recorded("answer-event-panama-2026.json");
    (rec.body as CaseStudy).answer_ids = [(answer.body as { id: string }).id];
    const { fetcher } = recordedFetch({ [`${BASE}/cases/panama-2026`]: rec, [`${BASE}${answer.path}`]: answer });
    render(
      <ApiProvider client={createHttpClient(BASE, fetcher)}>
        <MemoryRouter initialEntries={["/en/cases/panama-2026"]}>
          <AppRoutes />
        </MemoryRouter>
      </ApiProvider>,
    );
    const section = await screen.findByRole("region", { name: "Linked investigator answers" });
    const link = await within(section).findByRole("link", { name: (answer.body as { question: string }).question });
    expect(link.getAttribute("href")).toBe(`/en/answers/${(answer.body as { id: string }).id}`);
  });
});

describe("Haouz agreement interpretation", () => {
  it.each(["fr", "en", "ar"] as const)("explains agreement with the no-event baseline below the badge (%s)", (lang) => {
    // Display regression only: the measurements come from the recorded reference, as in finalFrom above.
    const finding = (finalFrom("case-panama-2026.json").body as CaseStudy).findings[0]!;
    finding.reference_source = { ...finding.reference_source!, name: "No-event baseline: random circles" };
    const { container, rerender } = render(
      <I18nextProvider i18n={i18nFor[lang]}><FindingView finding={finding} status="final" caseId="haouz-flood-2026" /></I18nextProvider>,
    );
    const note = container.querySelector(".finding-context");
    expect(note?.textContent).toBe(i18nFor[lang].t("case.noEventAgreement"));
    expect(note?.previousElementSibling?.className).toBe("finding-agreement");
    rerender(<I18nextProvider i18n={i18nFor[lang]}><FindingView finding={finding} status="final" caseId="panama-2026" /></I18nextProvider>);
    expect(container.querySelector(".finding-context")).toBeNull();
  });
});

describe("case view, errors", () => {
  it("an unknown case shows the backend's not-found text", async () => {
    const { fetcher } = recordedFetch({ [`${BASE}/cases/no-such-case`]: recorded("case-404.json") });
    render(
      <ApiProvider client={createHttpClient(BASE, fetcher)}>
        <MemoryRouter initialEntries={["/en/cases/no-such-case"]}>
          <AppRoutes />
        </MemoryRouter>
      </ApiProvider>,
    );
    expect(await screen.findByText("Case study not found.")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Not found" })).toBeTruthy();
  });
});
