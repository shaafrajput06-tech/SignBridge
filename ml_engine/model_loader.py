"""Safe trained-model loading with a clean rule-based fallback."""

from __future__ import annotations

from pathlib import Path

from ml_engine.feature_versions import bundle_feature_version


def load_model_bundle(path: Path, supported: tuple[str, ...] = ("v1",)):
    """Load a joblib model bundle, or return None so the caller falls back to the demo rules.

    ``supported`` lists the feature versions the caller can feed. A bundle without a
    ``feature_version`` field predates v2 and is treated as v1. The v1 clients (desktop, API)
    pass the default, so a v2 bundle is refused rather than fed the wrong features.
    """
    if not path.exists():
        return None
    try:
        import joblib
        bundle = joblib.load(path)
        if not isinstance(bundle, dict) or "model" not in bundle:
            return None
        if not hasattr(bundle["model"], "predict"):
            return None
        if bundle_feature_version(bundle) not in supported:
            return None
        return bundle
    except Exception:
        return None
