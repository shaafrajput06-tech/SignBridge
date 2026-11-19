// Web Worker that runs the ASL model off the page's main thread, so the camera view stays smooth.
// Messages: { id, type: "init", payload: { modelUrl, wasmPath, frames, sha256 } } and
//           { id, type: "run", payload: { input: Float32Array } }. Replies: { id, ok, result | error }.
import { createLiteRtAslModel } from "./asl_litert.js";

let model = null;

self.onmessage = async (event) => {
  const { id, type, payload } = event.data;
  try {
    let result;
    if (type === "init") {
      model?.close();
      model = await createLiteRtAslModel(payload);
      result = model.info;
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
