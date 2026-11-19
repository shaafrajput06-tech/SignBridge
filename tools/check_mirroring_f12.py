"""Finding F12: check on real recordings that mirrored and unmirrored camera input agree.

The desktop app mirrors frames before landmarking; the browser and the phone do not. Phase 0 proved
the two paths agree mathematically, but only if MediaPipe itself behaves the same on a mirrored
image. This tool measures that on real clips:

    python tools/check_mirroring_f12.py --clips path/to/clips

[HUMAN] Record about 20 short clips signing with the LEFT hand and 20 with the RIGHT hand (any
camera app; 3-6 s each; upper body and face in view; varied lighting). Name them left_*.mp4 and
right_*.mp4, or list them in a manifest CSV with columns file,signing_hand. The clips are only read.
Nothing is written except the two report files.

These clips are video of a person. Record only people who have agreed to it for this check (the
team's own members, ideally), keep the folder OUTSIDE this repository (the tool refuses a folder
inside it), and delete the clips once the report is reviewed. The reports name clips only as
clip_01, clip_02, ... with the signing hand; file names and folder paths are not written.

For every sampled frame it runs capture v2 twice: on the frame as recorded (input_mirrored=False)
and on a horizontally flipped copy (input_mirrored=True), then compares:

  side agreement        both paths put the signing hand on the same side
  truth match           that side is the hand the signer actually used
  hand shape difference largest |difference| in the v2 hand_shape values of the signing hand
  pose difference       largest |difference| in v2 pose positions (checks the left/right swap rule)
  label truth           MediaPipe's label on the unmirrored frame, swapped as canonicalize does when
                        there is no pose, names the hand actually used
  v1 label consistency  MediaPipe's handedness label flips when the image flips (Phase 0 assumption)
  v1 feature difference largest |difference| in the v1 features of the two paths

The pass thresholds below are starting values chosen before any real measurement; review them with
the first results instead of treating them as established. Reports: reports/f12_mirroring.{json,md}.
Exit code 0 = all checks pass, 2 = a check fails, 1 = not enough frames with hands.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Iterator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml_engine.capture_v2 import CaptureV2, SplitLandmarkerBackend  # noqa: E402
from ml_engine.features import normalize_landmarks  # noqa: E402
from ml_engine.features_v2 import feature_names, sequence_features  # noqa: E402

THRESHOLDS = {
    "side_agreement_min": 0.98,
    "truth_match_min": 0.95,
    "hand_shape_p95_max": 0.05,
    "pose_median_max": 0.05,
    "label_truth_min": 0.95,
    "v1_label_consistency_min": 0.98,
    "v1_feature_p95_max": 0.05,
}
MIN_FRAMES = 50
NAMES = feature_names()
SHAPE = {side: [i for i, n in enumerate(NAMES) if n.startswith(f"shape.{side}_hand[")] for side in ("left", "right")}
POSE = [i for i, n in enumerate(NAMES) if n.startswith("pos.pose[")]


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))] if ordered else float("nan")


def _swap(label):
    return {"left": "right", "right": "left"}.get(str(label).lower())


def check_clip(frames: Iterable, signing_hand: str, backend_factory: Callable[[], object], fps: float = 30.0) -> dict:
    """Compare both paths on one clip's RGB frames; returns per-frame measurements."""
    plain = CaptureV2(backend_factory(), input_mirrored=False)
    flipped = CaptureV2(backend_factory(), input_mirrored=True)
    out = {"signing_hand": signing_hand, "frames": 0, "hand_frames": 0, "agree": [], "truth_plain": [], "truth_flipped": [], "shape": [], "pose": [], "label_truth": [], "v1_label": [], "v1_diff": []}
    try:
        for index, rgb in enumerate(frames):
            timestamp = int(index * 1000 / fps)
            a = plain.process_rgb(rgb, timestamp)
            raw_a = plain.last_raw
            b = flipped.process_rgb(rgb[:, ::-1], timestamp)
            raw_b = flipped.last_raw
            out["frames"] += 1
            sides_a = [side for side in ("left", "right") if a[f"{side}_hand"] is not None]
            sides_b = [side for side in ("left", "right") if b[f"{side}_hand"] is not None]
            if len(sides_a) != 1 or len(sides_b) != 1:
                continue
            out["hand_frames"] += 1
            out["agree"].append(sides_a == sides_b)
            out["truth_plain"].append(sides_a[0] == signing_hand)
            out["truth_flipped"].append(sides_b[0] == signing_hand)
            fa, fb = sequence_features([a])["features"][0], sequence_features([b])["features"][0]
            if sides_a == sides_b:
                out["shape"].append(max(abs(fa[i] - fb[i]) for i in SHAPE[sides_a[0]]))
            if a["pose"] is not None and b["pose"] is not None:
                out["pose"].append(max(abs(fa[i] - fb[i]) for i in POSE))
            if len(raw_a["hands"]) == 1:
                out["label_truth"].append(_swap(raw_a["hands"][0]["handedness"]) == signing_hand)
            if len(raw_a["hands"]) == 1 and len(raw_b["hands"]) == 1:
                ha, hb = raw_a["hands"][0], raw_b["hands"][0]
                out["v1_label"].append(_swap(ha["handedness"]) == str(hb["handedness"]).lower())
                try:
                    va = normalize_landmarks(ha["landmarks"], ha["handedness"] or "Right")
                    vb = normalize_landmarks(hb["landmarks"], hb["handedness"] or "Right")
                    out["v1_diff"].append(max(abs(x - y) for x, y in zip(va, vb)))
                except ValueError:
                    pass
    finally:
        plain.close()
        flipped.close()
    return out


