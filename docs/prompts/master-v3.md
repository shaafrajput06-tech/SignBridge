# SignBridge — Master Prompt (v3: "Best translator" build)

Save this file in the repo as `docs/prompts/master-v3.md`. Then start a coding-agent session on the
GitHub repo **`shaafrajput06-tech/signbridge`** (give the agent push access) and paste:

> Read CLAUDE.md, docs/CONTEXT.md, docs/prompts/fast-track.md, reports/asl_mode_v1.md,
> reports/fast_track_assets.md and docs/prompts/master-v3.md. Execute master-v3.md stage by stage.
> Stop at every gate, and tell me in plain words exactly what I need to do. When all the work is done,
> finish with Stage 7: update the live website with everything the project produced.

---

## 0. What you are starting from (read before touching code)

There are two snapshots of this project. Treat them like this:

| Snapshot | What it is | Role in this prompt |
|---|---|---|
| **A — `SignBridge.zip` ("shared copy")** | The built, working static website (Vite build of 2026-11-19) plus `Start SignBridge.bat` / `serve.ps1`. Runs fully in the browser. | **The inference baseline. Keep it working, never regress it.** |
| **B — `SignBridge_v2_fast_track_stage2.zip` (`SignBridge_Complete`)** | An older copy of the source repo: Python ML engine, FastAPI backend, React/Vite web, Flutter app, tests, licence ledger, CLAUDE.md constitution, fast-track plan. Stage 1 done, Stage 2 (ASL mode) drafted. | Reference only. |
| **C — GitHub repo `shaafrajput06-tech/signbridge`, branch `main`** | The live source, newer than B (last checked commit `42a572f`, 2026-11-19): adds `.github/workflows/website.yml` (tests + build + deploy to GitHub Pages on every push to `main`, check results published at `/ci/`), `docs/WEBSITE.md`, `web/src/paths.js` (the `/SignBridge/` base path), two-hand web tests and camera/ASL fixes. Live site: **https://shaafrajput06-tech.github.io/SignBridge/** | **The codebase you work in. Always start from the latest `main`.** |

### The inference pipeline in snapshot A that must be preserved ("Inference Baseline v1")

```
camera ─▶ capture v2 (MediaPipe tasks-vision WASM: Pose Landmarker lite + Hand Landmarker ×2 + Face Landmarker)
       ─▶ islr_frame(): 543 × 3 per frame [face 468 | left hand 21 | pose 33 | right hand 21], NaN = missing,
          hands in anatomical slots decided by pose wrists, unmirrored coordinates
       ─▶ SignSegmenter (min_hand_frames 6, end_after_missing_frames 8, margin 2, max 192)
       ─▶ nearest-frame resample to 32 frames (browser path)
       ─▶ ASL ISLR 1st-place TFLite (250 signs, MIT, SHA-256 f55a2bb1…f0bb7) on LiteRT.js 2.6.0 in a Web Worker
          (server path: ai-edge-litert at native length via /api/asl/predict)
       ─▶ top-5 ─▶ "Pretty sure" (≥0.60) / "Not sure, is it one of these?" (≥0.25) / "Try once more"
PSL side: 13 rule-based demo hand shapes (v1, one hand) + 31 PSL reference clips (SLT dictionary pk-hfad-1, CC BY 4.0)
```

Files that hold it: `web/src/capture_v2.js`, `features_v2.js`, `asl_islr.js`, `asl_litert.js`, `asl_worker.js`,
`asl_client.js`, `AslMode.jsx`, `ml_engine/asl_islr.py`, `ml_engine/capture_v2.py`,
`shared_data/asl_islr_spec.json`, `shared_data/feature_spec_v2.json`, `models/asl/*`, and the built copy in
snapshot A `site/`.

**Rules for the baseline**
1. First commit: copy snapshot A's `site/` into the repo as `baseline/v1-site/` (read-only reference) and
   tag the current commit `inference-baseline-v1`. Record in a test which input → output it produces on the
   golden fixtures (`tests/golden/asl_islr_cases.json`, `v2_holistic.json.gz`).
