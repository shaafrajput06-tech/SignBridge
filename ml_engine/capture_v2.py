"""Capture v2: both hands, upper-body pose and a face subset, per frame, as canonical frames.

Uses MediaPipe's Pose, Hand and Face Landmarkers (the Python package has no Holistic
Landmarker; web/src/capture_v2.js uses the same three models). Each processed frame goes
through ``features_v2.canonicalize_frame`` so every platform stores the same thing.

Privacy: this module only keeps landmark numbers in memory. It never writes an image or a
video anywhere (tests/test_capture_v2.py checks that). Frames are rotated to upright before
landmarking, which fixes the rotated-phone-frame problem (finding F4) for any caller that
passes the camera's rotation.

Typical use:

    with CaptureV2(SplitLandmarkerBackend()) as capture:
        frame = capture.process_bgr(camera_frame, input_mirrored=False)
"""

from __future__ import annotations

import time
import urllib.request
from collections import deque
from pathlib import Path
from typing import Any, Iterable, Protocol

from ml_engine.features_v2 import SPEC, canonicalize_frame

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "models"
PARTS = ("hands", "pose", "face")
_MODEL_FOR_PART = {"hands": "hand", "pose": "pose", "face": "face"}
VALID_ROTATIONS = (0, 90, 180, 270)
DEVICE_ORIENTATION_DEGREES = {"portraitUp": 0, "landscapeLeft": 90, "portraitDown": 180, "landscapeRight": 270}


# --------------------------------------------------------------------------- rotation (F4)

def correction_rotation_degrees(sensor_orientation: int, device_orientation: str | int, lens_direction: str, platform: str = "android") -> int:
    """Clockwise rotation that makes a raw camera frame upright.

    Android follows the Camera2 rule for SENSOR_ORIENTATION: front cameras add the device
    rotation, back cameras subtract it. iOS uses the sensor orientation the camera plugin
    reports, as Google's ML Kit Flutter example does (not yet tested on an iPhone).
    mobile/lib/frame_rotation.dart implements the same rule; both are checked against
    tests/golden/rotation_cases.json.
    """
    if sensor_orientation % 90 or not 0 <= sensor_orientation < 360:
        raise ValueError(f"sensor orientation must be 0, 90, 180 or 270, got {sensor_orientation}")
    if platform == "ios":
        return sensor_orientation
    if platform != "android":
        raise ValueError(f"unknown platform {platform!r}")
    device = DEVICE_ORIENTATION_DEGREES[device_orientation] if isinstance(device_orientation, str) else int(device_orientation)
    if device not in VALID_ROTATIONS:
        raise ValueError(f"device orientation must be one of {VALID_ROTATIONS}, got {device}")
    if lens_direction == "front":
        return (sensor_orientation + device) % 360
    if lens_direction in ("back", "external"):
        return (sensor_orientation - device + 360) % 360
    raise ValueError(f"unknown lens direction {lens_direction!r}")


def _check_rotation(degrees: int) -> int:
    degrees = int(degrees) % 360
    if degrees not in VALID_ROTATIONS:
        raise ValueError(f"rotation must be a multiple of 90 degrees, got {degrees}")
    return degrees


