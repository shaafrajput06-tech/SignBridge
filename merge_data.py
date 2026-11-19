"""Validate and merge any number of landmark CSV files without deleting sources."""

from __future__ import annotations

import argparse
import csv
import math
from collections import Counter
from datetime import datetime
from pathlib import Path

from collect_data import CSV_HEADER, DATA_PATH, METADATA_COLUMNS
from vocabulary_utils import load_vocabulary


def read_valid_rows(path: Path):
    valid_ids = {item["id"] for item in load_vocabulary()}
    good, bad = [], 0
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        if next(reader, None) != CSV_HEADER:
            raise ValueError(f"Invalid SignBridge CSV schema: {path}")
        for row in reader:
            try:
                if len(row) != len(CSV_HEADER) or row[0] not in valid_ids:
                    raise ValueError
                if not all(math.isfinite(float(value)) for value in row[len(METADATA_COLUMNS):]):
                    raise ValueError
                good.append(row)
            except (ValueError, TypeError):
                bad += 1
    return good, bad


def write_csv(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(CSV_HEADER)
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge SignBridge landmark datasets")
    parser.add_argument("files", nargs="+", help="CSV files to merge")
    parser.add_argument("--update-main", action="store_true", help="ask before replacing the active dataset with the merged result")
    args = parser.parse_args()
    combined: list[list[str]] = []
    total_bad = 0
    sources = [Path(value).resolve() for value in args.files]
    if DATA_PATH.exists() and DATA_PATH.resolve() not in sources:
        sources.insert(0, DATA_PATH.resolve())
    for source in sources:
        rows, malformed = read_valid_rows(source)
        combined.extend(rows)
        total_bad += malformed
        print(f"Read {len(rows)} valid examples from {source.name}; skipped {malformed} malformed rows.")
    unique: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for row in combined:
        key = tuple(row)
        if key not in seen:
            seen.add(key)
            unique.append(row)
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    output = DATA_PATH.parent / f"merged_{datetime.now():%Y%m%d_%H%M%S_%f}.csv"
    write_csv(output, unique)
    print(f"Timestamped merge saved to {output} ({len(unique)} unique examples; {len(combined) - len(unique)} exact duplicates removed).")
    participant_counts = Counter(row[1] for row in unique)
    item_counts = Counter(row[0] for row in unique)
    names = {item["id"]: item["english"] for item in load_vocabulary()}
    print("Examples by participant:")
    for participant, count in sorted(participant_counts.items()):
        print(f"  {participant or 'anonymous'}: {count}")
    print("Examples by vocabulary item:")
    for identifier, count in sorted(item_counts.items(), key=lambda pair: names[pair[0]].casefold()):
        print(f"  {names[identifier]}: {count}")
    if args.update_main:
        if input("Replace the active training CSV with this merged dataset? Original inputs remain untouched. [y/N] ").strip().lower() == "y":
            write_csv(DATA_PATH, unique)
            print("Active training CSV updated after confirmation.")
        else:
            print("Active training CSV was left unchanged.")


if __name__ == "__main__":
    main()
