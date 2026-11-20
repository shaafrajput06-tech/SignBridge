# SignBridge — Context pack (state at the end of master v3 Stage 0, 2026-11-20)

## Product goal
A Deaf PSL signer and a hearing Urdu/English speaker hold a real conversation through one device.
Signing becomes text and speech on first launch, with honest confidence; replies become text and
reference sign clips. Works offline on a laptop, in a browser and on a phone.

## Plan in force: master v3
`docs/prompts/master-v3.md` (Stages 0-7) builds on the fast track (`docs/prompts/fast-track.md`,
CLAUDE.md section 8) and adds CLAUDE.md section 9 (baseline protection, licensed internet-video
learning, language purity, AI never invents a sign, measured performance budgets).
All work happens on branch **`v3/master`**; `main` is the live website and changes only when the
owner merges the v3 pull request in Stage 7. Stage 0 is done up to its gate (see "Waiting for").

## Where things live
- GitHub: `shaafrajput06-tech/SignBridge` (moving to `signbridge-pk/signbridge-pk.github.io`,
  `docs/DOMAIN.md`). Live site today: <https://shaafrajput06-tech.github.io/SignBridge/>; chosen
  address <https://signbridge-pk.github.io/> (`shared_data/site.json`).
- Any laptop: clone, `git checkout v3/master`, double-click `setup_windows.bat`
  (`docs/SETUP_NEW_LAPTOP.md`). The owner has no folder shared with Claude; GitHub is the only home.
- CI: `.github/workflows/website.yml` (main only: tests, build, deploy to Pages, results at `/ci/`);
  `.github/workflows/preview.yml` (`v3/**` and pull requests: tests incl. the baseline comparison,
  ASL worker + server check, Pages build and `build:shared` as artifacts; never deploys).

## Inference Baseline v1 (protected, CLAUDE.md 9.1)
- `baseline/v1-site/` + `baseline/v1-shared/`: the built shared copy of 2026-11-19, byte for byte
  (19 files in git; 47 third-party files restored by `python tools/baseline_v1.py restore
  --download | --zip PATH | --from-sources`, each checked against `baseline/manifest.json`).
- `tests/golden/baseline_v1_outputs.json`: what it produces on the golden fixtures, recorded in
  Chromium by `node tools/baseline/run.mjs --record` (frames, resampling, segments, words, real model
  top-5 for 39 cases). `tests/test_inference_baseline.py` and `web/tests/inference-baseline.test.mjs`
  hold today's code to it; `run_all_tests.py` runs the browser comparison when the baseline is restored.
- A new model replaces it only if better on top-1 on the same set and within the latency budget.

## Current state
- PSL: capture v2 (both hands + pose + face) on the PSL screen; PSL recognition "Not installed yet";
  Phase 0 gesture demo off by default. Coverage: Tier A 0, Tier B 0, Tier C optional (server only),
  Tier D 64. No trained PSL model.
- ASL mode: ISLR 1st-place TFLite (250 signs, MIT) — browser (LiteRT.js in a Web Worker, 32 frames)
  and server (ai-edge-litert, native length). On v3 the worker works again (`web/src/wasm_locate.js`);
  on the live `main` build it falls back to the page thread. Accuracy on the GISLR rerun set: pending.
- Features v2 (971 values/frame), recording format v2, licence ledger (`data/LICENSES.yaml`, 23 assets,
  `data_engine.ledger.assert_allowed`), vocabulary 64 entries — unchanged since fast-track Stage 2.
- `npm run build:shared` (in `web/`) makes `web/dist-shared/SignBridge-shared-copy.zip`.
- Tests: `python tools/run_all_tests.py [--smoke]`. CI (preview run 44709553244): 180 Python tests
  (2 skipped), licence check, Node v1 + v2 suites, baseline browser comparison — all passed.

## Waiting for (owner [ME])
1. Kaggle: `notebooks/asl_mode_eval.ipynb` → `asl_eval_results.json` (`docs/HOW_TO_RUN_ASL_EVAL.md`).
2. Laptop + phone self-test and camera check (`docs/HOW_TO_MEASURE_SPEED.md`).
3. Baseline release + tag `inference-baseline-v1` (`docs/HOW_TO_PUBLISH_BASELINE.md`): Claude's
   session cannot create releases or push tags.
4. Optional before Stage 7: the move to `signbridge-pk.github.io` (`docs/DOMAIN.md`); after it,
   Claude needs repo access again under the new name.

## Open findings
- "Pretty sure" (≥ 0.60) was shown for a PSL sign in ASL mode, and for 2 of 39 synthetic inputs: the
  threshold alone does not keep wrong words from being spoken. Set it from the Kaggle calibration table
  and add an unknown/not-a-sign check (ASL now; PSL in Stage 2).
- The baseline's UI extras (10 colour themes, Test signs, How to sign clips, Training screen) have no
  source in git; rebuild in Stages 3 and 5.
- Carried over: F3 rejection only on desktop SVM · F4/F5 Flutter fixes not verified on a device · F7
  `SVC(probability=True)` removed in scikit-learn 1.11 · F9 browser MediaPipe telemetry · F10
  participant names served without auth · F12 mirroring unverified on real video · pose/face `.task`
  hashes pinned but model cards not re-read · pose-based hand assignment ignores wrist visibility.

## People and decisions
- Deaf validation partner: none yet (requests drafted in `docs/permission_requests.md` [ME]).
- Website address: `signbridge-pk.github.io` (2026-11-20; `signbridge.github.io` is taken).
- Compute: free Kaggle / Colab GPU via notebooks the owner starts; GitHub Actions for builds/checks.

## Environment notes
Claude's workspace: no package installs, no artifact downloads, GitHub API limited to this repository,
no releases or tag pushes; headless Chrome 153 and Python mediapipe are available, so the baseline can
be run here. Project: Python 3.10-3.14, Node 22.12+, mediapipe 0.10.x, @mediapipe/tasks-vision 1.2.2,
@litertjs/core 2.6.0, scikit-learn < 1.11.
