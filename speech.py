"""Non-blocking speech output with Windows voices and an optional audio cache."""

from __future__ import annotations

import hashlib
import os
import queue
import re
import threading
import time
from pathlib import Path

from vocabulary_utils import load_vocabulary

BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "audio_cache"
VOICE_MATCH = {
    "en": re.compile(r"english|(^|[^a-z])en[-_][a-z]{2}($|[^a-z])", re.I),
    "ur": re.compile(r"urdu|(^|[^a-z])ur[-_][a-z]{2}($|[^a-z])", re.I),
}


class Speaker:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.status = "Voice on" if enabled else "Voice off"
        self._queue: queue.Queue = queue.Queue(maxsize=1)
        self._warned = False
        self._thread = threading.Thread(target=self._run, daemon=True) if enabled else None
        if self._thread:
            self._thread.start()

    def speak(self, text: str, language: str) -> None:
        if not self.enabled or not text:
            return
        try:
            self._queue.get_nowait()
        except queue.Empty:
            pass
        try:
            self._queue.put_nowait((text, language))
        except queue.Full:
            return

    def _run(self) -> None:
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except Exception:
            pass
        while True:
            entry = self._queue.get()
            if entry is None:
                return
            text, language = entry
            try:
                if not self._speak_system(text, language) and not self._speak_cache(text, language):
                    self._warn("No voice is available. Text remains on screen; install an Urdu voice or prepare the audio cache before the exhibition.")
            except Exception as error:
                self._warn(f"Speech is unavailable: {error}")

    def _speak_system(self, text: str, language: str) -> bool:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            voices = engine.getProperty("voices")
            selected = None
            for voice in voices:
                language_data = " ".join(str(value) for value in getattr(voice, "languages", []))
                if VOICE_MATCH[language].search(f"{voice.id} {voice.name} {language_data}"):
                    selected = voice.id
                    break
            if language == "ur" and selected is None:
                engine.stop()
                return False
            if selected:
                engine.setProperty("voice", selected)
            engine.setProperty("rate", 165)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
            return True
        except ImportError:
            return False

    def _speak_cache(self, text: str, language: str) -> bool:
        name = hashlib.sha256(f"{language}:{text}".encode("utf-8")).hexdigest()[:24]
        audio_path = CACHE_DIR / f"{language}_{name}.mp3"
        if not audio_path.exists():
            return False
        try:
            os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(str(audio_path))
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.04)
            return True
        except Exception:
            return False

    def _warn(self, message: str) -> None:
        self.status = "Text-only: speech unavailable"
        if not self._warned:
            print(message)
            self._warned = True

    def close(self) -> None:
        if self._thread:
            while True:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break
            try:
                self._queue.put_nowait(None)
            except queue.Full:
                pass


def _cached_file(text: str, language: str) -> Path:
    name = hashlib.sha256(f"{language}:{text}".encode("utf-8")).hexdigest()[:24]
    return CACHE_DIR / f"{language}_{name}.mp3"


def prefetch_all() -> None:
    """Cache both languages for all vocabulary items while internet is available."""
    try:
        from gtts import gTTS
    except ImportError:
        print("Install optional audio tools first: python -m pip install gTTS pygame")
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    vocabulary = load_vocabulary()
    total = len(vocabulary) * 2
    completed = 0
    for item in vocabulary:
        for language, text in (("en", item["english"]), ("ur", item["urdu"])):
            path = _cached_file(text, language)
            if not path.exists():
                temporary = path.with_suffix(".mp3.part")
                try:
                    gTTS(text=text, lang=language).save(str(temporary))
                    temporary.replace(path)
                except Exception as error:
                    temporary.unlink(missing_ok=True)
                    print(f"Could not cache {language} audio for {item['id']}: {error}")
            completed += 1
            print(f"Prepared {completed}/{total}: {language} - {item['english']}")


if __name__ == "__main__":
    prefetch_all()
