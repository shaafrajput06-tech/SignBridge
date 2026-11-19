"""OpenCV exhibition interface, vocabulary browser, and recognition loop."""

from __future__ import annotations

import argparse
import sys
import time
from collections import deque
from contextlib import nullcontext
from pathlib import Path

import cv2
import numpy as np

from ml_engine.gestures import classify_gesture
from ml_engine.model_loader import load_model_bundle
from signbridge_common import (
    BASE_DIR,
    CLASSIFIER_PATH,
    GESTURE_TO_ID,
    VOCABULARY,
    VOCABULARY_BY_ID,
    HandTracker,
    draw_hand,
    open_camera,
    put_texts,
    urdu_ready,
)
from speech import Speaker
from vocabulary_utils import display_text

WINDOW = "SignBridge | Exhibition"
LOST_SECONDS = 0.85
PAGE_SIZE = 12
HELP = [
    "E English   U Urdu   L switch language   R repeat word",
    "V voice on/off   M recognition mode   B opens browser   H help",
    "Vocabulary: type to search, C category, arrows browse, Enter select",
    "Q quit   Esc close panel",
    "Demo recognition uses MediaPipe hand tracking and landmark geometry.",
    "Unmapped vocabulary needs real examples before camera recognition.",
]


def parse_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="SignBridge live sign translator")
    parser.add_argument("--camera", type=int, default=0, help="camera index (try 1 for another webcam)")
    parser.add_argument("--lang", choices=("en", "ur"), default="en")
    parser.add_argument("--threshold", type=float, default=0.72, help="minimum calibrated trained-model probability")
    parser.add_argument("--hold", type=int, default=8, help="stable consecutive frames before accepting a pose")
    parser.add_argument("--no-voice", action="store_true")
    parser.add_argument("--roman-urdu", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--demo", action="store_true", help="start in AI Demo Mode (default)")
    mode.add_argument("--trained", action="store_true", help="start in AI Trained Mode when a model is available")
    return parser.parse_args(argv)


def _load_model():
    bundle = load_model_bundle(CLASSIFIER_PATH)
    if bundle is None and CLASSIFIER_PATH.exists():
        print("Saved model could not be loaded; continuing in demo mode.")
    return bundle


def _draw_card(frame, y0: int, y1: int, color=(21, 29, 43)) -> None:
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, y0), (frame.shape[1], y1), color, -1)
    cv2.addWeighted(overlay, 0.91, frame, 0.09, 0, frame)


def _browser_results(search: str, category: str, page: int) -> list[dict]:
    query = search.casefold().strip()
    results = [item for item in VOCABULARY
               if (not category or item["category"] == category)
               and (not query or query in " ".join((item["english"], item["urdu"], item["romanUrdu"], item["category"])).casefold())]
    start = max(0, page) * PAGE_SIZE
    return results[start:start + PAGE_SIZE]


def _predict(hand, trained_bundle, threshold: float):
    if trained_bundle:
        model = trained_bundle["model"]
        try:
            if trained_bundle.get("has_calibrated_probabilities") and hasattr(model, "predict_proba"):
                probabilities = model.predict_proba([hand.features])[0]
                index = int(probabilities.argmax())
                if float(probabilities[index]) < threshold:
                    return None, "Not sure — model probability below threshold"
                return str(model.classes_[index]), "Trained model prediction (calibrated score)"
            return str(model.predict([hand.features])[0]), "Trained model prediction (uncalibrated)"
        except Exception:
            return None, "Not sure — model could not classify this hand"
    gesture = classify_gesture(hand.landmarks)
    return (GESTURE_TO_ID.get(gesture), "Rule-based match" if gesture else "Not sure — show a supported demo pose")


