"""A two-minute check before the long training: an untrained model goes through the whole export and
must give the same answers in Keras (numpy features) and in TFLite (543-point input with NaN, features
inside the model) for every precision. Also prints the TFLite operators the bundle needs.

    python -m tools.psl_train.smoke
"""

from __future__ import annotations

import numpy as np

from ml_engine import psl_hands
from tools.psl_train import graph
from tools.psl_train.train import softmax


def sample_hands(rng: np.random.Generator, n: int) -> np.ndarray:
    base = rng.uniform(0.3, 0.7, (n, 1, 2, 1, 2))
    hands = np.empty((n, psl_hands.FRAMES, 2, 21, 3))
    hands[..., :2] = base + rng.normal(0, 0.05, (n, psl_hands.FRAMES, 2, 21, 2))
    hands[..., 2] = rng.normal(0, 0.03, (n, psl_hands.FRAMES, 2, 21))
    hands[0, :, 0] = np.nan  # one-handed
    hands[1, 3:7, 1] = np.nan  # a hand lost for a moment
    hands[2, :4] = np.nan  # no hands at the start
    return hands.astype(np.float32)


def main() -> int:
    import tensorflow as tf

    rng = np.random.default_rng(3)
    hands = sample_hands(rng, 8)
    reference = psl_hands.features(hands)
    in_graph = graph.hands_features(graph.to_rows(hands)).numpy()
    diff = float(np.abs(reference - in_graph).max())
    print(f"features: numpy vs TensorFlow max difference {diff:.2e}")
    assert diff < 1e-4, diff
    mirrored = graph.mirror_rows(graph.to_rows(hands)).numpy().reshape(hands.shape)
    assert np.allclose(np.nan_to_num(mirrored, nan=9), np.nan_to_num(psl_hands.mirror(hands), nan=9), atol=1e-6)

    model = graph.islr_lite(7)
    for mirror_average in (False, True):
        module = graph.Export(model, 1.3, mirror_average)
        keras_p = softmax(model.predict(reference, verbose=0), 1.3)
        if mirror_average:
            keras_p = (keras_p + softmax(model.predict(psl_hands.features(psl_hands.mirror(hands)), verbose=0), 1.3)) / 2
        for kind in ("float32", "float16", "int8"):
            blob = graph.to_tflite(module, kind)
            run, io = graph.tflite_runner(blob)
            scores = np.stack([run(psl_hands.to_islr(h)) for h in hands])
            p = softmax(scores)
            gap = float(np.abs(p - keras_p).max())
            print(f"mirror_average={mirror_average} {kind}: {len(blob):,} bytes, io {io}, max probability difference {gap:.2e}, "
                  f"same top-1 {np.mean(p.argmax(1) == keras_p.argmax(1)):.2f}")
            assert np.isfinite(scores).all(), "NaN reached the output"
            if kind == "float32":
                assert gap < 1e-4, gap
            if kind == "float32" and mirror_average:
                try:
                    tf.lite.experimental.Analyzer.analyze(model_content=blob)
                except Exception as error:  # noqa: BLE001
                    print("analyzer unavailable:", error)
    print("smoke check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
