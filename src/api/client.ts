import type { z } from "zod";
import type {
  AgentStep,
  Answer,
  AskRequest,
  DemoBundle,
  Discoveries,
  LbandProof,
  LibraryEvent,
  TemplatedText,
  Watch,
  WatchNotification,
} from "./contract";

/** Everything the UI may ask of the backend. Components never call fetch directly. */
export interface ApiClient {
  readonly mode: "http" | "fixtures";
  ask(req: AskRequest, onStep: (step: AgentStep) => void, signal?: AbortSignal): Promise<Answer>;
  answer(id: string, signal?: AbortSignal): Promise<Answer>;
  discoveries(region: string, signal?: AbortSignal): Promise<Discoveries>;
  watches(signal?: AbortSignal): Promise<Watch[]>;
  createWatch(answerId: string): Promise<Watch>;
  deleteWatch(id: string): Promise<void>;
  notifications(signal?: AbortSignal): Promise<WatchNotification[]>;
  library(signal?: AbortSignal): Promise<LibraryEvent[]>;
  lbandProof(signal?: AbortSignal): Promise<LbandProof>;
  demoBundle(signal?: AbortSignal): Promise<DemoBundle>;
}

/** The backend answered, but with an explicit error body (e.g. no coverage). */
export class ApiError extends Error {
  constructor(
    readonly code: string,
    readonly body: TemplatedText | null,
    readonly status: number,
  ) {
    super(`API error ${status}: ${code}`);
    this.name = "ApiError";
  }
}

/** The backend answered with data that does not match the contract. */
export class ContractError extends Error {
  constructor(
    readonly endpoint: string,
    readonly issues: z.ZodIssue[],
  ) {
    super(`Contract mismatch on ${endpoint}: ${issues.map((i) => `${i.path.join(".")} ${i.message}`).join("; ")}`);
    this.name = "ContractError";
  }
}

/** The network is unreachable and nothing usable is cached. */
export class OfflineError extends Error {
  constructor(readonly endpoint: string) {
    super(`Offline and no cached data for ${endpoint}`);
    this.name = "OfflineError";
  }
}

export function parseWith<T>(schema: z.ZodType<T, z.ZodTypeDef, unknown>, data: unknown, endpoint: string): T {
  const result = schema.safeParse(data);
  if (!result.success) throw new ContractError(endpoint, result.error.issues);
  return result.data;
}
