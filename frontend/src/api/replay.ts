import type { AgentStep, Answer } from "./contract";

const wait = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    });
  });

/**
 * Replays the recorded steps of an answer: each step is emitted "running"
 * then "done". `budgetMs` caps the total time so cached answers stay under a second.
 */
export async function replaySteps(answer: Answer, onStep: (step: AgentStep) => void, budgetMs: number, signal?: AbortSignal): Promise<Answer> {
  const recorded = answer.steps.reduce((sum, s) => sum + (s.duration_ms ?? 0), 0) || 1;
  const scale = Math.min(1, budgetMs / recorded);
  for (const s of answer.steps) {
    onStep({ ...s, status: "running", duration_ms: null });
    await wait(Math.max(30, (s.duration_ms ?? 0) * scale), signal);
    onStep(s);
  }
  return answer;
}
