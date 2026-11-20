"""PSL hands view, training changes and the SignSpeak converter (master-v3 Stage 2). numpy only;
the TensorFlow side is checked by tools/psl_train/smoke.py on GitHub Actions."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np

from ml_engine import psl_hands
from tools.psl_data import signspeak
from tools.psl_train import augment as aug

ROOT = Path(__file__).resolve().parents[1]


def rigid_hand() -> np.ndarray:
    """A hand-like rigid set of 21 points (image heights), wrist at the origin."""
    angles = np.linspace(-0.6, 0.6, 5)
    points = [np.zeros(3)]
    for a in angles:
        for k in range(1, 5):
            points.append(np.array([np.sin(a) * 0.03 * k, -np.cos(a) * 0.03 * k, 0.002 * k]))
    return np.array(points)


def turning_sequence(aspect: float, frames: int = 40, seed: int = 0) -> np.ndarray:
    """The rigid hand turning in 3D, as MediaPipe would report it for a camera of width/height `aspect`."""
    rng = np.random.default_rng(seed)
    hand = rigid_hand()
    out = np.full((frames, 2, 21, 3), np.nan)
    for t in range(frames):
        a, b, c = rng.uniform(-0.8, 0.8, 3)
        rx = np.array([[1, 0, 0], [0, np.cos(a), -np.sin(a)], [0, np.sin(a), np.cos(a)]])
        ry = np.array([[np.cos(b), 0, np.sin(b)], [0, 1, 0], [-np.sin(b), 0, np.cos(b)]])
        rz = np.array([[np.cos(c), -np.sin(c), 0], [np.sin(c), np.cos(c), 0], [0, 0, 1]])
        p = hand @ (rx @ ry @ rz).T + np.array([0.1, 0.0, 0.0])  # image heights from the image centre
        out[t, 1, :, 0] = (p[:, 0] + 0.5 * aspect) / aspect  # image widths
        out[t, 1, :, 1] = p[:, 1] + 0.5
        out[t, 1, :, 2] = (p[:, 2] - p[0, 2]) / aspect
    return out


class HandsViewTests(unittest.TestCase):
    def test_resample_matches_the_baseline_rule(self):
        spec = json.loads((ROOT / "shared_data" / "asl_islr_spec.json").read_text(encoding="utf-8"))
        self.assertIn("floor((2*i*(L-1) + (T-1)) / (2*(T-1)))", spec["fixed_length"]["rule"])
        for length in (1, 5, 32, 60, 191):
            expected = [((2 * i * (length - 1) + 31) // 62) for i in range(32)]
            self.assertEqual(psl_hands.resample_indices(length).tolist(), expected)

    def test_trim_keeps_two_frames_of_margin(self):
        hands = np.full((20, 2, 21, 3), np.nan)
        hands[6:11, 1] = 0.5
        self.assertEqual(psl_hands.trim_window(hands), (4, 13))
        self.assertIsNone(psl_hands.trim_window(np.full((5, 2, 21, 3), np.nan)))

    def test_features_size_masks_and_missing_hands(self):
        hands = turning_sequence(4 / 3)[:32]
        hands[:, 0] = psl_hands.mirror(hands)[:, 0]
        hands[3:5, 0] = np.nan
        f = psl_hands.features(hands)
        self.assertEqual(f.shape, (32, psl_hands.FEATURES_PER_FRAME))
        self.assertEqual(f.dtype, np.float32)
        self.assertTrue(np.isfinite(f).all())
        np.testing.assert_array_equal(f[3, -2:], [0.0, 1.0])
        np.testing.assert_array_equal(f[3, :63], 0.0)  # missing left hand: no shape
        np.testing.assert_array_equal(f[3, 136:172], 0.0)  # no hand-to-hand distances
        np.testing.assert_array_equal(f[5, 130:132], 0.0)  # no motion right after the hand comes back
        np.testing.assert_array_equal(f[6, -2:], [1.0, 1.0])
        shape = f[6, 63:126].reshape(21, 3)
        self.assertAlmostEqual(float(np.sqrt((shape[:, :2] ** 2).sum(1)).max()), 1.0, places=5)

    def test_hand_shape_is_features_v2s_hand_shape(self):
        hands = turning_sequence(4 / 3)[:32]
        f = psl_hands.features(hands)
        p = np.nan_to_num(hands[7, 1]) * np.array([4 / 3, 1, 4 / 3])
        rel = p - p[0]
        expected = rel / np.sqrt((rel[:, :2] ** 2).sum(1)).max()
        np.testing.assert_allclose(f[7, 63:126], expected.reshape(-1), atol=1e-6)

    def test_shape_does_not_change_when_the_picture_moves_or_grows(self):
        hands = turning_sequence(4 / 3)[:32]
        moved = hands.copy()
        moved[..., 0] = (moved[..., 0] - 0.5) * 1.2 + 0.5
        moved[..., 1] = (moved[..., 1] - 0.5) * 1.2 + 0.5
        moved[..., 2] *= 1.2
        a, b = psl_hands.features(hands), psl_hands.features(moved)
        np.testing.assert_allclose(a[:, :126], b[:, :126], atol=1e-5)  # shapes
        np.testing.assert_allclose(a[:, 126:130], b[:, 126:130], atol=1e-5)  # positions in hand sizes

    def test_mirror_twice_is_the_same_and_islr_round_trip(self):
        hands = turning_sequence(4 / 3)[:32]
        np.testing.assert_allclose(psl_hands.mirror(psl_hands.mirror(hands)), hands, equal_nan=True)
        m = psl_hands.mirror(hands)
        self.assertTrue(np.isnan(m[:, 1]).all() and not np.isnan(m[:, 0]).any())
        frames = psl_hands.to_islr(hands)
        self.assertEqual(frames.shape, (32, 543, 3))
        self.assertTrue(np.isnan(frames[:, :468]).all() and np.isnan(frames[:, 489:522]).all())
        np.testing.assert_allclose(psl_hands.from_islr(frames), hands, atol=1e-6, equal_nan=True)

    def test_aspect_correction(self):
        hands = turning_sequence(16 / 9)
        fixed = psl_hands.adjust_aspect(hands, 16 / 9)
        back = turning_sequence(4 / 3)
        np.testing.assert_allclose(fixed[:, 1, :, 0], back[:, 1, :, 0], atol=1e-9)
        np.testing.assert_allclose(fixed[:, 1, :, 2], back[:, 1, :, 2], atol=1e-9)


class AugmentTests(unittest.TestCase):
    def setUp(self):
        hands = np.stack([turning_sequence(4 / 3, 60, s) for s in range(6)]).astype(np.float32)
        hands[:, :5] = np.nan
        hands[:, 50:] = np.nan
        self.hands = hands
        self.lengths = np.full(6, 60)
        self.spans = aug.windows(hands, self.lengths)

    def test_windows_and_fixed(self):
        np.testing.assert_array_equal(self.spans, [[3, 52]] * 6)
        fixed = aug.fixed(self.hands, self.spans)
        self.assertEqual(fixed.shape, (6, 32, 2, 21, 3))
        np.testing.assert_array_equal(fixed[0], self.hands[0, 3:52][psl_hands.resample_indices(49)])

    def test_augment_keeps_missing_hands_missing_and_is_repeatable(self):
        a = aug.augment(self.hands, self.spans, np.random.default_rng(1))
        b = aug.augment(self.hands, self.spans, np.random.default_rng(1))
        np.testing.assert_array_equal(np.isnan(a), np.isnan(b))
        np.testing.assert_allclose(a, b, equal_nan=True)
        self.assertEqual(a.shape, (6, 32, 2, 21, 3))
        hand_lost = np.isnan(a[..., 0, 0]).all(axis=1)
        self.assertTrue(hand_lost.any(axis=1).all())  # each sample keeps one hand missing throughout (one-handed sign)
        self.assertFalse(hand_lost.all(axis=1).any())
        index = aug.random_frames(self.spans, np.random.default_rng(2), aug.Settings())
        self.assertTrue((np.diff(index, axis=1) >= 0).all())
        self.assertTrue((index >= 3).all() and (index < 52).all())

    def test_mixup_and_balanced_order(self):
        x = np.random.default_rng(0).normal(size=(10, 32, 174)).astype(np.float32)
        y = np.eye(5, dtype=np.float32)[np.arange(10) % 5]
        x2, y2 = aug.mixup(x, y, np.random.default_rng(0))
        np.testing.assert_allclose(y2.sum(1), 1.0, atol=1e-6)
        self.assertTrue((y2.max(1) >= 0.5 - 1e-6).all())
        labels = np.array([0] * 90 + [1] * 10)
        order = aug.balanced_order(labels, np.random.default_rng(0))
        self.assertGreater((labels[order] == 1).mean(), 0.2)


class SignSpeakConverterTests(unittest.TestCase):
    def test_estimates_the_camera_shape_from_a_rigid_palm(self):
        for aspect in (4 / 3, 16 / 9):
            samples = [turning_sequence(aspect, 40, s) for s in range(12)]
            result = signspeak.estimate_aspect(samples)
            self.assertAlmostEqual(result["estimate"], aspect, delta=0.03)
            self.assertAlmostEqual(result["nearest_common"], round(aspect, 4))

    def test_converts_an_archive_and_drops_test_folders_duplicates_and_partial_samples(self):
        rng = np.random.default_rng(0)

        def frames(n, two=False):
            raw = np.zeros((n, 126))
            raw[:, 63:] = rng.uniform(0.3, 0.7, (n, 63))
            if two:
                raw[:, :63] = rng.uniform(0.6, 0.9, (n, 63))
                raw[:, 63:][:, 0::3] = rng.uniform(0.2, 0.4, (n, 21))
            return raw

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            path = tmp / "a.zip"
            same = frames(60)
            with zipfile.ZipFile(path, "w") as z:
                def put(folder, word, sample, raw):
                    for i, row in enumerate(raw):
                        buf = io.BytesIO()
                        np.save(buf, row)
                        z.writestr(f"{folder}/{word}/{sample}/{i}.npy", buf.getvalue())
                put("MP_Data", "mine", "0", frames(60))
                put("MP_Data", "mine", "1", same)
                put("MP_Data", "mine", "2", same)  # exact duplicate
                put("MP_Data", "mine", "3", frames(10))  # partial
                put("MP_Data", "both", "0", frames(60, two=True))
                put("MP_Data_mobile", "mine", "0", frames(60))
                put("MP_Data", "test_word", "0", frames(60))
                put("MP_Data", "nothing", "0", frames(60))
            summary = signspeak.convert([path], tmp / "out")
            data = np.load(tmp / "out" / "signspeak.npz")
            self.assertEqual(summary["samples_kept"], 5)
            self.assertEqual(summary["counts"]["exact_duplicates_dropped"], 1)
            self.assertEqual(summary["counts"]["partial_samples_dropped"], 1)
            self.assertEqual(summary["folders_dropped_as_not_words"], {"test_word": 1})
            self.assertEqual(sorted(data["word"].tolist()), ["_unknown", "both", "mine", "mine", "mine"])
            self.assertEqual(sorted(set(data["device"].tolist())), ["phone", "webcam"])
            self.assertEqual(data["hands"].shape, (5, 60, 2, 21, 3))
            mine = data["hands"][data["word"] == "mine"]
            self.assertTrue(np.isnan(mine[:, :, 0]).all() and not np.isnan(mine[:, :, 1]).any())
            self.assertIn("unmirrored", summary["hand_order"]["decision"])
            self.assertEqual(signspeak.gloss_id("assalam-o-alaikum"), "assalam_o_alaikum")


class GlossTests(unittest.TestCase):
    def test_every_gloss_has_english_and_no_sign_description(self):
        doc = json.loads((ROOT / "shared_data" / "psl_glosses.json").read_text(encoding="utf-8"))
        vocab = {v["id"]: v for v in json.loads((ROOT / "shared_data" / "vocabulary.json").read_text(encoding="utf-8"))}
        for gloss, entry in doc["glosses"].items():
            self.assertTrue(entry["english"])
            self.assertNotIn("handSignHint", entry)
            self.assertNotIn("description", entry)
            if "vocabulary_id" in entry:
                self.assertEqual(entry["urdu"], vocab[entry["vocabulary_id"]]["urdu"])
            if "dictionary_url" in entry:
                self.assertTrue(entry["dictionary_url"].startswith("https://psl.org.pk/dictionary/"), gloss)


if __name__ == "__main__":
    unittest.main()


class GoldenInputTests(unittest.TestCase):
    def test_golden_cases_match_the_reference(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("psl_golden", ROOT / "tools" / "psl_golden.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        stored = json.loads((ROOT / "tests" / "golden" / "psl_hands_cases.json").read_text(encoding="utf-8"))
        self.assertEqual(stored, json.loads(json.dumps(module.build())), "rerun python tools/psl_golden.py")
