# Fast track Stage 1: asset audit and plan

Date: 2026-11-18. Checked by the agent from the public pages listed under Sources. Nothing was
downloaded: this workspace has no network for files, so every size, count and licence below is
what the publisher's page says, unless marked "third-party" (from a catalogue, to be re-checked on
download). No accuracy, latency or coverage number in this report was measured; the coverage counts
are mappings of the 64 vocabulary entries, worked out by hand from published label lists.

Machine-readable versions: `data/LICENSES.yaml` (the ledger, checked by `tools/check_licenses.py`)
and `reports/fast_track_vocab_map.csv` (the vocabulary map).

## The short version

- **ASL mode can work with zero training.** The 1st-place model of Google's isolated-sign competition
  is published on Hugging Face under MIT (one 11.2 MB TFLite file, 250 ASL signs), trained on data
  licensed CC BY 4.0. A public CC0 "rerun set" of the competition's hidden test data exists; a
  third-party project reports its signers are not in the training data, which Stage 2 checks before
  using it for the accuracy number. 26 of our 64 entries have an exact ASL match.
- **PSL recognition can be trained from public data for 12 of the 64 entries** (SignSpeak word
  landmarks, Apache-2.0; PkSLMNM videos, CC BY 4.0). **None of them can reach Tier A in Stage 3 as
  things stand**: neither dataset publishes signer IDs, so the signer-independent gate cannot be run.
  They start as Tier B ("Suggested, please confirm") until signer IDs or a second, independent PSL
  dataset are available (see "Decisions" below).
- **The PSL dictionary (788 clips, CC BY 4.0) gives reference clips for 33 of the 64 entries**, plus 2
  phrases word by word, and hundreds of signs outside our vocabulary. Its upstream organisation ("hfad")
  is not named, so provenance must be confirmed before a store release.
- **21 entries have no shippable PSL data yet**; 12 of those have nothing in ASL either (sorry, stop,
  understand, I do not understand, repeat, speak slowly, sit, stand, eat, write, money, dangerous).
- **No public, shippable pretrained PSL model exists.** The one PSL model found (PSL-128's Swin
  weights) is non-commercial, research-only and behind an access request.
- **None of the PSL datasets we may use names a Deaf validator who checked its signs.** (The UMT
  dataset was recorded with Deaf signers, but has no licence yet.) The UI must say "Community dataset,
  not yet validated" on every PSL result.
- Five permission requests are drafted in `docs/permission_requests.md` [ME].

## Asset summary

"We may" uses the ledger's six uses: pre = pretrain encoder, train = train on labels, eval = measure
accuracy, clip = show clips, ship-w = ship weights, ship-d = ship the files.

