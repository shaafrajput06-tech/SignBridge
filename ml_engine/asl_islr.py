"""ASL mode (fast track Stage 2): the Google Isolated Sign Language Recognition 1st-place model.

ASL is a separate language mode (CLAUDE.md 8.2). Nothing here is PSL, and nothing here may feed a PSL
model or be shown as PSL.

The model takes frames x 543 x 3 landmarks in the competition layout (face 468, left hand 21, pose 33,
right hand 21; NaN where a part is missing) and returns 250 scores. This module turns capture v2's raw
landmarker output into that layout, cuts the live stream into single signs, and runs the model with a
TFLite interpreter (ai-edge-litert, tflite-runtime or TensorFlow, whichever is installed), which takes
the variable number of frames the model was built for. web/src/asl_islr.js is the browser port; both
follow shared_data/asl_islr_spec.json, and tests/golden/asl_islr_cases.json keeps them identical.

    from ml_engine.asl_islr import AslRecognizer, SignSegmenter, islr_frame
    recogniser = AslRecognizer()                    # checks the licence ledger, the file hash and the spec
    segmenter = SignSegmenter()
    for raw in capture_frames:                      # raw = CaptureV2.last_raw (unmirrored input)
        sign = segmenter.push(islr_frame(raw))
        if sign is not None:
            print(recogniser.predict(sign)[:3])     # [{"label", "display", "probability"}, ...]
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Sequence

from ml_engine.features_v2 import canonicalize_frame

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "shared_data" / "asl_islr_spec.json"
ASL_FEATURE_VERSION = "asl-islr-543-v1"
NAN = float("nan")


class AslModelError(RuntimeError):
    """The ASL model, its files or its runtime cannot be used."""


def load_spec(path: Path = SPEC_PATH) -> dict:
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    if spec.get("feature_version") != ASL_FEATURE_VERSION:
        raise AslModelError(f"unsupported ASL feature version {spec.get('feature_version')!r}; this code supports {ASL_FEATURE_VERSION}")
    if spec.get("sign_language") != "ASL":
        raise AslModelError("the ASL spec must say sign_language ASL")
    return spec


SPEC = load_spec()
ROWS = SPEC["layout"]["rows_per_frame"]
PART = {part["name"]: (part["start"], part["count"]) for part in SPEC["layout"]["parts"]}


# --------------------------------------------------------------------------- one frame

def _put(frame: list[list[float]], part: str, points: Sequence[Sequence[float]] | None) -> None:
    if points is None:
        return
    start, count = PART[part]
    if len(points) < count:
        raise ValueError(f"{part} needs at least {count} points, got {len(points)}")
    for offset in range(count):
        point = points[offset]
        frame[start + offset] = [float(point[0]), float(point[1]), float(point[2])]


def islr_frame(raw: dict, spec: dict | None = None) -> list[list[float]]:
    """543 x [x, y, z] for one frame of raw capture v2 output (see features_v2.canonicalize_frame).

    Hands go to the competition's left/right slots by the signer's anatomical side, decided the same
    way as features v2 (pose wrists first). Missing parts stay NaN.
    """
    if raw.get("input_mirrored"):
        raise ValueError("ASL mode needs unmirrored frames: mirror only the display (shared_data/asl_islr_spec.json)")
    canonical = canonicalize_frame(raw, spec)
    frame = [[NAN, NAN, NAN] for _ in range(ROWS)]
    _put(frame, "face", raw.get("face"))
    _put(frame, "pose", raw.get("pose"))
    _put(frame, "left_hand", canonical["left_hand"])
    _put(frame, "right_hand", canonical["right_hand"])
    return frame


def hands_present(frame: Sequence[Sequence[float]]) -> bool:
    """True when either hand slot of a 543-row frame holds a hand."""
    for part in ("left_hand", "right_hand"):
        start, _count = PART[part]
        if not math.isnan(frame[start][0]):
            return True
    return False


def hand_counts(frame: Sequence[Sequence[float]]) -> tuple[bool, bool]:
    """(left hand present, right hand present) for a 543-row frame."""
    return tuple(not math.isnan(frame[PART[part][0]][0]) for part in ("left_hand", "right_hand"))  # type: ignore[return-value]


# --------------------------------------------------------------------------- sequences

def resample_indices(length: int, frames: int) -> list[int]:
    """Nearest-frame indices that turn `length` frames into `frames` frames (integer arithmetic only)."""
    if length < 1 or frames < 1:
        raise ValueError("length and frames must be at least 1")
    if frames == 1:
        return [0]
    return [(2 * i * (length - 1) + (frames - 1)) // (2 * (frames - 1)) for i in range(frames)]


def resample(sequence: Sequence[Any], frames: int) -> list[Any]:
    return [sequence[i] for i in resample_indices(len(sequence), frames)]


class SignSegmenter:
    """Cut a live stream of 543-row frames into single signs (shared_data/asl_islr_spec.json, segmentation).

    push() returns a finished sign (a list of frames) or None. The rule is deliberately simple so it
    behaves the same in Python and JavaScript: a sign is the stretch of frames that show a hand, plus a
    small margin, ended by a short gap without hands.
    """

    def __init__(self, spec: dict | None = None):
        rules = (spec or SPEC)["segmentation"]
        self.min_hand_frames = int(rules["min_hand_frames"])
        self.end_after = int(rules["end_after_missing_frames"])
        self.margin = int(rules["margin_frames"])
        self.max_frames = int(rules["max_frames"])
        self.reset()

    def reset(self) -> None:
        self._before: list[Any] = []
        self._sign: list[Any] = []
        self._active = False
        self._missing = 0
        self._hand_frames = 0

    @property
    def active(self) -> bool:
        return self._active

    def _finish(self, keep: int) -> list[Any] | None:
        sign = self._sign[:keep]
        long_enough = self._hand_frames >= self.min_hand_frames
        tail = self._sign[keep:]
        self.reset()
        self._before = tail[-self.margin:] if self.margin else []
        return sign if long_enough else None

    def push(self, frame: Sequence[Sequence[float]], present: bool | None = None) -> list[Any] | None:
        present = hands_present(frame) if present is None else bool(present)
        if not self._active:
            if not present:
                if self.margin:
                    self._before.append(frame)
                    self._before = self._before[-self.margin:]
                return None
            self._active = True
            self._sign = list(self._before) + [frame]
            self._before = []
            self._missing = 0
            self._hand_frames = 1
            return None
        self._sign.append(frame)
        if present:
            self._missing = 0
            self._hand_frames += 1
        else:
            self._missing += 1
        if self._missing >= self.end_after:
            return self._finish(len(self._sign) - self._missing + self.margin)
        if len(self._sign) >= self.max_frames:
            return self._finish(len(self._sign))
        return None

    def flush(self) -> list[Any] | None:
        """End the current sign now (for example when the camera stops)."""
        if not self._active:
            return None
        return self._finish(len(self._sign) - self._missing + min(self._missing, self.margin))


# --------------------------------------------------------------------------- scores

def probabilities(scores: Sequence[float]) -> list[float]:
    """The model's 250 outputs as probabilities: kept if they already are, otherwise softmax."""
    values = [float(v) for v in scores]
    if values and all(0.0 <= v <= 1.0 for v in values) and abs(sum(values) - 1.0) < 1e-3:
        return values
    top = max(values)
    exps = [math.exp(v - top) for v in values]
    total = sum(exps)
    return [e / total for e in exps]


