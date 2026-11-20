"""Writes tests/golden/psl_hands_cases.json: inputs and expected PSL model inputs (resample + camera-shape
rule), so web/src/psl_hands.js and ml_engine/psl_hands.py stay identical. Rerun only when the spec changes.

    python tools/psl_golden.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml_engine import psl_hands  # noqa: E402

OUT = ROOT / "tests" / "golden" / "psl_hands_cases.json"
CASES = [(12, 16 / 9, 0), (40, 9 / 16, 2)]  # up-sampled and down-sampled


def as_list(array: np.ndarray, digits: int = 7) -> list:
    return [[[None if np.isnan(v) else round(float(v), digits) for v in point] for point in frame] for frame in array]


def build() -> dict:
    cases = []
    for length, aspect, seed in CASES:
        rng = np.random.default_rng(seed)
        hands = rng.uniform(0.2, 0.8, (length, 2, 21, 3)).round(6)
        hands[..., 2] = rng.normal(0, 0.05, (length, 2, 21)).round(6)
        hands[: length // 4, 0] = np.nan
        hands[length // 2: length // 2 + 2, 1] = np.nan
        fixed = psl_hands.fixed_length(hands, trim=False)
        expected = psl_hands.adjust_aspect(fixed, aspect).astype(np.float32)
        cases.append({
            "aspect": aspect,
            "hands": as_list(hands.reshape(length, 42, 3)),
            "expected_hands": as_list(expected.reshape(psl_hands.FRAMES, 42, 3).astype(np.float64)),
        })
    return {"about": "hand rows only (left 21 then right 21 per frame); face and pose rows are NaN; null = NaN; expected values rounded to 7 decimals",
            "feature_version": psl_hands.SPEC["feature_version"], "cases": cases}


if __name__ == "__main__":
    OUT.write_text(json.dumps(build()), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
