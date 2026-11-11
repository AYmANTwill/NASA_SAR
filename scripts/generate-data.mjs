import fs from "node:fs";
import path from "node:path";
import { PNG } from "pngjs";
const root = "public/data";
fs.mkdirSync(root, { recursive: true });
const save = (name, data) => {
  const p = path.join(root, name);
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, JSON.stringify(data, null, 2));
};
const definitions = [
  [
    "venezuela",
    "Venezuela",
    "Coastal earthquakes",
    "earthquake",
    "#FF6B35",
    [10.6, -66.9],
    7.2,
    "2026-05-14",
    "Two simulated coastal seismic events reveal a striking surface displacement signature along the Caribbean plate boundary.",
    128,
    2840,
    -4.8,
    0.42,
    "M7.2 / M7.5",
    "Simulated seismic sequence",
  ],
  [
    "souss-massa",
    "Souss-Massa",
    "Water under pressure",
    "waterStress",
    "#F5B841",
    [30.1, -9.2],
    8,
    "2026-04-08",
    "A retreating vegetation signal and declining radar backscatter trace seasonal water stress across Morocco’s agricultural heartland.",
    -18,
    1640,
    -3.6,
    0.73,
    "12 mm",
    "Rainfall over 12 days",
  ],
  [
    "bihar",
    "Bihar",
    "A river beyond its banks",
    "flood",
    "#3BA7FF",
    [25.6, 85.1],
    7.4,
    "2026-07-03",
    "Smooth, inundated surfaces return less radar energy. The simulated monsoon footprint follows the Ganges floodplain.",
    24,
    3260,
    -8.2,
    0.31,
    "286 mm",
    "Monsoon rainfall",
  ],
  [
    "amazon",
    "Amazon",
    "The changing forest edge",
    "deforestation",
    "#3DDC84",
    [-10, -63],
    7.7,
    "2026-06-06",
    "Persistent patches of backscatter loss and declining vegetation index suggest canopy removal along expanding forest edges.",
    9,
    486,
    -5.4,
    0.58,
    "143",
    "Simulated fire detections",
  ],
  [
    "mexico-city",
    "Mexico City",
    "A city slowly sinking",
    "subsidence",
    "#B57BFF",
    [19.43, -99.13],
    9.3,
    "2026-03-02",
    "A broad deformation bowl illustrates differential ground motion across the basin. Groundwater extraction is a possible driver, not a proven attribution.",
    -218,
    312,
    -1.2,
    0.86,
    "38",
    "Infrastructure intersections",
  ],
];
const classes = [
  "earthquake",
  "waterStress",
  "flood",
  "deforestation",
  "subsidence",
];
const cases = definitions.map((d, i) => {
  const [
    id,
    name,
    subtitle,
    phenomenon,
    accentColor,
    center,
    zoom,
    start,
    description,
    displacement,
    area,
    backscatter,
    coherence,
    contextValue,
    contextLabel,
  ] = d;
  const dates = Array.from({ length: 8 }, (_, j) =>
    new Date(Date.parse(start) + j * 12 * 86400000).toISOString().slice(0, 10),
  );
  const span = i === 4 ? 0.22 : i === 1 ? 0.65 : 1.2;
  return {
    id,
    name,
    subtitle,
    phenomenon,
    accentColor,
    center,
    zoom,
    pitch: i === 0 || i === 4 ? 42 : 20,
    bearing: -12,
    bbox: [
      center[1] - span,
      center[0] - span * 0.7,
      center[1] + span,
      center[0] + span * 0.7,
    ],
    dates,
    description,
    kpis: {
      displacement_mm: displacement,
      affected_area_km2: area,
      backscatter_db: backscatter,
      coherence,
      affected_population: [84000, 42000, 218000, 1200, 346000][i],
    },
    classProbabilities: Object.fromEntries(
      classes.map((c, k) => [
        c,
        k === i
          ? [0.94, 0.89, 0.96, 0.92, 0.97][i]
          : (1 - [0.94, 0.89, 0.96, 0.92, 0.97][i]) / 4,
      ]),
    ),
    predictedClass: phenomenon,
    confidence: [0.94, 0.89, 0.96, 0.92, 0.97][i],
    contextValue,
    contextLabel,
  };
});
save("cases.json", cases);
const products = {
  gcov: {
    unit: "dB",
    min: -12,
    max: 12,
    colormap: ["#287dff", "#162d49", "#ff633e"],
  },
  gunw: {
    unit: "mm",
    min: -250,
    max: 250,
    colormap: [
      "#6345f5",
      "#30cbe8",
      "#9de051",
      "#ffe43d",
      "#ff5b50",
      "#6345f5",
    ],
  },
  coherence: {
    unit: "",
    min: 0,
    max: 1,
    colormap: ["#440154", "#31688e", "#35b779", "#fde725"],
  },
  goff: {
    unit: "m",
    min: 0,
    max: 2,
    colormap: ["#182453", "#b57bff", "#fff0c8"],
  },
  ndvi: {
    unit: "NDVI",
    min: 0,
    max: 1,
    colormap: ["#9d6e35", "#c6c64b", "#3ddc84"],
  },
  rainfall: {
    unit: "mm",
    min: 0,
    max: 300,
    colormap: ["#152848", "#3ba7ff", "#c1eaff"],
  },
};
const hex = (h) => h.match(/[0-9a-f]{2}/gi).map((x) => parseInt(x, 16));
function color(t, colors) {
  const p = Math.max(0, Math.min(0.999, t)) * (colors.length - 1),
    a = Math.floor(p),
    f = p - a;
  return hex(colors[a]).map((v, k) =>
    Math.round(v + (hex(colors[a + 1])[k] - v) * f),
  );
}
function field(x, y, ci, t) {
  const r = Math.hypot(x * 1.2, y),
    noise = (Math.sin(x * 31 + y * 23) + Math.sin(x * 63 - y * 19)) * 0.06;
  if (ci === 0) return Math.sin(r * 32 - t * 4) * Math.exp(-r * r * 2);
  if (ci === 1) return Math.sin(x * 7) * Math.cos(y * 9) * 0.5 + noise;
  if (ci === 2)
    return (
      Math.exp(-Math.pow(y - Math.sin(x * 5) * 0.25, 2) * 35) * -0.95 + noise
    );
  if (ci === 3)
    return (
      Math.sin(Math.floor(x * 16) * 17 + Math.floor(y * 16) * 9) * 0.65 + noise
    );
  return -Math.exp(-r * r * 3) + noise * 0.15;
}
for (const [ci, c] of cases.entries()) {
  save(
    "timeseries/" + c.id + ".json",
    c.dates.map((date, j) => ({
      date,
      backscatter_db: +(
        (c.kpis.backscatter_db * j) / 7 +
        Math.sin(j * 1.7) * 0.5
      ).toFixed(2),
      coherence: +Math.max(
        0.1,
        Math.min(0.98, 0.91 - ((0.91 - c.kpis.coherence) * j) / 7),
      ).toFixed(2),
      displacement_mm: +((c.kpis.displacement_mm * j) / 7).toFixed(1),
      rainfall_mm: Math.round(
        (ci === 2 ? 286 : 30) * (0.2 + Math.abs(Math.sin(j * 1.3))),
      ),
      ndvi: +(0.8 - ((ci === 1 || ci === 3 ? 0.45 : 0.12) * j) / 7).toFixed(2),
    })),
  );
  for (const [product, meta] of Object.entries(products))
    for (const [di, date] of c.dates.entries()) {
      const png = new PNG({ width: 160, height: 160 });
      const values = [];
      for (let py = 0; py < 160; py++)
        for (let px = 0; px < 160; px++) {
          const x = px / 80 - 1,
            y = py / 80 - 1,
            t = (di + 1) / 8,
            f = field(x, y, ci, t),
            r = Math.hypot(x, y),
            idx = (py * 160 + px) * 4;
          let value =
            product === "gunw"
              ? (f + 1) / 2
              : product === "coherence"
                ? 0.3 + Math.abs(f) * 0.65
                : product === "ndvi"
                  ? 0.65 + f * 0.3
                  : product === "rainfall"
                    ? Math.abs(f) * t
                    : (f * t + 1) / 2;
          if (px % 4 === 0 && py % 4 === 0)
            values.push(
              r <= 1
                ? +(
                    meta.min +
                    Math.max(0, Math.min(1, value)) * (meta.max - meta.min)
                  ).toFixed(3)
                : null,
            );
          const rgb = color(value, meta.colormap);
          png.data[idx] = rgb[0];
          png.data[idx + 1] = rgb[1];
          png.data[idx + 2] = rgb[2];
          png.data[idx + 3] = Math.round(
            Math.pow(Math.max(0, 1 - r), 0.7) *
              215 *
              (product === "gcov" ? 0.3 + Math.abs(f) : 0.85),
          );
        }
      const base = c.id + "/" + product + "/" + date;
      const filename = path.join(root, base + ".png");
      fs.mkdirSync(path.dirname(filename), { recursive: true });
      fs.writeFileSync(filename, PNG.sync.write(png));
      save(base + ".json", {
        bounds: c.bbox,
        ...meta,
        simulated: true,
        sampleGrid: { width: 40, height: 40, values },
      });
    }
}
const collection = (features) => ({ type: "FeatureCollection", features });
for (const kind of [
  "events",
  "fires",
  "floodExtent",
  "infrastructure",
  "classification",
]) {
  const features = cases.flatMap((c, ci) =>
    Array.from(
      {
        length:
          kind === "fires"
            ? 25
            : kind === "classification"
              ? 24
              : kind === "infrastructure"
                ? 16
                : 3,
      },
      (_, j) => {
        const [w, s, e, n] = c.bbox,
          lng = w + (e - w) * (0.15 + ((j * 0.618) % 1) * 0.7),
          lat = s + (n - s) * (0.15 + ((j * 0.381) % 1) * 0.7),
          size = (e - w) * 0.045;
        return {
          type: "Feature",
          properties: {
            caseId: c.id,
            class: c.phenomenon,
            name: kind + " " + (j + 1),
            magnitude: 7.2 + j * 0.15,
            height: 20 + j * 9,
            value: ci + j,
            simulated: true,
          },
          geometry:
            kind === "floodExtent" ||
            kind === "classification" ||
            kind === "infrastructure"
              ? {
                  type: "Polygon",
                  coordinates: [
                    [
                      [lng, lat],
                      [lng + size, lat],
                      [lng + size, lat + size],
                      [lng, lat + size],
                      [lng, lat],
                    ],
                  ],
                }
              : { type: "Point", coordinates: [lng, lat] },
        };
      },
    ),
  );
  save(kind + ".geojson", collection(features));
}
save(
  "alerts.json",
  cases.flatMap((c) =>
    [0, 1].map((j) => ({
      id: c.id + "-" + j,
      caseId: c.id,
      class: c.phenomenon,
      severity: j ? "moderate" : "high",
      confidence: c.confidence,
      lat: c.center[0] + j * 0.08,
      lng: c.center[1] + j * 0.08,
      timestamp: c.dates[6 + j] + "T10:24:00Z",
      message: [c.subtitle + " detected", "Change footprint expanded"][j],
    })),
  ),
);
console.log(
  "Generated 5 cases, 240 rasters + sidecars, 5 time series, 5 GeoJSON collections and 10 alerts.",
);
await import("./extend-data.mjs");