def rotate_image_clockwise(image, degrees: int):
    """Rotate an H x W (x C) array clockwise by 0, 90, 180 or 270 degrees, without copying pixels to disk."""
    import numpy as np

    degrees = _check_rotation(degrees)
    return image if degrees == 0 else np.ascontiguousarray(np.rot90(image, k=-(degrees // 90)))


def rotate_points_clockwise(points: Iterable[Any], degrees: int) -> list[list[float]]:
    """Where normalised points land after the image is rotated clockwise (same rule as the pixels)."""
    degrees = _check_rotation(degrees)
    out = []
    for point in points:
        x, y, *rest = [float(value) for value in point]
        if degrees == 90:
            x, y = 1.0 - y, x
        elif degrees == 180:
            x, y = 1.0 - x, 1.0 - y
        elif degrees == 270:
            x, y = y, 1.0 - x
        out.append([x, y, *rest])
    return out


# --------------------------------------------------------------------------- models

def model_path(part: str, model_dir: Path = MODEL_DIR) -> Path:
    return Path(model_dir) / SPEC["capture_models"][_MODEL_FOR_PART[part]]["file"]


def ensure_capture_model(part: str, model_dir: Path = MODEL_DIR, download: bool = True) -> Path:
    """Return the model file for a part, downloading the official MediaPipe file once if allowed.

    Files listed in shared_data/downloads.json (pose and face) must match their pinned size and
    SHA-256; a different file is refused rather than used.
    """
    from data_engine.downloads import DownloadError, entry_for, fetch, verify

    path = model_path(part, model_dir)
    pinned = entry_for(path.relative_to(ROOT).as_posix()) if Path(model_dir).resolve() == MODEL_DIR.resolve() else None
    if pinned is not None:
        problem = verify(path, pinned)
        if problem is None:
            return path
        if not download:
            raise FileNotFoundError(f"{problem}. Run python tools/fetch_assets.py once with internet.")
        try:
            return fetch(pinned, root=ROOT)
        except DownloadError as error:
            raise RuntimeError(str(error)) from error
    if path.exists() and path.stat().st_size > 100_000:
        return path
    info = SPEC["capture_models"][_MODEL_FOR_PART[part]]
    if not download:
        raise FileNotFoundError(f"{path.name} is missing. Download it once from {info['url']} into {path.parent}.")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".download")
    print(f"Downloading MediaPipe {part} model {path.name} (first run only)...")
    try:
        urllib.request.urlretrieve(info["url"], temporary)
        if temporary.stat().st_size < 100_000:
            raise OSError("the downloaded model file is incomplete")
        temporary.replace(path)
    except Exception as error:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"Could not download {path.name}. Connect to the internet once, or place the file from {info['url']} in {path.parent}. Details: {error}") from error
    return path


# --------------------------------------------------------------------------- backends

class LandmarkBackend(Protocol):
    def detect(self, rgb, timestamp_ms: int) -> dict: ...

    def close(self) -> None: ...


class SplitLandmarkerBackend:
    """MediaPipe Pose + Hand + Face Landmarkers in VIDEO mode, returning raw landmark lists."""

    def __init__(self, parts: Iterable[str] = PARTS, model_dir: Path = MODEL_DIR, download: bool = True):
        import mediapipe as mp

        self.parts = tuple(parts)
        unknown = set(self.parts) - set(PARTS)
        if unknown:
            raise ValueError(f"unknown parts {sorted(unknown)}; choose from {PARTS}")
        self._mp = mp
        vision = mp.tasks.vision
        base = mp.tasks.BaseOptions
        mode = vision.RunningMode.VIDEO
        self._hands = self._pose = self._face = None
        try:
            if "hands" in self.parts:
                self._hands = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
                    base_options=base(model_asset_path=str(ensure_capture_model("hands", model_dir, download))), running_mode=mode,
                    num_hands=SPEC["capture_models"]["hand"]["num"], min_hand_detection_confidence=0.55,
                    min_hand_presence_confidence=0.5, min_tracking_confidence=0.5))
            if "pose" in self.parts:
                self._pose = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
                    base_options=base(model_asset_path=str(ensure_capture_model("pose", model_dir, download))), running_mode=mode,
                    num_poses=1, min_pose_detection_confidence=0.5, min_pose_presence_confidence=0.5,
                    min_tracking_confidence=0.5, output_segmentation_masks=False))
            if "face" in self.parts:
                self._face = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
                    base_options=base(model_asset_path=str(ensure_capture_model("face", model_dir, download))), running_mode=mode,
                    num_faces=1, min_face_detection_confidence=0.5, min_face_presence_confidence=0.5,
                    min_tracking_confidence=0.5, output_face_blendshapes=False, output_facial_transformation_matrixes=False))
        except Exception:
            self.close()
            raise

    def detect(self, rgb, timestamp_ms: int) -> dict:
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        out: dict[str, Any] = {"hands": [], "pose": None, "face": None}
        if self._hands is not None:
            result = self._hands.detect_for_video(image, timestamp_ms)
            for index, landmarks in enumerate(result.hand_landmarks or []):
                label = None
                if result.handedness and index < len(result.handedness) and result.handedness[index]:
                    label = result.handedness[index][0].category_name
                out["hands"].append({"landmarks": [[p.x, p.y, p.z] for p in landmarks], "handedness": label})
        if self._pose is not None:
            result = self._pose.detect_for_video(image, timestamp_ms)
            if result.pose_landmarks:
                out["pose"] = [[p.x, p.y, p.z, 1.0 if p.visibility is None else p.visibility] for p in result.pose_landmarks[0]]
        if self._face is not None:
            result = self._face.detect_for_video(image, timestamp_ms)
            if result.face_landmarks:
                out["face"] = [[p.x, p.y, p.z] for p in result.face_landmarks[0]]
        return out

    def close(self) -> None:
        for name in ("_hands", "_pose", "_face"):
            task = getattr(self, name, None)
            if task is not None:
                task.close()
                setattr(self, name, None)


