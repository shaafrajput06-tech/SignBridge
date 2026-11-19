# SignBridge v2 — Fast-Track Master Prompt (ready-trained, exhibition build)

Save this file in the repo as `docs/prompts/fast-track.md`, then start a session in the
SignBridge_Complete folder and paste:

> Read CLAUDE.md, docs/CONTEXT.md, docs/handoffs/phase-1.md and docs/prompts/fast-track.md.
> Execute docs/prompts/fast-track.md stage by stage. Stop at each stage gate and tell me exactly what to do.

---

## 0. Why this prompt exists (read first)

The owner of this project is a student. They cannot record signers, label data or train models.
Phases 2–8 as written depend on Deaf signers recording PSL and on GPU training runs, so the
project has stalled. This prompt replaces that path with a **fast track**: ship a recogniser that works
**out of the box with zero training by the user**, using models and datasets that already exist, and
turn the result into a polished app on web, Android, iOS and desktop for a national STEM exhibition.

Everything in CLAUDE.md still applies (truth over impressiveness, licences, privacy, offline, tests,
small commits) **except the amendments in section 1**. Do not throw away Phase 0/1 work: capture v2,
features v2, parity tests, the vocabulary, the backend and the Flutter app are the foundation.

## 1. Constitution amendments (add these to CLAUDE.md as section 8 in your first commit)

1. **The user never trains anything.** No flow may require the user to record, label or train signs
   before recognition works. "Teach a sign" (Tier C) may exist as an optional extra, never as a step.
   If a model must be trained, the agent does it, or the agent ships a single notebook the user runs
   by pressing "Run all" on Kaggle or Google Colab (free GPU), with click-by-click instructions and
   the expected output at each cell. Prefer existing pretrained weights over any training.
2. **Two clearly separated sign languages.** ASL labels are now allowed **only inside a separate,
   clearly labelled "ASL" language mode**, never shown, mixed or described as PSL. PSL stays the
   primary language of the app. The UI always shows which sign language is active.
3. **Exhibition tiers.** PSL signs trained on public PSL data that pass the signer-independent gate are
   Tier A. Those that don't pass yet are Tier B ("Suggested — please confirm") and still usable. Deaf
   validator sign-off remains required for the "Validated by Deaf signers" badge; until then the UI
   says "Community dataset — not yet validated". Never hide this; judges respect it.
4. **Both hands, always.** Every recogniser, in every client, tracks and uses both hands at the same
   time, plus the pose and face points from features v2. One-handed demo poses alone are no longer
   enough. Details in section 2.
5. **AI does the work, not people.** Wherever a human used to train, label, tune or set something up,
   the app's built-in AI does it automatically (section 3). AI-made labels never become Tier A by
   themselves, and the AI never invents a sign. It only learns from licensed reference clips and from
   the user's own confirmed results.

## 2. Two-hand recognition (applies to every stage)

- Track **both hands at once** (2 × 21 landmarks) together with the pose (shoulders, elbows, wrists)
  and face points already defined in `shared_data/feature_spec_v2.json`. Check that capture v2 asks
  MediaPipe for `numHands: 2` (num_hands=2 in Python, the same in Flutter) on every platform, and add
  a test for it.
- Support **two-handed signs** (both hands moving), **one-handed signs** (other hand at rest or out of
  view) and **hand-to-hand contact** (touching, crossing, one hand tapping the other). Use the
  hand-to-hand and hand-to-face distances from features v2 as model inputs.
- Know **which hand is which**, even when hands cross or the selfie camera mirrors the image. Use the
  F12 mirroring rules and pose wrists to assign left and right, never MediaPipe's handedness label alone.
- **Left-handed signers:** detect the dominant hand from the first seconds of signing and mirror
  features so a left-handed signer gets the same accuracy. Report accuracy for both.
- Handle a hand **briefly disappearing** (occlusion or leaving the frame) with the presence mask instead
  of failing. Show a gentle hint if one hand stays out of view during a two-handed sign.
- The live camera view draws both hands in two different colours and shows "Both hands seen" or
  "Only one hand seen".
- Report accuracy separately for one-handed and two-handed signs in every model report.
- **Gate check:** a test clip set with two-handed, one-handed, crossing-hands and left-handed examples
  gives the same top-1 result on Python, web and Flutter.

## 3. Built-in AI that replaces human training

