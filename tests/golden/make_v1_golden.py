"""Regenerate tests/golden/v1_hands.json, the v1 cross-language parity fixture.

The hands are synthetic geometry built from the pose generator in tests/test_core.py,
then rotated, mirrored and jittered. They exist only to check that every implementation
of the v1 feature normalisation and demo rules (Python, JavaScript, later Dart) produces
the same output for the same input. They are not recorded signer data and must never be
used for training or evaluation.

Run from the project root:  python tests/golden/make_v1_golden.py
Regenerate only when the v1 behaviour is changed on purpose; the tests compare against
this file, so regenerating it hides a regression instead of catching it.
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

from ml_engine.features import normalize_landmarks  # noqa: E402
from ml_engine.gestures import classify_gesture  # noqa: E402
from test_core import sample_hand  # noqa: E402

OUTPUT = Path(__file__).resolve().parent / "v1_hands.json"
SEED = 20261110
POSES = {
    "CLOSED_FIST": dict(extended=[False] * 4),
    "INDEX_UP": dict(extended=[True, False, False, False]),
    "VICTORY": dict(extended=[True, True, False, False]),
    "THREE_FINGERS": dict(extended=[True, True, True, False]),
    "FOUR_FINGERS": dict(extended=[True] * 4, spread=True),
    "OPEN_PALM": dict(extended=[True] * 4, thumb="extended", spread=True),
    "STOP_PALM": dict(extended=[True] * 4),
    "FIVE_FINGERS": dict(extended=[True] * 4, thumb="extended"),
    "THUMBS_UP": dict(extended=[False] * 4, thumb="up"),
    "THUMBS_DOWN": dict(extended=[False] * 4, thumb="down"),
    "POINT": dict(extended=[True, False, False, False], direction="point"),
    "OK": dict(extended=[False, True, True, False]),
    "CALL_ME": dict(extended=[False, False, False, True], thumb="extended"),
}
VARIANTS_PER_POSE = 20


def rotate(points, degrees):
    angle = math.radians(degrees)
    wx, wy, _ = points[0]
    cos, sin = math.cos(angle), math.sin(angle)
    return [(wx + (x - wx) * cos - (y - wy) * sin, wy + (x - wx) * sin + (y - wy) * cos, z) for x, y, z in points]


def build_cases() -> list[dict]:
    rng = random.Random(SEED)
    cases = []
    for pose, options in POSES.items():
        for variant in range(VARIANTS_PER_POSE):
            points = sample_hand(**options)
            if variant == 0:
                angle, noise = 0.0, 0.0
            elif variant % 5 == 0:
                angle, noise = rng.choice([90.0, -90.0, 180.0]), 0.01
            else:
                angle, noise = rng.uniform(-35.0, 35.0), rng.choice([0.0, 0.006, 0.012])
            points = rotate(points, angle)
            points = [(x + rng.gauss(0, noise), y + rng.gauss(0, noise), z + rng.gauss(0, noise / 2)) for x, y, z in points]
            mirrored = variant % 2 == 1
            if mirrored:
                points = [(1.0 - x, y, z) for x, y, z in points]
            points = [(round(x, 6), round(y, 6), round(z, 6)) for x, y, z in points]
            handedness = "Left" if mirrored else "Right"
            cases.append({
                "id": f"{pose.lower()}_{variant:02d}",
                "source_pose": pose,
                "rotation_degrees": round(angle, 3),
                "mirrored": mirrored,
                "handedness": handedness,
                "points": [list(point) for point in points],
                "gesture": classify_gesture(points),
                "features": [round(value, 12) for value in normalize_landmarks(points, handedness)],
            })
    return cases


def main() -> None:
    payload = {
        "fixture": "SignBridge v1 parity fixture",
        "spec": "63 wrist-relative features (ml_engine/features.py normalize_landmarks) and demo rules (ml_engine/gestures.py classify_gesture)",
        "note": "Synthetic hand geometry for cross-language parity tests only. Not recorded signer data. Never use for training or evaluation.",
        "generator": "tests/golden/make_v1_golden.py",
        "seed": SEED,
        "feature_tolerance": 1e-9,
        "cases": build_cases(),
    }
    OUTPUT.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {len(payload['cases'])} cases to {OUTPUT}")


if __name__ == "__main__":
    main()
