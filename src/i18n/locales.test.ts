import { describe, expect, it } from "vitest";
import * as fx from "@/__fixtures__";
import type { TemplatedText } from "@/api/contract";
import ar from "./locales/ar.json";
import en from "./locales/en.json";
import fr from "./locales/fr.json";

const PLURAL = /_(zero|one|two|few|many|other)$/;

function flatten(obj: object, prefix = "", flat = false): string[] {
  return Object.entries(obj).flatMap(([k, v]) => {
    const key = prefix ? `${prefix}${flat ? "" : "."}${k}` : k;
    if (typeof v === "object" && v !== null) return flatten(v, key + (["tpl", "term"].includes(k) && !prefix ? "\u0000" : ""), ["tpl", "term"].includes(k) && !prefix);
    return [key.replace(PLURAL, "")];
  });
}

const keys = (o: object) => new Set(flatten(o));

describe("locale parity", () => {
  const base = keys(fr);
  for (const [name, locale] of [["ar", ar], ["en", en]] as const) {
    it(`${name} has exactly the French keys`, () => {
      const k = keys(locale);
      expect([...base].filter((x) => !k.has(x))).toEqual([]);
      expect([...k].filter((x) => !base.has(x))).toEqual([]);
    });
  }
  it("Arabic plural keys provide all six forms", () => {
    const flatAr = Object.entries(ar.tpl as Record<string, string>).map(([k]) => k);
    const bases = new Set(flatAr.filter((k) => PLURAL.test(k)).map((k) => k.replace(PLURAL, "")));
    for (const b of bases) for (const form of ["zero", "one", "two", "few", "many", "other"]) expect(flatAr).toContain(`${b}_${form}`);
  });
});

function templatesIn(value: unknown, out = new Set<string>()): Set<string> {
  if (Array.isArray(value)) value.forEach((v) => templatesIn(v, out));
  else if (value && typeof value === "object") {
    const tt = value as Partial<TemplatedText>;
    if (typeof tt.template === "string" && tt.params) out.add(tt.template);
    Object.values(value).forEach((v) => templatesIn(v, out));
  }
  return out;
}

describe("template catalog", () => {
  const used = templatesIn([fx.fixtureAnswers, fx.discoveries, fx.initialNotifications, fx.library, fx.lbandProof]);
  used.add("notify.watch_created");
  used.add("error.no_fixture");
  for (const [name, locale] of [["fr", fr], ["ar", ar], ["en", en]] as const) {
    it(`${name} translates every template used by the fixtures`, () => {
      const tpl = Object.keys(locale.tpl).map((k) => k.replace(PLURAL, ""));
      expect([...used].filter((id) => !tpl.includes(id))).toEqual([]);
    });
  }
  it("translations never hard-code a measured number (only {{placeholders}})", () => {
    for (const locale of [fr, ar, en]) {
      for (const [id, text] of Object.entries(locale.tpl as Record<string, string>)) {
        const stripped = text.replace(/\{\{[^}]+\}\}/g, "").replace(/\b(NISAR|SME2|GUNW|GCOV|GOFF|USGS|Sentinel-[12]|A2)\b/g, "");
        expect(/\d/.test(stripped), `${id}: ${text}`).toBe(false);
      }
    }
  });
});
