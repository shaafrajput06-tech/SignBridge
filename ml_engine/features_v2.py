"""Features v2: canonical holistic frames and per-sequence features.

The contract lives in shared_data/feature_spec_v2.json. This module is the reference
implementation; web/src/features_v2.js must give the same numbers (tests/test_features_v2.py
checks that to 1e-6 on the committed golden fixture).

Two steps:

1. ``canonicalize_frame(raw)`` turns one frame of raw landmarker output (both hands, the
   33-point pose and the 478-point face mesh, in normalised image coordinates) into a
   canonical frame: unmirrored view, anatomical left/right, the fixed pose and face subsets.
2. ``sequence_features(frames)`` turns a list of canonical frames into 971 values per frame:
   shoulder-normalised positions, hand shapes, velocities, hand-to-face and hand-to-hand
   distances, and presence masks.

The arithmetic is written as plain loops with ``math.sqrt`` (no ``hypot``, no numpy) so the
JavaScript port can repeat it operation for operation.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "shared_data" / "feature_spec_v2.json"
FEATURE_VERSION = "v2"
HAND_POINTS = 21
ASSIGNMENT_CODES = {"none": 0, "pose": 1, "label": 2, "position": 3}


def load_spec(path: Path = SPEC_PATH) -> dict:
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    if spec.get("feature_version") != FEATURE_VERSION:
        raise ValueError(f"{path} is feature version {spec.get('feature_version')!r}; this code supports {FEATURE_VERSION!r}")
    return spec


class Layout:
    """Index tables derived once from the spec."""

    def __init__(self, spec: dict):
        parts = {part["name"]: part for part in spec["parts"]}
        self.pose_indices: list[int] = list(parts["pose"]["indices"])
        face = parts["face"]
        self.face_indices: list[int] = [index for group in face["group_order"] for index in face["groups"][group]]
        if len(self.face_indices) != face["count"] or len(self.pose_indices) != parts["pose"]["count"]:
            raise ValueError("feature spec part counts do not match their index lists")
        self.pose_mirror = _mirror_map(spec["mirror_pairs"]["pose"])
        self.face_mirror = _mirror_map(spec["mirror_pairs"]["face"])
        blocks = {block["name"]: block for block in spec["blocks"]}
        self.hand_points: list[int] = list(blocks["hand_face_distance"]["hand_points"])
        anchors = blocks["hand_face_distance"]["face_anchors"]
        self.face_anchor_slots: list[int] = [self.face_indices.index(index) for index in anchors]
        self.pose_slot = {index: slot for slot, index in enumerate(self.pose_indices)}
        self.points_per_frame = 2 * HAND_POINTS + len(self.pose_indices) + len(self.face_indices)
        self.features_per_frame = sum(block["size"] for block in spec["blocks"])
        if self.features_per_frame != spec["features_per_frame"]:
            raise ValueError("feature spec block sizes do not add up to features_per_frame")
        self.max_pose_index = max(self.pose_indices + [index for pair in spec["mirror_pairs"]["pose"] for index in pair])
        self.max_face_index = max(self.face_indices + [index for pair in spec["mirror_pairs"]["face"] for index in pair])


def _mirror_map(pairs: Iterable[Sequence[int]]) -> dict[int, int]:
    mapping: dict[int, int] = {}
    for a, b in pairs:
        mapping[a] = b
        mapping[b] = a
    return mapping


SPEC = load_spec()
LAYOUT = Layout(SPEC)


def _layout(spec: dict | None) -> Layout:
    return LAYOUT if spec is None or spec is SPEC else Layout(spec)


# --------------------------------------------------------------------------- canonical frames

def _row(value: Any, width: int) -> list[float]:
    if isinstance(value, dict):
        row = [value["x"], value["y"], value.get("z", 0.0)]
        if width == 4:
            row.append(value.get("visibility", 1.0))
    else:
        row = list(value)
        if len(row) < 3:
            raise ValueError("a landmark needs x, y and z")
        row = row[:width] if len(row) >= width else row[:3] + [1.0]
    out = [float(item) for item in row]
    if not all(math.isfinite(item) for item in out):
        raise ValueError("landmark values must be finite")
    return out


def _rows(values: Any, width: int, minimum: int, name: str) -> list[list[float]]:
    rows = [_row(value, width) for value in values]
    if len(rows) < minimum:
        raise ValueError(f"{name} needs at least {minimum} landmarks, got {len(rows)}")
    return rows


def _swap_label(label: str | None) -> str | None:
    if label is None:
        return None
    lowered = label.lower()
    if lowered == "left":
        return "right"
    if lowered == "right":
        return "left"
    return None


def _distance2d(ax: float, ay: float, bx: float, by: float) -> float:
    dx = ax - bx
    dy = ay - by
    return math.sqrt(dx * dx + dy * dy)


def canonicalize_frame(raw: dict, spec: dict | None = None) -> dict:
    """Return the canonical frame for one frame of raw landmarker output.

    ``raw`` keys: ``timestamp_ms`` (int), ``image_width`` and ``image_height`` (after rotation
    correction), ``input_mirrored`` (bool, default False), ``hands`` (list of at most two
    ``{"landmarks": 21 x [x, y, z], "handedness": "Left" | "Right" | None}``), ``pose``
    (33 x [x, y, z, visibility] or None) and ``face`` (478 or 468 x [x, y, z] or None).
    """
    layout = _layout(spec)
    width = int(raw["image_width"])
    height = int(raw["image_height"])
    if width <= 0 or height <= 0:
        raise ValueError("image_width and image_height must be positive")
    timestamp = raw["timestamp_ms"]
    if isinstance(timestamp, bool) or int(timestamp) != timestamp:
        raise ValueError("timestamp_ms must be an integer number of milliseconds")
    mirrored = bool(raw.get("input_mirrored", False))

    def unmirror(row: list[float]) -> list[float]:
        return [1.0 - row[0]] + row[1:] if mirrored else row

    pose = None
    visibility = None
    if raw.get("pose") is not None:
        full = [unmirror(row) for row in _rows(raw["pose"], 4, layout.max_pose_index + 1, "pose")]
        pose, visibility = [], []
        for index in layout.pose_indices:
            source = layout.pose_mirror.get(index, index) if mirrored else index
            pose.append(full[source][:3])
            visibility.append(full[source][3])

    face = None
    if raw.get("face") is not None:
        full_face = [unmirror(row) for row in _rows(raw["face"], 3, layout.max_face_index + 1, "face")]
        face = [full_face[layout.face_mirror.get(index, index) if mirrored else index] for index in layout.face_indices]

    hands = list(raw.get("hands") or [])
    if len(hands) > 2:
        raise ValueError("at most two hands per frame")
    hand_rows = []
    for hand in hands:
        rows = [unmirror(row) for row in _rows(hand["landmarks"], 3, HAND_POINTS, "hand")]
        if len(rows) != HAND_POINTS:
            raise ValueError(f"a hand needs exactly {HAND_POINTS} landmarks")
        label = hand.get("handedness")
        # MediaPipe's handedness assumes a mirrored (selfie) input; swap it for unmirrored input.
        anatomical = (label.lower() if isinstance(label, str) and label.lower() in ("left", "right") else None) if mirrored else _swap_label(label)
        hand_rows.append((rows, anatomical))

    left = right = None
    method = "none"
    if hand_rows:
        if pose is not None:
            method = "pose"
            lw = pose[layout.pose_slot[15]]
            rw = pose[layout.pose_slot[16]]
            lwx, lwy, rwx, rwy = lw[0] * width, lw[1] * height, rw[0] * width, rw[1] * height

            def to_wrist(rows: list[list[float]], wx: float, wy: float) -> float:
                return _distance2d(rows[0][0] * width, rows[0][1] * height, wx, wy)

            if len(hand_rows) == 1:
                rows = hand_rows[0][0]
                if to_wrist(rows, lwx, lwy) <= to_wrist(rows, rwx, rwy):
                    left = rows
                else:
                    right = rows
            else:
                a, b = hand_rows[0][0], hand_rows[1][0]
                straight = to_wrist(a, lwx, lwy) + to_wrist(b, rwx, rwy)
                crossed = to_wrist(a, rwx, rwy) + to_wrist(b, lwx, lwy)
                left, right = (a, b) if straight <= crossed else (b, a)
        else:
            labels = [label for _, label in hand_rows]
            if all(label is not None for label in labels) and len(set(labels)) == len(labels):
                method = "label"
                for rows, label in hand_rows:
                    if label == "left":
                        left = rows
                    else:
                        right = rows
            else:
                # Unmirrored view: the signer's right hand appears further left in the image.
                method = "position"
                if len(hand_rows) == 1:
                    rows = hand_rows[0][0]
                    if rows[0][0] < 0.5:
                        right = rows
                    else:
                        left = rows
                else:
                    a, b = hand_rows[0][0], hand_rows[1][0]
                    right, left = (a, b) if a[0][0] <= b[0][0] else (b, a)

    return {
        "timestamp_ms": int(timestamp),
        "image_width": width,
        "image_height": height,
        "left_hand": left,
        "right_hand": right,
        "pose": pose,
        "pose_visibility": visibility,
        "face": face,
        "hand_assignment": ASSIGNMENT_CODES[method],
    }


# --------------------------------------------------------------------------- sequence features

def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def sequence_reference(frames: Sequence[dict], spec: dict | None = None) -> dict:
    """Origin and scale shared by every frame of the sequence (component-wise medians)."""
    layout = _layout(spec)
    mids_x: list[float] = []
    mids_y: list[float] = []
    widths: list[float] = []
    ls, rs = layout.pose_slot[11], layout.pose_slot[12]
    for frame in frames:
        pose = frame.get("pose")
        if pose is None:
            continue
        w, h = frame["image_width"], frame["image_height"]
        lx, ly = pose[ls][0] * w, pose[ls][1] * h
        rx, ry = pose[rs][0] * w, pose[rs][1] * h
        mids_x.append((lx + rx) / 2.0)
        mids_y.append((ly + ry) / 2.0)
        widths.append(_distance2d(lx, ly, rx, ry))
    if widths:
        scale = _median(widths)
        if scale > 1e-6:
            return {"origin": [_median(mids_x), _median(mids_y)], "scale": scale, "from_pose": True}
    first = frames[0]
    return {
        "origin": [first["image_width"] / 2.0, first["image_height"] / 2.0],
        "scale": first["image_height"] / 4.0,
        "from_pose": False,
    }


def _part_rows(frame: dict) -> list[list[list[float]] | None]:
    return [frame.get("left_hand"), frame.get("right_hand"), frame.get("pose"), frame.get("face")]


def sequence_features(frames: Sequence[dict], spec: dict | None = None) -> dict:
    """Return ``{"features": T x 971 floats, "timestamps_ms": [...], "reference": {...}}``."""
    layout = _layout(spec)
    if not frames:
        raise ValueError("a sequence needs at least one frame")
    timestamps = [frame["timestamp_ms"] for frame in frames]
    for previous, current in zip(timestamps, timestamps[1:]):
        if current <= previous:
            raise ValueError("timestamps_ms must be strictly increasing")
    sizes = [HAND_POINTS, HAND_POINTS, len(layout.pose_indices), len(layout.face_indices)]
    reference = sequence_reference(frames, spec)
    ox, oy = reference["origin"]
    scale = reference["scale"]

    output: list[list[float]] = []
    previous_positions: list[list[float] | None] | None = None
    previous_time = 0
    for frame_index, frame in enumerate(frames):
        w, h = frame["image_width"], frame["image_height"]
        parts = _part_rows(frame)
        positions_by_part: list[list[float] | None] = []
        for rows, size in zip(parts, sizes):
            if rows is None:
                positions_by_part.append(None)
                continue
            if len(rows) != size:
                raise ValueError(f"canonical part has {len(rows)} points, expected {size}")
            values: list[float] = []
            for point in rows:
                values.append((point[0] * w - ox) / scale)
                values.append((point[1] * h - oy) / scale)
                values.append((point[2] * w) / scale)
            positions_by_part.append(values)

        row: list[float] = []
        # positions
        for values, size in zip(positions_by_part, sizes):
            row.extend(values if values is not None else [0.0] * (size * 3))
        # hand_shape (never mirrored)
        for rows in parts[:2]:
            row.extend(_hand_shape(rows, w, h))
        # velocity
        if frame_index == 0 or previous_positions is None:
            row.extend([0.0] * (layout.points_per_frame * 3))
        else:
            dt = (frame["timestamp_ms"] - previous_time) / 1000.0
            for current, before, size in zip(positions_by_part, previous_positions, sizes):
                if current is None or before is None:
                    row.extend([0.0] * (size * 3))
                else:
                    row.extend([(a - b) / dt for a, b in zip(current, before)])
        # hand_face_distance
        face_values = positions_by_part[3]
        for hand_values in positions_by_part[:2]:
            for point in layout.hand_points:
                for slot in layout.face_anchor_slots:
                    if hand_values is None or face_values is None:
                        row.append(0.0)
                    else:
                        row.append(_distance2d(hand_values[point * 3], hand_values[point * 3 + 1], face_values[slot * 3], face_values[slot * 3 + 1]))
        # hand_hand_distance
        left_values, right_values = positions_by_part[0], positions_by_part[1]
        for i in layout.hand_points:
            for j in layout.hand_points:
                if left_values is None or right_values is None:
                    row.append(0.0)
                else:
                    row.append(_distance2d(left_values[i * 3], left_values[i * 3 + 1], right_values[j * 3], right_values[j * 3 + 1]))
        # masks
        row.extend([0.0 if rows is None else 1.0 for rows in parts])
        row.append(1.0 if reference["from_pose"] else 0.0)

        if len(row) != layout.features_per_frame:
            raise AssertionError(f"built {len(row)} features, expected {layout.features_per_frame}")
        output.append(row)
        previous_positions = positions_by_part
        previous_time = frame["timestamp_ms"]
    return {"features": output, "timestamps_ms": list(timestamps), "reference": reference}


def _hand_shape(rows: list[list[float]] | None, w: int, h: int) -> list[float]:
    if rows is None:
        return [0.0] * (HAND_POINTS * 3)
    wx, wy, wz = rows[0][0] * w, rows[0][1] * h, rows[0][2] * w
    centred = [(point[0] * w - wx, point[1] * h - wy, point[2] * w - wz) for point in rows]
    size = 0.0
    for x, y, _ in centred:
        length = math.sqrt(x * x + y * y)
        if length > size:
            size = length
    if size <= 1e-9:
        return [0.0] * (HAND_POINTS * 3)
    return [value / size for point in centred for value in point]


def feature_names(spec: dict | None = None) -> list[str]:
    """Human-readable name for each of the 971 columns, in order."""
    layout = _layout(spec)
    parts = [("left_hand", HAND_POINTS), ("right_hand", HAND_POINTS), ("pose", len(layout.pose_indices)), ("face", len(layout.face_indices))]
    point_names = []
    for name, count in parts:
        source = layout.pose_indices if name == "pose" else layout.face_indices if name == "face" else list(range(count))
        point_names += [f"{name}[{index}]" for index in source]
    names = [f"pos.{point}.{axis}" for point in point_names for axis in "xyz"]
    names += [f"shape.{side}[{i}].{axis}" for side in ("left_hand", "right_hand") for i in range(HAND_POINTS) for axis in "xyz"]
    names += [f"vel.{point}.{axis}" for point in point_names for axis in "xyz"]
    anchors = SPEC["blocks"][3]["face_anchors"] if spec is None else next(b for b in spec["blocks"] if b["name"] == "hand_face_distance")["face_anchors"]
    names += [f"dist.{side}[{p}]-face[{a}]" for side in ("left_hand", "right_hand") for p in layout.hand_points for a in anchors]
    names += [f"dist.left_hand[{i}]-right_hand[{j}]" for i in layout.hand_points for j in layout.hand_points]
    names += ["mask.left_hand", "mask.right_hand", "mask.pose", "mask.face", "mask.reference_from_pose"]
    return names
