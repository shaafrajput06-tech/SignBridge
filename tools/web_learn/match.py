"""Deduplicate clips and cross-check labels between independent sources (master-v3 Stage 1, steps 7-8).

Until the Stage 2 encoder exists, a clip's "embedding" is its two-hand trajectory: both hands' 21 points
relative to the signer's own body reference, resampled to a fixed length, compared with dynamic time
warping (DTW). Clips are:

- duplicates: same video file (SHA-256), or trajectories almost identical (re-uploads); duplicates never
  count as independent sources and never land on both sides of a train/test split;
- accepted: a word's clips from at least two independent sources agree (distance below the threshold);
- variant: sources disagree, but each side has two or more agreeing clips (a regional variant);
- single_source: only one independent source so far (usable as Tier B, waiting for a second source);
- rejected: disagrees with the other sources and has no support of its own.

The threshold is chosen on words whose label is already known from licensed data, and it is reported
with how many known pairs supported it. With too few known pairs the threshold is "not chosen" and no
clip is accepted by cross-checking (they stay single_source): blank is better than wrong.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence

import numpy as np

POINTS = 21
RESAMPLE = 24
DUPLICATE_DISTANCE = 0.02
MIN_KNOWN_PAIRS = 5


def trajectory(frames: Sequence[dict], length: int = RESAMPLE) -> np.ndarray:
    """length x 86: left hand (42), right hand (42), presence flags (2); body-relative, missing = 0."""
    from ml_engine.features_v2 import sequence_reference

    if not frames:
        return np.zeros((length, 4 * POINTS + 2), dtype=np.float32)
    reference = sequence_reference(frames)
    ox, oy = reference["origin"]
    scale = reference["scale"] or 1.0
    rows = []
    for frame in frames:
        w, h = frame["image_width"], frame["image_height"]
        row = []
        flags = []
        for part in ("left_hand", "right_hand"):
            points = frame.get(part)
            if points is None:
                row.extend([0.0] * (2 * POINTS))
                flags.append(0.0)
            else:
                for point in points[:POINTS]:
                    row.extend([(point[0] * w - ox) / scale, (point[1] * h - oy) / scale])
                flags.append(1.0)
        rows.append(row + flags)
    data = np.asarray(rows, dtype=np.float32)
    index = np.linspace(0, len(data) - 1, length).round().astype(int)
    return data[index]


def dtw(a: np.ndarray, b: np.ndarray) -> float:
    """Mean per-step distance along the best DTW path (scale: body-relative units)."""
    n, m = len(a), len(b)
    cost = np.full((n + 1, m + 1), np.inf)
    cost[0, 0] = 0.0
    local = np.sqrt(((a[:, None, :] - b[None, :, :]) ** 2).mean(axis=2))
    steps = np.zeros((n + 1, m + 1), dtype=np.int32)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            choices = (cost[i - 1, j - 1], cost[i - 1, j], cost[i, j - 1])
            k = int(np.argmin(choices))
            cost[i, j] = local[i - 1, j - 1] + choices[k]
            steps[i, j] = (steps[i - 1, j - 1], steps[i - 1, j], steps[i, j - 1])[k] + 1
    return float(cost[n, m] / max(1, steps[n, m]))


def deduplicate(clips: list[dict]) -> tuple[list[dict], list[dict]]:
    """clips: dicts with 'clip_id', 'video_sha256', 'trajectory'. Returns (kept, duplicates)."""
    kept, duplicates, by_hash = [], [], {}
    for clip in clips:
        twin = by_hash.get(clip.get("video_sha256"))
        if twin is None:
            twin = next((k for k in kept if dtw(k["trajectory"], clip["trajectory"]) < DUPLICATE_DISTANCE), None)
        if twin is not None:
            duplicates.append({**clip, "duplicate_of": twin["clip_id"]})
            continue
        kept.append(clip)
        if clip.get("video_sha256"):
            by_hash[clip["video_sha256"]] = clip
    return kept, duplicates


def choose_threshold(known: list[dict]) -> dict:
    """known: clips with a trusted 'gloss' and 'source_group'. Positives: same gloss, different source
    group; negatives: different glosses. Threshold: the largest distance that keeps precision >= 0.95."""
    positives, negatives = [], []
    possible = sum(1 for i, a in enumerate(known) for b in known[i + 1:] if a["gloss"] == b["gloss"] and a["source_group"] != b["source_group"])
    if possible < MIN_KNOWN_PAIRS:
        return {"known_positive_pairs": possible, "known_negative_pairs": None, "threshold": None,
                "reason": f"too few known pairs ({possible} same-sign pairs from different sources; need {MIN_KNOWN_PAIRS})"}
    for i, a in enumerate(known):
        for b in known[i + 1:]:
            distance = dtw(a["trajectory"], b["trajectory"])
            if a["gloss"] == b["gloss"] and a["source_group"] != b["source_group"]:
                positives.append(distance)
            elif a["gloss"] != b["gloss"]:
                negatives.append(distance)
    result = {"known_positive_pairs": len(positives), "known_negative_pairs": len(negatives), "threshold": None}
    if len(positives) < MIN_KNOWN_PAIRS or not negatives:
        result["reason"] = f"too few known pairs ({len(positives)} same-sign pairs from different sources; need {MIN_KNOWN_PAIRS})"
        return result
    best = None
    for t in sorted(positives):
        tp = sum(d <= t for d in positives)
        fp = sum(d <= t for d in negatives)
        if tp and tp / (tp + fp) >= 0.95:
            best = t
    if best is None:
        result["reason"] = "no threshold reaches 95 % precision on the known pairs"
        return result
    result.update(threshold=best, recall=sum(d <= best for d in positives) / len(positives),
                  precision=sum(d <= best for d in positives) / max(1, sum(d <= best for d in positives) + sum(d <= best for d in negatives)))
    return result


def cross_check(clips: list[dict], threshold: float | None) -> dict[str, str]:
    """clip_id -> label status, per gloss. clips need 'clip_id', 'gloss', 'source_group', 'trajectory'."""
    status: dict[str, str] = {}
    by_gloss: dict[str, list[dict]] = {}
    for clip in clips:
        by_gloss.setdefault(clip["gloss"], []).append(clip)
    for gloss, group in by_gloss.items():
        sources = {c["source_group"] for c in group}
        if len(sources) < 2 or threshold is None:
            for c in group:
                status[c["clip_id"]] = "single_source"
            continue
        agree = {c["clip_id"]: set() for c in group}
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                if dtw(a["trajectory"], b["trajectory"]) <= threshold:
                    agree[a["clip_id"]].add(b["clip_id"])
                    agree[b["clip_id"]].add(a["clip_id"])
        source_of = {c["clip_id"]: c["source_group"] for c in group}
        for c in group:
            others = agree[c["clip_id"]]
            if any(source_of[o] != c["source_group"] for o in others):
                status[c["clip_id"]] = "accepted"
            elif len(others) >= 1:
                status[c["clip_id"]] = "variant"   # agrees with its own source's clips only
            else:
                status[c["clip_id"]] = "rejected"
    return status
