# Master v3 Stage 1 handoff — 2026-11-20

## Result
PASS at the gate:
- The report lists real numbers for the first runs.
- Zero clips came from sources the ledger forbids.
- The run's ledger check of every manifest entry printed "Web-learned data check: PASSED" (run 44767308852).

Branch `v3/master`. Reports: `reports/v3_stage1_web_learn.md`, `reports/web_learn_v1.md`.

## What changed
- `tools/web_learn/` does the whole pipeline:
  - word list with English, Urdu and Roman Urdu queries;
  - search: SLT releases, Wikimedia Commons, Internet Archive, and YouTube metadata only;
  - licence rules, with ledger drafts written before any download;
  - fetch and capture v2 extraction;
  - quality and language checks;
  - dedupe and DTW cross-check;
  - manifest and report.
- `ml_engine/recording_v2.py`: new source `licensed_clip` (consent id = ledger id, no video stored).
- `data/licenses.schema.json`: new conditions for no-derivatives, platform terms, unconfirmed language and
  unstated licence version.
- `data_engine/ledger.py` ignores `data/web_learn/*`.
- `.github/workflows/web-learn.yml`: runs the pipeline on GitHub's computers.

## Measured results
| Metric | Run 1 (44753806707) | Run 2 (44767308852) | Report file |
|---|---|---|---|
| Clips kept (SLT PSL dictionary, CC BY 4.0) | 785 | 785 | reports/web_learn_v1.md |
| Clips rejected (no hands in most frames) | 3 | 3 | same |
| Open-web finds (Commons + Archive, 64 words) | 33, none sign language, 8 wrongly hinted PSL | 1, Spanish Sign Language, labels blocked | same |
| Downloaded from the open web | 0 (no ledger entries) | 0 (no ledger entry) | same |
| Vocabulary entries with a usable clip | 22 / 64 | 25 / 64 | same |

All runs were on GitHub Actions, 2026-11-20.

## Coverage
- Tier A: 0.
- Tier B: 785 web-learned dictionary signs (single source).
- Tier C: unchanged.
- Tier D: the rest.

## Data and licences
No new ledger entries were committed. The only drafted entry, for a Spanish Sign Language video, could
never label PSL.

## Not done / not tested
- Language classifier (needs the Stage 2 encoder).
- Cross-check threshold (needs two sources per sign).
- The dictionary mapping file matched 0 vocabulary words (593 pairs read); the baseline maps 6 more words.
- [ME] permission requests to Deaf organisations; optional `YOUTUBE_API_KEY` secret.

## Current state (copy into CONTEXT.md)
- The Stage 1 pipeline works on GitHub Actions.
- The SLT dictionary is the only usable licensed video source so far: 785 clips, 25 of the 64 vocabulary
  entries.

## Open findings (copy into CONTEXT.md)
- The open web has almost no licensed PSL video; growth needs permissions from Deaf organisations.
- Mapping-file matching needs a fix.
