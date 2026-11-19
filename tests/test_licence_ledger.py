"""Licence ledger (fast track Stage 1, Phase 2 task 1): schema, checker and the assert_allowed gate."""

from __future__ import annotations

import copy
import datetime as dt
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]

from data_engine.ledger import (  # noqa: E402
    LicenceError, assert_allowed, check_repository, load_ledger, load_schema, scan_files, schema_errors, sha256_file,
    validate_ledger,
)
import check_licenses  # noqa: E402

LEDGER = load_ledger()
SCHEMA = load_schema()


def entry(**overrides) -> dict:
    """A minimal valid entry; tests override what they need."""
    base = {
        "id": "test-asset", "name": "Test asset", "kind": "dataset", "sign_language": "PSL", "label_scope": "psl",
        "source_url": "https://example.org/data", "licence": "CC-BY-4.0", "licence_evidence": "read on the test page",
        "allowed_uses": {"pretrain_encoder": True, "train_labels": True, "evaluate": True, "reference_clip": False,
                         "redistribute_weights": True, "redistribute_data": False},
        "conditions": ["attribution"], "attribution": "Test asset (CC BY 4.0).", "status": "cleared_with_conditions",
        "checked_on": "2026-11-18", "checked_by": "test", "files": [],
    }
    base.update(overrides)
    return base


def ledger_with(*entries: dict) -> dict:
    return {"schema_version": 1, "assets": list(entries)}


class TempRepo:
    """A throwaway repository root with the given files (path -> bytes)."""

    def __init__(self, files: dict[str, bytes]):
        self._dir = tempfile.TemporaryDirectory()
        self.root = Path(self._dir.name)
        for relative, content in files.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

    def __enter__(self) -> Path:
        return self.root

    def __exit__(self, *exc) -> None:
        self._dir.cleanup()


class LedgerFileTests(unittest.TestCase):
    def test_real_ledger_is_valid(self):
        self.assertEqual(validate_ledger(LEDGER, SCHEMA), [])

    def test_built_in_validator_agrees_with_jsonschema(self):
        try:
            import jsonschema  # noqa: F401
        except ImportError:
            self.skipTest("jsonschema not installed; the built-in validator is used alone")
        broken = copy.deepcopy(LEDGER)
        broken["assets"][0]["status"] = "fine"
        del broken["assets"][1]["licence"]
        broken["assets"][2]["allowed_uses"]["sell"] = True
        broken["assets"][3]["files"].append({"path": "models/x.task", "sha256": "abc"})
        for ledger in (LEDGER, broken):
            with self.subTest(broken=ledger is broken):
                self.assertEqual(bool(schema_errors(ledger, SCHEMA, prefer_jsonschema=True)),
                                 bool(schema_errors(ledger, SCHEMA, prefer_jsonschema=False)))
        self.assertGreaterEqual(len(schema_errors(broken, SCHEMA, prefer_jsonschema=False)), 4)

    def test_every_section_4_asset_has_an_entry(self):
        ids = {item["id"] for item in LEDGER["assets"]}
        expected = {"psl-signspeak-words", "psl-ualpha40", "psl-saadbutt-openpose", "psl-umt-anwar-usama",
                    "asl-islr-1st-place-tflite", "asl-popsign-v1", "asl-fingerspelling-1st-place", "psl-slt-dictionary",
                    "mediapipe-hand-landmarker", "mediapipe-pose-landmarker-lite", "mediapipe-face-landmarker"}
        self.assertEqual(expected - ids, set())

    def test_committed_hand_model_hash_matches_the_ledger(self):
        hand = next(item for item in LEDGER["assets"] if item["id"] == "mediapipe-hand-landmarker")
        pinned = next(f["sha256"] for f in hand["files"] if f["path"] == "models/hand_landmarker.task")
        self.assertEqual(sha256_file(ROOT / "models" / "hand_landmarker.task"), pinned)

    def test_repository_passes_the_default_check(self):
        report = check_repository(LEDGER, ROOT)
        self.assertEqual(report.errors, [])


