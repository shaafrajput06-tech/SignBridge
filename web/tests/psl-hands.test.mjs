// PSL model input: web/src/psl_hands.js must build exactly what ml_engine/psl_hands.py builds
// (tests/golden/psl_hands_cases.json, written by tools/psl_golden.py), and the PSL client must refuse
// bundles it does not understand.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { adjustAspect, checkPslSpec, pslInput } from "../src/psl_hands.js";
import { checkPslManifest, pslBand, rankPsl, speaksWithoutConfirmation } from "../src/psl_client.js";

const root = new URL("../../", import.meta.url);
const spec = checkPslSpec(JSON.parse(readFileSync(new URL("shared_data/psl_hands_spec.json", root), "utf8")));
const golden = JSON.parse(readFileSync(new URL("tests/golden/psl_hands_cases.json", root), "utf8"));

function frameFromHands(rows) {
  const frame = Array.from({ length: 543 }, () => [NaN, NaN, NaN]);
  rows.forEach((point, i) => { frame[(i < 21 ? 468 : 522 - 21) + i] = point.map((v) => (v === null ? NaN : v)); });
  return frame;
}

test("the PSL input matches the Python reference for every golden case", () => {
  assert.equal(golden.feature_version, spec.feature_version);
  for (const item of golden.cases) {
    const input = pslInput(item.hands.map(frameFromHands), item.aspect, spec);
    assert.equal(input.length, spec.model_input.frames * 543 * 3);
    item.expected_hands.forEach((rows, t) => rows.forEach((point, i) => {
      const row = (i < 21 ? 468 : 522 - 21) + i;
      point.forEach((value, k) => {
        const got = input[(t * 543 + row) * 3 + k];
        if (value === null) assert.ok(Number.isNaN(got), `frame ${t} row ${row} should be missing`);
        else assert.ok(Math.abs(got - value) <= 1e-6, `frame ${t} row ${row}: ${got} vs ${value}`);
      });
    }));
    assert.ok(Number.isNaN(input[0]), "face rows stay NaN");
  }
});

test("the camera-shape rule changes only the hands, and not at the reference shape", () => {
  const frame = frameFromHands(Array.from({ length: 42 }, (_, i) => [0.25 + i / 100, 0.5, 0.1]));
  frame[0] = [0.3, 0.3, 0.3];
  const same = adjustAspect(frame, spec.model_input.aspect_reference, spec.model_input.aspect_reference);
  assert.deepEqual(same[468], frame[468]);
  const wide = adjustAspect(frame, 16 / 9, 4 / 3);
  assert.deepEqual(wide[0], [0.3, 0.3, 0.3]);
  assert.ok(Math.abs(wide[468][0] - (0.5 + (0.25 - 0.5) * (16 / 9) / (4 / 3))) < 1e-12);
  assert.ok(Math.abs(wide[468][2] - 0.1 * (16 / 9) / (4 / 3)) < 1e-12);
  assert.throws(() => adjustAspect(frame, 0, 4 / 3));
});

const manifest = {
  bundle: "signbridge-psl", sign_language: "PSL", feature_version: "psl-hands-v1",
  input: { shape: [32, 543, 3] }, output: { shape: [3] }, model: { file: "psl_v3.tflite", sha256: "a".repeat(64) },
  unknown_class: "_unknown", confidence: { sure: 0.6, unsure: 0.25 },
  classes: [
    { index: 0, gloss: "hello", english: "Hello", tier: "B", validated_by_deaf_signers: false },
    { index: 1, gloss: "water", english: "Water", tier: "B", validated_by_deaf_signers: false },
    { index: 2, gloss: "_unknown", english: "Not a sign", tier: null, validated_by_deaf_signers: false },
  ],
};

test("bundles are checked before use", () => {
  assert.equal(checkPslManifest(structuredClone(manifest)).classes.length, 3);
  assert.throws(() => checkPslManifest({ ...structuredClone(manifest), feature_version: "psl-hands-v9" }), /does not support/);
  assert.throws(() => checkPslManifest({ ...structuredClone(manifest), sign_language: "ASL" }), /not a SignMate PSL bundle/);
  assert.throws(() => checkPslManifest({ ...structuredClone(manifest), output: { shape: [4] } }), /does not match/);
});

test("ranking, bands and the no-speech rule for unvalidated signs", () => {
  const top = rankPsl([Math.log(0.7), Math.log(0.2), Math.log(0.1)], manifest);
  assert.equal(top[0].gloss, "hello");
  assert.ok(Math.abs(top[0].probability - 0.7) < 1e-9);
  assert.equal(pslBand(top, manifest), "sure");
  assert.equal(pslBand(rankPsl([Math.log(0.3), Math.log(0.3), Math.log(0.4)], manifest), manifest), "none", "'not a sign' on top means no answer");
  assert.equal(pslBand(rankPsl([Math.log(0.4), Math.log(0.35), Math.log(0.25)], manifest), manifest), "unsure");
  assert.equal(speaksWithoutConfirmation(top[0]), false);
  assert.equal(speaksWithoutConfirmation({ tier: "A", validated_by_deaf_signers: true }), true);
});
