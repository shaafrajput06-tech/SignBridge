// Browser smoke test with a fake camera: start the camera, then toggle voice, switch camera,
// and stop/start again. Each must leave hand tracking running without crashing the page.
//
// Run from the web folder:  npm run test:smoke   (builds first, then serves dist/ locally)
// Needs Playwright with Chromium. One-time setup, kept out of package.json so the exhibition
// install stays small:  npm install --no-save playwright && npx playwright install chromium
import { createRequire } from "node:module";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { preview } from "vite";

const webDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(import.meta.url);

let chromium;
try {
  ({ chromium } = require("playwright"));
} catch {
  console.log("SKIPPED camera smoke test: Playwright is not installed.");
  console.log("Install once with: npm install --no-save playwright && npx playwright install chromium");
  process.exit(0);
}
// SMOKE_URL tests a server that is already running instead, e.g. the dev server that
// start_web.bat starts:  set SMOKE_URL=http://127.0.0.1:5173/ && node tests/camera-smoke.mjs
const externalUrl = process.env.SMOKE_URL;
if (!externalUrl && !existsSync(path.join(webDir, "dist", "index.html"))) {
  console.error("dist/ is missing. Run npm run build first (npm run test:smoke does this for you).");
  process.exit(1);
}

const WAIT_MS = Number(process.env.SMOKE_WAIT_MS || 6000);
const server = externalUrl ? null : await preview({ root: webDir, logLevel: "silent", preview: { host: "127.0.0.1", port: 4174, strictPort: false, proxy: {} } });
const url = externalUrl || server.resolvedUrls.local[0];
console.log(`Camera smoke test against ${url}`);

async function scenario(name, action, expectedCameraStarts) {
  const browser = await chromium.launch({ args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream"] });
  const context = await browser.newContext({ permissions: ["camera"] });
  await context.addInitScript(() => {
    window.__cameraStarts = 0;
    const original = navigator.mediaDevices?.getUserMedia?.bind(navigator.mediaDevices);
    if (original) navigator.mediaDevices.getUserMedia = (...args) => { window.__cameraStarts += 1; return original(...args); };
  });
  const page = await context.newPage();
  const errors = [];
  let crashed = false;
  page.on("crash", () => { crashed = true; });
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => { if (/Aborted\(\)|recognition paused/i.test(message.text())) errors.push(message.text()); });
  const problems = [];
  try {
    await page.goto(url);
    await page.getByRole("button", { name: /Enable camera/ }).first().click();
    await page.locator(".help-modal input[type=checkbox]").check();
    await page.getByRole("button", { name: /Agree and enable camera/ }).click();
    await page.waitForTimeout(WAIT_MS);
    if (action) {
      await action(page);
      await page.waitForTimeout(WAIT_MS);
    }
    if (!crashed) {
      const errorPanel = await page.locator(".camera-placeholder").count();
      if (errorPanel) problems.push(`camera panel shows: ${(await page.locator(".camera-placeholder").innerText()).replace(/\s+/g, " ").slice(0, 140)}`);
      const indicator = (await page.locator(".camera-indicator").innerText()).trim();
      if (indicator !== "Camera on") problems.push(`indicator reads "${indicator}"`);
      const starts = await page.evaluate(() => window.__cameraStarts);
      if (expectedCameraStarts !== undefined && starts !== expectedCameraStarts) problems.push(`camera was started ${starts} times, expected ${expectedCameraStarts}`);
    }
  } catch (error) {
    if (!crashed) problems.push(`script error: ${error.message.split("\n")[0]}`);
  }
  if (crashed) problems.push("page crashed");
  if (errors.length) problems.push(`errors: ${[...new Set(errors)].slice(0, 3).join(" | ")}`);
  await browser.close().catch(() => {});
  console.log(`${problems.length ? "FAIL" : "PASS"}  ${name}${problems.length ? ` -> ${problems.join("; ")}` : ""}`);
  return problems.length === 0;
}

const results = [];
try {
  results.push(await scenario("camera starts and keeps running", null, 1));
  results.push(await scenario("voice toggle does not restart or break the camera", (page) => page.getByRole("button", { name: /^.?Voice (on|off)$/ }).first().click(), 1));
  results.push(await scenario("switching front/rear camera keeps tracking alive", (page) => page.getByRole("button", { name: /Switch front or rear camera/ }).click(), 2));
  results.push(await scenario("stop then start the camera again", async (page) => {
    await page.getByRole("button", { name: /Stop camera/ }).click();
    await page.waitForTimeout(1000);
    await page.getByRole("button", { name: /Enable camera/ }).first().click();
  }, 2));
} finally {
  await server?.close();
}
const failed = results.filter((ok) => !ok).length;
console.log(failed ? `${failed} of ${results.length} camera smoke scenarios failed` : `All ${results.length} camera smoke scenarios passed`);
process.exit(failed ? 1 : 0);
