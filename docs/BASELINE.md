# SignBridge Phase 0 baseline

Recorded 2026-11-10 at the end of Phase 0 (branch `phase-0`). Every result below was measured in this
phase. Anything that was not run is listed under "Not tested", not described as working.

No trained SignBridge model exists, and `data/` holds no signer recordings, so **no recognition
accuracy has been measured**. The training smoke tests use synthetic hands only to check that the
script runs; their scores are not reported anywhere.

## Test environment

| Item | Version |
|---|---|
| OS | Linux x86_64 (cloud container), no camera, no GPU |
| Python | CPython 3.10.20, 3.11, 3.12, 3.13.18, 3.14.6: each in a fresh virtual environment from `requirements.txt` |
| Python packages (3.14) | mediapipe 1.2.2, opencv-contrib-python 5.0.0.93, numpy 2.5.4, scikit-learn 1.9.1, joblib 1.6.0, fastapi 0.162.2, starlette 1.10.0, uvicorn 0.54.0, SQLAlchemy 2.1.8, httpx 0.28.1, pygame-ce 2.5.8, Pillow 13.0.0, pyttsx3 2.99, gTTS 2.5.4, python-bidi 0.6.12, arabic-reshaper 3.1.0 |
| Python packages (3.10) | as above except numpy 2.2.6, scikit-learn 1.7.2, SQLAlchemy 2.0.57, starlette 1.7.0, Pillow 12.3.0 |
| Node.js / npm | 22.23.4 / 10.9.9 |
| Web packages (`web/package-lock.json`) | react 19.3.1, react-dom 19.3.1, vite 8.3.6, @mediapipe/tasks-vision 1.2.2 |
| Browser for smoke test | Playwright 1.63.0, Chromium 153.0.8010.12 headless with a fake camera |

## Results

| Check | Result |
|---|---|
| `pip install -r requirements.txt` in a fresh environment | Succeeds on Linux 3.10, 3.11, 3.12, 3.13, 3.14 |
| Same install with the **original** requirements on 3.14 | Fails: `pygame==2.6.1` has no wheel and its source build fails (`sdl2-config` missing) |
| Wheel-only dependency resolution, new requirements | Succeeds for `win_amd64` and `macosx_14_0_arm64` on 3.10-3.14 (resolution only; not installed on those systems) |
| Wheel-only resolution, original requirements, `win_amd64` | 3.10-3.13 succeed; 3.14 fails on pygame. `start_signbridge.bat` tries 3.14 first |
| Python tests (`python -m unittest discover -s tests`) | **40 run, 40 pass, 0 skipped** on each of 3.10, 3.11, 3.12, 3.13, 3.14 (was 18: 14 core + 4 API) |
| Browser parity tests (`npm test` in `web/`) | 4 of 4 pass: JavaScript demo rules give the same gesture as Python on all 260 fixture hands; features match within 1e-9 |
| Wider parity sample (not committed) | 6,000 perturbed synthetic hands: 0 gesture mismatches, largest feature difference 3.3e-16 |
| Browser camera smoke test, production build (`npm run test:smoke`) | Before the fix: 1 of 4 pass (voice toggle, camera switch and stop/start crash the page). After: 4 of 4, in two consecutive runs |
| Same smoke test against the dev server (`npm run dev`, what `start_web.bat` runs) | Original code: 1 of 4. Fixed code: 4 of 4 |
| `npm ci` + `npm run build` from a clean clone | Succeeds |
| `python main.py --no-voice` under a virtual display, no camera (3.10 and 3.14) | Starts in AI Demo Mode, reports the missing camera, keeps the vocabulary window open |
| `train_model.py` on synthetic data | Writes model, metadata, report and confusion matrix; bundle loads. scikit-learn 1.9 warns that `SVC(probability=True)` is deprecated |
| `/api/recognize-frame` | Blank frame returns `hand_detected: false`; a non-image body returns 415 |

## Findings and status

Audit section 3 of the master prompt was checked against the code. These items were missing from it
or differ from it.

