# SignBridge v2 — Context pack (state at the end of fast-track Stage 1)

## Product goal
A Deaf PSL signer and a hearing Urdu/English speaker hold a real conversation through one device.
Signing becomes text and speech on first launch, with honest confidence; replies become text and
reference sign clips. Works offline on a laptop, in a browser and on a phone.

## Plan in force: the fast track
`docs/prompts/fast-track.md` replaces the Phase 2-8 path, because the owner cannot record signers or
train models. CLAUDE.md section 8 holds its amendments (no user training, separate ASL mode, exhibition
tiers, both hands always, built-in AI instead of human set-up). Branch `v2/fast-track` (from
`v2/phase-1`). Stage 1 (asset audit) is done and waits at its gate; next is Stage 2 (ASL mode).

## Current state
- Hand tracking v1 (default in every client): MediaPipe Hand Landmarker, 1 hand, 13 rule-based demo
  poses (`ml_engine/gestures.py`, `web/src/vision.js`). No PSL source is recorded for the demo poses.
- Capture v2 (`ml_engine/capture_v2.py`, `web/src/capture_v2.js`): Pose + Hand (2 hands) + Face
  landmarkers, frames rotated upright, canonical frames per `shared_data/feature_spec_v2.json` (spec 2.0.0).
- Features v2: 971 values per frame; Python reference and JS port agree exactly on the fixture.
- Recording format v2 (`ml_engine/recording_v2.py`): landmarks only, consent required. No recordings.
- **Licence ledger** `data/LICENSES.yaml` (23 assets) + `data/licenses.schema.json`; checker
  `tools/check_licenses.py` (also run by `tools/run_all_tests.py`); gate for code
  `data_engine.ledger.assert_allowed(asset_id, use, purpose_language)`.
- No trained model exists. Coverage: Tier A 0, Tier B 0, Tier C not supported, Tier D 64.
- Vocabulary: `vocabulary.json`, 64 entries, synced to `shared_data/` and `mobile/assets/`.
- API: FastAPI + SQLite (`backend/`). Clients: OpenCV desktop, React/Vite web, Flutter (never built here).
- Tests: `python tools/run_all_tests.py [--smoke]`. Here: 114 Python tests (2 skipped: API tests need
  fastapi, speech test needs pygame), licence check, 8 Node v2 tests. On Windows, `phase1_checks.bat`
  installs everything and runs all suites (`docs/HOW_TO_RUN_PHASE1_CHECKS.md`).

## Stage 1 findings that shape the next stages (reports/fast_track_assets.md)
- ASL mode: ISLR 1st-place TFLite (MIT, 250 signs) needs no training; measure on the CC0 GISLR rerun
  set inside Kaggle, not on the competition training data (the model was trained on it).
- PSL camera recognition is trainable from public data for 12 of 64 entries (SignSpeak Apache-2.0,
  PkSLMNM CC BY 4.0) plus UAlpha40 letters. No signer IDs, so splits are "weaker" and everything starts
  as Tier B until signer IDs or PSL-128 access arrive.
- PSL reference clips: SLT dictionary (788 clips, CC BY 4.0, provenance unverified) covers 33 entries
  + 2 phrases word by word.
- 21 entries have no shippable PSL data. No Deaf-validated public PSL data exists.
- This workspace cannot download files (shell network blocked); assets must be attached by the owner or
  fetched through a connected folder on the owner's computer.

## Open findings
- F3 rejection only on desktop SVM · F5 Flutter errors (fix not verified on a device) · F7
  `SVC(probability=True)` removed in scikit-learn 1.11 · F9 browser MediaPipe telemetry · F10 participant
  names served without auth · F4 Flutter rotation fix not verified on a device.
- F12 mirroring unverified on real video; the left/right swap rule for mirrored input is an assumption.
- Phase 1 gate: web capture frame rate unmeasured; full Phase 0 suite (API, browser smoke) not run here.
- One-hand v1 paths remain: `web/src/vision.js`, `backend/app.py /api/recognize-frame` (used by Flutter).
- Pose/face `.task` files: SHA-256 not recorded, model cards not re-read; `--release` blocks until done.
- Pose-based hand assignment ignores wrist visibility.

## People and decisions
- Deaf validation partner: none yet (FESF / Deaf Reach asked in `docs/permission_requests.md` [ME]).
- Permission requests drafted, not sent: FESF, PSL-128, UMT, SLT maintainer, SignSpeak, WLPSL.
- Compute: free Kaggle / Colab GPU via notebooks the owner starts with "Run all".

## Environment notes
Python 3.10-3.14, Node 22.12+, mediapipe 0.10.x (Python), @mediapipe/tasks-vision 1.2.x, scikit-learn
<1.11, PyYAML for the ledger. No GPU, camera or file downloads in the agent's workspace.
