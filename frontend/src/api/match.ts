import type { DemoBundle } from "./contract";

/** Lowercase, strip Latin diacritics, Arabic harakat/tatweel, punctuation and extra spaces. */
export function normalizeQuestion(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[ً-ٰٟـ]/g, "")
    .replace(/[أإآ]/g, "ا")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

const STOP = new Set(["le", "la", "les", "de", "du", "des", "a", "t", "il", "elle", "se", "ce", "the", "is", "of", "in", "since", "depuis", "after", "apres", "mes", "my"]);

function tokens(text: string): Set<string> {
  return new Set(normalizeQuestion(text).split(" ").filter((w) => w.length > 1 && !STOP.has(w)));
}

/** Jaccard similarity on content words. */
export function similarity(a: string, b: string): number {
  const ta = tokens(a), tb = tokens(b);
  if (!ta.size || !tb.size) return 0;
  let inter = 0;
  for (const w of ta) if (tb.has(w)) inter++;
  return inter / (ta.size + tb.size - inter);
}

/** Finds the precomputed answer for a question, or null. Exact normalized match wins; fuzzy needs ≥ 0.6. */
export function matchDemoQuestion(bundle: DemoBundle, question: string): string | null {
  const q = normalizeQuestion(question);
  let best: { id: string; score: number } | null = null;
  for (const entry of bundle.entries) {
    for (const { text: candidate } of entry.questions) {
      if (normalizeQuestion(candidate) === q) return entry.answer_id;
      const score = similarity(candidate, question);
      if (!best || score > best.score) best = { id: entry.answer_id, score };
    }
  }
  return best && best.score >= 0.6 ? best.id : null;
}
