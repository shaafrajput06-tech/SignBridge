"""ASL mode (fast track Stage 2): spec, 543-point adapter, resampling, segmenter, scores, recogniser checks,
and Python/JavaScript parity."""

from __future__ import annotations

import gzip
import json
import math
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data_engine.ledger import load_ledger  # noqa: E402
from ml_engine import asl_islr  # noqa: E402
from ml_engine.asl_islr import (  # noqa: E402
    PART, ROWS, SPEC, AslModelError, AslRecognizer, SignSegmenter, confidence_band, describe_sign, hand_counts, hands_present,
    islr_frame, load_classes, probabilities, resample, resample_indices, sha256_file, top_k,
)
from ml_engine.features_v2 import canonicalize_frame  # noqa: E402

FIXTURE = json.loads(gzip.decompress((ROOT / "tests" / "golden" / "v2_holistic.json.gz").read_bytes()))
CASES = json.loads((ROOT / "tests" / "golden" / "asl_islr_cases.json").read_text(encoding="utf-8"))
DUMP_SCRIPT = ROOT / "web" / "tests" / "tools" / "dump-asl.mjs"
DOWNLOADS = json.loads((ROOT / "shared_data" / "downloads.json").read_text(encoding="utf-8"))


def synthetic_raw(seed: int, hands: int = 2, pose: bool = True, face: int = 478, width: int = 640, height: int = 480) -> dict:
    rng = random.Random(seed)

    def points(n, cx, cy, spread=0.05):
        return [[cx + rng.uniform(-spread, spread), cy + rng.uniform(-spread, spread), rng.uniform(-0.1, 0.1)] for _ in range(n)]

    raw = {"timestamp_ms": 1000 + seed, "image_width": width, "image_height": height, "input_mirrored": False, "hands": [], "pose": None, "face": None}
    # Unmirrored view: the signer's right side is on the image's left.
    right_wrist, left_wrist = (0.30, 0.70), (0.70, 0.70)
    if pose:
        body = points(33, 0.5, 0.6, 0.2)
        body = [p + [1.0] for p in body]
        body[16][:2] = list(right_wrist)
        body[15][:2] = list(left_wrist)
        raw["pose"] = body
    if face:
        raw["face"] = points(face, 0.5, 0.3, 0.06)
    hand_list = []
    if hands >= 1:
        h = points(21, *right_wrist, 0.04)
        h[0][:2] = list(right_wrist)
        hand_list.append({"landmarks": h, "handedness": "Left"})  # MediaPipe labels assume a mirrored image
    if hands >= 2:
        h = points(21, *left_wrist, 0.04)
        h[0][:2] = list(left_wrist)
        hand_list.append({"landmarks": h, "handedness": "Right"})
    rng.shuffle(hand_list)
    raw["hands"] = hand_list
    return raw


def as_null(frame):
    return [[None if math.isnan(v) else v for v in point] for point in frame]


class SpecTests(unittest.TestCase):
    def test_layout_covers_543_rows_in_competition_order(self):
        parts = SPEC["layout"]["parts"]
        self.assertEqual([p["name"] for p in parts], ["face", "left_hand", "pose", "right_hand"])
        start = 0
        for part in parts:
            self.assertEqual(part["start"], start)
            start += part["count"]
        self.assertEqual(start, ROWS)
        self.assertEqual(ROWS, 543)

    def test_class_map_matches_its_pinned_hash_and_has_250_labels(self):
        path = ROOT / SPEC["classes"]["file"]
        self.assertEqual(sha256_file(path), SPEC["classes"]["sha256"])
        labels = load_classes()
        self.assertEqual(len(labels), 250)
        self.assertEqual(labels[0], "TV")
        self.assertEqual(labels[113], "hello")
        self.assertEqual(labels[249], "zipper")

    def test_download_list_spec_and_ledger_agree_on_every_hash(self):
        ledger = {entry["id"]: entry for entry in load_ledger()["assets"]}
        for item in DOWNLOADS["files"]:
            with self.subTest(path=item["path"]):
                pinned = {f["path"]: f.get("sha256") for f in ledger[item["asset_id"]]["files"]}
                self.assertEqual(pinned.get(item["path"]), item["sha256"])
                self.assertTrue(item["url"].startswith("https://"))
        by_path = {item["path"]: item for item in DOWNLOADS["files"]}
        self.assertEqual(by_path[SPEC["model"]["file"]]["sha256"], SPEC["model"]["sha256"])
        self.assertEqual(by_path[SPEC["model"]["file"]]["bytes"], SPEC["model"]["bytes"])
        self.assertEqual(by_path[SPEC["classes"]["file"]]["sha256"], SPEC["classes"]["sha256"])

    def test_unsupported_feature_version_is_refused(self):
        bad = dict(SPEC, feature_version="asl-islr-999")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "spec.json"
            path.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(AslModelError):
                asl_islr.load_spec(path)


