# ASL mode v1: report (fast track Stage 2)

Status: **draft, gate not passed yet.** Update 2026-11-20: see "Update (master v3, Stage 0)" at the
end; the Kaggle numbers and the owner's device numbers are still pending. Everything that can be built and checked without the owner's
laptop and a Kaggle run is done and tested. The measured numbers below say "pending" until those two
runs report back; none is estimated.

ASL is a separate language mode (CLAUDE.md 8.2). Nothing in it is, or is shown as, Pakistan Sign
Language.

## What ASL mode is

| | |
|---|---|
| Model | 1st place of Google's Isolated Sign Language Recognition competition (Hoyeol Sohn), from Hugging Face `sign/kaggle-asl-signs-1st-place`, MIT licence |
| File | `models/asl/model.tflite`, 11,242,036 bytes, SHA-256 `f55a2bb1…f0bb7` (downloaded once, refused if different) |
| Classes | 250 ASL signs (`models/asl/sign_to_prediction_index_map.json`, SHA-256 `1fe747c2…0bf5d`) |
| Training data | the competition corpus, 21 Deaf signers recruited by DPAN, CC BY 4.0 (not shipped) |
| Input | frames × 543 × 3 landmarks (face 468, left hand 21, pose 33, right hand 21; NaN where missing), any number of frames |
| Output | 250 scores; the app shows the top result in plain words |
| Training by the user | none |

Read from the model file itself (2026-11-18): one signature, `serving_default`, with input `inputs`
of shape `[-1, 543, 3]` (float32) and output `outputs` of shape `[250]`. It has 1,408 operators of
32 built-in kinds and no custom operators. The model does its own preprocessing, including two
conditional branches that pad short clips.

## How it runs

```
camera ─▶ capture v2 (both hands + pose + face, MediaPipe) ─▶ raw landmarks
        ─▶ islr_frame: 543 x 3 per frame, hands in anatomical slots (pose wrists decide)
        ─▶ SignSegmenter: a sign = frames with a hand, ended by 8 frames without one
        ─▶ model ─▶ top 5 ─▶ "Pretty sure" / "Not sure. Is it one of these?" / "I'm not sure. Try once more."
```

Two runtimes, chosen automatically (local server first, then the browser):

