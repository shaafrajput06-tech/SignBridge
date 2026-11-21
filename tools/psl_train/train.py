"""Train, measure and export the PSL recogniser (master-v3 Stage 2). Needs TensorFlow; runs on GitHub
Actions (.github/workflows/psl-train.yml) or on Kaggle/Colab with the same command.

    python -m tools.psl_train --data data/psl-signspeak-words/signspeak.npz --out out/psl [--epochs 100]

What it does, in order:
  1. Loads the converted SignSpeak data and maps each camera's shape to the reference shape.
  2. Protocol "device held out" (weaker: the dataset has no signer ids, so the same people may appear
     in both parts): trains on the computer-camera folders, tests on the phone folders. Both architectures
     (islr_lite and the GRU baseline) are trained and reported.
  3. Trains the shipped model on both folders (10 % kept aside for calibration and the export check).
  4. Exports TFLite float32 / float16 / int8, checks each against the Keras model, keeps the smallest one
     that loses at most 1 point, and writes the bundle: model, manifest (classes, tiers, metrics, licence
     ids, SHA-256), the full measurements as JSON, a Markdown summary and golden parity cases.
Every number in the output is measured in this run; nothing is estimated.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import time
from collections import Counter
from pathlib import Path

import numpy as np

from data_engine.ledger import assert_allowed
from ml_engine import psl_hands
from tools.psl_train import augment as aug

ROOT = Path(__file__).resolve().parents[2]
GLOSSES = json.loads((ROOT / "shared_data" / "psl_glosses.json").read_text(encoding="utf-8"))["glosses"]
LEDGER_IDS = ["psl-signspeak-words"]
UNKNOWN = "_unknown"
BADGE = "Community dataset — not yet validated"
SPEAK_LIMITS = (0.5, 0.6, 0.7, 0.8, 0.9)


def key(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


GLOSS_BY_KEY = {key(g): g for g in GLOSSES}


# ----------------------------------------------------------------------------------------------- data
def load(path: Path) -> dict:
    with np.load(path, allow_pickle=False) as z:
        data = {k: z[k] for k in z.files}
    summary_path = path.with_name("signspeak_summary.json")
    data["summary"] = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    hands = data["hands"].astype(np.float64)
    shapes = {}
    for device, info in data["summary"].get("camera_shape", {}).items():
        aspect = info.get("nearest_common")
        if aspect and abs(aspect - psl_hands.ASPECT_REFERENCE) > 1e-3:
            pick = data["device"] == device
            hands[pick] = psl_hands.adjust_aspect(hands[pick], aspect)
        shapes[device] = aspect
    data["hands"] = hands.astype(np.float32)
    data["camera_shapes_used"] = shapes
    data["spans"] = aug.windows(data["hands"], data["lengths"])
    return data


def choose_classes(words: np.ndarray, minimum: int = 8) -> list[str]:
    counts = Counter(words.tolist())
    signs = sorted(w for w, n in counts.items() if n >= minimum and w != UNKNOWN)
    return signs + ([UNKNOWN] if counts.get(UNKNOWN, 0) >= minimum else [])


def stratified_split(labels: np.ndarray, share: float, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    keep, held = [], []
    for c in np.unique(labels):
        idx = rng.permutation(np.flatnonzero(labels == c))
        k = int(round(len(idx) * share)) if len(idx) >= 5 else 0
        held.extend(idx[:k].tolist())
        keep.extend(idx[k:].tolist())
    return np.array(sorted(keep)), np.array(sorted(held))


def class_hands(data: dict, idx: np.ndarray, labels: np.ndarray, classes: list[str]) -> list[str]:
    out = []
    for c in range(len(classes)):
        uses = [psl_hands.hand_use(data["hands"][i, : data["lengths"][i]]) for i in idx[labels[idx] == c]]
        two = np.mean([u["two_handed"] for u in uses]) if uses else 0.0
        out.append("two" if two >= 0.5 else "one")
    return out


# ------------------------------------------------------------------------------------------- training
def make_dataset(keras, data, idx, labels, classes, batch, seed, settings):
    class EpochData(keras.utils.PyDataset):
        def __init__(self):
            super().__init__(workers=1, use_multiprocessing=False)
            self.rng = np.random.default_rng(seed)
            self.make()

        def make(self):
            order = idx[aug.balanced_order(labels[idx], self.rng)]
            hands = aug.augment(data["hands"][order], data["spans"][order], self.rng, settings)
            x = psl_hands.features(hands)
            y = np.eye(len(classes), dtype=np.float32)[labels[order]]
            self.x, self.y = aug.mixup(x, y, self.rng)

        def __len__(self):
            return math.ceil(len(self.x) / batch)

        def __getitem__(self, i):
            return self.x[i * batch:(i + 1) * batch], self.y[i * batch:(i + 1) * batch]

        def on_epoch_end(self):
            self.make()

    return EpochData()


def train(arch: str, data: dict, idx: np.ndarray, labels: np.ndarray, classes: list[str], epochs: int, seed: int, log: list):
    import keras

    from tools.psl_train import graph

    keras.utils.set_random_seed(seed)
    model = graph.ARCHITECTURES[arch](len(classes))
    batch = 64
    steps = math.ceil(len(idx) / batch) * epochs
    warm = max(1, steps // 20)
    schedule = keras.optimizers.schedules.CosineDecay(1e-5, steps - warm, alpha=0.02, warmup_target=1e-3, warmup_steps=warm)
    optimizer = keras.optimizers.AdamW(schedule, weight_decay=0.02, use_ema=True, ema_momentum=0.995)
    model.compile(optimizer=optimizer, loss=keras.losses.CategoricalCrossentropy(from_logits=True, label_smoothing=0.1), metrics=["accuracy"])
    started = time.perf_counter()
    history = model.fit(make_dataset(keras, data, idx, labels, classes, batch, seed, aug.Settings()), epochs=epochs, verbose=2)
    seconds = time.perf_counter() - started
    log.append({"model": arch, "train_samples": int(len(idx)), "epochs": epochs, "seconds": round(seconds, 1),
                "parameters": int(model.count_params()), "final_train_loss": round(float(history.history["loss"][-1]), 4)})
    print(f"trained {arch} on {len(idx)} samples, {epochs} epochs, {seconds:.0f} s")
    return model


def logits(model, data: dict, idx: np.ndarray, mirrored: bool = False) -> np.ndarray:
    hands = aug.fixed(data["hands"][idx], data["spans"][idx])
    if mirrored:
        hands = psl_hands.mirror(hands).astype(np.float32)
    return model.predict(psl_hands.features(hands), batch_size=256, verbose=0)


def softmax(z: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    z = z / temperature
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def probabilities(model, data, idx, temperature, mirror_average):
    p = softmax(logits(model, data, idx), temperature)
    if mirror_average:
        p = (p + softmax(logits(model, data, idx, mirrored=True), temperature)) / 2
    return p


def fit_temperature(z: np.ndarray, labels: np.ndarray, mirrored: np.ndarray | None = None) -> float:
    """The temperature with the lowest negative log-likelihood; with `mirrored` logits, for the average of
    the sign and its mirror image (what the shipped model outputs)."""
    best, best_nll = 1.0, float("inf")
    for t in np.arange(0.5, 3.001, 0.05):
        p = softmax(z, t) if mirrored is None else (softmax(z, t) + softmax(mirrored, t)) / 2
        nll = float(-np.mean(np.log(p[np.arange(len(labels)), labels] + 1e-12)))
        if nll < best_nll:
            best, best_nll = round(float(t), 2), nll
    return best


# ---------------------------------------------------------------------------------------- measurement
def measure(p: np.ndarray, labels: np.ndarray, classes: list[str], hands_per_class: list[str]) -> dict:
    n = len(labels)
    if n == 0:
        return {"samples": 0}
    order = np.argsort(-p, axis=1)
    top1 = order[:, 0] == labels
    top5 = (order[:, :5] == labels[:, None]).any(axis=1)
    conf = p.max(axis=1)
    per_class = {}
    for c, name in enumerate(classes):
        pick = labels == c
        if pick.any():
            per_class[name] = {"samples": int(pick.sum()), "top1": round(float(top1[pick].mean()), 4), "top5": round(float(top5[pick].mean()), 4)}
    groups = {}
    for kind in ("one", "two"):
        pick = np.array([hands_per_class[l] == kind and classes[l] != UNKNOWN for l in labels])
        groups[f"{kind}_handed"] = {"samples": int(pick.sum()), "top1": round(float(top1[pick].mean()), 4) if pick.any() else None,
                                     "top5": round(float(top5[pick].mean()), 4) if pick.any() else None}
    bins = []
    ece = 0.0
    for lo in np.arange(0.0, 1.0, 0.1):
        pick = (conf >= lo) & (conf < lo + 0.1 if lo < 0.9 else conf <= 1.0)
        if pick.any():
            acc, mean_conf = float(top1[pick].mean()), float(conf[pick].mean())
            ece += pick.mean() * abs(acc - mean_conf)
            bins.append({"from": round(float(lo), 1), "samples": int(pick.sum()), "confidence": round(mean_conf, 4), "accuracy": round(acc, 4)})
    speak = []
    for limit in SPEAK_LIMITS:
        pick = conf >= limit
        speak.append({"at_least": limit, "answered_share": round(float(pick.mean()), 4),
                      "wrong_share_of_answered": round(float((~top1[pick]).mean()), 4) if pick.any() else None})
    confusions = Counter((classes[t], classes[o]) for t, o, ok in zip(labels, order[:, 0], top1) if not ok)
    return {
        "samples": n,
        "top1": round(float(top1.mean()), 4),
        "top5": round(float(top5.mean()), 4),
        **groups,
        "expected_calibration_error": round(float(ece), 4),
        "reliability": bins,
        "speak_limits": speak,
        "confusions": [{"sign": a, "taken_for": b, "times": k} for (a, b), k in confusions.most_common(15)],
        "per_class": per_class,
    }


def independent_clips(folder: Path | None, classes: list[str]) -> dict:
    """Landmarks of the SLT PSL dictionary clips (Stage 1, web-learned v1): one performer who is not a
    SignSpeak signer, one clip per sign. Returns hands (N, L, 2, 21, 3), spans, labels and clip names."""
    if not folder or not (folder / "manifest.json").exists():
        return {}
    from data_engine.ledger import LicenceError

    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    index = {key(c): i for i, c in enumerate(classes) if c != UNKNOWN}
    picked = []
    for record in manifest["clips"]:
        gloss = str(record.get("gloss", ""))
        gloss = gloss.split(":", 1)[1] if gloss.startswith("slt:") else gloss
        label = index.get(key(gloss.split(".")[0]))
        if label is None or record.get("language") != "PSL":
            continue
        try:
            assert_allowed(record["ledger_id"], "evaluate")
        except LicenceError:
            continue
        with np.load(folder / record["file"], allow_pickle=False) as z:
            meta = json.loads(bytes(z["meta"]).decode("utf-8"))
            points, present = z["points"].astype(np.float64), z["present"]
        hands = points[:, :42].reshape(-1, 2, 21, 3)
        hands[present[:, 0] == 0, 0] = np.nan
        hands[present[:, 1] == 0, 1] = np.nan
        aspect = meta["image_width"] / meta["image_height"]
        picked.append((psl_hands.adjust_aspect(hands, aspect), label, record["gloss"]))
    if not picked:
        return {}
    length = max(len(h) for h, _, _ in picked)
    hands = np.full((len(picked), length, 2, 21, 3), np.nan, dtype=np.float32)
    lengths = np.zeros(len(picked), dtype=np.int64)
    for i, (h, _, _) in enumerate(picked):
        hands[i, : len(h)] = h
        lengths[i] = len(h)
    keep = np.array([psl_hands.trim_window(hands[i, : lengths[i]]) is not None for i in range(len(picked))])
    data = {"hands": hands[keep], "lengths": lengths[keep]}
    data["spans"] = aug.windows(data["hands"], data["lengths"])
    data["labels"] = np.array([l for (_, l, _), k in zip(picked, keep) if k])
    data["names"] = [g for (_, _, g), k in zip(picked, keep) if k]
    return data


# ---------------------------------------------------------------------------------------------- export
def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def islr_inputs(data: dict, idx: np.ndarray) -> np.ndarray:
    hands = aug.fixed(data["hands"][idx], data["spans"][idx])
    return np.stack([psl_hands.to_islr(h) for h in hands])


def export_bundle(model, data, idx, labels, classes, temperature, mirror_average, keras_probs, out: Path) -> dict:
    from tools.psl_train import graph

    module = graph.Export(model, temperature, mirror_average)
    inputs = islr_inputs(data, idx)
    keras_top = keras_probs.argmax(axis=1)
    keras_acc = float((keras_top == labels).mean())
    checks = {}
    blobs = {}
    for kind in ("float32", "float16", "int8"):
        try:
            blob = graph.to_tflite(module, kind)
        except Exception as error:  # noqa: BLE001
            checks[kind] = {"error": str(error)[:500]}
            continue
        run, io = graph.tflite_runner(blob)
        started = time.perf_counter()
        scores = np.stack([run(x) for x in inputs])
        ms = (time.perf_counter() - started) * 1000 / len(inputs)
        top = scores.argmax(axis=1)
        p = softmax(scores)
        checks[kind] = {"bytes": len(blob), "top1": round(float((top == labels).mean()), 4),
                        "same_top1_as_keras": round(float((top == keras_top).mean()), 4),
                        "max_probability_difference": round(float(np.abs(p - keras_probs).max()), 5),
                        "ms_per_sign_python_cpu": round(ms, 2), "io": io}
        blobs[kind] = blob
        print(f"tflite {kind}: {checks[kind]}")
    choice = "float32"
    for kind in ("int8", "float16"):
        c = checks.get(kind, {})
        if "top1" in c and keras_acc - c["top1"] <= 0.01 and c["same_top1_as_keras"] >= 0.98:
            if choice == "float32" or c["bytes"] < checks[choice]["bytes"]:
                choice = kind
    if choice not in blobs:
        raise SystemExit(f"no TFLite export worked: {checks}")
    blob = blobs[choice]
    out.mkdir(parents=True, exist_ok=True)
    (out / "psl_v3.tflite").write_bytes(blob)
    return {"keras_top1": round(keras_acc, 4), "checks": checks, "chosen": choice, "bytes": len(blob), "sha256": sha256(blob), "blob": blob}


def parity_cases(blob: bytes, data, idx, labels, classes, count: int = 6) -> dict:
    """A few real signs, rounded to 5 decimals, with the TFLite output for exactly those numbers."""
    from tools.psl_train import graph

    run, _ = graph.tflite_runner(blob)
    rng = np.random.default_rng(7)
    chosen = rng.choice(idx, size=min(count, len(idx)), replace=False)
    hands = np.round(aug.fixed(data["hands"][chosen], data["spans"][chosen]).astype(np.float64), 5).astype(np.float32)
    cases = []
    for i, h in zip(chosen, hands):
        scores = run(psl_hands.to_islr(h))
        top = np.argsort(-scores)[:5]
        cases.append({
            "sign": classes[labels[i]],
            "hands": [[[None if np.isnan(v) else float(v) for v in point] for point in hand] for hand in h.reshape(-1, 21, 3)],
            "top5": [int(t) for t in top],
            "top5_scores": [round(float(scores[t]), 5) for t in top],
        })
    return {"about": "frames x 2 hands x 21 points x (x, y, z) after trimming and resampling (hands listed frame by frame: left, right); null = missing hand",
            "frames": psl_hands.FRAMES, "cases": cases}


# ---------------------------------------------------------------------------------------------- report
def pct(value) -> str:
    return "—" if value is None else f"{100 * value:.1f} %"


def markdown(result: dict) -> str:
    d = result["device_held_out"]["islr_lite"]
    g = result["device_held_out"]["gru"]
    lines = [
        f"# PSL v3 training run ({result['date']})",
        "",
        f"Data: {result['data']['source']}; {result['data']['samples']} samples, {len(result['classes'])} classes "
        f"({result['data']['devices']}). Licence ids: {', '.join(LEDGER_IDS)}. Commit {result['commit']}.",
        "",
        "## Device held out (weaker: no signer ids, the same people may be in both parts)",
        "",
        "Trained on the computer-camera folders (desktop, laptop, webcam), tested on the phone folders (never seen in training). "
        f"Fair test: {result['device_held_out']['fair_test']['samples']} phone signs that have computer-camera training recordings and no label conflict.",
        "",
        "| Model | Test signs | Top-1 | Top-5 | One-handed top-1 | Two-handed top-1 | Calibration error |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, m in (("islr_lite (shipped recipe)", d["plain"]), ("islr_lite + mirror averaging", d["mirror_average"]), ("GRU baseline", g["plain"])):
        lines.append(f"| {name} | {m['samples']} | {pct(m['top1'])} | {pct(m['top5'])} | {pct(m['one_handed']['top1'])} ({m['one_handed']['samples']}) "
                     f"| {pct(m['two_handed']['top1'])} ({m['two_handed']['samples']}) | {m['expected_calibration_error']:.3f} |")
    held_info = result["device_held_out"]
    lines += ["", f"All {d['plain_all_phone']['samples']} phone signs, including those this protocol cannot learn: top-1 {pct(d['plain_all_phone']['top1'])}.",
              "Signs with only phone recordings (no training data in this protocol, not measured): " + (", ".join(held_info["untrained_in_this_protocol"]) or "none") + ".",
              "Label conflicts (phone recordings labelled the other way round; left out of the shipped model and the fair test): "
              + ("; ".join(" ↔ ".join(c["signs"]) for c in held_info["label_conflicts"]) or "none") + "."]
    lr = result["device_held_out"]["left_right"]
    lines += [
        "",
        f"Left- vs right-dominant (test signs mirrored = as a left-handed signer makes them): right {pct(lr['right_top1'])}, "
        f"left {pct(lr['left_top1'])}, gap {lr['gap_points']:.1f} points without mirror averaging; "
        f"{'0 by construction with mirror averaging (shipped)' if result['shipped']['mirror_average'] else 'mirror averaging not shipped'}.",
        "",
        "Wrong answers among confident ones (phone test, shipped recipe):",
        "",
        "| Shown when top-1 ≥ | Share answered | Wrong among answered |",
        "|---|---|---|",
    ]
    shown = d["mirror_average"] if result["shipped"]["mirror_average"] else d["plain"]
    for s in shown["speak_limits"]:
        lines.append(f"| {s['at_least']:.1f} | {pct(s['answered_share'])} | {pct(s['wrong_share_of_answered'])} |")
    lines += ["", "Most frequent confusions: " + "; ".join(f"{c['sign']} → {c['taken_for']} ({c['times']})" for c in shown["confusions"][:10]), ""]
    adaptation = result["device_held_out"].get("personal_adaptation", {})
    if adaptation.get("runs"):
        lines += ["## Personal adaptation (Stage 4)", "",
                  f"A simulated person confirms {adaptation['confirmations']} of their own signs (phone recordings, one person per phone folder, "
                  f"{adaptation['runs']} random repeats); top-1 on their other signs: {pct(adaptation['top1_before'])} before, "
                  f"{pct(adaptation['top1_after'])} after ({adaptation['change_points']:+.2f} points; worst repeat {adaptation['worst_change_points']:+.2f}).", ""]
    ind = result.get("independent_signer")
    lines += ["## Independent signer (shipped model)", ""]
    if ind:
        lines += [f"SLT PSL dictionary clips of the same words: one performer who is not a SignSpeak signer, one clip per sign "
                  f"({ind['samples']} clips). Top-1 {pct(ind['top1'])}, top-5 {pct(ind['top5'])}. A different dictionary: a miss can "
                  "also mean a regional variant of the sign, not only a model error.", "",
                  "| Sign | Answer | Probability | In top-5 |", "|---|---|---|---|"]
        lines += [f"| {c['sign']} | {c['answer']} | {c['probability']:.2f} | {'yes' if c['top5'] else 'no'} |" for c in ind["clips"]]
        lines.append("")
    else:
        lines += ["Not measured in this run (no web-learned SLT landmarks given).", ""]
    s = result["shipped"]
    lines += [
        "## Shipped model",
        "",
        f"Trained on both folders except a 10 % calibration part ({s['validation']['samples']} signs; same people and sessions, so weaker). "
        f"Calibration part top-1 {pct(s['validation']['top1'])}, top-5 {pct(s['validation']['top5'])}. Temperature {s['temperature']} "
        "(fitted on the held-out device's predictions of the same recipe), "
        f"mirror averaging {'on' if s['mirror_average'] else 'off'}.",
        "",
        "| Export | Bytes | Top-1 | Same top-1 as Keras | ms per sign (Python, CPU) |",
        "|---|---|---|---|---|",
    ]
    for kind, c in s["export"]["checks"].items():
        if "error" in c:
            lines.append(f"| {kind} | failed: {c['error'][:80]} | | | |")
        else:
            lines.append(f"| {kind}{' (chosen)' if kind == s['export']['chosen'] else ''} | {c['bytes']:,} | {pct(c['top1'])} | {pct(c['same_top1_as_keras'])} | {c['ms_per_sign_python_cpu']} |")
    lines += [
        "",
        f"Tiers: {s['tiers']['A']} Tier A, {s['tiers']['B']} Tier B. {s['tiers']['rule']}",
        "",
        "## Per sign (device held out, shipped recipe)",
        "",
        "| Sign | Hands | Train | Test | Top-1 | Top-5 |",
        "|---|---|---|---|---|---|",
    ]
    for c in result["classes"]:
        m = shown["per_class"].get(c["gloss"], {})
        lines.append(f"| {c['english']} | {c['hands']} | {c['train_samples']} | {m.get('samples', 0)} | {pct(m.get('top1'))} | {pct(m.get('top5'))} |")
    lines += ["", "Training runs: " + "; ".join(f"{t['model']} {t['train_samples']} samples {t['epochs']} epochs {t['seconds']} s" for t in result["training"]), ""]
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------ main
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Train and export the PSL recogniser")
    parser.add_argument("--data", type=Path, default=Path("data/psl-signspeak-words/signspeak.npz"))
    parser.add_argument("--out", type=Path, default=Path("out/psl"))
    parser.add_argument("--epochs", type=int, default=int(os.environ.get("PSL_EPOCHS", "100")))
    parser.add_argument("--gru-epochs", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--independent", type=Path, default=None,
                        help="web-learned folder (Stage 1) whose SLT dictionary clips test one signer absent from SignSpeak")
    args = parser.parse_args(argv)
    for ledger_id in LEDGER_IDS:
        assert_allowed(ledger_id, "train_labels")
        assert_allowed(ledger_id, "redistribute_weights")

    data = load(args.data)
    classes = choose_classes(data["word"])
    index = {c: i for i, c in enumerate(classes)}
    labels = np.array([index.get(w, -1) for w in data["word"]])
    usable = np.flatnonzero(labels >= 0)
    rng = np.random.default_rng(args.seed)
    print(f"{len(usable)} usable samples, {len(classes)} classes; camera shapes used: {data['camera_shapes_used']}")
    missing = [c for c in classes if c != UNKNOWN and key(c) not in GLOSS_BY_KEY]
    if missing:
        print("glosses without display names in shared_data/psl_glosses.json:", missing)

    log: list = []
    result: dict = {"date": dt.date.today().isoformat(), "commit": os.environ.get("GITHUB_SHA", "local")[:12],
                    "data": {"source": data["summary"].get("source", str(args.data)), "samples": int(len(usable)),
                             "devices": dict(Counter(data["device"][usable].tolist())), "camera_shapes_used": data["camera_shapes_used"]},
                    "training": log}

    # 1. device held out
    computer = usable[data["device"][usable] != "phone"]
    phone = usable[data["device"][usable] == "phone"]
    keep, val = stratified_split(labels[computer], 0.1, rng)
    train_idx, val_idx = computer[keep], computer[val]
    hands_per_class = class_hands(data, usable, labels, classes)
    held: dict = {}
    trained = set(labels[train_idx].tolist())
    for arch, epochs in (("islr_lite", args.epochs), ("gru", args.gru_epochs or args.epochs)):
        model = train(arch, data, train_idx, labels, classes, epochs, args.seed, log)
        t = fit_temperature(logits(model, data, val_idx), labels[val_idx])
        if arch == "islr_lite":
            phone_logits = logits(model, data, phone)
            phone_mirrored = logits(model, data, phone, mirrored=True)
            # Signs the phone recordings label the other way round: the model (trained without phones) calls
            # most of sign a "b" and most of sign b "a". Which side is right cannot be known from the data,
            # so those phone recordings are left out of the shipped model and of the fair test.
            answer = phone_logits.argmax(1)
            conflicts = []
            for a in sorted(set(labels[phone].tolist()) & trained):
                for b in sorted(set(labels[phone].tolist()) & trained):
                    if a < b:
                        ab = np.mean(answer[labels[phone] == a] == b)
                        ba = np.mean(answer[labels[phone] == b] == a)
                        if ab >= 0.6 and ba >= 0.6:
                            conflicts.append((a, b))
            conflicted = sorted({c for pair in conflicts for c in pair})
            held["label_conflicts"] = [{"signs": [classes[a], classes[b]], "note": "phone recordings labelled the other way round from the computer-camera ones"} for a, b in conflicts]
            held["untrained_in_this_protocol"] = sorted(classes[c] for c in set(labels[phone].tolist()) - trained)
            fair_mask = np.isin(labels[phone], sorted(trained)) & ~np.isin(labels[phone], conflicted)
            fair = phone[fair_mask]
            held["fair_test"] = {"samples": int(len(fair)), "rule": "phone test signs that have computer-camera training recordings and no label conflict"}
            held["temperature_from_held_out_device"] = {
                "plain": fit_temperature(phone_logits[fair_mask], labels[fair]),
                "mirror_average": fit_temperature(phone_logits[fair_mask], labels[fair], phone_mirrored[fair_mask])}
        held[arch] = {"temperature": t,
                      "plain_all_phone": measure(probabilities(model, data, phone, t, False), labels[phone], classes, hands_per_class),
                      "plain": measure(probabilities(model, data, fair, t, False), labels[fair], classes, hands_per_class),
                      "validation_plain": measure(probabilities(model, data, val_idx, t, False), labels[val_idx], classes, hands_per_class)}
        if arch == "islr_lite":
            held[arch]["mirror_average"] = measure(probabilities(model, data, fair, t, True), labels[fair], classes, hands_per_class)
            # Stage 4: a person who confirms 20 of their own signs (each phone folder = one simulated person).
            from tools.psl_train import personal

            t_ship = held["temperature_from_held_out_device"]["mirror_average"]
            ship_probs = (softmax(phone_logits[fair_mask], t_ship) + softmax(phone_mirrored[fair_mask], t_ship)) / 2
            held["personal_adaptation"] = personal.measure(np.log(ship_probs + 1e-9), labels[fair], data["archive"][fair])
            held[arch]["validation_mirror_average"] = measure(probabilities(model, data, val_idx, t, True), labels[val_idx], classes, hands_per_class)
            mirrored = softmax(phone_mirrored[fair_mask], t)
            left = float((mirrored.argmax(1) == labels[fair]).mean())
            right = held[arch]["plain"]["top1"]
            held["left_right"] = {"right_top1": right, "left_top1": round(left, 4), "gap_points": round(100 * abs(right - left), 2)}
        print(f"device held out, {arch}: top-1 {held[arch]['plain']['top1']} (fair test), {held[arch]['plain_all_phone']['top1']} (all phone)")
    result["device_held_out"] = held
    mirror_average = held["islr_lite"]["validation_mirror_average"]["top1"] >= held["islr_lite"]["validation_plain"]["top1"]
    if conflicted:
        dropped = usable[(data["device"][usable] == "phone") & np.isin(labels[usable], conflicted)]
        usable = np.setdiff1d(usable, dropped)
        print(f"left out of the shipped model: {len(dropped)} phone recordings of {[classes[c] for c in conflicted]} (label conflict)")

    # 2. shipped model on everything but a calibration part
    keep, val = stratified_split(labels[usable], 0.1, rng)
    final_train, final_val = usable[keep], usable[val]
    model = train("islr_lite", data, final_train, labels, classes, args.epochs, args.seed + 1, log)
    # The calibration part comes from the same sessions and is almost always right, which would push the
    # temperature to its minimum (over-confident). The shipped temperature is the one fitted on the
    # held-out device's predictions of the same recipe.
    temperature = held["temperature_from_held_out_device"]["mirror_average" if mirror_average else "plain"]
    val_probs = probabilities(model, data, final_val, temperature, mirror_average)
    validation = measure(val_probs, labels[final_val], classes, hands_per_class)
    exported = export_bundle(model, data, final_val, labels[final_val], classes, temperature, mirror_average, val_probs, args.out)
    blob = exported.pop("blob")

    independent = independent_clips(args.independent, classes)
    if independent:
        p = softmax(model.predict(psl_hands.features(aug.fixed(independent["hands"], independent["spans"])), verbose=0), temperature)
        if mirror_average:
            mirrored = psl_hands.mirror(aug.fixed(independent["hands"], independent["spans"])).astype(np.float32)
            p = (p + softmax(model.predict(psl_hands.features(mirrored), verbose=0), temperature)) / 2
        result["independent_signer"] = measure(p, independent["labels"], classes, hands_per_class)
        order = np.argsort(-p, axis=1)
        result["independent_signer"]["clips"] = [{"clip_gloss": name, "sign": classes[l], "answer": classes[o[0]],
                                                   "probability": round(float(p[i, o[0]]), 3), "top5": l in o[:5]}
                                                  for i, (name, l, o) in enumerate(zip(independent["names"], independent["labels"], order))]
        print(f"independent signer (SLT dictionary): {result['independent_signer']['top1']} top-1 on {len(independent['labels'])} clips")

    train_counts = Counter(labels[final_train].tolist())
    class_entries = []
    for i, gloss in enumerate(classes):
        meta = GLOSSES.get(GLOSS_BY_KEY.get(key(gloss), ""), {})
        entry = {"index": i, "gloss": GLOSS_BY_KEY.get(key(gloss), gloss),
                 "english": "Not a sign" if gloss == UNKNOWN else meta.get("english", gloss.replace("_", " ").capitalize()),
                 "urdu": "" if gloss == UNKNOWN else meta.get("urdu", ""),
                 "tier": None if gloss == UNKNOWN else "B", "validated_by_deaf_signers": False,
                 "hands": hands_per_class[i], "train_samples": int(train_counts.get(i, 0))}
        for field in ("vocabulary_id", "dictionary_url", "urdu_source"):
            if field in meta:
                entry[field] = meta[field]
        test = (held["islr_lite"]["mirror_average"] if mirror_average else held["islr_lite"]["plain"])["per_class"].get(gloss)
        if test:
            entry["device_held_out"] = test
        for conflict in held["label_conflicts"]:
            if gloss in conflict["signs"]:
                other = [g for g in conflict["signs"] if g != gloss][0]
                entry["data_note"] = f"The phone recordings of this sign were labelled as '{other}'; it was learned from computer-camera recordings only and not measured on unseen ones."
        if gloss in held["untrained_in_this_protocol"]:
            entry["data_note"] = "Only phone recordings exist, so it was not measured on recordings the model had not seen."
        class_entries.append(entry)
    result["classes"] = class_entries
    tiers = {"A": 0, "B": sum(1 for c in class_entries if c["tier"] == "B"),
             "rule": "Tier A needs a signer-independent test (CLAUDE.md 1, 8.3). SignSpeak publishes no signer ids, so no sign can pass that test with this data: every sign is Tier B (\"Suggested — please confirm\")."}
    result["shipped"] = {"temperature": temperature, "mirror_average": mirror_average, "validation": validation,
                         "export": exported, "tiers": tiers}

    manifest = {
        "bundle": "signbridge-psl",
        "version": f"3.0.0-{result['date'].replace('-', '')}",
        "created": result["date"],
        "commit": result["commit"],
        "sign_language": "PSL",
        "feature_version": psl_hands.SPEC["feature_version"],
        "input": {"layout": "asl-islr-543-v1", "shape": [psl_hands.FRAMES, psl_hands.ROWS_PER_FRAME, 3], "missing": "NaN",
                  "aspect_reference": psl_hands.ASPECT_REFERENCE, "parts_read": ["left_hand", "right_hand"],
                  "spec": "shared_data/psl_hands_spec.json"},
        "output": {"shape": [len(classes)], "values": "log of calibrated probabilities: softmax(outputs) gives them back"},
        "model": {"file": "psl_v3.tflite", "bytes": exported["bytes"], "sha256": exported["sha256"], "precision": exported["chosen"],
                  "architecture": "islr_lite", "parameters": int(model.count_params()), "temperature": temperature, "mirror_average": mirror_average},
        "classes": class_entries,
        "unknown_class": UNKNOWN if UNKNOWN in classes else None,
        "tiers": tiers,
        "badge": BADGE,
        "confidence": {"sure": 0.6, "unsure": 0.25, "speak": "never automatically: every sign is Tier B, so the person confirms first"},
        "licences": LEDGER_IDS,
        "attribution": [json.loads(json.dumps(_attribution(i))) for i in LEDGER_IDS],
        "metrics": {
            "device_held_out": {"protocol": "trained on computer-camera recordings, tested on phone recordings; weaker (no signer ids)",
                                "fair_test": held["fair_test"], "top1_all_phone": held["islr_lite"]["plain_all_phone"]["top1"],
                                "not_measured": held["untrained_in_this_protocol"], "label_conflicts": held["label_conflicts"],
                                "top1": (held["islr_lite"]["mirror_average"] if mirror_average else held["islr_lite"]["plain"])["top1"],
                                "top5": (held["islr_lite"]["mirror_average"] if mirror_average else held["islr_lite"]["plain"])["top5"],
                                "measured_on": "the same recipe trained without the phone folder (the shipped model also learned from it)"},
            "calibration_part": {"protocol": "10 % of both folders, same people and sessions (weaker)", "top1": validation["top1"], "top5": validation["top5"]},
            **({"independent_signer": {"protocol": "SLT PSL dictionary clips (CC BY 4.0): one performer absent from SignSpeak, one clip per sign; a different dictionary, so a miss can also be a regional variant",
                                       "samples": result["independent_signer"]["samples"], "top1": result["independent_signer"]["top1"],
                                       "top5": result["independent_signer"]["top5"]}} if "independent_signer" in result else {}),
        },
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    (args.out / "measurements.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    (args.out / "parity_cases.json").write_text(json.dumps(parity_cases(blob, data, final_val, labels, classes)), encoding="utf-8")
    report = markdown(result)
    (args.out / "report.md").write_text(report, encoding="utf-8")
    print("===PSL-REPORT-BEGIN===")
    print(report)
    print("===PSL-REPORT-END===")
    return 0


def _attribution(ledger_id: str) -> dict:
    entry = assert_allowed(ledger_id, "redistribute_weights")
    return {"ledger_id": ledger_id, "text": entry.get("attribution", ""), "licence": entry.get("licence", "")}


if __name__ == "__main__":
    raise SystemExit(main())
