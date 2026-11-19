// Capture v2 frame-rate benchmark (Phase 1 gate: >= 24 fps on a mid-range laptop browser).
// Open http://localhost:5173/bench.html after `npm run dev`. The result names the device and browser
// so it can be pasted into the Phase 1 handoff. Video frames are only read in memory.
import { createCaptureV2, loadFeatureSpecV2 } from "./capture_v2.js";

const $ = (id) => document.getElementById(id);
let lastResult = null;

function percentile(values, fraction) {
  if (!values.length) return 0;
  const ordered = [...values].sort((a, b) => a - b);
  return ordered[Math.min(ordered.length - 1, Math.floor(fraction * ordered.length))];
}

function gpuName() {
  try {
    const gl = document.createElement("canvas").getContext("webgl");
    const info = gl && gl.getExtension("WEBGL_debug_renderer_info");
    return info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : "unknown";
  } catch {
    return "unknown";
  }
}

async function run() {
  $("start").disabled = true;
  $("copy").disabled = true;
  const seconds = Math.max(5, Math.min(120, Number($("seconds").value) || 30));
  const [width, height] = $("resolution").value.split("x").map(Number);
  const parts = $("face").checked ? ["hands", "pose", "face"] : ["hands", "pose"];
  const output = $("output");
  let stream;
  let capture;
  try {
    output.textContent = "Loading models...";
    const spec = await loadFeatureSpecV2();
    capture = await createCaptureV2({ spec, parts });
    stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: width }, height: { ideal: height } }, audio: false });
    const video = $("video");
    video.srcObject = stream;
    await video.play();

    const perFrame = [];
    const partMs = { hands: [], pose: [], face: [] };
    const seen = { left_hand: 0, right_hand: 0, pose: 0, face: 0 };
    let frames = 0;
    let warmup = 30;
    let started = 0;
    const deadline = () => started && performance.now() - started >= seconds * 1000;
    await new Promise((resolve) => {
      const step = () => {
        if (deadline()) return resolve();
        const t0 = performance.now();
        const result = capture.processVideoFrame(video, t0);
        const t1 = performance.now();
        if (result) {
          if (warmup > 0) {
            warmup -= 1;
            if (warmup === 0) started = performance.now();
          } else {
            frames += 1;
            perFrame.push(t1 - t0);
            for (const [part, ms] of Object.entries(result.timings)) partMs[part].push(ms);
            for (const key of Object.keys(seen)) if (result.frame[key]) seen[key] += 1;
            if (frames % 15 === 0) output.textContent = `Measuring... ${((performance.now() - started) / 1000).toFixed(0)} s, ${capture.fps.toFixed(1)} fps`;
          }
        }
        if ("requestVideoFrameCallback" in video) video.requestVideoFrameCallback(step);
        else requestAnimationFrame(step);
      };
      step();
    });
    const elapsed = (performance.now() - started) / 1000;
    const track = stream.getVideoTracks()[0].getSettings();
    lastResult = {
      benchmark: "SignBridge capture v2",
      feature_version: spec.feature_version,
      spec_version: spec.spec_version,
      measured_at: new Date().toISOString(),
      seconds: Number(elapsed.toFixed(2)),
      frames,
      fps: Number((frames / elapsed).toFixed(2)),
      gate_24_fps: frames / elapsed >= 24 ? "PASS" : "FAIL",
      per_frame_ms: { mean: Number((perFrame.reduce((a, b) => a + b, 0) / Math.max(1, perFrame.length)).toFixed(2)), p95: Number(percentile(perFrame, 0.95).toFixed(2)) },
      per_part_ms_mean: Object.fromEntries(Object.entries(partMs).filter(([, v]) => v.length).map(([k, v]) => [k, Number((v.reduce((a, b) => a + b, 0) / v.length).toFixed(2))])),
      detected_share: Object.fromEntries(Object.entries(seen).map(([k, v]) => [k, Number((v / Math.max(1, frames)).toFixed(3))])),
      parts: capture.parts,
      delegates: capture.delegates,
      camera: { width: track.width, height: track.height, frame_rate: track.frameRate },
      device: { user_agent: navigator.userAgent, cpu_threads: navigator.hardwareConcurrency, memory_gb: navigator.deviceMemory ?? null, gpu: gpuName() },
      note: "Camera frame rate caps the result: a 30 fps camera cannot show more than about 30 fps.",
    };
    output.textContent = JSON.stringify(lastResult, null, 2);
    $("copy").disabled = false;
  } catch (error) {
    output.textContent = `Benchmark failed: ${error && error.message ? error.message : error}`;
  } finally {
    if (stream) for (const track of stream.getTracks()) track.stop();
    if (capture) capture.close();
    $("start").disabled = false;
  }
}

$("start").addEventListener("click", run);
$("copy").addEventListener("click", () => {
  if (lastResult) navigator.clipboard.writeText(JSON.stringify(lastResult, null, 2)).catch(() => {});
});
