// The website's own files are found next to the current page, so the same build works at a site root
// and under a GitHub Pages sub-path (src/paths.js).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { assetUrl, HAS_SERVER } from "../src/paths.js";

const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src");

test("files resolve next to the page, at a root or under a sub-path", () => {
  assert.equal(assetUrl("models/asl/model.tflite", "./", "https://u.github.io/SignBridge/"), "https://u.github.io/SignBridge/models/asl/model.tflite");
  assert.equal(assetUrl("/wasm", "./", "https://u.github.io/SignBridge/index.html"), "https://u.github.io/SignBridge/wasm");
  assert.equal(assetUrl("litert/", "./", "https://u.github.io/SignBridge/asl-selftest.html"), "https://u.github.io/SignBridge/litert/");
  assert.equal(assetUrl("vocabulary.json", "/", "http://localhost:5173/"), "http://localhost:5173/vocabulary.json");
  assert.equal(HAS_SERVER, true, "without VITE_API_BASE the local server is expected");
});

test("no source file fetches the website's own files from the site root", () => {
  const offenders = [];
  for (const name of readdirSync(src).filter((n) => /\.(js|jsx)$/.test(n))) {
    const text = readFileSync(path.join(src, name), "utf8");
    for (const match of text.matchAll(/["'`]\/(models|wasm|litert|vocabulary\.json|feature_spec_v2\.json|asl_islr_spec\.json)/g)) {
      offenders.push(`${name}: ${match[0]}`);
    }
  }
  assert.deepEqual(offenders, []);
});
