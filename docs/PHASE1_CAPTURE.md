# Phase 1: holistic capture and the v2 data contract

This is the technical reference for what Phase 1 added. The contract itself is
`shared_data/feature_spec_v2.json`; if this page and the spec disagree, the spec wins.

## Pipeline

```
camera frame ──rotate upright──▶ Pose + Hand + Face landmarkers ──▶ raw landmarks
   (F4 rule)                       (MediaPipe, VIDEO mode)              │
                                                                         ▼
                                                    canonicalize_frame (features_v2)
                                                    unmirrored view, anatomical sides,
                                                    9 pose + 69 face points, 2 hands
                                                                         │
                         ┌───────────────────────────────────────────────┤
                         ▼                                               ▼
              write_recording (.npz)                         sequence_features
              one file per sign instance                     971 values per frame
```

| Step | Python | JavaScript | Dart |
|---|---|---|---|
| Rotation rule | `ml_engine/capture_v2.py` `correction_rotation_degrees` | not needed (browser frames are upright) | `mobile/lib/frame_rotation.dart` |
| Landmarking | `ml_engine/capture_v2.py` `SplitLandmarkerBackend` | `web/src/capture_v2.js` | Phase 7 (phone still sends frames to the server) |
| Canonical frame + features | `ml_engine/features_v2.py` (reference) | `web/src/features_v2.js` | Phase 7 |
| Recording files | `ml_engine/recording_v2.py` | Phase 2 studio posts to the API | Phase 2 |

## Decisions and why

- **Pose + Hand + Face landmarkers instead of Holistic.** The Python `mediapipe` package (0.10.32 in
  this workspace) has no Holistic Landmarker. The browser could use one, but then the two platforms
  would run different models. Both use the same three `.task` files.
- **Canonical view is unmirrored.** It is what the camera sees and what MediaPipe's pose and face
  models are trained on. Mirroring is only for display. Mirrored input is un-mirrored, and pose and
  face left/right points are swapped back. Whether MediaPipe really behaves this way on mirrored
  images is what the F12 check measures on real clips.
- **Hands are assigned by the nearer pose wrist,** not by MediaPipe's handedness label, because the
  label assumes selfie input and is often wrong for two-handed signs. Without a pose, the label is
  used (swapped for unmirrored input); if labels clash, image position decides. The method is stored
  per frame (`hand_assignment`).
- **Handedness is data.** v1 mirrored every left hand into a right hand; v2 never does. Phase 3 may
  swap hands as augmentation only for glosses marked handedness-symmetric.
- **One reference per sequence.** Positions are centred on the component-wise median shoulder
  midpoint and scaled by the median shoulder width over the sequence. Per-frame centring would also
  remove real movement relative to the body, and the median ignores single-frame jitter. With no pose
  in the sequence, a documented fallback is used and the `reference_from_pose` mask is 0.
- **z is never mixed across parts.** Each MediaPipe model has its own depth origin, so all distances
  use x and y only.
- **Plain arithmetic for parity.** Python and JavaScript use the same loops and `sqrt` (no `hypot`,
  no numpy), so they agree exactly on the fixture (largest difference 0, tolerance 1e-6).

## Recording format v2

One `.npz` per sign instance: `points` (T x 120 x 3, float32, NaN where absent), `present` (T x 4),
`pose_visibility`, `timestamps_ms`, `hand_assignment`, and UTF-8 JSON `meta`. Required metadata:
gloss, pseudonymous signer ID, session, device ID, rotation applied, input mirrored, image size, fps
(measured from timestamps), frame count, consent ID, `consent_recorded`, `instance_unit`,
`video_stored`. Metadata is an allowlist, so names cannot be stored under any other key;
`video_stored: true` needs `video_consent: true`; live captures need `consent_recorded: true`.
Files are byte-identical for the same input.

Records converted from v1 keep the 63 v1 values exactly in `v1_features` and carry no v2 points.
They are marked `consent_recorded: false` (v1 kept no consent record) and `instance_unit: frame`
(one camera frame, not a whole sign), and they flag phone rows (collected before the F4 fix) and
anonymous rows. `training_use_refusal(meta)` returns the reason a record must stay out of training;
Phase 2 training and export code must call it, and must split v1 records by signer, never by record.

## How to check

```
python tools/run_all_tests.py                         # everything this machine can run
python tests/golden/make_v2_golden.py                 # only when features v2 change on purpose
python tools/convert_v1_to_v2.py --signer-key-file K  # convert data/sign_data.csv
python tools/check_mirroring_f12.py --clips DIR       # F12 on real clips [HUMAN records them]
```

Frame-rate measurement: `npm run dev` in `web/` (after `npm install` and placing the pose and face
models in `models/`), then open `http://localhost:5173/bench.html`, run 30 s, and copy the result.
