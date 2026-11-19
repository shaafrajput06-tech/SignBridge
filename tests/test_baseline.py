"""Phase 0 characterisation tests: what SignBridge does at the start of the v2 work.

These tests pin down current behaviour so later refactors can be checked against it.
Tests named ``test_current_*`` record known limitations that a later phase is expected
to change (the docstring names the phase). Update those deliberately when that phase lands.
"""

from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
import math
import os
import sys
import tempfile
import threading
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

from collect_data import CSV_HEADER, load_rows, save_rows
from ml_engine.features import normalize_landmarks
from ml_engine.gestures import classify_gesture
from test_core import sample_hand
from vocabulary_utils import load_vocabulary

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_V1 = ROOT / "tests" / "golden" / "v1_hands.json"
VOCABULARY_COPIES = [ROOT / "vocabulary.json", ROOT / "shared_data" / "vocabulary.json", ROOT / "mobile" / "assets" / "vocabulary.json"]
DEMO_GESTURES = {
    "OPEN_PALM", "THREE_FINGERS", "VICTORY", "THUMBS_UP", "CLOSED_FIST", "POINT", "STOP_PALM",
    "INDEX_UP", "FOUR_FINGERS", "CALL_ME", "OK", "THUMBS_DOWN", "FIVE_FINGERS",
}


def _mirror(points):
    return [(1.0 - x, y, z) for x, y, z in points]


def _swap(handedness: str) -> str:
    return "Right" if handedness == "Left" else "Left"


