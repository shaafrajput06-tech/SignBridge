"""The PSL model in TensorFlow: the hands-view maths (same as ml_engine/psl_hands.features), the two
architectures that are compared, and the export wrapper that reads the baseline's 543-point input.

Missing values: the input marks a missing hand with NaN, like the baseline. The graph tests "value > -1e6",
which is false for NaN, so it needs only built-in TFLite operators (no IsNan, no custom ops).
"""

from __future__ import annotations

import keras
import tensorflow as tf
from keras import layers

from ml_engine import psl_hands

HAND_POINTS = psl_hands.HAND_POINTS
FRAMES = psl_hands.FRAMES
FEATURES = psl_hands.FEATURES_PER_FRAME


def is_number(x: tf.Tensor) -> tf.Tensor:
    return tf.greater(x, -1e6)


def hands_features(h4: tf.Tensor, frames: int = FRAMES, reference: float = psl_hands.ASPECT_REFERENCE) -> tf.Tensor:
    """(B, frames * 2, 21, 3) float32, rows 2t and 2t + 1 = left and right hand of frame t, NaN for a
    missing hand -> (B, frames, 174). Kept at 4 dimensions so every TFLite kernel accepts it."""
    mask = is_number(h4[:, :, 0, 0])  # (B, 2T)
    maskf = tf.cast(mask, tf.float32)
    p = tf.where(is_number(h4), h4, tf.zeros_like(h4)) * tf.constant([reference, 1.0, reference], tf.float32)
    rel = p - p[:, :, :1, :]
    size = tf.reduce_max(tf.sqrt(tf.reduce_sum(tf.square(rel[..., :2]), axis=-1)), axis=-1)  # (B, 2T)
    valid = tf.logical_and(mask, size > 1e-6)
    validf = tf.cast(valid, tf.float32)
    count = tf.reduce_sum(validf, axis=1)
    scale = tf.where(count > 0, tf.reduce_sum(size * validf, axis=1) / tf.maximum(count, 1.0), tf.ones_like(count))
    scale = scale[:, None]  # (B, 1)

    safe = tf.where(valid, size, tf.ones_like(size))
    shape = rel / safe[:, :, None, None]
    shape = tf.where(valid[:, :, None, None], shape, tf.zeros_like(shape))
    shape = tf.reshape(shape, [-1, frames, 126])

    origin = tf.constant([0.5 * reference, 0.5], tf.float32)
    wrist = (p[:, :, 0, :2] - origin) / scale[:, :, None]  # (B, 2T, 2)
    wrist = tf.where(mask[:, :, None], wrist, tf.zeros_like(wrist))
    wrist = tf.reshape(wrist, [-1, frames, 4])  # left x, left y, right x, right y
    hands_present = tf.reshape(maskf, [-1, frames, 2])
    per_value = tf.reshape(tf.tile(hands_present[..., None], [1, 1, 1, 2]), [-1, frames, 4])
    both = per_value[:, 1:] * per_value[:, :-1]
    motion = tf.concat([tf.zeros_like(wrist[:, :1]), (wrist[:, 1:] - wrist[:, :-1]) * both], axis=1)

    hand_size = tf.reshape(tf.where(mask, size / scale, tf.zeros_like(size)), [-1, frames, 2])

    points = tf.reshape(tf.gather(p[..., :2], HAND_POINTS, axis=2), [-1, frames, 24])  # hand, point, (x, y)
    lx, ly = points[..., 0:12:2], points[..., 1:12:2]
    rx, ry = points[..., 12:24:2], points[..., 13:24:2]
    dx = lx[..., :, None] - rx[..., None, :]
    dy = ly[..., :, None] - ry[..., None, :]
    distance = tf.sqrt(dx * dx + dy * dy) / scale[:, :, None, None]  # (B, T, 6, 6)
    pair = hands_present[..., 0] * hands_present[..., 1]
    distance = tf.reshape(distance * pair[..., None, None], [-1, frames, 36])

    out = tf.concat([shape, wrist, motion, hand_size, distance, hands_present], axis=-1)
    return tf.clip_by_value(out, psl_hands.CLIP[0], psl_hands.CLIP[1])


def to_rows(hands) -> tf.Tensor:
    """(B, T, 2, 21, 3) -> (B, T * 2, 21, 3), the layout hands_features reads."""
    hands = tf.convert_to_tensor(hands, tf.float32)
    return tf.reshape(hands, [-1, hands.shape[1] * 2, 21, 3])


def mirror_rows(h4: tf.Tensor, frames: int = FRAMES) -> tf.Tensor:
    """x -> 1 - x and the two hands swapped (psl_hands.mirror), in the (B, 2T, 21, 3) layout."""
    pairs = tf.reshape(h4, [-1, frames, 2, 63])
    swapped = tf.reshape(tf.reverse(pairs, axis=[2]), [-1, frames * 2, 21, 3])
    return tf.concat([1.0 - swapped[..., :1], swapped[..., 1:]], axis=-1)


@keras.saving.register_keras_serializable("signbridge")
class AddPosition(layers.Layer):
    def build(self, input_shape):
        self.table = self.add_weight(name="table", shape=(input_shape[1], input_shape[2]), initializer="zeros")

    def call(self, x):
        return x + self.table


