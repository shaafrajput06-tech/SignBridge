"""Word list and search queries for the web-learning pipeline (master-v3 Stage 1, steps 1-2).

Words come from SignBridge's own vocabulary (English, Urdu, Roman Urdu) plus, when it is available,
the label list of the licensed SLT PSL dictionary (pk-hfad-1, about 780 signs). Queries are written
from fixed templates in English, Urdu and Roman Urdu. A language model may later suggest extra query
wordings (master-v3 9.5 allows queries), but it never decides a label.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VOCABULARY = ROOT / "vocabulary.json"


@dataclass
class Word:
    gloss: str                      # SignBridge gloss id, or "slt:<label>" for dictionary-only words
    english: str
    urdu: str = ""
    roman_urdu: str = ""
    synonyms: list[str] = field(default_factory=list)
    in_vocabulary: bool = True


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def vocabulary_words(path: Path = VOCABULARY) -> list[Word]:
    words = []
    for entry in json.loads(Path(path).read_text(encoding="utf-8")):
        words.append(Word(gloss=entry["id"], english=_clean(entry["english"]), urdu=_clean(entry.get("urdu", "")),
                          roman_urdu=_clean(entry.get("romanUrdu", "")), synonyms=[]))
    return words


def slt_label_words(labels: list[str], known: list[Word]) -> list[Word]:
    """Dictionary labels such as 'doctor.physician' or 'play.sports' become extra words.

    A label whose first part matches a vocabulary word (English, case-insensitive) is folded into that
    word as a synonym instead, so each sign is searched once.
    """
    by_english = {w.english.lower(): w for w in known}
    extra: dict[str, Word] = {}
    for label in labels:
        parts = [p.replace("_", " ").strip() for p in label.split(".") if p.strip()]
        if not parts:
            continue
        head = parts[0].lower()
        if head in by_english:
            word = by_english[head]
            for part in parts[1:]:
                if part.lower() not in {s.lower() for s in word.synonyms} and part.lower() != word.english.lower():
                    word.synonyms.append(part)
            continue
        key = f"slt:{label}"
        extra.setdefault(key, Word(gloss=key, english=parts[0], synonyms=parts[1:], in_vocabulary=False))
    return known + sorted(extra.values(), key=lambda w: w.gloss)


EN_TEMPLATES = ("Pakistan Sign Language {w}", "PSL sign for {w}", "{w} in Pakistan sign language")
UR_TEMPLATES = ("{w} اشارہ", "{w} اشاروں کی زبان")
ROMAN_TEMPLATES = ("{w} ishara", "{w} PSL sign")


def queries(word: Word) -> list[str]:
    """Search phrases for one word, deduplicated, English first."""
    out: list[str] = []
    for english in [word.english, *word.synonyms]:
        out.extend(t.format(w=english) for t in EN_TEMPLATES)
    if word.urdu:
        out.extend(t.format(w=word.urdu) for t in UR_TEMPLATES)
    if word.roman_urdu and word.roman_urdu.lower() != word.english.lower():
        out.extend(t.format(w=word.roman_urdu) for t in ROMAN_TEMPLATES)
    seen, unique = set(), []
    for q in out:
        if q.lower() not in seen:
            seen.add(q.lower())
            unique.append(q)
    return unique
