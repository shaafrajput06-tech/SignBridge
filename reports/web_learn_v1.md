# Web-learned signs v1: report

Made by `python -m tools.web_learn` on 2026-11-20 (search on 2026-11-20). Every number below is a
count from this run. No accuracy is claimed here: web-learned signs start as **Tier B** (CLAUDE.md 9.3).

## Words

- Vocabulary entries: 64; dictionary labels: 788; words in the list: 830.
- Searched on the open web (Wikimedia Commons, Internet Archive): 64 vocabulary words.

## Sources

| Source | Found | Licence allows training | Used (passed every check) |
|---|---|---|---|
| commons | 1 | 1 | 0 |
| slt | 788 | 788 | 785 |

YouTube results, when searched, are never downloaded (YouTube's terms); they count as found only.
Search problems: 0.

## Clips

- Kept: 785 (single_source 785).
- Duplicates removed: 0.
- Rejected by the quality or language checks: 3.
  - no hands in most frames: 3
- Not downloaded: 1.
  - no ledger entry web-commons-50567fb253 yet: 1

## Cross-check

Known same-sign pairs from different sources: 0 (different-sign pairs not compared: no threshold possible).
Threshold not chosen: too few known pairs (0 same-sign pairs from different sources; need 5). No clip was accepted by cross-checking; all stay single-source (Tier B).

## Language check

Clips are kept for PSL labels only when their own source says PSL (the SLT PSL dictionary, or a title or
description naming Pakistan Sign Language). The small PSL-vs-other classifier (master-v3 Stage 1, step 6) needs
the Stage 2 encoder and is not trained yet; until then every other clip is dropped from PSL labels.

## Coverage of the 64 vocabulary entries

- With at least one usable clip: 25 (bag, book, close, doctor, emergency, family, friend, good, help, hospital, market, mother, no, play, school, tea, teacher, time, today, tomorrow, wait, welcome, what, when, who).
- Still missing: 39 (bad, call, come, dangerous, drink, eat, excuse_me, father, food, go, goodbye, happy, hello, home, how_are_you, i_am_fine, i_do_not_understand, medicine, money, my_name_is, open, pain, phone, please, read, repeat, sad, sit, sleep, sorry, speak_slowly, stand, stop, thank_you, understand, water, where, write, yes).
- Dictionary signs outside the vocabulary with a usable clip: 760.

Landmarks are in `data/web_learned/v1/` (not committed; the workflow uploads them as an artifact).
