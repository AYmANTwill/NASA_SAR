import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => cleanup());

// jsdom has no WebGL: component tests get a stand-in for the MapLibre map. The real map is tested in Playwright.
vi.mock("@/components/map/RadarMap", () => ({
  default: ({ label, layer }: { label: string; layer: { id: string } | null }) => (
    <div role="region" aria-label={label} data-layer={layer?.id ?? ""} />
  ),
}));
