// Features v2: canonical holistic frames and per-sequence features.
// Port of ml_engine/features_v2.py (the reference). The contract is shared_data/feature_spec_v2.json.
// Keep the arithmetic in the same order as Python: plain loops and Math.sqrt (no Math.hypot), so the
// two give the same numbers. tests/test_features_v2.py and web/tests/v2-parity.test.mjs check this.
// This module has no imports, so it runs in the browser, in a Web Worker and under plain Node.

export const FEATURE_VERSION = "v2";
export const HAND_POINTS = 21;
export const ASSIGNMENT_CODES = Object.freeze({ none: 0, pose: 1, label: 2, position: 3 });

const layouts = new WeakMap();

function mirrorMap(pairs) {
  const mapping = new Map();
  for (const [a, b] of pairs) {
    mapping.set(a, b);
    mapping.set(b, a);
  }
  return mapping;
}

export function createLayout(spec) {
  if (!spec || spec.feature_version !== FEATURE_VERSION) {
    throw new Error(`Feature spec version ${spec && spec.feature_version} is not supported; this code supports ${FEATURE_VERSION}`);
  }
  const cached = layouts.get(spec);
  if (cached) return cached;
  const parts = Object.fromEntries(spec.parts.map((part) => [part.name, part]));
  const poseIndices = [...parts.pose.indices];
  const face = parts.face;
  const faceIndices = face.group_order.flatMap((group) => face.groups[group]);
  if (faceIndices.length !== face.count || poseIndices.length !== parts.pose.count) {
    throw new Error("feature spec part counts do not match their index lists");
  }
  const blocks = Object.fromEntries(spec.blocks.map((block) => [block.name, block]));
  const featuresPerFrame = spec.blocks.reduce((total, block) => total + block.size, 0);
  if (featuresPerFrame !== spec.features_per_frame) throw new Error("feature spec block sizes do not add up to features_per_frame");
  const poseSlot = new Map(poseIndices.map((index, slot) => [index, slot]));
  const layout = {
    poseIndices,
    faceIndices,
    poseMirror: mirrorMap(spec.mirror_pairs.pose),
    faceMirror: mirrorMap(spec.mirror_pairs.face),
    handPoints: [...blocks.hand_face_distance.hand_points],
    faceAnchorSlots: blocks.hand_face_distance.face_anchors.map((index) => faceIndices.indexOf(index)),
    poseSlot,
    pointsPerFrame: 2 * HAND_POINTS + poseIndices.length + faceIndices.length,
    featuresPerFrame,
    maxPoseIndex: Math.max(...poseIndices, ...spec.mirror_pairs.pose.flat()),
    maxFaceIndex: Math.max(...faceIndices, ...spec.mirror_pairs.face.flat()),
  };
  layouts.set(spec, layout);
  return layout;
}

function toRow(value, width) {
  let row;
  if (Array.isArray(value) || ArrayBuffer.isView(value)) {
    if (value.length < 3) throw new Error("a landmark needs x, y and z");
    row = value.length >= width ? Array.from(value).slice(0, width) : [value[0], value[1], value[2], 1.0];
  } else {
    row = [value.x, value.y, value.z ?? 0.0];
    if (width === 4) row.push(value.visibility ?? 1.0);
  }
  const out = row.map(Number);
  if (!out.every(Number.isFinite)) throw new Error("landmark values must be finite");
  return out;
}

function toRows(values, width, minimum, name) {
  const rows = Array.from(values, (value) => toRow(value, width));
  if (rows.length < minimum) throw new Error(`${name} needs at least ${minimum} landmarks, got ${rows.length}`);
  return rows;
}

function swapLabel(label) {
  if (typeof label !== "string") return null;
  const lowered = label.toLowerCase();
  if (lowered === "left") return "right";
  if (lowered === "right") return "left";
  return null;
}

function keepLabel(label) {
  if (typeof label !== "string") return null;
  const lowered = label.toLowerCase();
  return lowered === "left" || lowered === "right" ? lowered : null;
}

function distance2d(ax, ay, bx, by) {
  const dx = ax - bx;
  const dy = ay - by;
  return Math.sqrt(dx * dx + dy * dy);
}

