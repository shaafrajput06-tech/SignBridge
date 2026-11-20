// The ASL model with LiteRT.js (Google's in-browser TFLite runtime), on CPU (WebAssembly + XNNPACK).
// LiteRT.js cannot take a variable number of frames, so the model's input is rewritten to
// frames x 543 x 3 (patchTfliteFrames) before it is compiled; callers resample each sign to that length.
// Used inside src/asl_worker.js, and on the main thread when a module worker is not available.
import { loadAndCompile, loadLiteRt, Tensor } from "@litertjs/core";
import { patchTfliteFrames, readTfliteInput } from "./asl_islr.js";
import { pointWasmAtRuntimeFolder } from "./wasm_locate.js";

let runtimeLoad = null;

async function sha256Hex(buffer) {
  if (!globalThis.crypto?.subtle) return null; // plain-http LAN pages have no WebCrypto; npm run assets checked the file already
  const digest = await globalThis.crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function details(list) {
  return list.map((item) => ({ name: item.name, shape: Array.from(item.shape), dtype: item.dtype }));
}

// Returns { info, run(Float32Array) -> { scores, ms }, close() }.
export async function createLiteRtAslModel({ modelUrl, wasmPath, frames, sha256, rowsPerFrame = 543 }) {
  const started = performance.now();
  const response = await fetch(modelUrl);
  if (!response.ok) throw new Error(`The ASL model file was not found (${response.status}). Start the website once with internet so npm run assets can download it.`);
  const buffer = await response.arrayBuffer();
  const hash = await sha256Hex(buffer);
  if (hash && hash !== sha256) throw new Error(`The ASL model file is not the pinned one (SHA-256 ${hash}).`);
  const bytes = new Uint8Array(buffer);
  const originalInput = readTfliteInput(bytes);
  const patched = patchTfliteFrames(bytes, frames, rowsPerFrame);
  pointWasmAtRuntimeFolder(wasmPath); // in the worker: .wasm files come from litert/, not assets/
  runtimeLoad ??= loadLiteRt(wasmPath);
  await runtimeLoad;
  const model = await loadAndCompile(patched, { accelerator: "wasm" });
  const info = {
    runtime: "LiteRT.js (wasm)",
    frames,
    hashChecked: Boolean(hash),
    originalInput,
    inputs: details(model.getInputDetails()),
    outputs: details(model.getOutputDetails()),
    compileMs: performance.now() - started,
  };

  async function run(input) {
    if (!(input instanceof Float32Array) || input.length !== frames * rowsPerFrame * 3) throw new Error(`expected ${frames} x ${rowsPerFrame} x 3 float32 values`);
    const tensor = new Tensor(input, [frames, rowsPerFrame, 3]);
    const begin = performance.now();
    let outputs;
    try {
      outputs = await model.run(tensor);
    } finally {
      tensor.delete();
    }
    try {
      const first = Array.isArray(outputs) ? outputs[0] : Object.values(outputs)[0];
      let data;
      try { data = first.toTypedArray(); } catch { data = await first.data(); }
      return { scores: Array.from(data), ms: performance.now() - begin };
    } finally {
      for (const tensorOut of Array.isArray(outputs) ? outputs : Object.values(outputs)) tensorOut.delete();
    }
  }

  return { info, run, close: () => model.delete() };
}
