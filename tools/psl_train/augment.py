"""Training-time changes to PSL hand sequences (numpy only, so they are tested without TensorFlow).

Every change keeps the sign's meaning: speed and start/end jitter, a small turn, size and position change
of the whole picture, a slightly different camera shape, mirroring (a left-handed signer), tiny landmark
noise, and a hand briefly lost for 1-4 frames (fast movement, occlusion). A hand is never removed for the
whole sign, because that changes a two-handed sign into another one.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ml_engine import psl_hands


@dataclass(frozen=True)
class Settings:
    crop: float = 0.10  # up to this share of the sign cut from each end
    jitter: float = 0.4  # frame-index jitter, in output-frame steps
    mirror: float = 0.5
    rotate_degrees: float = 12.0
    scale: tuple[float, float] = (0.85, 1.15)
    stretch: tuple[float, float] = (0.9, 1.1)  # camera shape
    shift: float = 0.08
    noise: float = 0.002
    occlude: float = 0.25
    occlude_frames: tuple[int, int] = (1, 4)


def windows(hands: np.ndarray, lengths: np.ndarray) -> np.ndarray:
    """(N, 2) [start, end) of each sample's sign (psl_hands.trim_window)."""
    out = np.zeros((len(hands), 2), dtype=np.int64)
    for i in range(len(hands)):
        window = psl_hands.trim_window(hands[i, : lengths[i]])
        out[i] = window if window is not None else (0, lengths[i])
    return out


def fixed(hands: np.ndarray, spans: np.ndarray, frames: int = psl_hands.FRAMES) -> np.ndarray:
    """The evaluation input: each sign trimmed and resampled with the baseline rule, no changes."""
    out = np.empty((len(hands), frames, 2, 21, 3), dtype=np.float32)
    for i, (a, b) in enumerate(spans):
        out[i] = hands[i, a:b][psl_hands.resample_indices(int(b - a), frames)]
    return out


def random_frames(spans: np.ndarray, rng: np.random.Generator, settings: Settings, frames: int = psl_hands.FRAMES) -> np.ndarray:
    """(N, frames) frame indices: a randomly cropped window, resampled with jitter, kept in order."""
    a, b = spans[:, 0].astype(np.float64), spans[:, 1].astype(np.float64)
    length = b - a
    cut = np.floor(length * settings.crop).astype(np.int64)
    start_cut = rng.integers(0, cut + 1)
    end_cut = rng.integers(0, cut + 1)
    ok = (length - start_cut - end_cut) >= 8
    a = np.where(ok, a + start_cut, a)
    b = np.where(ok, b - end_cut, b)
    steps = np.linspace(0.0, 1.0, frames)[None, :]
    position = a[:, None] + steps * (b - a - 1)[:, None]
    position += rng.uniform(-settings.jitter, settings.jitter, position.shape) * ((b - a - 1) / max(frames - 1, 1))[:, None]
    index = np.clip(np.rint(position), a[:, None], (b - 1)[:, None]).astype(np.int64)
    return np.sort(index, axis=1)


def augment(hands: np.ndarray, spans: np.ndarray, rng: np.random.Generator, settings: Settings = Settings(),
            reference: float = psl_hands.ASPECT_REFERENCE) -> np.ndarray:
    """(N, L, 2, 21, 3) raw hands + their sign spans -> (N, 32, 2, 21, 3) changed copies (NaN kept)."""
    n = len(hands)
    index = random_frames(spans, rng, settings)
    out = np.take_along_axis(hands, index[:, :, None, None, None], axis=1).astype(np.float64)

    flip = rng.random(n) < settings.mirror
    out[flip] = psl_hands.mirror(out[flip])

    angle = np.deg2rad(rng.uniform(-settings.rotate_degrees, settings.rotate_degrees, n))
    scale = rng.uniform(*settings.scale, n)
    stretch = rng.uniform(*settings.stretch, n)
    shift = rng.uniform(-settings.shift, settings.shift, (n, 2))
    x = (out[..., 0] - 0.5) * reference  # image heights, centred
    y = out[..., 1] - 0.5
    cos, sin = np.cos(angle)[:, None, None, None], np.sin(angle)[:, None, None, None]
    s = scale[:, None, None, None]
    xr = (cos * x - sin * y) * s * stretch[:, None, None, None]
    yr = (sin * x + cos * y) * s
    out[..., 0] = xr / reference + 0.5 + shift[:, 0, None, None, None]
    out[..., 1] = yr + 0.5 + shift[:, 1, None, None, None]
    out[..., 2] *= s * stretch[:, None, None, None]
    out[..., :2] += rng.normal(0.0, settings.noise, out[..., :2].shape)

    lose = np.flatnonzero(rng.random(n) < settings.occlude)
    frames = out.shape[1]
    for i in lose:
        hand = int(rng.integers(0, 2))
        span = int(rng.integers(settings.occlude_frames[0], settings.occlude_frames[1] + 1))
        start = int(rng.integers(0, frames - span + 1))
        out[i, start:start + span, hand] = np.nan
    return out.astype(np.float32)


def mixup(x: np.ndarray, y: np.ndarray, rng: np.random.Generator, alpha: float = 0.2, share: float = 0.5) -> tuple[np.ndarray, np.ndarray]:
    """Blend a share of the samples with a random partner (features and one-hot labels alike)."""
    n = len(x)
    pick = rng.random(n) < share
    partner = rng.permutation(n)
    lam = rng.beta(alpha, alpha, n).astype(np.float32)
    lam = np.where(pick, np.maximum(lam, 1 - lam), 1.0).astype(np.float32)
    x2 = lam[:, None, None] * x + (1 - lam[:, None, None]) * x[partner]
    y2 = lam[:, None] * y + (1 - lam[:, None]) * y[partner]
    return x2.astype(np.float32), y2.astype(np.float32)


def balanced_order(labels: np.ndarray, rng: np.random.Generator, power: float = 0.5) -> np.ndarray:
    """One epoch of sample indices drawn with weight count(class) ** -power (rare signs seen more often)."""
    counts = np.bincount(labels)
    weights = counts[labels].astype(np.float64) ** -power
    return rng.choice(len(labels), size=len(labels), replace=True, p=weights / weights.sum())
