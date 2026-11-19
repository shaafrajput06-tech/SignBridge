// Cross-language parity: the browser's v1 features and demo rules must match the Python reference
// on the committed fixture (tests/golden/v1_hands.json). Run with: npm test (from the web folder).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { classifyGesture, normalizeLandmarks } from "../src/vision.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const fixture = JSON.parse(readFileSync(path.resolve(here, "../../tests/golden/v1_hands.json"), "utf8"));
const toPoints = (rows) => rows.map(([x, y, z]) => ({ x, y, z }));

test("fixture is the v1 parity fixture", () => {
  assert.equal(fixture.fixture, "SignBridge v1 parity fixture");
  assert.ok(fixture.cases.length >= 200);
});

test("browser demo rules match Python on every fixture hand", () => {
  const mismatches = fixture.cases
    .map((item) => ({ id: item.id, expected: item.gesture, actual: classifyGesture(toPoints(item.points)) ?? null }))
    .filter((row) => row.expected !== row.actual);
  assert.deepEqual(mismatches, []);
});

test("browser v1 features match Python within the fixture tolerance", () => {
  let worst = 0;
  let worstId = "";
  for (const item of fixture.cases) {
    const features = normalizeLandmarks(toPoints(item.points), item.handedness);
    assert.equal(features.length, 63, item.id);
    for (let index = 0; index < 63; index += 1) {
      const difference = Math.abs(features[index] - item.features[index]);
      if (difference > worst) { worst = difference; worstId = item.id; }
    }
  }
  assert.ok(worst < fixture.feature_tolerance, `largest difference ${worst} at ${worstId}`);
});

test("degenerate hand is rejected the same way as Python", () => {
  const flat = Array.from({ length: 21 }, () => ({ x: 0.5, y: 0.5, z: 0 }));
  assert.throws(() => normalizeLandmarks(flat));
  assert.equal(classifyGesture(flat), null);
  assert.equal(classifyGesture(flat.slice(0, 20)), null);
});
