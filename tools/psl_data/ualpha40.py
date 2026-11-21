"""UAlpha40 (psl-ualpha40, CC BY 4.0): Urdu alphabet of Pakistan Sign Language, from Mendeley Data.

    python -m tools.psl_data.ualpha40 --discover        # list folders, file counts and sizes; download nothing big
    python -m tools.psl_data.ualpha40 --convert OUT      # originals only -> hand landmarks (MediaPipe) -> OUT/ualpha40.npz

Nothing is downloaded before the licence ledger allows training. Images are read in memory and only hand
landmarks are kept (CLAUDE.md 4: landmarks, not pictures).
"""

from __future__ import annotations

import argparse
import json
import re
import tempfile
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

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


# Letter number in the file names (e.g. s0251-02alif.jpg) -> Urdu letter, in the Urdu alphabet's order.
URDU = "آ ا ب پ ت ٹ ث ج چ ح خ د ڈ ذ ر ڑ ز ژ س ش ص ض ط ظ ع غ ف ق ک گ ل م ن ں و ہ ھ ء ی ے".split()
FILE = re.compile(r"^(s\d{4})-(\d{2})([a-z]+)", re.IGNORECASE)
ROOT = Path(__file__).resolve().parents[2]


def download_url(record: dict) -> str:
    details = record.get("content_details", {})
    return details.get("download_url") or details.get("view_url") or record.get("download_url", "")


def landmarker():
    import mediapipe as mp  # noqa: F401
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python.vision import HandLandmarker, HandLandmarkerOptions, RunningMode

    return HandLandmarker.create_from_options(HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(ROOT / "models" / "hand_landmarker.task")),
        running_mode=RunningMode.IMAGE, num_hands=2, min_hand_detection_confidence=0.3, min_hand_presence_confidence=0.3))


def convert(out: Path) -> dict:
    """Original photos only (the dataset's augmented copies are left out: they are edits of the same photos).
    Keeps per photo: letter, signer id from the file name, image size and up to two hands' landmarks."""
    import mediapipe as mp
    import numpy as np

    picked = [(folder, record) for folder, record in tree() if folder.endswith("-Original")]
    print(f"{len(picked)} original photos in {len({f for f, _ in picked})} letter folders")
    detector = landmarker()
    rows, problems = [], Counter()

    def fetch(item):
        folder, record = item
        try:
            with urllib.request.urlopen(urllib.request.Request(download_url(record), headers={"User-Agent": UA["User-Agent"]}), timeout=120) as r:  # noqa: S310
                return folder, record, r.read()
        except Exception as error:  # noqa: BLE001
            return folder, record, error

    with tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor(8) as pool:
        for number, (folder, record, data) in enumerate(pool.map(fetch, picked), 1):
            name = record.get("filename", "")
            match = FILE.match(name)
            if isinstance(data, Exception) or not match:
                problems["could not download" if isinstance(data, Exception) else "file name without signer/letter"] += 1
                continue
            signer, letter_number = match.group(1).lower(), int(match.group(2))
            path = Path(tmp) / "photo.jpg"
            path.write_bytes(data)
            try:
                image = mp.Image.create_from_file(str(path))
            except Exception:  # noqa: BLE001
                problems["unreadable image"] += 1
                continue
            result = detector.detect(image)
            hands = np.full((2, 21, 3), np.nan, dtype=np.float32)
            labels = []
            for k, landmarks in enumerate(result.hand_landmarks[:2]):
                hands[k] = [[p.x, p.y, p.z] for p in landmarks]
                labels.append(result.handedness[k][0].category_name if result.handedness else "")
            if not result.hand_landmarks:
                problems["no hand found"] += 1
            rows.append({"signer": signer, "letter": letter_number, "folder": folder, "width": image.width, "height": image.height,
                         "hands": hands, "labels": labels})
            if number % 250 == 0:
                print(f"{number}/{len(picked)} photos read")
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / "ualpha40.npz",
                        hands=np.stack([r["hands"] for r in rows]),
                        letter=np.array([r["letter"] for r in rows]), signer=np.array([r["signer"] for r in rows]),
                        width=np.array([r["width"] for r in rows]), height=np.array([r["height"] for r in rows]),
                        handedness=np.array([",".join(r["labels"]) for r in rows]))
    found = Counter(r["letter"] for r in rows if not np.isnan(r["hands"][0, 0, 0]))
    summary = {"ledger_id": LEDGER_ID, "source": f"https://data.mendeley.com/datasets/{DATASET}/{VERSION}", "photos": len(rows),
               "with_a_hand": sum(found.values()), "signers": len({r["signer"] for r in rows}), "problems": dict(problems),
               "per_letter": {f"{n:02d} {URDU[n - 1]}": found.get(n, 0) for n in sorted({r["letter"] for r in rows})},
               "two_hands_found": sum(1 for r in rows if not np.isnan(r["hands"][1, 0, 0]))}
    (out / "ualpha40_summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--discover", action="store_true")
    parser.add_argument("--convert", type=Path, help="output folder for ualpha40.npz")
    args = parser.parse_args(argv)
    assert_allowed(LEDGER_ID, "train_labels")
    if args.discover:
        discover()
    if args.convert:
        summary = convert(args.convert)
        print("===UALPHA40-SUMMARY-BEGIN===")
        print(json.dumps(summary, indent=1, ensure_ascii=False))
        print("===UALPHA40-SUMMARY-END===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