def run_desktop(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.hold < 1:
        raise ValueError("--hold must be at least 1")
    if not 0 <= args.threshold <= 1:
        raise ValueError("--threshold must be between 0 and 1")
    model_bundle = _load_model()
    trained_mode = bool(model_bundle and args.trained)
    if args.trained and not model_bundle:
        print("No trained model is ready; starting AI Demo Mode. Record data and train first.")
    speaker = Speaker(enabled=not args.no_voice)
    camera = None
    camera_error = ""
    try:
        camera = open_camera(args.camera)
    except RuntimeError as error:
        camera_error = str(error)
        print(f"Camera unavailable. The vocabulary browser and speech controls remain open. {error}")
    tracker = None
    if camera is not None:
        print("MediaPipe processes camera input on this computer and does not send the images to Google. MediaPipe Tasks may send aggregate performance and usage metrics to Google.")
        try:
            metrics_consent = sys.stdin.isatty() and input("Allow MediaPipe Tasks metrics and start camera recognition? [y/N] ").strip().casefold() in {"y", "yes"}
        except EOFError:
            metrics_consent = False
        if not metrics_consent:
            camera.release()
            camera = None
            camera_error = "Camera recognition not started without MediaPipe metrics consent. Vocabulary browsing remains available."
            print(camera_error)
    if camera is not None:
        try:
            tracker = HandTracker(num_hands=2)
        except Exception as error:
            camera.release()
            camera = None
            camera_error = f"Hand tracking is unavailable: {error}"
            print(f"{camera_error} Vocabulary browsing remains available.")
    language = args.lang
    current_id = None
    accepted_id = None
    manual_selection = False
    status = camera_error or "Show a sign to the camera"
    recent: deque[str | None] = deque(maxlen=args.hold)
    last_hand_at = 0.0
    last_geometry_match = ""
    browser = False
    help_open = False
    search = ""
    category = ""
    categories = sorted({item["category"] for item in VOCABULARY})
    page = 0
    selected = 0
    voice_enabled = not args.no_voice
    print("SignBridge is starting in " + ("AI Trained Mode" if trained_mode else "AI Demo Mode"))
    if not urdu_ready() and language == "ur":
        print("Urdu shaping is unavailable; the screen will use Roman Urdu.")

    try:
        with (tracker if tracker is not None else nullcontext(None)) as active_tracker:
            while True:
                if camera is not None:
                    ok, frame = camera.read()
                    if not ok or frame is None:
                        camera.release()
                        camera = None
                        camera_error = f"Camera {args.camera} stopped providing frames. Try --camera 1."
                        status = camera_error
                        frame = np.zeros((760, 1200, 3), dtype=np.uint8)
                    else:
                        frame = cv2.flip(frame, 1)
                else:
                    frame = np.zeros((760, 1200, 3), dtype=np.uint8)
                height, width = frame.shape[:2]
                now = time.monotonic()
                hand = active_tracker.detect(frame) if active_tracker is not None and camera is not None else None
                if hand:
                    last_hand_at = now
                    draw_hand(frame, hand.landmarks)
                    predicted, status = _predict(hand, model_bundle if trained_mode else None, args.threshold)
                    recent.append(predicted)
                    stable = len(recent) == recent.maxlen and recent[0] is not None and all(value == recent[0] for value in recent)
                    if stable:
                        current_id = recent[0]
                        manual_selection = False
                        if current_id != accepted_id:
                            accepted_id = current_id
                            if current_id in {item["id"] for item in VOCABULARY}:
                                speaker.speak(VOCABULARY_BY_ID[current_id]["urdu" if language == "ur" else "english"], language)
                else:
                    recent.clear()
                    status = camera_error or "Show a sign to the camera"
                    if now - last_hand_at > LOST_SECONDS and not manual_selection:
                        current_id = None
                        accepted_id = None

                mode_text = "AI Trained Mode — trained classifier" if trained_mode else "AI Demo Mode — rule-based gestures"
                _draw_card(frame, 0, 58)
                put_texts(frame, [
                    {"text": "SignBridge", "x": 22, "y": 15, "size": 28, "color": (248, 248, 244)},
                    {"text": mode_text, "x": width - 18, "y": 22, "size": 18, "color": (133, 225, 194), "align": "right"},
                ])

                card_top = max(100, height - 214)
                _draw_card(frame, card_top, height)
                label_items = [
                    {"text": "English" if language == "en" else "Urdu output", "x": width // 2, "y": card_top + 18, "size": 19, "color": (178, 193, 211), "align": "center"},
                ]
                if current_id:
                    item = VOCABULARY_BY_ID[current_id]
                    selected_text = display_text(item, language, args.roman_urdu or (language == "ur" and not urdu_ready()))
                    label_items.append({"text": selected_text, "x": width // 2, "y": card_top + 44, "size": min(56, width // 17), "color": (250, 213, 111), "align": "center", "urdu": language == "ur" and selected_text == item["urdu"]})
                    helper = item["english"] if language == "ur" else (item["urdu"] if urdu_ready() else item["romanUrdu"])
                    label_items.append({"text": helper, "x": width // 2, "y": card_top + 112, "size": 24, "color": (229, 236, 244), "align": "center", "urdu": language == "en" and urdu_ready()})
                    label_items.append({"text": f"{item['category']}  |  {item.get('handSignHint') or 'Vocabulary item'}", "x": width // 2, "y": card_top + 152, "size": 16, "color": (179, 197, 218), "align": "center"})
                else:
                    label_items.append({"text": status, "x": width // 2, "y": card_top + 64, "size": 24, "color": (231, 238, 245), "align": "center"})
                voice_status = speaker.status if speaker.status != "Voice on" else ("Voice on" if voice_enabled else "Voice off")
                font_status = "Roman Urdu fallback" if language == "ur" and not urdu_ready() else "Urdu font ready"
                camera_status = f"Camera {args.camera}" if camera is not None else "No camera · vocabulary only"
                label_items.append({"text": f"{status}  |  {voice_status}  |  {camera_status}  |  {font_status}", "x": width // 2, "y": height - 25, "size": 15, "color": (150, 177, 199), "align": "center"})
                put_texts(frame, label_items)

                if browser:
                    results = _browser_results(search, category, page)
                    _draw_card(frame, 70, min(height - 225, 450), (17, 24, 36))
                    header = f"Vocabulary  |  Search: {search or 'all'}  |  Category: {category or 'all'}  |  Page {page + 1}"
                    rows = [{"text": header, "x": 22, "y": 82, "size": 20, "color": (250, 213, 111)}]
                    for index, item in enumerate(results):
                        marker = "> " if index == selected else "  "
                        available = "Demo" if item["demoAvailable"] else "Vocabulary mode"
                        rows.append({"text": f"{marker}{item['english']}  |  {item['romanUrdu']}  |  {available}", "x": 28, "y": 118 + index * 25, "size": 16, "color": (235, 240, 246) if index == selected else (172, 189, 207)})
                    rows.append({"text": "Tab category  |  type to search  |  arrows select/page  |  Enter speak  |  Backspace edit", "x": 22, "y": min(height - 245, 430), "size": 14, "color": (145, 180, 192)})
                    put_texts(frame, rows)
                if help_open:
                    top = 72 if not browser else min(height - 220, 470)
                    _draw_card(frame, top, min(height - 230, top + 184), (12, 20, 31))
                    put_texts(frame, [{"text": line, "x": 24, "y": top + 10 + i * 27, "size": 16, "color": (230, 237, 245)} for i, line in enumerate(HELP)])

                cv2.imshow(WINDOW, frame)
                key = cv2.waitKeyEx(1)
                char = key & 0xFF
                if key == 27:
                    browser = False
                    help_open = False
                elif not browser and char == ord("q"):
                    break
                elif not browser and char == ord("e"):
                    language = "en"
                elif not browser and char == ord("u"):
                    language = "ur"
                elif not browser and char == ord("l"):
                    language = "ur" if language == "en" else "en"
                elif not browser and char == ord("v"):
                    voice_enabled = not voice_enabled
                    speaker.close()
                    speaker = Speaker(enabled=voice_enabled)
                elif not browser and char == ord("r") and current_id:
                    item = VOCABULARY_BY_ID[current_id]
                    speaker.speak(item["urdu"] if language == "ur" else item["english"], language)
                elif not browser and char == ord("m"):
                    if model_bundle:
                        trained_mode = not trained_mode
                        recent.clear()
                        accepted_id = None
                    else:
                        status = "No trained model is available; the demo stays active"
                elif not browser and char == ord("b"):
                    browser = not browser
                    help_open = False
                    search = ""
                    category = ""
                    page = selected = 0
                elif not browser and char == ord("h"):
                    help_open = not help_open
                elif browser and key in (2490368, 2424832):  # up / left
                    if selected > 0:
                        selected -= 1
                    else:
                        page = max(0, page - 1)
                        selected = PAGE_SIZE - 1
                elif browser and key in (2621440, 2555904):  # down / right
                    if selected + 1 < len(_browser_results(search, category, page)):
                        selected += 1
                    elif len(_browser_results(search, category, page + 1)):
                        page += 1
                        selected = 0
                elif browser and (key in (10, 13)):
                    results = _browser_results(search, category, page)
                    if results and selected < len(results):
                        item = results[selected]
                        current_id = item["id"]
                        accepted_id = current_id
                        manual_selection = True
                        status = "Rule-based match" if item["demoAvailable"] else "Vocabulary Mode — training data required for camera recognition"
                        speaker.speak(item["urdu"] if language == "ur" else item["english"], language)
                elif browser and char in (8, 127):
                    search = search[:-1]
                    page = selected = 0
                elif browser and char == 9:
                    index = categories.index(category) if category in categories else -1
                    category = categories[(index + 1) % (len(categories) + 1)] if index + 1 < len(categories) else ""
                    if index == len(categories) - 1:
                        category = ""
                    page = selected = 0
                elif browser and 32 <= char <= 126 and chr(char).isprintable():
                    search += chr(char)
                    page = selected = 0

    finally:
        speaker.close()
        if camera is not None:
            camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    run_desktop()
