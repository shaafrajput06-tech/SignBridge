"""SignBridge local REST API. SQLite and training landmarks stay on this computer."""
from __future__ import annotations
import csv, json, threading, uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import joblib
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field
from backend.storage import RecognitionHistory, SessionLocal, Setting, TrainingExample, engine, initialize_database
from ml_engine.feature_versions import bundle_feature_version

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CSV_PATH = DATA_DIR / "sign_data.csv"
MODEL_PATH = ROOT / "models" / "sign_classifier.joblib"
METADATA_PATH = ROOT / "models" / "model_metadata.json"
REPORT_PATH = ROOT / "reports" / "training_report.txt"
MATRIX_PATH = ROOT / "reports" / "confusion_matrix.csv"
VOCAB_PATH = ROOT / "vocabulary.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CSV_COLUMNS = ["label", "participant", "session_id", "timestamp_utc", "frame_index", "frame_width", "frame_height", "handedness"] + [f"f{i}" for i in range(63)]
MODEL_LOCK = threading.Lock()
FRAME_LOCK = threading.Lock()
FRAME_DETECTOR = None

app = FastAPI(title="SignBridge API", version="1.0.0", description="Local vocabulary, training, model, settings, history, and camera inference API.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["GET", "POST", "PUT", "OPTIONS"], allow_headers=["*"])


initialize_database()


class SettingsUpdate(BaseModel):
    language: str | None = None
    roman_urdu: bool | None = None
    voice_enabled: bool | None = None


class LandmarkRecording(BaseModel):
    vocabulary_id: str
    participant: str = "anonymous"
    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    features: list[float]
    frame_index: int = 0
    frame_width: int = 0
    frame_height: int = 0
    handedness: str = "Unknown"
    timestamp_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="milliseconds"))


class RecordingBatch(BaseModel):
    consent: bool
    examples: list[LandmarkRecording]


class HistoryEntry(BaseModel):
    vocabulary_id: str
    language: str = "en"
    source: str = "camera"


def vocabulary() -> list[dict[str, Any]]:
    try:
        items = json.loads(VOCAB_PATH.read_text(encoding="utf-8-sig"))
        if len({item["id"] for item in items}) != len(items):
            raise ValueError("Vocabulary IDs must be unique")
        return items
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Vocabulary could not be loaded: {error}") from error


def model_bundle() -> dict[str, Any] | None:
    if not MODEL_PATH.exists():
        return None
    try:
        with MODEL_LOCK:
            bundle = joblib.load(MODEL_PATH)
    except Exception:
        return None
    # The API feeds v1 features; refuse a bundle trained on another feature version (rule 6).
    if isinstance(bundle, dict) and bundle_feature_version(bundle) != "v1":
        return None
    return bundle


