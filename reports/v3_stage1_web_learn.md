# Master v3 Stage 1: web-video learning pipeline — results (2026-11-20)

Status: **gate passed** (real numbers from the first runs; a test checks every manifest entry against the
licence ledger, and the check step passed in both runs). Pipeline: `tools/web_learn/`, workflow
`.github/workflows/web-learn.yml`, full report `reports/web_learn_v1.md`.

## Runs

| Run | Commit | What changed | Words | Clips kept | Rejected | Web finds | Sign-language web finds | Vocabulary covered |
|---|---|---|---|---|---|---|---|---|
| 44753806707 (GitHub Actions, 2026-11-20) | first run | — | 830 | 785 (SLT dictionary) | 3 (no hands in most frames) | 33 | 0 | 22 / 64 |
| 44767308852 (GitHub Actions, 2026-11-20) | 2nd run | dictionary mapping file used; strict PSL and sign-language filters | 830 | 785 (SLT dictionary) | 3 (no hands in most frames) | 1 | 1 (Spanish Sign Language) | 25 / 64 |

All numbers are counts read from the runs' logs and artifacts (`web-learn-metadata-v1`, `web-learned-v1`).

## Findings

- **The open web has almost no licensed PSL video.** Wikimedia Commons and the Internet Archive returned 33
  results for the 64 vocabulary words in the first run; none showed sign language. Eight were wrongly
  hinted as PSL by the first, loose rules (the "PSL" political party, Persian script). Those drafts were not
  committed; the rules were tightened (sign-language relevance filter, strict PSL patterns) and the tests
  updated. With the strict rules the second run found one sign-language video, correctly classed as
  Spanish Sign Language: its labels are blocked from PSL (`train_labels: false`), and it was not downloaded
  because its ledger entry was not committed (licence gate before download).
- **YouTube** search needs a `YOUTUBE_API_KEY` secret (not set) and is metadata-only even then: YouTube's terms
  forbid downloading, so YouTube clips are never used for training.
- **The SLT PSL dictionary is the usable source**: 785 of 788 clips passed the quality checks (one performer,
  one clip per sign, CC BY 4.0). The dictionary mapping file lifted vocabulary coverage from 22 to 25.
- **Cross-checking (two independent sources) is not possible yet**: 0 known same-sign pairs from different
  sources, so no threshold could be chosen; every web-learned sign stays single-source Tier B, as CLAUDE.md
  9.3 requires.
- **Language classifier** (step 6) needs the Stage 2 encoder; until it exists, only clips whose own source says
  PSL keep PSL labels. Everything else is dropped from labels.

## Still missing for the 64 vocabulary entries

39 entries have no usable licensed clip yet (list in `reports/web_learn_v1.md`). The Stage 2 SignSpeak
dataset covers some of them (hello, goodbye, thank you, excuse me, water, phone) with many samples each.

## Next steps

1. Permission requests to FESF/psl.org.pk and other Deaf organisations (`docs/permission_requests.md`, [ME]).
2. A YouTube API key secret if the owner wants Creative-Commons YouTube metadata searched (still no downloads).
3. Use the SLT clips as an independent-signer test and as extra training data in Stage 2 (one performer
   who is not a SignSpeak signer).
