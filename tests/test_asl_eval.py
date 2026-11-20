"""ASL evaluation notebook (fast track Stage 2): the core logic, the notebook being up to date, and a
dry run of every notebook cell with a stand-in model and stand-in landmark files."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]

import asl_eval_core as core  # noqa: E402
import build_asl_eval_notebook as builder  # noqa: E402
from ml_engine import asl_islr  # noqa: E402

NAN = float("nan")


def frame(left=False, right=False, right_wrist=(0.3, 0.6), nose=(0.5, 0.3)):
    f = np.full((543, 3), np.nan, dtype=np.float32)
    f[core.NOSE_ROW] = [nose[0], nose[1], 0]
    f[489:522] = 0.5
    f[core.POSE_RIGHT_WRIST] = [0.3, 0.6, 0]
    f[core.POSE_LEFT_WRIST] = [0.7, 0.6, 0]
    if left:
        f[468:489] = [0.7, 0.6, 0]
    if right:
        f[522:543] = [right_wrist[0], right_wrist[1], 0]
    return f


class CoreTests(unittest.TestCase):
    def test_resampling_matches_the_app(self):
        for length in (1, 2, 9, 33, 100):
            for count in (1, 16, 32, 64):
                self.assertEqual(core.resample_indices(length, count), asl_islr.resample_indices(length, count))

    def test_hand_facts(self):
        seq = np.stack([frame(right=True)] * 6 + [frame(left=True, right=True)] * 4 + [frame()] * 2)
        facts = core.hand_facts(seq)
        self.assertEqual((facts["right_frames"], facts["left_frames"], facts["both_frames"]), (10, 4, 4))
        self.assertFalse(facts["two_handed"])
        self.assertEqual(facts["dominant"], "right")
        both = np.stack([frame(left=True, right=True)] * 5 + [frame(left=True)] * 3)
        self.assertTrue(core.hand_facts(both)["two_handed"])
        self.assertEqual(core.hand_facts(both)["dominant"], "left")
        self.assertIsNone(core.hand_facts(np.stack([frame()]))["dominant"])

    def test_convention_facts(self):
        seq = np.stack([frame(right=True, right_wrist=(0.31, 0.6))] * 3 + [frame(right=True, right_wrist=(0.69, 0.6))])
        facts = core.convention_facts(seq)
        self.assertEqual(facts["right_slot_frames_with_pose"], 4)
        self.assertEqual(facts["right_slot_near_pose_right_wrist"], 3)
        self.assertEqual(facts["right_slot_left_of_nose"], 3)

    def test_type_order_check(self):
        good = ["face"] * 468 + ["left_hand"] * 21 + ["pose"] * 33 + ["right_hand"] * 21
        self.assertTrue(core.check_type_order(good * 2))
        self.assertFalse(core.check_type_order(good[:-1]))
        self.assertFalse(core.check_type_order(["pose"] * 33 + good[33:]))

    def test_evaluate_sample_runs_native_and_fixed_lengths(self):
        calls = []

        def predict(seq):
            calls.append(len(seq))
            scores = [0.0] * 250
            scores[7] = 5.0 if len(seq) != 16 else 0.0
            scores[9] = 1.0
            return scores

        seq = np.stack([frame(right=True)] * 20)
        record = core.evaluate_sample(seq, 7, predict, (16, 32), clock=iter([0.0, 0.002]).__next__)
        self.assertEqual(calls, [20, 16, 32])
        self.assertEqual(record["native_top5"][0], 7)
        self.assertAlmostEqual(record["native_ms"], 2.0)
        self.assertEqual(record["fixed"]["16"][0], 9)
        self.assertEqual(record["fixed"]["32"][0], 7)

    def test_summarise(self):
        def rec(sign, top, p, fixed=None, two=False, dom="right", who="a"):
            return {"sign": sign, "native_top5": top, "native_p": p, "native_ms": 10.0, "fixed": fixed or {},
                    "two_handed": two, "dominant": dom, "participant": who}

        records = [rec(1, [1, 2, 3, 4, 5], 0.95, {"32": [1, 0.9]}), rec(2, [3, 2, 1, 4, 5], 0.4, {"32": [2, 0.5]}, two=True),
                   rec(3, [3, 1, 2, 4, 5], 0.8, who="b", dom="left"), rec(4, [9, 8, 7, 6, 5], 0.2, two=True, who="b")]
        labels = [f"s{i}" for i in range(250)]
        out = core.summarise(records, labels)
        self.assertEqual(out["native"], {"top1": 0.5, "top5": 0.75})
        self.assertEqual(out["fixed_length"]["32"], {"samples": 2, "top1": 1.0, "native_top1_same_samples": 0.5})
        self.assertEqual(out["best_fixed_length"]["frames"], 32)
        self.assertEqual(out["best_fixed_length"]["loss_vs_native"], -0.5)
        self.assertEqual(out["groups"]["two_handed"]["top1"], 0.0)
        self.assertEqual(out["groups"]["one_handed"]["top1"], 1.0)
        self.assertEqual(out["groups"]["dominant_left"]["samples"], 1)
        self.assertEqual(out["per_signer"]["a"]["top1"], 0.5)
        by_t = {c["threshold"]: c for c in out["calibration"]}
        self.assertEqual(by_t[0.6]["coverage"], 0.5)
        self.assertEqual(by_t[0.6]["accuracy_when_covered"], 1.0)
        self.assertEqual(out["suggested_sure_threshold"], 0.5)
        self.assertEqual(out["latency_ms"]["median"], 10.0)

    def test_finding_inputs(self):
        with tempfile.TemporaryDirectory() as root:
            data = Path(root) / "rerun"
            data.mkdir()
            (data / "notes.csv").write_text("a,b\n1,2\n")
            (data / "rerun.csv").write_text("path,participant_id,sequence_id,sign\nx/1.parquet,7,1,hello\n")
            path, columns = core.find_label_csv(root)
            self.assertTrue(path.endswith("rerun.csv"))
            self.assertEqual(columns, {"path": "path", "sequence": "sequence_id", "sign": "sign", "participant": "participant_id"})
            self.assertIsNone(core.find_label_csv(root, exclude=[path]))
            blob = Path(root) / "m" / "model.tflite"
            blob.parent.mkdir()
            blob.write_bytes(b"abc")
            self.assertEqual(core.find_pinned_file(root, "model.tflite", hashlib.sha256(b"abc").hexdigest()), str(blob))
            self.assertIsNone(core.find_pinned_file(root, "model.tflite", "0" * 64))

    def test_finding_the_rerun_sets_layout(self):
        # The real rerun set (seen on Kaggle, 2026-11-20): labels.parqet at the top, landmark files in
        # test_landmark_files/, and sequence ids instead of paths. A label table inside the landmark
        # folder is never picked, and sequence ids are matched to files by name.
        with tempfile.TemporaryDirectory() as root:
            data = Path(root) / "datasets" / "sohier" / "rerun"
            (data / "test_landmark_files" / "55372").mkdir(parents=True)
            (data / "test_landmark_files" / "55372" / "1001.parquet").write_bytes(b"x")
            (data / "test_landmark_files" / "55372" / "1002.parquet").write_bytes(b"x")
            (data / "test_landmark_files" / "decoy.csv").write_text("path,sign\na,b\n")
            (data / "labels.csv").write_text("sequence_id,participant_id,sign\n1001,55372,hello\n1002,55372,bye\n")
            path, columns = core.find_label_table(root)
            self.assertTrue(path.endswith("labels.csv"))
            self.assertEqual(columns, {"path": None, "sequence": "sequence_id", "sign": "sign", "participant": "participant_id"})
            index = core.index_landmark_files(str(data))
            self.assertEqual(sorted(index), ["1001", "1002"])
            self.assertTrue(index["1001"].endswith("1001.parquet"))
            self.assertIsNone(core.label_columns(["frame", "row_id", "type", "landmark_index", "x", "y", "z"]))


class NotebookTests(unittest.TestCase):
    def test_notebook_is_up_to_date(self):
        expected = json.dumps(builder.build(), indent=1, ensure_ascii=False) + "\n"
        self.assertEqual(builder.OUT.read_text(encoding="utf-8"), expected, "run python tools/build_asl_eval_notebook.py")

    @unittest.skipUnless(importlib.util.find_spec("pandas"), "pandas is not installed: the notebook reads Kaggle's parquet files with it "
                         "(Kaggle has it; SignBridge itself does not need it). pip install pandas to run this test.")
    def test_every_cell_runs_with_a_stand_in_model_and_data(self):
        self.run_notebook(layout="paths")

    @unittest.skipUnless(importlib.util.find_spec("pandas"), "pandas is not installed")
    def test_every_cell_runs_with_the_rerun_sets_layout(self):
        self.run_notebook(layout="sequence_ids")

    def run_notebook(self, layout):
        notebook = json.loads(builder.OUT.read_text(encoding="utf-8"))
        cells = ["".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code"]
        labels = asl_islr.load_classes()
        rng = np.random.default_rng(3)
        with tempfile.TemporaryDirectory() as root:
            data = Path(root) / "asl-rerun"
            (data / "landmarks").mkdir(parents=True)
            rows = ["path,participant_id,sequence_id,sign"] if layout == "paths" else ["sequence_id,participant_id,sign"]
            sequences = {}
            for i in range(30):
                sign = labels[i % 5]
                rel = f"landmarks/{i}.parquet" if layout == "paths" else f"test_landmark_files/{100 + i % 3}/{5000 + i}.parquet"
                (data / rel).parent.mkdir(parents=True, exist_ok=True)
                (data / rel).write_bytes(b"stand-in")
                hands = [frame(right=True), frame(left=True, right=True), frame()][i % 3]
                sequences[str(data / rel)] = np.stack([hands + rng.normal(0, 0.001, hands.shape).astype(np.float32)] * (10 + i))
                rows.append(f"{rel},{100 + i % 3},{i},{sign}" if layout == "paths" else f"{5000 + i},{100 + i % 3},{sign}")
            (data / ("rerun_labels.csv" if layout == "paths" else "labels.csv")).write_text("\n".join(rows) + "\n")
            (data / "model.tflite").write_bytes(b"stand-in model")
            classes_bytes = (ROOT / "models" / "asl" / "sign_to_prediction_index_map.json").read_bytes()
            (data / "sign_to_prediction_index_map.json").write_bytes(classes_bytes)
            output = Path(root) / "out.json"

            class FakeInterpreter:
                def __init__(self, model_path):
                    self.model_path = model_path

                def get_input_details(self):
                    return [{"shape_signature": [-1, 543, 3]}]

                def get_signature_runner(self, name):
                    def run(inputs):
                        scores = np.zeros(250, dtype=np.float32)
                        scores[len(inputs) % 5] = 4.0  # right only when the length matches the sign
                        return {"outputs": scores}
                    return run

            fake_module = types.ModuleType("ai_edge_litert.interpreter")
            fake_module.Interpreter = FakeInterpreter
            namespace: dict = {}
            with patch.dict(sys.modules, {"ai_edge_litert": types.ModuleType("ai_edge_litert"), "ai_edge_litert.interpreter": fake_module}):
                for index, source in enumerate(cells):
                    if index == 0:
                        source = source.replace('"/kaggle/input"', repr(root)).replace('"/kaggle/working/asl_eval_results.json"', repr(str(output)))
                        exec(source, namespace)
                        namespace["MODEL"]["sha256"] = hashlib.sha256(b"stand-in model").hexdigest()
                        continue
                    exec(source, namespace)
                    if index == 1:  # the core: replace the parquet reader with the stand-in data
                        namespace["load_sequence"] = lambda path, check_order=False: sequences[path]
            results = json.loads(output.read_text())
        self.assertEqual(results["dataset"]["samples_evaluated"], 30)
        self.assertEqual(results["dataset"]["signers"], ["100", "101", "102"])
        self.assertEqual(results["layout_files_checked"], 5)
        summary = results["summary"]
        self.assertEqual(summary["samples"], 30)
        self.assertTrue(math.isclose(summary["native"]["top1"], sum((10 + i) % 5 == i % 5 for i in range(30)) / 30))
        self.assertEqual(set(summary["fixed_length"]), {"16", "24", "32", "48", "64"})
        self.assertEqual(summary["fixed_length"]["32"]["samples"], 6)
        self.assertIn("right_slot_near_pose_right_wrist", results["conventions"])
        self.assertEqual(summary["groups"]["no_hands"]["samples"], 10)


if __name__ == "__main__":
    unittest.main()
