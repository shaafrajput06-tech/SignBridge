"""Write notebooks/asl_mode_eval.ipynb from tools/asl_eval_core.py plus the driver cells below.

    python tools/build_asl_eval_notebook.py

The notebook runs on Kaggle with "Run all" (docs/HOW_TO_RUN_ASL_EVAL.md). Its evaluation code is a
verbatim copy of tools/asl_eval_core.py, which tests/test_asl_eval.py unit-tests; the same test
fails if the notebook is out of date.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "tools" / "asl_eval_core.py"
SPEC = ROOT / "shared_data" / "asl_islr_spec.json"
OUT = ROOT / "notebooks" / "asl_mode_eval.ipynb"

INTRO = """# SignBridge ASL mode: accuracy on signers the model never saw

This notebook measures the ASL model that SignBridge's ASL mode uses (the 1st-place model of Google's
Isolated Sign Language Recognition competition, MIT licence) on the competition's **rerun set**: the
hidden test data, released under CC0, whose signers are reported not to be in the training data.

**How to run:** follow `docs/HOW_TO_RUN_ASL_EVAL.md`. In short: add the dataset *ASL Isolated Sign
Recognition Rerun Set* as input, switch Internet on (or add your copy of `model.tflite`), then
**Run all**. It takes roughly 30-90 minutes on Kaggle's free CPU.

**What to send back:** the file `asl_eval_results.json` from the Output panel (or copy the block printed
by the last cell).

Nothing here trains anything. Every number it prints is measured, with the dataset and the date."""

SETTINGS = """# Settings. You do not need to change these.
FIXED_LENGTHS = [16, 24, 32, 48, 64]   # frame counts the browser could use; compared with the native length
FIXED_EVERY = 5                       # test the fixed lengths on every 5th sample (they take 5x the time)
MAX_SAMPLES = None                    # None = all samples; a number = a quicker, shorter run
INPUT_ROOT = "/kaggle/input"
OUTPUT_FILE = "/kaggle/working/asl_eval_results.json"
MODEL = {MODEL}
CLASSES = {CLASSES}
"""

LOAD_MODEL = """import json, os, time, datetime, urllib.request
import numpy as np

def get_pinned(item, name):
    found = find_pinned_file(INPUT_ROOT, name, item["sha256"])
    if found:
        print(f"Using the attached {name}: {found}")
        return found
    target = f"/kaggle/working/{name}"
    if not os.path.exists(target) or sha256_of(target) != item["sha256"]:
        print(f"Downloading {name} from {item['url']} (needs Internet switched on in the notebook settings)")
        urllib.request.urlretrieve(item["url"], target)
    if sha256_of(target) != item["sha256"]:
        raise SystemExit(f"{name} is not the pinned file (SHA-256 {sha256_of(target)}). Stop: do not evaluate a different model.")
    return target

model_path = get_pinned(MODEL, "model.tflite")
classes_path = get_pinned(CLASSES, "sign_to_prediction_index_map.json")
index_map = json.load(open(classes_path))
labels = [None] * len(index_map)
for label, index in index_map.items():
    labels[index] = label
assert len(labels) == 250 and None not in labels

try:
    from ai_edge_litert.interpreter import Interpreter
    runtime = "ai-edge-litert"
except ImportError:
    import tensorflow as tf
    Interpreter = tf.lite.Interpreter
    runtime = f"tensorflow {tf.__version__}"
interpreter = Interpreter(model_path=model_path)
runner = interpreter.get_signature_runner("serving_default")
def predict(sequence):
    return runner(inputs=np.asarray(sequence, dtype=np.float32))["outputs"]
print("Model ready:", runtime, "| input", interpreter.get_input_details()[0]["shape_signature"])
"""

FIND_DATA = """found = find_label_csv(INPUT_ROOT)
if found is None:
    raise SystemExit("No CSV with 'path' and 'sign' columns was found. Add the 'ASL Isolated Sign Recognition Rerun Set' dataset as input.")
csv_path, columns = found
import pandas as pd
table = pd.read_csv(csv_path)
base = os.path.dirname(csv_path)
def resolve(relative):
    for candidate in (os.path.join(base, relative), os.path.join(INPUT_ROOT, relative)):
        if os.path.exists(candidate):
            return candidate
    for folder, _dirs, files in os.walk(base):
        if os.path.basename(relative) in files:
            return os.path.join(folder, os.path.basename(relative))
    return None
