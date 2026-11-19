// Cross-language parity for features v2: the browser code (src/features_v2.js) must reproduce the
// Python reference on the committed fixture (tests/golden/v2_holistic.json.gz) within 1e-6.
// Needs no npm packages. Run with: node --test tests/v2-parity.test.mjs (from the web folder).
// tests/test_features_v2.py also runs tools/dump-v2.mjs and compares every value of every frame.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { canonicalizeFrame, sequenceFeatures, createLayout, FEATURE_VERSION } from "../src/features_v2.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const project = path.resolve(here, "../..");
const spec = JSON.parse(readFileSync(path.join(project, "shared_data/feature_spec_v2.json"), "utf8"));
const fixture = JSON.parse(gunzipSync(readFileSync(path.join(project, "tests/golden/v2_holistic.json.gz"))).toString("utf8"));
const tolerance = fixture.tolerance;

function worstDifference(actual, expected, where, state) {
  if (expected === null || actual === null) {
    assert.equal(actual, expected, where);
    return;
  }
  if (typeof expected === "number") {
    const difference = Math.abs(actual - expected);
    if (difference > state.worst) { state.worst = difference; state.where = where; }
    return;
  }
  assert.equal(actual.length, expected.length, where);
  for (let i = 0; i < expected.length; i += 1) worstDifference(actual[i], expected[i], `${where}[${i}]`, state);
}

test("fixture and spec agree on the feature version", () => {
  assert.equal(fixture.fixture, "SignBridge v2 parity fixture");
  assert.equal(fixture.feature_version, FEATURE_VERSION);
  assert.equal(fixture.spec_version, spec.spec_version);
  assert.ok(fixture.frame_count >= 1000, `only ${fixture.frame_count} frames`);
  assert.equal(createLayout(spec).featuresPerFrame, 971);
});

test("canonical frames match Python on every raw case", () => {
  const state = { worst: 0, where: "" };
  for (const item of fixture.canonicalize_cases) {
    const actual = canonicalizeFrame(item.raw, spec);
    for (const key of ["timestamp_ms", "image_width", "image_height", "hand_assignment"]) assert.equal(actual[key], item.expected[key], `${item.id}.${key}`);
    for (const key of ["left_hand", "right_hand", "pose", "pose_visibility", "face"]) worstDifference(actual[key], item.expected[key], `${item.id}.${key}`, state);
  }
  assert.ok(state.worst <= tolerance, `largest difference ${state.worst} at ${state.where}`);
});

test("sequence features match Python checksums on every frame and full vectors where stored", () => {
  const weights = Array.from({ length: 971 }, (_, i) => ((i * 7919) % 1009) / 1009 - 0.5);
  const state = { worst: 0, where: "" };
  let frames = 0;
  for (const sequence of fixture.sequences) {
    const result = sequenceFeatures(sequence.frames, spec);
    assert.equal(result.reference.from_pose, sequence.reference.from_pose, sequence.id);
    worstDifference(result.reference.origin, sequence.reference.origin, `${sequence.id}.origin`, state);
    worstDifference(result.reference.scale, sequence.reference.scale, `${sequence.id}.scale`, state);
    result.features.forEach((row, index) => {
      frames += 1;
      let s1 = 0, s2 = 0, s3 = 0;
      for (let i = 0; i < row.length; i += 1) { s1 += row[i]; s2 += Math.abs(row[i]); s3 += row[i] * weights[i]; }
      const [e1, e2, e3] = sequence.checksums[index];
      for (const [a, e, name] of [[s1, e1, "sum"], [s2, e2, "abs"], [s3, e3, "weighted"]]) {
        assert.ok(Math.abs(a - e) <= tolerance * row.length, `${sequence.id} frame ${index} ${name}: ${a} vs ${e}`);
      }
      const full = sequence.full_vectors[String(index)];
      if (full) worstDifference(Array.from(row), full, `${sequence.id} frame ${index}`, state);
    });
  }
  assert.equal(frames, fixture.frame_count);
  assert.ok(state.worst <= tolerance, `largest difference ${state.worst} at ${state.where}`);
});

test("bad input is rejected the same way as Python", () => {
  const frame = fixture.sequences[3].frames[0];
  assert.throws(() => sequenceFeatures([], spec));
  assert.throws(() => sequenceFeatures([frame, { ...frame }], spec), /strictly increasing/);
  assert.throws(() => canonicalizeFrame({ ...fixture.canonicalize_cases[0].raw, timestamp_ms: 1.5 }, spec), /integer/);
  assert.throws(() => canonicalizeFrame({ ...fixture.canonicalize_cases[0].raw, image_width: 0 }, spec), /positive/);
  assert.throws(() => createLayout({ ...spec, feature_version: "v9" }), /not supported/);
});
