"""The website's address lives in one place (shared_data/site.json); every file that names it agrees.

The owner chose https://signbridge-pk.github.io/ on 2026-11-20 (docs/DOMAIN.md). The old address
(shaafrajput06-tech.github.io/SignBridge) may only appear where a file talks about the move itself.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = json.loads((ROOT / "shared_data" / "site.json").read_text(encoding="utf-8"))

# Files that may mention the old address because they describe the move or keep history.
MAY_NAME_OLD_ADDRESS = {
    "shared_data/site.json",
    "docs/DOMAIN.md",
    "docs/WEBSITE.md",
    "docs/HOW_TO_MEASURE_SPEED.md",
    "README.md",
    "docs/prompts/master-v3.md",
    "tools/old_address_redirect/README.md",
    "tools/baseline_v1.py",
    "tests/test_site_address.py",
}
SKIP_DIRS = {".git", "node_modules", "dist", "baseline", ".dart_tool", "build", "__pycache__", ".venv"}
TEXT_SUFFIXES = {".md", ".py", ".js", ".mjs", ".jsx", ".json", ".html", ".yml", ".yaml", ".dart", ".txt", ".bat", ".ps1", ".toml", ".css"}
OLD_SITE = re.compile(r"shaafrajput06-tech\.github\.io/SignBridge", re.IGNORECASE)


def text_files():
    for path in ROOT.rglob("*"):
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES and not (set(path.relative_to(ROOT).parts) & SKIP_DIRS):
            yield path


class SiteConfigTests(unittest.TestCase):
    def test_config_is_complete_and_consistent(self):
        self.assertTrue(SITE["site_url"].startswith("https://") and SITE["site_url"].endswith("/"))
        self.assertEqual(SITE["name"], "SignBridge")
        owner, repo = SITE["repository"].split("/")
        self.assertEqual(SITE["repository_url"], f"https://github.com/{owner}/{repo}")
        # An organisation's main website comes from the repository named <owner>.github.io.
        if SITE["site_url"] == f"https://{owner}.github.io/":
            self.assertEqual(repo, f"{owner}.github.io")

    def test_readme_and_website_doc_give_the_current_address(self):
        for name in ("README.md", "docs/WEBSITE.md"):
            self.assertIn(SITE["site_url"], (ROOT / name).read_text(encoding="utf-8"), name)

    def test_old_address_appears_only_where_the_move_is_explained(self):
        offenders = []
        for path in text_files():
            relative = path.relative_to(ROOT).as_posix()
            if relative in MAY_NAME_OLD_ADDRESS or relative.startswith(("reports/", "docs/handoffs/")):
                continue
            if OLD_SITE.search(path.read_text(encoding="utf-8", errors="replace")):
                offenders.append(relative)
        self.assertEqual(offenders, [], "these files still name the old website address; use shared_data/site.json")

    def test_forwarding_pages_send_visitors_to_the_current_address(self):
        folder = ROOT / "tools" / "old_address_redirect"
        for name in ("SignBridge/index.html", "404.html"):
            html = (folder / name).read_text(encoding="utf-8")
            targets = set(re.findall(r'NEW_SITE = "([^"]+)"', html))
            self.assertEqual(targets, {SITE["site_url"]}, name)
            for url in re.findall(r'https://[a-z0-9.-]+\.github\.io/[^"\s<]*', html):
                self.assertTrue(url.startswith(SITE["site_url"]), f"{name}: {url}")


if __name__ == "__main__":
    unittest.main()