class SemanticRuleTests(unittest.TestCase):
    def test_duplicate_ids_are_rejected(self):
        problems = validate_ledger(ledger_with(entry(), entry()), SCHEMA)
        self.assertTrue(any("duplicate id" in p for p in problems), problems)

    def test_entry_that_is_not_cleared_cannot_allow_uses_or_cover_files(self):
        blocked = entry(status="permission_needed", files=[{"path": "data/test-asset/*"}])
        problems = validate_ledger(ledger_with(blocked), SCHEMA)
        self.assertTrue(any("cannot allow any use" in p for p in problems), problems)
        self.assertTrue(any("cannot cover files" in p for p in problems), problems)

    def test_asl_labels_must_be_scoped_to_asl_mode(self):
        problems = validate_ledger(ledger_with(entry(sign_language="ASL", label_scope="psl")), SCHEMA)
        self.assertTrue(any("asl_mode_only" in p for p in problems), problems)

    def test_non_commercial_asset_cannot_be_redistributed_or_pretrain_a_shipped_encoder(self):
        nc = entry(conditions=["attribution", "non_commercial"])
        problems = validate_ledger(ledger_with(nc), SCHEMA)
        self.assertTrue(any("cannot be redistributed" in p for p in problems), problems)
        nc_pretrain = entry(conditions=["non_commercial"], allowed_uses={**nc["allowed_uses"], "redistribute_weights": False})
        problems = validate_ledger(ledger_with(nc_pretrain), SCHEMA)
        self.assertTrue(any("pretrain_encoder must be false" in p for p in problems), problems)

    def test_attribution_condition_needs_text(self):
        problems = validate_ledger(ledger_with(entry(attribution=" ")), SCHEMA)
        self.assertTrue(any("needs attribution text" in p for p in problems), problems)

    def test_future_check_date_and_patterns_outside_checked_folders_are_rejected(self):
        tomorrow = (dt.date(2026, 11, 18) + dt.timedelta(days=1)).isoformat()
        problems = validate_ledger(ledger_with(entry(checked_on=tomorrow, files=[{"path": "src/model.bin"}])), SCHEMA,
                                   today=dt.date(2026, 11, 18))
        self.assertTrue(any("in the future" in p for p in problems), problems)
        self.assertTrue(any("outside the checked folders" in p for p in problems), problems)

    def test_sha256_needs_an_exact_path(self):
        problems = validate_ledger(ledger_with(entry(files=[{"path": "models/*.task", "sha256": "0" * 64}])), SCHEMA)
        self.assertTrue(any("needs an exact path" in p for p in problems), problems)


class RepositoryCheckTests(unittest.TestCase):
    def test_deliberately_unlicensed_asset_is_blocked(self):
        with TempRepo({"models/hand_landmarker.task": (ROOT / "models" / "hand_landmarker.task").read_bytes(),
                       "models/rogue_signs.tflite": b"not in the ledger"}) as root:
            report = check_repository(LEDGER, root)
        self.assertFalse(report.ok)
        self.assertTrue(any(e.startswith("models/rogue_signs.tflite: not in data/LICENSES.yaml") for e in report.errors), report.errors)
        self.assertEqual(report.covered.get("models/hand_landmarker.task"), "mediapipe-hand-landmarker")

    def test_command_line_checker_exits_non_zero_for_the_unlicensed_asset(self):
        with TempRepo({"data/LICENSES.yaml": (ROOT / "data" / "LICENSES.yaml").read_bytes(),
                       "data/unknown-dataset/clip_01.npz": b"x"}) as root:
            output = io.StringIO()
            with redirect_stdout(output):
                code = check_licenses.main(["--root", str(root)])
        self.assertEqual(code, 1)
        self.assertIn("data/unknown-dataset/clip_01.npz: not in data/LICENSES.yaml", output.getvalue())

    def test_swapped_file_with_the_same_name_is_blocked_by_its_hash(self):
        with TempRepo({"models/hand_landmarker.task": b"a different model with the same name"}) as root:
            report = check_repository(LEDGER, root)
        self.assertTrue(any("does not match the ledger" in e for e in report.errors), report.errors)

    def test_evaluation_only_asset_cannot_be_shipped(self):
        eval_only = entry(allowed_uses={"pretrain_encoder": False, "train_labels": False, "evaluate": True,
                                        "reference_clip": False, "redistribute_weights": False, "redistribute_data": False},
                          files=[{"path": "data/test-asset/*"}, {"path": "models/test-asset/*"}])
        with TempRepo({"data/test-asset/a.npz": b"1", "models/test-asset/model.onnx": b"2"}) as root:
            report = check_repository(ledger_with(eval_only), root)
        self.assertEqual(report.covered, {"data/test-asset/a.npz": "test-asset", "models/test-asset/model.onnx": "test-asset"})
        self.assertEqual(len(report.errors), 1, report.errors)
        self.assertIn("models/test-asset/model.onnx", report.errors[0])
        self.assertIn("redistribute_weights", report.errors[0])

    def test_clips_need_reference_and_redistribution_rights(self):
        no_clips = entry(files=[{"path": "web/public/clips/psl/*"}])
        with TempRepo({"web/public/clips/psl/hello.mp4": b"v"}) as root:
            report = check_repository(ledger_with(no_clips), root)
        self.assertTrue(any("reference_clip" in e and "redistribute_data" in e for e in report.errors), report.errors)

    def test_file_covered_by_two_entries_is_an_error(self):
        a = entry(id="asset-a", files=[{"path": "data/shared/*"}])
        b = entry(id="asset-b", files=[{"path": "data/shared/*.npz"}])
        with TempRepo({"data/shared/x.npz": b"1"}) as root:
            report = check_repository(ledger_with(a, b), root)
        self.assertTrue(any("more than one ledger entry" in e for e in report.errors), report.errors)

    def test_release_rules_require_hashes_and_resolved_provenance(self):
        unpinned = "mobile/assets/models/asl/model.tflite"  # covered by a pattern, so no hash is recorded for it
        files = {unpinned: b"phone copy stand-in", "web/public/clips/psl/help.mp4": b"clip"}
        with TempRepo(files) as root:
            default = check_repository(LEDGER, root)
            release = check_repository(LEDGER, root, release=True)
        self.assertTrue(default.ok, default.errors)
        self.assertTrue(any(f"{unpinned}: no SHA-256" in w for w in default.warnings), default.warnings)
        self.assertTrue(any(f"{unpinned}: no SHA-256" in e for e in release.errors), release.errors)
        self.assertTrue(any("web/public/clips/psl/help.mp4" in e and "provenance_unverified" in e for e in release.errors), release.errors)

    def test_readme_gitkeep_and_ledger_files_are_not_assets(self):
        with TempRepo({"fonts/README.md": b"#", "data/.gitkeep": b"", "data/LICENSES.yaml": b"x",
                       "data/cards/psl-v1.md": b"#", "models/hand_landmarker.task.download": b"partial"}) as root:
            self.assertEqual(scan_files(root), [])


