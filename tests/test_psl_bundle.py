"""The committed PSL bundle (models/psl): manifest rules, SHA-256, tiers, licences, and the Stage 2 gate's
Python part (same top-1 as the training run on tests/golden/psl_parity_cases.json). Skips cleanly when
no bundle is committed yet or LiteRT is not installed."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import numpy as np

from data_engine.ledger import assert_allowed
from ml_engine import psl_hands, psl_model

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "models" / "psl"
PARITY = ROOT / "tests" / "golden" / "psl_parity_cases.json"


@unittest.skipUnless((BUNDLE / "manifest.json").exists(), "no PSL bundle committed yet")
class BundleTests(unittest.TestCase):
    def setUp(self):
        self.manifest = psl_model.load_manifest(BUNDLE)

    def test_model_file_matches_the_manifest(self):
        blob = (BUNDLE / self.manifest["model"]["file"]).read_bytes()
        self.assertEqual(hashlib.sha256(blob).hexdigest(), self.manifest["model"]["sha256"])
        self.assertEqual(len(blob), self.manifest["model"]["bytes"])

    def test_tiers_badges_and_licences(self):
        for entry in self.manifest["classes"]:
            if entry["gloss"] == self.manifest.get("unknown_class"):
                self.assertIsNone(entry["tier"])
                continue
            self.assertIn(entry["tier"], ("A", "B"))
            self.assertFalse(entry["validated_by_deaf_signers"], "no Deaf validator sign-off is recorded yet (CLAUDE.md 3)")
            if entry["tier"] == "A":
                self.fail("Tier A needs the signer-independent gate; SignSpeak has no signer ids")
        self.assertEqual(self.manifest["badge"], "Community dataset — not yet validated")
        self.assertIn("never automatically", self.manifest["confidence"]["speak"])
        for ledger_id in self.manifest["licences"]:
            assert_allowed(ledger_id, "redistribute_weights")
            assert_allowed(ledger_id, "train_labels")

    def test_metrics_say_what_they_were_measured_on(self):
        held = self.manifest["metrics"]["device_held_out"]
        self.assertIn("weaker", held["protocol"])
        self.assertTrue(0.0 <= held["top1"] <= held["top5"] <= 1.0)

    def test_unsupported_feature_versions_are_refused(self):
        bad = dict(self.manifest, feature_version="psl-hands-v9")
        with self.assertRaises(psl_model.BundleError):
            folder = ROOT / "out" / "bad_bundle"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "manifest.json").write_text(json.dumps(bad), encoding="utf-8")
            psl_model.load_manifest(folder)

    def test_python_gives_the_training_runs_top1_on_the_parity_cases(self):
        try:
            model = psl_model.PslModel(BUNDLE)
        except psl_model.BundleError as error:
            self.skipTest(str(error))
        parity = json.loads(PARITY.read_text(encoding="utf-8"))
        for case in parity["cases"]:
            hands = np.array([[[np.nan if v is None else v for v in p] for p in hand] for hand in case["hands"]], dtype=np.float32)
            frames = psl_hands.to_islr(hands.reshape(psl_hands.FRAMES, 2, 21, 3))
            scores = model.scores(model.input_from_frames(frames, psl_hands.ASPECT_REFERENCE))
            self.assertEqual(int(np.argmax(scores)), case["top5"][0], case["sign"])
            np.testing.assert_allclose(scores[case["top5"]], case["top5_scores"], atol=2e-2)


if __name__ == "__main__":
    unittest.main()
