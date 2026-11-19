"""Pinned model downloads (fast track Stage 2): size and SHA-256 checks, refusal of wrong files, ledger gate."""

from __future__ import annotations

import hashlib
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]

from data_engine.downloads import DownloadError, fetch, load_downloads, verify  # noqa: E402
import fetch_assets  # noqa: E402

PAYLOAD = b"pinned model bytes " * 100


def item_for(payload: bytes = PAYLOAD, asset_id: str = "mediapipe-pose-landmarker-lite") -> dict:
    return {"path": "models/test_model.task", "asset_id": asset_id, "url": "https://example.invalid/model.task",
            "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(), "needed_for": "tests"}


def opener_serving(payload: bytes, calls: list | None = None):
    def opener(url, timeout=60):
        if calls is not None:
            calls.append(url)
        return io.BytesIO(payload)
    return opener


class DownloadTests(unittest.TestCase):
    def test_the_pinned_file_is_downloaded_once(self):
        with tempfile.TemporaryDirectory() as folder:
            calls = []
            path = fetch(item_for(), root=Path(folder), opener=opener_serving(PAYLOAD, calls), log=lambda _m: None)
            self.assertEqual(path.read_bytes(), PAYLOAD)
            fetch(item_for(), root=Path(folder), opener=opener_serving(PAYLOAD, calls), log=lambda _m: None)
            self.assertEqual(len(calls), 1)
            self.assertEqual(sorted(p.name for p in path.parent.iterdir()), ["test_model.task"])

    def test_a_different_download_is_refused_and_nothing_is_saved(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(DownloadError) as caught:
                fetch(item_for(), root=Path(folder), opener=opener_serving(b"tampered " * 211), log=lambda _m: None)
            self.assertIn("not the pinned one", str(caught.exception))
            self.assertFalse((Path(folder) / "models").exists() and any((Path(folder) / "models").iterdir()))

    def test_a_wrong_local_file_is_moved_aside_and_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "models" / "test_model.task"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"an older model")
            fetch(item_for(), root=Path(folder), opener=opener_serving(PAYLOAD), log=lambda _m: None)
            self.assertEqual(target.read_bytes(), PAYLOAD)
            self.assertEqual((target.parent / "test_model.task.bad").read_bytes(), b"an older model")

    def test_the_ledger_must_allow_the_asset(self):
        with tempfile.TemporaryDirectory() as folder, self.assertRaises(DownloadError):
            fetch(item_for(asset_id="psl-128"), root=Path(folder), opener=opener_serving(PAYLOAD), log=lambda _m: None)

    def test_network_failure_is_reported_plainly(self):
        def broken(url, timeout=60):
            raise OSError("no route to host")
        with tempfile.TemporaryDirectory() as folder, self.assertRaises(DownloadError) as caught:
            fetch(item_for(), root=Path(folder), opener=broken, log=lambda _m: None)
        self.assertIn("Connect to the internet once", str(caught.exception))

    def test_verify_names_the_problem(self):
        item = item_for()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "m.task"
            self.assertIn("missing", verify(path, item))
            path.write_bytes(b"x")
            self.assertIn("bytes", verify(path, item))
            path.write_bytes(b"y" * len(PAYLOAD))
            self.assertIn("SHA-256", verify(path, item))
            path.write_bytes(PAYLOAD)
            self.assertIsNone(verify(path, item))

    def test_check_mode_reports_missing_files_without_downloading(self):
        with tempfile.TemporaryDirectory() as folder:
            output = io.StringIO()
            with redirect_stdout(output):
                code = fetch_assets.main(["--check", "--root", folder])
            self.assertEqual(code, 0)
            self.assertEqual(output.getvalue().count("MISSING"), len(load_downloads()))


if __name__ == "__main__":
    unittest.main()
