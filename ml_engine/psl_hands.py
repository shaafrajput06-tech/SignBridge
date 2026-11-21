"""PSL hands view (shared_data/psl_hands_spec.json): the reference maths, in numpy.

The PSL model reads the two hands of the baseline's 543-point layout. This module is the reference for
the same steps the model does inside its graph (tools/psl_train/graph.py) and for the client-side input
rules (aspect correction, trimming, resampling), which web/src/psl_hands.js repeats. Golden cases in
tests/golden/psl_hands_cases.json keep them identical.

Arrays: hands is (frames, 2, 21, 3) float, hand 0 = the signer's left, hand 1 = the signer's right, x and y
normalised to the image, NaN for a missing hand.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

SPEC_PATH = Path(__file__).resolve().parents[1] / "shared_data" / "psl_hands_spec.json"
LEFT_ROWS = slice(468, 489)
RIGHT_ROWS = slice(522, 543)
ROWS_PER_FRAME = 543


def load_spec(path: Path = SPEC_PATH) -> dict:
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    if spec.get("feature_version") != "psl-hands-v1":
        raise ValueError(f"unsupported PSL hands spec {spec.get('feature_version')}")
    return spec


SPEC = load_spec()
FRAMES = SPEC["model_input"]["frames"]
ASPECT_REFERENCE = SPEC["model_input"]["aspect_reference"]
HAND_POINTS = SPEC["features"]["hand_points"]
FEATURES_PER_FRAME = SPEC["features"]["features_per_frame"]
CLIP = tuple(SPEC["features"]["clip"])
MARGIN = 2


def present(hands: np.ndarray) -> np.ndarray:
    """(frames, 2) bool: the hand's wrist x is a number."""
    return ~np.isnan(hands[..., 0, 0])


def resample_indices(length: int, frames: int = FRAMES) -> np.ndarray:
    """The baseline's nearest-frame rule (asl_islr_spec.json fixed_length.rule)."""
    if length < 1:
        raise ValueError("cannot resample an empty sequence")
    if frames == 1:
        return np.zeros(1, dtype=np.int64)
    i = np.arange(frames, dtype=np.int64)
    return (2 * i * (length - 1) + (frames - 1)) // (2 * (frames - 1))


def trim_window(hands: np.ndarray, margin: int = MARGIN) -> tuple[int, int] | None:
    """[start, end) of the frames from the first to the last frame with a hand, plus the margin."""
    any_hand = present(hands).any(axis=1)
    where = np.flatnonzero(any_hand)
    if where.size == 0:
        return None
    return max(0, int(where[0]) - margin), min(len(hands), int(where[-1]) + 1 + margin)


def adjust_aspect(hands: np.ndarray, aspect: float, reference: float = ASPECT_REFERENCE) -> np.ndarray:
    """Map x (and z) of a camera with width/height `aspect` to the training camera's shape."""
    out = np.array(hands, dtype=np.float64, copy=True)
    ratio = float(aspect) / float(reference)
    out[..., 0] = 0.5 + (out[..., 0] - 0.5) * ratio
    out[..., 2] = out[..., 2] * ratio
    return out


def fixed_length(hands: np.ndarray, frames: int = FRAMES, trim: bool = True) -> np.ndarray | None:
    """Trim (training) and resample to the model's frame count. None when no frame has a hand."""
    if trim:
        window = trim_window(hands)
        if window is None:
            return None
        hands = hands[window[0]:window[1]]
    return np.asarray(hands)[resample_indices(len(hands), frames)]


def features(hands: np.ndarray, reference: float = ASPECT_REFERENCE) -> np.ndarray:
    """(..., frames, 2, 21, 3) -> (..., frames, 174) float32, exactly as the model computes them."""
    h = np.asarray(hands, dtype=np.float64)
    mask = ~np.isnan(h[..., 0, 0])  # (..., T, 2)
    p = np.where(np.isnan(h), 0.0, h)
    p = p * np.array([reference, 1.0, reference])
    rel = p - p[..., :1, :]  # minus the wrist
    size = np.sqrt((rel[..., :2] ** 2).sum(-1)).max(-1)  # (..., T, 2)
    valid = mask & (size > 1e-6)
    count = valid.sum(axis=(-1, -2))
    scale = np.where(count > 0, (size * valid).sum(axis=(-1, -2)) / np.maximum(count, 1), 1.0)
    scale = scale[..., None, None]  # (..., 1, 1)

    shape = rel / np.where(valid, size, 1.0)[..., None, None]
    shape = np.where(valid[..., None, None], shape, 0.0).reshape(*shape.shape[:-3], 126)

    origin = np.array([0.5 * reference, 0.5])
    wrist = (p[..., 0, :2] - origin) / scale[..., None]  # (..., T, 2, 2)
    wrist = np.where(mask[..., None], wrist, 0.0)
    both = mask[..., 1:, :] & mask[..., :-1, :]
    motion = np.zeros_like(wrist)
    motion[..., 1:, :, :] = np.where(both[..., None], wrist[..., 1:, :, :] - wrist[..., :-1, :, :], 0.0)

    hand_size = np.where(mask, size / scale, 0.0)

    left = p[..., 0, HAND_POINTS, :2]  # (..., T, 6, 2)
    right = p[..., 1, HAND_POINTS, :2]
    diff = left[..., :, None, :] - right[..., None, :, :]
    distance = np.sqrt((diff ** 2).sum(-1)) / scale[..., None]  # (..., T, 6, 6)
    pair = mask[..., 0] & mask[..., 1]
    distance = np.where(pair[..., None, None], distance, 0.0).reshape(*distance.shape[:-2], 36)

    out = np.concatenate([
        shape,
        wrist.reshape(*wrist.shape[:-2], 4),
        motion.reshape(*motion.shape[:-2], 4),
        hand_size,
        distance,
        mask.astype(np.float64),
    ], axis=-1)
    return np.clip(out, *CLIP).astype(np.float32)


def to_islr(hands: np.ndarray) -> np.ndarray:
    """(frames, 2, 21, 3) -> (frames, 543, 3) float32 in the baseline layout (NaN for face and pose)."""
    out = np.full((len(hands), ROWS_PER_FRAME, 3), np.nan, dtype=np.float32)
    out[:, LEFT_ROWS] = hands[:, 0]
    out[:, RIGHT_ROWS] = hands[:, 1]
    return out


def from_islr(frames: np.ndarray) -> np.ndarray:
    """(frames, 543, 3) -> (frames, 2, 21, 3); a hand with any missing value counts as missing."""
    frames = np.asarray(frames, dtype=np.float64)
    hands = np.stack([frames[:, LEFT_ROWS], frames[:, RIGHT_ROWS]], axis=1)
    missing = np.isnan(hands).any(axis=(-1, -2))
    hands[missing] = np.nan
    return hands


def mirror(hands: np.ndarray) -> np.ndarray:
    """The same sign as a left-handed signer would make it: x -> 1 - x, hands swapped."""
    out = np.array(hands, dtype=np.float64, copy=True)[..., ::-1, :, :]
    out[..., 0] = 1.0 - out[..., 0]
    return out


def hand_use(hands: np.ndarray) -> dict:
    """How a sample uses its hands: frames with each hand, and which hand leads."""
    m = present(hands)
    left, right = int(m[:, 0].sum()), int(m[:, 1].sum())
    any_hand = int(m.any(axis=1).sum())
    both = int(m.all(axis=1).sum())
    return {"left": left, "right": right, "any": any_hand, "both": both,
            "two_handed": bool(any_hand and both / any_hand >= 0.5),
            "dominant": "right" if right >= left else "left"}
