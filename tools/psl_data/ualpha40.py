"""UAlpha40 (psl-ualpha40, CC BY 4.0): Urdu alphabet of Pakistan Sign Language, from Mendeley Data.

    python -m tools.psl_data.ualpha40 --discover        # list folders, file counts and sizes; download nothing big
    python -m tools.psl_data.ualpha40 --convert OUT      # originals only -> hand landmarks (MediaPipe) -> OUT/ualpha40.npz

Nothing is downloaded before the licence ledger allows training. Images are read in memory and only hand
landmarks are kept (CLAUDE.md 4: landmarks, not pictures).
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from collections import Counter, defaultdict

from data_engine.ledger import assert_allowed

LEDGER_ID = "psl-ualpha40"
DATASET, VERSION = "3pvnnckxyb", 3
API = "https://data.mendeley.com/public-api/datasets"
UA = {"User-Agent": "SignBridge-psl-data/1.0 (https://github.com/shaafrajput06-tech/SignBridge)", "Accept": "application/json"}


def get_json(url: str):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as response:  # noqa: S310
        return json.loads(response.read())


def folders() -> list[dict]:
    return get_json(f"{API}/{DATASET}/folders/{VERSION}")


def files(folder_id: str) -> list[dict]:
    return get_json(f"{API}/{DATASET}/files?folder_id={folder_id}&version={VERSION}")


def tree() -> list[tuple[str, dict]]:
    """[(folder path, file record)] for every file of the dataset version."""
    found = folders()
    by_id = {f["id"]: f for f in found}

    def path(folder_id: str) -> str:
        parts = []
        while folder_id in by_id:
            parts.append(by_id[folder_id]["name"])
            folder_id = by_id[folder_id].get("parent_id")
        return "/".join(reversed(parts))

    out = []
    for folder_id in ["root", *by_id]:
        for record in files(folder_id):
            out.append((path(folder_id) if folder_id != "root" else "", record))
    return out


def discover() -> None:
    entries = tree()
    print(f"{len(entries)} files")
    per_folder = defaultdict(lambda: [0, 0, Counter(), []])
    for folder, record in entries:
        details = record.get("content_details", {})
        stats = per_folder[folder]
        stats[0] += 1
        stats[1] += int(details.get("size") or record.get("size") or 0)
        stats[2][record.get("filename", "").rsplit(".", 1)[-1].lower()] += 1
        if len(stats[3]) < 3:
            stats[3].append(record.get("filename"))
    for folder, (count, size, kinds, examples) in sorted(per_folder.items()):
        print(f"  {folder or '(top)'}: {count} files, {size / 1e6:.1f} MB, {dict(kinds)}, e.g. {examples}")
    sample = entries[0][1] if entries else {}
    print("record keys:", sorted(sample), "content_details keys:", sorted(sample.get("content_details", {})))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--discover", action="store_true")
    args = parser.parse_args(argv)
    assert_allowed(LEDGER_ID, "train_labels")
    if args.discover:
        discover()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
