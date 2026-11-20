"""SignSpeak (psl-signspeak-words, Apache-2.0) -> one training file of PSL hand sequences.

Downloads both Hugging Face archives at a pinned revision (only after the licence ledger allows training),
reads MP_Data*/<word>/<sample>/<frame>.npy (126 values per frame: two hands x 21 points x (x, y, z)), and
writes data/psl-signspeak-words/signspeak.npz plus a summary JSON. Nothing here goes into git
(data/ is ignored); the training workflow uploads the result as an artifact.

Facts this script checks and prints instead of assuming (master-v3 Stage 2, docs/handoffs/v3-stage-2-plan.md):
  - which of the two 63-value blocks is the signer's right hand (from which block leads in one-handed signs)
  - the camera shape (width / height) of each folder, estimated from how rigid the palm stays
  - duplicates between the two archives, partial samples, and folders that are not words

    python -m tools.psl_data.signspeak [--out data/psl-signspeak-words] [--archives a.zip b.zip]
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import tempfile
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from data_engine.ledger import assert_allowed

LEDGER_ID = "psl-signspeak-words"
REPO = "mohibkhansherwani/DynamicWordLevelPakistanSignLanguageDataset"
REVISION = "1ba8b9fc58ad01431e50031fe3fe31e4d01f689d"  # read 2026-11-20 (tools/psl_data/discover.py)
ARCHIVES = ("PakistanSignLanguageDataset.zip", "PakistanSignLanguageDatasetV2.zip")
UA = {"User-Agent": "SignBridge-psl-data/1.0 (https://github.com/shaafrajput06-tech/SignBridge)"}
MEMBER = re.compile(r"^(?:.*/)?(MP_Data[^/]*)/([^/]+)/([^/]+)/(\d+)\.npy$")
DEVICES = {"MP_Data": "webcam", "MP_Data_mobile": "phone"}
UNKNOWN_FOLDERS = {"nothing"}  # becomes the "not a sign" class
NOT_WORDS = {"left_hand", "s", "test_word"}  # test folders of the dataset's authors; not PSL words
FULL_LENGTH = 60
MIN_LENGTH = 45
COMMON_ASPECTS = (9 / 16, 3 / 4, 1.0, 4 / 3, 16 / 9)
PALM = ((0, 5), (0, 17), (5, 17), (0, 9), (5, 9), (9, 13), (13, 17))


def gloss_id(folder: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", folder.strip().lower()).strip("_")


def download(name: str, folder: Path) -> Path:
    url = f"https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/{name}"
    path = folder / name
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=1800) as response, path.open("wb") as out:  # noqa: S310
        shutil.copyfileobj(response, out, length=1 << 20)
    print(f"downloaded {name}: {path.stat().st_size} bytes")
    return path


def read_archive(path: Path) -> dict[tuple[str, str, str], np.ndarray]:
    """{(folder, word, sample): (frames, 126) float64} for every sample whose frames are 0..n-1."""
    frames: dict[tuple[str, str, str], dict[int, str]] = defaultdict(dict)
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            match = MEMBER.match(name)
            if match:
                folder, word, sample, index = match.groups()
                frames[(folder, word, sample)][int(index)] = name
        samples = {}
        for key, members in frames.items():
            n = len(members)
            if sorted(members) != list(range(n)):
                continue
            rows = [np.load(io.BytesIO(archive.read(members[i])), allow_pickle=False).astype(np.float64).reshape(-1) for i in range(n)]
            if any(row.shape != (126,) for row in rows):
                continue
            samples[key] = np.stack(rows)
    return samples


def to_hands(raw: np.ndarray) -> np.ndarray:
    """(frames, 126) -> (frames, 2, 21, 3) in block order, NaN where a block is all zeros."""
    hands = raw.reshape(len(raw), 2, 21, 3).copy()
    empty = np.abs(hands).sum(axis=(-1, -2)) == 0
    hands[empty] = np.nan
    return hands


def block_order(samples: list[np.ndarray]) -> dict:
    """Which block leads in one-handed samples, and where each block's wrist sits in two-handed frames."""
    lead = Counter()
    x_first, x_second = [], []
    for hands in samples:
        m = ~np.isnan(hands[..., 0, 0])
        a, b = int(m[:, 0].sum()), int(m[:, 1].sum())
        both = m.all(axis=1)
        if a + b and both.sum() < 0.2 * max(a, b):
            lead["first" if a > b else "second"] += 1
        if both.any():
            x_first.extend(hands[both, 0, 0, 0].tolist())
            x_second.extend(hands[both, 1, 0, 0].tolist())
    first_right_of_second = float(np.mean(np.array(x_first) > np.array(x_second))) if x_first else None
    return {
        "one_handed_samples_led_by_first_block": lead["first"],
        "one_handed_samples_led_by_second_block": lead["second"],
        "two_handed_frames": len(x_first),
        "share_of_two_handed_frames_with_first_block_further_right_in_image": first_right_of_second,
    }


