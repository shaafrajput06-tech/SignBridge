// PSL model input (shared_data/psl_hands_spec.json): the baseline's 543-point frames, resampled to the
// model's frame count, with the camera-shape rule applied to the two hands. The hands-view maths itself
// runs inside the model, so the web, Python and Flutter clients share it by construction; this file only
// builds the input. Reference: ml_engine/psl_hands.py (adjust_aspect); golden cases in
// tests/golden/psl_hands_cases.json.
import { resample, toFloat32 } from "./asl_islr.js";
import { assetUrl } from "./paths.js";

export const PSL_FEATURE_VERSIONS = ["psl-hands-v1"];
const HAND_ROWS = [[468, 21], [522, 21]];

export function checkPslSpec(spec) {
  if (!PSL_FEATURE_VERSIONS.includes(spec?.feature_version)) throw new Error(`unsupported PSL hands spec ${spec?.feature_version}`);
  const input = spec.model_input;
  if (!Number.isInteger(input?.frames) || !(input.aspect_reference > 0)) throw new Error("the PSL hands spec has no frame count or camera shape");
  return spec;
}

export async function loadPslSpec(url = assetUrl("psl_hands_spec.json")) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`PSL spec could not be loaded (${response.status}). Run npm run assets.`);
  return checkPslSpec(await response.json());
}

// One 543-point frame with the hands mapped from a camera of width/height `aspect` to the training
// camera's shape: x' = 0.5 + (x - 0.5) * aspect / reference, z' = z * aspect / reference. NaN stays NaN.
export function adjustAspect(frame, aspect, reference) {
  const ratio = aspect / reference;
  if (!Number.isFinite(ratio) || ratio <= 0) throw new Error(`invalid camera shape ${aspect}`);
  const out = frame.slice();
  for (const [start, count] of HAND_ROWS) {
    for (let i = start; i < start + count; i += 1) {
      const [x, y, z] = frame[i];
      out[i] = [0.5 + (x - 0.5) * ratio, y, z * ratio];
    }
  }
  return out;
}

// A cut-out sign (frames x 543 x 3, from SignSegmenter) -> the model's Float32Array input.
export function pslInput(sequence, aspect, spec) {
  const { frames, aspect_reference: reference } = spec.model_input;
  if (!sequence?.length) throw new Error("no frames to recognise");
  const fixed = resample(sequence, frames).map((frame) => adjustAspect(frame, aspect, reference));
  return toFloat32(fixed, 543);
}