// raw: { timestamp_ms, image_width, image_height, input_mirrored, hands: [{ landmarks, handedness }], pose, face }
export function canonicalizeFrame(raw, spec) {
  const layout = createLayout(spec);
  const width = Math.trunc(Number(raw.image_width));
  const height = Math.trunc(Number(raw.image_height));
  if (!(width > 0) || !(height > 0)) throw new Error("image_width and image_height must be positive");
  const timestamp = raw.timestamp_ms;
  if (typeof timestamp !== "number" || !Number.isInteger(timestamp)) throw new Error("timestamp_ms must be an integer number of milliseconds");
  const mirrored = Boolean(raw.input_mirrored);
  const unmirror = (row) => (mirrored ? [1.0 - row[0], ...row.slice(1)] : row);

  let pose = null;
  let visibility = null;
  if (raw.pose != null) {
    const full = toRows(raw.pose, 4, layout.maxPoseIndex + 1, "pose").map(unmirror);
    pose = [];
    visibility = [];
    for (const index of layout.poseIndices) {
      const source = mirrored ? layout.poseMirror.get(index) ?? index : index;
      pose.push(full[source].slice(0, 3));
      visibility.push(full[source][3]);
    }
  }

  let face = null;
  if (raw.face != null) {
    const fullFace = toRows(raw.face, 3, layout.maxFaceIndex + 1, "face").map(unmirror);
    face = layout.faceIndices.map((index) => fullFace[mirrored ? layout.faceMirror.get(index) ?? index : index]);
  }

  const hands = Array.from(raw.hands || []);
  if (hands.length > 2) throw new Error("at most two hands per frame");
  const handRows = hands.map((hand) => {
    const rows = toRows(hand.landmarks, 3, HAND_POINTS, "hand").map(unmirror);
    if (rows.length !== HAND_POINTS) throw new Error(`a hand needs exactly ${HAND_POINTS} landmarks`);
    // MediaPipe's handedness assumes a mirrored (selfie) input; swap it for unmirrored input.
    const anatomical = mirrored ? keepLabel(hand.handedness) : swapLabel(hand.handedness);
    return { rows, label: anatomical };
  });

  let left = null;
  let right = null;
  let method = "none";
  if (handRows.length) {
    if (pose !== null) {
      method = "pose";
      const lw = pose[layout.poseSlot.get(15)];
      const rw = pose[layout.poseSlot.get(16)];
      const lwx = lw[0] * width, lwy = lw[1] * height, rwx = rw[0] * width, rwy = rw[1] * height;
      const toWrist = (rows, wx, wy) => distance2d(rows[0][0] * width, rows[0][1] * height, wx, wy);
      if (handRows.length === 1) {
        const rows = handRows[0].rows;
        if (toWrist(rows, lwx, lwy) <= toWrist(rows, rwx, rwy)) left = rows;
        else right = rows;
      } else {
        const a = handRows[0].rows;
        const b = handRows[1].rows;
        const straight = toWrist(a, lwx, lwy) + toWrist(b, rwx, rwy);
        const crossed = toWrist(a, rwx, rwy) + toWrist(b, lwx, lwy);
        [left, right] = straight <= crossed ? [a, b] : [b, a];
      }
    } else {
      const labels = handRows.map((hand) => hand.label);
      if (labels.every((label) => label !== null) && new Set(labels).size === labels.length) {
        method = "label";
        for (const hand of handRows) {
          if (hand.label === "left") left = hand.rows;
          else right = hand.rows;
        }
      } else {
        // Unmirrored view: the signer's right hand appears further left in the image.
        method = "position";
        if (handRows.length === 1) {
          const rows = handRows[0].rows;
          if (rows[0][0] < 0.5) right = rows;
          else left = rows;
        } else {
          const a = handRows[0].rows;
          const b = handRows[1].rows;
          [right, left] = a[0][0] <= b[0][0] ? [a, b] : [b, a];
        }
      }
    }
  }

  return {
    timestamp_ms: timestamp,
    image_width: width,
    image_height: height,
    left_hand: left,
    right_hand: right,
    pose,
    pose_visibility: visibility,
    face,
    hand_assignment: ASSIGNMENT_CODES[method],
  };
}

function median(values) {
  const ordered = [...values].sort((a, b) => a - b);
  const middle = Math.floor(ordered.length / 2);
  if (ordered.length % 2) return ordered[middle];
  return (ordered[middle - 1] + ordered[middle]) / 2.0;
}

export function sequenceReference(frames, spec) {
  const layout = createLayout(spec);
  const midsX = [];
  const midsY = [];
  const widths = [];
  const ls = layout.poseSlot.get(11);
  const rs = layout.poseSlot.get(12);
  for (const frame of frames) {
    const pose = frame.pose;
    if (pose == null) continue;
    const w = frame.image_width;
    const h = frame.image_height;
    const lx = pose[ls][0] * w, ly = pose[ls][1] * h;
    const rx = pose[rs][0] * w, ry = pose[rs][1] * h;
    midsX.push((lx + rx) / 2.0);
    midsY.push((ly + ry) / 2.0);
    widths.push(distance2d(lx, ly, rx, ry));
  }
  if (widths.length) {
    const scale = median(widths);
    if (scale > 1e-6) return { origin: [median(midsX), median(midsY)], scale, from_pose: true };
  }
  const first = frames[0];
  return { origin: [first.image_width / 2.0, first.image_height / 2.0], scale: first.image_height / 4.0, from_pose: false };
}

