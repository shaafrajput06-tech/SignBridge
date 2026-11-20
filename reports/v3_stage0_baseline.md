# Master v3, Stage 0: freeze the baseline, finish ASL mode — report

Date: 2026-11-20. Branch `v3/master` (from `main` at `42a572f`). Status: **gate not passed yet.**
Everything that can be built, run and measured without the owner's devices and a Kaggle run is done.
The rows marked *pending* need the [ME] steps at the end; none of them is estimated.

ASL is a separate language mode (CLAUDE.md 8.2). Nothing here is, or is shown as, PSL.

## What was done

| Item (master-v3.md) | Done | Where |
|---|---|---|
| Copy snapshot A's `site/` as a read-only reference | yes: 19 SignBridge-built files in git byte for byte, 47 third-party files (runtimes, models, CC BY 4.0 clips) restored from the zip or from the same pinned sources, every file checked against its SHA-256 | `baseline/`, `tools/baseline_v1.py` |
| Tag `inference-baseline-v1` | yes: tag on `42a572f` and the pre-release "Inference Baseline v1 (frozen reference)" with the zip as `SignBridge.zip` (GitHub's SHA-256 of the asset equals the frozen one). Made in the owner's browser on 2026-11-20, because this session's GitHub access may not create releases or push tags. `restore --download` restores 66 of 66 files from it | GitHub release `inference-baseline-v1` |
| Record input → output on the golden fixtures | yes, from the frozen build itself in Chromium, including the real model's top-5 for 39 cases | `tests/golden/baseline_v1_outputs.json`, `tools/baseline/` |
| Hold today's code to it | yes: Python and JavaScript reproduce the frames and the exact 32 × 543 × 3 model inputs bit for bit; the server path's top-1 is compared with the baseline browser path in CI | `tests/test_inference_baseline.py`, `web/tests/inference-baseline.test.mjs` |
| `npm run build:shared` | yes; packaging the frozen site reproduces the baseline zip's 66-file list with identical bytes (only `README.txt` is new). CI builds the v3 shared copy on every push | `web/scripts/build-shared.mjs` |
| Constitution section 9 | yes | `CLAUDE.md` |
| Preview build for every stage | yes: workflow on `v3/**` pushes and pull requests, artifacts `site-preview`, `shared-copy`, `check-results`; never deploys | `.github/workflows/preview.yml` |
| Kaggle evaluation (top-1/top-5, 16-64 frames, one/two-handed, left/right, hand slots) | notebook ready and covers all of these; **run pending** [ME] | `notebooks/asl_mode_eval.ipynb`, `docs/HOW_TO_RUN_ASL_EVAL.md` |
| Browser latency on the owner's laptop and phone | **pending** [ME] | `docs/HOW_TO_MEASURE_SPEED.md` |

Also done because they came up during the stage:

- **ASL worker regression fixed.** On the live build (`main`, Actions run 44525001065, 2026-11-19), the
  ASL model could not run in the Web Worker: the WebAssembly glue looked for its `.wasm` next to the
  worker script, got the HTML page back (`expected magic word 00 61 73 6d, found 3c 21 64 6f`) and fell
  back to the page thread. The frozen baseline build has a fix that never reached git; it is ported
  from the built code (`web/src/wasm_locate.js`). The v3 preview run 44709553244 now reports
  `worker true`.
- **Website address** `https://signbridge-pk.github.io/` (owner's choice; `signbridge.github.io` is
  taken by another GitHub organisation): `shared_data/site.json`, `docs/DOMAIN.md`, forwarding pages
  for the old address, a test that keeps every link consistent.
- **Any laptop can run and edit the project from GitHub:** `setup_windows.bat`,
  `docs/SETUP_NEW_LAPTOP.md`.

## Measured results

Synthetic inputs measure plumbing and speed, never accuracy.

| Metric | Value | Data | Device / browser | Source |
|---|---|---|---|---|
| Baseline reproduces itself | 39 of 39 model cases identical (same input SHA-256, same top-1, top-5 within 0.001), plus all frames, resamplings, segments and score words | golden fixtures (synthetic) | this workspace, headless Chrome 153, 2 logical cores, 2026-11-20; and GitHub Actions ubuntu-latest, Chromium, 2026-11-20 | `node tools/baseline/run.mjs`; preview run 44709553244 |
| Python (`ml_engine/asl_islr.py`) vs baseline | 26 of 26 unmirrored frames bit-identical (26 mirrored refused, as in the baseline); 84 of 84 resamplings; 13 of 13 segmenter streams; 5 of 5 score vectors; 32 of 32 model inputs bit-identical | same | this workspace, Python 3.13 | `tests/test_inference_baseline.py` |
| JavaScript (`web/src/asl_islr.js`) vs baseline | the same, and 39 of 39 model inputs (incl. 7 synthetic-signer signs) bit-identical | same | Node 22 | `web/tests/inference-baseline.test.mjs` |
| Model time per sign, baseline build, 32 frames, worker | median 12.8 ms over 39 cases (min 11.2, max 34.6); compile 367 ms | same | this workspace, headless Chrome 153, 2 logical cores | `run.mjs --timings` |
| Model time per sign, v3 preview build, worker | 16.3 / 10.9 / 9.8 ms (signs of 10 / 32 / 57 frames); compile 569 ms | self-test signs (synthetic) | GitHub Actions, HeadlessChrome 159, 4 logical cores | preview run 44709553244 |
| Same, live `main` build, page-thread fallback | 19.2 / 13.9 / 13.3 ms | same | GitHub Actions, HeadlessChrome 159, 4 logical cores, 2026-11-19 | Actions run 44525001065 |
| **Owner's laptop**, live `main` build (page-thread fallback; the worker failed with the same wasm error) | 51.8 / 49.4 / 46.9 ms per sign; 13.1 s from opening the page to a compiled model (includes downloading the 11 MB model and the runtime) | same | owner's Windows laptop (4 logical cores, ≥ 8 GB), the Claude desktop app's built-in browser (Chromium 156), pane displayed, 2026-11-20 | `asl-selftest.html` on the live site |
| Browser (LiteRT.js) vs server (ai-edge-litert), identical input | largest probability difference 1.9e-8; same top-1 on 3 of 3 | same | GitHub Actions | preview run 44709553244 |
| Server path (ai-edge-litert 2.3.0) vs the frozen baseline's browser outputs | top-1 identical on 32 of 32 fixture cases; largest top-5 probability difference 5.4e-7 | golden fixtures (synthetic) | GitHub Actions | preview run 44711995910 |
| Camera → ASL word on screen (plumbing only) | the baseline app showed "Pretty sure · kiss" (10 frames, 4 with both hands, model 68 ms, ran in the browser) | Chrome's fake camera playing the CC BY 4.0 PSL dictionary clip "help", slowed 12× | this workspace, headless Chrome 153 | manual run, 2026-11-20 |
| Capture frame rate | about 1 frame per second (10 frames in about 10 s of visible hands) | same | this workspace (2 cores, software WebGL): **not representative** of a laptop or phone | same |
| Top-1 / top-5, GISLR rerun set, native length and 16/24/32/48/64 frames | **pending** | GISLR rerun set (CC0), signers absent from training | Kaggle | `notebooks/asl_mode_eval.ipynb` [ME] |
| One- vs two-handed, left- vs right-dominant, hand-slot convention, accuracy above 0.60 | **pending** | same | Kaggle | same [ME] |
| Time per sign and frame rate on the owner's laptop and phone; camera → ASL word with a person signing | **pending** | — | owner's devices | `docs/HOW_TO_MEASURE_SPEED.md` [ME] |

## Findings that change later stages

1. **"Pretty sure" is not safe on signs outside the model's 250 ASL words.** The camera run above was a
   PSL sign, yet the model said "Pretty sure · kiss" (≥ 0.60), and 2 of the 39 synthetic cases also
   cleared 0.60 ("now"). Speaking only "Pretty sure" results therefore does not by itself meet the
   target "wrong word spoken aloud ≤ 2 %" (master-v3.md section 4). Next: choose the threshold from the
   Kaggle calibration table (the notebook reports accuracy above each threshold), and add an
   "unknown / not a sign" check for ASL mode as Stage 2 plans for PSL. Until then ASL results should
   not be spoken automatically; that change waits for the Kaggle numbers so it is made on evidence.
2. **The frozen baseline was built from source that is not in git** (the worker fix, 10 colour themes,
   "Test signs" cards, "How to sign" clips, a training screen). The worker fix is now in git. The
   others are user-interface work, rebuilt in later stages (clips: Stage 3; themes: Stage 5), and the
   baseline build stays available for comparison.
3. **This session cannot create GitHub releases or push tags** through its own GitHub access. The
   baseline release was made in the owner's signed-in browser instead; the release `v3.0.0` in Stage 7
   will be made the same way.
4. **Frame count for the browser path is decided by the Kaggle numbers, with a rule fixed in
   advance:** the smallest of 16/24/32/48/64 whose top-1 is within 0.5 points of the native length;
   if none is, the largest within the latency budget, and the server path stays the laptop default.

## [ME] steps to pass the gate

1. Kaggle: run `notebooks/asl_mode_eval.ipynb` and attach `asl_eval_results.json`
   (`docs/HOW_TO_RUN_ASL_EVAL.md`, about 10 minutes of clicks plus 30-90 minutes of waiting).
2. Laptop and phone: the self-test and the camera check (`docs/HOW_TO_MEASURE_SPEED.md`).
3. ~~Publish the baseline release and tag~~ — done 2026-11-20.
4. Optional now, needed by Stage 7: the move to `signbridge-pk.github.io` (`docs/DOMAIN.md`).
