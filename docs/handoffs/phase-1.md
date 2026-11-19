# Phase 1 handoff — 2026-11-18 (draft for Gate B)

## Result

**Not passed yet.** Gate A (self-check) is below. Two of the four acceptance criteria are met; the
other two need a person and a properly set-up machine: the web capture frame rate has not been
measured, and the full Phase 0 suite (API tests, browser smoke test) could not run in this workspace.

Gate B round 1 (independent reviewer, fresh context, 2026-11-18): **FAIL**. Besides the two open
criteria it found one consent finding, two overstated claims and seven smaller issues. All but three
are fixed (see "Gate B round 1" below). Gate B must be re-run once the open criteria are measured.

Branch `v2/phase-1` (from `v2/main`, which is `phase-0` plus the prompt architecture). Final commit:
see `git log -1 v2/phase-1`.

Branch naming: git cannot hold a branch called `v2` next to `v2/phase-N`, so the base branch is
`v2/main` (recorded in `docs/prompts/README.md`).

## Gate A — self-check

Environment for every number below: Linux x86_64 cloud container, 2 CPU threads, no camera, no GPU,
no network for package installs; Python 3.13.18, mediapipe 0.10.32, numpy 2.5.3, scikit-learn 1.9.1;
Node 22.23.4 with no npm packages installed; no Flutter SDK; fastapi, httpx and pygame not installed.

`python tools/run_all_tests.py --smoke` (exit 0, after the Gate B fixes):

```
Python unit tests                PASSED   (87 run, 2 skipped)
Browser v1 parity tests (Node)   SKIPPED: run npm install in the web folder first
Browser v2 tests (Node)          PASSED   (8 of 8)
Browser camera smoke test        SKIPPED: run npm install in the web folder first
Flutter tests                    SKIPPED: the Flutter SDK is not installed
```

The 2 Python skips are the whole of `tests/test_api.py` (8 tests; fastapi missing) and the cached
speech playback test (pygame missing).

| Criterion (docs/prompts/phase-1.md) | Measured | Produced by | Result |
|---|---|---|---|
| All Phase 0 tests pass | 31 of the 40 Phase 0 Python tests ran here and passed; 9 did not run (8 API, 1 speech). Phase 0 browser parity: 4 of 4 passed, but only with a temporary stand-in for `@mediapipe/tasks-vision` (npm install is blocked here; `web/src/vision.js` is unchanged since `phase-0`). Smoke test not run. | `tools/run_all_tests.py`; `git diff phase-0 -- ml_engine/features.py ml_engine/gestures.py web/src/vision.js tests/golden/v1_hands.json tests/test_core.py tests/test_baseline.py tests/test_api.py` is empty | **NOT VERIFIED** — `backend/app.py` changed (model loader guard) and its tests did not run |
| v2 parity tests pass on 1,000+ fixture frames | 1,132 frames, 1,099,172 values, largest \|JS − Python\| = 0 (tolerance 1e-6). A planted 2e-6 error in the JS port was caught (`2.0000000000575113e-06 not less than or equal to 1e-06`), then reverted. | `tests/test_features_v2.py::JavaScriptParityTests`, `web/tests/v2-parity.test.mjs` | **PASS** (Python == JS; Dart port not written, see below) |
| Web capture ≥ 24 fps on a mid-range laptop browser | not measured: no camera, GPU or browser packages here | `web/bench.html` is ready for the measurement | **OPEN [HUMAN]** |
| Rotated-frame test: identical features for upright and rotated input after correction | Python `CaptureV2`: largest feature difference < 1e-9 for 90°, 180°, 270° and 0°; without correction > 0.5. The phone path (Dart rotation rule + `copyRotate`) has tests in `mobile/test/` that have **not run**. | `tests/test_capture_v2.py::RotatedFrameTests` (real pixel rotation, real `CaptureV2`, marker-reading stand-in landmarker) | **PASS for Python only; NOT VERIFIED for the phone**, which is where F4 lives |
| No image or video written to disk by any capture path | Python: 0 writer calls and 0 new files with all image/video writers patched to fail, over 30 stand-in frames and 20 frames through the real MediaPipe hand model. Web: source scan plus `web/tests/capture-v2.test.mjs` with a stand-in MediaPipe (no browser run). Dart: source scan of `frame_rotation.dart`, `frame_errors.dart`, `frame_convert.dart` and `main.dart` for disk writes (`writeAsBytes`, `File(`, `path_provider`, ...); `frame_convert.dart` encodes a JPEG in memory for the local server, as Phase 0 did. | `tests/test_capture_v2.py::NoImageOnDiskTests` | **PASS for Python; web and Dart by source scan only** |

