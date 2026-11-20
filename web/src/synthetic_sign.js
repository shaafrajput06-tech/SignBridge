// Made-up signers for tests and the ASL self-test (no camera).
// NOT sign data: random landmark clouds that drift a little. Never train or evaluate on it.
// Used by web/src/asl_selftest.js, web/tests/inference-baseline.test.mjs and tools/baseline/harness.mjs,
// so the same seed always gives the same frames everywhere.

export function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// One raw capture v2 frame (unmirrored): body, face and 0-2 hands.
export function syntheticRaw(rng, t, hands) {
  const jitter = (v, s) => v + (rng() - 0.5) * s;
  const cloud = (n, cx, cy, s) => Array.from({ length: n }, () => [jitter(cx, s), jitter(cy, s), jitter(0, 0.1)]);
  const swing = Math.sin(t / 4) * 0.08;
  const rightWrist = [0.32 + swing, 0.62 - swing];
  const leftWrist = [0.68 - swing, 0.64 + swing];
  const pose = cloud(33, 0.5, 0.62, 0.3).map((p) => [...p, 0.99]);
  pose[11] = [0.62, 0.55, 0, 0.99]; pose[12] = [0.38, 0.55, 0, 0.99];
  pose[15] = [...leftWrist, 0, 0.9]; pose[16] = [...rightWrist, 0, 0.9];
  const raw = { timestamp_ms: 1000 + 33 * t, image_width: 640, image_height: 480, input_mirrored: false, hands: [], pose, face: cloud(478, 0.5, 0.3, 0.12) };
  if (hands >= 1) { const h = cloud(21, ...rightWrist, 0.08); h[0] = [...rightWrist, 0]; raw.hands.push({ landmarks: h, handedness: "Left" }); }
  if (hands >= 2) { const h = cloud(21, ...leftWrist, 0.08); h[0] = [...leftWrist, 0]; raw.hands.push({ landmarks: h, handedness: "Right" }); }
  return raw;
}

// How many hands are in view at frame t.
export const HAND_PATTERNS = {
  alternating: (t) => (t % 5 === 0 ? 1 : 2), // the self-test's pattern
  one: () => 1,
  two: () => 2,
  gap: (t) => (t >= 10 && t < 15 ? 0 : 2), // both hands, briefly out of view
};

export function syntheticRawSequence(seed, length, pattern = "alternating") {
  const handsAt = HAND_PATTERNS[pattern];
  if (!handsAt) throw new Error(`unknown hand pattern ${pattern}`);
  const rng = mulberry32(seed);
  return Array.from({ length }, (_, t) => syntheticRaw(rng, t, handsAt(t)));
}
