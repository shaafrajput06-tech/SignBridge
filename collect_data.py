"""Interactive collector for unlimited, locally stored landmark sessions."""

from __future__ import annotations

import argparse
import csv
import math
import sys
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

try:
    import cv2
except ImportError:
    cv2 = None

from signbridge_common import DATA_DIR, DATA_PATH, VOCABULARY, HandTracker, draw_hand, open_camera

METADATA_COLUMNS = ["label", "participant", "session_id", "timestamp_utc", "frame_index", "frame_width", "frame_height", "handedness"]
FEATURE_COLUMNS = [f"f{index}" for index in range(63)]
CSV_HEADER = METADATA_COLUMNS + FEATURE_COLUMNS


def parse_args():
    parser = argparse.ArgumentParser(description="Collect SignBridge landmark examples")
    parser.add_argument("--participant", default=None, help="optional participant name; empty is anonymous")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--target", type=int, default=100, help="optional frame target for this session; 0 means collect until stopped")
    parser.add_argument("--every", type=int, default=2, help="sample one frame for every N frames")
    parser.add_argument("--countdown", type=int, default=3)
    return parser.parse_args()


def validate_header(header: list[str] | None, path: Path = DATA_PATH) -> None:
    if header is not None and header != CSV_HEADER:
        raise ValueError(f"{path} has an unexpected CSV header. Keep a copy and merge it with merge_data.py after checking its columns.")


