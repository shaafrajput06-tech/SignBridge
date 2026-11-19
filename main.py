"""Run SignBridge's local, no-training exhibition demo."""

from __future__ import annotations

import importlib.util
import sys


def main() -> int:
    required = {"cv2": "opencv-python", "mediapipe": "mediapipe", "numpy": "numpy", "joblib": "joblib"}
    missing = [package for module, package in required.items() if importlib.util.find_spec(module) is None]
    if missing:
        print("SignBridge cannot start because required packages are missing.")
        print("Install them from this project folder with: python -m pip install -r requirements.txt")
        print("Missing: " + ", ".join(missing))
        return 2
    try:
        from app import run_desktop
        run_desktop()
        return 0
    except KeyboardInterrupt:
        print("SignBridge closed.")
        return 0
    except Exception as error:
        print(f"SignBridge stopped safely: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
