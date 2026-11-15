import { render } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { describe, expect, it } from "vitest";
import { CaseStudy } from "@/api/contract";
import { i18nFor } from "@/i18n";
import { recorded } from "@/test/recorded";
import { PassTimeline } from "./PassTimeline";

describe("optional timeline kinds", () => {
  it.each(["fr", "en", "ar"] as const)("separates known kinds and keeps old dates unclassified (%s)", (lang) => {
    const study = CaseStudy.parse(recorded("case-panama-2026.json").body);
    const event = study.timeline[0]!;
    study.timeline = [event, ...(["event", "acquisition", "publication"] as const).map((kind) => ({ ...event, kind }))];
    const { container } = render(<I18nextProvider i18n={i18nFor[lang]}><PassTimeline study={study} /></I18nextProvider>);
    for (const kind of ["event", "acquisition", "publication", "unspecified"]) {
      expect(container.querySelectorAll(`.pt-track[data-kind="${kind}"] .pt-mark`)).toHaveLength(1);
    }
    expect(container.querySelectorAll(".pt-list li")).toHaveLength(study.timeline.length);
    // Identical dates remain aligned even when they are on different tracks.
    expect(new Set([...container.querySelectorAll<HTMLElement>(".pt-mark")].map((m) => m.style.left)).size).toBe(1);
  });

  it("preserves kinds through API validation and rejects an unknown kind", () => {
    const study = CaseStudy.parse(recorded("case-panama-2026.json").body);
    const event = study.timeline[0]!;
    const typed = { ...study, timeline: [{ ...event, kind: "acquisition" }] };
    expect(CaseStudy.parse(typed).timeline[0]?.kind).toBe("acquisition");
    expect(CaseStudy.safeParse({ ...typed, timeline: [{ ...event, kind: "detection" }] }).success).toBe(false);
    expect(CaseStudy.parse(study).timeline[0]?.kind).toBeUndefined();
  });
});
