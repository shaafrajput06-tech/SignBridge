# SignBridge v3 — final report (2026-11-21)

Every number below comes from a committed report, named in the last column. "Weaker" means the test may
include people the model learned from.

## Models: baseline vs new, on the same sets
| Model | Test set | Split | Device / runner | Date | Top-1 | Top-5 | Source |
|---|---|---|---|---|---|---|---|
| ASL baseline (Inference Baseline v1, ISLR 1st place, kept unchanged) | GISLR rerun set, 39,443 signs | signers not in training (publisher's statement) | Kaggle CPU, 32 frames as in the browser | 2026-11-20 | 85.3 % (86.2 % full length) | 95.4 % (full length) | reports/asl_eval_results_2026-11-20.json |
| PSL: none in the baseline ("not installed") | — | — | — | — | — | — | baseline/ |
| PSL v3 (new) | SignSpeak phone recordings, 2,151 (fair test) | new recordings, *weaker* (no signer ids) | GitHub Actions | 2026-11-21 | 98.6 % | 99.7 % | reports/psl_v3_run.md |
| PSL v3 | SLT dictionary performer, 14 clips | one signer absent from training | GitHub Actions | 2026-11-21 | 35.7 % | 71.4 % | reports/psl_v3_run.md |
| PSL GRU (comparison) | same 2,151 | *weaker* | GitHub Actions | 2026-11-21 | 94.0 % | 99.3 % | reports/psl_v3_run.md |

The ASL model is the protected baseline (CLAUDE.md 9.1). Its outputs still match the recorded golden
outputs: 39 of 39 model cases in the browser, 0 differences. That comparison runs in
`tools/run_all_tests.py`.

## Coverage per tier
| Tier | PSL signs | Notes |
|---|---|---|
| A "Recognised" | 0 | Needs a signer-independent test and, for the badge, a Deaf validator |
| B "Suggested — please confirm" | 69 camera signs + 785 dictionary signs learned from licensed videos | 785 SLT dictionary signs have videos on the Dictionary page; the camera does not recognise them |
| C Personal | optional, local server only | unchanged |
| D Vocabulary only | the vocabulary phrases the camera does not suggest | 64 phrases in total |

Badge on every PSL sign: "Community dataset — not yet validated".

## Learning from licensed internet videos (Stage 1)
- 785 of 788 SLT dictionary videos were kept (CC BY 4.0); 3 were rejected because the hands were not
  visible.
- 25 of the 64 vocabulary entries have a video.
- Open web: 33 finds in run 1, none of them sign language. Run 2 found 1, in Spanish Sign Language, with
  its labels blocked. Nothing was downloaded without a ledger entry.
- Source: `reports/v3_stage1_web_learn.md`, `reports/web_learn_v1.md`.

## Performance
Source: `reports/performance_v3.json`.
| What | Result | Where | Date |
|---|---|---|---|
| PSL model, one sign, browser worker | median 14.4 ms | headless Chromium 153, 2 cores (Claude's workspace) | 2026-11-21 |
| ASL model, one sign, v3 build, worker | 9.8–16.3 ms | GitHub Actions, HeadlessChrome 159 | 2026-11-20 |
| ASL model, old live build, page thread | 46.9–51.8 ms | owner's laptop, Chromium 156 | 2026-11-20 |
| Lighthouse mobile | performance 90, accessibility 100, best practices 96, LCP 3.0 s | GitHub Actions, Lighthouse 12.8.2 | 2026-11-21 |
| Lighthouse desktop | accessibility 100, best practices 96, FCP 0.52 s, no LCP reported | same | 2026-11-21 |

Budgets missed or not measured:
- Mobile LCP of 2.5 s was missed (3.0 s).
- Best practices 100 was missed (96). The remaining finding was console 404s before the PSL bundle was
  committed; this needs re-measuring after release.
- The owner's laptop and phone have not been measured with v3.

## What the release contains (master-v3 Stage 7, list A)
| Item | State |
|---|---|
| PSL recogniser with tiers and the "not yet validated" badge | done (Tier B only) |
| ASL mode, labelled ASL | done (baseline kept) |
| Urdu and English finger-spelling | **not done** (UAlpha40 converter written; model not trained) |
| Continuous signing → sentence with raw glosses | partial: one sign at a time, then a sentence by rules, with the glosses shown underneath |
| Text/speech → PSL clips, conversation view, quick and emergency phrases | done (word-by-word aid) |
| AI autopilot behind a switch (camera check, personal adaptation, sentence builder, helper) | done |
| Full vocabulary + dictionary of the Stage 1 signs with their videos | done (788 dictionary signs) |
| Exhibition mode and kit | done (`docs/EXHIBITION_KIT.md`) |
| How well it works / Credits and licences / What's new pages, generated from the reports | done, with a test |
| Offline zip on GitHub Release v3.0.0 | needs the owner's browser [ME] |
| Move to signmate-pk.github.io | optional, needs the owner [ME] (`docs/DOMAIN.md`) |

## Known problems
- No test on new signers. The one independent signer scored 35.7 % top-1.
- The SignSpeak phone recordings of toothbrush and toothpaste disagree with its other recordings.
- The PSL model reads hands only.
- No Flutter model runtime.
- The dictionary's word-mapping file matched no vocabulary word (Stage 1).
