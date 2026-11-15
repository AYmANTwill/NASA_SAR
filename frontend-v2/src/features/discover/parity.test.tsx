import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ApiProvider } from "@/api/ApiProvider";
import { createHttpClient } from "@/api/client";
import { Discoveries, LbandProof } from "@/api/contract";
import { AppRoutes } from "@/app/routes";
import { recorded, recordedFetch } from "@/test/recorded";
import { discoveryScenario, proofScenario } from "@/test/parity-scenarios";
import { markerBounds } from "./DiscoverPage";
import { i18nFor } from "@/i18n";

const BASE = "http://test/api";
function show(path: string, endpoint: string, body: unknown, status = 200) {
  const { fetcher } = recordedFetch({ [BASE + endpoint]: { path: endpoint, body, status }, [BASE + "/library"]: recorded("library.json") });
  render(<ApiProvider client={createHttpClient(BASE, fetcher)}><MemoryRouter initialEntries={[path]}><AppRoutes /></MemoryRouter></ApiProvider>);
}

describe("ported discovery and proof pages", () => {
  it("keeps a finite map frame when no candidates exist", async () => {
    expect(markerBounds([]).every(Number.isFinite)).toBe(true);
    const body = Discoveries.parse({ ...discoveryScenario, zones: [] });
    show("/en/discover", "/discoveries?region=MA", body);
    expect(await screen.findByText(i18nFor.en.t("parity.noCandidates"))).toBeTruthy();
    expect(document.querySelectorAll(".evidence-row")).toHaveLength(0);
  });

  it("sorts candidates by API rank or exposure and carries coordinates into the investigation", async () => {
    show("/en/discover", "/discoveries?region=MA", Discoveries.parse(discoveryScenario));
    const first = discoveryScenario.zones[0]!;
    const name = first.location.name_i18n!.en!;
    const link = await screen.findByRole("link", { name });
    expect(link.getAttribute("href")).toContain(`lat=${first.location.lat}`);
    expect(document.querySelector(".evidence-row h2")?.textContent).toBe(name);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "exposure" } });
    expect(document.querySelector(".evidence-row h2")?.textContent).toBe(discoveryScenario.zones[1]!.location.name_i18n!.en);
  });

  it("offers observed places when the backend explicitly disables discovery", async () => {
    const response = recorded("discoveries.json");
    show("/fr/discover", "/discoveries?region=MA", response.body, response.status);
    expect(await screen.findByRole("heading", { name: i18nFor.fr.t("parity.observed") })).toBeTruthy();
    expect(document.querySelectorAll(".evidence-row").length).toBeGreaterThan(0);
  });

  it("renders available coherence data, forest bins, source and limits", async () => {
    show("/en/proof", "/proofs/lband-vs-cband", LbandProof.parse(proofScenario));
    expect(await screen.findByText(proofScenario.forest_source)).toBeTruthy();
    expect(document.querySelectorAll(".forest-bin")).toHaveLength(proofScenario.bins.length);
    expect(document.querySelectorAll(".sensor-panel")).toHaveLength(2);
    expect(document.querySelector(".limits")?.textContent).toContain("A single date pair is compared");
  });

  it("keeps the band explanation when the real comparison is unavailable", async () => {
    const response = recorded("lband-proof.json");
    show("/ar/proof", "/proofs/lband-vs-cband", response.body, response.status);
    expect(await screen.findByText((response.body as {message:{text:{ar:string}}}).message.text.ar)).toBeTruthy();
    expect(document.querySelector(".band-explainer svg")).toBeTruthy();
    expect(document.querySelector(".forest-bin")).toBeNull();
  });
});
