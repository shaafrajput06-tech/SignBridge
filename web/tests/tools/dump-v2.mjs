// Print the JavaScript features v2 output for the whole golden fixture as JSON on stdout.
// Used by tests/test_features_v2.py to compare every value of every frame with Python.
// Usage (from the project root): node web/tests/tools/dump-v2.mjs [fixture.json.gz]
import { readFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { canonicalizeFrame, sequenceFeatures } from "../../src/features_v2.js";

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
const spec = JSON.parse(readFileSync(path.join(project, "shared_data/feature_spec_v2.json"), "utf8"));
const fixturePath = process.argv[2] || path.join(project, "tests/golden/v2_holistic.json.gz");
const fixture = JSON.parse(gunzipSync(readFileSync(fixturePath)).toString("utf8"));
const output = {
  canonical: fixture.canonicalize_cases.map((item) => canonicalizeFrame(item.raw, spec)),
  sequences: fixture.sequences.map((sequence) => {
    const result = sequenceFeatures(sequence.frames, spec);
    return { reference: result.reference, features: result.features.map((row) => Array.from(row)) };
  }),
};
process.stdout.write(JSON.stringify(output));
