// Generates SYNTHETIC raster PNGs for src/__fixtures__ only.
// These images exercise the map UI; they are not NISAR measurements.
// Usage: node scripts/make-fixture-rasters.mjs
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { PNG } from "pngjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const palettes = JSON.parse(readFileSync(join(root, "src/design/palettes.json"), "utf8"));
const out = join(root, "public/__fixtures__/rasters");
mkdirSync(out, { recursive: true });

const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
function colorAt(stops, t) {
  const x = Math.min(1, Math.max(0, t)) * (stops.length - 1);
  const i = Math.min(stops.length - 2, Math.floor(x));
  const a = hex(stops[i]), b = hex(stops[i + 1]), f = x - i;
  return a.map((v, k) => Math.round(v + (b[k] - v) * f));
}
// Deterministic pseudo-noise so the files are reproducible.
function noise(x, y, seed) {
  const s = Math.sin(x * 12.9898 + y * 78.233 + seed * 37.719) * 43758.5453;
  return s - Math.floor(s);
}
function smoothNoise(x, y, seed, scale) {
  const xs = x / scale, ys = y / scale, x0 = Math.floor(xs), y0 = Math.floor(ys), fx = xs - x0, fy = ys - y0;
  const n = (a, b) => noise(a, b, seed);
  const top = n(x0, y0) * (1 - fx) + n(x0 + 1, y0) * fx;
  const bottom = n(x0, y0 + 1) * (1 - fx) + n(x0 + 1, y0 + 1) * fx;
  return top * (1 - fy) + bottom * fy;
}

function write(name, size, palette, min, max, field) {
  const png = new PNG({ width: size, height: size });
  const stops = palettes[palette];
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const u = x / (size - 1), v = y / (size - 1);
      const value = field(u, v, x, y);
      const idx = (size * y + x) << 2;
      if (value === null) { png.data[idx + 3] = 0; continue; }
      const [r, g, b] = colorAt(stops, (value - min) / (max - min));
      png.data[idx] = r; png.data[idx + 1] = g; png.data[idx + 2] = b; png.data[idx + 3] = 225;
    }
  }
  writeFileSync(join(out, name + ".png"), PNG.sync.write(png));
  console.log("wrote", name);
}

const S = 256;
const edge = (u, v) => u < 0.04 || v < 0.04 || u > 0.96 || v > 0.96;

// Two-lobed co-seismic pattern (synthetic).
write("panama-displacement", S, "diverging_displacement", -50, 50, (u, v, x, y) => {
  if (edge(u, v)) return null;
  const dx = u - 0.5, dy = v - 0.48;
  const lobe = 46 * Math.exp(-((dx + 0.12) ** 2 + dy ** 2) / 0.018) - 30 * Math.exp(-((dx - 0.14) ** 2 + (dy - 0.03) ** 2) / 0.02);
  if (smoothNoise(x, y, 3, 22) < 0.12) return null; // masked, incoherent
  return lobe + (smoothNoise(x, y, 1, 30) - 0.5) * 6;
});
write("panama-coherence-loss", S, "sequential_coherence_loss", 0, 1, (u, v, x, y) => {
  if (edge(u, v)) return null;
  const d = Math.hypot(u - 0.47, v - 0.5);
  return Math.min(1, Math.max(0, 0.9 * Math.exp(-(d * d) / 0.03) + (smoothNoise(x, y, 2, 12) - 0.5) * 0.35));
});
write("venezuela-displacement", S, "diverging_displacement", -30, 30, (u, v, x, y) => {
  if (edge(u, v)) return null;
  const dx = u - 0.5, dy = v - 0.5;
  return 26 * Math.exp(-(dx ** 2 + (dy + 0.05) ** 2) / 0.025) - 12 * Math.exp(-((dx - 0.2) ** 2 + dy ** 2) / 0.02) + (smoothNoise(x, y, 7, 30) - 0.5) * 4;
});
write("alwahda-velocity", S, "diverging_displacement", -20, 20, (u, v, x, y) => {
  if (edge(u, v)) return null;
  if (smoothNoise(x, y, 11, 18) < 0.15) return null;
  return (smoothNoise(x, y, 4, 26) - 0.5) * 5;
});
write("rif-slope-velocity", S, "diverging_displacement", -40, 40, (u, v, x, y) => {
  if (edge(u, v)) return null;
  const d = ((u - 0.55) / 0.9) ** 2 + ((v - 0.45) / 0.5) ** 2;
  return -34 * Math.exp(-d / 0.02) + (smoothNoise(x, y, 5, 24) - 0.5) * 5;
});
write("gharb-soil-moisture", S, "sequential_moisture", 0.05, 0.5, (u, v, x, y) => {
  if (edge(u, v)) return null;
  return 0.18 + 0.22 * smoothNoise(x, y, 9, 48) + 0.08 * Math.exp(-((u - 0.4) ** 2 + (v - 0.6) ** 2) / 0.05);
});
write("rif-coherence-nisar", S, "sequential_coherence", 0, 1, (u, v, x, y) => {
  if (edge(u, v)) return null;
  return Math.min(1, 0.45 + 0.35 * smoothNoise(x, y, 13, 20) + 0.1 * (1 - v));
});
write("rif-coherence-s1", S, "sequential_coherence", 0, 1, (u, v, x, y) => {
  if (edge(u, v)) return null;
  const forest = smoothNoise(x, y, 14, 40);
  return Math.max(0, 0.55 - 0.5 * forest + 0.12 * (smoothNoise(x, y, 15, 8) - 0.5));
});
