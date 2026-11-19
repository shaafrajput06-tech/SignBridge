"""Check the licence ledger and every asset file in the repository.

    python tools/check_licenses.py            validate data/LICENSES.yaml and check models/, data/, fonts/,
                                              web/public/models/, web/public/clips/ and mobile/assets/
    python tools/check_licenses.py --release  stricter, for store releases: every shipped file needs a
                                              recorded SHA-256, and nothing shipped may come from an asset
                                              with unresolved provenance or non-commercial terms
    python tools/check_licenses.py --list     print every asset with its status and allowed uses

Exit code 1 when the ledger is invalid or any file is not covered by an entry that allows its use.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data_engine.ledger import LedgerError, check_repository, load_ledger, uses_table, validate_ledger  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--release", action="store_true", help="store-release rules (hashes required, no unresolved conditions)")
    parser.add_argument("--list", action="store_true", help="print the asset table")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--ledger", type=Path, default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    ledger_path = args.ledger or args.root / "data" / "LICENSES.yaml"
    try:
        ledger = load_ledger(ledger_path)
    except LedgerError as error:
        print(f"Licence ledger: FAILED\n  {error}")
        return 1
    problems = validate_ledger(ledger)
    if problems:
        print(f"Licence ledger: FAILED ({len(problems)} problem(s) in {ledger_path.name})")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    if args.list:
        print("\n".join(uses_table(ledger)))
        print()

    report = check_repository(ledger, root=args.root, release=args.release)
    mode = "release" if args.release else "default"
    print(f"Licence ledger: {len(ledger['assets'])} assets, {len(report.covered)} files checked ({mode} rules)")
    for warning in report.warnings:
        print(f"  warning: {warning}")
    for error in report.errors:
        print(f"  ERROR: {error}")
    print("Licence check: " + ("PASSED" if report.ok else f"FAILED ({len(report.errors)} error(s))"))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
