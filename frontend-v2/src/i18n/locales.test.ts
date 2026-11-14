import { describe, expect, it } from "vitest";
import ar from "./locales/ar.json";
import en from "./locales/en.json";
import fr from "./locales/fr.json";
import { langFromPath, pathInLang, preferredLang } from "./index";

describe("language in the URL", () => {
  it("reads the first segment", () => {
    expect(langFromPath("/ar/cases/panama-2026")).toBe("ar");
    expect(langFromPath("/")).toBeNull();
    expect(langFromPath("/de/cases")).toBeNull();
  });
  it("switches language without changing the page", () => {
    expect(pathInLang("/fr/cases/panama-2026", "ar")).toBe("/ar/cases/panama-2026");
    expect(pathInLang("/en/", "fr")).toBe("/fr/");
    expect(pathInLang("/en", "fr")).toBe("/fr/");
  });
});

function keys(value: unknown, prefix = ""): string[] {
  if (typeof value !== "object" || value === null) return [prefix];
  return Object.entries(value).flatMap(([k, v]) => keys(v, prefix ? `${prefix}.${k}` : k));
}

describe("locales", () => {
  it("FR, EN and AR have exactly the same keys", () => {
    const reference = keys(fr).sort();
    expect(keys(en).sort()).toEqual(reference);
    expect(keys(ar).sort()).toEqual(reference);
  });

  it("no string is empty (except units that have no symbol, such as a count)", () => {
    for (const [name, locale] of Object.entries({ fr, en, ar })) {
      const empty = keys(locale)
        .filter((k) => !k.startsWith("unit."))
        .filter((k) => {
          const s = k.split(".").reduce<unknown>((o, p) => (o as Record<string, unknown>)[p], locale);
          return typeof s !== "string" || s.trim() === "";
        });
      expect(empty, name).toEqual([]);
    }
  });

  it("has a label for every unit of the contract", async () => {
    const { Unit } = await import("@/api/contract");
    for (const locale of [fr, en, ar]) expect(Object.keys(locale.unit).sort()).toEqual([...Unit.options].sort());
  });
});

describe("preferredLang", () => {
  it("takes the first supported browser language", () => {
    expect(preferredLang(["de-DE", "ar-MA", "en"])).toBe("ar");
    expect(preferredLang(["en-GB"])).toBe("en");
  });
  it("falls back to French", () => {
    expect(preferredLang(["de", "es"])).toBe("fr");
    expect(preferredLang([])).toBe("fr");
  });
});
