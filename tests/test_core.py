import csv
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collect_data import CSV_HEADER, load_rows
from ml_engine.features import feature_vector, normalize_landmarks
from ml_engine.gestures import classify_gesture
from ml_engine.model_loader import load_model_bundle
from signbridge_common import open_camera
from vocabulary_utils import display_text, load_vocabulary, validate_vocabulary


def sample_hand(extended, thumb="folded", spread=False, direction=None):
    wrist = (0.5, 0.9, 0.0)
    points = [wrist for _ in range(21)]
    if spread:
        bases = [0.3, 0.43, 0.58, 0.73]
        tips = [0.16, 0.37, 0.64, 0.87]
    elif extended == [True, True, True, True]:
        bases = [0.46, 0.49, 0.53, 0.56]
        tips = [0.44, 0.49, 0.54, 0.59]
    else:
        bases = [0.38, 0.46, 0.54, 0.62]
        tips = bases
    mcp_ids = [5, 9, 13, 17]
    pip_ids = [6, 10, 14, 18]
    dip_ids = [7, 11, 15, 19]
    tip_ids = [8, 12, 16, 20]
    for index, (base, mcp, pip, dip, tip) in enumerate(zip(bases, mcp_ids, pip_ids, dip_ids, tip_ids)):
        points[mcp] = (base, 0.66 if index != 1 else 0.62, 0.0)
        if extended[index]:
            points[pip] = (base, 0.49, 0.0)
            points[dip] = (tips[index], 0.36, 0.0)
            points[tip] = (tips[index], 0.20, 0.0)
        else:
            points[pip] = (base, 0.50, 0.0)
            points[dip] = (base + 0.04, 0.63, 0.0)
            points[tip] = (base + 0.02, 0.72, 0.0)
    if direction == "point":
        base = bases[0]
        points[6] = (base + 0.12, 0.62, 0.0)
        points[7] = (base + 0.23, 0.59, 0.0)
        points[8] = (base + 0.34, 0.56, 0.0)
    if thumb == "extended":
        points[1] = (0.44, 0.84, 0.0)
        points[2] = (0.26, 0.73, 0.0)
        points[3] = (0.08, 0.63, 0.0)
        points[4] = (-0.12, 0.54, 0.0)
    elif thumb == "up":
        points[1] = (0.45, 0.70, 0.0)
        points[2] = (0.44, 0.52, 0.0)
        points[3] = (0.44, 0.30, 0.0)
        points[4] = (0.44, 0.08, 0.0)
    elif thumb == "down":
        points[1] = (0.45, 1.06, 0.0)
        points[2] = (0.44, 1.23, 0.0)
        points[3] = (0.44, 1.40, 0.0)
        points[4] = (0.44, 1.58, 0.0)
    else:
        points[1] = (0.46, 0.84, 0.0)
        points[2] = (0.44, 0.78, 0.0)
        points[3] = (0.45, 0.76, 0.0)
        points[4] = (0.48, 0.74, 0.0)
    return points


class VocabularyTests(unittest.TestCase):
    def test_full_vocabulary_schema(self):
        items = load_vocabulary()
        self.assertEqual(len(items), 64)
        validate_vocabulary(items)
        self.assertEqual(len({item["id"] for item in items}), len(items))
        self.assertTrue(all("audioText" in item and "romanUrdu" in item for item in items))

    def test_urdu_and_roman_fallback(self):
        item = next(value for value in load_vocabulary() if value["id"] == "thank_you")
        self.assertEqual(display_text(item, "ur"), item["urdu"])
        self.assertEqual(display_text(item, "ur", roman_urdu=True), "Shukriya")


class FeatureTests(unittest.TestCase):
    def test_normalization_has_63_finite_values_and_wrist_at_origin(self):
        points = [{"x": 0.2 + i * 0.01, "y": 0.3 + i * 0.02, "z": i * 0.001} for i in range(21)]
        values = normalize_landmarks(points)
        self.assertEqual(len(values), 63)
        self.assertEqual(values[:3], [0.0, 0.0, 0.0])
        self.assertTrue(all(math.isfinite(value) for value in values))
        self.assertEqual(len(normalize_landmarks(points, "Left")), 63)

    def test_feature_vector_rejects_bad_size_and_infinity(self):
        with self.assertRaises(ValueError):
            feature_vector([0.0] * 62)
        with self.assertRaises(ValueError):
            feature_vector([float("inf")] + [0.0] * 62)


class GestureRuleTests(unittest.TestCase):
    def test_invalid_landmark_count_is_uncertain(self):
        self.assertIsNone(classify_gesture([(0, 0, 0)] * 20))

    def test_closed_fist(self):
        self.assertEqual(classify_gesture(sample_hand([False] * 4)), "CLOSED_FIST")

    def test_index_victory_three_and_four_fingers(self):
        self.assertEqual(classify_gesture(sample_hand([True, False, False, False])), "INDEX_UP")
        self.assertEqual(classify_gesture(sample_hand([True, True, False, False])), "VICTORY")
        self.assertEqual(classify_gesture(sample_hand([True, True, True, False])), "THREE_FINGERS")
        self.assertEqual(classify_gesture(sample_hand([True] * 4, spread=True)), "FOUR_FINGERS")

    def test_open_stop_and_five_finger_poses(self):
        self.assertEqual(classify_gesture(sample_hand([True] * 4, thumb="extended", spread=True)), "OPEN_PALM")
        self.assertEqual(classify_gesture(sample_hand([True] * 4)), "STOP_PALM")
        self.assertEqual(classify_gesture(sample_hand([True] * 4, thumb="extended")), "FIVE_FINGERS")

    def test_thumb_directions_and_horizontal_point(self):
        self.assertEqual(classify_gesture(sample_hand([False] * 4, thumb="up")), "THUMBS_UP")
        self.assertEqual(classify_gesture(sample_hand([False] * 4, thumb="down")), "THUMBS_DOWN")
        self.assertEqual(classify_gesture(sample_hand([True, False, False, False], direction="point")), "POINT")

    def test_ok_circle_and_call_me_pose(self):
        ok_hand = sample_hand([False, True, True, False])
        self.assertEqual(classify_gesture(ok_hand), "OK")
        call_hand = sample_hand([False, False, False, True], thumb="extended")
        self.assertEqual(classify_gesture(call_hand), "CALL_ME")


class CsvTests(unittest.TestCase):
    def test_valid_rows_load_and_malformed_rows_are_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sign_data.csv"
            good = ["hello", "anonymous", "session", "2026-01-01T00:00:00Z", "2", "640", "480", "Right"] + ["0.0"] * 63
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(CSV_HEADER)
                writer.writerow(good)
                writer.writerow(["bad", "row"])
            self.assertEqual(len(load_rows(path)), 1)

    def test_schema_mismatch_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            path.write_text("wrong,header\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_rows(path)


class FallbackTests(unittest.TestCase):
    def test_missing_or_broken_model_returns_demo_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.joblib"
            self.assertIsNone(load_model_bundle(missing))
            broken = Path(directory) / "broken.joblib"
            broken.write_bytes(b"not a model")
            self.assertIsNone(load_model_bundle(broken))

    def test_missing_camera_has_actionable_message(self):
        class FakeCamera:
            def isOpened(self): return False
            def release(self): self.released = True
        class FakeCv2:
            CAP_DSHOW = 700
            CAP_ANY = 0
            def VideoCapture(self, index, backend): return FakeCamera()
        with patch("signbridge_common.cv2", FakeCv2()):
            with self.assertRaisesRegex(RuntimeError, "--camera 1"):
                open_camera(0)


if __name__ == "__main__":
    unittest.main()