Add an "AI autopilot" layer inside the app. Everything below runs on the device by default, with no
button-pressing or training needed from the user.

1. **Learns signs automatically from dictionary clips.** The app's AI extracts both-hand landmarks
   from every licensed PSL reference clip (section 4, dictionary of roughly 780 signs), embeds them with
   the encoder and builds the Phase 4 prototype index by itself. This gives Tier B recognition of
   hundreds of signs from day one, with no person recording or labelling anything. A build script does
   this once; the result ships inside the app.
2. **Adapts to each user automatically.** Every time the user taps to confirm a Tier B suggestion, the
   AI adds that example to a personal on-device prototype, so it gets better for that person every
   day. It stays on the phone. No training screen, no data collection step.
3. **Self-calibration.** On first launch the AI checks the lighting, camera distance, framing and
   dominant hand in about 5 seconds while the user waves both hands, then sets the confidence
   thresholds and the camera settings itself. It re-checks whenever accuracy drops.
4. **Smart sentence builder.** A small language model turns the recognised glosses into natural
   Urdu and English sentences. Use an on-device model where the device can run one; an online model
   only if the user switches it on. Rule from Phase 6: it may reorder and inflect, never add meaning.
   The raw glosses are always shown underneath.
5. **AI helper chat.** An in-app assistant the user can talk or type to: "How do I sign 'hospital'?"
   (plays the reference clip), "Why didn't it understand me?" (reads the confidence and the framing
   check and explains in plain words), "Teach me 5 greetings" (starts a practice round). It only uses
   the app's own vocabulary and clips, and it says "I don't know" instead of guessing a sign.
6. **Self-improving dataset (agent-run, not human-run).** A script the AI coding agent runs
   (`tools/auto_improve.py`): it pulls newly licensed public PSL data, converts it, retrains, runs the
   evaluation gate and builds a new model bundle only if every number improves. The user's only step
   is to approve the new bundle. Donated user examples are used only with consent and stay Tier B
   until a Deaf validator approves them.
