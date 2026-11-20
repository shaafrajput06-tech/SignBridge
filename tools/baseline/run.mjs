// Inference Baseline v1 in a real browser (master-v3.md section 0).
//
// Serves the frozen baseline build (baseline/v1-site) on 127.0.0.1, opens it in headless Chromium and
// runs tools/baseline/harness.mjs there: the baseline's own JavaScript and its own LiteRT.js worker turn
// the golden inputs into frames, segments, confidence words and the real model's top-5.
//
//   node tools/baseline/run.mjs            compare with tests/golden/baseline_v1_outputs.json (exit 1 if different)
//   node tools/baseline/run.mjs --record   write tests/golden/baseline_v1_outputs.json (only when re-freezing)
//   node tools/baseline/run.mjs --timings FILE   also write per-case model times (not part of the golden file)
//
// Needs: the baseline's third-party files (python tools/baseline_v1.py restore ...) and Playwright with
// Chromium (npm install --no-save playwright && npx playwright install chromium, in web/).
// CHROME_PATH=/path/to/chrome uses an installed Chrome instead of Playwright's Chromium.
// Prints "SKIPPED ..." and exits with code 3 when Playwright or the baseline files are missing
// (tools/run_all_tests.py reports that as SKIPPED), unless BASELINE_REQUIRED=1 (CI): then it fails.

import { createServer } from "node:http";
import { createRequire } from "node:module";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import { fileURLToPath } from "node:url";
import path from "node:path";

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const site = path.join(project, "baseline", "v1-site");
const goldenPath = path.join(project, "tests", "golden", "baseline_v1_outputs.json");
const args = process.argv.slice(2);
const record = args.includes("--record");
const timingsOut = args.includes("--timings") ? args[args.indexOf("--timings") + 1] : null;
const required = process.env.BASELINE_REQUIRED === "1";

function skip(message) {
  console.log(`${required ? "FAILED" : "SKIPPED"} baseline browser run: ${message}`);
  process.exit(required ? 1 : 3);
}

// 1. The baseline files: every file the model run needs must match the manifest (the clips are optional).
const manifest = JSON.parse(readFileSync(path.join(project, "baseline", "manifest.json"), "utf8"));
const sha256 = (file) => createHash("sha256").update(readFileSync(file)).digest("hex");
const problems = [];
for (const entry of manifest.files) {
  if (!entry.path.startsWith("site/") || entry.path.startsWith("site/clips/")) continue;
  const file = path.join(site, entry.path.slice("site/".length));
  if (!existsSync(file)) problems.push(`${entry.path} missing`);
  else if (sha256(file) !== entry.sha256) problems.push(`${entry.path} differs from the manifest`);
}
if (problems.length) skip(`${problems.length} baseline files missing or changed (first: ${problems[0]}). Run python tools/baseline_v1.py restore --download (or --from-sources).`);

// 2. Playwright.
let chromium;
for (const base of [path.join(project, "web", "package.json"), path.join(project, "package.json"), process.env.PLAYWRIGHT_FROM && path.join(process.env.PLAYWRIGHT_FROM, "x.js")].filter(Boolean)) {
  try { ({ chromium } = createRequire(base)("playwright")); break; } catch { /* try the next place */ }
}
if (!chromium) skip("Playwright is not installed (in web/: npm install --no-save playwright && npx playwright install chromium).");