class VocabularyCopiesTests(unittest.TestCase):
    def test_all_three_vocabulary_copies_are_byte_identical(self):
        digests = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in VOCABULARY_COPIES}
        self.assertEqual(len(set(digests.values())), 1, f"Vocabulary copies differ: {digests}")

    def test_sync_tool_check_mode_agrees(self):
        import subprocess
        completed = subprocess.run([sys.executable, str(ROOT / "tools" / "sync_vocabulary.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_demo_items_map_one_to_one_onto_the_thirteen_rule_gestures(self):
        items = load_vocabulary()
        demo = [item for item in items if item["demoAvailable"]]
        gesture_ids = [item["gestureId"] for item in demo]
        self.assertEqual(len(gesture_ids), len(set(gesture_ids)), "a gesture is mapped to two vocabulary items")
        self.assertEqual(set(gesture_ids), DEMO_GESTURES)
        self.assertTrue(all(not item.get("gestureId") for item in items if not item["demoAvailable"]))

    def test_every_demo_gesture_id_exists_in_the_python_and_browser_rules(self):
        python_rules = (ROOT / "ml_engine" / "gestures.py").read_text(encoding="utf-8")
        browser_rules = (ROOT / "web" / "src" / "vision.js").read_text(encoding="utf-8")
        for gesture in DEMO_GESTURES:
            self.assertIn(f'"{gesture}"', python_rules)
            self.assertIn(f'"{gesture}"', browser_rules)


class MirrorConsistencyTests(unittest.TestCase):
    """Desktop mirrors the frame before detection and the browser does not (audit P1-3).

    For the two paths to agree, mirroring the landmarks and swapping the handedness label
    must give identical features, and the demo rules must ignore left/right mirroring.
    Whether MediaPipe's own landmarks are mirror-consistent needs real recordings (Phase 1).
    """

    def test_mirrored_landmarks_with_swapped_label_give_identical_features(self):
        cases = json.loads(GOLDEN_V1.read_text(encoding="utf-8"))["cases"]
        for case in cases:
            points = [tuple(point) for point in case["points"]]
            expected = normalize_landmarks(points, case["handedness"])
            mirrored = normalize_landmarks(_mirror(points), _swap(case["handedness"]))
            self.assertLess(max(abs(a - b) for a, b in zip(expected, mirrored)), 1e-12, case["id"])

    def test_demo_rules_ignore_left_right_mirroring(self):
        cases = json.loads(GOLDEN_V1.read_text(encoding="utf-8"))["cases"]
        for case in cases:
            points = [tuple(point) for point in case["points"]]
            self.assertEqual(classify_gesture(_mirror(points)), classify_gesture(points), case["id"])


class GoldenV1Tests(unittest.TestCase):
    """The Python reference must reproduce the committed v1 fixture exactly (web/tests checks JS)."""

    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(GOLDEN_V1.read_text(encoding="utf-8"))

    def test_fixture_covers_every_demo_gesture_and_the_uncertain_case(self):
        outputs = {case["gesture"] for case in self.fixture["cases"]}
        self.assertTrue(DEMO_GESTURES <= outputs)
        self.assertIn(None, outputs)

    def test_python_reproduces_fixture_gestures_and_features(self):
        tolerance = self.fixture["feature_tolerance"]
        for case in self.fixture["cases"]:
            points = [tuple(point) for point in case["points"]]
            self.assertEqual(classify_gesture(points), case["gesture"], case["id"])
            features = normalize_landmarks(points, case["handedness"])
            self.assertEqual(len(features), 63)
            self.assertLess(max(abs(a - b) for a, b in zip(features, case["features"])), tolerance, case["id"])

    def test_degenerate_hand_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_landmarks([(0.5, 0.5, 0.0)] * 21)
        self.assertIsNone(classify_gesture([(0.5, 0.5, 0.0)] * 21))

    def test_current_rules_change_answer_when_the_image_is_rotated_90_degrees(self):
        """Known limit (Phase 5 / Flutter rotation): unrotated portrait phone frames change demo answers."""
        def rotate(points, degrees):
            angle = math.radians(degrees)
            wx, wy, _ = points[0]
            return [(wx + (x - wx) * math.cos(angle) - (y - wy) * math.sin(angle), wy + (x - wx) * math.sin(angle) + (y - wy) * math.cos(angle), z) for x, y, z in points]
        index_up = sample_hand([True, False, False, False])
        thumbs_up = sample_hand([False] * 4, thumb="up")
        point = sample_hand([True, False, False, False], direction="point")
        self.assertEqual(classify_gesture(rotate(index_up, 90)), "POINT")
        self.assertIsNone(classify_gesture(rotate(thumbs_up, 90)))
        self.assertEqual(classify_gesture(rotate(point, 90)), "CLOSED_FIST")


class CsvRoundTripTests(unittest.TestCase):
    def test_save_then_load_keeps_rows_and_header(self):
        row = ["hello", "anonymous", "session-a", "2026-01-01T00:00:00Z", "2", "640", "480", "Right"] + [f"{0.01 * i:.8f}" for i in range(63)]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sign_data.csv"
            save_rows([row, row], path)
            with path.open(encoding="utf-8", newline="") as stream:
                self.assertEqual(next(csv.reader(stream)), CSV_HEADER)
            self.assertEqual(load_rows(path), [row, row])


def _synthetic_training_rows(participants, sessions_per_participant=2, frames=12, seed=3):
    """Synthetic smoke-test rows. They only prove the script runs; no score from them is meaningful."""
    import random
    rng = random.Random(seed)
    poses = {"hello": dict(extended=[True] * 4, thumb="extended", spread=True), "no": dict(extended=[False] * 4), "please": dict(extended=[True, True, False, False])}
    rows = []
    for participant in participants:
        for session in range(sessions_per_participant):
            for label, options in poses.items():
                for frame in range(frames):
                    points = [(x + rng.gauss(0, 0.01), y + rng.gauss(0, 0.01), z) for x, y, z in sample_hand(**options)]
                    rows.append([label, participant, f"{participant}-{session}", "2026-01-01T00:00:00Z", str(frame), "640", "480", "Right"] + [f"{value:.8f}" for value in normalize_landmarks(points)])
    return rows


class TrainingSmokeTests(unittest.TestCase):
    """train_model.py runs end to end on current library versions. No accuracy is asserted."""

    def _train(self, rows):
        try:
            import train_model
        except ImportError as error:
            self.skipTest(f"training dependencies are not installed: {error}")
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        base = Path(directory.name)
        data = base / "sign_data.csv"
        save_rows(rows, data)
        original_load = train_model.load_data
        with patch.object(train_model, "load_data", lambda: original_load(data)), \
                patch.object(train_model, "MODEL_DIR", base / "models"), \
                patch.object(train_model, "REPORT_PATH", base / "reports" / "training_report.txt"), \
                patch.object(train_model, "MATRIX_PATH", base / "reports" / "confusion_matrix.csv"), \
                patch.object(train_model, "METADATA_PATH", base / "models" / "model_metadata.json"), \
                warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
            warnings.simplefilter("ignore")
            train_model.main()
        return base

    def test_person_grouped_training_writes_model_metadata_and_report(self):
        from ml_engine.model_loader import load_model_bundle
        base = self._train(_synthetic_training_rows(["p1", "p2", "p3"]))
        bundle = load_model_bundle(base / "models" / "sign_classifier.joblib")
        self.assertIsNotNone(bundle)
        self.assertEqual(sorted(bundle["classes"]), ["hello", "no", "please"])
        metadata = json.loads((base / "models" / "model_metadata.json").read_text(encoding="utf-8"))
        self.assertIn("person-grouped", metadata["evaluation_method"])
        report = (base / "reports" / "training_report.txt").read_text(encoding="utf-8")
        self.assertIn("Evaluation: person-grouped", report)
        self.assertTrue((base / "reports" / "confusion_matrix.csv").exists())

    def test_current_single_participant_falls_back_to_frame_level_split(self):
        """Known limit (Phase 3, audit P0-4): one signer and one session yields a frame-level split, labelled weaker."""
        base = self._train(_synthetic_training_rows(["solo"], sessions_per_participant=1))
        metadata = json.loads((base / "models" / "model_metadata.json").read_text(encoding="utf-8"))
        self.assertIn("frame-level", metadata["evaluation_method"])
        self.assertIn("weaker", metadata["evaluation_method"])


class MergeSmokeTests(unittest.TestCase):
    def test_merge_removes_exact_duplicates_and_leaves_sources_untouched(self):
        import merge_data
        rows = _synthetic_training_rows(["p1"], sessions_per_participant=1, frames=2)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            first, second = base / "a.csv", base / "b.csv"
            save_rows(rows, first)
            save_rows(rows[:3], second)
            before = (first.read_bytes(), second.read_bytes())
            with patch.object(merge_data, "DATA_PATH", base / "sign_data.csv"), patch.object(sys, "argv", ["merge_data.py", str(first), str(second)]), contextlib.redirect_stdout(io.StringIO()):
                merge_data.main()
            merged = list(base.glob("merged_*.csv"))
            self.assertEqual(len(merged), 1)
            self.assertEqual(len(load_rows(merged[0])), len(rows))
            self.assertEqual((first.read_bytes(), second.read_bytes()), before)
            self.assertFalse((base / "sign_data.csv").exists())


class _Hand:
    def __init__(self, features):
        self.features = features
        self.landmarks = sample_hand([False] * 4)


class _UniformModel:
    """Stands in for a trained classifier that is unsure: equal probability for every class."""
    classes_ = ["hello", "no", "please"]

    def predict(self, rows):
        return ["no" for _ in rows]

    def predict_proba(self, rows):
        import numpy as np
        return np.full((len(rows), 3), 1 / 3)


class DesktopPredictTests(unittest.TestCase):
    """Characterises app._predict (audit P0-3 and Phase 0 finding 3)."""

    @classmethod
    def setUpClass(cls):
        try:
            import app
        except ImportError as error:
            raise unittest.SkipTest(f"desktop dependencies are not installed: {error}")
        cls.predict = staticmethod(app._predict)
        cls.hand = _Hand([0.0] * 63)

    def test_calibrated_model_below_threshold_is_rejected(self):
        label, status = self.predict(self.hand, {"model": _UniformModel(), "has_calibrated_probabilities": True}, 0.72)
        self.assertIsNone(label)
        self.assertIn("below threshold", status)

    def test_current_uncalibrated_model_is_never_rejected(self):
        """Known limit (Phase 3): when Random Forest is selected the flag is False and no threshold applies."""
        label, status = self.predict(self.hand, {"model": _UniformModel(), "has_calibrated_probabilities": False}, 0.72)
        self.assertEqual(label, "no")
        self.assertIn("uncalibrated", status)

    def test_demo_mode_maps_rule_gesture_to_vocabulary(self):
        label, status = self.predict(self.hand, None, 0.72)
        self.assertEqual(label, "no")
        self.assertEqual(status, "Rule-based match")


class SpeechCacheTests(unittest.TestCase):
    """Cached-audio playback works with whichever pygame distribution is installed (pygame or pygame-ce)."""

    def test_cached_file_is_played_back(self):
        try:
            import pygame  # noqa: F401
        except ImportError:
            self.skipTest("pygame/pygame-ce is not installed")
        import speech
        previous_driver = os.environ.get("SDL_AUDIODRIVER")
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        self.addCleanup(lambda: os.environ.pop("SDL_AUDIODRIVER", None) if previous_driver is None else os.environ.__setitem__("SDL_AUDIODRIVER", previous_driver))
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            name = hashlib.sha256("en:Hello".encode("utf-8")).hexdigest()[:24]
            (cache / f"en_{name}.mp3").write_bytes((ROOT / "tests" / "fixtures" / "silence_250ms.mp3").read_bytes())
            result = {}
            with patch.object(speech, "CACHE_DIR", cache):
                worker = threading.Thread(target=lambda: result.setdefault("played", speech.Speaker(enabled=False)._speak_cache("Hello", "en")), daemon=True)
                worker.start()
                worker.join(timeout=15)
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.music.unload() if hasattr(pygame.mixer.music, "unload") else None
                pygame.mixer.quit()
        self.assertFalse(worker.is_alive(), "cached playback did not finish")
        self.assertTrue(result.get("played"))


if __name__ == "__main__":
    unittest.main()
