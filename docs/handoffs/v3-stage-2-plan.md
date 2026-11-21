# Master v3 Stage 2: plan and facts found so far (2026-11-20)

Stage 2 trains the first PSL recogniser. This file records what the licensed data really looks like
(measured by `tools/psl_data/discover.py` on GitHub Actions, run e91912e), so the converters and the model
are built on facts, not guesses.

## Where training runs

GitHub Actions (CPU, no clicks for the owner). The owner's Kaggle account is not phone-verified (no
internet, no GPU in notebooks); Colab is the fallback if CPU time is not enough. Data never enters git:
workflows download, convert, train and upload the model bundle as an artifact; the bundle (weights +
manifest with SHA-256) is committed only if small and licensed for redistribution (SignSpeak is Apache-2.0,
SLT dictionary CC BY 4.0: both allow shipping weights).

## Data, as measured

### SignSpeak (`psl-signspeak-words`, Apache-2.0) - the main multi-sample source
- Hugging Face `mohibkhansherwani/DynamicWordLevelPakistanSignLanguageDataset` (repo sha 1ba8b9fc...):
  `PakistanSignLanguageDataset.zip` (158,784,931 bytes) and `PakistanSignLanguageDatasetV2.zip`
  (not opened yet), `README.md`, `links_to_words.txt`.
- Layout: `MP_Data/<word>/<sample>/<frame>.npy` (webcam / desktop) and `MP_Data_mobile/...` (phone).
  Each frame: float64 (126,) = two hands x 21 points x (x, y, z).
- V1 zip: 65 word folders, 4,399 sample folders (MP_Data 3,155, at most 50 per word; mobile 1,244, at most
  20 per word). Junk folders to drop: `left_hand`, `nothing`, `s`, `test_word`. Some samples are
  incomplete (1-27 frames instead of 60): keep only full 60-frame samples.
- Hand order: in a one-handed sample (`mine`) only the second 63-value block is filled, x between 0.47 and
  0.60 - consistent with [left hand | right hand] from MediaPipe Holistic on an unmirrored camera, the
  second block being the signer's right hand. To verify on more samples before training (count which block
  is filled for one-handed words); mirror augmentation covers left-handed signers either way.
- Labels: the signers copied the psl.org.pk (FESF) dictionary videos (`links_to_words.txt` links every
  word). Not validated by Deaf signers: UI must say "Community dataset - not yet validated".
- No signer ids. Split: train on `MP_Data`, test on `MP_Data_mobile` (different devices and sessions):
  report it as "device-independent (weaker): signer overlap unknown".
- Words relevant to the app vocabulary in V1: hello, thankyou (thank_you), goodbye, excuseme (excuse_me),
  water, mobile_phone (phone), you, we. V2 may add welcome, come here, good night and others.

### Others
- SLT dictionary (`psl-slt-dictionary`, CC BY 4.0): 785 usable clips, one performer, one clip per sign
  (Stage 1 run 44753806707): prototypes only (Tier B), and a source of PSL pretraining data.
- PkSLMNM (`psl-pkslmnm`, CC BY 4.0): a single `PkSLMNM.rar`, 7,469,741,224 bytes (needs unrar and about
  16 GB of disk on the runner; videos -> capture v2). 7 adjectives with facial expressions.
- Expression hands (`psl-expression-hands`, CC BY 4.0): `Hand Gestures Dataset.rar`, 3,451,683 bytes.
- UAlpha40 (`psl-ualpha40`, CC BY 4.0): the Mendeley root folder listed 0 files - its files sit in
  sub-folders; list them by folder id next.
- WLPSL (`psl-wlpsl-naeem`): evaluation only (non-commercial), 12 people - the best signer-independent
  check of the dictionary prototypes, if it can be downloaded without the owner's Kaggle key.

## Model

- Input: a "hands view" every source can fill - 2 hands x 21 points x 3, resampled to 32 frames,
  normalised per sample (wrist-relative shapes + hand positions relative to the sequence's own centre and
  scale), with masks for missing hands. The full 543-point baseline layout stays for ASL; PSL is a separate
  bundle with its own spec (`shared_data/psl_hands_spec.json`) and parity tests in Python and JS.
- Architecture: the ISLR recipe scaled down (1D depthwise conv + 2 transformer blocks), compared with a
  GRU; augmentation: speed, temporal crop, rotation, scale, shift, mirroring, hand dropout; label
  smoothing; an "unknown / not a sign" class from SignSpeak's `nothing` folder and SLT signs outside the
  class list; temperature calibration on a held-out part of the training devices.
- Export: TFLite fp16 (and int8 dynamic range if within 1 point), bundle manifest (classes, tiers, spec
  version, metrics, licence ids, SHA-256); runs on LiteRT.js in the existing worker.
- Tiers: Tier A only for signs that pass the gate on the held-out devices (top-1 >= 90 %, and the gate's
  other rules); everything else Tier B. No sign is "Validated by Deaf signers".

## Next steps (in order)

1. Finish Stage 1 v1 (second web-learn run 44767308852: report, mapping lines, handoff).
2. `tools/psl_data/signspeak.py`: download both zips (ledger-checked), drop junk and partial samples,
   verify the hand order on one-handed words, write `.npz` per sample + a manifest; print counts.
3. `ml_engine/psl_hands.py` (Python) + `web/src/psl_hands.js` (JS) for the hands view, with golden parity.
4. `.github/workflows/psl-train.yml`: convert, train both models, evaluate on MP_Data_mobile, export,
   print `reports/psl_v3.md` numbers into the log; artifact = bundle.
5. Wire the PSL screen to the bundle (Tier B / "not yet validated" labels), keep the ASL baseline intact.