2. Every new model or pipeline change runs **side by side** with the baseline on the same evaluation set.
   It replaces the baseline only if it is better on top-1 *and* not slower than the latency budget
   (section 5). Otherwise the baseline stays the default and the new one is opt-in.
3. The 543-point layout, the segmenter, the confidence words and the Python ↔ JS parity tests stay. You may
   *add* inputs (e.g. features v2 distances) in new models; you may not silently change the baseline's.
4. The offline "shared copy" (bat + PowerShell server, no install) must still be produced by
   `npm run build:shared` at the end of every stage.

Everything in `CLAUDE.md` (sections 1–8) still applies: truth over impressiveness, PSL first, Deaf-led,
licences and consent, privacy/offline, engineering rules, fast-track amendments. Add section 9 below to
CLAUDE.md in your first commit. Where section 9 conflicts with 1–8, section 9 wins.

---

## 1. Goal

Make SignBridge the most accurate, fastest and most trustworthy **two-way sign language translator**
available for Pakistan, on a public website at a **SignBridge domain**, deployed automatically from GitHub:

- **Sign → text/speech**: PSL (primary) and ASL (separate, clearly labelled mode). Isolated signs first,
  then continuous signing (sentences), plus Urdu and English fingerspelling.
- **Text/speech → sign**: Urdu/English → PSL reference clips (and later an avatar), word by word, honestly
  labelled.
- **AI built in**: the app's own AI does the training, labelling, calibration, sentence building and help.
- **Learns from internet videos**: an agent-run pipeline finds sign videos on the internet for every word,
  checks their licence, extracts landmarks, cross-checks labels and trains the models.
- **Fast, accurate, reliable website**: measured performance budgets (section 5), offline-capable PWA.

---

## 2. Constitution section 9 (add to CLAUDE.md)

1. **Baseline protection.** The Inference Baseline v1 (master-v3.md section 0) is never broken or
   replaced without a measured, side-by-side improvement on the same evaluation set.
2. **Internet videos are a data source, not a free-for-all.** Every video used for training is found,
   checked and logged by `tools/web_learn/`. It is used only when its licence or the owner's written
   permission allows that use, recorded in `data/LICENSES.yaml` *before* download. No scraping of sites
   whose terms forbid it; no bypassing logins, paywalls or rate limits. Where a valuable source has no
   licence, draft a permission request for me [ME] and move on.
3. **Every sign is trained from internet videos, but no sign is promoted by the internet alone.** A
   web-learned sign starts as Tier B. Tier A still needs the signer-independent gate (CLAUDE.md 1) and,
   for the "Validated by Deaf signers" badge, a Deaf validator's sign-off (CLAUDE.md 3).
4. **Language purity.** The web pipeline must classify the sign language of each clip; ASL, BSL, ISL or
   other clips never carry labels into PSL (they may pretrain the encoder only, if licensed).
5. **AI never invents a sign.** Language models may write sentences, explanations and search queries;
   they never generate sign descriptions, landmarks or labels that are not backed by a real clip.
6. **Performance is a feature.** Every release passes the budgets in section 5, measured, not estimated.

---

## 3. Stages

Each stage ends with: all tests green (`python tools/run_all_tests.py --smoke`), a report in `reports/`,
`docs/CONTEXT.md` updated, a handoff in `docs/handoffs/`, small commits, a preview build I can open
(`npm run build && npm run preview`, or the built site uploaded as a workflow artifact on the pull request),
then **stop** and list my [ME] steps.

**The live website is updated only once, at the end (Stage 7).** Every push to `main` publishes the live
site automatically, so all work from Stage 0 to Stage 6 stays on the branch `v3/master` and its pull request.
Never push to `main` before Stage 7.

If your workspace cannot download files or reach the internet, do **not** stop: put every download,
search and training step into a Kaggle/Colab notebook or a GitHub Actions workflow that I start with one
click, and give me click-by-click steps plus the expected output of each cell.

