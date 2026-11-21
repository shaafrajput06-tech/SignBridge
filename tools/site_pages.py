"""Builds shared_data/site_pages.json for the website's "How well it works", "Credits and licences" and
"What's new" pages (master-v3 Stage 7). Every number is read from a committed report file, never typed by
hand; tests/test_site_pages.py fails if the committed JSON and the reports disagree.

    python tools/site_pages.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "shared_data" / "site_pages.json"

# Ledger entries the shipped website uses, and how (descriptions only; licences come from the ledger).
SHIPPED = {
    "psl-signspeak-words": "Trains the PSL recogniser (hand landmarks of 70+ words).",
    "psl-slt-dictionary": "PSL dictionary videos (\"how it is signed\", dictionary page) and the independent-signer check.",
    "asl-islr-1st-place-tflite": "The ASL mode recogniser (250 ASL words).",
    "asl-gislr-competition-data": "The data the ASL recogniser was trained on.",
    "asl-gislr-rerun-set": "Measures the ASL recogniser on signers it never saw.",
    "mediapipe-hand-landmarker": "Finds both hands in the camera picture, on the device.",
    "mediapipe-pose-landmarker-lite": "Finds the shoulders and arms, on the device.",
    "mediapipe-face-landmarker": "Finds the face, on the device.",
    "signbridge-vocabulary": "The 64 English and Urdu phrases.",
}
SOFTWARE_LICENCES = {"react": "MIT", "react-dom": "MIT", "@mediapipe/tasks-vision": "Apache-2.0", "@litertjs/core": "Apache-2.0", "vite": "MIT"}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def psl_section() -> dict | None:
    manifest = read_json(ROOT / "models" / "psl" / "manifest.json")
    measured = read_json(ROOT / "reports" / "psl_v3_measurements.json")
    if not manifest or not measured:
        return None
    held = measured["device_held_out"]
    shipped_recipe = held["islr_lite"]["mirror_average" if manifest["model"]["mirror_average"] else "plain"]
    signs = [c for c in manifest["classes"] if c.get("tier")]
    return {
        "bundle": manifest["version"], "trained": manifest["created"], "source_report": "reports/psl_v3_run.md",
        "dataset": measured["data"]["source"], "samples": measured["data"]["samples"], "devices": measured["data"]["devices"],
        "signs": len(signs), "tiers": {"A": manifest["tiers"]["A"], "B": manifest["tiers"]["B"]}, "badge": manifest["badge"],
        "device_held_out": {
            "protocol": manifest["metrics"]["device_held_out"]["protocol"],
            "fair_test": held.get("fair_test"),
            "top1": shipped_recipe["top1"], "top5": shipped_recipe["top5"],
            "one_handed": shipped_recipe["one_handed"], "two_handed": shipped_recipe["two_handed"],
            "top1_all_phone": held["islr_lite"].get("plain_all_phone", {}).get("top1"),
            "gru_top1": held["gru"]["plain"]["top1"],
            "left_right": held.get("left_right"),
            "calibration_error": shipped_recipe["expected_calibration_error"],
            "speak_limits": shipped_recipe["speak_limits"],
            "not_measured": held.get("untrained_in_this_protocol", []),
            "label_conflicts": held.get("label_conflicts", []),
        },
        "independent_signer": {k: measured["independent_signer"][k] for k in ("samples", "top1", "top5")} if measured.get("independent_signer") else None,
        "personal_adaptation": held.get("personal_adaptation"),
        "model": {k: manifest["model"][k] for k in ("bytes", "precision", "architecture", "parameters", "sha256")},
        "per_sign": [{"english": c["english"], "urdu": c.get("urdu", ""), "hands": c["hands"], "tier": c["tier"],
                      "tested": c.get("device_held_out", {}).get("samples", 0), "top1": c.get("device_held_out", {}).get("top1"),
                      "top5": c.get("device_held_out", {}).get("top5"), "note": c.get("data_note", ""),
                      "dictionary_url": c.get("dictionary_url", "")} for c in signs],
    }


def asl_section() -> dict:
    path = ROOT / "reports" / "asl_eval_results_2026-11-20.json"
    data = read_json(path)
    s = data["summary"]
    speak = next(c for c in s["calibration"] if c["threshold"] == 0.7)
    sure = next(c for c in s["calibration"] if c["threshold"] == 0.6)
    return {
        "source_report": str(path.relative_to(ROOT)), "dataset": data["dataset"]["name"], "samples": s["samples"],
        "measured_on": data["measured_on"][:10], "where": data["source"],
        "top1": s["native"]["top1"], "top5": s["native"]["top5"],
        "browser_frames": s["best_fixed_length"]["frames"], "browser_top1": s["best_fixed_length"]["top1"],
        "left_dominant_top1": s["groups"]["dominant_left"]["top1"], "right_dominant_top1": s["groups"]["dominant_right"]["top1"],
        "two_handed": s["groups"]["two_handed"],
        "speak_at": 0.7, "wrong_when_spoken": round(1 - speak["accuracy_when_covered"], 4), "spoken_share": round(speak["coverage"], 4),
        "wrong_at_pretty_sure": round(1 - sure["accuracy_when_covered"], 4),
    }


def web_learn_section() -> dict:
    path = ROOT / "reports" / "web_learn_v1.md"
    text = path.read_text(encoding="utf-8")

    def number(pattern: str) -> int:
        match = re.search(pattern, text)
        if not match:
            raise ValueError(f"{path.name}: no match for {pattern!r}")
        return int(match.group(1))

    return {"source_report": str(path.relative_to(ROOT)), "kept": number(r"Kept: (\d+)"),
            "rejected": number(r"Rejected by the quality or language checks: (\d+)"),
            "vocabulary_covered": number(r"With at least one usable clip: (\d+)"),
            "vocabulary_total": number(r"Vocabulary entries: (\d+)"),
            "dictionary_labels": number(r"dictionary labels: (\d+)"),
            "outside_vocabulary": number(r"Dictionary signs outside the vocabulary with a usable clip: (\d+)")}


def credits_section() -> dict:
    ledger = yaml.safe_load((ROOT / "data" / "LICENSES.yaml").read_text(encoding="utf-8"))
    by_id = {e["id"]: e for e in ledger["assets"]}
    assets = []
    for asset_id, use in SHIPPED.items():
        e = by_id[asset_id]
        assets.append({"id": asset_id, "name": e["name"], "licence": e["licence"], "attribution": e.get("attribution", ""),
                       "source_url": e.get("source_url", ""), "used_for": use, "checked": str(e.get("date_checked", ""))})
    package = json.loads((ROOT / "web" / "package.json").read_text(encoding="utf-8"))
    software = [{"name": name, "version": version, "licence": SOFTWARE_LICENCES.get(name, "see the package")}
                for name, version in sorted({**package.get("dependencies", {}), **package.get("devDependencies", {})}.items())]
    return {"source": "data/LICENSES.yaml and web/package.json", "assets": assets, "software": software}


def whats_new_section() -> list:
    sections, current = [], None
    for line in (ROOT / "docs" / "WHATS_NEW.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current = {"title": line[3:].strip(), "items": []}
            sections.append(current)
        elif line.startswith("- ") and current is not None:
            current["items"].append(line[2:].strip())
    return sections


def build() -> dict:
    performance = read_json(ROOT / "reports" / "performance_v3.json")
    return {"about": "Generated by tools/site_pages.py from committed reports; do not edit by hand.",
            "psl": psl_section(), "asl": asl_section(), "web_learn": web_learn_section(),
            "performance": performance, "credits": credits_section(), "whats_new": whats_new_section()}


if __name__ == "__main__":
    OUT.write_text(json.dumps(build(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    sys.exit(0)
