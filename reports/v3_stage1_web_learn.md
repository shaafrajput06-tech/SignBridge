# Master v3 Stage 1: web-video learning pipeline — results (2026-11-20)

Status: **gate passed.** The report lists real numbers from the first runs. Zero clips came from sources the
ledger forbids. The run's ledger check (`python -m tools.web_learn check`, which checks every manifest entry
against `data/LICENSES.yaml`) printed "Web-learned data check: PASSED" in run 44767308852.
Pipeline: `tools/web_learn/`. Workflow: `.github/workflows/web-learn.yml`. Full report of the latest run:
`reports/web_learn_v1.md`.

## Runs

| Run (GitHub Actions, 2026-11-20) | Commit | What changed | Words | Clips kept | Rejected | Web finds | Sign-language web finds | Vocabulary covered |
|---|---|---|---|---|---|---|---|---|
| 44753806707 | 75f5f75 | first run | 830 | 785 (SLT dictionary) | 3 (no hands in most frames) | 33 (31 Commons, 2 Archive) | 0 | 22 / 64 |
| 44767308852 | 4fca89b | strict sign-language and PSL filters; dictionary mapping file read; punctuation ignored when matching | 830 | 785 (SLT dictionary) | 3 (no hands in most frames) | 1 (Commons) | 1 (Spanish Sign Language) | 25 / 64 |

All numbers are counts read from the two runs' logs (report between `===REPORT-BEGIN===` and `===REPORT-END===`,
search-step lines, ledger drafts).

## Findings

- **The open web has almost no licensed PSL video.** In the first run, Wikimedia Commons and the Internet
  Archive returned 33 results for the 64 vocabulary words. None of them showed sign language. The first,
  loose rules wrongly hinted 8 of them as PSL: videos about the "PSL" political parties (US and Brazil) and
  Persian-script videos. The licence gate held: none of the 33 was downloaded, because no ledger entry
  had been committed for them. Their drafts were not committed. The rules were tightened (a sign-language
  relevance filter, strict PSL patterns) and the tests were updated.
- **With the strict rules**, the second run found one sign-language video: "WIKITONGUES- Mónica signing
  Spanish Sign Language" (Wikimedia Commons, CC BY-SA 4.0). It was correctly classed as another sign
  language: `train_labels: false`, so it can never label PSL. It was not downloaded, because its ledger
  entry was not committed. No candidate file is committed (`data/web_learn/candidates_v1.json`): this one
  candidate cannot label PSL. It is recorded here instead.
- **YouTube** search needs a `YOUTUBE_API_KEY` secret, which is not set. Even with a key, YouTube is
  metadata-only: its terms forbid downloading, so YouTube clips are never used for training.
- **The SLT PSL dictionary is the usable source.** 785 of its 788 clips passed the quality checks. It has
  one performer and one clip per sign, under CC BY 4.0.
- **Vocabulary coverage 22 → 25 comes from punctuation, not from the mapping file.** All 25 search-step
  lines read "dictionary label … equals the word …". The 3 added words (what, when, who) are written
  "What?", "When?" and "Who?" in the vocabulary. The dictionary's own word-mapping file was read
  (593 pairs) but matched **no** vocabulary word. That needs fixing: Inference Baseline v1 already shows
  dictionary videos for 6 more vocabulary words through its own mapping (father, home, medicine, happy,
  sad, pain), so a working mapping should reach at least 31. Those 31 videos are on the website already
  (`shared_data/psl_clips.json`).
- **Cross-checking (two independent sources) is not possible yet.** There are 0 known same-sign pairs from
  different sources, so no threshold could be chosen. Every web-learned sign stays single-source Tier B,
  as CLAUDE.md 9.3 requires.
- **The language classifier** (step 6) needs the Stage 2 encoder. Until it exists, only clips whose own source
  says PSL keep PSL labels; every other clip is dropped from labels.

## Still missing for the 64 vocabulary entries

39 entries have no usable licensed clip from this pipeline yet (list in `reports/web_learn_v1.md`). The
Stage 2 SignSpeak dataset covers some of them with many samples each: hello, goodbye, thank you, excuse
me, water and phone.

## Next steps

1. Fix the mapping-file match (expect at least the 6 words the baseline already maps).
2. Permission requests to FESF/psl.org.pk and other Deaf organisations ([ME], drafts in
   `docs/permission_requests.md`).
3. A `YOUTUBE_API_KEY` secret, if the owner wants Creative Commons YouTube metadata searched (still no
   downloads).
4. Use the SLT clips as a test with one independent signer in Stage 2 (one performer who is not a
   SignSpeak signer).
