"""Licences of clips found on the internet, and what each one lets SignBridge do (CLAUDE.md 4, 9.2).

A clip is used only for what its licence (or the owner's written permission) allows. Licence text from
a platform is normalised to an SPDX-like id, then mapped to the ledger's six uses. Anything unknown,
"all rights reserved", non-commercial or no-derivatives is NOT trainable: it becomes a permission
request for the owner [ME] instead. The mapping is deliberately conservative.
"""

from __future__ import annotations

import re

USES = ("pretrain_encoder", "train_labels", "evaluate", "reference_clip", "redistribute_weights", "redistribute_data")

# id -> (allowed uses, conditions). Landmarks extracted from a video are a derivative of it, so ND
# licences allow nothing but showing the original; NC licences are left to written permission.
_RULES: dict[str, tuple[dict[str, bool], list[str]]] = {
    "CC0-1.0": ({u: True for u in USES}, []),
    "PDM-1.0": ({u: True for u in USES}, []),
    "CC-BY-4.0": ({u: True for u in USES}, ["attribution"]),
    "CC-BY-3.0": ({u: True for u in USES}, ["attribution"]),
    "CC-BY-2.0": ({u: True for u in USES}, ["attribution"]),
    "CC-BY": ({u: True for u in USES}, ["attribution", "licence_version_unstated"]),
    # Share-alike: data may be shared under the same licence; trained weights are not shipped from
    # share-alike data until that question has a clear answer.
    "CC-BY-SA-4.0": ({**{u: True for u in USES}, "redistribute_weights": False}, ["attribution", "share_alike"]),
    "CC-BY-SA-3.0": ({**{u: True for u in USES}, "redistribute_weights": False}, ["attribution", "share_alike"]),
    "CC-BY-SA-2.0": ({**{u: True for u in USES}, "redistribute_weights": False}, ["attribution", "share_alike"]),
    "CC-BY-SA": ({**{u: True for u in USES}, "redistribute_weights": False}, ["attribution", "share_alike", "licence_version_unstated"]),
    "CC-BY-ND": ({**{u: False for u in USES}, "reference_clip": True}, ["attribution", "no_derivatives"]),
    "CC-BY-NC": ({u: False for u in USES}, ["attribution", "non_commercial"]),
    "YOUTUBE-CC-BY": ({u: False for u in USES}, ["attribution", "platform_terms_forbid_download"]),
    "UNKNOWN": ({u: False for u in USES}, []),
}
# Licences that allow nothing until the owner gives written permission (drafted for the owner [ME]).
PERMISSION_LICENCES = {"CC-BY-NC", "YOUTUBE-CC-BY", "UNKNOWN"}


def normalise(text: str | None, platform: str = "") -> str:
    """'CC BY-SA 4.0', 'https://creativecommons.org/licenses/by/4.0/', 'Public domain' ... -> rule id."""
    raw = (text or "").strip().lower()
    if platform == "youtube":
        # YouTube's "Creative Commons" option is CC BY 3.0, but YouTube's terms forbid downloading
        # other than through YouTube's own features, so such videos are never fetched (master-v3 9.2).
        return "YOUTUBE-CC-BY" if "creative" in raw or "cc" in raw else "UNKNOWN"
    if not raw:
        return "UNKNOWN"
    if "publicdomain/zero" in raw or re.search(r"\bcc0\b", raw) or "cc-zero" in raw:
        return "CC0-1.0"
    if "publicdomain/mark" in raw or raw in {"pd", "public domain", "pdm", "public domain mark"} or raw.startswith("pd-"):
        return "PDM-1.0"
    url_match = re.search(r"creativecommons\.org/licenses/([a-z-]+)/(\d\.\d)", raw)
    if url_match:
        kind, version = url_match.groups()
    else:
        text_match = re.search(r"\bcc[ -]?((?:by)(?:[ -](?:nc|nd|sa))*)[ -]?(\d\.\d)?", raw)
        if not text_match:
            return "UNKNOWN"
        kind, version = text_match.group(1).replace(" ", "-"), text_match.group(2) or ""
    parts = kind.split("-")
    if "nc" in parts:
        return "CC-BY-NC"
    if "nd" in parts:
        return "CC-BY-ND"
    base = "CC-BY-SA" if "sa" in parts else "CC-BY"
    if version in {"4.0", "3.0", "2.0"}:
        return f"{base}-{version}"
    return base  # version missing or unusual (e.g. 2.5): same uses, recorded as "licence_version_unstated"


def allowed_uses(licence_id: str) -> dict[str, bool]:
    return dict(_RULES.get(licence_id, _RULES["UNKNOWN"])[0])


def conditions(licence_id: str) -> list[str]:
    return list(_RULES.get(licence_id, _RULES["UNKNOWN"])[1])


def trainable(licence_id: str) -> bool:
    uses = allowed_uses(licence_id)
    return uses["train_labels"] or uses["pretrain_encoder"]


def needs_permission(licence_id: str) -> bool:
    return licence_id in PERMISSION_LICENCES or licence_id not in _RULES