def summarise(clips: dict[str, dict]) -> dict:
    merged = {key: [] for key in ("agree", "truth_plain", "truth_flipped", "shape", "pose", "label_truth", "v1_label", "v1_diff")}
    frames = hand_frames = 0
    for result in clips.values():
        frames += result["frames"]
        hand_frames += result["hand_frames"]
        for key in merged:
            merged[key] += result[key]

    def rate(values):
        return sum(values) / len(values) if values else float("nan")

    measured = {
        "side_agreement": rate(merged["agree"]),
        "truth_match_unmirrored": rate(merged["truth_plain"]),
        "truth_match_mirrored": rate(merged["truth_flipped"]),
        "hand_shape_diff_median": statistics.median(merged["shape"]) if merged["shape"] else float("nan"),
        "hand_shape_diff_p95": _p95(merged["shape"]),
        "pose_diff_median": statistics.median(merged["pose"]) if merged["pose"] else float("nan"),
        "label_truth": rate(merged["label_truth"]),
        "v1_label_consistency": rate(merged["v1_label"]),
        "v1_feature_diff_p95": _p95(merged["v1_diff"]),
    }
    checks = {
        "side_agreement": measured["side_agreement"] >= THRESHOLDS["side_agreement_min"],
        "truth_match": min(measured["truth_match_unmirrored"], measured["truth_match_mirrored"]) >= THRESHOLDS["truth_match_min"],
        "hand_shape": measured["hand_shape_diff_p95"] <= THRESHOLDS["hand_shape_p95_max"],
        "pose_swap_rule": measured["pose_diff_median"] <= THRESHOLDS["pose_median_max"],
        "label_rule": measured["label_truth"] >= THRESHOLDS["label_truth_min"],
        "v1_labels": measured["v1_label_consistency"] >= THRESHOLDS["v1_label_consistency_min"],
        "v1_features": measured["v1_feature_diff_p95"] <= THRESHOLDS["v1_feature_p95_max"],
    }
    enough = hand_frames >= MIN_FRAMES and all(clips[name]["hand_frames"] for name in clips)
    verdict = "INSUFFICIENT DATA" if not enough else ("PASS" if all(checks.values()) else "FAIL")
    return {"verdict": verdict, "frames": frames, "frames_with_one_hand_in_both_paths": hand_frames, "clips": len(clips),
            "measured": measured, "checks": checks, "thresholds": THRESHOLDS}