| Runtime | Where | Frames given to the model | Status |
|---|---|---|---|
| ai-edge-litert (Google's TFLite runtime for Python) | the SignBridge server on the same computer (`/api/asl/predict`, landmarks only) | the sign's real length, as the model was built | code and tests done; **not run yet** (needs the laptop) |
| LiteRT.js 2.6.0 (WebAssembly) in a Web Worker | the browser, no server needed | resampled to 32 frames (nearest frame); the model file's input is rewritten to 32 × 543 × 3 before compiling, because LiteRT.js cannot take a variable frame count | code and tests done; **not run yet** (needs the laptop) |

## Checks done here

| Check | Result | Produced by |
|---|---|---|
| Python and JavaScript adapters give identical frames | 26 of 26 unmirrored fixture frames identical; 26 mirrored frames refused by both | `tests/test_asl_islr.py::JavaScriptParityTests` |
| Resampling identical in Python and JavaScript | 84 of 84 cases | same test |
| Segmenter identical in Python and JavaScript | 13 of 13 hand-presence streams | same test |
| Our 543-row layout equals the competition's reference reshape | identical (values and NaN positions) on 9 synthetic frames | `tests/test_asl_islr.py::FrameTests::test_layout_matches_the_competition_reference_reshape` |
| Model-file patch changes only the input's frame dimension | 8 bytes or fewer change; other models refused | `web/tests/asl-islr.test.mjs` (hand-built flatbuffer) |
| Recogniser refuses a missing file, a wrong hash, a ledger refusal | refused, with the fix in the message | `tests/test_asl_islr.py::RecognizerGuardTests` |
| Downloads refuse a file of the wrong size or SHA-256 | refused, nothing saved | `tests/test_downloads.py` |
| Licence ledger allows these uses | `asl-islr-1st-place-tflite`: ship weights, ASL labels only; ASL labels can never train a PSL model | `tests/test_licence_ledger.py` |
| Evaluation notebook | every cell executed with a stand-in model and data; results file written | `tests/test_asl_eval.py` |

Full suite in this workspace: 157 Python tests (4 skipped: server tests need FastAPI, speech needs
pygame, the real-model test needs the model and a TFLite runtime), licence check passed, Node v2 tests
passed.

## Measured results

| Metric | Value | Dataset / split / signers | Device | Source |
|---|---|---|---|---|
| Top-1 accuracy, native length (server path) | **86.2 %** (39,443 signs, 0 unreadable) | GISLR rerun set (CC0), 250 signs; signers reported absent from training by the dataset's publisher (the label file has no signer ids, so this could not be re-checked) | Kaggle CPU, tensorflow 2.21, 2026-11-20 | `reports/asl_eval_results_2026-11-20.json` |
| Top-5 accuracy, native length | **95.4 %** | same | Kaggle CPU, tensorflow 2.21, 2026-11-20 | `reports/asl_eval_results_2026-11-20.json` |
| Top-1 at 16 / 24 / 32 / 48 / 64 frames (browser path) | 84.2 / 85.0 / **85.3** / 85.0 / 84.6 % (native on the same 7,889 signs: 86.1 %) | every 5th sample of the same set | Kaggle CPU, tensorflow 2.21, 2026-11-20 | `reports/asl_eval_results_2026-11-20.json` |
| One-handed vs two-handed top-1 | 86.2 % (39,432 signs) vs 18.2 % (**11 signs only**: too few to mean anything; GISLR signs almost never show both hands in most frames) | same | Kaggle CPU, tensorflow 2.21, 2026-11-20 | `reports/asl_eval_results_2026-11-20.json` |
| Left- vs right-dominant top-1 | 89.1 % (13,609) vs 84.6 % (25,834): a **4.5-point gap**, over the 3-point target | same | Kaggle CPU, tensorflow 2.21, 2026-11-20 | `reports/asl_eval_results_2026-11-20.json` |
| Accuracy above the "Pretty sure" threshold | at 0.60: 97.2 % right, covering 76.6 % of signs (2.8 % wrong); at 0.70: 98.3 % (71.1 %, 1.7 % wrong); at 0.80: 99.0 % (64.2 %) | same | Kaggle CPU, tensorflow 2.21, 2026-11-20 | `reports/asl_eval_results_2026-11-20.json` |
| Hand-slot convention (assumed anatomical) | **confirmed**: the right-hand slot sits at the pose's right wrist in 99.85 % of 679,537 frames, and left of the nose in the (unmirrored) image in 99.52 % | same | Kaggle CPU, tensorflow 2.21, 2026-11-20 | `reports/asl_eval_results_2026-11-20.json` |
| Browser runtime loads and runs; latency per sign | pending | made-up landmark sequences (no accuracy meaning) | the owner's laptop | `web/asl-selftest.html` |
| Browser vs server output on identical input | pending | same | the owner's laptop | same |
| Camera → ASL word on screen | pending | a person signing | the owner's laptop | manual check |

## Known limits

- Signer-independent accuracy comes from the rerun set; whether its signers are absent from training
  is reported by a third party and checked by the notebook only if the competition's `train.csv` is
  attached.
- The browser path changes each sign's length to a fixed number of frames. The notebook measures what
  that costs. If the cost is large, the server path stays the default on the laptop.
- The model was trained on landmarks from MediaPipe Holistic 0.9 on phone selfie video. SignBridge uses
  newer MediaPipe Pose, Hand and Face models on a laptop camera. Accuracy with live signing in front
  of a laptop can differ from the rerun-set number.
- Mirrored camera input is refused (no mirror map for the full face mesh). Browsers give unmirrored
  frames; only the display is mirrored.
- ASL fingerspelling is not included (no published weights).
- The phone app does not have ASL mode until Stage 6 (on-device capture).

## Update (master v3, Stage 0, 2026-11-20)

Full details and sources: `reports/v3_stage0_baseline.md`.

| Row above | Now |
|---|---|
| Browser runtime loads and runs; latency per sign | Runs, in the Web Worker. Median per sign (32 frames, synthetic): 12.8 ms in this workspace (headless Chrome 153, 2 cores, frozen baseline build); 9.8-16.3 ms in GitHub Actions (HeadlessChrome 159, 4 cores, v3 preview build). The owner's laptop and phone: **pending**. |
| Browser vs server output on identical input | Same top-1 on 3 of 3 self-test signs, largest probability difference 1.9e-8 (GitHub Actions, preview run 44709553244). |
| Camera → ASL word on screen | The plumbing works end to end (fake camera, baseline build); a person signing ASL: **pending**. |
| All Kaggle rows | **Filled in** from the run of 2026-11-20 (Kaggle notebook version 2, model SHA-256 f55a2bb1…f0bb7), see the table above and `reports/asl_eval_results_2026-11-20.json`. Server-path latency there: median 10.9 ms, p90 20.1 ms per sign (Kaggle CPU, tensorflow). |

New finding: on the live build the model ran on the page thread, not in the worker (fixed on
`v3/master`, `web/src/wasm_locate.js`). And "Pretty sure" was shown for a PSL sign the ASL model
cannot know, so the 0.60 threshold alone does not stop wrong words being spoken; it will be set from
the Kaggle calibration table.

### Decisions taken from the Kaggle numbers (2026-11-20)

- **Browser frame count stays 32.** It is the most accurate of 16/24/32/48/64 (85.3 %, 0.8 points below native
  length on the same signs). The rule fixed before the run ("smallest within 0.5 points of native, otherwise the
  largest within the latency budget") assumed accuracy grows with frames; it does not (48 and 64 are worse), and no
  length came within 0.5 points, so the most accurate length was kept. The server path (native length) stays the
  default wherever the local server runs.
- **Spoken aloud only at 0.70 or more** (`confidence.speak_at`): at 0.60, 2.8 % of "Pretty sure" answers were
  wrong, more than the 2 % master-v3 allows to be spoken; at 0.70, 1.7 %. What the screen shows is unchanged
  (the baseline's words and thresholds), so the frozen baseline outputs still match.
- **Missed targets, with next steps:** left/right gap 4.5 points (target ≤ 3): try averaging the prediction on the
  original and the mirrored sign (test-time mirroring) in the next notebook run. Two-handed accuracy cannot be
  judged on GISLR (11 signs); it will be measured on PSL data in Stage 2. Out-of-vocabulary input (a PSL sign)
  was still shown as "Pretty sure"; an unknown/not-a-sign check is planned with Stage 2.
