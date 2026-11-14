import { ApiError, type ApiClient } from "./client";
import type { Watch, WatchNotification } from "./contract";
import { matchDemoQuestion } from "./match";
import { replaySteps } from "./replay";
import { addDays } from "@/lib/dates";

/**
 * Serves src/__fixtures__ (synthetic data) through the same interface as the
 * HTTP client. Loaded lazily so fixtures never ship in an http-mode build.
 */
export async function createFixtureClient(): Promise<ApiClient> {
  const fx = await import("@/__fixtures__");
  const answers = new Map(fx.fixtureAnswers.map((a) => [a.id, a]));
  const watches: Watch[] = structuredClone(fx.initialWatches);
  const notifications: WatchNotification[] = structuredClone(fx.initialNotifications);
  const latency = () => new Promise((r) => setTimeout(r, 120));
  const notFound = () => new ApiError("not_found", { template: "error.not_found", params: {} }, 404);

  return {
    mode: "fixtures",
    async ask(req, onStep, signal) {
      const id = matchDemoQuestion(fx.demoBundle, req.question);
      const answer = id ? answers.get(id) : undefined;
      if (!answer) {
        await latency();
        throw new ApiError("no_fixture", { template: "error.no_fixture", params: {} }, 404);
      }
      // Cached answers are staged by the step pacer (useAsk); "live" ones keep a realistic pace.
      return replaySteps({ ...answer, lang: req.lang }, onStep, answer.cached ? 0 : 3200, signal);
    },
    async answer(id) {
      await latency();
      const answer = answers.get(id);
      if (!answer) throw notFound();
      return answer;
    },
    async discoveries() {
      await latency();
      return fx.discoveries;
    },
    async watches() {
      await latency();
      return [...watches];
    },
    async createWatch(answerId) {
      await latency();
      const existing = watches.find((w) => w.answer_id === answerId);
      if (existing) return existing;
      const answer = answers.get(answerId);
      if (!answer) throw notFound();
      const last = answer.acquisitions.at(-1) ?? null;
      const watch: Watch = {
        id: "w-" + answerId,
        location: answer.location,
        question: answer.question,
        recipe: answer.recipe,
        created_at: new Date().toISOString(),
        level: null,
        confidence: answer.confidence,
        last_pass: last,
        next_pass: answer.next_pass ?? (last ? addDays(last, 12) : new Date().toISOString().slice(0, 10)),
        track: answer.tracks[0] ?? null,
        answer_id: answerId,
      };
      watches.unshift(watch);
      return watch;
    },
    async deleteWatch(id) {
      await latency();
      const index = watches.findIndex((w) => w.id === id);
      if (index === -1) throw notFound();
      watches.splice(index, 1);
    },
    async notifications() {
      await latency();
      return notifications.filter((n) => watches.some((w) => w.id === n.watch_id));
    },
    async library() {
      await latency();
      return fx.library;
    },
    async lbandProof() {
      await latency();
      return fx.lbandProof;
    },
    async demoBundle() {
      await latency();
      return fx.demoBundle;
    },
  };
}