unknown = sorted(set(table[columns["sign"]]) - set(labels))
print(f"Label file: {csv_path}")
print(f"Samples: {len(table)} | signs: {table[columns['sign']].nunique()} | signers: {table[columns['participant']].nunique() if columns['participant'] else 'not given'}")
if unknown:
    print("Signs not in the model's 250 (skipped):", unknown[:20])
table = table[table[columns["sign"]].isin(labels)].reset_index(drop=True)
if MAX_SAMPLES:
    table = table.iloc[::max(1, len(table) // MAX_SAMPLES)].head(MAX_SAMPLES).reset_index(drop=True)

# Optional: if the competition's own train.csv is attached too, check that no rerun signer was in training.
train_overlap = None
competition = find_label_csv(INPUT_ROOT, exclude=[csv_path])
if competition and columns["participant"] and competition[1]["participant"]:
    train_ids = set(pd.read_csv(competition[0])[competition[1]["participant"]])
    train_overlap = sorted(set(table[columns["participant"]]) & train_ids)
    print(f"Signers also in {competition[0]}: {train_overlap if train_overlap else 'none'}")
"""

LAYOUT = """# The competition layout: every frame's rows go face, left_hand, pose, right_hand.
layout_checked = 0
for relative in table[columns["path"]].head(5):
    path = resolve(relative)
    if path:
        load_sequence(path, check_order=True)
        layout_checked += 1
print(f"Row order checked on {layout_checked} files: face, left_hand, pose, right_hand")
"""

RUN = """records, facts, errors = [], [], []
started = time.time()
for i, row in table.iterrows():
    path = resolve(row[columns["path"]])
    if path is None:
        errors.append(f"missing file {row[columns['path']]}")
        continue
    try:
        sequence = load_sequence(path)
        if len(sequence) == 0:
            errors.append(f"empty {row[columns['path']]}")
            continue
        record = evaluate_sample(sequence, labels.index(row[columns["sign"]]), predict, FIXED_LENGTHS if i % FIXED_EVERY == 0 else ())
        record["participant"] = None if not columns["participant"] else str(row[columns["participant"]])
        records.append(record)
        facts.append(convention_facts(sequence))
    except Exception as error:
        errors.append(f"{row[columns['path']]}: {error}")
    if (i + 1) % 1000 == 0:
        done = sum(r['native_top5'][0] == r['sign'] for r in records) / max(1, len(records))
        print(f"{i + 1}/{len(table)} samples, {time.time() - started:.0f} s, top-1 so far {done:.3f}")
print(f"Finished {len(records)} samples in {time.time() - started:.0f} s; {len(errors)} could not be read")
"""

SUMMARY = """summary = summarise(records, labels)
results = {
    "notebook": "notebooks/asl_mode_eval.ipynb",
    "measured_on": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    "dataset": {"name": "ASL Isolated Sign Recognition Rerun Set", "label_file": csv_path, "samples_listed": int(len(table)),
                "samples_evaluated": len(records), "unreadable": len(errors), "first_errors": errors[:10],
                "signers": sorted({r["participant"] for r in records if r["participant"] is not None}),
                "signers_also_in_training_csv": train_overlap},
    "model": {"sha256": MODEL["sha256"], "runtime": runtime},
    "machine": {"cpu_count": os.cpu_count(), "note": "Kaggle notebook CPU; latency here is not the laptop's"},
    "layout_files_checked": layout_checked,
    "conventions": convention_summary(facts, records),
    "summary": summary,
}
json.dump(results, open(OUTPUT_FILE, "w"), indent=1)
short = {key: results[key] for key in ("measured_on", "model", "conventions")}
short["dataset"] = {k: v for k, v in results["dataset"].items() if k != "signers"}
short["summary"] = {k: v for k, v in summary.items() if k not in ("per_sign",)}
print(json.dumps(short, indent=1))
print(f"\\nSaved {OUTPUT_FILE}. Download it from the Output panel and attach it in the SignBridge chat.")
"""


def code(source: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": source.splitlines(keepends=True)}


def markdown(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}


def build() -> dict:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    model = {key: spec["model"][key] for key in ("url", "sha256")}
    classes = {key: spec["classes"][key] for key in ("url", "sha256")}
    settings = SETTINGS.replace("{MODEL}", json.dumps(model)).replace("{CLASSES}", json.dumps(classes))
    cells = [markdown(INTRO), code(settings), markdown("## The evaluation code (a copy of tools/asl_eval_core.py)"),
             code(CORE.read_text(encoding="utf-8")), markdown("## Model"), code(LOAD_MODEL), markdown("## Data"),
             code(FIND_DATA), code(LAYOUT), markdown("## Run"), code(RUN), markdown("## Results"), code(SUMMARY)]
    return {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                         "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(build(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
