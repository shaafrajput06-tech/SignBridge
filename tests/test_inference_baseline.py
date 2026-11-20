"""Inference Baseline v1 (master-v3.md section 0, CLAUDE.md 9.1): today's code must reproduce the baseline.

tests/golden/baseline_v1_outputs.json was recorded by running the frozen baseline build
(baseline/v1-site) in Chromium (node tools/baseline/run.mjs --record). These tests hold the Python
reference (ml_engine/asl_islr.py) to it, without a browser:

- the frozen files themselves are unchanged (tools/baseline_v1.py check);
- the 543-point frames, nearest-frame resampling, segmenter and confidence words are identical;
- the exact 32 x 543 x 3 model inputs are identical, bit for bit, for every case Python can build;
- with a TFLite runtime installed (ai-edge-litert; CI has it), the server path's top-1 equals the
  baseline browser path's top-1 on those same inputs, and the top-5 probabilities agree within 0.001.

web/tests/inference-baseline.test.mjs does the same for web/src/asl_islr.js.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import struct
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml_engine.asl_islr import SPEC, AslModelError, AslRecognizer, SignSegmenter, islr_frame, load_classes, probabilities, resample  # noqa: E402

GOLDEN = json.loads((ROOT / "tests" / "golden" / "baseline_v1_outputs.json").read_text(encoding="utf-8"))
INPUTS = json.loads((ROOT / "tests" / "golden" / "baseline_v1_inputs.json").read_text(encoding="utf-8"))
CASES = json.loads((ROOT / "tests" / "golden" / "asl_islr_cases.json").read_text(encoding="utf-8"))
FIXTURE = json.loads(gzip.decompress((ROOT / "tests" / "golden" / "v2_holistic.json.gz").read_bytes()))
NAN_BYTES = struct.pack("<I", 0x7FC00000)


def float32_sha256(sequence) -> str:
    """Same as float32Bytes + sha256Hex in tools/baseline/cases.mjs."""
    out = bytearray()
    for frame in sequence:
        for row in frame:
            for value in row:
                out += NAN_BYTES if math.isnan(value) else struct.pack("<f", value)
    return hashlib.sha256(bytes(out)).hexdigest()


def parts_present(frame) -> dict:
    return {part["name"]: sum(1 for r in range(part["start"], part["start"] + part["count"]) if not math.isnan(frame[r][0]))
            for part in SPEC["layout"]["parts"]}


def top_five(probs, labels):
    order = sorted(range(len(probs)), key=lambda i: (-probs[i], i))[:5]
    return [{"index": i, "label": labels[i], "probability": round(probs[i], 6)} for i in order]


def band(probability: float) -> str:
    c = SPEC["confidence"]
    return "sure" if probability >= c["sure"] else "unsure" if probability >= c["unsure"] else "none"


def python_model_cases():
    """The static and mix cases (the synthetic ones come from the JavaScript signer and are checked in Node)."""
    unmirrored = [(item["id"], islr_frame(item["raw"])) for item in FIXTURE["canonicalize_cases"] if not item["raw"].get("input_mirrored")]
    cases = {f"static_{case_id}": [frame] * INPUTS["static"]["repeat"] for case_id, frame in unmirrored}
    for mix in INPUTS["mix"]:
        cases[mix["id"]] = [unmirrored[(7 * j + mix["offset"]) % len(unmirrored)][1] for j in range(mix["length"])]
    return cases


class FrozenFilesTests(unittest.TestCase):
    def test_baseline_files_in_git_are_unchanged(self):
        completed = subprocess.run([sys.executable, str(ROOT / "tools" / "baseline_v1.py"), "check"], capture_output=True, text=True, timeout=120)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_golden_file_names_the_frozen_baseline_and_model(self):
        manifest = json.loads((ROOT / "baseline" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(GOLDEN["baseline_zip_sha256"], manifest["source_zip"]["sha256"])
        self.assertEqual(GOLDEN["model_sha256"], SPEC["model"]["sha256"])
        self.assertEqual(GOLDEN["recorded_with"]["frames"], INPUTS["fixed_frames"])
        self.assertEqual(INPUTS["fixed_frames"], SPEC["fixed_length"]["frames"])


class PipelineTests(unittest.TestCase):
    """Frames, resampling, segmenter and confidence words: identical to the baseline."""

    def test_islr_frames_match_the_baseline_bit_for_bit(self):
        for case, expected in zip(FIXTURE["canonicalize_cases"], GOLDEN["pipeline"]["frames"], strict=True):
            self.assertEqual(case["id"], expected["id"])
            if expected.get("refused"):
                with self.assertRaises(ValueError, msg=case["id"]):
                    islr_frame(case["raw"])
                continue
            frame = islr_frame(case["raw"])
            self.assertEqual(float32_sha256([frame]), expected["sha256"], case["id"])
            self.assertEqual(parts_present(frame), expected["parts"], case["id"])

    def test_resampling_matches_the_baseline(self):
        for expected in GOLDEN["pipeline"]["resampling"]:
            self.assertEqual(resample(list(range(expected["length"])), expected["count"]), expected["indices"])

    def test_segmenter_matches_the_baseline(self):
        for stream, expected in zip(CASES["segmenter_streams"], GOLDEN["pipeline"]["segments"], strict=True):
            segmenter = SignSegmenter()
            signs = []
            for index, present in enumerate(stream):
                sign = segmenter.push(index, bool(present))
                if sign:
                    signs.append(sign)
            rest = segmenter.flush()
            if rest:
                signs.append(rest)
            self.assertEqual([[s[0], s[-1], len(s)] for s in signs], expected)

    def test_scores_become_the_same_top_five_and_words(self):
        labels = load_classes()
        words = SPEC["confidence"]["words"]
        for vector, expected in zip(CASES["scores"], GOLDEN["pipeline"]["scores"], strict=True):
            probs = probabilities(vector)
            top = top_five(probs, labels)
            self.assertEqual([t["index"] for t in top], [t["index"] for t in expected["top"]])
            for got, want in zip(top, expected["top"]):
                self.assertAlmostEqual(got["probability"], want["probability"], places=6)
            self.assertEqual(band(probs[top[0]["index"]]), expected["band"])
            self.assertEqual(words[expected["band"]], expected["words"])


class ModelInputTests(unittest.TestCase):
    def test_model_inputs_match_the_baseline_bit_for_bit(self):
        expected = {item["id"]: item for item in GOLDEN["model"]}
        cases = python_model_cases()
        self.assertGreaterEqual(len(cases), 30)
        for case_id, sequence in cases.items():
            self.assertIn(case_id, expected)
            fixed = resample(sequence, INPUTS["fixed_frames"])
            self.assertEqual(float32_sha256(fixed), expected[case_id]["input_sha256"], case_id)

    def test_every_recorded_case_is_complete(self):
        labels = load_classes()
        for item in GOLDEN["model"]:
            self.assertEqual(len(item["top"]), 5, item["id"])
            probs = [t["probability"] for t in item["top"]]
            self.assertEqual(probs, sorted(probs, reverse=True), item["id"])
            for t in item["top"]:
                self.assertEqual(labels[t["index"]], t["label"], item["id"])
            self.assertEqual(item["band"], band(item["top"][0]["probability"]), item["id"])


class ServerPathTests(unittest.TestCase):
    """Server path (ai-edge-litert) against the baseline's browser path (LiteRT.js), identical inputs."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.recognizer = AslRecognizer()
        except AslModelError as error:
            raise unittest.SkipTest(f"no TFLite runtime or model here: {str(error).splitlines()[0]}")

    def test_server_top1_equals_baseline_top1_on_identical_inputs(self):
        expected = {item["id"]: item for item in GOLDEN["model"]}
        tolerance = GOLDEN["tolerance"]["probability_abs"]
        worst = 0.0
        cases = python_model_cases()
        for case_id, sequence in cases.items():
            probs = probabilities(self.recognizer.scores(resample(sequence, INPUTS["fixed_frames"])))
            want = expected[case_id]
            self.assertEqual(max(range(len(probs)), key=lambda i: (probs[i], -i)), want["top"][0]["index"], case_id)
            for t in want["top"]:
                difference = abs(probs[t["index"]] - t["probability"])
                worst = max(worst, difference)
                self.assertLessEqual(difference, tolerance, case_id)
        print(f"\n  Server path vs baseline browser path: {len(cases)} cases, top-1 identical, largest top-5 probability difference {worst:.2e}", file=sys.stderr)


if __name__ == "__main__":
    unittest.main()


class SpeakThresholdTests(unittest.TestCase):
    def test_spoken_only_at_seventy_percent_while_the_shown_words_stay(self):
        from ml_engine.asl_islr import confidence_band, should_speak

        self.assertEqual(SPEC["confidence"]["speak_at"], 0.7)
        self.assertEqual(confidence_band(0.65), "sure")
        self.assertFalse(should_speak(0.65))
        self.assertTrue(should_speak(0.7))
        self.assertFalse(should_speak(0.3))
        measured = json.loads((ROOT / "reports" / "asl_eval_results_2026-11-20.json").read_text(encoding="utf-8"))
        at = {row["threshold"]: row for row in measured["summary"]["calibration"]}
        self.assertLessEqual(1 - at[0.7]["accuracy_when_covered"], 0.02)   # the reason for 0.70
        self.assertGreater(1 - at[0.6]["accuracy_when_covered"], 0.02)
