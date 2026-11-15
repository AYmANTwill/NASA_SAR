import { render, screen, within } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ApiProvider } from "@/api/ApiProvider";
import { createHttpClient } from "@/api/client";
import { CaseStudy, type Finding, type Lang } from "@/api/contract";
import { AppRoutes } from "@/app/routes";
import { i18nFor } from "@/i18n";
import { formatNumber } from "@/i18n/format";
import { recorded, recordedFetch } from "@/test/recorded";
import { FindingView } from "./ledger";

const BASE = "http://test/api";
const reservoir = CaseStudy.parse(recorded("case-bin-el-ouidane-2026.json").body);
const haouz = CaseStudy.parse(recorded("haouz-open-water-package.json").body);
const heldout = reservoir.findings.find((f) => f.id === "heldout_iou")!;
const openWater = haouz.findings.find((f) => f.id === "open_water_change")!;
const formatted = (finding: Finding, lang: Lang) => `${formatNumber(finding.nisar.value, lang)} ± ${formatNumber(finding.nisar.uncertainty, lang)}`;

function view(finding: Finding, caseId: CaseStudy["id"], lang: Lang) {
  return <I18nextProvider i18n={i18nFor[lang]}><FindingView finding={finding} status="final" caseId={caseId} /></I18nextProvider>;
}

function page(study: CaseStudy) {
  const { fetcher } = recordedFetch({
    [`${BASE}/cases/${study.id}`]: { path: `/cases/${study.id}`, status: 200, body: study },
    [`${BASE}/water/raster-index`]: recorded("water-raster-index.json"),
  });
  render(<ApiProvider client={createHttpClient(BASE, fetcher)}><MemoryRouter initialEntries={[`/en/cases/${study.id}`]}><AppRoutes /></MemoryRouter></ApiProvider>);
}

describe("water model evidence", () => {
  it.each(["fr", "en", "ar"] as const)("shows the API's heldout_iou with its evaluation meaning (%s)", (lang) => {
    const { container } = render(view(heldout, reservoir.id, lang));
    expect(screen.getByRole("heading").textContent).toBe(heldout.label[lang]);
    expect(container.querySelector(".measure-number")?.textContent).toBe(formatted(heldout, lang));
    expect(screen.getByText(i18nFor[lang].t("case.heldoutIouContext"))).toBeTruthy();
  });

  it.each(["fr", "en", "ar"] as const)("updates the displayed score when a new model changes the API measurement (%s)", (lang) => {
    // A different input measurement, drawn from the recorded payload: no model score is typed here.
    const other = reservoir.findings.find((f) => f.id === "orbit_consistency")!;
    const updated = { ...heldout, nisar: { ...heldout.nisar, value: other.nisar.value, uncertainty: other.nisar.uncertainty } };
    const { container, rerender } = render(view(heldout, reservoir.id, lang));
    rerender(view(updated, reservoir.id, lang));
    expect(container.querySelector(".measure-number")?.textContent).toBe(formatted(updated, lang));
    expect(container.querySelector(".measure-number")?.textContent).not.toBe(formatted(heldout, lang));
  });

  it("does not substitute an uncontracted selection score when heldout_iou is absent", async () => {
    const study = { ...reservoir, findings: reservoir.findings.filter((f) => f.id !== heldout.id), selection_iou: heldout.nisar };
    page(study);
    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByText(i18nFor.en.t("case.heldoutIouContext"))).toBeNull();
    expect(screen.queryByRole("heading", { name: heldout.label.en })).toBeNull();
  });

  it.each(["fr", "en", "ar"] as const)("keeps Haouz open water neutral and explicitly says no clear change (%s)", (lang) => {
    const { container } = render(view(openWater, haouz.id, lang));
    expect(container.querySelector(".measure-number")?.textContent).toBe(formatted(openWater, lang));
    expect(screen.getByText(i18nFor[lang].t("case.openWaterNoClearChange"))).toBeTruthy();
    expect(screen.getByText(i18nFor[lang].t("case.openWaterContext"))).toBeTruthy();
    const badge = container.querySelector(".agreement-no_reference");
    expect(badge?.textContent).toBe(i18nFor[lang].t("agreement.no_reference"));
    expect(badge?.querySelector(".fill")).toBeNull();
    expect(container.querySelector(".agreement-agree, .agreement-partial, .agreement-disagree, svg.strip")).toBeNull();
  });

  it("rejects an API agreement on open water without a reference instead of showing a positive badge", async () => {
    const invalid = { ...haouz, findings: [{ ...openWater, agreement: "agree" as const }] };
    page(invalid);
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("Response rejected")).toBeTruthy();
    expect(document.querySelector(".agreement-agree")).toBeNull();
  });
});