// 3. A tiny static server: the baseline site, plus the harness files under /__baseline/.
const types = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".mjs": "text/javascript", ".json": "application/json", ".css": "text/css", ".wasm": "application/wasm", ".task": "application/octet-stream", ".tflite": "application/octet-stream", ".mp4": "video/mp4" };
const extra = {
  "/__baseline_harness.html": () => Buffer.from('<!doctype html><meta charset="utf-8"><title>baseline harness</title><script type="module" src="/__baseline/harness.mjs"></script>'),
  "/__baseline/harness.mjs": () => readFileSync(path.join(project, "tools", "baseline", "harness.mjs")),
  "/__baseline/cases.mjs": () => readFileSync(path.join(project, "tools", "baseline", "cases.mjs")),
  "/__baseline/synthetic_sign.js": () => readFileSync(path.join(project, "web", "src", "synthetic_sign.js")),
  "/__baseline/fixture.json": () => gunzipSync(readFileSync(path.join(project, "tests", "golden", "v2_holistic.json.gz"))),
  "/__baseline/asl_islr_cases.json": () => readFileSync(path.join(project, "tests", "golden", "asl_islr_cases.json")),
  "/__baseline/inputs.json": () => readFileSync(path.join(project, "tests", "golden", "baseline_v1_inputs.json")),
};
const server = createServer((request, response) => {
  const url = new URL(request.url, "http://127.0.0.1");
  let body = null;
  if (extra[url.pathname]) body = extra[url.pathname]();
  else {
    const relative = decodeURIComponent(url.pathname).replace(/^\/+/, "") || "index.html";
    const file = path.resolve(site, relative);
    if (file.startsWith(site + path.sep) && existsSync(file)) body = readFileSync(file);
  }
  if (!body) { response.writeHead(404); response.end("not found"); return; } // never an HTML fallback
  response.writeHead(200, { "Content-Type": types[path.extname(url.pathname)] || "application/octet-stream", "Cache-Control": "no-store" });
  response.end(body);
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const base = `http://127.0.0.1:${server.address().port}`;

// 4. Run the harness.
const launch = process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {};
const browser = await chromium.launch(launch);
let result;
try {
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(`${base}/__baseline_harness.html`);
  await page.waitForFunction(() => window.__baselineReady === true, null, { timeout: 60_000 }).catch(() => { throw new Error(`harness did not load: ${errors.join("; ") || "no page error"}`); });
  result = await page.evaluate(() => window.__runBaseline({ repeats: 3 }));
  result.browser_version = browser.version();
  if (errors.length) throw new Error(`page errors: ${errors.join("; ")}`);
} finally {
  await browser.close();
  server.close();
}

const { timings, ...outputs } = result;
if (timingsOut) writeFileSync(timingsOut, JSON.stringify({ measured_at: new Date().toISOString(), browser: result.browser_version, user_agent: result.user_agent, hardware_concurrency: result.hardware_concurrency, runtime: result.runtime, timings }, null, 2) + "\n");

const golden = {
  fixture: "SignBridge Inference Baseline v1: outputs",
  note: "What the frozen baseline build produces on tests/golden inputs, recorded by node tools/baseline/run.mjs --record. Synthetic inputs: these are not accuracy numbers.",
  baseline_zip_sha256: manifest.source_zip.sha256,
  model_sha256: "f55a2bb1ebe6d1e912a98e31c6ef3f995c9ae261f408fe115f2008099d3f0bb7",
  recorded_with: { browser: outputs.browser_version, runtime: outputs.runtime.runtime, thread: outputs.runtime.thread, frames: outputs.runtime.frames },
  tolerance: { probability_abs: 0.001 },
  pipeline: outputs.pipeline,
  model: outputs.model,
};

if (record) {
  writeFileSync(goldenPath, JSON.stringify(golden, null, 1) + "\n");
  console.log(`Recorded ${golden.model.length} model cases and the pipeline outputs into tests/golden/baseline_v1_outputs.json (${outputs.runtime.runtime}, thread ${outputs.runtime.thread}).`);
  process.exit(0);
}

// 5. Compare with the recorded outputs.
const expected = JSON.parse(readFileSync(goldenPath, "utf8"));
const diffs = [];
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
for (const key of ["frames", "resampling", "segments"]) if (!same(expected.pipeline[key], golden.pipeline[key])) diffs.push(`pipeline.${key} differs`);
expected.pipeline.scores.forEach((item, i) => {
  const got = golden.pipeline.scores[i];
  if (!got || item.band !== got.band || !same(item.top.map((t) => t.index), got.top.map((t) => t.index))) diffs.push(`pipeline.scores[${i}] differs`);
});
const tolerance = expected.tolerance.probability_abs;
for (const item of expected.model) {
  const got = golden.model.find((m) => m.id === item.id);
  if (!got) { diffs.push(`${item.id}: not produced`); continue; }
  if (got.input_sha256 !== item.input_sha256) diffs.push(`${item.id}: model input differs`);
  if (got.top[0].index !== item.top[0].index) diffs.push(`${item.id}: top-1 ${got.top[0].label}, expected ${item.top[0].label}`);
  const worst = Math.max(...item.top.map((t) => {
    const match = got.top.find((g) => g.index === t.index);
    return match ? Math.abs(match.probability - t.probability) : Infinity;
  }));
  if (worst > tolerance) diffs.push(`${item.id}: top-5 probabilities differ by up to ${worst}`);
  if (got.band !== item.band) diffs.push(`${item.id}: confidence ${got.band}, expected ${item.band}`);
}
console.log(`Baseline browser run (${outputs.runtime.runtime}, thread ${outputs.runtime.thread}${outputs.runtime.worker_error ? `, worker error: ${outputs.runtime.worker_error}` : ""}): ${golden.model.length} model cases, ${diffs.length} differences from the recorded outputs.`);
diffs.slice(0, 20).forEach((d) => console.log(`  ${d}`));
process.exit(diffs.length ? 1 : 0);
