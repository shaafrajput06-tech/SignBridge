"""Convert v1 landmark CSV rows into v2 recording files, one 1-frame record per row.

    python tools/convert_v1_to_v2.py --input data/sign_data.csv --output data/recordings_v2/v1 --signer-key-file KEYFILE

Nothing is lost: each record keeps the row's 63 v1 values exactly, plus its label, session, time,
frame index, frame size and handedness, and `record_to_v1_row` rebuilds the row. The one deliberate
change is privacy: participant names are replaced by pseudonymous signer IDs (HMAC-SHA256 with a
secret key you keep outside the repository). The same key always gives the same IDs, so re-running
gives byte-identical files.

The key comes from --signer-key-file or the SIGNBRIDGE_SIGNER_KEY environment variable. Keep it
private and keep it: it is the only link between names and IDs. --signer-map writes that link as a
CSV for your own consent records; it contains names, so never commit or share it.

Malformed rows are skipped with the same checks as collect_data.py, and listed in the report.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from collect_data import CSV_HEADER, load_rows  # noqa: E402
from ml_engine.recording_v2 import pseudonym, v1_row_to_record, write_recording  # noqa: E402


def read_key(key_file: str | None) -> bytes:
    if key_file:
        key = Path(key_file).read_bytes().strip()
    else:
        key = os.environ.get("SIGNBRIDGE_SIGNER_KEY", "").encode("utf-8").strip()
    if len(key) < 16:
        raise SystemExit("A signer key of at least 16 characters is required (--signer-key-file or SIGNBRIDGE_SIGNER_KEY). "
                         "It turns participant names into pseudonymous IDs; keep it private and outside the repository.")
    return key


def convert(input_path: Path, output_dir: Path, key: bytes, signer_map: Path | None = None) -> dict:
    rows = load_rows(input_path)
    with input_path.open("r", encoding="utf-8-sig", newline="") as stream:
        total = max(0, sum(1 for _ in csv.reader(stream)) - 1)
    written, warnings, names = [], Counter(), {}
    for row in rows:
        frames, meta, v1 = v1_row_to_record(row, CSV_HEADER, key)
        digest = hashlib.sha256(",".join(row).encode("utf-8")).hexdigest()[:10]
        frame_index = row[CSV_HEADER.index("frame_index")]
        name = f"{meta['session_id']}_{frame_index.zfill(6)}_{digest}.npz"
        path = output_dir / meta["gloss_id"] / meta["signer_id"] / name
        write_recording(path, frames, meta, v1_features=v1)
        written.append(str(path.relative_to(output_dir)).replace(os.sep, "/"))
        warnings.update(meta["warnings"])
        participant = row[CSV_HEADER.index("participant")]
        names.setdefault(participant, pseudonym(participant, key))
    report = {
        "input_rows": total,
        "converted": len(written),
        "skipped_malformed": total - len(rows),
        "signers": len({value for value in names.values()}),
        "glosses": len({path.split("/")[0] for path in written}),
        "warnings": dict(sorted(warnings.items())),
        "files": sorted(written),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "conversion_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if signer_map is not None:
        with signer_map.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["participant", "signer_id"])
            writer.writerows(sorted(names.items()))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "sign_data.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "recordings_v2" / "v1")
    parser.add_argument("--signer-key-file", default=None)
    parser.add_argument("--signer-map", type=Path, default=None, help="also write participant -> signer_id (contains names: keep private)")
    args = parser.parse_args(argv)
    if not args.input.exists():
        print(f"{args.input} does not exist; nothing to convert.")
        return 1
    report = convert(args.input, args.output, read_key(args.signer_key_file), args.signer_map)
    print(f"Converted {report['converted']} of {report['input_rows']} rows ({report['skipped_malformed']} malformed) "
          f"into {args.output}; {report['signers']} signer IDs, {report['glosses']} labels.")
    for warning, count in report["warnings"].items():
        print(f"  warning ({count} rows): {warning}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