| Asset (ledger id) | Lang | Licence | We may | Size | Signs | Signers | Input | Decision |
|---|---|---|---|---|---|---|---|---|
| SignSpeak word landmarks (`psl-signspeak-words`) | PSL | Apache-2.0 | pre, train, eval, ship-w, ship-d | Kaggle v3 410.5 MB; HF 435.2 MB | 70+ (Kaggle) / 60+ (HF) words | "multiple", no IDs | 2 hands × 21 points × xyz, 60 frames | **Use** (Stage 3 main PSL source) |
| UAlpha40 (`psl-ualpha40`) | PSL | CC BY 4.0 | all six | not stated (third-party 5.8 GB) | 40 Urdu letters (36 static, 4 dynamic) | 100 or 110, no IDs | JPG + MP4 | **Use** (fingerspelling head) |
| PkSLMNM (`psl-pkslmnm`) | PSL | CC BY 4.0 | all six | not stated (third-party 7.5 GB) | 7 adjectives | 100 or 180, no IDs stated | MP4 1920×1080 | **Use** (bad, sad, happy; face cues) |
| Expression through Hands (`psl-expression-hands`) | PSL | CC BY 4.0 | all six | third-party 3.5 MB | same 7 adjectives | not stated | not stated | Later, low value |
| WLPSL, Naeem (`psl-wlpsl-naeem`) | PSL | C-UDA, non-commercial | eval only | 370.3 MB | 31 words | 12 | MP4 (248 videos) | **Evaluate only** (yes, no, good, dangerous) |
| PSL-128 (`psl-128`) | PSL | CC BY-NC 4.0 + research terms, access by request | nothing yet | not stated; full-resolution copy about 55 GiB | 128 | 68 (male; IDs and signer split included) | Holistic landmarks (32, 258) + 224px video | **Ask permission** |
| UMT PSL dataset (`psl-umt-anwar-usama`) | PSL | none stated | nothing | not stated | alphabet, numbers, daily words | Deaf, from Deaf institutes | images + video | **Ask permission** |
| Saad Butt OpenPose (`psl-saadbutt-openpose`) | PSL | GPL-2.0 | eval only | 9.2 MB | 37 letters + 12 words | 9 non-expert | 2D OpenPose, single images | **Don't use** |
| FESF dictionary, psl.org.pk (`psl-fesf-dictionary`) | PSL | all rights reserved | nothing | 5,000-7,500+ words | — | — | web clips | **Ask permission**; never scrape |
| NISE compendium (`psl-nise-compendium`) | PSL | not released | nothing | 1,500 signs | — | — | — | Re-check later |
| PSL lexicon, Noorullah (`psl-lexicon-noorullah`) | PSL | CC BY-SA vs CC BY (conflict) | nothing | 80.9 KB | 635 text rows | — | text only | Not needed |
| SLT dictionary pk-hfad-1 (`psl-slt-dictionary`) | PSL | CC BY 4.0 (provenance unverified) | all six | not stated per release | 788 clips (README: 776 signs, 27 min) | 1 performer per clip | MP4 + MediaPipe pose/hand CSVs | **Use** (reference clips, Tier B prototypes) |
| SLT replications (`psl-slt-replications`) | PSL | CC BY 4.0 when released | nothing | planned 788 × 12 × 4 = 37,824 clips | 788 | not stated; person codes mark deaf/hearing | — | "Coming soon"; re-check |
| ISLR 1st-place TFLite (`asl-islr-1st-place-tflite`) | ASL | MIT | train (ASL only), eval, ship-w | 11.2 MB | 250 | trained on 21 Deaf signers | Holistic landmarks, 543 points/frame | **Use** (Stage 2) |
| GISLR competition data (`asl-gislr-competition-data`) | ASL | CC BY 4.0 + competition rules | pre, train, eval, ship-w | not stated | 250 | 21 Deaf | Holistic 0.9.0.1, 543 points | Reference only (model was trained on it) |
| GISLR rerun set (`asl-gislr-rerun-set`) | ASL | CC0 | all except clip | 14.15 GB | 250 | third-party: 10 Deaf, not in training | same as above | **Use** for Stage 2 accuracy (in a Kaggle notebook) |
| PopSign ASL v1.0 (`asl-popsign-v1`) | ASL | CC BY 4.0 | all six | 1.1 TB | 250 | 47 Deaf | video | Maybe: ASL reference clips |
| ASL fingerspelling 1st place (`asl-fingerspelling-1st-place`) | ASL | Apache-2.0 code, **no weights** | nothing | — | — | — | — | **Drop** (training needed) |
| MediaPipe hand / pose / face `.task` | — | Apache-2.0 | eval, ship | hand 7.8 MB (committed) | — | — | images | Use; pin pose/face hashes before release |

## Each asset in detail

### SignSpeak word landmarks: `psl-signspeak-words`

- **Source:** Kaggle `mohib123456/dynamic-word-level-pakistan-sign-language-dataset` (version 3, updated
  2026-06-28) and Hugging Face `mohibkhansherwani/DynamicWordLevelPakistanSignLanguageDataset`
  (DOI 10.57967/hf/8164). Authors: Mohib Ullah Khan Sherwani and the SignSpeak team, COMSATS
  University Islamabad, Abbottabad Campus (a final-year project).
- **Licence:** Apache-2.0 on both pages. We may train, ship weights and even re-share the data, with
  attribution.
- **Size and samples:** the two copies differ. Kaggle v3: 410,548,665 bytes, 70+ words, 100 samples per
  word (30 phone, 50 laptop camera, 20 USB webcam). Hugging Face: two zips of 158,784,931 and
  276,450,712 bytes, 60+ words, 70 samples per word (50 webcam, 20 phone). Stage 3 uses the Kaggle v3
  copy and reports which.
- **Signers:** "multiple"; no count and no signer IDs. Deaf status not stated. The word list file
  (`links_to_words.txt`) links each word to a PSL website clip the signers copied.
- **Words relevant to us:** hello, thank you, goodbye, excuse me, welcome, please, water, come here,
  mobile phone (and "go away", which is not our "go"). Others are mostly objects and animals (dog, fan,
  bridge, umbrella) and greetings we do not have yet (assalamualaikum, walaikumassalam, good morning,
  good night, see you later).
