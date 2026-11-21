# Master v3 Stages 2-6 handoff — 2026-11-21

## Result
- Stage 2: done with the gate partly met.
  - Met: one- and two-handed accuracy reported separately, left/right gap, calibration, web parity.
  - Not met: there is no signer-independent test (the dataset has no signer ids), so no sign is Tier A.
  - Not done: Flutter loading.
- Stages 3-6: done, except finger-spelling and continuous recognition.
- The full list is in `reports/final_v3.md`.

## What changed
- PSL bundle:
  - `models/psl/` (ledger entry `signbridge-psl-model-v3`);
  - `tools/psl_data/signspeak.py`, `tools/psl_train/`, `.github/workflows/psl-train.yml`,
    `.github/workflows/bundle-fetch.yml`;
  - `ml_engine/psl_hands.py`, `ml_engine/psl_model.py`, `web/src/psl_hands.js`, `web/src/psl_client.js`.
- Web:
  - PSL suggestion card;
  - dictionary videos and the Dictionary page;
  - sentence builder, reply panel, quick and emergency phrases;
  - offline helper, camera check, personal adaptation, AI helpers switch;
  - service worker and offline save;
  - How well it works, Credits and What's new pages.
- Reports:
  - `reports/psl_v3.md`, `reports/psl_v3_run.md`, `reports/performance_v3.json`, `reports/final_v3.md`;
  - `docs/EXHIBITION_KIT.md`, `docs/WHATS_NEW.md`.

## Measured results
See `reports/psl_v3.md` and `reports/final_v3.md`. Every row names its dataset, split, device and date.

## Not done / not tested
- Finger-spelling: the UAlpha40 converter is written, but no model.
- Continuous signing.
- Flutter runtime.
- The owner's laptop/phone speed with v3.
- A camera test with a person signing PSL.
- Deaf validation.

## Needs the owner [ME]
- Attach the offline zip to the GitHub Release v3.0.0 (this session cannot create releases).
- Optionally, move the site to signbridge-pk.github.io (`docs/DOMAIN.md`).
- Try three PSL signs on the live site with a laptop camera and a phone.