def append_csv(example: LandmarkRecording) -> None:
    row = [example.vocabulary_id, example.participant or "anonymous", example.session_id, example.timestamp_utc, str(example.frame_index), str(example.frame_width), str(example.frame_height), example.handedness] + [f"{float(value):.8f}" for value in example.features]
    exists = CSV_PATH.exists()
    with CSV_PATH.open("a", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        if not exists:
            writer.writerow(CSV_COLUMNS)
        writer.writerow(row)


@app.get("/api/health")
def health():
    bundle = model_bundle()
    return {"status": "ok", "service": "SignBridge API", "database": engine.dialect.name, "recognition_mode": "AI Trained Mode" if bundle else "AI Demo Mode", "model_available": bool(bundle), "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}


@app.get("/api/vocabulary")
def get_vocabulary(search: str = "", category: str = "", page: int = 1, page_size: int = 64):
    items = vocabulary()
    query = search.casefold().strip()
    filtered = [item for item in items if (not category or item["category"] == category) and (not query or query in " ".join((item["english"], item["urdu"], item["romanUrdu"], item["category"])).casefold())]
    page, page_size = max(1, page), min(128, max(1, page_size))
    start = (page - 1) * page_size
    return {"items": filtered[start:start + page_size], "total": len(filtered), "page": page, "page_size": page_size, "categories": sorted({item["category"] for item in items})}


@app.get("/api/vocabulary/{vocabulary_id}")
def get_vocabulary_item(vocabulary_id: str):
    found = next((item for item in vocabulary() if item["id"] == vocabulary_id), None)
    if found is None:
        raise HTTPException(status_code=404, detail="Vocabulary item was not found")
    return found


@app.get("/api/settings")
def get_settings():
    values: dict[str, Any] = {"language": "en", "roman_urdu": False, "voice_enabled": True}
    with SessionLocal() as db:
        for row in db.query(Setting).all():
            values[row.key] = json.loads(row.value)
    return values


@app.put("/api/settings")
def update_settings(update: SettingsUpdate):
    data = update.model_dump(exclude_none=True)
    if data.get("language") not in (None, "en", "ur"):
        raise HTTPException(status_code=422, detail="language must be en or ur")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with SessionLocal() as db:
        for key, value in data.items():
            row = db.get(Setting, key)
            if row is None:
                db.add(Setting(key=key, value=json.dumps(value), updated_at=now))
            else:
                row.value = json.dumps(value)
                row.updated_at = now
        db.commit()
    return get_settings()


@app.get("/api/model-status")
def get_model_status():
    bundle = model_bundle()
    if not bundle:
        return {"available": False, "mode": "AI Demo Mode", "model_name": None, "accuracy": None, "evaluation_method": None, "classes": []}
    metadata = {}
    if METADATA_PATH.exists():
        try:
            metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"available": True, "mode": "AI Trained Mode", "model_name": metadata.get("model_name", bundle.get("model_name")), "accuracy": metadata.get("accuracy", bundle.get("accuracy")), "evaluation_method": metadata.get("evaluation_method", bundle.get("evaluation_method")), "trained_at": metadata.get("trained_at", bundle.get("trained_at")), "examples": metadata.get("n_examples", bundle.get("n_examples", 0)), "classes": metadata.get("vocabulary_ids", bundle.get("vocabulary_ids", [])), "class_counts": metadata.get("class_counts", bundle.get("class_counts", {}))}


@app.get("/api/training-report", response_class=PlainTextResponse)
def training_report():
    return REPORT_PATH.read_text(encoding="utf-8") if REPORT_PATH.exists() else "No training report is available. Record examples and run python train_model.py."


@app.get("/api/training-counts")
def training_counts():
    counts = Counter()
    if CSV_PATH.exists():
        with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream)
            if next(reader, None) == CSV_COLUMNS:
                known = {item["id"] for item in vocabulary()}
                for row in reader:
                    if len(row) == len(CSV_COLUMNS) and row[0] in known:
                        counts[row[0]] += 1
    return dict(counts)


@app.get("/api/confusion-matrix.csv")
def confusion_matrix_file():
    if not MATRIX_PATH.exists():
        raise HTTPException(status_code=404, detail="No evaluated confusion matrix is available")
    return FileResponse(MATRIX_PATH, media_type="text/csv", filename="confusion_matrix.csv")


@app.get("/api/training-data.csv")
def training_data_export():
    if not CSV_PATH.exists():
        raise HTTPException(status_code=404, detail="No training examples have been saved")
    return FileResponse(CSV_PATH, media_type="text/csv", filename="signbridge_training_data.csv")


@app.post("/api/recordings")
def upload_recordings(batch: RecordingBatch):
    if not batch.consent:
        raise HTTPException(status_code=400, detail="Explicit consent is required before saving training landmarks")
    known = {item["id"] for item in vocabulary()}
    for example in batch.examples:
        if example.vocabulary_id not in known:
            raise HTTPException(status_code=422, detail=f"Unknown vocabulary ID: {example.vocabulary_id}")
        if len(example.features) != 63 or not np.isfinite(np.asarray(example.features, dtype=float)).all():
            raise HTTPException(status_code=422, detail="Each example must contain 63 finite normalized features")
    try:
        with SessionLocal() as db:
            for example in batch.examples:
                db.add(TrainingExample(vocabulary_id=example.vocabulary_id, participant=example.participant or "anonymous", session_id=example.session_id, features_json=json.dumps(example.features), created_at=example.timestamp_utc))
                append_csv(example)
            db.commit()
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Training data could not be saved: {error}") from error
    return {"saved": len(batch.examples), "video_saved": False, "message": "Only landmark coordinates and optional participant name were saved locally."}


