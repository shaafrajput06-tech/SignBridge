"""python -m tools.web_learn {search,add-ledger,fetch,check} - see tools/web_learn/pipeline.py."""

from __future__ import annotations

import argparse
import os
import sys

from tools.web_learn import pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.web_learn", description=pipeline.__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    search = sub.add_parser("search", help="find candidates and draft ledger entries (no downloads)")
    search.add_argument("--version", type=int, default=1)
    search.add_argument("--web-words", type=int, default=None, help="search only the first N vocabulary words on the web")
    ledger = sub.add_parser("add-ledger", help="append the drafted entries to data/LICENSES.yaml")
    ledger.add_argument("--version", type=int, default=1)
    fetch = sub.add_parser("fetch", help="download ledger-allowed clips, extract landmarks, write the report")
    fetch.add_argument("--version", type=int, default=1)
    fetch.add_argument("--limit", type=int, default=None)
    sub.add_parser("check", help="every web_learned manifest entry is allowed by the ledger")
    args = parser.parse_args(argv)

    if args.command == "search":
        pipeline.run_search(args.version, youtube_key=os.environ.get("YOUTUBE_API_KEY") or None, web_words=args.web_words)
        return 0
    if args.command == "add-ledger":
        print(f"Added {pipeline.add_ledger(args.version)} entries to data/LICENSES.yaml")
        return 0
    if args.command == "fetch":
        pipeline.run_fetch(args.version, limit=args.limit)
        return 0
    problems = pipeline.check_all()
    for problem in problems:
        print(problem)
    print("Web-learned data check: " + ("PASSED" if not problems else f"FAILED ({len(problems)})"))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
