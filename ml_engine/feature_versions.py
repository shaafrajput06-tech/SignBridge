"""The feature_version switch: which landmark features a model, recording or client uses.

v1  one frame, one hand, 63 wrist-relative values, left hands mirrored (ml_engine/features.py);
    the demo rules in ml_engine/gestures.py work on v1 landmarks. Default for every client
    until a v2 model bundle exists (Phase 3).
v2  sequences of both hands, upper-body pose and a face subset, 971 values per frame
    (ml_engine/features_v2.py, shared_data/feature_spec_v2.json); captured by ml_engine/capture_v2.py.

Every model bundle and recording names its feature version, and loaders refuse versions they do
not support (constitution rule 6). Bundles written before v2 carry no field and are v1.
"""

from __future__ import annotations

import os

SUPPORTED_FEATURE_VERSIONS = ("v1", "v2")
DEFAULT_FEATURE_VERSION = "v1"
ENVIRONMENT_VARIABLE = "SIGNBRIDGE_FEATURE_VERSION"
DESCRIPTIONS = {
    "v1": {"frames": "single", "features_per_frame": 63, "module": "ml_engine.features"},
    "v2": {"frames": "sequence", "features_per_frame": 971, "module": "ml_engine.features_v2"},
}


def resolve_feature_version(value: str | None = None) -> str:
    """The explicit value, else $SIGNBRIDGE_FEATURE_VERSION, else v1; refuses unknown versions."""
    chosen = (value or os.environ.get(ENVIRONMENT_VARIABLE) or DEFAULT_FEATURE_VERSION).strip().lower()
    if chosen not in SUPPORTED_FEATURE_VERSIONS:
        raise ValueError(f"Unsupported feature version {chosen!r}; supported: {', '.join(SUPPORTED_FEATURE_VERSIONS)}")
    return chosen


def bundle_feature_version(bundle: dict) -> str:
    return str(bundle.get("feature_version", "v1"))