Licence checker: does not exist yet (Phase 2, `data/LICENSES.yaml`). Vocabulary sync check:
`python tools/sync_vocabulary.py --check` exit 0.

### Every number in this phase and where it comes from

| Number | Source |
|---|---|
| 971 features per frame, 120 points per frame, 9 pose + 69 face points | `shared_data/feature_spec_v2.json`; `tests/test_features_v2.py::SpecTests` |
| 1,132 fixture frames, 37 sequences, 52 canonicalize cases, 1,541 KB | `python tests/golden/make_v2_golden.py` output; `tests/golden/v2_holistic.json.gz` |
| largest \|JS − Python\| = 0 over 1,099,172 values | `tests/test_features_v2.py::JavaScriptParityTests` (prints the line) |
| planted 2e-6 error caught | manual mutation run, Gate A (not committed) |
| rotation differences < 1e-9 / > 0.5 | `tests/test_capture_v2.py::RotatedFrameTests` assertions |
| 14 rotation cases | `tests/golden/rotation_cases.json` |
| 87 Python tests run (31 Phase 0 + 54 new + 2 skip entries), 8 Node v2 tests, 11 Dart tests written | test files; `tools/run_all_tests.py` output |
| F12 thresholds (0.98, 0.95, 0.05, 0.05, 0.95, 0.98, 0.05) | `tools/check_mirroring_f12.py` `THRESHOLDS`: starting values chosen before any measurement |
| Gate B: 0 difference over 305,675 values on 42 edge-case sequences; 8 of 8 JS mutations caught | reviewer's own runs, not committed |
| 24 fps, 1e-6 tolerance, 1,000 frames | targets from `docs/prompts/phase-1.md` |

No accuracy, latency or frame-rate number was measured in this phase.

## What changed

- `CLAUDE.md`, `docs/CONTEXT.md`, `docs/prompts/*`, `docs/handoffs/TEMPLATE.md`: the five prompt layers, copied from the architecture document (commit on `v2/main`).
- `shared_data/feature_spec_v2.json`: the v2 contract (parts, face and pose indices, mirror pairs, hand assignment, normalisation, 971-value layout, capture models).
- `ml_engine/features_v2.py` (reference) and `web/src/features_v2.js`: canonical frames and sequence features.
- `ml_engine/capture_v2.py` and `web/src/capture_v2.js`: Pose + Hand + Face landmarkers, upright rotation, fps meter. The Python package has no Holistic Landmarker, so both platforms use the split models.
- `ml_engine/recording_v2.py`: recording format v2. `tools/convert_v1_to_v2.py`: v1 CSV rows to 1-frame records.
- `ml_engine/feature_versions.py`: feature version names and descriptions. In practice the "switch" is that every model bundle and recording names its feature version and the v1 loaders (`ml_engine/model_loader.py`, `backend/app.py`) refuse anything but v1; `train_model.py` writes `feature_version: v1`. `resolve_feature_version` / `SIGNBRIDGE_FEATURE_VERSION` exist but no client reads them yet: v2 is used only by calling capture v2 directly.
- `mobile/lib/frame_rotation.dart`, `frame_convert.dart`, `frame_errors.dart`, `main.dart`: F4 rotation, 2-plane iOS and BGRA frames, F5 error reporting, overlay mirrored only for the front camera. Replaces `_jpegFromYuv` (reason: it read `planes[2]`, which does not exist on iOS, and never rotated).
- `tools/check_mirroring_f12.py`: the F12 check for real clips.
- `web/bench.html`, `web/src/bench.js`, `web/vite.config.js`, `web/scripts/copy-assets.mjs`: frame-rate bench page and its assets.
- `tools/run_all_tests.py`: runs the v2 Node tests without npm packages, runs `flutter test` when available, and reports the smoke test as skipped (not failed) when npm packages are missing.
- Tests: `tests/test_features_v2.py`, `test_capture_v2.py`, `test_recording_v2.py`, `test_check_mirroring_f12.py`, `web/tests/v2-parity.test.mjs`, `web/tests/capture-v2.test.mjs`, `mobile/test/*.dart`.
- Docs: `docs/PHASE1_CAPTURE.md`, README sections, `mobile/README.md`.