| # | Finding | Evidence | Status |
|---|---|---|---|
| F1 | The install blocker is **pygame**, not psycopg. psycopg-binary has wheels for 3.10-3.14. | Wheel resolution above; failed 3.14 source build | **Fixed**: `pygame-ce` (imported as `pygame`; cached-audio test passes). psycopg moved to `requirements-postgres.txt` as planned |
| F2 | Web camera crash: the camera cleanup closed the cached MediaPipe detector, and the next start reused the closed one (WASM `Aborted()`) | Smoke test, with a no-toggle control run; patching only the detector release stops it | **Fixed** in `vision.js` and `App.jsx`. Voice toggle no longer restarts the camera |
| F3 | Rejection of unsure predictions is narrower than audit P0-3 says. Desktop rejects only when the SVM was selected (Random Forest sets `has_calibrated_probabilities: false`). The website ignores the probability `/api/predict` returns. `/api/recognize-frame` (phone) applies none | `tests/test_baseline.py::DesktopPredictTests`, `tests/test_api.py::test_current_predict_returns_a_label_even_when_the_model_is_unsure` | Open, Phase 3. Characterisation tests in place |
| F4 | Flutter sends frames without rotating for the sensor. With synthetic hands rotated 90 degrees: Wait reads as Help, Help reads as No, Yes and Bad give nothing. Phone-collected training samples would be stored rotated | `test_current_rules_change_answer_when_the_image_is_rotated_90_degrees` | Open, Phase 5. **Do not collect phone training data until fixed** (README notes this) |
| F5 | Any error in the Flutter frame loop, including a likely iOS `planes[2]` range error, is shown as "Local server unavailable" | Code reading (`mobile/lib/main.dart`, `_processFrame`) | Open, Phase 5. Not testable here |
| F6 | The Emergency hint said "clearly spread", but the rule needs fingers close together; spread fingers give Hello | `ml_engine/gestures.py` thresholds vs `vocabulary.json` | **Fixed**: hint text only, all three copies, no ID changes |
| F7 | scikit-learn 1.11 removes `SVC(probability=True)`; requirements were unpinned | Deprecation warning in training | **Mitigated**: capped `<1.11`. The real replacement changes calibration, so it belongs in Phase 3 |
| F8 | mediapipe installs `opencv-contrib-python` while requirements also listed `opencv-python`; both provide `cv2` | `pip show mediapipe` | **Fixed**: only the contrib package is listed |
| F9 | MediaPipe Tasks in the browser contacts `odml.pa.googleapis.com` (usage metrics), as the consent notice says | Network attempt during the smoke test | Informational. Relevant to the offline PWA work in Phase 4 |
| F10 | `/api/training-data.csv` serves participant names to anyone on the network, without a token | Code reading | Open, audit P2-3 |
| F11 | Exhibition checklist pointed to `/health`; the route is `/api/health` | Code reading | **Fixed** |
| F12 | The mirror effects between desktop (frame flipped) and browser (not flipped) cancel: mirrored landmarks with the swapped handedness label give identical features, and the demo rules ignore mirroring | `MirrorConsistencyTests` | Confirmed mathematically. Whether MediaPipe's own landmarks are mirror-consistent still needs real recordings (Phase 1) |

Confirmed as stated in the audit: 64 vocabulary items in three byte-identical copies; 13 demo items;
50 of the other 51 have blank hints (Goodbye has one); Sorry/Excuse me and Eat/Food share Urdu text;
`data/` is empty; no trained model; v1 features and augmentation as described; 8-frame hold; mobile
sends a frame at most every 650 ms and needs 8 stable answers (at least about 5 s).

## Not tested

- **Windows, macOS, iOS, Android.** Only Linux was run. For Windows and macOS, prebuilt-package availability was checked, not an install or run. `start_signbridge.bat`, `start_web.bat`, `start_backend.bat` and `run_tests.bat` were not executed.
- **Flutter.** The Flutter/Dart SDK and pub.dev cannot be downloaded in this workspace, so the mobile app was neither built nor analysed. The Dart parity tests planned for Phase 1 need a machine with Flutter, or those sites allowed.
- **Real camera input.** No physical camera; the browser test uses Chromium's fake camera, which shows no hands. Hand tracking quality, frame rate and the demo poses on real hands are unmeasured.
- **Speech output.** Cached playback was tested with a silent audio driver; system voices (pyttsx3, browser, Flutter TTS) were not.
- **HTTPS / phone browsers.** Not tested.

## How to repeat

```
python tools/run_all_tests.py            # Python + browser parity tests
python tools/run_all_tests.py --smoke    # also the fake-camera browser test (needs Playwright)
python tests/golden/make_v1_golden.py    # only when v1 behaviour changes on purpose
python tools/sync_vocabulary.py --check  # vocabulary copies match
```