def load_classes(path: Path | None = None, spec: dict | None = None) -> list[str]:
    spec = spec or SPEC
    path = Path(path) if path else ROOT / spec["classes"]["file"]
    mapping = json.loads(path.read_text(encoding="utf-8"))
    labels = [None] * len(mapping)
    for label, index in mapping.items():
        labels[int(index)] = label
    if len(labels) != spec["classes"]["count"] or any(label is None for label in labels):
        raise AslModelError(f"{path} does not hold {spec['classes']['count']} distinct class indices")
    return labels  # type: ignore[return-value]


def display_name(label: str, spec: dict | None = None) -> str:
    return (spec or SPEC)["display_names"].get(label, label)


def top_k(scores: Sequence[float], labels: Sequence[str], k: int = 5, spec: dict | None = None) -> list[dict]:
    probs = probabilities(scores)
    order = sorted(range(len(probs)), key=lambda i: (-probs[i], i))[:k]
    return [{"label": labels[i], "display": display_name(labels[i], spec), "probability": probs[i]} for i in order]


def confidence_band(probability: float, spec: dict | None = None) -> str:
    """'sure', 'unsure' or 'none' (shared_data/asl_islr_spec.json, confidence). Only 'sure' may be spoken."""
    rules = (spec or SPEC)["confidence"]
    if probability >= rules["sure"]:
        return "sure"
    if probability >= rules["unsure"]:
        return "unsure"
    return "none"