def estimate_aspect(samples: list[np.ndarray], limit: int = 400) -> dict:
    """Width/height of the camera, from how constant the palm's 3D bone lengths stay as the hand turns.

    MediaPipe's x is in image widths, y in image heights and z roughly in image widths, so lengths are
    measured on (x * a, y, z * a), in image heights; the right a keeps a rigid palm's lengths most constant.
    """
    rng = np.random.default_rng(0)
    chosen = [samples[i] for i in rng.permutation(len(samples))[:limit]]
    candidates = np.round(np.arange(0.50, 2.01, 0.01), 2)
    scores = np.zeros(len(candidates))
    used = 0
    for hands in chosen:
        for h in range(2):
            pts = hands[:, h]
            pts = pts[~np.isnan(pts[:, 0, 0])]
            if len(pts) < 10:
                continue
            used += 1
            for k, a in enumerate(candidates):
                scaled = pts * np.array([a, 1.0, a])
                lengths = np.stack([np.linalg.norm(scaled[:, i] - scaled[:, j], axis=-1) for i, j in PALM], axis=1)
                scores[k] += float(np.mean(lengths.std(axis=0) / np.maximum(lengths.mean(axis=0), 1e-9)))
    if not used:
        return {"estimate": None, "nearest_common": None, "hands_used": 0}
    best = float(candidates[int(np.argmin(scores))])
    nearest = min(COMMON_ASPECTS, key=lambda c: abs(c - best))
    curve = {f"{a:.2f}": round(scores[k] / used, 5) for k, a in enumerate(candidates) if round(a * 100) % 10 == 0}
    return {"estimate": best, "nearest_common": round(nearest, 4), "hands_used": used, "rigidity_curve": curve}


def convert(archives: list[Path], out: Path) -> dict:
    seen: dict[str, tuple] = {}
    kept: list[tuple[str, str, str, str, np.ndarray]] = []
    report = Counter()
    dropped_folders = Counter()
    for path in archives:
        samples = read_archive(path)
        report[f"samples_in_{path.name}"] = len(samples)
        for (folder, word, sample), raw in sorted(samples.items()):
            if word.lower() in NOT_WORDS:
                dropped_folders[word] += 1
                continue
            digest = hashlib.sha256(np.ascontiguousarray(raw, dtype=np.float64).tobytes()).hexdigest()
            if digest in seen:
                report["exact_duplicates_dropped"] += 1
                continue
            seen[digest] = (path.name, folder, word, sample)
            if len(raw) < MIN_LENGTH:
                report["partial_samples_dropped"] += 1
                continue
            hands = to_hands(raw)
            if (~np.isnan(hands[..., 0, 0])).any(axis=1).sum() < 6:
                report["samples_with_under_6_hand_frames_dropped"] += 1
                continue
            kept.append((path.name, folder, word, sample, hands))
    order = block_order([k[4] for k in kept if k[2].lower() not in UNKNOWN_FOLDERS])
    # MediaPipe Holistic names hands from the body it sees, so its left block always appears further right
    # in the image; what tells an unmirrored capture of right-handed signers from a mirrored one is
    # which block leads one-handed signs.
    second_leads = order["one_handed_samples_led_by_second_block"] >= order["one_handed_samples_led_by_first_block"]
    order["decision"] = ("first block = signer's left hand, second = signer's right (unmirrored capture; most signers right-handed)"
                         if second_leads else
                         "capture was mirrored: x -> 1 - x and blocks swapped so hand 0 is the signer's left")
    if not second_leads:
        kept = [(z, f, w, s, _mirror(h)) for z, f, w, s, h in kept]

    by_device = defaultdict(list)
    for _, folder, _, _, hands in kept:
        by_device[DEVICES.get(folder, folder)].append(hands)
    aspects = {device: estimate_aspect(items) for device, items in by_device.items()}

    length = max(len(k[4]) for k in kept)
    hands_array = np.full((len(kept), length, 2, 21, 3), np.nan, dtype=np.float32)
    lengths = np.zeros(len(kept), dtype=np.int32)
    for i, k in enumerate(kept):
        hands_array[i, : len(k[4])] = k[4]
        lengths[i] = len(k[4])
    words = np.array(["_unknown" if k[2].lower() in UNKNOWN_FOLDERS else gloss_id(k[2]) for k in kept])
    devices = np.array([DEVICES.get(k[1], k[1]) for k in kept])
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / "signspeak.npz", hands=hands_array, lengths=lengths, word=words, device=devices,
                        folder_word=np.array([k[2] for k in kept]), sample=np.array([k[3] for k in kept]),
                        archive=np.array([k[0] for k in kept]))
    per_word = defaultdict(Counter)
    for w, d in zip(words, devices):
        per_word[str(w)][str(d)] += 1
    summary = {
        "ledger_id": LEDGER_ID,
        "source": f"https://huggingface.co/datasets/{REPO} @ {REVISION}",
        "archives": [p.name for p in archives],
        "counts": dict(report),
        "folders_dropped_as_not_words": dict(dropped_folders),
        "samples_kept": len(kept),
        "words": len(per_word),
        "per_word": {w: dict(c) for w, c in sorted(per_word.items())},
        "devices": dict(Counter(devices.tolist())),
        "hand_order": order,
        "camera_shape": aspects,
        "frames_per_sample": dict(Counter(lengths.tolist())),
    }
    (out / "signspeak_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _mirror(hands: np.ndarray) -> np.ndarray:
    out = hands[:, ::-1].copy()
    out[..., 0] = 1.0 - out[..., 0]
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("data/psl-signspeak-words"))
    parser.add_argument("--archives", type=Path, nargs="*", help="already downloaded archives (skips the download)")
    args = parser.parse_args(argv)
    assert_allowed(LEDGER_ID, "train_labels")
    with tempfile.TemporaryDirectory() as tmp:
        archives = args.archives or [download(name, Path(tmp)) for name in ARCHIVES]
        summary = convert(list(archives), args.out)
    print("===SIGNSPEAK-SUMMARY-BEGIN===")
    print(json.dumps({k: v for k, v in summary.items() if k != "per_word"}, indent=2))
    print("per word (webcam / phone):")
    for word, counts in summary["per_word"].items():
        print(f"  {word}: {counts.get('webcam', 0)} / {counts.get('phone', 0)}")
    print("===SIGNSPEAK-SUMMARY-END===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
