# Master v3 Stage 0 handoff — 2026-11-20

## Result
Gate **not passed yet** (waiting for [ME] steps: Kaggle run, owner's laptop/phone measurements,
camera check by a person). Branch `v3/master`; preview workflow green (run 44709553244). Report:
`reports/v3_stage0_baseline.md`.

## What changed
- `CLAUDE.md` section 9; `docs/prompts/master-v3.md` saved.
- `baseline/` (frozen Inference Baseline v1: 19 files in git, 47 restored by `tools/baseline_v1.py`,
  `baseline/manifest.json` with every SHA-256); `.gitattributes` keeps it byte-exact.
- `tools/baseline/run.mjs`, `harness.mjs`, `cases.mjs`: run the frozen build in Chromium and record or
  compare `tests/golden/baseline_v1_outputs.json` (inputs: `tests/golden/baseline_v1_inputs.json`).
- `tests/test_inference_baseline.py`, `web/tests/inference-baseline.test.mjs`: today's Python and JS
  must reproduce the baseline (frames and model inputs bit for bit); server vs baseline top-1 in CI.
- `web/src/synthetic_sign.js`: the self-test's made-up signer, shared (no behaviour change).
- `web/src/wasm_locate.js` (+ test), used by `asl_litert.js`: fixes the ASL worker regression on
  `main` by porting the baseline build's `locateFile` fix (no rewrite: one call added).
- `web/scripts/build-shared.mjs`, `web/shared-copy/`, `npm run build:shared` (+ test).
- `.github/workflows/preview.yml`: tests, baseline comparison, ASL worker + server check, Pages
  build and shared copy for `v3/**` and pull requests; never deploys.
- `tools/run_all_tests.py`: adds "Baseline v1 in a browser" (SKIPPED when the baseline files are not
  restored; required in CI via `BASELINE_REQUIRED=1`).
- Site address: `shared_data/site.json`, `docs/DOMAIN.md`, `tools/old_address_redirect/`,
  `tests/test_site_address.py`; README and `docs/WEBSITE.md` updated.
- Any laptop: `setup_windows.bat`, `docs/SETUP_NEW_LAPTOP.md`. Guides: `docs/HOW_TO_MEASURE_SPEED.md`,
  `docs/HOW_TO_PUBLISH_BASELINE.md`; `docs/HOW_TO_RUN_ASL_EVAL.md` now downloads the notebook from GitHub.

## Measured results
| Metric | Value | Dataset / split / signers | Device | Report file |
|---|---|---|---|---|
| Baseline reproduces itself | 39/39 model cases, all pipeline outputs | golden fixtures (synthetic) | workspace Chrome 153; GitHub Actions Chromium | reports/v3_stage0_baseline.md |
| Python and JS vs baseline | bit-identical frames and model inputs | same | Python 3.13, Node 22 | same |
| Model time per sign (32 frames, worker) | median 12.8 ms (baseline build); 9.8-16.3 ms (v3 build) | synthetic | workspace 2 cores; Actions 4 cores | same |
| Browser vs server | max probability difference 1.9e-8, same top-1 3/3 | synthetic | GitHub Actions | same |
| GISLR accuracy, frame counts, one/two-handed, left/right, hand slots | pending | GISLR rerun set | Kaggle | asl_mode_v1.md |

## Coverage
Unchanged: PSL Tier A 0 · Tier B 0 · Tier C optional (server only) · Tier D 64. ASL mode: 250 ASL
signs, accuracy pending.

## Data and licences
No new ledger entries. The baseline zip's third-party files are the ledger's existing assets
(MediaPipe models, ASL model, LiteRT.js, SLT dictionary clips); they are not committed.

## Not done / not tested
- [ME] Kaggle run; laptop + phone self-test and camera check; baseline release + tag; optional domain move.
- The tag `inference-baseline-v1` exists only in this workspace (push refused); the owner creates it
  with the release.
- Source of the baseline's UI extras (themes, Test signs, How to sign clips, Training screen) is not in
  git; rebuilt in Stages 3 and 5.
- Flutter tests not run (no Flutter SDK here or in CI).
- The capture frame rate measured here (~1 fps) is not representative; real devices pending.

## Current state (copy into CONTEXT.md)
See docs/CONTEXT.md (regenerated with this handoff).

## Open findings (copy into CONTEXT.md)
- "Pretty sure" (≥ 0.60) shown for a PSL sign in ASL mode: threshold alone does not stop wrong words.
- Releases/tags cannot be created from Claude's session: owner steps needed (baseline now, v3.0.0 at Stage 7).
- Baseline UI extras without source in git.
