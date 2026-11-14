import { z } from "zod";
import {
  Answer,
  ApiErrorBody,
  CaseStudy,
  CaseSummary,
  DemoBundle,
  Discoveries,
  Health,
  LbandProof,
  LibraryEvent,
  Watch,
  WatchNotification,
} from "@/api/contract";

/**
 * The offline demo replays live backend responses recorded by
 * scripts/snapshot.ts. Each response is kept as the backend sent it (status +
 * body) and is validated with the contract twice: when it is recorded, and
 * again by the replay client when it is shown.
 */
export interface RecordedResponse {
  status: number;
  body: unknown;
}

export interface Snapshot {
  generated_at: string;
  source: string;
  /** Keyed by API path, e.g. "/cases/panama-2026" or "/discoveries?region=morocco". */
  responses: Record<string, RecordedResponse>;
  /** Images (figures, map layers) copied next to the build, by their API path. */
  files: string[];
}

type Schema = z.ZodType<unknown, z.ZodTypeDef, unknown>;

const ROUTES: [RegExp, Schema][] = [
  [/^\/health$/, Health],
  [/^\/cases$/, z.array(CaseSummary)],
  [/^\/cases\/[^/]+$/, CaseStudy],
  [/^\/answers\/[^/]+$/, Answer],
  [/^\/library$/, z.array(LibraryEvent)],
  [/^\/demo$/, DemoBundle],
  [/^\/discoveries\?/, Discoveries],
  [/^\/proofs\/lband-vs-cband$/, LbandProof],
  [/^\/watches$/, z.array(Watch)],
  [/^\/notifications$/, z.array(WatchNotification)],
];

/** The contract schema of a path's successful response. */
export function schemaFor(path: string): Schema | null {
  return ROUTES.find(([pattern]) => pattern.test(path))?.[1] ?? null;
}

export interface SnapshotProblem {
  path: string;
  problem: string;
}

/** Every response must pass the contract (an error status must carry an ApiErrorBody). */
export function validateSnapshot(snapshot: Snapshot): SnapshotProblem[] {
  const problems: SnapshotProblem[] = [];
  for (const [path, response] of Object.entries(snapshot.responses)) {
    const schema = response.status >= 400 ? ApiErrorBody : schemaFor(path);
    if (!schema) {
      problems.push({ path, problem: "no contract schema for this path" });
      continue;
    }
    const result = schema.safeParse(response.body);
    if (!result.success) {
      for (const issue of result.error.issues) problems.push({ path, problem: `${issue.path.join(".") || "(root)"}: ${issue.message}` });
    }
  }
  return problems;
}

/** CASE_CONTRACT.md, rule 5: a demo build refuses any draft case. */
export function draftCases(snapshot: Snapshot): string[] {
  return Object.entries(snapshot.responses)
    .filter(([path, r]) => /^\/cases\/[^/]+$/.test(path) && r.status < 400)
    .filter(([, r]) => (r.body as { status?: string }).status === "draft")
    .map(([path]) => path.replace("/cases/", ""));
}

/** Questions are matched after removing case, accents, punctuation and extra spaces. */
export function normalizeQuestion(text: string): string {
  return text
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .trim();
}
