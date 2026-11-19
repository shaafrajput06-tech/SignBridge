"""Run every automated SignBridge test that this machine can run, and say what was skipped.

    python tools/run_all_tests.py           Python tests + licence ledger check + browser parity tests (Node) + Flutter tests (if installed)
    python tools/run_all_tests.py --smoke   also the fake-camera browser smoke test (needs Playwright)

Node tests that import src/vision.js need `npm install` in web/ (they load @mediapipe/tasks-vision).
The v2 Node tests need no packages and run whenever Node is installed.

Exit code is non-zero when any suite that ran has failures. Suites that cannot run here
(for example Node is not installed) are reported as SKIPPED, never as passed.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def run(name: str, command: list[str], cwd: Path) -> str:
    print(f"\n=== {name} ===", flush=True)
    completed = subprocess.run(command, cwd=cwd)
    return "PASSED" if completed.returncode == 0 else f"FAILED (exit {completed.returncode})"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--smoke", action="store_true", help="also run the browser camera smoke test")
    args = parser.parse_args()
    results: dict[str, str] = {}

    results["Python unit tests"] = run("Python unit tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests"], ROOT)
    results["Licence ledger check"] = run("Licence ledger check", [sys.executable, str(ROOT / "tools" / "check_licenses.py")], ROOT)

    node = shutil.which("node")
    all_node_tests = sorted((WEB / "tests").glob("*.test.mjs"))
    needs_packages = [str(p.relative_to(WEB)) for p in all_node_tests if "src/vision.js" in p.read_text(encoding="utf-8")]
    standalone = [str(p.relative_to(WEB)) for p in all_node_tests if str(p.relative_to(WEB)) not in needs_packages]
    if not node:
        results["Browser v1 parity tests (Node)"] = "SKIPPED: Node.js is not installed"
        results["Browser v2 tests (Node)"] = "SKIPPED: Node.js is not installed"
    else:
        if not (WEB / "node_modules" / "@mediapipe" / "tasks-vision").exists():
            results["Browser v1 parity tests (Node)"] = "SKIPPED: run npm install in the web folder first"
        else:
            results["Browser v1 parity tests (Node)"] = run("Browser v1 parity tests (Node)", [node, "--test", *needs_packages], WEB)
        results["Browser v2 tests (Node)"] = run("Browser v2 tests (Node)", [node, "--test", *standalone], WEB)

    if args.smoke:
        npm = shutil.which("npm")
        if not npm:
            results["Browser camera smoke test"] = "SKIPPED: npm is not installed"
        elif not (WEB / "node_modules" / "@mediapipe" / "tasks-vision").exists():
            results["Browser camera smoke test"] = "SKIPPED: run npm install in the web folder first"
        else:
            results["Browser camera smoke test"] = run("Browser camera smoke test", [npm, "run", "test:smoke"], WEB)
    else:
        results["Browser camera smoke test"] = "SKIPPED: add --smoke to run it"

    flutter = shutil.which("flutter")
    if not flutter:
        results["Flutter tests"] = "SKIPPED: the Flutter SDK is not installed (mobile/test has unit tests to run with flutter test)"
    else:
        results["Flutter tests"] = run("Flutter tests", [flutter, "test"], ROOT / "mobile")
    print("\n=== Summary ===")
    for name, outcome in results.items():
        print(f"{name:<32} {outcome}")
    return 1 if any(outcome.startswith("FAILED") for outcome in results.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