def conv_block(x, dim: int, kernel: int, drop: float):
    skip = x
    x = layers.Dense(dim * 2, activation="swish")(x)
    x = layers.DepthwiseConv1D(kernel, padding="same", use_bias=False)(x)
    x = layers.BatchNormalization(momentum=0.95)(x)
    x = layers.Dense(dim)(x)
    x = layers.Dropout(drop)(x)
    return layers.Add()([skip, x])


def transformer_block(x, dim: int, heads: int, drop: float):
    skip = x
    y = layers.LayerNormalization()(x)
    y = layers.MultiHeadAttention(heads, dim // heads, dropout=drop)(y, y)
    y = layers.Dropout(drop)(y)
    x = layers.Add()([skip, y])
    skip = x
    y = layers.LayerNormalization()(x)
    y = layers.Dense(dim * 2, activation="swish")(y)
    y = layers.Dropout(drop)(y)
    y = layers.Dense(dim)(y)
    y = layers.Dropout(drop)(y)
    return layers.Add()([skip, y])


def islr_lite(classes: int, dim: int = 192, kernel: int = 9, blocks: int = 2, heads: int = 4, drop: float = 0.2) -> keras.Model:
    """The baseline's ISLR 1st-place recipe, made smaller for 32 frames: depthwise 1D conv blocks + transformer."""
    inputs = keras.Input((FRAMES, FEATURES), name="features")
    x = layers.Dense(dim, use_bias=False)(inputs)
    x = layers.BatchNormalization(momentum=0.95)(x)
    x = AddPosition()(x)
    for _ in range(blocks):
        for _ in range(3):
            x = conv_block(x, dim, kernel, drop)
        x = transformer_block(x, dim, heads, drop)
    x = layers.Dense(dim * 2, activation="swish")(x)
    x = layers.GlobalAveragePooling1D()(x)
    x = layers.Dropout(0.4)(x)
    outputs = layers.Dense(classes, name="logits")(x)
    return keras.Model(inputs, outputs, name="islr_lite")


def gru_baseline(classes: int, units: int = 128, drop: float = 0.3) -> keras.Model:
    """The comparison model master-v3 asks for: two GRU layers."""
    inputs = keras.Input((FRAMES, FEATURES), name="features")
    x = layers.Dense(units * 2, activation="swish")(inputs)
    x = layers.Bidirectional(layers.GRU(units, return_sequences=True))(x)
    x = layers.GRU(units)(x)
    x = layers.Dropout(drop)(x)
    outputs = layers.Dense(classes, name="logits")(x)
    return keras.Model(inputs, outputs, name="gru")


ARCHITECTURES = {"islr_lite": islr_lite, "gru": gru_baseline}


class Export(tf.Module):
    """frames x 543 x 3 (baseline layout, NaN for missing) -> one score per class.

    softmax(scores) = the calibrated probabilities: logits / temperature, averaged with the mirrored sign
    when mirror_average is on (the same sign as a left-handed signer makes it)."""

    def __init__(self, model: keras.Model, temperature: float, mirror_average: bool):
        super().__init__()
        self.model = model
        self.temperature = float(temperature)
        self.mirror_average = bool(mirror_average)

    @tf.function(input_signature=[tf.TensorSpec([FRAMES, psl_hands.ROWS_PER_FRAME, 3], tf.float32, name="inputs")])
    def serve(self, inputs):
        rows = tf.reshape(tf.stack([inputs[:, 468:489], inputs[:, 522:543]], axis=1), [1, FRAMES * 2, 21, 3])
        if self.mirror_average:
            rows = tf.concat([rows, mirror_rows(rows)], axis=0)
        logits = self.model(hands_features(rows), training=False) / self.temperature
        probs = tf.reduce_mean(tf.nn.softmax(logits, axis=-1), axis=0)
        return {"outputs": tf.math.log(probs + 1e-9)}


def to_tflite(export: Export, kind: str) -> bytes:
    """kind: float32, float16 (fp16 weights) or int8 (dynamic-range int8 weights). Built-in ops only."""
    converter = tf.lite.TFLiteConverter.from_concrete_functions([export.serve.get_concrete_function()], export)
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS]
    if kind in ("float16", "int8"):
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
    if kind == "float16":
        converter.target_spec.supported_types = [tf.float16]
    return converter.convert()


def tflite_runner(model_bytes: bytes):
    """A function frames x 543 x 3 -> scores, with LiteRT (ai-edge-litert, as the local server uses) or,
    if it is not installed, TensorFlow's own TFLite interpreter."""
    try:
        from ai_edge_litert.interpreter import Interpreter
    except ImportError:
        Interpreter = tf.lite.Interpreter  # noqa: N806
    interpreter = Interpreter(model_content=model_bytes)
    interpreter.allocate_tensors()
    inp = interpreter.get_input_details()[0]
    out = interpreter.get_output_details()[0]

    def run(x):
        interpreter.set_tensor(inp["index"], x.astype("float32"))
        interpreter.invoke()
        return interpreter.get_tensor(out["index"]).copy()

    return run, {"input": [inp["name"], inp["shape"].tolist()], "output": [out["name"], out["shape"].tolist()]}
