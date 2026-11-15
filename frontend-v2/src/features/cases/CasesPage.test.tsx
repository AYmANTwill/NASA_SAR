import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ApiProvider } from "@/api/ApiProvider";
import { createHttpClient } from "@/api/client";
import type { CaseSummary } from "@/api/contract";
import { recorded, recordedFetch, recordedNames, type Recorded } from "@/test/recorded";
import { AppRoutes } from "@/app/routes";

const BASE = "http://test/api";
const summaries = recorded("cases.json").body as CaseSummary[];

function renderCases(lang: string, override: Record<string, Recorded> = {}) {
  const { fetcher } = recordedFetch({
    [`${BASE}/cases`]: recorded("cases.json"),
    ...Object.fromEntries(recordedNames("case-").map((n) => [`${BASE}${recorded(n).path}`, recorded(n)])),
    ...override,
  });
  render(
    <ApiProvider client={createHttpClient(BASE, fetcher)}>
      <MemoryRouter initialEntries={[`/${lang}/`]}>
        <AppRoutes />
      </MemoryRouter>
    </ApiProvider>,
  );
}

describe("case list", () => {
  it("lists every case of the API, in its order, with its title in the page language", async () => {
    renderCases("ar");
    const links = await screen.findAllByRole("link", { name: (name) => summaries.some((s) => s.title.ar === name) });
    expect(links.map((l) => l.textContent)).toEqual(summaries.map((s) => s.title.ar));
    expect(links[0]?.getAttribute("href")).toBe(`/ar/cases/${summaries[0]?.id}`);
  });

  it("marks each draft and says that drafts are not results", async () => {
    renderCases("en");
    await screen.findAllByRole("article");
    const drafts = summaries.filter((s) => s.status === "draft").length;
    expect(screen.getAllByText("Draft")).toHaveLength(drafts);
    if (drafts > 0) expect(screen.getByRole("note").textContent).toMatch(/not measured yet/);
  });

  it("a case that breaks the contract shows its own error; the others still show", async () => {
    const broken = structuredClone(recorded("case-panama-2026.json"));
    (broken.body as { limits: unknown[] }).limits = [];
    renderCases("en", { [`${BASE}/cases/panama-2026`]: broken });
    const card = (await screen.findByRole("link", { name: /Panama/ })).closest("article") as HTMLElement;
    expect(await within(card).findByText("Response rejected")).toBeTruthy();
    const other = summaries.find((s) => s.id !== "panama-2026");
    if (other) expect(screen.getByRole("link", { name: other.title.en })).toBeTruthy();
  });
});