class AssertAllowedTests(unittest.TestCase):
    def test_cleared_use_returns_the_entry(self):
        self.assertEqual(assert_allowed("psl-signspeak-words", "train_labels", ledger=LEDGER)["licence"], "Apache-2.0")
        assert_allowed("psl-slt-dictionary", "reference_clip", ledger=LEDGER)
        assert_allowed("mediapipe-hand-landmarker", "redistribute_weights", ledger=LEDGER)

    def test_uses_the_licence_does_not_allow_are_refused(self):
        refused = [
            ("psl-128", "train_labels"),               # permission needed
            ("psl-umt-anwar-usama", "evaluate"),       # no licence at all
            ("psl-fesf-dictionary", "reference_clip"),  # all rights reserved
            ("psl-wlpsl-naeem", "redistribute_weights"),  # non-commercial
            ("psl-wlpsl-naeem", "train_labels"),       # evaluation only
            ("psl-saadbutt-openpose", "train_labels"),  # GPL-2.0, evaluation only
            ("asl-fingerspelling-1st-place", "redistribute_weights"),  # no weights published
            ("not-in-the-ledger", "evaluate"),
        ]
        for asset_id, use in refused:
            with self.subTest(asset=asset_id, use=use), self.assertRaises(LicenceError):
                assert_allowed(asset_id, use, ledger=LEDGER)

    def test_asl_and_psl_labels_never_cross(self):
        with self.assertRaises(LicenceError):
            assert_allowed("asl-islr-1st-place-tflite", "train_labels", purpose_language="PSL", ledger=LEDGER)
        assert_allowed("asl-islr-1st-place-tflite", "train_labels", purpose_language="ASL", ledger=LEDGER)
        with self.assertRaises(LicenceError):
            assert_allowed("psl-signspeak-words", "train_labels", purpose_language="ASL", ledger=LEDGER)
        with self.assertRaises(LicenceError):
            assert_allowed("asl-popsign-v1", "reference_clip", purpose_language="PSL", ledger=LEDGER)

    def test_unknown_use_or_language_is_a_programming_error(self):
        with self.assertRaises(ValueError):
            assert_allowed("psl-signspeak-words", "sell", ledger=LEDGER)
        with self.assertRaises(ValueError):
            assert_allowed("psl-signspeak-words", "train_labels", purpose_language="BSL", ledger=LEDGER)


if __name__ == "__main__":
    unittest.main()
