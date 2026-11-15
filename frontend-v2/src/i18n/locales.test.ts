import { describe, expect, it } from "vitest";
import ar from "./locales/ar.json";
import en from "./locales/en.json";
import fr from "./locales/fr.json";
import { langFromPath, pathInLang, preferredLang } from "./index";
import { readFileSync } from "node:fs";

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
  it("retains every original frontend template and term in each language", () => {
    for (const lang of ["fr", "en", "ar"]) {
      const original = JSON.parse(readFileSync(`../frontend/src/i18n/locales/${lang}.json`, "utf8")) as Record<string, Record<string, string>>;
      const current = JSON.parse(readFileSync(`src/i18n/templates/${lang}.json`, "utf8")) as Record<string, Record<string, string>>;
      for (const root of ["tpl", "term"]) expect(Object.keys(original[root]!).filter((key) => !(key in current[root]!))).toEqual([]);
    }
  });
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

  /**
   * "Never type a number": interface strings carry no number of their own. Allowed: proper
   * names (ERA5, Sentinel-1, SME2) and the contract's agreement rule (2σ / 4σ, CASE_CONTRACT.md).
   * Numbers reach the screen only as {{parameters}} from the API.
   */
  it("no interface string contains a number of its own", async () => {
    const allowedKeys = /^(agreement\.(agree|partial|disagree)|source\.(open_meteo|sentinel1|sentinel2)|limit\.soil_depth)$/;
    const templates = { fr: await import("./templates/fr.json"), en: await import("./templates/en.json"), ar: await import("./templates/ar.json") };
    for (const [name, locale] of Object.entries({ fr, en, ar })) {
      const strings: [string, string][] = [];
      const walk = (o: unknown, p: string) => {
        if (typeof o === "string") strings.push([p, o]);
        else if (o && typeof o === "object") for (const [k, v] of Object.entries(o)) walk(v, p ? `${p}.${k}` : k);
      };
      walk(locale, "");
      const tpl = templates[name as keyof typeof templates];
      for (const [k, v] of Object.entries({ ...tpl.tpl, ...tpl.term })) strings.push([k, v]);
      const offenders = strings.filter(([k, s]) => !allowedKeys.test(k) && /\d/.test(s.replace(/\{\{[^}]*\}\}/g, "").replace(/Sentinel-1/g, "Sentinel")));
      expect(offenders, name).toEqual([]);
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
