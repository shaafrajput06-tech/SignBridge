"""ASL routes of the local server (fast track Stage 2): /api/asl/status and /api/asl/predict."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def frames(count: int, hand: bool = True) -> list:
    out = []
    for t in range(count):
        frame = [[None, None, None] for _ in range(543)]
        for row in range(489, 522):  # pose
            frame[row] = [0.5 + 0.001 * row % 0.3, 0.6, 0.0]
        if hand:
            for row in range(522, 543):  # right hand
                frame[row] = [0.3 + 0.01 * math.sin(t + row), 0.6 + 0.005 * row % 0.1, -0.02]
        out.append(frame)
    return out


class AslRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from fastapi.testclient import TestClient
            from backend import app as api
        except Exception as error:  # fastapi, httpx or other server packages missing here
            raise unittest.SkipTest(f"server packages are not installed: {error}")
        cls.client = TestClient(api.app)

    def test_status_names_the_language_and_feature_version(self):
        status = self.client.get("/api/asl/status").json()
        self.assertEqual(status["sign_language"], "ASL")
        self.assertEqual(status["feature_version"], "asl-islr-543-v1")
        self.assertEqual(status["classes"], 250)
        if not status["available"]:
            self.assertTrue(status["reason"])

    def test_bad_input_is_rejected_before_the_model(self):
        for body in ({}, {"frames": []}, {"frames": [[[0, 0, 0]] * 10]}, {"frames": frames(1)[:1] * 400},
                     {"frames": [[["x", 0, 0]] * 543]}):
            with self.subTest(body=str(body)[:60]):
                self.assertEqual(self.client.post("/api/asl/predict", json=body).status_code, 422)

    def test_prediction_or_a_clear_unavailable_reply(self):
        status = self.client.get("/api/asl/status").json()
        reply = self.client.post("/api/asl/predict", json={"frames": frames(12), "scores": True})
        if not status["available"]:
            self.assertEqual(reply.status_code, 503)
            self.assertIn("not available", reply.json()["detail"])
            return
        self.assertEqual(reply.status_code, 200, reply.text)
        body = reply.json()
        self.assertEqual(body["sign_language"], "ASL")
        self.assertEqual(len(body["top"]), 5)
        self.assertEqual(len(body["scores"]), 250)
        self.assertIn(body["band"], ("sure", "unsure", "none"))
        self.assertEqual(body["frames"], 12)
        probabilities = [item["probability"] for item in body["top"]]
        self.assertEqual(probabilities, sorted(probabilities, reverse=True))


if __name__ == "__main__":
    unittest.main()
