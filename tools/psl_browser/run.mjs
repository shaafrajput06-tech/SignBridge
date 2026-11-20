// Stage 2 gate, web part: the PSL bundle in a real browser gives the same top-1 as Python on the parity
// cases (tests/golden/psl_parity_cases.json, written by tools/psl_train with the shipped TFLite file).
//
//   node tools/psl_browser/run.mjs [bundle folder, default models/psl]
//
// Uses the frozen baseline build's LiteRT.js (baseline/v1-site, restored by python tools/baseline_v1.py
// restore ...) and Playwright's Chromium, like tools/baseline/run.mjs. Exit 3 = SKIPPED (missing pieces),
// unless BASELINE_REQUIRED=1.
import { createServer } from "node:http";
import { createRequire } from "node:module";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const site = path.join(project, "baseline", "v1-site");
const bundle = path.resolve(process.argv[2] || path.join(project, "models", "psl"));
const parityPath = existsSync(path.join(bundle, "parity_cases.json")) ? path.join(bundle, "parity_cases.json") : path.join(project, "tests", "golden", "psl_parity_cases.json");
const required = process.env.BASELINE_REQUIRED === "1";

function skip(message) {
  console.log(`${required ? "FAILED" : "SKIPPED"} PSL browser run: ${message}`);
  process.exit(required ? 1 : 3);
}

if (!existsSync(path.join(bundle, "manifest.json"))) skip(`no PSL bundle in ${bundle}`);
if (!existsSync(parityPath)) skip("no parity cases");
if (!existsSync(path.join(site, "assets", "asl_client-CAfZVWoY.js")) || !existsSync(path.join(site, "litert", "litert_wasm_internal.wasm"))) skip("the baseline build's runtime files are missing (python tools/baseline_v1.py restore ...)");
let chromium;
for (const base of [path.join(project, "web", "package.json"), path.join(project, "package.json"), process.env.PLAYWRIGHT_FROM && path.join(process.env.PLAYWRIGHT_FROM, "x.js")].filter(Boolean)) {
  try { ({ chromium } = createRequire(base)("playwright")); break; } catch { /* next */ }
}
if (!chromium) skip("Playwright is not installed");

const manifest = JSON.parse(readFileSync(path.join(bundle, "manifest.json"), "utf8"));
const types = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".mjs": "text/javascript", ".json": "application/json", ".wasm": "application/wasm", ".tflite": "application/octet-stream" };
const extra = {
  "/__psl.html": () => Buffer.from('<!doctype html><meta charset="utf-8"><title>PSL harness</title><script type="module" src="/__psl/harness.mjs"></script>'),
  "/__psl/harness.mjs": () => readFileSync(path.join(project, "tools", "psl_browser", "harness.mjs")),
  "/__psl/manifest.json": () => readFileSync(path.join(bundle, "manifest.json")),
  "/__psl/parity_cases.json": () => readFileSync(parityPath),
  [`/__psl/${manifest.model.file}`]: () => readFileSync(path.join(bundle, manifest.model.file)),
};
const server = createServer((request, response) => {
  const url = new URL(request.url, "http://127.0.0.1");
  let body = extra[url.pathname]?.() ?? null;
  if (!body) {
    const file = path.resolve(site, decodeURIComponent(url.pathname).replace(/^\/+/, ""));
    if (file.startsWith(site + path.sep) && existsSync(file)) body = readFileSync(file);
  }
  if (!body) { response.writeHead(404); response.end("not found"); return; }
  response.writeHead(200, { "Content-Type": types[path.extname(url.pathname)] || "application/octet-stream", "Cache-Control": "no-store" });
  response.end(body);
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const base = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {});
let result;
try {
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(`${base}/__psl.html`);
  await page.waitForFunction(() => window.__pslReady === true, null, { timeout: 60_000 }).catch(() => { throw new Error(`harness did not load: ${errors.join("; ")}`); });
  result = await page.evaluate(() => window.__runPsl());
  result.browser = browser.version();
} finally {
  await browser.close();
  server.close();
}
const same = result.cases.filter((c) => c.same_top1).length;
const gap = Math.max(...result.cases.map((c) => c.score_gap));
console.log(`PSL browser run (${result.runtime.runtime}, thread ${result.runtime.thread}, Chromium ${result.browser}): ${same}/${result.cases.length} cases with the same top-1 as Python; largest score difference ${gap.toFixed(5)}; median ${result.cases.map((c) => c.ms).sort((a, b) => a - b)[Math.floor(result.cases.length / 2)].toFixed(1)} ms per sign.`);
for (const c of result.cases.filter((x) => !x.same_top1)) console.log(`  ${c.sign}: browser ${c.top5.join(",")} vs Python ${c.expected_top5.join(",")}`);
process.exit(same === result.cases.length ? 0 : 1);
