"""Personal adaptation: the same maths as web/src/personal.js, and its measurement (master-v3 Stage 4).

A per-sign bias on top of the model's scores, nudged by a few gradient steps each time the person
confirms a sign. measure() simulates a person who confirms 20 of their own signs (the true sign each
time, as when they tap the right suggestion) and compares top-1 on their other signs before and after.
"""

from __future__ import annotations

import numpy as np

SETTINGS = {"rate": 0.1, "decay": 0.05, "steps": 1, "limit": 2.0}  # chosen on toy cases so it never hurt (see tests)


def softmax(z: np.ndarray) -> np.ndarray:
    e = np.exp(z - z.max(axis=-1, keepdims=True))
    return e / e.sum(axis=-1, keepdims=True)


def learn(bias: np.ndarray, scores: np.ndarray, confirmed: int, settings: dict = SETTINGS) -> np.ndarray:
    bias = bias.astype(np.float64).copy()
    for _ in range(settings["steps"]):
        p = softmax(scores + bias)
        target = np.zeros_like(bias)
        target[confirmed] = 1.0
        bias = np.clip(bias - settings["rate"] * (p - target + settings["decay"] * bias), -settings["limit"], settings["limit"])
    return bias


def measure(scores: np.ndarray, labels: np.ndarray, groups: np.ndarray, confirmations: int = 20, repeats: int = 10, seed: int = 0) -> dict:
    """scores: (N, C) log-probabilities from the shipped recipe on recordings it never saw; groups: one id per
    simulated person (here: each recording folder). For each group and repeat: confirm `confirmations`
    random samples, then top-1 on that group's remaining samples before and after."""
    rng = np.random.default_rng(seed)
    before, after = [], []
    for group in np.unique(groups):
        idx = np.flatnonzero(groups == group)
        if len(idx) <= confirmations + 10:
            continue
        for _ in range(repeats):
            order = rng.permutation(idx)
            seen, rest = order[:confirmations], order[confirmations:]
            bias = np.zeros(scores.shape[1])
            for i in seen:
                bias = learn(bias, scores[i], int(labels[i]))
            before.append(float((scores[rest].argmax(1) == labels[rest]).mean()))
            after.append(float(((scores[rest] + bias).argmax(1) == labels[rest]).mean()))
    if not before:
        return {"runs": 0}
    return {"runs": len(before), "confirmations": confirmations, "top1_before": round(float(np.mean(before)), 4),
            "top1_after": round(float(np.mean(after)), 4), "change_points": round(100 * float(np.mean(after) - np.mean(before)), 2),
            "worst_change_points": round(100 * float(np.min(np.array(after) - np.array(before))), 2), "settings": SETTINGS}
