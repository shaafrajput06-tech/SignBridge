// Personal adaptation (master-v3 Stage 4): each time the person confirms a PSL suggestion, a small per-sign
// bias on top of the model's scores is nudged towards what they confirmed. It stays in this browser
// (localStorage), never leaves the device, never adds a sign, and "Forget" removes it.
// Same maths as tools/psl_train/personal.py, which measures it (reports/autopilot_v1.md).

export const PERSONAL_SETTINGS = { rate: 0.1, decay: 0.05, steps: 1, limit: 2 };
const STORE = "signbridge_psl_personal_v1";

function softmax(values) {
  const top = Math.max(...values);
  const e = values.map((v) => Math.exp(v - top));
  const sum = e.reduce((a, b) => a + b, 0);
  return e.map((v) => v / sum);
}

export function emptyPersonal(bundleVersion, classes) {
  return { bundle: bundleVersion, bias: new Array(classes).fill(0), confirmed: 0 };
}

// Scores (log-probabilities) plus the personal bias.
export function adapt(scores, personal) {
  if (!personal || personal.bias.length !== scores.length) return Array.from(scores);
  return Array.from(scores, (value, i) => value + personal.bias[i]);
}

// A few gradient steps of cross-entropy on the confirmed sign, with weight decay, bias kept in [-limit, limit].
export function learn(personal, scores, confirmedIndex, settings = PERSONAL_SETTINGS) {
  const bias = personal.bias.slice();
  for (let step = 0; step < settings.steps; step += 1) {
    const p = softmax(Array.from(scores, (value, i) => value + bias[i]));
    for (let i = 0; i < bias.length; i += 1) {
      const gradient = p[i] - (i === confirmedIndex ? 1 : 0) + settings.decay * bias[i];
      bias[i] = Math.max(-settings.limit, Math.min(settings.limit, bias[i] - settings.rate * gradient));
    }
  }
  return { ...personal, bias, confirmed: personal.confirmed + 1 };
}

export function loadPersonal(bundleVersion, classes, storage = globalThis.localStorage) {
  try {
    const saved = JSON.parse(storage?.getItem(STORE) || "null");
    if (saved && saved.bundle === bundleVersion && saved.bias?.length === classes) return saved;
  } catch { /* storage unavailable or damaged: start fresh */ }
  return emptyPersonal(bundleVersion, classes);
}

export function savePersonal(personal, storage = globalThis.localStorage) {
  try { storage?.setItem(STORE, JSON.stringify(personal)); } catch { /* private mode: keep it for this visit only */ }
}

export function forgetPersonal(storage = globalThis.localStorage) {
  try { storage?.removeItem(STORE); } catch { /* nothing stored */ }
}