7. **Learns new signs from the internet (agent-run pipeline, `tools/web_learn.py`).**
   - Searches the web for PSL sign videos (official PSL dictionaries, Deaf organisations, education
     sites, Creative Commons videos) for every vocabulary word that has no data yet.
   - Uses only sources whose licence or written permission allows the use, recorded in
     data/LICENSES.yaml. It never downloads from sites whose terms forbid it (for example YouTube
     without the owner's permission). For valuable sources without a licence, it drafts a polite
     permission email for me to send to the organisation [ME].
   - Extracts both-hand landmarks only. It keeps no video unless the licence allows it.
   - Auto-labels each clip from its title, caption or page text, then **cross-checks**: a sign is
     accepted only when at least 2 independent sources show matching movements (embedding
     similarity above a threshold chosen on known signs). It rejects ASL or other sign languages,
     and keeps regional variants as variants.
   - Turns each accepted sign into many training examples with augmentation (speed, angle, size,
     mirroring for left-handers) and adds it to the prototype index as Tier B.
   - Runs on the developer's computer before each release, never live inside the user's app,
     so the app stays offline, private and store-safe.
   - Writes reports/web_learn_vN.md: words searched, sources used, signs accepted, signs rejected
     and why. It measures accuracy for internet-learned signs separately.
8. **Honest by design.** The AI always shows its confidence in plain words ("Pretty sure", "Not sure,
   is it one of these?") and never speaks a low-confidence result out loud.

Put the autopilot behind one clear switch in Settings, on by default, with a one-line explanation
of what stays on the device.

## 4. Ready-made assets to evaluate (check each licence and record it in data/LICENSES.yaml)

Verify that each one exists, what its licence allows (pretrain / train / reference / redistribute
weights), and its real size. If a licence is unclear or forbids redistribution, don't ship it: say so
and pick the next option.

**Sign → text, PSL**
- *Dynamic Word-Level Pakistan Sign Language Dataset* (Kaggle `mohib123456/dynamic-word-level-pakistan-sign-language-dataset`;
  Hugging Face `mohibkhansherwani/DynamicWordLevelPakistanSignLanguageDataset`): 60+ PSL words,
  about 70 samples per word, 60-frame MediaPipe landmark sequences. Landmarks only, so it can be
  mapped to features v2 hands without video.
- PSL Urdu alphabet datasets for fingerspelling: UAlpha40 (Mendeley, DOI 10.17632/3pvnnckxyb.3,
  36 static and 4 dynamic letters), the Kaggle `saadbutt321/pakistan-sign-language-dataset`, and the
  UMT PSL dataset (alphabets, numbers, daily words, recorded at Deaf institutes).
- Search for any other public PSL landmark or video datasets and pretrained PSL models, and list them
  with licences in the stage 1 report.

**Sign → text, ASL mode (pretrained, no training needed)**
- 1st-place model of Google's Isolated Sign Language Recognition competition (250 ASL signs,
  TFLite, MediaPipe Holistic landmarks): Hugging Face `sign/kaggle-asl-signs-1st-place` and
  Kaggle notebook `hoyso48/1st-place-solution-inference`. The training data is PopSign ASL v1.0
  (CC BY 4.0).
- 1st-place solution of Google's ASL Fingerspelling Recognition competition (weights if public).

**Text/speech → sign (reverse direction, gives the largest vocabulary)**
- `sign-language-translator` project (GitHub `sign-language-translator/sign-language-datasets`):
  a Pakistan sign dictionary of roughly 780 reference clips from recognised organisations, plus
  landmark releases. If the licence allows `reference_clip` use, this lets the app *show* hundreds
  of PSL signs for typed or spoken Urdu/English, even where camera recognition isn't available yet.

## 5. Stages (each ends with a gate: tests green, a short report in reports/, a commit, then stop)

### Stage 1 — Asset audit and plan (no code changes beyond docs)
- Fill data/LICENSES.yaml (Phase 2 task 1, schema plus checker) for every asset in section 4.
- reports/fast_track_assets.md: for each asset, the licence, what we may do with it, size, number of
  signs and signers, input format, and how it maps to features v2.
- Map the 64 vocabulary entries to the assets: which can be recognised (PSL / ASL), which can only
  be shown as a reference clip, and which have nothing yet.
- Close the two open Phase 1 items: prepare `phase1_checks.bat` instructions for the fps bench and
  the full Phase 0 suite on my Windows laptop, written step by step for a beginner.
- **Gate:** I read the report and reply "go".

### Stage 2 — ASL mode, working today with zero training
- Wrap the pretrained 250-sign ISLR model as a model bundle (manifest, classes, feature version,
  licence IDs, SHA-256). Convert to what each client needs: TFLite (Flutter), ONNX or TF.js (web),
  Python (desktop). Its input is MediaPipe Holistic landmarks, so write an adapter from capture v2
  output to that model's expected input, with a parity test against the reference inference notebook.
- Measure top-1/top-5 accuracy on a held-out split of the competition data and the latency on this
  machine. Report both with dataset, split and date.
- **Gate:** camera → ASL word on screen in the web app, numbers in reports/asl_mode_v1.md.

### Stage 3 — PSL recogniser from public PSL data (the agent trains; the user doesn't)
- Write `notebooks/train_psl_fast_track.ipynb`: downloads the licensed PSL datasets, converts them to
  recording format v2, splits by signer where signer IDs exist (otherwise report the split as
  "weaker"), trains the Phase 3 baseline first (GRU or 1D-conv over landmark sequences), then the
  compact conv-transformer if time allows, then calibration and an "unknown" class. It exports a
  bundle and a report automatically.
- It must run with "Run all" on a free Kaggle or Colab GPU in under 2 hours. Write
  docs/HOW_TO_RUN_THE_NOTEBOOK.md with click-by-click steps and screenshots described in words.
- Train on both hands plus pose and face (section 2): include two-handed and hand-contact signs,
  mirror augmentation for left-handed signers, and report one-handed vs two-handed accuracy.
- Add PSL fingerspelling (Urdu alphabet) as a second head or a separate small model.
- Promote to Tier A only glosses that pass the gate; the rest are Tier B.
- **Gate:** the bundle loads in all three clients, reports/psl_fast_track_v1.md lists per-sign
  accuracy honestly, and low-confidence results are shown as suggestions, never spoken.

### Stage 4 — Reverse direction and conversation
- Text or speech (Urdu/English) → PSL reference clips from the dictionary, played in sequence, with a
  clear note that this is a word-by-word aid. Offline speech-to-text where the device supports it.
- Rule-based gloss → sentence (Phase 6 task 1, rules only, no LLM needed), raw glosses always shown.
- Split-screen conversation view, quick phrases, emergency phrases panel.

### Stage 4b — AI autopilot (section 3)
- Build the automatic dictionary-learning script and ship the prototype index, so hundreds of PSL
  signs work as Tier B suggestions with zero human recording.
- On-device personal adaptation from confirmed suggestions, self-calibration on first launch,
  the smart sentence builder, the AI helper chat, `tools/auto_improve.py` and `tools/web_learn.py`.
- **Gate:** a fresh install recognises signs and calibrates itself with no training screen anywhere.
  reports/autopilot_v1.md measures accuracy before and after 20 confirmed examples from one test
  user, and the coverage gained from the dictionary index.

### Stage 5 — Human, hand-crafted interface (not "AI-looking")
Before coding, write docs/DESIGN.md and show me screen mockups (one per main screen). Then build it in
the React web app and the Flutter app so both look like one product.
- Avoid the generic AI look: no purple/blue gradients, glowing orbs, sparkle icons, glassmorphism,
  robot or brain imagery, or "AI-powered" badges.
- Warm and local: warm off-white paper background, deep ink blue text, one accent (terracotta or
  truck-art mustard), subtle textures, hand-drawn line illustrations of real hands, slightly
  irregular rounded shapes. A typeface pairing with character for English plus a proper Nastaliq
  font for Urdu (check font licences; the fonts/ folder exists for this).
- Friendly human copy in English and Urdu ("Show me a sign", "I'm not sure — try once more"), never
  technical wording on the main screens.
- Deaf-first UX (Phase 7 task 4): large captions, high contrast option, visual and haptic cues,
  signing-space guide, lighting/framing coach, confidence in plain words, RTL Urdu, screen-reader labels.
- **Gate:** a WCAG 2.2 AA check on the web UI, and screenshots of every screen on phone and desktop sizes.

### Stage 6 — On-device everywhere and store-ready
- Web: installable PWA, self-hosted WASM and models, inference in a Web Worker, works in airplane
  mode (Phase 7 task 1). Deploy free on Netlify, Vercel or GitHub Pages with HTTPS so phone cameras work.
- Flutter (keep Flutter; the mobile app already exists): on-device MediaPipe + LiteRT, so no local
  server is needed. Builds for Android (AAB/APK) and iOS (IPA).
- Desktop: the same web UI served locally by the existing launcher.
- docs/PUBLISHING.md, written for a beginner: Google Play developer account (one-time fee) and Apple
  Developer Program (yearly fee; an iOS build needs a Mac or a cloud Mac build service such as
  Codemagic), signing keys, the store listing, a privacy policy page, camera-permission text, the
  data-safety form, content rating, typical review times, and common rejection reasons.
- **Gate:** recognition works with networking off on the web PWA, Android and desktop, and the fps and
  latency numbers are measured on a named phone and laptop.

### Stage 7 — Exhibition kit
- "Exhibition mode": one tap, full screen, large captions, a live panel showing the landmarks being
  tracked and the confidence, a counter of supported signs per tier, and offline operation.
- docs/EXHIBITION_KIT.md: a 2-minute pitch, a 5-minute technical walkthrough, a diagram (camera →
  landmarks → features v2 → model → gloss → sentence → speech), tri-fold poster text, 20 likely judge
  questions with honest answers, a limitations slide, and a social-impact section with cited
  statistics on deafness in Pakistan and worldwide (sourced, never invented).
- Update DEMO_SCRIPT.md and EXHIBITION_CHECKLIST.md: a backup plan for bad lighting, no Wi-Fi or a
  dead laptop (recorded demo video, phone fallback).
- What will impress judges, built in: two-hand tracking, an AI autopilot that learns with no human
  training, offline privacy-first AI, PSL and Urdu (rare), two-way
  conversation, honest measured accuracy, and a licence ledger.

## 6. Rules for working with me
- I am a beginner. After each stage, tell me in plain words what changed, how to run it on Windows,
  and how to test it on my phone.
- Give complete files, never fragments. Keep the test suite green.
- If something can't be done (a licence forbids it, no data exists, a number misses its target),
  tell me straight away with the measured result and the best alternative. Never invent numbers.
- Steps that need me (accounts, fees, running the notebook, measuring on my devices) are marked
  **[ME]**, prepared fully, and listed at the end of each stage.
