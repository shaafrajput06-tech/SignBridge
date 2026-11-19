"""Fast track section 2: capture v2 asks MediaPipe for two hands on every platform that runs it.

The JavaScript side is covered by web/tests/capture-v2.test.mjs (numHands === 2). The phone does not
run MediaPipe on the device yet (it sends frames to the server), so there is no Dart check until
Stage 6 moves landmarking onto the phone.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml_engine.capture_v2 import SPEC, SplitLandmarkerBackend  # noqa: E402


class TwoHandsTests(unittest.TestCase):
    def test_feature_spec_asks_for_two_hands(self):
        self.assertEqual(SPEC["capture_models"]["hand"]["num"], 2)
        parts = [part["name"] for part in SPEC["parts"]]
        self.assertIn("left_hand", parts)
        self.assertIn("right_hand", parts)

    def test_python_capture_passes_num_hands_2_to_mediapipe(self):
        try:
            import mediapipe as mp
        except ImportError:
            self.skipTest("mediapipe is not installed")
        captured = {}

        def fake_create(options):
            captured["options"] = options
            return MagicMock()

        with patch.object(mp.tasks.vision.HandLandmarker, "create_from_options", side_effect=fake_create):
            backend = SplitLandmarkerBackend(parts=("hands",), download=False)
            backend.close()
        self.assertEqual(captured["options"].num_hands, 2)

    def test_web_capture_reads_the_hand_count_from_the_spec(self):
        source = (ROOT / "web" / "src" / "capture_v2.js").read_text(encoding="utf-8")
        self.assertIn("numHands: models.hand.num", source)


if __name__ == "__main__":
    unittest.main()
