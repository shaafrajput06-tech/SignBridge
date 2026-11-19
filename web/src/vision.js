import { FilesetResolver, HandLandmarker } from "@mediapipe/tasks-vision";
import { assetUrl } from "./paths.js";

let detectorPromise;

export async function createHandDetector() {
  if (!detectorPromise) {
    detectorPromise = (async () => {
      const files = await FilesetResolver.forVisionTasks(assetUrl("wasm"));
      const options = {
        baseOptions: { modelAssetPath: assetUrl("models/hand_landmarker.task"), delegate: "GPU" },
        runningMode: "VIDEO",
        numHands: 2, // both hands, always (CLAUDE.md 8.4)
        minHandDetectionConfidence: 0.55,
        minHandPresenceConfidence: 0.5,
        minTrackingConfidence: 0.5,
      };
      try {
        return await HandLandmarker.createFromOptions(files, options);
      } catch {
        options.baseOptions.delegate = "CPU";
        return HandLandmarker.createFromOptions(files, options);
      }
    })();
  }
  try {
    return await detectorPromise;
  } catch (error) {
    detectorPromise = null;
    throw error;
  }
}

// Close the shared detector and forget it, so the next createHandDetector() builds a fresh one.
// Closing the detector without clearing the cache made the next camera start reuse a closed
// MediaPipe task, which aborts the WASM runtime and crashes the page.
export function releaseHandDetector() {
  const pending = detectorPromise;
  detectorPromise = null;
  if (pending) pending.then((detector) => detector.close()).catch(() => {});
}

const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y, (a.z || 0) - (b.z || 0));
const dot = (a, b) => a.x * b.x + a.y * b.y;

function extended(points, pip, tip) {
  const wrist = points[0];
  const palm = { x: points[9].x - wrist.x, y: points[9].y - wrist.y };
  const finger = { x: points[tip].x - points[pip].x, y: points[tip].y - points[pip].y };
  const palmLength = Math.hypot(palm.x, palm.y);
  if (palmLength <= 1e-6 || distance(wrist, points[tip]) <= distance(wrist, points[pip]) * 1.08) return false;
  const forward = dot(finger, { x: palm.x / palmLength, y: palm.y / palmLength });
  const horizontalIndex = pip === 6 && Math.abs(finger.x) > Math.abs(finger.y) * 1.15;
  return forward > palmLength * 0.12 || horizontalIndex;
}

export function classifyGesture(points) {
  if (!points || points.length !== 21) return null;
  const wrist = points[0];
  const scale = Math.max(...points.map((point) => distance(wrist, point)));
  if (scale < 1e-6) return null;
  const fingers = [extended(points, 6, 8), extended(points, 10, 12), extended(points, 14, 16), extended(points, 18, 20)];
  const count = fingers.filter(Boolean).length;
  const thumbTip = points[4];
  const thumbExtended = distance(thumbTip, points[5]) > scale * 0.55 && distance(thumbTip, points[2]) > distance(points[3], points[2]) * 1.08;
  const fingerSpan = distance(points[8], points[20]) / scale;
  const thumbIndexGap = distance(points[4], points[8]) / scale;
  if (thumbIndexGap < 0.24 && fingers[1] && fingers[2]) return "OK";
  if (thumbExtended && fingers[3] && count <= 1) return "CALL_ME";
  if (count === 0 && thumbExtended) {
    const dx = thumbTip.x - wrist.x;
    const dy = thumbTip.y - wrist.y;
    if (Math.abs(dx) < scale * 0.72 && dy < -scale * 0.3) return "THUMBS_UP";
    if (Math.abs(dx) < scale * 0.72 && dy > scale * 0.3) return "THUMBS_DOWN";
  }
  if (count === 0 && !thumbExtended) return "CLOSED_FIST";
  if (count === 1 && fingers[0] && !thumbExtended) {
    const dx = points[8].x - points[5].x;
    const dy = points[8].y - points[5].y;
    if (Math.abs(dy) > Math.abs(dx) * 1.15 && dy < 0) return "INDEX_UP";
    if (Math.abs(dx) > Math.abs(dy) * 1.15) return "POINT";
  }
  if (count === 2 && fingers[0] && fingers[1]) return "VICTORY";
  if (count === 3 && fingers[0] && fingers[1] && fingers[2]) return "THREE_FINGERS";
  if (count === 4) {
    if (thumbExtended) return fingerSpan <= 0.72 ? "FIVE_FINGERS" : "OPEN_PALM";
    return fingerSpan > 0.58 ? "FOUR_FINGERS" : "STOP_PALM";
  }
  return null;
}

export function normalizeLandmarks(points, handedness = "Right") {
  if (!points || points.length !== 21) throw new Error("Expected 21 hand landmarks");
  const origin = points[0];
  const mirror = handedness.toLowerCase() === "left" ? -1 : 1;
  const centered = points.map((point) => ({ x: (point.x - origin.x) * mirror, y: point.y - origin.y, z: (point.z || 0) - (origin.z || 0) }));
  const scale = Math.max(...centered.map((point) => Math.hypot(point.x, point.y)));
  if (scale <= 1e-9) throw new Error("Hand landmarks have no measurable size");
  return centered.flatMap((point) => [point.x / scale, point.y / scale, point.z / scale]);
}

// hands: null, one hand (21 points), or a list of { points, colour }. Points may be {x, y} objects
// (MediaPipe) or [x, y, z] rows (capture v2), in unmirrored image coordinates; the drawing is mirrored
// to match the mirrored preview and follows the video's object-fit: cover crop.
export function drawLandmarks(canvas, video, hands) {
  if (!canvas || !video) return;
  const rect = video.getBoundingClientRect();
  const width = Math.max(1, Math.round(rect.width * devicePixelRatio));
  const height = Math.max(1, Math.round(rect.height * devicePixelRatio));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  const context = canvas.getContext("2d");
  context.clearRect(0, 0, width, height);
  if (!hands || !video.videoWidth) return;
  const list = Array.isArray(hands) && hands.length && hands[0]?.points ? hands : [{ points: hands }];
  const scale = Math.max(width / video.videoWidth, height / video.videoHeight);
  const offsetX = (width - video.videoWidth * scale) / 2;
  const offsetY = (height - video.videoHeight * scale) / 2;
  const px = (point) => offsetX + (Array.isArray(point) ? point[0] : point.x) * video.videoWidth * scale;
  const py = (point) => offsetY + (Array.isArray(point) ? point[1] : point.y) * video.videoHeight * scale;
  const links = [[0,1],[1,2],[2,3],[3,4],[0,5],[5,6],[6,7],[7,8],[5,9],[9,10],[10,11],[11,12],[9,13],[13,14],[14,15],[15,16],[13,17],[17,18],[18,19],[19,20],[0,17]];
  context.save();
  context.scale(-1, 1);
  context.translate(-width, 0);
  context.lineWidth = Math.max(2, width / 460);
  for (const { points, colour } of list) {
    if (!points?.length) continue;
    context.strokeStyle = colour || "#69d9b5";
    context.fillStyle = colour || "#f7ca69";
    for (const [a, b] of links) {
      context.beginPath();
      context.moveTo(px(points[a]), py(points[a]));
      context.lineTo(px(points[b]), py(points[b]));
      context.stroke();
    }
    for (const point of points) {
      context.beginPath();
      context.arc(px(point), py(point), Math.max(3, width / 260), 0, Math.PI * 2);
      context.fill();
    }
  }
  context.restore();
}
