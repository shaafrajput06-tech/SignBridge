// Print the JavaScript ASL-mode results for the shared cases as JSON on stdout.
// tests/test_asl_islr.py runs this and compares every value with ml_engine/asl_islr.py.
// Usage (from the project root): node web/tests/tools/dump-asl.mjs
import { readFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { checkAslSpec, islrFrame, probabilities, resampleIndices, SignSegmenter, topK, labelsFromIndexMap, confidenceBand } from "../../src/asl_islr.js";

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
const featureSpec = JSON.parse(readFileSync(path.join(project, "shared_data/feature_spec_v2.json"), "utf8"));
const aslSpec = checkAslSpec(JSON.parse(readFileSync(path.join(project, "shared_data/asl_islr_spec.json"), "utf8")));
const fixture = JSON.parse(gunzipSync(readFileSync(path.join(project, "tests/golden/v2_holistic.json.gz"))).toString("utf8"));
const cases = JSON.parse(readFileSync(path.join(project, "tests/golden/asl_islr_cases.json"), "utf8"));
const labels = labelsFromIndexMap(JSON.parse(readFileSync(path.join(project, aslSpec.classes.file), "utf8")), aslSpec.classes.count);

const nanToNull = (frame) => frame.map((point) => point.map((value) => (Number.isNaN(value) ? null : value)));

const frames = fixture.canonicalize_cases.map((item) => {
  try {
    return { id: item.id, frame: nanToNull(islrFrame(item.raw, featureSpec, aslSpec)) };
  } catch (error) {
    return { id: item.id, error: String(error.message || error) };
  }
});

const resampling = cases.resample.map(([length, count]) => resampleIndices(length, count));

const segments = cases.segmenter_streams.map((stream) => {
  const segmenter = new SignSegmenter(aslSpec);
  const out = [];
  stream.forEach((present, index) => {
    const sign = segmenter.push(index, Boolean(present));
    if (sign) out.push(sign);
  });
  const rest = segmenter.flush();
  if (rest) out.push(rest);
  return out;
});

const scores = cases.scores.map((vector) => ({
  probabilities: probabilities(vector),
  top: topK(vector, labels, 5, aslSpec),
  band: confidenceBand(probabilities(vector).reduce((a, b) => Math.max(a, b), 0), aslSpec),
}));

process.stdout.write(JSON.stringify({ frames, resampling, segments, scores }));