class FrameTests(unittest.TestCase):
    def test_parts_land_in_their_rows_and_missing_parts_stay_nan(self):
        raw = synthetic_raw(1)
        frame = islr_frame(raw)
        self.assertEqual(len(frame), 543)
        face_start, _ = PART["face"]
        pose_start, _ = PART["pose"]
        self.assertEqual(frame[face_start + 467], raw["face"][467])
        self.assertEqual(frame[pose_start + 32], raw["pose"][32][:3])
        no_parts = islr_frame(synthetic_raw(2, hands=0, pose=False, face=0))
        self.assertTrue(all(math.isnan(v) for point in no_parts for v in point))

    def test_iris_points_are_dropped_and_a_468_point_face_also_works(self):
        for count in (468, 478):
            raw = synthetic_raw(3, face=count)
            frame = islr_frame(raw)
            self.assertEqual(frame[467], raw["face"][467])
            self.assertFalse(math.isnan(frame[467][0]))

    def test_hands_go_to_anatomical_slots_by_pose_wrists_whatever_the_order_or_label(self):
        for seed in range(10):
            raw = synthetic_raw(seed)
            frame = islr_frame(raw)
            canonical = canonicalize_frame(raw)
            left_start, _ = PART["left_hand"]
            right_start, _ = PART["right_hand"]
            self.assertEqual(frame[left_start], canonical["left_hand"][0])
            self.assertEqual(frame[right_start], canonical["right_hand"][0])
            # The signer's right hand is the one at the image's left (x = 0.30) in an unmirrored view.
            self.assertAlmostEqual(frame[right_start][0], 0.30)
            self.assertAlmostEqual(frame[left_start][0], 0.70)
            self.assertEqual(hand_counts(frame), (True, True))

    def test_one_hand_frames(self):
        frame = islr_frame(synthetic_raw(4, hands=1))
        self.assertEqual(hand_counts(frame), (False, True))
        self.assertTrue(hands_present(frame))

    def test_mirrored_input_is_refused(self):
        raw = synthetic_raw(5)
        raw["input_mirrored"] = True
        with self.assertRaises(ValueError):
            islr_frame(raw)

    def test_layout_matches_the_competition_reference_reshape(self):
        """The competition's starter code reads a parquet file whose rows go face, left_hand, pose,
        right_hand for every frame, and reshapes them to frames x 543 x 3. Build that long table from
        the same raw parts and check the reshape equals our frames."""
        import numpy as np

        raws = [synthetic_raw(seed, hands=seed % 3, pose=seed % 2 == 0, face=(0, 468, 478)[seed % 3]) for seed in range(9)]
        long_rows = []
        for raw in raws:
            canonical = canonicalize_frame(raw)
            groups = [("face", (raw["face"] or [None] * 468)[:468] if raw["face"] else [None] * 468),
                      ("left_hand", canonical["left_hand"] or [None] * 21),
                      ("pose", [p[:3] for p in raw["pose"]] if raw["pose"] else [None] * 33),
                      ("right_hand", canonical["right_hand"] or [None] * 21)]
            for _type, points in groups:
                for point in points:
                    long_rows.append([math.nan] * 3 if point is None else list(point[:3]))
        reference = np.asarray(long_rows, dtype=np.float32).reshape(len(raws), 543, 3)  # load_relevant_data_subset
        ours = np.asarray([islr_frame(raw) for raw in raws], dtype=np.float32)
        self.assertTrue(np.array_equal(np.isnan(reference), np.isnan(ours)))
        self.assertTrue(np.array_equal(np.nan_to_num(reference), np.nan_to_num(ours)))


