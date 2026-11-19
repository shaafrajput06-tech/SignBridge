"""Hand landmark feature normalization shared by the desktop and API."""

from __future__ import annotations

import math
from typing import Iterable, Sequence


def _xyz(point: object) -> tuple[float, float, float]:
    if isinstance(point, dict):
        return float(point["x"]), float(point["y"]), float(point.get("z", 0.0))
    if hasattr(point, "x"):
        return float(point.x), float(point.y), float(getattr(point, "z", 0.0))
    values = list(point)  # type: ignore[arg-type]
    return float(values[0]), float(values[1]), float(values[2] if len(values) > 2 else 0.0)


def normalize_landmarks(landmarks: Iterable[object], handedness: str = "Right") -> list[float]:
    """Return 63 wrist-relative, scale-normalized coordinates.

    Coordinates are normalized in their input units, so the result is
    consistent for MediaPipe's normalized image coordinates and pixel data.
    Left hands are mirrored into a right-hand orientation.
    """
    points = [_xyz(point) for point in landmarks]
    if len(points) != 21:
        raise ValueError(f"Expected 21 hand landmarks, got {len(points)}")
    ox, oy, oz = points[0]
    centered = [(x - ox, y - oy, z - oz) for x, y, z in points]
    if handedness.lower() == "left":
        centered = [(-x, y, z) for x, y, z in centered]
    scale = max(math.hypot(x, y) for x, y, _ in centered)
    if scale <= 1e-9:
        raise ValueError("Landmarks do not describe a hand with a measurable size")
    return [coordinate / scale for point in centered for coordinate in point]


def feature_vector(values: Sequence[float]) -> list[float]:
    """Validate an already-normalized classifier input."""
    if len(values) != 63:
        raise ValueError(f"Expected 63 normalized features, got {len(values)}")
    output = [float(value) for value in values]
    if not all(math.isfinite(value) for value in output):
        raise ValueError("Features must be finite numbers")
    return output