function handShape(rows, w, h, out) {
  if (rows == null) {
    for (let i = 0; i < HAND_POINTS * 3; i += 1) out.push(0.0);
    return;
  }
  const wx = rows[0][0] * w, wy = rows[0][1] * h, wz = rows[0][2] * w;
  const centred = rows.map((point) => [point[0] * w - wx, point[1] * h - wy, point[2] * w - wz]);
  let size = 0.0;
  for (const [x, y] of centred) {
    const length = Math.sqrt(x * x + y * y);
    if (length > size) size = length;
  }
  if (size <= 1e-9) {
    for (let i = 0; i < HAND_POINTS * 3; i += 1) out.push(0.0);
    return;
  }
  for (const point of centred) out.push(point[0] / size, point[1] / size, point[2] / size);
}

function pushZeros(out, count) {
  for (let i = 0; i < count; i += 1) out.push(0.0);
}

// Returns { features: Float64Array[] (one per frame, 971 values), timestamps_ms, reference }.
export function sequenceFeatures(frames, spec) {
  const layout = createLayout(spec);
  if (!frames || !frames.length) throw new Error("a sequence needs at least one frame");
  const timestamps = frames.map((frame) => frame.timestamp_ms);
  for (let i = 1; i < timestamps.length; i += 1) {
    if (!(timestamps[i] > timestamps[i - 1])) throw new Error("timestamps_ms must be strictly increasing");
  }
  const sizes = [HAND_POINTS, HAND_POINTS, layout.poseIndices.length, layout.faceIndices.length];
  const reference = sequenceReference(frames, spec);
  const [ox, oy] = reference.origin;
  const scale = reference.scale;

  const output = [];
  let previousPositions = null;
  let previousTime = 0;
  frames.forEach((frame, frameIndex) => {
    const w = frame.image_width;
    const h = frame.image_height;
    const parts = [frame.left_hand ?? null, frame.right_hand ?? null, frame.pose ?? null, frame.face ?? null];
    const positionsByPart = parts.map((rows, partIndex) => {
      if (rows == null) return null;
      if (rows.length !== sizes[partIndex]) throw new Error(`canonical part has ${rows.length} points, expected ${sizes[partIndex]}`);
      const values = [];
      for (const point of rows) {
        values.push((point[0] * w - ox) / scale, (point[1] * h - oy) / scale, (point[2] * w) / scale);
      }
      return values;
    });

    const row = [];
    // positions
    positionsByPart.forEach((values, partIndex) => {
      if (values == null) pushZeros(row, sizes[partIndex] * 3);
      else for (const value of values) row.push(value);
    });
    // hand_shape (never mirrored)
    handShape(parts[0], w, h, row);
    handShape(parts[1], w, h, row);
    // velocity
    if (frameIndex === 0 || previousPositions === null) {
      pushZeros(row, layout.pointsPerFrame * 3);
    } else {
      const dt = (frame.timestamp_ms - previousTime) / 1000.0;
      positionsByPart.forEach((current, partIndex) => {
        const before = previousPositions[partIndex];
        if (current == null || before == null) pushZeros(row, sizes[partIndex] * 3);
        else for (let i = 0; i < current.length; i += 1) row.push((current[i] - before[i]) / dt);
      });
    }
    // hand_face_distance
    const faceValues = positionsByPart[3];
    for (const handValues of positionsByPart.slice(0, 2)) {
      for (const point of layout.handPoints) {
        for (const slot of layout.faceAnchorSlots) {
          if (handValues == null || faceValues == null) row.push(0.0);
          else row.push(distance2d(handValues[point * 3], handValues[point * 3 + 1], faceValues[slot * 3], faceValues[slot * 3 + 1]));
        }
      }
    }
    // hand_hand_distance
    const leftValues = positionsByPart[0];
    const rightValues = positionsByPart[1];
    for (const i of layout.handPoints) {
      for (const j of layout.handPoints) {
        if (leftValues == null || rightValues == null) row.push(0.0);
        else row.push(distance2d(leftValues[i * 3], leftValues[i * 3 + 1], rightValues[j * 3], rightValues[j * 3 + 1]));
      }
    }
    // masks
    for (const rows of parts) row.push(rows == null ? 0.0 : 1.0);
    row.push(reference.from_pose ? 1.0 : 0.0);

    if (row.length !== layout.featuresPerFrame) throw new Error(`built ${row.length} features, expected ${layout.featuresPerFrame}`);
    output.push(Float64Array.from(row));
    previousPositions = positionsByPart;
    previousTime = frame.timestamp_ms;
  });
  return { features: output, timestamps_ms: timestamps, reference };
}
