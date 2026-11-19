// ASL mode (fast track Stage 2): browser port of ml_engine/asl_islr.py. ASL is a separate language
// mode (CLAUDE.md 8.2): nothing here is PSL, and nothing here may be shown as PSL.
//
// Turns capture v2's raw landmarker output into the Google Isolated Sign Language Recognition layout
// (frames x 543 x 3: face 468, left hand 21, pose 33, right hand 21; NaN where missing), cuts the
// live stream into single signs, and rewrites the model file so LiteRT.js (which cannot take a variable
// number of frames) gets a fixed frame count. Follows shared_data/asl_islr_spec.json; Python and this
// file must give identical results (tests/test_asl_islr.py runs tests/tools/dump-asl.mjs).
import { canonicalizeFrame } from "./features_v2.js";
import { assetUrl } from "./paths.js";

export const ASL_FEATURE_VERSION = "asl-islr-543-v1";

export function checkAslSpec(spec) {
  if (!spec || spec.feature_version !== ASL_FEATURE_VERSION) throw new Error(`Unsupported ASL feature version ${spec?.feature_version}`);
  if (spec.sign_language !== "ASL") throw new Error("The ASL spec must say sign_language ASL");
  return spec;
}

export async function loadAslSpec(url = assetUrl("asl_islr_spec.json")) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`ASL spec could not be loaded (${response.status}). Run npm run assets.`);
  return checkAslSpec(await response.json());
}

function parts(spec) {
  const out = {};
  for (const part of spec.layout.parts) out[part.name] = [part.start, part.count];
  return out;
}

function put(frame, part, points, layoutParts) {
  if (points === null || points === undefined) return;
  const [start, count] = layoutParts[part];
  if (points.length < count) throw new Error(`${part} needs at least ${count} points, got ${points.length}`);
  for (let offset = 0; offset < count; offset += 1) {
    const point = points[offset];
    frame[start + offset] = [Number(point[0]), Number(point[1]), Number(point[2])];
  }
}

// 543 x [x, y, z] for one frame of raw capture v2 output. Hands go to the competition's left/right
// slots by the signer's anatomical side, decided exactly as features v2 does (pose wrists first).
export function islrFrame(raw, featureSpec, aslSpec) {
  if (raw.input_mirrored) throw new Error("ASL mode needs unmirrored frames: mirror only the display (shared_data/asl_islr_spec.json)");
  const canonical = canonicalizeFrame(raw, featureSpec);
  const layoutParts = parts(aslSpec);
  const frame = Array.from({ length: aslSpec.layout.rows_per_frame }, () => [NaN, NaN, NaN]);
  put(frame, "face", raw.face ?? null, layoutParts);
  put(frame, "pose", raw.pose ?? null, layoutParts);
  put(frame, "left_hand", canonical.left_hand, layoutParts);
  put(frame, "right_hand", canonical.right_hand, layoutParts);
  return frame;
}

export function handCounts(frame, aslSpec) {
  const layoutParts = parts(aslSpec);
  return [!Number.isNaN(frame[layoutParts.left_hand[0]][0]), !Number.isNaN(frame[layoutParts.right_hand[0]][0])];
}

export function handsPresent(frame, aslSpec) {
  const [left, right] = handCounts(frame, aslSpec);
  return left || right;
}

// Nearest-frame indices that turn `length` frames into `frames` frames (integer arithmetic only).
export function resampleIndices(length, frames) {
  if (!Number.isInteger(length) || !Number.isInteger(frames) || length < 1 || frames < 1) throw new Error("length and frames must be integers of at least 1");
  if (frames === 1) return [0];
  const out = [];
  for (let i = 0; i < frames; i += 1) out.push(Math.floor((2 * i * (length - 1) + (frames - 1)) / (2 * (frames - 1))));
  return out;
}

export function resample(sequence, frames) {
  return resampleIndices(sequence.length, frames).map((index) => sequence[index]);
}

// frames x 543 x 3 as one Float32Array (NaN kept), ready for a model input tensor.
export function toFloat32(sequence, rowsPerFrame = 543) {
  const out = new Float32Array(sequence.length * rowsPerFrame * 3);
  let k = 0;
  for (const frame of sequence) {
    if (frame.length !== rowsPerFrame) throw new Error(`each frame needs ${rowsPerFrame} rows`);
    for (const point of frame) { out[k] = point[0]; out[k + 1] = point[1]; out[k + 2] = point[2]; k += 3; }
  }
  return out;
}

// JSON for the local server: NaN is not valid JSON, so missing values travel as null.
export function sequenceForJson(sequence) {
  return sequence.map((frame) => frame.map((point) => point.map((value) => (Number.isNaN(value) ? null : value))));
}

// Cut a live stream of 543-row frames into single signs (shared_data/asl_islr_spec.json, segmentation).
export class SignSegmenter {
  constructor(aslSpec) {
    const rules = aslSpec.segmentation;
    this.aslSpec = aslSpec;
    this.minHandFrames = rules.min_hand_frames;
    this.endAfter = rules.end_after_missing_frames;
    this.margin = rules.margin_frames;
    this.maxFrames = rules.max_frames;
    this.reset();
  }

  reset() {
    this.before = [];
    this.sign = [];
    this.isActive = false;
    this.missing = 0;
    this.handFrames = 0;
  }

  get active() { return this.isActive; }

  finish(keep) {
    const sign = this.sign.slice(0, keep);
    const longEnough = this.handFrames >= this.minHandFrames;
    const tail = this.sign.slice(keep);
    this.reset();
    this.before = this.margin ? tail.slice(-this.margin) : [];
    return longEnough ? sign : null;
  }

