"""The PSL bundle in Python (local server, tools and tests): models/psl/manifest.json + the TFLite file.

Refuses a bundle whose feature version it does not support or whose model file does not match the
manifest's SHA-256 (CLAUDE.md 6). Runs the model with LiteRT (ai-edge-litert), or TensorFlow's
interpreter if that is what is installed. Builds exactly the input web/src/psl_hands.js builds.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from ml_engine import psl_hands

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "models" / "psl"
SUPPORTED_FEATURE_VERSIONS = ("psl-hands-v1",)


class BundleError(RuntimeError):
    pass


def load_manifest(folder: Path = BUNDLE) -> dict:
    path = Path(folder) / "manifest.json"
    if not path.exists():
        raise BundleError(f"no PSL bundle at {folder}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("bundle") != "signbridge-psl" or manifest.get("sign_language") != "PSL":
        raise BundleError("not a SignBridge PSL bundle")
    if manifest.get("feature_version") not in SUPPORTED_FEATURE_VERSIONS:
        raise BundleError(f"unsupported PSL feature version {manifest.get('feature_version')}")
    if manifest["input"]["shape"] != [psl_hands.FRAMES, psl_hands.ROWS_PER_FRAME, 3]:
        raise BundleError(f"unexpected input shape {manifest['input']['shape']}")
    if len(manifest["classes"]) != manifest["output"]["shape"][0]:
        raise BundleError("class list and model output disagree")
    return manifest


def _interpreter(model_bytes: bytes):
    try:
        from ai_edge_litert.interpreter import Interpreter
    except ImportError:
        try:
            from tensorflow.lite import Interpreter  # type: ignore[no-redef]
        except ImportError as error:
            raise BundleError("install ai-edge-litert to run the PSL model in Python") from error
    interpreter = Interpreter(model_content=model_bytes)
    interpreter.allocate_tensors()
    return interpreter


class PslModel:
    def __init__(self, folder: Path = BUNDLE):
        self.folder = Path(folder)
        self.manifest = load_manifest(self.folder)
        blob = (self.folder / self.manifest["model"]["file"]).read_bytes()
        digest = hashlib.sha256(blob).hexdigest()
        if digest != self.manifest["model"]["sha256"]:
            raise BundleError(f"the PSL model file is not the one in the manifest (SHA-256 {digest})")
        self.interpreter = _interpreter(blob)
        self._in = self.interpreter.get_input_details()[0]["index"]
        self._out = self.interpreter.get_output_details()[0]["index"]

    def input_from_frames(self, frames: np.ndarray, aspect: float) -> np.ndarray:
        """A cut-out sign as baseline frames (T, 543, 3), NaN for missing -> the model input (32, 543, 3)."""
        frames = np.asarray(frames, dtype=np.float64)
        fixed = frames[psl_hands.resample_indices(len(frames), psl_hands.FRAMES)].copy()
        for rows in (psl_hands.LEFT_ROWS, psl_hands.RIGHT_ROWS):
            fixed[:, rows] = psl_hands.adjust_aspect(fixed[:, rows], aspect)
        return fixed.astype(np.float32)

    def scores(self, model_input: np.ndarray) -> np.ndarray:
        self.interpreter.set_tensor(self._in, np.asarray(model_input, dtype=np.float32))
        self.interpreter.invoke()
        return self.interpreter.get_tensor(self._out).copy()

    def predict(self, frames: np.ndarray, aspect: float, k: int = 5) -> dict:
        scores = self.scores(self.input_from_frames(frames, aspect))
        p = np.exp(scores - scores.max())
        p /= p.sum()
        order = np.argsort(-p)[:k]
        top = [{**self.manifest["classes"][i], "probability": float(p[i])} for i in order]
        first = top[0]
        conf = self.manifest["confidence"]
        if first["gloss"] == self.manifest.get("unknown_class"):
            band = "none"
        else:
            band = "sure" if first["probability"] >= conf["sure"] else "unsure" if first["probability"] >= conf["unsure"] else "none"
        return {"top": top, "band": band}
