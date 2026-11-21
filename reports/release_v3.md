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
- The move to signmate-pk.github.io was optional at release time; it was done later the same day (below).

## New name and address (2026-11-21)
- The owner renamed the app **SignMate** and chose the address **https://signmate-pk.github.io/**.
- PR #4 (rename) was merged into `main` as d6e0774 after preview run 44896124848 passed on 94b7d26.
- The free organisation `signmate-pk` was created (owner: `shaafrajput06-tech`), and the repository was
  transferred from `shaafrajput06-tech/SignBridge` to `signmate-pk/signmate-pk.github.io` in one step.
  Pages kept its "GitHub Actions" source; the settings page reported "Your site is live at
  https://signmate-pk.github.io/".
- Checked in the owner's browser at the new address: title "SignMate — Hand signs into words",
  "69 PSL signs · suggestions", "Community dataset — not yet validated". One label still said
  "ASK SIGNBRIDGE"; fixed in the follow-up commit.
- The GitHub Release v3.0.0 and its asset moved with the repository (its file is still named
  `SignBridge-shared-copy.zip`; later builds are named `SignMate-shared-copy.zip`).
