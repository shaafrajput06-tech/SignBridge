"""The web-learning pipeline: search -> ledger -> fetch + extract -> quality -> language -> cross-check -> report.

Run on a machine with internet (GitHub Actions: .github/workflows/web-learn.yml), never inside the app:

    python -m tools.web_learn search --version 1            candidates + draft ledger entries (no downloads)
    python -m tools.web_learn add-ledger --version 1        append the drafts to data/LICENSES.yaml (then commit)
    python -m tools.web_learn fetch --version 1             download only ledger-allowed clips, extract, report
    python -m tools.web_learn check                         every manifest entry is allowed by the ledger

Outputs: data/web_learn/candidates_vN.json and ledger_drafts_vN.yaml (metadata, committed);
data/web_learned/vN/ (landmark .npz files + manifest.json; data, never committed); reports/web_learn_vN.md.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import tempfile
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable

import yaml

from data_engine.ledger import LEDGER_PATH, load_ledger
from tools.web_learn import ledger as web_ledger
from tools.web_learn import licences
from tools.web_learn.sources import (SLT_MAPPING_URL, USER_AGENT, Candidate, get_json, mapping_pairs, search_all, slt_candidates,
                                     slt_clips, vocabulary_labels)
from tools.web_learn.words import vocabulary_words, slt_label_words

ROOT = Path(__file__).resolve().parents[2]
META_DIR = ROOT / "data" / "web_learn"
DATA_DIR = ROOT / "data" / "web_learned"
REPORTS = ROOT / "reports"
MAX_DOWNLOAD_BYTES = 150 * 1024 * 1024


def candidates_path(version: int) -> Path:
    return META_DIR / f"candidates_v{version}.json"


# --------------------------------------------------------------------------- search

def run_search(version: int, youtube_key: str | None = None, web_words: int | None = None, log: Callable[[str], None] = print) -> dict:
    vocabulary = vocabulary_words()
    clips = slt_clips()
    words = slt_label_words([c["label"] for c in clips], vocabulary)
    labels = {c["label"] for c in clips}
    try:
        pairs = mapping_pairs(get_json(SLT_MAPPING_URL), labels)
    except Exception as error:  # noqa: BLE001
        pairs = []
        log(f"dictionary mapping file not read: {error}")
    mapped = vocabulary_labels(words, pairs, labels)
    found = slt_candidates(words, clips, mapped)
    log(f"SLT dictionary: {len(clips)} clips; mapping file pairs: {len(pairs)}; vocabulary words with a clip: "
        f"{len({g for g, _ in mapped.values()})} via {len(mapped)} labels")
    for label, (gloss, evidence) in sorted(mapped.items(), key=lambda item: item[1][0]):
        log(f"  {gloss} <- {evidence}")
    web_targets = [w for w in words if w.in_vocabulary][: web_words or None]
    web, problems = search_all(web_targets, youtube_key=youtube_key, log=log)
    candidates = found + web
    ledger = load_ledger()
    drafts = web_ledger.entries_to_add(candidates, ledger)
    for candidate in candidates:
        candidate.ledger_id = web_ledger.entry_id(candidate)
    META_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": version,
        "searched_on": dt.date.today().isoformat(),
        "words": {"vocabulary": len(vocabulary), "dictionary_labels": len(clips), "total": len(words),
                  "web_searched": [w.gloss for w in web_targets]},
        "dictionary_mapping": {"url": SLT_MAPPING_URL, "pairs": len(pairs),
                               "vocabulary_labels": {label: list(value) for label, value in sorted(mapped.items())}},
        "sources_searched": ["slt"] + ["commons", "archive"] + (["youtube"] if youtube_key else []),
        "problems": problems,
        "candidates": [c.to_dict() for c in candidates],
    }
    candidates_path(version).write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (META_DIR / f"ledger_drafts_v{version}.yaml").write_text(
        yaml.safe_dump(drafts, sort_keys=False, allow_unicode=True, width=110), encoding="utf-8")
    log(f"{len(candidates)} candidates ({len(web)} from the web), {len(drafts)} draft ledger entries, {len(problems)} problems")
    return payload


def add_ledger(version: int) -> int:
    drafts = yaml.safe_load((META_DIR / f"ledger_drafts_v{version}.yaml").read_text(encoding="utf-8")) or []
    existing = {a["id"] for a in load_ledger()["assets"]}
    return web_ledger.append_entries(LEDGER_PATH, [d for d in drafts if d["id"] not in existing])


# --------------------------------------------------------------------------- fetch + extract

def download(url: str, target: Path) -> str:
    """Stream a file to disk (size-capped) and return its SHA-256."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    digest = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(request, timeout=120) as response, open(target, "wb") as out:  # noqa: S310
        while True:
            block = response.read(1 << 20)
            if not block:
                break
            size += len(block)
            if size > MAX_DOWNLOAD_BYTES:
                raise ValueError(f"larger than {MAX_DOWNLOAD_BYTES // (1 << 20)} MB")
            digest.update(block)
            out.write(block)
    return digest.hexdigest()


