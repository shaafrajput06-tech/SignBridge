// CLAUDE.md 8.4: every recogniser in every client tracks both hands at once. This scans the web app for
// MediaPipe HandLandmarker settings so a one-hand setting (as in the Phase 0 detector) cannot come back.
import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "src");
const files = readdirSync(src).filter((name) => /\.(js|jsx)$/.test(name));

test("every numHands setting in the web app asks for two hands", () => {
  const settings = [];
  for (const name of files) {
    for (const match of readFileSync(path.join(src, name), "utf8").matchAll(/numHands\s*:\s*([^,\n}]+)/g)) {
      settings.push({ name, value: match[1].trim() });
    }
  }
  assert.ok(settings.length >= 2, `expected the Phase 0 detector and capture v2, found ${JSON.stringify(settings)}`);
  for (const { name, value } of settings) {
    assert.ok(value === "2" || value === "models.hand.num", `${name} sets numHands to ${value}`);
  }
});

test("the PSL screen uses capture v2 (both hands, pose, face), not the one-hand Phase 0 detector", () => {
  const app = readFileSync(path.join(src, "App.jsx"), "utf8");
  assert.match(app, /createCaptureV2\(/);
  assert.doesNotMatch(app, /createHandDetector\(/);
});
