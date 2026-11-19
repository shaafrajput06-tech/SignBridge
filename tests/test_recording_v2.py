"""Recording format v2 and the v1 CSV converter (Phase 1), plus the feature_version switch."""

from __future__ import annotations

import csv
import gzip
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]

from collect_data import CSV_HEADER, save_rows  # noqa: E402
from ml_engine.feature_versions import resolve_feature_version  # noqa: E402
from ml_engine.features_v2 import sequence_features  # noqa: E402
from ml_engine.model_loader import load_model_bundle  # noqa: E402
from ml_engine.recording_v2 import (  # noqa: E402
    RecordingError, base_meta, key_fingerprint, pseudonym, read_recording, record_to_v1_row, recording_features,
    training_use_refusal, write_recording,
)
import convert_v1_to_v2  # noqa: E402

FIXTURE = json.loads(gzip.decompress((ROOT / "tests" / "golden" / "v2_holistic.json.gz").read_bytes()))
KEY = b"test-key-not-a-secret-0123456789"


def live_meta(**changes):
    meta = base_meta(source="capture_v2", gloss_id="hello", signer_id="s_abc123", session_id="sess-1", device="laptop-webcam",
                     camera_orientation_degrees=0, input_mirrored=False, image_width=1, image_height=1, fps=None,
                     consent_id="consent-0001", consent_recorded=True, created_utc="2026-11-17T00:00:00+00:00")
    meta.update(changes)
    return meta


def float32_frames(frames):
    def rows(value):
        return None if value is None else np.asarray(value, dtype=np.float32).astype(np.float64).tolist()
    return [{**frame, **{key: rows(frame[key]) for key in ("left_hand", "right_hand", "pose", "pose_visibility", "face")}} for frame in frames]


class RecordingRoundTripTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.frames = next(s for s in FIXTURE["sequences"] if s["id"] == "hands_flicker")["frames"]

    def tearDown(self):
        self.temporary.cleanup()

    def test_frames_and_features_survive_a_round_trip(self):
        path = write_recording(self.base / "a.npz", self.frames, live_meta())
        record = read_recording(path)
        expected = float32_frames(self.frames)
        self.assertEqual(record["frames"], expected)
        self.assertEqual(recording_features(path)["features"], sequence_features(expected)["features"])
        self.assertEqual(record["meta"]["frame_count"], len(self.frames))
        self.assertEqual(record["meta"]["fps"], round((len(self.frames) - 1) * 1000 / (self.frames[-1]["timestamp_ms"] - self.frames[0]["timestamp_ms"]), 3))
        self.assertEqual((record["meta"]["image_width"], record["meta"]["image_height"]), (self.frames[0]["image_width"], self.frames[0]["image_height"]))

    def test_same_input_gives_byte_identical_files(self):
        a = write_recording(self.base / "a.npz", self.frames, live_meta())
        b = write_recording(self.base / "b.npz", self.frames, live_meta())
        self.assertEqual(a.read_bytes(), b.read_bytes())

    def test_file_holds_landmarks_only(self):
        path = write_recording(self.base / "a.npz", self.frames, live_meta())
        with np.load(path, allow_pickle=False) as data:
            self.assertEqual(sorted(data.files), ["hand_assignment", "meta", "points", "pose_visibility", "present", "timestamps_ms"])
            for name in data.files:
                array = data[name]
                image_like = array.dtype == np.uint8 and array.ndim >= 2 and name != "present"
                self.assertFalse(image_like, name)
            self.assertEqual(data["points"].shape, (len(self.frames), 120, 3))
            self.assertEqual(data["meta"].ndim, 1)

    def test_metadata_rules(self):
        bad = [
            {"consent_id": " "},
            {"participant": "Ayesha"},
            {"video_stored": True},
            {"signer_id": "Ayesha Khan"},
            {"camera_orientation_degrees": 45},
            {"input_mirrored": None},
            {"feature_version": "v1"},
            {"source": "webcam"},
            {"consent_recorded": False},
            {"instance_unit": "frame"},
            {"signer_name": "Ayesha"},
            {"notes": "recorded with Ayesha"},
            {"v1": {"name": "Ayesha"}},
            {"device": "Ayesha's laptop"},
            {"warnings": [{"name": "Ayesha"}]},
        ]
        for change in bad:
            with self.assertRaises(RecordingError, msg=change):
                write_recording(self.base / "bad.npz", self.frames, live_meta(**change))
        meta = live_meta()
        del meta["consent_id"]
        with self.assertRaises(RecordingError):
            write_recording(self.base / "bad.npz", self.frames, meta)
        write_recording(self.base / "video.npz", self.frames, live_meta(video_stored=True, video_consent=True))
        self.assertIsNone(training_use_refusal(read_recording(self.base / "video.npz")["meta"]))

    def test_frame_rules(self):
        frames = [dict(frame) for frame in self.frames[:3]]
        frames[2]["timestamp_ms"] = frames[1]["timestamp_ms"]
        with self.assertRaises(RecordingError):
            write_recording(self.base / "t.npz", frames, live_meta())
        frames = [dict(frame) for frame in self.frames[:3]]
        frames[1]["image_width"] += 1
        with self.assertRaises(RecordingError):
            write_recording(self.base / "s.npz", frames, live_meta())
        with self.assertRaises(RecordingError):
            write_recording(self.base / "e.npz", [], live_meta())
        with self.assertRaises(RecordingError):
            write_recording(self.base / "x.json", self.frames, live_meta())