def source_group(candidate: Candidate) -> str:
    """Independent-source key: the same uploader on the same platform counts as one source."""
    return f"{candidate.source}:{(candidate.uploader or 'unknown').strip().lower()}"


def run_fetch(version: int, limit: int | None = None, log: Callable[[str], None] = print, extractor=None, downloader=download) -> dict:
    from ml_engine.recording_v2 import base_meta, write_recording
    from tools.web_learn import extract as ex
    from tools.web_learn import match

    payload = json.loads(candidates_path(version).read_text(encoding="utf-8"))
    candidates = [Candidate.from_dict(c) for c in payload["candidates"]]
    ledger = load_ledger()
    out_dir = DATA_DIR / f"v{version}"
    out_dir.mkdir(parents=True, exist_ok=True)
    if extractor is None:
        from ml_engine.capture_v2 import SplitLandmarkerBackend

        shared_backend, face_counter = SplitLandmarkerBackend(), ex.make_face_counter()
        extractor = lambda path: ex.extract_video(path, backend=shared_backend, face_counter=face_counter)  # noqa: E731
    records, skipped, rejected = [], [], []
    todo = [c for c in candidates if c.download_allowed]
    for candidate in candidates:
        if not candidate.download_allowed:
            skipped.append({"clip": candidate.source_id, "source": candidate.source,
                            "reason": web_ledger.fetch_refusal(candidate, ledger) or f"licence {candidate.licence_id} allows no training use"})
    if limit:
        todo = todo[:limit]
    for number, candidate in enumerate(todo, 1):
        refusal = web_ledger.fetch_refusal(candidate, ledger)
        if refusal:
            skipped.append({"clip": candidate.source_id, "source": candidate.source, "reason": refusal})
            continue
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "clip.bin"
            try:
                sha = downloader(candidate.media_url, video)
                raws, frames, quality = extractor(video)
            except Exception as error:  # noqa: BLE001
                rejected.append({"clip": candidate.source_id, "source": candidate.source, "reasons": [f"could not read: {str(error)[:120]}"]})
                continue
        reasons = ex.rejection_reasons(quality)
        if candidate.language != "PSL":
            reasons.append(f"not shown to be PSL (clip text says: {candidate.language})")
        clip_id = f"{candidate.ledger_id}__{hashlib.sha1(candidate.source_id.encode()).hexdigest()[:8]}"
        record = {"clip_id": clip_id, "ledger_id": candidate.ledger_id, "source": candidate.source, "source_id": candidate.source_id,
                  "source_group": source_group(candidate), "gloss": candidate.gloss, "label_evidence": candidate.label_evidence,
                  "language": candidate.language, "licence": candidate.licence_id, "video_sha256": sha, "quality": quality.to_dict()}
        if reasons:
            rejected.append({"clip": candidate.source_id, "source": candidate.source, "reasons": reasons})
            continue
        if not candidate.label_evidence:
            record["label_note"] = "the clip's own text does not name the word; label comes from the search only"
        gloss_id = re.sub(r"[^A-Za-z0-9_.-]", "-", candidate.gloss.replace(":", "_"))[:64]
        meta = base_meta(source="licensed_clip", gloss_id=gloss_id, signer_id=hashlib.sha1(source_group(candidate).encode()).hexdigest()[:12],
                         session_id=clip_id[:64], device="web-video", camera_orientation_degrees=None, input_mirrored=False,
                         image_width=quality.width, image_height=quality.height, fps=None, consent_id=candidate.ledger_id,
                         consent_recorded=False, signer_id_reliable=False, capture_backend="mediapipe-split-v2",
                         warnings=["web-learned: Tier B until the gate and a Deaf validator pass it"])
        npz = out_dir / f"{clip_id}.npz"
        write_recording(npz, frames, meta)
        record["file"] = npz.name
        record["npz_sha256"] = hashlib.sha256(npz.read_bytes()).hexdigest()
        record["trajectory"] = match.trajectory(frames)
        records.append(record)
        if number % 25 == 0:
            log(f"{number}/{len(todo)} clips processed, {len(records)} kept")

    kept, duplicates = match.deduplicate(records)
    threshold = match.choose_threshold([r for r in kept if r["source"] == "slt"])
    statuses = match.cross_check(kept, threshold["threshold"])
    for record in kept:
        record["label_status"] = statuses.get(record["clip_id"], "single_source")
        if not web_ledger.label_allowed(record["ledger_id"], ledger):
            record["label_status"] = "pretrain_only"
        record.pop("trajectory")
    manifest = {"version": version, "made_on": dt.date.today().isoformat(), "threshold": threshold,
                "clips": kept, "duplicates": [{k: v for k, v in d.items() if k != "trajectory"} for d in duplicates],
                "rejected": rejected, "skipped": skipped}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    problems = web_ledger.manifest_problems(manifest, ledger)
    if problems:
        raise SystemExit("ledger check failed: " + "; ".join(problems[:5]))
    report = write_report(version, payload, manifest)
    log(report)
    return manifest


# --------------------------------------------------------------------------- report

