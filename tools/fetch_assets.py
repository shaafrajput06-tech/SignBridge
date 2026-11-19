"""Download the model files SignBridge needs (once) and check each against its pinned SHA-256.

    python tools/fetch_assets.py           download every missing file in shared_data/downloads.json
    python tools/fetch_assets.py --check   only check the files that are present (no network)
    python tools/fetch_assets.py --only asl    only files whose "needed_for" mentions the word

Files: MediaPipe pose and face models (capture v2) and the ASL model with its class map. A file whose
size or hash differs is moved aside (name.bad) and downloaded again. Each asset must be allowed by
data/LICENSES.yaml.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data_engine.downloads import DownloadError, fetch, load_downloads, verify  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="check present files only; never download")
    parser.add_argument("--only", default="", help="only files whose needed_for contains this word")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    items = [item for item in load_downloads() if args.only.lower() in item["needed_for"].lower()]
    failures = 0
    for item in items:
        target = args.root / item["path"]
        if args.check:
            problem = verify(target, item)
            if problem is None:
                print(f"OK       {item['path']}")
            elif not target.exists():
                print(f"MISSING  {item['path']} (run python tools/fetch_assets.py)")
            else:
                print(f"WRONG    {problem}")
                failures += 1
            continue
        try:
            fetch(item, root=args.root)
            print(f"OK       {item['path']}")
        except DownloadError as error:
            print(f"FAILED   {error}")
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