### Stage 0 — Freeze the baseline and finish Stage 2 (ASL mode)
- Do the baseline rules in section 0 (copy, tag, golden tests, `build:shared`).
- Close the pending items in `reports/asl_mode_v1.md`: run `notebooks/asl_mode_eval.ipynb` on Kaggle
  (GISLR rerun set, CC0) for top-1/top-5 at native length and at 16/24/32/48/64 frames, one- vs two-handed,
  left- vs right-dominant, and the hand-slot check. Pick the frame count from the measurement.
- Measure browser latency per sign with `asl-selftest.html` on my laptop [ME] and on one phone [ME].
- **Gate:** camera → ASL word on the preview build; numbers filled in, none estimated.

### Stage 1 — AI web-video learning pipeline (`tools/web_learn/`)
Build an agent-run pipeline (runs on my computer, Kaggle, Colab or GitHub Actions — never inside the
user's browser at runtime):

1. **Word list.** Every vocabulary entry (64 now, then the ~780-sign SLT dictionary list, then a 1,500+
   PSL core list), each with English, Urdu, Roman Urdu and known synonyms.
2. **Search.** For each word, search with several query variants in English, Urdu and Roman Urdu
   ("PSL sign for hospital", "ہسپتال اشارہ", "Pakistan sign language hospital").
   Sources, in order of preference:
   - Licensed datasets already in the ledger (SignSpeak, UAlpha40, PkSLMNM, SLT dictionary, later PSL-128 /
     UMT / SLT replications if permission arrives).
   - Official Deaf organisations and education sites (FESF/psl.org.pk, NISE, Deaf Reach, schools) — only
     with written permission [ME drafts in `docs/permission_requests.md`].
   - YouTube via the **YouTube Data API v3** with `videoLicense=creativeCommon`, Vimeo/Wikimedia Commons with
     CC licences, Internet Archive items with open licences. Respect each platform's terms of service;
     if a platform's terms forbid downloading, use only the official API/embeds or ask the owner.
   - An LLM may help write queries and read page text/captions to propose a label. It never decides a
     label alone.
3. **Licence gate.** Before any download: write a ledger entry (URL, licence, uploader, allowed uses,
   date checked). `data_engine.ledger.assert_allowed()` must pass or the clip is skipped and logged.
4. **Extract.** Run capture v2 (both hands + pose + face) on each clip → landmark `.npz` in recording
   format v2. Keep video only if the licence allows redistribution and it is needed as a reference clip.
5. **Quality filter.** Reject clips with no hands for most frames, more than one signer, heavy cuts,
   tiny or blurred signer, or wrong framing. Trim to the sign with the segmenter.
6. **Language check.** A small classifier (trained on licensed PSL vs ASL/other data) flags clips that are
   probably not PSL; flagged clips are dropped from PSL labels.
7. **Cross-check labels.** Accept a (word → sign) pair only when **≥ 2 independent sources** agree, i.e. their
   embeddings (from the encoder in Stage 2) are closer than a threshold chosen on known signs. Disagreeing
   sources become *regional variants* of the same gloss if each has ≥ 2 supporting clips; otherwise rejected.
8. **Dedupe** near-identical clips (same video re-uploaded) so they do not count as independent sources or
   leak across train/test splits.
9. **Output** `data/web_learned/vN/` (landmarks + manifest) and `reports/web_learn_vN.md`: words searched,
   sources found / licensed / used, clips accepted / rejected and why, signs covered, signs still missing.
- **Gate:** report lists real numbers for the first run; zero clips from sources the ledger forbids
  (a test checks every manifest entry against the ledger).

### Stage 2 — Train the best PSL recogniser (agent trains, user only presses "Run all")
`notebooks/train_psl_v3.ipynb` (Kaggle/Colab free GPU, < 3 h), plus `docs/HOW_TO_RUN_THE_NOTEBOOK.md`.

- **Data:** licensed PSL datasets + Stage 1 web-learned clips. Split by signer/source (a source's clips never
  appear in both train and test). Where signer IDs are missing, cluster signers by appearance-free cues
  (body proportions from pose) and label the split "weaker" if that is the best possible.
- **Encoder pretraining:** self-supervised (masked-landmark modelling / contrastive) on all licensed sign
  data, including ASL data whose licence allows `pretrain` — no ASL labels carried over.
- **Model:** start from the ISLR 1st-place recipe that already works in the baseline (1D depthwise conv +
  transformer blocks over landmark sequences, 543-point input), extended with features v2 hand-to-hand and
  hand-to-face distances. Compare against a GRU baseline. Report both.
- **Training tricks:** heavy augmentation (speed, temporal crop, rotation, scale, shift, mirroring for
  left-handers, random hand/face dropout), label smoothing, mixup on landmarks, EMA weights, class-balanced
  sampling, an explicit "unknown / not a sign" class, temperature calibration.
- **Fingerspelling:** Urdu alphabet head (UAlpha40) and English letters, as a separate small model.
- **Export:** TFLite fp16 and int8 (dynamic range), checked for accuracy loss ≤ 1 point; a versioned bundle
  (weights + manifest: classes, tiers, feature version, metrics, licence IDs, SHA-256). Must run on LiteRT.js
  in the existing Web Worker with the same input layout as the baseline.
- **Report** `reports/psl_v3.md`: per-sign top-1/top-5, one- vs two-handed, left- vs right-dominant,
  internet-learned vs dataset signs, calibration curve, confusion pairs, latency. Tier A only for signs
  passing the gate; the rest Tier B.
- **Gate:** bundle loads in web, Python and Flutter with identical top-1 on the parity clip set.

### Stage 3 — Continuous signing and two-way translation
- **Continuous sign → sentence:** sliding-window recognition over the segmenter + CTC or a
  sequence model trained on concatenated isolated signs (and real continuous data if any licensed set
  exists); gloss sequence → Urdu/English sentence.
- **Sentence builder (AI):** rules first (Phase 6), then a small language model that may reorder and
  inflect but never adds meaning; raw glosses always shown underneath. On-device model where the device
  can run it; an online LLM only if the user switches it on.
- **Text/speech → PSL:** Urdu/English text or speech (browser speech recognition, offline where supported)
  → gloss → reference clips played in sequence, labelled "word-by-word aid". Prepare a landmark-driven
  avatar from the same clips as a later option.
- **Conversation view:** split screen, quick phrases, emergency panel.

### Stage 4 — AI autopilot inside the app
Implement fast-track section 3 fully, on the device, with one Settings switch (on by default):
dictionary-clip prototype index (hundreds of Tier B signs from day one), personal adaptation from the user's
confirmed suggestions (stays on the device), 5-second self-calibration (lighting, distance, framing,
dominant hand), AI helper chat (only uses the app's own vocabulary and clips; says "I don't know"), and
`tools/auto_improve.py` that reruns Stage 1 + Stage 2 and ships a new bundle only if every gate number improves.
- **Gate:** fresh install recognises signs with no training screen anywhere; `reports/autopilot_v1.md`
  measures accuracy before/after 20 confirmed examples.

### Stage 5 — Fast, accurate, polished website (performance stage)
Hit the budgets in section 5 and keep the hand-crafted design rules of fast-track Stage 5 (warm, local,
Deaf-first, Urdu Nastaliq, no "AI look"). Required techniques:
- Inference in a Web Worker (already), **WebGPU delegate when available**, WASM SIMD + threads fallback
  (needs COOP/COEP headers — set them on the host; if the host can't, use a cross-origin-isolation
  service worker), CPU fallback last. Detect and pick automatically.
- Run hand landmarks every frame, face/pose at a lower rate when the user is still; skip the face model in
  modes that don't need it. Reuse video frames (`requestVideoFrameCallback`), no canvas copies on the main thread.
- Lazy-load models after first paint with a progress bar; cache models/WASM with a service worker
  (versioned by SHA-256) so second visits start instantly and work offline; Brotli; immutable cache headers
  on hashed assets; code-split ASL/PSL/translator routes; preload only what the first screen needs.
- Installable PWA, works in airplane mode after first load.
- Error handling: camera denied, no WebGPU, low-end phone (auto-switch to lighter models), slow network.
- Playwright tests: camera smoke with a fake video, offline test, Lighthouse CI on every PR.
- **Gate:** budgets met on a named laptop and a named mid-range Android phone; WCAG 2.2 AA pass.

### Stage 6 — Exhibition kit and final report
Do Stage 7 of `docs/prompts/fast-track.md` (exhibition mode, pitch, judge Q&A, poster text, limitations slide, cited statistics),
plus `reports/final_v3.md`: baseline vs new model on the same sets, coverage per tier, web-learn totals,
performance numbers, all with dataset, split, device and date.
- **Gate:** I read `reports/final_v3.md` and reply "release".

### Stage 7 — Final release: update the live website with the output of the project
This is the last step, done only after Stages 0–6 have passed their gates and I have replied "release".
The live website must then show **everything the project produced**, not just a new build.

**A. Output that must be on the live website** (each one reachable from the home screen):
- The new PSL recogniser bundle from Stage 2, with every sign marked Tier A "Recognised" or Tier B
  "Suggested — please confirm", and "Community dataset — not yet validated" where no Deaf validator signed off.
- ASL mode (the protected baseline, or the measured better model), clearly labelled ASL.
- Urdu and English fingerspelling.
- Continuous signing → Urdu/English sentence, with the raw glosses underneath.
- Text/speech → PSL reference clips (word-by-word aid) and the conversation view with quick and emergency phrases.
- The AI autopilot: self-calibration, personal adaptation, sentence builder and helper chat, behind the
  Settings switch.
- The full vocabulary, including every sign learned from internet videos in Stage 1, with its reference clip
  where the licence allows the clip to be shown (otherwise "no clip yet").
- Exhibition mode from Stage 6.
- A **"How well it works" page** built at build time from the committed reports (`reports/psl_v3.md`,
  `asl_mode_v1.md`, `web_learn_vN.md`, `autopilot_v1.md`, `final_v3.md`): accuracy per sign and tier,
  one- vs two-handed, speed on the named devices, dataset/split/date for every number. Numbers are read
  from the report files, never typed by hand; a test fails if the page and the reports disagree.
- A **"Credits and licences" page** generated from `data/LICENSES.yaml`, with every attribution the licences require.
- A **download link to the offline shared copy** (`npm run build:shared` zip, the Start SignBridge.bat
  version) attached to a GitHub Release `v3.0.0`, with short Windows instructions.
- Release notes on a "What's new" page and in the GitHub Release: what changed since the old site.

**B. How to publish it**

1. **What exists today.** The site is GitHub Pages, deployed by `.github/workflows/website.yml` on every push
   to `main`, served at `https://shaafrajput06-tech.github.io/SignBridge/` with base path `/SignBridge/`
   (`web/src/paths.js`, `vite.config.js`). Keep this workflow; extend it, don't replace it.
2. **Release flow.** Bring the pull request from `v3/master` to `main` up to date with the latest `main`,
   put a summary of every stage and the measured numbers in its description, and let the workflow's checks
   run on it. **I merge it [ME]**; the merge publishes the new site. Never push directly to `main`.
   Then tag `v3.0.0` and publish the GitHub Release with the offline zip and the release notes.
3. **GitHub Pages limits.** Pages cannot send custom headers, so for threaded WASM (COOP/COEP) use a
   cross-origin-isolation service worker, tested on Chrome, Edge, Safari and Android Chrome. Large model files
   are fetched by `tools/fetch_assets.py` during the build (size + SHA-256 checked) or stored as GitHub
   Release assets — never committed to git history without Git LFS. Keep the whole build under the Pages
   size limit (1 GB site, 100 MB per file).
4. **Domain → "signbridge".** A web address needs an extension, so offer me these and let me choose [ME]:
   - **Free:** a GitHub organisation or account named `signbridge` (if available) hosting the site at
     `https://signbridge.github.io/` — transfer the repo there, set base path to `/`, and update links.
   - **Own domain:** check availability and price of e.g. `signbridge.pk`, `signbridge.com.pk`,
     `signbridge.app`, `signbridge.org`. After I buy it: add `CNAME` to the build output, set
     Settings → Pages → Custom domain, write the exact DNS records for my registrar (A/AAAA for the apex,
     CNAME for `www` → `shaafrajput06-tech.github.io`), verify the domain in GitHub, tick "Enforce HTTPS",
     change the base path from `/SignBridge/` to `/`.
   - Either way: update every hard-coded URL, the PWA manifest, service worker scope, `sitemap.xml`,
     `robots.txt`, Open Graph tags, README, `docs/WEBSITE.md` and the Flutter app's links; keep branding
     **SignBridge** everywhere. GitHub redirects the old `github.io/SignBridge` address only when the custom
     domain is on the same account — if not, leave a small redirect page at the old address.
5. **After it goes live, check the live site, not the preview:** open every item in list A and confirm it
   works; run the camera on a laptop and a phone (one PSL sign, one ASL sign, one two-handed sign, one
   sentence); confirm it works offline after the first visit; check `/ci/status.json`; run Lighthouse; and
   confirm the "How well it works" numbers match the reports. Write `reports/release_v3.md` with the results
   and screenshots. If anything is broken, fix it on a branch and release again; if a fix can't be made
   quickly, revert the merge so the old site comes back, and tell me.
6. **Gate:** the new site is live on the SignBridge address over HTTPS with every output in list A working,
   the old URL reaches the new one, the GitHub Release has the offline zip, and `reports/release_v3.md`
   is committed. Then tell me in plain words: the live address, what's new, and anything still marked
   Tier B or "not yet validated".

---

## 4. Accuracy targets (aims, not claims)

Report what you measure; if a target is missed, say so with the number and the best next step.

| Metric | Target |
|---|---|
| ASL mode top-1 on GISLR rerun set (signer-independent) | ≥ baseline measurement; never lower |
| PSL isolated top-1, signer/source-independent, Tier A signs | ≥ 90 % |
| PSL top-5, all Tier B signs | ≥ 85 % |
| Wrong word spoken aloud (confidence above "Pretty sure" but wrong) | ≤ 2 % |
| One-handed vs two-handed gap | ≤ 5 points |
| Left- vs right-dominant gap | ≤ 3 points |
| Signs covered (Tier A + B) | 64 vocabulary entries first, then 500+ |

## 5. Performance budgets (website)

| Metric | Laptop (Chrome) | Mid-range Android (Chrome) |
|---|---|---|
| First load LCP | ≤ 2.0 s | ≤ 2.5 s (4G) |
| Repeat visit to camera-ready | ≤ 1.5 s | ≤ 2.5 s |
| Landmark tracking | ≥ 30 fps | ≥ 20 fps |
| End of sign → word on screen | ≤ 150 ms | ≤ 300 ms |
| Main-thread long tasks during recognition | none > 50 ms | none > 100 ms |
| Lighthouse Performance / Accessibility / Best Practices | ≥ 90 / 100 / 100 | ≥ 85 / 100 / 100 |
| Works offline after first visit | yes | yes |

## 6. Working with me
- I am a beginner on Windows. After each stage, tell me in plain words what changed, how to run it, how to
  test it on my phone, and the live URL.
- Give complete files, never fragments. Keep every test green. Small commits; no data, model weights
  without LFS, keys or secrets in git (use GitHub Actions secrets for API keys such as the YouTube Data API).
- Steps that need me — accounts, buying the domain, DNS, API keys, sending permission emails, pressing
  "Run all", measuring on my devices — are marked **[ME]**, fully prepared, and listed at the end of each stage.
- Never invent a number, a licence or a sign. If something can't be done, say so straight away and give the
  best alternative.