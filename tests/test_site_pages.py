"""The website's "How well it works", "Credits" and "What's new" pages read shared_data/site_pages.json.
It must be exactly what tools/site_pages.py builds from the committed reports, so the page and the reports
never disagree (master-v3 Stage 7)."""

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def builder():
    spec = importlib.util.spec_from_file_location("site_pages", ROOT / "tools" / "site_pages.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SitePagesTests(unittest.TestCase):
    def test_committed_pages_match_the_reports(self):
        stored = json.loads((ROOT / "shared_data" / "site_pages.json").read_text(encoding="utf-8"))
        self.assertEqual(stored, json.loads(json.dumps(builder().build(), ensure_ascii=False)), "rerun python tools/site_pages.py")

    def test_every_shipped_asset_is_credited_with_its_ledger_licence(self):
        pages = builder().build()
        ids = {a["id"] for a in pages["credits"]["assets"]}
        self.assertIn("psl-slt-dictionary", ids)
        self.assertIn("asl-islr-1st-place-tflite", ids)
        for asset in pages["credits"]["assets"]:
            self.assertTrue(asset["licence"])
            if asset["licence"] not in ("project-owned",):
                self.assertTrue(asset["attribution"], asset["id"])

    def test_psl_bundle_licences_are_credited(self):
        pages = builder().build()
        manifest_path = ROOT / "models" / "psl" / "manifest.json"
        if not manifest_path.exists():
            self.skipTest("no PSL bundle committed")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        ids = {a["id"] for a in pages["credits"]["assets"]}
        for ledger_id in manifest["licences"]:
            self.assertIn(ledger_id, ids)
        self.assertEqual(pages["psl"]["signs"], sum(1 for c in manifest["classes"] if c.get("tier")))


if __name__ == "__main__":
    unittest.main()
