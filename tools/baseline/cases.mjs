// Builds the Inference Baseline v1 cases from tests/golden/ inputs, given an implementation of the ASL
// pipeline (islrFrame, resample, SignSegmenter, probabilities). The same code runs:
//   - in the browser against the frozen baseline build (tools/baseline/harness.mjs), to record outputs;
//   - in Node against today's web/src/asl_islr.js (web/tests/inference-baseline.test.mjs), to compare.
// tests/test_inference_baseline.py mirrors it in Python for ml_engine/asl_islr.py.

// float32 little-endian bytes of frames x rows x 3, NaN written as 0x7fc00000 (one canonical NaN).
export function float32Bytes(sequence) {
  const values = [];
  for (const frame of sequence) for (const row of frame) for (const v of row) values.push(v);
  const view = new DataView(new ArrayBuffer(values.length * 4));
  values.forEach((v, i) => {
    if (Number.isNaN(v)) view.setUint32(i * 4, 0x7fc00000, true);
    else view.setFloat32(i * 4, v, true);
  });
  return new Uint8Array(view.buffer);
}

export async function sha256Hex(bytes) {
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

export function partsPresent(frame, aslSpec) {
  const out = {};
  for (const part of aslSpec.layout.parts) {
    let rows = 0;
    for (let r = part.start; r < part.start + part.count; r += 1) if (!Number.isNaN(frame[r][0])) rows += 1;
    out[part.name] = rows;
  }
  return out;
}

export function topFive(probs, labels) {
  return probs.map((p, i) => i).sort((a, b) => probs[b] - probs[a] || a - b).slice(0, 5)
    .map((i) => ({ index: i, label: labels[i], probability: Number(probs[i].toFixed(6)) }));
}

export function band(probability, aslSpec) {
  const c = aslSpec.confidence;
  const name = probability >= c.sure ? "sure" : probability >= c.unsure ? "unsure" : "none";
  return { band: name, words: c.words[name] };
}

// Everything that needs no model: frames, resampling, segmentation, scores -> words.
export async function pipelineOutputs(impl, { featureSpec, aslSpec, labels, fixture, cases }) {
  const frames = [];
  for (const item of fixture.canonicalize_cases) {
    try {
      const frame = impl.islrFrame(item.raw, featureSpec, aslSpec);
      frames.push({ id: item.id, sha256: await sha256Hex(float32Bytes([frame])), parts: partsPresent(frame, aslSpec) });
    } catch (error) {
      frames.push({ id: item.id, refused: true });
    }
  }
  const resampling = cases.resample.map(([length, count]) => ({ length, count, indices: impl.resample(Array.from({ length }, (_, i) => i), count) }));
  const segments = cases.segmenter_streams.map((stream) => {
    const segmenter = new impl.SignSegmenter(aslSpec);
    const out = [];
    stream.forEach((present, index) => { const sign = segmenter.push(index, Boolean(present)); if (sign) out.push(sign); });
    const rest = segmenter.flush();
    if (rest) out.push(rest);
    return out.map((sign) => [sign[0], sign[sign.length - 1], sign.length]);
  });
  const scores = cases.scores.map((vector) => {
    const probs = impl.probabilities(vector);
    const top = topFive(probs, labels);
    return { top, ...band(probs[top[0].index], aslSpec) };
  });
  return { frames, resampling, segments, scores };
}

// The model inputs: id, kind, length and the frames x 543 x 3 sequence before resampling.
// syntheticRawSequence: from web/src/synthetic_sign.js (passed in, so this file has no imports).
export function modelCases(impl, { featureSpec, aslSpec, fixture, inputs, syntheticRawSequence }) {
  const unmirrored = fixture.canonicalize_cases.filter((item) => !item.raw.input_mirrored).map((item) => ({ id: item.id, frame: impl.islrFrame(item.raw, featureSpec, aslSpec) }));
  const out = [];
  for (const item of unmirrored) {
    out.push({ id: `static_${item.id}`, kind: "static", sequence: Array.from({ length: inputs.static.repeat }, () => item.frame) });
  }
  for (const mix of inputs.mix) {
    out.push({ id: mix.id, kind: "mix", sequence: Array.from({ length: mix.length }, (_, j) => unmirrored[(7 * j + mix.offset) % unmirrored.length].frame) });
  }
  for (const syn of inputs.synthetic) {
    out.push({ id: syn.id, kind: "synthetic", sequence: syntheticRawSequence(syn.seed, syn.length, syn.pattern).map((raw) => impl.islrFrame(raw, featureSpec, aslSpec)) });
  }
  return out;
}