@app.post("/api/history")
def add_history(entry: HistoryEntry):
    if entry.vocabulary_id not in {item["id"] for item in vocabulary()} or entry.language not in ("en", "ur"):
        raise HTTPException(status_code=422, detail="Unknown vocabulary item or unsupported language")
    created = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    with SessionLocal() as db:
        result = RecognitionHistory(vocabulary_id=entry.vocabulary_id, language=entry.language, source=entry.source, created_at=created)
        db.add(result)
        db.commit()
        record_id = result.id
    return {"id": record_id, "vocabulary_id": entry.vocabulary_id, "language": entry.language, "source": entry.source, "created_at": created}


@app.get("/api/history")
def get_history(limit: int = 100):
    with SessionLocal() as db:
        rows = db.query(RecognitionHistory).order_by(RecognitionHistory.id.desc()).limit(min(500, max(1, limit))).all()
    return [{"id": row.id, "vocabulary_id": row.vocabulary_id, "language": row.language, "source": row.source, "created_at": row.created_at} for row in rows]


@app.post("/api/predict")
def predict_landmarks(body: dict[str, Any]):
    bundle = model_bundle()
    if not bundle:
        raise HTTPException(status_code=409, detail="No trained classifier is available. Use AI Demo Mode.")
    features = body.get("features")
    if not isinstance(features, list) or len(features) != 63:
        raise HTTPException(status_code=422, detail="features must contain 63 values")
    try:
        array = np.asarray(features, dtype=np.float32)
        if not np.isfinite(array).all():
            raise ValueError("Features must be finite")
        model = bundle["model"]
        label = str(model.predict([array])[0])
        result = {"vocabulary_id": label, "mode": "AI Trained Mode", "status": "trained model prediction"}
        if bundle.get("has_calibrated_probabilities") and hasattr(model, "predict_proba"):
            probabilities = model.predict_proba([array])[0]
            result["calibrated_probability"] = float(probabilities[list(model.classes_).index(label)])
        return result
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"Model prediction failed: {error}") from error


@app.post("/api/recognize-frame")
async def recognize_frame(request: Request):
    """Process one transient mobile-camera JPEG; never persist image bytes."""
    try:
        import cv2
        import mediapipe as mp
        from ml_engine.features import normalize_landmarks
        from ml_engine.gestures import classify_gesture
        from signbridge_common import GESTURE_TO_ID, HAND_MODEL_PATH, ensure_hand_model
    except ImportError as error:
        raise HTTPException(status_code=503, detail="Install MediaPipe and OpenCV to use camera recognition.") from error
    payload = await request.body()
    image = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=415, detail="The request body is not a readable JPEG camera frame")
    global FRAME_DETECTOR
    try:
        ensure_hand_model()
        with FRAME_LOCK:
            if FRAME_DETECTOR is None:
                options = mp.tasks.vision.HandLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(HAND_MODEL_PATH)), running_mode=mp.tasks.vision.RunningMode.IMAGE, num_hands=1)
                FRAME_DETECTOR = mp.tasks.vision.HandLandmarker.create_from_options(options)
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            result = FRAME_DETECTOR.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
        if not result.hand_landmarks:
            return {"hand_detected": False, "vocabulary_id": None, "mode": "AI Demo Mode", "status": "Show a hand to the camera"}
        landmarks = result.hand_landmarks[0]
        gesture_id = classify_gesture(landmarks)
        vocabulary_id = GESTURE_TO_ID.get(gesture_id)
        bundle = model_bundle()
        if bundle:
            handedness = result.handedness[0][0].category_name if result.handedness and result.handedness[0] else "Right"
            features = normalize_landmarks(landmarks, handedness)
            vocabulary_id = str(bundle["model"].predict([features])[0])
            return {"hand_detected": True, "vocabulary_id": vocabulary_id, "gesture_id": gesture_id, "features": features, "landmarks": [[point.x, point.y] for point in landmarks], "mode": "AI Trained Mode", "status": "trained model prediction"}
        handedness = result.handedness[0][0].category_name if result.handedness and result.handedness[0] else "Right"
        features = normalize_landmarks(landmarks, handedness)
        return {"hand_detected": True, "vocabulary_id": vocabulary_id, "gesture_id": gesture_id, "features": features, "landmarks": [[point.x, point.y] for point in landmarks], "mode": "AI Demo Mode", "status": "Rule-based match" if vocabulary_id else "Not sure — pose is outside the demo set"}
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"Camera frame processing failed: {error}") from error