No Phase 0 characterisation test was changed.

## Gate B round 1 (2026-11-18): FAIL — findings and what was done

| Severity | Finding | Status |
|---|---|---|
| high (consent) | v1 records carried a placeholder consent ID that passed the "consent required" check, undocumented | **Fixed**: `consent_recorded` (required); live captures must be true; v1 records are false and `training_use_refusal()` refuses them; documented |
| medium (honesty) | Dart no-disk scan skipped the real capture code (`frame_convert.dart`, `main.dart`) | **Fixed**: both scanned for disk writes; claim corrected above |
| medium (honesty) | Rotated-frame criterion marked PASS although only the Python path ran; F4 lives in Dart | **Fixed**: marked NOT VERIFIED for the phone |
| medium (privacy) | F12 asked for 40 video clips with no consent, retention or deletion guidance; reports included folder path and clip names | **Fixed**: guidance in the tool; folders inside the repo are refused; reports use `clip_NN` |
| medium | F12 never checked the no-pose label rule against the hand actually used | **Fixed**: `label_truth` measure and `label_rule` check |
| medium (leakage by design) | each v1 frame becomes a record, so near-duplicates from one sitting look independent | **Fixed**: `instance_unit: frame`; docs say split v1 records by signer only |
| low (leakage) | pseudonyms differed for "Ayesha  Khan" vs "Ayesha Khan"; no way to spot a different key | **Fixed**: whitespace collapsed; `signer_key_fingerprint` stored. Spelling variants still need a person to review the signer map |
| low (privacy) | name blocklist only checked top-level keys | **Fixed**: metadata allowlist; `device` must be an ID |
| low (honesty) | `SIGNBRIDGE_FEATURE_VERSION` is read by no client | **Reworded** (above); not wired, since no v2 client exists yet |
| low | pose-based hand assignment ignores wrist visibility | **Open**: decide after F12 shows real behaviour |
| low (licence, disclosed) | pose/face `.task` files have no SHA-256 check and get copied into web builds without a ledger entry | **Open**: Phase 2 ledger; must be done before any release build |
| info | implicit `camera` promotion; any `TypeError` read as an unreadable reply | **Fixed**: `camera!`; replies parsed in `_parseRecognitionReply`, other `TypeError`s are "unexpected" |

## Measured results

| Metric | Value | Dataset / split / signers | Device | Report file |
|---|---|---|---|---|
| Python vs JS feature parity (max abs difference) | 0 | synthetic fixture, 1,132 frames, no signers | cloud container above | `tests/golden/v2_holistic.json.gz` via `tests/test_features_v2.py` |
| Rotation correction (max feature difference) | < 1e-9 | synthetic marker scenes | cloud container above | `tests/test_capture_v2.py` |
| Web capture frame rate | not measured | — | — | — |
| F12 on real recordings | not measured | — | — | — |

## Coverage

Tier A: 0 glosses · Tier B: 0 · Tier C: not supported yet · Tier D: 64 (unchanged vocabulary).
Phase 1 does no recognition.

## Data and licences

No data added; `data/` is still empty. New ledger candidates for Phase 2: the MediaPipe
`pose_landmarker_lite.task` and `face_landmarker.task` model files (downloaded on first use into
`models/`, not committed) need `data/LICENSES.yaml` entries alongside the committed
`hand_landmarker.task`. Their SHA-256 hashes are not recorded yet (no network here).

## Not done / not tested

