# Phase 3 — Pretrained recogniser and model bundle

OBJECTIVE
Train a landmark-sequence model that recognises Tier A PSL signs out of the box, knows when it does
not know, and runs on-device everywhere. Ship it inside the app as a signed, versioned bundle.

INPUTS
Phase 2 dataset release + splits + ledger, feature_spec_v2.json, train_model.py (keep as baseline).

TASKS
1. Baselines first: run the v1 SVM/RF pipeline on per-frame v2 features and a GRU on sequences, so
   every later number has a comparison.
2. Encoder: a compact hybrid of depthwise temporal 1D-convolutions and transformer blocks over
   resampled sequences (start: 64 frames, 2-8 M parameters), with a presence mask for missing hands.
   Inputs: positions, velocities, hand-to-face and hand-to-hand distances from feature spec v2.
3. Self-supervised pretraining: masked-landmark modelling on all unlabeled sequences the ledger allows
   for pretrain_encoder (PSL recordings, plus ASL sets such as PopSign if licensed). No ASL labels.
4. Fine-tuning on PSL train signers with two heads:
   (a) classification head over Tier A glosses;
   (b) embedding head (supervised-contrastive or ArcFace) used by Phase 4 retrieval.
   Augment: speed and temporal resampling, small affine and rotation, landmark dropout, frame drop,
   hand-swap only for glosses marked handedness-symmetric.
5. Calibration and rejection (fixes F3, F7): temperature scaling on validation signers; an "unknown"
   decision from calibrated confidence plus embedding distance; a non-sign/background class trained on
   idle and transitional motion. Thresholds chosen on validation, reported on test.
6. Evaluation (signer-independent test set only): top-1, top-5, macro-F1, per-gloss accuracy,
   confusion pairs, expected calibration error, false-accept rate on unknown signs and non-signs,
   accuracy by device type, lighting and signer group. Write reports/eval_vN.md.
7. Promotion rule: a gloss becomes Tier A only if its test accuracy and false-accept meet the gate
   AND a Deaf validator approved its reference. Others stay B.
8. Export: ONNX (onnxruntime-web with WebGPU/WASM, onnxruntime in Python) and LiteRT/TFLite (Flutter).
   int8 quantisation if the accuracy drop is <= 1 point. Parity test: Python vs ONNX vs LiteRT logits.
9. Bundle: models/psl-recogniser-vN/ with weights, manifest.json (glosses + tiers, feature version,
   metrics, ledger IDs, SHA-256), model card. Loader in ml_engine/model_loader.py, web and Flutter;
   clients refuse unknown feature versions. The app ships with this bundle: no setup needed.
10. [HUMAN] GPU time for pretraining and fine-tuning; review of the eval report by the Deaf partner.

DELIVERABLES
Training code (training/), baselines, eval report, bundle + model card, loaders, export parity tests.

ACCEPTANCE GATE (signer-independent test set)
- Tier A: top-1 >= 90% macro over Tier A glosses, top-5 >= 97%.
- Expected calibration error <= 0.05; false-accept on unknown signs and non-signs <= 5% at the
  chosen threshold.
- Model <= 10 MB after quantisation; <= 30 ms per inference on a mid-range laptop CPU (record device).
- Beats both baselines; any gloss below the gate is listed and stays Tier B.

OUT OF SCOPE
Continuous signing (Phase 5), UI redesign (Phase 7).
