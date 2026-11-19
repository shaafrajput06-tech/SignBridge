"""Copy the root vocabulary.json to the web/desktop and mobile copies, or check they match.

    python tools/sync_vocabulary.py           validate vocabulary.json, then overwrite the copies
    python tools/sync_vocabulary.py --check   exit 1 if any copy differs (used by the tests)

vocabulary.json in the project root is the only file to edit by hand. Vocabulary IDs are
never changed by this tool; it copies bytes after the schema check passes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vocabulary_utils import load_vocabulary  # noqa: E402

SOURCE = ROOT / "vocabulary.json"
COPIES = [ROOT / "shared_data" / "vocabulary.json", ROOT / "mobile" / "assets" / "vocabulary.json"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronise SignBridge vocabulary copies")
    parser.add_argument("--check", action="store_true", help="only report whether the copies match")
    args = parser.parse_args()
    load_vocabulary(SOURCE)
    source = SOURCE.read_bytes()
    stale = [path for path in COPIES if not path.exists() or path.read_bytes() != source]
    if args.check:
        for path in stale:
            print(f"Out of date: {path.relative_to(ROOT).as_posix()} (run python tools/sync_vocabulary.py)")
        return 1 if stale else 0
    for path in stale:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(source)
        print(f"Updated {path.relative_to(ROOT).as_posix()}")
    if not stale:
        print("All vocabulary copies already match vocabulary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
