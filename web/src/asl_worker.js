// Web Worker that runs the ASL model off the page's main thread, so the camera view stays smooth.
// Messages: { id, type: "init", payload: { modelUrl, wasmPath, frames, sha256 } } and
//           { id, type: "run", payload: { input: Float32Array } }. Replies: { id, ok, result | error }.
import { createLiteRtAslModel } from "./asl_litert.js";
import { installImportScriptsShim } from "./importscripts_shim.js";

let model = null;
let shimInstalled = null;

self.onmessage = async (event) => {
  const { id, type, payload } = event.data;
  try {
    let result;
    if (type === "init") {
      // LiteRT.js needs importScripts(), which module workers block; only the bundled runtime folder is allowed.
      shimInstalled ??= installImportScriptsShim({ scope: self, allowedPrefix: payload.wasmPath });
      model?.close();
      model = await createLiteRtAslModel(payload);
      result = { ...model.info, importScriptsShim: shimInstalled };
    } else if (type === "run") {
      if (!model) throw new Error("the ASL model is not loaded yet");
      result = await model.run(payload.input);
    } else {
      throw new Error(`unknown message ${type}`);
    }
    self.postMessage({ id, ok: true, result });
  } catch (error) {
    self.postMessage({ id, ok: false, error: String(error?.message || error) });
  }
};
