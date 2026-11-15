import { describe, expect, it } from "vitest";
import { recorded, recordedFetch } from "@/test/recorded";
import { createReplayClient } from "@/demo/replay";
import { validateSnapshot, type Snapshot } from "@/demo/snapshot";
import { createHttpClient } from "./client";
import { ContractError } from "./errors";
import { WaterRasterIndex } from "./water";

const BASE = "http://test/api";
const PATH = "/water/raster-index";

describe("optional water images", () => {
  it("reads the recorded live PNGs without turning package legends into RasterLayer palettes", async () => {
    const rec = recorded("water-raster-index.json");
    const { fetcher } = recordedFetch({ [BASE + PATH]: rec });
    const index = await createHttpClient(BASE, fetcher).waterRasterIndex();
    const raw = rec.body as { layers: { url: string; bounds: number[] }[] };
    expect(index?.layers.map((l) => ({ url: l.url, bounds: l.bounds }))).toEqual(raw.layers.map((l) => ({ url: l.url, bounds: l.bounds })));
    expect(index?.layers.every((l) => !("palette" in l) && !("legend" in l))).toBe(true);
  });

  it("keeps an older API usable when the endpoint returns a generic 404", async () => {
    const { fetcher } = recordedFetch({ [BASE + PATH]: () => new Response('{"detail":"Not Found"}', { status: 404 }) });
    await expect(createHttpClient(BASE, fetcher).waterRasterIndex()).resolves.toBeNull();
  });

  it("rejects inverted coordinates before an image can be placed on the map", async () => {
    const broken = structuredClone(recorded("water-raster-index.json"));
    const layer = (broken.body as { layers: { bounds: number[] }[] }).layers[0]!;
    layer.bounds = [layer.bounds[2]!, layer.bounds[1]!, layer.bounds[0]!, layer.bounds[3]!];
    const { fetcher } = recordedFetch({ [BASE + PATH]: broken });
    await expect(createHttpClient(BASE, fetcher).waterRasterIndex()).rejects.toBeInstanceOf(ContractError);
  });

  it("validates and replays the optional response, while older snapshots need no water endpoint", async () => {
    const snapshot: Snapshot = { generated_at: "recorded", source: BASE, responses: {}, files: [] };
    await expect(createReplayClient(snapshot).waterRasterIndex()).resolves.toBeNull();
    const rec = recorded("water-raster-index.json");
    snapshot.responses[PATH] = rec;
    expect(validateSnapshot(snapshot)).toEqual([]);
    await expect(createReplayClient(snapshot).waterRasterIndex()).resolves.toEqual(WaterRasterIndex.parse(rec.body));
  });
});
