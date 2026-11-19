// ASL mode self-test (web/asl-selftest.html). No camera: made-up landmark sequences only.
// Reports: does the browser runtime (LiteRT.js) load and run, how long one sign takes, is it
// deterministic, and does it match the server runtime (ai-edge-litert) on the very same input.
import { loadFeatureSpecV2 } from "./capture_v2.js";
import { islrFrame, loadAslSpec, probabilities, resample } from "./asl_islr.js";
import { createBrowserAsl, createServerAsl, loadAslLabels } from "./asl_client.js";

const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");

function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// A made-up signer: body, face and hands that drift a little from frame to frame.
function syntheticRaw(rng, t, hands) {
  const jitter = (v, s) => v + (rng() - 0.5) * s;
  const cloud = (n, cx, cy, s) => Array.from({ length: n }, () => [jitter(cx, s), jitter(cy, s), jitter(0, 0.1)]);
  const swing = Math.sin(t / 4) * 0.08;
  const rightWrist = [0.32 + swing, 0.62 - swing];
  const leftWrist = [0.68 - swing, 0.64 + swing];
  const pose = cloud(33, 0.5, 0.62, 0.3).map((p) => [...p, 0.99]);
  pose[11] = [0.62, 0.55, 0, 0.99]; pose[12] = [0.38, 0.55, 0, 0.99];
  pose[15] = [...leftWrist, 0, 0.9]; pose[16] = [...rightWrist, 0, 0.9];
  const raw = { timestamp_ms: 1000 + 33 * t, image_width: 640, image_height: 480, input_mirrored: false, hands: [], pose, face: cloud(478, 0.5, 0.3, 0.12) };
  if (hands >= 1) { const h = cloud(21, ...rightWrist, 0.08); h[0] = [...rightWrist, 0]; raw.hands.push({ landmarks: h, handedness: "Left" }); }
  if (hands >= 2) { const h = cloud(21, ...leftWrist, 0.08); h[0] = [...leftWrist, 0]; raw.hands.push({ landmarks: h, handedness: "Right" }); }
  return raw;
}

function syntheticSign(seed, length, featureSpec, aslSpec) {
  const rng = mulberry32(seed);
  return Array.from({ length }, (_, t) => islrFrame(syntheticRaw(rng, t, t % 5 === 0 ? 1 : 2), featureSpec, aslSpec));
}

const median = (values) => { const v = [...values].sort((a, b) => a - b); return v[Math.floor(v.length / 2)]; };
const maxDiff = (a, b) => a.reduce((m, value, i) => Math.max(m, Math.abs(value - b[i])), 0);
const argmax = (values) => values.reduce((best, value, i) => (value > values[best] ? i : best), 0);

async function main() {
  const summary = { page: "asl-selftest", userAgent: navigator.userAgent, hardwareConcurrency: navigator.hardwareConcurrency, startedAt: new Date().toISOString() };
  const [featureSpec, aslSpec] = await Promise.all([loadFeatureSpecV2(), loadAslSpec()]);
  const labels = await loadAslLabels(aslSpec);
  const frames = aslSpec.fixed_length.frames;
  const signs = [[11, 10], [22, frames], [33, 57]].map(([seed, length]) => ({ seed, length, sequence: syntheticSign(seed, length, featureSpec, aslSpec) }));
  summary.fixedFrames = frames;
  summary.signLengths = signs.map((s) => s.length);

  let browser = null;
  for (const useWorker of [true, false]) {
    try {
      browser = await createBrowserAsl({ aslSpec, labels, useWorker });
      summary.browser = { ok: true, ...browser.info };
      break;
    } catch (error) {
      summary[useWorker ? "browserWorkerError" : "browserPageError"] = String(error.message || error);
    }
  }
  if (!browser) summary.browser = { ok: false };

  let server = null;
  try {
    server = await createServerAsl({ aslSpec, labels });
    summary.server = { ok: true, ...server.info };
  } catch (error) {
    summary.server = { ok: false, reason: String(error.message || error) };
  }

  summary.signs = [];
  for (const sign of signs) {
    const fixed = resample(sign.sequence, frames);
    const entry = { seed: sign.seed, length: sign.length };
    if (browser) {
      const times = [];
      let first = null;
      let deterministic = true;
      for (let i = 0; i < 6; i += 1) {
        const { scores, ms } = await browser.scoresFixed(fixed);
        if (i > 0) times.push(ms);
        if (first === null) first = scores; else if (maxDiff(first, scores) !== 0) deterministic = false;
      }
      const probs = probabilities(first);
      entry.browser = {
        medianMs: Math.round(median(times) * 10) / 10,
        finite: first.every(Number.isFinite),
        probabilitySum: Math.round(probs.reduce((a, b) => a + b, 0) * 1e6) / 1e6,
        deterministic,
        top1: labels[argmax(probs)],
        top1Probability: Math.round(Math.max(...probs) * 1e4) / 1e4,
      };
      if (server) {
        const fixedReply = await server.scores(fixed);
        const serverProbs = probabilities(fixedReply.scores);
        entry.parityFixedInput = { maxAbsProbabilityDifference: maxDiff(probs, serverProbs), sameTop1: argmax(probs) === argmax(serverProbs), serverMs: fixedReply.ms };
      }
    }
    if (server) {
      const nativeReply = await server.scores(sign.sequence);
      entry.serverNative = { top1: nativeReply.top[0].label, top1Probability: nativeReply.top[0].probability, ms: nativeReply.ms };
    }
    summary.signs.push(entry);
  }
  summary.finishedAt = new Date().toISOString();
  const parity = summary.signs.map((s) => s.parityFixedInput).filter(Boolean);
  summary.verdict = {
    browserRuns: Boolean(browser) && summary.signs.every((s) => s.browser?.finite && s.browser.deterministic && Math.abs(s.browser.probabilitySum - 1) < 1e-3),
    serverRuns: Boolean(server),
    // The camera view stays smooth only when the model runs in the worker; the page thread is a fallback.
    workerRuns: summary.browser?.thread === "worker",
    runtimesAgree: parity.length ? parity.every((p) => p.sameTop1 && p.maxAbsProbabilityDifference < 1e-3) : null,
  };
  browser?.close();
  return summary;
}

main().then((summary) => {
  window.__aslSelfTest = summary;
  statusEl.textContent = `Done. Browser runtime: ${summary.verdict.browserRuns ? "works" : "FAILED"} (${summary.verdict.workerRuns ? "background worker" : "page thread fallback"}) · server runtime: ${summary.verdict.serverRuns ? "works" : "not available"} · runtimes agree: ${summary.verdict.runtimesAgree === null ? "not compared" : summary.verdict.runtimesAgree ? "yes" : "NO"}`;
  resultEl.textContent = JSON.stringify(summary, null, 2);
}).catch((error) => {
  window.__aslSelfTest = { error: String(error.message || error) };
  statusEl.textContent = `Self-test failed: ${error.message || error}`;
});