# --------------------------------------------------------------------------- capture

class FpsMeter:
    """Frames per second over a rolling window of processed frames (wall-clock)."""

    def __init__(self, window: int = 60):
        self._times: deque[float] = deque(maxlen=window)

    def tick(self, now: float | None = None) -> None:
        self._times.append(time.perf_counter() if now is None else now)

    @property
    def fps(self) -> float:
        if len(self._times) < 2:
            return 0.0
        span = self._times[-1] - self._times[0]
        return (len(self._times) - 1) / span if span > 0 else 0.0


class CaptureV2:
    """Turn camera frames into canonical v2 frames. Keeps nothing but the last result and timing."""

    def __init__(self, backend: LandmarkBackend | None = None, *, input_mirrored: bool = False, rotation_degrees: int = 0):
        self.backend = backend if backend is not None else SplitLandmarkerBackend()
        self.input_mirrored = bool(input_mirrored)
        self.rotation_degrees = _check_rotation(rotation_degrees)
        self.meter = FpsMeter()
        self.last_raw: dict | None = None  # the last raw landmark output, kept in memory for checks such as F12
        self._start = time.monotonic()
        self._last_timestamp = -1

    def _timestamp(self, timestamp_ms: int | None) -> int:
        if timestamp_ms is None:
            timestamp_ms = int((time.monotonic() - self._start) * 1000)
        timestamp_ms = max(int(timestamp_ms), self._last_timestamp + 1)
        self._last_timestamp = timestamp_ms
        return timestamp_ms

    def process_rgb(self, rgb, timestamp_ms: int | None = None, *, input_mirrored: bool | None = None, rotation_degrees: int | None = None) -> dict:
        rotation = self.rotation_degrees if rotation_degrees is None else _check_rotation(rotation_degrees)
        upright = rotate_image_clockwise(rgb, rotation)
        height, width = upright.shape[:2]
        timestamp = self._timestamp(timestamp_ms)
        raw = self.backend.detect(upright, timestamp)
        raw.update({
            "timestamp_ms": timestamp,
            "image_width": width,
            "image_height": height,
            "input_mirrored": self.input_mirrored if input_mirrored is None else bool(input_mirrored),
        })
        frame = canonicalize_frame(raw)
        self.last_raw = raw
        self.meter.tick()
        return frame

    def process_bgr(self, frame_bgr, timestamp_ms: int | None = None, **options) -> dict:
        rgb = frame_bgr[:, :, ::-1]
        import numpy as np

        return self.process_rgb(np.ascontiguousarray(rgb), timestamp_ms, **options)

    @property
    def fps(self) -> float:
        return self.meter.fps

    def close(self) -> None:
        self.backend.close()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
