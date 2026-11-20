// Runs in headless Chromium, served by tools/psl_browser/run.mjs; never shipped. Loads the PSL bundle with
// the LiteRT.js worker of the frozen baseline build (the same runtime version the website uses) and runs
// the parity cases: frames x 2 hands, turned into the 543-point input exactly as web/src/psl_hands.js does.
import { d as probabilities, n as createBrowserAsl } from "/assets/asl_client-CAfZVWoY.js";

const json = async (url) => { const r = await fetch(url); if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`); return r.json(); };

function frames(item) {
  const out = [];
  for (let t = 0; t < item.hands.length / 2; t += 1) {
    const frame = Array.from({ length: 543 }, () => [NaN, NaN, NaN]);
    item.hands[2 * t].forEach((p, i) => { frame[468 + i] = p.map((v) => (v === null ? NaN : v)); });
    item.hands[2 * t + 1].forEach((p, i) => { frame[522 + i] = p.map((v) => (v === null ? NaN : v)); });
    out.push(frame);
  }
  return out;
}

window.__runPsl = async () => {
  const [manifest, parity] = await Promise.all([json("/__psl/manifest.json"), json("/__psl/parity_cases.json")]);
  // The baseline's browser recogniser only needs the frame count, rows per frame and the pinned hash.
  const spec = { fixed_length: { frames: manifest.input.shape[0] }, layout: { rows_per_frame: 543 }, model: { sha256: manifest.model.sha256 } };
  const labels = manifest.classes.map((c) => c.gloss);
  let recognizer;
  let workerError = null;
  try {
    recognizer = await createBrowserAsl({ aslSpec: spec, labels, useWorker: true, modelUrl: `${location.origin}/__psl/${manifest.model.file}`, wasmPath: `${location.origin}/litert/` });
  } catch (error) {
    workerError = String(error.message || error);
    recognizer = await createBrowserAsl({ aslSpec: spec, labels, useWorker: false, modelUrl: `${location.origin}/__psl/${manifest.model.file}`, wasmPath: `${location.origin}/litert/` });
  }
  const cases = [];
  for (const item of parity.cases) {
    const reply = await recognizer.scoresFixed(frames(item));
    const p = probabilities(reply.scores);
    const order = p.map((v, i) => [v, i]).sort((a, b) => b[0] - a[0]).slice(0, 5).map(([, i]) => i);
    const scoreGap = Math.max(...item.top5.map((index, k) => Math.abs(reply.scores[index] - item.top5_scores[k])));
    cases.push({ sign: item.sign, top5: order, expected_top5: item.top5, same_top1: order[0] === item.top5[0], score_gap: scoreGap, ms: reply.ms });
  }
  const info = recognizer.info;
  recognizer.close?.();
  return { cases, runtime: { runtime: info.runtime, thread: info.thread, worker_error: workerError, compile_ms: Math.round(info.compileMs ?? -1) } };
};
window.__pslReady = true;
