"""Central vocabulary loading, lookup, and schema checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
VOCABULARY_PATH = BASE_DIR / "vocabulary.json"


def load_vocabulary(path: Path = VOCABULARY_PATH) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as stream:
        items = json.load(stream)
    validate_vocabulary(items)
    return items


def validate_vocabulary(items: object) -> None:
    if not isinstance(items, list) or not items:
        raise ValueError("Vocabulary must be a non-empty JSON array")
    required = {"id", "english", "urdu", "romanUrdu", "category", "demoAvailable", "audioText"}
    identifiers: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"Vocabulary item {index + 1} must be an object")
        missing = required - item.keys()
        if missing:
            raise ValueError(f"Vocabulary item {index + 1} is missing: {', '.join(sorted(missing))}")
        identifier = item["id"]
        if not isinstance(identifier, str) or not identifier.strip() or identifier in identifiers:
            raise ValueError(f"Vocabulary item {index + 1} has a blank or duplicate ID")
        identifiers.add(identifier)
        for key in ("english", "urdu", "romanUrdu", "category", "audioText"):
            if not isinstance(item[key], str) or not item[key].strip():
                raise ValueError(f"Vocabulary item {identifier} needs text for {key}")
        if not isinstance(item["demoAvailable"], bool):
            raise ValueError(f"Vocabulary item {identifier} has an invalid demoAvailable value")
        if item["demoAvailable"] and not item.get("gestureId"):
            raise ValueError(f"Vocabulary item {identifier} needs a gestureId for the demo")


def vocabulary_by_id() -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in load_vocabulary()}


def display_text(item: dict[str, Any], language: str, roman_urdu: bool = False) -> str:
    if language == "ur":
        return item["romanUrdu"] if roman_urdu else item["urdu"]
    return item["english"]
