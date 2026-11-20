"""Turn one licensed video into landmarks (master-v3 Stage 1, steps 4-5).

Capture v2 (both hands + pose + face, the same models as the app) runs on every frame (at most 30 per
second). The video itself is not kept: only canonical landmark frames are written, in recording format
v2 (source "licensed_clip"). Quality numbers are measured on the way so the filter can explain every
rejection in plain words.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

MAX_FPS = 30.0
FACE_COUNT_EVERY = 10  # count faces (a second person?) on every 10th frame


@dataclass
class Quality:
    frames: int = 0
    seconds: float = 0.0
    hand_frames: int = 0
    two_hand_frames: int = 0
    pose_frames: int = 0
    multi_person_checks: int = 0
    multi_person_hits: int = 0
    cuts: int = 0
    shoulder_width_median: float | None = None   # fraction of the frame width
    sharpness_median: float | None = None        # variance of the Laplacian on a 320-px-wide grey frame
    width: int = 0
    height: int = 0
    segment: list[int] = field(default_factory=list)  # [first, last] frame of the sign after trimming

    def to_dict(self) -> dict:
        return asdict(self)


def _median(values: list[float]) -> float | None:
    values = sorted(v for v in values if v is not None and math.isfinite(v))
    if not values:
        return None
    mid = len(values) // 2
    return values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2


def shoulder_width(frame: dict) -> float | None:
    """Distance between the pose shoulders as a fraction of the frame width (raw capture frame)."""
    pose = frame.get("pose")
    if not pose or len(pose) < 13:
        return None
    (lx, ly), (rx, ry) = pose[11][:2], pose[12][:2]
    return math.hypot(lx - rx, ly - ry)


def trim_to_sign(hand_present: list[bool], margin: int = 2, min_hand_frames: int = 6) -> list[int]:
    """[first, last] frames of the longest run with hands (gaps of up to 8 frames bridged), or []."""
    best, start, gap, hands, run_hands = [], None, 0, 0, 0
    for index, present in enumerate(hand_present + [False] * 9):
        if present:
            if start is None:
                start, run_hands = index, 0
            gap = 0
            run_hands += 1
            last = index
        elif start is not None:
            gap += 1
            if gap > 8:
                if run_hands >= min_hand_frames and (not best or last - start > best[1] - best[0]):
                    best, hands = [start, last], run_hands
                start = None
    if not best:
        return []
    return [max(0, best[0] - margin), min(len(hand_present) - 1, best[1] + margin)]


_CLOCK: dict[int, int] = {}  # last timestamp given to each shared backend (MediaPipe video mode needs them increasing)


def make_face_counter(model_path: Path | None = None):
    """A callable(rgb) -> number of faces (up to 2), for the second-person check, or None if unavailable."""
    try:
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions
        from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions, RunningMode
    except ImportError:
        return None
    model_path = Path(model_path or Path(__file__).resolve().parents[2] / "models" / "face_landmarker.task")
    if not model_path.is_file():
        return None
    landmarker = FaceLandmarker.create_from_options(FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path)), running_mode=RunningMode.IMAGE, num_faces=2))

    def count(rgb) -> int:
        import numpy as np

        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        return len(landmarker.detect(image).face_landmarks)

    return count


def extract_video(path: Path, *, backend=None, face_counter=None) -> tuple[list[dict], list[dict], Quality]:
    """Return (raw capture frames, canonical frames, quality) for the trimmed sign in one video file.

    backend: a capture v2 LandmarkBackend shared across videos (default: a new MediaPipe
    SplitLandmarkerBackend for this video). face_counter: callable(rgb) -> number of faces, or None.
    """
    import cv2

    from ml_engine.capture_v2 import CaptureV2, SplitLandmarkerBackend

    video = cv2.VideoCapture(str(path))
    if not video.isOpened():
        raise ValueError("the video cannot be opened")
    fps = video.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(1, round(fps / MAX_FPS))
    quality = Quality()
    raws: list[dict] = []
    canon: list[dict] = []
    widths: list[float] = []
    sharpness: list[float] = []
    previous_hist = None
    own_backend = backend is None
    capture = CaptureV2(backend or SplitLandmarkerBackend(), input_mirrored=False)
    offset = _CLOCK.get(id(capture.backend), -1) + 1 if not own_backend else 0
    try:
        index = 0
        while True:
            ok, frame_bgr = video.read()
            if not ok:
                break
            if index % step:
                index += 1
                continue
            timestamp = offset + int(round(index * 1000.0 / fps))
            index += 1
            height, width = frame_bgr.shape[:2]
            quality.width, quality.height = width, height
            small = cv2.resize(frame_bgr, (320, max(1, int(320 * height / width))))
            grey = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            sharpness.append(float(cv2.Laplacian(grey, cv2.CV_64F).var()))
            hist = cv2.calcHist([small], [0, 1, 2], None, [8, 8, 8], [0, 256] * 3)
            hist = cv2.normalize(hist, hist).flatten()
            if previous_hist is not None and cv2.compareHist(previous_hist, hist, cv2.HISTCMP_BHATTACHARYYA) > 0.5:
                quality.cuts += 1
            previous_hist = hist
            canonical = capture.process_bgr(frame_bgr, timestamp_ms=timestamp)
            raw = capture.last_raw if hasattr(capture, "last_raw") else {}
            raws.append(raw)
            canon.append(canonical)
            hands = int(canonical.get("left_hand") is not None) + int(canonical.get("right_hand") is not None)
            quality.hand_frames += hands > 0
            quality.two_hand_frames += hands == 2
            quality.pose_frames += canonical.get("pose") is not None
            width_value = shoulder_width(raw)
            if width_value is not None:
                widths.append(width_value)
            if face_counter is not None and (len(canon) - 1) % FACE_COUNT_EVERY == 0:
                quality.multi_person_checks += 1
                quality.multi_person_hits += face_counter(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)) > 1
    finally:
        video.release()
        if own_backend:
            capture.close()
        elif canon:
            _CLOCK[id(capture.backend)] = canon[-1]["timestamp_ms"] + 1000
    quality.frames = len(canon)
    quality.seconds = round(quality.frames * step / fps, 2) if fps else 0.0
    quality.shoulder_width_median = _median(widths)
    quality.sharpness_median = _median(sharpness)
    quality.segment = trim_to_sign([c.get("left_hand") is not None or c.get("right_hand") is not None for c in canon])
    if quality.segment:
        first, last = quality.segment
        raws, canon = raws[first:last + 1], canon[first:last + 1]
    return raws, canon, quality


# Quality rules (master-v3 Stage 1, step 5). Each returns a plain-words reason, or None.
def rejection_reasons(quality: Quality) -> list[str]:
    reasons = []
    if quality.frames < 8:
        reasons.append(f"too short ({quality.frames} frames)")
    if quality.frames and quality.hand_frames / quality.frames < 0.4:
        reasons.append(f"no hands in most frames ({quality.hand_frames} of {quality.frames})")
    if not quality.segment:
        reasons.append("no sign found (no run of 6+ frames with hands)")
    if quality.multi_person_checks and quality.multi_person_hits / quality.multi_person_checks > 0.3:
        reasons.append("more than one person in view")
    if quality.cuts > 2:
        reasons.append(f"heavy editing ({quality.cuts} cuts)")
    if quality.shoulder_width_median is not None and quality.shoulder_width_median < 0.08:
        reasons.append("signer too small in the frame")
    if quality.pose_frames == 0:
        reasons.append("no upper body in view (wrong framing)")
    if quality.sharpness_median is not None and quality.sharpness_median < 15:
        reasons.append("too blurred")
    return reasons
