// Chooses where the ASL model runs and gives the page one predict(sign) call.
//   "server":  the SignBridge server on this computer (ai-edge-litert); takes the sign's real length,
//              the way the model was built. Used when the server is running.
//   "browser": LiteRT.js in a Web Worker (or on the page if workers fail); the sign is resampled to the
//              fixed frame count in shared_data/asl_islr_spec.json. Works with no server at all.
// Either way only landmark numbers are used; no image leaves the browser.
import { confidenceBand, labelsFromIndexMap, resample, sequenceForJson, toFloat32, topK } from "./asl_islr.js";
import { API_BASE, HAS_SERVER, assetUrl } from "./paths.js";

export async function loadAslLabels(aslSpec, url = assetUrl("models/asl/sign_to_prediction_index_map.json")) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`The ASL class list was not found (${response.status}). Run npm run assets.`);
  return labelsFromIndexMap(await response.json(), aslSpec.classes.count);
}

function finish(scoresOrTop, labels, aslSpec, extra) {
  const top = Array.isArray(scoresOrTop) && typeof scoresOrTop[0] === "number" ? topK(scoresOrTop, labels, 5, aslSpec) : scoresOrTop;
  return { top, band: confidenceBand(top[0]?.probability ?? 0, aslSpec), ...extra };
}

export async function createServerAsl({ aslSpec, labels, api = API_BASE }) {
  const response = await fetch(`${api}/asl/status`);
  if (!response.ok) throw new Error(`server ASL status ${response.status}`);
  const status = await response.json();
  if (!status.available) throw new Error(status.reason || "the server cannot run the ASL model");
  if (status.feature_version !== aslSpec.feature_version) throw new Error(`the server uses ASL feature version ${status.feature_version}`);
  return {
    kind: "server",
    info: { runtime: `local server (${status.runtime})`, frames: null, ...status },
    async scores(sequence) {
      const reply = await fetch(`${api}/asl/predict`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ frames: sequenceForJson(sequence), scores: true }) });
      if (!reply.ok) throw new Error((await reply.json().catch(() => ({}))).detail || `server ASL predict ${reply.status}`);
      return reply.json();
    },
    async predict(sequence) {
      const body = await this.scores(sequence);
      return finish(body.top, labels, aslSpec, { ms: body.ms, frames: sequence.length, runtime: "server" });
    },
    close() {},
  };
}

function workerChannel(worker) {
  let nextId = 1;
  const waiting = new Map();
  worker.onmessage = (event) => {
    const { id, ok, result, error } = event.data;
    const entry = waiting.get(id);
    if (!entry) return;
    waiting.delete(id);
    if (ok) entry.resolve(result); else entry.reject(new Error(error));
  };
  worker.onerror = (event) => {
    for (const entry of waiting.values()) entry.reject(new Error(event.message || "the ASL worker stopped"));
    waiting.clear();
  };
  return (type, payload, transfer = []) => new Promise((resolve, reject) => {
    const id = nextId++;
    waiting.set(id, { resolve, reject });
    worker.postMessage({ id, type, payload }, transfer);
  });
}

// URLs are made absolute here, on the page: a worker would resolve relative ones against its own script.
export async function createBrowserAsl({ aslSpec, labels, useWorker = true, modelUrl = assetUrl("models/asl/model.tflite"), wasmPath = assetUrl("litert/") }) {
  const frames = aslSpec.fixed_length.frames;
  const options = { modelUrl, wasmPath, frames, sha256: aslSpec.model.sha256, rowsPerFrame: aslSpec.layout.rows_per_frame };
  let call;
  let info;
  let close;
  if (useWorker && typeof Worker !== "undefined") {
    const worker = new Worker(new URL("./asl_worker.js", import.meta.url), { type: "module" });
    call = workerChannel(worker);
    try {
      info = { ...(await call("init", options)), thread: "worker" };
    } catch (error) {
      worker.terminate();
      throw error;
    }
    close = () => worker.terminate();
  } else {
    const { createLiteRtAslModel } = await import("./asl_litert.js");
    const model = await createLiteRtAslModel(options);
    call = (type, payload) => model.run(payload.input);
    info = { ...model.info, thread: "page" };
    close = () => model.close();
  }
  return {
    kind: "browser",
    info,
    async scoresFixed(fixedSequence) {
      const input = toFloat32(fixedSequence, aslSpec.layout.rows_per_frame);
      return call("run", { input }, [input.buffer]);
    },
    async predict(sequence) {
      const result = await this.scoresFixed(resample(sequence, frames));
      return finish(result.scores, labels, aslSpec, { ms: result.ms, frames: sequence.length, runtime: "browser" });
    },
    close,
  };
}

// "auto": the server when it is running, otherwise the browser (worker first, then the page).
export async function createAslRecognizer({ aslSpec, labels, prefer = "auto", api = API_BASE }) {
  const errors = [];
  const serverPossible = HAS_SERVER && api !== "none";
  const attempts = prefer === "browser" || !serverPossible ? ["worker", "page"] : prefer === "server" ? ["server"] : ["server", "worker", "page"];
  for (const attempt of attempts) {
    try {
      if (attempt === "server") return await createServerAsl({ aslSpec, labels, api });
      return await createBrowserAsl({ aslSpec, labels, useWorker: attempt === "worker" });
    } catch (error) {
      errors.push(`${attempt}: ${error.message || error}`);
    }
  }
  throw new Error(`ASL mode could not start (${errors.join("; ")})`);
}
