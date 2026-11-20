# Inference Baseline v1 (frozen, read-only)

This folder is the reference every new model or pipeline change in SignBridge is measured against
(`docs/prompts/master-v3.md` section 0, `CLAUDE.md` section 9.1). **Never edit these files.** A test
(`tests/test_inference_baseline.py`) fails if any of them changes.

## What it is

The built "shared copy" of the SignBridge website, a Vite build of 2026-11-19 that runs fully in the
browser (`SignBridge.zip`, SHA-256 `c1612538…a0f0d4`, 57,784,700 bytes).

```
camera ─▶ capture v2 (MediaPipe tasks-vision WASM: Pose Landmarker lite + Hand Landmarker ×2 + Face Landmarker)
       ─▶ islr_frame(): 543 × 3 per frame [face 468 | left hand 21 | pose 33 | right hand 21], NaN = missing,
          hands in anatomical slots decided by pose wrists, unmirrored coordinates
       ─▶ SignSegmenter (min_hand_frames 6, end_after_missing_frames 8, margin 2, max 192)
       ─▶ nearest-frame resample to 32 frames (browser path)
       ─▶ ASL ISLR 1st-place TFLite (250 signs, MIT, SHA-256 f55a2bb1…f0bb7) on LiteRT.js 2.6.0 in a Web Worker
       ─▶ top-5 ─▶ "Pretty sure" (≥ 0.60) / "Not sure, is it one of these?" (≥ 0.25) / "Try once more"
```

| Path | In git? | What |
|---|---|---|
| `v1-site/` HTML, JavaScript, CSS, JSON | yes | the files SignBridge built |
| `v1-shared/` | yes | `Start SignBridge.bat`, `serve.ps1`, `README.txt` of the shared copy |
| `manifest.json` | yes | all 66 files with size and SHA-256 |
| `v1-site/litert/`, `v1-site/wasm/`, `v1-site/models/*.task`, `v1-site/models/asl/model.tflite`, `v1-site/clips/` | no | third-party runtimes, models and CC BY 4.0 clips, restored from the zip |
| `../tests/golden/baseline_v1_outputs.json` | yes | what the baseline produces on the golden fixtures, including the real model's top-5 |

The zip is kept as the asset of the GitHub release
[`inference-baseline-v1`](https://github.com/shaafrajput06-tech/SignBridge/releases/tag/inference-baseline-v1),
and the git tag `inference-baseline-v1` marks the source commit that was live when it was frozen.

## Restore and run it

```
python tools/baseline_v1.py restore --download        # or: restore --zip path\to\SignBridge.zip
python tools/baseline_v1.py status                    # 66 of 66 files present and correct
python -m http.server 8766 --directory baseline/v1-site
```

Then open <http://localhost:8766/> (the app) or <http://localhost:8766/asl-selftest.html> (ASL self-test).

## Side-by-side rule

A new model or pipeline replaces this baseline as the default only when, on the same evaluation set, it
is better on top-1 **and** within the latency budget (master-v3.md section 5). Otherwise the baseline
stays the default and the new one is opt-in. The 543-point layout, the segmenter, the confidence words
and the Python ↔ JavaScript parity tests stay; new models may add inputs, never silently change these.

## Known gap: source code

This build contains work that is not in the git history (an importScripts shim plus a `locateFile`
fix that let LiteRT.js run inside the module worker, 10 colour themes, "Test signs" cards and "How to
sign" clips). Its source was not available when the baseline was frozen. The worker fix is re-applied
from the built code in v3 Stage 0 (`reports/v3_stage0_baseline.md`); the rest waits for the source
folder from the owner's computer.