def read_clip(path: Path, every: int, limit: int) -> Iterator:
    import cv2

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open {path}")
    try:
        index = kept = 0
        while kept < limit:
            ok, frame = capture.read()
            if not ok:
                break
            if index % every == 0:
                kept += 1
                yield frame[:, :, ::-1].copy()
            index += 1
    finally:
        capture.release()


def find_clips(folder: Path) -> list[tuple[Path, str]]:
    manifest = folder / "manifest.csv"
    if manifest.exists():
        with manifest.open(encoding="utf-8") as stream:
            return [(folder / row["file"], row["signing_hand"].strip().lower()) for row in csv.DictReader(stream)]
    clips = []
    for path in sorted(folder.iterdir()):
        prefix = path.name.split("_", 1)[0].lower()
        if prefix in ("left", "right") and path.suffix.lower() in (".mp4", ".mov", ".avi", ".mkv", ".webm"):
            clips.append((path, prefix))
    return clips


def write_reports(summary: dict, clips: dict[str, dict], out_dir: Path) -> tuple[Path, Path]:
    """Write the reports with anonymous clip labels (clip_01 ...); no file names or paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    per_clip = {f"clip_{number:02d}": {"signing_hand": r.get("signing_hand"), "frames": r["frames"], "frames_with_one_hand": r["hand_frames"]}
                for number, r in enumerate(clips.values(), 1)}
    payload = {"check": "F12 mirroring on real recordings", "measured_at": stamp, **summary, "per_clip": per_clip}
    json_path = out_dir / "f12_mirroring.json"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [f"# F12 mirroring check: {summary['verdict']}", "", f"Measured {stamp} on {summary['clips']} clips; "
             f"{summary['frames']} frames, {summary['frames_with_one_hand_in_both_paths']} with one hand in both paths.", "",
             "| Measure | Value | Check |", "|---|---|---|"]
    check_for = {"side_agreement": "side_agreement", "truth_match_unmirrored": "truth_match", "truth_match_mirrored": "truth_match",
                 "hand_shape_diff_p95": "hand_shape", "pose_diff_median": "pose_swap_rule", "label_truth": "label_rule", "v1_label_consistency": "v1_labels", "v1_feature_diff_p95": "v1_features"}
    for key, value in summary["measured"].items():
        check = check_for.get(key)
        lines.append(f"| {key} | {value:.4f} | {'' if check is None else ('PASS' if summary['checks'][check] else 'FAIL')} |")
    lines += ["", "Thresholds are starting values set before the first real measurement: " + ", ".join(f"{k} {v}" for k, v in THRESHOLDS.items()) + "."]
    md_path = out_dir / "f12_mirroring.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clips", type=Path, required=True)
    parser.add_argument("--every", type=int, default=2, help="use every Nth frame")
    parser.add_argument("--max-frames", type=int, default=150, help="frames per clip at most")
    parser.add_argument("--reports", type=Path, default=ROOT / "reports")
    args = parser.parse_args(argv)
    if ROOT == args.clips.resolve() or ROOT in args.clips.resolve().parents:
        print("Keep the clips outside the repository so video of people can never be committed. Move the folder and try again.")
        return 1
    clips = find_clips(args.clips)
    if not clips:
        print(f"No clips found in {args.clips}. Name them left_*.mp4 / right_*.mp4 or add manifest.csv.")
        return 1
    results = {}
    for path, hand in clips:
        print(f"Checking {path.name} ({hand} hand)...", flush=True)
        results[path.name] = check_clip(read_clip(path, args.every, args.max_frames), hand, SplitLandmarkerBackend)
    summary = summarise(results)
    json_path, md_path = write_reports(summary, results, args.reports)
    print(f"F12: {summary['verdict']}. Reports: {json_path}, {md_path}")
    return {"PASS": 0, "FAIL": 2}.get(summary["verdict"], 1)


if __name__ == "__main__":
    sys.exit(main())
