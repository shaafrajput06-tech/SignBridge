// Inference Baseline v1 (master-v3.md section 0): today's web/src/asl_islr.js must reproduce what the
// frozen baseline build produced (tests/golden/baseline_v1_outputs.json, recorded in Chromium by
// tools/baseline/run.mjs). Frames, resampling, segmenter, confidence words and the exact 32 x 543 x 3
// model inputs (including the synthetic-signer cases) are compared without a browser.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { checkAslSpec, islrFrame, labelsFromIndexMap, probabilities, resample, SignSegmenter } from "../src/asl_islr.js";
import { syntheticRawSequence } from "../src/synthetic_sign.js";
import { float32Bytes, modelCases, pipelineOutputs, sha256Hex } from "../../tools/baseline/cases.mjs";

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const read = (relative) => readFileSync(path.join(project, relative), "utf8");
const featureSpec = JSON.parse(read("shared_data/feature_spec_v2.json"));
const aslSpec = checkAslSpec(JSON.parse(read("shared_data/asl_islr_spec.json")));
const labels = labelsFromIndexMap(JSON.parse(read(aslSpec.classes.file)), aslSpec.classes.count);
const fixture = JSON.parse(gunzipSync(readFileSync(path.join(project, "tests/golden/v2_holistic.json.gz"))).toString("utf8"));
const cases = JSON.parse(read("tests/golden/asl_islr_cases.json"));
const inputs = JSON.parse(read("tests/golden/baseline_v1_inputs.json"));
const golden = JSON.parse(read("tests/golden/baseline_v1_outputs.json"));
const impl = { islrFrame, resample, SignSegmenter, probabilities };

test("frames, resampling, segmenter and confidence words match the baseline", async () => {
  const today = await pipelineOutputs(impl, { featureSpec, aslSpec, labels, fixture, cases });
  assert.deepEqual(today.frames, golden.pipeline.frames);
  assert.deepEqual(today.resampling, golden.pipeline.resampling);
  assert.deepEqual(today.segments, golden.pipeline.segments);
  assert.deepEqual(today.scores, golden.pipeline.scores);
});

test("every model input (static, mix and synthetic-signer cases) matches the baseline bit for bit", async () => {
  const expected = new Map(golden.model.map((item) => [item.id, item]));
  const built = modelCases(impl, { featureSpec, aslSpec, fixture, inputs, syntheticRawSequence });
  assert.equal(built.length, golden.model.length);
  for (const item of built) {
    assert.ok(expected.has(item.id), item.id);
    assert.equal(item.sequence.length, expected.get(item.id).length, item.id);
    const fixed = resample(item.sequence, inputs.fixed_frames);
    assert.equal(await sha256Hex(float32Bytes(fixed)), expected.get(item.id).input_sha256, item.id);
  }
});

test("the self-test page's made-up signs are unchanged by moving the signer into synthetic_sign.js", () => {
  // web/src/asl_selftest.js used seeds 11/22/33 with the alternating pattern before the move; the
  // baseline recorded the same three signs (syn_s11/s22/s33), so equal inputs prove equal behaviour.
  const ids = inputs.synthetic.filter((s) => s.pattern === "alternating").map((s) => s.seed);
  assert.deepEqual(ids, [11, 22, 33]);
  const first = syntheticRawSequence(11, 2)[0];
  assert.equal(first.face.length, 478);
  assert.equal(first.hands.length, 1); // frame 0: one hand (t % 5 === 0)
});