# --------------------------------------------------------------------------- ASL mode (fast track Stage 2)
# ASL is a separate language mode (CLAUDE.md 8.2). These routes take landmark numbers only (frames x 543 x 3,
# null where a part is missing), never images, and run the ASL model with its real frame count.
ASL_LOCK = threading.Lock()
ASL_STATE: dict[str, Any] = {"recogniser": None}
ASL_MAX_FRAMES = 384


def asl_recogniser():
    """The loaded ASL model, or (None, reason). Success is cached; a failure is retried on the next call."""
    with ASL_LOCK:
        if ASL_STATE["recogniser"] is not None:
            return ASL_STATE["recogniser"], None
        try:
            from ml_engine.asl_islr import AslRecognizer
            ASL_STATE["recogniser"] = AslRecognizer()
            return ASL_STATE["recogniser"], None
        except Exception as error:
            return None, str(error)


@app.get("/api/asl/status")
def asl_status():
    from ml_engine.asl_islr import SPEC as ASL_SPEC
    recogniser, reason = asl_recogniser()
    return {"available": recogniser is not None, "reason": reason, "runtime": getattr(recogniser, "runtime", None),
            "sign_language": "ASL", "feature_version": ASL_SPEC["feature_version"], "classes": ASL_SPEC["classes"]["count"],
            "model_sha256": ASL_SPEC["model"]["sha256"]}


@app.post("/api/asl/predict")
def asl_predict(body: dict[str, Any]):
    import time

    from ml_engine.asl_islr import ROWS, confidence_band, top_k
    frames = body.get("frames")
    if not isinstance(frames, list) or not 1 <= len(frames) <= ASL_MAX_FRAMES:
        raise HTTPException(status_code=422, detail=f"frames must be a list of 1 to {ASL_MAX_FRAMES} frames")
    try:
        array = np.array(frames, dtype=object)
        if array.shape != (len(frames), ROWS, 3):
            raise ValueError(f"expected frames x {ROWS} x 3, got {array.shape}")
        missing = np.equal(array, None)
        array[missing] = np.nan
        sequence = array.astype(np.float32)
        if np.isinf(sequence).any():
            raise ValueError("values must be finite numbers or null")
    except (ValueError, TypeError) as error:
        raise HTTPException(status_code=422, detail=f"frames could not be read: {error}") from error
    recogniser, reason = asl_recogniser()
    if recogniser is None:
        raise HTTPException(status_code=503, detail=f"ASL mode is not available on the server: {reason}")
    started = time.perf_counter()
    with ASL_LOCK:
        scores = recogniser.scores(sequence)
    elapsed = (time.perf_counter() - started) * 1000
    top = top_k(scores, recogniser.labels, 5)
    reply = {"top": top, "band": confidence_band(top[0]["probability"]), "frames": int(sequence.shape[0]), "ms": elapsed,
             "runtime": recogniser.runtime, "sign_language": "ASL"}
    if body.get("scores"):
        reply["scores"] = scores
    return reply