- **Format:** MediaPipe hand landmarks only, 21 points × (x, y, z) × 2 hands = 126 values per frame,
  60 frames per sample (SignSpeak README). No pose, no face, no video.
- **Mapping to features v2:** both hand blocks fill directly. With no pose, features v2 uses its
  documented fallback (image centre and image height / 4, `reference_from_pose` = 0); the pose and face
  blocks and the hand-face distances are zero with their masks at 0. Three unknowns must be handled in
  Stage 3: image aspect ratio (needed to convert to pixels; phone clips are probably portrait), frame
  rate (60 frames over "2-3 s" means about 20-30 fps; velocities depend on it) and whether frames were
  mirrored (decides left/right). Plan: train a "hands view" of features v2 (hand shapes, hand-to-hand
  distances, hand velocities, masks) with random aspect, speed and mirror augmentation, so the same
  model runs on any client's capture v2 output.
- **Risks:** no signer IDs means every split is "weaker"; label quality not validated by Deaf signers.

### UAlpha40: `psl-ualpha40`

- Mendeley Data 3pvnnckxyb version 3 (7 January 2025), Bahria University Karachi; article in Data in
  Brief (doi:10.1016/j.dib.2025.111342). Licence CC BY 4.0.
- 40 Urdu letters: 36 static as JPG, 4 dynamic as MP4. 22,280 images (2,897 original, 19,383 augmented)
  and 393 videos. Participants: the article says both 100 and 110; signer IDs not mentioned.
- Follows the letter standards published by FESF; collected "with the assistance of domain experts";
  no Deaf validator named.