On Windows, `phase1_checks.bat` (repository root) does the first and third items below in one go:
it installs the packages, runs every suite with `--smoke`, writes logs and machine details to
`reports\phase1_checks\`, and opens the benchmark page. It was written without a Windows machine
to try it on.

- **[HUMAN] Frame rate.** On a mid-range laptop: `npm install` in `web/`, place the pose and face models in `models/` (see README), `npm run dev`, open `/bench.html`, run 30 s with your upper body and face in view, copy the JSON into this handoff. Gate: `fps` ≥ 24.
- **[HUMAN] F12 recordings.** Record about 20 clips signing with the left hand and 20 with the right (3-6 s, upper body and face visible), name them `left_*.mp4` / `right_*.mp4`, run `python tools/check_mirroring_f12.py --clips <folder>`, and commit `reports/f12_mirroring.md`.
- **Full Phase 0 suite** on a machine with `requirements.txt` installed and `npm install` done: `python tools/run_all_tests.py --smoke`. The API tests matter most because `backend/app.py` changed.
- **Flutter.** Nothing in `mobile/` was compiled or run. Run `flutter analyze` and `flutter test` in `mobile/`, then try the app on an Android phone (portrait and landscape, front and back camera) and an iPhone. The iOS rotation branch follows Google's ML Kit example and is the least certain part.
- **Dart parity for features v2** (spec: "== Dart where Flutter is available") was not written: Flutter is not available here, and the phone does not compute features until Phase 7.
- **Real landmarks.** Capture v2 has only run on synthetic frames. Pose and face models were never loaded (they could not be downloaded here). The web capture ran only against a stand-in MediaPipe.
- **Browser builds.** `vite build` with the new `bench.html` input was not run.
- **Assumption to confirm with F12:** that MediaPipe's pose and face left/right labels follow a mirrored image (so canonicalize swaps them back). If F12 fails `pose_swap_rule`, change the rule in the spec, bump `spec_version`, and regenerate the fixture.
- Gate B has not been run.

## Current state (copy into CONTEXT.md)

- Hand tracking v1 unchanged: MediaPipe Hand Landmarker, 1 hand, 21 landmarks; 13 rule-based demo poses; all clients still use v1 by default (`ml_engine/feature_versions.py`).
- Capture v2: `ml_engine/capture_v2.py`, `web/src/capture_v2.js`; Pose + Hand + Face landmarkers; frames rotated upright first; canonical frames (unmirrored view, anatomical sides) per `shared_data/feature_spec_v2.json` (spec 2.0.0).
- Features v2: 971 values per frame (positions, hand shapes, velocities, hand-face and hand-hand distances, masks); Python reference `ml_engine/features_v2.py`, JS port `web/src/features_v2.js`; parity fixture `tests/golden/v2_holistic.json.gz` (1,132 synthetic frames, difference 0).
- Recording format v2: `ml_engine/recording_v2.py` (.npz per sign instance, landmarks only, metadata allowlist, recorded consent required for live captures, pseudonymous signer IDs); v1 converter `tools/convert_v1_to_v2.py`. No recordings exist yet.
- Model bundles name their feature version; v1 loaders refuse others. No trained model exists.
- Flutter: frames rotated before sending (F4), errors classified (F5); not yet compiled or run on a phone.
- Tests: 85 Python tests plus 8 Node v2 tests run here; Phase 0's 8 API tests, 1 speech test, 4 v1 browser parity tests and 4 smoke tests need installed packages; 11 Dart tests need Flutter. Run: `python tools/run_all_tests.py [--smoke]`; on Windows `phase1_checks.bat` also installs everything and opens the fps benchmark.
- Records converted from v1 have no consent record (`consent_recorded: false`) and are one frame each; `training_use_refusal()` must gate every Phase 2 training or export path.

## Open findings (copy into CONTEXT.md)

- F3 rejection only on desktop SVM (Phase 3).
- F4 fix implemented in Flutter, **not verified on a device**; keep phone training data blocked until it is.
- F5 fix implemented, **not verified on a device**.
- F7 `SVC(probability=True)` removed in scikit-learn 1.11 (Phase 3).
- F9 browser MediaPipe telemetry (Phase 7).
- F10 participant names served without auth (Phase 2).
- F12 tool ready; needs the 40 recorded clips.
- New: web capture frame rate unmeasured (Phase 1 gate).
- New: the canonical left/right swap rule for mirrored input is an assumption until F12 runs.
- New: pose-based hand assignment ignores wrist visibility (decide after F12).
- New: pose/face model files need SHA-256 pinning and licence ledger entries before any release build (Phase 2).
