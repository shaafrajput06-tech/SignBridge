"""Shared paths, MediaPipe hand tracking, drawing, and text shaping."""

from __future__ import annotations

import os
import time
import urllib.request
from pathlib import Path

from vocabulary_utils import load_vocabulary
from ml_engine.features import normalize_landmarks

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"
HAND_MODEL_PATH = MODEL_DIR / "hand_landmarker.task"
CLASSIFIER_PATH = MODEL_DIR / "sign_classifier.joblib"
REPORT_DIR = BASE_DIR / "reports"
DATA_DIR = BASE_DIR / "data"
DATA_PATH = DATA_DIR / "sign_data.csv"
FONT_DIR = BASE_DIR / "fonts"
NUM_LANDMARKS = 21
NUM_FEATURES = NUM_LANDMARKS * 3
VOCABULARY = load_vocabulary()
VOCABULARY_BY_ID = {item["id"]: item for item in VOCABULARY}
GESTURE_TO_ID = {
    item["gestureId"]: item["id"] for item in VOCABULARY if item.get("gestureId")
}

try:
    import cv2
    import mediapipe as mp
except ImportError:
    cv2 = None
    mp = None

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = ImageDraw = ImageFont = pil_features = None

try:
    from PIL import features as pil_features
except ImportError:
    pil_features = None

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:
    arabic_reshaper = get_display = None

FORCE_ROMAN_URDU = False


def ensure_hand_model() -> None:
    if HAND_MODEL_PATH.exists() and HAND_MODEL_PATH.stat().st_size > 100_000:
        return
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
    temporary = HAND_MODEL_PATH.with_suffix(".task.download")
    print("MediaPipe hand model is missing. Downloading the official model (about 8 MB)...")

    def progress(blocks: int, block_size: int, total: int) -> None:
        if total > 0:
            percent = min(100, int(blocks * block_size * 100 / total))
            print(f"\rDownloading hand model: {percent:3d}%", end="", flush=True)

    try:
        urllib.request.urlretrieve(url, temporary, reporthook=progress)
        if temporary.stat().st_size < 100_000:
            raise OSError("The downloaded model file is incomplete.")
        temporary.replace(HAND_MODEL_PATH)
        print("\nMediaPipe hand model is ready.")
    except Exception as error:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(
            "Could not download MediaPipe's hand model. Connect to the internet once, "
            "or place the official hand_landmarker.task file in the models folder. "
            f"Details: {error}"
        ) from error


class HandResult:
    def __init__(self, landmarks: list, handedness: str, features: list[float]):
        self.landmarks = landmarks
        self.handedness = handedness
        self.features = features


class HandTracker:
    def __init__(self, num_hands: int = 1):
        if cv2 is None or mp is None:
            raise RuntimeError("Install the project dependencies with: python -m pip install -r requirements.txt")
        ensure_hand_model()
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(HAND_MODEL_PATH.resolve())),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=num_hands,
            min_hand_detection_confidence=0.55,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._detector = mp.tasks.vision.HandLandmarker.create_from_options(options)
        self._start = time.monotonic()
        self._last_timestamp = -1

    def detect(self, frame_bgr) -> HandResult | None:
        height, width = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        timestamp = max(int((time.monotonic() - self._start) * 1000), self._last_timestamp + 1)
        self._last_timestamp = timestamp
        result = self._detector.detect_for_video(image, timestamp)
        if not result.hand_landmarks:
            return None
        landmarks = result.hand_landmarks[0]
        handedness = "Right"
        if result.handedness and result.handedness[0]:
            handedness = result.handedness[0][0].category_name
        features = normalize_landmarks(landmarks, handedness)
        return HandResult(landmarks, handedness, features)

    def close(self) -> None:
        self._detector.close()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def open_camera(index: int = 0):
    if cv2 is None:
        raise RuntimeError("OpenCV is missing. Run: python -m pip install -r requirements.txt")
    camera = cv2.VideoCapture(index, cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY)
    if not camera.isOpened():
        camera.release()
        raise RuntimeError(f"Could not open camera {index}. Close other camera apps and try --camera 1.")
    return camera


def draw_hand(frame, landmarks) -> None:
    height, width = frame.shape[:2]
    points = [(int(point.x * width), int(point.y * height)) for point in landmarks]
    if mp is not None:
        connections = mp.tasks.vision.HandLandmarksConnections.HAND_CONNECTIONS
        for link in connections:
            cv2.line(frame, points[link.start], points[link.end], (76, 196, 149), 2, cv2.LINE_AA)
    for point in points:
        cv2.circle(frame, point, 4, (248, 196, 74), -1, cv2.LINE_AA)


def _supports_urdu(path: Path) -> bool:
    if ImageFont is None:
        return False
    try:
        font = ImageFont.truetype(str(path), 34)
        missing = font.getmask("\ue000").tobytes()
        return all(font.getmask(letter).tobytes() != missing for letter in "ہںیےٹ")
    except Exception:
        return False


def _font_path(urdu: bool = False):
    candidates = []
    if urdu:
        candidates += list(FONT_DIR.glob("*.ttf")) + list(FONT_DIR.glob("*.otf")) if FONT_DIR.exists() else []
    root = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    candidates += [root / name for name in (("tahoma.ttf", "arial.ttf", "segoeui.ttf") if urdu else ("segoeui.ttf", "arial.ttf"))]
    if urdu:
        return next((path for path in candidates if path.exists() and _supports_urdu(path)), None)
    return next((path for path in candidates if path.exists()), None)


def urdu_ready() -> bool:
    return bool(Image and ImageDraw and ImageFont and arabic_reshaper and get_display and _font_path(True)) and not FORCE_ROMAN_URDU


def put_texts(frame, items: list[dict]) -> None:
    if Image is None or ImageDraw is None or ImageFont is None:
        for item in items:
            cv2.putText(frame, item["text"], (int(item["x"]), int(item["y"])), cv2.FONT_HERSHEY_SIMPLEX, item.get("scale", 0.7), item.get("color", (255, 255, 255)), 2, cv2.LINE_AA)
        return
    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(image)
    latin = _font_path(False)
    for item in items:
        font_path = _font_path(True) if item.get("urdu") and urdu_ready() else latin
        if not font_path:
            continue
        size = int(item.get("size", 24))
        font = ImageFont.truetype(str(font_path), size)
        text = get_display(arabic_reshaper.reshape(item["text"])) if item.get("urdu") and urdu_ready() else item["text"]
        anchor = {"left": "la", "center": "ma", "right": "ra"}.get(item.get("align", "left"), "la")
        b, g, r = item.get("color", (255, 255, 255))
        draw.text((int(item["x"]), int(item["y"])), text, font=font, fill=(r, g, b), anchor=anchor, stroke_width=1, stroke_fill=(14, 19, 28))
    frame[:] = cv2.cvtColor(__import__("numpy").array(image), cv2.COLOR_RGB2BGR)