class V1ConverterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        features = [[round(0.01 * i - 0.3 + 0.001 * n, 8) for i in range(63)] for n in range(5)]
        meta = [
            ["hello", "Ayesha Khan", "s1", "2026-11-10T10:00:00+00:00", "0", "640", "480", "Right"],
            ["hello", "Ayesha Khan", "s1", "2026-11-10T10:00:01+00:00", "2", "640", "480", "Right"],
            ["thank_you", "Bilal", "s2", "2026-11-10T11:00:00+00:00", "0", "1280", "720", "Left"],
            ["yes", "anonymous", "mobile-1731230000", "2026-11-10T12:00:00+00:00", "0", "0", "0", "Unknown"],
            ["no", "ayesha khan ", "s3", "2026-11-10T13:00:00+00:00", "7", "640", "480", "Right"],
        ]
        self.rows = [m + [repr(v) for v in f] for m, f in zip(meta, features)]
        self.csv = self.base / "sign_data.csv"
        save_rows(self.rows, self.csv)
        with self.csv.open("a", encoding="utf-8", newline="") as stream:
            csv.writer(stream).writerow(["not_a_word"] + ["x"] * (len(CSV_HEADER) - 1))
        self.key_file = self.base / "key.txt"
        self.key_file.write_bytes(KEY)

    def tearDown(self):
        self.temporary.cleanup()

    def run_converter(self, output, *extra):
        with patch("builtins.print"):
            return convert_v1_to_v2.main(["--input", str(self.csv), "--output", str(output), "--signer-key-file", str(self.key_file), *extra])

    def test_every_valid_row_becomes_a_lossless_record(self):
        output = self.base / "out"
        self.assertEqual(self.run_converter(output), 0)
        report = json.loads((output / "conversion_report.json").read_text(encoding="utf-8"))
        self.assertEqual((report["input_rows"], report["converted"], report["skipped_malformed"]), (6, 5, 1))
        self.assertEqual(report["signers"], 3, "Ayesha Khan and 'ayesha khan ' are one signer; anonymous is one ID")
        rebuilt = {}
        for name in report["files"]:
            record = read_recording(output / name)
            self.assertEqual(record["meta"]["source"], "v1-csv")
            self.assertEqual(record["frames"][0]["left_hand"], None)
            row = record_to_v1_row(record)
            rebuilt[(row[0], row[2], row[4])] = row
        for original in self.rows:
            row = rebuilt[(original[0], original[2], original[4])]
            self.assertEqual(row[0], original[0])
            self.assertEqual(row[1] == original[1], original[1] == "anonymous", "names become signer IDs")
            self.assertEqual(row[2:8], original[2:8])
            self.assertEqual([float(v) for v in row[8:]], [float(v) for v in original[8:]])
        with self.assertRaises(RecordingError):
            recording_features(output / report["files"][0])

    def test_v1_records_are_marked_unconsented_frames_and_refused_for_training(self):
        output = self.base / "out"
        self.run_converter(output)
        report = json.loads((output / "conversion_report.json").read_text(encoding="utf-8"))
        for name in report["files"]:
            meta = read_recording(output / name)["meta"]
            self.assertFalse(meta["consent_recorded"])
            self.assertEqual(meta["instance_unit"], "frame")
            self.assertEqual(meta["signer_key_fingerprint"], key_fingerprint(KEY))
            self.assertIn("no recorded consent", training_use_refusal(meta))

    def test_pseudonyms_ignore_case_and_whitespace_but_depend_on_the_key(self):
        self.assertEqual(pseudonym("Ayesha  Khan", KEY), pseudonym(" ayesha khan\t", KEY))
        self.assertNotEqual(pseudonym("Ayesha Khan", KEY), pseudonym("Ayesha Khan", KEY + b"x"))
        self.assertNotEqual(key_fingerprint(KEY), key_fingerprint(KEY + b"x"))

    def test_names_never_reach_the_output(self):
        output = self.base / "out"
        self.run_converter(output)
        for path in output.rglob("*"):
            if path.is_file():
                data = path.read_bytes()
                if path.suffix == ".npz":
                    import zipfile
                    with zipfile.ZipFile(path) as archive:
                        data = b"".join(archive.read(name) for name in archive.namelist())
                for name in (b"Ayesha", b"ayesha", b"Bilal"):
                    self.assertNotIn(name, data, path)

    def test_warnings_flag_phone_and_anonymous_rows(self):
        output = self.base / "out"
        self.run_converter(output)
        report = json.loads((output / "conversion_report.json").read_text(encoding="utf-8"))
        self.assertTrue(any("F4" in warning for warning in report["warnings"]))
        self.assertTrue(any("anonymous" in warning for warning in report["warnings"]))

    def test_rerun_is_byte_identical(self):
        a, b = self.base / "a", self.base / "b"
        self.run_converter(a)
        self.run_converter(b)
        files_a = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
        files_b = sorted(p.relative_to(b) for p in b.rglob("*") if p.is_file())
        self.assertEqual(files_a, files_b)
        for name in files_a:
            self.assertEqual((a / name).read_bytes(), (b / name).read_bytes(), name)

    def test_refuses_to_run_without_a_key(self):
        with patch.dict(os.environ, {"SIGNBRIDGE_SIGNER_KEY": ""}), self.assertRaises(SystemExit):
            convert_v1_to_v2.main(["--input", str(self.csv), "--output", str(self.base / "x")])

    def test_signer_map_is_written_only_on_request(self):
        output = self.base / "out"
        self.run_converter(output)
        self.assertFalse(any("map" in p.name for p in output.rglob("*")))
        mapping = self.base / "signer_map.local.csv"
        self.run_converter(self.base / "out2", "--signer-map", str(mapping))
        self.assertIn("Ayesha Khan", mapping.read_text(encoding="utf-8"))


