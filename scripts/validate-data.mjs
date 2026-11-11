import fs from "node:fs";
import assert from "node:assert/strict";
const root = "public/data/";
const read = (p) => JSON.parse(fs.readFileSync(root + p, "utf8"));
const cases = read("cases.json"),
  alerts = read("alerts.json");
assert.equal(new Set(cases.map((c) => c.id)).size, cases.length);
let rasters = 0;
for (const c of cases) {
  assert.ok(
    Math.abs(
      Object.values(c.classProbabilities).reduce((a, b) => a + b, 0) - 1,
    ) < 1e-6,
  );
  assert.ok(c.confidence >= 0 && c.confidence <= 1);
  const series = read("timeseries/" + c.id + ".json");
  assert.deepEqual(
    series.map((row) => row.date),
    c.dates,
  );
  assert.deepEqual([...c.dates].sort(), c.dates);
  for (const product of [
    "gcov",
    "gunw",
    "coherence",
    "goff",
    "ndvi",
    "rainfall",
  ])
    for (const date of c.dates) {
      const prefix = c.id + "/" + product + "/" + date,
        meta = read(prefix + ".json"),
        png = fs.readFileSync(root + prefix + ".png");
      assert.deepEqual(meta.bounds, c.bbox);
      assert.ok(meta.min < meta.max);
      assert.equal(png.subarray(1, 4).toString(), "PNG");
      assert.equal(
        meta.sampleGrid.values.length,
        meta.sampleGrid.width * meta.sampleGrid.height,
      );
      assert.ok(
        meta.sampleGrid.values.every((v) => v === null || Number.isFinite(v)),
      );
      rasters++;
    }
}
for (const a of alerts) assert.ok(cases.some((c) => c.id === a.caseId));
for (const file of [
  "events",
  "fires",
  "floodExtent",
  "infrastructure",
  "classification",
]) {
  const collection = read(file + ".geojson");
  assert.equal(collection.type, "FeatureCollection");
  for (const f of collection.features)
    assert.ok(cases.some((c) => c.id === f.properties.caseId));
}
console.log(
  "PASS: " +
    cases.length +
    " cases, " +
    rasters +
    " PNG/sidecar pairs, time series, probability sums, context and alert references.",
);
