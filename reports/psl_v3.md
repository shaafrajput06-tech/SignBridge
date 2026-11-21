# PSL recogniser v3 — Stage 2 report (2026-11-21)

Bundle `models/psl/` (version 3.0.0-20261121, int8, 1,854,048 bytes, SHA-256 in the manifest and the ledger
entry `signbridge-psl-model-v3`). It was trained by `.github/workflows/psl-train.yml`, run 44884632047
(commit c34d8ad), on GitHub's CPU runners. The full measurements of that run are in `reports/psl_v3_run.md`
and `reports/psl_v3_measurements.json`.

## Data
- SignSpeak (`psl-signspeak-words`, Apache-2.0): hand landmarks only, 126 values per frame.
  - Both Hugging Face archives were read at revision 1ba8b9fc. That gave 6,818 usable samples of
    70 classes (69 signs and "not a sign"): laptop 3,309, phone 2,308, webcam 1,201.
  - 4,360 exact duplicates between the two archives were dropped, and the authors' test folders were
    removed.
  - Hand order was checked: in 3,734 one-handed samples the second block leads, against 11 for the
    first. Camera shape was estimated from palm rigidity: about 4:3 for every folder.
- No signer ids are published, so **no test can be signer-independent**.

## Results (measured in run 44884632047)
| Test | Samples | Top-1 | Top-5 |
|---|---|---|---|
| Phone recordings never seen in training (fair test: signs with computer-camera training recordings and no label conflict) — *weaker* | 2,151 | 98.6 % | 99.7 % |
| All phone recordings, including signs this protocol cannot learn | 2,308 | 91.8 % | — |
| One-handed / two-handed (fair test) | 1,379 / 763 | 98.8 % / 99.0 % | — |
| Left-handed (mirrored) vs right-handed (fair test, no mirror averaging) | 2,151 | 98.7 % vs 98.6 % | — |
| GRU baseline (fair test) | 2,151 | 94.0 % | 99.3 % |
| **One independent signer** (SLT dictionary performer, absent from SignSpeak; 14 clips of the same words) | 14 | **35.7 %** | **71.4 %** |
| Calibration part (same sessions) — *weaker* | 669 | 99.6 % | 100.0 % |

- Calibration error on the fair test: 0.004.
- When top-1 ≥ 0.7, 98.7 % of the signs are answered and 0.8 % of those answers are wrong.
- Personal adaptation (20 confirmations, simulated with phone recordings): 98.6 % → 98.6 %. No
  measurable gain, because there is almost no room left on this test.
- Python CPU: 1.39 ms per sign.
- Browser (LiteRT.js, worker, headless Chromium 153 in Claude's workspace): 6/6 parity cases have
  the same top-1 as Python; median 14.4 ms.

## What the numbers mean
- On new recordings of the same dataset, the model is very accurate.
- On one new signer from a different dictionary, it is right about a third of the time. The miss rate
  may come partly from regional variants of the signs, but it also shows how much the model depends on
  the SignSpeak signers. This is why every sign is **Tier B**: a suggestion the person confirms. It is
  also why the app never speaks a PSL answer by itself.

## Decisions
- **Label conflict:** the phone recordings of toothbrush and toothpaste are labelled the other way round
  from the computer-camera ones. The held-out model gave 32 and 29 answers the other way round in
  run 44778328389. Which side is right cannot be known from the data. The 63 phone recordings were left
  out of the shipped model and of the fair test, and both signs carry a data note.
- **Signs with phone recordings only** (come, give, want) are in the shipped model, but they are
  marked "not measured".
- The shipped temperature (0.55) was fitted on the fair test's predictions of the same recipe, not on
  the same-session calibration part.
- int8 was chosen: it lost 0 points against Keras on the calibration part, and its top-1 matched
  Keras on 100 % of signs.

## Stage 2 gate (master-v3)
| Part | Result |
|---|---|
| PSL top-1 ≥ 90 % signer-independent on Tier A signs | **Not met**: no signer ids. No sign is Tier A; all 69 are Tier B. |
| One- and two-handed reported separately | Met |
| Left/right gap ≤ 3 points | Met (0.1 points on the fair test) |
| Bundle loads in web and Python with the same top-1 | Web: met (6/6, headless Chromium). Python: test in `tests/test_psl_bundle.py` (runs where ai-edge-litert is installed). Flutter: **not done**; the Flutter app has no model runtime yet. |
| Calibration error ≤ 0.05 | Met on the fair test (0.004) |

Not done in Stage 2: pretraining on other datasets, PkSLMNM (7.47 GB RAR), finger-spelling (UAlpha40
converter written, model not trained), a test on new signers, Deaf validation.