def write_report(version: int, payload: dict, manifest: dict) -> str:
    candidates = payload["candidates"]
    by_source = Counter(c["source"] for c in candidates)
    licensed = Counter(c["source"] for c in candidates if licences.trainable(c["licence_id"]))
    used = Counter(r["source"] for r in manifest["clips"])
    status = Counter(r["label_status"] for r in manifest["clips"])
    reasons = Counter(reason.split(" (")[0] for item in manifest["rejected"] for reason in item["reasons"])
    skip_reasons = Counter(item["reason"].split(" (")[0][:90] for item in manifest["skipped"])
    vocabulary = {w["id"]: w for w in json.loads((ROOT / "vocabulary.json").read_text(encoding="utf-8"))}
    covered = defaultdict(list)
    for record in manifest["clips"]:
        if record["label_status"] in {"accepted", "variant", "single_source"}:
            covered[record["gloss"]].append(record)
    vocab_covered = sorted(g for g in covered if g in vocabulary)
    missing = sorted(set(vocabulary) - set(vocab_covered))
    threshold = manifest["threshold"]
    lines = [
        f"# Web-learned signs v{version}: report",
        "",
        f"Made by `python -m tools.web_learn` on {manifest['made_on']} (search on {payload['searched_on']}). Every number below is a",
        "count from this run. No accuracy is claimed here: web-learned signs start as **Tier B** (CLAUDE.md 9.3).",
        "",
        "## Words",
        "",
        f"- Vocabulary entries: {payload['words']['vocabulary']}; dictionary labels: {payload['words']['dictionary_labels']}; words in the list: {payload['words']['total']}.",
        f"- Searched on the open web (Wikimedia Commons, Internet Archive{', YouTube' if 'youtube' in payload['sources_searched'] else ''}): {len(payload['words']['web_searched'])} vocabulary words.",
        "",
        "## Sources",
        "",
        "| Source | Found | Licence allows training | Used (passed every check) |",
        "|---|---|---|---|",
    ]
    for source in sorted(by_source):
        lines.append(f"| {source} | {by_source[source]} | {licensed[source]} | {used[source]} |")
    lines += [
        "",
        "YouTube results, when searched, are never downloaded (YouTube's terms); they count as found only.",
        f"Search problems: {len(payload['problems'])}." + (f" First: {payload['problems'][0]}" if payload["problems"] else ""),
        "",
        "## Clips",
        "",
        f"- Kept: {len(manifest['clips'])} ({', '.join(f'{k} {v}' for k, v in sorted(status.items())) or 'none'}).",
        f"- Duplicates removed: {len(manifest['duplicates'])}.",
        f"- Rejected by the quality or language checks: {len(manifest['rejected'])}.",
    ]
    lines += [f"  - {reason}: {count}" for reason, count in reasons.most_common()]
    lines.append(f"- Not downloaded: {len(manifest['skipped'])}.")
    lines += [f"  - {reason}: {count}" for reason, count in skip_reasons.most_common(8)]
    lines += [
        "",
        "## Cross-check",
        "",
        f"Known same-sign pairs from different sources: {threshold['known_positive_pairs']}" + (f"; known different-sign pairs: {threshold['known_negative_pairs']}." if threshold.get('known_negative_pairs') is not None else " (different-sign pairs not compared: no threshold possible)."),
        (f"Threshold {threshold['threshold']:.3f} (precision {threshold['precision']:.2f}, recall {threshold['recall']:.2f} on the known pairs)."
         if threshold.get("threshold") is not None else f"Threshold not chosen: {threshold.get('reason')}. No clip was accepted by cross-checking; all stay single-source (Tier B)."),
        "",
        "## Language check",
        "",
        "Clips are kept for PSL labels only when their own source says PSL (the SLT PSL dictionary, or a title or",
        "description naming Pakistan Sign Language). The small PSL-vs-other classifier (master-v3 Stage 1, step 6) needs",
        "the Stage 2 encoder and is not trained yet; until then every other clip is dropped from PSL labels.",
        "",
        "## Coverage of the 64 vocabulary entries",
        "",
        f"- With at least one usable clip: {len(vocab_covered)} ({', '.join(vocab_covered) or 'none'}).",
        f"- Still missing: {len(missing)} ({', '.join(missing)}).",
        f"- Dictionary signs outside the vocabulary with a usable clip: {len([g for g in covered if g not in vocabulary])}.",
        "",
        "Landmarks are in `data/web_learned/v{0}/` (not committed; the workflow uploads them as an artifact).".format(version),
    ]
    text = "\n".join(lines) + "\n"
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / f"web_learn_v{version}.md").write_text(text, encoding="utf-8")
    return text


def check_all() -> list[str]:
    ledger = load_ledger()
    problems = []
    for manifest_path in sorted(DATA_DIR.glob("v*/manifest.json")):
        problems += [f"{manifest_path.parent.name}: {p}" for p in web_ledger.manifest_problems(json.loads(manifest_path.read_text(encoding="utf-8")), ledger)]
    return problems