class PredictModel:
    def predict(self, rows):
        return ["hello"] * len(rows)


class FeatureVersionSwitchTests(unittest.TestCase):
    def test_v1_is_the_default_and_unknown_versions_are_refused(self):
        with patch.dict(os.environ, {"SIGNBRIDGE_FEATURE_VERSION": ""}):
            self.assertEqual(resolve_feature_version(), "v1")
        with patch.dict(os.environ, {"SIGNBRIDGE_FEATURE_VERSION": "v2"}):
            self.assertEqual(resolve_feature_version(), "v2")
        self.assertEqual(resolve_feature_version("V1"), "v1")
        with self.assertRaises(ValueError):
            resolve_feature_version("v9")

    def test_v1_loader_refuses_bundles_for_other_feature_versions(self):
        try:
            import joblib
        except ImportError as error:
            self.skipTest(f"joblib is not installed: {error}")

        with tempfile.TemporaryDirectory() as folder:
            for version, loads in ((None, True), ("v1", True), ("v2", False), ("v9", False)):
                path = Path(folder) / f"{version}.joblib"
                bundle = {"model": PredictModel(), "classes": ["hello"]}
                if version:
                    bundle["feature_version"] = version
                joblib.dump(bundle, path)
                self.assertEqual(load_model_bundle(path) is not None, loads, version)
            self.assertIsNotNone(load_model_bundle(Path(folder) / "v2.joblib", supported=("v1", "v2")))


if __name__ == "__main__":
    unittest.main()
