# Publish the Inference Baseline v1 release and tag [ME] (about 3 minutes)

Claude's session may not create GitHub releases or push tags, so this one step is yours. It stores the
frozen baseline zip on GitHub, so any laptop and every CI run can download it
(`python tools/baseline_v1.py restore --download`), and it creates the tag `inference-baseline-v1`
that master-v3.md section 0 asks for.

You need the `SignBridge.zip` you already have (the shared copy of 2026-11-19, 57,784,700 bytes).

1. Rename the file to **`SignBridge-shared-copy-v1.zip`** (right-click > Rename). The download tool
   looks for exactly this name.
2. Open <https://github.com/shaafrajput06-tech/SignBridge/releases/new> (signed in).
3. **Choose a tag:** type `inference-baseline-v1` and click **+ Create new tag: inference-baseline-v1
   on publish**. **Target:** `main` (do this before the v3 pull request is merged, so the tag marks
   the old live code, commit `42a572f`).
4. **Release title:** `Inference Baseline v1 (frozen reference)`.
5. **Description:** paste:

   > Frozen reference, not a new version of the app. The built offline shared copy of 2026-11-19,
   > kept so every new model can be compared with it side by side (master-v3.md section 0).
   > SHA-256 of the zip: c1612538cfd1e30951db7a2b0be33d061bcd1e49436f2dffd2219ebf58a0f0d4.
   > Credits and licences: README.txt inside the zip. The PSL clips come from a community dictionary
   > and have not yet been validated by Deaf signers.

6. Drag `SignBridge-shared-copy-v1.zip` into **Attach binaries**. Wait for the upload to finish.
7. Tick **Set as a pre-release**. Click **Publish release**.

Check: on the laptop, `python tools/baseline_v1.py restore --download` prints
`Baseline: 66 of 66 files present and correct.` If the zip were a different file, the tool refuses it
(it checks the SHA-256 above).
