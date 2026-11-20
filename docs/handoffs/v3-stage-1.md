# Master v3 Stage 1 handoff — 2026-11-20

## Result
PASS at the gate: the first runs report real numbers, and the ledger check of every manifest entry passed.
Branch `v3/master`. Report: `reports/v3_stage1_web_learn.md`, `reports/web_learn_v1.md`.

## What changed
- `tools/web_learn/`: word list (EN/UR/Roman queries), search (SLT releases, Wikimedia Commons, Internet
  Archive, YouTube metadata only), licence rules, ledger drafts written before any download, fetch +
  capture v2 extraction, quality and language checks, dedupe and DTW cross-check, manifest and report.
- `ml_engine/recording_v2.py`: new source `licensed_clip` (consent id = ledger id, no video stored).
- `data/licenses.schema.json`: conditions for no-derivatives, platform terms, unconfirmed language,
  unstated licence version. `data_engine/ledger.py` ignores `data/web_learn/*`.
- `.github/workflows/web-learn.yml`: runs the pipeline on GitHub's computers.

## Measured results
| Metric | Value | Source | Device | Report file |
|---|---|---|---|---|
| Clips kept | 785 | SLT PSL dictionary (CC BY 4.0) | GitHub Actions | reports/web_learn_v1.md |
| Clips rejected | 3 (no hands in most frames) | same | GitHub Actions | same |
| Licensed sign-language video found on the open web | 1 (Spanish SL, labels blocked) | Commons + Archive, 64 words | GitHub Actions | same |
| Vocabulary entries with a usable clip | 25 / 64 | same | GitHub Actions | same |

## Coverage
Tier A: 0 · Tier B: 785 web-learned dictionary signs (single source) · Tier C: unchanged · Tier D: the rest.

## Data and licences
No new ledger entries committed (the only drafted one, a Spanish Sign Language video, was not needed).

## Not done / not tested
- Language classifier (needs the Stage 2 encoder). Cross-check threshold (needs two sources per sign).
- [ME] permission requests to Deaf organisations; optional `YOUTUBE_API_KEY` secret.

## Current state (copy into CONTEXT.md)
Stage 1 pipeline works on GitHub Actions; the SLT dictionary is the only usable licensed video source so far.

## Open findings (copy into CONTEXT.md)
The open web has almost no licensed PSL video; growth needs permissions from Deaf organisations.
