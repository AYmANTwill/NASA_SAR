import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ApiProvider } from "@/api/ApiProvider";
import { createHttpClient } from "@/api/client";
import type { CaseStudy, Lang } from "@/api/contract";
import { AppRoutes } from "@/app/routes";
import { formatNumber } from "@/i18n/format";
import { recorded, recordedFetch, type Recorded } from "@/test/recorded";

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
