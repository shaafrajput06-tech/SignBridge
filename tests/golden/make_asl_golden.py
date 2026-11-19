"""Write tests/golden/asl_islr_cases.json: shared inputs for the ASL-mode Python/JavaScript parity test.

    python tests/golden/make_asl_golden.py

The file holds inputs only (resampling sizes, hand-presence streams, model score vectors). The
expected results are computed by ml_engine/asl_islr.py in tests/test_asl_islr.py and compared with
web/src/asl_islr.js through web/tests/tools/dump-asl.mjs. The raw capture frames come from the
features v2 fixture (tests/golden/v2_holistic.json.gz).
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent / "asl_islr_cases.json"


def main() -> None:
    rng = random.Random(20261118)
    resample = [[length, count] for count in (1, 2, 16, 24, 32, 48, 64) for length in (1, 2, 3, 7, 16, 31, 32, 33, 64, 100, 191, 192)]

    streams = [
        [0] * 5 + [1] * 12 + [0] * 12,                       # one clean sign
        [0] * 3 + [1] * 4 + [0] * 12,                         # too short: dropped
        [1] * 10 + [0] * 3 + [1] * 10 + [0] * 10,             # a short gap does not end the sign
        [0] * 2 + [1] * 10 + [0] * 9 + [1] * 8 + [0] * 9,      # two signs
        [1] * 200 + [0] * 9,                                  # longer than max_frames: cut
        [0] * 4 + [1] * 9 + [0] * 3,                          # still open at the end: flush
        [0] * 10,                                             # nothing
    ]
    for _ in range(6):
        streams.append([1 if rng.random() < 0.55 else 0 for _ in range(rng.randint(20, 120))])

    scores = []
    logits = [rng.gauss(0.0, 2.0) for _ in range(250)]
    scores.append([round(v, 6) for v in logits])
    top = max(logits)
    exps = [math.exp(v - top) for v in logits]
    total = sum(exps)
    scores.append([e / total for e in exps])
    clear = [rng.uniform(-1.0, 1.0) for _ in range(250)]
    clear[113] = 9.0
    scores.append(clear)
    scores.append([0.0] * 250)
    tie = [0.0] * 250
    tie[7] = tie[3] = 4.0
    scores.append(tie)

    OUT.write_text(json.dumps({"fixture": "SignBridge ASL mode parity cases", "resample": resample,
                               "segmenter_streams": streams, "scores": scores}, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(resample)} resampling cases, {len(streams)} streams, {len(scores)} score vectors)")


if __name__ == "__main__":
    main()