- **Mapping:** run capture v2 on each image and video (in the agent's notebook). Static letters become
  1-frame sequences. Augmented images must be dropped or kept with their original, so no augmented copy
  of a test image lands in training.

### PkSLMNM: `psl-pkslmnm`

- Mendeley Data m3m9924p3v version 2 (26 September 2022), Bahria University Karachi. CC BY 4.0.
- 7 adjective signs, each with a matching facial expression: bad, best, sad, glad, scared, stiff,
  surprised. MP4, 1920×1080, about 2 s per clip. Participants: 100 (Mendeley) or 180 (article); Deaf
  status and signer IDs not stated.
- **Mapping:** full features v2 from video, including face points, so it is our only source of PSL
  non-manual (face) data. Gives bad, sad and (if "glad" is the same sign) happy.

### WLPSL (Naeem et al.): `psl-wlpsl-naeem`

- Kaggle `jahanzebnaeem/wlpsl`, 370,276,472 bytes, 31 words, 248 videos, 12 people (2 team members and
  10 volunteers). Licence: Computational Use of Data Agreement, academic use only, no commercial use.
- Decision: **evaluation only**. Nothing trained on it may ship, because the app is going to public
  stores. It holds yes, no, good and dangerous, which our trainable sources lack, so it can measure how
  well the dictionary-clip suggestions (Stage 4b) work on 12 people they never saw.

### PSL-128: `psl-128`

- Zenodo record 21946282, version 1.0.0, published 2026-09-12. 128 word-level signs in 15 categories,
  9,068 clips, 68 male signers (students of a special-education college; some were minors when
  recorded), signer folders S01-S68 and a signer-independent split file. MediaPipe Holistic landmarks
  (one 32 × 258 array per clip: pose 33 × 4 + hands 2 × 21 × 3) and 224×224 video.
- Licence CC BY-NC 4.0 plus research-use terms; files are restricted until the paper is accepted.
- It is the only PSL dataset found with signer IDs, so it is the best path to a real signer-independent
  number. We need access and written permission for a free, non-commercial exhibition app [ME].

### UMT PSL dataset: `psl-umt-anwar-usama`

- UMT Lahore eScholar handle 123456789/18672 (Haroon Anwar, Muhammad Usama; issued 2021-09-14). Images
  and videos of Deaf people from several Deaf institutes: alphabets, numbers, daily words. The record
  has no rights statement, so nothing may be used without written permission [ME].

### Saad Butt OpenPose dataset: `psl-saadbutt-openpose`

- Kaggle, GPL-2.0, 9,200,060 bytes; 37 Urdu letters and 12 Urdu words as 2D OpenPose points from single
  images of 9 non-expert subjects. GPL-2.0 is a software licence: weights trained on it might have to be
  released under GPL. Evaluation only, and not recommended.

### FESF PSL dictionary, NISE compendium, Noorullah lexicon

- **FESF / Deaf Reach (psl.org.pk):** the PSL reference that UAlpha40 and SignSpeak follow; all rights
  reserved. Ask permission [ME]; never scrape it (fast-track section 3.7).
- **NISE/DGSE compendium:** still not released as far as found.
- **Noorullah lexicon (Kaggle):** 635 text rows, motion files not included, licence fields conflict.
  Not needed.

### SLT Pakistan dictionary: `psl-slt-dictionary`

- GitHub `sign-language-translator/sign-language-datasets` by Mudassar Iqbal. The repository licence is
  CC BY 4.0. Release v0.0.3 holds `pk-hfad-1.videos-mp4.zip` (788 clips); v0.0.4 holds MediaPipe
  landmark CSVs (pose 33 points + 21 per hand, 5 values each: x, y, z, visibility, presence; image and
  world coordinates; one row per video frame). `parallel_texts/pk-dictionary-mapping.json` maps Urdu and
  English words to clip labels.
- **Provenance:** clips are described as coming from "recognized organizations"; "hfad" is never
  expanded and no permission chain is written down. The stated licence allows use with credit, so the
  ledger allows it, but `tools/check_licenses.py --release` blocks a store release until the maintainer
  confirms the source [ME].
- **Mapping:** the landmark CSVs fill both hands and the 9 pose points of features v2 (pose indices 0,
  11-16, 23, 24 are a subset of the 33); face is absent (mask 0). One clip per sign means recognition
  built on it is a one-example prototype: Tier B at most.
- The label index was read through a web page summary, not parsed by a script. Stage 4 re-reads
  `pk-dictionary-mapping.json` with code and corrects the vocabulary map if anything differs.

### ISLR 1st-place model and its data (ASL mode)

- **Model:** Hugging Face `sign/kaggle-asl-signs-1st-place`, licence MIT; `model.tflite` 11,242,036
  bytes and `sign_to_prediction_index_map.json` (250 signs). It comes from Hoyeol Sohn's Kaggle notebook
  `hoyso48/1st-place-solution-inference`; his GitHub repository is MIT too.
- **Input:** the competition format, MediaPipe Holistic landmarks with 543 points per frame (face 468,
  left hand 21, pose 33, right hand 21); the winning solution is reported to use 118 of those points.
  The input shape and the exact point list are confirmed by loading the file and reading the notebook in
  Stage 2.
- **Mapping from capture v2:** capture v2 runs the same three landmark models, but features v2 keeps
  only 9 pose and 69 face points. The ASL adapter therefore reads the raw landmark lists before they are
  reduced (Face Landmarker gives 478 points, whose first 468 follow the Holistic face mesh; Pose
  Landmarker gives all 33) and places them in the competition layout. Which of our
  anatomical hands goes into the competition's "left_hand" slot is decided by a parity test against the
  reference notebook, as the Stage 2 prompt asks.
- **Accuracy test set:** the model was trained on the competition's 21 training signers, so a split of
  that data is not held out. The Kaggle "ASL Isolated Sign Recognition Rerun Set" (CC0, 14,150,884,811
  bytes) is the competition's hidden test data; a third-party project reports it has 10 Deaf signers who
  are not in the training set. Stage 2 checks this from the files and runs the evaluation inside a
  Kaggle notebook (no 14 GB download) [ME: press Run all].
- **PopSign ASL v1.0** (CC BY 4.0, 47 Deaf signers, 250 signs, 1.1 TB of video) could supply ASL
  reference clips later. Whether its signers overlap the competition's is unknown.
- **ASL fingerspelling:** the 1st-place code is Apache-2.0 but no weights are published, and training it
  is far beyond a free 2-hour notebook. Dropped from the fast track.

### MediaPipe capture models

- `hand_landmarker.task` is committed (7,819,105 bytes, SHA-256 `fbc2a300…7cde1`); its model card says
  Apache License 2.0. `pose_landmarker_lite.task` and `face_landmarker.task` are downloaded on first use.
  Their model cards were not re-read in this session and their SHA-256 hashes are not recorded yet (no
  network here). Both are needed before a store release; `--release` enforces the hashes.

### Other searches

- **Pretrained PSL models:** none that can ship. SignSpeak's GitHub repository shows no licence and no
  weight files; PSL-128's Swin weights are restricted and non-commercial.
- **Other leads not added to the ledger:** a Mendeley PSL Urdu-alphabet hand-shape dataset from MNS
  University of Agriculture Multan (y9svrbh27n) and an unnamed "CC0 raw PSL videos" Kaggle upload that a
  catalogue suspects is copied from FESF. Neither was checked; the second must not be used unless its
  origin is proven.

## Vocabulary map (64 entries)

| Status | Entries | Meaning |
|---|---|---|
| PSL camera: trainable from public data | 12 | Multi-person public data with a licence that lets us ship the model. Starts as Tier B (no signer IDs). |
| PSL camera: suggestion from one dictionary clip | 29 | Only the one SLT dictionary clip: shown as a reference clip and used as a Tier B prototype by the autopilot (Stage 4b). |
| PSL clips only, word by word | 2 | "How are you?" and "My name is" can be shown as a sequence of word clips; no phrase recognition. |
| No shippable PSL data yet | 21 | 2 of these (yes, dangerous) have evaluation-only data in WLPSL. |

Other counts: 35 entries can show a PSL clip (33 single clips + 2 word by word); 4 of the 12 trainable
entries also have a dictionary clip (welcome, come, happy, sad); ASL mode has an exact match for 26
entries and a related sign for 5 more (store, call-on-phone, owie, fine). The 13 Phase 0 demo poses
are easy hand shapes with no PSL source recorded for them, so they should leave PSL mode once
real PSL recognition exists (Stage 3).

"Eval-only data" means WLPSL (non-commercial): yes, no, good and dangerous.

| # | Entry | PSL camera data (licence allows shipping) | PSL eval-only data | PSL dictionary clip | ASL mode | Fast-track status |
|---|---|---|---|---|---|---|
| 1 | Hello | SignSpeak `hi/hello` | — | — | `hello` | **Trainable** |
| 2 | Goodbye | SignSpeak `goodbye` | — | — | `bye` | **Trainable** |
| 3 | Thank you | SignSpeak `thankyou` | — | — | `thankyou` | **Trainable** |
| 4 | Please | SignSpeak `please` | — | — | `please` | **Trainable** |
| 5 | Sorry | — | — | — | — | None yet |
| 6 | Welcome | SignSpeak `welcome` | — | `welcome(reception)` | — | **Trainable** |
| 7 | Excuse me | SignSpeak `excuseme` | — | — | — | **Trainable** |
| 8 | Yes | — | WLPSL `yes` | — | `yes` | None yet |
| 9 | No | — | WLPSL `no` | `not` | `no` | Suggestion (1 clip) |
| 10 | Help | — | — | `help` | — | Suggestion (1 clip) |
| 11 | Stop | — | — | — | — | None yet |
| 12 | Wait | — | — | `wait` | `wait` | Suggestion (1 clip) |
| 13 | Come | SignSpeak `comehere` (phrase 'come here': check with a Deaf validator) | — | `aao` | — | **Trainable** |
| 14 | Go | — | — | `jao` | `go` | Suggestion (1 clip) |
| 15 | Understand | — | — | — | — | None yet |
| 16 | I do not understand | — | — | — | — | None yet |
| 17 | Repeat | — | — | — | — | None yet |
| 18 | Speak slowly | — | — | — | — | None yet |
| 19 | Sit | — | — | — | — | None yet |
| 20 | Stand | — | — | — | — | None yet |
| 21 | Eat | — | — | — | — | None yet |
| 22 | Drink | — | — | — | `drink` | None yet |
| 23 | Sleep | — | — | — | `sleep` | None yet |
| 24 | Open | — | — | — | `open` | None yet |
| 25 | Close | — | — | `shut` | `close` | Suggestion (1 clip) |
| 26 | Write | — | — | — | — | None yet |
| 27 | Read | — | — | — | `read` | None yet |
| 28 | Play | — | — | `play(sports)` | — | Suggestion (1 clip) |
| 29 | Mother | — | — | `mother` | `mom` | Suggestion (1 clip) |
| 30 | Father | — | — | `papa` | `dad` | Suggestion (1 clip) |
| 31 | Friend | — | — | `friend` | — | Suggestion (1 clip) |
| 32 | Family | — | — | `family` | — | Suggestion (1 clip) |
| 33 | Teacher | — | — | `teacher` | — | Suggestion (1 clip) |
| 34 | Doctor | — | — | `doctor(physician)` | — | Suggestion (1 clip) |
| 35 | Home | — | — | `house` | `home` | Suggestion (1 clip) |
| 36 | School | — | — | `school` | — | Suggestion (1 clip) |
| 37 | Hospital | — | — | `hospital` | — | Suggestion (1 clip) |
| 38 | Market | — | — | `market` | `store` (related) | Suggestion (1 clip) |
| 39 | Water | SignSpeak `water` | — | — | `water` | **Trainable** |
| 40 | Food | — | — | — | `food` | None yet |
| 41 | Tea | — | — | `tea` | — | Suggestion (1 clip) |
| 42 | Phone | SignSpeak `mobilephone` (exact (mobile phone)) | — | — | `callonphone` (related) | **Trainable** |
| 43 | Money | — | — | — | — | None yet |
| 44 | Book | — | — | `book` | `book` | Suggestion (1 clip) |
| 45 | Bag | — | — | `bag(noun)` | — | Suggestion (1 clip) |
| 46 | Medicine | — | — | `medication` | — | Suggestion (1 clip) |
| 47 | Good | — | WLPSL `good` | `good` | — | Suggestion (1 clip) |
| 48 | Bad | PkSLMNM `bad` | — | — | `bad` | **Trainable** |
| 49 | Happy | PkSLMNM `glad` ('glad': check it is the same sign as 'happy') | — | `happiness` | `happy` | **Trainable** |
| 50 | Sad | PkSLMNM `sad` | — | `unhappy` | `sad` | **Trainable** |
| 51 | Pain | — | — | `ache` | `owie` (related) | Suggestion (1 clip) |
| 52 | Emergency | — | — | `emergency` | — | Suggestion (1 clip) |
| 53 | Call | — | — | — | `callonphone` (related) | None yet |
| 54 | Dangerous | — | WLPSL `dangerous` | — | — | None yet |
| 55 | What? | — | — | `what` | — | Suggestion (1 clip) |
| 56 | Where? | — | — | — | `where` | None yet |
| 57 | Who? | — | — | `who` | `who` | Suggestion (1 clip) |
| 58 | When? | — | — | `when` | — | Suggestion (1 clip) |
| 59 | How are you? | — | — | aap + kesy (word by word) | — | Clips word by word |
| 60 | I am fine | — | — | — | `fine` (related) | None yet |
| 61 | My name is | — | — | mera + name (word by word) | — | Clips word by word |
| 62 | Today | — | — | `today` | — | Suggestion (1 clip) |
| 63 | Tomorrow | — | — | `tomorrow` | `tomorrow` | Suggestion (1 clip) |
| 64 | Time | — | — | `time` | `time` | Suggestion (1 clip) |

Dictionary labels are the part after `pk-hfad-1_`. Labels marked "check" need a Deaf validator before
they count as the same sign.

## Section 2 check: both hands

- Capture v2 asks MediaPipe for 2 hands on Python (`ml_engine/capture_v2.py`, now tested by
  `tests/test_two_hands.py`) and on the web (`web/src/capture_v2.js`, tested by
  `web/tests/capture-v2.test.mjs`). Both read the number from `shared_data/feature_spec_v2.json`.
- **The v1 paths still use one hand:** `web/src/vision.js` (`numHands: 1`), `backend/app.py`
  `/api/recognize-frame` (`num_hands=1`, which is what the Flutter app calls), and the default of
  `signbridge_common.HandTracker`. These are the Phase 0 demo paths. Stage 2 switches the web app and
  Stage 6 moves the phone to on-device capture v2; until then the phone is one-handed.
- The phone does not run MediaPipe on the device yet, so there is no Dart check until Stage 6.

## Decisions for you at this gate

1. **Tier A is out of reach for now. Accept that PSL starts as Tier B?** My recommendation: yes. Every
   PSL sign is shown as "Suggested, please confirm" with "Community dataset, not yet validated", which is
   exactly what amendment 3 allows. The paths to Tier A are: PSL-128 access (signer-independent split),
   signer IDs from the SignSpeak authors, or signer IDs found in the PkSLMNM file names once downloaded.
2. **Retire the 13 Phase 0 demo poses from PSL mode in Stage 3?** They are hand shapes chosen for a demo,
   with no PSL source recorded. Recommendation: move them to a clearly labelled "Gesture demo" switch, off by default.
3. **Send the five permission emails** in `docs/permission_requests.md` (FESF, PSL-128, UMT, SLT
   maintainer, SignSpeak authors). None of the fast track waits for the answers.

## Plan adjustments for Stages 2-7

- **Stage 2 (ASL mode):** I need `model.tflite` and `sign_to_prediction_index_map.json` from the
  Hugging Face page. This workspace cannot download, so either attach the two files here or connect the
  project folder on your laptop and I will fetch them through your computer [ME]. Accuracy is measured on
  the rerun set inside a Kaggle notebook you start with "Run all" [ME].
- **Stage 3 (PSL):** trains on SignSpeak + PkSLMNM (12 entries) + UAlpha40 letters. Splits reported as
  "weaker" (by camera type or recording session where possible). Landmarks for the video datasets are
  extracted inside the notebook with capture v2.
- **Stage 4 (reverse direction):** SLT dictionary clips for 35 entries and the rest of its 788 clips,
  with attribution shown in the app. Re-parse the mapping file with code first.
- **Stage 4b (autopilot):** dictionary-clip prototypes for the 29 one-clip entries and beyond;
  WLPSL measures prototype accuracy on 12 unseen people for yes, no, good and dangerous (no and good have
  clips; yes and dangerous would come from `tools/web_learn.py` if a licensed source is found).
- **Stage 6 (store):** record pose/face model hashes, re-read their model cards, and resolve the SLT
  provenance, or `check_licenses.py --release` will block the build.

## [ME] steps from this stage

1. Read this report and reply "go", plus your answers to the three decisions above.
2. Optional now, needed before the gate re-run: run `phase1_checks.bat` on your Windows laptop
   (`docs/HOW_TO_RUN_PHASE1_CHECKS.md`) and send back the `reports\phase1_checks` folder.
3. Send the permission emails in `docs/permission_requests.md` when you are ready.
4. For Stage 2: attach the two ASL model files, or connect the project folder.

## Sources

Each was read on 2026-11-18.

- SignSpeak: <https://huggingface.co/datasets/mohibkhansherwani/DynamicWordLevelPakistanSignLanguageDataset>,
  <https://www.kaggle.com/datasets/mohib123456/dynamic-word-level-pakistan-sign-language-dataset> (API metadata),
  <https://github.com/MohibUllahKhanSherwani/SignSpeak_FYP>
- UAlpha40: <https://data.mendeley.com/datasets/3pvnnckxyb/3>, <https://pmc.ncbi.nlm.nih.gov/articles/PMC11848795/>
- PkSLMNM: <https://data.mendeley.com/datasets/m3m9924p3v/2>, <https://www.techscience.com/cmc/v74n1/49833/html>
- Expression through Hands: <https://data.mendeley.com/datasets/4d6tj5snkd/3>
- WLPSL: <https://www.kaggle.com/datasets/jahanzebnaeem/wlpsl> (API metadata)
- PSL-128: <https://zenodo.org/records/21946282>
- UMT: <https://escholar.umt.edu.pk/handle/123456789/18672> (DSpace REST record)
- Saad Butt: <https://www.kaggle.com/datasets/saadbutt321/pakistan-sign-language-dataset> (API metadata)
- Noorullah lexicon: <https://www.kaggle.com/datasets/shayannoorullah/pakistani-sign-language-psl-lexicon-dataset>
- SLT: <https://github.com/sign-language-translator/sign-language-datasets> (README, LICENSE, releases,
  `parallel_texts/pk-dictionary-mapping.json`)
- ISLR model: <https://huggingface.co/sign/kaggle-asl-signs-1st-place>,
  <https://github.com/hoyso48/Google---Isolated-Sign-Language-Recognition-1st-place-solution>
- GISLR competition: <https://www.kaggle.com/competitions/asl-signs>; rerun set:
  <https://www.kaggle.com/datasets/sohier/461054610546105>
- PopSign: <https://signdata.cc.gatech.edu/view/datasets/popsign_v1_0/index.html>
- ASL fingerspelling: <https://github.com/ChristofHenkel/kaggle-asl-fingerspelling-1st-place-solution>
- MediaPipe hand model card: <https://storage.googleapis.com/mediapipe-assets/Model%20Card%20Hand%20Tracking%20(Lite_Full)%20with%20Fairness%20Oct%202021.pdf>
- Third-party catalogue used only for leads and marked facts: <https://github.com/juleshenry/marionet/issues/152>
