"""Licence ledger entries for clips found on the web (master-v3 Stage 1, step 3; CLAUDE.md 4 and 9.2).

The rule: a clip is downloaded only if data/LICENSES.yaml already holds an entry for it whose uses
allow what the pipeline will do (data_engine.ledger.assert_allowed). So the pipeline runs in two steps:

  search  -> candidates + draft ledger entries   (metadata only; nothing is downloaded)
  commit the entries to data/LICENSES.yaml       (reviewable in git; the licence decision is visible)
  fetch   -> downloads only clips whose committed entry allows it

Dataset-level entries (for example `psl-slt-dictionary`) cover all their clips, so those clips need no
new entry. Web finds get one entry per clip, id `web-<source>-<key>`.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Iterable

import yaml

from data_engine.ledger import LicenceError, assert_allowed, load_ledger, validate_ledger
from tools.web_learn import licences
from tools.web_learn.sources import Candidate, candidate_key

PLATFORM_NAMES = {"commons": "Wikimedia Commons", "archive": "Internet Archive", "youtube": "YouTube", "slt": "GitHub (SLT)"}
FETCH_USE = "pretrain_encoder"  # the least a fetched clip must allow; labels additionally need train_labels


def entry_id(candidate: Candidate) -> str:
    return candidate.ledger_id or f"web-{candidate.source}-{candidate_key(candidate)}"


def draft_entry(candidate: Candidate, today: str | None = None) -> dict:
    """A ledger entry for one web clip, from its licence metadata."""
    today = today or dt.date.today().isoformat()
    uses = licences.allowed_uses(candidate.licence_id)
    is_psl = candidate.language == "PSL"
    if not is_psl:
        # Language purity (master-v3 9.4): a clip not shown to be PSL never carries labels into PSL.
        uses["train_labels"] = False
        uses["reference_clip"] = False
    conditions = licences.conditions(candidate.licence_id)
    if not is_psl:
        conditions.append("language_unconfirmed")
    status = "cleared_with_conditions" if (uses["pretrain_encoder"] or uses["train_labels"]) else "permission_needed"
    platform = PLATFORM_NAMES.get(candidate.source, candidate.source)
    title = candidate.title.strip()[:120]
    return {
        "id": entry_id(candidate),
        "name": f"{platform}: {title}",
        "kind": "reference_clips",
        "sign_language": "PSL" if is_psl else "none",
        "label_scope": "psl" if is_psl else "none",
        "source_url": candidate.page_url,
        "licence": candidate.licence_id,
        "licence_evidence": f"{platform} metadata: {candidate.licence_raw!r} (read {candidate.found_on} by tools/web_learn).",
        "allowed_uses": uses,
        "conditions": conditions,
        "attribution": f"\"{title}\" by {candidate.uploader}, {candidate.licence_id}, via {platform}.",
        "status": status,
        "checked_on": today,
        "checked_by": "agent (tools/web_learn)",
        "files": [{"path": f"data/web_learned/*/{entry_id(candidate)}*"}] if status != "permission_needed" else [],
        "facts": {"platform": candidate.source, "platform_id": candidate.source_id, "uploader": candidate.uploader,
                  "proposed_gloss": candidate.gloss, "label_evidence": candidate.label_evidence or "none",
                  "language_hint": candidate.language},
        "notes": "Found by the web-learning pipeline. Web-learned signs start as Tier B and need the "
                 "signer-independent gate and a Deaf validator before Tier A (CLAUDE.md 9.3).",
    }


def entries_to_add(candidates: Iterable[Candidate], ledger: dict) -> list[dict]:
    """Draft entries for candidates that have no ledger entry yet (dataset-covered clips are skipped)."""
    existing = {asset["id"] for asset in ledger["assets"]}
    out, seen = [], set()
    for candidate in candidates:
        if candidate.ledger_id and candidate.ledger_id in existing:
            continue
        draft = draft_entry(candidate)
        if draft["id"] not in existing and draft["id"] not in seen:
            seen.add(draft["id"])
            out.append(draft)
    return out


def append_entries(path: Path, entries: list[dict]) -> int:
    """Add entries to the ledger file (YAML) and re-validate the whole ledger. Returns how many were added."""
    if not entries:
        return 0
    ledger = load_ledger(path)
    ledger["assets"].extend(entries)
    errors = validate_ledger(ledger)
    if errors:
        raise ValueError("the ledger would become invalid: " + "; ".join(errors[:5]))
    block = yaml.safe_dump(entries, sort_keys=False, allow_unicode=True, width=110)
    text = Path(path).read_text(encoding="utf-8").rstrip("\n") + "\n\n  # --- added by tools/web_learn ---\n"
    text += "".join(f"  {line}\n" if line else "\n" for line in block.splitlines())
    Path(path).write_text(text, encoding="utf-8")
    if len(load_ledger(path)["assets"]) != len(ledger["assets"]):
        raise ValueError("the ledger did not round-trip after appending entries")
    return len(entries)


def fetch_refusal(candidate: Candidate, ledger: dict) -> str | None:
    """Why a clip must not be downloaded, or None. The ledger decides; platform rules come first."""
    if candidate.source == "youtube" or not candidate.media_url:
        return "platform terms do not allow downloading (listed for embedding or a permission request)"
    try:
        assert_allowed(entry_id(candidate), FETCH_USE, purpose_language="PSL", ledger=ledger)
    except LicenceError as error:
        if "is not in data/LICENSES.yaml" in str(error):
            return f"no ledger entry {entry_id(candidate)} yet (commit the drafted entries first)"
        return str(error)
    return None


def label_allowed(ledger_id: str, ledger: dict) -> bool:
    """May clips under this ledger entry carry PSL labels (train_labels for PSL)?"""
    try:
        assert_allowed(ledger_id, "train_labels", purpose_language="PSL", ledger=ledger)
        return True
    except LicenceError:
        return False


def manifest_problems(manifest: dict, ledger: dict) -> list[str]:
    """Every clip in a web_learned manifest must be allowed by the ledger for what the manifest claims."""
    problems = []
    for clip in manifest.get("clips", []):
        ledger_id = clip.get("ledger_id", "")
        try:
            assert_allowed(ledger_id, FETCH_USE, purpose_language="PSL", ledger=ledger)
        except LicenceError as error:
            problems.append(f"{clip.get('clip_id')}: {error}")
            continue
        if clip.get("label_status") in {"accepted", "variant", "single_source"}:
            try:
                assert_allowed(ledger_id, "train_labels", purpose_language="PSL", ledger=ledger)
            except LicenceError as error:
                problems.append(f"{clip.get('clip_id')}: has a PSL label but {error}")
    return problems
