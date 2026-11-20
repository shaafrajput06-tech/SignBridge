// Runs inside the frozen baseline build (baseline/v1-site) in a real browser, using the baseline's own
// bundled modules. Served by tools/baseline/run.mjs; never shipped. The import names below are the
// minified export names of the v1 bundles (checked against baseline/manifest.json by run.mjs).
import { n as loadFeatureSpecV2 } from "/assets/capture_v2-B1HThk3J.js";
import { a as SignSegmenter, c as islrFrame, d as probabilities, i as loadAslLabels, l as loadAslSpec, n as createBrowserAsl, p as resample } from "/assets/asl_client-CAfZVWoY.js";
import { band, float32Bytes, modelCases, pipelineOutputs, sha256Hex, topFive } from "/__baseline/cases.mjs";
import { syntheticRawSequence } from "/__baseline/synthetic_sign.js";

const median = (values) => { const v = [...values].sort((a, b) => a - b); return v[Math.floor(v.length / 2)]; };
const json = async (url) => { const r = await fetch(url); if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`); return r.json(); };

window.__runBaseline = async ({ repeats = 3 } = {}) => {
  const [featureSpec, aslSpec] = await Promise.all([loadFeatureSpecV2(), loadAslSpec()]);
  const labels = await loadAslLabels(aslSpec);
  const [fixture, cases, inputs] = await Promise.all([json("/__baseline/fixture.json"), json("/__baseline/asl_islr_cases.json"), json("/__baseline/inputs.json")]);
  const impl = { islrFrame, resample, SignSegmenter, probabilities };
  const pipeline = await pipelineOutputs(impl, { featureSpec, aslSpec, labels, fixture, cases });

  let recognizer = null;
  let workerError = null;
  try {
    recognizer = await createBrowserAsl({ aslSpec, labels, useWorker: true });
  } catch (error) {
    workerError = String(error.message || error);
    recognizer = await createBrowserAsl({ aslSpec, labels, useWorker: false });
  }
  const model = [];
  const timings = [];
  for (const item of modelCases(impl, { featureSpec, aslSpec, fixture, inputs, syntheticRawSequence })) {
    const fixed = resample(item.sequence, inputs.fixed_frames);
    const times = [];
    let scores = null;
    for (let i = 0; i < repeats; i += 1) {
      const reply = await recognizer.scoresFixed(fixed);
      if (i > 0 || repeats === 1) times.push(reply.ms);
      scores = reply.scores;
    }
    const probs = probabilities(scores);
    const top = topFive(probs, labels);
    model.push({ id: item.id, kind: item.kind, length: item.sequence.length, input_sha256: await sha256Hex(float32Bytes(fixed)), top, ...band(probs[top[0].index], aslSpec) });
    timings.push({ id: item.id, median_ms: Math.round(median(times) * 100) / 100 });
  }
  const info = recognizer.info;
  recognizer.close?.();
  return { pipeline, model, timings, runtime: { runtime: info.runtime, thread: info.thread, frames: info.frames, compile_ms: Math.round(info.compileMs ?? -1), worker_error: workerError }, user_agent: navigator.userAgent, hardware_concurrency: navigator.hardwareConcurrency };
};
window.__baselineReady = true;
