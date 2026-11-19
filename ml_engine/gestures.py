"""Conservative rule-based geometry for a small exhibition gesture set."""

from __future__ import annotations

import math
from typing import Iterable


def _point(value: object) -> tuple[float, float, float]:
    if isinstance(value, dict):
        return float(value["x"]), float(value["y"]), float(value.get("z", 0.0))
    if hasattr(value, "x"):
        return float(value.x), float(value.y), float(getattr(value, "z", 0.0))
    row = list(value)  # type: ignore[arg-type]
    return float(row[0]), float(row[1]), float(row[2] if len(row) > 2 else 0.0)


def _distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _dot(a: tuple[float, float], b: tuple[float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _finger_extended(points: list[tuple[float, float, float]], mcp: int, pip: int, tip: int) -> bool:
    wrist = points[0]
    palm = (points[9][0] - wrist[0], points[9][1] - wrist[1])
    finger = (points[tip][0] - points[pip][0], points[tip][1] - points[pip][1])
    palm_length = math.hypot(*palm)
    if palm_length < 1e-6:
        return False
    forward = _dot(finger, (palm[0] / palm_length, palm[1] / palm_length))
    wrist_tip = _distance(wrist, points[tip])
    wrist_pip = _distance(wrist, points[pip])
    extended_length = wrist_tip > wrist_pip * 1.08
    horizontal_index = mcp == 5 and abs(finger[0]) > abs(finger[1]) * 1.15
    return extended_length and (forward > palm_length * 0.12 or horizontal_index)


def classify_gesture(landmarks: Iterable[object]) -> str | None:
    """Classify only visibly distinct static shapes; return a gesture ID or None.

    A narrow, upright open palm is treated as the stop pose; a splayed open
    palm is Hello. This distinction is a demo convention, not sign-language
    interpretation. Camera geometry cannot distinguish signs that use the
    same hand shape or require movement, facial expression, or context.
    """
    points = [_point(value) for value in landmarks]
    if len(points) != 21:
        return None
    scale = max(_distance(points[0], point) for point in points)
    if scale < 1e-6:
        return None

    fingers = [
        _finger_extended(points, 5, 6, 8),
        _finger_extended(points, 9, 10, 12),
        _finger_extended(points, 13, 14, 16),
        _finger_extended(points, 17, 18, 20),
    ]
    thumb_tip = points[4]
    thumb_ip = points[3]
    thumb_extended = (
        _distance(thumb_tip, points[5]) > scale * 0.55
        and _distance(thumb_tip, points[2]) > _distance(thumb_ip, points[2]) * 1.08
    )
    count = sum(fingers)
    finger_span = _distance(points[8], points[20]) / scale
    thumb_index_gap = _distance(points[4], points[8]) / scale

    if thumb_index_gap < 0.24 and fingers[1] and fingers[2]:
        return "OK"
    if thumb_extended and fingers[3] and count <= 1:
        return "CALL_ME"
    if count == 0 and thumb_extended:
        dx = thumb_tip[0] - points[0][0]
        dy = thumb_tip[1] - points[0][1]
        if abs(dx) < scale * 0.72 and dy < -scale * 0.3:
            return "THUMBS_UP"
        if abs(dx) < scale * 0.72 and dy > scale * 0.3:
            return "THUMBS_DOWN"
    if count == 0 and not thumb_extended:
        return "CLOSED_FIST"

    if count == 1 and fingers[0] and not thumb_extended:
        index = points[8]
        base = points[5]
        dx, dy = index[0] - base[0], index[1] - base[1]
        if abs(dy) > abs(dx) * 1.15 and dy < 0:
            return "INDEX_UP"
        if abs(dx) > abs(dy) * 1.15:
            return "POINT"

    if count == 2 and fingers[0] and fingers[1]:
        return "VICTORY"
    if count == 3 and all(fingers[:3]):
        return "THREE_FINGERS"
    if count == 4:
        if thumb_extended:
            return "FIVE_FINGERS" if finger_span <= 0.72 else "OPEN_PALM"
        return "FOUR_FINGERS" if finger_span > 0.58 else "STOP_PALM"
    return None