def should_speak(probability: float, spec: dict | None = None) -> bool:
    """Speak aloud only when 'sure' and >= confidence.speak_at (0.70; measured 1.7 % wrong on the GISLR rerun set)."""
    rules = (spec or SPEC)["confidence"]
    return confidence_band(probability, spec) == "sure" and probability >= rules.get("speak_at", rules["sure"])


# --------------------------------------------------------------------------- the model

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _interpreter_class():
    """The first installed TFLite interpreter, and its name."""
    try:
        from ai_edge_litert.interpreter import Interpreter
        return Interpreter, "ai-edge-litert"
    except ImportError:
        pass
    try:
        from tflite_runtime.interpreter import Interpreter
        return Interpreter, "tflite-runtime"
    except ImportError:
        pass
    try:
        import tensorflow as tf
        return tf.lite.Interpreter, "tensorflow"
    except ImportError:
        pass
    raise AslModelError("no TFLite runtime is installed: run  pip install -r requirements.txt  (it includes ai-edge-litert)")


class AslRecognizer:
    """The ASL model with a TFLite interpreter. Refuses to start unless the ledger, spec and file hash agree."""

    def __init__(self, model_path: Path | str | None = None, classes_path: Path | str | None = None, spec: dict | None = None, num_threads: int = 2):
        from data_engine.ledger import LicenceError, assert_allowed

        self.spec = spec or SPEC
        if self.spec.get("feature_version") != ASL_FEATURE_VERSION:
            raise AslModelError(f"unsupported ASL feature version {self.spec.get('feature_version')!r}")
        model = self.spec["model"]
        try:
            assert_allowed(model["asset_id"], "redistribute_weights", purpose_language="ASL")
        except LicenceError as error:
            raise AslModelError(str(error)) from error
        self.model_path = Path(model_path) if model_path else ROOT / model["file"]
        if not self.model_path.exists():
            raise AslModelError(f"{self.model_path} is missing: run  python tools/fetch_assets.py  once with internet")
        actual = sha256_file(self.model_path)
        if actual != model["sha256"]:
            raise AslModelError(f"{self.model_path.name} has SHA-256 {actual}, expected {model['sha256']}; delete it and run tools/fetch_assets.py again")
        self.labels = load_classes(Path(classes_path) if classes_path else None, self.spec)
        interpreter_class, self.runtime = _interpreter_class()
        self._interpreter = interpreter_class(model_path=str(self.model_path), num_threads=num_threads)
        details = self._interpreter.get_input_details()
        if len(details) != 1 or list(details[0]["shape_signature"])[1:] != model["input"]["shape_signature"][1:]:
            raise AslModelError(f"unexpected model input {details}")
        self._input_index = details[0]["index"]
        self._output_index = self._interpreter.get_output_details()[0]["index"]
        self._frames = None

    def scores(self, sequence: Sequence[Sequence[Sequence[float]]]) -> list[float]:
        import numpy as np

        array = np.asarray(sequence, dtype=np.float32)
        if array.ndim != 3 or array.shape[1:] != (ROWS, 3) or array.shape[0] < 1:
            raise ValueError(f"expected frames x {ROWS} x 3, got {array.shape}")
        if self._frames != array.shape[0]:
            self._interpreter.resize_tensor_input(self._input_index, list(array.shape), strict=False)
            self._interpreter.allocate_tensors()
            self._frames = array.shape[0]
        self._interpreter.set_tensor(self._input_index, array)
        self._interpreter.invoke()
        return [float(v) for v in self._interpreter.get_tensor(self._output_index).reshape(-1)]

    def predict(self, sequence: Sequence[Sequence[Sequence[float]]], k: int = 5) -> list[dict]:
        return top_k(self.scores(sequence), self.labels, k, self.spec)


def describe_sign(sequence: Iterable[Sequence[Sequence[float]]]) -> dict:
    """Frame count and how many frames showed one or two hands (for reports and the UI hint)."""
    frames = list(sequence)
    both = one = 0
    for frame in frames:
        left, right = hand_counts(frame)
        if left and right:
            both += 1
        elif left or right:
            one += 1
    return {"frames": len(frames), "two_hand_frames": both, "one_hand_frames": one}
