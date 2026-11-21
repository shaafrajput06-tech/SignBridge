# SignBridge 3.0 release — live checks (2026-11-21)

- Pull request #2 (v3/master → main) was merged at 94c3acf. Website workflow run 44891975839 succeeded:
  - 228 Python tests;
  - licence check, default and release rules;
  - ASL browser and server self-test: worker true, runtimes agree;
  - PSL dictionary: 31 offline videos, 788 signs listed.
  It deployed to GitHub Pages at 10:00 UTC.
- Live address: https://shaafrajput06-tech.github.io/SignBridge/

## Checked on the live site (fetched from the live address, 2026-11-21)
| Check | Result |
|---|---|
| `/ci/status.json` | commit 94c3acf; tests success, licence release rules success, ASL browser and server check success |
| `/models/psl/manifest.json` | version 3.0.0-20261121, PSL, badge "Community dataset — not yet validated", 0 Tier A / 69 Tier B, 70 classes, model SHA-256 72c71f80…, 1,854,048 bytes |
| `/site_pages.json` (How well it works, Credits, What's new) | 69 PSL signs; fair test 98.6 %; one independent signer 35.7 % (14 clips); ASL 85.3 % in the browser; 785 web-learned videos; 10 credited assets; 6 What's new sections |

## GitHub Release and the live page in the owner's browser (2026-11-21)
- GitHub Release **v3.0.0** "SignBridge 3.0" was published at 10:28 UTC, tag v3.0.0 → 94c3acf (main):
  https://github.com/shaafrajput06-tech/SignBridge/releases/tag/v3.0.0
  - Asset `SignBridge-shared-copy.zip`, 59,203,519 bytes, SHA-256 a4dae669…c5c4f. It is the offline copy
    built and tested by the preview checks of pull request #2 (run 44891334895).
  - The SHA-256 was checked in the browser before the upload.
- The live home page, opened in the Claude desktop app's browser on the owner's laptop:
  - shows "69 PSL signs · suggestions" and the badge "Community dataset — not yet validated";
  - has the nav links Translate / Vocabulary / Dictionary / How well it works;
  - has the footer links "Save for offline use (120 MB)", What's new, Credits & licences, Privacy & help.

## Not checked yet (need a person or a device) [ME]
- Camera on a laptop and on a phone: one PSL sign, one ASL sign, one two-handed sign, one sentence.
- Offline after the first visit, on the live site.
- Lighthouse on the live site (the preview measurements are in `reports/performance_v3.json`).
- The move to signmate-pk.github.io is optional (`docs/DOMAIN.md`); the old address is still the live one.
