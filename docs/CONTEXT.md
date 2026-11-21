# SignBridge — Context pack (master v3: Stages 0-6 done, release prepared, 2026-11-21)

## Product goal
A Deaf PSL signer and a hearing Urdu/English speaker hold a real conversation through one device.
Signing becomes text and speech on first launch, with honest confidence; replies become text and
reference sign clips. Works offline on a laptop, in a browser and on a phone.

## Plan in force: master v3
`docs/prompts/master-v3.md` (Stages 0-7) builds on the fast track (`docs/prompts/fast-track.md`,
CLAUDE.md section 8) and adds CLAUDE.md section 9 (baseline protection, licensed internet-video
learning, language purity, AI never invents a sign, measured performance budgets).
All work happens on branch **`v3/master`**; `main` is the live website and changes only when the
owner merges the v3 pull request in Stage 7. Stage 0 is done up to its gate (see "Waiting for");
Stage 1 passed its gate (`reports/v3_stage1_web_learn.md`). Stages 2-6 are done with the limits in
`reports/final_v3.md` (PSL v3: `reports/psl_v3.md`; exhibition kit: `docs/EXHIBITION_KIT.md`).
PR #1 (interim release of Stages 0-1) was merged on 2026-11-20, but its website deploy was stopped on the
owner's request ("complete all things then publish it"): the live site is still the old build, and
nobody should press "Run workflow" on `main` until the final release.

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
- Release `inference-baseline-v1` (tag on `42a572f`, asset `SignBridge.zip`, SHA-256 checked) holds
  the zip; made in the owner's browser (this session's GitHub access cannot create releases).
- `baseline/v1-site/` + `baseline/v1-shared/`: the built shared copy of 2026-11-19, byte for byte
  (19 files in git; 47 third-party files restored by `python tools/baseline_v1.py restore
  --download | --zip PATH | --from-sources`, each checked against `baseline/manifest.json`).
- `tests/golden/baseline_v1_outputs.json`: what it produces on the golden fixtures, recorded in
  Chromium by `node tools/baseline/run.mjs --record` (frames, resampling, segments, words, real model
  top-5 for 39 cases). `tests/test_inference_baseline.py` and `web/tests/inference-baseline.test.mjs`
  hold today's code to it; `run_all_tests.py` runs the browser comparison when the baseline is restored.
- A new model replaces it only if better on top-1 on the same set and within the latency budget.

## Current state
- PSL: bundle `models/psl/` (v3.0.0-20261121, int8 1.85 MB, 69 signs + "not a sign", all Tier B,
  "Community dataset — not yet validated"), trained on SignSpeak by `.github/workflows/psl-train.yml`
  (run 44884632047). Fair phone test 98.6 % top-1 (weaker); one independent signer 35.7 % (14 clips).
  Runs in the same LiteRT.js worker code as ASL; never spoken until the person confirms.
- New on the site: PSL dictionary videos (31 offline) and a Dictionary page (788 SLT signs), sentence
  builder, reply panel, quick/emergency phrases, AI helpers switch (camera check, personal adaptation,
  helper), offline service worker, How well it works / Credits / What's new pages from
  `shared_data/site_pages.json` (`tools/site_pages.py`, tested).
- ASL mode: ISLR 1st-place TFLite (250 signs, MIT) — browser (LiteRT.js in a Web Worker, 32 frames)
  and server (ai-edge-litert, native length). On v3 the worker works again (`web/src/wasm_locate.js`);
  on the live `main` build it falls back to the page thread. GISLR rerun set (39,443 signs, Kaggle,
  2026-11-20): top-1 86.2 %, top-5 95.4 % (native); 85.3 % at the browser's 32 frames; left/right gap 4.5
  points (target 3, missed). Spoken aloud only at ≥ 0.70 (1.7 % wrong; 2.8 % at the 0.60 "Pretty sure").
- Stage 1 web learning (`tools/web_learn`, `.github/workflows/web-learn.yml`), runs 44753806707 and
  44767308852 (GitHub Actions, 2026-11-20): 785 of 788 SLT PSL dictionary clips kept (CC BY 4.0, one
  performer), 3 rejected (no hands); 25 / 64 vocabulary entries have a clip (22 in run 1; the 3 added are
  what / when / who, matched once "?" is ignored). Open web: run 1 found 33 videos, none sign language,
  8 wrongly hinted PSL, none downloaded; run 2 found 1, Spanish Sign Language, labels blocked. Ledger check
  of every manifest entry: PASSED. All web-learned signs are Tier B (single source).
- Features v2 (971 values/frame), recording format v2, licence ledger (`data/LICENSES.yaml`, 23 assets,
  `data_engine.ledger.assert_allowed`), vocabulary 64 entries — unchanged since fast-track Stage 2.
- `npm run build:shared` (in `web/`) makes `web/dist-shared/SignBridge-shared-copy.zip`.
- Tests: `python tools/run_all_tests.py [--smoke]`. CI (preview run 44709553244): 180 Python tests
  (2 skipped), licence check, Node v1 + v2 suites, baseline browser comparison — all passed.

## Waiting for (owner [ME])
1. Phone self-test and a camera check with a person signing ASL (`docs/HOW_TO_MEASURE_SPEED.md`).
   (Kaggle run: done. The owner's Kaggle account is not phone-verified: no internet or GPU in notebooks.)
3. Optional before Stage 7: the move to `signbridge-pk.github.io` (`docs/DOMAIN.md`); after it,
   Claude needs repo access again under the new name.

## Open findings
- The open web has almost no licensed PSL video: growth needs permissions from Deaf organisations.
- The SLT dictionary's own word-mapping file was read (593 pairs) but matched 0 vocabulary words; the
  baseline already maps 6 more (father, home, medicine, happy, sad, pain). Fix before the next web run.
- "Pretty sure" (≥ 0.60) was shown for a PSL sign in ASL mode, and for 2 of 39 synthetic inputs: an
  unknown/not-a-sign check is still needed (ASL and PSL, Stage 2). Speaking now needs ≥ 0.70.
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