  push(frame, present = null) {
    const has = present === null ? handsPresent(frame, this.aslSpec) : Boolean(present);
    if (!this.isActive) {
      if (!has) {
        if (this.margin) { this.before.push(frame); this.before = this.before.slice(-this.margin); }
        return null;
      }
      this.isActive = true;
      this.sign = [...this.before, frame];
      this.before = [];
      this.missing = 0;
      this.handFrames = 1;
      return null;
    }
    this.sign.push(frame);
    if (has) { this.missing = 0; this.handFrames += 1; } else this.missing += 1;
    if (this.missing >= this.endAfter) return this.finish(this.sign.length - this.missing + this.margin);
    if (this.sign.length >= this.maxFrames) return this.finish(this.sign.length);
    return null;
  }

  flush() {
    if (!this.isActive) return null;
    return this.finish(this.sign.length - this.missing + Math.min(this.missing, this.margin));
  }
}

// The model's 250 outputs as probabilities: kept if they already are, otherwise softmax.
export function probabilities(scores) {
  const values = Array.from(scores, Number);
  const sum = values.reduce((a, b) => a + b, 0);
  if (values.length && values.every((v) => v >= 0 && v <= 1) && Math.abs(sum - 1) < 1e-3) return values;
  const top = Math.max(...values);
  const exps = values.map((v) => Math.exp(v - top));
  const total = exps.reduce((a, b) => a + b, 0);
  return exps.map((e) => e / total);
}

export function labelsFromIndexMap(indexMap, count) {
  const labels = new Array(Object.keys(indexMap).length).fill(null);
  for (const [label, index] of Object.entries(indexMap)) labels[Number(index)] = label;
  if (labels.length !== count || labels.some((label) => label === null)) throw new Error(`the class map does not hold ${count} distinct indices`);
  return labels;
}

export function displayName(label, aslSpec) {
  return aslSpec.display_names[label] ?? label;
}

export function topK(scores, labels, k, aslSpec) {
  const probs = probabilities(scores);
  const order = probs.map((p, i) => i).sort((a, b) => probs[b] - probs[a] || a - b).slice(0, k);
  return order.map((i) => ({ label: labels[i], display: displayName(labels[i], aslSpec), probability: probs[i] }));
}

// 'sure', 'unsure' or 'none'. Only 'sure' results may be spoken (CLAUDE.md 1).
export function confidenceBand(probability, aslSpec) {
  const rules = aslSpec.confidence;
  if (probability >= rules.sure) return "sure";
  if (probability >= rules.unsure) return "unsure";
  return "none";
}

// ------------------------------------------------------------------ TFLite flatbuffer: read and patch the input

function reader(bytes) {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const u32 = (o) => view.getUint32(o, true);
  const i32 = (o) => view.getInt32(o, true);
  const u16 = (o) => view.getUint16(o, true);
  const table = (pos) => ({ pos, vt: pos - i32(pos) });
  const field = (t, id) => {
    const size = u16(t.vt);
    const off = 4 + 2 * id;
    if (off >= size) return 0;
    const rel = u16(t.vt + off);
    return rel ? t.pos + rel : 0;
  };
  const ref = (o) => o + u32(o);
  const vector = (t, id) => { const o = field(t, id); if (!o) return null; const v = ref(o); return { length: u32(v), start: v + 4 }; };
  const tables = (t, id) => { const v = vector(t, id); return v ? Array.from({ length: v.length }, (_, i) => table(ref(v.start + 4 * i))) : []; };
  const ints = (t, id) => { const v = vector(t, id); return v ? { values: Array.from({ length: v.length }, (_, i) => i32(v.start + 4 * i)), start: v.start } : null; };
  return { view, u32, table, field, ref, tables, ints };
}

function inputTensor(bytes) {
  const r = reader(bytes);
  if (bytes.byteLength < 8 || String.fromCharCode(...bytes.subarray(4, 8)) !== "TFL3") throw new Error("not a TFLite model (no TFL3 identifier)");
  const model = r.table(r.ref(0));
  const subgraph = r.tables(model, 2)[0];
  if (!subgraph) throw new Error("the model has no subgraph");
  const inputs = r.ints(subgraph, 1);
  if (!inputs || inputs.values.length !== 1) throw new Error("expected exactly one model input");
  const tensor = r.tables(subgraph, 0)[inputs.values[0]];
  return { shape: r.ints(tensor, 0), signature: r.ints(tensor, 7) };
}

// { shape, signature } of the first subgraph's input tensor.
export function readTfliteInput(bytes) {
  const { shape, signature } = inputTensor(bytes);
  return { shape: shape?.values ?? null, signature: signature?.values ?? null };
}

// A copy of the model whose input is frames x 543 x 3 instead of [-1, 543, 3]. Only the first dimension
// of the input tensor's shape and shape signature changes; every other byte stays the same.
export function patchTfliteFrames(bytes, frames, rowsPerFrame = 543) {
  if (!Number.isInteger(frames) || frames < 1) throw new Error("frames must be a positive integer");
  const source = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  const { shape, signature } = inputTensor(source);
  if (!shape || shape.values.length !== 3 || shape.values[1] !== rowsPerFrame || shape.values[2] !== 3) throw new Error(`unexpected model input shape ${JSON.stringify(shape?.values)}`);
  if (signature && (signature.values.length !== 3 || signature.values[1] !== rowsPerFrame || signature.values[2] !== 3)) throw new Error(`unexpected model input signature ${JSON.stringify(signature.values)}`);
  const copy = new Uint8Array(source);
  const view = new DataView(copy.buffer, copy.byteOffset, copy.byteLength);
  view.setInt32(shape.start, frames, true);
  if (signature) view.setInt32(signature.start, frames, true);
  return copy;
}
