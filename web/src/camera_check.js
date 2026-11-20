// The 5-second camera check (master-v3 Stage 4, "self-calibration"): from the first seconds of tracking it
// tells the person, in plain words, whether the light, distance and framing will work. Uses only numbers the
// tracker already has and a tiny brightness sample of the video; nothing is stored or sent.

export function createCameraCheck({ frames = 150 } = {}) {
  const stats = { seen: 0, face: 0, pose: 0, hands: 0, handHeights: [], brightness: [] };
  return {
    stats,
    get done() { return stats.seen >= frames; },
    // frame: capture v2 canonical frame ({ left_hand, right_hand, pose, face } with normalised points)
    add(frame, brightness = null) {
      if (stats.seen >= frames) return;
      stats.seen += 1;
      if (frame?.face) stats.face += 1;
      if (frame?.pose) stats.pose += 1;
      const hands = [frame?.left_hand, frame?.right_hand].filter(Boolean);
      if (hands.length) stats.hands += 1;
      for (const hand of hands) {
        const ys = hand.map((point) => point[1]);
        stats.handHeights.push(Math.max(...ys) - Math.min(...ys));
      }
      if (brightness !== null) stats.brightness.push(brightness);
    },
  };
}

const median = (values) => { if (!values.length) return null; const v = [...values].sort((a, b) => a - b); return v[Math.floor(v.length / 2)]; };

// -> [{ id, ok, text }] advice, in the order a person should fix things.
export function cameraAdvice(stats) {
  const advice = [];
  const light = median(stats.brightness);
  if (light !== null) {
    if (light < 0.18) advice.push({ id: "light", ok: false, text: "It is quite dark. Face a window or a lamp." });
    else if (light > 0.85) advice.push({ id: "light", ok: false, text: "Very bright behind or on you. Avoid a window behind you." });
    else advice.push({ id: "light", ok: true, text: "Light is fine." });
  }
  const faceShare = stats.seen ? stats.face / stats.seen : 0;
  advice.push(faceShare >= 0.6 ? { id: "framing", ok: true, text: "Your face is in view." } : { id: "framing", ok: false, text: "Move so your face and shoulders are in the picture." });
  const size = median(stats.handHeights);
  if (size === null) advice.push({ id: "hands", ok: false, text: "Raise your hands in front of your chest so I can see them." });
  else if (size < 0.08) advice.push({ id: "distance", ok: false, text: "You are far away. Come a little closer." });
  else if (size > 0.45) advice.push({ id: "distance", ok: false, text: "You are very close. Move back a little so both hands fit." });
  else advice.push({ id: "distance", ok: true, text: "Distance is good." });
  return advice;
}

// Average brightness (0..1) of a video frame, from a 32 x 18 sample.
export function videoBrightness(video, canvas) {
  if (!video?.videoWidth) return null;
  canvas.width = 32;
  canvas.height = 18;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  context.drawImage(video, 0, 0, 32, 18);
  const { data } = context.getImageData(0, 0, 32, 18);
  let sum = 0;
  for (let i = 0; i < data.length; i += 4) sum += 0.2126 * data[i] + 0.7152 * data[i + 1] + 0.0722 * data[i + 2];
  return sum / (data.length / 4) / 255;
}
