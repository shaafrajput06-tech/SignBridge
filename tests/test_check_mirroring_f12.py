"""The F12 mirroring check tool (Phase 1). The real check needs recorded clips ([HUMAN]); these tests
prove the tool detects agreement and disagreement, using stand-in landmarkers with known behaviour."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tools"), str(ROOT / "tests")]

import check_mirroring_f12 as f12  # noqa: E402
from ml_engine.features_v2 import SPEC  # noqa: E402
from test_capture_v2 import MarkerBackend, MarkerScene  # noqa: E402

SENTINEL = 4000


class MirrorBehaviourBackend(MarkerBackend):
    """Reports one hand, and on a flipped image behaves like the rule in the feature spec assumes
    MediaPipe does: pose/face left-right labels follow the mirrored image and handedness labels flip.
    With swap_pose_on_flip=False it imitates a landmarker that the canonical rule would get wrong."""

    def __init__(self, scene, only, swap_pose_on_flip=True):
        super().__init__(scene)
        self.only = only
        self.swap_pose_on_flip = swap_pose_on_flip

    def detect(self, rgb, timestamp_ms):
        out = super().detect(rgb, timestamp_ms)
        ids = rgb[:, :, 0].astype(int) + 256 * rgb[:, :, 1].astype(int)
        flipped = ids[0, -1] == SENTINEL
        hand = next(h for h, side in zip(out["hands"], ("left", "right")) if side == self.only)
        if flipped:
            hand = {**hand, "handedness": "Left" if hand["handedness"] == "Right" else "Right"}
            if self.swap_pose_on_flip:
                for a, b in SPEC["mirror_pairs"]["pose"]:
                    out["pose"][a], out["pose"][b] = out["pose"][b], out["pose"][a]
                for a, b in SPEC["mirror_pairs"]["face"]:
                    out["face"][a], out["face"][b] = out["face"][b], out["face"][a]
        out["hands"] = [hand]
        return out


class WrongLabelBackend(MirrorBehaviourBackend):
    """Gives the opposite handedness label to the one MediaPipe's documented convention predicts."""

    def detect(self, rgb, timestamp_ms):
        out = super().detect(rgb, timestamp_ms)
        for hand in out["hands"]:
            hand["handedness"] = "Left" if hand["handedness"] == "Right" else "Right"
        return out


def clip(scene, count=30):
    image = scene.image()
    image[0, 0] = (SENTINEL % 256, SENTINEL // 256, 255)
    return [image] * count


class F12ToolTests(unittest.TestCase):
    def run_tool(self, swap=True, labels=("left", "right")):
        results = {}
        for seed, (hand, label) in enumerate(zip(("left", "right"), labels)):
            scene = MarkerScene(seed=seed + 20)
            results[f"{label}_{seed}.mp4"] = f12.check_clip(clip(scene), label, lambda s=scene, h=hand: MirrorBehaviourBackend(s, h, swap))
        return results, f12.summarise(results)

    def test_consistent_landmarker_passes(self):
        _, summary = self.run_tool()
        self.assertEqual(summary["verdict"], "PASS", summary)
        self.assertEqual(summary["measured"]["side_agreement"], 1.0)
        self.assertLess(summary["measured"]["hand_shape_diff_p95"], 1e-9)
        self.assertLess(summary["measured"]["pose_diff_median"], 1e-9)
        self.assertEqual(summary["measured"]["v1_label_consistency"], 1.0)
        self.assertEqual(summary["measured"]["label_truth"], 1.0)

    def test_wrong_pose_swap_assumption_is_caught(self):
        _, summary = self.run_tool(swap=False)
        self.assertEqual(summary["verdict"], "FAIL")
        self.assertFalse(summary["checks"]["pose_swap_rule"])

    def test_mislabelled_clips_fail_truth_match(self):
        _, summary = self.run_tool(labels=("right", "left"))
        self.assertFalse(summary["checks"]["truth_match"])

    def test_wrong_handedness_labels_fail_the_label_rule(self):
        results = {}
        for seed, hand in enumerate(("left", "right")):
            scene = MarkerScene(seed=seed + 30)
            backend = lambda s=scene, h=hand: WrongLabelBackend(s, h)
            results[f"{hand}.mp4"] = f12.check_clip(clip(scene), hand, backend)
        summary = f12.summarise(results)
        self.assertEqual(summary["measured"]["label_truth"], 0.0)
        self.assertFalse(summary["checks"]["label_rule"])
        self.assertTrue(summary["checks"]["truth_match"], "pose-based assignment still finds the right hand")

    def test_clips_inside_the_repository_are_refused(self):
        self.assertEqual(f12.main(["--clips", str(ROOT / "tests")]), 1)

    def test_too_few_frames_is_reported_as_insufficient(self):
        scene = MarkerScene(seed=3)
        results = {"left_a.mp4": f12.check_clip(clip(scene, 5), "left", lambda: MirrorBehaviourBackend(scene, "left"))}
        self.assertEqual(f12.summarise(results)["verdict"], "INSUFFICIENT DATA")

    def test_reports_and_clip_discovery(self):
        results, summary = self.run_tool()
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            json_path, md_path = f12.write_reports(summary, results, base / "reports")
            self.assertIn("PASS", md_path.read_text(encoding="utf-8"))
            report = json_path.read_text(encoding="utf-8")
            self.assertIn('"verdict": "PASS"', report)
            for clip_name in results:
                self.assertNotIn(clip_name, report + md_path.read_text(encoding="utf-8"), "clip file names must not reach the report")
            self.assertIn("clip_01", report)
            for name in ("left_1.mp4", "right_2.MOV", "notes.txt", "other_3.mp4"):
                (base / name).write_bytes(b"")
            self.assertEqual([(p.name, h) for p, h in f12.find_clips(base)], [("left_1.mp4", "left"), ("right_2.MOV", "right")])
            (base / "manifest.csv").write_text("file,signing_hand\nother_3.mp4,Right\n", encoding="utf-8")
            self.assertEqual([(p.name, h) for p, h in f12.find_clips(base)], [("other_3.mp4", "right")])


if __name__ == "__main__":
    unittest.main()
