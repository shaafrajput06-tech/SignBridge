"""Recording format v2: one .npz file per sign instance, landmarks only.

A file holds the canonical v2 frames of one sign instance (see features_v2.canonicalize_frame)
plus the metadata needed for signer-independent training and consent tracking. It never holds
pixels: the only uint8 array is the UTF-8 metadata JSON.

Arrays (T = frames):

    points           float32 (T, 120, 3)  left_hand 21, right_hand 21, pose 9, face 69; NaN where absent
    present          uint8   (T, 4)       left_hand, right_hand, pose, face
    pose_visibility  float32 (T, 9)       NaN where the pose is absent
    timestamps_ms    int64   (T,)         strictly increasing
    hand_assignment  int8    (T,)         codes from the feature spec (none, pose, label, position)
    v1_features      float64 (T, 63)      only in records converted from v1 CSV rows
    meta             uint8   (N,)         UTF-8 JSON, see REQUIRED_META

Metadata is an allowlist (REQUIRED_META, OPTIONAL_META): any other key is refused, so a name cannot
be stored under another field. ``consent_recorded`` is true only for a real consent record; live
captures must have one, and ``training_use_refusal`` keeps records without one out of training.

Landmarks are stored as float32, the precision MediaPipe produces. Files are written with fixed
zip timestamps and entry order, so the same input always gives byte-identical files (Phase 2
needs deterministic manifests). Read them with ``read_recording`` (``np.load`` with
``allow_pickle=False`` also works).
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import math
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from ml_engine.features_v2 import LAYOUT, SPEC, sequence_features

FORMAT = "signbridge-recording"
FORMAT_VERSION = 2
SOURCES = ("capture_v2", "v1-csv")
PARTS = ("left_hand", "right_hand", "pose", "face")
PART_SIZES = (21, 21, len(LAYOUT.pose_indices), len(LAYOUT.face_indices))
REQUIRED_META = {
    "format": str, "format_version": int, "feature_version": str, "feature_spec_version": str, "source": str,
    "gloss_id": str, "signer_id": str, "session_id": str, "device": str, "camera_orientation_degrees": (int, type(None)),
    "input_mirrored": (bool, type(None)), "image_width": int, "image_height": int, "fps": (float, int, type(None)),
    "frame_count": int, "consent_id": str, "consent_recorded": bool, "instance_unit": str, "video_stored": bool, "created_utc": str,
}
# Only these keys may appear, so names cannot slip in under another key; signers are pseudonymous IDs.
OPTIONAL_META = {"video_consent": bool, "signer_id_reliable": bool, "signer_key_fingerprint": str, "warnings": list, "v1": dict, "capture_backend": str}
V1_META_KEYS = {"timestamp_utc", "frame_index", "handedness", "session_id", "feature_version", "features_note"}
INSTANCE_UNITS = ("sign", "frame")
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
ENTRY_ORDER = ("meta", "points", "present", "pose_visibility", "timestamps_ms", "hand_assignment", "v1_features")
_ZIP_DATE = (1980, 1, 1, 0, 0, 0)


class RecordingError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def base_meta(**fields: Any) -> dict:
    """Metadata with the format fields filled in; callers supply the rest."""
    meta = {
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "feature_version": SPEC["feature_version"],
        "feature_spec_version": SPEC["spec_version"],
        "video_stored": False,
        "instance_unit": "sign",
        "created_utc": utc_now(),
    }
    meta.update(fields)
    return meta


def validate_meta(meta: dict) -> None:
    unknown = set(meta) - set(REQUIRED_META) - set(OPTIONAL_META)
    if unknown:
        raise RecordingError(f"metadata keys not allowed (no personal or free-form fields): {sorted(unknown)}")
    for key, kind in OPTIONAL_META.items():
        if key in meta and not isinstance(meta[key], kind):
            raise RecordingError(f"metadata {key!r} has the wrong type ({type(meta[key]).__name__})")
    if "v1" in meta:
        extra = set(meta["v1"]) - V1_META_KEYS
        if extra or not all(isinstance(value, str) for value in meta["v1"].values()):
            raise RecordingError(f"metadata 'v1' may only hold text fields {sorted(V1_META_KEYS)}")
    if not all(isinstance(item, str) for item in meta.get("warnings", [])):
        raise RecordingError("metadata 'warnings' must be a list of text")
    for key, kind in REQUIRED_META.items():
        if key not in meta:
            raise RecordingError(f"metadata is missing {key!r}")
        value = meta[key]
        if isinstance(value, bool) and kind in (int, (float, int, type(None)), (int, type(None))):
            raise RecordingError(f"metadata {key!r} must be a number, not a boolean")
        if not isinstance(value, kind):
            raise RecordingError(f"metadata {key!r} has the wrong type ({type(value).__name__})")
    if meta["format"] != FORMAT or meta["format_version"] != FORMAT_VERSION:
        raise RecordingError(f"not a {FORMAT} v{FORMAT_VERSION} file")
    if meta["feature_version"] != SPEC["feature_version"]:
        raise RecordingError(f"feature version {meta['feature_version']!r} is not supported")
    if meta["source"] not in SOURCES:
        raise RecordingError(f"unknown source {meta['source']!r}")
    for key in ("gloss_id", "signer_id", "session_id", "device"):
        if not ID_PATTERN.match(meta[key]):
            raise RecordingError(f"{key} {meta[key]!r} must be 1-64 letters, digits, '_', '.' or '-'")
    if not meta["consent_id"].strip():
        raise RecordingError("consent_id is required: no recording without a consent record")
    if meta["instance_unit"] not in INSTANCE_UNITS:
        raise RecordingError(f"instance_unit must be one of {INSTANCE_UNITS}")
    if meta["video_stored"] and meta.get("video_consent") is not True:
        raise RecordingError("video_stored is true but the signer did not opt in to video (video_consent)")
    if meta["source"] == "capture_v2":
        if not meta["consent_recorded"]:
            raise RecordingError("live captures need a recorded consent (consent_recorded true with a real consent_id)")
        if meta["instance_unit"] != "sign":
            raise RecordingError("live captures hold one sign instance per file (instance_unit 'sign')")
        if meta["image_width"] <= 0 or meta["image_height"] <= 0:
            raise RecordingError("image size must be positive")
        if meta["camera_orientation_degrees"] not in (0, 90, 180, 270):
            raise RecordingError("camera_orientation_degrees must be the rotation applied: 0, 90, 180 or 270")
        if meta["input_mirrored"] is None:
            raise RecordingError("input_mirrored must be true or false for live captures")


def training_use_refusal(meta: dict) -> str | None:
    """Why a record must not be used to train or evaluate, or None if nothing in it forbids that.

    Phase 2 training and export code must call this for every record. It does not replace the
    licence ledger check (data/LICENSES.yaml) or Deaf validation; it only covers what the record
    itself knows: consent and whether the signer can be told apart for signer-independent splits.
    """
    validate_meta(meta)
    if not meta["consent_recorded"]:
        return f"no recorded consent (consent_id {meta['consent_id']!r})"
    if meta.get("signer_id_reliable") is False:
        return "signer cannot be identified, so signer-independent splits are impossible"
    return None


def _frames_to_arrays(frames: Sequence[dict]) -> dict[str, np.ndarray]:
    count = len(frames)
    points = np.full((count, LAYOUT.points_per_frame, 3), np.nan, dtype=np.float32)
    present = np.zeros((count, 4), dtype=np.uint8)
    visibility = np.full((count, PART_SIZES[2]), np.nan, dtype=np.float32)
    timestamps = np.zeros(count, dtype=np.int64)
    assignment = np.zeros(count, dtype=np.int8)
    for t, frame in enumerate(frames):
        offset = 0
        for part_index, (part, size) in enumerate(zip(PARTS, PART_SIZES)):
            rows = frame.get(part)
            if rows is not None:
                block = np.asarray(rows, dtype=np.float64)
                if block.shape != (size, 3) or not np.all(np.isfinite(block)):
                    raise RecordingError(f"frame {t}: {part} must be {size} finite x, y, z points")
                points[t, offset:offset + size] = block
                present[t, part_index] = 1
            offset += size
        if frame.get("pose") is not None and frame.get("pose_visibility") is not None:
            visibility[t] = np.asarray(frame["pose_visibility"], dtype=np.float64)
        timestamps[t] = int(frame["timestamp_ms"])
        assignment[t] = int(frame.get("hand_assignment", 0))
    if count > 1 and np.any(np.diff(timestamps) <= 0):
        raise RecordingError("timestamps_ms must be strictly increasing")
    return {"points": points, "present": present, "pose_visibility": visibility, "timestamps_ms": timestamps, "hand_assignment": assignment}


def _write_npz(path: Path, arrays: dict[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with zipfile.ZipFile(temporary, "w") as archive:
        for name in ENTRY_ORDER:
            if name not in arrays:
                continue
            buffer = io.BytesIO()
            np.lib.format.write_array(buffer, np.ascontiguousarray(arrays[name]), allow_pickle=False)
            info = zipfile.ZipInfo(f"{name}.npy", date_time=_ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, buffer.getvalue(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
    temporary.replace(path)


def measured_fps(timestamps_ms: Sequence[int]) -> float | None:
    if len(timestamps_ms) < 2 or timestamps_ms[-1] <= timestamps_ms[0]:
        return None
    return round((len(timestamps_ms) - 1) * 1000.0 / (timestamps_ms[-1] - timestamps_ms[0]), 3)


def write_recording(path: Path, frames: Sequence[dict], meta: dict, v1_features: Sequence[Sequence[float]] | None = None) -> Path:
    """Write one sign instance. ``meta`` is completed with image size, frame count and fps."""
    if not frames:
        raise RecordingError("a recording needs at least one frame")
    meta = dict(meta)
    if meta.get("source") == "capture_v2":
        sizes = {(frame["image_width"], frame["image_height"]) for frame in frames}
        if len(sizes) != 1:
            raise RecordingError("all frames of one recording must have the same image size")
        meta["image_width"], meta["image_height"] = sizes.pop()
        meta["fps"] = measured_fps([frame["timestamp_ms"] for frame in frames])
    meta["frame_count"] = len(frames)
    validate_meta(meta)
    arrays = _frames_to_arrays(frames)
    if v1_features is not None:
        v1 = np.asarray(v1_features, dtype=np.float64)
        if v1.shape != (len(frames), 63) or not np.all(np.isfinite(v1)):
            raise RecordingError("v1_features must be finite, one row of 63 values per frame")
        arrays["v1_features"] = v1
    elif meta["source"] == "v1-csv":
        raise RecordingError("records converted from v1 must carry v1_features")
    arrays["meta"] = np.frombuffer(json.dumps(meta, sort_keys=True, ensure_ascii=False).encode("utf-8"), dtype=np.uint8)
    path = Path(path)
    if path.suffix != ".npz":
        raise RecordingError("recording files use the .npz extension")
    _write_npz(path, arrays)
    return path


def read_recording(path: Path) -> dict:
    """Return ``{"meta": dict, "frames": [canonical frames], "v1_features": list | None}``."""
    with np.load(Path(path), allow_pickle=False) as data:
        names = set(data.files)
        required = {"meta", "points", "present", "pose_visibility", "timestamps_ms", "hand_assignment"}
        if not required <= names:
            raise RecordingError(f"{path} is missing {sorted(required - names)}")
        meta = json.loads(bytes(data["meta"]).decode("utf-8"))
        validate_meta(meta)
        points, present, visibility = data["points"], data["present"], data["pose_visibility"]
        timestamps, assignment = data["timestamps_ms"], data["hand_assignment"]
        v1 = data["v1_features"].tolist() if "v1_features" in names else None
    count = meta["frame_count"]
    if points.shape != (count, LAYOUT.points_per_frame, 3) or present.shape != (count, 4) or len(timestamps) != count:
        raise RecordingError(f"{path}: array shapes do not match frame_count {count}")
    frames = []
    for t in range(count):
        frame: dict[str, Any] = {
            "timestamp_ms": int(timestamps[t]),
            "image_width": meta["image_width"],
            "image_height": meta["image_height"],
            "hand_assignment": int(assignment[t]),
        }
        offset = 0
        for part_index, (part, size) in enumerate(zip(PARTS, PART_SIZES)):
            frame[part] = points[t, offset:offset + size].astype(np.float64).tolist() if present[t, part_index] else None
            offset += size
        frame["pose_visibility"] = visibility[t].astype(np.float64).tolist() if present[t, 2] else None
        frames.append(frame)
    return {"meta": meta, "frames": frames, "v1_features": v1}


def recording_features(path: Path) -> dict:
    record = read_recording(path)
    if record["meta"]["source"] == "v1-csv":
        raise RecordingError("records converted from v1 hold v1 features only; v2 features need a v2 capture")
    return sequence_features(record["frames"])


# --------------------------------------------------------------------------- v1 CSV rows

def pseudonym(participant: str, key: bytes) -> str:
    """Stable pseudonymous signer ID. Without the key the name cannot be recovered or re-derived.

    Case and all whitespace runs are normalised, so "Ayesha  Khan" and "ayesha khan" are one signer.
    Spelling variants are not caught: review the signer map (convert_v1_to_v2.py --signer-map).
    """
    cleaned = " ".join(participant.split()).casefold()
    if cleaned in ("", "anonymous"):
        return "anonymous"
    return "s_" + hmac.new(key, cleaned.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def key_fingerprint(key: bytes) -> str:
    """Short public fingerprint of the signer key, so records made with different keys can be spotted."""
    return hashlib.sha256(b"signbridge-signer-key:" + key).hexdigest()[:12]


def _safe_id(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-.")[:64]
    return cleaned if cleaned and ID_PATTERN.match(cleaned) else fallback


def v1_row_to_record(row: Sequence[str], header: Sequence[str], key: bytes) -> tuple[list[dict], dict, list[list[float]]]:
    """Wrap one v1 CSV row (one frame, 63 normalised hand values) as a 1-frame v2 record.

    The v1 values are kept exactly in ``v1_features``. They cannot become v2 points: v1 stored
    wrist-relative, mirrored hand shapes with no pose or face, so the v2 frame is empty and marked
    as such. The participant name is replaced by a pseudonymous signer ID.

    v1 kept no consent record, so ``consent_recorded`` is false and ``training_use_refusal`` refuses
    these records until consent is confirmed. Each record is one camera frame, not a whole sign
    (``instance_unit`` 'frame'); frames from one sitting are near-duplicates, so any split must be
    by signer, never by record.
    """
    values = dict(zip(header, row))
    features = [float(values[f"f{index}"]) for index in range(63)]
    if not all(math.isfinite(value) for value in features):
        raise RecordingError("v1 row has non-finite features")
    width, height = int(float(values["frame_width"] or 0)), int(float(values["frame_height"] or 0))
    signer = pseudonym(values["participant"], key)
    warnings = []
    if width == 0 and height == 0:
        warnings.append("phone sample (frame size 0): collected before the F4 rotation fix, so the hand may be rotated")
    if signer == "anonymous":
        warnings.append("anonymous signer: cannot be used for signer-independent splits")
    warnings.append("no consent record from v1: confirm consent before any training use")
    meta = base_meta(
        source="v1-csv",
        gloss_id=values["label"],
        signer_id=signer,
        signer_id_reliable=signer != "anonymous",
        session_id=_safe_id(values["session_id"], "v1-session"),
        device="unknown-v1",
        camera_orientation_degrees=None,
        input_mirrored=None,
        image_width=width,
        image_height=height,
        fps=None,
        consent_id="v1-legacy-unrecorded",
        consent_recorded=False,
        instance_unit="frame",
        signer_key_fingerprint=key_fingerprint(key),
        created_utc=values["timestamp_utc"] or "unknown",
        v1={"timestamp_utc": values["timestamp_utc"], "frame_index": values["frame_index"], "handedness": values["handedness"],
            "session_id": values["session_id"], "feature_version": "v1", "features_note": "63 wrist-relative values, left hands mirrored (ml_engine/features.py)"},
        warnings=warnings,
    )
    frame = {"timestamp_ms": 0, "image_width": max(width, 1), "image_height": max(height, 1), "left_hand": None, "right_hand": None,
             "pose": None, "pose_visibility": None, "face": None, "hand_assignment": 0}
    return [frame], meta, [features]


def record_to_v1_row(record: dict) -> list[str]:
    """Rebuild the v1 CSV row (participant column holds the signer ID, never the name)."""
    meta, v1 = record["meta"], record["meta"]["v1"]
    features = record["v1_features"][0]
    return [meta["gloss_id"], meta["signer_id"], v1["session_id"], v1["timestamp_utc"], v1["frame_index"],
            str(meta["image_width"]), str(meta["image_height"]), v1["handedness"], *[repr(value) for value in features]]
