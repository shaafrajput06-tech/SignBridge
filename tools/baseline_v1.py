"""Inference Baseline v1: freeze, restore and check the reference website (master-v3.md section 0).

The baseline is the built "shared copy" of 2026-11-19 (SignBridge.zip: Start SignBridge.bat, serve.ps1,
README.txt and site/). It is the reference every new model and pipeline change is compared with.

What lives where
  baseline/v1-site/       the files SignBridge itself built (HTML, JavaScript, CSS, JSON): in git
  baseline/v1-shared/     Start SignBridge.bat, serve.ps1, README.txt of the shared copy: in git
  baseline/manifest.json  every file of the shared copy with its size and SHA-256, and where it lives
  third-party binaries    MediaPipe and LiteRT runtimes, the .task and .tflite models and the PSL clips:
                          NOT in git (size, licences); restored from the shared-copy zip, which is kept
                          as the asset of the GitHub release "inference-baseline-v1"

Commands (run from the project folder)
  python tools/baseline_v1.py check                    the files in git match the manifest (also a test)
  python tools/baseline_v1.py restore --zip PATH       copy the third-party files from SignBridge.zip
  python tools/baseline_v1.py restore --download       the same, downloading the zip from the release
  python tools/baseline_v1.py status                   which files are present, missing or different
  python tools/baseline_v1.py freeze --zip PATH        (once) write baseline/ from the zip; refuses to
                                                       overwrite an existing manifest without --force

Every file is checked against its SHA-256 before it is used; a wrong file is refused, never kept.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "baseline"
MANIFEST = BASELINE / "manifest.json"
SITE = BASELINE / "v1-site"
SHARED = BASELINE / "v1-shared"
ZIP_PREFIX = "SignBridge/"
RELEASE_TAG = "inference-baseline-v1"
RELEASE_ASSET = "SignBridge-shared-copy-v1.zip"
RELEASE_URL = f"https://github.com/shaafrajput06-tech/SignBridge/releases/download/{RELEASE_TAG}/{RELEASE_ASSET}"

# Files SignBridge built itself are kept in git. Everything from a third-party package or a dataset
# (runtimes, models, video clips) is restored from the zip instead.
THIRD_PARTY_PREFIXES = ("site/litert/", "site/wasm/", "site/clips/")
THIRD_PARTY_SUFFIXES = (".wasm", ".tflite", ".task", ".mp4")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def in_git(relative: str) -> bool:
    return not (relative.startswith(THIRD_PARTY_PREFIXES) or relative.endswith(THIRD_PARTY_SUFFIXES))


def local_path(relative: str) -> Path:
    """Where a shared-copy file lives in the repository."""
    if relative.startswith("site/"):
        return SITE / relative[len("site/"):]
    return SHARED / relative


def safe_relative(name: str) -> str | None:
    """The shared-copy path of a zip member, or None for folders and anything outside SignBridge/."""
    if not name.startswith(ZIP_PREFIX) or name.endswith("/"):
        return None
    relative = name[len(ZIP_PREFIX):]
    parts = PurePosixPath(relative).parts
    if not parts or any(part in ("..", "") for part in parts) or relative.startswith("/"):
        raise ValueError(f"unsafe path in the zip: {name!r}")
    return relative


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def freeze(zip_path: Path, force: bool) -> int:
    if MANIFEST.exists() and not force:
        print(f"{MANIFEST.relative_to(ROOT)} already exists: the baseline is frozen. Use --force only to re-freeze on purpose.")
        return 1
    data = zip_path.read_bytes()
    files = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for info in sorted(archive.infolist(), key=lambda item: item.filename):
            relative = safe_relative(info.filename)
            if relative is None:
                continue
            content = archive.read(info)
            entry = {"path": relative, "bytes": len(content), "sha256": sha256_bytes(content), "in_git": in_git(relative)}
            files.append(entry)
            if entry["in_git"]:
                target = local_path(relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
    manifest = {
        "name": "SignBridge Inference Baseline v1",
        "description": "The built shared copy of the SignBridge website (Vite build of 2026-11-19), frozen as the "
                       "reference for master-v3.md section 0. Never edit these files; compare new work against them.",
        "source_zip": {"name": zip_path.name, "bytes": len(data), "sha256": sha256_bytes(data)},
        "release": {"tag": RELEASE_TAG, "asset": RELEASE_ASSET, "url": RELEASE_URL},
        "frozen_on": "2026-11-20",
        "files": files,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    kept = sum(1 for item in files if item["in_git"])
    print(f"Froze {len(files)} files ({kept} in git, {len(files) - kept} restored from the zip) into {BASELINE.relative_to(ROOT)}/")
    return 0


def status(manifest: dict) -> dict[str, list[str]]:
    result = {"ok": [], "missing": [], "different": []}
    for entry in manifest["files"]:
        path = local_path(entry["path"])
        if not path.is_file():
            result["missing"].append(entry["path"])
        elif path.stat().st_size != entry["bytes"] or sha256_file(path) != entry["sha256"]:
            result["different"].append(entry["path"])
        else:
            result["ok"].append(entry["path"])
    return result


def check(manifest: dict) -> list[str]:
    """Problems with the files that must be in git (third-party files may be absent)."""
    problems = []
    current = status(manifest)
    for relative in current["different"]:
        problems.append(f"{relative}: differs from the frozen baseline")
    for relative in current["missing"]:
        if in_git(relative):
            problems.append(f"{relative}: missing (it belongs in git)")
    listed = {local_path(entry["path"]).resolve() for entry in manifest["files"]}
    for folder in (SITE, SHARED):
        for path in folder.rglob("*"):
            if path.is_file() and path.resolve() not in listed:
                problems.append(f"{path.relative_to(ROOT).as_posix()}: not part of the frozen baseline")
    return problems


def download(url: str) -> bytes:
    print(f"Downloading {url}")
    with urllib.request.urlopen(url, timeout=600) as response:  # noqa: S310 (fixed https URL)
        return response.read()


def restore(manifest: dict, zip_path: Path | None, use_download: bool) -> int:
    data = zip_path.read_bytes() if zip_path else download(manifest["release"]["url"])
    expected = manifest["source_zip"]
    if len(data) != expected["bytes"] or sha256_bytes(data) != expected["sha256"]:
        print(f"Refused: the zip is not the frozen shared copy (expected {expected['bytes']} bytes, SHA-256 {expected['sha256'][:12]}…).")
        return 1
    wanted = {entry["path"]: entry for entry in manifest["files"]}
    restored = 0
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for info in archive.infolist():
            relative = safe_relative(info.filename)
            if relative is None or relative not in wanted:
                continue
            entry = wanted[relative]
            target = local_path(relative)
            if target.is_file() and target.stat().st_size == entry["bytes"] and sha256_file(target) == entry["sha256"]:
                continue
            content = archive.read(info)
            if sha256_bytes(content) != entry["sha256"]:
                print(f"Refused {relative}: SHA-256 does not match the manifest.")
                return 1
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
                handle.write(content)
            os.replace(handle.name, target)
            restored += 1
    current = status(manifest)
    print(f"Restored {restored} files. Baseline: {len(current['ok'])} of {len(manifest['files'])} files present and correct.")
    return 0 if not current["missing"] and not current["different"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="files in git match the manifest")
    sub.add_parser("status", help="present / missing / different files")
    restore_parser = sub.add_parser("restore", help="restore third-party files from the shared-copy zip")
    source = restore_parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--zip", type=Path)
    source.add_argument("--download", action="store_true")
    freeze_parser = sub.add_parser("freeze", help="write baseline/ from the zip (once)")
    freeze_parser.add_argument("--zip", type=Path, required=True)
    freeze_parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "freeze":
        return freeze(args.zip, args.force)
    manifest = load_manifest()
    if args.command == "check":
        problems = check(manifest)
        for problem in problems:
            print(problem)
        print("Baseline check passed." if not problems else f"Baseline check FAILED ({len(problems)} problems).")
        return 0 if not problems else 1
    if args.command == "status":
        current = status(manifest)
        for key in ("ok", "missing", "different"):
            print(f"{key}: {len(current[key])}")
        for relative in current["missing"] + current["different"]:
            print(f"  {relative}")
        return 0
    return restore(manifest, args.zip, args.download)


if __name__ == "__main__":
    sys.exit(main())
