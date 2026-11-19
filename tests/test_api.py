import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
except ImportError as error:
    raise unittest.SkipTest(f"API integration dependencies are not installed: {error}")

_temporary = tempfile.TemporaryDirectory(prefix="signbridge-api-tests-")
_database = Path(_temporary.name) / "api-tests.sqlite3"
os.environ["SIGNBRIDGE_DATABASE_URL"] = f"sqlite:///{_database.as_posix()}"
storage = importlib.import_module("backend.storage")
api = importlib.import_module("backend.app")


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_session_factory = api.SessionLocal
        cls.original_csv = api.CSV_PATH
        cls.original_model = api.MODEL_PATH
        cls.original_metadata = api.METADATA_PATH
        cls.test_engine = create_engine(f"sqlite:///{_database.as_posix()}", connect_args={"check_same_thread": False})
        api.SessionLocal = sessionmaker(bind=cls.test_engine, autoflush=False, expire_on_commit=False)
        api.CSV_PATH = Path(_temporary.name) / "sign_data.csv"
        api.MODEL_PATH = Path(_temporary.name) / "missing-model.joblib"
        api.METADATA_PATH = Path(_temporary.name) / "missing-metadata.json"
        cls.client = TestClient(api.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        api.SessionLocal = cls.original_session_factory
        api.CSV_PATH = cls.original_csv
        api.MODEL_PATH = cls.original_model
        api.METADATA_PATH = cls.original_metadata
        cls.test_engine.dispose()
        storage.engine.dispose()
        _temporary.cleanup()

    def setUp(self):
        with api.SessionLocal() as db:
            db.query(storage.Setting).delete()
            db.query(storage.RecognitionHistory).delete()
            db.query(storage.TrainingExample).delete()
            db.commit()
        api.CSV_PATH.unlink(missing_ok=True)

    def test_health_and_vocabulary_search(self):
        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["database"], "sqlite")
        vocabulary = self.client.get("/api/vocabulary", params={"search": "Shukriya"})
        self.assertEqual(vocabulary.status_code, 200)
        self.assertEqual(vocabulary.json()["items"][0]["id"], "thank_you")

    def test_settings_and_history_sync(self):
        settings = self.client.put("/api/settings", json={"language": "ur", "roman_urdu": True})
        self.assertEqual(settings.status_code, 200)
        self.assertEqual(self.client.get("/api/settings").json()["language"], "ur")
        entry = self.client.post("/api/history", json={"vocabulary_id": "hello", "language": "ur", "source": "mobile"})
        self.assertEqual(entry.status_code, 200)
        self.assertEqual(self.client.get("/api/history").json()[0]["vocabulary_id"], "hello")

    def test_training_upload_requires_consent_and_writes_valid_csv(self):
        example = {"vocabulary_id": "hello", "participant": "anonymous", "session_id": "test-session", "features": [0.0] * 63}
        denied = self.client.post("/api/recordings", json={"consent": False, "examples": [example]})
        self.assertEqual(denied.status_code, 400)
        saved = self.client.post("/api/recordings", json={"consent": True, "examples": [example]})
        self.assertEqual(saved.status_code, 200)
        self.assertFalse(saved.json()["video_saved"])
        self.assertEqual(self.client.get("/api/training-counts").json()["hello"], 1)
        self.assertTrue(api.CSV_PATH.exists())

    def test_postgres_without_optional_driver_gives_install_hint(self):
        import subprocess
        import sys
        try:
            import psycopg  # noqa: F401
            self.skipTest("psycopg is installed, so the missing-driver message cannot be shown")
        except ImportError:
            pass
        environment = dict(os.environ, SIGNBRIDGE_DATABASE_URL="postgresql+psycopg://user:pass@127.0.0.1:1/signbridge")
        completed = subprocess.run([sys.executable, "-c", "import backend.storage"], cwd=Path(__file__).resolve().parents[1], env=environment, capture_output=True, text=True)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("requirements-postgres.txt", completed.stderr)

    def test_prediction_falls_back_when_model_is_missing(self):
        response = self.client.post("/api/predict", json={"features": [0.0] * 63})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.get("/api/model-status").json()["available"], False)

    def test_current_predict_returns_a_label_even_when_the_model_is_unsure(self):
        """Known limit (Phase 3, audit P0-3): /api/predict reports a probability but never rejects."""
        import joblib
        from sklearn.dummy import DummyClassifier
        model = DummyClassifier(strategy="prior").fit([[0.0] * 63] * 3, ["hello", "no", "please"])
        bundle_path = Path(_temporary.name) / "uniform-model.joblib"
        joblib.dump({"model": model, "classes": ["hello", "no", "please"], "has_calibrated_probabilities": True}, bundle_path)
        api.MODEL_PATH = bundle_path
        try:
            response = self.client.post("/api/predict", json={"features": [0.0] * 63})
        finally:
            api.MODEL_PATH = Path(_temporary.name) / "missing-model.joblib"
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn(body["vocabulary_id"], {"hello", "no", "please"})
        self.assertLess(body["calibrated_probability"], 0.5)

    def test_predict_rejects_wrong_feature_count(self):
        response = self.client.post("/api/predict", json={"features": [0.0] * 62})
        self.assertIn(response.status_code, (409, 422))

    def test_recognize_frame_without_a_hand_and_with_a_bad_body(self):
        try:
            import cv2
            import mediapipe  # noqa: F401
            import numpy as np
        except ImportError as error:
            self.skipTest(f"camera recognition dependencies are not installed: {error}")
        ok, jpeg = cv2.imencode(".jpg", np.full((240, 320, 3), 128, np.uint8))
        self.assertTrue(ok)
        response = self.client.post("/api/recognize-frame", content=jpeg.tobytes(), headers={"Content-Type": "image/jpeg"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["hand_detected"], False)
        self.assertEqual(response.json()["mode"], "AI Demo Mode")
        bad = self.client.post("/api/recognize-frame", content=b"not an image", headers={"Content-Type": "image/jpeg"})
        self.assertEqual(bad.status_code, 415)


if __name__ == "__main__":
    unittest.main()