class ResampleTests(unittest.TestCase):
    def test_known_values(self):
        self.assertEqual(resample_indices(10, 4), [0, 3, 6, 9])
        self.assertEqual(resample_indices(5, 9), [0, 1, 1, 2, 2, 3, 3, 4, 4])
        self.assertEqual(resample_indices(1, 3), [0, 0, 0])
        self.assertEqual(resample_indices(7, 1), [0])

    def test_first_and_last_frames_are_kept_order_is_kept_and_same_length_is_identity(self):
        for length in range(1, 120):
            for count in (2, 16, 32, 64):
                indices = resample_indices(length, count)
                self.assertEqual(len(indices), count)
                self.assertEqual(indices[0], 0)
                self.assertEqual(indices[-1], length - 1)
                self.assertEqual(indices, sorted(indices))
            self.assertEqual(resample_indices(length, length), list(range(length)))
        self.assertEqual(resample(list("abcdefghij"), 4), list("adgj"))

    def test_bad_sizes_are_rejected(self):
        for args in ((0, 3), (3, 0)):
            with self.assertRaises(ValueError):
                resample_indices(*args)


class SegmenterTests(unittest.TestCase):
    def run_stream(self, stream):
        segmenter = SignSegmenter()
        out = []
        for index, present in enumerate(stream):
            sign = segmenter.push(index, bool(present))
            if sign:
                out.append(sign)
        rest = segmenter.flush()
        if rest:
            out.append(rest)
        return out

    def test_one_clean_sign_keeps_two_frames_of_margin(self):
        self.assertEqual(self.run_stream([0] * 5 + [1] * 12 + [0] * 12), [list(range(3, 19))])

    def test_short_flicker_is_dropped_and_short_gap_does_not_split(self):
        self.assertEqual(self.run_stream([0] * 3 + [1] * 4 + [0] * 12), [])
        self.assertEqual(self.run_stream([1] * 10 + [0] * 3 + [1] * 10 + [0] * 10), [list(range(0, 25))])

    def test_two_signs_and_a_cut_at_max_frames(self):
        two = self.run_stream([0] * 2 + [1] * 10 + [0] * 9 + [1] * 8 + [0] * 9)
        self.assertEqual(two, [list(range(0, 14)), list(range(19, 31))])
        long = self.run_stream([1] * 200 + [0] * 9)
        self.assertEqual(len(long[0]), SPEC["segmentation"]["max_frames"])

    def test_flush_returns_an_open_sign(self):
        self.assertEqual(self.run_stream([0] * 4 + [1] * 9 + [0] * 3), [list(range(2, 15))])

    def test_describe_sign_counts_one_and_two_hand_frames(self):
        frames = [islr_frame(synthetic_raw(s, hands=s % 3)) for s in range(9)]
        self.assertEqual(describe_sign(frames), {"frames": 9, "two_hand_frames": 3, "one_hand_frames": 3})


class ScoreTests(unittest.TestCase):
    def test_logits_become_probabilities_and_probabilities_stay(self):
        logits = CASES["scores"][0]
        probs = probabilities(logits)
        self.assertAlmostEqual(sum(probs), 1.0, places=9)
        self.assertEqual(probabilities(CASES["scores"][1]), CASES["scores"][1])

    def test_top_k_orders_by_probability_then_index_and_names_labels(self):
        labels = load_classes()
        top = top_k(CASES["scores"][2], labels, 3)
        self.assertEqual(top[0]["label"], "hello")
        self.assertGreater(top[0]["probability"], 0.9)
        tie = top_k(CASES["scores"][4], labels, 2)
        self.assertEqual([t["label"] for t in tie], [labels[3], labels[7]])
        self.assertEqual(top_k([0.0] * 249 + [5.0], labels, 1)[0]["display"], "zipper")
        thank = labels.index("thankyou")
        scores = [0.0] * 250
        scores[thank] = 9.0
        self.assertEqual(top_k(scores, labels, 1)[0]["display"], "thank you")

    def test_confidence_bands(self):
        self.assertEqual(confidence_band(0.95), "sure")
        self.assertEqual(confidence_band(SPEC["confidence"]["sure"]), "sure")
        self.assertEqual(confidence_band(0.4), "unsure")
        self.assertEqual(confidence_band(0.1), "none")


