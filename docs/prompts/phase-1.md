# Phase 1 — Holistic capture and the v2 data contract

OBJECTIVE
Replace single-frame, single-hand capture with time sequences of both hands, upper body and a face
subset, identical on Python, web and Flutter. Fix the capture bugs that would poison training data.

INPUTS
CLAUDE.md, docs/CONTEXT.md, ml_engine/features.py, web/src/vision.js, mobile/lib/main.dart,
tests/golden/, docs/BASELINE.md (F4, F5, F12).

TASKS
1. Add a capture layer `ml_engine/capture_v2.py` and `web/src/capture_v2.js` using MediaPipe
   Holistic Landmarker (or Pose + Hand + Face landmarkers where Holistic is unavailable). Per frame keep:
   2 x 21 hand points, upper-body pose points (nose, shoulders, elbows, wrists, hips), and a fixed face
   subset (lips, eyebrows, eye corners, nose tip; list the indices in one shared JSON file).
2. Define features v2 in `ml_engine/features_v2.py` and a JSON spec `shared_data/feature_spec_v2.json`:
   coordinates centred on the shoulder midpoint, scaled by shoulder width, a presence mask per hand,
   handedness kept as data (never silently mirrored for two-handed signs), timestamps in ms.
3. Define the recording format v2: one file per sign instance (`.npz` or Parquet) with the frame array,
   mask, fps, gloss ID, signer ID (pseudonymous), session, device, camera orientation, consent ID.
   Write a converter that wraps v1 CSV rows as 1-frame v2 records so nothing is lost.
4. Fix F4: rotate Flutter frames by sensor orientation before landmarking; add a rotation test.
   Fix F5: report the real error class in the Flutter UI and logs.
5. Verify F12 on real recordings: [HUMAN] record 20 short clips each of left- and right-hand signing;
   the agent writes the check and reports the result.
6. Golden fixtures v2: synthetic + recorded sequences; parity tests Python == JS (== Dart where
   Flutter is available) to 1e-6.
7. Keep v1 demo rules and features working unchanged behind a `feature_version` switch.

DELIVERABLES
capture_v2 (Python, JS), features_v2, feature_spec_v2.json, recording format + converter,
Flutter rotation and error fixes, v2 golden fixtures and parity tests, updated docs.

ACCEPTANCE GATE
- All Phase 0 tests pass; v2 parity tests pass on 1,000+ fixture frames.
- Web capture runs at >= 24 fps on a mid-range laptop browser (measure and record device + fps).
- Rotated-frame test: identical features for upright and rotated input after correction.
- No image or video is written to disk by any capture path (test it).

OUT OF SCOPE
Model training, new UI, translation.
