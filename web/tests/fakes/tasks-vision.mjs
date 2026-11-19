// Stand-in for @mediapipe/tasks-vision, used only by tests/capture-v2.test.mjs. It returns fixed
// landmarks in the shapes the real library returns, and records how capture_v2.js calls it.
export const calls = { created: [], detect: [], closed: [] };
export const settings = { failGpu: false, hands: [], pose: null, face: null };

class FakeTask {
  constructor(kind, options) { this.kind = kind; this.options = options; }
  static async createFromOptions(files, options) {
    if (settings.failGpu && options.baseOptions.delegate === "GPU") throw new Error("GPU unavailable");
    const task = new this(this.kind, options);
    calls.created.push({ kind: this.kind, delegate: options.baseOptions.delegate, model: options.baseOptions.modelAssetPath, options });
    return task;
  }
  close() { calls.closed.push(this.kind); }
}

export class HandLandmarker extends FakeTask {
  static kind = "hands";
  detectForVideo(video, timestamp) {
    calls.detect.push({ kind: "hands", timestamp });
    return { landmarks: settings.hands.map((hand) => hand.points), handedness: settings.hands.map((hand) => [{ categoryName: hand.label, score: 0.9 }]), worldLandmarks: [] };
  }
}

export class PoseLandmarker extends FakeTask {
  static kind = "pose";
  detectForVideo(video, timestamp) {
    calls.detect.push({ kind: "pose", timestamp });
    return { landmarks: settings.pose ? [settings.pose] : [], worldLandmarks: [] };
  }
}

export class FaceLandmarker extends FakeTask {
  static kind = "face";
  detectForVideo(video, timestamp) {
    calls.detect.push({ kind: "face", timestamp });
    return { faceLandmarks: settings.face ? [settings.face] : [] };
  }
}

export const FilesetResolver = { forVisionTasks: async (path) => ({ wasmPath: path }) };
