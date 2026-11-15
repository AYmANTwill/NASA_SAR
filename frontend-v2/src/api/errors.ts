import type { z } from "zod";
import type { TemplatedText } from "./contract";

/** The backend answered with an error body (ApiErrorBody): a known, explained refusal. */
export class ApiError extends Error {
  readonly name = "ApiError";
  constructor(
    readonly code: string,
    readonly body: TemplatedText | null,
    readonly status: number,
    readonly endpoint: string,
  ) {
    super(`${endpoint}: ${status} ${code}`);
  }
}

/** The backend answered with data that does not match the contract. It is never shown. */
export class ContractError extends Error {
  readonly name = "ContractError";
  constructor(
    readonly endpoint: string,
    readonly issues: z.ZodIssue[],
  ) {
    super(`${endpoint}: contract mismatch: ${issues.map((i) => `${i.path.join(".") || "(root)"} ${i.message}`).join("; ")}`);
  }
}

/** The backend could not be reached at all. */
export class OfflineError extends Error {
  readonly name = "OfflineError";
  constructor(readonly endpoint: string) {
    super(`${endpoint}: backend unreachable`);
  }
}

export type KnownError = ApiError | ContractError | OfflineError;

export function isKnownError(error: unknown): error is KnownError {
  return error instanceof ApiError || error instanceof ContractError || error instanceof OfflineError;
}

/**
 * Error codes that describe a state of the service, not a failure: the
 * interface shows them as information (DESIGN.md, PLAN.md section 3).
 */
export const INFORMATION_CODES: ReadonlySet<string> = new Set(["discoveries_disabled", "not_available", "not_in_demo", "read_only"]);

/** Validates a response; on mismatch, throws a ContractError and nothing of the data is used. */
export function parseWith<T>(schema: z.ZodType<T, z.ZodTypeDef, unknown>, data: unknown, endpoint: string): T {
  const result = schema.safeParse(data);
  if (!result.success) throw new ContractError(endpoint, result.error.issues);
  return result.data;
}
