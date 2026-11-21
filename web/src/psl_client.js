// The PSL recogniser in the browser: loads the versioned bundle (models/psl/manifest.json + model),
// refuses a bundle whose feature version this client does not support (CLAUDE.md 6), and runs it with
// LiteRT.js in the same Web Worker code as ASL mode. Only landmark numbers are used; no image leaves
// the browser. Every class carries its tier; Tier B signs are suggestions the person confirms.
import { probabilities } from "./asl_islr.js";
import { workerChannel } from "./asl_client.js";
import { PSL_FEATURE_VERSIONS, pslInput } from "./psl_hands.js";
import { assetUrl } from "./paths.js";

export function checkPslManifest(manifest) {
  if (manifest?.bundle !== "signbridge-psl" || manifest.sign_language !== "PSL") throw new Error("this is not a SignMate PSL bundle");
  if (!PSL_FEATURE_VERSIONS.includes(manifest.feature_version)) throw new Error(`this website does not support PSL feature version ${manifest.feature_version}; update SignMate`);
  const [frames, rows, values] = manifest.input?.shape ?? [];
  if (!Number.isInteger(frames) || rows !== 543 || values !== 3) throw new Error(`unexpected PSL model input ${JSON.stringify(manifest.input?.shape)}`);
  if (!/^[0-9a-f]{64}$/.test(manifest.model?.sha256 ?? "")) throw new Error("the PSL bundle has no SHA-256 for its model");
  if (!Array.isArray(manifest.classes) || manifest.classes.length !== manifest.output?.shape?.[0]) throw new Error("the PSL class list does not match the model output");
  manifest.classes.forEach((entry, index) => { if (entry.index !== index) throw new Error("PSL classes are out of order"); });
  return manifest;
}

export async function loadPslManifest(url = assetUrl("models/psl/manifest.json")) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`The PSL model is not installed (${response.status}).`);
  return checkPslManifest(await response.json());
}

// Scores -> the k most likely classes with their names, tier and probability.
export function rankPsl(scores, manifest, k = 5) {
  const p = probabilities(scores);
  return p.map((probability, index) => ({ probability, ...manifest.classes[index] }))
    .sort((a, b) => b.probability - a.probability)
    .slice(0, k)
    .map((entry) => ({ ...entry, unknown: entry.gloss === manifest.unknown_class }));
}

// "sure" / "unsure" / "none" from the bundle's thresholds; "not a sign" as the top answer is "none".
export function pslBand(top, manifest) {
  const first = top[0];
  if (!first || first.unknown) return "none";
  const { sure, unsure } = manifest.confidence;
  if (first.probability >= sure) return "sure";
  if (first.probability >= unsure) return "unsure";
  return "none";
}

// Tier B (and anything unvalidated) is never spoken by itself: the person confirms first (CLAUDE.md 1, 8.3).
export function speaksWithoutConfirmation(entry) {
  return entry?.tier === "A" && entry?.validated_by_deaf_signers === true;
}

export async function createPslRecognizer({ manifest, spec, useWorker = true, base = assetUrl("models/psl/"), wasmPath = assetUrl("litert/") }) {
  const frames = manifest.input.shape[0];
  if (frames !== spec.model_input.frames) throw new Error("the PSL bundle and the PSL spec disagree on the frame count");
  const options = { modelUrl: new URL(manifest.model.file, base).href, wasmPath, frames, sha256: manifest.model.sha256, rowsPerFrame: 543, name: "PSL" };
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
    info,
    async scores(sequence, aspect) {
      const input = pslInput(sequence, aspect, spec);
      return call("run", { input }, [input.buffer]);
    },
    // adjust(scores) -> scores lets the page add the person's own adaptation (personal.js) before ranking.
    async predict(sequence, aspect, adjust = (scores) => scores) {
      const result = await this.scores(sequence, aspect);
      const scores = adjust(result.scores);
      const top = rankPsl(scores, manifest);
      return { top, band: pslBand(top, manifest), ms: result.ms, frames: sequence.length, scores: result.scores };
    },
    close,
  };
}