class RecognizerGuardTests(unittest.TestCase):
    def test_missing_model_file_says_how_to_fetch_it(self):
        with self.assertRaises(AslModelError) as caught:
            AslRecognizer(model_path=ROOT / "models" / "asl" / "not-there.tflite")
        self.assertIn("fetch_assets", str(caught.exception))

    def test_wrong_hash_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            fake = Path(folder) / "model.tflite"
            fake.write_bytes(b"TFL3 not the real model")
            with self.assertRaises(AslModelError) as caught:
                AslRecognizer(model_path=fake)
            self.assertIn("SHA-256", str(caught.exception))

    def test_ledger_refusal_stops_the_recogniser(self):
        from data_engine.ledger import LicenceError

        with patch("data_engine.ledger.assert_allowed", side_effect=LicenceError("blocked for the test")):
            with self.assertRaises(AslModelError) as caught:
                AslRecognizer()
        self.assertIn("blocked for the test", str(caught.exception))

    def test_without_a_runtime_the_error_names_the_install_command(self):
        try:
            asl_islr._interpreter_class()
            self.skipTest("a TFLite runtime is installed here")
        except AslModelError as error:
            self.assertIn("pip install -r requirements.txt", str(error))


class RealModelTests(unittest.TestCase):
    """Runs where tools/fetch_assets.py has downloaded the model and a TFLite runtime is installed."""

    def setUp(self):
        if not (ROOT / SPEC["model"]["file"]).exists():
            self.skipTest("models/asl/model.tflite not downloaded (python tools/fetch_assets.py)")
        try:
            asl_islr._interpreter_class()
        except AslModelError:
            self.skipTest("no TFLite runtime installed")

    def test_variable_lengths_give_250_probabilities_deterministically(self):
        recogniser = AslRecognizer()
        frames = [islr_frame(synthetic_raw(seed, hands=1 + seed % 2)) for seed in range(40)]
        for length in (1, 7, 32, 40):
            with self.subTest(length=length):
                scores = recogniser.scores(frames[:length])
                self.assertEqual(len(scores), 250)
                self.assertTrue(all(math.isfinite(v) for v in scores))
                self.assertAlmostEqual(sum(probabilities(scores)), 1.0, places=5)
        self.assertEqual(recogniser.scores(frames[:20]), recogniser.scores(frames[:20]))


class JavaScriptParityTests(unittest.TestCase):
    def test_javascript_matches_python(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is not installed")
        completed = subprocess.run([node, str(DUMP_SCRIPT)], cwd=ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        js = json.loads(completed.stdout)
        compared = 0
        for case, actual in zip(FIXTURE["canonicalize_cases"], js["frames"], strict=True):
            if case["raw"].get("input_mirrored"):
                self.assertIn("unmirrored", actual.get("error", ""), case["id"])
                continue
            self.assertEqual(actual["frame"], as_null(islr_frame(case["raw"])), case["id"])
            compared += 1
        self.assertGreaterEqual(compared, 20)
        self.assertEqual(js["resampling"], [resample_indices(n, t) for n, t in CASES["resample"]])
        expected_segments = [SegmenterTests().run_stream(stream) for stream in CASES["segmenter_streams"]]
        self.assertEqual(js["segments"], expected_segments)
        labels = load_classes()
        for vector, actual in zip(CASES["scores"], js["scores"], strict=True):
            probs = probabilities(vector)
            self.assertLessEqual(max(abs(a - b) for a, b in zip(actual["probabilities"], probs)), 1e-12)
            expected_top = top_k(vector, labels, 5)
            self.assertEqual([t["label"] for t in actual["top"]], [t["label"] for t in expected_top])
            self.assertEqual(actual["band"], confidence_band(max(probs)))
        print(f"\n  ASL parity: {compared} frames, {len(CASES['resample'])} resampling cases, {len(CASES['segmenter_streams'])} streams identical", file=sys.stderr)


if __name__ == "__main__":
    unittest.main()