def load_rows(path: Path = DATA_PATH) -> list[list[str]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        header = next(reader, None)
        validate_header(header, path)
        for row_number, row in enumerate(reader, 2):
            try:
                if len(row) != len(CSV_HEADER) or row[0] not in {item["id"] for item in VOCABULARY}:
                    raise ValueError("wrong field count or unknown vocabulary ID")
                values = [float(value) for value in row[len(METADATA_COLUMNS):]]
                if not all(math.isfinite(value) for value in values):
                    raise ValueError("non-finite landmark value")
                rows.append(row)
            except (TypeError, ValueError):
                print(f"Skipping malformed data row {row_number} in {path.name}.")
    return rows


def save_rows(rows: list[list[str]], path: Path = DATA_PATH) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(CSV_HEADER)
        writer.writerows(rows)
    temporary.replace(path)


def choose_vocabulary() -> dict:
    query = ""
    category = ""
    page = 0
    page_size = 12
    categories = sorted({item["category"] for item in VOCABULARY})
    while True:
        matches = [item for item in VOCABULARY if (not category or item["category"] == category) and (not query or query.casefold() in f"{item['english']} {item['romanUrdu']} {item['urdu']}".casefold())]
        start = page * page_size
        shown = matches[start:start + page_size]
        print(f"\nChoose a vocabulary item — search: {query or 'all'}; category: {category or 'all'}; page {page + 1}")
        for index, item in enumerate(shown, 1):
            print(f"  {index:2}. {item['english']} ({item['romanUrdu']}) — {item['category']}")
        print("Commands: number/ID select, /text search, category name filter, n/p pages, x exit")
        choice = input("Selection: ").strip()
        if choice.lower() == "x":
            raise SystemExit(0)
        if choice.lower() == "n" and start + page_size < len(matches):
            page += 1
            continue
        if choice.lower() == "p" and page > 0:
            page -= 1
            continue
        if choice.startswith("/"):
            query = choice[1:].strip()
            page = 0
            continue
        exact = next((item for item in VOCABULARY if item["id"].casefold() == choice.casefold()), None)
        if exact:
            return exact
        if choice.isdigit() and 1 <= int(choice) <= len(shown):
            return shown[int(choice) - 1]
        matching_category = next((name for name in categories if name.casefold() == choice.casefold()), None)
        if matching_category:
            category = matching_category
            page = 0
            continue
        print("No matching item. Try its displayed number, ID, or a search beginning with '/'.")


def main() -> None:
    args = parse_args()
    if cv2 is None:
        raise RuntimeError("OpenCV is missing. Install dependencies with python -m pip install -r requirements.txt")
    if args.target < 0 or args.every < 1 or args.countdown < 0:
        raise ValueError("--target and --countdown must be zero or greater; --every must be at least one")
    participant = args.participant
    if participant is None:
        participant = input("Participant name (press Enter for anonymous): ").strip()
    participant = participant.strip()[:120]
    item = choose_vocabulary()
    existing = load_rows()
    count = sum(row[0] == item["id"] for row in existing)
    print(f"{count} examples already saved for {item['english']}.")
    camera = open_camera(args.camera)
    pending: list[list[str]] = []
    session_id = uuid.uuid4().hex
    state = "idle"
    countdown_until = 0.0
    frame_index = 0
    sample_index = 0
    pause_started = 0.0
    saved_session_id: str | None = None

    try:
        with HandTracker(num_hands=2) as tracker:
            while True:
                ok, frame = camera.read()
                if not ok:
                    raise RuntimeError(f"Camera {args.camera} stopped providing frames.")
                frame = cv2.flip(frame, 1)
                hand = tracker.detect(frame)
                if hand:
                    draw_hand(frame, hand.landmarks)
                now = time.monotonic()
                if state == "countdown" and now >= countdown_until:
                    state = "recording"
                    print("Recording. P pause/resume, S save and stop, D discard this session, Z undo saved session, Q quit.")
                if state == "recording" and hand:
                    frame_index += 1
                    if frame_index % args.every == 0:
                        sample_index += 1
                        timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
                        metadata = [item["id"], participant or "anonymous", session_id, timestamp, str(frame_index), str(frame.shape[1]), str(frame.shape[0]), hand.handedness]
                        pending.append(metadata + [f"{value:.8f}" for value in hand.features])
                        if args.target and len(pending) >= args.target:
                            added = len(pending)
                            existing.extend(pending)
                            save_rows(existing)
                            saved_session_id = session_id
                            count += added
                            print(f"Saved {added} examples for {item['english']}.")
                            pending = []
                            state = "idle"
                h, w = frame.shape[:2]
                line1 = f"SignBridge Data Collection | {item['english']} | saved {count} | this session {len(pending)}"
                line2 = (f"Recording {len(pending)}" + (f" / {args.target}" if args.target else " — no target") if state == "recording" else f"{state.title()} — SPACE record, P pause, S save/stop, D discard, Z undo, Q quit")
                cv2.rectangle(frame, (0, 0), (w, 82), (20, 30, 43), -1)
                cv2.putText(frame, line1, (18, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.63, (245, 241, 231), 2, cv2.LINE_AA)
                cv2.putText(frame, line2, (18, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (164, 217, 196), 1, cv2.LINE_AA)
                if state == "countdown":
                    cv2.putText(frame, str(max(1, int(countdown_until - now) + 1)), (w // 2 - 22, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 3, (248, 200, 92), 5, cv2.LINE_AA)
                elif state in ("recording", "paused") and not hand:
                    cv2.putText(frame, "Show your hand", (w // 2 - 140, h // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)
                cv2.imshow("SignBridge | Training data", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    if pending:
                        answer = input("Save the current unsaved session before quitting? [y/N] ").strip().lower()
                        if answer == "y":
                            existing.extend(pending)
                            save_rows(existing)
                    break
                if key == ord(" ") and state == "idle":
                    state = "countdown"
                    countdown_until = now + args.countdown
                    session_id = uuid.uuid4().hex
                    pending = []
                    frame_index = 0
                elif key == ord("p") and state == "recording":
                    state = "paused"
                    pause_started = now
                elif key == ord("p") and state == "paused":
                    state = "recording"
                    countdown_until = now + max(0.0, args.countdown - (now - pause_started))
                elif key == ord("s") and state in ("recording", "paused"):
                    if pending:
                        existing.extend(pending)
                        save_rows(existing)
                        saved_session_id = session_id
                        count += len(pending)
                        print(f"Saved {len(pending)} examples for {item['english']}.")
                    pending = []
                    state = "idle"
                elif key == ord("d") and state in ("countdown", "recording", "paused"):
                    pending = []
                    state = "idle"
                    print("Current unsaved session discarded.")
                elif key == ord("z") and saved_session_id:
                    existing = [row for row in existing if row[2] != saved_session_id]
                    save_rows(existing)
                    saved_session_id = None
                    count = sum(row[0] == item["id"] for row in existing)
                    print("Last saved session removed.")
    finally:
        camera.release()
        cv2.destroyAllWindows()
    print(f"Collection ended. Data remains in {DATA_PATH.name}; source video is not saved.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as error:
        print(error, file=sys.stderr)
        raise SystemExit(2)
